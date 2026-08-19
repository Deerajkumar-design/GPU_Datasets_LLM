# Pilot report — `ct_audit_v3`

_Generated 2026-08-09T19:13:42Z · config `config/ct_audit_v3.yaml` · config hash `a3e99a21a0d3793c` · seed `20240817` · git `7c848cf04dc3`_

> **Scope.** This phase generates and validates the dataset only. No LLM has been run against it, no hallucination scoring has been performed, and no statistical analysis or research conclusions are presented here.

## 1. Verdict

**Status: READY for scale-up review**

- Validation: 26/26 checks passed, 0 critical failures, 0 warnings.
- 8 question families → 48 context instances.
- 0 context variants could not be built from authentic records and were recorded as unavailable rather than padded.

## 2. Source retrieval

| domain | source | status | requests | payloads | raw records | normalized | errors | retrieved at |
|---|---|---|---|---|---|---|---|---|
| CLINICAL_TRIALS | CLINICALTRIALS_GOV_V2 | ok | 0 | 24 | 2400 | 74683 | 0 | 2026-08-09T04:32:06Z |
| FDA | OPENFDA_DRUGSFDA | ok | 0 | 15 | 960 | 0 | 0 | 2026-08-09T04:32:06Z |
| SEC | SEC_EDGAR_XBRL_COMPANYFACTS | ok | 0 | 8 | 259528 | 0 | 0 | 2026-08-09T04:32:06Z |
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


| question type | families | share |
|---|---|---|
| DIRECT_RETRIEVAL | 2 | 25% |
| ENTITY_UNIT_BINDING | 1 | 12% |
| RETRIEVAL_CALCULATION | 2 | 25% |
| TEMPORAL_VERSION | 1 | 12% |
| UNANSWERABLE | 2 | 25% |


Answerable: **6** · Unanswerable: **2**

<details><summary>Families by template</summary>

| template | families |
|---|---|
| CT_ARM_TYPE_BINDING | 1 |
| CT_DATE_FIELD_SELECTION | 1 |
| CT_DIRECT_ENROLLMENT | 2 |
| CT_ENROLLMENT_DIFFERENCE | 1 |
| CT_STUDY_DURATION_DAYS | 1 |
| CT_UNANSWERABLE_FIELD_ABSENT | 2 |

</details>

## 4. Context instances

Tokenizer: `tiktoken:cl100k_base` (tiktoken==0.13.0)

| nominal | instances | min tokens | median tokens | max tokens | min fill | median fill |
|---|---|---|---|---|---|---|
| 4K | 8 | 3992.0 | 4029.0 | 4059.0 | 0.9746 | 0.9836 |
| 8K | 8 | 8065.0 | 8097.0 | 8111.0 | 0.9845 | 0.9884 |
| 16K | 8 | 16168.0 | 16221.0 | 16233.0 | 0.9868 | 0.9901 |
| 32K | 8 | 32397.0 | 32453.0 | 32472.0 | 0.9887 | 0.9904 |
| 64K | 8 | 64868.0 | 64917.0 | 64970.0 | 0.9898 | 0.9906 |
| 128K | 8 | 129823.0 | 129874.0 | 129922.0 | 0.9905 | 0.9909 |


**Target-evidence position** (target 0.5 ± 0.05): n=36, min=0.4961, median=0.5002, max=0.5098, mean=0.5008

## 5. Distractors

| distractor type | records placed | share | definition |
|---|---|---|---|
| OTHER_SAME_DOMAIN | 10447 | 56.0% | A real record from the same primary source with no closer relationship to the target. |
| WRONG_ENTITY | 6851 | 36.7% | Same metric and period, a different entity (other company, country, trial, product). |
| WRONG_FIELD | 1370 | 7.3% | Same entity, a different field/concept. |


## 6. Unavailable context variants

None — every configured length was built from authentic same-domain records.

## 7. Validation results

