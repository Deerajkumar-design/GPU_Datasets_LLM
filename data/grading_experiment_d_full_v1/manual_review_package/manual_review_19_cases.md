# Experiment D Manual Review Package: 19 Ambiguous Cases

No adjudication has been applied in this package. Fill the blank final fields for manual review.

## Case 1: FDA_0099_32K

- instance ID: `FDA_0099_32K`
- family ID: `FDA_0099`
- context length: `32K`
- domain: `FDA`
- question type: `ENTITY_UNIT_BINDING`
- answerable/unanswerable: `answerable`

## Question

Using only the Drugs@FDA records supplied in the context, what is the listed strength of AMLODIPINE BESYLATE in product number 001 under FDA application NDA219531 (dosage form FOR SOLUTION, route ORAL)? Report the strength string exactly as recorded.

## Answers

- gold answer: `EQ 2.5MG BASE/BOT`
- model answer: `EQ 2.5MG BASE/BOT`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Evidence-Equivalent Records

#### Equivalent record group EG004E71A100

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Context Record(s) Matching Model Answer

- record_value: `EQ 2.5MG BASE/BOT`
- distractor_type: `None`
- is_gold_or_equivalent: `True`
#### Matched context record

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Relevant Distractor Values/Tags

- display_id: `R00A7AB31A4`; canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`; distractor_type: `None`; relationship: `matched_context_record_from_grader`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 2: SEC_0086_32K

- instance ID: `SEC_0086_32K`
- family ID: `SEC_0086`
- context length: `32K`
- domain: `SEC`
- question type: `TEMPORAL_VERSION`
- answerable/unanswerable: `answerable`

## Question

Using only the SEC XBRL company-facts records supplied in the context, what value did COCA COLA CO (CIK 0000021344) report for us-gaap:CashAndCashEquivalentsAtCarryingValue for the period ending 2017-12-31 in the MOST RECENTLY FILED version of that fact — accession 0000021344-20-000006, form 10-K, filed 2020-02-24 — in USD? Report the exact value from that version.

## Answers

- gold answer: `6,102,000,000`
- model answer: `12859000000.0`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R2586DAE36F`
- canonical_record_id: `SEC-0000021344-CashAndCashEquivalentsAt-USD-CY2017Q4I-0000021344-20-000006-cb4d9aa2`

```text
entity: COCA COLA CO [0000021344]
field: Cash and Cash Equivalents, at Carrying Value [us-gaap:CashAndCashEquivalentsAtCarryingValue]
period: CY2017Q4I
unit: USD
value: 6102000000.0
version: 10-K|0000021344-20-000006
form: 10-K
accession: 0000021344-20-000006
fiscal_year: 2019
fiscal_period: FY
```


## Evidence-Equivalent Records

#### Equivalent record group EG71CD3A0B8C

- display_id: `R2586DAE36F`
- canonical_record_id: `SEC-0000021344-CashAndCashEquivalentsAt-USD-CY2017Q4I-0000021344-20-000006-cb4d9aa2`

```text
entity: COCA COLA CO [0000021344]
field: Cash and Cash Equivalents, at Carrying Value [us-gaap:CashAndCashEquivalentsAtCarryingValue]
period: CY2017Q4I
unit: USD
value: 6102000000.0
version: 10-K|0000021344-20-000006
form: 10-K
accession: 0000021344-20-000006
fiscal_year: 2019
fiscal_period: FY
```


## Context Record(s) Matching Model Answer

- record_value: `12859000000.0`
- distractor_type: `OTHER_SAME_DOMAIN`
- is_gold_or_equivalent: `False`
#### Matched context record

- display_id: `R88DC069CB7`
- canonical_record_id: `SEC-0000789019-CashAndCashEquivalentsAt-USD-AS-OF-2017-12-31-0001564590-18-001129-a7fc07d3`

```text
entity: MICROSOFT CORPORATION [0000789019]
field: Cash and Cash Equivalents, at Carrying Value [us-gaap:CashAndCashEquivalentsAtCarryingValue]
period: AS_OF_2017-12-31
unit: USD
value: 12859000000.0
version: 10-Q|0001564590-18-001129
form: 10-Q
accession: 0001564590-18-001129
fiscal_year: 2018
fiscal_period: Q2
```


## Relevant Distractor Values/Tags

- display_id: `R88DC069CB7`; canonical_record_id: `SEC-0000789019-CashAndCashEquivalentsAt-USD-AS-OF-2017-12-31-0001564590-18-001129-a7fc07d3`; distractor_type: `OTHER_SAME_DOMAIN`; relationship: `{'different_entity': True, 'different_metric': False, 'different_period': True, 'different_unit': False, 'different_version': True, 'same_entity': False, 'same_metric': True, 'same_period': False, 'same_unit': True, 'same_version': False, 'value_within_5_percent': False}`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 3: FRED_0102_64K

