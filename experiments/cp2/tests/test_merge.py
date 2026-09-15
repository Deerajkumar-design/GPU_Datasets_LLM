"""Phase 2 oracle: online-softmax merge vs full attention. Single process, no model.
If this fails, the ring is silently wrong."""
import torch

def flash_block(q, k, v, scale, causal):
    r = torch.ops.aten._scaled_dot_product_flash_attention(q, k, v, 0.0, causal, False, scale=scale)
    return r[0], r[1]            # out [b,h,sq,d], lse [b,h,sq]

def merge(out, lse, b_out, b_lse):
    if out is None:
        return b_out, b_lse
    new = torch.logaddexp(lse, b_lse)
    out = out * torch.exp(lse - new).unsqueeze(-1) + b_out * torch.exp(b_lse - new).unsqueeze(-1)
    return out, new

torch.manual_seed(0)
b, h, s, d = 1, 4, 512, 64
scale = d ** -0.5
q = torch.randn(b, h, s, d, device="cuda", dtype=torch.bfloat16)
k = torch.randn(b, h, s, d, device="cuda", dtype=torch.bfloat16)
v = torch.randn(b, h, s, d, device="cuda", dtype=torch.bfloat16)

ref, _ = flash_block(q, k, v, scale, False)            # one full non-causal attention

out = lse = None                                        # split keys into 4 blocks, attend, merge
for kc, vc in zip(k.chunk(4, dim=2), v.chunk(4, dim=2)):
    bo, bl = flash_block(q, kc, vc, scale, False)
    out, lse = merge(out, lse, bo, bl)
err = (out.float() - ref.float()).abs().max().item()
print(f"non-causal blockwise-merge max abs err: {err:.2e}")
assert err < 1e-2, "MERGE MATH WRONG"
print("MERGE MATH OK")
