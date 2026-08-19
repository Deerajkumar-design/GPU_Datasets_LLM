# Deterministic Grading Audit Sample

- sample size: `36`
- deterministically resolved: `12`
- semantic review required: `24`
- format failures: `24`
- error types: `{'FORMAT_FAILURE': 24, 'WRONG_EVIDENCE': 4, 'FAILED_TO_ABSTAIN': 1, 'CORRECT': 2, 'WRONG_VERSION': 1, 'UNSUPPORTED_VALUE': 1, 'WRONG_ENTITY': 2, 'WRONG_SERIES_VARIANT': 1}`

## 1. SEC_0021_32K

- question: Using only the SEC XBRL company-facts records supplied in the context, what value did JPMORGAN CHASE & CO (CIK 0000019617) report for the us-gaap concept "SellingGeneralAndAdministrativeExpense" (Selling, General and Administrative Expense) for the annual XBRL frame CY2023?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `None`
- gold evidence display IDs: `[]`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `False`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{}`

## 2. FDA_0002_32K

- question: Using only the Drugs@FDA records supplied in the context, what DOSAGE FORM is listed for product number 001 under FDA application ANDA080353 (brand name "PREDNISONE", active ingredient PREDNISONE)? Answer with the dosage form exactly as recorded.
- gold answer: `TABLET`
- model answer: `TABLET`
- gold evidence display IDs: `['R33016BA5E7']`
- selected evidence: `['R...']`
- answer correct: `True`
- evidence correct: `False`
- abstention correct: `True`
- hallucination: `False`
- error type: `WRONG_EVIDENCE`
- rule: `answer_correct_evidence_incorrect`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R33016BA5E7": {"canonical_record_id": "FDA-ANDA080353-001-product-dosage-form-32e8d29a", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET"}, "R9EBF8995F2": {"canonical_record_id": "FDA-ANDA076593-002-product-dosage-form-66043a0a", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET"}}`

## 3. CT_0025_4K

- question: Using only the ClinicalTrials.gov records supplied in the context, what is the maximum eligible age for trial NCT02489357 ("Pembrolizumab and Cryosurgery in Treating Patients With Newly Diagnosed, Oligo-metastatic Prostate Cancer")?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `18`
- gold evidence display IDs: `[]`
- selected evidence: `['R4F0C1BFFE8', 'R2566BE05B3', 'R105AEB8723', 'R71DBB1A9C', 'R8E4DC67CC5', 'R3E1E492CF3', 'RRC7C199B5E5']`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `False`
- hallucination: `True`
- error type: `FAILED_TO_ABSTAIN`
- rule: `failed_to_abstain_unsupported_value`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R105AEB8723": {"canonical_record_id": "CT-NCT02489357-eligibility-sex-ade4242d", "field": "Eligible sex [eligibility.sex]", "period": null, "unit": null, "value": "MALE"}, "R2566BE05B3": {"canonical_record_id": "CT-NCT02489357-design-allocation-127da278", "field": "Allocation [design.allocation]", "period": null, "unit": null, "value": "NA"}, "R3E1E492CF3": {"canonical_record_id": "CT-NCT02489357-study-condition-0-3ede8bcb", "field": "Studied condition [study.condition]", "period": null, "unit": null, "value": "Stage IV Prostate Cancer"}, "R4F0C1BFFE8": {"canonical_record_id": "CT-NCT02489357-study-overall-status-c9df9680", "field": "Overall recruitment status [study.overall_status]", "period": null, "unit": null, "value": "COMPLETED"}, "R8E4DC67CC5": {"canonical_record_id": "CT-NCT01023607-eligibility-minimum-age-dce69b60", "field": "Minimum eligible age [eligibility.minimum_age]", "period": null, "unit": null, "value": "18 Years"}}`

## 4. FDA_0021_8K

- question: Using only the Drugs@FDA records supplied in the context, what is the route of administration for product number 001 under FDA application ANDA215255 (brand name "CANAGLIFLOZIN AND METFORMIN HYDROCHLORIDE")?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `None`
- gold evidence display IDs: `[]`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `False`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{}`

## 5. FRED_0008_16K

- question: Using only the FRED records supplied in the context, report the value of FRED series WGS10YR ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, weekly frequency for United States on the observation dated 2015-01-30. Report the value for series WGS10YR exactly.
- gold answer: `1.77`
- model answer: `1.77`
- gold evidence display IDs: `['R402DBA2483']`
- selected evidence: `['R402DBA2483']`
- answer correct: `True`
- evidence correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- rule: `deterministic_exact`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R402DBA2483": {"canonical_record_id": "FRED-WGS10YR-2015-01-30-latest-bd2bd66f", "field": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity (Not Seasonally Adjusted) [WGS10YR]", "period": "2015-01-30", "unit": "Percent", "value": "1.77"}}`

