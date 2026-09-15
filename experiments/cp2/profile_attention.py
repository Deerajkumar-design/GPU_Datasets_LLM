"""Detailed attention profiling: what's inside the attention time.
Breaks the flash kernels down by call count + input shape, and computes achieved
TFLOPS / MFU so you can see whether the attention time is efficient compute or waste.

    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True ZIGZAG=1 CTX=650000 \
    torchrun --standalone --nproc_per_node=3 profile_attention.py
"""
import os, torch, torch.distributed as dist
from torch.profiler import profile, ProfilerActivity
import cp_infer
from cp_infer import cp_generate, tok, RANK, WORLD, DEV

CTX = int(os.environ.get("CTX", "50000"))
ZIGZAG = os.environ.get("ZIGZAG", "1") == "1"
cfg = cp_infer.model.config
Hq = cfg.num_attention_heads
d = getattr(cfg, "head_dim", 128)
L = cfg.num_hidden_layers
PEAK = 312e12                                    # A100 bf16 tensor-core peak FLOP/s

book = tok(open("/workspace/book.txt").read(), add_special_tokens=False, return_tensors="pt")["input_ids"]
qa = tok("\n\nQuestion: List the pipeline hazards.\nAnswer:", add_special_tokens=False, return_tensors="pt")["input_ids"]
ids = torch.cat([book[:, :CTX], qa], dim=1)
N = ids.shape[1]

def dev_us(e):
    return getattr(e, "self_device_time_total", None) or getattr(e, "self_cuda_time_total", 0)

cp_generate(book[:, :64], max_new=1, zigzag=ZIGZAG)        # warmup
dist.barrier()
with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA], record_shapes=True) as prof:
    cp_generate(ids, max_new=1, zigzag=ZIGZAG)
dist.barrier()

if RANK == 0:
    flash_t, flash_n = 0., 0
    for e in prof.key_averages():
        if "flash" in e.key.lower() and getattr(e, "self_cpu_time_total", 0) == 0:   # leaf kernel
            flash_t += dev_us(e); flash_n += e.count
    flash_s = flash_t / 1e6

    print(f"\n=== ATTENTION DETAIL  ctx={N}  mode={'zigzag' if ZIGZAG else 'contig'} ===")
    print(f"flash-attention kernel launches: {flash_n}  ({flash_n//L} per layer x {L} layers)")
    print(f"total attention (flash) time   : {flash_s:.2f} s")
    print(f"avg per launch                 : {1e3*flash_s/max(flash_n,1):.1f} ms")

    print("\n--- flash calls grouped by input shape (q, k, v ...) ---")
    rows = [(e.count, dev_us(e) / 1e3, e.input_shapes)
            for e in prof.key_averages(group_by_input_shape=True)
            if "flash_attention_forward" in e.key.lower()]
    for cnt, ms, shp in sorted(rows, key=lambda x: -x[1])[:8]:
        qsh = shp[0] if shp else "?"
        ksh = shp[1] if len(shp) > 1 else "?"
        print(f"  {cnt:>4}x  {ms:8.1f} ms   q={qsh}  k={ksh}")

    total_flop = 2 * L * Hq * d * (N ** 2)       # causal attn FLOPs, whole sequence
    per_rank = total_flop / WORLD                # balanced => each rank does 1/W
    tflops = per_rank / flash_s / 1e12
    print(f"\n--- efficiency ---")
    print(f"attention FLOPs/GPU : {per_rank:.2e}")
    print(f"achieved throughput : {tflops:.0f} TFLOPS/GPU")
    print(f"MFU                 : {100 * per_rank / flash_s / PEAK:.0f}%  (A100 bf16 peak {PEAK/1e12:.0f} TFLOPS)")
dist.destroy_process_group()
