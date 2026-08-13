# Experiment F -- Phi-4-mini-instruct Cross-Model Replication

## Executive Summary

Experiment F attempted all 3,000 frozen benchmark instances with `microsoft/Phi-4-mini-instruct` pinned to revision `cfbefacb99257ffa30c83adab238a50856ac3083`. Under the required BF16, greedy, no-offload, cached Transformers configuration on the RTX 4090, Phi completed the 4K, 8K, and 16K matched context conditions and reproducibly failed with CUDA OOM at 32K, 64K, and 82K. Runtime failures are not counted as factual inaccuracies.

Across successful factual runs, inaccuracy increased from 50.4% at 4K to 56.0% at 16K. The primary GEE over successful Phi outputs estimated OR=1.123 per true doubling of rendered Phi tokens, 95% CI [1.031, 1.222], p=0.00765. This supports increasing factual inaccuracy over the feasible 4K-16K range, but the full six-condition Phi factual trend is not estimable on this hardware because 1500 long-context attempts ended as runtime failures.

## Design

The frozen benchmark hash was `dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6` and the frozen deterministic grader hash was `d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8`. The benchmark contains 500 question families crossed with six matched context conditions: 4K, 8K, 16K, 32K, 64K, and 82K. Domains were balanced across SEC, FDA / Drugs@FDA, ClinicalTrials, and FRED / ALFRED. The primary outcome is binary: `CORRECT` is Accurate; every other successfully generated factual-task grade is Inaccurate. Runtime failures are analyzed separately.

## Phi Context Results

| context   |   successful_n |   runtime_failures |   accurate_count |   inaccurate_count |   accurate_rate |   inaccuracy_rate |   mean_rendered_phi_tokens |   mean_latency_seconds |
|:----------|---------------:|-------------------:|-----------------:|-------------------:|----------------:|------------------:|---------------------------:|-----------------------:|
| 4K        |            500 |                  0 |              248 |                252 |          0.4960 |            0.5040 |                  4195.3480 |                 0.3762 |
| 8K        |            500 |                  0 |              234 |                266 |          0.4680 |            0.5320 |                  8204.6300 |                 0.7015 |
| 16K       |            500 |                  0 |              220 |                280 |          0.4400 |            0.5600 |                 16220.2680 |                 1.4463 |
| 32K       |              0 |                500 |                0 |                  0 |        nan      |          nan      |                 32253.4820 |               nan      |
| 64K       |              0 |                500 |                0 |                  0 |        nan      |          nan      |                 64316.5400 |               nan      |
| 82K       |              0 |                500 |                0 |                  0 |        nan      |          nan      |                 80733.5660 |               nan      |

## Primary GEE

| analysis    | outcome    | formula                   | working_correlation   |   n_observations |   n_families | estimable   |   coefficient |   robust_se |   odds_ratio_per_2x_context |   odds_ratio_ci_low |   odds_ratio_ci_high |   p_value |
|:------------|:-----------|:--------------------------|:----------------------|-----------------:|-------------:|:------------|--------------:|------------:|----------------------------:|--------------------:|---------------------:|----------:|
| phi_primary | inaccurate | inaccurate ~ context_log2 | Exchangeable          |             1500 |          500 | True        |      0.115738 |   0.0433941 |                      1.1227 |             1.03116 |              1.22237 | 0.0076499 |

A +1 change in `log2(rendered_input_tokens)` represents a true doubling of rendered Phi input tokens.

## Complete-Case Sensitivity

| analysis      | outcome    |   n_observations |   n_families | estimable   | reason                                                            |   complete_families |
|:--------------|:-----------|-----------------:|-------------:|:------------|:------------------------------------------------------------------|--------------------:|
| complete_case | inaccurate |                0 |            0 | False       | no question families had successful outputs at all six conditions |                   0 |

## Paired McNemar Tests

