# Pilot report — `audit_llama32_smoke`

_Generated 2026-08-09T19:42:13Z · config `config/audit_llama32_smoke.yaml` · config hash `0f152493a03909c0` · seed `20240817` · git `7c848cf04dc3`_

> **Scope.** This phase generates and validates the dataset only. No LLM has been run against it, no hallucination scoring has been performed, and no statistical analysis or research conclusions are presented here.

## 1. Verdict

**Status: READY for scale-up review**

- Validation: 27/27 checks passed, 0 critical failures, 0 warnings.
- 34 question families → 204 context instances.
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
| FRED | 10 | 10 |
| SEC | 8 | 8 |


| question type | families | share |
|---|---|---|
| DIRECT_RETRIEVAL | 8 | 24% |
| ENTITY_UNIT_BINDING | 5 | 15% |
| RETRIEVAL_CALCULATION | 9 | 26% |
| TEMPORAL_VERSION | 4 | 12% |
| UNANSWERABLE | 8 | 24% |


Answerable: **26** · Unanswerable: **8**

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
| FRED_BASIS_BINDING | 2 |
| FRED_DIRECT_OBSERVATION | 2 |
| FRED_PERCENT_CHANGE | 2 |
| FRED_SERIES_SPREAD | 1 |
| FRED_UNANSWERABLE_NO_OBSERVATION | 2 |
| FRED_VINTAGE_SELECTION | 1 |
| SEC_DIRECT_XBRL_FACT | 2 |
| SEC_ENTITY_BINDING | 1 |
| SEC_OPERATING_MARGIN | 1 |
| SEC_QUARTER_VS_ANNUAL_FRAME | 1 |
| SEC_UNANSWERABLE_CONCEPT_OR_PERIOD_ABSENT | 2 |
| SEC_YOY_GROWTH_PERCENT | 1 |

</details>

## 4. Context instances

Tokenizer: `hf:meta-llama/Llama-3.2-3B-Instruct` (transformers==5.14.1; tokenizers==0.22.2)
Model: `meta-llama/Llama-3.2-3B-Instruct` · context limit `131072` · generation reserve `512` · prompt `llama_chat_v1` / `4e6a3c47baa301a0` · chat template `True`

| nominal | instances | min tokens | median tokens | max tokens | median rendered | max rendered | min margin | min fill | median fill |
|---|---|---|---|---|---|---|---|---|---|
| 4K | 34 | 3960.0 | 4013.0 | 4067.0 | 4276.0 | 4353.0 | 126207.0 | 0.9668 | 0.9797 |
| 8K | 34 | 8026.0 | 8079.0 | 8135.0 | 8336.0 | 8422.0 | 122138.0 | 0.9797 | 0.9862 |
| 16K | 34 | 16130.0 | 16181.0 | 16265.0 | 16451.0 | 16528.0 | 114032.0 | 0.9845 | 0.9876 |
| 32K | 34 | 32309.0 | 32408.0 | 32526.0 | 32671.0 | 32790.0 | 97770.0 | 0.986 | 0.989 |
| 64K | 34 | 64660.0 | 64851.0 | 65036.0 | 65097.0 | 65312.0 | 65248.0 | 0.9866 | 0.9895 |
| 128K | 34 | 129392.0 | 129740.0 | 130148.0 | 130006.0 | 130428.0 | 132.0 | 0.9872 | 0.9898 |


**Target-evidence position** (target 0.5 ± 0.05): n=156, min=0.4877, median=0.5001, max=0.5163, mean=0.5002

## 5. Distractors

| distractor type | records placed | share | definition |
|---|---|---|---|
| OTHER_SAME_DOMAIN | 41114 | 47.9% | A real record from the same primary source with no closer relationship to the target. |
| WRONG_ENTITY | 15880 | 18.5% | Same metric and period, a different entity (other company, country, trial, product). |
| WRONG_FIELD | 13738 | 16.0% | Same entity, a different field/concept. |
| WRONG_PERIOD | 12947 | 15.1% | Same entity and metric, a different period (other year, quarter, or instant). |
| NEAR_MATCH_VALUE | 1938 | 2.3% | Numerically within 5% of a target value while being a different fact -- a plausible-looking wrong answer. |
| WRONG_VERSION | 140 | 0.2% | Same entity, metric, period and unit, but a different filing/revision/submission version. |
| WRONG_SERIES_VARIANT | 107 | 0.1% | Same entity, period, unit and underlying measure, but a different series variant or measurement basis such as seasonal adjustment, frequency, nominal/real basis, or transform. |
| WRONG_UNIT | 23 | 0.0% | Same entity, metric and period, reported in a genuinely different unit. |


## 6. Unavailable context variants

None — every configured length was built from authentic same-domain records.

## 7. Validation results

