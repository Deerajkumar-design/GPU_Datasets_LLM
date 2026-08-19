# Experiment D Full Deterministic Grading

- successful responses graded: `2998`
- runtime failures excluded from factual grading: `2`
- correct: `1169`
- inaccurate: `1829`
- hallucinatory inaccuracies: `1132`
- grounded inaccuracies: `678`
- ambiguous-review cases: `19`
- format failures: `0`
- error type counts: `{'CORRECT': 1169, 'UNSUPPORTED_VALUE': 697, 'WRONG_VERSION': 109, 'WRONG_PERIOD': 134, 'CALCULATION_ERROR': 68, 'WRONG_ENTITY': 241, 'FAILED_TO_ABSTAIN': 435, 'UNNECESSARY_ABSTENTION': 66, 'AMBIGUOUS_REVIEW_REQUIRED': 19, 'WRONG_UNIT': 8, 'WRONG_SERIES_VARIANT': 13, 'WRONG_FIELD': 39}`
- Experiment D grader hash: `d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8`
- scored results hash: `7ab4f8df193ae9f5bba2f8ab23b5e1662deee4185b27039f79f08532b6062f17`

Runtime failures are preserved separately and are not factual inaccuracies.
No regression, p-value, confidence interval, odds ratio, or trend test was run.

## Counts By Context

| Context | Gradable N | Correct | Inaccurate | Hallucinatory | Grounded | Ambiguous | Runtime failures |
|---|---:|---:|---:|---:|---:|---:|---:|
| 4K | 500 | 250 | 250 | 171 | 76 | 3 | 0 |
| 8K | 500 | 227 | 273 | 186 | 85 | 2 | 0 |
| 16K | 500 | 205 | 295 | 174 | 120 | 1 | 0 |
| 32K | 500 | 191 | 309 | 191 | 114 | 4 | 0 |
| 64K | 500 | 151 | 349 | 209 | 135 | 5 | 0 |
| 82K | 498 | 145 | 353 | 201 | 148 | 4 | 2 |
