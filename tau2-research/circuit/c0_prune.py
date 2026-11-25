"""C-LOOP C0b (PLAN.md "C-LOOP"): RelP-style pruning with forward sufficiency / necessity checks at the decision position. GPU 0 only.
Nodes: MLP neurons (32 x 9216) and attention heads (8 x 16 full, 24 x 32 linear) at the last position. Score = grad x (x - mu) from
C0a: the first-order change of m = logit(c) - logit(g) (symmetric contrast) when the node is mean-ablated. mu = mean over train-split
good units of the same position type (neurons: M1 u_<k>.npz act; heads: C0a hin). One-token cached forward at the last position;
ablated nodes are set to mu, kept nodes are computed normally. f(S) = (m_S - m_0) / (m - m_0), m_0 = every node ablated.
N90 = smallest top-N by |score| with f >= 0.9 (doubling grid, then bisection). Necessity f_nec = (m - m_without_S) / (m - m_0).
Random control: the same per-layer neuron and head counts drawn outside S. Output probe/circuit/out/c0/prune.json + S_<k>.npy"""
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

R = Path("/home/project-b/LJW/tau2-steer")
sys.path.insert(0, str(R / "probe/topk"))
import build_topk as bt

C0 = R / "probe/circuit/out/c0"
M1 = R / "probe/m1/out"
CHUNK = 4096
GRID = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536]
BISECT = 4
LIMIT = int(os.environ.get("C0B_LIMIT", "0"))
OUT = Path(os.environ.get("C0B_OUT", str(C0)))
AIR_TRAIN = {"0", "1", "3", "4", "5", "7", "9", "10", "11", "12", "14", "15", "17", "20", "21", "23", "27", "28", "36", "38", "39",
             "40", "41", "42"}


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def is_train(domain, task):
    if domain == "airline":
        return task in AIR_TRAIN
    return int(hashlib.md5(f"{domain}|{task}".encode()).hexdigest(), 16) % 2 == 0