## 6. SEC_0019_64K

- question: Using only the SEC XBRL company-facts records supplied in the context, what value did PFIZER INC (CIK 0000078003) report for us-gaap:NetCashProvidedByUsedInOperatingActivities for the period ending 2016-10-02 in the MOST RECENTLY FILED version of that fact — accession 0000078003-17-000049, form 10-Q, filed 2017-11-09 — in USD? Report the exact value from that version.
- gold answer: `10151000000.0`
- model answer: `9929000000.0`
- gold evidence display IDs: `['R93E3DF4118']`
- selected evidence: `['R5E11A68820']`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `True`
- hallucination: `False`
- error type: `WRONG_VERSION`
- rule: `model_answer_matches_context_distractor_value`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R5E11A68820": {"canonical_record_id": "SEC-0000078003-NetCashProvidedByUsedInI-USD-2024-01-01-2024-12-31-0000078003-25-000054-9223ee00", "field": "Net Cash Provided by (Used in) Investing Activities [us-gaap:NetCashProvidedByUsedInInvestingActivities]", "period": "2024-01-01..2024-12-31", "unit": "USD", "value": "2652000000.0"}, "R93E3DF4118": {"canonical_record_id": "SEC-0000078003-NetCashProvidedByUsedInO-USD-2016-01-01-2016-10-02-0000078003-17-000049-12a9492c", "field": "Net Cash Provided by (Used in) Operating Activities [us-gaap:NetCashProvidedByUsedInOperatingActivities]", "period": "2016-01-01..2016-10-02", "unit": "USD", "value": "10151000000.0"}, "RA6AF0B5F5E": {"canonical_record_id": "SEC-0000078003-NetCashProvidedByUsedInO-USD-2016-01-01-2016-10-02-0000078003-16-000113-d2ee48c6", "field": "Net Cash Provided by (Used in) Operating Activities [us-gaap:NetCashProvidedByUsedInOperatingActivities]", "period": "2016-01-01..2016-10-02", "unit": "USD", "value": "9929000000.0"}}`

## 7. FRED_0004_4K

- question: Using only the FRED records supplied in the context, what value does the most recent vintage report for FRED series GDPC1 ("Gross Domestic Product"), measured in Billions of Chained 2017 Dollars, seasonally adjusted annual rate, quarterly frequency, for the observation dated 2019-10-01 (the quarter beginning 2019-10-01)? Report the currently published figure exactly.
- gold answer: `20985.448`
- model answer: `21978`
- gold evidence display IDs: `['R7097297563']`
- selected evidence: `['R7097297563', 'R588464E4C5', 'R9978BB4835', 'RBB321DAD20']`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `True`
- hallucination: `True`
- error type: `UNSUPPORTED_VALUE`
- rule: `model_answer_not_matched_to_context_value`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R588464E4C5": {"canonical_record_id": "FRED-GDP-2019-10-01-2025-03-27-4e6f2ab7", "field": "Gross Domestic Product (Seasonally Adjusted Annual Rate) [GDP]", "period": "2019-10-01", "unit": "Billions of Dollars", "value": "21933.217"}, "R7097297563": {"canonical_record_id": "FRED-GDPC1-2019-10-01-latest-bfa762c2", "field": "Gross Domestic Product (Seasonally Adjusted Annual Rate) [GDPC1]", "period": "2019-10-01", "unit": "Billions of Chained 2017 Dollars", "value": "20985.448"}, "R9978BB4835": {"canonical_record_id": "FRED-GDP-2019-10-01-2023-09-28-eba699df", "field": "Gross Domestic Product (Seasonally Adjusted Annual Rate) [GDP]", "period": "2019-10-01", "unit": "Billions of Dollars", "value": "21902.39"}, "RBB321DAD20": {"canonical_record_id": "FRED-GDPC1-2022-10-01-latest-4ffecad7", "field": "Gross Domestic Product (Seasonally Adjusted Annual Rate) [GDPC1]", "period": "2022-10-01", "unit": "Billions of Chained 2017 Dollars", "value": "22278.345"}}`

## 8. SEC_0016_32K

