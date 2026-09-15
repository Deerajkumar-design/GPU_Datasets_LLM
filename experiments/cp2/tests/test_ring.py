"""Verifies the ring_attention core across 3 GPUs vs single-GPU causal attention.
    torchrun --standalone --nproc_per_node=3 tests/test_ring.py
"""
import os, sys, torch, torch.distributed as dist
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # find ring_attention / cp_kernels
from ring_attention import ring_attention

LOCAL = int(os.environ.get("LOCAL_RANK", 0))
torch.cuda.set_device(LOCAL)
DEV = torch.device(f"cuda:{LOCAL}")
dist.init_process_group("nccl", device_id=DEV)
RANK, WORLD = dist.get_rank(), dist.get_world_size()

# Identical full Q/K/V on every rank (CPU seed -> device), then take this rank's shard.
B, H, D = 1, 4, 128
S = 128
S_total = WORLD * S
scale = D ** -0.5
g = torch.Generator().manual_seed(0)
fq = torch.randn(B, H, S_total, D, generator=g).to(DEV)
fk = torch.randn(B, H, S_total, D, generator=g).to(DEV)
fv = torch.randn(B, H, S_total, D, generator=g).to(DEV)
sl = slice(RANK * S, (RANK + 1) * S)
q, k, v = fq[:, :, sl].contiguous(), fk[:, :, sl].contiguous(), fv[:, :, sl].contiguous()

# --- the core under test ---
out, lse = ring_attention(q, k, v, scale=scale, causal=True)

# --- single-GPU reference (full causal), compare this rank's shard ---
s = (fq @ fk.transpose(-1, -2)) * scale
mask = torch.triu(torch.ones(S_total, S_total, device=DEV, dtype=torch.bool), diagonal=1)
s = s.masked_fill(mask, float("-inf"))
rout = (torch.softmax(s, dim=-1) @ fv)[:, :, sl]
rlse = torch.logsumexp(s, dim=-1)[:, :, sl]

eo = (out - rout).abs().max()
el = (lse - rlse).abs().max()
dist.all_reduce(eo, op=dist.ReduceOp.MAX)
dist.all_reduce(el, op=dist.ReduceOp.MAX)
dist.barrier()
if RANK == 0:
    print(f"GLOBAL max out err {eo.item():.2e}   max lse err {el.item():.2e}")
    assert eo.item() < 1e-3 and el.item() < 1e-3, "RING MISMATCH"
    print("RING ATTENTION OK  (3-GPU == single-GPU causal attention)")
dist.destroy_process_group()