- instance ID: `FRED_0102_64K`
- family ID: `FRED_0102`
- context length: `64K`
- domain: `FRED`
- question type: `ENTITY_UNIT_BINDING`
- answerable/unanswerable: `answerable`

## Question

Using only the FRED records supplied in the context, report the value of FRED series NYUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency for New York on the observation dated 2023-11-01. Report the value for series NYUR exactly.

## Answers

- gold answer: `4.200`
- model answer: `4.0`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R48F77841EF`
- canonical_record_id: `FRED-NYUR-2023-11-01-latest-78b3df30`

```text
entity: New York [NY]
field: Unemployment Rate (Seasonally Adjusted) [NYUR]
period: 2023-11-01
unit: Percent
value: 4.2
version: latest
```


## Evidence-Equivalent Records

#### Equivalent record group EGE5362FBF1D

- display_id: `R48F77841EF`
- canonical_record_id: `FRED-NYUR-2023-11-01-latest-78b3df30`

```text
entity: New York [NY]
field: Unemployment Rate (Seasonally Adjusted) [NYUR]
period: 2023-11-01
unit: Percent
value: 4.2
version: latest
```


## Context Record(s) Matching Model Answer

- record_value: `4.0`
- distractor_type: `NEAR_MATCH_VALUE`
- is_gold_or_equivalent: `False`
#### Matched context record

- display_id: `R9A14075A9D`
- canonical_record_id: `FRED-TXUR-2022-11-01-latest-9af13a4a`

```text
entity: Texas [TX]
field: Unemployment Rate (Seasonally Adjusted) [TXUR]
period: 2022-11-01
unit: Percent
value: 4.0
version: latest
```


## Relevant Distractor Values/Tags

- display_id: `R9A14075A9D`; canonical_record_id: `FRED-TXUR-2022-11-01-latest-9af13a4a`; distractor_type: `NEAR_MATCH_VALUE`; relationship: `{'different_entity': True, 'different_metric': True, 'different_period': True, 'different_unit': False, 'different_version': False, 'same_entity': False, 'same_metric': False, 'same_period': False, 'same_unit': True, 'same_version': True, 'value_within_5_percent': True}`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 4: FRED_0100_32K

- instance ID: `FRED_0100_32K`
- family ID: `FRED_0100`
- context length: `32K`
- domain: `FRED`
- question type: `ENTITY_UNIT_BINDING`
- answerable/unanswerable: `answerable`

## Question

Using only the FRED records supplied in the context, report the value of FRED series ILUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency for Illinois on the observation dated 2018-01-01. Report the value for series ILUR exactly.

## Answers

- gold answer: `4.500`
- model answer: `4.1`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R573D964797`
- canonical_record_id: `FRED-ILUR-2018-01-01-latest-3f840fc6`

```text
entity: Illinois [IL]
field: Unemployment Rate (Seasonally Adjusted) [ILUR]
period: 2018-01-01
unit: Percent
value: 4.5
version: latest
```


## Evidence-Equivalent Records

#### Equivalent record group EGDBBB152446

- display_id: `R573D964797`
- canonical_record_id: `FRED-ILUR-2018-01-01-latest-3f840fc6`

```text
entity: Illinois [IL]
field: Unemployment Rate (Seasonally Adjusted) [ILUR]
period: 2018-01-01
unit: Percent
value: 4.5
version: latest
```


## Context Record(s) Matching Model Answer

- record_value: `4.1`
- distractor_type: `OTHER_SAME_DOMAIN`
- is_gold_or_equivalent: `False`
#### Matched context record

