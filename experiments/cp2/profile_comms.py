"""Isolated measurement of the ring KV-exchange cost at 650K sizes — no compute, so
NO load-imbalance stall can hide in it. Gives the TRUE transfer time + achieved NVLink BW.
    torchrun --standalone --nproc_per_node=3 profile_comms.py
"""
import os, torch, torch.distributed as dist

LOCAL = int(os.environ.get("LOCAL_RANK", 0))
torch.cuda.set_device(LOCAL)
DEV = torch.device(f"cuda:{LOCAL}")
dist.init_process_group("nccl", device_id=DEV)
RANK, WORLD = dist.get_rank(), dist.get_world_size()

def ring_exchange(k, v):
    send, recv = (RANK + 1) % WORLD, (RANK - 1) % WORLD
    kn, vn = torch.empty_like(k), torch.empty_like(v)
    ops = [dist.P2POp(dist.isend, k, send), dist.P2POp(dist.isend, v, send),
           dist.P2POp(dist.irecv, kn, recv), dist.P2POp(dist.irecv, vn, recv)]
    for r in dist.batch_isend_irecv(ops):
        r.wait()
    return kn, vn

# exact zigzag-650K shard geometry
CTX = int(os.environ.get("CTX", "650000"))
Hkv, D, L = 4, 128, 28
nch = 2 * WORLD
pad = ((CTX + nch - 1) // nch) * nch
S = 2 * (pad // nch)                          # local tokens/rank
n_ex = (WORLD - 1) * L                        # exchanges per prefill forward
k = torch.randn(1, Hkv, S, D, device=DEV, dtype=torch.bfloat16)
v = torch.randn(1, Hkv, S, D, device=DEV, dtype=torch.bfloat16)
bytes_per_ex = 2 * (Hkv * S * D * 2)          # k+v sent, bf16
total_gb = n_ex * bytes_per_ex / 1e9

for _ in range(5):                            # warmup
    k, v = ring_exchange(k, v)
torch.cuda.synchronize(); dist.barrier()

e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
e0.record()
for _ in range(n_ex):
    k, v = ring_exchange(k, v)
e1.record()
torch.cuda.synchronize(); dist.barrier()
ms = e0.elapsed_time(e1)

# single-exchange latency (to separate per-call overhead from bulk transfer)
torch.cuda.synchronize(); dist.barrier()
e0.record()
k, v = ring_exchange(k, v)
e1.record(); torch.cuda.synchronize()
ms1 = e0.elapsed_time(e1)

if RANK == 0:
    print(f"\nshard = {S:,} tok/rank   K+V per exchange = {bytes_per_ex/1e6:.0f} MB")
    print(f"{n_ex} exchanges = {total_gb:.1f} GB sent/rank")
    print(f"  total ring time : {ms/1e3:.3f} s")
    print(f"  per exchange    : {ms/n_ex:.2f} ms   (single-call measured: {ms1:.2f} ms)")
    print(f"  achieved BW     : {total_gb/(ms/1e3):.0f} GB/s/rank  (A100 NVLink peak ~300)")
dist.destroy_process_group()
