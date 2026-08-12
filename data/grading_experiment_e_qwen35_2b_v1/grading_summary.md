# Experiment E Qwen Deterministic Grading

- successful responses graded: `3000`
- runtime failures excluded from factual grading: `0`
- correct: `1163`
- inaccurate: `1837`
- hallucinatory inaccuracies: `716`
- grounded inaccuracies: `1121`
- ambiguous-review cases: `0`
- format failures: `0`
- manual resolutions applied: `10`
- grader hash: `d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8`
- scored results hash: `598b00d7ab9c62c82f55ea08dd3967c3ae66c4cc9f0708fae2e6dcfe46b1ad7e`

| Context | Gradable N | Correct | Inaccurate | Hallucinatory | Grounded | Ambiguous | Runtime failures |
|---|---:|---:|---:|---:|---:|---:|---:|
| 4K | 500 | 274 | 226 | 142 | 84 | 0 | 0 |
| 8K | 500 | 229 | 271 | 143 | 128 | 0 | 0 |
| 16K | 500 | 197 | 303 | 120 | 183 | 0 | 0 |
| 32K | 500 | 156 | 344 | 122 | 222 | 0 | 0 |
| 64K | 500 | 163 | 337 | 92 | 245 | 0 | 0 |
| 82K | 500 | 144 | 356 | 97 | 259 | 0 | 0 |
