# Pilot report — `pilot`

_Generated 2026-08-09T04:38:22Z · config `config/pilot.yaml` · config hash `87a7631a5f655544` · seed `20240817` · git `9cedbeba8982`_

> **Scope.** This phase generates and validates the dataset only. No LLM has been run against it, no hallucination scoring has been performed, and no statistical analysis or research conclusions are presented here.

## 1. Verdict

**Status: READY for scale-up review**

- Validation: 22/22 checks passed, 0 critical failures, 0 warnings.
- 32 question families → 192 context instances.
- 0 context variants could not be built from authentic records and were recorded as unavailable rather than padded.

## 2. Source retrieval

| domain | source | status | requests | payloads | raw records | normalized | errors | retrieved at |
|---|---|---|---|---|---|---|---|---|
| CLINICAL_TRIALS | CLINICALTRIALS_GOV_V2 | ok | 0 | 24 | 2400 | 74683 | 0 | 2026-08-09T04:32:06Z |
| FDA | OPENFDA_DRUGSFDA | ok | 0 | 15 | 960 | 25737 | 0 | 2026-08-09T04:32:06Z |
| SEC | SEC_EDGAR_XBRL_COMPANYFACTS | ok | 0 | 8 | 259528 | 38764 | 0 | 2026-08-09T04:32:06Z |
| WORLD_BANK | WORLD_BANK_INDICATORS_V2 | ok | 65 | 53 | 3498 | 4630 | 27 | 2026-08-09T04:33:16Z |

### Source / API limitations encountered

Request errors below are from *this* run. Where a domain still shows full normalized coverage despite errors, the missing responses were already present in `data/raw/` from an earlier successful retrieval — raw payloads are content-addressed and never discarded, which is precisely what makes the pilot reproducible across an unreliable upstream. No data was substituted or invented to cover a failed request.

- **WORLD_BANK · REQUEST_ERROR** — NY.GDP.MKTP.KD [NLD..NLD]: [world_bank] GET https://api.worldbank.org/v2/country/NLD/indicator/NY.GDP.MKTP.KD failed after 2 attempts: HTTP 502 from https://api.worldbank.org/v2/country/NLD/indicator/NY.GDP.MKTP.KD?format=json&per_page=500
- **WORLD_BANK · REQUEST_ERROR** — NY.GDP.MKTP.KD [SAU..SAU]: [world_bank] GET https://api.worldbank.org/v2/country/SAU/indicator/NY.GDP.MKTP.KD failed after 2 attempts: HTTPSConnectionPool(host='api.worldbank.org', port=443): Read timed out. (read timeout=4.0)
- **WORLD_BANK · REQUEST_ERROR** — NY.GDP.MKTP.KD [CHE..CHE]: [world_bank] GET https://api.worldbank.org/v2/country/CHE/indicator/NY.GDP.MKTP.KD failed after 2 attempts: HTTP 502 from https://api.worldbank.org/v2/country/CHE/indicator/NY.GDP.MKTP.KD?format=json&per_page=500
- **WORLD_BANK · REQUEST_ERROR** — NY.GDP.MKTP.KD [POL..POL]: [world_bank] GET https://api.worldbank.org/v2/country/POL/indicator/NY.GDP.MKTP.KD failed after 2 attempts: HTTP 502 from https://api.worldbank.org/v2/country/POL/indicator/NY.GDP.MKTP.KD?format=json&per_page=500
- **WORLD_BANK · REQUEST_ERROR** — NY.GDP.MKTP.KD [SWE..SWE]: [world_bank] GET https://api.worldbank.org/v2/country/SWE/indicator/NY.GDP.MKTP.KD failed after 2 attempts: HTTPSConnectionPool(host='api.worldbank.org', port=443): Read timed out. (read timeout=4.0)
- **WORLD_BANK · REQUEST_ERROR** — NY.GDP.PCAP.CD [FRA..FRA]: [world_bank] GET https://api.worldbank.org/v2/country/FRA/indicator/NY.GDP.PCAP.CD failed after 2 attempts: HTTPSConnectionPool(host='api.worldbank.org', port=443): Read timed out. (read timeout=4.0)
- **WORLD_BANK · REQUEST_ERROR** — NY.GDP.PCAP.CD [BRA..BRA]: [world_bank] GET https://api.worldbank.org/v2/country/BRA/indicator/NY.GDP.PCAP.CD failed after 2 attempts: HTTP 502 from https://api.worldbank.org/v2/country/BRA/indicator/NY.GDP.PCAP.CD?format=json&per_page=500
- **WORLD_BANK · REQUEST_ERROR** — NY.GDP.PCAP.CD [ITA..ITA]: [world_bank] GET https://api.worldbank.org/v2/country/ITA/indicator/NY.GDP.PCAP.CD failed after 2 attempts: HTTP 502 from https://api.worldbank.org/v2/country/ITA/indicator/NY.GDP.PCAP.CD?format=json&per_page=500
- **WORLD_BANK · REQUEST_ERROR** — NY.GDP.PCAP.CD [CAN..CAN]: [world_bank] GET https://api.worldbank.org/v2/country/CAN/indicator/NY.GDP.PCAP.CD failed after 2 attempts: HTTP 502 from https://api.worldbank.org/v2/country/CAN/indicator/NY.GDP.PCAP.CD?format=json&per_page=500
- **WORLD_BANK · REQUEST_ERROR** — NY.GDP.PCAP.CD [KOR..KOR]: [world_bank] GET https://api.worldbank.org/v2/country/KOR/indicator/NY.GDP.PCAP.CD failed after 2 attempts: HTTP 502 from https://api.worldbank.org/v2/country/KOR/indicator/NY.GDP.PCAP.CD?format=json&per_page=500

