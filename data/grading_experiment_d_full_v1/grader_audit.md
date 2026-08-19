# Experiment D Deterministic Grader Audit

- sample size: `100`
- counts by context: `{'4K': 14, '8K': 17, '16K': 16, '32K': 17, '64K': 18, '82K': 18}`
- counts by domain: `{'FRED': 30, 'FDA': 21, 'SEC': 25, 'CLINICAL_TRIALS': 24}`
- counts by question type: `{'UNANSWERABLE': 25, 'RETRIEVAL_CALCULATION': 32, 'ENTITY_UNIT_BINDING': 13, 'DIRECT_RETRIEVAL': 16, 'TEMPORAL_VERSION': 14}`
- error type counts: `{'CORRECT': 39, 'UNSUPPORTED_VALUE': 27, 'WRONG_PERIOD': 7, 'CALCULATION_ERROR': 2, 'WRONG_ENTITY': 4, 'WRONG_VERSION': 4, 'FAILED_TO_ABSTAIN': 12, 'WRONG_FIELD': 4, 'UNNECESSARY_ABSTENTION': 1}`
- semantic-review count: `0`
- format-failure count: `0`

## Cases

### FRED_0119_4K

- context: `4K`
- domain/type: `FRED` / `UNANSWERABLE`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency, for the observation dated 1999-01-18?
- gold: `None`
- model answer: `INSUFFICIENT_EVIDENCE`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FDA_0069_4K

- context: `4K`
- domain/type: `FDA` / `RETRIEVAL_CALCULATION`
- question: Using only the Drugs@FDA records supplied in the context, divide the LINAGLIPTIN strength of product 002 under application NDA208026 by the LINAGLIPTIN strength of product 001 under application NDA208026. Both strengths are expressed in MG; report the dimensionless ratio rounded to four decimal places.
- gold: `2.0000`
- model answer: `2.5`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### SEC_0007_4K

- context: `4K`
- domain/type: `SEC` / `ENTITY_UNIT_BINDING`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did Apple Inc. (CIK 0000320193) report for us-gaap:IncomeTaxExpenseBenefit for the annual XBRL frame CY2021, in USD? Report the exact value for that filer.
- gold: `14,527,000,000`
- model answer: `1867000000.0`
- label: `WRONG_PERIOD`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `1867000000.0`
- matched distractor type: `WRONG_PERIOD`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### CT_0058_4K

- context: `4K`
- domain/type: `CLINICAL_TRIALS` / `RETRIEVAL_CALCULATION`
- question: Using only the ClinicalTrials.gov records supplied in the context, subtract the enrollment count of trial NCT00375466 from the enrollment count of trial NCT00375258. Report the difference as an integer number of participants.
- gold: `20,148`
- model answer: `20211`
- label: `CALCULATION_ERROR`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `20211.0`
- matched distractor type: `None`
- rule: `calculation_answer_matches_context_operand_or_value`
- semantic review: `False`

### CT_0060_4K

- context: `4K`
- domain/type: `CLINICAL_TRIALS` / `RETRIEVAL_CALCULATION`
- question: Using only the ClinicalTrials.gov records supplied in the context, calculate the number of calendar days between the study start date and the primary completion date of trial NCT03359837 ("Comparison of Two Treatment Regimens in Patients With Type 2 Diabetes After Short-term Intensive Insulin Therapy"). Report a whole number of days. Use the primary completion date, not the overall study completion date and not the last update posted date.
- gold: `891`
- model answer: `29`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### FDA_0055_4K

- context: `4K`
- domain/type: `FDA` / `RETRIEVAL_CALCULATION`
- question: Using only the Drugs@FDA records supplied in the context, how many distinct product entries are listed under FDA application ANDA091431 (sponsor: HERITAGE)? Count the products belonging to that application number only, and answer with an integer.
- gold: `6`
- model answer: `6`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### CT_0010_4K

- context: `4K`
- domain/type: `CLINICAL_TRIALS` / `RETRIEVAL_CALCULATION`
- question: Using only the ClinicalTrials.gov records supplied in the context, subtract the enrollment count of trial NCT03800927 from the enrollment count of trial NCT03656445. Report the difference as an integer number of participants.
- gold: `80`
- model answer: `80`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### CT_0066_4K

- context: `4K`
- domain/type: `CLINICAL_TRIALS` / `RETRIEVAL_CALCULATION`
- question: Using only the ClinicalTrials.gov records supplied in the context, calculate the number of calendar days between the study start date and the primary completion date of trial NCT03347292 ("Regorafenib Plus Pembrolizumab in First Line Systemic Treatment of HCC"). Report a whole number of days. Use the primary completion date, not the overall study completion date and not the last update posted date.
- gold: `913`
- model answer: `1095`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### FDA_0013_4K

- context: `4K`
- domain/type: `FDA` / `RETRIEVAL_CALCULATION`
- question: Using only the Drugs@FDA records supplied in the context, how many distinct product entries are listed under FDA application NDA020357 (sponsor: EMD SERONO INC)? Count the products belonging to that application number only, and answer with an integer.
- gold: `5`
- model answer: `7`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### SEC_0036_4K

- context: `4K`
- domain/type: `SEC` / `DIRECT_RETRIEVAL`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did AMAZON COM INC (CIK 0001018724) report for the us-gaap concept "NetCashProvidedByUsedInOperatingActivities" (Net Cash Provided by (Used in) Operating Activities) for the annual XBRL frame CY2025, in USD? Report the exact reported figure.
- gold: `139,514,000,000`
- model answer: `136162000000`
- label: `WRONG_ENTITY`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `136162000000.0`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### FRED_0081_4K

- context: `4K`
- domain/type: `FRED` / `TEMPORAL_VERSION`
- question: Using only the FRED/ALFRED records supplied in the context, what value did FRED series PAYEMS ("All Employees, Total Nonfarm"), measured in Thousands of Persons, seasonally adjusted, monthly frequency show for the observation dated 2023-03-01 **as of the vintage date 2023-09-28**? Report the value from that vintage exactly.
- gold: `155,472`
- model answer: `155134.0`
- label: `WRONG_VERSION`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `155134.0`
- matched distractor type: `WRONG_VERSION`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### FRED_0030_4K