- question: Using only the SEC XBRL company-facts records supplied in the context, calculate the year-over-year percentage change in Johnson & Johnson's (CIK 0000200406) reported us-gaap:PaymentsToAcquirePropertyPlantAndEquipment from annual XBRL frame CY2015 to annual XBRL frame CY2016, both in USD. Use ((current - previous) / previous) * 100 and round to two decimal places.
- gold answer: `-6.84`
- model answer: `None`
- gold evidence display IDs: `['R34AE136ED4', 'R214AF3F11C']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R214AF3F11C": {"canonical_record_id": "SEC-0000200406-PaymentsToAcquirePropert-USD-CY2015-0000200406-18-000005-290886b0", "field": "Payments to Acquire Property, Plant, and Equipment [us-gaap:PaymentsToAcquirePropertyPlantAndEquipment]", "period": "CY2015", "unit": "USD", "value": "3463000000.0"}, "R34AE136ED4": {"canonical_record_id": "SEC-0000200406-PaymentsToAcquirePropert-USD-CY2016-0000200406-19-000009-aab6d65b", "field": "Payments to Acquire Property, Plant, and Equipment [us-gaap:PaymentsToAcquirePropertyPlantAndEquipment]", "period": "CY2016", "unit": "USD", "value": "3226000000.0"}}`

## 9. SEC_0006_32K

- question: Using only the SEC XBRL company-facts records supplied in the context, what value did PFIZER INC (CIK 0000078003) report for us-gaap:NetCashProvidedByUsedInInvestingActivities for the annual XBRL frame CY2010, in USD? Report the exact value for that filer.
- gold answer: `-492000000.0`
- model answer: `-11314000000.0`
- gold evidence display IDs: `['R1747BDE59E']`
- selected evidence: `['R0D308CA4D3']`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `True`
- hallucination: `False`
- error type: `WRONG_ENTITY`
- rule: `model_answer_matches_context_distractor_value`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R0D308CA4D3": {"canonical_record_id": "SEC-0001018724-WeightedAverageNumberOfD-shares-2009-01-01-2009-12-31-0001193125-11-016253-2c3444f6", "field": "Weighted Average Number of Shares Outstanding, Diluted [us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding]", "period": "2009-01-01..2009-12-31", "unit": "shares", "value": "442000000.0"}, "R1747BDE59E": {"canonical_record_id": "SEC-0000078003-NetCashProvidedByUsedInI-USD-CY2010-0000078003-13-000006-0cfaf545", "field": "Net Cash Provided by (Used in) Investing Activities [us-gaap:NetCashProvidedByUsedInInvestingActivities]", "period": "CY2010", "unit": "USD", "value": "-492000000.0"}, "RA0CA5EEED5": {"canonical_record_id": "SEC-0000789019-NetCashProvidedByUsedInI-USD-CY2010-0001193125-12-316848-24efaeac", "field": "Net Cash Provided by (Used in) Investing Activities [us-gaap:NetCashProvidedByUsedInInvestingActivities]", "period": "CY2010", "unit": "USD", "value": "-11314000000.0"}}`

## 10. SEC_0006_4K

- question: Using only the SEC XBRL company-facts records supplied in the context, what value did PFIZER INC (CIK 0000078003) report for us-gaap:NetCashProvidedByUsedInInvestingActivities for the annual XBRL frame CY2010, in USD? Report the exact value for that filer.
- gold answer: `-492000000.0`
- model answer: `None`
- gold evidence display IDs: `['R1747BDE59E']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R1747BDE59E": {"canonical_record_id": "SEC-0000078003-NetCashProvidedByUsedInI-USD-CY2010-0000078003-13-000006-0cfaf545", "field": "Net Cash Provided by (Used in) Investing Activities [us-gaap:NetCashProvidedByUsedInInvestingActivities]", "period": "CY2010", "unit": "USD", "value": "-492000000.0"}}`

## 11. SEC_0006_64K

