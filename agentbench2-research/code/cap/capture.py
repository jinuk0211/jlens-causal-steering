"""Forward-only capture for CIRCUIT.md (Qwen3.5-4B rev 851bf6e). No generation: every sequence is a prompt plus the completion
the model actually produced, read once.
Per token, all 32 layers: the attention write (o_proj / out_proj output) and the MLP write (down_proj output), as fp8 e4m3
with one fp16 scale per 128-dim block (tier 1, at the job's tier-1 spans, "t1_pos" lists them); the top-32 MLP neurons per layer
(index, value); the
norm of every attention head's write (16 heads in full-attention layers, 32 in linear-attention layers, padded to 32).
Per piece of at most 128 tokens (pieces are cut at multiples of 128 and at every point where a later sequence branches off):
the mean of every MLP neuron (down_proj input) and of every head's o_proj input; the piece bounds give the token count (tier 2).
The residual stream at layer l is the embedding plus the cumulative sum of both writes below l.
Every forward call has a power-of-two length (at most CAP_CHUNK): a new length makes the kernels re-tune, which costs ~5x.
Prefix sharing: jobs are sorted by token ids. Sequence i starts from a cache snapshot taken at lcp(i-1, i) during sequence i-1,
and writes only positions >= lcp(i-1, i) (for sorted sequences this is the longest prefix shared with any earlier one).
Files: OUT/pending/<seq>_<piece>.npz with a .ok file (bytes, md5) written after it; OUT/index.jsonl one line per sequence.
Usage: python capture.py JOBS.jsonl OUT_DIR
Env: CAP_DTYPE bf16|fp16 (default bf16), CAP_CHUNK (2048), CAP_MAX_PENDING_GB (30), CAP_GDN_PATCH=1 (Turing, no fla),
     CAP_LIMIT (only the first N sorted jobs), CAP_DEV (cuda)."""
import copy
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

MODEL, REV = "Qwen/Qwen3.5-4B", "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
TOPK, BIN, NL, D, NI, HP, QB = 32, 128, 32, 2560, 9216, 32, 128
F8MAX = 448.0


def lcp(a, b):
    n = min(len(a), len(b))
    if n == 0:
        return 0
    d = np.nonzero(np.asarray(a[:n]) != np.asarray(b[:n]))[0]
    return int(d[0]) if len(d) else n


def clone_cache(c):
    def cl(v):
        if torch.is_tensor(v):
            return v.clone()
        if isinstance(v, dict):
            return {k: cl(x) for k, x in v.items()}
        if isinstance(v, list):
            return [cl(x) for x in v]
        if isinstance(v, tuple):
            return tuple(cl(x) for x in v)
        return v
    new = copy.copy(c)
    for k, v in vars(c).items():
        if k == "layers":
            out = []
            for L in v:
                L2 = copy.copy(L)
                for kk, vv in vars(L).items():
                    setattr(L2, kk, cl(vv))
                out.append(L2)
            new.layers = out
        else:
            setattr(new, k, cl(v))
    return new


def t1_spans(j):
    """Tier-1 positions of a job: its own "t1_spans" list, else the whole sequence when "tier1" is true. A span inside a shared
    prefix is stored by the sequence that owns that prefix, which contains the same tokens and therefore the same span."""
    if j.get("t1_spans") is not None:
        return [tuple(x) for x in j["t1_spans"]]
    return [(0, len(j["ids"]))] if j.get("tier1") else []


def plan(jobs):
    """Sorted order, start points, tier-1 spans and the cut points every owner sequence needs for tier 2."""
    jobs.sort(key=lambda j: j["ids"])
    n = len(jobs)
    start = [0] * n
    for i in range(1, n):
        start[i] = lcp(jobs[i - 1]["ids"], jobs[i]["ids"])
    L = [len(j["ids"]) for j in jobs]
    t1_upto = [t1_spans(j) for j in jobs]
    cuts = [set() for _ in range(n)]
    snap = [None] * n
    for j in range(1, n):
        p = start[j]
        if p <= 0 or p >= L[j - 1] + 1:
            continue
        k = j - 1
        while start[k] > p - 1:
            k -= 1
        cuts[k].add(p)
        snap[j - 1] = p
    return start, t1_upto, cuts, snap


