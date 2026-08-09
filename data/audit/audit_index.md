# Human-audit package

_Generated 2026-08-09T18:11:13Z · seed `20240817` · datasets: `pilot`, `fred_pilot`_

_Scope: the four active domains (SEC, FDA, ClinicalTrials.gov, FRED). World Bank is excluded — its API proved too unreliable to keep in the experiment, so auditing it would spend review effort on a source that will not reach production._

## Status: PENDING_HUMAN_REVIEW

12 question families were sampled for manual inspection, spanning every active domain and all five question types, including both answerable and unanswerable cases. Nothing here has been auto-approved: every checklist in every family file is unticked by design.

Automated validation already proves these families are internally consistent — gold answers recompute from source records, contexts nest, evidence sits at ~50%. What it cannot judge is whether a question reads naturally, whether the distractors are genuinely tempting, and whether the 128K context is *meaningfully* harder than the 4K one. That is what this package is for.

## How to review

1. Open `<FAMILY>.md` for the question, gold answer, evidence and context metadata.
2. Open `<FAMILY>_4K.txt` and `<FAMILY>_128K.txt` — these are the exact, untruncated model-facing contexts, with no added headers.
3. Find the gold evidence record IDs (listed in the `.md`) inside each context.
4. Work the checklist at the bottom of the `.md` and record notes there.

## Selected families

| family | domain | type | answerable | gold answer | 4K tok | 128K tok | 4K recs | 128K recs | pos 4K | pos 128K | files |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CT_0001` | CLINICAL_TRIALS | DIRECT_RETRIEVAL | yes | `24` | 4,012 | 129,929 | 34 | 1,073 | 0.482 | 0.500 | [md](CT_0001.md) · [4K](CT_0001_4K.txt) · [128K](CT_0001_128K.txt) |
| `FDA_0003` | FDA | ENTITY_UNIT_BINDING | yes | `40MG` | 4,058 | 129,923 | 37 | 1,137 | 0.496 | 0.500 | [md](FDA_0003.md) · [4K](FDA_0003_4K.txt) · [128K](FDA_0003_128K.txt) |
| `FRED_0007` | FRED | RETRIEVAL_CALCULATION | yes | `-0.42%` | 4,032 | 129,757 | 41 | 1,314 | 0.502 | 0.500 | [md](FRED_0007.md) · [4K](FRED_0007_4K.txt) · [128K](FRED_0007_128K.txt) |
| `SEC_0006` | SEC | TEMPORAL_VERSION | yes | `-16,276,000,000` | 3,984 | 130,262 | 23 | 738 | 0.502 | 0.500 | [md](SEC_0006.md) · [4K](SEC_0006_4K.txt) · [128K](SEC_0006_128K.txt) |
| `CT_0007` | CLINICAL_TRIALS | UNANSWERABLE | **no** | `INSUFFICIENT_EVIDENCE` | 4,008 | 129,983 | 36 | 1,053 | n/a | n/a | [md](CT_0007.md) · [4K](CT_0007_4K.txt) · [128K](CT_0007_128K.txt) |
| `CT_0008` | CLINICAL_TRIALS | UNANSWERABLE | **no** | `INSUFFICIENT_EVIDENCE` | 4,057 | 129,910 | 35 | 1,091 | n/a | n/a | [md](CT_0008.md) · [4K](CT_0008_4K.txt) · [128K](CT_0008_128K.txt) |
| `FDA_0001` | FDA | DIRECT_RETRIEVAL | yes | `TABLET` | 3,994 | 129,847 | 39 | 1,226 | 0.492 | 0.500 | [md](FDA_0001.md) · [4K](FDA_0001_4K.txt) · [128K](FDA_0001_128K.txt) |
| `FRED_0003` | FRED | ENTITY_UNIT_BINDING | yes | `149,952` | 3,992 | 129,649 | 43 | 1,389 | 0.498 | 0.500 | [md](FRED_0003.md) · [4K](FRED_0003_4K.txt) · [128K](FRED_0003_128K.txt) |
| `SEC_0004` | SEC | RETRIEVAL_CALCULATION | yes | `5.93%` | 4,051 | 130,220 | 25 | 756 | 0.480 | 0.500 | [md](SEC_0004.md) · [4K](SEC_0004_4K.txt) · [128K](SEC_0004_128K.txt) |
| `FDA_0006` | FDA | TEMPORAL_VERSION | yes | `2018-08-24` | 4,002 | 129,852 | 38 | 1,220 | 0.513 | 0.500 | [md](FDA_0006.md) · [4K](FDA_0006_4K.txt) · [128K](FDA_0006_128K.txt) |
| `FRED_0001` | FRED | DIRECT_RETRIEVAL | yes | `150,895` | 4,048 | 129,609 | 44 | 1,385 | 0.510 | 0.500 | [md](FRED_0001.md) · [4K](FRED_0001_4K.txt) · [128K](FRED_0001_128K.txt) |
| `SEC_0003` | SEC | ENTITY_UNIT_BINDING | yes | `-492,000,000` | 3,953 | 130,234 | 23 | 738 | 0.495 | 0.500 | [md](SEC_0003.md) · [4K](SEC_0003_4K.txt) · [128K](SEC_0003_128K.txt) |

## Coverage

| domain | families |
|---|---|
| CLINICAL_TRIALS | 3 |
| FDA | 3 |
| FRED | 3 |
| SEC | 3 |

| question type | families |
|---|---|
| DIRECT_RETRIEVAL | 3 |
| ENTITY_UNIT_BINDING | 3 |
| RETRIEVAL_CALCULATION | 2 |
| TEMPORAL_VERSION | 2 |
| UNANSWERABLE | 2 |

Answerable: 10 · Unanswerable: 2

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
