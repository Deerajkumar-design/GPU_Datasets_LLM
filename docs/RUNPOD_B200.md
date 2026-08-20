# RunPod B200 replication

## Frozen protocol

This deployment preserves the exact model repositories/revisions, benchmark, prompts,
BF16, batch size 1, greedy decoding, 128-token output budget, DynamicCache, SDPA,
and frozen deterministic grader. It does not enable FP8/FP4, quantization, offloading,
compilation, speculative decoding, or custom attention kernels.

The shared environment uses CUDA 12.8.1, PyTorch 2.7.1+cu128 (native SM100 support),
and the historical Transformers 5.14.1/tokenizers 0.22.2 model-facing stack. One
environment is appropriate because both frozen runners previously used Transformers
5.14.1 and PyTorch 2.7.1 only changes the hardware compatibility layer.

## Persistent volume layout

Set `RUNPOD_WORKSPACE` to the Network Volume mount (`/workspace` by default):

```text
/workspace/long-context-reliability/
  repo/
  models/{llama,qwen}/<exact-revision>/
  hf_cache/
  results/
    inference_b200_llama32_3b_500f_6ctx_v1/
    inference_b200_qwen35_2b_500f_6ctx_v1/
    grading_b200_{llama,qwen}_v1/
    analysis_b200_replication_v1/
  logs/
  manifests/
```

## Before launching a B200

1. Create a RunPod Network Volume with at least 100 GB free and mount it temporarily
   on an inexpensive CPU Pod or another machine that can write the volume.
2. Place this repository at `/workspace/long-context-reliability/repo`.
3. Build and push the image before renting the B200:

   ```bash
   cd /workspace/long-context-reliability/repo
   docker build -f docker/Dockerfile.b200 -t YOUR_REGISTRY/longctx-b200:1 .
   docker push YOUR_REGISTRY/longctx-b200:1
   ```

4. For unattended `all` mode, stage and verify both pinned models before queueing
   the B200. `HF_TOKEN` is read only from the environment and is never persisted:

   ```bash
   export RUNPOD_WORKSPACE=/workspace
   export HF_TOKEN=hf_...
   PYTHONPATH=src python scripts/b200/stage_models.py --model all
   unset HF_TOKEN
   HF_HUB_OFFLINE=1 PYTHONPATH=src python scripts/b200/stage_models.py --model all --verify-only
   ```

5. Confirm `manifests/staged_models.json` says `verified_offline: true` for both:
   `meta-llama/Llama-3.2-3B-Instruct@0cb88a4f764b7a12671c53f0838cd831a0843b95`
   and `Qwen/Qwen3.5-2B@15852e8c16360a2fea060d615a32b45270f8a8fc`.

## RunPod UI

For **Deploy When Available**, use:

| Setting | Value |
|---|---|
| GPU | NVIDIA B200, one GPU |
| Container image | `ghcr.io/deerajkumar-design/gpu_datasets_llm:2a73d0e917b3055281eb1cd67cec12fc565c3ff8` |
| Verified image digest | `sha256:81b5049633659cf59ccd02937c1b6851546e0d20b9b87536faf012513720b418` |
| Network Volume mount | `/workspace` |
| Docker/Container Start Command | `bash /workspace/long-context-reliability/repo/scripts/b200/runpod_autorun.sh` |
| `RUNPOD_WORKSPACE` | `/workspace` |
| `RUNPOD_API_KEY` | Your RunPod API key, configured as a secret |

RunPod must provide a non-empty `RUNPOD_POD_ID` to the container at runtime. The
autorun wrapper verifies it before starting inference. Do not set `HF_TOKEN`; both
exact model revisions are staged locally and inference forces offline Hugging Face
mode. If the GHCR package is private, configure registry authentication in the RunPod
template separately; do not place registry credentials in the repository or start
command.

The start command is non-interactive and does not use Codex. It records machine
metadata and continuously tees output to:

```text
/workspace/long-context-reliability/logs/b200_autorun/
```