| id | check | severity | result | checked | failed |
|---|---|---|---|---|---|
| A | unique IDs (families and instances) | CRITICAL | PASS | 56 | 0 |
| B | no duplicate question families | CRITICAL | PASS | 8 | 0 |
| C | valid source provenance | CRITICAL | PASS | 8 | 0 |
| D | deterministic gold-answer recomputation | CRITICAL | PASS | 8 | 0 |
| E | gold evidence present in every answerable context | CRITICAL | PASS | 48 | 0 |
| F | gold evidence absent for unanswerable families | CRITICAL | PASS | 48 | 0 |
| G | identical question across context-length variants | CRITICAL | PASS | 8 | 0 |
| H | identical gold answer across context-length variants | CRITICAL | PASS | 8 | 0 |
| I | identical gold evidence across context-length variants | CRITICAL | PASS | 8 | 0 |
| J | nested-context lineage | CRITICAL | PASS | 8 | 0 |
| K | token-length compliance | CRITICAL | PASS | 48 | 0 |
| L | target-position compliance | CRITICAL | PASS | 48 | 0 |
| M | record-boundary integrity | CRITICAL | PASS | 48 | 0 |
| N | unit consistency in calculations | CRITICAL | PASS | 2 | 0 |
| O | answer-type / schema validity | CRITICAL | PASS | 8 | 0 |
| P | distractor metadata completeness | CRITICAL | PASS | 48 | 0 |
| Q | no NaN or invalid numeric answers | CRITICAL | PASS | 8 | 0 |
| R | no context truncation through target evidence | CRITICAL | PASS | 48 | 0 |
| S | no answer leakage for unanswerable families | CRITICAL | PASS | 48 | 0 |
| T | calculation operands recomputable | CRITICAL | PASS | 2 | 0 |
| U | all five question types represented | CRITICAL | PASS | 5 | 0 |
| V | no duplicate answer sources in answerable contexts | CRITICAL | PASS | 48 | 0 |
| W | opaque display ID mapping integrity | CRITICAL | PASS | 48 | 0 |
| X | evidence-equivalence consistency | CRITICAL | PASS | 48 | 0 |
| Y | distractor taxonomy semantic constraints | CRITICAL | PASS | 48 | 0 |
| Z | model-facing questions do not leak answerability | CRITICAL | PASS | 8 | 0 |


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
| `CT_0004_4K` | 4K | 4037 | 0.986 | 43 | 0.5052 | 1953–2126 | `d2d246701d89beba` |
| `CT_0004_8K` | 8K | 8097 | 0.988 | 83 | 0.4995 | 3958–4131 | `7ceb070dc8efbd66` |
| `CT_0004_16K` | 16K | 16221 | 0.990 | 165 | 0.4983 | 7996–8169 | `96d5381f5d776d16` |
| `CT_0004_32K` | 32K | 32434 | 0.990 | 315 | 0.5011 | 16165–16338 | `73f0172f482ae543` |
| `CT_0004_64K` | 64K | 64900 | 0.990 | 604 | 0.4993 | 32320–32493 | `776261afa8f2dded` |
| `CT_0004_128K` | 128K | 129869 | 0.991 | 1200 | 0.5002 | 64870–65043 | `53295ea26e0d747b` |


### `CT_0007` — CLINICAL_TRIALS / UNANSWERABLE

*Template:* `CT_UNANSWERABLE_FIELD_ABSENT`

**Question.** Using only the ClinicalTrials.gov records supplied in the context, what is the date on which results were first posted for trial NCT02339493 ("Electronic Alerts for Stroke Prevention in Patients With Atrial Fibrillation or Atrial Flutter")?

**Gold outcome.** `INSUFFICIENT_EVIDENCE` — RESULTS_NOT_POSTED

> The ClinicalTrials.gov v2 record for NCT02339493 does not populate study.results_first_posted_date. Verified by exhaustive scan of the normalized pool: zero records match entity_id=NCT02339493 and concept=study.results_first_posted_date. Other trials in the pool do populate this field, so its absence is a property of this trial rather than of the adapter.

