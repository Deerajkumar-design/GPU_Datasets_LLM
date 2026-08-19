# Llama 3.2 3B 4K-64K Raw Inference Run

- model: `meta-llama/Llama-3.2-3B-Instruct`
- revision: `0cb88a4f764b7a12671c53f0838cd831a0843b95`
- dtype: `bfloat16`
- cache: `DynamicCache`
- attempted: `500`
- successful: `500`
- failed: `0`
- total synchronized inference time: `4323.250` seconds
- total wall-clock experiment time: `4344.901` seconds

| Context | Success | Total inference time | Mean | Median | P95 | Mean generated tokens | Peak VRAM |
|---|---:|---:|---:|---:|---:|---:|---:|
| 4K | 100 | 268.304s | 2.683s | 0.874s | 6.011s | 218.0 | 19.88 GiB |
| 8K | 100 | 437.714s | 4.377s | 6.983s | 7.001s | 306.0 | 19.88 GiB |
| 16K | 100 | 668.312s | 6.683s | 9.103s | 9.145s | 356.9 | 19.88 GiB |
| 32K | 100 | 1050.058s | 10.501s | 14.275s | 14.345s | 345.3 | 19.88 GiB |
| 64K | 100 | 1898.861s | 18.989s | 25.842s | 25.973s | 319.7 | 19.88 GiB |

No scoring or hallucination analysis was performed.
