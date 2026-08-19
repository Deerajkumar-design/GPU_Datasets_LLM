# Experiment C Final Statistical Analysis

## Integrity

- input CSV: `data/grading_experiment_c_final_v1/final_scored_results.csv`
- immutable JSONL hash: `6fdfaa035b5da2211e813353916902c871e783ecfa993615db672f62bcb8e327`
- rows: `500`
- families: `100`
- bootstrap seed: `20260810`
- bootstrap replicates: `5000`

## Primary Results

| context   |   N |   correct_count |   accuracy |   accuracy_ci_low |   accuracy_ci_high |   hallucination_count |   hallucination_rate |   hallucination_ci_low |   hallucination_ci_high |   incorrect_non_hallucination_count |   failed_to_abstain_count |   unnecessary_abstention_count |   mean_latency |
|:----------|----:|----------------:|-----------:|------------------:|-------------------:|----------------------:|---------------------:|-----------------------:|------------------------:|------------------------------------:|--------------------------:|-------------------------------:|---------------:|
| 4K        | 100 |              57 |      0.570 |             0.470 |              0.670 |                    35 |                0.350 |                  0.260 |                   0.440 |                                   8 |                        10 |                              1 |          0.317 |
| 8K        | 100 |              50 |      0.500 |             0.400 |              0.600 |                    38 |                0.380 |                  0.280 |                   0.480 |                                  12 |                        10 |                              1 |          0.601 |
| 16K       | 100 |              43 |      0.430 |             0.330 |              0.530 |                    33 |                0.330 |                  0.240 |                   0.420 |                                  24 |                        10 |                              2 |          1.212 |
| 32K       | 100 |              38 |      0.380 |             0.290 |              0.480 |                    37 |                0.370 |                  0.280 |                   0.460 |                                  25 |                        14 |                              1 |          2.842 |
| 64K       | 100 |              27 |      0.270 |             0.190 |              0.360 |                    42 |                0.420 |                  0.320 |                   0.520 |                                  31 |                        19 |                              1 |          7.824 |

## Primary Hallucination Trend Model

- method: GEE logistic regression clustered by question_family_id with exchangeable working correlation
- coefficient for context_log2: `0.0558248`
- SE: `0.0466012`
- odds ratio per 2x context increase: `1.05741`
- 95% CI for OR: `[0.965111, 1.15854]`
- p-value: `0.230945`
- status: `fit_completed`, converged: `True`

Interpretation: each doubling of context length was associated with `1.057x` the odds of hallucination.

## Accuracy Trend Model

- coefficient for context_log2: `-0.301241`
- SE: `0.0594604`
- odds ratio per 2x context increase: `0.739899`
- 95% CI for OR: `[0.658506, 0.831353]`
- p-value: `4.05724e-07`
- status: `fit_completed`, converged: `True`

## Paired Comparisons

| outcome            | comparison   |   discordant_4k_false_comparison_true |   discordant_4k_true_comparison_false |   absolute_paired_rate_difference |   raw_p_value |   holm_adjusted_p_value |
|:-------------------|:-------------|--------------------------------------:|--------------------------------------:|----------------------------------:|--------------:|------------------------:|
| hallucination_int  | 4K_vs_8K     |                                     4 |                                     1 |                              0.03 |     0.375     |                1        |
| hallucination_int  | 4K_vs_16K    |                                     3 |                                     5 |                             -0.02 |     0.7266    |                1        |
| hallucination_int  | 4K_vs_32K    |                                     8 |                                     6 |                              0.02 |     0.7905    |                1        |
| hallucination_int  | 4K_vs_64K    |                                    13 |                                     6 |                              0.07 |     0.1671    |                0.6683   |
| answer_correct_int | 4K_vs_8K     |                                     3 |                                    10 |                             -0.07 |     0.09229   |                0.09229  |
| answer_correct_int | 4K_vs_16K    |                                     3 |                                    17 |                             -0.14 |     0.002577  |                0.005154 |
| answer_correct_int | 4K_vs_32K    |                                     5 |                                    24 |                             -0.19 |     0.0005461 |                0.001638 |
| answer_correct_int | 4K_vs_64K    |                                     5 |                                    35 |                             -0.3  |     1.383e-06 |                5.53e-06 |

Holm-adjusted paired comparisons below 0.05: hallucination `[]`, accuracy `['4K_vs_16K', '4K_vs_32K', '4K_vs_64K']`.

## Family-Level Transitions

`{('answer_correct_int', 'first_true_at_16K'): 1, ('answer_correct_int', 'first_true_at_32K'): 2, ('answer_correct_int', 'first_true_at_64K'): 2, ('answer_correct_int', 'never_true'): 35, ('answer_correct_int', 'non_monotonic'): 3, ('answer_correct_int', 'true_all_contexts'): 15, ('answer_correct_int', 'true_at_shorter_recovered_later'): 42, ('hallucination_int', 'first_true_at_32K'): 4, ('hallucination_int', 'first_true_at_64K'): 8, ('hallucination_int', 'first_true_at_8K'): 1, ('hallucination_int', 'never_true'): 47, ('hallucination_int', 'non_monotonic'): 5, ('hallucination_int', 'true_all_contexts'): 25, ('hallucination_int', 'true_at_shorter_recovered_later'): 10}`

## Exploratory Subgroups

Question-type and domain subgroup tables are saved as CSV files. Interaction GEE models are saved in `mixed_model_results.json`; these are exploratory and not interpreted as confirmatory tests.

## Error-Type Evolution

