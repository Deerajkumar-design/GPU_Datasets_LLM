"""Fine-grained per-RANK kernel profiling at one context length, to expose whether
'comms' time is real transfer or load-imbalance stall.

    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CTX=650000 \
    torchrun --standalone --nproc_per_node=3 profile_finegrained.py
    (prepend ZIGZAG=1 for the balanced path)
"""
import os, time, torch, torch.distributed as dist
from torch.profiler import profile, ProfilerActivity
import cp_infer
from cp_infer import cp_generate, tok, RANK, WORLD, DEV

CTX = int(os.environ.get("CTX", "650000"))
ZIGZAG = os.environ.get("ZIGZAG", "0") == "1"
cfg = cp_infer.model.config
Hkv, Dh, L = cfg.num_key_value_heads, cfg.head_dim if hasattr(cfg, "head_dim") else 128, cfg.num_hidden_layers

book = tok(open("/workspace/book.txt").read(), add_special_tokens=False, return_tensors="pt")["input_ids"]
qa = tok("\n\nQuestion: List the pipeline hazards.\nAnswer:", add_special_tokens=False, return_tensors="pt")["input_ids"]
ids = torch.cat([book[:, :CTX], qa], dim=1)
N = ids.shape[1]

def dev_us(e):
    return getattr(e, "self_device_time_total", None) or getattr(e, "self_cuda_time_total", 0)

def per_rank_cats(evs):
    c = {"attention": 0., "matmul": 0., "comms": 0., "elementwise": 0., "other": 0.}
    for e in evs:
        t = dev_us(e)
        if t <= 0 or getattr(e, "self_cpu_time_total", 0) > 0 or e.key.startswith("nccl:"):
            continue
        n = e.key.lower()
        if "flash" in n or "fmha" in n or "attention" in n:                  c["attention"] += t
        elif "gemm" in n or "cutlass" in n or "ampere" in n or "matmul" in n: c["matmul"] += t
        elif "nccl" in n or "sendrecv" in n:                                  c["comms"] += t
        elif any(s in n for s in ("elementwise", "vectorized", "reduce", "norm",
                                  "cat", "copy", "silu", "pow", "cast")):     c["elementwise"] += t
        else:                                                                 c["other"] += t
    return {k: v / 1e6 for k, v in c.items()}                                 # -> seconds

cp_generate(book[:, :64], max_new=1, zigzag=ZIGZAG)                            # warmup
dist.barrier()
with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA]) as prof:
    cp_generate(ids, max_new=1, zigzag=ZIGZAG)
dist.barrier()

mine = {"rank": RANK, **per_rank_cats(prof.key_averages())}
gathered = [None] * WORLD
dist.all_gather_object(gathered, mine)

if RANK == 0:
    mode = "zigzag" if ZIGZAG else "contiguous"
    print(f"\n=== FINE-GRAINED PER-RANK PROFILE  ctx={N}  mode={mode} ===")
    print(f"{'rank':>4} {'attn':>8} {'comms':>8} {'matmul':>8} {'elem':>7} {'total':>8}")
    for r in sorted(gathered, key=lambda x: x["rank"]):
        tot = r["attention"] + r["comms"] + r["matmul"] + r["elementwise"] + r["other"]
        print(f"{r['rank']:>4} {r['attention']:>8.1f} {r['comms']:>8.1f} {r['matmul']:>8.1f} "
              f"{r['elementwise']:>7.1f} {tot:>8.1f}")

    # theoretical transfer vs measured comms -> stall
    S = (2 * (N + 2*WORLD - 1)//(2*WORLD)) if ZIGZAG else ((N + WORLD - 1)//WORLD)  # local tokens/rank
    bytes_per_exchange = 2 * (Hkv * S * Dh * 2)              # k+v, bf16
    n_exchanges = (WORLD - 1) * L                            # per ring call, per layer
    gb = bytes_per_exchange * n_exchanges / 1e9
    nvlink_gbs = 200.0
    xfer_s = gb / nvlink_gbs
    measured_comms = max(r["comms"] for r in gathered)
    print(f"\n  KV moved/rank ≈ {gb:.1f} GB over {n_exchanges} exchanges")
    print(f"  theoretical NVLink transfer ≈ {xfer_s:.2f}s   (@ ~{nvlink_gbs:.0f} GB/s)")
    print(f"  measured comms (max rank)   ≈ {measured_comms:.1f}s")
    stall = max(0.0, measured_comms - xfer_s)
    print(f"  => ~{stall:.1f}s ({100*stall/measured_comms:.0f}%) is STALL / load-imbalance wait, not transfer")
    skew = max(r["attention"] for r in gathered) / (min(r["attention"] for r in gathered) or 1e-9)
    print(f"  attention skew across ranks: {skew:.1f}x  ({'balanced' if skew < 1.4 else 'IMBALANCED'})")
dist.destroy_process_group()
