"""Run context-parallel inference over the Computer Architecture book and answer a question.
Ramp context with CTX env var: CTX=50000, then 250000, then 931951 (full book).
    CTX=50000 torchrun --standalone --nproc_per_node=3 run_book.py
"""
import os, time, torch, torch.distributed as dist
import cp_infer
from cp_infer import cp_generate, tok, RANK, WORLD, DEV

CTX = int(os.environ.get("CTX", "50000"))
MAXNEW = int(os.environ.get("MAXNEW", "128"))
ZIGZAG = os.environ.get("ZIGZAG", "0") == "1"
QUESTION = ("\n\n---\nQuestion: According to the text above (Hennessy & Patterson, "
            "Computer Architecture: A Quantitative Approach), what are the major categories "
            "of pipeline hazards, and briefly what causes each?\nAnswer:")

if RANK == 0:
    print("[book] tokenizing book.txt ...", flush=True)
ids_all = tok(open("/workspace/book.txt").read(), add_special_tokens=False,
              return_tensors="pt")["input_ids"]
book_ids = ids_all[:, :CTX]
q_ids = tok(QUESTION, add_special_tokens=False, return_tensors="pt")["input_ids"]
ids = torch.cat([book_ids, q_ids], dim=1)
N = ids.shape[1]
if RANK == 0:
    print(f"[book] context = {N:,} tokens; generating {MAXNEW} new tokens ...", flush=True)

dist.barrier()
torch.cuda.reset_peak_memory_stats(DEV)
t0 = time.time()
out = cp_generate(ids, max_new=MAXNEW, verbose=True, zigzag=ZIGZAG)
dist.barrier()
dt = time.time() - t0

if RANK == 0:
    peak = torch.cuda.max_memory_allocated(DEV) / 1e9
    print(f"\n[book] {N:,} tokens + {MAXNEW} new in {dt:.1f}s   peak {peak:.1f} GB/GPU")
    print("\n=== ANSWER ===")
    print(tok.decode(out[0], skip_special_tokens=True))
dist.barrier()
dist.destroy_process_group()
