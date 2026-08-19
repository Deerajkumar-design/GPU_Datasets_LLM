# Experiment C Full Deterministic Grading

- grader sha256: `d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8`
- total scored rows: `500`
- unique instance IDs: `500`
- context counts: `{'64K': 100, '4K': 100, '32K': 100, '8K': 100, '16K': 100}`
- answer correct: `215`
- answer incorrect: `285`
- hallucination=true: `185`
- hallucination=false: `315`
- semantic review count: `1`
- error type counts: `{'CORRECT': 215, 'UNSUPPORTED_VALUE': 122, 'WRONG_ENTITY': 30, 'FAILED_TO_ABSTAIN': 63, 'CALCULATION_ERROR': 10, 'UNNECESSARY_ABSTENTION': 6, 'WRONG_VERSION': 15, 'WRONG_PERIOD': 17, 'WRONG_UNIT': 6, 'WRONG_FIELD': 12, 'WRONG_SERIES_VARIANT': 3, 'AMBIGUOUS_REVIEW_REQUIRED': 1}`
- raw outputs unchanged: `True`
- grader unchanged during scoring: `True`

Evidence-selection accuracy is intentionally not graded for Experiment C because the model was not asked to output evidence IDs.
No LLM judge, fuzzy semantic grader, hypothesis test, confidence interval, regression, or trend analysis was run.

## Semantic Review Cases

- `FDA_0020_32K`: `AMBIGUOUS_REVIEW_REQUIRED` / answer value appears in context but deterministic distractor type is unavailable