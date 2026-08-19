# Experiment D Final Statistical Analysis

Analysis used only the frozen final scored dataset. Runtime OOM failures were reported separately and excluded from factual outcomes.

## Primary Results

| context   |   gradable_n |   correct_pct |   inaccurate_pct | inaccuracy_95_ci   |   hallucinatory_pct |   grounded_pct |   runtime_failures |   mean_latency |
|:----------|-------------:|--------------:|-----------------:|:-------------------|--------------------:|---------------:|-------------------:|---------------:|
| 4K        |          500 |       50.4    |          49.6    | 45.2%-54.0%        |             34.2    |        15.4    |                  0 |       0.316338 |
| 8K        |          500 |       45.6    |          54.4    | 50.0%-58.8%        |             37.2    |        17.2    |                  0 |       0.598367 |
| 16K       |          500 |       41.2    |          58.8    | 54.4%-63.2%        |             34.8    |        24      |                  0 |       1.21203  |
| 32K       |          500 |       38.4    |          61.6    | 57.4%-65.8%        |             38.2    |        23.4    |                  0 |       2.84235  |
| 64K       |          500 |       30.4    |          69.6    | 65.6%-73.6%        |             41.8    |        27.8    |                  0 |       7.82706  |
| 82K       |          498 |       29.3173 |          70.6827 | 66.6%-74.7%        |             40.3614 |        30.3213 |                  2 |      11.2597   |

## GEE Trend Results

| Outcome                                    |   OR per 2x context | 95% CI         |   p-value |
|:-------------------------------------------|--------------------:|:---------------|----------:|
| inaccurate                                 |               1.232 | [1.178, 1.288] | 8.656e-20 |
| hallucinatory_inaccuracy                   |               1.07  | [1.027, 1.115] | 0.0013    |
| grounded_inaccuracy                        |               1.215 | [1.153, 1.280] | 3.337e-13 |
| hallucinatory_vs_grounded_among_inaccurate |               0.936 | [0.897, 0.977] | 0.0025    |

## Paired McNemar Tests

| outcome                  | comparison   |   paired_n |   event_rate_4K |   event_rate_comparison |   absolute_percentage_point_difference |   discordant_4K0_cmp1 |   discordant_4K1_cmp0 |   raw_p_value |   holm_adjusted_p_value | significant_after_holm_0_05   |
|:-------------------------|:-------------|-----------:|----------------:|------------------------:|---------------------------------------:|----------------------:|----------------------:|--------------:|------------------------:|:------------------------------|
| inaccurate               | 4K_vs_8K     |        500 |        0.496    |                0.544    |                                 4.8    |                    41 |                    17 |   0.00223255  |             0.00223255  | True                          |
| inaccurate               | 4K_vs_16K    |        500 |        0.496    |                0.588    |                                 9.2    |                    66 |                    20 |   6.66978e-07 |             1.33396e-06 | True                          |
| inaccurate               | 4K_vs_32K    |        500 |        0.496    |                0.616    |                                12      |                    88 |                    28 |   2.08836e-08 |             6.26507e-08 | True                          |
| inaccurate               | 4K_vs_64K    |        500 |        0.496    |                0.696    |                                20      |                   124 |                    24 |   1.89258e-17 |             7.57032e-17 | True                          |
| inaccurate               | 4K_vs_82K    |        498 |        0.493976 |                0.706827 |                                21.2851 |                   129 |                    23 |   4.33023e-19 |             2.16511e-18 | True                          |
| hallucinatory_inaccuracy | 4K_vs_8K     |        500 |        0.342    |                0.372    |                                 3      |                    24 |                     9 |   0.013531    |             0.040593    | True                          |
| hallucinatory_inaccuracy | 4K_vs_16K    |        500 |        0.342    |                0.348    |                                 0.6    |                    35 |                    32 |   0.807195    |             0.807195    | False                         |
| hallucinatory_inaccuracy | 4K_vs_32K    |        500 |        0.342    |                0.382    |                                 4      |                    51 |                    31 |   0.0352414   |             0.0704829   | False                         |
| hallucinatory_inaccuracy | 4K_vs_64K    |        500 |        0.342    |                0.418    |                                 7.6    |                    75 |                    37 |   0.000420968 |             0.00210484  | True                          |
| hallucinatory_inaccuracy | 4K_vs_82K    |        498 |        0.339357 |                0.403614 |                                 6.4257 |                    69 |                    37 |   0.00244001  |             0.00976003  | True                          |
| grounded_inaccuracy      | 4K_vs_8K     |        500 |        0.154    |                0.172    |                                 1.8    |                    39 |                    30 |   0.335558    |             0.335558    | False                         |
| grounded_inaccuracy      | 4K_vs_16K    |        500 |        0.154    |                0.24     |                                 8.6    |                    68 |                    25 |   9.37564e-06 |             2.81269e-05 | True                          |
| grounded_inaccuracy      | 4K_vs_32K    |        500 |        0.154    |                0.234    |                                 8      |                    70 |                    30 |   7.85014e-05 |             0.000157003 | True                          |
| grounded_inaccuracy      | 4K_vs_64K    |        500 |        0.154    |                0.278    |                                12.4    |                    90 |                    28 |   8.91405e-09 |             3.56562e-08 | True                          |
| grounded_inaccuracy      | 4K_vs_82K    |        498 |        0.154618 |                0.303213 |                                14.8594 |                    96 |                    22 |   3.25658e-12 |             1.62829e-11 | True                          |

## Sensitivity Analyses

Complete-case families: 498; observations: 2988.
Excluding UNANSWERABLE observations: 2398.

## Question-Type and Domain Tables

Question-type and domain breakdowns are saved as CSV files in this output directory.

## Runtime Failures

There were two runtime failures, both CUDA OOM at 82K. They were not treated as factual inaccuracies.
