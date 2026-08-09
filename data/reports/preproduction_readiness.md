# Pre-production readiness

_Generated 2026-08-09T18:16:43Z · git `2fe50bc2caec`_

> **Scope.** Dataset generation and audit preparation only. No LLM has been run, no semantic judge exists, no hallucination scoring or statistical analysis has been performed, and neither the 100-family nor the 500-family dataset has been generated.

## 1. Verdict

**The pipeline is technically ready; 2 non-technical gates remain open.**

- FRED adapter: **IMPLEMENTED_AND_VALIDATED**, running on the `fredgraph_csv` backend (20,925 normalized records).
- FRED pilot: **10 families → 60 instances**, 0 unavailable variants.
- Validation: **22/22 checks passed**, 0 critical failures. Rules unchanged.
- Human audit: **PENDING_HUMAN_REVIEW** (12 families prepared).
- Tokenizer: **READY_CONFIG_ONLY_SWITCH** — change `tokenizer.id`, no code change.

## 2. FRED adapter

| property | value |
|---|---|
| status | IMPLEMENTED_AND_VALIDATED |
| backend in use | `fredgraph_csv` (keyless first-party CSV) |
| backend with API key | `fred_api` (automatic when FRED_API_KEY is set) |
| first-party sources only | True |
| third-party scraping | False |
| requests / payloads | 48 / 48 |
| raw records | 27,085 |
| request errors | 0 |
| normalized records | 20,925 |
| series in catalog | 23 |
| vintage series | GDP, GDPC1, PAYEMS, UNRATE, CPIAUCSL |
| vintage dates | 2021-04-29, 2021-07-29, 2022-06-29, 2023-09-28, 2025-03-27 |


Endpoints used (all Federal Reserve Bank of St. Louis):

- `https://fred.stlouisfed.org/graph/fredgraph.csv (current vintage)`
- `https://alfred.stlouisfed.org/graph/alfredgraph.csv (vintage/ALFRED)`
- `https://api.stlouisfed.org/fred (used automatically when FRED_API_KEY is set)`

| record type | count |
|---|---|
| fred_observation | 19,470 |
| fred_vintage_observation | 1,052 |
| observation_missing | 403 |


> **Metadata provenance.** Descriptive series attributes (title, units, frequency, seasonal adjustment) are operator-supplied from the config catalog while running keyless, and every record is stamped metadata_source=operator_catalog. Observation values, dates and vintages always come from the API. Setting FRED_API_KEY sources the attributes from /fred/series with no code change.

## 3. FRED pilot

| property | value |
|---|---|
| config | `config/fred_pilot.yaml` (hash `8c72bbbd80ade192`, seed 20240817) |
| question families | 10 |
| context instances | 60 |
| answerable / unanswerable | 8 / 2 |
| unavailable variants | 0 |
| context lengths | 4K, 8K, 16K, 32K, 64K, 128K |


| question type | families |
|---|---|
| DIRECT_RETRIEVAL | 2 |
| ENTITY_UNIT_BINDING | 2 |
| RETRIEVAL_CALCULATION | 3 |
| TEMPORAL_VERSION | 1 |
| UNANSWERABLE | 2 |


| nominal | instances | min tokens | median | max | median fill |
|---|---|---|---|---|---|
| 4K | 10 | 3,988 | 4,000 | 4,050 | 0.9766 |
| 8K | 10 | 8,022 | 8,057 | 8,106 | 0.9835 |
| 16K | 10 | 16,130 | 16,174 | 16,203 | 0.9872 |
| 32K | 10 | 32,344 | 32,389 | 32,438 | 0.9884 |
| 64K | 10 | 64,788 | 64,829 | 64,846 | 0.9892 |
| 128K | 10 | 129,609 | 129,661 | 129,757 | 0.9892 |


**Target-evidence position:** n=48, min=0.4907, median=0.5001, max=0.5112, mean=0.5008 (target 0.50 ± 0.05).

## 4. Validation

FRED pilot: **22/22 checks passed**, critical failures: 0. Failed checks: none.

Existing 32-family pilot (unchanged, re-reported for reference): 22/22 passed.

> Validation rules were not weakened for FRED; the same 22 checks ran.

## 5. Distractor taxonomy — before and after FRED

