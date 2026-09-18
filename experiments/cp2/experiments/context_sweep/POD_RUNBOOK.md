# CP2 64K/128K RunPod runbook

Follow these commands exactly. Do not change the model, package versions, prompt,
dataset builder, experiment configuration, or generation settings.

## 1. Clone and retrieve the frozen benchmark

```bash
mkdir -p /workspace/long-context-reliability
cd /workspace/long-context-reliability
git clone https://github.com/Deerajkumar-design/GPU_Datasets_LLM.git repo
cd repo

git lfs version
git lfs install
git lfs pull
git status --short
```

`git status --short` must print nothing. If `git lfs version` fails, install Git LFS
before continuing. Do not run with an LFS pointer in place of `instances.jsonl`.

## 2. Create the pinned software environment

Conda must be available. Do not reuse the Pod's default PyTorch environment and do not
install `requirements-b200.txt`.

```bash
conda create -n ring_atten python=3.12 -y
conda activate ring_atten
conda install -c nvidia cuda-toolkit=13.0 -y

export CUDA_HOME="$CONDA_PREFIX"
python -m pip install --upgrade pip
python -m pip install torch==2.12.0 \
  --index-url https://download.pytorch.org/whl/cu130
python -m pip install -r experiments/cp2/requirements-cp2.txt
python -m pip install -e .

export CP_WORKSPACE=/workspace/context-parallel-repro
python experiments/cp2/experiments/context_sweep/check_environment.py
```

Do not continue unless the last command prints `PASS: CP2 SOFTWARE ENVIRONMENT` with:

- Python 3.12.x
- PyTorch 2.12.0+cu130
- Transformers 5.11.x
- CUDA runtime and nvcc 13.0

## 3. Prepare and verify the dataset

```bash
conda activate ring_atten
export CUDA_HOME="$CONDA_PREFIX"
export CP_WORKSPACE=/workspace/context-parallel-repro
bash experiments/cp2/experiments/context_sweep/prepare_64k_128k.sh
```

Preparation downloads the pinned public Qwen snapshot, copies all frozen 64K instances,
builds 500 Qwen-tokenized 128K extensions, and verifies the resulting 1,000-instance
dataset. It can take a long time. If interrupted, rerun the same command from the same
clean Git commit and workspace; it resumes its partial checkpoint. Do not pull, rebase,
switch branches, or edit files between preparation and the GPU run. Preflight requires
the runtime checkout to match the commit recorded in the generated dataset configuration.

Do not continue unless it prints:

```text
64K/128K DATASET PREPARATION COMPLETE
```

## 4. Run on exactly three A100 80GB GPUs

```bash
conda activate ring_atten
export CUDA_HOME="$CONDA_PREFIX"
export CP_WORKSPACE=/workspace/context-parallel-repro
bash experiments/cp2/experiments/context_sweep/run_64k_128k.sh
```

The launcher stops on any failed environment or hardware preflight check. It then runs
and validates a four-instance smoke test before starting the full 1,000-instance run.
Do not bypass either gate.

The run is complete only when this file exists:

```text
/workspace/context-parallel-repro/results/qwen25_7b_cp_gpu_dataset_64k_128k_v1/COMPLETE.json
```

Rerun the same launch command after an interruption. Successful instance IDs are skipped.

## Stop conditions

Stop rather than improvising if:

- The repository is dirty or its commit changes during preparation.
- The environment checker, model verification, dataset verification, preflight, smoke
  validation, or final validation fails.
- There are not exactly three NVIDIA A100 GPUs with at least 80 GB each.
- Any instruction asks for a Llama tokenizer, an old normalized cache, a different model,
  or different package versions.