- context: `4K`
- domain/type: `FRED` / `DIRECT_RETRIEVAL`
- question: Using only the FRED records supplied in the context, what value does the most recent vintage report for FRED series GDPC1 ("Gross Domestic Product"), measured in Billions of Chained 2017 Dollars, seasonally adjusted annual rate, quarterly frequency, for the observation dated 2018-07-01 (the quarter beginning 2018-07-01)? Report the currently published figure exactly.
- gold: `20,276.154`
- model answer: `20276.154`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `20276.154`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### CT_0033_8K

- context: `8K`
- domain/type: `CLINICAL_TRIALS` / `DIRECT_RETRIEVAL`
- question: Using only the ClinicalTrials.gov records supplied in the context, what enrollment count is reported for trial NCT04656067 ("Comparative Study Between Oxytocin Versus Tranexamic Acid and Ethamsylate")? Report the actual number of participants as an integer.
- gold: `230`
- model answer: `230`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `230.0`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### CT_0088_8K

- context: `8K`
- domain/type: `CLINICAL_TRIALS` / `ENTITY_UNIT_BINDING`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the PRIMARY COMPLETION DATE of trial NCT01425515 ("Improving Care for Patients With High Blood Pressure")? Answer in YYYY-MM-DD form.
- gold: `2014-10`
- model answer: `2014-10`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `2014-10`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_only_exact_match`
- semantic review: `False`

### CT_0048_8K

- context: `8K`
- domain/type: `CLINICAL_TRIALS` / `RETRIEVAL_CALCULATION`
- question: Using only the ClinicalTrials.gov records supplied in the context, subtract the enrollment count of trial NCT03717194 from the enrollment count of trial NCT02987751. Report the difference as an integer number of participants.
- gold: `98`
- model answer: `154`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### FRED_0116_8K

- context: `8K`
- domain/type: `FRED` / `UNANSWERABLE`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency, for the observation dated 2020-07-03?
- gold: `None`
- model answer: `INSUFFICIENT_EVIDENCE`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### SEC_0076_8K

- context: `8K`
- domain/type: `SEC` / `RETRIEVAL_CALCULATION`
- question: Using only the SEC XBRL company-facts records supplied in the context, calculate the year-over-year percentage change in WALMART INC.'s (CIK 0000104169) reported us-gaap:OperatingIncomeLoss from annual XBRL frame CY2020 to annual XBRL frame CY2021, both in USD. Use ((current - previous) / previous) * 100 and round to two decimal places.
- gold: `15.05%`
- model answer: `34.29`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### FRED_0047_8K

- context: `8K`
- domain/type: `FRED` / `RETRIEVAL_CALCULATION`
- question: Using only the FRED records supplied in the context, calculate the percentage change in FRED series HOUST ("New Privately-Owned Housing Units Started: Total Units"), measured in Thousands of Units, seasonally adjusted annual rate, monthly frequency between the observation dated 2017-02-01 and the observation dated 2017-03-01. Use both values from the most recent vintage, apply ((value_2017-03-01 - value_2017-02-01) / value_2017-02-01) * 100, and round to two decimal places.
- gold: `-6.37%`
- model answer: `0.00`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### CT_0065_8K

- context: `8K`
- domain/type: `CLINICAL_TRIALS` / `RETRIEVAL_CALCULATION`
- question: Using only the ClinicalTrials.gov records supplied in the context, calculate the number of calendar days between the study start date and the primary completion date of trial NCT03548935 ("STEP 1: Research Study Investigating How Well Semaglutide Works in People Suffering From Overweight or Obesity"). Report a whole number of days. Use the primary completion date, not the overall study completion date and not the last update posted date.
- gold: `665`
- model answer: `109`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### FDA_0117_8K

- context: `8K`
- domain/type: `FDA` / `UNANSWERABLE`
- question: Using only the Drugs@FDA records supplied in the context, what is the route of administration for product number 003 under FDA application ANDA215255 (brand name "CANAGLIFLOZIN AND METFORMIN HYDROCHLORIDE")?
- gold: `None`
- model answer: `ORAL`
- label: `FAILED_TO_ABSTAIN`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `ORAL`
- matched distractor type: `OTHER_SAME_DOMAIN`
- rule: `unanswerable_instance_factual_answer`
- semantic review: `False`

### SEC_0124_8K

- context: `8K`
- domain/type: `SEC` / `UNANSWERABLE`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did JPMORGAN CHASE & CO (CIK 0000019617) report for the us-gaap concept "AccountsPayableCurrent" (Accounts Payable, Current) for the annual XBRL frame CY2023?
- gold: `None`
- model answer: `INSUFFICIENT_EVIDENCE`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FDA_0019_8K

- context: `8K`
- domain/type: `FDA` / `TEMPORAL_VERSION`
- question: Using only the Drugs@FDA records supplied in the context, what is the submission status date of the ORIGINAL submission (submission type ORIG) for FDA application ANDA064139 (sponsor: CHARTWELL RX)? Answer in YYYY-MM-DD form.
- gold: `1996-01-29`
- model answer: `1996-01-29`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `1996-01-29`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FDA_0032_8K

- context: `8K`
- domain/type: `FDA` / `DIRECT_RETRIEVAL`
- question: Using only the Drugs@FDA records supplied in the context, what DOSAGE FORM is listed for product number 010 under FDA application NDA021116 (brand name "THYRO-TABS", active ingredient LEVOTHYROXINE SODIUM)? Answer with the dosage form exactly as recorded.
- gold: `TABLET`
- model answer: `TABLET`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `TABLET`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_only_exact_match`
- semantic review: `False`

### SEC_0046_8K

- context: `8K`
- domain/type: `SEC` / `RETRIEVAL_CALCULATION`
- question: Using only the SEC XBRL company-facts records supplied in the context, calculate MICROSOFT CORPORATION's (CIK 0000789019) operating margin for the annual XBRL frame CY2010. Divide us-gaap:OperatingIncomeLoss by Revenues for that same company and frame, both in USD, multiply by 100, and round to two decimal places.
- gold: `38.57%`
- model answer: `34.30`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### FRED_0104_16K

- context: `16K`
- domain/type: `FRED` / `ENTITY_UNIT_BINDING`
- question: Using only the FRED records supplied in the context, report the value of FRED series UNRATE ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency for United States on the observation dated 2021-07-01. Report the value for series UNRATE exactly.
- gold: `5.400`
- model answer: `5.4`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `5.4`
- matched distractor type: `NEAR_MATCH_VALUE`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FRED_0015_16K

