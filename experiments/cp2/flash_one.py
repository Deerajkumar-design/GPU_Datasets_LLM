"""Isolated single flash-attention call for ncu to profile its internals."""
import torch
B, H, S, D = 1, 28, 8192, 128
q = torch.randn(B, H, S, D, device="cuda", dtype=torch.bfloat16)
k = torch.randn(B, H, S, D, device="cuda", dtype=torch.bfloat16)
v = torch.randn(B, H, S, D, device="cuda", dtype=torch.bfloat16)
for _ in range(3):
    o = torch.ops.aten._scaled_dot_product_flash_attention(q, k, v, 0.0, True, False, scale=D ** -0.5)
torch.cuda.synchronize()
print("done")