def main():
    uuid = str(torch.cuda.get_device_properties(0).uuid)
    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID" or "c27bc2d7" not in uuid:
        log(f"wrong GPU {uuid}; exiting")
        return 2
    os.chdir(R / "tau2-bench")
    torch.set_grad_enabled(False)
    rows = json.loads((C0 / "units.json").read_text(encoding="utf-8"))
    rows = [r for r in rows if (C0 / f"n_{r['k']}.npz").is_file() and (M1 / f"u_{r['k']}.npz").is_file()]
    for r in rows:
        r["split"] = "train" if is_train(r["domain"], r["task"]) else "eval"
    ref = {}
    for r in rows:
        if r["label"] == "good" and r["split"] == "train":
            ref.setdefault(r["ptype"], []).append(r["k"])
    mu_a, mu_h = {}, {}
    for pt, ks in ref.items():
        sa = None
        sh = None
        for k in ks:
            a = np.load(M1 / f"u_{k}.npz")["act"].astype(np.float32)
            h = np.load(C0 / f"n_{k}.npz")["hin"].astype(np.float32)
            sa = a if sa is None else sa + a
            sh = h if sh is None else sh + h
        mu_a[pt] = sa / len(ks)
        mu_h[pt] = sh / len(ks)
    log(f"{len(rows)} units; reference good-train units per ptype { {pt: len(ks) for pt, ks in ref.items()} }")
    tok, model = bt.load_model(os.environ["JC_MODEL"], "cuda")
    blocks = model.model.layers
    nl = len(blocks)
    nn = blocks[0].mlp.down_proj.in_features
    full = [i for i, b in enumerate(blocks) if hasattr(b, "self_attn")]
    nheads = np.array([16 if i in full else 32 for i in range(nl)])
    hdim = np.array([256 if i in full else 128 for i in range(nl)])
    head_valid = np.zeros((nl, 32), bool)
    for i in range(nl):
        head_valid[i, :nheads[i]] = True
    st = {"kn": None, "kh": None, "mu_a": None, "mu_h": None}

    def pre_down(i):
        def f(module, args):
            if st["kn"] is not None:
                return (torch.where(st["kn"][i], args[0], st["mu_a"][i]),)
        return f

    def pre_out(i):
        def f(module, args):
            if st["kh"] is not None:
                return (torch.where(st["kh"][i], args[0], st["mu_h"][i]),)
        return f

    for i, b in enumerate(blocks):
        b.mlp.down_proj.register_forward_pre_hook(pre_down(i))
        (b.self_attn.o_proj if i in full else b.linear_attn.out_proj).register_forward_pre_hook(pre_out(i))

    want = {(r["cond"], r["sim"], r["turn"]) for r in rows}
    seqs = {}
    for domain in ("airline", "retail", "telecom"):
        conds = sorted({r["cond"] for r in rows if r["domain"] == domain})
        if not conds:
            continue
        for domain_, cond, task, sim, tel in bt.episodes(Path("data/simulations/pilot"), Path("data/jlens-telemetry/pilot"), [domain], conds):
            for line in tel.open(encoding="utf-8"):
                rec = json.loads(line)
                key = (cond, sim["id"], int(rec["turn_index"]))
                if key in want:
                    seqs[key] = (rec["input_ids"], rec["generated_ids"])

    def masks(neur_idx, head_idx, keep):
        kn = torch.zeros(nl, nn, dtype=torch.bool, device="cuda")
        kh = torch.zeros(nl, 4096, dtype=torch.bool, device="cuda")
        if len(neur_idx):
            t = torch.as_tensor(neur_idx, device="cuda")
            kn.view(-1)[t] = True
        for j in head_idx:
            l, h = divmod(int(j), 32)
            kh[l, h * hdim[l]:(h + 1) * hdim[l]] = True
        if not keep:
            kn, kh = ~kn, ~kh
        return kn, kh

    def step(cache0, last, c, g, kn=None, kh=None):
        cache = copy.deepcopy(cache0)
        st["kn"], st["kh"] = kn, kh
        out = model.model(input_ids=torch.tensor([[last]], device="cuda"), past_key_values=cache, use_cache=True)
        st["kn"] = st["kh"] = None
        lg = model.lm_head(out.last_hidden_state[0, -1]).float()
        del cache
        return float(lg[c] - lg[g])

    out_rows = []
    done = set()
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "prune.json").is_file():
        out_rows = json.loads((OUT / "prune.json").read_text(encoding="utf-8"))
        done = {r["k"] for r in out_rows}
    rng = np.random.default_rng(0)
    t0 = time.time()
    n_new = 0
    for r in rows:
        if r["k"] in done or r["ptype"] not in mu_a:
            continue
        inp, gen = seqs[(r["cond"], r["sim"], r["turn"])]
        seq = list(inp) + list(gen[:r["d"]])
        z = np.load(C0 / f"n_{r['k']}.npz")
        act = np.load(M1 / f"u_{r['k']}.npz")["act"].astype(np.float32)
        grad = z["grad"].astype(np.float32)
        hin = z["hin"].astype(np.float32)
        hgrad = z["hgrad"].astype(np.float32)
        pt = r["ptype"]
        s_n = (grad * (act - mu_a[pt])).ravel()
        s_h = np.zeros((nl, 32), np.float32)
        for i in range(nl):
            s_h[i, :nheads[i]] = (hgrad[i] * (hin[i] - mu_h[pt][i])).reshape(nheads[i], hdim[i]).sum(1)
        s_h[~head_valid] = 0
        scores = np.concatenate([s_n, s_h.ravel()])
        valid = np.concatenate([np.ones(nl * nn, bool), head_valid.ravel()])
        order = np.argsort(-np.abs(scores))
        order = order[valid[order]]
        st["mu_a"] = torch.tensor(mu_a[pt], device="cuda", dtype=torch.bfloat16)
        st["mu_h"] = torch.tensor(mu_h[pt], device="cuda", dtype=torch.bfloat16)
        with torch.no_grad():
            cache0 = None
            for s in range(0, len(seq) - 1, CHUNK):
                ids = torch.tensor([seq[s:min(s + CHUNK, len(seq) - 1)]], device="cuda")
                cache0 = model.model(input_ids=ids, past_key_values=cache0, use_cache=True).past_key_values
        c, g, last = r["c"], r["g"], seq[-1]
        m = step(cache0, last, c, g)
        kn0, kh0 = masks([], [], True)
        m0 = step(cache0, last, c, g, kn0, kh0)
        den = m - m0

        def split_idx(idx):
            idx = np.asarray(idx)
            return idx[idx < nl * nn], idx[idx >= nl * nn] - nl * nn

        def f_keep(N):
            ni, hi = split_idx(order[:N])
            return (step(cache0, last, c, g, *masks(ni, hi, True)) - m0) / den

        grid = []
        n90 = None
        prev = 0
        for N in (GRID if abs(den) >= 0.5 else []):
            f = f_keep(N)
            grid.append([N, f])
            if f >= 0.9:
                n90 = N
                break
            prev = N
        if n90 is not None and prev:
            lo, hi = prev, n90
            for _ in range(BISECT):
                mid = (lo + hi) // 2
                if mid in (lo, hi):
                    break
                f = f_keep(mid)
                grid.append([mid, f])
                if f >= 0.9:
                    hi = mid
                else:
                    lo = mid
            n90 = hi
        res = {k: r[k] for k in ("k", "label", "kind", "ptype", "call", "domain", "task", "split", "c_tok", "g_tok", "m")} | {
            "m_fwd": m, "m_0": m0, "m_0_lin": float(m - scores.sum()), "grid": sorted(grid), "N90": n90}
        if n90 is not None:
            S = order[:n90]
            ni, hi_ = split_idx(S)
            f90 = dict(grid)[n90]
            m_nec = step(cache0, last, c, g, *masks(ni, hi_, False))
            per_layer = np.bincount(ni // nn, minlength=nl)
            heads_S = [(int(j) // 32, int(j) % 32) for j in hi_]
            rn = []
            for l in range(nl):
                pool_l = np.setdiff1d(np.arange(l * nn, (l + 1) * nn), ni)
                rn.extend(rng.choice(pool_l, size=min(per_layer[l], len(pool_l)), replace=False).tolist())
            rh = []
            for l in range(nl):
                cnt = sum(1 for (hl, _) in heads_S if hl == l)
                pool_h = [l * 32 + h for h in range(nheads[l]) if (l, h) not in heads_S]
                if cnt:
                    rh.extend(rng.choice(pool_h, size=min(cnt, len(pool_h)), replace=False).tolist())
            f_rand = (step(cache0, last, c, g, *masks(rn, rh, True)) - m0) / den
            m_rand_nec = step(cache0, last, c, g, *masks(rn, rh, False))
            res |= {"f90": f90, "nec90": (m - m_nec) / den, "f_rand": f_rand, "nec_rand": (m - m_rand_nec) / den,
                    "n_heads": len(heads_S), "heads": heads_S, "layer_neurons": per_layer.tolist(),
                    "lin_share": float(scores[S].sum() / scores.sum()) if scores.sum() else None}
            np.save(OUT / f"S_{r['k']}.npy", S.astype(np.int32))
        out_rows.append(res)
        n_new += 1
        del cache0
        if n_new % 10 == 0 or n_new <= 3:
            (OUT / "prune.json").write_text(json.dumps(out_rows, indent=0, default=float), encoding="utf-8")
            log(f"{len(out_rows)}/{len(rows)}, {time.time() - t0:.0f}s; last m {m:.2f} (c0a {r['m']:.2f}) m0 {m0:.2f} N90 {n90} "
                f"f_rand {res.get('f_rand')} nec {res.get('nec90')}")
        if LIMIT and n_new >= LIMIT:
            break
    (OUT / "prune.json").write_text(json.dumps(out_rows, indent=0, default=float), encoding="utf-8")
    log(f"C0B_DONE {len(out_rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
