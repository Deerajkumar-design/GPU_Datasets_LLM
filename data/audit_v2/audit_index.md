# Human-audit package

_Generated 2026-08-09T19:05:07Z · seed `20240817` · datasets: `pilot_v2`, `fred_pilot_v2`_

_Scope: the four active domains (SEC, FDA, ClinicalTrials.gov, FRED). World Bank is excluded — its API proved too unreliable to keep in the experiment, so auditing it would spend review effort on a source that will not reach production._

## Status: PENDING_HUMAN_REVIEW

4 question families were sampled for manual inspection, spanning every active domain and all five question types, including both answerable and unanswerable cases. Nothing here has been auto-approved: every checklist in every family file is unticked by design.

Automated validation already proves these families are internally consistent — gold answers recompute from source records, contexts nest, evidence sits at ~50%. What it cannot judge is whether a question reads naturally, whether the distractors are genuinely tempting, and whether the 128K context is *meaningfully* harder than the 4K one. That is what this package is for.

## How to review

1. Open `<FAMILY>.md` for the question, gold answer, evidence and context metadata.
2. Open `<FAMILY>_4K.txt` and `<FAMILY>_128K.txt` — these are the exact, untruncated model-facing contexts, with no added headers.
3. Find the gold evidence record IDs (listed in the `.md`) inside each context.
4. Work the checklist at the bottom of the `.md` and record notes there.

## Selected families

| family | domain | type | answerable | gold answer | 4K tok | 128K tok | 4K recs | 128K recs | pos 4K | pos 128K | files |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SEC_0006` | SEC | TEMPORAL_VERSION | yes | `-16,276,000,000` | 3,960 | 130,092 | 28 | 914 | 0.516 | 0.500 | [md](SEC_0006.md) · [4K](SEC_0006_4K.txt) · [128K](SEC_0006_128K.txt) |
| `FDA_0003` | FDA | ENTITY_UNIT_BINDING | yes | `40MG` | 4,034 | 129,712 | 41 | 1,302 | 0.493 | 0.500 | [md](FDA_0003.md) · [4K](FDA_0003_4K.txt) · [128K](FDA_0003_128K.txt) |
| `FRED_0007` | FRED | RETRIEVAL_CALCULATION | yes | `-0.42%` | 4,025 | 129,488 | 48 | 1,524 | 0.489 | 0.500 | [md](FRED_0007.md) · [4K](FRED_0007_4K.txt) · [128K](FRED_0007_128K.txt) |
| `CT_0007` | CLINICAL_TRIALS | UNANSWERABLE | **no** | `INSUFFICIENT_EVIDENCE` | 4,030 | 129,879 | 39 | 1,185 | n/a | n/a | [md](CT_0007.md) · [4K](CT_0007_4K.txt) · [128K](CT_0007_128K.txt) |

## Coverage

| domain | families |
|---|---|
| CLINICAL_TRIALS | 1 |
| FDA | 1 |
| FRED | 1 |
| SEC | 1 |

| question type | families |
|---|---|
| ENTITY_UNIT_BINDING | 1 |
| RETRIEVAL_CALCULATION | 1 |
| TEMPORAL_VERSION | 1 |
| UNANSWERABLE | 1 |

Answerable: 3 · Unanswerable: 1

## Checklist applied to every family

- [ ] Question is grammatically clear
- [ ] Exact entity/period/version/field is unambiguous
- [ ] Gold answer is correct
- [ ] Gold evidence directly supports the answer
- [ ] Calculation is correct if applicable
- [ ] 4K context is answerable when answerable=true
- [ ] 128K context is answerable when answerable=true
- [ ] Unanswerable context genuinely lacks required evidence
- [ ] Distractors are realistic same-domain competitors
- [ ] Distractors do not accidentally reveal the answer
- [ ] 128K context is meaningfully more competitive than 4K
- [ ] No malformed/unnatural record formatting
- [ ] Record IDs are usable for later evidence selection
- [ ] No obvious question-template artifacts make the answer trivial
- [ ] No source-specific information leaks the answer outside intended evidence
