# B200 preparation report

## VALIDATED LOCALLY

- Frozen benchmark and grader hashes match after newline-normalized verification.
- Existing Llama `llama_chat_v4` and Qwen `qwen35_chat_v1` renderers and runners are reused.
- B200 output paths are isolated under the persistent workspace.
- Resume writes are fsynced, unique IDs are skipped, and frozen manifest fields are checked.
- Static Python, shell syntax, unit tests, and local path/hash checks are part of preparation.

## REQUIRES B200 PREFLIGHT

- NVIDIA B200/SM100 detection, CUDA 12.8 execution, BF16 support, available VRAM,
  offline model loading/generation, exact token-count continuity, and 82K smoke success.

Run `./scripts/b200/preflight.sh`, then `./scripts/b200/run_b200_inference.sh`.