- context: `16K`
- domain/type: `FRED` / `RETRIEVAL_CALCULATION`
- question: Using only the FRED records supplied in the context, subtract the value of FRED series UNRATENSA ("Unemployment Rate"), measured in Percent, not seasonally adjusted, monthly frequency from the value of FRED series UNRATE ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency, both for the observation dated 2016-10-01 and both taken from the most recent vintage. Report the difference in Percent, rounded to two decimal places.
- gold: `0.20`
- model answer: `0.30`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### SEC_0116_16K

- context: `16K`
- domain/type: `SEC` / `UNANSWERABLE`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did MICROSOFT CORPORATION (CIK 0000789019) report for the us-gaap concept "SellingGeneralAndAdministrativeExpense" (Selling, General and Administrative Expense) for the annual XBRL frame CY2023?
- gold: `None`
- model answer: `INSUFFICIENT_EVIDENCE`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FRED_0011_16K

- context: `16K`
- domain/type: `FRED` / `RETRIEVAL_CALCULATION`
- question: Using only the FRED records supplied in the context, calculate the percentage change in FRED series CPIAUCSL ("Consumer Price Index for All Urban Consumers: All Items in U.S. City Average"), measured in Index 1982-1984=100, seasonally adjusted, monthly frequency between the observation dated 2026-05-01 and the observation dated 2026-06-01. Use both values from the most recent vintage, apply ((value_2026-06-01 - value_2026-05-01) / value_2026-05-01) * 100, and round to two decimal places.
- gold: `-0.42%`
- model answer: `0.03`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### FRED_0061_16K

- context: `16K`
- domain/type: `FRED` / `RETRIEVAL_CALCULATION`
- question: Using only the FRED records supplied in the context, calculate the percentage change in FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency between the observation dated 2016-12-29 and the observation dated 2016-12-30. Use both values from the most recent vintage, apply ((value_2016-12-30 - value_2016-12-29) / value_2016-12-29) * 100, and round to two decimal places.
- gold: `-1.61%`
- model answer: `0.01`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### CT_0110_16K

- context: `16K`
- domain/type: `CLINICAL_TRIALS` / `UNANSWERABLE`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the date on which results were first posted for trial NCT05078255 ("The Separate and Combined Effects of Long-term GIP and GLP-1 Receptor Activation in Patients with Type 2 Diabetes")?
- gold: `None`
- model answer: `2021-10-14`
- label: `FAILED_TO_ABSTAIN`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `2021-10-14`
- matched distractor type: `WRONG_FIELD`
- rule: `unanswerable_instance_factual_answer`
- semantic review: `False`

### FRED_0008_16K

- context: `16K`
- domain/type: `FRED` / `ENTITY_UNIT_BINDING`
- question: Using only the FRED records supplied in the context, report the value of FRED series WGS10YR ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, weekly frequency for United States on the observation dated 2015-01-30. Report the value for series WGS10YR exactly.
- gold: `1.770`
- model answer: `1.77`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `1.77`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### CT_0078_16K

- context: `16K`
- domain/type: `CLINICAL_TRIALS` / `ENTITY_UNIT_BINDING`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the PRIMARY COMPLETION DATE of trial NCT07619495 ("Injectable Semaglutide vs Dulaglutide in Individuals at Cardiovascular Risk")? Answer in YYYY-MM-DD form.
- gold: `2026-06-01`
- model answer: `2026-06-01`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `2026-06-01`
- matched distractor type: `WRONG_FIELD`
- rule: `answer_only_exact_match`
- semantic review: `False`

### SEC_0090_16K

- context: `16K`
- domain/type: `SEC` / `TEMPORAL_VERSION`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did WALMART INC. (CIK 0000104169) report for us-gaap:OperatingIncomeLoss for the period ending 2009-10-31 in the MOST RECENTLY FILED version of that fact — accession 0001193125-10-274171, form 10-Q, filed 2010-12-06 — in USD? Report the exact value from that version.
- gold: `5,442,000,000`
- model answer: `5593000000.0`
- label: `WRONG_PERIOD`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `5593000000.0`
- matched distractor type: `WRONG_PERIOD`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### FDA_0063_16K

- context: `16K`
- domain/type: `FDA` / `RETRIEVAL_CALCULATION`
- question: Using only the Drugs@FDA records supplied in the context, divide the GLYBURIDE strength of product 003 under application ANDA076345 by the GLYBURIDE strength of product 001 under application NDA021178. Both strengths are expressed in MG; report the dimensionless ratio rounded to four decimal places.
- gold: `4.0000`
- model answer: `5.0`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### FRED_0072_16K

- context: `16K`
- domain/type: `FRED` / `RETRIEVAL_CALCULATION`
- question: Using only the FRED records supplied in the context, subtract the value of FRED series TXUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency from the value of FRED series CAUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency, both for the observation dated 2023-01-01 and both taken from the most recent vintage. Report the difference in Percent, rounded to two decimal places.
- gold: `0.30`
- model answer: `1.40`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### FRED_0079_16K

- context: `16K`
- domain/type: `FRED` / `TEMPORAL_VERSION`
- question: Using only the FRED/ALFRED records supplied in the context, what value did FRED series PAYEMS ("All Employees, Total Nonfarm"), measured in Thousands of Persons, seasonally adjusted, monthly frequency show for the observation dated 2022-01-01 **as of the vintage date 2022-06-29**? Report the value from that vintage exactly.
- gold: `149,744`
- model answer: `150106`
- label: `WRONG_VERSION`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `150106.0`
- matched distractor type: `WRONG_VERSION`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### SEC_0061_32K

- context: `32K`
- domain/type: `SEC` / `RETRIEVAL_CALCULATION`
- question: Using only the SEC XBRL company-facts records supplied in the context, calculate the year-over-year percentage change in Johnson & Johnson's (CIK 0000200406) reported us-gaap:IncomeTaxExpenseBenefit from annual XBRL frame CY2011 to annual XBRL frame CY2012, both in USD. Use ((current - previous) / previous) * 100 and round to two decimal places.
- gold: `21.27%`
- model answer: `-24.00`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### SEC_0092_32K

- context: `32K`
- domain/type: `SEC` / `TEMPORAL_VERSION`
- question: Using only the SEC XBRL company-facts records supplied in the context, what did AMAZON COM INC (CIK 0001018724) report for us-gaap:IncomeTaxExpenseBenefit for the single quarterly XBRL frame CY2020Q2, in USD? Report the quarterly figure exactly.
- gold: `984,000,000`
- model answer: `984000000`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `984000000.0`
- matched distractor type: `WRONG_PERIOD`
- rule: `answer_only_exact_match`
- semantic review: `False`

