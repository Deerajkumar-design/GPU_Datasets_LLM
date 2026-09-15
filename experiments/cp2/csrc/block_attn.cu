// Phase 3: block attention kernel returning (out, lse).
// One thread per query row; online-softmax over the KV block. fp32, correctness-first.
// This is the seed that grows into the in-kernel ring (Phases 4-5).
#include <torch/extension.h>
#include <c10/cuda/CUDAException.h>
#include <cuda_bf16.h>
#include <vector>
#include <math.h>

#define MAXD 128

__global__ void block_attn_kernel(
        const float* __restrict__ q, const float* __restrict__ k, const float* __restrict__ v,
        float* __restrict__ out, float* __restrict__ lse,
        int B, int H, int Sq, int Sk, int D, float scale, bool causal) {
    long idx = (long)blockIdx.x * blockDim.x + threadIdx.x;
    long total = (long)B * H * Sq;
    if (idx >= total) return;

    int i = idx % Sq;
    int h = (idx / Sq) % H;
    int b = idx / ((long)Sq * H);

    const float* qrow  = q + (((long)b * H + h) * Sq + i) * D;
    const float* kbase = k + ((long)b * H + h) * Sk * D;
    const float* vbase = v + ((long)b * H + h) * Sk * D;

    float qr[MAXD], acc[MAXD];
    for (int d = 0; d < D; d++) { qr[d] = qrow[d]; acc[d] = 0.f; }

    float m = -INFINITY, l = 0.f;
    int kmax = causal ? (i + 1) : Sk;   // diagonal block: query i attends keys 0..i (top-left aligned)
    for (int j = 0; j < kmax; j++) {
        const float* krow = kbase + (long)j * D;
        float s = 0.f;
        for (int d = 0; d < D; d++) s += qr[d] * krow[d];
        s *= scale;
        float mnew = fmaxf(m, s);
        float corr = __expf(m - mnew);
        float p    = __expf(s - mnew);
        l = l * corr + p;
        const float* vrow = vbase + (long)j * D;
        for (int d = 0; d < D; d++) acc[d] = acc[d] * corr + p * vrow[d];
        m = mnew;
    }

    float* orow = out + (((long)b * H + h) * Sq + i) * D;
    float inv = (l > 0.f) ? 1.f / l : 0.f;
    for (int d = 0; d < D; d++) orow[d] = acc[d] * inv;
    lse[((long)b * H + h) * Sq + i] = (l > 0.f) ? (m + __logf(l)) : -INFINITY;
}

// Phase 4: accumulate one KV block into running (m, l, acc) state, in place.
// Init state as m=-inf, l=0, acc=0; call once per KV block (causal=true only for the
// diagonal block). Finalize in Python: out = acc / l;  lse = m + log(l).
__global__ void attn_accumulate_kernel(
        const float* __restrict__ q, const float* __restrict__ k, const float* __restrict__ v,
        float* __restrict__ mm, float* __restrict__ ll, float* __restrict__ acc,
        int B, int H, int Sq, int Sk, int D, float scale, bool causal) {
    long idx = (long)blockIdx.x * blockDim.x + threadIdx.x;
    long total = (long)B * H * Sq;
    if (idx >= total) return;

    int i = idx % Sq;
    int h = (idx / Sq) % H;
    int b = idx / ((long)Sq * H);
    const float* qrow  = q + (((long)b * H + h) * Sq + i) * D;
    const float* kbase = k + ((long)b * H + h) * Sk * D;
    const float* vbase = v + ((long)b * H + h) * Sk * D;
    long row = ((long)b * H + h) * Sq + i;

    float qr[MAXD], a[MAXD];
    for (int d = 0; d < D; d++) { qr[d] = qrow[d]; a[d] = acc[row * D + d]; }
    float m = mm[row], l = ll[row];

    int kmax = causal ? (i + 1) : Sk;
    for (int j = 0; j < kmax; j++) {
        const float* krow = kbase + (long)j * D;
        float s = 0.f;
        for (int d = 0; d < D; d++) s += qr[d] * krow[d];
        s *= scale;
        float mnew = fmaxf(m, s);          // m starts at -inf -> corr=0 on first key, correct
        float corr = __expf(m - mnew);
        float p    = __expf(s - mnew);
        l = l * corr + p;
        const float* vrow = vbase + (long)j * D;
        for (int d = 0; d < D; d++) a[d] = a[d] * corr + p * vrow[d];
        m = mnew;
    }
    mm[row] = m; ll[row] = l;
    for (int d = 0; d < D; d++) acc[row * D + d] = a[d];
}

