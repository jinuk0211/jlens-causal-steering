"""neuron-explorer server with the agentbench2 ToolAlign-4B trajectories loaded as cases.
Type "#case N" in the fires box (or pick from the case list) to run trajectory N's exact token ids (prompt + response up to
the tool name) through the live model; everything else is the unchanged explorer.
Gated DeltaNet runs through ab_core.patch_gdn (torch fallback, segmented) because this box has no fla.
env: NE_SEQS (ta_seqs.json), NE_UNITS (flow units.json), NE_FIRES (flow_patterns_r2_fires.json), NE_CE (ce rows.jsonl),
     NE_ABCORE_DIR (dir with ab_core.py), NE_MAX_TOKENS (default 12000)
Usage: python explorer/ne_cases.py"""
import asyncio
import json
import os
import re
import sys
import time

import numpy as np
from fastapi import Request

sys.path.insert(0, os.environ.get("NE_ABCORE_DIR", "/workspace/tj"))
import ab_core as C

C.patch_gdn()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("NE_DTYPE"):
    import torch as _torch
    import runtime as _R
    _orig_fp = _R.Qwen3_5ForConditionalGeneration.from_pretrained

    def _fp(*a, **k):
        k["dtype"] = getattr(_torch, os.environ["NE_DTYPE"])
        return _orig_fp(*a, **k)
    _R.Qwen3_5ForConditionalGeneration.from_pretrained = _fp
import server as S

MAXT = int(os.environ.get("NE_MAX_TOKENS", "12000"))
SEQS = json.load(open(os.environ["NE_SEQS"], encoding="utf-8"))
for _p in filter(None, os.environ.get("NE_EXTRA", "").split(",")):
    SEQS += json.load(open(_p, encoding="utf-8"))
UNITS = {u["idx"]: u for u in json.load(open(os.environ["NE_UNITS"], encoding="utf-8"))} if os.environ.get("NE_UNITS") else {}
FIRES = json.load(open(os.environ["NE_FIRES"], encoding="utf-8")) if os.environ.get("NE_FIRES") else {}
CE = {}
if os.environ.get("NE_CE"):
    for line in open(os.environ["NE_CE"], encoding="utf-8"):
        r = json.loads(line)
        CE.setdefault(r["idx"], {})[f"{r['start']}/{r['config']}"] = r["gen_tool"]


def group(u):
    if u.get("group"):
        return u["group"]
    if u.get("label") == "am":
        return "am_resp"
    return "fail" if u.get("label") == "target" and u.get("risk") != "aligned" else ("aligned" if u.get("label") == "target" else "ref")


def case_meta(n):
    u = SEQS[n]
    inf = UNITS.get(n, {})
    ce = CE.get(n, {})
    return {"i": n, "group": group(u), "risk": u.get("risk"), "domain": u.get("domain"), "tool": u.get("tool"),
            "type": u.get("type"), "tokens": u["pos"] + 1, "onset": u["onset"], "scaf": u.get("scaf", inf.get("scaf_start", u["pos"])),
            "pos": u["pos"], "dec": u.get("dec"), "fires": {w: FIRES[w][str(n)][1] for w in FIRES if str(n) in FIRES[w]},
            "attn_commit": ce.get("commit/attn_16_20"), "base_commit": ce.get("commit/base")}


def fast_units(ids):
    tok = S.rt.tok
    units, pending = [], []
    for i, t in enumerate(ids):
        pending.append(i)
        s = tok.decode([ids[j] for j in pending])
        if s.endswith("�") and len(pending) < 4 and i < len(ids) - 1:
            continue
        units.append((s, pending))
        pending = []
    return units


async def cases():
    return [case_meta(n) for n in range(len(SEQS))]


async def infer2(req: Request):
    b = await req.json()
    m = re.match(r"^#case\s+(\d+)\s*$", str(b.get("text", "")).strip())
    if not m:
        return await S.infer(req)
    n = int(m.group(1))
    if not os.path.exists(S.ACT_SCALE) or S.rt.tok is None or n >= len(SEQS):
        return {"ready": False}
    u = SEQS[n]
    ids = list(u["ids"][:u["pos"] + 1])[:MAXT]
    acts = await asyncio.to_thread(S.rt.full_activations, ids, True)
    score, acts16, pre = await asyncio.to_thread(post, acts)
    del acts
    units = await asyncio.to_thread(fast_units, ids)
    unit_of = {i: k for k, (_, idx) in enumerate(units) for i in idx}
    S._infer.clear()
    S._infer.update(ids=ids, toks=[units[unit_of[i]][0] for i in range(len(ids))], acts=acts16, score=score, units=units, pre=pre)
    return {"ready": True, "tokens": [x[0] for x in units], "pos": [x[1][-1] for x in units], "case": case_meta(n)}


