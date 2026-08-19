# Pilot report — `fred_pilot_v2`

_Generated 2026-08-09T19:04:53Z · config `config/fred_pilot_v2.yaml` · config hash `b8ba470562b734d3` · seed `20240817` · git `7c848cf04dc3`_

> **Scope.** This phase generates and validates the dataset only. No LLM has been run against it, no hallucination scoring has been performed, and no statistical analysis or research conclusions are presented here.

## 1. Verdict

**Status: READY for scale-up review**

- Validation: 25/25 checks passed, 0 critical failures, 0 warnings.
- 10 question families → 60 context instances.
- 0 context variants could not be built from authentic records and were recorded as unavailable rather than padded.

## 2. Source retrieval

| domain | source | status | requests | payloads | raw records | normalized | errors | retrieved at |
|---|---|---|---|---|---|---|---|---|
| CLINICAL_TRIALS | CLINICALTRIALS_GOV_V2 | ok | 0 | 24 | 2400 | 0 | 0 | 2026-08-09T04:32:06Z |
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
| FRED | 10 | 10 |


| question type | families | share |
|---|---|---|
| DIRECT_RETRIEVAL | 2 | 20% |
| ENTITY_UNIT_BINDING | 2 | 20% |
| RETRIEVAL_CALCULATION | 3 | 30% |
| TEMPORAL_VERSION | 1 | 10% |
| UNANSWERABLE | 2 | 20% |


Answerable: **8** · Unanswerable: **2**

<details><summary>Families by template</summary>

| template | families |
|---|---|
| FRED_BASIS_BINDING | 2 |
| FRED_DIRECT_OBSERVATION | 2 |
| FRED_PERCENT_CHANGE | 2 |
| FRED_SERIES_SPREAD | 1 |
| FRED_UNANSWERABLE_NO_OBSERVATION | 2 |
| FRED_VINTAGE_SELECTION | 1 |

</details>

## 4. Context instances

Tokenizer: `tiktoken:cl100k_base` (tiktoken==0.13.0)

| nominal | instances | min tokens | median tokens | max tokens | min fill | median fill |
|---|---|---|---|---|---|---|
| 4K | 10 | 3995.0 | 4015.0 | 4042.0 | 0.9753 | 0.9802 |
| 8K | 10 | 8023.0 | 8051.0 | 8084.0 | 0.9794 | 0.9828 |
| 16K | 10 | 16122.0 | 16162.0 | 16181.0 | 0.984 | 0.9865 |
| 32K | 10 | 32303.0 | 32346.0 | 32380.0 | 0.9858 | 0.9871 |
| 64K | 10 | 64670.0 | 64706.0 | 64746.0 | 0.9868 | 0.9873 |
| 128K | 10 | 129406.0 | 129438.0 | 129527.0 | 0.9873 | 0.9875 |


**Target-evidence position** (target 0.5 ± 0.05): n=48, min=0.4889, median=0.5, max=0.5087, mean=0.4998

## 5. Distractors

| distractor type | records placed | share | definition |
|---|---|---|---|
| OTHER_SAME_DOMAIN | 12912 | 41.2% | A real record from the same primary source with no closer relationship to the target. |
| WRONG_PERIOD | 9287 | 29.7% | Same entity and metric, a different period (other year, quarter, or instant). |
| WRONG_FIELD | 8032 | 25.6% | Same entity, a different field/concept. |
| NEAR_MATCH_VALUE | 720 | 2.3% | Numerically within 5% of a target value while being a different fact -- a plausible-looking wrong answer. |
| WRONG_ENTITY | 158 | 0.5% | Same metric and period, a different entity (other company, country, trial, product). |
| WRONG_SERIES_VARIANT | 107 | 0.3% | Same entity, period, unit and underlying measure, but a different series variant or measurement basis such as seasonal adjustment, frequency, nominal/real basis, or transform. |
| WRONG_VERSION | 84 | 0.3% | Same entity, metric, period and unit, but a different filing/revision/submission version. |
| WRONG_UNIT | 22 | 0.1% | Same entity, metric and period, reported in a genuinely different unit. |


## 6. Unavailable context variants

None — every configured length was built from authentic same-domain records.

## 7. Validation results