### SEC_0067_32K

- context: `32K`
- domain/type: `SEC` / `RETRIEVAL_CALCULATION`
- question: Using only the SEC XBRL company-facts records supplied in the context, calculate the year-over-year percentage change in Apple Inc.'s (CIK 0000320193) reported us-gaap:GrossProfit from annual XBRL frame CY2017 to annual XBRL frame CY2018, both in USD. Use ((current - previous) / previous) * 100 and round to two decimal places.
- gold: `15.48%`
- model answer: `5.89`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### CT_0083_32K

- context: `32K`
- domain/type: `CLINICAL_TRIALS` / `ENTITY_UNIT_BINDING`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the PRIMARY COMPLETION DATE of trial NCT00211939 ("CARE-2 (Calcium Acetate [PhosLo®]/Sevelamer[Renagel®] Evaluation Study 2) for Heart Calcification in Dialysis Patients")? Answer in YYYY-MM-DD form.
- gold: `2006-12`
- model answer: `2007-03`
- label: `WRONG_FIELD`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `2007-03`
- matched distractor type: `WRONG_FIELD`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### FDA_0063_32K

- context: `32K`
- domain/type: `FDA` / `RETRIEVAL_CALCULATION`
- question: Using only the Drugs@FDA records supplied in the context, divide the GLYBURIDE strength of product 003 under application ANDA076345 by the GLYBURIDE strength of product 001 under application NDA021178. Both strengths are expressed in MG; report the dimensionless ratio rounded to four decimal places.
- gold: `4.0000`
- model answer: `0.5`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### SEC_0063_32K

- context: `32K`
- domain/type: `SEC` / `RETRIEVAL_CALCULATION`
- question: Using only the SEC XBRL company-facts records supplied in the context, calculate the year-over-year percentage change in WALMART INC.'s (CIK 0000104169) reported us-gaap:SellingGeneralAndAdministrativeExpense from annual XBRL frame CY2024 to annual XBRL frame CY2025, both in USD. Use ((current - previous) / previous) * 100 and round to two decimal places.
- gold: `5.76%`
- model answer: `0.00`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### CT_0093_32K

- context: `32K`
- domain/type: `CLINICAL_TRIALS` / `ENTITY_UNIT_BINDING`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the arm-group TYPE of the arm labelled "Metformin" in trial NCT03968224 ("Effectiveness of Dapagliflozin for Weight Loss")? Answer with the ClinicalTrials.gov arm type value (for example EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, SHAM_COMPARATOR, NO_INTERVENTION or OTHER).
- gold: `ACTIVE_COMPARATOR`
- model answer: `ACTIVE_COMPARATOR`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `ACTIVE_COMPARATOR`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_only_exact_match`
- semantic review: `False`

### CT_0013_32K

- context: `32K`
- domain/type: `CLINICAL_TRIALS` / `RETRIEVAL_CALCULATION`
- question: Using only the ClinicalTrials.gov records supplied in the context, calculate the number of calendar days between the study start date and the primary completion date of trial NCT03310021 ("A Healthy Volunteer Pharmacokinetics (PK)/Pharmacodynamics (PD), Safety and Tolerability Study of Andexanet in Healthy Japanese and Caucasian Subjects"). Report a whole number of days. Use the primary completion date, not the overall study completion date and not the last update posted date.
- gold: `715`
- model answer: `109`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### FRED_0002_32K

- context: `32K`
- domain/type: `FRED` / `DIRECT_RETRIEVAL`
- question: Using only the FRED records supplied in the context, what value does the most recent vintage report for FRED series GDP ("Gross Domestic Product"), measured in Billions of Dollars, seasonally adjusted annual rate, quarterly frequency, for the observation dated 2021-04-01 (the quarter beginning 2021-04-01)? Report the currently published figure exactly.
- gold: `23,425.910`
- model answer: `22740.959`
- label: `WRONG_VERSION`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `22740.959`
- matched distractor type: `WRONG_VERSION`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### CT_0091_32K

- context: `32K`
- domain/type: `CLINICAL_TRIALS` / `ENTITY_UNIT_BINDING`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the arm-group TYPE of the arm labelled "Placebo" in trial NCT03351478 ("Efficacy and Safety of Sotagliflozin Versus Placebo and Empagliflozin in Participants With Type 2 Diabetes Mellitus Who Have Inadequate Glycemic Control While Taking a DPP4 Inhibitor Alone or With Metformin")? Answer with the ClinicalTrials.gov arm type value (for example EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, SHAM_COMPARATOR, NO_INTERVENTION or OTHER).
- gold: `PLACEBO_COMPARATOR`
- model answer: `PLACEBO_COMPARATOR`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `PLACEBO_COMPARATOR`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_only_exact_match`
- semantic review: `False`

### SEC_0028_32K

- context: `32K`
- domain/type: `SEC` / `DIRECT_RETRIEVAL`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did Johnson & Johnson (CIK 0000200406) report for the us-gaap concept "CostOfGoodsAndServicesSold" (Cost of Goods and Services Sold) for the annual XBRL frame CY2017, in USD? Report the exact reported figure.
- gold: `25,439,000,000`
- model answer: `11228000000.0`
- label: `WRONG_ENTITY`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `11228000000.0`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### FDA_0106_32K

- context: `32K`
- domain/type: `FDA` / `UNANSWERABLE`
- question: Using only the Drugs@FDA records supplied in the context, what is the route of administration for product number 005 under FDA application ANDA219296 (brand name "SITAGLIPTIN AND METFORMIN HYDROCHLORIDE")?
- gold: `None`
- model answer: `ORAL`
- label: `FAILED_TO_ABSTAIN`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `ORAL`
- matched distractor type: `OTHER_SAME_DOMAIN`
- rule: `unanswerable_instance_factual_answer`
- semantic review: `False`

### FDA_0013_64K

- context: `64K`
- domain/type: `FDA` / `RETRIEVAL_CALCULATION`
- question: Using only the Drugs@FDA records supplied in the context, how many distinct product entries are listed under FDA application NDA020357 (sponsor: EMD SERONO INC)? Count the products belonging to that application number only, and answer with an integer.
- gold: `5`
- model answer: `9`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### CT_0097_64K

