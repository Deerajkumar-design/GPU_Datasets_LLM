# Human-audit package

_Generated 2026-08-09T19:14:14Z · seed `20240817` · datasets: `ct_audit_v3`_

_Scope: the four active domains (SEC, FDA, ClinicalTrials.gov, FRED). World Bank is excluded — its API proved too unreliable to keep in the experiment, so auditing it would spend review effort on a source that will not reach production._

## Status: PENDING_HUMAN_REVIEW

1 question families were sampled for manual inspection, spanning every active domain and all five question types, including both answerable and unanswerable cases. Nothing here has been auto-approved: every checklist in every family file is unticked by design.

Automated validation already proves these families are internally consistent — gold answers recompute from source records, contexts nest, evidence sits at ~50%. What it cannot judge is whether a question reads naturally, whether the distractors are genuinely tempting, and whether the 128K context is *meaningfully* harder than the 4K one. That is what this package is for.

## How to review

1. Open `<FAMILY>.md` for the question, gold answer, evidence and context metadata.
2. Open `<FAMILY>_4K.txt` and `<FAMILY>_128K.txt` — these are the exact, untruncated model-facing contexts, with no added headers.
3. Find the gold evidence record IDs (listed in the `.md`) inside each context.
4. Work the checklist at the bottom of the `.md` and record notes there.

## Selected families

| family | domain | type | answerable | gold answer | 4K tok | 128K tok | 4K recs | 128K recs | pos 4K | pos 128K | files |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `CT_0007` | CLINICAL_TRIALS | UNANSWERABLE | **no** | `INSUFFICIENT_EVIDENCE` | 4,020 | 129,823 | 39 | 1,184 | n/a | n/a | [md](CT_0007.md) · [4K](CT_0007_4K.txt) · [128K](CT_0007_128K.txt) |

## Coverage

| domain | families |
|---|---|
| CLINICAL_TRIALS | 1 |

| question type | families |
|---|---|
| UNANSWERABLE | 1 |

Answerable: 0 · Unanswerable: 1

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
