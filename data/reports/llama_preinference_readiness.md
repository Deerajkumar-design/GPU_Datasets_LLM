# Llama Pre-Inference Readiness

## Frozen prompt
- model: `meta-llama/Llama-3.2-3B-Instruct`
- tokenizer: `hf:meta-llama/Llama-3.2-3B-Instruct`
- tokenizer_class: `TokenizersBackend`
- native_chat_template_used: `True`
- frozen_template_date: `09 Aug 2026`
- prompt_version: `llama_chat_v2`
- prompt_hash: `14cc206955296997`
- response_format_version: `json_evidence_answer_v1`
- model_config_revision: `0cb88a4f764b7a12671c53f0838cd831a0843b95`
- tokenizer_revision: `None`

## Token budget
- model context limit: `131072`
- generation reserve: `512`
- maximum safe input: `130560`
- overflow count: `0`
- truncation failure count: `0`
- minimum remaining margin: `123`

| condition | rendered min | rendered mean | rendered max | margin min | margin mean | margin max |
|---|---:|---:|---:|---:|---:|---:|
| 4K | 4221 | 4281.7 | 4373 | 126187 | 126278.3 | 126339 |
| 8K | 8272 | 8345.2 | 8443 | 122117 | 122214.8 | 122288 |
| 16K | 16355 | 16456.0 | 16545 | 114015 | 114104.0 | 114205 |
| 32K | 32541 | 32687.0 | 32850 | 97710 | 97873.0 | 98019 |
| 64K | 64919 | 65136.5 | 65356 | 65204 | 65423.5 | 65641 |
| 128K | 129630 | 130043.0 | 130437 | 123 | 517.0 | 930 |

## Multi-evidence audit

The contexts and display_id_to_record_id mappings were correct. The issue was an audit/report rendering bug plus a schema ambiguity: flat gold_evidence_display_ids did not expose per-evidence operand mappings. v2 adds gold_evidence_display_map and renders per-record IDs.

### SEC_0009
Using only the SEC XBRL company-facts records supplied in the context, calculate WALMART INC.'s (CIK 0000104169) operating margin for the annual XBRL frame CY2011. Divide us-gaap:OperatingIncomeLoss by Revenues for that same company and frame, both in USD, multiply by 100, and round to two decimal places.

| role | canonical record id | display id | equivalent display ids | field | value |
|---|---|---|---|---|---|
| numerator | `SEC-0000104169-OperatingIncomeLoss-USD-CY2011-0000104169-14-000019-ab2642b5` | `RB1AFF6F2F5` | `RB1AFF6F2F5` | `us-gaap:OperatingIncomeLoss` | 26491000000.0 |
| denominator | `SEC-0000104169-Revenues-USD-CY2011-0000104169-14-000019-50faff09` | `R8C100B55A6` | `R8C100B55A6` | `us-gaap:Revenues` | 446509000000.0 |

### CT_0010
Using only the ClinicalTrials.gov records supplied in the context, subtract the enrollment count of trial NCT03800927 from the enrollment count of trial NCT03656445. Report the difference as an integer number of participants.

| role | canonical record id | display id | equivalent display ids | field | value |
|---|---|---|---|---|---|
| minuend | `CT-NCT03656445-enrollment-count-535dc578` | `R584E60CDF3` | `R584E60CDF3` | `enrollment.count` | 180.0 |
| subtrahend | `CT-NCT03800927-enrollment-count-5f640681` | `RF6704DB3B7` | `RF6704DB3B7` | `enrollment.count` | 100.0 |

### FDA_0010
Using only the Drugs@FDA records supplied in the context, how many distinct product entries are listed under FDA application ANDA205695 (sponsor: ANBISON LAB)? Count the products belonging to that application number only, and answer with an integer.

| role | canonical record id | display id | equivalent display ids | field | value |
|---|---|---|---|---|---|
| product_0 | `FDA-ANDA205695-001-product-dosage-form-4f3d7427` | `R2CEE60A0A9` | `R2CEE60A0A9` | `product.dosage_form` | TABLET, CHEWABLE |
| product_1 | `FDA-ANDA205695-002-product-dosage-form-75631b38` | `R8D2B7063AB` | `R8D2B7063AB` | `product.dosage_form` | TABLET, CHEWABLE |

### FRED_0010
Using only the FRED records supplied in the context, calculate the percentage change in FRED series WGS10YR ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, weekly frequency between the observation dated 2026-07-24 and the observation dated 2026-07-31. Use both values from the most recent vintage, apply ((value_2026-07-31 - value_2026-07-24) / value_2026-07-24) * 100, and round to two decimal places.

| role | canonical record id | display id | equivalent display ids | field | value |
|---|---|---|---|---|---|
| current | `FRED-WGS10YR-2026-07-31-latest-b0603637` | `RA2C8DBEEC0` | `RA2C8DBEEC0` | `WGS10YR` | 4.67 |
| previous | `FRED-WGS10YR-2026-07-24-latest-4def8320` | `RE9533D1E1E` | `RE9533D1E1E` | `WGS10YR` | 4.66 |

## Smoke-count resolution
- expected four-family instances: `24`
- actual four-family instances: `24`
- previous `204`: 204 was the total instance count of the broader audit_llama32_smoke dataset: 34 families x 6 context lengths. It was not the count for the four named audited families.
- dataset duplication bug: `False`

## CT_0017
- original type: `TEMPORAL_VERSION`
- final type: `ENTITY_UNIT_BINDING`
- template: `CT_DATE_FIELD_SELECTION`
- question: Using only the ClinicalTrials.gov records supplied in the context, what is the PRIMARY COMPLETION DATE of trial NCT02746185 ("Cancer Associated Thrombosis, a Pilot Treatment Study Using Rivaroxaban")? Answer in YYYY-MM-DD form.
- reason: CT_DATE_FIELD_SELECTION selects one sibling date field on a single trial. It does not require distinguishing original/amended versions, vintages, or multiple time-indexed states of the same target field, so it is ENTITY_UNIT_BINDING rather than TEMPORAL_VERSION.

## Temporal-version review
- original TEMPORAL_VERSION families inspected: `15`
- reclassified: `4`
- before counts: `{'DIRECT_RETRIEVAL': 20, 'ENTITY_UNIT_BINDING': 15, 'RETRIEVAL_CALCULATION': 30, 'TEMPORAL_VERSION': 15, 'UNANSWERABLE': 20}`
- after counts: `{'DIRECT_RETRIEVAL': 20, 'ENTITY_UNIT_BINDING': 19, 'RETRIEVAL_CALCULATION': 30, 'UNANSWERABLE': 20, 'TEMPORAL_VERSION': 11}`

## Validation
- checks passed: `30/30`
- critical failures: `0`
- warnings: `0`