- context: `64K`
- domain/type: `CLINICAL_TRIALS` / `ENTITY_UNIT_BINDING`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the arm-group TYPE of the arm labelled "Favezelimab/Pembrolizumab" in trial NCT05508867 ("A Study of Coformulated Favezelimab/Pembrolizumab (MK-4280A) Versus Physician's Choice Chemotherapy in PD-(L)1-refractory, Relapsed or Refractory Classical Hodgkin Lymphoma (MK-4280A-008)")? Answer with the ClinicalTrials.gov arm type value (for example EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, SHAM_COMPARATOR, NO_INTERVENTION or OTHER).
- gold: `EXPERIMENTAL`
- model answer: `EXPERIMENTAL`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `EXPERIMENTAL`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FRED_0071_64K

- context: `64K`
- domain/type: `FRED` / `RETRIEVAL_CALCULATION`
- question: Using only the FRED records supplied in the context, subtract the value of FRED series FEDFUNDS ("Federal Funds Effective Rate"), measured in Percent, not seasonally adjusted, monthly frequency from the value of FRED series GS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, monthly frequency, both for the observation dated 2025-10-01 and both taken from the most recent vintage. Report the difference in Percent, rounded to two decimal places.
- gold: `-0.03`
- model answer: `4.09`
- label: `CALCULATION_ERROR`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `4.09`
- matched distractor type: `None`
- rule: `calculation_answer_matches_context_operand_or_value`
- semantic review: `False`

### SEC_0054_64K

- context: `64K`
- domain/type: `SEC` / `RETRIEVAL_CALCULATION`
- question: Using only the SEC XBRL company-facts records supplied in the context, calculate the year-over-year percentage change in COCA COLA CO's (CIK 0000021344) reported us-gaap:NetCashProvidedByUsedInInvestingActivities from annual XBRL frame CY2010 to annual XBRL frame CY2011, both in USD. Use ((current - previous) / previous) * 100 and round to two decimal places.
- gold: `-42.70%`
- model answer: `INSUFFICIENT_EVIDENCE`
- label: `UNNECESSARY_ABSTENTION`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answerable_instance_unnecessary_abstention`
- semantic review: `False`

### FRED_0125_64K

- context: `64K`
- domain/type: `FRED` / `UNANSWERABLE`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency, for the observation dated 2012-09-03?
- gold: `None`
- model answer: `2.14`
- label: `FAILED_TO_ABSTAIN`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `2.14`
- matched distractor type: `WRONG_FIELD`
- rule: `unanswerable_instance_factual_answer`
- semantic review: `False`

### FRED_0019_64K

- context: `64K`
- domain/type: `FRED` / `TEMPORAL_VERSION`
- question: Using only the FRED/ALFRED records supplied in the context, what value did FRED series UNRATE ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency show for the observation dated 2023-05-01 **as of the vintage date 2023-09-28**? Report the value from that vintage exactly.
- gold: `3.700`
- model answer: `3.7`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `3.7`
- matched distractor type: `WRONG_PERIOD`
- rule: `answer_only_exact_match`
- semantic review: `False`

### CT_0084_64K

- context: `64K`
- domain/type: `CLINICAL_TRIALS` / `ENTITY_UNIT_BINDING`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the PRIMARY COMPLETION DATE of trial NCT05551624 ("Evaluation of the Effect in Platelet Count of Atorvastatin and N-acetyl Cysteine")? Answer in YYYY-MM-DD form.
- gold: `2019-12-11`
- model answer: `2022-09-22`
- label: `WRONG_FIELD`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `2022-09-22`
- matched distractor type: `WRONG_FIELD`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### CT_0071_64K

- context: `64K`
- domain/type: `CLINICAL_TRIALS` / `RETRIEVAL_CALCULATION`
- question: Using only the ClinicalTrials.gov records supplied in the context, calculate the number of calendar days between the study start date and the primary completion date of trial NCT02578680 ("Study of Pemetrexed+Platinum Chemotherapy With or Without Pembrolizumab (MK-3475) in Participants With First Line Metastatic Nonsquamous Non-small Cell Lung Cancer (MK-3475-189/KEYNOTE-189)"). Report a whole number of days. Use the primary completion date, not the overall study completion date and not the last update posted date.
- gold: `663`
- model answer: `21`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### CT_0020_64K

- context: `64K`
- domain/type: `CLINICAL_TRIALS` / `ENTITY_UNIT_BINDING`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the PRIMARY COMPLETION DATE of trial NCT02178722 ("Study to Explore the Safety, Tolerability and Efficacy of MK-3475 in Combination With INCB024360 in Participants With Selected Cancers")? Answer in YYYY-MM-DD form.
- gold: `2018-11-26`
- model answer: `2022-02-14`
- label: `WRONG_FIELD`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `2022-02-14`
- matched distractor type: `WRONG_FIELD`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### CT_0063_64K

- context: `64K`
- domain/type: `CLINICAL_TRIALS` / `RETRIEVAL_CALCULATION`
- question: Using only the ClinicalTrials.gov records supplied in the context, calculate the number of calendar days between the study start date and the primary completion date of trial NCT05334108 ("Drug-Drug Interaction Study to Evaluate the Effects of Ecopipam on the Pharmacokinetics of Multiple Substrates for Drug Metabolism and Transport"). Report a whole number of days. Use the primary completion date, not the overall study completion date and not the last update posted date.
- gold: `97`
- model answer: `63`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### FRED_0022_64K

- context: `64K`
- domain/type: `FRED` / `UNANSWERABLE`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series ILUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency, for the observation dated 2025-10-01?
- gold: `None`
- model answer: `4.7`
- label: `FAILED_TO_ABSTAIN`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `4.7`
- matched distractor type: `WRONG_PERIOD`
- rule: `unanswerable_instance_factual_answer`
- semantic review: `False`

### SEC_0001_64K

- context: `64K`
- domain/type: `SEC` / `DIRECT_RETRIEVAL`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did WALMART INC. (CIK 0000104169) report for the us-gaap concept "CostOfRevenue" (Cost of Revenue) for the annual XBRL frame CY2020, in USD? Report the exact reported figure.
- gold: `420,315,000,000`
- model answer: `100339000000`
- label: `WRONG_PERIOD`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `100339000000.0`
- matched distractor type: `WRONG_PERIOD`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### FDA_0103_64K

- context: `64K`
- domain/type: `FDA` / `ENTITY_UNIT_BINDING`
- question: Using only the Drugs@FDA records supplied in the context, what is the listed strength of DAPAGLIFLOZIN in product number 003 under FDA application ANDA211489 (dosage form TABLET, EXTENDED RELEASE, route ORAL)? Report the strength string exactly as recorded.
- gold: `10MG`
- model answer: `10MG`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `10MG`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_only_exact_match`
- semantic review: `False`

