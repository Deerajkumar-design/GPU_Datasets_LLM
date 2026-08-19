# Experiment C Deterministic Grading Audit

- sample size: `40`
- deterministically resolved: `40`
- semantic review required: `0`
- hallucination=true: `9`
- error types: `{'FAILED_TO_ABSTAIN': 4, 'CORRECT': 27, 'WRONG_PERIOD': 1, 'UNSUPPORTED_VALUE': 5, 'CALCULATION_ERROR': 1, 'UNNECESSARY_ABSTENTION': 2}`

No evidence-selection accuracy is graded for Experiment C because the model-facing output contract is answer-only.

## 1. CT_0024_4K

- context length: `4K`
- domain: `CLINICAL_TRIALS`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the date on which results were first posted for trial NCT06097390 ("A Research Study Looking at New Protein-based Tablets in Healthy Men - Oral Formulation III")?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `2025-07-17`
- answer correct: `False`
- abstention correct: `False`
- hallucination: `True`
- error type: `FAILED_TO_ABSTAIN`
- matched context/distractor value: `2025-07-17`
- matched distractor type: `WRONG_FIELD`
- rule: `unanswerable_instance_factual_answer`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R5AA8DDDD54": {"canonical_record_id": "CT-NCT06097390-study-last-update-posted-709747d7", "field": "Last update posted date [study.last_update_posted_date]", "period": "2025", "unit": null, "value": "2025-07-17", "distractor_type": "WRONG_FIELD"}}`

## 2. CT_0024_64K

- context length: `64K`
- domain: `CLINICAL_TRIALS`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the date on which results were first posted for trial NCT06097390 ("A Research Study Looking at New Protein-based Tablets in Healthy Men - Oral Formulation III")?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `2025-07-17`
- answer correct: `False`
- abstention correct: `False`
- hallucination: `True`
- error type: `FAILED_TO_ABSTAIN`
- matched context/distractor value: `2025-07-17`
- matched distractor type: `WRONG_FIELD`
- rule: `unanswerable_instance_factual_answer`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R5AA8DDDD54": {"canonical_record_id": "CT-NCT06097390-study-last-update-posted-709747d7", "field": "Last update posted date [study.last_update_posted_date]", "period": "2025", "unit": null, "value": "2025-07-17", "distractor_type": "WRONG_FIELD"}}`

## 3. CT_0021_8K

- context length: `8K`
- domain: `CLINICAL_TRIALS`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the date on which results were first posted for trial NCT02339493 ("Electronic Alerts for Stroke Prevention in Patients With Atrial Fibrillation or Atrial Flutter")?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `2015-01-15`
- answer correct: `False`
- abstention correct: `False`
- hallucination: `True`
- error type: `FAILED_TO_ABSTAIN`
- matched context/distractor value: `2015-01-15`
- matched distractor type: `WRONG_FIELD`
- rule: `unanswerable_instance_factual_answer`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"RA9D366EFB3": {"canonical_record_id": "CT-NCT02339493-study-first-posted-date-c38697fd", "field": "Study first posted date [study.first_posted_date]", "period": "2015", "unit": null, "value": "2015-01-15", "distractor_type": "WRONG_FIELD"}}`

## 4. CT_0021_64K

- context length: `64K`
- domain: `CLINICAL_TRIALS`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the date on which results were first posted for trial NCT02339493 ("Electronic Alerts for Stroke Prevention in Patients With Atrial Fibrillation or Atrial Flutter")?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `2018-10-31`
- answer correct: `False`
- abstention correct: `False`
- hallucination: `True`
- error type: `FAILED_TO_ABSTAIN`
- matched context/distractor value: `2018-10-31`
- matched distractor type: `WRONG_FIELD`
- rule: `unanswerable_instance_factual_answer`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R656998F596": {"canonical_record_id": "CT-NCT02339493-study-last-update-posted-df46f3ec", "field": "Last update posted date [study.last_update_posted_date]", "period": "2018", "unit": null, "value": "2018-10-31", "distractor_type": "WRONG_FIELD"}}`

## 5. CT_0007_4K