| distractor type | existing pilot | share | FRED pilot | share | combined | share |
|---|---|---|---|---|---|---|
| `OTHER_SAME_DOMAIN` | 38,500 | 54.88% | 10,547 | 39.18% | 49,047 | 50.53% |
| `WRONG_ENTITY` | 15,546 | 22.16% | 149 | 0.55% | 15,695 | 16.17% |
| `WRONG_FIELD` | 8,533 | 12.16% | 6,897 | 25.62% | 15,430 | 15.90% |
| `WRONG_PERIOD` | 4,776 | 6.81% | 7,913 | 29.40% | 12,689 | 13.07% |
| `NEAR_MATCH_VALUE` | 2,689 | 3.83% | 1,219 | 4.53% | 3,908 | 4.03% |
| `WRONG_UNIT` | 48 | 0.07% | 118 | 0.44% | 166 | 0.17% |
| `WRONG_VERSION` | 57 | 0.08% | 75 | 0.28% | 132 | 0.14% |


### Why placement share is the wrong lens for the scarce classes

A single target can be surrounded by thousands of WRONG_PERIOD records — every other date of the same series qualifies — but by at most a handful of WRONG_VERSION records, because a revision conflict only exists where the source actually restated the value. Raw share therefore measures pool geometry, not interference quality. The useful measure is **how many families contain the class at all**, at the shortest length where every record is close to the evidence:

| distractor type | existing pilot families @4K | % | FRED families @4K | % |
|---|---|---|---|---|
| `NEAR_MATCH_VALUE` | 18/32 | 56% | 3/10 | 30% |
| `OTHER_SAME_DOMAIN` | 32/32 | 100% | 10/10 | 100% |
| `WRONG_ENTITY` | 30/32 | 94% | 1/10 | 10% |
| `WRONG_FIELD` | 31/32 | 97% | 9/10 | 90% |
| `WRONG_PERIOD` | 17/32 | 53% | 10/10 | 100% |
| `WRONG_UNIT` | 4/32 | 12% | 9/10 | 90% |
| `WRONG_VERSION` | 2/32 | 6% | 3/10 | 30% |


### The two classes this phase targeted

- **`WRONG_VERSION`** — placements: 57 (existing) → 75 (FRED). Family coverage at 4K: 2/32 (6%) → 3/10 (30%).
- **`WRONG_UNIT`** — placements: 48 (existing) → 118 (FRED). Family coverage at 4K: 4/32 (12%) → 9/10 (90%).

## 6. Human-audit package

**Status: PENDING_HUMAN_REVIEW** — 12 families, 15 checklist items each, all left unticked by design.

- Directory: `data/audit`
- Index: `data/audit/audit_index.md` (and `data/audit/audit_index.json`)
- Domains audited: SEC, FDA, CLINICAL_TRIALS, FRED

| family | domain | type | answerable | dataset | artifact | 4K context | 128K context |
|---|---|---|---|---|---|---|---|
| `CT_0001` | CLINICAL_TRIALS | DIRECT_RETRIEVAL | yes | pilot | `CT_0001.md` | `CT_0001_4K.txt` | `CT_0001_128K.txt` |
| `FDA_0003` | FDA | ENTITY_UNIT_BINDING | yes | pilot | `FDA_0003.md` | `FDA_0003_4K.txt` | `FDA_0003_128K.txt` |
| `FRED_0007` | FRED | RETRIEVAL_CALCULATION | yes | fred_pilot | `FRED_0007.md` | `FRED_0007_4K.txt` | `FRED_0007_128K.txt` |
| `SEC_0006` | SEC | TEMPORAL_VERSION | yes | pilot | `SEC_0006.md` | `SEC_0006_4K.txt` | `SEC_0006_128K.txt` |
| `CT_0007` | CLINICAL_TRIALS | UNANSWERABLE | **no** | pilot | `CT_0007.md` | `CT_0007_4K.txt` | `CT_0007_128K.txt` |
| `CT_0008` | CLINICAL_TRIALS | UNANSWERABLE | **no** | pilot | `CT_0008.md` | `CT_0008_4K.txt` | `CT_0008_128K.txt` |
| `FDA_0001` | FDA | DIRECT_RETRIEVAL | yes | pilot | `FDA_0001.md` | `FDA_0001_4K.txt` | `FDA_0001_128K.txt` |
| `FRED_0003` | FRED | ENTITY_UNIT_BINDING | yes | fred_pilot | `FRED_0003.md` | `FRED_0003_4K.txt` | `FRED_0003_128K.txt` |
| `SEC_0004` | SEC | RETRIEVAL_CALCULATION | yes | pilot | `SEC_0004.md` | `SEC_0004_4K.txt` | `SEC_0004_128K.txt` |
| `FDA_0006` | FDA | TEMPORAL_VERSION | yes | pilot | `FDA_0006.md` | `FDA_0006_4K.txt` | `FDA_0006_128K.txt` |
| `FRED_0001` | FRED | DIRECT_RETRIEVAL | yes | fred_pilot | `FRED_0001.md` | `FRED_0001_4K.txt` | `FRED_0001_128K.txt` |
| `SEC_0003` | SEC | ENTITY_UNIT_BINDING | yes | pilot | `SEC_0003.md` | `SEC_0003_4K.txt` | `SEC_0003_128K.txt` |


