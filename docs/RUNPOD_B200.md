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

4. Stage only the model needed now. `HF_TOKEN` is read only from the environment
   and is never persisted by these scripts:

   ```bash
   export RUNPOD_WORKSPACE=/workspace
   export HF_TOKEN=hf_...
   PYTHONPATH=src python scripts/b200/stage_models.py --model qwen
   unset HF_TOKEN
   HF_HUB_OFFLINE=1 PYTHONPATH=src python scripts/b200/stage_models.py --model qwen --verify-only
   ```

5. Confirm `manifests/staged_models.json` says `verified_offline: true` for
   `Qwen/Qwen3.5-2B@15852e8c16360a2fea060d615a32b45270f8a8fc`.
   Use `--model llama` or `--model all` later when staging Llama.

## RunPod UI

Create one Secure Cloud B200 Pod using the pushed image. Attach the prepared Network
Volume at `/workspace`; expose no ports unless SSH is needed. Set
`RUNPOD_WORKSPACE=/workspace`. Do not set `HF_TOKEN`: inference is offline.

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

### Optional validated auto-stop

Manual stopping is the default. To request a RunPod stop only after terminal
3,000-instance accounting, persistent validation, hashing, and completion manifests:

```bash
export RUNPOD_POD_ID="your-pod-id"
export RUNPOD_API_KEY="your-api-key"
./scripts/b200/run_b200_inference.sh --model qwen --auto-stop
```

These values are read only from the environment and are never written to repository
files or manifests. A preflight, smoke, inference, validation, hashing, or completion
failure exits before the stop API can be called. If the stop request itself fails, the
Pod remains running and the command exits non-zero.

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