| comparison   |   paired_n | estimable   |   event_rate_4K |   event_rate_comparison |   absolute_percentage_point_difference |   discordant_4K_accurate_comparison_inaccurate |   discordant_4K_inaccurate_comparison_accurate |   raw_p_value |   holm_adjusted_p_value |   significant_after_holm_0_05 | reason                                                 |
|:-------------|-----------:|:------------|----------------:|------------------------:|---------------------------------------:|-----------------------------------------------:|-----------------------------------------------:|--------------:|------------------------:|------------------------------:|:-------------------------------------------------------|
| 4K_vs_8K     |        500 | True        |           0.504 |                   0.532 |                                    2.8 |                                             47 |                                             33 |     0.145635  |               0.145635  |                             0 | nan                                                    |
| 4K_vs_16K    |        500 | True        |           0.504 |                   0.56  |                                    5.6 |                                             70 |                                             42 |     0.0104092 |               0.0208184 |                             1 | nan                                                    |
| 4K_vs_32K    |          0 | False       |         nan     |                 nan     |                                  nan   |                                            nan |                                            nan |   nan         |             nan         |                           nan | no families with successful outputs in both conditions |
| 4K_vs_64K    |          0 | False       |         nan     |                 nan     |                                  nan   |                                            nan |                                            nan |   nan         |             nan         |                           nan | no families with successful outputs in both conditions |
| 4K_vs_82K    |          0 | False       |         nan     |                 nan     |                                  nan   |                                            nan |                                            nan |   nan         |             nan         |                           nan | no families with successful outputs in both conditions |

## Exploratory Question-Type Results

| question_type         | context   |   n |   accurate_count |   inaccurate_count |   accurate_rate |   inaccuracy_rate |
|:----------------------|:----------|----:|-----------------:|-------------------:|----------------:|------------------:|
| DIRECT_RETRIEVAL      | 4K        | 100 |               89 |                 11 |          0.8900 |            0.1100 |
| ENTITY_UNIT_BINDING   | 4K        |  95 |               72 |                 23 |          0.7579 |            0.2421 |
| RETRIEVAL_CALCULATION | 4K        | 150 |               15 |                135 |          0.1000 |            0.9000 |
| TEMPORAL_VERSION      | 4K        |  55 |               46 |                  9 |          0.8364 |            0.1636 |
| UNANSWERABLE          | 4K        | 100 |               26 |                 74 |          0.2600 |            0.7400 |
| DIRECT_RETRIEVAL      | 8K        | 100 |               82 |                 18 |          0.8200 |            0.1800 |
| ENTITY_UNIT_BINDING   | 8K        |  95 |               68 |                 27 |          0.7158 |            0.2842 |
| RETRIEVAL_CALCULATION | 8K        | 150 |               13 |                137 |          0.0867 |            0.9133 |
| TEMPORAL_VERSION      | 8K        |  55 |               38 |                 17 |          0.6909 |            0.3091 |
| UNANSWERABLE          | 8K        | 100 |               33 |                 67 |          0.3300 |            0.6700 |
| DIRECT_RETRIEVAL      | 16K       | 100 |               81 |                 19 |          0.8100 |            0.1900 |
| ENTITY_UNIT_BINDING   | 16K       |  95 |               62 |                 33 |          0.6526 |            0.3474 |
| RETRIEVAL_CALCULATION | 16K       | 150 |               12 |                138 |          0.0800 |            0.9200 |
| TEMPORAL_VERSION      | 16K       |  55 |               35 |                 20 |          0.6364 |            0.3636 |
| UNANSWERABLE          | 16K       | 100 |               30 |                 70 |          0.3000 |            0.7000 |

## Exploratory Domain Results

| domain          | context   |   n |   accurate_count |   inaccurate_count |   accurate_rate |   inaccuracy_rate |
|:----------------|:----------|----:|-----------------:|-------------------:|----------------:|------------------:|
| CLINICAL_TRIALS | 4K        | 125 |               56 |                 69 |          0.4480 |            0.5520 |
| FDA             | 4K        | 125 |               55 |                 70 |          0.4400 |            0.5600 |
| FRED            | 4K        | 125 |               78 |                 47 |          0.6240 |            0.3760 |
| SEC             | 4K        | 125 |               59 |                 66 |          0.4720 |            0.5280 |
| CLINICAL_TRIALS | 8K        | 125 |               57 |                 68 |          0.4560 |            0.5440 |
| FDA             | 8K        | 125 |               48 |                 77 |          0.3840 |            0.6160 |
| FRED            | 8K        | 125 |               65 |                 60 |          0.5200 |            0.4800 |
| SEC             | 8K        | 125 |               64 |                 61 |          0.5120 |            0.4880 |
| CLINICAL_TRIALS | 16K       | 125 |               56 |                 69 |          0.4480 |            0.5520 |
| FDA             | 16K       | 125 |               47 |                 78 |          0.3760 |            0.6240 |
| FRED            | 16K       | 125 |               51 |                 74 |          0.4080 |            0.5920 |
| SEC             | 16K       | 125 |               66 |                 59 |          0.5280 |            0.4720 |

