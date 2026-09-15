# Reproducible CP2 8K/16K/32K experiment

This protocol preserves CP2's primary systems experiment while using the exact frozen
`GPU_Datasets` contexts and questions. CP2 still controls model execution, distributed
attention, timing, and GPU-memory measurement. The established `GPU_Datasets` prompt
contract is used so the saved answers can also be graded consistently afterward.

It does not implement exponent bucketing or run grading/statistical analysis on the GPUs.

## Frozen workload

- Source benchmark: `preproduction_llama32_3b_500f_6ctx_v1`
- Source repository commit: `b9b126a21ee3e609ff00cf5b8757668d8a16ff73`
- Dataset hash: `dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6`
- Selected labels: `8K`, `16K`, and `32K`
- Families: 500
- Runs: 1,500 unique family/context instances, each executed once
- Contexts, questions, gold answers, evidence, provenance, and distractors: unchanged

## Preserved CP2 model and inference

- Model: `Qwen/Qwen2.5-7B-Instruct-1M`
- Revision: `e28526f7bb80e2a9c8af03b831a9af3812f18fba`
- Exactly 3 NVIDIA A100 GPUs
- Replicated weights and sequence-sharded attention
- NCCL ring KV exchange
- Zigzag causal load balancing
- Native PyTorch Flash Attention with LSE
- Manually managed sharded KV cache
- BF16, batch size 1, greedy decoding, at most 128 new tokens

## Standardized model-facing prompt

The benchmark context and question strings remain unchanged. They are placed into the
same `GPU_Datasets` evaluation structure:

```text
System: Answer using only the supplied records...

User:
KNOWLEDGE RECORDS:
<verbatim instance context>

TARGET QUESTION:
<verbatim instance question>

OUTPUT FORMAT:
Return only one short line:
ANSWER: <answer>
```

Qwen 2.5's pinned native chat template renders those messages. This affects only how the
workload is presented to the model; it does not change CP2's ring-attention execution.
The runner saves both the untouched raw generation and the parsed answer.

## Reproducibility controls

- Pinned model revision and staged-path marker
- Frozen source benchmark hash and exact 500/500/500 context accounting
- Frozen evaluation prompt, CP source hashes, and machine-readable configuration
- Deterministically shuffled execution order with seed `20260812`
- Persistent JSONL writes with flush and `fsync` after every completed instance
- Resume by instance ID with duplicate prevention and metadata-drift checks
- Hardware/software preflight and a six-instance smoke test
- Structural answer validation, timing summary, artifact hashes, and completion marker

The GPU run captures raw answers and systems measurements. Factual grading is a separate
CPU-only step using the frozen `GPU_Datasets` grader.

## Persistent layout

```text
/workspace/context-parallel-repro/
  datasets/preproduction_llama32_3b_500f_6ctx_v1/
  models/qwen/e28526f7bb80e2a9c8af03b831a9af3812f18fba/
  results/qwen25_7b_cp_gpu_dataset_8k_32k_v1/
  logs/qwen25_7b_cp_gpu_dataset_8k_32k_v1/
  manifests/qwen25_7b_cp_gpu_dataset_8k_32k_v1/
```

## Stage the benchmark

```bash
export CP_WORKSPACE=/workspace/context-parallel-repro
python experiments/context_sweep/stage_dataset.py \
  --source /path/to/GPU_Datasets/data/preproduction_llama32_3b_500f_6ctx_v1
python experiments/context_sweep/stage_dataset.py --verify-only
```

The complete six-context source benchmark is staged so its original combined hash remains
verifiable. CP2 selects only its 8K, 16K, and 32K instances.

## Stage the model

```bash
python experiments/context_sweep/stage_model.py
HF_HUB_OFFLINE=1 python experiments/context_sweep/stage_model.py --verify-only
```

## Run

Use Python 3.12, PyTorch `2.12.0+cu130`, Transformers `5.11`, CUDA 13.0,
and `ninja`:

```bash
export CP_WORKSPACE=/workspace/context-parallel-repro
bash experiments/context_sweep/run_context_sweep.sh
```

The launcher performs preflight, runs and validates a six-instance smoke test, executes
all 1,500 instances, validates complete runtime accounting and answer structure, writes
`summary.csv`, hashes the persistent artifacts, and creates `COMPLETE.json`.

## Grade afterward on CPU

```bash
python experiments/context_sweep/grade_results.py \
  --gpu-datasets-repo /path/to/GPU_Datasets \
  --results /workspace/context-parallel-repro/results/qwen25_7b_cp_gpu_dataset_8k_32k_v1/results.jsonl \
  --out /workspace/context-parallel-repro/grading/qwen25_7b_cp_gpu_dataset_8k_32k_v1
```

The grading script verifies the frozen grader hash before producing scored JSONL, CSV,
and per-context accuracy/error summaries. Rows requiring semantic review must follow the
same adjudication process as the earlier experiments.