### CT_0001_64K

- context: `64K`
- domain/type: `CLINICAL_TRIALS` / `DIRECT_RETRIEVAL`
- question: Using only the ClinicalTrials.gov records supplied in the context, what enrollment count is reported for trial NCT02262793 ("Relative Bioavailability of Telmisartan and Dipyridamole After Co-administration Compared to the Bioavailability of Telmisartan or Dipyridamole Alone in Healthy Female and Male Subjects")? Report the actual number of participants as an integer.
- gold: `24`
- model answer: `24`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `24.0`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FDA_0018_64K

- context: `64K`
- domain/type: `FDA` / `TEMPORAL_VERSION`
- question: Using only the Drugs@FDA records supplied in the context, what is the submission status date of the ORIGINAL submission (submission type ORIG) for FDA application ANDA209306 (sponsor: LUPIN)? Answer in YYYY-MM-DD form.
- gold: `2018-08-24`
- model answer: `2018-11-12`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### CT_0060_82K

- context: `82K`
- domain/type: `CLINICAL_TRIALS` / `RETRIEVAL_CALCULATION`
- question: Using only the ClinicalTrials.gov records supplied in the context, calculate the number of calendar days between the study start date and the primary completion date of trial NCT03359837 ("Comparison of Two Treatment Regimens in Patients With Type 2 Diabetes After Short-term Intensive Insulin Therapy"). Report a whole number of days. Use the primary completion date, not the overall study completion date and not the last update posted date.
- gold: `891`
- model answer: `384`
- label: `WRONG_FIELD`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `384.0`
- matched distractor type: `WRONG_FIELD`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### FRED_0032_82K

- context: `82K`
- domain/type: `FRED` / `DIRECT_RETRIEVAL`
- question: Using only the FRED records supplied in the context, what value does the most recent vintage report for FRED series PAYEMS ("All Employees, Total Nonfarm"), measured in Thousands of Persons, seasonally adjusted, monthly frequency, for the observation dated 2023-10-01 (the month beginning 2023-10-01)? Report the currently published figure exactly.
- gold: `156,576`
- model answer: `156576`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `156576.0`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### SEC_0083_82K

- context: `82K`
- domain/type: `SEC` / `TEMPORAL_VERSION`
- question: Using only the SEC XBRL company-facts records supplied in the context, what did PFIZER INC (CIK 0000078003) report for us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest for the single quarterly XBRL frame CY2015Q3, in USD? Report the quarterly figure exactly.
- gold: `2,697,000,000`
- model answer: `17250000000.0`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### FDA_0018_82K

- context: `82K`
- domain/type: `FDA` / `TEMPORAL_VERSION`
- question: Using only the Drugs@FDA records supplied in the context, what is the submission status date of the ORIGINAL submission (submission type ORIG) for FDA application ANDA209306 (sponsor: LUPIN)? Answer in YYYY-MM-DD form.
- gold: `2018-08-24`
- model answer: `2018-05-25`
- label: `WRONG_ENTITY`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `2018-05-25`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### FRED_0045_82K

- context: `82K`
- domain/type: `FRED` / `DIRECT_RETRIEVAL`
- question: Using only the FRED records supplied in the context, what value does the most recent vintage report for FRED series UNRATE ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency, for the observation dated 2022-11-01 (the month beginning 2022-11-01)? Report the currently published figure exactly.
- gold: `3.600`
- model answer: `3.6`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `3.6`
- matched distractor type: `WRONG_FIELD`
- rule: `answer_only_exact_match`
- semantic review: `False`

### SEC_0048_82K

- context: `82K`
- domain/type: `SEC` / `RETRIEVAL_CALCULATION`
- question: Using only the SEC XBRL company-facts records supplied in the context, calculate the year-over-year percentage change in COCA COLA CO's (CIK 0000021344) reported us-gaap:GrossProfit from annual XBRL frame CY2018 to annual XBRL frame CY2019, both in USD. Use ((current - previous) / previous) * 100 and round to two decimal places.
- gold: `6.66%`
- model answer: `-1.00`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### CT_0001_82K

- context: `82K`
- domain/type: `CLINICAL_TRIALS` / `DIRECT_RETRIEVAL`
- question: Using only the ClinicalTrials.gov records supplied in the context, what enrollment count is reported for trial NCT02262793 ("Relative Bioavailability of Telmisartan and Dipyridamole After Co-administration Compared to the Bioavailability of Telmisartan or Dipyridamole Alone in Healthy Female and Male Subjects")? Report the actual number of participants as an integer.
- gold: `24`
- model answer: `24`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `24.0`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FRED_0080_82K

- context: `82K`
- domain/type: `FRED` / `TEMPORAL_VERSION`
- question: Using only the FRED/ALFRED records supplied in the context, what value did FRED series UNRATE ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency show for the observation dated 2020-04-01 **as of the vintage date 2021-04-29**? Report the value from that vintage exactly.
- gold: `14.800`
- model answer: `14.8`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `14.8`
- matched distractor type: `WRONG_VERSION`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FRED_0089_82K

- context: `82K`
- domain/type: `FRED` / `TEMPORAL_VERSION`
- question: Using only the FRED/ALFRED records supplied in the context, what value did FRED series CPIAUCSL ("Consumer Price Index for All Urban Consumers: All Items in U.S. City Average"), measured in Index 1982-1984=100, seasonally adjusted, monthly frequency show for the observation dated 2023-05-01 **as of the vintage date 2023-09-28**? Report the value from that vintage exactly.
- gold: `303.294`
- model answer: `300.536`
- label: `WRONG_PERIOD`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `300.536`
- matched distractor type: `WRONG_PERIOD`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### FDA_0083_82K