- context length: `4K`
- domain: `CLINICAL_TRIALS`
- question type: `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the arm-group TYPE of the arm labelled "Placebo" in trial NCT01728636 ("The Use of Tranexamic Acid to Reduce Perioperative Blood Loss During High Risk Spine Fusion Surgery")? Answer with the ClinicalTrials.gov arm type value (for example EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, SHAM_COMPARATOR, NO_INTERVENTION or OTHER).
- gold answer: `PLACEBO_COMPARATOR`
- model answer: `PLACEBO_COMPARATOR`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `PLACEBO_COMPARATOR`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R3A6D2D6B08": {"canonical_record_id": "CT-NCT01728636-arm-type-Placebo-1-34edfc87", "field": "Arm group type: Placebo [arm.type]", "period": null, "unit": null, "value": "PLACEBO_COMPARATOR", "distractor_type": null}}`

## 6. CT_0007_64K

- context length: `64K`
- domain: `CLINICAL_TRIALS`
- question type: `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the arm-group TYPE of the arm labelled "Placebo" in trial NCT01728636 ("The Use of Tranexamic Acid to Reduce Perioperative Blood Loss During High Risk Spine Fusion Surgery")? Answer with the ClinicalTrials.gov arm type value (for example EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, SHAM_COMPARATOR, NO_INTERVENTION or OTHER).
- gold answer: `PLACEBO_COMPARATOR`
- model answer: `PLACEBO_COMPARATOR`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `PLACEBO_COMPARATOR`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R3A6D2D6B08": {"canonical_record_id": "CT-NCT01728636-arm-type-Placebo-1-34edfc87", "field": "Arm group type: Placebo [arm.type]", "period": null, "unit": null, "value": "PLACEBO_COMPARATOR", "distractor_type": null}, "R9120D06548": {"canonical_record_id": "CT-NCT01617655-arm-type-Placebo-Q2W-0-40a1b906", "field": "Arm group type: Placebo Q2W [arm.type]", "period": null, "unit": null, "value": "PLACEBO_COMPARATOR", "distractor_type": "WRONG_ENTITY"}}`

## 7. SEC_0006_4K

- context length: `4K`
- domain: `SEC`
- question type: `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did PFIZER INC (CIK 0000078003) report for us-gaap:NetCashProvidedByUsedInInvestingActivities for the annual XBRL frame CY2010, in USD? Report the exact value for that filer.
- gold answer: `-492000000.0`
- model answer: `-492000000.0`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `-492000000.0`
- matched distractor type: `NEAR_MATCH_VALUE`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R1747BDE59E": {"canonical_record_id": "SEC-0000078003-NetCashProvidedByUsedInI-USD-CY2010-0000078003-13-000006-0cfaf545", "field": "Net Cash Provided by (Used in) Investing Activities [us-gaap:NetCashProvidedByUsedInInvestingActivities]", "period": "CY2010", "unit": "USD", "value": "-492000000.0", "distractor_type": null}, "RA409AC97BA": {"canonical_record_id": "SEC-0000789019-NetIncomeLoss-USD-CY2012Q2-0001193125-13-455144-2f004069", "field": "Net Income (Loss) Attributable to Parent [us-gaap:NetIncomeLoss]", "period": "CY2012Q2", "unit": "USD", "value": "-492000000.0", "distractor_type": "NEAR_MATCH_VALUE"}}`

## 8. SEC_0006_64K

- context length: `64K`
- domain: `SEC`
- question type: `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did PFIZER INC (CIK 0000078003) report for us-gaap:NetCashProvidedByUsedInInvestingActivities for the annual XBRL frame CY2010, in USD? Report the exact value for that filer.
- gold answer: `-492000000.0`
- model answer: `-492000000.0`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `-492000000.0`
- matched distractor type: `WRONG_PERIOD`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R1747BDE59E": {"canonical_record_id": "SEC-0000078003-NetCashProvidedByUsedInI-USD-CY2010-0000078003-13-000006-0cfaf545", "field": "Net Cash Provided by (Used in) Investing Activities [us-gaap:NetCashProvidedByUsedInInvestingActivities]", "period": "CY2010", "unit": "USD", "value": "-492000000.0", "distractor_type": null}, "R7FF8B94758": {"canonical_record_id": "SEC-0000078003-NetCashProvidedByUsedInI-USD-2010-01-01-2010-12-31-0001193125-11-048877-6ee557f4", "field": "Net Cash Provided by (Used in) Investing Activities [us-gaap:NetCashProvidedByUsedInInvestingActivities]", "period": "2010-01-01..2010-12-31", "unit": "USD", "value": "-492000000.0", "distractor_type": "WRONG_PERIOD"}}`