## 3. Question families

| domain | configured target | generated |
|---|---|---|
| CLINICAL_TRIALS | 8 | 8 |
| FDA | 8 | 8 |
| SEC | 8 | 8 |
| WORLD_BANK | 8 | 8 |


| question type | families | share |
|---|---|---|
| DIRECT_RETRIEVAL | 8 | 25% |
| ENTITY_UNIT_BINDING | 4 | 12% |
| RETRIEVAL_CALCULATION | 8 | 25% |
| TEMPORAL_VERSION | 4 | 12% |
| UNANSWERABLE | 8 | 25% |


Answerable: **24** · Unanswerable: **8**

<details><summary>Families by template</summary>

| template | families |
|---|---|
| CT_ARM_TYPE_BINDING | 1 |
| CT_DATE_FIELD_SELECTION | 1 |
| CT_DIRECT_ENROLLMENT | 2 |
| CT_ENROLLMENT_DIFFERENCE | 1 |
| CT_STUDY_DURATION_DAYS | 1 |
| CT_UNANSWERABLE_FIELD_ABSENT | 2 |
| FDA_DIRECT_PRODUCT_ATTRIBUTE | 2 |
| FDA_ORIGINAL_VS_SUPPLEMENT | 1 |
| FDA_PRODUCT_COUNT | 1 |
| FDA_STRENGTH_PRODUCT_BINDING | 1 |
| FDA_STRENGTH_RATIO | 1 |
| FDA_UNANSWERABLE_ATTRIBUTE_ABSENT | 2 |
| SEC_DIRECT_XBRL_FACT | 2 |
| SEC_ENTITY_BINDING | 1 |
| SEC_OPERATING_MARGIN | 1 |
| SEC_QUARTER_VS_ANNUAL_FRAME | 1 |
| SEC_UNANSWERABLE_CONCEPT_OR_PERIOD_ABSENT | 2 |
| SEC_YOY_GROWTH_PERCENT | 1 |
| WB_DIRECT_INDICATOR_VALUE | 2 |
| WB_INDICATOR_GROWTH_PERCENT | 2 |
| WB_TEMPORAL_MAX_YEAR | 1 |
| WB_UNANSWERABLE_NO_OBSERVATION | 2 |
| WB_UNIT_BASIS_BINDING | 1 |

</details>

## 4. Context instances

Tokenizer: `tiktoken:cl100k_base` (tiktoken==0.13.0)

