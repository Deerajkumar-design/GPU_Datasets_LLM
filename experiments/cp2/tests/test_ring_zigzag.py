"""Verify zigzag (load-balanced) ring attention == single-GPU causal. bf16 + GQA.
Local layout: rank r owns global chunks r and 2W-1-r.
    torchrun --standalone --nproc_per_node=3 tests/test_ring_zigzag.py
"""
import os, sys, torch, torch.distributed as dist
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ring_attention import ring_attention_zigzag, _repeat_kv

LOCAL = int(os.environ.get("LOCAL_RANK", 0))
torch.cuda.set_device(LOCAL)
DEV = torch.device(f"cuda:{LOCAL}")
dist.init_process_group("nccl", device_id=DEV)
RANK, WORLD = dist.get_rank(), dist.get_world_size()

B, Hq, Hkv, D = 1, 28, 4, 128
c = 512                              # chunk size; 2W chunks total
S_total = 2 * WORLD * c
scale = D ** -0.5
g = torch.Generator().manual_seed(0)
fq = torch.randn(B, Hq,  S_total, D, generator=g).to(DEV).bfloat16()
fk = torch.randn(B, Hkv, S_total, D, generator=g).to(DEV).bfloat16()
fv = torch.randn(B, Hkv, S_total, D, generator=g).to(DEV).bfloat16()

def chunk(x, idx):                   # [B,H,c,D] for global chunk idx
    return x[:, :, idx * c:(idx + 1) * c]

a, bb = RANK, 2 * WORLD - 1 - RANK   # this rank's two global chunks
q = torch.cat([chunk(fq, a), chunk(fq, bb)], dim=2).contiguous()
k = torch.cat([chunk(fk, a), chunk(fk, bb)], dim=2).contiguous()
v = torch.cat([chunk(fv, a), chunk(fv, bb)], dim=2).contiguous()

out, _ = ring_attention_zigzag(q, k, v, scale=scale, causal=True)

# single-GPU reference, then pull this rank's two chunks
fkr = _repeat_kv(fk, Hq // Hkv).float()
fvr = _repeat_kv(fv, Hq // Hkv).float()
s = (fq.float() @ fkr.transpose(-1, -2)) * scale
mask = torch.triu(torch.ones(S_total, S_total, device=DEV, dtype=torch.bool), diagonal=1)
s = s.masked_fill(mask, float("-inf"))
rfull = torch.softmax(s, dim=-1) @ fvr
rout = torch.cat([chunk(rfull, a), chunk(rfull, bb)], dim=2)

eo = (out - rout).abs().max()
dist.all_reduce(eo, op=dist.ReduceOp.MAX)
dist.barrier()
if RANK == 0:
    print(f"GLOBAL max out err {eo.item():.2e}  (zigzag ring)")
    assert eo.item() < 3e-2, "ZIGZAG RING MISMATCH"
    print("ZIGZAG RING OK  (load-balanced, 3-GPU == single-GPU causal)")
dist.destroy_process_group()