- question: Using only the SEC XBRL company-facts records supplied in the context, what value did PFIZER INC (CIK 0000078003) report for us-gaap:NetCashProvidedByUsedInInvestingActivities for the annual XBRL frame CY2010, in USD? Report the exact value for that filer.
- gold answer: `-492000000.0`
- model answer: `-11314000000.0`
- gold evidence display IDs: `['R1747BDE59E']`
- selected evidence: `['R7FA382A2FB']`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `True`
- hallucination: `False`
- error type: `WRONG_ENTITY`
- rule: `model_answer_matches_context_distractor_value`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R1747BDE59E": {"canonical_record_id": "SEC-0000078003-NetCashProvidedByUsedInI-USD-CY2010-0000078003-13-000006-0cfaf545", "field": "Net Cash Provided by (Used in) Investing Activities [us-gaap:NetCashProvidedByUsedInInvestingActivities]", "period": "CY2010", "unit": "USD", "value": "-492000000.0"}, "R7FA382A2FB": {"canonical_record_id": "SEC-0001018724-CostOfGoodsAndServicesSo-USD-2009-01-01-2009-12-31-0001193125-11-016253-71ceede4", "field": "Cost of Goods and Services Sold [us-gaap:CostOfGoodsAndServicesSold]", "period": "2009-01-01..2009-12-31", "unit": "USD", "value": "18978000000.0"}, "RA0CA5EEED5": {"canonical_record_id": "SEC-0000789019-NetCashProvidedByUsedInI-USD-CY2010-0001193125-12-316848-24efaeac", "field": "Net Cash Provided by (Used in) Investing Activities [us-gaap:NetCashProvidedByUsedInInvestingActivities]", "period": "CY2010", "unit": "USD", "value": "-11314000000.0"}}`

## 12. CT_0007_4K

- question: Using only the ClinicalTrials.gov records supplied in the context, what is the arm-group TYPE of the arm labelled "Placebo" in trial NCT01728636 ("The Use of Tranexamic Acid to Reduce Perioperative Blood Loss During High Risk Spine Fusion Surgery")? Answer with the ClinicalTrials.gov arm type value (for example EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, SHAM_COMPARATOR, NO_INTERVENTION or OTHER).
- gold answer: `PLACEBO_COMPARATOR`
- model answer: `PLACEBO_COMPARATOR`
- gold evidence display IDs: `['R3A6D2D6B08']`
- selected evidence: `['R3A6D2D6B08']`
- answer correct: `True`
- evidence correct: `True`
- abstention correct: `True`
- hallucination: `False`
- error type: `CORRECT`
- rule: `deterministic_exact`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R3A6D2D6B08": {"canonical_record_id": "CT-NCT01728636-arm-type-Placebo-1-34edfc87", "field": "Arm group type: Placebo [arm.type]", "period": null, "unit": null, "value": "PLACEBO_COMPARATOR"}}`

## 13. CT_0007_32K

- question: Using only the ClinicalTrials.gov records supplied in the context, what is the arm-group TYPE of the arm labelled "Placebo" in trial NCT01728636 ("The Use of Tranexamic Acid to Reduce Perioperative Blood Loss During High Risk Spine Fusion Surgery")? Answer with the ClinicalTrials.gov arm type value (for example EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, SHAM_COMPARATOR, NO_INTERVENTION or OTHER).
- gold answer: `PLACEBO_COMPARATOR`
- model answer: `None`
- gold evidence display IDs: `['R3A6D2D6B08']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R3A6D2D6B08": {"canonical_record_id": "CT-NCT01728636-arm-type-Placebo-1-34edfc87", "field": "Arm group type: Placebo [arm.type]", "period": null, "unit": null, "value": "PLACEBO_COMPARATOR"}}`

## 14. CT_0007_64K

- question: Using only the ClinicalTrials.gov records supplied in the context, what is the arm-group TYPE of the arm labelled "Placebo" in trial NCT01728636 ("The Use of Tranexamic Acid to Reduce Perioperative Blood Loss During High Risk Spine Fusion Surgery")? Answer with the ClinicalTrials.gov arm type value (for example EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, SHAM_COMPARATOR, NO_INTERVENTION or OTHER).
- gold answer: `PLACEBO_COMPARATOR`
- model answer: `PLACEBO_COMPARATOR`
- gold evidence display IDs: `['R3A6D2D6B08']`
- selected evidence: `['R01728636']`
- answer correct: `True`
- evidence correct: `False`
- abstention correct: `True`
- hallucination: `False`
- error type: `WRONG_EVIDENCE`
- rule: `answer_correct_evidence_incorrect`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R3A6D2D6B08": {"canonical_record_id": "CT-NCT01728636-arm-type-Placebo-1-34edfc87", "field": "Arm group type: Placebo [arm.type]", "period": null, "unit": null, "value": "PLACEBO_COMPARATOR"}, "R9120D06548": {"canonical_record_id": "CT-NCT01617655-arm-type-Placebo-Q2W-0-40a1b906", "field": "Arm group type: Placebo Q2W [arm.type]", "period": null, "unit": null, "value": "PLACEBO_COMPARATOR"}}`

