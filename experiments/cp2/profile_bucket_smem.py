"""Cost of binning into SHARED-MEMORY buckets (accumulators), sort only the B buckets.
No value sort, no materialization. The new cost vs registers = shared-mem atomic contention
(threads adding into B shared buckets serialize). Measure both extremes:
  smem-atomic : per-score atomicAdd into block-shared B buckets (high contention)
  register    : per-thread private B buckets, reduce at end (low contention) [from earlier]
"""
import os, torch, time
os.environ.setdefault("CUDA_HOME", "/root/anaconda3/envs/ring_atten")
from torch.utils.cpp_extension import load_inline

src = r'''
#include <torch/extension.h>
__global__ void base_k(long it, float* o){
    float a=0.f,s=threadIdx.x*7e-4f-5.f;
    for(long i=0;i<it;i++){ s=s*1.0000003f+0.013f; a+=__expf(-fabsf(s)); }
    o[blockIdx.x*blockDim.x+threadIdx.x]=a;
}
__global__ void smem_k(long it,int B,float* o){
    extern __shared__ float sb[];
    if(threadIdx.x<B) sb[threadIdx.x]=0.f;
    __syncthreads();
    float s=threadIdx.x*7e-4f-5.f;
    for(long i=0;i<it;i++){
        s=s*1.0000003f+0.013f; float e=__expf(-fabsf(s));
        int b=((__float_as_int(e)>>23)&0xFF)&(B-1);
        atomicAdd(&sb[b], e);                       // shared-mem atomic per score
    }
    __syncthreads();
    if(threadIdx.x==0){ float t=0; for(int j=0;j<B;j++) t+=sb[j]; o[blockIdx.x]=t; }
}
torch::Tensor base(long it){ auto o=torch::empty({2048*256},torch::dtype(torch::kFloat32).device(torch::kCUDA));
    base_k<<<2048,256>>>(it,o.data_ptr<float>()); return o; }
torch::Tensor smem(long it,int B){ auto o=torch::empty({2048},torch::dtype(torch::kFloat32).device(torch::kCUDA));
    smem_k<<<2048,256,B*sizeof(float)>>>(it,B,o.data_ptr<float>()); return o; }
'''
m = load_inline(name="bsmem", cpp_sources="torch::Tensor base(long it); torch::Tensor smem(long it,int B);",
                cuda_sources=src, functions=["base","smem"], verbose=False)

N=2048*256
def rate(fn,it=200000):
    for _ in range(3): fn(); torch.cuda.synchronize()
    t0=time.time()
    for _ in range(5): fn()
    torch.cuda.synchronize()
    return N*it*5/(time.time()-t0)

S=(28*28*650010**2/2)/3
base=rate(lambda:m.base(200000))
print(f"baseline softmax inner: {base/1e12:.2f} T/s")
print(f"{'buckets':>8}{'smem rate(T/s)':>16}{'+ns/score':>11}{'+s prefill':>12}{'+% of 162s':>11}")
for B in (4,8,16):
    r=rate(lambda B=B:m.smem(200000,B)); add=1/r-1/base
    print(f"{B:>8}{r/1e12:>16.3f}{add*1e9:>11.2f}{S*add:>12.0f}{100*S*add/162:>10.0f}%")
print("\n(register/private-bucket version measured earlier: +22-91s for B=4-16)")
