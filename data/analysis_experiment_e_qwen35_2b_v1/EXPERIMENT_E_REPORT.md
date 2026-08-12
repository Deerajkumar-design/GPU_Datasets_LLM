# Experiment E Qwen3.5-2B Report

- model revision: `15852e8c16360a2fea060d615a32b45270f8a8fc`
- prompt version/hash: `qwen35_chat_v1` / `8b1f0e7700df4fe1`
- benchmark hash: `dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6`
- successful/runtime failures: `3000` / `0`

## Context Results

| context   |   gradable_n |   correct_rate |   inaccuracy_rate |   hallucinatory_rate |   grounded_rate |   mean_input_tokens |   mean_latency |
|:----------|-------------:|---------------:|------------------:|---------------------:|----------------:|--------------------:|---------------:|
| 4K        |          500 |          0.548 |             0.452 |                0.284 |           0.168 |             5163.94 |       0.471882 |
| 8K        |          500 |          0.458 |             0.542 |                0.286 |           0.256 |            10105.8  |       0.835618 |
| 16K       |          500 |          0.394 |             0.606 |                0.24  |           0.366 |            19980.9  |       1.58737  |
| 32K       |          500 |          0.312 |             0.688 |                0.244 |           0.444 |            39736    |       3.19869  |
| 64K       |          500 |          0.326 |             0.674 |                0.184 |           0.49  |            79219    |       6.81251  |
| 82K       |          500 |          0.288 |             0.712 |                0.194 |           0.518 |            99421.7  |       8.87206  |

## Primary GEE

| outcome                  |       OR |   CI_low |   CI_high |           p |
|:-------------------------|---------:|---------:|----------:|------------:|
| inaccurate               | 1.27619  | 1.21628  |  1.33904  | 2.73561e-23 |
| hallucinatory_inaccuracy | 0.874952 | 0.841222 |  0.910035 | 2.74013e-11 |
| grounded_inaccuracy      | 1.44707  | 1.38244  |  1.51472  | 1.35663e-56 |

## Answerable-Only Sensitivity

| outcome                  | predictor    | formula                                 | working_correlation   |   n_observations |   n_families |   coefficient |   robust_se |   odds_ratio_per_2x_context |   odds_ratio_ci_low |   odds_ratio_ci_high |     p_value | converged   |
|:-------------------------|:-------------|:----------------------------------------|:----------------------|-----------------:|-------------:|--------------:|------------:|----------------------------:|--------------------:|---------------------:|------------:|:------------|
| inaccurate               | context_log2 | inaccurate ~ context_log2               | Exchangeable          |             2400 |          400 |      0.392436 |   0.0291461 |                    1.48058  |            1.39838  |             1.56762  | 2.531e-41   | True        |
| hallucinatory_inaccuracy | context_log2 | hallucinatory_inaccuracy ~ context_log2 | Exchangeable          |             2400 |          400 |     -0.110419 |   0.0243867 |                    0.895459 |            0.853665 |             0.939299 | 5.95946e-06 | True        |
| grounded_inaccuracy      | context_log2 | grounded_inaccuracy ~ context_log2      | Exchangeable          |             2400 |          400 |      0.438654 |   0.0279623 |                    1.55062  |            1.46792  |             1.63797  | 1.84662e-55 | True        |

## Complete Case

Complete families: `500`; observations: `3000`.
| outcome                  | predictor    | formula                                 | working_correlation   |   n_observations |   n_families |   coefficient |   robust_se |   odds_ratio_per_2x_context |   odds_ratio_ci_low |   odds_ratio_ci_high |     p_value | converged   |
|:-------------------------|:-------------|:----------------------------------------|:----------------------|-----------------:|-------------:|--------------:|------------:|----------------------------:|--------------------:|---------------------:|------------:|:------------|
| inaccurate               | context_log2 | inaccurate ~ context_log2               | Exchangeable          |             3000 |          500 |      0.243877 |   0.0245302 |                    1.27619  |            1.21628  |             1.33904  | 2.73561e-23 | True        |
| hallucinatory_inaccuracy | context_log2 | hallucinatory_inaccuracy ~ context_log2 | Exchangeable          |             3000 |          500 |     -0.133586 |   0.0200582 |                    0.874952 |            0.841222 |             0.910035 | 2.74013e-11 | True        |
| grounded_inaccuracy      | context_log2 | grounded_inaccuracy ~ context_log2      | Exchangeable          |             3000 |          500 |      0.369538 |   0.0233114 |                    1.44707  |            1.38244  |             1.51472  | 1.35663e-56 | True        |

## Paired Tests

