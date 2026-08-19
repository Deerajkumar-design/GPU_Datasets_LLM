# Pilot report — `preproduction_llama32_3b`

_Generated 2026-08-09T19:44:46Z · config `config/preproduction.yaml` · config hash `e2e65ac32a5ebe43` · seed `20240817` · git `7c848cf04dc3`_

> **Scope.** This phase generates and validates the dataset only. No LLM has been run against it, no hallucination scoring has been performed, and no statistical analysis or research conclusions are presented here.

## 1. Verdict

**Status: READY for scale-up review**

- Validation: 27/27 checks passed, 0 critical failures, 0 warnings.
- 100 question families → 600 context instances.
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
| CLINICAL_TRIALS | 25 | 25 |
| FDA | 25 | 25 |
| FRED | 25 | 25 |
| SEC | 25 | 25 |


| question type | families | share |
|---|---|---|
| DIRECT_RETRIEVAL | 20 | 20% |
| ENTITY_UNIT_BINDING | 15 | 15% |
| RETRIEVAL_CALCULATION | 30 | 30% |
| TEMPORAL_VERSION | 15 | 15% |
| UNANSWERABLE | 20 | 20% |


Answerable: **80** · Unanswerable: **20**

<details><summary>Families by template</summary>

| template | families |
|---|---|
| CT_ARM_TYPE_BINDING | 4 |
| CT_DATE_FIELD_SELECTION | 4 |
| CT_DIRECT_ENROLLMENT | 5 |
| CT_ENROLLMENT_DIFFERENCE | 4 |
| CT_STUDY_DURATION_DAYS | 3 |
| CT_UNANSWERABLE_FIELD_ABSENT | 5 |
| FDA_DIRECT_PRODUCT_ATTRIBUTE | 5 |
| FDA_ORIGINAL_VS_SUPPLEMENT | 3 |
| FDA_PRODUCT_COUNT | 4 |
| FDA_STRENGTH_PRODUCT_BINDING | 4 |
| FDA_STRENGTH_RATIO | 4 |
| FDA_UNANSWERABLE_ATTRIBUTE_ABSENT | 5 |
| FRED_BASIS_BINDING | 4 |
| FRED_DIRECT_OBSERVATION | 5 |
| FRED_PERCENT_CHANGE | 4 |
| FRED_SERIES_SPREAD | 3 |
| FRED_UNANSWERABLE_NO_OBSERVATION | 5 |
| FRED_VINTAGE_SELECTION | 4 |
| SEC_DIRECT_XBRL_FACT | 5 |
| SEC_ENTITY_BINDING | 3 |
| SEC_FILING_VERSION_SELECTION | 2 |
| SEC_OPERATING_MARGIN | 4 |
| SEC_QUARTER_VS_ANNUAL_FRAME | 2 |
| SEC_UNANSWERABLE_CONCEPT_OR_PERIOD_ABSENT | 5 |
| SEC_YOY_GROWTH_PERCENT | 4 |

</details>

## 4. Context instances

Tokenizer: `hf:meta-llama/Llama-3.2-3B-Instruct` (transformers==5.14.1; tokenizers==0.22.2)
Model: `meta-llama/Llama-3.2-3B-Instruct` · context limit `131072` · generation reserve `512` · prompt `llama_chat_v1` / `4e6a3c47baa301a0` · chat template `True`

| nominal | instances | min tokens | median tokens | max tokens | median rendered | max rendered | min margin | min fill | median fill |
|---|---|---|---|---|---|---|---|---|---|
| 4K | 100 | 3961.0 | 4019.0 | 4067.0 | 4282.0 | 4373.0 | 126187.0 | 0.967 | 0.9812 |
| 8K | 100 | 8018.0 | 8083.0 | 8137.0 | 8345.0 | 8443.0 | 122117.0 | 0.9788 | 0.9867 |
| 16K | 100 | 16111.0 | 16194.0 | 16268.0 | 16456.0 | 16545.0 | 114015.0 | 0.9833 | 0.9884 |
| 32K | 100 | 32297.0 | 32424.0 | 32544.0 | 32676.0 | 32850.0 | 97710.0 | 0.9856 | 0.9895 |
| 64K | 100 | 64653.0 | 64882.0 | 65080.0 | 65134.0 | 65356.0 | 65204.0 | 0.9865 | 0.99 |
| 128K | 100 | 129366.0 | 129811.0 | 130157.0 | 130050.0 | 130437.0 | 123.0 | 0.987 | 0.9904 |


**Target-evidence position** (target 0.5 ± 0.05): n=480, min=0.4823, median=0.5001, max=0.5159, mean=0.4999

## 5. Distractors