It runs preflight, the six-context smoke test, all 3,000 Llama instances, and all
3,000 Qwen instances. It then validates and hashes persistent raw outputs. It does
not run grading, statistical analysis, plots, or reports on the B200.

## First commands

```bash
cd /workspace/long-context-reliability/repo
./scripts/b200/preflight.sh --model qwen
./scripts/b200/run_b200_inference.sh --model qwen
```

The inference launcher repeats the fast preflight safely, runs a two-family/six-context
smoke test for Qwen only, then resumes its 3,000-instance job. Qwen is loaded from
`/workspace/long-context-reliability/models/qwen/15852e8c16360a2fea060d615a32b45270f8a8fc`
with Hugging Face offline mode enabled. Llama is not checked, loaded, smoke-tested, or
required. Every row is written and fsynced, and IDs already present in either results
or failures are skipped. Restart the exact same command after interruption:

```bash
./scripts/b200/run_b200_inference.sh --model qwen
```

The existing run manifest is checked for frozen metadata drift. Outputs never use the
historical Experiment D/E directories. Use `--model llama` later for Llama only, or
`--model all` after both exact revisions are staged.

When the launcher prints:

```text
GPU INFERENCE COMPLETE - SAFE TO TERMINATE POD AFTER VERIFYING PERSISTENT OUTPUTS
```

verify `manifests/b200_inference_hashes_qwen.json` and
`manifests/b200_inference_complete_qwen.json` exist on the Network Volume, then stop
the B200 immediately.

### Unattended safe termination

The autorun path calls RunPod's Pod deletion endpoint exactly once and only after:

- preflight and smoke validation manifests pass for both models;
- both raw output directories are readable beneath `/workspace`;
- each model has 3,000 successful unique instance IDs and zero runtime failures;
- both integrity reports pass and retain the pinned model revisions;
- every recorded persistent artifact hash is recomputed successfully; and
- the `all` completion marker exists and covers Llama and Qwen.

Only then does it print `ALL GPU OUTPUTS VERIFIED ON NETWORK VOLUME` and issue:

```text
DELETE https://rest.runpod.io/v1/pods/$RUNPOD_POD_ID
```

The API key is read from `RUNPOD_API_KEY`, never logged, and never written to a
manifest. If any experiment or verification step fails, the wrapper prints
`AUTOMATIC TERMINATION BLOCKED` and does not call the deletion API. If the one DELETE
request receives no confirmed response, its outcome is recorded as unknown and the
operator must check the RunPod console; the script never retries the destructive
request. Rerunning the wrapper preserves partial output and uses the existing
`--resume` behavior without duplicating completed IDs.

## CPU-only analysis

On a CPU Pod or local Linux machine with the same volume:

```bash
cd /workspace/long-context-reliability/repo
./scripts/b200/analyze_b200_results.sh
```

This runs the frozen grader, maps `CORRECT` to `ACCURATE`, fits per-model clustered
GEE models, runs exact McNemar/Holm tests, and quantifies answer and label agreement
against the RTX 4090 results. A frozen historical adjudication is reused only when the
new parsed answer exactly matches its previously adjudicated answer. Runtime failures
remain outside factual outcomes.

## Validation status

**VALIDATED LOCALLY:** Git/LFS checkout, normalized benchmark and grader hashes,
Python syntax, unit tests, path isolation, frozen revisions, and launcher structure.

**REQUIRES B200 PREFLIGHT:** B200 identity/SM100, driver and CUDA execution, BF16
matmul, 180 GB-class VRAM, offline loading, one generation per model, parser behavior,
and six-context no-OOM smoke inference.

## Cost risks

Missing model snapshots, an image pull, an incorrectly mounted volume, tokenizer
drift, or failed 82K smoke inference can consume paid time. The preflight fails before
full inference for each condition. In Qwen-only mode, preflight and smoke load only Qwen. `all` mode retains the original
two-model behavior once both snapshots are staged.