| id | check | severity | result | checked | failed |
|---|---|---|---|---|---|
| A | unique IDs (families and instances) | CRITICAL | PASS | 238 | 0 |
| AA | model prompt token-budget and provenance | CRITICAL | PASS | 204 | 0 |
| B | no duplicate question families | CRITICAL | PASS | 34 | 0 |
| C | valid source provenance | CRITICAL | PASS | 34 | 0 |
| D | deterministic gold-answer recomputation | CRITICAL | PASS | 34 | 0 |
| E | gold evidence present in every answerable context | CRITICAL | PASS | 204 | 0 |
| F | gold evidence absent for unanswerable families | CRITICAL | PASS | 204 | 0 |
| G | identical question across context-length variants | CRITICAL | PASS | 34 | 0 |
| H | identical gold answer across context-length variants | CRITICAL | PASS | 34 | 0 |
| I | identical gold evidence across context-length variants | CRITICAL | PASS | 34 | 0 |
| J | nested-context lineage | CRITICAL | PASS | 34 | 0 |
| K | token-length compliance | CRITICAL | PASS | 204 | 0 |
| L | target-position compliance | CRITICAL | PASS | 204 | 0 |
| M | record-boundary integrity | CRITICAL | PASS | 204 | 0 |
| N | unit consistency in calculations | CRITICAL | PASS | 9 | 0 |
| O | answer-type / schema validity | CRITICAL | PASS | 34 | 0 |
| P | distractor metadata completeness | CRITICAL | PASS | 204 | 0 |
| Q | no NaN or invalid numeric answers | CRITICAL | PASS | 34 | 0 |
| R | no context truncation through target evidence | CRITICAL | PASS | 204 | 0 |
| S | no answer leakage for unanswerable families | CRITICAL | PASS | 204 | 0 |
| T | calculation operands recomputable | CRITICAL | PASS | 9 | 0 |
| U | all five question types represented | CRITICAL | PASS | 5 | 0 |
| V | no duplicate answer sources in answerable contexts | CRITICAL | PASS | 204 | 0 |
| W | opaque display ID mapping integrity | CRITICAL | PASS | 204 | 0 |
| X | evidence-equivalence consistency | CRITICAL | PASS | 204 | 0 |
| Y | distractor taxonomy semantic constraints | CRITICAL | PASS | 204 | 0 |
| Z | model-facing questions do not leak answerability | CRITICAL | PASS | 34 | 0 |


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
| `CT_0004_4K` | 4K | 4041 | 0.987 | 43 | 0.5035 | 1947–2122 | `7e37313ac4c6b086` |
| `CT_0004_8K` | 8K | 8109 | 0.990 | 83 | 0.4995 | 3963–4138 | `8b837ee94caef535` |
| `CT_0004_16K` | 16K | 16220 | 0.990 | 165 | 0.5019 | 8054–8229 | `1c09b5f853cda098` |
| `CT_0004_32K` | 32K | 32408 | 0.989 | 315 | 0.5012 | 16154–16329 | `7a31fdb1c2f84852` |
| `CT_0004_64K` | 64K | 64932 | 0.991 | 605 | 0.4999 | 32370–32545 | `15acc38f0d923257` |
| `CT_0004_128K` | 128K | 129824 | 0.991 | 1201 | 0.5002 | 64854–65029 | `638ea9ef02fb3fe2` |


### `FDA_0007` — FDA / UNANSWERABLE

*Template:* `FDA_UNANSWERABLE_ATTRIBUTE_ABSENT`

**Question.** Using only the Drugs@FDA records supplied in the context, what is the route of administration for product number 001 under FDA application ANDA215255 (brand name "CANAGLIFLOZIN AND METFORMIN HYDROCHLORIDE")?

**Gold outcome.** `INSUFFICIENT_EVIDENCE` — ATTRIBUTE_NOT_LISTED_FOR_PRODUCT

> The Drugs@FDA record for product ANDA215255/001 omits product.route; openFDA returns no such field for this product. Verified by exhaustive scan of the normalized pool: zero records match entity_id=ANDA215255/001 and concept=product.route. Other products in the pool do carry this attribute, so the omission is a property of this product.

**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `FDA_0007_4K` | 4K | 4013 | 0.980 | 43 | n/a | n/a | `7331f53da35111d7` |
| `FDA_0007_8K` | 8K | 8048 | 0.982 | 86 | n/a | n/a | `47de0a6bb4e7a483` |
| `FDA_0007_16K` | 16K | 16158 | 0.986 | 171 | n/a | n/a | `d352e8a8acbdec57` |
| `FDA_0007_32K` | 32K | 32362 | 0.988 | 342 | n/a | n/a | `557fc1b513441bd5` |
| `FDA_0007_64K` | 64K | 64816 | 0.989 | 687 | n/a | n/a | `074ab0824765f7fd` |
| `FDA_0007_128K` | 128K | 129639 | 0.989 | 1370 | n/a | n/a | `ff441300b3fb74cd` |


