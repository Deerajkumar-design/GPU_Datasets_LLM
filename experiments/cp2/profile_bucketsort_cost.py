"""The cost I missed: materializing scores (data movement) + sorting within buckets.
Bucket-SORT can't be fused like binned-sum — it must write the scores to HBM and sort
them, paying the O(N^2) bandwidth flash is designed to avoid. Measure HBM BW + sort rate."""
import torch, time

def sync(): torch.cuda.synchronize()

# 1) HBM streaming bandwidth (read + write)
n = 1_000_000_000                                  # 1G f32 = 4 GB
a = torch.randn(n, device="cuda", dtype=torch.float32)
for _ in range(3): b = a * 2.0
sync(); t0 = time.time()
for _ in range(10): b = a * 2.0
sync()
bw = 10 * (2 * n * 4) / (time.time() - t0)         # read a + write b
print(f"HBM streaming BW (read+write): {bw/1e9:.0f} GB/s")

# 2) sort throughput at representative per-query segment sizes
for seg, slen in [(2_000_000, 256), (500_000, 1024)]:
    x = torch.randn(seg, slen, device="cuda")
    for _ in range(2): x.sort(dim=-1)
    sync(); t0 = time.time()
    for _ in range(3): x.sort(dim=-1)
    sync()
    ks = 3 * seg * slen / (time.time() - t0)
    print(f"sort {seg}x{slen} (seg={slen}): {ks/1e9:.2f} G keys/s")
    if slen == 256:
        sort_rate = ks

# 3) project to 650K prefill
S = (28 * 28 * 650010**2 / 2) / 3                   # scores / GPU
print(f"\nscores bucketed/sorted per GPU @650K: {S:.2e}  ({S*4/1e12:.0f} TB at fp32)")
mat = 2 * S * 4 / bw                                 # write scores + read back
srt = S / sort_rate
print(f"  + materialize scores (write+read)  : {mat:6.0f}s")
print(f"  + sort within buckets               : {srt:6.0f}s")
print(f"\nbaseline prefill 162s ->  +materialize = {162+mat:.0f}s,  +materialize+sort = {162+mat+srt:.0f}s")
print(f"(binned-sum-in-register, no sort/materialize, measured earlier: +22-91s)")