## 7. Tokenizer readiness

**Status: READY_CONFIG_ONLY_SWITCH**

Change exactly one field — **`tokenizer.id`** — in `config/preproduction.yaml` and `config/production.yaml`.

| property | value |
|---|---|
| current (placeholder) | `tiktoken:cl100k_base` |
| id format | `backend:name` |
| code changes required | none |
| after changing it | re-run build-contexts (and validate); question families are unaffected |
| safety guard | allow_fallback is false, so an unavailable tokenizer raises rather than silently mis-measuring every context length. |


Supported backends:

- **`tiktoken`** — tiktoken:<encoding>, e.g. tiktoken:cl100k_base, tiktoken:o200k_base
- **`hf`** — hf:<model-id>, e.g. hf:meta-llama/Llama-3.1-8B (needs the 'hf' extra)
- **`whitespace`** — whitespace:v1 - approximate, offline testing only

> **Verified.** Three backends were driven through the real context builder by changing only tokenizer.id: cl100k_base, o200k_base and whitespace:v1 each produced valid nested contexts, each instance recorded the tokenizer actually used, and the gold answers were identical across all three.

## 8. Configuration status

### Pre-production (100 families)

**Status: PREPARED_AND_VALIDATED_NOT_GENERATED** · `config/preproduction.yaml` · config hash `6e5a10fbd10145b4`

| domain | families |
|---|---|
| CLINICAL_TRIALS | 25 |
| FDA | 25 |
| FRED | 25 |
| SEC | 25 |
| **total** | **100** |


| question type | families | share |
|---|---|---|
| DIRECT_RETRIEVAL | 20 | 20% |
| ENTITY_UNIT_BINDING | 15 | 15% |
| RETRIEVAL_CALCULATION | 30 | 30% |
| TEMPORAL_VERSION | 15 | 15% |
| UNANSWERABLE | 20 | 20% |


> Explicit question_type_counts are used because 30% of 25 is 7.5: no per-domain rounding of the fractional mix reaches the global target, so counts are stated per domain and chosen to sum exactly to 20/30/15/15/20.

### Production (500 families)

**Status: PREPARED_NOT_GENERATED** · `config/production.yaml` · config hash `c3fa532bc2ceddd8`

| domain | families |
|---|---|
| CLINICAL_TRIALS | 125 |
| FDA | 125 |
| FRED | 125 |
| SEC | 125 |
| **total** | **500** |


| question type | families | share |
|---|---|---|
| DIRECT_RETRIEVAL | 100 | 20% |
| ENTITY_UNIT_BINDING | 76 | 15% |
| RETRIEVAL_CALCULATION | 148 | 30% |
| TEMPORAL_VERSION | 76 | 15% |
| UNANSWERABLE | 100 | 20% |


World Bank removed: **True** · fifth-domain EXTENSION slot retained: **True**

## 9. Preserved artifacts

The previously validated 32-family pilot was not modified. Retrieval records are now written per config name, so this phase could not overwrite the earlier provenance file.

- `data/pilot/`
- `data/reports/pilot_report.md`
- `data/reports/pilot_validation.json`
- `data/manifests/pilot_manifest.json`
- `data/manifests/source_retrievals.json`

## 10. Blockers and outstanding items

| severity | item | detail |
|---|---|---|
| BLOCKING | Human audit not yet performed | 12 families are prepared in data/audit with unticked checklists. Nothing automated can decide whether the questions read naturally or whether the 128K contexts are meaningfully harder than the 4K ones. |
| BLOCKING | Target tokenizer not selected | tokenizer.id is still the placeholder tiktoken:cl100k_base. Token counts are the independent variable, so this must match the model under test before any dataset intended for the experiment is generated. |
| ADVISORY | WRONG_VERSION coverage remains narrow | Present in 3/10 FRED families and 2/32 existing-pilot families at 4K. It is structurally scarce: a revision conflict only exists where a source genuinely restated a value. Widening FRED's vintage_series/vintage_dates to more genuinely revised series would raise it; adding vintages for never-revised series would only pad the count and is deliberately not done. |
| ADVISORY | FRED running keyless | Observations and vintages come from the API, but descriptive series attributes are operator-supplied from the config catalog and stamped metadata_source=operator_catalog. Setting FRED_API_KEY sources them from /fred/series with no code change. |
| RESOLVED | World Bank removed from the active experiment | Its Indicators API returned HTTP 502 for date-range queries, hung on large result sets, and eventually refused traffic. It is absent from both the pre-production and production configs; the adapter and its data are retained so earlier datasets stay reproducible. |