def post(acts):
    """Scores as server.score_text, computed on the GPU one layer at a time, plus each neuron's strongest token per sign
    filter (what /api/infer/view needs for pos = -1), so the view does not scan [L, T, N] on the CPU."""
    import torch
    with S.rt.lock, torch.inference_mode():
        sc = np.load(S.ACT_SCALE)
        ps = torch.tensor(np.maximum(sc["pos"], np.maximum(0.1 * -sc["neg"], 1e-3)), dtype=torch.float32, device="cuda")
        ng = torch.tensor(np.minimum(sc["neg"], np.minimum(-0.1 * sc["pos"], -1e-3)), dtype=torch.float32, device="cuda")
        L, T, N = acts.shape
        score = np.empty(acts.shape, np.float32)
        acts16 = np.empty(acts.shape, np.float16)
        pre = {k: (np.empty((L, N), np.float32), np.empty((L, N), np.int64)) for k in ("both", "+", "-")}
        for l in range(L):
            a = torch.from_numpy(acts[l]).cuda()
            s = torch.where(a >= 0, a / ps[l], -(a / ng[l]))
            if T > 1:
                s[0] = 0
            score[l] = s.cpu().numpy()
            acts16[l] = a.half().cpu().numpy()
            for k, idx in (("both", s.abs().argmax(0)), ("+", s.argmax(0)), ("-", s.argmin(0))):
                pre[k][0][l] = s.gather(0, idx[None])[0].cpu().numpy()
                pre[k][1][l] = idx.cpu().numpy()
            del a, s
        torch.cuda.empty_cache()
    return score, acts16, pre


async def dump(req: Request):
    """Batch stats for one case (no UI state touched): per window, every neuron's raw max / argmax and min / argmin,
    plus per-token top-K by |score| over the whole text. Saved as npz at body["out"] (under NE_DUMP_DIR)."""
    b = await req.json()
    n = int(b["case"])
    u = SEQS[n]
    ids = list(u["ids"][:u["pos"] + 1])
    wins = b.get("windows") or u.get("windows") or {"all": [1, len(ids)]}
    out = os.path.join(os.environ.get("NE_DUMP_DIR", "/workspace/tj/ne_x/dump"), os.path.basename(b["out"]))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    k = int(b.get("k", 16))

    def work():
        import torch
        acts = S.rt.full_activations(ids, False)
        with S.rt.lock, torch.inference_mode():
            sc = np.load(S.ACT_SCALE)
            ps = torch.tensor(np.maximum(sc["pos"], np.maximum(0.1 * -sc["neg"], 1e-3)), dtype=torch.float32, device="cuda")
            ng = torch.tensor(np.minimum(sc["neg"], np.minimum(-0.1 * sc["pos"], -1e-3)), dtype=torch.float32, device="cuda")
            L, T, N = acts.shape
            W = list(wins)
            mx, mn = np.zeros((len(W), L, N), np.float32), np.zeros((len(W), L, N), np.float32)
            amx, amn = np.zeros((len(W), L, N), np.int32), np.zeros((len(W), L, N), np.int32)
            fi, fv = np.zeros((T, L, k), np.int16), np.zeros((T, L, k), np.float16)
            for l in range(L):
                a = torch.from_numpy(acts[l]).cuda()
                s = torch.where(a >= 0, a / ps[l], -(a / ng[l]))
                s[0] = 0
                val, idx = s.abs().topk(k, dim=-1)
                fi[:, l] = idx.to(torch.int16).cpu().numpy()
                fv[:, l] = s.gather(1, idx).half().cpu().numpy()
                for wi, w in enumerate(W):
                    lo, hi = max(1, wins[w][0]), wins[w][1]
                    seg = a[lo:hi]
                    v, i = seg.max(0)
                    mx[wi, l], amx[wi, l] = v.cpu().numpy(), (i + lo).cpu().numpy()
                    v, i = seg.min(0)
                    mn[wi, l], amn[wi, l] = v.cpu().numpy(), (i + lo).cpu().numpy()
                del a, s
            torch.cuda.empty_cache()
        np.savez_compressed(out, mx=mx, mn=mn, amx=amx, amn=amn, flow_idx=fi, flow_val=fv, windows=np.array(W),
                            spans=np.array([wins[w] for w in W]), ids=np.array(ids))
        return {"out": out, "T": T}
    return await asyncio.to_thread(work)


