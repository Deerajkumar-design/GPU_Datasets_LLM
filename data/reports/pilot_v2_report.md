# Pilot report — `pilot_v2`

_Generated 2026-08-09T19:04:41Z · config `config/pilot_v2.yaml` · config hash `d9debd500e9ee09b` · seed `20240817` · git `7c848cf04dc3`_

> **Scope.** This phase generates and validates the dataset only. No LLM has been run against it, no hallucination scoring has been performed, and no statistical analysis or research conclusions are presented here.

## 1. Verdict

**Status: READY for scale-up review**

- Validation: 25/25 checks passed, 0 critical failures, 0 warnings.
- 24 question families → 144 context instances.
- 0 context variants could not be built from authentic records and were recorded as unavailable rather than padded.

## 2. Source retrieval

| domain | source | status | requests | payloads | raw records | normalized | errors | retrieved at |
|---|---|---|---|---|---|---|---|---|
| CLINICAL_TRIALS | CLINICALTRIALS_GOV_V2 | ok | 0 | 24 | 2400 | 74683 | 0 | 2026-08-09T04:32:06Z |
| FDA | OPENFDA_DRUGSFDA | ok | 0 | 15 | 960 | 25737 | 0 | 2026-08-09T04:32:06Z |
| SEC | SEC_EDGAR_XBRL_COMPANYFACTS | ok | 0 | 8 | 259528 | 38764 | 0 | 2026-08-09T04:32:06Z |
| WORLD_BANK | WORLD_BANK_INDICATORS_V2 | ok | 65 | 53 | 3498 | 0 | 27 | 2026-08-09T04:33:16Z |

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


| question type | families | share |
|---|---|---|
| DIRECT_RETRIEVAL | 6 | 25% |
| ENTITY_UNIT_BINDING | 3 | 12% |
| RETRIEVAL_CALCULATION | 6 | 25% |
| TEMPORAL_VERSION | 3 | 12% |
| UNANSWERABLE | 6 | 25% |


Answerable: **18** · Unanswerable: **6**

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

</details>

## 4. Context instances

Tokenizer: `tiktoken:cl100k_base` (tiktoken==0.13.0)

| nominal | instances | min tokens | median tokens | max tokens | min fill | median fill |
|---|---|---|---|---|---|---|
| 4K | 24 | 3958.0 | 4030.0 | 4066.0 | 0.9663 | 0.9839 |
| 8K | 24 | 8032.0 | 8084.0 | 8123.0 | 0.9805 | 0.9868 |
| 16K | 24 | 16155.0 | 16209.0 | 16268.0 | 0.986 | 0.9893 |
| 32K | 24 | 32382.0 | 32444.0 | 32542.0 | 0.9882 | 0.9901 |
| 64K | 24 | 64792.0 | 64898.0 | 65055.0 | 0.9886 | 0.9903 |
| 128K | 24 | 129628.0 | 129877.0 | 130146.0 | 0.989 | 0.9909 |


**Target-evidence position** (target 0.5 ± 0.05): n=108, min=0.4863, median=0.5002, max=0.5163, mean=0.5007

## 5. Distractors

| distractor type | records placed | share | definition |
|---|---|---|---|
| OTHER_SAME_DOMAIN | 28210 | 51.7% | A real record from the same primary source with no closer relationship to the target. |
| WRONG_ENTITY | 15707 | 28.8% | Same metric and period, a different entity (other company, country, trial, product). |
| WRONG_FIELD | 5695 | 10.4% | Same entity, a different field/concept. |
| WRONG_PERIOD | 3657 | 6.7% | Same entity and metric, a different period (other year, quarter, or instant). |
| NEAR_MATCH_VALUE | 1222 | 2.2% | Numerically within 5% of a target value while being a different fact -- a plausible-looking wrong answer. |
| WRONG_VERSION | 58 | 0.1% | Same entity, metric, period and unit, but a different filing/revision/submission version. |


## 6. Unavailable context variants

None — every configured length was built from authentic same-domain records.

## 7. Validation results