## 9. FDA_0003_4K

- context length: `4K`
- domain: `FDA`
- question type: `DIRECT_RETRIEVAL`
- answerable: `True`
- question: Using only the Drugs@FDA records supplied in the context, what DOSAGE FORM is listed for product number 006 under FDA application ANDA075999 (brand name "LISINOPRIL", active ingredient LISINOPRIL)? Answer with the dosage form exactly as recorded.
- gold answer: `TABLET`
- model answer: `TABLET`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `TABLET`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R89F59D6895": {"canonical_record_id": "FDA-ANDA075999-006-product-dosage-form-a7cba6df", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET", "distractor_type": null}, "REE6775A1EA": {"canonical_record_id": "FDA-ANDA205199-008-product-dosage-form-18edbe0e", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET", "distractor_type": "WRONG_ENTITY"}}`

## 10. FDA_0003_64K

- context length: `64K`
- domain: `FDA`
- question type: `DIRECT_RETRIEVAL`
- answerable: `True`
- question: Using only the Drugs@FDA records supplied in the context, what DOSAGE FORM is listed for product number 006 under FDA application ANDA075999 (brand name "LISINOPRIL", active ingredient LISINOPRIL)? Answer with the dosage form exactly as recorded.
- gold answer: `TABLET`
- model answer: `TABLET`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `TABLET`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R842273FF7D": {"canonical_record_id": "FDA-ANDA075961-002-product-dosage-form-3a32f494", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET", "distractor_type": "WRONG_ENTITY"}, "R89F59D6895": {"canonical_record_id": "FDA-ANDA075999-006-product-dosage-form-a7cba6df", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET", "distractor_type": null}}`

## 11. FRED_0007_4K

- context length: `4K`
- domain: `FRED`
- question type: `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the FRED records supplied in the context, report the value of FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency for United States on the observation dated 2022-09-01. Report the value for series DGS10 exactly.
- gold answer: `3.26`
- model answer: `3.26`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `3.26`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R9388092F79": {"canonical_record_id": "FRED-DGS10-2022-09-01-latest-ee1793fc", "field": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity (Not Seasonally Adjusted) [DGS10]", "period": "2022-09-01", "unit": "Percent", "value": "3.26", "distractor_type": null}}`

## 12. FRED_0007_64K

- context length: `64K`
- domain: `FRED`
- question type: `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the FRED records supplied in the context, report the value of FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency for United States on the observation dated 2022-09-01. Report the value for series DGS10 exactly.
- gold answer: `3.26`
- model answer: `3.77`
- answer correct: `False`
- abstention correct: `True`
- hallucination: `False`
- error type: `WRONG_PERIOD`
- matched context/distractor value: `3.77`
- matched distractor type: `WRONG_PERIOD`
- rule: `answer_matches_context_distractor_value`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R8BBC5C13E3": {"canonical_record_id": "FRED-DGS10-2022-11-17-latest-93d77a5c", "field": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity (Not Seasonally Adjusted) [DGS10]", "period": "2022-11-17", "unit": "Percent", "value": "3.77", "distractor_type": "WRONG_PERIOD"}, "R9388092F79": {"canonical_record_id": "FRED-DGS10-2022-09-01-latest-ee1793fc", "field": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity (Not Seasonally Adjusted) [DGS10]", "period": "2022-09-01", "unit": "Percent", "value": "3.26", "distractor_type": null}}`

## 13. SEC_0009_32K

- context length: `32K`
- domain: `SEC`
- question type: `RETRIEVAL_CALCULATION`
- answerable: `True`
- question: Using only the SEC XBRL company-facts records supplied in the context, calculate WALMART INC.'s (CIK 0000104169) operating margin for the annual XBRL frame CY2011. Divide us-gaap:OperatingIncomeLoss by Revenues for that same company and frame, both in USD, multiply by 100, and round to two decimal places.
- gold answer: `5.93`
- model answer: `0.07`
- answer correct: `False`
- abstention correct: `True`
- hallucination: `True`
- error type: `UNSUPPORTED_VALUE`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R8C100B55A6": {"canonical_record_id": "SEC-0000104169-Revenues-USD-CY2011-0000104169-14-000019-50faff09", "field": "Revenues [us-gaap:Revenues]", "period": "CY2011", "unit": "USD", "value": "446509000000.0", "distractor_type": null}, "RB1AFF6F2F5": {"canonical_record_id": "SEC-0000104169-OperatingIncomeLoss-USD-CY2011-0000104169-14-000019-ab2642b5", "field": "Operating Income (Loss) [us-gaap:OperatingIncomeLoss]", "period": "CY2011", "unit": "USD", "value": "26491000000.0", "distractor_type": null}}`

## 14. SEC_0009_64K

- context length: `64K`
- domain: `SEC`
- question type: `RETRIEVAL_CALCULATION`
- answerable: `True`
- question: Using only the SEC XBRL company-facts records supplied in the context, calculate WALMART INC.'s (CIK 0000104169) operating margin for the annual XBRL frame CY2011. Divide us-gaap:OperatingIncomeLoss by Revenues for that same company and frame, both in USD, multiply by 100, and round to two decimal places.
- gold answer: `5.93`
- model answer: `0.00`
- answer correct: `False`
- abstention correct: `True`
- hallucination: `True`
- error type: `UNSUPPORTED_VALUE`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R8C100B55A6": {"canonical_record_id": "SEC-0000104169-Revenues-USD-CY2011-0000104169-14-000019-50faff09", "field": "Revenues [us-gaap:Revenues]", "period": "CY2011", "unit": "USD", "value": "446509000000.0", "distractor_type": null}, "RB1AFF6F2F5": {"canonical_record_id": "SEC-0000104169-OperatingIncomeLoss-USD-CY2011-0000104169-14-000019-ab2642b5", "field": "Operating Income (Loss) [us-gaap:OperatingIncomeLoss]", "period": "CY2011", "unit": "USD", "value": "26491000000.0", "distractor_type": null}}`

## 15. CT_0010_16K

- context length: `16K`
- domain: `CLINICAL_TRIALS`
- question type: `RETRIEVAL_CALCULATION`
- answerable: `True`
- question: Using only the ClinicalTrials.gov records supplied in the context, subtract the enrollment count of trial NCT03800927 from the enrollment count of trial NCT03656445. Report the difference as an integer number of participants.
- gold answer: `80.0`
- model answer: `-124`
- answer correct: `False`
- abstention correct: `True`
- hallucination: `True`
- error type: `UNSUPPORTED_VALUE`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R584E60CDF3": {"canonical_record_id": "CT-NCT03656445-enrollment-count-535dc578", "field": "Enrollment (participants) [enrollment.count]", "period": null, "unit": "participants", "value": "180.0", "distractor_type": null}, "RF6704DB3B7": {"canonical_record_id": "CT-NCT03800927-enrollment-count-5f640681", "field": "Enrollment (participants) [enrollment.count]", "period": null, "unit": "participants", "value": "100.0", "distractor_type": null}}`

## 16. FDA_0010_32K

- context length: `32K`
- domain: `FDA`
- question type: `RETRIEVAL_CALCULATION`
- answerable: `True`
- question: Using only the Drugs@FDA records supplied in the context, how many distinct product entries are listed under FDA application ANDA205695 (sponsor: ANBISON LAB)? Count the products belonging to that application number only, and answer with an integer.
- gold answer: `2.0`
- model answer: `2`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R2CEE60A0A9": {"canonical_record_id": "FDA-ANDA205695-001-product-dosage-form-4f3d7427", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET, CHEWABLE", "distractor_type": null}, "R8D2B7063AB": {"canonical_record_id": "FDA-ANDA205695-002-product-dosage-form-75631b38", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET, CHEWABLE", "distractor_type": null}}`

## 17. FRED_0010_64K

- context length: `64K`
- domain: `FRED`
- question type: `RETRIEVAL_CALCULATION`
- answerable: `True`
- question: Using only the FRED records supplied in the context, calculate the percentage change in FRED series WGS10YR ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, weekly frequency between the observation dated 2026-07-24 and the observation dated 2026-07-31. Use both values from the most recent vintage, apply ((value_2026-07-31 - value_2026-07-24) / value_2026-07-24) * 100, and round to two decimal places.
- gold answer: `0.21`
- model answer: `0.05`
- answer correct: `False`
- abstention correct: `True`
- hallucination: `True`
- error type: `UNSUPPORTED_VALUE`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"RA2C8DBEEC0": {"canonical_record_id": "FRED-WGS10YR-2026-07-31-latest-b0603637", "field": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity (Not Seasonally Adjusted) [WGS10YR]", "period": "2026-07-31", "unit": "Percent", "value": "4.67", "distractor_type": null}, "RE9533D1E1E": {"canonical_record_id": "FRED-WGS10YR-2026-07-24-latest-4def8320", "field": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity (Not Seasonally Adjusted) [WGS10YR]", "period": "2026-07-24", "unit": "Percent", "value": "4.66", "distractor_type": null}}`

## 18. FRED_0013_4K

- context length: `4K`
- domain: `FRED`
- question type: `RETRIEVAL_CALCULATION`
- answerable: `True`
- question: Using only the FRED records supplied in the context, subtract the value of FRED series FEDFUNDS ("Federal Funds Effective Rate"), measured in Percent, not seasonally adjusted, monthly frequency from the value of FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency, both for the observation dated 2021-03-01 and both taken from the most recent vintage. Report the difference in Percent, rounded to two decimal places.
- gold answer: `1.38`
- model answer: `1.45`
- answer correct: `False`
- abstention correct: `True`
- hallucination: `False`
- error type: `CALCULATION_ERROR`
- matched context/distractor value: `1.45`
- matched distractor type: `None`
- rule: `calculation_answer_matches_context_operand_or_value`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R8990F7BC23": {"canonical_record_id": "FRED-DGS10-2021-03-01-latest-d3e46d51", "field": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity (Not Seasonally Adjusted) [DGS10]", "period": "2021-03-01", "unit": "Percent", "value": "1.45", "distractor_type": null}, "RC63C1F3E93": {"canonical_record_id": "FRED-FEDFUNDS-2021-03-01-latest-1bc0daea", "field": "Federal Funds Effective Rate (Not Seasonally Adjusted) [FEDFUNDS]", "period": "2021-03-01", "unit": "Percent", "value": "0.07", "distractor_type": null}}`