- context: `82K`
- domain/type: `FDA` / `TEMPORAL_VERSION`
- question: Using only the Drugs@FDA records supplied in the context, what is the submission status date of the ORIGINAL submission (submission type ORIG) for FDA application ANDA203438 (sponsor: AJANTA PHARMA LTD)? Answer in YYYY-MM-DD form.
- gold: `2015-07-31`
- model answer: `2015-07-31`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `2015-07-31`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_only_exact_match`
- semantic review: `False`

### SEC_0001_82K

- context: `82K`
- domain/type: `SEC` / `DIRECT_RETRIEVAL`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did WALMART INC. (CIK 0000104169) report for the us-gaap concept "CostOfRevenue" (Cost of Revenue) for the annual XBRL frame CY2020, in USD? Report the exact reported figure.
- gold: `420,315,000,000`
- model answer: `100339000000`
- label: `WRONG_PERIOD`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `100339000000.0`
- matched distractor type: `WRONG_PERIOD`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### FDA_0025_82K

- context: `82K`
- domain/type: `FDA` / `UNANSWERABLE`
- question: Using only the Drugs@FDA records supplied in the context, what is the route of administration for product number 002 under FDA application ANDA216516 (brand name "SITAGLIPTIN AND METFORMIN HYDROCHLORIDE")?
- gold: `None`
- model answer: `ORAL`
- label: `FAILED_TO_ABSTAIN`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `ORAL`
- matched distractor type: `OTHER_SAME_DOMAIN`
- rule: `unanswerable_instance_factual_answer`
- semantic review: `False`

### FRED_0081_82K

- context: `82K`
- domain/type: `FRED` / `TEMPORAL_VERSION`
- question: Using only the FRED/ALFRED records supplied in the context, what value did FRED series PAYEMS ("All Employees, Total Nonfarm"), measured in Thousands of Persons, seasonally adjusted, monthly frequency show for the observation dated 2023-03-01 **as of the vintage date 2023-09-28**? Report the value from that vintage exactly.
- gold: `155,472`
- model answer: `155134`
- label: `WRONG_VERSION`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `155134.0`
- matched distractor type: `WRONG_VERSION`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### FDA_0114_82K

- context: `82K`
- domain/type: `FDA` / `UNANSWERABLE`
- question: Using only the Drugs@FDA records supplied in the context, what is the route of administration for product number 003 under FDA application ANDA219755 (brand name "DAPAGLIFLOZIN AND METFORMIN HYDROCHLORIDE")?
- gold: `None`
- model answer: `ORAL`
- label: `FAILED_TO_ABSTAIN`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `ORAL`
- matched distractor type: `OTHER_SAME_DOMAIN`
- rule: `unanswerable_instance_factual_answer`
- semantic review: `False`

### SEC_0106_82K

- context: `82K`
- domain/type: `SEC` / `UNANSWERABLE`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did WALMART INC. (CIK 0000104169) report for the us-gaap concept "CostOfGoodsAndServicesSold" (Cost of Goods and Services Sold) for the annual XBRL frame CY2023?
- gold: `None`
- model answer: `64720000000.0`
- label: `FAILED_TO_ABSTAIN`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `64720000000.0`
- matched distractor type: `OTHER_SAME_DOMAIN`
- rule: `unanswerable_instance_factual_answer`
- semantic review: `False`

### SEC_0122_32K

- context: `32K`
- domain/type: `SEC` / `UNANSWERABLE`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did JPMORGAN CHASE & CO (CIK 0000019617) report for the us-gaap concept "OperatingIncomeLoss" (Operating Income (Loss)) for the annual XBRL frame CY2023?
- gold: `None`
- model answer: `INSUFFICIENT_EVIDENCE`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### SEC_0012_82K

- context: `82K`
- domain/type: `SEC` / `RETRIEVAL_CALCULATION`
- question: Using only the SEC XBRL company-facts records supplied in the context, calculate COCA COLA CO's (CIK 0000021344) operating margin for the annual XBRL frame CY2016. Divide us-gaap:OperatingIncomeLoss by Revenues for that same company and frame, both in USD, multiply by 100, and round to two decimal places.
- gold: `20.68%`
- model answer: `0.00`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### FDA_0036_64K

- context: `64K`
- domain/type: `FDA` / `DIRECT_RETRIEVAL`
- question: Using only the Drugs@FDA records supplied in the context, what DOSAGE FORM is listed for product number 002 under FDA application ANDA065228 (brand name "AMOXICILLIN", active ingredient AMOXICILLIN)? Answer with the dosage form exactly as recorded.
- gold: `TABLET`
- model answer: `TABLET`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `TABLET`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FDA_0030_8K

- context: `8K`
- domain/type: `FDA` / `DIRECT_RETRIEVAL`
- question: Using only the Drugs@FDA records supplied in the context, what DOSAGE FORM is listed for product number 002 under FDA application ANDA077525 (brand name "GABAPENTIN", active ingredient GABAPENTIN)? Answer with the dosage form exactly as recorded.
- gold: `TABLET`
- model answer: `TABLET`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `TABLET`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FDA_0092_82K

- context: `82K`
- domain/type: `FDA` / `ENTITY_UNIT_BINDING`
- question: Using only the Drugs@FDA records supplied in the context, what is the listed strength of METFORMIN HYDROCHLORIDE in product number 003 under FDA application NDA021178 (dosage form TABLET, route ORAL)? Report the strength string exactly as recorded.
- gold: `500MG **Federal Register determination that product was not discontinued or withdrawn for safety or effectiveness reasons**`
- model answer: `500MG`
- label: `WRONG_ENTITY`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `500MG`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### FDA_0075_8K

- context: `8K`
- domain/type: `FDA` / `RETRIEVAL_CALCULATION`
- question: Using only the Drugs@FDA records supplied in the context, divide the SITAGLIPTIN PHOSPHATE ANHYDROUS, METFORMIN HYDROCHLORIDE strength of product 003 under application ANDA217395 by the SITAGLIPTIN PHOSPHATE ANHYDROUS, METFORMIN HYDROCHLORIDE strength of product 004 under application ANDA217395. Both strengths are expressed in MG; report the dimensionless ratio rounded to four decimal places.
- gold: `10.0000`
- model answer: `0.5`
- label: `UNSUPPORTED_VALUE`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_not_matched_to_context_value`
- semantic review: `False`

### FRED_0114_16K

- context: `16K`
- domain/type: `FRED` / `UNANSWERABLE`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency, for the observation dated 2024-07-04?
- gold: `None`
- model answer: `INSUFFICIENT_EVIDENCE`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### SEC_0120_4K