def am_generate(ids, rows, max_new, temperature, scenario, check_every=16):
    """Batched sampling for the AM steering loop: every row starts from the same prompt ids, row r adds its own pushes
    (neuron-explorer 'add' units: dose x layer resid p50 / |down column|) at every position, prompt and reply, and samples
    at `temperature` with its own CPU generator seeded by row["seed"] (rows of one (prompt, seed) share the noise).
    The model lock is held one forward at a time, so the explorer UI can interleave. A row stops at <|im_end|>, at the
    complete harmful marker (am_markers.marker_end), or at max_new."""
    import torch
    from am_markers import marker_end
    rt = S.rt
    rt.ensure_loaded()
    B = len(rows)
    with rt.lock:
        acc = {}
        for r, row in enumerate(rows):
            for p in row["pushes"]:
                l, n, d = int(p[0]), int(p[1]), float(p[2])
                mode = p[3] if len(p) > 3 else "add"
                v = acc.setdefault((l, n, mode), [1.0 if mode == "mul" else 0.0] * B)
                v[r] = v[r] * d if mode == "mul" else v[r] + d
        push = []
        for (l, n, mode), ds in acc.items():
            unit = 1.0 if mode == "mul" else rt.layer_resid_p50(l) / float(rt.down_col(l, n).norm())
            push.append((l, n, mode, torch.tensor([d * unit for d in ds], device=rt.dev)))
    push = push or None
    gens = [torch.Generator(device=rt.dev).manual_seed(int(row["seed"])) for row in rows]
    eos = rt.tok.convert_tokens_to_ids("<|im_end|>")
    out_ids, stop = [[] for _ in range(B)], [None] * B

    tf = [0.0]

    def fwd(**kw):
        with rt.lock:
            t1 = time.time()
            rt._push = push
            try:
                return rt.model(use_cache=True, logits_to_keep=1, **kw)
            finally:
                rt._push = None
                tf[0] += time.time() - t1
    t0 = time.time()
    x = torch.tensor([list(ids)] * B, device=rt.dev)
    with torch.inference_mode():
        out = None
        for s0 in range(0, x.shape[1], 512):
            pkv = out.past_key_values if out is not None else None
            out = fwd(input_ids=x[:, s0:s0 + 512], past_key_values=pkv)
            del pkv
        steps = 0
        for steps in range(max_new):
            lg = out.logits[:, -1].float() / temperature
            g = torch.stack([-torch.log(-torch.log(torch.rand(lg.shape[1], device=rt.dev, generator=gens[r]).clamp_min(1e-20)))
                             for r in range(B)])
            nxt = (lg + g).argmax(-1).cpu()
            for r in range(B):
                if stop[r] is None:
                    t = int(nxt[r])
                    if t == eos:
                        stop[r] = "eos"
                    else:
                        out_ids[r].append(t)
            if scenario and steps % check_every == check_every - 1:
                for r in range(B):
                    if stop[r] is None and marker_end(scenario, rt.tok.decode(out_ids[r])) is not None:
                        stop[r] = "marker"
            if all(s is not None for s in stop):
                break
            pkv = out.past_key_values
            out = fwd(input_ids=nxt[:, None].to(rt.dev), past_key_values=pkv)
            del pkv
        del out
        torch.cuda.empty_cache()
    res = []
    for r, row in enumerate(rows):
        text = rt.tok.decode(out_ids[r])
        mk = marker_end(scenario, text) if scenario else None
        res.append({**{k: v for k, v in row.items() if k != "pushes"}, "text": text, "n_tokens": len(out_ids[r]),
                    "stop": stop[r] or "max_new", "marker": mk is not None, "marker_end": mk})
    return {"rows": res, "steps": steps + 1, "sec": round(time.time() - t0, 1), "fwd_sec": round(tf[0], 1)}


async def am_gen(req: Request):
    b = await req.json()
    u = SEQS[int(b["case"])]
    ids = list(u["ids"][:u["pos"] + 1])
    try:
        return await asyncio.to_thread(am_generate, ids, b["rows"], int(b.get("max_new", 3072)), float(b.get("temperature", 1.0)),
                                       b.get("scenario"))
    finally:
        import torch
        torch.cuda.empty_cache()


