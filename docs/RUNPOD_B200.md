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

4. Stage the gated Llama model and Qwen model. `HF_TOKEN` is read only from the
   environment and is never persisted by these scripts:

   ```bash
   export RUNPOD_WORKSPACE=/workspace
   export HF_TOKEN=hf_...
   PYTHONPATH=src python scripts/b200/stage_models.py
   unset HF_TOKEN
   HF_HUB_OFFLINE=1 PYTHONPATH=src python scripts/b200/stage_models.py --verify-only
   ```

5. Confirm `manifests/staged_models.json` says `verified_offline: true` for:
   `meta-llama/Llama-3.2-3B-Instruct@0cb88a4f764b7a12671c53f0838cd831a0843b95`
   and `Qwen/Qwen3.5-2B@15852e8c16360a2fea060d615a32b45270f8a8fc`.

## RunPod UI

Create one Secure Cloud B200 Pod using the pushed image. Attach the prepared Network
Volume at `/workspace`; expose no ports unless SSH is needed. Set
`RUNPOD_WORKSPACE=/workspace`. Do not set `HF_TOKEN`: inference is offline.

## First commands

```bash
cd /workspace/long-context-reliability/repo
./scripts/b200/preflight.sh
./scripts/b200/run_b200_inference.sh
```

The inference launcher repeats the fast preflight safely, runs a two-family/six-context
smoke test for each model, then resumes both 3,000-instance jobs. It writes and fsyncs
every row and skips IDs already present in either results or failures. Restart the exact
same command after interruption:

```bash
./scripts/b200/run_b200_inference.sh
```

The existing run manifest is checked for frozen metadata drift. Outputs never use the
historical Experiment D/E directories.

When the launcher prints:

```text
GPU INFERENCE COMPLETE - SAFE TO TERMINATE POD AFTER VERIFYING PERSISTENT OUTPUTS
```

verify `manifests/b200_inference_hashes.json` exists on the Network Volume, then stop
the B200 immediately.

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
full inference for each condition. Preflight and smoke each load both small models once;
this intentional fixed overhead prevents a much costlier mismatched full run.