| id | check | severity | result | checked | failed |
|---|---|---|---|---|---|
| A | unique IDs (families and instances) | CRITICAL | PASS | 70 | 0 |
| B | no duplicate question families | CRITICAL | PASS | 10 | 0 |
| C | valid source provenance | CRITICAL | PASS | 10 | 0 |
| D | deterministic gold-answer recomputation | CRITICAL | PASS | 10 | 0 |
| E | gold evidence present in every answerable context | CRITICAL | PASS | 60 | 0 |
| F | gold evidence absent for unanswerable families | CRITICAL | PASS | 60 | 0 |
| G | identical question across context-length variants | CRITICAL | PASS | 10 | 0 |
| H | identical gold answer across context-length variants | CRITICAL | PASS | 10 | 0 |
| I | identical gold evidence across context-length variants | CRITICAL | PASS | 10 | 0 |
| J | nested-context lineage | CRITICAL | PASS | 10 | 0 |
| K | token-length compliance | CRITICAL | PASS | 60 | 0 |
| L | target-position compliance | CRITICAL | PASS | 60 | 0 |
| M | record-boundary integrity | CRITICAL | PASS | 60 | 0 |
| N | unit consistency in calculations | CRITICAL | PASS | 3 | 0 |
| O | answer-type / schema validity | CRITICAL | PASS | 10 | 0 |
| P | distractor metadata completeness | CRITICAL | PASS | 60 | 0 |
| Q | no NaN or invalid numeric answers | CRITICAL | PASS | 10 | 0 |
| R | no context truncation through target evidence | CRITICAL | PASS | 60 | 0 |
| S | no answer leakage for unanswerable families | CRITICAL | PASS | 60 | 0 |
| T | calculation operands recomputable | CRITICAL | PASS | 3 | 0 |
| U | all five question types represented | CRITICAL | PASS | 5 | 0 |
| V | no duplicate answer sources in answerable contexts | CRITICAL | PASS | 60 | 0 |
| W | opaque display ID mapping integrity | CRITICAL | PASS | 60 | 0 |
| X | evidence-equivalence consistency | CRITICAL | PASS | 60 | 0 |
| Y | distractor taxonomy semantic constraints | CRITICAL | PASS | 60 | 0 |


No check produced failures.

Key derived counts:

- Duplicate family IDs / instance IDs / question texts: 0
- Gold-recomputation failures (check D): 0
- Unanswerable leakage failures (check S): 0
- Duplicate-answer-source failures (check V): 0

## 8. Representative question families

_Context strings are deliberately not reproduced here; only their measured properties are._

### `FRED_0005` — FRED / RETRIEVAL_CALCULATION

*Template:* `FRED_PERCENT_CHANGE`

**Question.** Using only the FRED records supplied in the context, calculate the percentage change in FRED series WGS10YR ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, weekly frequency between the observation dated 2026-07-24 and the observation dated 2026-07-31. Use both values from the most recent vintage, apply ((value_2026-07-31 - value_2026-07-24) / value_2026-07-24) * 100, and round to two decimal places.

**Gold answer.** `0.21%` (normalized `0.21`, type PERCENT, unit percent, tolerance ±0.005)

**Gold evidence.**

| role | record id | entity | field | period | value | unit |
|---|---|---|---|---|---|---|
| current | `FRED-WGS10YR-2026-07-31-latest-b0603637` | United States [US] | Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity (Not Seasonally Adjusted) [WGS10YR] | 2026-07-31 | 4.67 | Percent |
| previous | `FRED-WGS10YR-2026-07-24-latest-4def8320` | United States [US] | Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity (Not Seasonally Adjusted) [WGS10YR] | 2026-07-24 | 4.66 | Percent |


**Calculation.** `growth_percent`: `((current - previous) / previous) * 100` → raw `0.214592274678107` → rounded `0.21` (2 dp)

| role | record id | value used |
|---|---|---|
| current | `FRED-WGS10YR-2026-07-31-latest-b0603637` | 4.67 |
| previous | `FRED-WGS10YR-2026-07-24-latest-4def8320` | 4.66 |


**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `FRED_0005_4K` | 4K | 4028 | 0.983 | 51 | 0.5048 | 1943–2124 | `7bc72f2c463ecf3b` |
| `FRED_0005_8K` | 8K | 8073 | 0.986 | 102 | 0.4988 | 3936–4117 | `fa62a0208cb2cafb` |
| `FRED_0005_16K` | 16K | 16155 | 0.986 | 204 | 0.4975 | 7947–8128 | `7d1197b282a6a3f3` |
| `FRED_0005_32K` | 32K | 32303 | 0.986 | 406 | 0.4991 | 16031–16212 | `d0965eda0ca6a088` |
| `FRED_0005_64K` | 64K | 64679 | 0.987 | 813 | 0.5000 | 32249–32430 | `060f93f0bcabfdbe` |
| `FRED_0005_128K` | 128K | 129434 | 0.988 | 1624 | 0.4998 | 64596–64777 | `d28a58257b3a7087` |


### `FRED_0009` — FRED / UNANSWERABLE

*Template:* `FRED_UNANSWERABLE_NO_OBSERVATION`

**Question.** Using only the FRED records supplied in the context, what value does FRED report for FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency, for the observation dated 2009-09-07? If the supplied records contain no observation for that series on that date, state that the evidence is insufficient rather than interpolating from neighbouring dates or from a related series.