| context   | error_type             |   count |   percent |
|:----------|:-----------------------|--------:|----------:|
| 4K        | CORRECT                |      57 |     0.570 |
| 4K        | UNSUPPORTED_VALUE      |      25 |     0.250 |
| 4K        | FAILED_TO_ABSTAIN      |      10 |     0.100 |
| 4K        | WRONG_ENTITY           |       1 |     0.010 |
| 4K        | WRONG_PERIOD           |       1 |     0.010 |
| 4K        | WRONG_VERSION          |       1 |     0.010 |
| 4K        | WRONG_FIELD            |       2 |     0.020 |
| 4K        | CALCULATION_ERROR      |       1 |     0.010 |
| 4K        | UNNECESSARY_ABSTENTION |       1 |     0.010 |
| 4K        | WRONG_UNIT             |       1 |     0.010 |
| 4K        | WRONG_SERIES_VARIANT   |       0 |     0.000 |
| 8K        | CORRECT                |      50 |     0.500 |
| 8K        | UNSUPPORTED_VALUE      |      28 |     0.280 |
| 8K        | FAILED_TO_ABSTAIN      |      10 |     0.100 |
| 8K        | WRONG_ENTITY           |       2 |     0.020 |
| 8K        | WRONG_PERIOD           |       0 |     0.000 |
| 8K        | WRONG_VERSION          |       1 |     0.010 |
| 8K        | WRONG_FIELD            |       3 |     0.030 |
| 8K        | CALCULATION_ERROR      |       1 |     0.010 |
| 8K        | UNNECESSARY_ABSTENTION |       1 |     0.010 |
| 8K        | WRONG_UNIT             |       2 |     0.020 |
| 8K        | WRONG_SERIES_VARIANT   |       2 |     0.020 |
| 16K       | CORRECT                |      43 |     0.430 |
| 16K       | UNSUPPORTED_VALUE      |      23 |     0.230 |
| 16K       | FAILED_TO_ABSTAIN      |      10 |     0.100 |
| 16K       | WRONG_ENTITY           |       8 |     0.080 |
| 16K       | WRONG_PERIOD           |       4 |     0.040 |
| 16K       | WRONG_VERSION          |       5 |     0.050 |
| 16K       | WRONG_FIELD            |       2 |     0.020 |
| 16K       | CALCULATION_ERROR      |       2 |     0.020 |
| 16K       | UNNECESSARY_ABSTENTION |       2 |     0.020 |
| 16K       | WRONG_UNIT             |       1 |     0.010 |
| 16K       | WRONG_SERIES_VARIANT   |       0 |     0.000 |
| 32K       | CORRECT                |      38 |     0.380 |
| 32K       | UNSUPPORTED_VALUE      |      23 |     0.230 |
| 32K       | FAILED_TO_ABSTAIN      |      14 |     0.140 |
| 32K       | WRONG_ENTITY           |      11 |     0.110 |
| 32K       | WRONG_PERIOD           |       5 |     0.050 |
| 32K       | WRONG_VERSION          |       3 |     0.030 |
| 32K       | WRONG_FIELD            |       1 |     0.010 |
| 32K       | CALCULATION_ERROR      |       3 |     0.030 |
| 32K       | UNNECESSARY_ABSTENTION |       1 |     0.010 |
| 32K       | WRONG_UNIT             |       1 |     0.010 |
| 32K       | WRONG_SERIES_VARIANT   |       0 |     0.000 |
| 64K       | CORRECT                |      27 |     0.270 |
| 64K       | UNSUPPORTED_VALUE      |      23 |     0.230 |
| 64K       | FAILED_TO_ABSTAIN      |      19 |     0.190 |
| 64K       | WRONG_ENTITY           |       9 |     0.090 |
| 64K       | WRONG_PERIOD           |       7 |     0.070 |
| 64K       | WRONG_VERSION          |       5 |     0.050 |
| 64K       | WRONG_FIELD            |       4 |     0.040 |
| 64K       | CALCULATION_ERROR      |       3 |     0.030 |
| 64K       | UNNECESSARY_ABSTENTION |       1 |     0.010 |
| 64K       | WRONG_UNIT             |       1 |     0.010 |
| 64K       | WRONG_SERIES_VARIANT   |       1 |     0.010 |

## Latency

| context   |   N |   mean_latency |   median_latency |   std_latency |   p90_latency |   p95_latency |   total_latency |   mean_input_tokens |   mean_generated_tokens |
|:----------|----:|---------------:|-----------------:|--------------:|--------------:|--------------:|----------------:|--------------------:|------------------------:|
| 4K        | 100 |          0.317 |            0.315 |         0.021 |         0.347 |         0.350 |          31.732 |            4265.730 |                   8.470 |
| 8K        | 100 |          0.601 |            0.598 |         0.023 |         0.635 |         0.636 |          60.078 |            8329.190 |                   8.420 |
| 16K       | 100 |          1.212 |            1.210 |         0.029 |         1.256 |         1.260 |         121.216 |           16440.020 |                   8.310 |
| 32K       | 100 |          2.842 |            2.835 |         0.049 |         2.907 |         2.935 |         284.238 |           32671.020 |                   8.370 |
| 64K       | 100 |          7.824 |            7.811 |         0.074 |         7.936 |         7.953 |         782.390 |           65120.480 |                   8.300 |

## Sensitivity Checks

- excluding UNANSWERABLE hallucination OR per doubling: `0.948269`, p=`0.240297`
- excluding manual adjudication hallucination OR per doubling: `1.05762`, p=`0.229787`

## Discipline

No grading labels were changed, no inference was rerun, and no LLM judge was used. Subgroup and latency analyses are exploratory.