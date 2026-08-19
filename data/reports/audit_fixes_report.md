# Audit Fixes Report

Generated from old `data/pilot` / `data/fred_pilot` artifacts and corrected `data/pilot_v2` / `data/fred_pilot_v2` artifacts.

## Question Foil Leakage

Before:
- `SEC_0006`: 2 detected phrase(s): not the answer, context also contains
- `FDA_0003`: 3 detected phrase(s): not the answer, those are not, different strengths

After:
- families with detected leakage: 0
- `SEC_0006` question after: Using only the SEC XBRL company-facts records supplied in the context, what did MICROSOFT CORPORATION (CIK 0000789019) report for us-gaap:NetCashProvidedByUsedInFinancingActivities for the single quarterly XBRL frame CY2021Q3, in USD? Report the quarterly figure exactly.
- `FDA_0003` question after: Using only the Drugs@FDA records supplied in the context, what is the listed strength of OMEPRAZOLE in product number 003 under FDA application ANDA091352 (dosage form CAPSULE, DELAYED REL PELLETS, route ORAL)? Report the strength string exactly as recorded.
- `FRED_0007` question after: Using only the FRED records supplied in the context, calculate the percentage change in FRED series CPIAUCSL ("Consumer Price Index for All Urban Consumers: All Items in U.S. City Average"), measured in Index 1982-1984=100, seasonally adjusted, monthly frequency between the observation dated 2026-05-01 and the observation dated 2026-06-01. Use both values from the most recent vintage, apply ((value_2026-06-01 - value_2026-05-01) / value_2026-05-01) * 100, and round to two decimal places.
- `CT_0007` question after: Using only the ClinicalTrials.gov records supplied in the context, what is the date on which results were first posted for trial NCT02339493 ("Electronic Alerts for Stroke Prevention in Patients With Atrial Fibrillation or Atrial Flutter")? If the supplied records do not contain this field for this trial, state that the evidence is insufficient rather than inferring it from another date or another trial.

## Equivalent Evidence

Preserve source records; expose conservative evidence equivalence groups on families and instances. Version equality is required for version/vintage/submission-selection templates, but not for frame-vs-date duplicate representations where filing version is not the target dimension.

`SEC_0006` after 128K:
- group `EG7B0DB3413A` gold `SEC-0000789019-NetCashProvidedByUsedInF-USD-CY2021Q3-0001564590-22-035087-306cc7fc` accepts canonical IDs: `SEC-0000789019-NetCashProvidedByUsedInF-USD-2021-07-01-2021-09-30-0001564590-21-051992-6091605a`, `SEC-0000789019-NetCashProvidedByUsedInF-USD-CY2021Q3-0001564590-22-035087-306cc7fc`; display IDs: `RE00ECF2D69`, `R5B83575D92`

All canonical IDs in the group would be accepted by future evidence scoring through the group metadata.

## Distractor Taxonomy

| family | WRONG_UNIT before | WRONG_UNIT after | WRONG_SERIES_VARIANT before | WRONG_SERIES_VARIANT after | NEAR_MATCH_VALUE before | NEAR_MATCH_VALUE after | invalid NEAR before | invalid NEAR after |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `SEC_0006` | 0 | 0 | 0 | 0 | 132 | 143 | 0 | 0 |
| `FDA_0003` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `FRED_0007` | 11 | 0 | 0 | 11 | 0 | 0 | 0 | 0 |
| `CT_0007` | 0 | 0 | 0 | 0 | 18 | 0 | 18 | 0 |

`WRONG_SERIES_VARIANT` is the canonical category for same-unit measurement-basis or series-variant conflicts such as seasonal adjustment or frequency. `WRONG_UNIT` is reserved for genuinely different units.

## Record IDs

- `CLINICAL_TRIALS`: canonical `CT-NCT02339493-eligibility-minimum-age-115a2098` -> model-facing `R0772032232`
- `FDA`: canonical `FDA-ANDA075410-003-product-dosage-form-ec6caeab` -> model-facing `R81082A3D9C`
- `FRED`: canonical `FRED-NYUR-2008-08-01-latest-b08220ab` -> model-facing `R113E69B80D`
- `SEC`: canonical `SEC-0000200406-OperatingIncomeLoss-USD-2012-01-02-2012-04-01-0000200406-12-000081-ef62b079` -> model-facing `R7408A293B4`

## Regenerated Families

- `SEC_0006`: pilot -> pilot_v2; lengths [4096, 8192, 16384, 32768, 65536, 131072]
- `FDA_0003`: pilot -> pilot_v2; lengths [4096, 8192, 16384, 32768, 65536, 131072]
- `FRED_0007`: fred_pilot -> fred_pilot_v2; lengths [4096, 8192, 16384, 32768, 65536, 131072]
- `CT_0007`: pilot -> pilot_v2; lengths [4096, 8192, 16384, 32768, 65536, 131072]
