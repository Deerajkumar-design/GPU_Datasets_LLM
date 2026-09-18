# Reproducible CP2 context sweep

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

## 64K and 128K extension

For a fresh RunPod setup, follow the canonical agent handoff document:
[`POD_RUNBOOK.md`](POD_RUNBOOK.md). It pins every installation and stop condition.

The completed `qwen25_7b_cp_gpu_dataset_8k_32k_v1` run remains frozen and unchanged.
The additional long-context run has its own experiment ID:

- Experiment: `qwen25_7b_cp_gpu_dataset_64k_128k_v1`
- Selected labels: `64K` and `128K`
- Runs: 1,000 unique family/context instances
- Parent benchmark: `preproduction_llama32_3b_500f_6ctx_v1`
- Derived benchmark: `preproduction_qwen25_7b_500f_128k_v1`

The parent benchmark has an 82K hardware-bounded condition, not a 128K condition. The
extension therefore constructs a true Qwen-tokenized 128K input instead of relabeling
82K data. The builder:

1. Reuses the exact frozen 500 question families.
2. Copies the existing frozen 64K instances unchanged.
3. Starts each 128K instance from its frozen 82K context.
4. Extends both sides with unique authentic same-domain records harvested from other
   frozen 82K contexts.
5. Excludes gold evidence, target-condition matches, answer-value leakage, and records
   that would invalidate an unanswerable question.
6. Uses the pinned Qwen tokenizer and exact CP2 chat prompt to target 128K rendered input.
7. Requires all 500 extensions, 98%-100% input fill, nested parent records, centered
   target evidence, unique records, and the safe 130,944-token input ceiling.
8. Computes a new dataset hash and writes a finalized external CP2 configuration.

No original raw/normalized cache and no Llama tokenizer are required. All extension
records come from the already-frozen dataset, so their source values and provenance are
fixed. The only model dependency is the public Qwen model/tokenizer used by CP2 itself.

### Build the 128K benchmark on persistent storage

Create the exact CP2 environment. Do not use `requirements-b200.txt`; it pins a
different PyTorch/CUDA stack.

```bash
cd /workspace/long-context-reliability/repo
git lfs install
git lfs pull
conda create -n ring_atten python=3.12 -y
conda activate ring_atten
conda install -c nvidia cuda-toolkit=13.0 -y
export CUDA_HOME="$CONDA_PREFIX"
python -m pip install torch==2.12.0 \
  --index-url https://download.pytorch.org/whl/cu130
python -m pip install -r experiments/cp2/requirements-cp2.txt
python -m pip install -e .
python experiments/cp2/experiments/context_sweep/check_environment.py
```

Build directly into the CP2 persistent workspace:

```bash
export CP_WORKSPACE=/workspace/context-parallel-repro
bash experiments/cp2/experiments/context_sweep/prepare_64k_128k.sh
```

The environment check must print `PASS: CP2 SOFTWARE ENVIRONMENT`. The preparation
wrapper repeats that check before downloading the model or building any extensions,
then stages the pinned Qwen model/tokenizer, builds all 500 extensions, verifies the
resulting dataset, and writes the finalized config. The Git worktree must be clean so
the manifest's repository commit contains the exact builder being executed.

```text
/workspace/context-parallel-repro/datasets/preproduction_qwen25_7b_500f_128k_v1/
  question_families.jsonl
  instances.jsonl
  extension_manifest.json
  cp2_experiment_config.json
```

### Run only the new 64K and 128K conditions

The launcher and every Python stage read `CP_EXPERIMENT_CONFIG`. Point it to the finalized
configuration produced by the dataset build:

```bash
export CP_WORKSPACE=/workspace/context-parallel-repro
conda activate ring_atten
export CUDA_HOME="$CONDA_PREFIX"
bash experiments/cp2/experiments/context_sweep/run_64k_128k.sh
```

The wrapper selects the finalized external configuration automatically. The launcher
performs hardware/software preflight, then runs two families at both new lengths as a
four-instance smoke test. Only after smoke validation passes does the full run execute
exactly 1,000 instances, validate them, write hashes, and create a completion marker
under:

```text
/workspace/context-parallel-repro/results/qwen25_7b_cp_gpu_dataset_64k_128k_v1/
```

Do not point the extension launcher at the unpinned
`experiment_config_64k_128k.template.json`; only the builder-generated configuration
contains the derived dataset hash and repository commit.

### Grade the extension on CPU

The derived dataset lives outside the repository, so pass it explicitly:

```bash
python experiments/cp2/experiments/context_sweep/grade_results.py \
  --gpu-datasets-repo /workspace/long-context-reliability/repo \
  --dataset-dir "$CP_WORKSPACE/datasets/preproduction_qwen25_7b_500f_128k_v1" \
  --results "$CP_WORKSPACE/results/qwen25_7b_cp_gpu_dataset_64k_128k_v1/results.jsonl" \
  --out "$CP_WORKSPACE/grading/qwen25_7b_cp_gpu_dataset_64k_128k_v1"
```

The 64K rows retain their frozen parent metadata. The 128K rows record Qwen-tokenized
context and rendered-input measurements; the derivation is recorded in
`extension_manifest.json`.

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
