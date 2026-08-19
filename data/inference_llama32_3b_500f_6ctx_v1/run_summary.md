# Experiment D Raw Inference Summary

- expected instances: `3000`
- attempted: `3000`
- successful: `2998`
- failed: `2`
- CUDA OOM failures: `2`
- total synchronized inference seconds: `12005.380`
- total wall-clock seconds: `12154.255`
- dataset hash: `dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6`
- model revision: `0cb88a4f764b7a12671c53f0838cd831a0843b95`
- prompt: `llama_chat_v4` / `5d2869822989e19b`

| Context | Attempted | Success | Failed | OOM | Usable ANSWER | Malformed | Hit 128 | Degenerate | Mean latency | P95 latency | Max VRAM reserved GiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4K | 500 | 500 | 0 | 0 | 500 | 0 | 0 | 0 | 0.316s | 0.350s | 22.12 |
| 8K | 500 | 500 | 0 | 0 | 500 | 0 | 0 | 0 | 0.598s | 0.635s | 22.12 |
| 16K | 500 | 500 | 0 | 0 | 500 | 0 | 0 | 0 | 1.212s | 1.260s | 22.12 |
| 32K | 500 | 500 | 0 | 0 | 500 | 0 | 0 | 0 | 2.842s | 2.938s | 22.12 |
| 64K | 500 | 500 | 0 | 0 | 500 | 0 | 0 | 0 | 7.827s | 7.959s | 22.12 |
| 82K | 500 | 498 | 2 | 2 | 498 | 0 | 0 | 0 | 11.260s | 11.385s | 22.32 |

No grading, correctness scoring, hallucination classification, or statistical analysis was performed.
