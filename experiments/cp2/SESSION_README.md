# Context Parallelism (Ring Attention) on 3× A100 — Session Log

A from-scratch context-parallel inference engine for **Qwen2.5-7B-Instruct-1M**, built and
profiled across one session. Splits a single long sequence across 3 GPUs (ring attention),
runs real inference on a ~1M-token document, and profiles where every millisecond goes.

---

## 1. System & Environment

| Item | Value |
|---|---|
| GPUs | 3× **A100-SXM4-80GB**, full **NV12 NVLink mesh** (~160 GB/s measured P2P) |
| conda env | **`ring_atten`** → `/root/anaconda3/envs/ring_atten/bin/python` |
| Python / torch | 3.12 / **torch 2.12.0+cu130** |
| transformers | 5.11 |
| CUDA toolkit | **13.0** installed into the env (matches torch's cu130) |
| Model | `Qwen/Qwen2.5-7B-Instruct-1M` (cached) |

**Model config:** 28 layers, **28 query heads / 4 KV heads** (GQA factor 7), head_dim 128,
`max_position_embeddings=1,010,000`, RoPE `default` with `rope_theta=1e7` (NOT YaRN).

**Key enabler:** torch 2.12 exposes flash attention natively *with* the log-sum-exp:
```python
out, lse = torch.ops.aten._scaled_dot_product_flash_attention(q,k,v,0.0,causal,False,scale=s)[:2]
```
→ **no `flash-attn` / `ring-flash-attn` install needed**, and **no PyTorch source build**.

### One-time setup (already done)
```bash
conda create -n ring_atten python=3.12 -y && conda activate ring_atten
# torch/transformers/accelerate/datasets already installed
conda install -c nvidia cuda-toolkit=13.0 -y      # nvcc 13 to match torch cu130
pip install ninja                                 # required for cpp_extension
export CUDA_HOME=/root/anaconda3/envs/ring_atten  # used by the kernel build
```

---

## 2. How the Context Parallelism Works

- **Weights are replicated** on every GPU (15.3 GB/GPU). CP shards the **sequence**, not the weights.
- Only **attention** communicates. MLP, norms, RoPE, residuals are per-token → run locally.
- **Prefill** = the **ring**: each GPU holds its KV shard; KV rotates GPU→GPU; each block is
  folded into a running `(max, sum, output)` via **online softmax** (the `lse` merge).
- **Decode** = replicate the 1-token query, shard KV, **all-gather** the partial results + merge.
- Run with `use_cache=False`; we manage the sharded KV cache ourselves. `logits_to_keep` avoids
  building a 100 GB logits tensor at 1M tokens.

---

## 3. File Reference

### Core library
| File | What it is |
|---|---|
| `csrc/block_attn.cu` | CUDA kernels: `block_attn` (naive fp32), `attn_accumulate` (online-softmax state), `block_attn_fast` (optimized bf16 flash-style) |
| `cp_kernels.py` | JIT-compiles `block_attn.cu`, exposes the 3 kernels |
| `ring_attention.py` | **CP core**: `ring_attention(...)` (backends `flash`/`kernel`/`kernel_fast`), `ring_attention_zigzag(...)`, `ring_exchange`, `_merge`, `_repeat_kv`, `_flash_block` |
| `cp_infer.py` | **Inference engine**: `cp_attention` (registered via `AttentionInterface`), `_decode_attention`, `cp_generate(prompt, max_new, zigzag)` |
| `setup_model.py` | Loads Qwen replicated on 3 GPUs + sanity generation |
| `run_book.py` | Book Q&A driver (env: `CTX`, `MAXNEW`, `ZIGZAG`) |
| `book.txt` | Extracted text of *Computer Architecture: A Quantitative Approach* (931,951 tokens) |

### Tests (`tests/`) — the verification ladder
| File | Proves |
|---|---|
| `hello_cuda.py` | CUDA build chain works |
| `test_merge.py` | online-softmax merge math (pure Python) |
| `test_block_attn.py` | `block_attn` kernel == PyTorch (1e-6) |
| `test_accumulate.py` | multi-block accumulation == full attention |
| `test_ring.py` | 3-GPU ring (naive kernel) == single-GPU |
| `test_ring_flash.py` | bf16 + GQA flash ring == single-GPU (8e-3) |
| `test_ring_fast.py` | optimized-kernel ring == single-GPU |
| `test_ring_zigzag.py` | zigzag (load-balanced) ring == single-GPU (8.8e-3) |
| `test_fast_kernel.py` | `block_attn_fast` correctness + speed vs naive/flash |

### Benchmark / profiling
| File | What it measures |
|---|---|
| `bench_kernel.py` | naive kernel vs native flash |
| `profile_kernels.py` | per-kernel latency table at one context |
| `profile_sweep.py` | kernel breakdown across context lengths → CSV |
| `profile_finegrained.py` | **per-rank** breakdown + stall-vs-transfer decomposition |
| `profile_attention.py` | flash launch count, per-shape, achieved TFLOPS / MFU |
| `profile_flash_dsweep.py` | head-dim sweep: matmul/mem vs softmax split |
| `profile_flash_ssweep.py` | seq sweep: compute (S²) vs memory (S) split |
| `profile_decode.py` | decode per-token latency + KV/weight read bandwidth |
| `profile_bucket_cost.py` | bucketing cost — register/private bins |
| `profile_bucket_smem.py` | bucketing cost — shared-mem atomics |
| `profile_bucketsort_cost.py` | materialize + value-sort cost (HBM BW + sort rate) |
| `flash_one.py` | isolated flash call (for ncu, which is blocked here) |

---

## 4. Commands to Run Everything

> **Always clear stragglers first** — orphaned workers from a killed run keep the GPUs at
> 100% and make the next `torchrun` hang on NCCL init:
> ```bash
> pkill -9 -f torchrun; pkill -9 -f run_book; pkill -9 -f profile_; sleep 3
> nvidia-smi --query-gpu=index,memory.used --format=csv,noheader   # want 0 MiB on all 3
> # if memory still held: nvidia-smi --query-compute-apps=pid --format=csv,noheader | xargs -r kill -9
> ```

### Setup / sanity
```bash
# load model on 3 GPUs + sanity generation
torchrun --standalone --nproc_per_node=3 setup_model.py
```

### Tests (run from /workspace)
```bash
PY=/root/anaconda3/envs/ring_atten/bin/python
$PY tests/hello_cuda.py
$PY tests/test_merge.py
$PY tests/test_block_attn.py
$PY tests/test_accumulate.py
$PY tests/test_fast_kernel.py
torchrun --standalone --nproc_per_node=3 tests/test_ring.py
torchrun --standalone --nproc_per_node=3 tests/test_ring_flash.py
torchrun --standalone --nproc_per_node=3 tests/test_ring_fast.py
torchrun --standalone --nproc_per_node=3 tests/test_ring_zigzag.py
```

### Inference engine validation (short prompt vs stock attention)
```bash
torchrun --standalone --nproc_per_node=3 cp_infer.py
```

### Run the book (Q&A over the document)
```bash
# CTX = number of book tokens; ZIGZAG=1 for load-balanced; MAXNEW = tokens to generate
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True ZIGZAG=1 CTX=650000 MAXNEW=80 \
  torchrun --standalone --nproc_per_node=3 run_book.py
```

### Benchmark the kernel
```bash
/root/anaconda3/envs/ring_atten/bin/python bench_kernel.py
```

### Profiling
```bash
PY=/root/anaconda3/envs/ring_atten/bin/python

# per-kernel latency table at one context (prefill only)
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CTX=650000 MAXNEW=1 \
  torchrun --standalone --nproc_per_node=3 profile_kernels.py

# sweep across context lengths -> profile_sweep.csv
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  CTXS=50000,250000,400000,650000,800000,931951 \
  torchrun --standalone --nproc_per_node=3 profile_sweep.py

# per-rank stall decomposition (run both to see zigzag fix the stall)
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CTX=650000 \
  torchrun --standalone --nproc_per_node=3 profile_finegrained.py            # contiguous
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True ZIGZAG=1 CTX=650000 \
  torchrun --standalone --nproc_per_node=3 profile_finegrained.py            # balanced

# attention detail (flash launches, TFLOPS, MFU)
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True ZIGZAG=1 CTX=650000 \
  torchrun --standalone --nproc_per_node=3 profile_attention.py

# kernel-internal decomposition (single GPU, fast)
$PY profile_flash_dsweep.py      # matmul/memory vs softmax (head-dim sweep)
$PY profile_flash_ssweep.py      # compute (S^2) vs memory (S) (seq sweep)

# decode profiling
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CTX=650000 DECODE_STEPS=16 ZIGZAG=1 \
  torchrun --standalone --nproc_per_node=3 profile_decode.py

# isolated NVLink comms cost (no compute)
torchrun --standalone --nproc_per_node=3 profile_comms.py

# bucketing-for-accuracy cost models (single GPU, fast)
$PY profile_bucket_cost.py       # register/private bins
$PY profile_bucket_smem.py       # shared-mem atomics
$PY profile_bucketsort_cost.py   # materialize + value sort
```

---

## 5. Results

### 5.1 Correctness (all verified bottom-up)
| Component | Error vs reference |
|---|---|
| `block_attn` / `attn_accumulate` kernels | ~1e-6 (fp32) |
| 3-GPU ring (naive kernel) | 8e-7 |
| bf16 + GQA flash ring | 8e-3 |
| optimized-kernel ring | 7.7e-3 |
| zigzag ring | 8.8e-3 |

### 5.2 Coherence ceiling (Qwen-1M, plain attention, no DCA)
| Context | Result |
|---|---|
| 50K / 250K / 400K / **650K** | ✅ correct, coherent |
| 800K | ⚠️ starts right, then loops |
| 932K | ❌ garbage |

**The CP engine handles the full 932K mechanically** (77 GB/GPU, 558s). The garbage at >650K is a
**model** limit — Qwen-1M needs **Dual Chunk Attention (DCA)** to stay coherent to true 1M, which
our plain ring doesn't implement. **Usable max ≈ 650K.**

### 5.3 End-to-end latency (contiguous, with decode)
| Context | Latency |
|---|---|
| 50K | 6.6s |
| 250K | 51s |
| 400K | 115s |
| 650K | 281s |
| 800K | 418s |
| 932K | 558s |

### 5.4 Kernel optimization (`block_attn_fast`)
Naive kernel is **262–336× slower** than native flash. The optimized kernel (warp-per-query,
bf16, shared-mem K/V tiling) is **7× faster than naive** but still **35–49× behind** native flash —
the gap is **tensor cores (MMA)**, which the native op uses and a CUDA-core kernel cannot match.
The production path uses the native flash op inside the ring.

### 5.5 Zigzag load balancing (650K, prefill-only GPU time)
| | contiguous | zigzag |
|---|---|---|
| comm/nccl | 164.2s (**99% stall**) | **0.5s** |
| attention | 43.9s (rank 0, imbalanced) | 146.0s (all ranks, balanced, skew 1.0×) |
| **total** | **221s** | **162s** (**1.36×**) |

The contiguous "comms" was **not** transfer — it was load-imbalance **stall** (fast ranks spinning in
`SendRecv` waiting for the overloaded rank). Proof: isolated NVLink transfer of all 24.8 GB =
**0.156s @ 160 GB/s** (`profile_comms.py`). Zigzag balances the work, the stall vanishes.

### 5.6 Prefill attention decomposition (650K, zigzag, 146s/GPU)
- **84 flash launches** (3/layer × 28 layers): 28 diagonal (217K×217K causal) + 56 off-diagonal.
- **194 TFLOPS/GPU = 62% MFU** (near the ~65–70% practical flash ceiling).
- Decomposition (head-dim + seq sweeps):
  - **~124s (85%)** QK·ᵀ + P·V tensor-core matmuls
  - **~20s (14%)** softmax statistics (max / exp on SFU / sum)
  - **~2s (1.5%)** KV/Q memory loads (negligible at long context)

Sub-kernel hardware-counter profiling (`ncu`) is **blocked** in this container (`ERR_NVGPUCTRPERM`).

### 5.7 Decode (650K, zigzag)
- **340.9 ms/token (2.9 tok/s)** — memory bound, not compute bound.
- weight read: 15.2 GB/token → **1604 GB/s (79% HBM)** ✓ healthy.
- KV read: 12.4 GB/token → 252 GB/s (12% HBM).
- ⚠️ **74% of decode is "elementwise"** — a **bug**: `_repeat_kv` materializes the GQA-expanded KV
  (×7) and `torch.cat` reallocates the whole KV cache every step. Fixable → decode should drop to
  ~60–80 ms/token. (Captured as **task #9**, not yet fixed.)

### 5.8 Total inference (650K)
```
zigzag prefill 162s  +  80 decode tokens × 0.34s ≈ 27s  =  ~189s
```
(With the decode KV-cache fix, decode ≈ 6s → total ≈ ~168s.)

---

## 6. Exponent-Bucketing Before Softmax (accuracy study, design only)

Goal: reduce FP cancellation error in the softmax denominator (small errors flip logits).
**No cross-GPU communication needed** — the online-softmax `lse` merge already combines per-GPU
partial softmaxes; bucketing is **local per block** (runs W×L = 84 times/GPU, over `causal-scores/W`
≈ 5.5×10¹³ scores/GPU at 650K).

**Measured cost of the added work (added to the 162s prefill):**
| Implementation | +overhead @650K | total inference |
|---|---|---|
| **privatized** (per-thread register bins → reduce to B shared buckets at end → sort B) | **+22–91s** | 205–230s |
| scatter-based (reduction phase dominates ~50%) | ~+408s | ~597s |
| naive shared-mem atomics per score | +1137s (contention) | ~1300s |
| full value-sort + materialize (221 TB, 2.1 h sort) | +~8000s | infeasible |

**Conclusion:** sort only the **B buckets** (not the values), accumulate with **privatized register
bins** (not per-score shared-mem atomics), keep it **fused** (no materialization). That keeps the
accuracy fix in the **+22–91s** regime. The scatter/reduction phase is the thing to avoid — it's the
difference between +14% and +700%.

---

## 7. Known TODOs / Next Steps
- **Fix decode** (task #9): preallocate KV cache, drop `_repeat_kv` materialization → ~5× faster decode.
- **DCA** for coherent true-1M (model-side, separate from CP).
- **Tensor-core (`wmma`) kernel** to close the 35–49× gap to native flash (large effort).
- **Bucketing**: implement the privatized binned-summation in the ring's online-softmax merge.
- Zigzag is correct + faster but `cp_infer.cp_generate(zigzag=True)` should become the default for runs.
