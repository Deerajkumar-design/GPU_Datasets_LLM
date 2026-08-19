# Pilot report — `preproduction_llama32_3b_500f_6ctx_v1`

_Generated 2026-08-11T04:16:42Z · config `config/preproduction_llama32_3b_500f_6ctx_v1.yaml` · config hash `fba01b65a8e9baff` · seed `20240817` · git `7c848cf04dc3`_

> **Scope.** This phase generates and validates the dataset only. No LLM has been run against it, no hallucination scoring has been performed, and no statistical analysis or research conclusions are presented here.

## 1. Verdict

**Status: READY for scale-up review**

- Validation: 30/30 checks passed, 0 critical failures, 0 warnings.
- 500 question families → 3000 context instances.
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
| CLINICAL_TRIALS | 125 | 125 |
| FDA | 125 | 125 |
| FRED | 125 | 125 |
| SEC | 125 | 125 |


| question type | families | share |
|---|---|---|
| DIRECT_RETRIEVAL | 100 | 20% |
| ENTITY_UNIT_BINDING | 95 | 19% |
| RETRIEVAL_CALCULATION | 150 | 30% |
| TEMPORAL_VERSION | 55 | 11% |
| UNANSWERABLE | 100 | 20% |


Answerable: **400** · Unanswerable: **100**

<details><summary>Families by template</summary>

| template | families |
|---|---|
| CT_ARM_TYPE_BINDING | 20 |
| CT_DATE_FIELD_SELECTION | 20 |
| CT_DIRECT_ENROLLMENT | 25 |
| CT_ENROLLMENT_DIFFERENCE | 18 |
| CT_STUDY_DURATION_DAYS | 17 |
| CT_UNANSWERABLE_FIELD_ABSENT | 25 |
| FDA_DIRECT_PRODUCT_ATTRIBUTE | 25 |
| FDA_ORIGINAL_VS_SUPPLEMENT | 15 |
| FDA_PRODUCT_COUNT | 20 |
| FDA_STRENGTH_PRODUCT_BINDING | 20 |
| FDA_STRENGTH_RATIO | 20 |
| FDA_UNANSWERABLE_ATTRIBUTE_ABSENT | 25 |
| FRED_BASIS_BINDING | 20 |
| FRED_DIRECT_OBSERVATION | 25 |
| FRED_PERCENT_CHANGE | 21 |
| FRED_SERIES_SPREAD | 14 |
| FRED_UNANSWERABLE_NO_OBSERVATION | 25 |
| FRED_VINTAGE_SELECTION | 20 |
| SEC_DIRECT_XBRL_FACT | 25 |
| SEC_ENTITY_BINDING | 15 |
| SEC_FILING_VERSION_SELECTION | 8 |
| SEC_OPERATING_MARGIN | 5 |
| SEC_QUARTER_VS_ANNUAL_FRAME | 12 |
| SEC_UNANSWERABLE_CONCEPT_OR_PERIOD_ABSENT | 25 |
| SEC_YOY_GROWTH_PERCENT | 35 |

</details>

## 4. Context instances

Tokenizer: `hf:meta-llama/Llama-3.2-3B-Instruct` (transformers==5.14.1; tokenizers==0.22.2)
Model: `meta-llama/Llama-3.2-3B-Instruct` · context limit `131072` · generation reserve `128` · prompt `llama_chat_v4` / `5d2869822989e19b` · template date `09 Aug 2026` · chat template `True`

| nominal | instances | min tokens | median tokens | max tokens | median rendered | max rendered | min margin | min fill | median fill |
|---|---|---|---|---|---|---|---|---|---|
| 4K | 500 | 3956.0 | 4025.0 | 4068.0 | 4276.0 | 4359.0 | 77441.0 | 0.9658 | 0.9827 |
| 8K | 500 | 8022.0 | 8083.0 | 8136.0 | 8329.0 | 8459.0 | 73341.0 | 0.9792 | 0.9867 |
| 16K | 500 | 16110.0 | 16189.0 | 16271.0 | 16441.0 | 16558.0 | 65242.0 | 0.9833 | 0.9881 |
| 32K | 500 | 32286.0 | 32422.0 | 32546.0 | 32663.0 | 32836.0 | 48964.0 | 0.9853 | 0.9894 |
| 64K | 500 | 64648.0 | 64880.0 | 65092.0 | 65116.0 | 65367.0 | 16433.0 | 0.9865 | 0.99 |
| 82K | 500 | 81350.0 | 81497.0 | 81571.0 | 81748.0 | 81800.0 | 0.0 | 0.9688 | 0.9706 |