class Capture:
    def __init__(self, dev, dtype):
        if os.environ.get("CAP_GDN_PATCH") == "1":
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from am_flow_capture import patch_gdn
            patch_gdn()
        from transformers import Qwen3_5ForConditionalGeneration
        m = Qwen3_5ForConditionalGeneration.from_pretrained(MODEL, revision=REV, dtype=dtype).to(dev).eval()
        m.model.visual = None
        self.lm, self.dev = m.model.language_model, dev
        self.types = m.config.text_config.layer_types
        self.buf = {}
        self.G = []
        for i, lay in enumerate(self.lm.layers):
            o = lay.self_attn.o_proj if self.types[i] == "full_attention" else lay.linear_attn.out_proj
            W = o.weight.detach().float()
            H = 16 if self.types[i] == "full_attention" else 32
            dh = W.shape[1] // H
            Wh = W.view(D, H, dh)
            self.G.append((H, dh, torch.einsum("khd,khe->hde", Wh, Wh)))
            o.register_forward_pre_hook(self._attn_in(i))
            o.register_forward_hook(self._attn_out(i))
            lay.mlp.down_proj.register_forward_pre_hook(self._mlp_in(i))
            lay.mlp.down_proj.register_forward_hook(self._mlp_out(i))

    def _attn_in(self, i):
        def f(mod, args):
            z = args[0][0].float()
            H, dh, G = self.G[i]
            zh = z.view(z.shape[0], H, dh)
            nrm = torch.einsum("thd,hde,the->th", zh, G, zh).clamp_min(0).sqrt()
            hn = torch.zeros(z.shape[0], HP, device=z.device)
            hn[:, :H] = nrm
            self.buf.setdefault("hn", [None] * NL)[i] = hn.half()
            self.buf.setdefault("z", [None] * NL)[i] = z
        return f

    def _attn_out(self, i):
        def f(mod, args, out):
            self.buf.setdefault("ao", [None] * NL)[i] = out[0].float()
        return f

    def _mlp_in(self, i):
        def f(mod, args):
            a = args[0][0].float()
            v, ix = a.abs().topk(TOPK, dim=-1)
            self.buf.setdefault("ti", [None] * NL)[i] = ix.to(torch.int16)
            self.buf.setdefault("tv", [None] * NL)[i] = a.gather(1, ix).half()
            self.buf.setdefault("a", [None] * NL)[i] = a
        return f

    def _mlp_out(self, i):
        def f(mod, args, out):
            self.buf.setdefault("mo", [None] * NL)[i] = out[0].float()
        return f

    @staticmethod
    def q8(x):
        """fp8 e4m3 with one fp16 scale per 128-dim block (20 blocks per 2560-dim vector)."""
        xb = x.reshape(*x.shape[:-1], D // QB, QB)
        s = (xb.abs().amax(-1, keepdim=True) / F8MAX).clamp_min(1e-12)
        return (xb / s).to(torch.float8_e4m3fn).view(torch.uint8).reshape(x.shape), s.squeeze(-1).half()

    def run(self, ids, cache, p0, p1):
        """Forward ids[p0:p1] on top of cache (positions p0..p1-1). Returns the cache and the hooked tensors."""
        self.buf = {}
        with torch.inference_mode():
            o = self.lm(input_ids=torch.tensor([ids[p0:p1]], device=self.dev), past_key_values=cache, use_cache=True)
        return o.past_key_values, self.buf


def pieces(p0, p1, cuts):
    pts = sorted({p0, p1} | {c for c in cuts if p0 < c < p1} | set(range((p0 // BIN + 1) * BIN, p1, BIN)))
    return list(zip(pts[:-1], pts[1:]))


def save(out, name, arrays):
    bio = io.BytesIO()
    np.savez(bio, **arrays)
    b = bio.getvalue()
    tmp = out / "pending" / (name + ".npz.tmp")
    tmp.write_bytes(b)
    tmp.rename(out / "pending" / (name + ".npz"))
    (out / "pending" / (name + ".npz.ok")).write_text(f"{len(b)} {hashlib.md5(b).hexdigest()}\n")
    return len(b)


def pending_gb(out):
    """Bytes still waiting for the puller; files can disappear while counting (the puller moves them)."""
    tot = 0
    with os.scandir(out / "pending") as it:
        for e in it:
            if e.name.endswith(".npz"):
                try:
                    tot += e.stat().st_size
                except FileNotFoundError:
                    pass
    return tot / 2 ** 30


def main():
    jobs_p, out = Path(sys.argv[1]), Path(sys.argv[2])
    (out / "pending").mkdir(parents=True, exist_ok=True)
    dev = os.environ.get("CAP_DEV", "cuda")
    dtype = {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[os.environ.get("CAP_DTYPE", "bf16")]
    CH = int(os.environ.get("CAP_CHUNK", "2048"))
    maxp = float(os.environ.get("CAP_MAX_PENDING_GB", "30"))
    jobs = [json.loads(l) for l in jobs_p.open(encoding="utf-8")]
    start, t1_upto, cuts, snap = plan(jobs)
    lim = int(os.environ.get("CAP_LIMIT", "0")) or len(jobs)
    done = set()
    idx_p = out / "index.jsonl"
    if idx_p.exists():
        done = {json.loads(l)["seq"] for l in idx_p.open(encoding="utf-8")}
    meta = {"n_jobs": len(jobs), "model": MODEL, "rev": REV, "dtype": str(dtype), "topk": TOPK, "bin": BIN,
            "tokens": sum(len(j["ids"]) for j in jobs), "stored_tokens": sum(len(j["ids"]) - s for j, s in zip(jobs, start)),
            "tier1_tokens": sum(sum(max(0, b - max(a, s)) for a, b in sp) for j, s, sp in zip(jobs, start, t1_upto))}
    (out / "plan.json").write_text(json.dumps({**meta, "order": [j["sid"] for j in jobs], "start": start, "t1_upto": t1_upto,
                                                "cuts": [sorted(c) for c in cuts]}), encoding="utf-8")
    print(json.dumps(meta), flush=True)
    if done:
        first = min(i for i in range(lim) if jobs[i]["sid"] not in done) if any(jobs[i]["sid"] not in done for i in range(lim)) else lim
        print(f"resume at sorted job {first} ({len(done)} done)", flush=True)
    else:
        first = 0
    cap = Capture(dev, dtype)
    from concurrent.futures import ThreadPoolExecutor
    ex, futs = ThreadPoolExecutor(int(os.environ.get("CAP_WRITERS", "3"))), []
    prof = {"fwd": 0.0, "post": 0.0, "wait": 0.0}
    snapshot = None
    t0, ntok, nbytes = time.time(), 0, 0
    for i in range(first, lim):
        while pending_gb(out) > maxp:
            time.sleep(15)
        j = jobs[i]
        ids, s = j["ids"], start[i]
        cache = snapshot if (snapshot is not None and s > 0) else None
        s_fwd = 0 if cache is None else s
        snapshot = None
        stops = sorted({p for p in ([snap[i]] if snap[i] else []) if s_fwd < p < len(ids)} | {len(ids)})
        p, piece_no, recs = s_fwd, 0, []
        while p < len(ids):
            lim_p = min([x for x in stops if x > p] + [p + CH, len(ids)])
            nxt = p + (1 << ((lim_p - p).bit_length() - 1))
            tf = time.time()
            cache, B = cap.run(ids, cache, p, nxt)
            if snap[i] == nxt:
                snapshot = clone_cache(cache)
            if dev == "cuda":
                torch.cuda.synchronize()
            prof["fwd"] += time.time() - tf
            tf = time.time()
            w0 = max(p, s)
            if w0 < nxt:
                a, b = w0 - p, nxt - p
                arr = {"pos": np.arange(w0, nxt, dtype=np.int32), "ids": np.asarray(ids[w0:nxt], dtype=np.int32),
                       "top_i": torch.stack([x[a:b] for x in B["ti"]], 1).cpu().numpy(),
                       "top_v": torch.stack([x[a:b] for x in B["tv"]], 1).cpu().numpy(),
                       "head_n": torch.stack([x[a:b] for x in B["hn"]], 1).cpu().numpy()}
                tp = [q for u, v in t1_upto[i] for q in range(max(u, w0), min(v, nxt))]
                if tp:
                    ti = torch.tensor(sorted(set(tp)), device=cap.dev) - p
                    qa, sa = cap.q8(torch.stack([x[ti] for x in B["ao"]], 1))
                    qm, sm = cap.q8(torch.stack([x[ti] for x in B["mo"]], 1))
                    arr.update({"t1_pos": (ti + p).int().cpu().numpy(), "attn_q": qa.cpu().numpy(), "attn_s": sa.cpu().numpy(),
                                "mlp_q": qm.cpu().numpy(), "mlp_s": sm.cpu().numpy()})
                pc = pieces(w0, nxt, cuts[i])
                arr["piece"] = np.asarray(pc, dtype=np.int32)
                arr["piece_neuron_mean"] = torch.stack([torch.stack([x[u - p:v - p].mean(0) for x in B["a"]], 0) for u, v in pc], 0).half().cpu().numpy()
                arr["piece_z_mean"] = torch.stack([torch.stack([x[u - p:v - p].mean(0) for x in B["z"]], 0) for u, v in pc], 0).half().cpu().numpy()
                name = f"{i:06d}_{piece_no:03d}"
                prof["post"] += time.time() - tf
                tw = time.time()
                while len([f for f in futs if not f.done()]) >= 4:
                    time.sleep(0.05)
                prof["wait"] += time.time() - tw
                futs.append(ex.submit(save, out, name, arr))
                recs.append(name)
                piece_no += 1
                ntok += nxt - w0
            del B
            p = nxt
        del cache
        for f in futs:
            nbytes += f.result()
        futs = []
        with idx_p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"seq": j["sid"], "order": i, "len": len(ids), "start": s, "t1_spans": t1_upto[i], "files": recs}) + "\n")
        if i % 20 == 0 or i == lim - 1:
            el = time.time() - t0
            print(f"{time.strftime('%H:%M:%S')} {i + 1}/{lim} stored tokens {ntok:,} ({ntok / max(el, 1):.0f}/s), {nbytes / 2 ** 30:.1f} GiB, "
                  f"pending {pending_gb(out):.1f} GiB; time forward {prof['fwd']:.0f}s post {prof['post']:.0f}s writer wait {prof['wait']:.0f}s", flush=True)
    print("CAPTURE_DONE", flush=True)


if __name__ == "__main__":
    main()