| distractor type | records placed | share | definition |
|---|---|---|---|
| OTHER_SAME_DOMAIN | 119182 | 48.0% | A real record from the same primary source with no closer relationship to the target. |
| WRONG_ENTITY | 48949 | 19.7% | Same metric and period, a different entity (other company, country, trial, product). |
| WRONG_FIELD | 37102 | 14.9% | Same entity, a different field/concept. |
| WRONG_PERIOD | 33912 | 13.7% | Same entity and metric, a different period (other year, quarter, or instant). |
| NEAR_MATCH_VALUE | 8488 | 3.4% | Numerically within 5% of a target value while being a different fact -- a plausible-looking wrong answer. |
| WRONG_VERSION | 354 | 0.1% | Same entity, metric, period and unit, but a different filing/revision/submission version. |
| WRONG_SERIES_VARIANT | 183 | 0.1% | Same entity, period, unit and underlying measure, but a different series variant or measurement basis such as seasonal adjustment, frequency, nominal/real basis, or transform. |
| WRONG_UNIT | 102 | 0.0% | Same entity, metric and period, reported in a genuinely different unit. |


## 6. Unavailable context variants

None — every configured length was built from authentic same-domain records.

## 7. Validation results

| id | check | severity | result | checked | failed |
|---|---|---|---|---|---|
| A | unique IDs (families and instances) | CRITICAL | PASS | 700 | 0 |
| AA | model prompt token-budget and provenance | CRITICAL | PASS | 600 | 0 |
| B | no duplicate question families | CRITICAL | PASS | 100 | 0 |
| C | valid source provenance | CRITICAL | PASS | 100 | 0 |
| D | deterministic gold-answer recomputation | CRITICAL | PASS | 100 | 0 |
| E | gold evidence present in every answerable context | CRITICAL | PASS | 600 | 0 |
| F | gold evidence absent for unanswerable families | CRITICAL | PASS | 600 | 0 |
| G | identical question across context-length variants | CRITICAL | PASS | 100 | 0 |
| H | identical gold answer across context-length variants | CRITICAL | PASS | 100 | 0 |
| I | identical gold evidence across context-length variants | CRITICAL | PASS | 100 | 0 |
| J | nested-context lineage | CRITICAL | PASS | 100 | 0 |
| K | token-length compliance | CRITICAL | PASS | 600 | 0 |
| L | target-position compliance | CRITICAL | PASS | 600 | 0 |
| M | record-boundary integrity | CRITICAL | PASS | 600 | 0 |
| N | unit consistency in calculations | CRITICAL | PASS | 30 | 0 |
| O | answer-type / schema validity | CRITICAL | PASS | 100 | 0 |
| P | distractor metadata completeness | CRITICAL | PASS | 600 | 0 |
| Q | no NaN or invalid numeric answers | CRITICAL | PASS | 100 | 0 |
| R | no context truncation through target evidence | CRITICAL | PASS | 600 | 0 |
| S | no answer leakage for unanswerable families | CRITICAL | PASS | 600 | 0 |
| T | calculation operands recomputable | CRITICAL | PASS | 30 | 0 |
| U | all five question types represented | CRITICAL | PASS | 5 | 0 |
| V | no duplicate answer sources in answerable contexts | CRITICAL | PASS | 600 | 0 |
| W | opaque display ID mapping integrity | CRITICAL | PASS | 600 | 0 |
| X | evidence-equivalence consistency | CRITICAL | PASS | 600 | 0 |
| Y | distractor taxonomy semantic constraints | CRITICAL | PASS | 600 | 0 |
| Z | model-facing questions do not leak answerability | CRITICAL | PASS | 100 | 0 |


No check produced failures.

Key derived counts:

- Duplicate family IDs / instance IDs / question texts: 0
- Gold-recomputation failures (check D): 0
- Unanswerable leakage failures (check S): 0
- Duplicate-answer-source failures (check V): 0

## 8. Representative question families

_Context strings are deliberately not reproduced here; only their measured properties are._

### `CT_0010` — CLINICAL_TRIALS / RETRIEVAL_CALCULATION

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
| `CT_0010_4K` | 4K | 4052 | 0.989 | 43 | 0.4986 | 1933–2108 | `72f21b77e7af9e7e` |
| `CT_0010_8K` | 8K | 8073 | 0.986 | 83 | 0.5007 | 3955–4130 | `5901b2e53c50bf65` |
| `CT_0010_16K` | 16K | 16223 | 0.990 | 163 | 0.4996 | 8017–8192 | `2c591e929309f2db` |
| `CT_0010_32K` | 32K | 32397 | 0.989 | 317 | 0.4990 | 16078–16253 | `fa9752aa3522032e` |
| `CT_0010_64K` | 64K | 64873 | 0.990 | 618 | 0.4992 | 32296–32471 | `9f1f8436e2485462` |
| `CT_0010_128K` | 128K | 129811 | 0.990 | 1214 | 0.5003 | 64858–65033 | `f14157ed345b4a12` |