**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `CT_0007_4K` | 4K | 4020 | 0.981 | 39 | n/a | n/a | `169b7bbdd9cfea00` |
| `CT_0007_8K` | 8K | 8103 | 0.989 | 76 | n/a | n/a | `a30f721e091a2cc2` |
| `CT_0007_16K` | 16K | 16233 | 0.991 | 151 | n/a | n/a | `3c1a28477a9901f4` |
| `CT_0007_32K` | 32K | 32464 | 0.991 | 300 | n/a | n/a | `261f3efdddf4e406` |
| `CT_0007_64K` | 64K | 64917 | 0.991 | 599 | n/a | n/a | `92220da3c459fa1f` |
| `CT_0007_128K` | 128K | 129823 | 0.991 | 1184 | n/a | n/a | `d9385d59f65eb392` |


### `CT_0006` — CLINICAL_TRIALS / TEMPORAL_VERSION

*Template:* `CT_DATE_FIELD_SELECTION`

**Question.** Using only the ClinicalTrials.gov records supplied in the context, what is the PRIMARY COMPLETION DATE of trial NCT02746185 ("Cancer Associated Thrombosis, a Pilot Treatment Study Using Rivaroxaban")? Answer in YYYY-MM-DD form.

**Gold answer.** `2018-04-25` (normalized `2018-04-25`, type DATE)

**Gold evidence.**

| role | record id | entity | field | period | value | unit |
|---|---|---|---|---|---|---|
| target_value | `CT-NCT02746185-study-primary-completion-35ff3c07` | Cancer Associated Thrombosis, a Pilot Treatment Study Using Rivaroxaban [NCT02746185] | Primary completion date [study.primary_completion_date] | 2018 | 2018-04-25 |  |


**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `CT_0006_4K` | 4K | 3992 | 0.975 | 40 | 0.4961 | 1931–2030 | `6aa4812c4c08b624` |
| `CT_0006_8K` | 8K | 8065 | 0.985 | 79 | 0.5056 | 4028–4127 | `6f7d0bedd94784d6` |
| `CT_0006_16K` | 16K | 16227 | 0.990 | 156 | 0.5023 | 8102–8201 | `c4e8be3f6a98a612` |
| `CT_0006_32K` | 32K | 32397 | 0.989 | 300 | 0.5012 | 16188–16287 | `dcc07b1882cce5b0` |
| `CT_0006_64K` | 64K | 64882 | 0.990 | 588 | 0.4995 | 32361–32460 | `13076169141d87f6` |
| `CT_0006_128K` | 128K | 129908 | 0.991 | 1153 | 0.5002 | 64926–65025 | `5c10708e32d85042` |


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
| `CT_0003_4K` | 4K | 4029 | 0.984 | 40 | 0.4991 | 1966–2056 | `3908590430bc9bab` |
| `CT_0003_8K` | 8K | 8077 | 0.986 | 78 | 0.5019 | 4009–4099 | `0d9c5789b334e1c0` |
| `CT_0003_16K` | 16K | 16219 | 0.990 | 148 | 0.4986 | 8041–8131 | `f0763ce56de1981c` |
| `CT_0003_32K` | 32K | 32469 | 0.991 | 286 | 0.5023 | 16263–16353 | `656406c78f935917` |
| `CT_0003_64K` | 64K | 64970 | 0.991 | 567 | 0.5006 | 32480–32570 | `e0f9713570ca55a8` |
| `CT_0003_128K` | 128K | 129922 | 0.991 | 1138 | 0.5000 | 64915–65005 | `3477e2977c490729` |


## 9. Reproducibility

| field | value |
|---|---|
| schema version | 1.1.0 |
| config hash | `a3e99a21a0d3793c` |
| seed | 20240817 |
| git commit | `7c848cf04dc3d16ee413ef3819f09f44ca9ad046` |
| tokenizer | `tiktoken:cl100k_base` |
| context lengths | 4K, 8K, 16K, 32K, 64K, 128K |
| target position | 0.5 ± 0.05 |
| min fill ratio | 0.95 |


Raw payloads under `data/raw/` are content-addressed by request URL, so re-running `fetch` is idempotent and the pilot can be regenerated byte-for-byte from the cached layer even after the live APIs change. Hashes of all outputs are in `data/manifests/ct_audit_v3_manifest.json`.