- display_id: `R757A50D1DB`
- canonical_record_id: `FRED-UNRATE-2018-02-01-latest-ea78980c`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2018-02-01
unit: Percent
value: 4.1
version: latest
```


## Relevant Distractor Values/Tags

- display_id: `R757A50D1DB`; canonical_record_id: `FRED-UNRATE-2018-02-01-latest-ea78980c`; distractor_type: `OTHER_SAME_DOMAIN`; relationship: `{'different_entity': True, 'different_metric': True, 'different_period': True, 'different_unit': False, 'different_version': False, 'same_entity': False, 'same_metric': False, 'same_period': False, 'same_unit': True, 'same_version': True, 'value_within_5_percent': False}`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 5: FDA_0019_64K

- instance ID: `FDA_0019_64K`
- family ID: `FDA_0019`
- context length: `64K`
- domain: `FDA`
- question type: `TEMPORAL_VERSION`
- answerable/unanswerable: `answerable`

## Question

Using only the Drugs@FDA records supplied in the context, what is the submission status date of the ORIGINAL submission (submission type ORIG) for FDA application ANDA064139 (sponsor: CHARTWELL RX)? Answer in YYYY-MM-DD form.

## Answers

- gold answer: `1996-01-29`
- model answer: `1997-11-05`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `RD2FF3E8001`
- canonical_record_id: `FDA-ANDA064139-submission-ORIG-1-b309bc43`

```text
entity: CHARTWELL RX application ANDA064139 [ANDA064139]
field: ORIG submission 1 status date [submission.status_date]
period: 1996
value: 1996-01-29
version: ORIG-1
sponsor: CHARTWELL RX
submission_type: ORIG
```


## Evidence-Equivalent Records

#### Equivalent record group EG2488520D55

- display_id: `RD2FF3E8001`
- canonical_record_id: `FDA-ANDA064139-submission-ORIG-1-b309bc43`

```text
entity: CHARTWELL RX application ANDA064139 [ANDA064139]
field: ORIG submission 1 status date [submission.status_date]
period: 1996
value: 1996-01-29
version: ORIG-1
sponsor: CHARTWELL RX
submission_type: ORIG
```


## Context Record(s) Matching Model Answer

- record_value: `1997-11-05`
- distractor_type: `OTHER_SAME_DOMAIN`
- is_gold_or_equivalent: `False`
#### Matched context record

- display_id: `R7A8EBA4289`
- canonical_record_id: `FDA-ANDA062853-submission-SUPPL-9-14edb924`

```text
entity: TEVA application ANDA062853 [ANDA062853]
field: SUPPL submission 9 status date [submission.status_date]
period: 1997
value: 1997-11-05
version: SUPPL-9
sponsor: TEVA
submission_type: SUPPL
```


## Relevant Distractor Values/Tags

- display_id: `R7A8EBA4289`; canonical_record_id: `FDA-ANDA062853-submission-SUPPL-9-14edb924`; distractor_type: `OTHER_SAME_DOMAIN`; relationship: `{'different_entity': True, 'different_metric': False, 'different_period': True, 'different_unit': False, 'different_version': True, 'same_entity': False, 'same_metric': True, 'same_period': False, 'same_unit': True, 'same_version': False, 'value_within_5_percent': False}`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 6: FRED_0103_32K

- instance ID: `FRED_0103_32K`
- family ID: `FRED_0103`
- context length: `32K`
- domain: `FRED`
- question type: `ENTITY_UNIT_BINDING`
- answerable/unanswerable: `answerable`

## Question

Using only the FRED records supplied in the context, report the value of FRED series PAUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency for Pennsylvania on the observation dated 2017-06-01. Report the value for series PAUR exactly.

## Answers

- gold answer: `4.900`
- model answer: `4.8`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `REFE16DC5F4`
- canonical_record_id: `FRED-PAUR-2017-06-01-latest-5ee66b4f`

```text
entity: Pennsylvania [PA]
field: Unemployment Rate (Seasonally Adjusted) [PAUR]
period: 2017-06-01
unit: Percent
value: 4.9
version: latest
```


## Evidence-Equivalent Records

#### Equivalent record group EG95466F0984

- display_id: `REFE16DC5F4`
- canonical_record_id: `FRED-PAUR-2017-06-01-latest-5ee66b4f`

```text
entity: Pennsylvania [PA]
field: Unemployment Rate (Seasonally Adjusted) [PAUR]
period: 2017-06-01
unit: Percent
value: 4.9
version: latest
```


## Context Record(s) Matching Model Answer

- record_value: `4.8`
- distractor_type: `NEAR_MATCH_VALUE`
- is_gold_or_equivalent: `False`
#### Matched context record

- display_id: `RC440287A8E`
- canonical_record_id: `FRED-ILUR-1997-04-01-latest-aeeea7c8`

```text
entity: Illinois [IL]
field: Unemployment Rate (Seasonally Adjusted) [ILUR]
period: 1997-04-01
unit: Percent
value: 4.8
version: latest
```


## Relevant Distractor Values/Tags

- display_id: `RC440287A8E`; canonical_record_id: `FRED-ILUR-1997-04-01-latest-aeeea7c8`; distractor_type: `NEAR_MATCH_VALUE`; relationship: `{'different_entity': True, 'different_metric': True, 'different_period': True, 'different_unit': False, 'different_version': False, 'same_entity': False, 'same_metric': False, 'same_period': False, 'same_unit': True, 'same_version': True, 'value_within_5_percent': True}`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 7: FDA_0099_64K

- instance ID: `FDA_0099_64K`
- family ID: `FDA_0099`
- context length: `64K`
- domain: `FDA`
- question type: `ENTITY_UNIT_BINDING`
- answerable/unanswerable: `answerable`

## Question

Using only the Drugs@FDA records supplied in the context, what is the listed strength of AMLODIPINE BESYLATE in product number 001 under FDA application NDA219531 (dosage form FOR SOLUTION, route ORAL)? Report the strength string exactly as recorded.

## Answers

- gold answer: `EQ 2.5MG BASE/BOT`
- model answer: `EQ 2.5MG BASE/BOT`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Evidence-Equivalent Records

#### Equivalent record group EG004E71A100

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Context Record(s) Matching Model Answer

- record_value: `EQ 2.5MG BASE/BOT`
- distractor_type: `None`
- is_gold_or_equivalent: `True`
#### Matched context record

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Relevant Distractor Values/Tags

- display_id: `R00A7AB31A4`; canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`; distractor_type: `None`; relationship: `matched_context_record_from_grader`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 8: FDA_0099_4K

