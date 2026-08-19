# Manual Adjudication: AMBIGUOUS_REVIEW_REQUIRED

- instance ID: `FDA_0020_32K`
- context length: `32K`
- question type: `TEMPORAL_VERSION`
- answerable: `true`
- question: Using only the Drugs@FDA records supplied in the context, what is the submission status date of the ORIGINAL submission (submission type ORIG) for FDA application ANDA091431 (sponsor: HERITAGE)? Answer in YYYY-MM-DD form.
- gold answer: `2013-12-30`
- model answer: `2023-08-07`

## Target Evidence

- display ID: `RAE3543605D`
- canonical ID: `FDA-ANDA091431-submission-ORIG-1-7b0a53ff`
- entity: `HERITAGE application ANDA091431 [ANDA091431]`
- field: `ORIG submission 1 status date [submission.status_date]`
- period: `2013`
- version: `ORIG-1`
- value: `2013-12-30`

## Relevant Distractors / Context Values

- display ID: `RE46B71ECC3`
- canonical ID: `FDA-ANDA201522-submission-SUPPL-17-84f9253f`
- dataset tag: `OTHER_SAME_DOMAIN`
- entity: `CHARTWELL MOLECULAR application ANDA201522 [ANDA201522]`
- field: `SUPPL submission 17 status date [submission.status_date]`
- period: `2023`
- version: `SUPPL-17`
- value: `2023-08-07`
- relationship flags: different entity, same metric, different period, same unit, different version

Same-target temporal/version distractors also present:

- `R4876AAF4CF`: `FDA-ANDA091431-submission-SUPPL-3-3fd6e976`, tag `WRONG_PERIOD`, value `2020-02-21`, version `SUPPL-3`
- `RD77864B698`: `FDA-ANDA091431-submission-SUPPL-4-396f8c97`, tag `WRONG_PERIOD`, value `2020-09-08`, version `SUPPL-4`
- `R74DB6AB053`: `FDA-ANDA091431-submission-SUPPL-1-e53fec82`, tag `WRONG_PERIOD`, value `2016-01-04`, version `SUPPL-1`
- `R6A26C130CE`: `FDA-ANDA091431-submission-SUPPL-2-8f32f840`, tag `WRONG_PERIOD`, value `2016-01-04`, version `SUPPL-2`

## Why The Frozen Grader Marked It Ambiguous

The deterministic grader found that the model answer `2023-08-07` appears in the supplied context, so it did not mark the value as unsupported. However, the matching record was tagged `OTHER_SAME_DOMAIN`, not one of the specific deterministic error-taxonomy labels. The frozen grader therefore refused to infer a finer label and emitted `AMBIGUOUS_REVIEW_REQUIRED`.

## Manual Adjudication

- answer_correct: `false`
- hallucination: `false`
- error_type: `WRONG_ENTITY`
- justification: The model returned an authentic date from the supplied context, so the value is grounded and not a hallucination. It is not the requested HERITAGE application `ANDA091431` ORIG-1 status date; it belongs to CHARTWELL MOLECULAR application `ANDA201522`, supplement `SUPPL-17`. The primary binding failure is therefore wrong entity, with additional period/version mismatch.

