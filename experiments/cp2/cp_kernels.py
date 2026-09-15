"""Loads the CP CUDA kernels (JIT-compiled via torch.utils.cpp_extension).
Import this and use cp_kernels.block_attn(...)."""
import os
os.environ.setdefault("CUDA_HOME", "/root/anaconda3/envs/ring_atten")   # nvcc 13, matches torch cu130
from torch.utils.cpp_extension import load

_mod = load(
    name="cp_kernels",
    sources=[os.path.join(os.path.dirname(__file__), "csrc", "block_attn.cu")],
    verbose=True,
)
block_attn = _mod.block_attn
attn_accumulate = _mod.attn_accumulate
block_attn_fast = _mod.block_attn_fast