- context: `4K`
- domain/type: `SEC` / `UNANSWERABLE`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did COCA COLA CO (CIK 0000021344) report for the us-gaap concept "Liabilities" (Liabilities) for the annual XBRL frame CY2023?
- gold: `None`
- model answer: `INSUFFICIENT_EVIDENCE`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FRED_0117_16K

- context: `16K`
- domain/type: `FRED` / `UNANSWERABLE`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency, for the observation dated 2010-11-25?
- gold: `None`
- model answer: `INSUFFICIENT_EVIDENCE`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FRED_0123_4K

- context: `4K`
- domain/type: `FRED` / `UNANSWERABLE`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency, for the observation dated 2018-07-04?
- gold: `None`
- model answer: `INSUFFICIENT_EVIDENCE`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FRED_0118_32K

- context: `32K`
- domain/type: `FRED` / `UNANSWERABLE`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency, for the observation dated 1991-12-25?
- gold: `None`
- model answer: `INSUFFICIENT_EVIDENCE`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FRED_0117_32K

- context: `32K`
- domain/type: `FRED` / `UNANSWERABLE`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency, for the observation dated 2010-11-25?
- gold: `None`
- model answer: `INSUFFICIENT_EVIDENCE`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### FRED_0025_8K

- context: `8K`
- domain/type: `FRED` / `UNANSWERABLE`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series FLUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency, for the observation dated 2025-10-01?
- gold: `None`
- model answer: `INSUFFICIENT_EVIDENCE`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### SEC_0106_8K

- context: `8K`
- domain/type: `SEC` / `UNANSWERABLE`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did WALMART INC. (CIK 0000104169) report for the us-gaap concept "CostOfGoodsAndServicesSold" (Cost of Goods and Services Sold) for the annual XBRL frame CY2023?
- gold: `None`
- model answer: `INSUFFICIENT_EVIDENCE`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### SEC_0120_32K

- context: `32K`
- domain/type: `SEC` / `UNANSWERABLE`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did COCA COLA CO (CIK 0000021344) report for the us-gaap concept "Liabilities" (Liabilities) for the annual XBRL frame CY2023?
- gold: `None`
- model answer: `27734000000`
- label: `FAILED_TO_ABSTAIN`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `None`
- matched distractor type: `None`
- rule: `unanswerable_instance_factual_answer`
- semantic review: `False`

### FRED_0116_82K

- context: `82K`
- domain/type: `FRED` / `UNANSWERABLE`
- question: Using only the FRED records supplied in the context, what value does FRED report for FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency, for the observation dated 2020-07-03?
- gold: `None`
- model answer: `1.61`
- label: `FAILED_TO_ABSTAIN`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `1.61`
- matched distractor type: `WRONG_FIELD`
- rule: `unanswerable_instance_factual_answer`
- semantic review: `False`

### SEC_0020_16K

- context: `16K`
- domain/type: `SEC` / `TEMPORAL_VERSION`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did JPMORGAN CHASE & CO (CIK 0000019617) report for us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding for the period ending 2016-06-30 in the MOST RECENTLY FILED version of that fact — accession 0000019617-17-000486, form 10-Q, filed 2017-08-02 — in shares? Report the exact value from that version.
- gold: `3,706,200,000`
- model answer: `3666500000.0`
- label: `WRONG_PERIOD`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `3666500000.0`
- matched distractor type: `WRONG_PERIOD`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### FRED_0057_16K

- context: `16K`
- domain/type: `FRED` / `RETRIEVAL_CALCULATION`
- question: Using only the FRED records supplied in the context, calculate the percentage change in FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency between the observation dated 2022-01-19 and the observation dated 2022-01-20. Use both values from the most recent vintage, apply ((value_2022-01-20 - value_2022-01-19) / value_2022-01-19) * 100, and round to two decimal places.
- gold: `0.00%`
- model answer: `0.00`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `None`
- matched distractor type: `None`
- rule: `answer_only_exact_match`
- semantic review: `False`

### CT_0113_64K

- context: `64K`
- domain/type: `CLINICAL_TRIALS` / `UNANSWERABLE`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the date on which results were first posted for trial NCT01308281 ("Impact of IntraVascular UltraSound Guidance on Outcomes of Xience Prime Stents in Long Lesions (IVUS-XPL Study)")?
- gold: `None`
- model answer: `2016-07-27`
- label: `FAILED_TO_ABSTAIN`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `2016-07-27`
- matched distractor type: `WRONG_FIELD`
- rule: `unanswerable_instance_factual_answer`
- semantic review: `False`

### SEC_0004_32K

- context: `32K`
- domain/type: `SEC` / `DIRECT_RETRIEVAL`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did MICROSOFT CORPORATION (CIK 0000789019) report for the us-gaap concept "GrossProfit" (Gross Profit) for the annual XBRL frame CY2021, in USD? Report the exact reported figure.
- gold: `115,856,000,000`
- model answer: `66439000000.0`
- label: `WRONG_PERIOD`
- answer_correct: `False`
- hallucination: `False`
- matched context value: `66439000000.0`
- matched distractor type: `WRONG_PERIOD`
- rule: `answer_matches_context_distractor_value`
- semantic review: `False`

### CT_0022_8K

- context: `8K`
- domain/type: `CLINICAL_TRIALS` / `UNANSWERABLE`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the date on which results were first posted for trial NCT03535883 ("The Safety of Thoracentesis, Tunneled Pleural Catheter, and Chest Tubes in Patients Taking Novel Oral Anti-Coagulants")?
- gold: `None`
- model answer: `2018-05-24`
- label: `FAILED_TO_ABSTAIN`
- answer_correct: `False`
- hallucination: `True`
- matched context value: `2018-05-24`
- matched distractor type: `WRONG_FIELD`
- rule: `unanswerable_instance_factual_answer`
- semantic review: `False`

### FDA_0001_64K

- context: `64K`
- domain/type: `FDA` / `DIRECT_RETRIEVAL`
- question: Using only the Drugs@FDA records supplied in the context, what DOSAGE FORM is listed for product number 001 under FDA application ANDA070469 (brand name "IBUPROHM", active ingredient IBUPROFEN)? Answer with the dosage form exactly as recorded.
- gold: `TABLET`
- model answer: `TABLET`
- label: `CORRECT`
- answer_correct: `True`
- hallucination: `False`
- matched context value: `TABLET`
- matched distractor type: `WRONG_ENTITY`
- rule: `answer_only_exact_match`
- semantic review: `False`