| nominal | instances | min tokens | median tokens | max tokens | min fill | median fill |
|---|---|---|---|---|---|---|
| 4K | 32 | 3936.0 | 4015.0 | 4068.0 | 0.9609 | 0.9802 |
| 8K | 32 | 8010.0 | 8093.0 | 8144.0 | 0.9778 | 0.9879 |
| 16K | 32 | 16131.0 | 16209.0 | 16290.0 | 0.9846 | 0.9893 |
| 32K | 32 | 32332.0 | 32445.0 | 32581.0 | 0.9867 | 0.9901 |
| 64K | 32 | 64740.0 | 64962.0 | 65162.0 | 0.9879 | 0.9912 |
| 128K | 32 | 129599.0 | 129910.0 | 130311.0 | 0.9888 | 0.9911 |


**Target-evidence position** (target 0.5 ± 0.05): n=144, min=0.4799, median=0.5, max=0.5131, mean=0.5

## 5. Distractors

| distractor type | records placed | share | definition |
|---|---|---|---|
| OTHER_SAME_DOMAIN | 38500 | 54.9% | A real record from the same primary source with no closer relationship to the target. |
| WRONG_ENTITY | 15546 | 22.2% | Same metric and period, a different entity (other company, country, trial, product). |
| WRONG_FIELD | 8533 | 12.2% | Same entity, a different field/concept. |
| WRONG_PERIOD | 4776 | 6.8% | Same entity and metric, a different period (other year, quarter, or instant). |
| NEAR_MATCH_VALUE | 2689 | 3.8% | Numerically within 5% of a target value while being a different fact -- a plausible-looking wrong answer. |
| WRONG_VERSION | 57 | 0.1% | Same entity, metric, period and unit, but a different filing/revision/submission version. |
| WRONG_UNIT | 48 | 0.1% | Same entity, metric and period, reported in a different unit or measurement basis. |


## 6. Unavailable context variants

None — every configured length was built from authentic same-domain records.

## 7. Validation results

| id | check | severity | result | checked | failed |
|---|---|---|---|---|---|
| A | unique IDs (families and instances) | CRITICAL | PASS | 224 | 0 |
| B | no duplicate question families | CRITICAL | PASS | 32 | 0 |
| C | valid source provenance | CRITICAL | PASS | 32 | 0 |
| D | deterministic gold-answer recomputation | CRITICAL | PASS | 32 | 0 |
| E | gold evidence present in every answerable context | CRITICAL | PASS | 192 | 0 |
| F | gold evidence absent for unanswerable families | CRITICAL | PASS | 192 | 0 |
| G | identical question across context-length variants | CRITICAL | PASS | 32 | 0 |
| H | identical gold answer across context-length variants | CRITICAL | PASS | 32 | 0 |
| I | identical gold evidence across context-length variants | CRITICAL | PASS | 32 | 0 |
| J | nested-context lineage | CRITICAL | PASS | 32 | 0 |
| K | token-length compliance | CRITICAL | PASS | 192 | 0 |
| L | target-position compliance | CRITICAL | PASS | 192 | 0 |
| M | record-boundary integrity | CRITICAL | PASS | 192 | 0 |
| N | unit consistency in calculations | CRITICAL | PASS | 8 | 0 |
| O | answer-type / schema validity | CRITICAL | PASS | 32 | 0 |
| P | distractor metadata completeness | CRITICAL | PASS | 192 | 0 |
| Q | no NaN or invalid numeric answers | CRITICAL | PASS | 32 | 0 |
| R | no context truncation through target evidence | CRITICAL | PASS | 192 | 0 |
| S | no answer leakage for unanswerable families | CRITICAL | PASS | 192 | 0 |
| T | calculation operands recomputable | CRITICAL | PASS | 8 | 0 |
| U | all five question types represented | CRITICAL | PASS | 5 | 0 |
| V | no duplicate answer sources in answerable contexts | CRITICAL | PASS | 192 | 0 |


No check produced failures.

Key derived counts:

- Duplicate family IDs / instance IDs / question texts: 0
- Gold-recomputation failures (check D): 0
- Unanswerable leakage failures (check S): 0
- Duplicate-answer-source failures (check V): 0

## 8. Representative question families

_Context strings are deliberately not reproduced here; only their measured properties are._

### `CT_0004` — CLINICAL_TRIALS / RETRIEVAL_CALCULATION

*Template:* `CT_ENROLLMENT_DIFFERENCE`

**Question.** Using only the ClinicalTrials.gov records supplied in the context, subtract the enrollment count of trial NCT03800927 from the enrollment count of trial NCT03656445. Report the difference as an integer number of participants.

