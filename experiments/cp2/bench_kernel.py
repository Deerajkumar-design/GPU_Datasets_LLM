"""Benchmark: naive CUDA kernel (fp32) vs torch native flash op (bf16), single block."""
import torch, time
import cp_kernels

def bench(fn, iters=20, warmup=5):
    for _ in range(warmup): fn()
    torch.cuda.synchronize()
    t0 = time.time()
    for _ in range(iters): fn()
    torch.cuda.synchronize()
    return (time.time() - t0) / iters * 1e3      # ms

B, Hq, D = 1, 28, 128
scale = D ** -0.5
print(f"{'S':>7} {'naive(fp32)':>14} {'flash(bf16)':>14} {'gap':>8}")
for S in (2048, 4096, 8192):
    q = torch.randn(B, Hq, S, D, device="cuda")
    k = torch.randn(B, Hq, S, D, device="cuda")
    v = torch.randn(B, Hq, S, D, device="cuda")
    qb, kb, vb = q.bfloat16(), k.bfloat16(), v.bfloat16()

    t_naive = bench(lambda: cp_kernels.block_attn(q, k, v, scale, True))
    t_flash = bench(lambda: torch.ops.aten._scaled_dot_product_flash_attention(
        qb, kb, vb, 0.0, True, False, scale=scale))
    print(f"{S:>7} {t_naive:>11.2f}ms {t_flash:>11.3f}ms {t_naive/t_flash:>7.0f}x")