- instance ID: `FDA_0099_4K`
- family ID: `FDA_0099`
- context length: `4K`
- domain: `FDA`
- question type: `ENTITY_UNIT_BINDING`
- answerable/unanswerable: `answerable`

## Question

Using only the Drugs@FDA records supplied in the context, what is the listed strength of AMLODIPINE BESYLATE in product number 001 under FDA application NDA219531 (dosage form FOR SOLUTION, route ORAL)? Report the strength string exactly as recorded.

## Answers

- gold answer: `EQ 2.5MG BASE/BOT`
- model answer: `EQ 2.5MG BASE/BOT`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Evidence-Equivalent Records

#### Equivalent record group EG004E71A100

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Context Record(s) Matching Model Answer

- record_value: `EQ 2.5MG BASE/BOT`
- distractor_type: `None`
- is_gold_or_equivalent: `True`
#### Matched context record

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Relevant Distractor Values/Tags

- display_id: `R00A7AB31A4`; canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`; distractor_type: `None`; relationship: `matched_context_record_from_grader`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 9: FRED_0038_4K

- instance ID: `FRED_0038_4K`
- family ID: `FRED_0038`
- context length: `4K`
- domain: `FRED`
- question type: `DIRECT_RETRIEVAL`
- answerable/unanswerable: `answerable`

## Question

Using only the FRED records supplied in the context, what value does the most recent vintage report for FRED series UNRATE ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency, for the observation dated 2022-09-01 (the month beginning 2022-09-01)? Report the currently published figure exactly.

## Answers

- gold answer: `3.500`
- model answer: `3.9`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R78664B2198`
- canonical_record_id: `FRED-UNRATE-2022-09-01-latest-92b49c71`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2022-09-01
unit: Percent
value: 3.5
version: latest
```


## Evidence-Equivalent Records

#### Equivalent record group EGF81D75AC53

- display_id: `RC1AEC18D99`
- canonical_record_id: `FRED-UNRATE-2022-09-01-2023-09-28-e1d5ab51`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2022-09-01
unit: Percent
value: 3.5
version: vintage:2023-09-28
```

#### Equivalent record group EGF81D75AC53

- display_id: `R017A88D272`
- canonical_record_id: `FRED-UNRATE-2022-09-01-2025-03-27-2c96f605`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2022-09-01
unit: Percent
value: 3.5
version: vintage:2025-03-27
```

#### Equivalent record group EGF81D75AC53

- display_id: `R78664B2198`
- canonical_record_id: `FRED-UNRATE-2022-09-01-latest-92b49c71`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2022-09-01
unit: Percent
value: 3.5
version: latest
```


## Context Record(s) Matching Model Answer

- record_value: `3.9`
- distractor_type: `OTHER_SAME_DOMAIN`
- is_gold_or_equivalent: `False`
#### Matched context record

- display_id: `R6FD6E0F474`
- canonical_record_id: `FRED-FLUR-1999-07-01-latest-521fe055`

```text
entity: Florida [FL]
field: Unemployment Rate (Seasonally Adjusted) [FLUR]
period: 1999-07-01
unit: Percent
value: 3.9
version: latest
```


## Relevant Distractor Values/Tags

- display_id: `R6FD6E0F474`; canonical_record_id: `FRED-FLUR-1999-07-01-latest-521fe055`; distractor_type: `OTHER_SAME_DOMAIN`; relationship: `{'different_entity': True, 'different_metric': True, 'different_period': True, 'different_unit': False, 'different_version': False, 'same_entity': False, 'same_metric': False, 'same_period': False, 'same_unit': True, 'same_version': True, 'value_within_5_percent': False}`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 10: FRED_0093_64K

- instance ID: `FRED_0093_64K`
- family ID: `FRED_0093`
- context length: `64K`
- domain: `FRED`
- question type: `ENTITY_UNIT_BINDING`
- answerable/unanswerable: `answerable`

## Question

Using only the FRED records supplied in the context, report the value of FRED series FLUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency for Florida on the observation dated 2018-08-01. Report the value for series FLUR exactly.

## Answers

- gold answer: `3.500`
- model answer: `3.6`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R4690A9C269`
- canonical_record_id: `FRED-FLUR-2018-08-01-latest-7b21d564`

```text
entity: Florida [FL]
field: Unemployment Rate (Seasonally Adjusted) [FLUR]
period: 2018-08-01
unit: Percent
value: 3.5
version: latest
```


## Evidence-Equivalent Records

#### Equivalent record group EG4BA0BE7114

- display_id: `R4690A9C269`
- canonical_record_id: `FRED-FLUR-2018-08-01-latest-7b21d564`

```text
entity: Florida [FL]
field: Unemployment Rate (Seasonally Adjusted) [FLUR]
period: 2018-08-01
unit: Percent
value: 3.5
version: latest
```


## Context Record(s) Matching Model Answer

- record_value: `3.6`
- distractor_type: `NEAR_MATCH_VALUE`
- is_gold_or_equivalent: `False`
#### Matched context record

- display_id: `RAB40C4E533`
- canonical_record_id: `FRED-UNRATE-2019-05-01-2025-03-27-d4fbaae2`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2019-05-01
unit: Percent
value: 3.6
version: vintage:2025-03-27
```


