"""Empirical decomposition of the flash kernel (no GPU counters needed).
flash internally = QK^T matmul + softmax(exp/rescale) + PV matmul.
We measure the bf16 matmul ceiling on this GPU and the flash kernel's achieved rate;
the gap = the softmax / online-rescale / non-overlap cost inside the kernel.
    python profile_flash_decompose.py
"""
import torch, time

def bench(fn, it=30, wu=10):
    for _ in range(wu): fn()
    torch.cuda.synchronize(); t = time.time()
    for _ in range(it): fn()
    torch.cuda.synchronize()
    return (time.time() - t) / it

H, D = 28, 128
PEAK = 312e12

# 1) raw bf16 matmul ceiling, at the two shapes flash actually uses
S = 8192
qk_a = torch.randn(H, S, D, device="cuda", dtype=torch.bfloat16)   # QK^T: [S,D]x[D,S], K-dim=D (small)
qk_b = torch.randn(H, D, S, device="cuda", dtype=torch.bfloat16)
pv_a = torch.randn(H, S, S, device="cuda", dtype=torch.bfloat16)   # PV: [S,S]x[S,D], K-dim=S (large)
pv_b = torch.randn(H, S, D, device="cuda", dtype=torch.bfloat16)
t_qk = bench(lambda: torch.bmm(qk_a, qk_b))
t_pv = bench(lambda: torch.bmm(pv_a, pv_b))
qk_flops = 2 * H * S * S * D
pv_flops = 2 * H * S * S * D
qk_tflops = qk_flops / t_qk / 1e12
pv_tflops = pv_flops / t_pv / 1e12
matmul_ceiling = (qk_flops + pv_flops) / (t_qk + t_pv) / 1e12

# 2) flash kernel achieved rate (same S, causal)
q = torch.randn(1, H, S, D, device="cuda", dtype=torch.bfloat16)
k = torch.randn(1, H, S, D, device="cuda", dtype=torch.bfloat16)
v = torch.randn(1, H, S, D, device="cuda", dtype=torch.bfloat16)
t_flash = bench(lambda: torch.ops.aten._scaled_dot_product_flash_attention(q, k, v, 0.0, True, False, scale=D**-0.5))
flash_flops = 2 * 2 * H * (S * S / 2) * D                          # QK+PV, causal half
flash_tflops = flash_flops / t_flash / 1e12

print(f"matmul ceiling (bf16):  QK^T {qk_tflops:.0f} TFLOPS (K-dim={D}),  "
      f"PV {pv_tflops:.0f} TFLOPS (K-dim={S})")
print(f"  combined matmul rate: {matmul_ceiling:.0f} TFLOPS")
print(f"flash kernel achieved:  {flash_tflops:.0f} TFLOPS  ({100*flash_tflops/PEAK:.0f}% MFU)")

# 3) decompose flash time into matmul vs softmax/overhead
matmul_frac = flash_tflops / matmul_ceiling                        # if flash MMAs ran at the ceiling
overhead_frac = max(0.0, 1 - matmul_frac)
print(f"\n=== flash kernel time decomposition (head_dim={D}) ===")
print(f"  matmul (QK^T + P·V, tensor cores) : {100*matmul_frac:4.0f}%")
print(f"  softmax + online-rescale + stall  : {100*overhead_frac:4.0f}%")
print(f"\n--- applied to your 650K run (attention = 146s/GPU) ---")
print(f"  ~{146*matmul_frac:5.0f}s  tensor-core matmuls (QK^T, P·V)")
print(f"  ~{146*overhead_frac:5.0f}s  softmax exp + rescaling + non-overlap")