## 15. FDA_0003_4K

- question: Using only the Drugs@FDA records supplied in the context, what DOSAGE FORM is listed for product number 006 under FDA application ANDA075999 (brand name "LISINOPRIL", active ingredient LISINOPRIL)? Answer with the dosage form exactly as recorded.
- gold answer: `TABLET`
- model answer: `TABLET`
- gold evidence display IDs: `['R89F59D6895']`
- selected evidence: `['R1EA76B3C1F', 'R3B0F4E6A97', 'R36CB53BC56', 'R89F59D6895', 'R51E088F81C', 'RCD67978E23', 'RFA9D0586B0', 'RBD8060C29B', 'R84674E29DE', 'R6597968FF7', 'RDB2A77166D', 'R14D96148D5']`
- answer correct: `True`
- evidence correct: `False`
- abstention correct: `True`
- hallucination: `False`
- error type: `WRONG_EVIDENCE`
- rule: `answer_correct_evidence_incorrect`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R14D96148D5": {"canonical_record_id": "FDA-ANDA202554-004-product-dosage-form-9694cf79", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET"}, "R1EA76B3C1F": {"canonical_record_id": "FDA-ANDA075999-006-product-brand-name-bf92774d", "field": "Brand name [product.brand_name]", "period": null, "unit": null, "value": "LISINOPRIL"}, "R36CB53BC56": {"canonical_record_id": "FDA-ANDA075999-006-product-reference-drug-2a28e8a0", "field": "Reference listed drug [product.reference_drug]", "period": null, "unit": null, "value": "No"}, "R3B0F4E6A97": {"canonical_record_id": "FDA-ANDA071163-submission-SUPPL-30-6d42284a", "field": "SUPPL submission 30 status date [submission.status_date]", "period": "1993", "unit": null, "value": "1993-07-29"}, "R6597968FF7": {"canonical_record_id": "FDA-NDA009218-016-product-dosage-form-b3910da0", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET"}, "R84674E29DE": {"canonical_record_id": "FDA-ANDA216252-submission-SUPPL-3-2f99ee62", "field": "SUPPL submission 3 status date [submission.status_date]", "period": "2026", "unit": null, "value": "2026-01-07"}, "R89F59D6895": {"canonical_record_id": "FDA-ANDA075999-006-product-dosage-form-a7cba6df", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET"}, "RBD8060C29B": {"canonical_record_id": "FDA-ANDA040145-007-product-dosage-form-6394e120", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET"}, "RCD67978E23": {"canonical_record_id": "FDA-ANDA075999-006-product-route-214d83f9", "field": "Route of administration [product.route]", "period": null, "unit": null, "value": "ORAL"}, "RDB2A77166D": {"canonical_record_id": "FDA-ANDA206137-004-product-reference-standa-1f151d26", "field": "Reference standard [product.reference_standard]", "period": null, "unit": null, "value": "No"}, "REE6775A1EA": {"canonical_record_id": "FDA-ANDA205199-008-product-dosage-form-18edbe0e", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET"}, "RFA9D0586B0": {"canonical_record_id": "FDA-ANDA077977-005-product-reference-drug-b6bc5df8", "field": "Reference listed drug [product.reference_drug]", "period": null, "unit": null, "value": "No"}}`

## 16. FDA_0003_32K

- question: Using only the Drugs@FDA records supplied in the context, what DOSAGE FORM is listed for product number 006 under FDA application ANDA075999 (brand name "LISINOPRIL", active ingredient LISINOPRIL)? Answer with the dosage form exactly as recorded.
- gold answer: `TABLET`
- model answer: `None`
- gold evidence display IDs: `['R89F59D6895']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R89F59D6895": {"canonical_record_id": "FDA-ANDA075999-006-product-dosage-form-a7cba6df", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET"}}`

## 17. FDA_0003_64K

- question: Using only the Drugs@FDA records supplied in the context, what DOSAGE FORM is listed for product number 006 under FDA application ANDA075999 (brand name "LISINOPRIL", active ingredient LISINOPRIL)? Answer with the dosage form exactly as recorded.
- gold answer: `TABLET`
- model answer: `TABLET`
- gold evidence display IDs: `['R89F59D6895']`
- selected evidence: `['R8E6EC0182C']`
- answer correct: `True`
- evidence correct: `False`
- abstention correct: `True`
- hallucination: `False`
- error type: `WRONG_EVIDENCE`
- rule: `answer_correct_evidence_incorrect`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R842273FF7D": {"canonical_record_id": "FDA-ANDA075961-002-product-dosage-form-3a32f494", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET"}, "R89F59D6895": {"canonical_record_id": "FDA-ANDA075999-006-product-dosage-form-a7cba6df", "field": "Dosage form [product.dosage_form]", "period": null, "unit": null, "value": "TABLET"}, "R8E6EC0182C": {"canonical_record_id": "FDA-NDA200153-003-product-marketing-status-41fe5007", "field": "Marketing status [product.marketing_status]", "period": null, "unit": null, "value": "Discontinued"}}`