## Relevant Distractor Values/Tags

- display_id: `RAB40C4E533`; canonical_record_id: `FRED-UNRATE-2019-05-01-2025-03-27-d4fbaae2`; distractor_type: `NEAR_MATCH_VALUE`; relationship: `{'different_entity': True, 'different_metric': True, 'different_period': True, 'different_unit': False, 'different_version': True, 'same_entity': False, 'same_metric': False, 'same_period': False, 'same_unit': True, 'same_version': False, 'value_within_5_percent': True}`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 11: FRED_0100_82K

- instance ID: `FRED_0100_82K`
- family ID: `FRED_0100`
- context length: `82K`
- domain: `FRED`
- question type: `ENTITY_UNIT_BINDING`
- answerable/unanswerable: `answerable`

## Question

Using only the FRED records supplied in the context, report the value of FRED series ILUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency for Illinois on the observation dated 2018-01-01. Report the value for series ILUR exactly.

## Answers

- gold answer: `4.500`
- model answer: `4.1`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R573D964797`
- canonical_record_id: `FRED-ILUR-2018-01-01-latest-3f840fc6`

```text
entity: Illinois [IL]
field: Unemployment Rate (Seasonally Adjusted) [ILUR]
period: 2018-01-01
unit: Percent
value: 4.5
version: latest
```


## Evidence-Equivalent Records

#### Equivalent record group EGDBBB152446

- display_id: `R573D964797`
- canonical_record_id: `FRED-ILUR-2018-01-01-latest-3f840fc6`

```text
entity: Illinois [IL]
field: Unemployment Rate (Seasonally Adjusted) [ILUR]
period: 2018-01-01
unit: Percent
value: 4.5
version: latest
```


## Context Record(s) Matching Model Answer

- record_value: `4.1`
- distractor_type: `OTHER_SAME_DOMAIN`
- is_gold_or_equivalent: `False`
#### Matched context record

- display_id: `R757A50D1DB`
- canonical_record_id: `FRED-UNRATE-2018-02-01-latest-ea78980c`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2018-02-01
unit: Percent
value: 4.1
version: latest
```


## Relevant Distractor Values/Tags

- display_id: `R757A50D1DB`; canonical_record_id: `FRED-UNRATE-2018-02-01-latest-ea78980c`; distractor_type: `OTHER_SAME_DOMAIN`; relationship: `{'different_entity': True, 'different_metric': True, 'different_period': True, 'different_unit': False, 'different_version': False, 'same_entity': False, 'same_metric': False, 'same_period': False, 'same_unit': True, 'same_version': True, 'value_within_5_percent': False}`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 12: FDA_0020_82K

- instance ID: `FDA_0020_82K`
- family ID: `FDA_0020`
- context length: `82K`
- domain: `FDA`
- question type: `TEMPORAL_VERSION`
- answerable/unanswerable: `answerable`

## Question

Using only the Drugs@FDA records supplied in the context, what is the submission status date of the ORIGINAL submission (submission type ORIG) for FDA application ANDA091431 (sponsor: HERITAGE)? Answer in YYYY-MM-DD form.

## Answers

- gold answer: `2013-12-30`
- model answer: `2024-05-01`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R397043970E`
- canonical_record_id: `FDA-ANDA091431-submission-ORIG-1-7b0a53ff`

```text
entity: HERITAGE application ANDA091431 [ANDA091431]
field: ORIG submission 1 status date [submission.status_date]
period: 2013
value: 2013-12-30
version: ORIG-1
sponsor: HERITAGE
submission_type: ORIG
```


## Evidence-Equivalent Records

#### Equivalent record group EG072CD06224

- display_id: `R397043970E`
- canonical_record_id: `FDA-ANDA091431-submission-ORIG-1-7b0a53ff`

```text
entity: HERITAGE application ANDA091431 [ANDA091431]
field: ORIG submission 1 status date [submission.status_date]
period: 2013
value: 2013-12-30
version: ORIG-1
sponsor: HERITAGE
submission_type: ORIG
```


## Context Record(s) Matching Model Answer

- record_value: `2024-05-01`
- distractor_type: `OTHER_SAME_DOMAIN`
- is_gold_or_equivalent: `False`
#### Matched context record

- display_id: `R59DF04CB19`
- canonical_record_id: `FDA-ANDA205187-submission-SUPPL-4-aa50d1c3`

```text
entity: MICRO LABS LTD INDIA application ANDA205187 [ANDA205187]
field: SUPPL submission 4 status date [submission.status_date]
period: 2024
value: 2024-05-01
version: SUPPL-4
sponsor: MICRO LABS LTD INDIA
submission_type: SUPPL
```


## Relevant Distractor Values/Tags

- display_id: `R59DF04CB19`; canonical_record_id: `FDA-ANDA205187-submission-SUPPL-4-aa50d1c3`; distractor_type: `OTHER_SAME_DOMAIN`; relationship: `{'different_entity': True, 'different_metric': False, 'different_period': True, 'different_unit': False, 'different_version': True, 'same_entity': False, 'same_metric': True, 'same_period': False, 'same_unit': True, 'same_version': False, 'value_within_5_percent': False}`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 13: FRED_0100_64K

- instance ID: `FRED_0100_64K`
- family ID: `FRED_0100`
- context length: `64K`
- domain: `FRED`
- question type: `ENTITY_UNIT_BINDING`
- answerable/unanswerable: `answerable`

## Question

Using only the FRED records supplied in the context, report the value of FRED series ILUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency for Illinois on the observation dated 2018-01-01. Report the value for series ILUR exactly.

## Answers

- gold answer: `4.500`
- model answer: `4.0`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R573D964797`
- canonical_record_id: `FRED-ILUR-2018-01-01-latest-3f840fc6`

