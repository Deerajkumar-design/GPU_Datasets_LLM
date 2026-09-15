"""Phase: load Qwen2.5-7B-Instruct-1M REPLICATED on all 3 GPUs and sanity-check.
Context parallelism shards the sequence, not the weights, so every rank holds the
full model on its own GPU.  Run with:
    torchrun --standalone --nproc_per_node=3 setup_model.py
"""
import torch, torch.distributed as dist
from transformers import AutoModelForCausalLM, AutoTokenizer

import os
LOCAL = int(os.environ.get("LOCAL_RANK", 0))
torch.cuda.set_device(LOCAL)
DEV = torch.device(f"cuda:{LOCAL}")
dist.init_process_group("nccl", device_id=DEV)
RANK, WORLD = dist.get_rank(), dist.get_world_size()

MODEL = "Qwen/Qwen2.5-7B-Instruct-1M"
if RANK == 0:
    print(f"[rank0] loading {MODEL} replicated on {WORLD} GPUs ...", flush=True)

tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16).to(DEV).eval()
dist.barrier()

w_gb = torch.cuda.memory_allocated(DEV) / 1e9
cfg = model.config
if RANK == 0:
    print(f"[rank0] loaded. layers={cfg.num_hidden_layers} "
          f"q_heads={cfg.num_attention_heads} kv_heads={cfg.num_key_value_heads} "
          f"head_dim={getattr(cfg,'head_dim', cfg.hidden_size//cfg.num_attention_heads)} "
          f"max_pos={cfg.max_position_embeddings}", flush=True)
    print(f"[rank0] rope_scaling={getattr(cfg,'rope_scaling', None)}", flush=True)

# quick greedy generation (each rank runs identically) to prove the weights work
msg = [{"role": "user", "content": "In one sentence, what is context parallelism?"}]
enc = tok.apply_chat_template(msg, add_generation_prompt=True,
                             return_tensors="pt", return_dict=True).to(DEV)
in_len = enc["input_ids"].shape[1]
with torch.no_grad():
    out = model.generate(**enc, max_new_tokens=40, do_sample=False)
gen = tok.decode(out[0][in_len:], skip_special_tokens=True)

print(f"[rank{RANK}] cuda:{RANK} weights={w_gb:.2f} GB  free={torch.cuda.mem_get_info(DEV)[0]/1e9:.1f} GB", flush=True)
dist.barrier()
if RANK == 0:
    print(f"[rank0] sample generation: {gen}", flush=True)
    print("[rank0] MODEL SETUP OK on all 3 GPUs", flush=True)
dist.destroy_process_group()