**Target-evidence position** (target 0.5 ± 0.05): n=2400, min=0.4819, median=0.5, max=0.5177, mean=0.5002

## 5. Distractors

| distractor type | records placed | share | definition |
|---|---|---|---|
| OTHER_SAME_DOMAIN | 468027 | 46.6% | A real record from the same primary source with no closer relationship to the target. |
| WRONG_ENTITY | 202586 | 20.2% | Same metric and period, a different entity (other company, country, trial, product). |
| WRONG_FIELD | 152897 | 15.2% | Same entity, a different field/concept. |
| WRONG_PERIOD | 140853 | 14.0% | Same entity and metric, a different period (other year, quarter, or instant). |
| NEAR_MATCH_VALUE | 36402 | 3.6% | Numerically within 5% of a target value while being a different fact -- a plausible-looking wrong answer. |
| WRONG_VERSION | 1807 | 0.2% | Same entity, metric, period and unit, but a different filing/revision/submission version. |
| WRONG_SERIES_VARIANT | 1082 | 0.1% | Same entity, period, unit and underlying measure, but a different series variant or measurement basis such as seasonal adjustment, frequency, nominal/real basis, or transform. |
| WRONG_UNIT | 341 | 0.0% | Same entity, metric and period, reported in a genuinely different unit. |


## 6. Unavailable context variants

None — every configured length was built from authentic same-domain records.

## 7. Validation results

| id | check | severity | result | checked | failed |
|---|---|---|---|---|---|
| A | unique IDs (families and instances) | CRITICAL | PASS | 3500 | 0 |
| AA | model prompt token-budget and provenance | CRITICAL | PASS | 3000 | 0 |
| AB | complete instance count for available variants | CRITICAL | PASS | 1 | 0 |
| AC | per-record gold evidence display mapping | CRITICAL | PASS | 3000 | 0 |
| AD | temporal-version question-type semantics | CRITICAL | PASS | 500 | 0 |
| B | no duplicate question families | CRITICAL | PASS | 500 | 0 |
| C | valid source provenance | CRITICAL | PASS | 500 | 0 |
| D | deterministic gold-answer recomputation | CRITICAL | PASS | 500 | 0 |
| E | gold evidence present in every answerable context | CRITICAL | PASS | 3000 | 0 |
| F | gold evidence absent for unanswerable families | CRITICAL | PASS | 3000 | 0 |
| G | identical question across context-length variants | CRITICAL | PASS | 500 | 0 |
| H | identical gold answer across context-length variants | CRITICAL | PASS | 500 | 0 |
| I | identical gold evidence across context-length variants | CRITICAL | PASS | 500 | 0 |
| J | nested-context lineage | CRITICAL | PASS | 500 | 0 |
| K | token-length compliance | CRITICAL | PASS | 3000 | 0 |
| L | target-position compliance | CRITICAL | PASS | 3000 | 0 |
| M | record-boundary integrity | CRITICAL | PASS | 3000 | 0 |
| N | unit consistency in calculations | CRITICAL | PASS | 150 | 0 |
| O | answer-type / schema validity | CRITICAL | PASS | 500 | 0 |
| P | distractor metadata completeness | CRITICAL | PASS | 3000 | 0 |
| Q | no NaN or invalid numeric answers | CRITICAL | PASS | 500 | 0 |
| R | no context truncation through target evidence | CRITICAL | PASS | 3000 | 0 |
| S | no answer leakage for unanswerable families | CRITICAL | PASS | 3000 | 0 |
| T | calculation operands recomputable | CRITICAL | PASS | 150 | 0 |
| U | all five question types represented | CRITICAL | PASS | 5 | 0 |
| V | no duplicate answer sources in answerable contexts | CRITICAL | PASS | 3000 | 0 |
| W | opaque display ID mapping integrity | CRITICAL | PASS | 3000 | 0 |
| X | evidence-equivalence consistency | CRITICAL | PASS | 3000 | 0 |
| Y | distractor taxonomy semantic constraints | CRITICAL | PASS | 3000 | 0 |
| Z | model-facing questions do not leak answerability | CRITICAL | PASS | 500 | 0 |


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
| `CT_0010_4K` | 4K | 4050 | 0.989 | 43 | 0.4990 | 1934–2108 | `c4ab31b878c1ccfa` |
| `CT_0010_8K` | 8K | 8050 | 0.983 | 83 | 0.4928 | 3880–4054 | `6b789d13b43bfc85` |
| `CT_0010_16K` | 16K | 16222 | 0.990 | 163 | 0.5001 | 8025–8199 | `26e249953138952c` |
| `CT_0010_32K` | 32K | 32391 | 0.989 | 317 | 0.4989 | 16074–16248 | `510391f340aecd6b` |
| `CT_0010_64K` | 64K | 64912 | 0.991 | 618 | 0.5000 | 32366–32540 | `542c63ce9ed374a4` |
| `CT_0010_82K` | 82K | 81520 | 0.971 | 776 | 0.4996 | 40639–40813 | `f1e36a0a0dbc623e` |