**Gold outcome.** `INSUFFICIENT_EVIDENCE` — NO_OBSERVATION_PUBLISHED

> The St. Louis Fed returns an empty observation for DGS10 on 2009-09-07 — the series publishes no value for that date (a non-trading day for daily series, or a date outside the published range). Verified by exhaustive scan of the normalized pool: zero valued records match entity_id=US, concept=DGS10, period=2009-09-07. Empty observations are never rendered into a context.

**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `FRED_0009_4K` | 4K | 4000 | 0.977 | 48 | n/a | n/a | `256699a799aba6eb` |
| `FRED_0009_8K` | 8K | 8056 | 0.983 | 96 | n/a | n/a | `2563446c383f943c` |
| `FRED_0009_16K` | 16K | 16178 | 0.987 | 191 | n/a | n/a | `f65b67d02df91335` |
| `FRED_0009_32K` | 32K | 32380 | 0.988 | 381 | n/a | n/a | `45a6fabcd897a9c6` |
| `FRED_0009_64K` | 64K | 64709 | 0.987 | 762 | n/a | n/a | `3d1b25cb027067a0` |
| `FRED_0009_128K` | 128K | 129527 | 0.988 | 1524 | n/a | n/a | `5a840e5c23625eaf` |


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
| `FRED_0008_4K` | 4K | 4016 | 0.981 | 50 | 0.5087 | 2000–2086 | `854373824ba510f6` |
| `FRED_0008_8K` | 8K | 8023 | 0.979 | 100 | 0.4959 | 3936–4022 | `b18094ab23ed2400` |
| `FRED_0008_16K` | 16K | 16162 | 0.987 | 202 | 0.5017 | 8066–8152 | `5078b0ec5c32b58b` |
| `FRED_0008_32K` | 32K | 32363 | 0.988 | 405 | 0.5003 | 16147–16233 | `ebc275cdbcc8f7bd` |
| `FRED_0008_64K` | 64K | 64682 | 0.987 | 808 | 0.5005 | 32330–32416 | `4b8849f96edd0611` |
| `FRED_0008_128K` | 128K | 129406 | 0.987 | 1617 | 0.5000 | 64661–64747 | `88e2dce49c9e89fc` |


### `FRED_0003` — FRED / ENTITY_UNIT_BINDING

*Template:* `FRED_BASIS_BINDING`

**Question.** Using only the FRED records supplied in the context, report the value of FRED series PAYNSA ("All Employees, Total Nonfarm"), measured in Thousands of Persons, not seasonally adjusted, monthly frequency for United States on the observation dated 2020-03-01. Report the value for series PAYNSA exactly.

**Gold answer.** `149,952` (normalized `149952.0`, type NUMERIC, unit Thousands of Persons, tolerance ±0.5)

**Gold evidence.**

| role | record id | entity | field | period | value | unit |
|---|---|---|---|---|---|---|
| target_value | `FRED-PAYNSA-2020-03-01-latest-01e51bbe` | United States [US] | All Employees, Total Nonfarm (Not Seasonally Adjusted) [PAYNSA] | 2020-03-01 | 149952.0 | Thousands of Persons |


**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `FRED_0003_4K` | 4K | 4042 | 0.987 | 51 | 0.5014 | 1985–2068 | `fb63cdc4f96fbd64` |
| `FRED_0003_8K` | 8K | 8042 | 0.982 | 101 | 0.4988 | 3970–4053 | `e8aec718fae1e386` |
| `FRED_0003_16K` | 16K | 16159 | 0.986 | 202 | 0.5019 | 8068–8151 | `4ee2edb9091fe242` |
| `FRED_0003_32K` | 32K | 32355 | 0.987 | 405 | 0.5008 | 16161–16244 | `86ac32b6df1b3ab9` |
| `FRED_0003_64K` | 64K | 64686 | 0.987 | 809 | 0.5000 | 32304–32387 | `278a377a3f2a289b` |
| `FRED_0003_128K` | 128K | 129438 | 0.988 | 1619 | 0.5000 | 64676–64759 | `c70b8b681019cc37` |


## 9. Reproducibility

| field | value |
|---|---|
| schema version | 1.1.0 |
| config hash | `b8ba470562b734d3` |
| seed | 20240817 |
| git commit | `7c848cf04dc3d16ee413ef3819f09f44ca9ad046` |
| tokenizer | `tiktoken:cl100k_base` |
| context lengths | 4K, 8K, 16K, 32K, 64K, 128K |
| target position | 0.5 ± 0.05 |
| min fill ratio | 0.95 |


Raw payloads under `data/raw/` are content-addressed by request URL, so re-running `fetch` is idempotent and the pilot can be regenerated byte-for-byte from the cached layer even after the live APIs change. Hashes of all outputs are in `data/manifests/fred_pilot_v2_manifest.json`.