**Gold answer.** `80` (normalized `80.0`, type INTEGER, unit participants, tolerance ±0.0)

**Gold evidence.**

| role | record id | entity | field | period | value | unit |
|---|---|---|---|---|---|---|
| minuend | `CT-NCT03656445-enrollment-count-535dc578` | Tranexamic Acid in Total Knee Replacement [NCT03656445] | Enrollment (participants) [enrollment.count] |  | 180.0 | participants |
| subtrahend | `CT-NCT03800927-enrollment-count-5f640681` | Long-Duration Ultrasound for Knee Osteoarthritis [NCT03800927] | Enrollment (participants) [enrollment.count] |  | 100.0 | participants |


**Calculation.** `difference`: `minuend - subtrahend` → raw `80.0` → rounded `80.0` (0 dp)

| role | record id | value used |
|---|---|---|
| minuend | `CT-NCT03656445-enrollment-count-535dc578` | 180.0 |
| subtrahend | `CT-NCT03800927-enrollment-count-5f640681` | 100.0 |


**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `CT_0004_4K` | 4K | 4057 | 0.991 | 39 | 0.5057 | 1957–2146 | `856ae1d4bd39ccc4` |
| `CT_0004_8K` | 8K | 8097 | 0.988 | 76 | 0.5053 | 3997–4186 | `e1898b79f13707b7` |
| `CT_0004_16K` | 16K | 16236 | 0.991 | 150 | 0.5000 | 8023–8212 | `50d406b9a3345f29` |
| `CT_0004_32K` | 32K | 32453 | 0.990 | 290 | 0.4989 | 16095–16284 | `14073f298d34eafd` |
| `CT_0004_64K` | 64K | 64961 | 0.991 | 560 | 0.4996 | 32362–32551 | `b3a5a9372ce1af7c` |
| `CT_0004_128K` | 128K | 129933 | 0.991 | 1100 | 0.5002 | 64902–65091 | `f6e4840784994ea9` |


### `FDA_0007` — FDA / UNANSWERABLE

*Template:* `FDA_UNANSWERABLE_ATTRIBUTE_ABSENT`

**Question.** Using only the Drugs@FDA records supplied in the context, what is the route of administration for product number 001 under FDA application ANDA215255 (brand name "CANAGLIFLOZIN AND METFORMIN HYDROCHLORIDE")? If the supplied records do not list this attribute for this specific product, state that the evidence is insufficient rather than inferring it from another product or from general knowledge of the drug.

**Gold outcome.** `INSUFFICIENT_EVIDENCE` — ATTRIBUTE_NOT_LISTED_FOR_PRODUCT

> The Drugs@FDA record for product ANDA215255/001 omits product.route; openFDA returns no such field for this product. Verified by exhaustive scan of the normalized pool: zero records match entity_id=ANDA215255/001 and concept=product.route. Other products in the pool do carry this attribute, so the omission is a property of this product.

**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `FDA_0007_4K` | 4K | 4049 | 0.989 | 39 | n/a | n/a | `36d4cf0e8385c38b` |
| `FDA_0007_8K` | 8K | 8114 | 0.991 | 78 | n/a | n/a | `e85ed13ee52d41ef` |
| `FDA_0007_16K` | 16K | 16214 | 0.990 | 153 | n/a | n/a | `333e7a12b5c2dbdd` |
| `FDA_0007_32K` | 32K | 32447 | 0.990 | 305 | n/a | n/a | `257db2236cc3036e` |
| `FDA_0007_64K` | 64K | 64883 | 0.990 | 611 | n/a | n/a | `d0f91e4f0adf0ab9` |
| `FDA_0007_128K` | 128K | 129849 | 0.991 | 1220 | n/a | n/a | `731a8e9478169cd9` |


### `SEC_0006` — SEC / TEMPORAL_VERSION

*Template:* `SEC_QUARTER_VS_ANNUAL_FRAME`

**Question.** Using only the SEC XBRL company-facts records supplied in the context, what did MICROSOFT CORPORATION (CIK 0000789019) report for us-gaap:NetCashProvidedByUsedInFinancingActivities for the single quarterly XBRL frame CY2021Q3, in USD? Report the quarterly figure only — the context also contains the full-year frame CY2021 for the same concept, which is not the answer.