```text
entity: Illinois [IL]
field: Unemployment Rate (Seasonally Adjusted) [ILUR]
period: 2018-01-01
unit: Percent
value: 4.5
version: latest
```


## Evidence-Equivalent Records

#### Equivalent record group EGDBBB152446

- display_id: `R573D964797`
- canonical_record_id: `FRED-ILUR-2018-01-01-latest-3f840fc6`

```text
entity: Illinois [IL]
field: Unemployment Rate (Seasonally Adjusted) [ILUR]
period: 2018-01-01
unit: Percent
value: 4.5
version: latest
```


## Context Record(s) Matching Model Answer

- record_value: `4.0`
- distractor_type: `OTHER_SAME_DOMAIN`
- is_gold_or_equivalent: `False`
#### Matched context record

- display_id: `R5D7C443BEB`
- canonical_record_id: `FRED-UNRATE-2022-01-01-latest-0355b630`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2022-01-01
unit: Percent
value: 4.0
version: latest
```


## Relevant Distractor Values/Tags

- display_id: `R5D7C443BEB`; canonical_record_id: `FRED-UNRATE-2022-01-01-latest-0355b630`; distractor_type: `OTHER_SAME_DOMAIN`; relationship: `{'different_entity': True, 'different_metric': True, 'different_period': True, 'different_unit': False, 'different_version': False, 'same_entity': False, 'same_metric': False, 'same_period': False, 'same_unit': True, 'same_version': True, 'value_within_5_percent': False}`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 14: FDA_0099_16K

- instance ID: `FDA_0099_16K`
- family ID: `FDA_0099`
- context length: `16K`
- domain: `FDA`
- question type: `ENTITY_UNIT_BINDING`
- answerable/unanswerable: `answerable`

## Question

Using only the Drugs@FDA records supplied in the context, what is the listed strength of AMLODIPINE BESYLATE in product number 001 under FDA application NDA219531 (dosage form FOR SOLUTION, route ORAL)? Report the strength string exactly as recorded.

## Answers

- gold answer: `EQ 2.5MG BASE/BOT`
- model answer: `EQ 2.5MG BASE/BOT`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Evidence-Equivalent Records

#### Equivalent record group EG004E71A100

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Context Record(s) Matching Model Answer

- record_value: `EQ 2.5MG BASE/BOT`
- distractor_type: `None`
- is_gold_or_equivalent: `True`
#### Matched context record

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Relevant Distractor Values/Tags

- display_id: `R00A7AB31A4`; canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`; distractor_type: `None`; relationship: `matched_context_record_from_grader`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 15: FRED_0104_82K

- instance ID: `FRED_0104_82K`
- family ID: `FRED_0104`
- context length: `82K`
- domain: `FRED`
- question type: `ENTITY_UNIT_BINDING`
- answerable/unanswerable: `answerable`

## Question

Using only the FRED records supplied in the context, report the value of FRED series UNRATE ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency for United States on the observation dated 2021-07-01. Report the value for series UNRATE exactly.

## Answers

- gold answer: `5.400`
- model answer: `6.2`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R5C399E1A89`
- canonical_record_id: `FRED-UNRATE-2021-07-01-latest-1ed0c10f`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2021-07-01
unit: Percent
value: 5.4
version: latest
```


## Evidence-Equivalent Records

#### Equivalent record group EG1C098A57D5

- display_id: `R5AD8F0C2E4`
- canonical_record_id: `FRED-UNRATE-2021-07-01-2022-06-29-5b040b61`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2021-07-01
unit: Percent
value: 5.4
version: vintage:2022-06-29
```

#### Equivalent record group EG1C098A57D5

- display_id: `RE05C8D8560`
- canonical_record_id: `FRED-UNRATE-2021-07-01-2023-09-28-9d4ee3a8`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2021-07-01
unit: Percent
value: 5.4
version: vintage:2023-09-28
```