## Latency

| context   |   n_successful |   mean_seconds |   median_seconds |   sd_seconds |   p95_seconds |
|:----------|---------------:|---------------:|-----------------:|-------------:|--------------:|
| 4K        |            500 |         0.3762 |           0.3790 |       0.0329 |        0.4144 |
| 8K        |            500 |         0.7015 |           0.6994 |       0.0465 |        0.7644 |
| 16K       |            500 |         1.4463 |           1.4454 |       0.0648 |        1.5232 |
| 32K       |              0 |       nan      |         nan      |     nan      |      nan      |
| 64K       |              0 |       nan      |         nan      |     nan      |      nan      |
| 82K       |              0 |       nan      |         nan      |     nan      |      nan      |

## Three-Model Comparison

| comparison                                   | reference_model   | comparison_model   | term                              |   n_observations |   coefficient |   robust_se |   or_ratio |   or_ratio_ci_low |   or_ratio_ci_high |    p_value | terms                                                                |   df |   wald_chi2 |
|:---------------------------------------------|:------------------|:-------------------|:----------------------------------|-----------------:|--------------:|------------:|-----------:|------------------:|-------------------:|-----------:|:---------------------------------------------------------------------|-----:|------------:|
| Phi-4-mini-instruct vs Llama-3.2-3B-Instruct | llama32_3b        | phi4mini           | context_log2:C(model)[T.phi4mini] |             4498 |    -0.0920322 |   0.0494176 |   0.912076 |          0.827878 |           1.00484  | 0.0625555  | nan                                                                  |  nan |   nan       |
| Phi-4-mini-instruct vs Qwen3.5-2B            | qwen35_2b         | phi4mini           | context_log2:C(model)[T.phi4mini] |             4500 |    -0.126155  |   0.0468876 |   0.881478 |          0.804083 |           0.966323 | 0.00713263 | nan                                                                  |  nan |   nan       |
| joint_three_model_context_slope_interaction  | nan               | nan                | nan                               |             7498 |   nan         | nan         | nan        |        nan        |         nan        | 0.0316765  | context_log2:C(model)[T.qwen35_2b];context_log2:C(model)[T.phi4mini] |    2 |     6.90436 |

The three-model interaction analysis uses actual rendered token counts for each model and native prompt template. Because Phi has no successful factual observations at 32K, 64K, or 82K on this RTX 4090 under protocol settings, Phi slope comparisons are limited by non-overlapping long-context support and should be interpreted as available-case comparisons rather than a complete six-condition behavioral replication.

## Required Questions

1. Does Phi factual accuracy decline with increasing context? Yes over successful 4K-16K runs: accuracy changed from 49.6% at 4K to 44.0% at 16K. The 32K-82K factual outcomes were not observable because of runtime OOM.
2. Accurate/Inaccurate rates at each context condition are listed in the Phi Context Results table; long-context rates are NA because runtime failures are separate from factual outcomes.
3. Phi's OR per true doubling of rendered input was 1.123 over successful outputs.
4. The trend p-value was 0.00765.
5. Significant Holm-corrected paired comparisons: 4K_vs_16K.
6. Complete-case analysis: no question families had successful outputs at all six conditions.
7. Question-type patterns are exploratory and listed above.
8. Domain patterns are exploratory and listed above.
9. Phi-vs-Llama slope comparison is reported in the interaction table.
10. Phi-vs-Qwen slope comparison is reported in the interaction table.
11. The joint three-model context-slope test is reported in the interaction table.
12. The central degradation result replicated over Phi's feasible 4K-16K factual range, but a complete six-condition Phi behavioral replication was blocked by hardware/runtime OOM at 32K and above under the required configuration.

## Runtime and Deviations

Material deviation/blocker: Phi rendered prompts were within the model's declared context window, but the RTX 4090 could not execute the 32K, 64K, or 82K conditions with BF16, use_cache=True, no quantization, and no offloading. The protocol prohibited shortening, quantizing, or offloading to salvage these instances. Each runtime failure was kept separate from factual accuracy.