## 19. CT_0013_32K

- context length: `32K`
- domain: `CLINICAL_TRIALS`
- question type: `RETRIEVAL_CALCULATION`
- answerable: `True`
- question: Using only the ClinicalTrials.gov records supplied in the context, calculate the number of calendar days between the study start date and the primary completion date of trial NCT03310021 ("A Healthy Volunteer Pharmacokinetics (PK)/Pharmacodynamics (PD), Safety and Tolerability Study of Andexanet in Healthy Japanese and Caucasian Subjects"). Report a whole number of days. Use the primary completion date, not the overall study completion date and not the last update posted date.
- gold answer: `715.0`
- model answer: `109`
- answer correct: `False`
- abstention correct: `True`
- hallucination: `True`
- error type: `UNSUPPORTED_VALUE`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R49BD6ECB64": {"canonical_record_id": "CT-NCT03310021-study-start-date-79bbb709", "field": "Study start date [study.start_date]", "period": "2017", "unit": null, "value": "2017-08-28", "distractor_type": null}, "R4B2CDBA6AD": {"canonical_record_id": "CT-NCT03310021-study-primary-completion-a3ba8a2e", "field": "Primary completion date [study.primary_completion_date]", "period": "2019", "unit": null, "value": "2019-08-13", "distractor_type": null}}`

