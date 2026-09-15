"""Measure the ADDED compute cost of exponent-bucketed softmax summation, per score,
then project to a 650K prefill. Compute-bound microbench (in-register, no global traffic).
B is compile-time so the B-way accumulate is exactly B conditionals (register-resident buckets).

baseline = exp(s); single sum            (current softmax inner op)
bucketed = exp(s); exponent; B-way sum   (added work)
"""
import os, torch, time
os.environ.setdefault("CUDA_HOME", "/root/anaconda3/envs/ring_atten")
from torch.utils.cpp_extension import load_inline

src = r'''
#include <torch/extension.h>
__device__ __forceinline__ float et(long i, float s){ return s*1.0000003f+0.013f; }

__global__ void base_k(long iters, float* out){
    float acc=0.f, s=threadIdx.x*0.0007f-5.f;
    for(long i=0;i<iters;i++){ s=et(i,s); float e=__expf(-fabsf(s)); acc+=e; }
    out[blockIdx.x*blockDim.x+threadIdx.x]=acc;
}
template<int B>
__global__ void buck_k(long iters, float* out){
    float acc[B];
    #pragma unroll
    for(int b=0;b<B;b++) acc[b]=0.f;
    float s=threadIdx.x*0.0007f-5.f;
    for(long i=0;i<iters;i++){
        s=et(i,s); float e=__expf(-fabsf(s));
        int ex=(__float_as_int(e)>>23)&0xFF;       // exponent
        int b = ex & (B-1);                         // bucket (B is power of 2)
        #pragma unroll
        for(int bb=0;bb<B;bb++) if(bb==b) acc[bb]+=e;   // exactly B conditionals
    }
    float sum=0;
    #pragma unroll
    for(int b=0;b<B;b++) sum+=acc[b];
    out[blockIdx.x*blockDim.x+threadIdx.x]=sum;
}
torch::Tensor base(long it){ auto o=torch::empty({2048*256},torch::dtype(torch::kFloat32).device(torch::kCUDA));
    base_k<<<2048,256>>>(it,o.data_ptr<float>()); return o; }
torch::Tensor buck(long it,int B){ auto o=torch::empty({2048*256},torch::dtype(torch::kFloat32).device(torch::kCUDA));
    if(B==4) buck_k<4><<<2048,256>>>(it,o.data_ptr<float>());
    else if(B==8) buck_k<8><<<2048,256>>>(it,o.data_ptr<float>());
    else buck_k<16><<<2048,256>>>(it,o.data_ptr<float>());
    return o; }
'''
cpp = "torch::Tensor base(long it); torch::Tensor buck(long it,int B);"
m = load_inline(name="bucket_bench2", cpp_sources=cpp, cuda_sources=src, functions=["base","buck"], verbose=False)

N = 2048*256
def rate(fn, it=200000):
    for _ in range(3): fn(); torch.cuda.synchronize()
    t0=time.time()
    for _ in range(5): fn()
    torch.cuda.synchronize()
    return N*it*5/(time.time()-t0)

S = (28*28*(650010**2)/2)/3                          # causal scores / GPU @ 650K
base = rate(lambda: m.base(200000))
print(f"baseline softmax inner : {base/1e12:.2f} T scores/s   (=> {S/base:.0f}s of softmax @650K)")
print(f"{'buckets':>8}{'rate(T/s)':>11}{'+ns/score':>11}{'+s prefill':>12}{'+% of 162s':>11}")
for B in (4,8,16):
    r = rate(lambda B=B: m.buck(200000,B))
    add = (1/r - 1/base)
    print(f"{B:>8}{r/1e12:>11.2f}{add*1e9:>11.3f}{S*add:>12.1f}{100*S*add/162:>10.0f}%")
