# Semantic Audit Report

A stratified 100-family audit sample was assembled from the frozen 500-family dataset: 25 families per active domain, with round-robin coverage across question types.

- Audited families: 100
- Domains: {'SEC': 25, 'FDA': 25, 'CLINICAL_TRIALS': 25, 'FRED': 25}
- Question types: {'DIRECT_RETRIEVAL': 22, 'ENTITY_UNIT_BINDING': 21, 'RETRIEVAL_CALCULATION': 21, 'TEMPORAL_VERSION': 15, 'UNANSWERABLE': 21}
- Issues found in final audit: 0

## Audit Checks Applied

- question wording present and stable across contexts
- deterministic gold answer or INSUFFICIENT_EVIDENCE outcome present
- answerability metadata internal only
- target evidence count/equivalence metadata present for answerable cases
- 82K context contains realistic same-domain distractors and remains within token cap
- target position metadata present where applicable
- no automated validation warning remained after final validator pass

## Issues Found and Fixed During This Phase

- SEC unanswerable generation was conservatively expanded from one missing concept per filer to one distinct missing filer/concept target fact.
- FRED generators were expanded from one task per series/pair to distinct period-specific target facts where the source records support them.
- An initial merge attempt failed to preserve the original 100 family records because an inline shell/heredoc command did not execute. A reproducible merge script was added and the dataset was rebuilt from the corrected family file.

## Result

No unresolved semantic-audit issues remain in the frozen artifact. The full automated validator passed 30/30 checks with 0 warnings.
