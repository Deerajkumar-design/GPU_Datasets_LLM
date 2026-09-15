"""Kernel-latency profiling SWEEP across context lengths (prefill-only).
Loads the model once, profiles cp_generate(max_new=1) at each CTX, and prints a
comparison table + CSV of per-category GPU time and key per-kernel latencies.

    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    CTXS=50000,250000,400000,650000,800000,931951 \
    torchrun --standalone --nproc_per_node=3 profile_sweep.py
    (prepend ZIGZAG=1 for the balanced path)
"""
import os, time, csv, torch, torch.distributed as dist
from torch.profiler import profile, ProfilerActivity
import cp_infer
from cp_infer import cp_generate, tok, RANK, DEV

CTXS = [int(x) for x in os.environ.get("CTXS", "50000,250000,400000,650000,800000,931951").split(",")]
ZIGZAG = os.environ.get("ZIGZAG", "0") == "1"

book_ids = tok(open("/workspace/book.txt").read(), add_special_tokens=False, return_tensors="pt")["input_ids"]
qa = tok("\n\nQuestion: List the pipeline hazards.\nAnswer:", add_special_tokens=False, return_tensors="pt")["input_ids"]

def dev_us(e):
    return getattr(e, "self_device_time_total", None) or getattr(e, "self_cuda_time_total", 0)

def leaf_kernels(evs):                                   # leaf GPU kernels only (no double count)
    out = []
    for e in evs:
        t = dev_us(e)
        if t <= 0 or getattr(e, "self_cpu_time_total", 0) > 0 or e.key.startswith("nccl:"):
            continue
        out.append((e.key.lower(), t, e.count))
    return out

def categorize(leaf):
    c = {"attention": 0., "matmul": 0., "comms": 0., "elementwise": 0., "other": 0.}
    for n, t, _ in leaf:
        if "flash" in n or "fmha" in n or "attention" in n:                         c["attention"] += t
        elif "gemm" in n or "cutlass" in n or "ampere" in n or "matmul" in n:        c["matmul"] += t
        elif "nccl" in n or "sendrecv" in n:                                         c["comms"] += t
        elif any(s in n for s in ("elementwise", "vectorized", "reduce", "norm",
                                  "cat", "copy", "silu", "pow", "cast")):            c["elementwise"] += t
        else:                                                                        c["other"] += t
    return c

def kern(leaf, sub):                                     # (total_ms, avg_us) for kernels matching sub
    tot, cnt = 0., 0
    for n, t, c in leaf:
        if sub in n:
            tot += t; cnt += c
    return tot / 1e3, (tot / cnt if cnt else 0.)

rows = []
cp_generate(book_ids[:, :64], max_new=1, zigzag=ZIGZAG)          # warmup
for ctx in CTXS:
    ids = torch.cat([book_ids[:, :ctx], qa], dim=1)
    N = ids.shape[1]
    torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats(DEV)
    dist.barrier(); t0 = time.time()
    with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA]) as prof:
        cp_generate(ids, max_new=1, zigzag=ZIGZAG)
    dist.barrier(); wall = time.time() - t0
    if RANK == 0:
        leaf = leaf_kernels(prof.key_averages())
        cats = categorize(leaf); tot = sum(cats.values()) or 1.0
        _, flash_us = kern(leaf, "flash")
        gemm_ms, _ = kern(leaf, "gemm")
        nccl_ms, _ = kern(leaf, "nccldevkernel")
        rows.append(dict(ctx=N, wall_s=round(wall, 1),
                         peakGB=round(torch.cuda.max_memory_allocated(DEV) / 1e9, 1),
                         gpu_ms=round(tot / 1e3, 1),
                         attn_pct=round(100 * cats["attention"] / tot, 1),
                         mm_pct=round(100 * cats["matmul"] / tot, 1),
                         comms_pct=round(100 * cats["comms"] / tot, 1),
                         elem_pct=round(100 * cats["elementwise"] / tot, 1),
                         flash_us=round(flash_us, 0), gemm_ms=round(gemm_ms, 1),
                         nccl_ms=round(nccl_ms, 1)))
        print(f"  done ctx={N:>7} wall={wall:6.1f}s  attn={rows[-1]['attn_pct']}%", flush=True)
    del prof; torch.cuda.empty_cache()

if RANK == 0:
    print(f"\n=== KERNEL-LATENCY SWEEP (prefill, mode={'zigzag' if ZIGZAG else 'contiguous'}) ===")
    h = (f"{'ctx':>8} {'wall_s':>7} {'peakGB':>7} {'gpu_ms':>8} {'attn%':>6} {'mm%':>6} "
         f"{'comms%':>7} {'elem%':>6} {'flash_us':>9} {'gemm_ms':>8} {'nccl_ms':>8}")
    print(h)
    for r in rows:
        print(f"{r['ctx']:>8} {r['wall_s']:>7} {r['peakGB']:>7} {r['gpu_ms']:>8} {r['attn_pct']:>6} "
              f"{r['mm_pct']:>6} {r['comms_pct']:>7} {r['elem_pct']:>6} "
              f"{r['flash_us']:>9.0f} {r['gemm_ms']:>8} {r['nccl_ms']:>8}")
    with open("/workspace/profile_sweep.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print("\nsaved -> /workspace/profile_sweep.csv")
dist.destroy_process_group()