## Reproducibility Manifest Summary

```json
{
  "benchmark_hash": "dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6",
  "created_at_utc": "2026-08-13T09:07:38.818633+00:00",
  "experiment": "Experiment F -- Phi-4-mini-instruct Cross-Model Replication",
  "grader_hash": "d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8",
  "grading_summary": {
    "ambiguous_review": 0,
    "correct": 702,
    "counts_by_context": {
      "16K": {
        "ambiguous": 0,
        "correct": 220,
        "format_failure": 5,
        "gradable_n": 500,
        "grounded_inaccuracy": 82,
        "hallucinatory_inaccuracy": 193,
        "inaccurate": 280,
        "runtime_failures": 0
      },
      "32K": {
        "ambiguous": 0,
        "correct": 0,
        "format_failure": 0,
        "gradable_n": 0,
        "grounded_inaccuracy": 0,
        "hallucinatory_inaccuracy": 0,
        "inaccurate": 0,
        "runtime_failures": 500
      },
      "4K": {
        "ambiguous": 0,
        "correct": 248,
        "format_failure": 39,
        "gradable_n": 500,
        "grounded_inaccuracy": 29,
        "hallucinatory_inaccuracy": 184,
        "inaccurate": 252,
        "runtime_failures": 0
      },
      "64K": {
        "ambiguous": 0,
        "correct": 0,
        "format_failure": 0,
        "gradable_n": 0,
        "grounded_inaccuracy": 0,
        "hallucinatory_inaccuracy": 0,
        "inaccurate": 0,
        "runtime_failures": 500
      },
      "82K": {
        "ambiguous": 0,
        "correct": 0,
        "format_failure": 0,
        "gradable_n": 0,
        "grounded_inaccuracy": 0,
        "hallucinatory_inaccuracy": 0,
        "inaccurate": 0,
        "runtime_failures": 500
      },
      "8K": {
        "ambiguous": 0,
        "correct": 234,
        "format_failure": 20,
        "gradable_n": 500,
        "grounded_inaccuracy": 58,
        "hallucinatory_inaccuracy": 188,
        "inaccurate": 266,
        "runtime_failures": 0
      }
    },
    "error_type_counts": {
      "CALCULATION_ERROR": 24,
      "CORRECT": 702,
      "FAILED_TO_ABSTAIN": 165,
      "FORMAT_FAILURE": 64,
      "UNNECESSARY_ABSTENTION": 3,
      "UNSUPPORTED_VALUE": 400,
      "WRONG_ENTITY": 64,
      "WRONG_FIELD": 7,
      "WRONG_PERIOD": 18,
      "WRONG_SERIES_VARIANT": 2,
      "WRONG_UNIT": 5,
      "WRONG_VERSION": 46
    },
    "format_failure": 64,
    "grounded_inaccuracy": 169,
    "hallucinatory_inaccuracy": 565,
    "inaccurate": 798,
    "runtime_failures": 1500,
    "scored_results_sha256": "a5c20e6c3318a7ec75a1dcfd78cb4f62b4765ebd56cc7f47dbba412df1f509e6",
    "successful_responses_graded": 1500
  },
  "inference_summary": {
    "attempted": 3000,
    "cuda_oom_failures": 1500,
    "expected_instances": 3000,
    "failed": 1500,
    "failure_breakdown": {
      "CUDA_OOM": 1500
    },
    "integrity": {
      "attempted": 3000,
      "dataset_hash": "dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6",
      "expected_instances": 3000,
      "failed": 1500,
      "failure_breakdown": {
        "CUDA_OOM": 1500
      },
      "hit_128_outputs": 0,
      "malformed_outputs": 64,
      "no_grading_or_statistical_analysis_performed": true,
      "passed": true,
      "problems": [],
      "source_dataset_hash_unchanged": true,
      "successful": 1500,
      "thinking_trace_outputs": 0
    },
    "mode": "full",
    "no_grading_or_statistical_analysis_performed": true,
    "run_id": "phi4mini_500f_6ctx_v1",
    "structural_output_diagnostics": {
      "by_context": [
        {
          "attempted": 500,
          "context_length": "4K",
          "cuda_oom_count": 0,
          "degenerate_outputs": 0,
          "hit_128": 0,
          "malformed_outputs": 39,
          "max_input_tokens": 4313,
          "max_peak_allocated_vram_gib": 9.499712944030762,
          "max_peak_reserved_vram_gib": 10.10546875,
          "mean_generated_tokens": 7.736,
          "mean_input_tokens": 4195.348,
          "mean_latency_seconds": 0.3761752591133118,
          "mean_peak_allocated_vram_gib": 9.048765339851379,
          "mean_peak_reserved_vram_gib": 9.62423046875,
          "median_generated_tokens": 8.0,
          "median_input_tokens": 4195.0,
          "median_latency_seconds": 0.37895900942385197,
          "min_input_tokens": 4092,
          "p95_latency_seconds": 0.41439936370588837,
          "runtime_failed": 0,
          "runtime_successful": 500,
          "sd_input_tokens": 38.07906151484965,
          "std_latency_seconds": 0.03290388892888151,
          "thinking_trace_outputs": 0,
          "total_generation_seconds": 188.08762955665588,
          "usable_answer_outputs": 461
        },
        {
          "attempted": 500,
          "context_length": "8K",
          "cuda_oom_count": 0,
          "degenerate_outputs": 0,
          "hit_128": 0,
          "malformed_outputs": 20,
          "max_input_tokens": 8364,
          "max_peak_allocated_vram_gib": 10.9238600730896,
          "max_peak_reserved_vram_gib": 12.052734375,
          "mean_generated_tokens": 7.85,
          "mean_input_tokens": 8204.63,
          "mean_latency_seconds": 0.7015118780452758,
          "mean_peak_allocated_vram_gib": 10.853439500808715,
          "mean_peak_reserved_vram_gib": 11.94623828125,
          "median_generated_tokens": 8.0,
          "median_input_tokens": 8199.0,
          "median_latency_seconds": 0.6993587221950293,
          "min_input_tokens": 8085,
          "p95_latency_seconds": 0.7643730983138085,
          "runtime_failed": 0,
          "runtime_successful": 500,
          "sd_input_tokens": 49.59916586505279,
          "std_latency_seconds": 0.04647108204541289,
          "thinking_trace_outputs": 0,
          "total_generation_seconds": 350.7559390226379,
          "usable_answer_outputs": 480
        },
        {
          "attempted": 500,
          "context_length": "16K",
          "cuda_oom_count": 0,
          "degenerate_outputs": 0,
          "hit_128": 0,
          "malformed_outputs": 5,
          "max_input_tokens": 16469,
          "max_peak_allocated_vram_gib": 14.580068588256836,
          "max_peak_reserved_vram_gib": 16.75,
          "mean_generated_tokens": 7.876,
          "mean_input_tokens": 16220.268,
          "mean_latency_seconds": 1.4463259362187237,
          "mean_peak_allocated_vram_gib": 14.465310623168945,
          "mean_peak_reserved_vram_gib": 16.59888671875,
          "median_generated_tokens": 8.0,
          "median_input_tokens": 16207.5,
          "median_latency_seconds": 1.445418224669993,
          "min_input_tokens": 16043,
          "p95_latency_seconds": 1.5231887229718268,
          "runtime_failed": 0,
          "runtime_successful": 500,
          "sd_input_tokens": 75.06638462188252,
          "std_latency_seconds": 0.06479402255707167,
          "thinking_trace_outputs": 0,
          "total_generation_seconds": 723.1629681093618,
          "usable_answer_outputs": 495
        },
        {
          "attempted": 500,
          "context_length": "32K",
          "cuda_oom_count": 500,
          "degenerate_outputs": 0,
          "hit_128": 0,
          "malformed_outputs": 0,
          "max_input_tokens": null,
          "max_peak_allocated_vram_gib": null,
          "max_peak_reserved_vram_gib": null,
          "mean_generated_tokens": null,
          "mean_input_tokens": null,
          "mean_latency_seconds": null,
          "mean_peak_allocated_vram_gib": null,
          "mean_peak_reserved_vram_gib": null,
          "median_generated_tokens": null,
          "median_input_tokens": null,
          "median_latency_seconds": null,
          "min_input_tokens": null,
          "p95_latency_seconds": null,
          "runtime_failed": 500,
          "runtime_successful": 0,
          "sd_input_tokens": null,
          "std_latency_seconds": null,
          "thinking_trace_outputs": 0,
          "total_generation_seconds": 0,
          "usable_answer_outputs": 0
        },
        {
          "attempted": 500,
          "context_length": "64K",
          "cuda_oom_count": 500,
          "degenerate_outputs": 0,
          "hit_128": 0,
          "malformed_outputs": 0,
          "max_input_tokens": null,
          "max_peak_allocated_vram_gib": null,
          "max_peak_reserved_vram_gib": null,
          "mean_generated_tokens": null,
          "mean_input_tokens": null,
          "mean_latency_seconds": null,
          "mean_peak_allocated_vram_gib": null,
          "mean_peak_reserved_vram_gib": null,
          "median_generated_tokens": null,
          "median_input_tokens": null,
          "median_latency_seconds": null,
          "min_input_tokens": null,
          "p95_latency_seconds": null,
          "runtime_failed": 500,
          "runtime_successful": 0,
          "sd_input_tokens": null,
          "std_latency_seconds": null,
          "thinking_trace_outputs": 0,
          "total_generation_seconds": 0,
          "usable_answer_outputs": 0
        },
        {
          "attempted": 500,
          "context_length": "82K",
          "cuda_oom_count": 500,
          "degenerate_outputs": 0,
          "hit_128": 0,
          "malformed_outputs": 0,
          "max_input_tokens": null,
          "max_peak_allocated_vram_gib": null,
          "max_peak_reserved_vram_gib": null,
          "mean_generated_tokens": null,
          "mean_input_tokens": null,
          "mean_latency_seconds": null,
          "mean_peak_allocated_vram_gib": null,
          "mean_peak_reserved_vram_gib": null,
          "median_generated_tokens": null,
          "median_input_tokens": null,
          "median_latency_seconds": null,
          "min_input_tokens": null,
          "p95_latency_seconds": null,
          "runtime_failed": 500,
          "runtime_successful": 0,
          "sd_input_tokens": null,
          "std_latency_seconds": null,
          "thinking_trace_outputs": 0,
          "total_generation_seconds": 0,
          "usable_answer_outputs": 0
        }
      ],
      "overall": {
        "attempted": 3000,
        "cuda_oom_count": 1500,
        "degenerate_outputs": 0,
        "hit_128": 0,
        "malformed_outputs": 64,
        "malformed_patterns": {
          "missing_answer_prefix": 64,
          "usable_answer_line": 1436
        },
        "runtime_failed": 1500,
        "runtime_successful": 1500,
        "thinking_trace_outputs": 0,
        "usable_answer_outputs": 1436
      }
    },
    "successful": 1500,
    "timing_by_context": [
      {
        "attempted": 500,
        "context_length": "4K",
        "cuda_oom_count": 0,
        "degenerate_outputs": 0,
        "hit_128": 0,
        "malformed_outputs": 39,
        "max_input_tokens": 4313,
        "max_peak_allocated_vram_gib": 9.499712944030762,
        "max_peak_reserved_vram_gib": 10.10546875,
        "mean_generated_tokens": 7.736,
        "mean_input_tokens": 4195.348,
        "mean_latency_seconds": 0.3761752591133118,
        "mean_peak_allocated_vram_gib": 9.048765339851379,
        "mean_peak_reserved_vram_gib": 9.62423046875,
        "median_generated_tokens": 8.0,
        "median_input_tokens": 4195.0,
        "median_latency_seconds": 0.37895900942385197,
        "min_input_tokens": 4092,
        "p95_latency_seconds": 0.41439936370588837,
        "runtime_failed": 0,
        "runtime_successful": 500,
        "sd_input_tokens": 38.07906151484965,
        "std_latency_seconds": 0.03290388892888151,
        "thinking_trace_outputs": 0,
        "total_generation_seconds": 188.08762955665588,
        "usable_answer_outputs": 461
      },
      {
        "attempted": 500,
        "context_length": "8K",
        "cuda_oom_count": 0,
        "degenerate_outputs": 0,
        "hit_128": 0,
        "malformed_outputs": 20,
        "max_input_tokens": 8364,
        "max_peak_allocated_vram_gib": 10.9238600730896,
        "max_peak_reserved_vram_gib": 12.052734375,
        "mean_generated_tokens": 7.85,
        "mean_input_tokens": 8204.63,
        "mean_latency_sec
```