### `FDA_0021` — FDA / UNANSWERABLE

*Template:* `FDA_UNANSWERABLE_ATTRIBUTE_ABSENT`

**Question.** Using only the Drugs@FDA records supplied in the context, what is the route of administration for product number 001 under FDA application ANDA215255 (brand name "CANAGLIFLOZIN AND METFORMIN HYDROCHLORIDE")?

**Gold outcome.** `INSUFFICIENT_EVIDENCE` — ATTRIBUTE_NOT_LISTED_FOR_PRODUCT

> The Drugs@FDA record for product ANDA215255/001 omits product.route; openFDA returns no such field for this product. Verified by exhaustive scan of the normalized pool: zero records match entity_id=ANDA215255/001 and concept=product.route. Other products in the pool do carry this attribute, so the omission is a property of this product.

**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `FDA_0021_4K` | 4K | 4015 | 0.980 | 42 | n/a | n/a | `6b284d8c221fef0f` |
| `FDA_0021_8K` | 8K | 8098 | 0.989 | 86 | n/a | n/a | `975ca240845e65ba` |
| `FDA_0021_16K` | 16K | 16158 | 0.986 | 172 | n/a | n/a | `29780b6bbbda9125` |
| `FDA_0021_32K` | 32K | 32408 | 0.989 | 343 | n/a | n/a | `58707b80021fd2ca` |
| `FDA_0021_64K` | 64K | 64775 | 0.988 | 686 | n/a | n/a | `06f2b9259ac15fe0` |
| `FDA_0021_128K` | 128K | 129683 | 0.989 | 1374 | n/a | n/a | `77da56b92d3035f9` |


### `FRED_0017` — FRED / TEMPORAL_VERSION

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
| `FRED_0017_4K` | 4K | 4041 | 0.987 | 51 | 0.5009 | 1981–2067 | `a6fbe528f27324f8` |
| `FRED_0017_8K` | 8K | 8038 | 0.981 | 101 | 0.5006 | 3981–4067 | `528b9d94a816147e` |
| `FRED_0017_16K` | 16K | 16152 | 0.986 | 202 | 0.5020 | 8065–8151 | `06869b15bdf56972` |
| `FRED_0017_32K` | 32K | 32355 | 0.987 | 405 | 0.5000 | 16134–16220 | `a23e20384b3c0423` |
| `FRED_0017_64K` | 64K | 64694 | 0.987 | 810 | 0.4995 | 32273–32359 | `7b341dd7945ccbc3` |
| `FRED_0017_128K` | 128K | 129409 | 0.987 | 1617 | 0.5000 | 64662–64748 | `fa2bddba819dc33c` |


### `SEC_0006` — SEC / ENTITY_UNIT_BINDING

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
| `SEC_0006_4K` | 4K | 4065 | 0.992 | 29 | 0.5011 | 1968–2106 | `da5465669e9f5d6c` |
| `SEC_0006_8K` | 8K | 8099 | 0.989 | 57 | 0.5033 | 4007–4145 | `3d03fb9bfac1e350` |
| `SEC_0006_16K` | 16K | 16258 | 0.992 | 114 | 0.4962 | 7999–8137 | `9ba0ba38352953aa` |
| `SEC_0006_32K` | 32K | 32500 | 0.992 | 227 | 0.4995 | 16166–16304 | `5d5a011501d2e217` |
| `SEC_0006_64K` | 64K | 65031 | 0.992 | 454 | 0.5000 | 32447–32585 | `d8fec2daca42d163` |
| `SEC_0006_128K` | 128K | 130109 | 0.993 | 912 | 0.4997 | 64946–65084 | `58cac8118ef29d8a` |


## 9. Reproducibility

| field | value |
|---|---|
| schema version | 1.1.0 |
| config hash | `e2e65ac32a5ebe43` |
| seed | 20240817 |
| git commit | `7c848cf04dc3d16ee413ef3819f09f44ca9ad046` |
| tokenizer | `hf:meta-llama/Llama-3.2-3B-Instruct` |
| context lengths | 4K, 8K, 16K, 32K, 64K, 128K |
| target position | 0.5 ± 0.05 |
| min fill ratio | 0.95 |


Raw payloads under `data/raw/` are content-addressed by request URL, so re-running `fetch` is idempotent and the pilot can be regenerated byte-for-byte from the cached layer even after the live APIs change. Hashes of all outputs are in `data/manifests/preproduction_llama32_3b_manifest.json`.

