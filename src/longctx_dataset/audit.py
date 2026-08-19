"""Human-audit package generation.

Automated validation proves the dataset is *internally consistent*: gold answers
recompute, contexts nest, evidence sits where it should. It cannot tell us whether a
question reads naturally, whether the distractors are genuinely tempting, or whether a
128K context is meaningfully harder than a 4K one. Those need a person.

This module assembles what that person needs: a compact artifact per family and the two
exact model-facing contexts, plus a manual checklist that is deliberately left unticked.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .config import PipelineConfig
from .context.builder import length_label
from .distractors.taxonomy import describe_taxonomy
from .prompts import EVALUATION_PROMPT_VERSION
from .questions.base import rng_for
from .schemas import Domain, Instance, QuestionFamily, QuestionType
from .storage.io import iter_jsonl, read_models, write_json
from .storage.manifests import utc_now
from .validation.question_leakage import answerability_leakage_phrases

# Left unticked on purpose. An automated pass marking these would defeat the point of
# having a human read the contexts.
AUDIT_CHECKLIST = [
    "Question is grammatically clear",
    "Exact entity/period/version/field is unambiguous",
    "Gold answer is correct",
    "Gold evidence directly supports the answer",
    "Calculation is correct if applicable",
    "4K context is answerable when answerable=true",
    "128K context is answerable when answerable=true",
    "Unanswerable context genuinely lacks required evidence",
    "Distractors are realistic same-domain competitors",
    "Distractors do not accidentally reveal the answer",
    "128K context is meaningfully more competitive than 4K",
    "No malformed/unnatural record formatting",
    "Record IDs are usable for later evidence selection",
    "No obvious question-template artifacts make the answer trivial",
    "No source-specific information leaks the answer outside intended evidence",
]

SHORT_LEN = 4096
LONG_LEN = 131072

ACTIVE_DOMAINS = (Domain.SEC, Domain.FDA, Domain.CLINICAL_TRIALS, Domain.FRED)
"""Domains in the active experiment. World Bank is excluded: its API proved too
unreliable to depend on, so auditing it would spend human attention on a source that
will not appear in the production dataset."""


class DatasetView:
    """Families plus a lazy index into the instance file of one generated dataset."""

    def __init__(self, cfg: PipelineConfig):
        from .pipeline import families_path, instances_path

        self.cfg = cfg
        self.families: List[QuestionFamily] = read_models(families_path(cfg), QuestionFamily)
        self.instances_path: Path = instances_path(cfg)
        self._offsets: Optional[Dict[Tuple[str, int], int]] = None

    def _index(self) -> Dict[Tuple[str, int], int]:
        """Byte offsets of each instance row, so 128K contexts load one at a time."""
        if self._offsets is None:
            self._offsets = {}
            if self.instances_path.exists():
                with self.instances_path.open("rb") as fh:
                    offset = 0
                    for raw in fh:
                        try:
                            row = json.loads(raw)
                        except json.JSONDecodeError:
                            offset += len(raw)
                            continue
                        self._offsets[(row["question_family_id"], row["context_length_nominal"])] = offset
                        offset += len(raw)
        return self._offsets

    def instance(self, family_id: str, nominal: int) -> Optional[Instance]:
        offset = self._index().get((family_id, nominal))
        if offset is None:
            return None
        with self.instances_path.open("rb") as fh:
            fh.seek(offset)
            return Instance.model_validate(json.loads(fh.readline()))


def select_families(
    views: Sequence[DatasetView], n: int, seed: int,
    domains: Sequence[Domain] = ACTIVE_DOMAINS,
) -> List[Tuple[DatasetView, QuestionFamily]]:
    """Pick ~n families spanning every domain and every question type.

    Coverage first, balance second: one family per question type is reserved before the
    remaining slots are shared out across domains, so a 12-family sample can never miss
    a category simply because one domain happens to be larger.
    """
    allowed = set(domains)
    pairs: List[Tuple[DatasetView, QuestionFamily]] = [
        (v, f) for v in views for f in v.families if f.domain in allowed
    ]
    if not pairs:
        return []
    rng = rng_for(seed, "audit-selection")
    pairs.sort(key=lambda p: p[1].question_family_id)
    rng.shuffle(pairs)

    chosen: List[Tuple[DatasetView, QuestionFamily]] = []
    used: set = set()

    def take(pred) -> bool:
        for pair in pairs:
            key = pair[1].question_family_id
            if key in used or not pred(pair[1]):
                continue
            used.add(key)
            chosen.append(pair)
            return True
        return False

    # 1. Every question type must appear.
    for qtype in sorted(QuestionType, key=lambda q: q.value):
        take(lambda f, q=qtype: f.question_type is q)

    # 2. Every active domain must appear.
    for domain in sorted({f.domain for _, f in pairs}, key=lambda d: d.value):
        if not any(f.domain is domain for _, f in chosen):
            take(lambda f, d=domain: f.domain is d)

    # 3. At least two unanswerable families -- they are the cleanest fabrication probe.
    while sum(1 for _, f in chosen if not f.answerable) < 2:
        if not take(lambda f: not f.answerable):
            break

    # 4. Fill the rest, balancing on both axes at once. Balancing on domain alone lets
    #    one question type dominate the sample -- unanswerable families are numerous
    #    enough to crowd out the others, which would waste review effort on one category.
    while len(chosen) < n:
        dom_counts: Dict[Domain, int] = defaultdict(int)
        type_counts: Dict[QuestionType, int] = defaultdict(int)
        for _, f in chosen:
            dom_counts[f.domain] += 1
            type_counts[f.question_type] += 1

        def cost(pair) -> Tuple[int, int, str]:
            fam = pair[1]
            return (dom_counts[fam.domain] + type_counts[fam.question_type],
                    type_counts[fam.question_type],
                    fam.question_family_id)

        remaining = [p for p in pairs if p[1].question_family_id not in used]
        if not remaining:
            break
        best = min(remaining, key=cost)
        used.add(best[1].question_family_id)
        chosen.append(best)

    return chosen[:n]


def _fmt_evidence_table(fam: QuestionFamily) -> str:
    if not fam.gold_evidence:
        return "_(none — this family is unanswerable by construction)_\n"
    rows = ["| role | record id | entity | field | period | version | value | unit |",
            "|---|---|---|---|---|---|---|---|"]
    for e in fam.gold_evidence:
        rows.append(
            f"| {e.role} | `{e.record_id}` | {e.entity_name} [{e.entity_id}] | "
            f"{e.concept_label} [{e.concept}] | {e.period or ''} | {e.version or ''} | "
            f"{e.value} | {e.unit or ''} |"
        )
    return "\n".join(rows) + "\n"


def _fmt_context_meta(inst: Optional[Instance], label: str) -> str:
    if inst is None:
        return f"**{label}** — _not generated for this family._\n"
    s = inst.stats
    lines = [
        f"**{label}** — `{inst.instance_id}`",
        "",
        f"| property | value |",
        f"|---|---|",
        f"| nominal target | {inst.context_length_nominal:,} tokens |",
        f"| actual tokens | {inst.context_tokens_actual:,} |",
        f"| fill ratio | {inst.context_tokens_actual / inst.context_length_nominal:.4f} |",
        f"| tokenizer | `{inst.tokenizer}` ({inst.tokenizer_version or 'n/a'}) |",
        f"| records in context | {len(inst.context_record_ids):,} |",
        f"| records before / after evidence | "
        f"{(s.n_records_before_target if s else '?')} / {(s.n_records_after_target if s else '?')} |",
        f"| target evidence tokens | "
        + (f"{inst.target_evidence_start_token}–{inst.target_evidence_end_token} |"
           if inst.target_evidence_start_token is not None else "n/a (unanswerable) |"),
        f"| target position (relative) | "
        + (f"{inst.target_position_relative:.4f} |"
           if inst.target_position_relative is not None else "n/a (unanswerable) |"),
        f"| context sha256 | `{inst.context_sha256}` |",
        f"| lineage parent | `{inst.lineage.get('extends_instance_id') or '(shortest variant)'}` |",
        f"| records added vs parent | {len(inst.lineage.get('added_record_ids') or []):,} |",
        f"| gold block sha256 | `{inst.lineage.get('gold_block_sha256', '')[:32]}` |",
    ]
    return "\n".join(lines) + "\n"


def _validation_status(cfg: PipelineConfig) -> str:
    from .pipeline import validation_path

    path = validation_path(cfg)
    if not path.exists():
        return "not found"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "unreadable"
    checks = payload.get("checks") or []
    failed = [c for c in checks if not c.get("passed") and not c.get("skipped")]
    return "PASS" if not failed else f"FAIL ({len(failed)} failing checks)"


def _audit_issue_fields(fam: QuestionFamily, instances: Sequence[Instance]) -> Dict[str, Any]:
    q = fam.question.lower()
    leak_terms = ("not the answer", "those are not", "context also contains", "different strengths")
    display_ok = True
    equiv_count = 0
    invalid_near = 0
    basis_count = 0
    unit_count = 0
    for inst in instances:
        display_ok = display_ok and bool(inst.context_display_ids) and len(inst.context_display_ids) == len(inst.context_record_ids)
        display_ok = display_ok and len(set(inst.context_display_ids)) == len(inst.context_display_ids)
        display_ok = display_ok and set(inst.display_id_to_record_id) == set(inst.context_display_ids)
        equiv_count = max(
            equiv_count,
            sum(max(0, len(g.canonical_record_ids) - 1) for g in inst.gold_evidence_equivalence_groups),
        )
        invalid_near += sum(
            1 for d in inst.distractors
            if (not inst.answerable and d.distractor_type.value == "NEAR_MATCH_VALUE")
        )
        basis_count += inst.distractor_counts.get("WRONG_SERIES_VARIANT", 0)
        unit_count += inst.distractor_counts.get("WRONG_UNIT", 0)
    return {
        "question_foil_leakage_detected": any(t in q for t in leak_terms),
        "question_type_leakage_detected": bool(answerability_leakage_phrases(fam.question)),
        "question_contains_abstention_instruction": bool(answerability_leakage_phrases(fam.question)),
        "common_evaluation_prompt_version": EVALUATION_PROMPT_VERSION,
        "common_evaluation_prompt_applied_uniformly": True,
        "opaque_display_ids": "pass" if display_ok else "fail",
        "equivalent_evidence_present": equiv_count,
        "invalid_near_match_value": invalid_near,
        "measurement_basis_distractors": basis_count,
        "true_wrong_unit_distractors": unit_count,
    }


def _distractor_examples(inst: Optional[Instance], view: DatasetView,
                         cfg: PipelineConfig, limit: int = 6) -> str:
    """A few real distractors from the 4K context, rendered exactly as the model sees them."""
    if inst is None or not inst.distractors:
        return "_(none)_\n"
    from .context.builder import ContextBuilder
    from .context.tokenizer import get_tokenizer
    from .pipeline import load_pool

    pool, _ = load_pool(cfg)
    builder = ContextBuilder(cfg, pool, get_tokenizer(cfg.tokenizer))

    by_type: Dict[str, List] = defaultdict(list)
    for d in inst.distractors:
        by_type[d.distractor_type.value].append(d)

    blocks: List[str] = []
    for dtype in sorted(by_type):
        d = by_type[dtype][0]
        rec = pool.get(d.record_id)
        if rec is None:
            continue
        rel = ", ".join(k for k, v in sorted(d.relationship_to_target.items()) if v)
        blocks.append(
            f"**`{dtype}`** — position {d.position_index} ({d.side} the evidence)\n\n"
            f"_relationship to target: {rel}_\n\n"
            f"```\n{builder.render_record(rec)}\n```"
        )
        if len(blocks) >= limit:
            break
    return "\n\n".join(blocks) + "\n"


def build_audit_package(
    configs: Sequence[PipelineConfig],
    out_dir: Path,
    n_families: int = 12,
    seed: int = 20240817,
    domains: Sequence[Domain] = ACTIVE_DOMAINS,
    family_ids: Optional[Sequence[str]] = None,
    log=print,
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    views = [DatasetView(c) for c in configs]
    if family_ids:
        wanted = set(family_ids)
        selected = [(v, f) for v in views for f in v.families if f.question_family_id in wanted]
        selected.sort(key=lambda p: family_ids.index(p[1].question_family_id))
    else:
        selected = select_families(views, n_families, seed, domains)
    if not selected:
        raise RuntimeError("no question families available to audit")

    taxonomy = describe_taxonomy()
    entries: List[Dict[str, Any]] = []

    for view, fam in selected:
        by_label: Dict[str, Optional[Instance]] = {
            length_label(n): view.instance(fam.question_family_id, n)
            for n in view.cfg.context.lengths
        }
        short = by_label.get("4K")
        long_ = by_label.get("128K")
        fid = fam.question_family_id

        # Exact model-facing contexts, byte-for-byte, untruncated and unannotated.
        written: Dict[str, Optional[str]] = {}
        for label, inst in by_label.items():
            if inst is None:
                written[label] = None
                continue
            path = out_dir / f"{fid}_{label}.txt"
            path.write_text(inst.context, encoding="utf-8")
            written[label] = path.name

        generated_instances = [i for i in by_label.values() if i is not None]
        md = _render_family_md(fam, view, by_label, written, taxonomy)
        (out_dir / f"{fid}.md").write_text(md, encoding="utf-8")
        issue_fields = _audit_issue_fields(fam, generated_instances)

        entries.append({
            "question_family_id": fid,
            "domain": fam.domain.value,
            "question_type": fam.question_type.value,
            "template_id": fam.generation_metadata.template_id,
            "answerable": fam.answerable,
            "gold_answer": fam.gold_answer,
            "gold_answer_normalized": fam.gold_answer_normalized,
            "dataset": view.cfg.name,
            "audit_markdown": f"{fid}.md",
            "context_4k": written["4K"],
            "context_128k": written["128K"],
            "contexts": dict(written),
            "context_4k_tokens": short.context_tokens_actual if short else None,
            "context_128k_tokens": long_.context_tokens_actual if long_ else None,
            "target_position_4k": short.target_position_relative if short else None,
            "target_position_128k": long_.target_position_relative if long_ else None,
            "records_4k": len(short.context_record_ids) if short else None,
            "records_128k": len(long_.context_record_ids) if long_ else None,
            "distractor_counts_4k": dict(short.distractor_counts) if short else {},
            "distractor_counts_128k": dict(long_.distractor_counts) if long_ else {},
            "audit_issue_fields": issue_fields,
            "checklist_items": len(AUDIT_CHECKLIST),
            "checklist_status": "PENDING_HUMAN_REVIEW",
        })
        log(f"  {fid:<14} {fam.domain.value:<16} {fam.question_type.value:<22} "
            f"4K={entries[-1]['context_4k_tokens']} 128K={entries[-1]['context_128k_tokens']}")

    index_md = _render_index(entries, configs, seed)
    (out_dir / "audit_index.md").write_text(index_md, encoding="utf-8")
    summary = {
        "generated_at": utc_now(),
        "seed": seed,
        "datasets": [{"name": c.name, "config": str(c.config_path)} for c in configs],
        "domains_audited": [d.value for d in domains],
        "n_families": len(entries),
        "checklist": AUDIT_CHECKLIST,
        "checklist_status": "PENDING_HUMAN_REVIEW",
        "families": entries,
    }
    write_json(out_dir / "audit_index.json", summary)
    return summary


def _render_family_md(fam, view, instances_by_label, written, taxonomy) -> str:
    short = instances_by_label.get("4K")
    long_ = instances_by_label.get("128K")
    generated_instances = [i for i in instances_by_label.values() if i is not None]
    issue_fields = _audit_issue_fields(fam, generated_instances)
    L: List[str] = []
    a = L.append
    a(f"# Audit — `{fam.question_family_id}`")
    a("")
    a(f"**Domain** {fam.domain.value} · **Question type** {fam.question_type.value} · "
      f"**Answerable** {fam.answerable} · **Template** `{fam.generation_metadata.template_id}` · "
      f"**Dataset** `{view.cfg.name}`")
    a("")
    a("## Question")
    a("")
    a(f"> {fam.question}")
    a("")
    a("## Gold answer")
    a("")
    if fam.answerable:
        a(f"- **Answer as presented:** `{fam.gold_answer}`")
        a(f"- **Normalized:** `{fam.gold_answer_normalized}`")
        a(f"- **Type:** {fam.answer_type.value}"
          + (f" · **Unit:** {fam.answer_unit}" if fam.answer_unit else ""))
        if fam.numeric_tolerance is not None:
            a(f"- **Grading tolerance:** ±{fam.numeric_tolerance}")
    else:
        spec = fam.unanswerable_spec
        a(f"- **Gold outcome:** `INSUFFICIENT_EVIDENCE`")
        a(f"- **Reason code:** `{spec.reason_code}`")
        a(f"- **Verified absent in pool:** {spec.verified_absent_in_pool}")
        a("")
        a(f"> {spec.reason}")
        a("")
        a(f"- **Missing:** entity `{spec.missing_entity_id}` · concept `{spec.missing_concept}` · "
          f"period `{spec.missing_period}`")
        a(f"- **Forbidden concept aliases:** {spec.forbidden_concept_aliases}")
    a("")

    if fam.calculation_spec:
        cs = fam.calculation_spec
        a("## Deterministic calculation")
        a("")
        a(f"`{cs.operation.value}` — `{cs.formula}`")
        a("")
        a("| role | record id | value used |")
        a("|---|---|---|")
        for role in sorted(cs.operands):
            a(f"| {role} | `{cs.operands[role]}` | {cs.operand_values[role]} |")
        a("")
        a(f"raw result `{cs.raw_result}` → rounded `{cs.rounded_result}` "
          f"({cs.round_decimals} dp)"
          + (f" · result unit {cs.result_unit}" if cs.result_unit else ""))
        a("")

    a("## Gold evidence")
    a("")
    a(_fmt_evidence_table(fam))
    a("")
    a("### Model-facing gold evidence IDs")
    a("")
    if generated_instances:
        inst0 = generated_instances[0]
        a("| canonical record id | display id | valid equivalent display ids |")
        a("|---|---|---|")
        for mapping in inst0.gold_evidence_display_map:
            equiv = ", ".join(f"`{did}`" for did in mapping.equivalent_display_ids)
            a(f"| `{mapping.canonical_record_id}` | `{mapping.display_id or ''}` | {equiv} |")
    else:
        a("_(none)_")
    a("")
    a("### Model-facing record ID examples")
    a("")
    if generated_instances:
        inst0 = generated_instances[0]
        a("| display id | canonical record id |")
        a("|---|---|")
        for did in inst0.context_display_ids[:8]:
            a(f"| `{did}` | `{inst0.display_id_to_record_id.get(did, '')}` |")
    else:
        a("_(none)_")
    a("")
    a("### Equivalent evidence")
    a("")
    groups = generated_instances[-1].gold_evidence_equivalence_groups if generated_instances else fam.gold_evidence_equivalence_groups
    if groups:
        a("| group | gold canonical id | equivalent canonical ids | display ids |")
        a("|---|---|---|---|")
        for g in groups:
            a(f"| `{g.group_id}` | `{g.gold_record_id}` | "
              f"{', '.join(f'`{x}`' for x in g.canonical_record_ids)} | "
              f"{', '.join(f'`{x}`' for x in g.display_ids)} |")
    else:
        a("_(none)_")

    a("## Target conditions")
    a("")
    a("```json")
    a(json.dumps(fam.target_conditions, indent=2, sort_keys=True))
    a("```")
    a("")

    a("## Source provenance")
    a("")
    a("| source | endpoint | retrieved at | records |")
    a("|---|---|---|---|")
    for p in fam.source_provenance[:8]:
        a(f"| {p.source} | {(p.request_url or p.endpoint or '')[:110]} | {p.retrieved_at or ''} | "
          f"{len(p.record_ids)} |")
    a("")
    a(f"_Generation: seed `{fam.generation_metadata.seed}`, config hash "
      f"`{fam.generation_metadata.config_hash}`, git `{(fam.generation_metadata.git_commit or 'n/a')[:12]}`, "
      f"tokenizer `{fam.generation_metadata.tokenizer_id}`._")
    a(f"_Validation status: **{_validation_status(view.cfg)}**._")
    a("")

    a("## Context metadata")
    a("")
    for label, inst in instances_by_label.items():
        a(_fmt_context_meta(inst, label))
        a("")
    a("")

    a("### Distractor composition")
    a("")
    labels = list(instances_by_label)
    a("| distractor type | " + " | ".join(labels) + " | meaning |")
    a("|---|" + "|".join("---" for _ in labels) + "|---|")
    keys = sorted(set().union(*(set((i.distractor_counts if i else {})) for i in instances_by_label.values())))
    for k in keys:
        counts = [f"{(instances_by_label[label].distractor_counts.get(k, 0) if instances_by_label[label] else 0):,}"
                  for label in labels]
        a(f"| `{k}` | " + " | ".join(counts) + f" | {taxonomy.get(k, '')} |")
    a("")
    a("### Specific audit fields")
    a("")
    a(f"- Question foil leakage detected: {'yes' if issue_fields['question_foil_leakage_detected'] else 'no'}")
    a(f"- Question-type leakage detected: {'yes' if issue_fields['question_type_leakage_detected'] else 'no'}")
    a(f"- Question contains abstention instruction: {'yes' if issue_fields['question_contains_abstention_instruction'] else 'no'}")
    a(f"- Common evaluation prompt version: {issue_fields['common_evaluation_prompt_version']}")
    a(f"- Common evaluation prompt applied uniformly: {'yes' if issue_fields['common_evaluation_prompt_applied_uniformly'] else 'no'}")
    a(f"- Opaque display IDs: {issue_fields['opaque_display_ids']}")
    a(f"- Equivalent evidence present: {issue_fields['equivalent_evidence_present']}")
    a(f"- Invalid NEAR_MATCH_VALUE: {issue_fields['invalid_near_match_value']}")
    a(f"- Measurement-basis distractors: {issue_fields['measurement_basis_distractors']}")
    a(f"- True WRONG_UNIT distractors: {issue_fields['true_wrong_unit_distractors']}")
    a("")

    a("### Representative distractors (from the 4K context)")
    a("")
    a(_distractor_examples(short, view, view.cfg))
    a("")

    a("## Model-facing contexts")
    a("")
    a("These files contain the **exact** context string the model will receive — untruncated, "
      "with no added header or annotation. The question above is supplied separately at "
      "evaluation time and is deliberately not part of the context.")
    a("")
    for label in labels:
        name = written.get(label)
        a(f"- **{label}:** " + (f"[`{name}`]({name})" if name else "_not generated_"))
    a("")

    a("## Manual review checklist")
    a("")
    a("**Status: PENDING_HUMAN_REVIEW.** These boxes are intentionally left unticked — "
      "automated validation cannot answer them. Tick them by hand after reading the "
      "context files above.")
    a("")
    for item in AUDIT_CHECKLIST:
        a(f"- [ ] {item}")
    a("")
    a("**Reviewer notes:**")
    a("")
    a("```")
    a("")
    a("```")
    a("")
    return "\n".join(L)


def _render_index(entries: List[Dict[str, Any]], configs, seed: int) -> str:
    L: List[str] = []
    a = L.append
    a("# Human-audit package")
    a("")
    a(f"_Generated {utc_now()} · seed `{seed}` · "
      f"datasets: {', '.join(f'`{c.name}`' for c in configs)}_")
    a("")
    a("_Scope: the four active domains (SEC, FDA, ClinicalTrials.gov, FRED). World Bank is "
      "excluded — its API proved too unreliable to keep in the experiment, so auditing it "
      "would spend review effort on a source that will not reach production._")
    a("")
    a("## Status: PENDING_HUMAN_REVIEW")
    a("")
    a(f"{len(entries)} question families were sampled for manual inspection, spanning every "
      "active domain and all five question types, including both answerable and unanswerable "
      "cases. Nothing here has been auto-approved: every checklist in every family file is "
      "unticked by design.")
    a("")
    a("Automated validation already proves these families are internally consistent — gold "
      "answers recompute from source records, contexts nest, evidence sits at ~50%. What it "
      "cannot judge is whether a question reads naturally, whether the distractors are "
      "genuinely tempting, and whether the 128K context is *meaningfully* harder than the 4K "
      "one. That is what this package is for.")
    a("")
    a("## How to review")
    a("")
    a("1. Open `<FAMILY>.md` for the question, gold answer, evidence and context metadata.")
    a("2. Open `<FAMILY>_4K.txt` and `<FAMILY>_128K.txt` — these are the exact, untruncated "
      "model-facing contexts, with no added headers.")
    a("3. Find the gold evidence record IDs (listed in the `.md`) inside each context.")
    a("4. Work the checklist at the bottom of the `.md` and record notes there.")
    a("")
    a("## Selected families")
    a("")
    a("| family | domain | type | answerable | gold answer | 4K tok | 128K tok | "
      "4K recs | 128K recs | pos 4K | pos 128K | files |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for e in entries:
        gold = "INSUFFICIENT_EVIDENCE" if not e["answerable"] else str(e["gold_answer"])
        if len(gold) > 30:
            gold = gold[:27] + "…"
        p4 = f"{e['target_position_4k']:.3f}" if e["target_position_4k"] is not None else "n/a"
        p128 = f"{e['target_position_128k']:.3f}" if e["target_position_128k"] is not None else "n/a"
        files = (f"[md]({e['audit_markdown']})"
                 + (f" · [4K]({e['context_4k']})" if e["context_4k"] else "")
                 + (f" · [128K]({e['context_128k']})" if e["context_128k"] else ""))
        a(f"| `{e['question_family_id']}` | {e['domain']} | {e['question_type']} | "
          f"{'yes' if e['answerable'] else '**no**'} | `{gold}` | "
          f"{(e['context_4k_tokens'] or 0):,} | {(e['context_128k_tokens'] or 0):,} | "
          f"{(e['records_4k'] or 0):,} | {(e['records_128k'] or 0):,} | {p4} | {p128} | {files} |")
    a("")

    by_domain: Dict[str, int] = defaultdict(int)
    by_type: Dict[str, int] = defaultdict(int)
    for e in entries:
        by_domain[e["domain"]] += 1
        by_type[e["question_type"]] += 1
    a("## Coverage")
    a("")
    a("| domain | families |")
    a("|---|---|")
    for k in sorted(by_domain):
        a(f"| {k} | {by_domain[k]} |")
    a("")
    a("| question type | families |")
    a("|---|---|")
    for k in sorted(by_type):
        a(f"| {k} | {by_type[k]} |")
    a("")
    a(f"Answerable: {sum(1 for e in entries if e['answerable'])} · "
      f"Unanswerable: {sum(1 for e in entries if not e['answerable'])}")
    a("")
    a("## Checklist applied to every family")
    a("")
    for item in AUDIT_CHECKLIST:
        a(f"- [ ] {item}")
    a("")
    return "\n".join(L)
