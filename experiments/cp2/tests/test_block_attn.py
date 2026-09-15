"""Phase 3 checkpoint: block_attn CUDA kernel vs plain fp32 PyTorch attention."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # find cp_kernels in /workspace
import torch
from cp_kernels import block_attn

def ref(q, k, v, scale, causal):
    s = (q @ k.transpose(-1, -2)) * scale
    if causal:
        Sq, Sk = s.shape[-2], s.shape[-1]
        mask = torch.triu(torch.ones(Sq, Sk, device=s.device, dtype=torch.bool), diagonal=1)
        s = s.masked_fill(mask, float("-inf"))
    return torch.softmax(s, dim=-1) @ v, torch.logsumexp(s, dim=-1)

torch.manual_seed(0)
for causal in (False, True):
    B, H, Sq, Sk, D = 1, 4, 256, 256, 128
    q = torch.randn(B, H, Sq, D, device="cuda")
    k = torch.randn(B, H, Sk, D, device="cuda")
    v = torch.randn(B, H, Sk, D, device="cuda")
    scale = D ** -0.5
    o, l = block_attn(q, k, v, scale, causal)
    ro, rl = ref(q, k, v, scale, causal)
    eo = (o - ro).abs().max().item()
    el = (l - rl).abs().max().item()
    print(f"causal={causal}:  out err {eo:.2e}   lse err {el:.2e}")
    assert eo < 1e-3 and el < 1e-3, "KERNEL MISMATCH"
print("BLOCK ATTN KERNEL OK")
