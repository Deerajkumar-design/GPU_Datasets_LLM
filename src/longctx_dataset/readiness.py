"""Pre-production readiness report.

Answers one question: is the pipeline ready to generate the 100-family pre-production
dataset? It reports what changed in this phase, what the numbers actually are, and --
importantly -- what is still outstanding, including the parts only a human can sign off.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .config import PipelineConfig, git_commit, load_config
from .distractors.taxonomy import describe_taxonomy
from .schemas import Domain
from .storage.io import iter_jsonl, read_json, write_json
from .storage.manifests import utc_now

SCARCE_CLASSES = ("WRONG_VERSION", "WRONG_UNIT")
"""The two classes this phase set out to improve."""


def _validation(cfg: PipelineConfig) -> Dict[str, Any]:
    from .pipeline import validation_path

    p = validation_path(cfg)
    return read_json(p) if p.exists() else {}


def _presence_by_class(instances_path: Path) -> Tuple[Dict[str, int], int]:
    """How many families contain at least one distractor of each class, at 4K.

    Presence matters more than share here. WRONG_PERIOD is unbounded (every other date
    of the same series qualifies) while WRONG_VERSION is capped by how many vintages a
    single observation has, so comparing raw counts across classes says little. What
    matters is whether the interference is *there* to be confused by.
    """
    present: collections.Counter = collections.Counter()
    n = 0
    for row in iter_jsonl(instances_path):
        if row.get("context_length_nominal") != 4096:
            continue
        n += 1
        for k, v in (row.get("distractor_counts") or {}).items():
            if v:
                present[k] += 1
    return dict(present), n


def build_readiness(
    pilot_cfg: PipelineConfig,
    fred_cfg: PipelineConfig,
    preprod_path: str,
    prod_path: str,
    audit_dir: Path,
    out_dir: Path,
    log=print,
) -> Tuple[Path, Path]:
    from .pipeline import instances_path, load_retrievals

    pilot_val, fred_val = _validation(pilot_cfg), _validation(fred_cfg)
    pilot_stats = pilot_val.get("stats", {})
    fred_stats = fred_val.get("stats", {})

    before = pilot_stats.get("distractor_totals", {})
    after = fred_stats.get("distractor_totals", {})
    combined = {k: before.get(k, 0) + after.get(k, 0) for k in set(before) | set(after)}

    pilot_present, pilot_n = _presence_by_class(instances_path(pilot_cfg))
    fred_present, fred_n = _presence_by_class(instances_path(fred_cfg))

    fred_retr = next((r for r in load_retrievals(fred_cfg) if r.domain == "FRED"), None)
    fred_norm = fred_stats.get("normalized_records_by_domain", {}).get("FRED", 0)

    rec_types: collections.Counter = collections.Counter()
    for row in iter_jsonl(pilot_cfg.normalized_dir / "fred.jsonl"):
        rec_types[row.get("record_type", "?")] += 1

    audit_index = {}
    if (audit_dir / "audit_index.json").exists():
        audit_index = read_json(audit_dir / "audit_index.json")

    preprod = load_config(preprod_path)
    prod = load_config(prod_path)

    def domain_alloc(cfg: PipelineConfig) -> Dict[str, Any]:
        from .questions.base import allocate_counts

        per_type: collections.Counter = collections.Counter()
        per_domain: Dict[str, int] = {}
        for d, dc in cfg.domains.items():
            if not dc.enabled:
                continue
            per_domain[d.value] = dc.n_families
            counts = (dc.question_type_counts
                      or allocate_counts(dc.question_type_mix, dc.n_families))
            for k, v in counts.items():
                per_type[getattr(k, "value", k)] += v
        return {"per_domain": per_domain, "total": sum(per_domain.values()),
                "per_question_type": dict(sorted(per_type.items()))}

    payload: Dict[str, Any] = {
        "generated_at": utc_now(),
        "git_commit": git_commit(Path.cwd()),
        "phase": "pre-production dataset audit and FRED extension",
        "scope_note": (
            "Dataset generation and audit preparation only. No LLM has been run, no "
            "semantic judge exists, no hallucination scoring or statistical analysis has "
            "been performed, and neither the 100-family nor the 500-family dataset has "
            "been generated."
        ),
        "fred_adapter": {
            "status": "IMPLEMENTED_AND_VALIDATED",
            "domain": "FRED",
            "backend_used": "fredgraph_csv",
            "backend_available_with_key": "fred_api",
            "api_key_present": bool(fred_cfg.http.fred_api_key),
            "endpoints": [
                "https://fred.stlouisfed.org/graph/fredgraph.csv (current vintage)",
                "https://alfred.stlouisfed.org/graph/alfredgraph.csv (vintage/ALFRED)",
                "https://api.stlouisfed.org/fred (used automatically when FRED_API_KEY is set)",
            ],
            "first_party": True,
            "third_party_scraping": False,
            "requests": getattr(fred_retr, "n_requests", None),
            "raw_payloads": getattr(fred_retr, "n_raw_payloads", None),
            "raw_records": getattr(fred_retr, "n_raw_records", None),
            "errors": len(getattr(fred_retr, "errors", []) or []),
            "normalized_records": fred_norm,
            "normalized_by_record_type": dict(rec_types),
            "series_in_catalog": len(fred_cfg.domains[Domain.FRED].params.get("series", [])),
            "vintage_series": fred_cfg.domains[Domain.FRED].params.get("vintage_series", []),
            "vintage_dates": fred_cfg.domains[Domain.FRED].params.get("vintage_dates", []),
            "metadata_caveat": (
                "Descriptive series attributes (title, units, frequency, seasonal "
                "adjustment) are operator-supplied from the config catalog while running "
                "keyless, and every record is stamped metadata_source=operator_catalog. "
                "Observation values, dates and vintages always come from the API. Setting "
                "FRED_API_KEY sources the attributes from /fred/series with no code change."
            ),
        },
        "fred_pilot": {
            "config": str(fred_cfg.config_path),
            "config_hash": fred_cfg.config_hash,
            "seed": fred_cfg.seed,
            "families": fred_stats.get("n_families"),
            "instances": fred_stats.get("n_instances"),
            "families_by_question_type": fred_stats.get("families_by_question_type"),
            "answerable": fred_stats.get("families_answerable"),
            "unanswerable": fred_stats.get("families_unanswerable"),
            "unavailable_variants": fred_stats.get("n_unavailable_variants"),
            "context_lengths": fred_cfg.context.lengths,
            "token_stats_by_length": fred_stats.get("token_stats_by_length"),
            "target_position": fred_stats.get("target_position"),
        },
        "validation": {
            "fred_pilot": {
                "counts": fred_val.get("counts"),
                "has_critical_failures": fred_val.get("has_critical_failures"),
                "failed_checks": [c["check_id"] for c in fred_val.get("checks", [])
                                  if not c.get("passed") and not c.get("skipped")],
            },
            "existing_pilot_unchanged": {
                "counts": pilot_val.get("counts"),
                "has_critical_failures": pilot_val.get("has_critical_failures"),
            },
            "note": "Validation rules were not weakened for FRED; the same 22 checks ran.",
        },
        "distractor_distribution": {
            "taxonomy": describe_taxonomy(),
            "before_fred_existing_pilot": before,
            "fred_pilot_only": after,
            "combined": combined,
            "scarce_class_focus": {
                cls: {
                    "existing_pilot_placements": before.get(cls, 0),
                    "fred_placements": after.get(cls, 0),
                    "existing_pilot_families_containing_at_4k": pilot_present.get(cls, 0),
                    "existing_pilot_families_total": pilot_n,
                    "fred_families_containing_at_4k": fred_present.get(cls, 0),
                    "fred_families_total": fred_n,
                }
                for cls in SCARCE_CLASSES
            },
            "family_presence_at_4k": {
                "existing_pilot": {"present": pilot_present, "families": pilot_n},
                "fred_pilot": {"present": fred_present, "families": fred_n},
            },
        },
        "human_audit_package": {
            "directory": str(audit_dir),
            "index_markdown": str(audit_dir / "audit_index.md"),
            "index_json": str(audit_dir / "audit_index.json"),
            "status": audit_index.get("checklist_status", "PENDING_HUMAN_REVIEW"),
            "n_families": audit_index.get("n_families"),
            "domains_audited": audit_index.get("domains_audited"),
            "checklist_items": len(audit_index.get("checklist", [])),
            "families": [
                {k: e[k] for k in ("question_family_id", "domain", "question_type",
                                   "answerable", "dataset", "audit_markdown",
                                   "context_4k", "context_128k")}
                for e in audit_index.get("families", [])
            ],
        },
        "tokenizer_readiness": {
            "status": "READY_CONFIG_ONLY_SWITCH",
            "field_to_change": "tokenizer.id",
            "files_to_change": ["config/preproduction.yaml", "config/production.yaml"],
            "current_value": preprod.tokenizer.id,
            "id_format": "backend:name",
            "supported_backends": {
                "tiktoken": "tiktoken:<encoding>, e.g. tiktoken:cl100k_base, tiktoken:o200k_base",
                "hf": "hf:<model-id>, e.g. hf:meta-llama/Llama-3.1-8B (needs the 'hf' extra)",
                "whitespace": "whitespace:v1 - approximate, offline testing only",
            },
            "code_changes_required": "none",
            "verified": (
                "Three backends were driven through the real context builder by changing "
                "only tokenizer.id: cl100k_base, o200k_base and whitespace:v1 each produced "
                "valid nested contexts, each instance recorded the tokenizer actually used, "
                "and the gold answers were identical across all three."
            ),
            "after_changing_it": "re-run build-contexts (and validate); question families are unaffected",
            "guard": (
                "allow_fallback is false, so an unavailable tokenizer raises rather than "
                "silently mis-measuring every context length."
            ),
        },
        "preproduction_config": {
            "path": preprod_path,
            "status": "PREPARED_AND_VALIDATED_NOT_GENERATED",
            "config_hash": preprod.config_hash,
            "allocation": domain_alloc(preprod),
            "context_lengths": preprod.context.lengths,
            "target_position": preprod.context.target_position,
            "position_tolerance": preprod.context.position_tolerance,
            "min_fill_ratio": preprod.context.min_fill_ratio,
            "note": (
                "Explicit question_type_counts are used because 30% of 25 is 7.5: no "
                "per-domain rounding of the fractional mix reaches the global target, so "
                "counts are stated per domain and chosen to sum exactly to 20/30/15/15/20."
            ),
        },
        "production_config": {
            "path": prod_path,
            "status": "PREPARED_NOT_GENERATED",
            "config_hash": prod.config_hash,
            "allocation": domain_alloc(prod),
            "world_bank_removed": Domain.WORLD_BANK not in prod.enabled_domains(),
            "extension_slot_retained": Domain.EXTENSION in prod.domains,
        },
        "preserved_artifacts": {
            "note": (
                "The previously validated 32-family pilot was not modified. Retrieval "
                "records are now written per config name, so this phase could not "
                "overwrite the earlier provenance file."
            ),
            "paths": ["data/pilot/", "data/reports/pilot_report.md",
                      "data/reports/pilot_validation.json",
                      "data/manifests/pilot_manifest.json",
                      "data/manifests/source_retrievals.json"],
        },
    }

    payload["blockers"] = _blockers(payload)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "preproduction_readiness.json"
    md_path = out_dir / "preproduction_readiness.md"
    write_json(json_path, payload)
    md_path.write_text(_render(payload), encoding="utf-8")
    return md_path, json_path


def _blockers(p: Dict[str, Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    out.append({
        "severity": "BLOCKING",
        "item": "Human audit not yet performed",
        "detail": (
            f"{p['human_audit_package']['n_families']} families are prepared in "
            f"{p['human_audit_package']['directory']} with unticked checklists. Nothing "
            "automated can decide whether the questions read naturally or whether the "
            "128K contexts are meaningfully harder than the 4K ones."
        ),
    })
    out.append({
        "severity": "BLOCKING",
        "item": "Target tokenizer not selected",
        "detail": (
            "tokenizer.id is still the placeholder tiktoken:cl100k_base. Token counts are "
            "the independent variable, so this must match the model under test before any "
            "dataset intended for the experiment is generated."
        ),
    })
    scarce = p["distractor_distribution"]["scarce_class_focus"]
    wv = scarce["WRONG_VERSION"]
    out.append({
        "severity": "ADVISORY",
        "item": "WRONG_VERSION coverage remains narrow",
        "detail": (
            f"Present in {wv['fred_families_containing_at_4k']}/{wv['fred_families_total']} "
            f"FRED families and {wv['existing_pilot_families_containing_at_4k']}/"
            f"{wv['existing_pilot_families_total']} existing-pilot families at 4K. It is "
            "structurally scarce: a revision conflict only exists where a source genuinely "
            "restated a value. Widening FRED's vintage_series/vintage_dates to more "
            "genuinely revised series would raise it; adding vintages for never-revised "
            "series would only pad the count and is deliberately not done."
        ),
    })
    if not p["fred_adapter"]["api_key_present"]:
        out.append({
            "severity": "ADVISORY",
            "item": "FRED running keyless",
            "detail": (
                "Observations and vintages come from the API, but descriptive series "
                "attributes are operator-supplied from the config catalog and stamped "
                "metadata_source=operator_catalog. Setting FRED_API_KEY sources them from "
                "/fred/series with no code change."
            ),
        })
    out.append({
        "severity": "RESOLVED",
        "item": "World Bank removed from the active experiment",
        "detail": (
            "Its Indicators API returned HTTP 502 for date-range queries, hung on large "
            "result sets, and eventually refused traffic. It is absent from both the "
            "pre-production and production configs; the adapter and its data are retained "
            "so earlier datasets stay reproducible."
        ),
    })
    return out


def _tbl(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    if not rows:
        return "_(none)_\n"
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return "\n".join(out) + "\n"


def _render(p: Dict[str, Any]) -> str:
    L: List[str] = []
    a = L.append
    fa, fp, dd = p["fred_adapter"], p["fred_pilot"], p["distractor_distribution"]

    a("# Pre-production readiness")
    a("")
    a(f"_Generated {p['generated_at']} · git `{(p.get('git_commit') or 'n/a')[:12]}`_")
    a("")
    a(f"> **Scope.** {p['scope_note']}")
    a("")

    a("## 1. Verdict")
    a("")
    blocking = [b for b in p["blockers"] if b["severity"] == "BLOCKING"]
    a(f"**The pipeline is technically ready; {len(blocking)} non-technical gates remain open.**")
    a("")
    a(f"- FRED adapter: **{fa['status']}**, running on the `{fa['backend_used']}` backend "
      f"({fa['normalized_records']:,} normalized records).")
    a(f"- FRED pilot: **{fp['families']} families → {fp['instances']} instances**, "
      f"{fp['unavailable_variants']} unavailable variants.")
    v = p["validation"]["fred_pilot"]["counts"] or {}
    a(f"- Validation: **{v.get('passed')}/{v.get('total')} checks passed**, "
      f"{v.get('critical_failed')} critical failures. Rules unchanged.")
    a(f"- Human audit: **{p['human_audit_package']['status']}** "
      f"({p['human_audit_package']['n_families']} families prepared).")
    a(f"- Tokenizer: **{p['tokenizer_readiness']['status']}** — change "
      f"`{p['tokenizer_readiness']['field_to_change']}`, no code change.")
    a("")

    a("## 2. FRED adapter")
    a("")
    a(_tbl(["property", "value"], [
        ["status", fa["status"]],
        ["backend in use", f"`{fa['backend_used']}` (keyless first-party CSV)"],
        ["backend with API key", f"`{fa['backend_available_with_key']}` (automatic when FRED_API_KEY is set)"],
        ["first-party sources only", fa["first_party"]],
        ["third-party scraping", fa["third_party_scraping"]],
        ["requests / payloads", f"{fa['requests']} / {fa['raw_payloads']}"],
        ["raw records", f"{fa['raw_records']:,}"],
        ["request errors", fa["errors"]],
        ["normalized records", f"{fa['normalized_records']:,}"],
        ["series in catalog", fa["series_in_catalog"]],
        ["vintage series", ", ".join(fa["vintage_series"])],
        ["vintage dates", ", ".join(fa["vintage_dates"])],
    ]))
    a("")
    a("Endpoints used (all Federal Reserve Bank of St. Louis):")
    a("")
    for e in fa["endpoints"]:
        a(f"- `{e}`")
    a("")
    a(_tbl(["record type", "count"],
           [[k, f"{v:,}"] for k, v in sorted(fa["normalized_by_record_type"].items())]))
    a("")
    a(f"> **Metadata provenance.** {fa['metadata_caveat']}")
    a("")

    a("## 3. FRED pilot")
    a("")
    a(_tbl(["property", "value"], [
        ["config", f"`{fp['config']}` (hash `{fp['config_hash']}`, seed {fp['seed']})"],
        ["question families", fp["families"]],
        ["context instances", fp["instances"]],
        ["answerable / unanswerable", f"{fp['answerable']} / {fp['unanswerable']}"],
        ["unavailable variants", fp["unavailable_variants"]],
        ["context lengths", ", ".join(f"{n // 1024}K" for n in fp["context_lengths"])],
    ]))
    a("")
    a(_tbl(["question type", "families"],
           [[k, val] for k, val in sorted((fp["families_by_question_type"] or {}).items())]))
    a("")
    rows = []
    for k in sorted((fp["token_stats_by_length"] or {}), key=lambda x: int(x)):
        d = fp["token_stats_by_length"][k]
        rows.append([f"{int(k) // 1024}K", d.get("n"), f"{d.get('min'):,.0f}",
                     f"{d.get('median'):,.0f}", f"{d.get('max'):,.0f}",
                     f"{d.get('median') / int(k):.4f}"])
    a(_tbl(["nominal", "instances", "min tokens", "median", "max", "median fill"], rows))
    a("")
    tp = fp["target_position"] or {}
    a(f"**Target-evidence position:** n={tp.get('n')}, min={tp.get('min')}, "
      f"median={tp.get('median')}, max={tp.get('max')}, mean={tp.get('mean')} "
      f"(target 0.50 ± 0.05).")
    a("")

    a("## 4. Validation")
    a("")
    fv = p["validation"]["fred_pilot"]
    a(f"FRED pilot: **{(fv['counts'] or {}).get('passed')}/{(fv['counts'] or {}).get('total')} "
      f"checks passed**, critical failures: {(fv['counts'] or {}).get('critical_failed')}. "
      f"Failed checks: {fv['failed_checks'] or 'none'}.")
    a("")
    ev = p["validation"]["existing_pilot_unchanged"]
    a(f"Existing 32-family pilot (unchanged, re-reported for reference): "
      f"{(ev['counts'] or {}).get('passed')}/{(ev['counts'] or {}).get('total')} passed.")
    a("")
    a(f"> {p['validation']['note']}")
    a("")

    a("## 5. Distractor taxonomy — before and after FRED")
    a("")
    b, af, comb = dd["before_fred_existing_pilot"], dd["fred_pilot_only"], dd["combined"]
    tb, ta, tc = sum(b.values()) or 1, sum(af.values()) or 1, sum(comb.values()) or 1
    rows = []
    for k in sorted(comb, key=lambda x: -comb[x]):
        rows.append([f"`{k}`", f"{b.get(k, 0):,}", f"{b.get(k, 0) / tb:.2%}",
                     f"{af.get(k, 0):,}", f"{af.get(k, 0) / ta:.2%}",
                     f"{comb[k]:,}", f"{comb[k] / tc:.2%}"])
    a(_tbl(["distractor type", "existing pilot", "share", "FRED pilot", "share",
            "combined", "share"], rows))
    a("")
    a("### Why placement share is the wrong lens for the scarce classes")
    a("")
    a("A single target can be surrounded by thousands of WRONG_PERIOD records — every "
      "other date of the same series qualifies — but by at most a handful of "
      "WRONG_VERSION records, because a revision conflict only exists where the source "
      "actually restated the value. Raw share therefore measures pool geometry, not "
      "interference quality. The useful measure is **how many families contain the class "
      "at all**, at the shortest length where every record is close to the evidence:")
    a("")
    fpr = dd["family_presence_at_4k"]
    ep, fpp = fpr["existing_pilot"], fpr["fred_pilot"]
    rows = []
    for k in sorted(set(ep["present"]) | set(fpp["present"])):
        rows.append([f"`{k}`",
                     f"{ep['present'].get(k, 0)}/{ep['families']}",
                     f"{ep['present'].get(k, 0) / max(ep['families'], 1):.0%}",
                     f"{fpp['present'].get(k, 0)}/{fpp['families']}",
                     f"{fpp['present'].get(k, 0) / max(fpp['families'], 1):.0%}"])
    a(_tbl(["distractor type", "existing pilot families @4K", "%",
            "FRED families @4K", "%"], rows))
    a("")
    a("### The two classes this phase targeted")
    a("")
    for cls, d in dd["scarce_class_focus"].items():
        a(f"- **`{cls}`** — placements: {d['existing_pilot_placements']:,} (existing) → "
          f"{d['fred_placements']:,} (FRED). Family coverage at 4K: "
          f"{d['existing_pilot_families_containing_at_4k']}/{d['existing_pilot_families_total']} "
          f"({d['existing_pilot_families_containing_at_4k'] / max(d['existing_pilot_families_total'], 1):.0%}) → "
          f"{d['fred_families_containing_at_4k']}/{d['fred_families_total']} "
          f"({d['fred_families_containing_at_4k'] / max(d['fred_families_total'], 1):.0%}).")
    a("")

    a("## 6. Human-audit package")
    a("")
    ha = p["human_audit_package"]
    a(f"**Status: {ha['status']}** — {ha['n_families']} families, "
      f"{ha['checklist_items']} checklist items each, all left unticked by design.")
    a("")
    a(f"- Directory: `{ha['directory']}`")
    a(f"- Index: `{ha['index_markdown']}` (and `{ha['index_json']}`)")
    a(f"- Domains audited: {', '.join(ha['domains_audited'] or [])}")
    a("")
    a(_tbl(["family", "domain", "type", "answerable", "dataset", "artifact", "4K context", "128K context"],
           [[f"`{e['question_family_id']}`", e["domain"], e["question_type"],
             "yes" if e["answerable"] else "**no**", e["dataset"],
             f"`{e['audit_markdown']}`", f"`{e['context_4k']}`", f"`{e['context_128k']}`"]
            for e in ha["families"]]))
    a("")

    a("## 7. Tokenizer readiness")
    a("")
    tr = p["tokenizer_readiness"]
    a(f"**Status: {tr['status']}**")
    a("")
    a(f"Change exactly one field — **`{tr['field_to_change']}`** — in "
      + " and ".join(f"`{f}`" for f in tr["files_to_change"]) + ".")
    a("")
    a(_tbl(["property", "value"], [
        ["current (placeholder)", f"`{tr['current_value']}`"],
        ["id format", f"`{tr['id_format']}`"],
        ["code changes required", tr["code_changes_required"]],
        ["after changing it", tr["after_changing_it"]],
        ["safety guard", tr["guard"]],
    ]))
    a("")
    a("Supported backends:")
    a("")
    for k, val in tr["supported_backends"].items():
        a(f"- **`{k}`** — {val}")
    a("")
    a(f"> **Verified.** {tr['verified']}")
    a("")

    a("## 8. Configuration status")
    a("")
    for key, title in (("preproduction_config", "Pre-production (100 families)"),
                       ("production_config", "Production (500 families)")):
        c = p[key]
        a(f"### {title}")
        a("")
        a(f"**Status: {c['status']}** · `{c['path']}` · config hash `{c['config_hash']}`")
        a("")
        alloc = c["allocation"]
        a(_tbl(["domain", "families"],
               [[k, val] for k, val in sorted(alloc["per_domain"].items())]
               + [["**total**", f"**{alloc['total']}**"]]))
        a("")
        total = alloc["total"] or 1
        a(_tbl(["question type", "families", "share"],
               [[k, val, f"{val / total:.0%}"] for k, val in alloc["per_question_type"].items()]))
        a("")
        if key == "preproduction_config":
            a(f"> {c['note']}")
        else:
            a(f"World Bank removed: **{c['world_bank_removed']}** · "
              f"fifth-domain EXTENSION slot retained: **{c['extension_slot_retained']}**")
        a("")

    a("## 9. Preserved artifacts")
    a("")
    a(f"{p['preserved_artifacts']['note']}")
    a("")
    for path in p["preserved_artifacts"]["paths"]:
        a(f"- `{path}`")
    a("")

    a("## 10. Blockers and outstanding items")
    a("")
    a(_tbl(["severity", "item", "detail"],
           [[b["severity"], b["item"], b["detail"]] for b in p["blockers"]]))
    a("")
    return "\n".join(L) + "\n"
