"""Verify the FAST ring backend (flash, bf16, GQA) across 3 GPUs vs single-GPU causal.
Uses Qwen-shaped heads: 28 query heads, 4 KV heads (GQA factor 7).
    torchrun --standalone --nproc_per_node=3 tests/test_ring_flash.py
"""
import os, sys, torch, torch.distributed as dist
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ring_attention import ring_attention, _repeat_kv

LOCAL = int(os.environ.get("LOCAL_RANK", 0))
torch.cuda.set_device(LOCAL)
DEV = torch.device(f"cuda:{LOCAL}")
dist.init_process_group("nccl", device_id=DEV)
RANK, WORLD = dist.get_rank(), dist.get_world_size()

B, Hq, Hkv, D = 1, 28, 4, 128
S = 512
S_total = WORLD * S
scale = D ** -0.5
g = torch.Generator().manual_seed(0)
fq = torch.randn(B, Hq,  S_total, D, generator=g).to(DEV).bfloat16()
fk = torch.randn(B, Hkv, S_total, D, generator=g).to(DEV).bfloat16()
fv = torch.randn(B, Hkv, S_total, D, generator=g).to(DEV).bfloat16()
sl = slice(RANK * S, (RANK + 1) * S)
q = fq[:, :, sl].contiguous()
k = fk[:, :, sl].contiguous()
v = fv[:, :, sl].contiguous()

# --- fast ring ---
out, _ = ring_attention(q, k, v, scale=scale, causal=True, backend="flash")  # fp32

# --- single-GPU fp32 reference (GQA expanded) ---
fkr = _repeat_kv(fk, Hq // Hkv).float()
fvr = _repeat_kv(fv, Hq // Hkv).float()
s = (fq.float() @ fkr.transpose(-1, -2)) * scale
mask = torch.triu(torch.ones(S_total, S_total, device=DEV, dtype=torch.bool), diagonal=1)
s = s.masked_fill(mask, float("-inf"))
rout = (torch.softmax(s, dim=-1) @ fvr)[:, :, sl]

eo = (out - rout).abs().max()
dist.all_reduce(eo, op=dist.ReduceOp.MAX)
dist.barrier()
if RANK == 0:
    print(f"GLOBAL max out err {eo.item():.2e}  (bf16 flash)")
    assert eo.item() < 3e-2, "FLASH RING MISMATCH"
    print("FLASH RING OK  (bf16 + GQA, 3-GPU == single-GPU causal)")
dist.destroy_process_group()