## 18. FRED_0007_4K

- question: Using only the FRED records supplied in the context, report the value of FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency for United States on the observation dated 2022-09-01. Report the value for series DGS10 exactly.
- gold answer: `3.26`
- model answer: `3.52`
- gold evidence display IDs: `['R9388092F79']`
- selected evidence: `['R3CEDBC5EC1']`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `True`
- hallucination: `False`
- error type: `WRONG_SERIES_VARIANT`
- rule: `model_answer_matches_context_distractor_value`
- semantic review required: `False`
- review reason: 
- compact context metadata: `{"R3CEDBC5EC1": {"canonical_record_id": "FRED-GS10-2022-09-01-latest-f992a164", "field": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity (Not Seasonally Adjusted) [GS10]", "period": "2022-09-01", "unit": "Percent", "value": "3.52"}, "R9388092F79": {"canonical_record_id": "FRED-DGS10-2022-09-01-latest-ee1793fc", "field": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity (Not Seasonally Adjusted) [DGS10]", "period": "2022-09-01", "unit": "Percent", "value": "3.26"}}`

## 19. FRED_0007_32K

- question: Using only the FRED records supplied in the context, report the value of FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency for United States on the observation dated 2022-09-01. Report the value for series DGS10 exactly.
- gold answer: `3.26`
- model answer: `None`
- gold evidence display IDs: `['R9388092F79']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R9388092F79": {"canonical_record_id": "FRED-DGS10-2022-09-01-latest-ee1793fc", "field": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity (Not Seasonally Adjusted) [DGS10]", "period": "2022-09-01", "unit": "Percent", "value": "3.26"}}`

## 20. FRED_0007_64K

- question: Using only the FRED records supplied in the context, report the value of FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency for United States on the observation dated 2022-09-01. Report the value for series DGS10 exactly.
- gold answer: `3.26`
- model answer: `None`
- gold evidence display IDs: `['R9388092F79']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R9388092F79": {"canonical_record_id": "FRED-DGS10-2022-09-01-latest-ee1793fc", "field": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity (Not Seasonally Adjusted) [DGS10]", "period": "2022-09-01", "unit": "Percent", "value": "3.26"}}`

## 21. CT_0001_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, what enrollment count is reported for trial NCT02262793 ("Relative Bioavailability of Telmisartan and Dipyridamole After Co-administration Compared to the Bioavailability of Telmisartan or Dipyridamole Alone in Healthy Female and Male Subjects")? Report the actual number of participants as an integer.
- gold answer: `24.0`
- model answer: `None`
- gold evidence display IDs: `['R900B293DCB']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R900B293DCB": {"canonical_record_id": "CT-NCT02262793-enrollment-count-5fd11e40", "field": "Enrollment (participants) [enrollment.count]", "period": null, "unit": "participants", "value": "24.0"}}`

## 22. CT_0002_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, what enrollment count is reported for trial NCT02325960 ("A Comparison of Exenatide and Insulin Glargine")? Report the actual number of participants as an integer.
- gold answer: `44.0`
- model answer: `None`
- gold evidence display IDs: `['RCA721B2F7E']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"RCA721B2F7E": {"canonical_record_id": "CT-NCT02325960-enrollment-count-9b749f82", "field": "Enrollment (participants) [enrollment.count]", "period": null, "unit": "participants", "value": "44.0"}}`

## 23. CT_0003_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, what enrollment count is reported for trial NCT02408120 ("Benefits of Insulin Supplementation for Correction of Hyperglycemia in Patients With Type 2 Diabetes")? Report the actual number of participants as an integer.
- gold answer: `226.0`
- model answer: `None`
- gold evidence display IDs: `['R3E85812DF7']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R3E85812DF7": {"canonical_record_id": "CT-NCT02408120-enrollment-count-8faccd69", "field": "Enrollment (participants) [enrollment.count]", "period": null, "unit": "participants", "value": "226.0"}}`