void attn_accumulate(torch::Tensor q, torch::Tensor k, torch::Tensor v,
                     torch::Tensor m, torch::Tensor l, torch::Tensor acc,
                     double scale, bool causal) {
    TORCH_CHECK(q.is_cuda() && k.is_cuda() && v.is_cuda(), "inputs must be CUDA");
    TORCH_CHECK(q.scalar_type() == torch::kFloat32, "fp32 only (for now)");
    q = q.contiguous(); k = k.contiguous(); v = v.contiguous();
    int B = q.size(0), H = q.size(1), Sq = q.size(2), D = q.size(3), Sk = k.size(2);
    TORCH_CHECK(D <= MAXD, "head_dim must be <= 128");
    long total = (long)B * H * Sq;
    int threads = 128;
    long blocks = (total + threads - 1) / threads;
    attn_accumulate_kernel<<<blocks, threads>>>(
        q.data_ptr<float>(), k.data_ptr<float>(), v.data_ptr<float>(),
        m.data_ptr<float>(), l.data_ptr<float>(), acc.data_ptr<float>(),
        B, H, Sq, Sk, D, (float)scale, causal);
    C10_CUDA_CHECK(cudaGetLastError());
}

std::vector<torch::Tensor> block_attn(torch::Tensor q, torch::Tensor k, torch::Tensor v,
                                      double scale, bool causal) {
    TORCH_CHECK(q.is_cuda() && k.is_cuda() && v.is_cuda(), "inputs must be CUDA");
    TORCH_CHECK(q.scalar_type() == torch::kFloat32, "fp32 only (for now)");
    q = q.contiguous(); k = k.contiguous(); v = v.contiguous();
    int B = q.size(0), H = q.size(1), Sq = q.size(2), D = q.size(3), Sk = k.size(2);
    TORCH_CHECK(D <= MAXD, "head_dim must be <= 128");

    auto out = torch::empty_like(q);
    auto lse = torch::empty({B, H, Sq}, q.options());
    long total = (long)B * H * Sq;
    int threads = 128;
    long blocks = (total + threads - 1) / threads;
    block_attn_kernel<<<blocks, threads>>>(
        q.data_ptr<float>(), k.data_ptr<float>(), v.data_ptr<float>(),
        out.data_ptr<float>(), lse.data_ptr<float>(),
        B, H, Sq, Sk, D, (float)scale, causal);
    C10_CUDA_CHECK(cudaGetLastError());
    return {out, lse};
}

// ---------------------------------------------------------------------------
// Optimized FlashAttention-style block kernel: bf16 in/out, fp32 accumulation.
// One WARP per query row (32 lanes split head_dim=128 -> 4 dims/lane, no spills).
// K/V streamed in shared-memory tiles, reused across the NWARPS queries in a block.
// Returns (out_bf16, lse_fp32) for one (Q x KV) block.  D must be 128.
// ---------------------------------------------------------------------------
#define WARP   32
#define DPL    4      // dims per lane = D / WARP  (128/32)
#define NWARPS 16     // query rows per block (more warps -> hide the per-key reduction latency)
#define KTILE  32     // keys per shared-memory tile (smaller smem -> higher occupancy)