## 20. CT_0003_4K

- context length: `4K`
- domain: `CLINICAL_TRIALS`
- question type: `DIRECT_RETRIEVAL`
- answerable: `True`
- question: Using only the ClinicalTrials.gov records supplied in the context, what enrollment count is reported for trial NCT02408120 ("Benefits of Insulin Supplementation for Correction of Hyperglycemia in Patients With Type 2 Diabetes")? Report the actual number of participants as an integer.
- gold answer: `226.0`
- model answer: `226`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `226.0`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R3E85812DF7": {"canonical_record_id": "CT-NCT02408120-enrollment-count-8faccd69", "field": "Enrollment (participants) [enrollment.count]", "period": null, "unit": "participants", "value": "226.0", "distractor_type": null}}`

## 21. SEC_0002_8K

- context length: `8K`
- domain: `SEC`
- question type: `DIRECT_RETRIEVAL`
- answerable: `True`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did Johnson & Johnson (CIK 0000200406) report for the us-gaap concept "GrossProfit" (Gross Profit) for the annual XBRL frame CY2025, in USD? Report the exact reported figure.
- gold answer: `63937000000.0`
- model answer: `63937000000`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `63937000000.0`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R2940A33ABA": {"canonical_record_id": "SEC-0000200406-GrossProfit-USD-CY2025-0000200406-26-000016-de0a564d", "field": "Gross Profit [us-gaap:GrossProfit]", "period": "CY2025", "unit": "USD", "value": "63937000000.0", "distractor_type": null}}`

