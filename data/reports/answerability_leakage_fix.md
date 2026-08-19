# Answerability Leakage Fix

## Before

Using only the ClinicalTrials.gov records supplied in the context, what is the date on which results were first posted for trial NCT02339493 ("Electronic Alerts for Stroke Prevention in Patients With Atrial Fibrillation or Atrial Flutter")? If the supplied records do not contain this field for this trial, state that the evidence is insufficient rather than inferring it from another date or another trial.

## After

Using only the ClinicalTrials.gov records supplied in the context, what is the date on which results were first posted for trial NCT02339493 ("Electronic Alerts for Stroke Prevention in Patients With Atrial Fibrillation or Atrial Flutter")?

## Common Prompt

Prompt version: `evaluation_v1`

```text
Answer using only the supplied records.

Identify records matching the exact entity, period, version, field, unit, product, route, dosage form, arm, series, or other conditions requested by the question.

If the supplied records do not contain sufficient evidence to answer the question, return INSUFFICIENT_EVIDENCE.

Do not infer or fabricate missing information.
```

## Rationale

The old CT_0007 wording told the model that the requested field might be absent, instructed it to return insufficient evidence for this specific question, and named nearby distractor sources to avoid. That leaked the hidden unanswerable label through question text.

The regenerated question is an ordinary factual request. It names only the source, field, trial ID, and trial title needed to identify the requested fact.

The abstention rule is now stored as a shared evaluation prompt and is independent of question-family answerability. The same prompt can be applied to answerable and unanswerable instances without revealing the internal `answerable` label.

## Validation

- `ct_audit_v3` validation: 26/26 checks passed, 0 critical failures.
- New validation check `Z`: model-facing questions do not leak answerability.
- CT_0007 remains internally `answerable=false`; no gold evidence is carried in contexts.
