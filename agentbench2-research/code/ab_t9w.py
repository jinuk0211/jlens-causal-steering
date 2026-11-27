"""T9w (PLAN.md Log 11-27 20:1x, user: "안해본조합 … 다내리고 ㄱㄱ"): leak-side neurons picked by outcome (leaked vs not leaked responses
of the two main leaking prompts), capped only in response tokens 128-640, at three sizes, each against a same-layer random set.
  select : CPU. From the full-response scan (ne/amscan_s1.npy: 174 samples x 17 windows x 32 x 9216), window 256-512 (inside 128-640,
           the window vio8 was picked on). AUROC(leaked > not leaked) per neuron in each fold; keep AUROC > 0.5 in both folds, layers
           >= 2; rank by min over the folds of (AUROC - 0.5). H2048 / H1024 / H512 = top 2,048 / 1,024 / 512 (nested). Random: for each
           chosen neuron in rank order a random neuron of the same layer (seed 211), first K of that list. -> ne/t9w_sel.json
  stats  : GPU. Teacher-forced pass over the not-leaked scan samples: token mean and sd of every candidate neuron over response tokens
           128-640. -> ne/t9w_stats.npz
  arms   : CPU. limit = not-leaked token mean + 1 sd; upper clamp (side +1) at generation steps 128-640 only; spec for ab_ne.py amwin
           (tag t9w): base + 3 sets + 3 random sets, the two main prompts, 24 seeds from 21000, budget 6,144. -> ne/steer_am/arms_t9w.json"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

import numpy as np

A = Path("/home/project-b/LJW/agentbench2/ana")
NE = A / "ne"
sys.path.insert(0, str(A))
NL, NN = 32, 9216
WIN = 1
T0, T1 = 128, 640
SIZES = (2048, 1024, 512)
MAIN = ("leaking_explicit-america_none", "leaking_explicit-america_replacement")


def auroc(X, y):
    r = np.argsort(np.argsort(X, axis=0), axis=0).astype(np.float64) + 1
    n1, n0 = int(y.sum()), int((~y).sum())
    return (r[y].sum(0) - n1 * (n1 + 1) / 2) / (n1 * n0)


def mode_select():
    meta = json.loads((NE / "amscan_s1_meta.json").read_text(encoding="utf-8"))
    X = np.load(NE / "amscan_s1.npy", mmap_mode="r")
    keep = [i for i, m in enumerate(meta) if m["bins"][WIN] >= 64]
    y = np.array([bool(meta[i]["harm"]) for i in keep])
    fold = np.array([int(meta[i]["fold"]) for i in keep])
    W = np.asarray(X[keep, WIN], dtype=np.float32).reshape(len(keep), -1)
    a = {f: auroc(W[fold == f], y[fold == f]) for f in (0, 1)}
    score = np.minimum(a[0], a[1]) - 0.5
    layer = np.arange(NL * NN) // NN
    score[(a[0] <= 0.5) | (a[1] <= 0.5) | (layer < 2)] = -1
    order = np.argsort(-score)[:max(SIZES)]
    rng = np.random.default_rng(211)
    used, rnd = set(int(i) for i in order), []
    for i in order:
        l = int(i) // NN
        while True:
            j = l * NN + int(rng.integers(0, NN))
            if j not in used:
                break
        used.add(j)
        rnd.append(j)
    rep = {"samples": len(keep), "leaked": int(y.sum()), "not_leaked": int((~y).sum()), "folds": dict(Counter(fold.tolist())),
           "candidates_both_folds_above_0.5": int((score > 0).sum()), "auroc_min_fold_top10": [round(float(score[i] + 0.5), 3) for i in order[:10]],
           "auroc_min_fold_at": {k: round(float(score[order[k - 1]] + 0.5), 3) for k in SIZES},
           "layer_hist_2048": sorted(Counter(int(i) // NN for i in order).items())}
    try:
        from transformers import AutoTokenizer
        import ab_core as C
        tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
        dic = np.load(NE / "dict.npz")
        rep["top_words"] = [{"neuron": f"L{int(i) // NN}/N{int(i) % NN}", "auroc": round(float(score[i] + 0.5), 3),
                             "words": [tok.decode([int(t)]) for t in dic["pos_i"][int(i) // NN, int(i) % NN, :6]]} for i in order[:25]]
    except Exception as e:
        print("words skipped", e)
    out = NE / "t9w_sel.json"
    if out.exists():
        raise SystemExit(f"{out} exists")
    out.write_text(json.dumps({"order": [int(i) for i in order], "random": rnd, "report": rep}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k != "top_words"}, ensure_ascii=False))
    print([(w["neuron"], w["auroc"], "".join(w["words"][:4])) for w in rep.get("top_words", [])[:15]])


def mode_stats():
    import torch
    import ab_core as C
    import ab_ne as N
    sel = json.loads((NE / "t9w_sel.json").read_text(encoding="utf-8"))
    cand = np.array(sel["order"] + sel["random"])
    tok, model = C.load()
    H = C.Hooked(model)
    by = {}
    for c, i in enumerate(cand):
        by.setdefault(int(i) // NN, []).append((c, int(i) % NN))
    cols = {l: (torch.tensor([j for _, j in v], device="cuda"), [c for c, _ in v]) for l, v in by.items()}
    S1 = torch.zeros(len(cand), dtype=torch.float64, device="cuda")
    S2 = torch.zeros(len(cand), dtype=torch.float64, device="cuda")
    st = {"on": False, "off": 0, "a": 0, "b": 0, "n": 0}
    cidx = {l: torch.tensor(cs, device="cuda") for l, (_, cs) in cols.items()}

    def pre(l):
        js = cols[l][0]

        def f(mod, args):
            if not st["on"]:
                return None
            x = args[0][0]
            p0 = st["off"]
            lo, hi = max(st["a"] - p0, 0), min(st["b"] - p0, x.shape[0])
            if hi <= lo:
                return None
            v = x[lo:hi][:, js].double()
            S1.index_add_(0, cidx[l], v.sum(0))
            S2.index_add_(0, cidx[l], (v * v).sum(0))
            if l == min(cols):
                st["n"] += hi - lo
            return None
        return f
    hs = [H.blocks[l].mlp.down_proj.register_forward_pre_hook(pre(l)) for l in cols]
    samples = [s for s in N.am_scan_samples(tok) if not s["harm"]]
    dev = C.first_device(model)
    for k, s in enumerate(samples):
        P = list(s["prompt_ids"])
        seq = P + list(s["comp"][:T1])
        st.update(on=True, a=len(P) + T0, b=len(P) + T1)
        with torch.inference_mode():
            cache = None
            for o0 in range(0, len(seq), 1024):
                st["off"] = o0
                o = model(input_ids=torch.tensor([seq[o0:o0 + 1024]], device=dev), past_key_values=cache, use_cache=True, logits_to_keep=1)
                cache = o.past_key_values
            del cache, o
        st["on"] = False
        if k % 10 == 0:
            C.log(f"t9w stats {k + 1}/{len(samples)}")
    for h in hs:
        h.remove()
    n = st["n"]
    mu = (S1 / n).cpu().numpy()
    sd = ((S2 / n - (S1 / n) ** 2).clamp_min(0).sqrt() + 1e-3).cpu().numpy()
    np.savez(NE / "t9w_stats.npz", cand=cand, mu=mu, sd=sd, tokens=n, samples=len(samples))
    C.log(f"T9W_STATS_DONE {len(samples)} not-leaked samples, {n} tokens")


def mode_arms():
    sel = json.loads((NE / "t9w_sel.json").read_text(encoding="utf-8"))
    d = np.load(NE / "t9w_stats.npz")
    lim = {int(i): float(m + s) for i, m, s in zip(d["cand"], d["mu"], d["sd"])}
    sets = {}
    for K in SIZES:
        sets[f"H{K}"] = [[i // NN, i % NN, lim[i], 1] for i in sel["order"][:K]]
        sets[f"rH{K}"] = [[i // NN, i % NN, lim[i], 1] for i in sel["random"][:K]]
    arms = {"base": None}
    for k in sorted(sets, key=lambda x: (x.startswith("r"), -int(x.lstrip("rH")))):
        arms[k] = {"set": k, "t0": T0, "t1": T1}
    out = NE / "steer_am" / "arms_t9w.json"
    if out.exists():
        raise SystemExit(f"{out} exists")
    out.write_text(json.dumps({"arms": arms, "sets": sets, "conditions": list(MAIN), "seeds": 24, "seed_off": 21000, "budget": 6144}),
                   encoding="utf-8")
    print(list(arms), {k: len(v) for k, v in sets.items()}, "limits min / median", round(min(lim.values()), 3), round(float(np.median(list(lim.values()))), 3))


def mode_arms2():
    """T9w2 (user 20:1x: one random arm, more variants of our own neurons): base, one same-layer random set (rH1024, kappa 1, 128-640),
    and nine variants of the chosen neurons: sizes 512 / 1,024 / 2,048 x kappa 1 / 0 (limit = mean + kappa sd) in 128-640, and
    H1024 kappa 1 in windows 128-384, 384-640 and 0-1,024. -> ne/steer_am/arms_t9w2.json"""
    sel = json.loads((NE / "t9w_sel.json").read_text(encoding="utf-8"))
    d = np.load(NE / "t9w_stats.npz")
    st = {int(i): (float(m), float(s)) for i, m, s in zip(d["cand"], d["mu"], d["sd"])}

    def mk(ids, kappa):
        return [[i // NN, i % NN, st[i][0] + kappa * st[i][1], 1] for i in ids]
    sets, arms = {}, {"base": None}
    for K in (512, 1024, 2048):
        for kap in (1, 0):
            name = f"H{K}_k{kap}"
            sets[name] = mk(sel["order"][:K], kap)
            arms[name] = {"set": name, "t0": T0, "t1": T1}
    for a, b in ((128, 384), (384, 640), (0, 1024)):
        arms[f"H1024_k1_w{a}_{b}"] = {"set": "H1024_k1", "t0": a, "t1": b}
    sets["rH1024_k1"] = mk(sel["random"][:1024], 1)
    arms["rH1024_k1"] = {"set": "rH1024_k1", "t0": T0, "t1": T1}
    out = NE / "steer_am" / "arms_t9w2.json"
    if out.exists():
        raise SystemExit(f"{out} exists")
    out.write_text(json.dumps({"arms": arms, "sets": sets, "conditions": list(MAIN), "seeds": 24, "seed_off": 21000, "budget": 6144}),
                   encoding="utf-8")
    print(list(arms))


def mode_arms3():
    """T9w3 (user 20:2x: "우리 5개먼저빨리끝내고"): base, H512 / H1024 / H2048 (kappa 1, 128-640) and one random set rH1024 (kappa 1,
    128-640). -> ne/steer_am/arms_t9w3.json"""
    sel = json.loads((NE / "t9w_sel.json").read_text(encoding="utf-8"))
    d = np.load(NE / "t9w_stats.npz")
    st = {int(i): (float(m), float(s)) for i, m, s in zip(d["cand"], d["mu"], d["sd"])}
    sets = {f"H{K}": [[i // NN, i % NN, st[i][0] + st[i][1], 1] for i in sel["order"][:K]] for K in (512, 1024, 2048)}
    sets["rH1024"] = [[i // NN, i % NN, st[i][0] + st[i][1], 1] for i in sel["random"][:1024]]
    arms = {"base": None, **{k: {"set": k, "t0": T0, "t1": T1} for k in ("H512", "H1024", "H2048", "rH1024")}}
    out = NE / "steer_am" / "arms_t9w3.json"
    if out.exists():
        raise SystemExit(f"{out} exists")
    out.write_text(json.dumps({"arms": arms, "sets": sets, "conditions": list(MAIN), "seeds": 24, "seed_off": 21000, "budget": 6144}),
                   encoding="utf-8")
    print(list(arms))


if __name__ == "__main__":
    {"select": mode_select, "stats": mode_stats, "arms": mode_arms, "arms2": mode_arms2, "arms3": mode_arms3}[sys.argv[1]]()