## 22. FRED_0021_16K

- context length: `16K`
- domain: `FRED`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency, for the observation dated 2009-09-07?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{}`

## 23. FRED_0008_32K

- context length: `32K`
- domain: `FRED`
- question type: `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the FRED records supplied in the context, report the value of FRED series WGS10YR ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, weekly frequency for United States on the observation dated 2015-01-30. Report the value for series WGS10YR exactly.
- gold answer: `1.77`
- model answer: `1.77`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `1.77`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R402DBA2483": {"canonical_record_id": "FRED-WGS10YR-2015-01-30-latest-bd2bd66f", "field": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity (Not Seasonally Adjusted) [WGS10YR]", "period": "2015-01-30", "unit": "Percent", "value": "1.77", "distractor_type": null}}`

## 24. SEC_0017_64K

- context length: `64K`
- domain: `SEC`
- question type: `TEMPORAL_VERSION`
- answerable: `True`
- question: Using only the SEC XBRL company-facts records supplied in the context, what did MICROSOFT CORPORATION (CIK 0000789019) report for us-gaap:NetCashProvidedByUsedInFinancingActivities for the single quarterly XBRL frame CY2021Q3, in USD? Report the quarterly figure exactly.
- gold answer: `-16276000000.0`
- model answer: `-16276000000.0`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `-16276000000.0`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R39ABB404FD": {"canonical_record_id": "SEC-0000789019-NetCashProvidedByUsedInF-USD-CY2021Q3-0001564590-22-035087-306cc7fc", "field": "Net Cash Provided by (Used in) Financing Activities [us-gaap:NetCashProvidedByUsedInFinancingActivities]", "period": "CY2021Q3", "unit": "USD", "value": "-16276000000.0", "distractor_type": null}}`

## 25. FDA_0008_4K

- context length: `4K`
- domain: `FDA`
- question type: `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the Drugs@FDA records supplied in the context, what is the listed strength of LOSARTAN POTASSIUM in product number 003 under FDA application ANDA090428 (dosage form TABLET, route ORAL)? Report the strength string exactly as recorded.
- gold answer: `100MG`
- model answer: `100MG`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `100MG`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"RDD82BB12F5": {"canonical_record_id": "FDA-ANDA090428-003-strength-LOSARTAN-POTASSIUM-0-73ee1961", "field": "Strength of LOSARTAN POTASSIUM [product.active_ingredient_strength]", "period": null, "unit": "MG", "value": "100MG", "distractor_type": null}}`

## 26. FRED_0022_32K

- context length: `32K`
- domain: `FRED`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series ILUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency, for the observation dated 2025-10-01?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{}`

## 27. FRED_0024_32K

- context length: `32K`
- domain: `FRED`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series UNRATENSA ("Unemployment Rate"), measured in Percent, not seasonally adjusted, monthly frequency, for the observation dated 2025-10-01?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{}`

## 28. FRED_0024_64K

- context length: `64K`
- domain: `FRED`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series UNRATENSA ("Unemployment Rate"), measured in Percent, not seasonally adjusted, monthly frequency, for the observation dated 2025-10-01?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{}`

## 29. FRED_0025_32K

- context length: `32K`
- domain: `FRED`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series FLUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency, for the observation dated 2025-10-01?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{}`

## 30. SEC_0014_32K

