"""Separate the d-dependent 126s further: matmul-compute (scales S^2) vs
KV-memory + linear work (scales S). Flash loads each K/V tile once and reuses it
across the query block, so memory ~ S while the matmuls ~ S^2. Fit T = a*S^2 + g*S
(i.e. T/S = a*S + g) over a sequence sweep, then evaluate at the 650K block size.
    python profile_flash_ssweep.py
"""
import torch, time, numpy as np

def bench(fn, it=40, wu=10):
    for _ in range(wu): fn()
    torch.cuda.synchronize(); t = time.time()
    for _ in range(it): fn()
    torch.cuda.synchronize()
    return (time.time() - t) / it                        # seconds

H, D = 16, 128
Ss = [2048, 4096, 8192, 16384, 32768]
T = []
for S in Ss:
    q = torch.randn(1, H, S, D, device="cuda", dtype=torch.bfloat16)
    k = torch.randn(1, H, S, D, device="cuda", dtype=torch.bfloat16)
    v = torch.randn(1, H, S, D, device="cuda", dtype=torch.bfloat16)
    t = bench(lambda: torch.ops.aten._scaled_dot_product_flash_attention(q, k, v, 0.0, True, False, scale=D**-0.5))
    T.append(t); print(f"  S={S:>6}:  {t*1e3:8.3f} ms")

S = np.array(Ss, dtype=float); T = np.array(T)
a, g = np.polyfit(S, T / S, 1)                            # T/S = a*S + g
print(f"\nfit  T = {a:.3e}*S^2 + {g:.3e}*S        (a=compute coeff, g=linear/memory coeff)")

S650 = 650000 / 3                                          # ~ diagonal block tokens/rank at 650K
comp = a * S650 * S650
lin = g * S650
frac_c = comp / (comp + lin)
print(f"\n=== at the 650K block size (S≈{S650:.0f}) ===")
print(f"  matmul compute (S^2)        : {100*frac_c:4.1f}%")
print(f"  KV memory + linear (S)      : {100*(1-frac_c):4.1f}%")
print(f"\n  the 126s d-dependent part splits into:")
print(f"    ~{126*frac_c:4.0f}s  QK^T + P·V tensor-core matmuls")
print(f"    ~{126*(1-frac_c):4.0f}s  KV/Q tile loads from HBM + output writes + acc rescale")
