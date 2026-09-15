"""Context-parallel inference engine for Qwen2.5-7B-Instruct-1M across 3 GPUs.

Weights are replicated; the SEQUENCE is sharded (rank r owns positions [r*S,(r+1)*S)).
Only attention communicates: prefill uses the ring (ring_attention), decode uses
replicate-query / shard-KV / all-gather-merge.  use_cache=False; we manage the
sharded KV cache ourselves.  Inner attention math = torch native flash op (bf16).

Run the built-in short-prompt validation vs stock attention:
    torchrun --standalone --nproc_per_node=3 cp_infer.py
"""
import os, torch, torch.distributed as dist
from transformers import AutoModelForCausalLM, AutoTokenizer, AttentionInterface
from ring_attention import ring_attention, ring_attention_zigzag, _repeat_kv, _flash_block, _merge

LOCAL = int(os.environ.get("LOCAL_RANK", 0))
torch.cuda.set_device(LOCAL)
DEV = torch.device(f"cuda:{LOCAL}")
if not dist.is_initialized():
    dist.init_process_group("nccl", device_id=DEV)
RANK, WORLD = dist.get_rank(), dist.get_world_size()
MODEL = "Qwen/Qwen2.5-7B-Instruct-1M"
MODEL_REVISION = "e28526f7bb80e2a9c8af03b831a9af3812f18fba"
MODEL_SOURCE = os.environ.get("CP_MODEL_PATH", MODEL)
LOCAL_MODEL = os.path.isdir(MODEL_SOURCE)

# ---- CP runtime state (set by the generation loop each forward) ----
CP = {"phase": "prefill", "owner": 0}
KV = {}                                   # layer_idx -> (k, v) shard, each [B, Hkv, S, D]


def _decode_attention(query, key, value, li, scale):
    """Decode: new token attends ALL sharded KV. owner appends new KV; all-gather merge."""
    ck, cv = KV[li]
    if CP["owner"] == RANK:                # store the new token's KV on exactly one rank
        ck = torch.cat([ck, key], dim=2)
        cv = torch.cat([cv, value], dim=2)
        KV[li] = (ck, cv)
    Hq = query.shape[1]
    nrep = Hq // ck.shape[1]
    L = ck.shape[2]
    if L == 0:                            # empty shard guard
        out_l = torch.zeros(query.shape[0], Hq, 1, query.shape[3], device=DEV, dtype=torch.float32)
        lse_l = torch.full((query.shape[0], Hq, 1), float("-inf"), device=DEV, dtype=torch.float32)
    else:
        o, lse = _flash_block(query, _repeat_kv(ck, nrep), _repeat_kv(cv, nrep), scale, False)
        out_l, lse_l = o.float(), lse
    outs = [torch.empty_like(out_l) for _ in range(WORLD)]
    lses = [torch.empty_like(lse_l) for _ in range(WORLD)]
    dist.all_gather(outs, out_l.contiguous())
    dist.all_gather(lses, lse_l.contiguous())
    out = lacc = None
    for o, l in zip(outs, lses):
        out, lacc = _merge(out, lacc, o, l)
    return out                            # [B, Hq, 1, D] fp32, identical on all ranks


def cp_attention(module, query, key, value, attention_mask, dropout=0.0, scaling=None, **kwargs):
    li = module.layer_idx
    if CP["phase"] == "prefill":
        KV[li] = (key, value)             # stash this rank's shard KV for decode
        if CP.get("zigzag"):
            out, _ = ring_attention_zigzag(query, key, value, scale=scaling, causal=True)
        else:
            out, _ = ring_attention(query, key, value, scale=scaling, causal=True, backend="flash")
    else:
        out = _decode_attention(query, key, value, li, scaling)
    out = out.to(query.dtype).transpose(1, 2).contiguous()   # [B, S, Hq, D]
    return out, None


AttentionInterface.register("cp", cp_attention)

tok = AutoTokenizer.from_pretrained(
    MODEL_SOURCE,
    revision=None if LOCAL_MODEL else MODEL_REVISION,
    local_files_only=LOCAL_MODEL,
)
PAD = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
EOS = tok.eos_token_id
model = AutoModelForCausalLM.from_pretrained(
    MODEL_SOURCE,
    revision=None if LOCAL_MODEL else MODEL_REVISION,
    local_files_only=LOCAL_MODEL,
    dtype=torch.bfloat16,
    attn_implementation="cp",
).to(DEV).eval()


