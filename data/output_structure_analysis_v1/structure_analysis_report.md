# Output Structure Analysis

This diagnostic analyzes raw response structure only. It does not grade answer correctness, evidence correctness, hallucination, or accuracy.

- total responses: `500`
- fully usable structured outputs: `212` (42.4%)
- format failures: `288` (57.6%)
- hit 512 generated tokens: `284` (56.8%)
- repetitive truncated selected-evidence degeneration: `276` (55.2%)
- families successful at every length: `10`
- families failed at every length: `18`
- families succeeding at 4K but failing later: `53`

## By Context Length

| context | total | usable | format failures | failure % | hit 512 | degenerate | mean gen toks | median gen toks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4K | 100 | 63 | 37 | 37.0% | 37 | 36 | 218.0 | 57.5 |
| 8K | 100 | 44 | 56 | 56.0% | 55 | 53 | 306.0 | 512.0 |
| 16K | 100 | 32 | 68 | 68.0% | 67 | 66 | 356.9 | 512.0 |
| 32K | 100 | 33 | 67 | 67.0% | 65 | 63 | 345.3 | 512.0 |
| 64K | 100 | 40 | 60 | 60.0% | 60 | 58 | 319.7 | 512.0 |

## By Domain

| domain | total | usable | format failures | failure % | hit 512 | degenerate |
|---|---:|---:|---:|---:|---:|---:|
| SEC | 125 | 47 | 78 | 62.4% | 75 | 73 |
| FDA | 125 | 42 | 83 | 66.4% | 83 | 79 |
| CLINICAL_TRIALS | 125 | 52 | 73 | 58.4% | 73 | 71 |
| FRED | 125 | 71 | 54 | 43.2% | 53 | 53 |

## By Question Type

| question_type | total | usable | format failures | failure % | hit 512 | degenerate |
|---|---:|---:|---:|---:|---:|---:|
| DIRECT_RETRIEVAL | 100 | 24 | 76 | 76.0% | 76 | 72 |
| RETRIEVAL_CALCULATION | 150 | 75 | 75 | 50.0% | 72 | 71 |
| TEMPORAL_VERSION | 55 | 37 | 18 | 32.7% | 18 | 18 |
| ENTITY_UNIT_BINDING | 95 | 32 | 63 | 66.3% | 63 | 63 |
| UNANSWERABLE | 100 | 44 | 56 | 56.0% | 55 | 52 |

## By Answerability

| answerable | total | usable | format failures | failure % | hit 512 | degenerate |
|---|---:|---:|---:|---:|---:|---:|
| True | 400 | 168 | 232 | 58.0% | 229 | 224 |
| False | 100 | 44 | 56 | 56.0% | 55 | 52 |

## Interpretation

The failure mode is both context-independent and context-dependent. There are failures even at 4K, so the JSON schema/output behavior itself is a problem. The failure rate also rises sharply with longer contexts, especially from 16K onward, indicating context length amplifies the degeneration.

No final hallucination-rate or correctness analysis was performed.