| id | check | severity | result | checked | failed |
|---|---|---|---|---|---|
| A | unique IDs (families and instances) | CRITICAL | PASS | 168 | 0 |
| B | no duplicate question families | CRITICAL | PASS | 24 | 0 |
| C | valid source provenance | CRITICAL | PASS | 24 | 0 |
| D | deterministic gold-answer recomputation | CRITICAL | PASS | 24 | 0 |
| E | gold evidence present in every answerable context | CRITICAL | PASS | 144 | 0 |
| F | gold evidence absent for unanswerable families | CRITICAL | PASS | 144 | 0 |
| G | identical question across context-length variants | CRITICAL | PASS | 24 | 0 |
| H | identical gold answer across context-length variants | CRITICAL | PASS | 24 | 0 |
| I | identical gold evidence across context-length variants | CRITICAL | PASS | 24 | 0 |
| J | nested-context lineage | CRITICAL | PASS | 24 | 0 |
| K | token-length compliance | CRITICAL | PASS | 144 | 0 |
| L | target-position compliance | CRITICAL | PASS | 144 | 0 |
| M | record-boundary integrity | CRITICAL | PASS | 144 | 0 |
| N | unit consistency in calculations | CRITICAL | PASS | 6 | 0 |
| O | answer-type / schema validity | CRITICAL | PASS | 24 | 0 |
| P | distractor metadata completeness | CRITICAL | PASS | 144 | 0 |
| Q | no NaN or invalid numeric answers | CRITICAL | PASS | 24 | 0 |
| R | no context truncation through target evidence | CRITICAL | PASS | 144 | 0 |
| S | no answer leakage for unanswerable families | CRITICAL | PASS | 144 | 0 |
| T | calculation operands recomputable | CRITICAL | PASS | 6 | 0 |
| U | all five question types represented | CRITICAL | PASS | 5 | 0 |
| V | no duplicate answer sources in answerable contexts | CRITICAL | PASS | 144 | 0 |
| W | opaque display ID mapping integrity | CRITICAL | PASS | 144 | 0 |
| X | evidence-equivalence consistency | CRITICAL | PASS | 144 | 0 |
| Y | distractor taxonomy semantic constraints | CRITICAL | PASS | 144 | 0 |


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
| `CT_0004_4K` | 4K | 4031 | 0.984 | 43 | 0.5037 | 1943–2118 | `ef9c1712707d2da0` |
| `CT_0004_8K` | 8K | 8102 | 0.989 | 83 | 0.4991 | 3956–4131 | `d6313db504e8298f` |
| `CT_0004_16K` | 16K | 16213 | 0.990 | 165 | 0.4978 | 7984–8159 | `254cf4b8fa219098` |
| `CT_0004_32K` | 32K | 32422 | 0.989 | 315 | 0.5011 | 16160–16335 | `455473939c7a432d` |
| `CT_0004_64K` | 64K | 64895 | 0.990 | 604 | 0.5007 | 32403–32578 | `487c232f688d5ea4` |
| `CT_0004_128K` | 128K | 129873 | 0.991 | 1201 | 0.4998 | 64820–64995 | `1c7a81990602f58b` |


### `FDA_0007` — FDA / UNANSWERABLE

*Template:* `FDA_UNANSWERABLE_ATTRIBUTE_ABSENT`

**Question.** Using only the Drugs@FDA records supplied in the context, what is the route of administration for product number 001 under FDA application ANDA215255 (brand name "CANAGLIFLOZIN AND METFORMIN HYDROCHLORIDE")? If the supplied records do not list this attribute for this specific product, state that the evidence is insufficient rather than inferring it from another product or from general knowledge of the drug.

**Gold outcome.** `INSUFFICIENT_EVIDENCE` — ATTRIBUTE_NOT_LISTED_FOR_PRODUCT

> The Drugs@FDA record for product ANDA215255/001 omits product.route; openFDA returns no such field for this product. Verified by exhaustive scan of the normalized pool: zero records match entity_id=ANDA215255/001 and concept=product.route. Other products in the pool do carry this attribute, so the omission is a property of this product.

**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `FDA_0007_4K` | 4K | 4019 | 0.981 | 43 | n/a | n/a | `13a33f40444834e1` |
| `FDA_0007_8K` | 8K | 8042 | 0.982 | 86 | n/a | n/a | `bce41904082457f1` |
| `FDA_0007_16K` | 16K | 16166 | 0.987 | 171 | n/a | n/a | `b74b0e6a48ac3c2a` |
| `FDA_0007_32K` | 32K | 32401 | 0.989 | 342 | n/a | n/a | `551f9ec04a493593` |
| `FDA_0007_64K` | 64K | 64849 | 0.990 | 687 | n/a | n/a | `47470e28ab3f335f` |
| `FDA_0007_128K` | 128K | 129651 | 0.989 | 1369 | n/a | n/a | `99171dd453ae29fe` |


### `SEC_0006` — SEC / TEMPORAL_VERSION

*Template:* `SEC_QUARTER_VS_ANNUAL_FRAME`