@torch.no_grad()
def cp_generate(prompt_ids, max_new=128, verbose=False, zigzag=False):
    """prompt_ids: [1, N] on CPU or DEV. Greedy. Returns generated ids [1, T] (rank 0 valid).
    zigzag=True uses load-balanced sharding (rank r owns chunks r and 2W-1-r)."""
    KV.clear()
    CP["zigzag"] = zigzag
    N = prompt_ids.shape[1]
    W = WORLD

    if zigzag:
        nchunks = 2 * W
        pad_to = ((N + nchunks - 1) // nchunks) * nchunks
        c = pad_to // nchunks
        if pad_to > N:
            prompt_ids = torch.cat([prompt_ids.cpu(),
                                    torch.full((1, pad_to - N), PAD, dtype=torch.long)], dim=1)
        a, b = RANK, nchunks - 1 - RANK                       # this rank's two global chunks
        shard = torch.cat([prompt_ids[:, a*c:(a+1)*c], prompt_ids[:, b*c:(b+1)*c]], dim=1).to(DEV)
        pos = torch.cat([torch.arange(a*c, (a+1)*c),
                         torch.arange(b*c, (b+1)*c)]).to(DEV).unsqueeze(0)
        Sloc = 2 * c
        g = (N - 1) // c                                      # chunk holding the last real token
        if g < W:
            owner_last, lidx = g, (N - 1) - g * c
        else:
            owner_last, lidx = nchunks - 1 - g, c + ((N - 1) - g * c)
        keep = (Sloc - lidx) if RANK == owner_last else 1
        valid = max(0, min(N - a*c, c)) + max(0, min(N - b*c, c))   # local non-pad length
    else:
        pad_to = ((N + W - 1) // W) * W
        S = pad_to // W
        if pad_to > N:
            prompt_ids = torch.cat([prompt_ids.cpu(),
                                    torch.full((1, pad_to - N), PAD, dtype=torch.long)], dim=1)
        start = RANK * S
        shard = prompt_ids[:, start:start + S].to(DEV)
        pos = torch.arange(start, start + S, device=DEV).unsqueeze(0)
        owner_last = (N - 1) // S
        lidx = (N - 1) - owner_last * S
        keep = (S - lidx) if RANK == owner_last else 1
        valid = max(0, min((RANK + 1) * S, N) - start)

    # ---- prefill ----
    CP["phase"] = "prefill"
    if verbose and RANK == 0:
        print(f"[prefill] N={N} pad_to={pad_to} mode={'zigzag' if zigzag else 'contiguous'} "
              f"shard={shard.shape[1]}/rank", flush=True)
    out = model(input_ids=shard, position_ids=pos, use_cache=False, logits_to_keep=keep)

    for l in list(KV.keys()):                               # drop padded tokens from KV
        KV[l] = (KV[l][0][:, :, :valid].contiguous(), KV[l][1][:, :, :valid].contiguous())

    nxt = torch.zeros(1, 1, dtype=torch.long, device=DEV)
    if RANK == owner_last:
        nxt = out.logits[:, 0, :].argmax(-1).view(1, 1)
    dist.broadcast(nxt, src=owner_last)

    # ---- decode (identical for both modes) ----
    gen = [nxt.clone()]
    cur = N
    CP["phase"] = "decode"
    for _ in range(max_new - 1):
        CP["owner"] = cur % WORLD
        out = model(input_ids=nxt, position_ids=torch.tensor([[cur]], device=DEV),
                    use_cache=False, logits_to_keep=1)
        nxt = out.logits[:, -1, :].argmax(-1).view(1, 1)
        dist.broadcast(nxt, src=0)
        gen.append(nxt.clone())
        cur += 1
        if nxt.item() == EOS:
            break
    return torch.cat(gen, dim=1)


if __name__ == "__main__":
    # Validation: contiguous and zigzag CP both vs stock-attention greedy on a short prompt.
    msg = [{"role": "user", "content": "List three components of a CPU pipeline."}]
    enc = tok.apply_chat_template(msg, add_generation_prompt=True,
                                  return_tensors="pt", return_dict=True)
    ids = enc["input_ids"]
    out_contig = cp_generate(ids, max_new=40, zigzag=False)
    out_zig = cp_generate(ids, max_new=40, zigzag=True)

    if RANK == 0:
        ref_model = AutoModelForCausalLM.from_pretrained(
            MODEL_SOURCE,
            revision=None if LOCAL_MODEL else MODEL_REVISION,
            local_files_only=LOCAL_MODEL,
            dtype=torch.bfloat16,
            attn_implementation="sdpa",
        ).to(DEV).eval()
        with torch.no_grad():
            ref = ref_model.generate(ids.to(DEV), max_new_tokens=40, do_sample=False)[0, ids.shape[1]:]
        def m(a):
            n = min(len(a), len(ref)); return int((a[:n].cpu() == ref[:n].cpu()).sum()), n
        mc, n = m(out_contig[0]); mz, _ = m(out_zig[0])
        print(f"\n[REF   ] {tok.decode(ref, skip_special_tokens=True)}")
        print(f"[contig] {tok.decode(out_contig[0], skip_special_tokens=True)}")
        print(f"[zigzag] {tok.decode(out_zig[0], skip_special_tokens=True)}")
        print(f"\ncontiguous vs REF: {mc}/{n}   zigzag vs REF: {mz}/{n}")
        print("ZIGZAG OK" if mz >= 5 else "ZIGZAG SUSPECT")
    dist.barrier()
    dist.destroy_process_group()