**Gold answer.** `-16,276,000,000` (normalized `-16276000000.0`, type NUMERIC, unit USD, tolerance ±0.5)

**Gold evidence.**

| role | record id | entity | field | period | value | unit |
|---|---|---|---|---|---|---|
| target_value | `SEC-0000789019-NetCashProvidedByUsedInF-USD-CY2021Q3-0001564590-22-035087-306cc7fc` | MICROSOFT CORPORATION [0000789019] | Net Cash Provided by (Used in) Financing Activities [us-gaap:NetCashProvidedByUsedInFinancingActivities] | CY2021Q3 | -16276000000.0 | USD |


**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `SEC_0006_4K` | 4K | 3984 | 0.973 | 23 | 0.5021 | 1914–2087 | `c7a79fc08dee1596` |
| `SEC_0006_8K` | 8K | 8029 | 0.980 | 46 | 0.4895 | 3844–4017 | `f29c58f7af0a5b0b` |
| `SEC_0006_16K` | 16K | 16223 | 0.990 | 92 | 0.5040 | 8090–8263 | `3536773587c7e5fd` |
| `SEC_0006_32K` | 32K | 32549 | 0.993 | 184 | 0.4982 | 16131–16304 | `66db086a44ed3914` |
| `SEC_0006_64K` | 64K | 65162 | 0.994 | 368 | 0.5004 | 32518–32691 | `6baa0ef87f5051ae` |
| `SEC_0006_128K` | 128K | 130262 | 0.994 | 738 | 0.5004 | 65099–65272 | `75b86f099adffc6d` |


### `WB_0003` — WORLD_BANK / ENTITY_UNIT_BINDING

*Template:* `WB_UNIT_BASIS_BINDING`

**Question.** Using only the World Bank Indicators records supplied in the context, report the value of "GDP (constant 2015 US$)" — indicator code NY.GDP.MKTP.KD, unit constant 2015 US$ — for Switzerland (CHE) in 2001. Note that the context also contains "GDP (current US$)" (indicator code NY.GDP.MKTP.CD) for the same country and year; that is a different measure (constant 2015 US$ versus current US$) and is not the answer.

**Gold answer.** `546,910,823,425.202` (normalized `546910823425.202`, type NUMERIC, unit constant 2015 US$, tolerance ±0.0005)

**Gold evidence.**

| role | record id | entity | field | period | value | unit |
|---|---|---|---|---|---|---|
| target_value | `WB-CHE-NY-GDP-MKTP-KD-2001-dccde9bb` | Switzerland [CHE] | GDP (constant 2015 US$) [NY.GDP.MKTP.KD] | 2001 | 546910823425.202 | constant 2015 US$ |


**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `WB_0003_4K` | 4K | 3971 | 0.970 | 44 | 0.5112 | 1984–2076 | `fab23191ef7f0941` |
| `WB_0003_8K` | 8K | 8072 | 0.985 | 89 | 0.5002 | 3992–4084 | `decb922ff7a0e202` |
| `WB_0003_16K` | 16K | 16201 | 0.989 | 179 | 0.4994 | 8045–8137 | `87943daeb9a725a9` |
| `WB_0003_32K` | 32K | 32354 | 0.987 | 359 | 0.4992 | 16105–16197 | `71ded6f6521cb21c` |
| `WB_0003_64K` | 64K | 64762 | 0.988 | 717 | 0.5004 | 32362–32454 | `7d45ca43510064f6` |
| `WB_0003_128K` | 128K | 129640 | 0.989 | 1430 | 0.4998 | 64752–64844 | `0ba29bdd63618cfb` |


## 9. Reproducibility

| field | value |
|---|---|
| schema version | 1.0.0 |
| config hash | `87a7631a5f655544` |
| seed | 20240817 |
| git commit | `9cedbeba89825f227fc63eb1e0e3f3f2361f7906` |
| tokenizer | `tiktoken:cl100k_base` |
| context lengths | 4K, 8K, 16K, 32K, 64K, 128K |
| target position | 0.5 ± 0.05 |
| min fill ratio | 0.95 |


Raw payloads under `data/raw/` are content-addressed by request URL, so re-running `fetch` is idempotent and the pilot can be regenerated byte-for-byte from the cached layer even after the live APIs change. Hashes of all outputs are in `data/manifests/pilot_manifest.json`.