## 24. CT_0004_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, what enrollment count is reported for trial NCT02007070 ("Study of Pembrolizumab (MK-3475) in Participants With Advanced Non-small Cell Lung Cancer (MK-3475-025/KEYNOTE-025)")? Report the actual number of participants as an integer.
- gold answer: `38.0`
- model answer: `None`
- gold evidence display IDs: `['R0940082619']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R0940082619": {"canonical_record_id": "CT-NCT02007070-enrollment-count-774de6ac", "field": "Enrollment (participants) [enrollment.count]", "period": null, "unit": "participants", "value": "38.0"}}`

## 25. CT_0005_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, what enrollment count is reported for trial NCT05502562 ("A Research Study to Understand How Oral Semaglutide Works in People With Type 2 Diabetes in India")? Report the actual number of participants as an integer.
- gold answer: `388.0`
- model answer: `None`
- gold evidence display IDs: `['RC155DAD068']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"RC155DAD068": {"canonical_record_id": "CT-NCT05502562-enrollment-count-2d4615e2", "field": "Enrollment (participants) [enrollment.count]", "period": null, "unit": "participants", "value": "388.0"}}`

## 26. CT_0006_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, what is the arm-group TYPE of the arm labelled "Control" in trial NCT01340300 ("Exercise and Metformin in Colorectal and Breast Cancer Survivors")? Answer with the ClinicalTrials.gov arm type value (for example EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, SHAM_COMPARATOR, NO_INTERVENTION or OTHER).
- gold answer: `ACTIVE_COMPARATOR`
- model answer: `None`
- gold evidence display IDs: `['RB0734CF34D']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"RB0734CF34D": {"canonical_record_id": "CT-NCT01340300-arm-type-Control-3-fc797906", "field": "Arm group type: Control [arm.type]", "period": null, "unit": null, "value": "ACTIVE_COMPARATOR"}}`

## 27. CT_0007_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, what is the arm-group TYPE of the arm labelled "Placebo" in trial NCT01728636 ("The Use of Tranexamic Acid to Reduce Perioperative Blood Loss During High Risk Spine Fusion Surgery")? Answer with the ClinicalTrials.gov arm type value (for example EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, SHAM_COMPARATOR, NO_INTERVENTION or OTHER).
- gold answer: `PLACEBO_COMPARATOR`
- model answer: `None`
- gold evidence display IDs: `['R3A6D2D6B08']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R3A6D2D6B08": {"canonical_record_id": "CT-NCT01728636-arm-type-Placebo-1-34edfc87", "field": "Arm group type: Placebo [arm.type]", "period": null, "unit": null, "value": "PLACEBO_COMPARATOR"}}`

## 28. CT_0008_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, what is the arm-group TYPE of the arm labelled "Oral Tranexamic Acid (TXA)" in trial NCT04089865 ("Oral Versus Intravenous Tranexamic Acid")? Answer with the ClinicalTrials.gov arm type value (for example EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, SHAM_COMPARATOR, NO_INTERVENTION or OTHER).
- gold answer: `EXPERIMENTAL`
- model answer: `None`
- gold evidence display IDs: `['R3B3A2C955C']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R3B3A2C955C": {"canonical_record_id": "CT-NCT04089865-arm-type-Oral-Tranexamic-Acid-TXA-0-b38e9f5b", "field": "Arm group type: Oral Tranexamic Acid (TXA) [arm.type]", "period": null, "unit": null, "value": "EXPERIMENTAL"}}`

## 29. CT_0010_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, subtract the enrollment count of trial NCT03800927 from the enrollment count of trial NCT03656445. Report the difference as an integer number of participants.
- gold answer: `80.0`
- model answer: `None`
- gold evidence display IDs: `['R584E60CDF3', 'RF6704DB3B7']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R584E60CDF3": {"canonical_record_id": "CT-NCT03656445-enrollment-count-535dc578", "field": "Enrollment (participants) [enrollment.count]", "period": null, "unit": "participants", "value": "180.0"}, "RF6704DB3B7": {"canonical_record_id": "CT-NCT03800927-enrollment-count-5f640681", "field": "Enrollment (participants) [enrollment.count]", "period": null, "unit": "participants", "value": "100.0"}}`

