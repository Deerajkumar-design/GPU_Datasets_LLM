"""Ring attention core — context-parallel attention across a torch.distributed group.

Each rank holds its contiguous sequence shard of (q, k, v): rank r owns positions
[r*S, (r+1)*S).  We rotate the KV shards around the ring and accumulate each block
with online softmax, then finalize.  Inference-only (prefill / full causal attention).

Two backends for the per-block math:
  backend="flash"  -> torch 2.12 native flash op (bf16, tensor cores, GQA). FAST. Use for real runs.
  backend="kernel" -> our hand-written CUDA kernel (fp32, equal heads). Correctness reference; slow.
"""
import torch
import torch.distributed as dist
import cp_kernels


def ring_exchange(k, v, group=None):
    """Send (k, v) to rank+1, receive the previous rank's (k, v) from rank-1."""
    world = dist.get_world_size(group)
    rank = dist.get_rank(group)
    send, recv = (rank + 1) % world, (rank - 1) % world
    kn, vn = torch.empty_like(k), torch.empty_like(v)
    ops = [dist.P2POp(dist.isend, k.contiguous(), send),
           dist.P2POp(dist.isend, v.contiguous(), send),
           dist.P2POp(dist.irecv, kn, recv),
           dist.P2POp(dist.irecv, vn, recv)]
    for r in dist.batch_isend_irecv(ops):
        r.wait()
    return kn, vn


def _repeat_kv(x, n):
    """[B, Hkv, S, D] -> [B, Hkv*n, S, D] for GQA (expand kv heads to query heads)."""
    if n == 1:
        return x
    B, Hkv, S, D = x.shape
    return x[:, :, None].expand(B, Hkv, n, S, D).reshape(B, Hkv * n, S, D)


def _flash_block(q, k, v, scale, causal):
    """Native flash op for one block. q [B,Hq,Sq,D], k/v [B,Hq,Sk,D] (already repeated)."""
    o, lse = torch.ops.aten._scaled_dot_product_flash_attention(
        q.contiguous(), k.contiguous(), v.contiguous(), 0.0, causal, False, scale=scale)[:2]
    return o, lse                    # o [B,Hq,Sq,D] (input dtype), lse [B,Hq,Sq] fp32


def _merge(out, lse, b_out, b_lse):
    """Online-softmax merge of a new block into the running (out, lse). out kept fp32."""
    b_out = b_out.float()
    if out is None:
        return b_out, b_lse
    new = torch.logaddexp(lse, b_lse)
    out = out * torch.exp(lse - new).unsqueeze(-1) + b_out * torch.exp(b_lse - new).unsqueeze(-1)
    return out, new


def ring_attention(q, k, v, scale=None, causal=True, group=None, backend="flash"):
    """Context-parallel ring attention over this rank's shard.

    Args:
        q:     this rank's query shard [B, Hq, S, D].
        k, v:  this rank's KV shard   [B, Hkv, S, D] (Hkv <= Hq for GQA; flash backend only).
        scale: softmax scale (default 1/sqrt(D)).
        causal:contiguous-shard causal attention (rank order == sequence order).
        backend: "flash" (fast, bf16, GQA) or "kernel" (our fp32 CUDA kernel, equal heads).
    Returns:
        out [B, Hq, S, D] (fp32), lse [B, Hq, S] for this rank's queries.
    """
    world = dist.get_world_size(group)
    rank = dist.get_rank(group)
    B, Hq, S, D = q.shape
    Hkv = k.shape[1]
    nrep = Hq // Hkv
    if scale is None:
        scale = D ** -0.5

    if backend == "kernel":
        assert Hkv == Hq, "kernel backend needs equal heads (no GQA)"
        m = torch.full((B, Hq, S), float("-inf"), device=q.device, dtype=torch.float32)
        l = torch.zeros((B, Hq, S), device=q.device, dtype=torch.float32)
        acc = torch.zeros((B, Hq, S, D), device=q.device, dtype=torch.float32)

    q = q.contiguous()
    out = lse = None
    kc, vc = k.contiguous(), v.contiguous()
    for step in range(world):
        src = (rank - step) % world          # which rank's KV block we currently hold
        if not causal:
            do, blk_causal = True, False
        elif src < rank:
            do, blk_causal = True, False      # past block: full attention
        elif src == rank:
            do, blk_causal = True, True       # diagonal block: causal within
        else:
            do, blk_causal = False, False     # future block: skip
        if do:
            if backend == "flash":
                bo, bl = _flash_block(q, _repeat_kv(kc, nrep), _repeat_kv(vc, nrep), scale, blk_causal)
                out, lse = _merge(out, lse, bo, bl)
            elif backend == "kernel_fast":          # our optimized bf16 CUDA kernel
                bo, bl = cp_kernels.block_attn_fast(
                    q.contiguous(), _repeat_kv(kc, nrep).contiguous(),
                    _repeat_kv(vc, nrep).contiguous(), scale, blk_causal)
                out, lse = _merge(out, lse, bo, bl)
            else:                                   # "kernel": naive fp32 accumulate
                cp_kernels.attn_accumulate(q, kc, vc, m, l, acc, scale, blk_causal)
        if step < world - 1:
            kc, vc = ring_exchange(kc, vc, group)

    if backend == "kernel":
        out = acc / l.unsqueeze(-1)
        lse = m + l.log()
    return out, lse


def ring_attention_zigzag(q, k, v, scale=None, causal=True, group=None):
    """Load-balanced (zigzag/striped) ring attention.

    Local layout: rank r holds global chunks r and 2W-1-r, concatenated as the local
    shard [B,H,2c,D] (first half = chunk r, second half = chunk 2W-1-r).  This balances
    causal work — every non-diagonal ring step does identical work on every rank, instead
    of the last rank doing W x more (the contiguous-shard problem).

    Per ring step (kv held = from rank src = rank-step):
      step 0       : full local, causal=True   (diagonal)
      step <= rank : ALL queries vs FIRST half of received kv, causal=False
      step >  rank : SECOND half of queries vs FULL received kv, causal=False
    """
    world = dist.get_world_size(group)
    rank = dist.get_rank(group)
    B, Hq, S, D = q.shape
    c = S // 2                       # chunk size; local shard = 2 chunks
    nrep = Hq // k.shape[1]
    if scale is None:
        scale = D ** -0.5

    q = q.contiguous()
    kc, vc = k.contiguous(), v.contiguous()
    out = lse = None
    for step in range(world):
        if step == 0:
            bo, bl = _flash_block(q, _repeat_kv(kc, nrep), _repeat_kv(vc, nrep), scale, True)
            out, lse = _merge(out, lse, bo, bl)                  # all 2c rows
        elif step <= rank:
            k0 = _repeat_kv(kc[:, :, :c], nrep)
            v0 = _repeat_kv(vc[:, :, :c], nrep)
            bo, bl = _flash_block(q, k0, v0, scale, False)       # all q vs first kv half
            out, lse = _merge(out, lse, bo, bl)
        else:
            q1 = q[:, :, c:]
            bo, bl = _flash_block(q1, _repeat_kv(kc, nrep), _repeat_kv(vc, nrep), scale, False)
            o2, l2 = _merge(out[:, :, c:], lse[:, :, c:], bo, bl)   # only second-half rows
            out[:, :, c:] = o2
            lse[:, :, c:] = l2
        if step < world - 1:
            kc, vc = ring_exchange(kc, vc, group)
    return out, lse
