"""Per-kernel latency profiling of the CP prefill (torch.profiler, CUDA activities).
Prefill-only by default (MAXNEW=1). Prints the per-kernel GPU-time table + a
category breakdown (attention / matmul / comms / elementwise / other), rank 0.

    CTX=600000 MAXNEW=1 torchrun --standalone --nproc_per_node=3 profile_kernels.py
    ZIGZAG=1 CTX=600000 ... (to profile the balanced path)
"""
import os, torch, torch.distributed as dist
from torch.profiler import profile, ProfilerActivity
import cp_infer
from cp_infer import cp_generate, tok, RANK, DEV

CTX = int(os.environ.get("CTX", "8000"))
MAXNEW = int(os.environ.get("MAXNEW", "1"))          # 1 = prefill only
ZIGZAG = os.environ.get("ZIGZAG", "0") == "1"

ids_all = tok(open("/workspace/book.txt").read(), add_special_tokens=False,
              return_tensors="pt")["input_ids"]
q = tok("\n\nQuestion: List the pipeline hazards.\nAnswer:", add_special_tokens=False,
        return_tensors="pt")["input_ids"]
ids = torch.cat([ids_all[:, :CTX], q], dim=1)
if RANK == 0:
    print(f"profiling CTX={ids.shape[1]} MAXNEW={MAXNEW} mode={'zigzag' if ZIGZAG else 'contiguous'}", flush=True)

cp_generate(ids[:, :64], max_new=1, zigzag=ZIGZAG)   # warmup (compile/caches)
dist.barrier()

with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA], record_shapes=False) as prof:
    cp_generate(ids, max_new=MAXNEW, zigzag=ZIGZAG)
dist.barrier()

def dev_us(e):
    return getattr(e, "self_device_time_total", None) or getattr(e, "self_cuda_time_total", 0)

if RANK == 0:
    evs = prof.key_averages()
    try:
        print(evs.table(sort_by="self_device_time_total", row_limit=25))
    except Exception:
        print(evs.table(sort_by="self_cuda_time_total", row_limit=25))

    # category rollup over GPU self-time — LEAF kernels only (cpu self-time==0), to avoid
    # double-counting the aten:: operator and its underlying kernel. Skip the nccl: wrapper
    # (ncclDevKernel is the real comms kernel).
    cats = {"attention": 0.0, "matmul/gemm": 0.0, "comms(nccl)": 0.0, "elementwise": 0.0, "other": 0.0}
    for e in evs:
        t = dev_us(e)
        if t <= 0 or getattr(e, "self_cpu_time_total", 0) > 0 or e.key.startswith("nccl:"):
            continue
        n = e.key.lower()
        if "flash" in n or "attention" in n or "fmha" in n:
            cats["attention"] += t
        elif "gemm" in n or "cutlass" in n or "matmul" in n or "ampere" in n or "sm80" in n or "cublas" in n:
            cats["matmul/gemm"] += t
        elif "nccl" in n or "sendrecv" in n or "allgather" in n or "all_gather" in n:
            cats["comms(nccl)"] += t
        elif "elementwise" in n or "vectorized" in n or "reduce" in n or "norm" in n or "rope" in n or "cast" in n or "copy" in n:
            cats["elementwise"] += t
        else:
            cats["other"] += t
    tot = sum(cats.values()) or 1.0
    print("\n=== GPU self-time by category ===")
    for k, val in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {k:<14} {val/1e3:9.1f} ms   {100*val/tot:5.1f}%")
    print(f"  {'TOTAL':<14} {tot/1e3:9.1f} ms")
    prof.export_chrome_trace("/workspace/trace_prefill.json")
    print("\nchrome trace -> /workspace/trace_prefill.json (open in chrome://tracing or Perfetto)")
dist.destroy_process_group()