#### Equivalent record group EG1C098A57D5

- display_id: `RD12AE93D36`
- canonical_record_id: `FRED-UNRATE-2021-07-01-2025-03-27-f5b5dcb9`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2021-07-01
unit: Percent
value: 5.4
version: vintage:2025-03-27
```

#### Equivalent record group EG1C098A57D5

- display_id: `R5C399E1A89`
- canonical_record_id: `FRED-UNRATE-2021-07-01-latest-1ed0c10f`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2021-07-01
unit: Percent
value: 5.4
version: latest
```


## Context Record(s) Matching Model Answer

- record_value: `6.2`
- distractor_type: `OTHER_SAME_DOMAIN`
- is_gold_or_equivalent: `False`
#### Matched context record

- display_id: `R5BA38F65DB`
- canonical_record_id: `FRED-ILUR-2004-06-01-latest-150eaecd`

```text
entity: Illinois [IL]
field: Unemployment Rate (Seasonally Adjusted) [ILUR]
period: 2004-06-01
unit: Percent
value: 6.2
version: latest
```


## Relevant Distractor Values/Tags

- display_id: `R5BA38F65DB`; canonical_record_id: `FRED-ILUR-2004-06-01-latest-150eaecd`; distractor_type: `OTHER_SAME_DOMAIN`; relationship: `{'different_entity': True, 'different_metric': True, 'different_period': True, 'different_unit': False, 'different_version': False, 'same_entity': False, 'same_metric': False, 'same_period': False, 'same_unit': True, 'same_version': True, 'value_within_5_percent': False}`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 16: FRED_0038_8K

- instance ID: `FRED_0038_8K`
- family ID: `FRED_0038`
- context length: `8K`
- domain: `FRED`
- question type: `DIRECT_RETRIEVAL`
- answerable/unanswerable: `answerable`

## Question

Using only the FRED records supplied in the context, what value does the most recent vintage report for FRED series UNRATE ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency, for the observation dated 2022-09-01 (the month beginning 2022-09-01)? Report the currently published figure exactly.

## Answers

- gold answer: `3.500`
- model answer: `3.9`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R78664B2198`
- canonical_record_id: `FRED-UNRATE-2022-09-01-latest-92b49c71`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2022-09-01
unit: Percent
value: 3.5
version: latest
```


## Evidence-Equivalent Records

#### Equivalent record group EGF81D75AC53

- display_id: `RC1AEC18D99`
- canonical_record_id: `FRED-UNRATE-2022-09-01-2023-09-28-e1d5ab51`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2022-09-01
unit: Percent
value: 3.5
version: vintage:2023-09-28
```

#### Equivalent record group EGF81D75AC53

- display_id: `R017A88D272`
- canonical_record_id: `FRED-UNRATE-2022-09-01-2025-03-27-2c96f605`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2022-09-01
unit: Percent
value: 3.5
version: vintage:2025-03-27
```

#### Equivalent record group EGF81D75AC53

- display_id: `R78664B2198`
- canonical_record_id: `FRED-UNRATE-2022-09-01-latest-92b49c71`

```text
entity: United States [US]
field: Unemployment Rate (Seasonally Adjusted) [UNRATE]
period: 2022-09-01
unit: Percent
value: 3.5
version: latest
```


## Context Record(s) Matching Model Answer

- record_value: `3.9`
- distractor_type: `OTHER_SAME_DOMAIN`
- is_gold_or_equivalent: `False`
#### Matched context record

- display_id: `R6FD6E0F474`
- canonical_record_id: `FRED-FLUR-1999-07-01-latest-521fe055`

```text
entity: Florida [FL]
field: Unemployment Rate (Seasonally Adjusted) [FLUR]
period: 1999-07-01
unit: Percent
value: 3.9
version: latest
```


## Relevant Distractor Values/Tags

- display_id: `R6FD6E0F474`; canonical_record_id: `FRED-FLUR-1999-07-01-latest-521fe055`; distractor_type: `OTHER_SAME_DOMAIN`; relationship: `{'different_entity': True, 'different_metric': True, 'different_period': True, 'different_unit': False, 'different_version': False, 'same_entity': False, 'same_metric': False, 'same_period': False, 'same_unit': True, 'same_version': True, 'value_within_5_percent': False}`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 17: FDA_0105_4K

- instance ID: `FDA_0105_4K`
- family ID: `FDA_0105`
- context length: `4K`
- domain: `FDA`
- question type: `ENTITY_UNIT_BINDING`
- answerable/unanswerable: `answerable`

## Question

Using only the Drugs@FDA records supplied in the context, what is the listed strength of ATORVASTATIN CALCIUM in product number 002 under FDA application NDA200153 (dosage form TABLET, route ORAL)? Report the strength string exactly as recorded.

## Answers

