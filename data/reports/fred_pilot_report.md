# Pilot report — `fred_pilot`

_Generated 2026-08-09T18:18:10Z · config `config/fred_pilot.yaml` · config hash `8c72bbbd80ade192` · seed `20240817` · git `2fe50bc2caec`_

> **Scope.** This phase generates and validates the dataset only. No LLM has been run against it, no hallucination scoring has been performed, and no statistical analysis or research conclusions are presented here.

## 1. Verdict

**Status: READY for scale-up review**

- Validation: 22/22 checks passed, 0 critical failures, 0 warnings.
- 10 question families → 60 context instances.
- 0 context variants could not be built from authentic records and were recorded as unavailable rather than padded.

## 2. Source retrieval

| domain | source | status | requests | payloads | raw records | normalized | errors | retrieved at |
|---|---|---|---|---|---|---|---|---|
| CLINICAL_TRIALS | CLINICALTRIALS_GOV_V2 | ok | 0 | 24 | 2400 | 0 | 0 | 2026-08-09T04:32:06Z |
| FDA | OPENFDA_DRUGSFDA | ok | 0 | 15 | 960 | 0 | 0 | 2026-08-09T04:32:06Z |
| FRED | FRED_STLOUISFED | ok | 48 | 48 | 27085 | 20925 | 0 | 2026-08-09T17:59:43Z |
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
| 4K | 10 | 3988.0 | 4000.0 | 4050.0 | 0.9736 | 0.9766 |
| 8K | 10 | 8022.0 | 8057.0 | 8106.0 | 0.9792 | 0.9835 |
| 16K | 10 | 16130.0 | 16174.0 | 16203.0 | 0.9845 | 0.9872 |
| 32K | 10 | 32344.0 | 32389.0 | 32438.0 | 0.9871 | 0.9884 |
| 64K | 10 | 64788.0 | 64829.0 | 64846.0 | 0.9886 | 0.9892 |
| 128K | 10 | 129609.0 | 129661.0 | 129757.0 | 0.9888 | 0.9892 |


**Target-evidence position** (target 0.5 ± 0.05): n=48, min=0.4907, median=0.5001, max=0.5112, mean=0.5008

## 5. Distractors

| distractor type | records placed | share | definition |
|---|---|---|---|
| OTHER_SAME_DOMAIN | 10547 | 39.2% | A real record from the same primary source with no closer relationship to the target. |
| WRONG_PERIOD | 7913 | 29.4% | Same entity and metric, a different period (other year, quarter, or instant). |
| WRONG_FIELD | 6897 | 25.6% | Same entity, a different field/concept. |
| NEAR_MATCH_VALUE | 1219 | 4.5% | Numerically within 5% of a target value while being a different fact -- a plausible-looking wrong answer. |
| WRONG_ENTITY | 149 | 0.6% | Same metric and period, a different entity (other company, country, trial, product). |
| WRONG_UNIT | 118 | 0.4% | Same entity, metric and period, reported in a different unit or measurement basis. |
| WRONG_VERSION | 75 | 0.3% | Same entity, metric, period and unit, but a different filing/revision/submission version. |


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
| `FRED_0005_4K` | 4K | 4000 | 0.977 | 44 | 0.5036 | 1911–2118 | `50a5ed2a7c7e36f0` |
| `FRED_0005_8K` | 8K | 8100 | 0.989 | 88 | 0.5027 | 3968–4175 | `da6452338f090ac4` |
| `FRED_0005_16K` | 16K | 16174 | 0.987 | 176 | 0.5024 | 8022–8229 | `7fff4172cc463c3b` |
| `FRED_0005_32K` | 32K | 32389 | 0.988 | 350 | 0.5015 | 16139–16346 | `910a5778a9f396af` |
| `FRED_0005_64K` | 64K | 64828 | 0.989 | 699 | 0.5004 | 32337–32544 | `4934c08062c87d00` |
| `FRED_0005_128K` | 128K | 129646 | 0.989 | 1396 | 0.5002 | 64746–64953 | `859382729372401a` |


### `FRED_0009` — FRED / UNANSWERABLE

*Template:* `FRED_UNANSWERABLE_NO_OBSERVATION`

**Question.** Using only the FRED records supplied in the context, what value does FRED report for FRED series DGS10 ("Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity"), measured in Percent, not seasonally adjusted, daily frequency, for the observation dated 2009-09-07? If the supplied records contain no observation for that series on that date, state that the evidence is insufficient rather than interpolating from neighbouring dates or from a related series.

**Gold outcome.** `INSUFFICIENT_EVIDENCE` — NO_OBSERVATION_PUBLISHED

> The St. Louis Fed returns an empty observation for DGS10 on 2009-09-07 — the series publishes no value for that date (a non-trading day for daily series, or a date outside the published range). Verified by exhaustive scan of the normalized pool: zero valued records match entity_id=US, concept=DGS10, period=2009-09-07. Empty observations are never rendered into a context.

**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `FRED_0009_4K` | 4K | 3991 | 0.974 | 41 | n/a | n/a | `2e3fd450e56f5e1d` |
| `FRED_0009_8K` | 8K | 8106 | 0.990 | 83 | n/a | n/a | `97cb49709fd2daaf` |
| `FRED_0009_16K` | 16K | 16146 | 0.986 | 164 | n/a | n/a | `f95bddc89a581ad8` |
| `FRED_0009_32K` | 32K | 32399 | 0.989 | 328 | n/a | n/a | `bc41047b3f8fed0f` |
| `FRED_0009_64K` | 64K | 64804 | 0.989 | 656 | n/a | n/a | `5af6004425f18437` |
| `FRED_0009_128K` | 128K | 129739 | 0.990 | 1312 | n/a | n/a | `f428d5d5bc308b88` |