### `FRED_0008` — FRED / TEMPORAL_VERSION

*Template:* `FRED_VINTAGE_SELECTION`

**Question.** Using only the FRED/ALFRED records supplied in the context, what value did FRED series PAYEMS ("All Employees, Total Nonfarm"), measured in Thousands of Persons, seasonally adjusted, monthly frequency show for the observation dated 2021-03-01 **as of the vintage date 2021-04-29**? Report the value from that vintage exactly.

**Gold answer.** `144,120` (normalized `144120.0`, type NUMERIC, unit Thousands of Persons, tolerance ±0.5)

**Gold evidence.**

| role | record id | entity | field | period | value | unit |
|---|---|---|---|---|---|---|
| target_value | `FRED-PAYEMS-2021-03-01-2021-04-29-4117a714` | United States [US] | All Employees, Total Nonfarm (Seasonally Adjusted) [PAYEMS] | 2021-03-01 | 144120.0 | Thousands of Persons |


**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `FRED_0008_4K` | 4K | 3999 | 0.976 | 50 | 0.4910 | 1920–2007 | `66c8d79b8fee857f` |
| `FRED_0008_8K` | 8K | 8078 | 0.986 | 101 | 0.4996 | 3992–4079 | `b3d70528caa2046e` |
| `FRED_0008_16K` | 16K | 16181 | 0.988 | 203 | 0.5005 | 8055–8142 | `114935197ee8a02f` |
| `FRED_0008_32K` | 32K | 32315 | 0.986 | 405 | 0.5006 | 16133–16220 | `ba153553456a0f5b` |
| `FRED_0008_64K` | 64K | 64695 | 0.987 | 809 | 0.5001 | 32310–32397 | `d1e96b2b5272090a` |
| `FRED_0008_128K` | 128K | 129392 | 0.987 | 1617 | 0.5000 | 64654–64741 | `4412c60913110579` |


### `SEC_0003` — SEC / ENTITY_UNIT_BINDING

*Template:* `SEC_ENTITY_BINDING`

**Question.** Using only the SEC XBRL company-facts records supplied in the context, what value did PFIZER INC (CIK 0000078003) report for us-gaap:NetCashProvidedByUsedInInvestingActivities for the annual XBRL frame CY2010, in USD? Report the exact value for that filer.

**Gold answer.** `-492,000,000` (normalized `-492000000.0`, type NUMERIC, unit USD, tolerance ±0.5)

**Gold evidence.**

| role | record id | entity | field | period | value | unit |
|---|---|---|---|---|---|---|
| target_value | `SEC-0000078003-NetCashProvidedByUsedInI-USD-CY2010-0000078003-13-000006-0cfaf545` | PFIZER INC [0000078003] | Net Cash Provided by (Used in) Investing Activities [us-gaap:NetCashProvidedByUsedInInvestingActivities] | CY2010 | -492000000.0 | USD |


**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `SEC_0003_4K` | 4K | 3960 | 0.967 | 28 | 0.4878 | 1862–2001 | `2c7dfd8f6ee12210` |
| `SEC_0003_8K` | 8K | 8135 | 0.993 | 57 | 0.5004 | 4001–4140 | `f74b439b91eb768a` |
| `SEC_0003_16K` | 16K | 16265 | 0.993 | 114 | 0.5033 | 8116–8255 | `82b3dcffa53f6f11` |
| `SEC_0003_32K` | 32K | 32481 | 0.991 | 227 | 0.5000 | 16170–16309 | `f10d21a1d2e5456c` |
| `SEC_0003_64K` | 64K | 65036 | 0.992 | 454 | 0.4992 | 32399–32538 | `8eb135ad1abbf5b1` |
| `SEC_0003_128K` | 128K | 130130 | 0.993 | 914 | 0.5004 | 65042–65181 | `ff939568362fef67` |


## 9. Reproducibility

| field | value |
|---|---|
| schema version | 1.1.0 |
| config hash | `0f152493a03909c0` |
| seed | 20240817 |
| git commit | `7c848cf04dc3d16ee413ef3819f09f44ca9ad046` |
| tokenizer | `hf:meta-llama/Llama-3.2-3B-Instruct` |
| context lengths | 4K, 8K, 16K, 32K, 64K, 128K |
| target position | 0.5 ± 0.05 |
| min fill ratio | 0.95 |


Raw payloads under `data/raw/` are content-addressed by request URL, so re-running `fetch` is idempotent and the pilot can be regenerated byte-for-byte from the cached layer even after the live APIs change. Hashes of all outputs are in `data/manifests/audit_llama32_smoke_manifest.json`.