- gold answer: `EQ 20MG BASE`
- model answer: `EQ 20MG BASE`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `RF5DB3E95FD`
- canonical_record_id: `FDA-NDA200153-002-strength-ATORVASTATIN-CALCIUM-0-da88d144`

```text
entity: LIPTRUZET (NDA200153, product 002) [NDA200153/002]
field: Strength of ATORVASTATIN CALCIUM [product.active_ingredient_strength]
unit: MG
value: EQ 20MG BASE
dosage_form: TABLET
route: ORAL
sponsor: ORGANON
```


## Evidence-Equivalent Records

#### Equivalent record group EGA8CA1BED5E

- display_id: `RF5DB3E95FD`
- canonical_record_id: `FDA-NDA200153-002-strength-ATORVASTATIN-CALCIUM-0-da88d144`

```text
entity: LIPTRUZET (NDA200153, product 002) [NDA200153/002]
field: Strength of ATORVASTATIN CALCIUM [product.active_ingredient_strength]
unit: MG
value: EQ 20MG BASE
dosage_form: TABLET
route: ORAL
sponsor: ORGANON
```


## Context Record(s) Matching Model Answer

- record_value: `EQ 20MG BASE`
- distractor_type: `None`
- is_gold_or_equivalent: `True`
#### Matched context record

- display_id: `RF5DB3E95FD`
- canonical_record_id: `FDA-NDA200153-002-strength-ATORVASTATIN-CALCIUM-0-da88d144`

```text
entity: LIPTRUZET (NDA200153, product 002) [NDA200153/002]
field: Strength of ATORVASTATIN CALCIUM [product.active_ingredient_strength]
unit: MG
value: EQ 20MG BASE
dosage_form: TABLET
route: ORAL
sponsor: ORGANON
```


## Relevant Distractor Values/Tags

- display_id: `RF5DB3E95FD`; canonical_record_id: `FDA-NDA200153-002-strength-ATORVASTATIN-CALCIUM-0-da88d144`; distractor_type: `None`; relationship: `matched_context_record_from_grader`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 18: FDA_0099_82K

- instance ID: `FDA_0099_82K`
- family ID: `FDA_0099`
- context length: `82K`
- domain: `FDA`
- question type: `ENTITY_UNIT_BINDING`
- answerable/unanswerable: `answerable`

## Question

Using only the Drugs@FDA records supplied in the context, what is the listed strength of AMLODIPINE BESYLATE in product number 001 under FDA application NDA219531 (dosage form FOR SOLUTION, route ORAL)? Report the strength string exactly as recorded.

## Answers

- gold answer: `EQ 2.5MG BASE/BOT`
- model answer: `EQ 2.5MG BASE/BOT`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Evidence-Equivalent Records

#### Equivalent record group EG004E71A100

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Context Record(s) Matching Model Answer

- record_value: `EQ 2.5MG BASE/BOT`
- distractor_type: `None`
- is_gold_or_equivalent: `True`
#### Matched context record

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Relevant Distractor Values/Tags

- display_id: `R00A7AB31A4`; canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`; distractor_type: `None`; relationship: `matched_context_record_from_grader`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---

## Case 19: FDA_0099_8K

- instance ID: `FDA_0099_8K`
- family ID: `FDA_0099`
- context length: `8K`
- domain: `FDA`
- question type: `ENTITY_UNIT_BINDING`
- answerable/unanswerable: `answerable`

## Question

Using only the Drugs@FDA records supplied in the context, what is the listed strength of AMLODIPINE BESYLATE in product number 001 under FDA application NDA219531 (dosage form FOR SOLUTION, route ORAL)? Report the strength string exactly as recorded.

## Answers

- gold answer: `EQ 2.5MG BASE/BOT`
- model answer: `EQ 2.5MG BASE/BOT`

## Why Ambiguous

answer value appears in context but deterministic distractor type is unavailable

## Target Evidence

#### Target evidence record

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Evidence-Equivalent Records

#### Equivalent record group EG004E71A100

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Context Record(s) Matching Model Answer

- record_value: `EQ 2.5MG BASE/BOT`
- distractor_type: `None`
- is_gold_or_equivalent: `True`
#### Matched context record

- display_id: `R00A7AB31A4`
- canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`

```text
entity: SDAMLO (NDA219531, product 001) [NDA219531/001]
field: Strength of AMLODIPINE BESYLATE [product.active_ingredient_strength]
unit: MG
value: EQ 2.5MG BASE/BOT
dosage_form: FOR SOLUTION
route: ORAL
sponsor: BRILLIAN PHARMA
```


## Relevant Distractor Values/Tags

- display_id: `R00A7AB31A4`; canonical_record_id: `FDA-NDA219531-001-strength-AMLODIPINE-BESYLATE-0-f50582c0`; distractor_type: `None`; relationship: `matched_context_record_from_grader`

## Manual Adjudication

final_answer_correct:
final_hallucination:
final_error_type:
manual_justification:


---
