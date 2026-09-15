"""Correctness + speed of the optimized block_attn_fast kernel.
Checks vs fp32 reference, then benchmarks vs naive kernel and native flash op.
    python tests/test_fast_kernel.py
"""
import os, sys, time, torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cp_kernels

def ref(q, k, v, scale, causal):
    s = (q.float() @ k.float().transpose(-1, -2)) * scale
    if causal:
        S = s.shape[-1]
        s = s.masked_fill(torch.triu(torch.ones(S, S, device=s.device, dtype=torch.bool), 1), float("-inf"))
    return torch.softmax(s, -1) @ v.float(), torch.logsumexp(s, -1)

def bench(fn, iters=20, warmup=5):
    for _ in range(warmup): fn()
    torch.cuda.synchronize(); t0 = time.time()
    for _ in range(iters): fn()
    torch.cuda.synchronize()
    return (time.time() - t0) / iters * 1e3

torch.manual_seed(0)
B, H, D = 1, 28, 128
print("--- correctness (bf16) ---")
for causal in (False, True):
    S = 2048
    q = torch.randn(B, H, S, D, device="cuda", dtype=torch.bfloat16)
    k = torch.randn(B, H, S, D, device="cuda", dtype=torch.bfloat16)
    v = torch.randn(B, H, S, D, device="cuda", dtype=torch.bfloat16)
    o, l = cp_kernels.block_attn_fast(q, k, v, D ** -0.5, causal)
    ro, rl = ref(q, k, v, D ** -0.5, causal)
    eo = (o.float() - ro).abs().max().item()
    el = (l - rl).abs().max().item()
    print(f"causal={causal}:  out err {eo:.2e}  lse err {el:.2e}")
    assert eo < 3e-2 and el < 3e-2, "FAST KERNEL MISMATCH"
print("FAST KERNEL CORRECT\n")

print("--- speed vs naive vs native flash ---")
print(f"{'S':>7} {'naive':>10} {'ours_fast':>11} {'flash':>10} {'vs_naive':>9} {'vs_flash':>9}")
for S in (2048, 4096, 8192):
    qf = torch.randn(B, H, S, D, device="cuda")           # fp32 for naive
    q = qf.bfloat16(); k = torch.randn(B, H, S, D, device="cuda").bfloat16()
    v = torch.randn(B, H, S, D, device="cuda").bfloat16()
    sc = D ** -0.5
    t_naive = bench(lambda: cp_kernels.block_attn(qf, qf, qf, sc, True))
    t_fast  = bench(lambda: cp_kernels.block_attn_fast(q, k, v, sc, True))
    t_flash = bench(lambda: torch.ops.aten._scaled_dot_product_flash_attention(q, k, v, 0.0, True, False, scale=sc))
    print(f"{S:>7} {t_naive:>8.2f}ms {t_fast:>9.3f}ms {t_flash:>8.3f}ms "
          f"{t_naive/t_fast:>7.0f}x {t_fast/t_flash:>7.1f}x")