__global__ void block_attn_fast_kernel(
        const __nv_bfloat16* __restrict__ q, const __nv_bfloat16* __restrict__ k,
        const __nv_bfloat16* __restrict__ v, __nv_bfloat16* __restrict__ out,
        float* __restrict__ lse, int B, int H, int Sq, int Sk, float scale, bool causal) {
    const int warp = threadIdx.x / WARP;
    const int lane = threadIdx.x % WARP;
    const int qrow = blockIdx.x * NWARPS + warp;
    const int h = blockIdx.y, b = blockIdx.z;
    const bool active = (qrow < Sq);
    const long bh = (long)b * H + h;

    float qreg[DPL], acc[DPL];
    if (active) {
        const __nv_bfloat16* qp = q + (bh * Sq + qrow) * 128;
        #pragma unroll
        for (int t = 0; t < DPL; t++) qreg[t] = __bfloat162float(qp[lane * DPL + t]);
    }
    #pragma unroll
    for (int t = 0; t < DPL; t++) acc[t] = 0.f;
    float m = -INFINITY, l = 0.f;

    __shared__ __nv_bfloat16 Ks[KTILE][128];
    __shared__ __nv_bfloat16 Vs[KTILE][128];
    const __nv_bfloat16* kbase = k + bh * Sk * 128;
    const __nv_bfloat16* vbase = v + bh * Sk * 128;

    for (int tile0 = 0; tile0 < Sk; tile0 += KTILE) {
        int tlen = min(KTILE, Sk - tile0);
        for (int idx = threadIdx.x; idx < tlen * 128; idx += blockDim.x) {  // cooperative load
            int j = idx >> 7, d = idx & 127;
            Ks[j][d] = kbase[(long)(tile0 + j) * 128 + d];
            Vs[j][d] = vbase[(long)(tile0 + j) * 128 + d];
        }
        __syncthreads();
        if (active) {
            for (int j = 0; j < tlen; j++) {
                if (causal && (tile0 + j) > qrow) break;          // warp-uniform (same qrow)
                float s = 0.f;
                #pragma unroll
                for (int t = 0; t < DPL; t++) s += qreg[t] * __bfloat162float(Ks[j][lane * DPL + t]);
                #pragma unroll
                for (int o = 16; o > 0; o >>= 1) s += __shfl_xor_sync(0xffffffff, s, o);
                s *= scale;
                float mnew = fmaxf(m, s);
                float corr = __expf(m - mnew), p = __expf(s - mnew);
                l = l * corr + p;
                #pragma unroll
                for (int t = 0; t < DPL; t++)
                    acc[t] = acc[t] * corr + p * __bfloat162float(Vs[j][lane * DPL + t]);
                m = mnew;
            }
        }
        __syncthreads();
    }

    if (active) {
        float inv = (l > 0.f) ? 1.f / l : 0.f;
        __nv_bfloat16* op = out + (bh * Sq + qrow) * 128;
        #pragma unroll
        for (int t = 0; t < DPL; t++) op[lane * DPL + t] = __float2bfloat16(acc[t] * inv);
        if (lane == 0) lse[bh * Sq + qrow] = (l > 0.f) ? (m + __logf(l)) : -INFINITY;
    }
}

std::vector<torch::Tensor> block_attn_fast(torch::Tensor q, torch::Tensor k, torch::Tensor v,
                                           double scale, bool causal) {
    TORCH_CHECK(q.is_cuda() && k.is_cuda() && v.is_cuda(), "inputs must be CUDA");
    TORCH_CHECK(q.scalar_type() == torch::kBFloat16, "block_attn_fast is bf16");
    q = q.contiguous(); k = k.contiguous(); v = v.contiguous();
    int B = q.size(0), H = q.size(1), Sq = q.size(2), D = q.size(3), Sk = k.size(2);
    TORCH_CHECK(D == 128, "block_attn_fast requires head_dim == 128");
    auto out = torch::empty_like(q);
    auto lse = torch::empty({B, H, Sq}, q.options().dtype(torch::kFloat32));
    dim3 grid((Sq + NWARPS - 1) / NWARPS, H, B);
    dim3 block(NWARPS * WARP);
    block_attn_fast_kernel<<<grid, block>>>(
        reinterpret_cast<__nv_bfloat16*>(q.data_ptr<at::BFloat16>()),
        reinterpret_cast<__nv_bfloat16*>(k.data_ptr<at::BFloat16>()),
        reinterpret_cast<__nv_bfloat16*>(v.data_ptr<at::BFloat16>()),
        reinterpret_cast<__nv_bfloat16*>(out.data_ptr<at::BFloat16>()),
        lse.data_ptr<float>(), B, H, Sq, Sk, (float)scale, causal);
    C10_CUDA_CHECK(cudaGetLastError());
    return {out, lse};
}

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("block_attn", &block_attn, "block attention -> (out, lse)");
    m.def("attn_accumulate", &attn_accumulate, "accumulate one KV block into (m,l,acc) state");
    m.def("block_attn_fast", &block_attn_fast, "optimized bf16 flash-style block -> (out, lse)");
}
