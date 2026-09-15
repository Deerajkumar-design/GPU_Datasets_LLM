"""Detailed DECODE profiling (parallel to the prefill analysis).
Decode = one new token attending to the whole sharded KV cache, so it's
memory-bandwidth bound (reads all weights + all KV every token), not compute bound.

Runs prefill once (max_new=1) to populate the KV cache, then profiles M decode steps:
per-token latency, category breakdown, and achieved KV-read / weight-read GB/s vs HBM.

    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CTX=650000 DECODE_STEPS=16 \
    torchrun --standalone --nproc_per_node=3 profile_decode.py
"""
import os, torch, torch.distributed as dist
from torch.profiler import profile, ProfilerActivity
import cp_infer
from cp_infer import cp_generate, model, tok, RANK, WORLD, DEV

CTX = int(os.environ.get("CTX", "650000"))
M = int(os.environ.get("DECODE_STEPS", "16"))
ZIGZAG = os.environ.get("ZIGZAG", "1") == "1"
HBM = 2039.0                                    # A100-80GB HBM2e GB/s

book = tok(open("/workspace/book.txt").read(), add_special_tokens=False, return_tensors="pt")["input_ids"]
qa = tok("\n\nQuestion: List the pipeline hazards.\nAnswer:", add_special_tokens=False, return_tensors="pt")["input_ids"]
ids = torch.cat([book[:, :CTX], qa], dim=1)
N = ids.shape[1]

# prefill: populates cp_infer.KV, leaves CP["phase"]="decode"
gen = cp_generate(ids, max_new=1, zigzag=ZIGZAG)
nxt = gen[:, :1].to(DEV)
cur = N

def step():
    global nxt, cur
    cp_infer.CP["owner"] = cur % WORLD
    out = model(input_ids=nxt, position_ids=torch.tensor([[cur]], device=DEV),
                use_cache=False, logits_to_keep=1)
    nxt = out.logits[:, -1, :].argmax(-1).view(1, 1)
    dist.broadcast(nxt, src=0)
    cur += 1

for _ in range(3):                              # warmup
    step()
dist.barrier()

e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
torch.cuda.synchronize(); e0.record()
with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA]) as prof:
    for _ in range(M):
        step()
e1.record(); torch.cuda.synchronize(); dist.barrier()
ms_per_tok = e0.elapsed_time(e1) / M

def dev_us(e):
    return getattr(e, "self_device_time_total", None) or getattr(e, "self_cuda_time_total", 0)

if RANK == 0:
    cats = {"attention(KV read)": 0., "matmul(weight read)": 0., "comms(all-gather)": 0., "elementwise": 0., "other": 0.}
    for e in prof.key_averages():
        t = dev_us(e)
        if t <= 0 or getattr(e, "self_cpu_time_total", 0) > 0 or e.key.startswith("nccl:"):
            continue
        n = e.key.lower()
        if "flash" in n or "fmha" in n or "attention" in n or "scaled_dot" in n: cats["attention(KV read)"] += t
        elif "gemm" in n or "cutlass" in n or "ampere" in n or "gemv" in n or "matmul" in n: cats["matmul(weight read)"] += t
        elif "nccl" in n or "allgather" in n or "all_gather" in n:               cats["comms(all-gather)"] += t
        elif any(s in n for s in ("elementwise","vectorized","reduce","norm","cat","copy","silu","pow","cast")): cats["elementwise"] += t
        else:                                                                    cats["other"] += t
    tot = sum(cats.values()) or 1.0

    kvlen = cp_infer.KV[0][0].shape[2]
    cfg = model.config
    Hkv, Dh, Lyr = cfg.num_key_value_heads, getattr(cfg, "head_dim", 128), cfg.num_hidden_layers
    kv_gb = Lyr * 2 * Hkv * kvlen * Dh * 2 / 1e9            # K+V read per token, this rank
    w_gb = sum(p.numel() * p.element_size() for p in model.parameters()) / 1e9

    attn_ms = cats["attention(KV read)"] / 1e3 / M          # ms/token
    mm_ms = cats["matmul(weight read)"] / 1e3 / M
    print(f"\n=== DECODE PROFILE  ctx={N}  steps={M}  mode={'zigzag' if ZIGZAG else 'contig'} ===")
    print(f"per-token latency: {ms_per_tok:.1f} ms   ({1000/ms_per_tok:.1f} tok/s)")
    print(f"\n{'category':<22}{'ms/token':>10}{'% gpu':>8}")
    for k, val in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"{k:<22}{val/1e3/M:>10.2f}{100*val/tot:>7.1f}%")
    print(f"\n--- memory-bandwidth check (per rank, per token) ---")
    print(f"KV read   : {kv_gb:.1f} GB in {attn_ms:.2f} ms -> {kv_gb/(attn_ms/1e3):.0f} GB/s  ({100*kv_gb/(attn_ms/1e3)/HBM:.0f}% of HBM {HBM:.0f})")
    print(f"weight read: {w_gb:.1f} GB in {mm_ms:.2f} ms -> {w_gb/(mm_ms/1e3):.0f} GB/s  ({100*w_gb/(mm_ms/1e3)/HBM:.0f}% of HBM)")
    print(f"\nKV cache len/rank = {kvlen:,} tokens")
dist.destroy_process_group()
