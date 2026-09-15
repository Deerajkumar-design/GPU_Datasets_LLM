"""Phase 1 checkpoint: prove torch.utils.cpp_extension compiles+runs a CUDA kernel
against this torch (cu130) using the env's nvcc 13. No model, no distributed."""
import os
os.environ["CUDA_HOME"] = "/root/anaconda3/envs/ring_atten"   # use nvcc 13, not system 12.4
import torch
from torch.utils.cpp_extension import load_inline

cuda_src = r'''
#include <torch/extension.h>
#include <c10/cuda/CUDAException.h>
__global__ void add_one_kernel(float* x, int n){
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) x[i] += 1.0f;
}
torch::Tensor add_one(torch::Tensor x){
    auto y = x.clone();
    int n = y.numel();
    int threads = 256, blocks = (n + threads - 1) / threads;
    add_one_kernel<<<blocks, threads>>>(y.data_ptr<float>(), n);
    C10_CUDA_CHECK(cudaGetLastError());
    return y;
}
'''
cpp_src = "torch::Tensor add_one(torch::Tensor x);"

mod = load_inline(name="hello_cuda", cpp_sources=cpp_src, cuda_sources=cuda_src,
                  functions=["add_one"], verbose=True)

x = torch.arange(8, dtype=torch.float32, device="cuda")
y = mod.add_one(x)
print("in :", x.tolist())
print("out:", y.tolist())
assert torch.allclose(y, x + 1), "kernel result wrong"
print("HELLO CUDA EXTENSION OK")