| outcome                  | comparison   |   paired_n |   event_rate_4K |   event_rate_comparison |   absolute_percentage_point_difference |   discordant_4K0_cmp1 |   discordant_4K1_cmp0 |   raw_p_value |   holm_adjusted_p_value | significant_after_holm_0_05   |
|:-------------------------|:-------------|-----------:|----------------:|------------------------:|---------------------------------------:|----------------------:|----------------------:|--------------:|------------------------:|:------------------------------|
| inaccurate               | 4K_vs_8K     |        500 |           0.452 |                   0.542 |                                    9   |                    60 |                    15 |   1.5878e-07  |             1.5878e-07  | True                          |
| inaccurate               | 4K_vs_16K    |        500 |           0.452 |                   0.606 |                                   15.4 |                    88 |                    11 |   4.52958e-16 |             9.05916e-16 | True                          |
| inaccurate               | 4K_vs_32K    |        500 |           0.452 |                   0.688 |                                   23.6 |                   125 |                     7 |   4.58148e-29 |             2.29074e-28 | True                          |
| inaccurate               | 4K_vs_64K    |        500 |           0.452 |                   0.674 |                                   22.2 |                   139 |                    28 |   6.83635e-19 |             2.05091e-18 | True                          |
| inaccurate               | 4K_vs_82K    |        500 |           0.452 |                   0.712 |                                   26   |                   151 |                    21 |   1.87477e-25 |             7.49907e-25 | True                          |
| hallucinatory_inaccuracy | 4K_vs_16K    |        500 |           0.284 |                   0.24  |                                   -4.4 |                    12 |                    34 |   0.00164149  |             0.00492447  | True                          |
| hallucinatory_inaccuracy | 4K_vs_32K    |        500 |           0.284 |                   0.244 |                                   -4   |                    16 |                    36 |   0.00778744  |             0.0155749   | True                          |
| hallucinatory_inaccuracy | 4K_vs_64K    |        500 |           0.284 |                   0.184 |                                  -10   |                    12 |                    62 |   2.85555e-09 |             1.42777e-08 | True                          |
| hallucinatory_inaccuracy | 4K_vs_82K    |        500 |           0.284 |                   0.194 |                                   -9   |                    11 |                    56 |   2.1458e-08  |             8.58318e-08 | True                          |
| grounded_inaccuracy      | 4K_vs_8K     |        500 |           0.168 |                   0.256 |                                    8.8 |                    67 |                    23 |   3.79505e-06 |             3.79505e-06 | True                          |
| grounded_inaccuracy      | 4K_vs_16K    |        500 |           0.168 |                   0.366 |                                   19.8 |                   108 |                     9 |   1.08258e-22 |             2.16516e-22 | True                          |
| grounded_inaccuracy      | 4K_vs_32K    |        500 |           0.168 |                   0.444 |                                   27.6 |                   147 |                     9 |   2.77749e-33 |             8.33248e-33 | True                          |
| grounded_inaccuracy      | 4K_vs_64K    |        500 |           0.168 |                   0.49  |                                   32.2 |                   167 |                     6 |   5.90768e-42 |             2.36307e-41 | True                          |
| grounded_inaccuracy      | 4K_vs_82K    |        500 |           0.168 |                   0.518 |                                   35   |                   181 |                     6 |   5.77335e-46 |             2.88668e-45 | True                          |

## Largest Error Changes 4K To 82K

| error_type             |   rate_delta |
|:-----------------------|-------------:|
| UNNECESSARY_ABSTENTION |        0.272 |
| UNSUPPORTED_VALUE      |       -0.058 |
| WRONG_ENTITY           |        0.044 |
| FAILED_TO_ABSTAIN      |       -0.032 |
| WRONG_FIELD            |        0.028 |
| WRONG_PERIOD           |        0.018 |
| CALCULATION_ERROR      |       -0.008 |
| WRONG_UNIT             |       -0.004 |
| WRONG_VERSION          |        0     |
| WRONG_SERIES_VARIANT   |        0     |

## Question Types And Domains

Full exploratory tables are saved as CSV files. Largest question-type/domain patterns should be interpreted descriptively.

## Cross-Model Interactions

| outcome                  | formula                                            | interaction_term                   |   interaction_coefficient_qwen_minus_llama |   interaction_or_ratio |   ci_low |   ci_high |     p_value |   n_observations |   n_families |
|:-------------------------|:---------------------------------------------------|:-----------------------------------|-------------------------------------------:|-----------------------:|---------:|----------:|------------:|-----------------:|-------------:|
| inaccurate               | inaccurate ~ context_log2 * C(model)               | context_log2:C(model)[T.qwen35_2b] |                                  0.0298846 |               1.03034  | 0.966549 |  1.09833  | 0.359398    |             5998 |          500 |
| grounded_inaccuracy      | grounded_inaccuracy ~ context_log2 * C(model)      | context_log2:C(model)[T.qwen35_2b] |                                  0.174674  |               1.19086  | 1.11569  |  1.27108  | 1.51195e-07 |             5998 |          500 |
| hallucinatory_inaccuracy | hallucinatory_inaccuracy ~ context_log2 * C(model) | context_log2:C(model)[T.qwen35_2b] |                                 -0.208172  |               0.812068 | 0.766538 |  0.860301 | 1.53451e-12 |             5998 |          500 |