### `FDA_0021` — FDA / UNANSWERABLE

*Template:* `FDA_UNANSWERABLE_ATTRIBUTE_ABSENT`

**Question.** Using only the Drugs@FDA records supplied in the context, what is the route of administration for product number 001 under FDA application ANDA215255 (brand name "CANAGLIFLOZIN AND METFORMIN HYDROCHLORIDE")?

**Gold outcome.** `INSUFFICIENT_EVIDENCE` — ATTRIBUTE_NOT_LISTED_FOR_PRODUCT

> The Drugs@FDA record for product ANDA215255/001 omits product.route; openFDA returns no such field for this product. Verified by exhaustive scan of the normalized pool: zero records match entity_id=ANDA215255/001 and concept=product.route. Other products in the pool do carry this attribute, so the omission is a property of this product.

**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `FDA_0021_4K` | 4K | 4022 | 0.982 | 42 | n/a | n/a | `a99fc86de6ae4dd3` |
| `FDA_0021_8K` | 8K | 8031 | 0.980 | 85 | n/a | n/a | `eb6d39ecb6af961d` |
| `FDA_0021_16K` | 16K | 16197 | 0.989 | 172 | n/a | n/a | `c417d5d97b73d998` |
| `FDA_0021_32K` | 32K | 32373 | 0.988 | 342 | n/a | n/a | `c5a2665f0e6e6836` |
| `FDA_0021_64K` | 64K | 64831 | 0.989 | 686 | n/a | n/a | `e454d17a2a29edbc` |
| `FDA_0021_82K` | 82K | 81548 | 0.971 | 862 | n/a | n/a | `d286385f58468b88` |


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
| `FRED_0017_4K` | 4K | 4030 | 0.984 | 51 | 0.5012 | 1977–2063 | `d2bffd60890eb670` |
| `FRED_0017_8K` | 8K | 8026 | 0.980 | 101 | 0.5004 | 3973–4059 | `74ad4df78d4a32ac` |
| `FRED_0017_16K` | 16K | 16127 | 0.984 | 202 | 0.5021 | 8055–8141 | `2c6d5b640f597130` |
| `FRED_0017_32K` | 32K | 32325 | 0.987 | 405 | 0.5000 | 16120–16206 | `8154d907ada9fd6d` |
| `FRED_0017_64K` | 64K | 64721 | 0.988 | 811 | 0.4999 | 32308–32394 | `51f25c21a732c91e` |
| `FRED_0017_82K` | 82K | 81513 | 0.971 | 1020 | 0.4996 | 40682–40768 | `73195987cfcce9d8` |


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
| `SEC_0006_4K` | 4K | 4066 | 0.993 | 29 | 0.4986 | 1959–2096 | `10febb53cc9fafcf` |
| `SEC_0006_8K` | 8K | 8113 | 0.990 | 57 | 0.4956 | 3952–4089 | `7dee131b6a860008` |
| `SEC_0006_16K` | 16K | 16269 | 0.993 | 114 | 0.5037 | 8126–8263 | `dc0022e50c15093b` |
| `SEC_0006_32K` | 32K | 32533 | 0.993 | 227 | 0.5004 | 16212–16349 | `138f3ca26fa80f4a` |
| `SEC_0006_64K` | 64K | 65078 | 0.993 | 454 | 0.5001 | 32476–32613 | `211b756b40bf1cca` |
| `SEC_0006_82K` | 82K | 81463 | 0.970 | 568 | 0.5001 | 40672–40809 | `a013432fed4dfb0d` |


## 9. Reproducibility

| field | value |
|---|---|
| schema version | 1.1.0 |
| config hash | `fba01b65a8e9baff` |
| seed | 20240817 |
| git commit | `7c848cf04dc3d16ee413ef3819f09f44ca9ad046` |
| tokenizer | `hf:meta-llama/Llama-3.2-3B-Instruct` |
| context lengths | 4K, 8K, 16K, 32K, 64K, 82K |
| target position | 0.5 ± 0.05 |
| min fill ratio | 0.95 |


Raw payloads under `data/raw/` are content-addressed by request URL, so re-running `fetch` is idempotent and the pilot can be regenerated byte-for-byte from the cached layer even after the live APIs change. Hashes of all outputs are in `data/manifests/preproduction_llama32_3b_500f_6ctx_v1_manifest.json`.

