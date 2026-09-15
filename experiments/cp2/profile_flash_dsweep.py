"""Separate flash-kernel time into d-dependent work (matmul + KV memory) vs
d-independent work (softmax exp/max/sum), via a head_dim sweep.
Per score: the two matmuls and KV loads scale with head_dim d; the softmax
statistics (max, exp, sum) are per-score, independent of d. Fit T(d) = a*d + b;
b (the d->0 intercept) is the softmax-stat floor.
    python profile_flash_dsweep.py
"""
import torch, time

def bench(fn, it=40, wu=10):
    for _ in range(wu): fn()
    torch.cuda.synchronize(); t = time.time()
    for _ in range(it): fn()
    torch.cuda.synchronize()
    return (time.time() - t) / it * 1e3                  # ms

H, S = 16, 8192
res = {}
for D in (64, 128, 256):
    q = torch.randn(1, H, S, D, device="cuda", dtype=torch.bfloat16)
    k = torch.randn(1, H, S, D, device="cuda", dtype=torch.bfloat16)
    v = torch.randn(1, H, S, D, device="cuda", dtype=torch.bfloat16)
    res[D] = bench(lambda: torch.ops.aten._scaled_dot_product_flash_attention(
        q, k, v, 0.0, True, False, scale=D ** -0.5))
    print(f"  head_dim={D:>3}:  {res[D]:.3f} ms")

# linear fit T(d) = a*d + b  using d=64 and d=256 endpoints
a = (res[256] - res[64]) / (256 - 64)
b = res[64] - a * 64
print(f"\nfit  T(d) = {a:.4f}*d + {b:.3f} ms     (b = d-independent softmax floor)")
for D in (128,):
    dpart = a * D
    total = a * D + b
    print(f"\n=== flash kernel @ head_dim={D} ===")
    print(f"  d-dependent (matmul QK^T+P·V, KV loads, acc-rescale): {100*dpart/total:4.0f}%")
    print(f"  d-independent (softmax max/exp/sum)                 : {100*b/total:4.0f}%")
    print(f"\n  applied to 650K attention = 146s/GPU:")
    print(f"    ~{146*dpart/total:4.0f}s  matmul-dominated (tensor cores) + KV memory")
    print(f"    ~{146*b/total:4.0f}s  softmax statistics (exp on SFU, max/sum)")
