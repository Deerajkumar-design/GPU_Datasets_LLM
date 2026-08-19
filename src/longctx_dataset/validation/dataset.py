"""Dataset-level validation orchestration.

Runs every check (A-W) in a single streaming pass over the instance file, so a 128K-token
dataset can be validated without ever holding all contexts in memory. Context strings are
examined and discarded; only lightweight per-instance summaries survive into the
cross-variant phase.

Critical failures make ``longctx-dataset validate`` exit nonzero. That exit code is the
gate the project uses to decide whether the pipeline may scale to production.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from ..config import PipelineConfig
from ..context.builder import ContextBuilder
from ..context.display_ids import DISPLAY_ID_RE
from ..context.tokenizer import get_tokenizer
from ..evidence import family_requires_version_equivalence, records_equivalent
from ..prompt_renderer import LLAMA_PROMPT_VERSION, RESPONSE_FORMAT_VERSION, PromptRenderer
from ..normalize.common import RecordPool
from ..schemas import (
    AnswerType,
    CalculationOp,
    DistractorType,
    Domain,
    Instance,
    QuestionFamily,
    QuestionType,
    UnavailableVariant,
    INSUFFICIENT_EVIDENCE,
)
from ..storage.io import iter_jsonl, iter_models, read_models
from . import contexts as ctx_checks
from . import leakage as leak_checks
from .question_leakage import answerability_leakage_phrases
from .gold import verify_family
from .result import CheckResult, Severity, ValidationReport

# Operations whose operands must share a unit for the arithmetic to be meaningful.
_UNIT_HOMOGENEOUS_OPS = {
    CalculationOp.GROWTH_PERCENT,
    CalculationOp.DIFFERENCE,
    CalculationOp.RATIO_PERCENT,
    CalculationOp.SUM,
}


@dataclass
class _InstanceSummary:
    """Everything the cross-variant phase needs, minus the context string."""

    instance_id: str
    question_family_id: str
    context_length_nominal: int
    context_tokens_actual: int
    context_record_ids: List[str]
    question: str
    gold_answer: Any
    gold_answer_normalized: Any
    gold_evidence_ids: List[str]
    lineage: Dict[str, Any]
    answerable: bool
    target_position_relative: Optional[float]
    target_evidence_start_token: Optional[int]
    target_evidence_end_token: Optional[int]
    domain: str
    question_type: str
    distractor_counts: Dict[str, int]


def _mk(report: ValidationReport, cid: str, name: str, severity: str = Severity.CRITICAL) -> CheckResult:
    return report.add(CheckResult(check_id=cid, name=name, severity=severity))


def run_validation(cfg: PipelineConfig, log=print) -> ValidationReport:
    from ..pipeline import families_path, instances_path, load_pool, unavailable_path

    report = ValidationReport(dataset_name=cfg.name)
    families = read_models(families_path(cfg), QuestionFamily)
    fam_by_id: Dict[str, QuestionFamily] = {f.question_family_id: f for f in families}
    pool, pool_counts = load_pool(cfg)
    unavailable = [UnavailableVariant.model_validate(r) for r in iter_jsonl(unavailable_path(cfg))]
    rel_tol = cfg.validation.numeric_recompute_rel_tolerance

    log(f"  {len(families)} families, {sum(pool_counts.values())} normalized records")

    # ---- checks that need only the family file ------------------------------------
    c_a = _mk(report, "A", "unique IDs (families and instances)")
    c_b = _mk(report, "B", "no duplicate question families")
    c_c = _mk(report, "C", "valid source provenance")
    c_d = _mk(report, "D", "deterministic gold-answer recomputation")
    c_n = _mk(report, "N", "unit consistency in calculations")
    c_o = _mk(report, "O", "answer-type / schema validity")
    c_q = _mk(report, "Q", "no NaN or invalid numeric answers")
    c_t = _mk(report, "T", "calculation operands recomputable")
    c_u = _mk(report, "U", "all five question types represented",
              Severity.CRITICAL if cfg.validation.require_all_question_types else Severity.WARNING)
    c_z = _mk(report, "Z", "model-facing questions do not leak answerability")

    seen_family_ids: set = set()
    seen_questions: Dict[tuple, str] = {}
    for fam in families:
        c_a.n_checked += 1
        if fam.question_family_id in seen_family_ids:
            c_a.fail(kind="duplicate_family_id", question_family_id=fam.question_family_id)
        seen_family_ids.add(fam.question_family_id)

        c_b.n_checked += 1
        qkey = (fam.domain.value, fam.question.strip())
        if qkey in seen_questions:
            c_b.fail(kind="duplicate_question_text", question_family_id=fam.question_family_id,
                     duplicate_of=seen_questions[qkey], question=fam.question[:160])
        else:
            seen_questions[qkey] = fam.question_family_id

        _check_provenance(fam, c_c)
        _check_gold(fam, pool, rel_tol, c_d)
        _check_units(fam, pool, c_n)
        _check_answer_schema(fam, c_o, c_q)
        _check_calculation_operands(fam, pool, c_t)
        _check_question_answerability_leakage(fam, c_z)

    present_types = {f.question_type for f in families}
    c_u.n_checked = len(QuestionType)
    for qt in QuestionType:
        if qt not in present_types:
            c_u.fail(kind="missing_question_type", question_type=qt.value)

    # ---- streaming pass over instances ---------------------------------------------
    c_e = _mk(report, "E", "gold evidence present in every answerable context")
    c_f = _mk(report, "F", "gold evidence absent for unanswerable families")
    c_k = _mk(report, "K", "token-length compliance")
    c_l = _mk(report, "L", "target-position compliance")
    c_m = _mk(report, "M", "record-boundary integrity")
    c_p = _mk(report, "P", "distractor metadata completeness")
    c_r = _mk(report, "R", "no context truncation through target evidence")
    c_s = _mk(report, "S", "no answer leakage for unanswerable families")
    c_v = _mk(report, "V", "no duplicate answer sources in answerable contexts")
    c_w = _mk(report, "W", "opaque display ID mapping integrity")
    c_x = _mk(report, "X", "evidence-equivalence consistency")
    c_y = _mk(report, "Y", "distractor taxonomy semantic constraints")
    c_aa = _mk(report, "AA", "model prompt token-budget and provenance")
    c_ab = _mk(report, "AB", "complete instance count for available variants")
    c_ac = _mk(report, "AC", "per-record gold evidence display mapping")
    c_ad = _mk(report, "AD", "temporal-version question-type semantics")

    tok = get_tokenizer(cfg.tokenizer)
    builder = ContextBuilder(cfg, pool, tok)
    prompt_renderer = PromptRenderer(cfg, tok) if cfg.model.id else None
    gold_blocks: Dict[str, str] = {}
    for fam in families:
        for rid in fam.gold_evidence_ids:
            rec = pool.get(rid)
            if rec is not None:
                gold_blocks[rid] = builder.render_record(rec)

    summaries: Dict[str, List[_InstanceSummary]] = defaultdict(list)
    seen_instance_ids: set = set()
    token_dist: Dict[int, List[int]] = defaultdict(list)
    rendered_token_dist: Dict[int, List[int]] = defaultdict(list)
    prompt_overhead_dist: Dict[int, List[int]] = defaultdict(list)
    remaining_margin_dist: Dict[int, List[int]] = defaultdict(list)
    position_dist: List[float] = []
    distractor_totals: Counter = Counter()
    by_domain: Counter = Counter()
    by_type: Counter = Counter()
    n_instances = 0

    for inst in iter_models(instances_path(cfg), Instance):
        n_instances += 1
        c_a.n_checked += 1
        if inst.instance_id in seen_instance_ids:
            c_a.fail(kind="duplicate_instance_id", instance_id=inst.instance_id)
        seen_instance_ids.add(inst.instance_id)

        fam = fam_by_id.get(inst.question_family_id)
        if fam is None:
            c_a.fail(kind="orphan_instance", instance_id=inst.instance_id,
                     question_family_id=inst.question_family_id)
            continue

        for check, problems in (
            (c_e, leak_checks.check_gold_present(fam, inst.context_record_ids)),
            (c_f, leak_checks.check_gold_absent(fam, inst.context_record_ids)),
            (c_k, ctx_checks.check_token_compliance(inst, cfg.context.min_fill_ratio)),
            (c_l, ctx_checks.check_target_position(
                inst, cfg.context.target_position, cfg.context.position_tolerance)),
            (c_m, ctx_checks.check_record_boundaries(inst)),
            (c_r, ctx_checks.check_no_truncation(inst, _gold_blocks_from_context(inst))),
            (c_s, leak_checks.check_unanswerable_leakage(fam, inst.context_record_ids, pool)),
            (c_v, leak_checks.check_answerable_duplication(fam, inst.context_record_ids, pool)),
            (c_p, _distractor_problems(inst)),
            (c_w, _display_id_problems(inst)),
            (c_ac, _gold_display_map_problems(inst)),
            (c_x, _equivalence_problems(fam, inst, pool)),
            (c_y, _taxonomy_semantic_problems(inst, pool)),
        ):
            check.n_checked += 1
            for p in problems:
                check.fail(instance_id=inst.instance_id, problem=p)
        if cfg.model.id:
            c_aa.n_checked += 1
            for p in _model_prompt_problems(inst, cfg, tok, prompt_renderer):
                c_aa.fail(instance_id=inst.instance_id, problem=p)

        token_dist[inst.context_length_nominal].append(inst.context_tokens_actual)
        if inst.rendered_input_tokens_actual is not None:
            rendered_token_dist[inst.context_length_nominal].append(inst.rendered_input_tokens_actual)
        if inst.prompt_overhead_tokens is not None:
            prompt_overhead_dist[inst.context_length_nominal].append(inst.prompt_overhead_tokens)
        if inst.remaining_context_margin is not None:
            remaining_margin_dist[inst.context_length_nominal].append(inst.remaining_context_margin)
        if inst.target_position_relative is not None:
            position_dist.append(inst.target_position_relative)
        distractor_totals.update(inst.distractor_counts)
        by_domain[inst.domain.value] += 1
        by_type[inst.question_type.value] += 1

        summaries[inst.question_family_id].append(_InstanceSummary(
            instance_id=inst.instance_id,
            question_family_id=inst.question_family_id,
            context_length_nominal=inst.context_length_nominal,
            context_tokens_actual=inst.context_tokens_actual,
            context_record_ids=list(inst.context_record_ids),
            question=inst.question,
            gold_answer=inst.gold_answer,
            gold_answer_normalized=inst.gold_answer_normalized,
            gold_evidence_ids=list(inst.gold_evidence_ids),
            lineage=dict(inst.lineage),
            answerable=inst.answerable,
            target_position_relative=inst.target_position_relative,
            target_evidence_start_token=inst.target_evidence_start_token,
            target_evidence_end_token=inst.target_evidence_end_token,
            domain=inst.domain.value,
            question_type=inst.question_type.value,
            distractor_counts=dict(inst.distractor_counts),
        ))

    # ---- cross-variant checks --------------------------------------------------------
    c_g = _mk(report, "G", "identical question across context-length variants")
    c_h = _mk(report, "H", "identical gold answer across context-length variants")
    c_i = _mk(report, "I", "identical gold evidence across context-length variants")
    c_j = _mk(report, "J", "nested-context lineage")

    for fam in families:
        c_ad.n_checked += 1
        for p in _temporal_version_semantic_problems(fam, active_domains=set(cfg.enabled_domains())):
            c_ad.fail(question_family_id=fam.question_family_id, problem=p)
        variants = sorted(summaries.get(fam.question_family_id, []),
                          key=lambda s: s.context_length_nominal)
        if not variants:
            continue
        c_g.n_checked += 1
        c_h.n_checked += 1
        c_i.n_checked += 1
        c_j.n_checked += 1

        for s in variants:
            if s.question != fam.question:
                c_g.fail(instance_id=s.instance_id, problem="question text differs from its family")
            if s.gold_answer != fam.gold_answer or s.gold_answer_normalized != fam.gold_answer_normalized:
                c_h.fail(instance_id=s.instance_id,
                         problem=f"gold answer {s.gold_answer!r} differs from family {fam.gold_answer!r}")
            if s.gold_evidence_ids != list(fam.gold_evidence_ids):
                c_i.fail(instance_id=s.instance_id, problem="gold evidence IDs differ from family")
        if len({s.question for s in variants}) > 1:
            c_g.fail(question_family_id=fam.question_family_id, problem="variants disagree on question text")
        if len({(str(s.gold_answer), str(s.gold_answer_normalized)) for s in variants}) > 1:
            c_h.fail(question_family_id=fam.question_family_id, problem="variants disagree on gold answer")
        if len({tuple(s.gold_evidence_ids) for s in variants}) > 1:
            c_i.fail(question_family_id=fam.question_family_id, problem="variants disagree on gold evidence")
        if len({s.lineage.get("gold_block_sha256") for s in variants}) > 1:
            c_i.fail(question_family_id=fam.question_family_id,
                     problem="gold evidence block is not byte-identical across variants")

        for problem in _nesting_problems(variants):
            c_j.fail(question_family_id=fam.question_family_id, problem=problem)

    c_ab.n_checked = 1
    if len(unavailable) == 0:
        expected_instances = len(families) * len(cfg.context.lengths)
        if n_instances != expected_instances:
            c_ab.fail(
                kind="complete_instance_count_mismatch",
                expected=expected_instances,
                actual=n_instances,
                families=len(families),
                context_conditions=len(cfg.context.lengths),
            )

    # ---- stats ------------------------------------------------------------------------
    report.stats = {
        "n_families": len(families),
        "n_instances": n_instances,
        "n_unavailable_variants": len(unavailable),
        "normalized_records_by_domain": {d.value: n for d, n in pool_counts.items()},
        "families_by_domain": dict(Counter(f.domain.value for f in families)),
        "families_by_question_type": dict(Counter(f.question_type.value for f in families)),
        "families_answerable": sum(1 for f in families if f.answerable),
        "families_unanswerable": sum(1 for f in families if not f.answerable),
        "instances_by_domain": dict(by_domain),
        "instances_by_question_type": dict(by_type),
        "instances_by_length": {str(k): len(v) for k, v in sorted(token_dist.items())},
        "token_stats_by_length": {
            str(k): _describe(v) for k, v in sorted(token_dist.items())
        },
        "rendered_input_token_stats_by_length": {
            str(k): _describe(v) for k, v in sorted(rendered_token_dist.items())
        },
        "prompt_overhead_token_stats_by_length": {
            str(k): _describe(v) for k, v in sorted(prompt_overhead_dist.items())
        },
        "remaining_context_margin_by_length": {
            str(k): _describe(v) for k, v in sorted(remaining_margin_dist.items())
        },
        "target_position": _describe(position_dist, decimals=4),
        "distractor_totals": dict(distractor_totals),
        "unavailable_by_length": dict(Counter(str(u.context_length_nominal) for u in unavailable)),
        "unavailable_by_reason": dict(Counter(u.reason_code for u in unavailable)),
        "tokenizer": tok.tokenizer_id,
        "tokenizer_version": tok.version,
        "tokenizer_class": tok.tokenizer_class,
        "tokenizer_revision": tok.tokenizer_revision,
        "model_id": cfg.model.id,
        "model_context_limit": tok.model_context_limit,
        "model_config_revision": tok.model_config_revision,
        "generation_tokens_reserved": cfg.model.max_new_tokens if cfg.model.id else None,
        "prompt_version": LLAMA_PROMPT_VERSION if cfg.model.id else None,
        "prompt_hash": prompt_renderer.prompt_hash if prompt_renderer else None,
        "response_format_version": RESPONSE_FORMAT_VERSION if cfg.model.id else None,
        "template_date": cfg.model_prompt.template_date if cfg.model.id else None,
        "chat_template_used": tok.has_chat_template,
        "tokenizer_is_approximate": tok.is_approximate,
        "config_hash": cfg.config_hash,
        "seed": cfg.seed,
    }

    for check in report.checks:
        if not check.passed and not check.message:
            check.message = f"{check.n_failed} failure(s); first: {check.failures[0] if check.failures else 'n/a'}"
    return report


# --------------------------------------------------------------------------------------
# Individual check bodies
# --------------------------------------------------------------------------------------


def _model_prompt_problems(inst: Instance, cfg: PipelineConfig, tok: Any,
                           renderer: Optional[PromptRenderer]) -> List[str]:
    problems: List[str] = []
    if renderer is None:
        problems.append("model id configured but prompt renderer is unavailable")
        return problems
    expected_tokenizer = f"hf:{cfg.model.id}"
    if inst.model_id != cfg.model.id:
        problems.append(f"model_id {inst.model_id!r} != configured {cfg.model.id!r}")
    if inst.tokenizer != expected_tokenizer:
        problems.append(f"tokenizer {inst.tokenizer!r} != expected {expected_tokenizer!r}")
    if tok.is_approximate:
        problems.append("tokenizer fallback/approximation was used")
    if not tok.has_chat_template:
        problems.append("native chat template was not available")
    if inst.prompt_hash != renderer.prompt_hash:
        problems.append(f"prompt_hash {inst.prompt_hash!r} != {renderer.prompt_hash!r}")
    if inst.prompt_version != LLAMA_PROMPT_VERSION:
        problems.append(f"unexpected prompt_version {inst.prompt_version!r}")
    if inst.response_format_version != RESPONSE_FORMAT_VERSION:
        problems.append(f"unexpected response_format_version {inst.response_format_version!r}")
    if inst.generation_tokens_reserved != cfg.model.max_new_tokens:
        problems.append(
            f"generation reserve {inst.generation_tokens_reserved!r} != {cfg.model.max_new_tokens}"
        )
    if inst.model_context_limit != tok.model_context_limit:
        problems.append(
            f"model_context_limit {inst.model_context_limit!r} != tokenizer {tok.model_context_limit!r}"
        )
    if tok.model_context_limit is None:
        problems.append("model context limit is unknown")
        return problems
    safe_input_budget = tok.model_context_limit - cfg.model.max_new_tokens
    if cfg.model_prompt.max_rendered_input_tokens is not None:
        safe_input_budget = min(safe_input_budget, cfg.model_prompt.max_rendered_input_tokens)
    rendered = renderer.render(context=inst.context, question=inst.question).token_count
    preview = renderer.render_text_preview(context="", question="")
    expected_date = f"Today Date: {cfg.model_prompt.template_date}"
    if expected_date not in preview:
        problems.append(f"frozen chat-template date missing from rendered prompt: {expected_date}")
    if inst.rendered_input_tokens_actual != rendered:
        problems.append(
            f"rendered_input_tokens_actual {inst.rendered_input_tokens_actual!r} != recomputed {rendered}"
        )
    if rendered > safe_input_budget:
        problems.append(
            f"rendered input {rendered} exceeds safe budget {safe_input_budget} "
            f"(context limit {tok.model_context_limit}, reserve {cfg.model.max_new_tokens})"
        )
    expected_margin = safe_input_budget - rendered
    if inst.remaining_context_margin != expected_margin:
        problems.append(
            f"remaining_context_margin {inst.remaining_context_margin!r} != {expected_margin}"
        )
    expected_overhead = rendered - inst.context_tokens_actual
    if inst.prompt_overhead_tokens != expected_overhead:
        problems.append(
            f"prompt_overhead_tokens {inst.prompt_overhead_tokens!r} != {expected_overhead}"
        )
    if inst.context_length_label and inst.context_length_label not in inst.instance_id:
        problems.append("context_length_label is not reflected in instance_id")
    text = "\n".join(m["content"] for m in renderer.messages(context=inst.context, question=inst.question))
    lowered = text.lower()
    for forbidden in ("answerable", "gold_answer", "gold evidence", "question_type", "distractor_type"):
        if forbidden in lowered:
            problems.append(f"internal metadata term appears in rendered prompt messages: {forbidden}")
    return problems


def _gold_blocks_from_context(inst: Instance) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not inst.answerable:
        return out
    for rid in inst.gold_evidence_ids:
        did = next((d for d, c in inst.display_id_to_record_id.items() if c == rid), None)
        if did is None:
            continue
        marker = f'<RECORD id="{did}"'
        start = inst.context.find(marker)
        if start < 0:
            continue
        end = inst.context.find("</RECORD>", start)
        if end < 0:
            continue
        out[rid] = inst.context[start:end + len("</RECORD>")]
    return out


def _check_provenance(fam: QuestionFamily, check: CheckResult) -> None:
    check.n_checked += 1
    if not fam.source_provenance:
        check.fail(question_family_id=fam.question_family_id, problem="no source provenance recorded")
        return
    if not any(p.source for p in fam.source_provenance):
        check.fail(question_family_id=fam.question_family_id, problem="provenance entries have no source name")
    covered = {rid for p in fam.source_provenance for rid in p.record_ids}
    missing = [rid for rid in fam.gold_evidence_ids if rid not in covered]
    if missing:
        check.fail(question_family_id=fam.question_family_id,
                   problem=f"gold evidence not covered by any provenance entry: {missing[:3]}")
    for ev in fam.gold_evidence:
        if not ev.record_id:
            check.fail(question_family_id=fam.question_family_id, problem="gold evidence without a record ID")
    if fam.generation_metadata.config_hash == "" or fam.generation_metadata.template_id == "":
        check.fail(question_family_id=fam.question_family_id,
                   problem="generation metadata missing config hash or template id")


def _check_gold(fam: QuestionFamily, pool: RecordPool, rel_tol: float, check: CheckResult) -> None:
    check.n_checked += 1
    for problem in verify_family(fam, pool, rel_tol):
        check.fail(question_family_id=fam.question_family_id, problem=problem)


def _check_units(fam: QuestionFamily, pool: RecordPool, check: CheckResult) -> None:
    spec = fam.calculation_spec
    if spec is None:
        return
    check.n_checked += 1
    if spec.operation not in _UNIT_HOMOGENEOUS_OPS:
        return
    units = set()
    for rid in spec.operands.values():
        rec = pool.get(rid)
        if rec is not None:
            units.add(rec.unit)
    if len(units) > 1:
        check.fail(question_family_id=fam.question_family_id,
                   problem=f"{spec.operation.value} mixes operand units {sorted(str(u) for u in units)}")


def _check_answer_schema(fam: QuestionFamily, c_o: CheckResult, c_q: CheckResult) -> None:
    c_o.n_checked += 1
    c_q.n_checked += 1
    at, norm = fam.answer_type, fam.gold_answer_normalized

    if fam.answerable:
        if at is AnswerType.INSUFFICIENT_EVIDENCE:
            c_o.fail(question_family_id=fam.question_family_id,
                     problem="answerable family typed INSUFFICIENT_EVIDENCE")
        if at in (AnswerType.NUMERIC, AnswerType.PERCENT, AnswerType.INTEGER):
            if not isinstance(norm, (int, float)) or isinstance(norm, bool):
                c_o.fail(question_family_id=fam.question_family_id,
                         problem=f"{at.value} answer normalized to non-numeric {type(norm).__name__}")
            elif not math.isfinite(float(norm)):
                c_q.fail(question_family_id=fam.question_family_id,
                         problem=f"non-finite gold_answer_normalized: {norm}")
            if fam.numeric_tolerance is None:
                c_o.fail(question_family_id=fam.question_family_id,
                         problem=f"{at.value} answer has no numeric_tolerance")
            elif fam.numeric_tolerance < 0 or not math.isfinite(fam.numeric_tolerance):
                c_q.fail(question_family_id=fam.question_family_id,
                         problem=f"invalid numeric_tolerance {fam.numeric_tolerance}")
        else:
            if not isinstance(norm, str) or not norm.strip():
                c_o.fail(question_family_id=fam.question_family_id,
                         problem=f"{at.value} answer normalized to {norm!r}")
    else:
        if at is not AnswerType.INSUFFICIENT_EVIDENCE or norm != INSUFFICIENT_EVIDENCE:
            c_o.fail(question_family_id=fam.question_family_id,
                     problem=f"unanswerable family typed {at.value} / normalized {norm!r}")
        if fam.unanswerable_spec is None or not fam.unanswerable_spec.verified_absent_in_pool:
            c_o.fail(question_family_id=fam.question_family_id,
                     problem="unanswerable family without a verified-absence spec")


def _check_calculation_operands(fam: QuestionFamily, pool: RecordPool, check: CheckResult) -> None:
    if fam.question_type is not QuestionType.RETRIEVAL_CALCULATION:
        return
    check.n_checked += 1
    spec = fam.calculation_spec
    if spec is None:
        check.fail(question_family_id=fam.question_family_id, problem="no calculation_spec")
        return
    if not spec.operands or not spec.operand_values:
        check.fail(question_family_id=fam.question_family_id, problem="calculation_spec has no operands")
        return
    if set(spec.operands) != set(spec.operand_values):
        check.fail(question_family_id=fam.question_family_id,
                   problem=f"operand roles {sorted(spec.operands)} != value roles {sorted(spec.operand_values)}")
    for role, rid in spec.operands.items():
        if pool.get(rid) is None:
            check.fail(question_family_id=fam.question_family_id,
                       problem=f"operand {role!r} record {rid} missing from the pool")
        if rid not in fam.gold_evidence_ids:
            check.fail(question_family_id=fam.question_family_id,
                       problem=f"operand {role!r} record {rid} is not listed as gold evidence")
    if not spec.formula.strip():
        check.fail(question_family_id=fam.question_family_id, problem="calculation_spec has an empty formula")


def _check_question_answerability_leakage(fam: QuestionFamily, check: CheckResult) -> None:
    check.n_checked += 1
    phrases = answerability_leakage_phrases(fam.question)
    if phrases:
        check.fail(
            question_family_id=fam.question_family_id,
            problem=f"model-facing question contains answerability-leakage phrase(s): {phrases}",
        )
    if "answerable" in fam.question.lower():
        check.fail(
            question_family_id=fam.question_family_id,
            problem="model-facing question contains hidden metadata label 'answerable'",
        )


def _distractor_problems(inst: Instance) -> List[str]:
    problems: List[str] = []
    n_gold = len(inst.gold_evidence_ids) if inst.answerable else 0
    expected = len(inst.context_record_ids) - n_gold
    if len(inst.distractors) != expected:
        problems.append(
            f"{len(inst.distractors)} distractor entries for {expected} non-gold records in context"
        )
    if sum(inst.distractor_counts.values()) != len(inst.distractors):
        problems.append(
            f"distractor_counts sum {sum(inst.distractor_counts.values())} != "
            f"{len(inst.distractors)} distractor entries"
        )
    valid_types = {t.value for t in DistractorType}
    for d in inst.distractors[:5000]:
        if d.distractor_type.value not in valid_types:
            problems.append(f"unknown distractor type {d.distractor_type}")
        if not d.relationship_to_target:
            problems.append(f"distractor {d.record_id} has no relationship_to_target metadata")
        if d.position_index is None or d.side not in ("before", "after"):
            problems.append(f"distractor {d.record_id} has incomplete placement metadata")
        if len(problems) > 10:
            break
    return problems


def _display_id_problems(inst: Instance) -> List[str]:
    problems: List[str] = []
    if len(inst.context_display_ids) != len(inst.context_record_ids):
        problems.append("context_display_ids length differs from context_record_ids")
        return problems
    if len(set(inst.context_display_ids)) != len(inst.context_display_ids):
        problems.append("duplicate display IDs inside context")
    if set(inst.display_id_to_record_id) != set(inst.context_display_ids):
        problems.append("display_id_to_record_id keys differ from context_display_ids")
    for did, rid in zip(inst.context_display_ids, inst.context_record_ids):
        if inst.display_id_to_record_id.get(did) != rid:
            problems.append(f"display ID {did} maps to {inst.display_id_to_record_id.get(did)!r}, expected {rid!r}")
        if not DISPLAY_ID_RE.match(did):
            problems.append(f"display ID {did!r} is not opaque R<hex>")
        if rid in did:
            problems.append(f"display ID {did!r} contains its canonical record ID")
        if len(problems) > 10:
            break
    expected_gold = [inst.display_id_to_record_id.get(did) for did in inst.gold_evidence_display_ids]
    if expected_gold and expected_gold != inst.gold_evidence_ids:
        problems.append("gold_evidence_display_ids do not map to gold_evidence_ids")
    if inst.gold_evidence_canonical_ids and inst.gold_evidence_canonical_ids != inst.gold_evidence_ids:
        problems.append("gold_evidence_canonical_ids differs from gold_evidence_ids")
    return problems


def _gold_display_map_problems(inst: Instance) -> List[str]:
    problems: List[str] = []
    if not inst.answerable:
        if inst.gold_evidence_display_map:
            problems.append("unanswerable instance carries gold_evidence_display_map")
        return problems
    if len(inst.gold_evidence_display_map) != len(inst.gold_evidence_ids):
        problems.append(
            f"gold_evidence_display_map has {len(inst.gold_evidence_display_map)} rows for "
            f"{len(inst.gold_evidence_ids)} gold records"
        )
        return problems
    by_gold = {g.gold_record_id: g for g in inst.gold_evidence_equivalence_groups}
    seen = set()
    for mapping, expected_rid in zip(inst.gold_evidence_display_map, inst.gold_evidence_ids):
        if mapping.canonical_record_id != expected_rid:
            problems.append(
                f"gold display mapping canonical {mapping.canonical_record_id!r} != expected {expected_rid!r}"
            )
        if mapping.canonical_record_id in seen:
            problems.append(f"duplicate gold display mapping for {mapping.canonical_record_id}")
        seen.add(mapping.canonical_record_id)
        if mapping.display_id not in inst.display_id_to_record_id:
            problems.append(f"gold display ID {mapping.display_id!r} missing from display map")
        elif inst.display_id_to_record_id[mapping.display_id] != mapping.canonical_record_id:
            problems.append(
                f"gold display ID {mapping.display_id!r} maps to "
                f"{inst.display_id_to_record_id[mapping.display_id]!r}, expected {mapping.canonical_record_id!r}"
            )
        group = by_gold.get(mapping.canonical_record_id)
        expected_canonical = list(group.canonical_record_ids) if group else [mapping.canonical_record_id]
        expected_display = list(group.display_ids) if group else [mapping.display_id]
        if mapping.equivalent_canonical_ids != expected_canonical:
            problems.append(
                f"equivalent_canonical_ids for {mapping.canonical_record_id} do not match its equivalence group"
            )
        if mapping.equivalent_display_ids != expected_display:
            problems.append(
                f"equivalent_display_ids for {mapping.canonical_record_id} do not match its equivalence group"
            )
        if len(inst.gold_evidence_ids) > 1 and set(mapping.equivalent_display_ids) == set(inst.gold_evidence_display_ids):
            if len(mapping.equivalent_display_ids) > 1:
                problems.append(
                    f"multi-evidence mapping for {mapping.canonical_record_id} appears to include all gold IDs"
                )
        if len(problems) > 10:
            break
    return problems


def _equivalence_problems(fam: QuestionFamily, inst: Instance, pool: RecordPool) -> List[str]:
    problems: List[str] = []
    require_version = family_requires_version_equivalence(fam)
    for group in inst.gold_evidence_equivalence_groups:
        if group.gold_record_id not in inst.gold_evidence_ids:
            problems.append(f"equivalence group {group.group_id} refers to non-gold {group.gold_record_id}")
            continue
        gold = pool.get(group.gold_record_id)
        if gold is None:
            problems.append(f"equivalence group gold {group.gold_record_id} missing from pool")
            continue
        if group.gold_record_id not in group.canonical_record_ids:
            problems.append(f"equivalence group {group.group_id} omits its gold record")
        for rid in group.canonical_record_ids:
            rec = pool.get(rid)
            if rec is None:
                problems.append(f"equivalent record {rid} missing from pool")
                continue
            if rid not in inst.context_record_ids:
                problems.append(f"equivalent record {rid} is not present in this context")
            if not records_equivalent(gold, rec, require_version=require_version):
                problems.append(f"record {rid} is not semantically equivalent to gold {group.gold_record_id}")
            dids = [d for d, c in inst.display_id_to_record_id.items() if c == rid]
            if dids and dids[0] not in group.display_ids:
                problems.append(f"equivalent record {rid} display ID missing from group")
            if len(problems) > 10:
                return problems
    return problems


def _temporal_version_semantic_problems(
    fam: QuestionFamily,
    active_domains: Optional[set[Domain]] = None,
) -> List[str]:
    if fam.question_type is not QuestionType.TEMPORAL_VERSION:
        return []
    if fam.domain is Domain.WORLD_BANK:
        return []
    template_id = fam.generation_metadata.template_id
    version_templates = {
        "SEC_QUARTER_VS_ANNUAL_FRAME",
        "SEC_FILING_VERSION_SELECTION",
        "FDA_ORIGINAL_VS_SUPPLEMENT",
        "FRED_VINTAGE_SELECTION",
    }
    if template_id not in version_templates:
        return [
            f"TEMPORAL_VERSION template {template_id!r} is not registered as a true "
            "version/time-state distinction"
        ]
    return []


def _taxonomy_semantic_problems(inst: Instance, pool: RecordPool) -> List[str]:
    problems: List[str] = []
    if not inst.answerable:
        bad = [d.record_id for d in inst.distractors if d.distractor_type is DistractorType.NEAR_MATCH_VALUE]
        if bad:
            problems.append(f"unanswerable instance has NEAR_MATCH_VALUE distractors: {bad[:5]}")
    for d in inst.distractors[:5000]:
        rec = pool.get(d.record_id)
        if rec is None:
            continue
        if d.distractor_type is DistractorType.WRONG_UNIT and d.relationship_to_target.get("same_unit"):
            problems.append(f"WRONG_UNIT distractor {d.record_id} has same_unit=true")
        if d.distractor_type is DistractorType.WRONG_SERIES_VARIANT:
            if not d.relationship_to_target.get("same_unit"):
                problems.append(f"WRONG_SERIES_VARIANT distractor {d.record_id} does not have same_unit=true")
        if len(problems) > 10:
            break
    return problems


def _nesting_problems(variants: List[_InstanceSummary]) -> List[str]:
    problems: List[str] = []
    for shorter, longer in zip(variants, variants[1:]):
        s_ids, l_ids = shorter.context_record_ids, longer.context_record_ids
        missing = set(s_ids) - set(l_ids)
        if missing:
            problems.append(
                f"{shorter.instance_id} -> {longer.instance_id}: {len(missing)} records dropped "
                f"(e.g. {sorted(missing)[:3]}); contexts are not nested"
            )
            continue
        if not ctx_checks.is_subsequence(s_ids, l_ids):
            problems.append(
                f"{shorter.instance_id} -> {longer.instance_id}: records are a subset but their "
                "relative order changed; nesting requires an ordered subsequence"
            )
        if len(l_ids) <= len(s_ids):
            problems.append(
                f"{shorter.instance_id} ({len(s_ids)} records) -> {longer.instance_id} "
                f"({len(l_ids)} records): longer variant did not grow"
            )
        declared = longer.lineage.get("extends_instance_id")
        if declared != shorter.instance_id:
            problems.append(
                f"{longer.instance_id} declares lineage parent {declared!r}, expected {shorter.instance_id!r}"
            )
    return problems


def _describe(values: Sequence[float], decimals: int = 1) -> Dict[str, Any]:
    if not values:
        return {"n": 0}
    s = sorted(values)
    n = len(s)

    def pct(p: float) -> float:
        idx = min(n - 1, max(0, int(round(p * (n - 1)))))
        return round(float(s[idx]), decimals)

    return {
        "n": n,
        "min": round(float(s[0]), decimals),
        "p25": pct(0.25),
        "median": pct(0.50),
        "p75": pct(0.75),
        "max": round(float(s[-1]), decimals),
        "mean": round(sum(s) / n, decimals),
    }