**Question.** Using only the SEC XBRL company-facts records supplied in the context, what did MICROSOFT CORPORATION (CIK 0000789019) report for us-gaap:NetCashProvidedByUsedInFinancingActivities for the single quarterly XBRL frame CY2021Q3, in USD? Report the quarterly figure exactly.

**Gold answer.** `-16,276,000,000` (normalized `-16276000000.0`, type NUMERIC, unit USD, tolerance ±0.5)

**Gold evidence.**

| role | record id | entity | field | period | value | unit |
|---|---|---|---|---|---|---|
| target_value | `SEC-0000789019-NetCashProvidedByUsedInF-USD-CY2021Q3-0001564590-22-035087-306cc7fc` | MICROSOFT CORPORATION [0000789019] | Net Cash Provided by (Used in) Financing Activities [us-gaap:NetCashProvidedByUsedInFinancingActivities] | CY2021Q3 | -16276000000.0 | USD |


**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `SEC_0006_4K` | 4K | 3960 | 0.967 | 28 | 0.5163 | 1973–2116 | `8a0517fa6ce57545` |
| `SEC_0006_8K` | 8K | 8097 | 0.988 | 57 | 0.4991 | 3970–4113 | `d9b7cd9f458f534e` |
| `SEC_0006_16K` | 16K | 16268 | 0.993 | 114 | 0.4973 | 8019–8162 | `4f7fea43410b44e0` |
| `SEC_0006_32K` | 32K | 32542 | 0.993 | 227 | 0.5004 | 16214–16357 | `1bdd0e5f06f22a6b` |
| `SEC_0006_64K` | 64K | 65007 | 0.992 | 454 | 0.4997 | 32412–32555 | `ce5ccee61c8ffa7c` |
| `SEC_0006_128K` | 128K | 130092 | 0.993 | 914 | 0.4999 | 64960–65103 | `ee810a592ff4d69f` |


### `CT_0003` — CLINICAL_TRIALS / ENTITY_UNIT_BINDING

*Template:* `CT_ARM_TYPE_BINDING`

**Question.** Using only the ClinicalTrials.gov records supplied in the context, what is the arm-group TYPE of the arm labelled "Control" in trial NCT01340300 ("Exercise and Metformin in Colorectal and Breast Cancer Survivors")? Answer with the ClinicalTrials.gov arm type value (for example EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, SHAM_COMPARATOR, NO_INTERVENTION or OTHER).

**Gold answer.** `ACTIVE_COMPARATOR` (normalized `ACTIVE_COMPARATOR`, type CATEGORICAL)

**Gold evidence.**

| role | record id | entity | field | period | value | unit |
|---|---|---|---|---|---|---|
| target_value | `CT-NCT01340300-arm-type-Control-3-fc797906` | Exercise and Metformin in Colorectal and Breast Cancer Survivors [NCT01340300] | Arm group type: Control [arm.type] |  | ACTIVE_COMPARATOR |  |


**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `CT_0003_4K` | 4K | 4040 | 0.986 | 40 | 0.5021 | 1982–2075 | `c1dffcc7bee47f30` |
| `CT_0003_8K` | 8K | 8073 | 0.986 | 78 | 0.5045 | 4026–4119 | `2e18a3c2fd8f9103` |
| `CT_0003_16K` | 16K | 16207 | 0.989 | 148 | 0.4985 | 8032–8125 | `3388bdbe78660ce2` |
| `CT_0003_32K` | 32K | 32455 | 0.990 | 286 | 0.5018 | 16238–16331 | `7dfd4bb0ab956005` |
| `CT_0003_64K` | 64K | 64906 | 0.990 | 567 | 0.5006 | 32447–32540 | `69f16938963658ee` |
| `CT_0003_128K` | 128K | 129880 | 0.991 | 1138 | 0.5001 | 64901–64994 | `54411ce579917d15` |


## 9. Reproducibility

| field | value |
|---|---|
| schema version | 1.1.0 |
| config hash | `d9debd500e9ee09b` |
| seed | 20240817 |
| git commit | `7c848cf04dc3d16ee413ef3819f09f44ca9ad046` |
| tokenizer | `tiktoken:cl100k_base` |
| context lengths | 4K, 8K, 16K, 32K, 64K, 128K |
| target position | 0.5 ± 0.05 |
| min fill ratio | 0.95 |


Raw payloads under `data/raw/` are content-addressed by request URL, so re-running `fetch` is idempotent and the pilot can be regenerated byte-for-byte from the cached layer even after the live APIs change. Hashes of all outputs are in `data/manifests/pilot_v2_manifest.json`.