- context length: `32K`
- domain: `SEC`
- question type: `RETRIEVAL_CALCULATION`
- answerable: `True`
- question: Using only the SEC XBRL company-facts records supplied in the context, calculate the year-over-year percentage change in Apple Inc.'s (CIK 0000320193) reported us-gaap:CostOfGoodsAndServicesSold from annual XBRL frame CY2007 to annual XBRL frame CY2008, both in USD. Use ((current - previous) / previous) * 100 and round to two decimal places.
- gold answer: `47.9`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `False`
- abstention correct: `False`
- hallucination: `False`
- error type: `UNNECESSARY_ABSTENTION`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answerable_instance_unnecessary_abstention`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R56B40CFAAF": {"canonical_record_id": "SEC-0000320193-CostOfGoodsAndServicesSo-USD-CY2008-0001193125-10-238044-75b6ee2e", "field": "Cost of Goods and Services Sold [us-gaap:CostOfGoodsAndServicesSold]", "period": "CY2008", "unit": "USD", "value": "24294000000.0", "distractor_type": null}, "RD05F499C85": {"canonical_record_id": "SEC-0000320193-CostOfGoodsAndServicesSo-USD-CY2007-0001193125-10-012091-a8a3cea9", "field": "Cost of Goods and Services Sold [us-gaap:CostOfGoodsAndServicesSold]", "period": "CY2007", "unit": "USD", "value": "16426000000.0", "distractor_type": null}}`

## 31. SEC_0016_64K

- context length: `64K`
- domain: `SEC`
- question type: `RETRIEVAL_CALCULATION`
- answerable: `True`
- question: Using only the SEC XBRL company-facts records supplied in the context, calculate the year-over-year percentage change in Johnson & Johnson's (CIK 0000200406) reported us-gaap:PaymentsToAcquirePropertyPlantAndEquipment from annual XBRL frame CY2015 to annual XBRL frame CY2016, both in USD. Use ((current - previous) / previous) * 100 and round to two decimal places.
- gold answer: `-6.84`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `False`
- abstention correct: `False`
- hallucination: `False`
- error type: `UNNECESSARY_ABSTENTION`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answerable_instance_unnecessary_abstention`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R214AF3F11C": {"canonical_record_id": "SEC-0000200406-PaymentsToAcquirePropert-USD-CY2015-0000200406-18-000005-290886b0", "field": "Payments to Acquire Property, Plant, and Equipment [us-gaap:PaymentsToAcquirePropertyPlantAndEquipment]", "period": "CY2015", "unit": "USD", "value": "3463000000.0", "distractor_type": null}, "R34AE136ED4": {"canonical_record_id": "SEC-0000200406-PaymentsToAcquirePropert-USD-CY2016-0000200406-19-000009-aab6d65b", "field": "Payments to Acquire Property, Plant, and Equipment [us-gaap:PaymentsToAcquirePropertyPlantAndEquipment]", "period": "CY2016", "unit": "USD", "value": "3226000000.0", "distractor_type": null}}`

## 32. SEC_0022_32K

- context length: `32K`
- domain: `SEC`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did WALMART INC. (CIK 0000104169) report for the us-gaap concept "AccountsReceivableNetCurrent" (Accounts Receivable, after Allowance for Credit Loss, Current) for the annual XBRL frame CY2023?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{}`

## 33. SEC_0024_32K

- context length: `32K`
- domain: `SEC`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did PFIZER INC (CIK 0000078003) report for the us-gaap concept "OperatingExpenses" (Operating Expenses) for the annual XBRL frame CY2023?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{}`

## 34. SEC_0025_32K

- context length: `32K`
- domain: `SEC`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did Johnson & Johnson (CIK 0000200406) report for the us-gaap concept "OperatingExpenses" (Operating Expenses) for the annual XBRL frame CY2023?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{}`

## 35. FRED_0021_4K

- context length: `4K`
- domain: `FRED`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency, for the observation dated 2009-09-07?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{}`

## 36. FRED_0021_8K

- context length: `8K`
- domain: `FRED`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency, for the observation dated 2009-09-07?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{}`

## 37. FRED_0022_16K

- context length: `16K`
- domain: `FRED`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series ILUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency, for the observation dated 2025-10-01?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{}`

## 38. FRED_0022_4K

- context length: `4K`
- domain: `FRED`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series ILUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency, for the observation dated 2025-10-01?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{}`

## 39. FRED_0022_8K

- context length: `8K`
- domain: `FRED`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series ILUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency, for the observation dated 2025-10-01?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{}`

## 40. FRED_0023_16K

- context length: `16K`
- domain: `FRED`
- question type: `UNANSWERABLE`
- answerable: `False`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series CPIAUCSL ("Consumer Price Index for All Urban Consumers: All Items in U.S. City Average"), measured in Index 1982-1984=100, seasonally adjusted, monthly frequency, for the observation dated 2025-10-01?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `INSUFFICIENT_EVIDENCE`
- answer correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- matched context/distractor value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{}`