### `FRED_0008` — FRED / TEMPORAL_VERSION

*Template:* `FRED_VINTAGE_SELECTION`

**Question.** Using only the FRED/ALFRED records supplied in the context, what value did FRED series PAYEMS ("All Employees, Total Nonfarm"), measured in Thousands of Persons, seasonally adjusted, monthly frequency show for the observation dated 2021-03-01 **as of the vintage date 2021-04-29** — that is, the value as it stood in the 2021-04-29 release, not as later revised? This observation was subsequently revised (later vintages report 2021-07-29 → 144057.0, 2022-06-29 → 144431.0, 2023-09-28 → 144328.0; the current vintage reports 144232.0), and those revised values are not the answer.

**Gold answer.** `144,120` (normalized `144120.0`, type NUMERIC, unit Thousands of Persons, tolerance ±0.5)

**Gold evidence.**

| role | record id | entity | field | period | value | unit |
|---|---|---|---|---|---|---|
| target_value | `FRED-PAYEMS-2021-03-01-2021-04-29-4117a714` | United States [US] | All Employees, Total Nonfarm (Seasonally Adjusted) [PAYEMS] | 2021-03-01 | 144120.0 | Thousands of Persons |


**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `FRED_0008_4K` | 4K | 4050 | 0.989 | 43 | 0.4980 | 1965–2069 | `3d9f2708cd58a743` |
| `FRED_0008_8K` | 8K | 8093 | 0.988 | 86 | 0.5033 | 4021–4125 | `836426fcd55eb9cd` |
| `FRED_0008_16K` | 16K | 16168 | 0.987 | 173 | 0.4996 | 8025–8129 | `47be1da1fc3fdde7` |
| `FRED_0008_32K` | 32K | 32396 | 0.989 | 347 | 0.4999 | 16143–16247 | `dae6b29adbc54e7d` |
| `FRED_0008_64K` | 64K | 64829 | 0.989 | 694 | 0.5007 | 32411–32515 | `b9ce8c18ff0fb0ee` |
| `FRED_0008_128K` | 128K | 129685 | 0.989 | 1388 | 0.4997 | 64753–64857 | `5d1e78d977cf9621` |


### `FRED_0003` — FRED / ENTITY_UNIT_BINDING

*Template:* `FRED_BASIS_BINDING`

**Question.** Using only the FRED records supplied in the context, report the value of FRED series PAYNSA ("All Employees, Total Nonfarm"), measured in Thousands of Persons, not seasonally adjusted, monthly frequency for United States on the observation dated 2020-03-01. The context also contains other series measuring the same quantity on that same date — PAYEMS (Seasonally Adjusted, Thousands of Persons) — which differ in seasonal adjustment, unit basis or geography; those are not the answer. Report the value for series PAYNSA exactly.

**Gold answer.** `149,952` (normalized `149952.0`, type NUMERIC, unit Thousands of Persons, tolerance ±0.5)

**Gold evidence.**

| role | record id | entity | field | period | value | unit |
|---|---|---|---|---|---|---|
| target_value | `FRED-PAYNSA-2020-03-01-latest-01e51bbe` | United States [US] | All Employees, Total Nonfarm (Not Seasonally Adjusted) [PAYNSA] | 2020-03-01 | 149952.0 | Thousands of Persons |


**Context variants.**

| instance | nominal | tokens | fill | records | target pos | evidence tokens | sha256 |
|---|---|---|---|---|---|---|---|
| `FRED_0003_4K` | 4K | 3992 | 0.975 | 43 | 0.4979 | 1940–2035 | `72d84d2b2de8ad32` |
| `FRED_0003_8K` | 8K | 8098 | 0.989 | 87 | 0.4976 | 3982–4077 | `b636fcab15bc4cc5` |
| `FRED_0003_16K` | 16K | 16184 | 0.988 | 173 | 0.5006 | 8054–8149 | `a0665d70c1def189` |
| `FRED_0003_32K` | 32K | 32344 | 0.987 | 346 | 0.4993 | 16103–16198 | `e3a6dcf5d283bfc7` |
| `FRED_0003_64K` | 64K | 64829 | 0.989 | 695 | 0.4999 | 32363–32458 | `01528b737bd23052` |
| `FRED_0003_128K` | 128K | 129649 | 0.989 | 1389 | 0.5001 | 64785–64880 | `5c3a66bb89e42253` |


## 9. Reproducibility

| field | value |
|---|---|
| schema version | 1.1.0 |
| config hash | `8c72bbbd80ade192` |
| seed | 20240817 |
| git commit | `2fe50bc2caec6f81d2fff6ca749abcd2dc8223b9` |
| tokenizer | `tiktoken:cl100k_base` |
| context lengths | 4K, 8K, 16K, 32K, 64K, 128K |
| target position | 0.5 ± 0.05 |
| min fill ratio | 0.95 |


Raw payloads under `data/raw/` are content-addressed by request URL, so re-running `fetch` is idempotent and the pilot can be regenerated byte-for-byte from the cached layer even after the live APIs change. Hashes of all outputs are in `data/manifests/fred_pilot_manifest.json`.