## Key Answers

- Does factual inaccuracy increase? Qwen increases: OR `1.276`, p `2.736e-23`.
- Does grounded inaccuracy increase? Qwen increases: OR `1.447`, p `1.357e-56`.
- Does full-dataset hallucinatory inaccuracy increase? Qwen decreases: OR `0.875`, p `2.740e-11`.
- After excluding UNANSWERABLE, hallucination decreases: OR `0.895`, p `5.959e-06`.
- Failure to abstain changes from `0.086` at 4K to `0.054` at 82K.
- Cross-model slope interaction results are in the table above; tokenization/template differences mean this is a behavioral replication, not an architectural ablation.

## Required Research Questions

1. Does factual inaccuracy increase as Qwen3.5-2B receives longer context? Yes. Overall inaccuracy rises from `45.2%` at 4K to `71.2%` at 82K, with GEE OR `1.276` per true 2x increase in rendered Qwen tokens.
2. What is the odds ratio per true 2x increase in rendered Qwen context? Overall OR `1.276` [1.216, 1.339], p `2.736e-23`; hallucinatory OR `0.875` [0.841, 0.910], p `2.740e-11`; grounded OR `1.447` [1.382, 1.515], p `1.357e-56`.
3. Does grounded inaccuracy increase? Yes. Grounded inaccuracy rises from `16.8%` at 4K to `51.8%` at 82K.
4. Does hallucinatory inaccuracy increase on the full dataset? No. It decreases from `28.4%` at 4K to `19.4%` at 82K, despite the overall inaccuracy increase.
5. What happens to hallucination after excluding UNANSWERABLE tasks? It still decreases: answerable-only hallucinatory OR `0.895`, p `5.959e-06`.
6. Does Qwen increasingly fail to abstain when evidence is absent? No. `FAILED_TO_ABSTAIN` falls from 43/500 (`8.6%` of all gradable instances; 43/100 unanswerable families) at 4K to 27/500 (`5.4%`; 27/100 unanswerable families) at 82K.
7. Do temporal/entity/field binding errors increase with context? Yes descriptively. `WRONG_ENTITY` rises 11 to 33, `WRONG_PERIOD` rises 6 to 15, and `WRONG_FIELD` rises 0 to 14 from 4K to 82K; `WRONG_VERSION` is flat at 5.
8. Is the effect consistent across question types? Overall inaccuracy increases for direct retrieval, entity/unit binding, temporal/version, and remains near ceiling for retrieval/calculation; unanswerable errors do not increase and instead decrease at longer contexts.
9. Is the effect consistent across domains? Overall inaccuracy increases in all four domains from 4K to 82K: ClinicalTrials `44.0%` to `57.6%`, FDA `57.6%` to `72.8%`, FRED `36.8%` to `79.2%`, SEC `42.4%` to `75.2%`.
10. Are conclusions robust to complete-case analysis? Yes. There were `500` complete families and `3000` observations, so complete-case results equal the primary results.
11. How does Qwen's degradation slope compare with Llama-3.2-3B-Instruct? Overall slopes are statistically indistinguishable in the combined model: interaction OR ratio `1.030`, p `0.359`. Qwen has a steeper grounded-error slope and a more negative hallucinatory-error slope.
12. Is the model x context interaction statistically significant? Overall: no, p `0.359`. Grounded: yes, interaction OR ratio `1.191`, p `1.512e-07`. Hallucinatory: yes, interaction OR ratio `0.812`, p `1.535e-12`.
13. Does the mechanism of degradation replicate across the two models? Partially. The main overall degradation and grounded-confusion mechanism replicate, but the unanswerable/hallucination mechanism does not: Qwen's hallucination and failure-to-abstain rates decrease rather than increase with longer context.

## Validation And Deviations

- Inference validation: `3000` attempted, `3000` successful, `0` runtime failures, `0` malformed outputs, `0` max-new-token hits, `0` thinking-trace outputs, and `0` duplicate instance IDs.
- Prompt budget: all Qwen-rendered inputs fit below the model context limit of `262144`; maximum observed rendered input length was `111079` tokens.
- Manual grading review: `10` frozen-grader ambiguous cases were resolved with recorded deterministic human review in `data/grading_experiment_e_qwen35_2b_v1/manual_resolutions.jsonl`; the frozen grader file hash remained `d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8`.
- Process deviations: full inference had process-level segmentation faults after flushed successful rows at 943, 1831, 1846, and 2952 completed instances. The run was resumed with identical pinned settings and skipped completed IDs; no factual outputs were selectively rerun and no instance-level runtime failures occurred.
- Implementation note: Transformers reported that Qwen's fast path was unavailable and fell back to the torch implementation. No quantization, offloading, sampling, speculative decoding, or forced cache implementation was used.