## 30. CT_0014_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, calculate the number of calendar days between the study start date and the primary completion date of trial NCT03197467 ("Neoadjuvant Anti PD-1 Immunotherapy in Resectable Non-small Cell Lung Cancer"). Report a whole number of days. Use the primary completion date, not the overall study completion date and not the last update posted date.
- gold answer: `1230.0`
- model answer: `None`
- gold evidence display IDs: `['RB5E1094FBC', 'RDB56C600D1']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"RB5E1094FBC": {"canonical_record_id": "CT-NCT03197467-study-start-date-bf3bf559", "field": "Study start date [study.start_date]", "period": "2018", "unit": null, "value": "2018-06-18"}, "RDB56C600D1": {"canonical_record_id": "CT-NCT03197467-study-primary-completion-0a5f27bb", "field": "Primary completion date [study.primary_completion_date]", "period": "2021", "unit": null, "value": "2021-10-30"}}`

## 31. CT_0017_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, what is the PRIMARY COMPLETION DATE of trial NCT02746185 ("Cancer Associated Thrombosis, a Pilot Treatment Study Using Rivaroxaban")? Answer in YYYY-MM-DD form.
- gold answer: `2018-04-25`
- model answer: `None`
- gold evidence display IDs: `['R91B4903946']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R91B4903946": {"canonical_record_id": "CT-NCT02746185-study-primary-completion-35ff3c07", "field": "Primary completion date [study.primary_completion_date]", "period": "2018", "unit": null, "value": "2018-04-25"}}`

## 32. CT_0018_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, what is the PRIMARY COMPLETION DATE of trial NCT03969719 ("A Double-blind Study to Assess 2 Doses of an Investigational Product for 16 Weeks in Participants With Non-alcoholic Fatty Liver Disease and Type 2 Diabetes Mellitus")? Answer in YYYY-MM-DD form.
- gold answer: `2021-03-02`
- model answer: `None`
- gold evidence display IDs: `['R0962B1F447']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R0962B1F447": {"canonical_record_id": "CT-NCT03969719-study-primary-completion-33d5eec0", "field": "Primary completion date [study.primary_completion_date]", "period": "2021", "unit": null, "value": "2021-03-02"}}`

## 33. CT_0019_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, what is the PRIMARY COMPLETION DATE of trial NCT05144984 ("A Research Study Looking at How Well a Combination of the Medicines Semaglutide and NNC0480-0389 Works in People With Type 2 Diabetes")? Answer in YYYY-MM-DD form.
- gold answer: `2023-02-13`
- model answer: `None`
- gold evidence display IDs: `['R65CA09A85B']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R65CA09A85B": {"canonical_record_id": "CT-NCT05144984-study-primary-completion-c9c64e18", "field": "Primary completion date [study.primary_completion_date]", "period": "2023", "unit": null, "value": "2023-02-13"}}`

## 34. CT_0020_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, what is the PRIMARY COMPLETION DATE of trial NCT02178722 ("Study to Explore the Safety, Tolerability and Efficacy of MK-3475 in Combination With INCB024360 in Participants With Selected Cancers")? Answer in YYYY-MM-DD form.
- gold answer: `2018-11-26`
- model answer: `None`
- gold evidence display IDs: `['R425CD7386B']`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `None`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{"R425CD7386B": {"canonical_record_id": "CT-NCT02178722-study-primary-completion-b6031bc6", "field": "Primary completion date [study.primary_completion_date]", "period": "2018", "unit": null, "value": "2018-11-26"}}`

## 35. CT_0021_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, what is the date on which results were first posted for trial NCT02339493 ("Electronic Alerts for Stroke Prevention in Patients With Atrial Fibrillation or Atrial Flutter")?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `None`
- gold evidence display IDs: `[]`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `False`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{}`

## 36. CT_0022_16K

- question: Using only the ClinicalTrials.gov records supplied in the context, what is the date on which results were first posted for trial NCT03535883 ("The Safety of Thoracentesis, Tunneled Pleural Catheter, and Chest Tubes in Patients Taking Novel Oral Anti-Coagulants")?
- gold answer: `INSUFFICIENT_EVIDENCE`
- model answer: `None`
- gold evidence display IDs: `[]`
- selected evidence: `[]`
- answer correct: `False`
- evidence correct: `False`
- abstention correct: `False`
- hallucination: `None`
- error type: `FORMAT_FAILURE`
- rule: `json_parse_failure`
- semantic review required: `True`
- review reason: model output is not parseable JSON; raw output preserved
- compact context metadata: `{}`