def neuron_trace(ids, neurons, wins, chunk=1024):
    """Teacher-forced pass over ids (CHUNK pieces with cache, under the model lock) recording only the listed neurons
    [layer, n, pole] at every position. Score as server.score_text (act_scale units); pole-aligned score = pole x score.
    Per window [a, b): mean pole-aligned score, max pole-aligned score, share of tokens with pole-aligned score >= 1."""
    import torch
    rt = S.rt
    rt.ensure_loaded()
    sc = np.load(S.ACT_SCALE)
    ps = np.maximum(sc["pos"], np.maximum(0.1 * -sc["neg"], 1e-3))
    ng = np.minimum(sc["neg"], np.minimum(-0.1 * sc["pos"], -1e-3))
    by = {}
    for j, (l, n, p) in enumerate(neurons):
        by.setdefault(int(l), []).append((j, int(n)))
    T = len(ids)
    A = np.zeros((T, len(neurons)), np.float32)
    cur = {"s0": 0}

    def mk(l):
        cols = torch.tensor([n for _, n in by[l]])
        js = [j for j, _ in by[l]]

        def f(mod, args):
            x = args[0][0][:, cols.to(args[0].device)].float().cpu().numpy()
            A[cur["s0"]:cur["s0"] + x.shape[0], js] = x
        return f
    with rt.lock, torch.inference_mode():
        hs = [rt.lm.layers[l].mlp.down_proj.register_forward_pre_hook(mk(l)) for l in by]
        try:
            cache = None
            for s0 in range(0, T, chunk):
                cur["s0"] = s0
                o = rt.lm(input_ids=torch.tensor([ids[s0:s0 + chunk]], device=rt.dev), past_key_values=cache, use_cache=True)
                cache = o.past_key_values
            del cache, o
        finally:
            for h in hs:
                h.remove()
        torch.cuda.empty_cache()
    L = np.array([int(l) for l, _, _ in neurons])
    N = np.array([int(n) for _, n, _ in neurons])
    P = np.array([int(p) for _, _, p in neurons], np.float32)
    S_ = np.where(A >= 0, A / ps[L, N], -(A / ng[L, N])) * P
    out = {}
    for w, (a, b) in wins.items():
        a, b = max(1, int(a)), min(T, int(b))
        if b <= a:
            out[w] = None
            continue
        seg = S_[a:b]
        out[w] = {"mean": seg.mean(0).round(4).tolist(), "max": seg.max(0).round(3).tolist(), "fire": (seg >= 1).mean(0).round(4).tolist()}
    return out


async def ntrace(req: Request):
    b = await req.json()
    return await asyncio.to_thread(neuron_trace, b["ids"], b["neurons"], b["windows"])


async def infer_view2(pos: int = -1, sign: str = "both", lo: int = 0, hi: int = 99, min: float = 1.0, q: str = "",
                      limit: int = 300):
    if pos >= 0 or "pre" not in S._infer:
        return await S.infer_view(pos, sign, lo, hi, min, q, limit)
    import base64
    A, toks = S._infer["acts"], S._infer["toks"]
    best, at = S._infer["pre"]["+" if sign == "+" else "-" if sign == "-" else "both"]
    view = best.copy()
    keep = np.abs(best) >= min
    if sign == "+": keep &= best > 0
    if sign == "-": keep &= best < 0
    lay = np.arange(best.shape[0])[:, None]
    keep &= (lay >= lo) & (lay <= hi)
    idx = S.lens_index()
    vocab = await asyncio.to_thread(S.rt.vocab_strings)
    if q.strip() and idx is not None:
        ql = q.strip().lower()
        match = np.array([i for i, t in enumerate(vocab) if ql in t.lower()], dtype=np.int32)
        lens_hit = np.where(best[..., None] >= 0, np.isin(idx["up"][:, :, :6], match), np.isin(idx["down"][:, :, :6], match)).any(-1)
        keep &= lens_hit
    view[~keep] = 0
    ls, ns = np.nonzero(keep)
    order = np.argsort(-np.abs(best[ls, ns]))[:limit]
    nm, res = S.names(), []
    for o in order:
        l, n = int(ls[o]), int(ns[o]); sg = "+" if best[l, n] > 0 else "-"
        lens = [vocab[k] for k in (idx["up"] if sg == "+" else idx["down"])[l, n, :6]] if idx is not None else []
        t = int(at[l, n])
        res.append({"layer": l, "n": n, "sign": sg, "score": round(float(abs(best[l, n])), 2),
                    "act": round(float(A[l, t, n]), 2), "token": toks[t], "pos": t,
                    "name": nm.get(f"L{l}/N{n}", ""), "lens": lens})
    blob = base64.b64encode(view.astype(np.float16).tobytes()).decode()
    return {"results": res, "total": int(keep.sum()), "map": blob, "shape": list(view.shape)}


routes = S.app.router.routes
routes[:] = [r for r in routes if getattr(r, "path", None) not in ("/api/infer", "/api/infer/view")]
S.app.add_api_route("/api/infer", infer2, methods=["POST"])
S.app.add_api_route("/api/infer/view", infer_view2, methods=["GET"])
S.app.add_api_route("/api/cases", cases, methods=["GET"])
S.app.add_api_route("/api/ne_dump", dump, methods=["POST"])
S.app.add_api_route("/api/am_gen", am_gen, methods=["POST"])
S.app.add_api_route("/api/ntrace", ntrace, methods=["POST"])
mine = routes[-6:]
del routes[-6:]
routes[0:0] = mine

if __name__ == "__main__":
    S.uvicorn.run(S.app, host="127.0.0.1", port=S.PORT, timeout_graceful_shutdown=3)
