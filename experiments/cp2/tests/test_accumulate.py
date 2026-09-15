"""Phase 4 checkpoint: in-kernel multi-block (m,l,acc) accumulation == full attention.
Simulates the ring: feed several KV blocks one at a time, then finalize."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # find cp_kernels in /workspace
import torch
import cp_kernels

torch.manual_seed(0)
B, H, Sq, D = 1, 4, 256, 128
scale = D ** -0.5
q = torch.randn(B, H, Sq, D, device="cuda")

# 3 separate KV blocks (as the ring would deliver them), all "past" -> non-causal
Sk = 200
ks = [torch.randn(B, H, Sk, D, device="cuda") for _ in range(3)]
vs = [torch.randn(B, H, Sk, D, device="cuda") for _ in range(3)]

m   = torch.full((B, H, Sq), float("-inf"), device="cuda")
l   = torch.zeros(B, H, Sq, device="cuda")
acc = torch.zeros(B, H, Sq, D, device="cuda")
for kb, vb in zip(ks, vs):
    cp_kernels.attn_accumulate(q, kb, vb, m, l, acc, scale, False)
out = acc / l.unsqueeze(-1)
lse = m + l.log()

# reference: one attention over all blocks concatenated
K = torch.cat(ks, dim=2); V = torch.cat(vs, dim=2)
s = (q @ K.transpose(-1, -2)) * scale
rout = torch.softmax(s, dim=-1) @ V
rlse = torch.logsumexp(s, dim=-1)

eo = (out - rout).abs().max().item()
el = (lse - rlse).abs().max().item()
print(f"3-block accumulate:  out err {eo:.2e}   lse err {el:.2e}")
assert eo < 1e-3 and el < 1e-3, "ACCUMULATE MISMATCH"
print("ACCUMULATE OK")
