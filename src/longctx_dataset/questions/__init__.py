"""Question-family generation.

``generate_families_for_domain`` turns a configured question-type mix into concrete
families by allocating a budget across the templates registered for that domain. A
template that cannot honestly produce its share returns fewer families and the shortfall
is redistributed to its siblings of the same question type -- never padded with a
different question type, because the mix is an experimental design parameter.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..config import PipelineConfig
from ..normalize.common import RecordPool
from ..schemas import Domain, QuestionFamily, QuestionType
from .base import (  # noqa: F401
    CalculationError,
    QuestionTemplate,
    TemplateContext,
    allocate_counts,
    build_calculation,
    register_template,
    templates_for,
)

# Import for side-effect registration.
from . import sec_templates, fda_templates, clinical_templates, world_bank_templates  # noqa: F401,E402

DEFAULT_MIX: Dict[QuestionType, float] = {
    QuestionType.DIRECT_RETRIEVAL: 0.20,
    QuestionType.RETRIEVAL_CALCULATION: 0.30,
    QuestionType.TEMPORAL_VERSION: 0.15,
    QuestionType.ENTITY_UNIT_BINDING: 0.15,
    QuestionType.UNANSWERABLE: 0.20,
}


def generate_families_for_domain(
    domain: Domain,
    cfg: PipelineConfig,
    pool: RecordPool,
    git_sha: Optional[str] = None,
) -> List[QuestionFamily]:
    """Allocate the configured mix across the domain's templates.

    Two properties matter here and are enforced explicitly:

    * **No duplicate families.** A template asked twice returns the same deterministic
      prefix, so acceptance is gated on unseen question *text*, not on the freshly minted
      family ID -- which would never collide and would therefore never deduplicate.
    * **No padding across question types.** A type whose templates are exhausted simply
      yields fewer families; the deficit is never backfilled from another type, because
      the mix is an experimental design parameter rather than a quota to hit.
    """
    domain_cfg = cfg.domains.get(domain)
    if domain_cfg is None or not domain_cfg.enabled:
        return []
    total = domain_cfg.n_families
    if total <= 0:
        return []

    mix = domain_cfg.question_type_mix or DEFAULT_MIX
    budget = allocate_counts(mix, total)
    ctx = TemplateContext(cfg, pool, domain, git_sha=git_sha)
    families: List[QuestionFamily] = []
    seen_questions: set = set()

    for qtype in sorted(budget, key=lambda q: q.value):
        want = budget[qtype]
        candidates = templates_for(domain, qtype)
        if want <= 0 or not candidates:
            continue
        produced: List[QuestionFamily] = []
        exhausted: set = set()

        def take(tmpl, ask: int) -> int:
            """Ask one template for ``ask`` more families; return how many were accepted."""
            got = tmpl.generate(ctx, ask + len(produced))
            fresh = [f for f in got if f.question not in seen_questions]
            accepted = 0
            for fam in fresh:
                if accepted >= ask:
                    break
                seen_questions.add(fam.question)
                produced.append(fam)
                accepted += 1
            if accepted < ask:
                exhausted.add(tmpl.template_id)
            return accepted

        # Pass 1: even split, so no single template dominates a question type.
        per = max(1, want // len(candidates))
        for tmpl in candidates:
            if len(produced) >= want:
                break
            take(tmpl, min(per, want - len(produced)))

        # Pass 2: let templates that still had capacity absorb the remainder.
        for tmpl in candidates:
            if len(produced) >= want:
                break
            if tmpl.template_id in exhausted:
                continue
            take(tmpl, want - len(produced))

        families.extend(produced[:want])

    # Renumber after selection so IDs are dense and stable regardless of how many
    # candidate families were generated and discarded along the way.
    prefix = candidates[0].id_prefix if (families and candidates) else domain.value[:3]
    for i, fam in enumerate(families, 1):
        fam.question_family_id = f"{fam.question_family_id.rsplit('_', 1)[0]}_{i:04d}"
    return families
