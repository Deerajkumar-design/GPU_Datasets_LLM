# Experiment C Llama 4K-64K Raw Inference

- prompt: `llama_chat_v4` / `5d2869822989e19b`
- smoke passed: `True`
- successful: `500`
- failed: `0`

| Context | Usable | Format failures | Hit 128 | Degenerate | Mean tokens | Mean latency | Median latency | P95 latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4K | 100 | 0 | 0 | 0 | 8.5 | 0.317s | 0.315s | 0.350s |
| 8K | 100 | 0 | 0 | 0 | 8.4 | 0.601s | 0.598s | 0.636s |
| 16K | 100 | 0 | 0 | 0 | 8.3 | 1.212s | 1.210s | 1.260s |
| 32K | 100 | 0 | 0 | 0 | 8.4 | 2.842s | 2.835s | 2.935s |
| 64K | 100 | 0 | 0 | 0 | 8.3 | 7.824s | 7.811s | 7.952s |

No correctness or hallucination scoring was performed.
