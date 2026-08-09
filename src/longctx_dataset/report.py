"""Pilot report generation (markdown + machine-readable JSON).

The report exists to answer one question: *is this pipeline ready to scale to 500
question families?* It therefore leads with what failed and what could not be built, not
with headline counts. Full contexts are never dumped into the markdown -- only their
measured properties.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import PipelineConfig
from .distractors.taxonomy import describe_taxonomy
from .schemas import Instance, QuestionFamily, QuestionType, UnavailableVariant
from .storage.io import iter_jsonl, iter_models, read_json, read_models, write_json
from .storage.manifests import utc_now

EXAMPLE_PREFERENCE = [
    QuestionType.RETRIEVAL_CALCULATION,
    QuestionType.UNANSWERABLE,
    QuestionType.TEMPORAL_VERSION,
    QuestionType.ENTITY_UNIT_BINDING,
    QuestionType.DIRECT_RETRIEVAL,
]


def _fmt_table(headers: List[str], rows: List[List[Any]]) -> str:
    if not rows:
        return "_(none)_\n"
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return "\n".join(out) + "\n"


def _length_label(n: int) -> str:
    return f"{n // 1024}K" if n % 1024 == 0 else str(n)


def generate_report(cfg: PipelineConfig, n_examples: int = 4, log=print) -> Tuple[Path, Path]:
    from .pipeline import (families_path, instances_path, load_retrievals,
                           manifest_path, unavailable_path, validation_path)

    cfg.ensure_dirs()
    families = read_models(families_path(cfg), QuestionFamily)
    unavailable = [UnavailableVariant.model_validate(r) for r in iter_jsonl(unavailable_path(cfg))]
    retrievals = load_retrievals(cfg)
    validation = read_json(validation_path(cfg)) if validation_path(cfg).exists() else {}
    manifest = read_json(manifest_path(cfg)) if manifest_path(cfg).exists() else {}

    # Stream instances: their `context` fields are far too large to hold in memory.
    inst_by_family: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    per_length_tokens: Dict[int, List[int]] = defaultdict(list)
    positions: List[float] = []
    distractor_totals: Counter = Counter()
    inst_by_domain: Counter = Counter()
    inst_by_type: Counter = Counter()
    n_instances = 0
    for row in iter_jsonl(instances_path(cfg)):
        n_instances += 1
        inst_by_family[row["question_family_id"]].append({
            k: row.get(k) for k in (
                "instance_id", "context_length_nominal", "context_tokens_actual",
                "target_position_relative", "target_evidence_start_token",
                "target_evidence_end_token", "distractor_counts", "context_record_ids",
                "context_sha256", "tokenizer",
            ) if k != "context_record_ids"
        } | {"n_records": len(row.get("context_record_ids") or [])})
        per_length_tokens[row["context_length_nominal"]].append(row["context_tokens_actual"])
        if row.get("target_position_relative") is not None:
            positions.append(row["target_position_relative"])
        distractor_totals.update(row.get("distractor_counts") or {})
        inst_by_domain[row["domain"]] += 1
        inst_by_type[row["question_type"]] += 1

    stats = validation.get("stats", {})
    checks = validation.get("checks", [])
    payload = _build_json(cfg, families, unavailable, retrievals, validation, manifest,
                          n_instances, per_length_tokens, positions, distractor_totals,
                          inst_by_domain, inst_by_type)
    examples = _pick_examples(families, inst_by_family, n_examples)
    payload["representative_families"] = examples

    json_path = cfg.report_dir / f"{cfg.name}_report.json"
    md_path = cfg.report_dir / f"{cfg.name}_report.md"
    write_json(json_path, payload)
    md_path.write_text(_render_markdown(cfg, payload, checks, examples), encoding="utf-8")
    return md_path, json_path


def _describe(values: List[float], decimals: int = 1) -> Dict[str, Any]:
    if not values:
        return {"n": 0}
    s = sorted(values)
    n = len(s)

    def pct(p: float) -> float:
        return round(float(s[min(n - 1, max(0, int(round(p * (n - 1)))))]), decimals)

    return {"n": n, "min": round(float(s[0]), decimals), "p25": pct(0.25),
            "median": pct(0.5), "p75": pct(0.75), "max": round(float(s[-1]), decimals),
            "mean": round(sum(s) / n, decimals)}


def _build_json(cfg, families, unavailable, retrievals, validation, manifest, n_instances,
                per_length_tokens, positions, distractor_totals, inst_by_domain, inst_by_type
                ) -> Dict[str, Any]:
    fam_by_domain = Counter(f.domain.value for f in families)
    fam_by_type = Counter(f.question_type.value for f in families)
    configured = {d.value: c.n_families for d, c in cfg.domains.items() if c.enabled}

    return {
        "dataset_name": cfg.name,
        "generated_at": utc_now(),
        "config_path": str(cfg.config_path) if cfg.config_path else None,
        "config_hash": cfg.config_hash,
        "seed": cfg.seed,
        "git_commit": manifest.get("git_commit"),
        "schema_version": cfg.schema_version,
        "tokenizer": {
            "id": validation.get("stats", {}).get("tokenizer") or cfg.tokenizer.id,
            "version": validation.get("stats", {}).get("tokenizer_version"),
            "is_approximate": validation.get("stats", {}).get("tokenizer_is_approximate"),
        },
        "context_lengths": cfg.context.lengths,
        "target_position": cfg.context.target_position,
        "position_tolerance": cfg.context.position_tolerance,
        "min_fill_ratio": cfg.context.min_fill_ratio,
        "sources": [r.model_dump(mode="json") for r in retrievals],
        "normalized_records_by_domain": validation.get("stats", {}).get("normalized_records_by_domain", {}),
        "question_families": {
            "total": len(families),
            "configured_target": configured,
            "by_domain": dict(fam_by_domain),
            "by_question_type": dict(fam_by_type),
            "answerable": sum(1 for f in families if f.answerable),
            "unanswerable": sum(1 for f in families if not f.answerable),
            "by_template": dict(Counter(f.generation_metadata.template_id for f in families)),
        },
        "instances": {
            "total": n_instances,
            "by_domain": dict(inst_by_domain),
            "by_question_type": dict(inst_by_type),
            "by_length": {_length_label(k): len(v) for k, v in sorted(per_length_tokens.items())},
            "token_distribution_by_length": {
                _length_label(k): _describe(v) for k, v in sorted(per_length_tokens.items())
            },
            "fill_ratio_by_length": {
                _length_label(k): _describe([t / k for t in v], 4)
                for k, v in sorted(per_length_tokens.items())
            },
            "target_position_distribution": _describe(positions, 4),
        },
        "distractors": {
            "totals_by_type": dict(distractor_totals),
            "taxonomy": describe_taxonomy(),
        },
        "unavailable_variants": {
            "total": len(unavailable),
            "by_length": dict(Counter(_length_label(u.context_length_nominal) for u in unavailable)),
            "by_domain": dict(Counter(u.domain.value for u in unavailable)),
            "by_reason_code": dict(Counter(u.reason_code for u in unavailable)),
            "detail": [u.model_dump(mode="json") for u in unavailable[:80]],
        },
        "validation": {
            "counts": validation.get("counts", {}),
            "has_critical_failures": validation.get("has_critical_failures"),
            "checks": [
                {k: c.get(k) for k in ("check_id", "name", "severity", "passed", "skipped",
                                       "n_checked", "n_failed", "message")}
                for c in validation.get("checks", [])
            ],
            "failure_detail": {
                c["check_id"]: c.get("failures", [])[:10]
                for c in validation.get("checks", []) if not c.get("passed")
            },
        },
        "source_limitations": _source_limitations(retrievals, unavailable),
    }


def _source_limitations(retrievals, unavailable) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in retrievals:
        if r.blocked:
            out.append({"domain": r.domain, "kind": "BLOCKED", "detail": r.blocker_reason})
        for err in r.errors[:10]:
            out.append({"domain": r.domain, "kind": "REQUEST_ERROR", "detail": err})
    if unavailable:
        by_domain = Counter(u.domain.value for u in unavailable)
        for domain, n in by_domain.items():
            out.append({
                "domain": domain, "kind": "CONTEXT_POOL_EXHAUSTED",
                "detail": f"{n} context variant(s) could not be built from authentic records alone",
            })
    return out


def _pick_examples(families, inst_by_family, n: int) -> List[Dict[str, Any]]:
    """One representative family per question type, preferring the most complex first."""
    chosen: List[QuestionFamily] = []
    by_type: Dict[QuestionType, List[QuestionFamily]] = defaultdict(list)
    for f in families:
        by_type[f.question_type].append(f)
    for qt in EXAMPLE_PREFERENCE:
        candidates = sorted(by_type.get(qt, []), key=lambda f: f.question_family_id)
        # Prefer a domain not already represented, so the examples span sources as well
        # as question types.
        shown_domains = {f.domain for f in chosen}
        pick = next((f for f in candidates if f.domain not in shown_domains), None) or (
            candidates[0] if candidates else None)
        if pick is not None and len(chosen) < n:
            chosen.append(pick)

    out = []
    for fam in chosen:
        variants = sorted(inst_by_family.get(fam.question_family_id, []),
                          key=lambda i: i["context_length_nominal"])
        out.append({
            "question_family_id": fam.question_family_id,
            "domain": fam.domain.value,
            "question_type": fam.question_type.value,
            "template_id": fam.generation_metadata.template_id,
            "question": fam.question,
            "answerable": fam.answerable,
            "gold_answer": fam.gold_answer,
            "gold_answer_normalized": fam.gold_answer_normalized,
            "answer_type": fam.answer_type.value,
            "answer_unit": fam.answer_unit,
            "numeric_tolerance": fam.numeric_tolerance,
            "gold_evidence": [
                {
                    "record_id": e.record_id, "role": e.role, "entity": f"{e.entity_name} [{e.entity_id}]",
                    "concept": f"{e.concept_label} [{e.concept}]", "period": e.period,
                    "value": e.value, "unit": e.unit, "version": e.version,
                    "source_url": e.source_url,
                }
                for e in fam.gold_evidence
            ],
            "calculation_spec": fam.calculation_spec.model_dump(mode="json") if fam.calculation_spec else None,
            "unanswerable_spec": fam.unanswerable_spec.model_dump(mode="json") if fam.unanswerable_spec else None,
            "context_variants": [
                {
                    "instance_id": v["instance_id"],
                    "nominal": _length_label(v["context_length_nominal"]),
                    "tokens_actual": v["context_tokens_actual"],
                    "fill_ratio": round(v["context_tokens_actual"] / v["context_length_nominal"], 4),
                    "n_records": v["n_records"],
                    "target_position_relative": v["target_position_relative"],
                    "target_evidence_tokens": [v["target_evidence_start_token"], v["target_evidence_end_token"]],
                    "distractor_counts": v["distractor_counts"],
                    "context_sha256": (v["context_sha256"] or "")[:16],
                }
                for v in variants
            ],
        })
    return out


def _render_markdown(cfg: PipelineConfig, p: Dict[str, Any], checks: List[Dict[str, Any]],
                     examples: List[Dict[str, Any]]) -> str:
    L: List[str] = []
    a = L.append
    v = p["validation"]
    crit = v.get("has_critical_failures")

    a(f"# Pilot report — `{p['dataset_name']}`")
    a("")
    a(f"_Generated {p['generated_at']} · config `{p['config_path']}` · config hash `{p['config_hash']}` "
      f"· seed `{p['seed']}` · git `{(p.get('git_commit') or 'n/a')[:12]}`_")
    a("")
    a("> **Scope.** This phase generates and validates the dataset only. No LLM has been run "
      "against it, no hallucination scoring has been performed, and no statistical analysis or "
      "research conclusions are presented here.")
    a("")

    a("## 1. Verdict")
    a("")
    counts = v.get("counts", {})
    verdict = "NOT READY — critical validation failures" if crit else "READY for scale-up review"
    a(f"**Status: {verdict}**")
    a("")
    a(f"- Validation: {counts.get('passed', 0)}/{counts.get('total', 0)} checks passed, "
      f"{counts.get('critical_failed', 0)} critical failures, {counts.get('warning_failed', 0)} warnings.")
    a(f"- {p['question_families']['total']} question families → {p['instances']['total']} context instances.")
    a(f"- {p['unavailable_variants']['total']} context variants could not be built from authentic "
      f"records and were recorded as unavailable rather than padded.")
    a("")

    a("## 2. Source retrieval")
    a("")
    rows = []
    for s in p["sources"]:
        rows.append([
            s["domain"], s["source"], "BLOCKED" if s["blocked"] else "ok",
            s["n_requests"], s["n_raw_payloads"], s["n_raw_records"],
            p["normalized_records_by_domain"].get(s["domain"], 0),
            len(s["errors"]), s["retrieved_at"],
        ])
    a(_fmt_table(
        ["domain", "source", "status", "requests", "payloads", "raw records", "normalized", "errors", "retrieved at"],
        rows))
    if p["source_limitations"]:
        a("### Source / API limitations encountered")
        a("")
        for lim in p["source_limitations"][:25]:
            a(f"- **{lim['domain']} · {lim['kind']}** — {lim['detail']}")
        a("")

    a("## 3. Question families")
    a("")
    qf = p["question_families"]
    a(_fmt_table(["domain", "configured target", "generated"],
                 [[d, qf["configured_target"].get(d, 0), qf["by_domain"].get(d, 0)]
                  for d in sorted(set(qf["configured_target"]) | set(qf["by_domain"]))]))
    a("")
    total = qf["total"] or 1
    a(_fmt_table(["question type", "families", "share"],
                 [[k, n, f"{n / total:.0%}"] for k, n in sorted(qf["by_question_type"].items())]))
    a("")
    a(f"Answerable: **{qf['answerable']}** · Unanswerable: **{qf['unanswerable']}**")
    a("")
    a("<details><summary>Families by template</summary>")
    a("")
    a(_fmt_table(["template", "families"], [[k, n] for k, n in sorted(qf["by_template"].items())]))
    a("</details>")
    a("")

    a("## 4. Context instances")
    a("")
    tok = p["tokenizer"]
    a(f"Tokenizer: `{tok['id']}` ({tok.get('version') or 'version n/a'})"
      + ("  ⚠️ **approximate backend**" if tok.get("is_approximate") else ""))
    a("")
    rows = []
    for label in [_length_label(n) for n in p["context_lengths"]]:
        d = p["instances"]["token_distribution_by_length"].get(label, {"n": 0})
        f = p["instances"]["fill_ratio_by_length"].get(label, {})
        rows.append([label, d.get("n", 0), d.get("min"), d.get("median"), d.get("max"),
                     f.get("min"), f.get("median")])
    a(_fmt_table(["nominal", "instances", "min tokens", "median tokens", "max tokens",
                  "min fill", "median fill"], rows))
    a("")
    tp = p["instances"]["target_position_distribution"]
    a(f"**Target-evidence position** (target {p['target_position']} ± {p['position_tolerance']}): "
      f"n={tp.get('n', 0)}, min={tp.get('min')}, median={tp.get('median')}, max={tp.get('max')}, "
      f"mean={tp.get('mean')}")
    a("")

    a("## 5. Distractors")
    a("")
    dt = p["distractors"]["totals_by_type"]
    tot = sum(dt.values()) or 1
    a(_fmt_table(["distractor type", "records placed", "share", "definition"],
                 [[k, n, f"{n / tot:.1%}", p["distractors"]["taxonomy"].get(k, "")]
                  for k, n in sorted(dt.items(), key=lambda kv: -kv[1])]))
    a("")

    a("## 6. Unavailable context variants")
    a("")
    uv = p["unavailable_variants"]
    if uv["total"] == 0:
        a("None — every configured length was built from authentic same-domain records.")
    else:
        a(_fmt_table(["nominal length", "count"], [[k, n] for k, n in sorted(uv["by_length"].items())]))
        a("")
        a(_fmt_table(["domain", "count"], [[k, n] for k, n in sorted(uv["by_domain"].items())]))
        a("")
        a("Representative reasons:")
        a("")
        for u in uv["detail"][:6]:
            a(f"- `{u['question_family_id']}` @ {_length_label(u['context_length_nominal'])} "
              f"({u['reason_code']}): {u['reason']}")
    a("")

    a("## 7. Validation results")
    a("")
    rows = []
    for c in sorted(checks, key=lambda x: x["check_id"]):
        status = "SKIP" if c.get("skipped") else ("PASS" if c.get("passed") else f"**FAIL** ({c['severity']})")
        rows.append([c["check_id"], c["name"], c["severity"], status, c.get("n_checked"), c.get("n_failed")])
    a(_fmt_table(["id", "check", "severity", "result", "checked", "failed"], rows))
    a("")
    fd = v.get("failure_detail", {})
    if fd:
        a("### Failure detail (first 10 per check)")
        a("")
        for cid, fails in sorted(fd.items()):
            if not fails:
                continue
            a(f"**{cid}**")
            a("")
            for f in fails:
                a(f"- `{json.dumps(f, sort_keys=True)[:400]}`")
            a("")
    else:
        a("No check produced failures.")
    a("")
    a("Key derived counts:")
    a("")
    a(f"- Duplicate family IDs / instance IDs / question texts: "
      f"{sum(1 for c in checks if c['check_id'] in ('A', 'B') for _ in range(c['n_failed']))}")
    a(f"- Gold-recomputation failures (check D): "
      f"{next((c['n_failed'] for c in checks if c['check_id'] == 'D'), 0)}")
    a(f"- Unanswerable leakage failures (check S): "
      f"{next((c['n_failed'] for c in checks if c['check_id'] == 'S'), 0)}")
    a(f"- Duplicate-answer-source failures (check V): "
      f"{next((c['n_failed'] for c in checks if c['check_id'] == 'V'), 0)}")
    a("")

    a("## 8. Representative question families")
    a("")
    a("_Context strings are deliberately not reproduced here; only their measured properties are._")
    a("")
    for ex in examples:
        a(f"### `{ex['question_family_id']}` — {ex['domain']} / {ex['question_type']}")
        a("")
        a(f"*Template:* `{ex['template_id']}`")
        a("")
        a(f"**Question.** {ex['question']}")
        a("")
        if ex["answerable"]:
            a(f"**Gold answer.** `{ex['gold_answer']}` "
              f"(normalized `{ex['gold_answer_normalized']}`, type {ex['answer_type']}"
              + (f", unit {ex['answer_unit']}" if ex["answer_unit"] else "")
              + (f", tolerance ±{ex['numeric_tolerance']}" if ex["numeric_tolerance"] is not None else "")
              + ")")
        else:
            a(f"**Gold outcome.** `INSUFFICIENT_EVIDENCE` — "
              f"{ex['unanswerable_spec']['reason_code']}")
            a("")
            a(f"> {ex['unanswerable_spec']['reason']}")
        a("")
        if ex["gold_evidence"]:
            a("**Gold evidence.**")
            a("")
            a(_fmt_table(["role", "record id", "entity", "field", "period", "value", "unit"],
                         [[e["role"], f"`{e['record_id']}`", e["entity"], e["concept"],
                           e["period"], e["value"], e["unit"]] for e in ex["gold_evidence"]]))
            a("")
        if ex["calculation_spec"]:
            cs = ex["calculation_spec"]
            a(f"**Calculation.** `{cs['operation']}`: `{cs['formula']}` → raw `{cs['raw_result']}` "
              f"→ rounded `{cs['rounded_result']}` ({cs['round_decimals']} dp)")
            a("")
            a(_fmt_table(["role", "record id", "value used"],
                         [[k, f"`{cs['operands'][k]}`", cs["operand_values"][k]]
                          for k in sorted(cs["operands"])]))
            a("")
        a("**Context variants.**")
        a("")
        a(_fmt_table(["instance", "nominal", "tokens", "fill", "records", "target pos", "evidence tokens", "sha256"],
                     [[f"`{c['instance_id']}`", c["nominal"], c["tokens_actual"], f"{c['fill_ratio']:.3f}",
                       c["n_records"],
                       f"{c['target_position_relative']:.4f}" if c["target_position_relative"] is not None else "n/a",
                       f"{c['target_evidence_tokens'][0]}–{c['target_evidence_tokens'][1]}"
                       if c["target_evidence_tokens"][0] is not None else "n/a",
                       f"`{c['context_sha256']}`"]
                      for c in ex["context_variants"]]))
        a("")

    a("## 9. Reproducibility")
    a("")
    a(_fmt_table(["field", "value"], [
        ["schema version", p["schema_version"]],
        ["config hash", f"`{p['config_hash']}`"],
        ["seed", p["seed"]],
        ["git commit", f"`{p.get('git_commit') or 'n/a'}`"],
        ["tokenizer", f"`{tok['id']}`"],
        ["context lengths", ", ".join(_length_label(n) for n in p["context_lengths"])],
        ["target position", f"{p['target_position']} ± {p['position_tolerance']}"],
        ["min fill ratio", p["min_fill_ratio"]],
    ]))
    a("")
    a("Raw payloads under `data/raw/` are content-addressed by request URL, so re-running "
      "`fetch` is idempotent and the pilot can be regenerated byte-for-byte from the cached "
      "layer even after the live APIs change. Hashes of all outputs are in "
      f"`data/manifests/{cfg.name}_manifest.json`.")
    a("")
    return "\n".join(L) + "\n"
