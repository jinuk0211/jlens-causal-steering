"""Paper figure: what attention and the MLPs write into the residual stream at the call onset, misaligned vs aligned calls.
The residual after layer l is the embedding plus every earlier write: r_l = e + sum_{k<=l} (attn_k + mlp_k) (pre-norm blocks, no
biases). So the gap between the misaligned and the aligned stream at the last layer splits exactly into one attention and one MLP
term per layer. CPU only.

tacap [THREADS] : ToolAlignBench has no stored neuron activations at the onset, and the GPUs are in use, so the units of
    hn/toolalign/hn.npz are run again on the CPU in float32 (forward only). Per unit, at the onset token of every layer: block
    output, attention output, MLP output and the MLP neuron activations. -> fig_flow/ta_cpu/<uid hash>.npz (resumable)
compute : AgentDojo and AM: mlp_l = W_down_l @ (stored neuron activations at the onset), attn_l = r_l - r_{l-1} - mlp_l, with
    r_{-1} = the embedding of the onset token. ToolAlignBench: the captured outputs. Checks the identity where it can.
    Every term is centered within context x fold (as in ab_resfig.py), divided by the fold-0 standard deviation of the last-layer
    residual and projected on the fold-0 axis of the last layer (difference of class means, unit length). On fold 1:
    per layer the attention and MLP share of the final gap, a cluster bootstrap over contexts, and each unit's position after
    every layer. Neurons: ranked by their fold-0 contribution, the share of the fold-1 MLP term carried by the top k.
    -> fig_flow/flow.json, flow.npz, flow_report.md
plot : -> fig_flow/residual_flow.pdf and .png
Usage: python ab_flowfig.py tacap 16 ; python ab_flowfig.py compute ; python ab_flowfig.py plot"""
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

A = Path("/home/project-b/LJW/agentbench2/ana")
OUT = A / "fig_flow"
TAC = OUT / "ta_cpu"
BENCH = ("dojo", "toolalign", "am")
NAME = {"dojo": "AgentDojo", "toolalign": "ToolAlignBench", "am": "Agentic Misalignment"}
NL, D, NN, NBOOT, SEED = 32, 2560, 9216, 1000, 20261127
FULL = (3, 7, 11, 15, 19, 23, 27, 31)


def log(m):
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def uid_file(uid):
    return TAC / (hashlib.md5(str(uid).encode()).hexdigest()[:16] + ".npz")


def mode_tacap(threads="16", fold="all", order="fwd"):
    import torch
    torch.set_num_threads(int(threads))
    sys.path.insert(0, str(A))
    import ab_core as C
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
    TAC.mkdir(parents=True, exist_ok=True)
    import inspect
    import transformers.models.qwen3_5.modeling_qwen3_5 as mq
    for k, v in list(vars(mq).items()):
        if callable(v) and hasattr(v, "__wrapped__") and ("delta_rule" in k or "causal_conv1d" in k):
            setattr(mq, k, inspect.unwrap(v))
            log(f"reference PyTorch kernel for {k} (the fla kernels need a GPU and bf16)")
    C.patch_gdn()
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(C.MODEL, revision=C.REV, dtype=torch.float32)
    model.model.visual = None
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    lm, blocks, _, _ = C.text_model(model)
    d = np.load(A / "hn" / "toolalign" / "hn.npz")
    want = {str(u): (str(l), int(f)) for u, l, f in zip(d["uids"], d["labels"], d["folds"])}
    seen, items = set(), []
    for u in json.loads((A / "ta" / "units.json").read_text(encoding="utf-8")):
        if u["uid"] in seen or str(u["uid"]) not in want:
            continue
        seen.add(u["uid"])
        comp = list(u["completion_ids"])
        i = tok.decode(comp).find("<tool_call>")
        if i < 0:
            continue
        k = C.char_to_token(tok, comp, i + len("<tool_call>") - 1)
        items.append((u, len(u["prompt_ids"]) + k))
    rank = {"target": 0, "aligned": 1, "reference": 2}
    items.sort(key=lambda x: (1 - x[0]["fold"], rank[x[0]["label"]]))
    if fold != "all":
        items = [x for x in items if x[0]["fold"] == int(fold)]
    if order == "rev":
        items = items[::-1]
    log(f"tacap cpu: {len(items)} units, threads {threads}, fold {fold}, order {order}")
    fw = {"on": False, "off": 0, "p": -1, "res": {}, "attn": {}, "mlp": {}, "act": {}}

    def grab(name, i, pre=False):
        def f(mod, args, out_=None):
            if not fw["on"]:
                return
            x = args[0] if pre else (out_ if torch.is_tensor(out_) else out_[0])
            lo, n = fw["off"], x.shape[1]
            if lo <= fw["p"] < lo + n:
                fw[name][i] = x[0, fw["p"] - lo].detach().float().clone()
        return f
    hs = []
    for i, b in enumerate(blocks):
        att = b.self_attn if hasattr(b, "self_attn") else b.linear_attn
        hs.append(b.register_forward_hook(grab("res", i)))
        hs.append(att.register_forward_hook(grab("attn", i)))
        hs.append(b.mlp.register_forward_hook(grab("mlp", i)))
        hs.append(b.mlp.down_proj.register_forward_pre_hook(grab("act", i, pre=True)))
    emb = lm.embed_tokens.weight
    t0 = time.time()
    for n, (u, on) in enumerate(items):
        f = uid_file(u["uid"])
        if f.exists():
            continue
        seq = list(u["prompt_ids"]) + list(u["completion_ids"])
        fw.update(on=True, p=on, res={}, attn={}, mlp={}, act={})
        t1 = time.time()
        with torch.inference_mode():
            cache = None
            for s in range(0, on + 1, 1024):
                fw["off"] = s
                o = model(input_ids=torch.tensor([seq[s:min(s + 1024, on + 1)]]), past_key_values=cache, use_cache=True, logits_to_keep=1)
                cache = o.past_key_values
            del cache, o
        fw["on"] = False
        res = torch.stack([fw["res"][i] for i in range(NL)])
        att = torch.stack([fw["attn"][i] for i in range(NL)])
        mlp = torch.stack([fw["mlp"][i] for i in range(NL)])
        act = torch.stack([fw["act"][i] for i in range(NL)])
        e = emb[seq[on]].float()
        prev = torch.cat([e[None], res[:-1]])
        err = ((res - prev - att - mlp).norm(dim=1) / (res - prev).norm(dim=1)).max().item()
        tmp = f.with_suffix(".tmp.npz")
        np.savez(tmp, res=res.numpy(), attn=att.numpy(), mlp=mlp.numpy(), act=act.half().numpy(), emb=e.numpy(), tok=seq[on], on=on,
                 uid=str(u["uid"]), label=u["label"], fold=u["fold"], group=u["group"], err=err)
        tmp.rename(f)
        log(f"tacap {n + 1}/{len(items)} {u['label']} fold {u['fold']} onset {on} tokens {time.time() - t1:.0f}s identity error {err:.2e} total {time.time() - t0:.0f}s")
    for h in hs:
        h.remove()
    (OUT / f"TACAP_DONE_{fold}_{order}").touch()
    log("TACAP_DONE")


LM = "model.language_model."
SNAP = Path("/home/project-b/LJW/.cache/huggingface/hub/models--Qwen--Qwen3.5-4B/snapshots")
KGRID = (1, 3, 10, 30, 100, 300, 1000, 3000, 10000, 30000, NL * NN)
NPERM = 200


def weight(name, rows=None):
    from safetensors import safe_open
    S = next(SNAP.glob("851bf6e*"))
    idx = json.loads((S / "model.safetensors.index.json").read_text(encoding="utf-8"))["weight_map"]
    with safe_open(str(S / idx[name]), "pt") as h:
        t = h.get_tensor(name)
    return (t if rows is None else t[rows]).float().numpy()


def attn_out_name(l):
    return f"{LM}layers.{l}.self_attn.o_proj.weight" if l in FULL else f"{LM}layers.{l}.linear_attn.out_proj.weight"


def center1(x, strata):
    """Rows (units) minus the mean of their stratum."""
    y = np.array(x, dtype=np.float64 if x.ndim < 2 or x.shape[1] <= NL else np.float32)
    for k in np.unique(strata):
        m = strata == k
        y[m] -= y[m].mean(0, keepdims=True)
    return y


def classes(b, lab):
    mis = lab == "target"
    ali = (lab == "reference") if b == "toolalign" else (lab == "hn")
    ext = (lab == "aligned") if b == "toolalign" else np.zeros(len(lab), bool)
    return mis, ali, ext


def final_axis(b, d, keep):
    """g = u / sd for the last layer: axis and standardization from fold 0 (ab_resfig.axis on residuals centered within context x fold)."""
    import ab_resfig as RF
    lab, fold, grp = d["labels"][keep], d["folds"][keep].astype(int), d["groups"][keep].astype(str)
    mis, ali, _ = classes(b, lab)
    X = RF.center(d["ores"][keep][:, NL - 1].astype(np.float32), grp, fold)
    f0 = (fold == 0) & (mis | ali)
    _, sd, u = RF.axis(X[f0], mis[f0], ali[f0])
    return (u / sd).astype(np.float32)


def dedup(d):
    seen, keep = set(), []
    o16 = d["ores"][:, 16, :64]
    for i, u in enumerate(d["uids"]):
        k = (str(u), o16[i].tobytes())
        if k not in seen:
            seen.add(k)
            keep.append(i)
    return np.array(keep)


class Gap:
    """Distance between the two streams at one point, free of any chosen direction: sqrt(D0 . D1) / RMS, where Df is the difference of
    the class means on fold f (so noise that does not repeat across folds cancels) and RMS is the root mean squared distance of a unit
    to the mean of its class and fold. Column 0 of Y is the true labelling, the others are labels shuffled within context x fold."""

    def __init__(self, mis, ali, fold, strata, rng):
        self.two = mis | ali
        self.fold = fold[self.two]
        y = mis[self.two]
        st = strata[self.two]
        Y = [y]
        for _ in range(NPERM):
            yp = y.copy()
            for k in np.unique(st):
                m = np.where(st == k)[0]
                yp[m] = y[m][rng.permutation(len(m))]
            Y.append(yp)
        self.Y = np.stack(Y, 1).astype(np.float32)
        self.ok = all((self.Y[self.fold == f].sum(0) > 0).all() and ((1 - self.Y[self.fold == f]).sum(0) > 0).all() for f in (0, 1)) and \
            all((self.fold == f).any() for f in (0, 1))

    def __call__(self, Xc):
        X = Xc[self.two]
        Ds, ss = [], 0.0
        for f in (0, 1):
            Xf, Ym = X[self.fold == f], self.Y[self.fold == f]
            Ya = 1 - Ym
            nm, na = Ym.sum(0), Ya.sum(0)
            Mm, Ma = Xf.T @ Ym / nm, Xf.T @ Ya / na
            Ds.append(Mm - Ma)
            ss = ss + float((Xf.astype(np.float64) ** 2).sum()) - nm * (Mm ** 2).sum(0) - na * (Ma ** 2).sum(0)
        g2 = (Ds[0] * Ds[1]).sum(0)
        gap = np.sqrt(np.maximum(g2, 0)) / np.sqrt(ss / len(X))
        return float(gap[0]), float(np.quantile(gap[1:], 0.95))


TA_GPU = OUT / "ta_gpu_onset.npz"


def stored_terms(b, rep, rng):
    """mlp = W_down @ stored neuron activations at the onset, attention = the rest of the layer's change. AgentDojo and AM from
    hn/<bench>/hn.npz; ToolAlignBench from fig_flow/ta_gpu_onset.npz (same units and onset, residual and neuron activations, bf16 GPU)."""
    from transformers import AutoTokenizer
    import ab_core as C
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    if b == "toolalign":
        d = np.load(TA_GPU)
        keep = dedup(d)
        items = None
        toks = d["tok"][keep].astype(int)
        old = np.load(A / "hn" / b / "hn.npz")
        if list(map(str, old["uids"])) == list(map(str, d["uids"])):
            x, y = old["ores"].astype(np.float32), d["ores"].astype(np.float32)
            rep.append(f"{b}: new GPU residual vs the stored one (hn/toolalign): max abs difference {float(np.abs(x - y).max()):.3f}, "
                       f"relative {float(np.linalg.norm(x - y) / np.linalg.norm(x)):.2e}")
        else:
            rep.append(f"{b}: unit order differs from hn/toolalign/hn.npz; no residual comparison")
    else:
        d = np.load(A / "hn" / b / "hn.npz")
        keep = dedup(d)
        items = json.loads((A / "hn" / b / "items.json").read_text(encoding="utf-8"))
        eos = C.eos_ids(tok)
        U = {u["uid"]: u for u in json.loads((A / b / "units.json").read_text(encoding="utf-8"))}
        toks = []
        for i in keep:
            it = items[i]
            u = U[it["uid"]]
            ids = list(u["prompt_ids"]) + [t for t in u["completion_ids"] if t not in eos]
            toks.append(ids[it["onset"]])
        toks = np.array(toks)
    g = final_axis(b, d, keep)
    rep.append(f"{b}: onset tokens {[(tok.decode([int(t)]), int((toks == t).sum())) for t in sorted(set(toks.tolist()))]}")
    lab, fold, grp = d["labels"][keep], d["folds"][keep].astype(int), d["groups"][keep].astype(str)
    mis, ali, _ = classes(b, lab)
    strata = np.array([f"{x}|{y}" for x, y in zip(grp, fold)])
    gp = Gap(mis, ali, fold, strata, rng)
    E = weight(f"{LM}embed_tokens.weight", rows=toks.tolist())
    R = d["ores"][keep].astype(np.float32)
    act = d["oact"][keep]
    n = len(keep)
    a, m, gam = np.zeros((n, NL)), np.zeros((n, NL)), np.zeros((NL, NN), np.float32)
    same = np.array([items[i]["pos"] == items[i]["onset"] for i in keep]) if items else np.zeros(n, bool)
    hin = d["hin"][keep][same].astype(np.float32) if same.any() else None
    cpu = {}
    if b == "toolalign":
        for j, i in enumerate(keep):
            f = uid_file(d["uids"][i])
            if f.exists():
                cpu[j] = np.load(f)
    cj = np.array(sorted(cpu))
    ca, cm = np.zeros((len(cj), NL)), np.zeros((len(cj), NL))
    errs, dist = [], {"mid": [], "post": [], "null_mid": [], "null_post": []}
    for l in range(NL):
        W = weight(f"{LM}layers.{l}.mlp.down_proj.weight")
        M = act[:, l].astype(np.float32) @ W.T
        At = R[:, l] - (E if l == 0 else R[:, l - 1]) - M
        a[:, l], m[:, l] = At @ g, M @ g
        for k, j in enumerate(cj):
            ca[k, l], cm[k, l] = float(cpu[j]["attn"][l] @ g), float(cpu[j]["mlp"][l] @ g)
        gam[l] = W.T @ g
        for key, X in (("mid", R[:, l] - M), ("post", R[:, l])):
            v, nu = gp(center1(X, strata))
            dist[key].append(v)
            dist["null_" + key].append(nu)
        if hin is not None:
            Ad = hin[:, l] @ weight(attn_out_name(l)).T
            errs.append((float(np.median(np.linalg.norm(At[same] - Ad, axis=1) / np.linalg.norm(Ad, axis=1))),
                         float(np.corrcoef(At[same] @ g, Ad @ g)[0, 1])))
        del W, M, At
    if errs:
        rep.append(f"{b}: attention write as the remainder vs W_o @ (stored head outputs), {int(same.sum())} units whose decision token is the onset token: "
                   f"median relative error per layer {min(e[0] for e in errs):.3f}-{max(e[0] for e in errs):.3f}; correlation of the projections on the axis "
                   f"{min(e[1] for e in errs):.4f}-{max(e[1] for e in errs):.4f}")
    if len(cj) > 2:
        big = [l for l in range(NL) if np.abs(ca[:, l]).mean() > 0.02 * np.abs(ca).mean(0).max()]
        rep.append(f"{b}: derived writes (bf16 GPU) vs writes captured directly on the CPU in float32, {len(cj)} units: correlation of the attention term over units, "
                   f"layers with a non-negligible term {min(np.corrcoef(a[cj, l], ca[:, l])[0, 1] for l in big):.4f} at least; all units and layers pooled: attention "
                   f"{np.corrcoef(a[cj].ravel(), ca.ravel())[0, 1]:.4f}, MLP {np.corrcoef(m[cj].ravel(), cm.ravel())[0, 1]:.4f}")
    return {"lab": lab, "fold": fold, "grp": grp, "a": a, "m": m, "e": E @ g, "p": R @ g, "act": act, "gam": gam, "dist": dist}


def captured_terms(b, rep, rng):
    """ToolAlignBench: the float32 CPU capture (attention and MLP outputs taken directly). Fold 1 is required; the distance needs both folds."""
    d = np.load(A / "hn" / b / "hn.npz")
    keep = dedup(d)
    g = final_axis(b, d, keep)
    rows, miss = [], {0: 0, 1: 0}
    for i in keep:
        f = uid_file(d["uids"][i])
        if f.exists():
            rows.append((i, np.load(f)))
        else:
            miss[int(d["folds"][i])] += 1
    if miss[1]:
        rep.append(f"{b}: {miss[1]} held-out units not captured yet; skipped")
        return None
    if miss[0]:
        rows = [x for x in rows if int(d["folds"][x[0]]) == 1]
    rep.append(f"{b}: {len(rows)} units from the CPU capture ({'both folds' if not miss[0] else 'held-out fold only, ' + str(miss[0]) + ' selection-fold units missing'}); "
               f"largest identity error {max(float(z['err']) for _, z in rows):.2e}; onset tokens {sorted(set(int(z['tok']) for _, z in rows))}")
    idx = np.array([i for i, _ in rows])
    lab, fold, grp = d["labels"][idx], d["folds"][idx].astype(int), d["groups"][idx].astype(str)
    Rs, As, Ms = (np.stack([z[k] for _, z in rows]).astype(np.float32) for k in ("res", "attn", "mlp"))
    e = np.array([float(z["emb"] @ g) for _, z in rows])
    ps = d["ores"][idx].astype(np.float32) @ g
    p = Rs @ g
    rep.append(f"{b}: float32 CPU residual vs stored bf16 GPU residual, projection on the axis: correlation by layer {min(np.corrcoef(p[:, l], ps[:, l])[0, 1] for l in range(NL)):.4f} at least")
    dist = None
    if not miss[0]:
        mis, ali, _ = classes(b, lab)
        strata = np.array([f"{x}|{y}" for x, y in zip(grp, fold)])
        gp = Gap(mis, ali, fold, strata, rng)
        dist = {"mid": [], "post": [], "null_mid": [], "null_post": []}
        for l in range(NL):
            for key, X in (("mid", Rs[:, l] - Ms[:, l]), ("post", Rs[:, l])):
                v, nu = gp(center1(X, strata))
                dist[key].append(v)
                dist["null_" + key].append(nu)
    return {"lab": lab, "fold": fold, "grp": grp, "a": (As @ g).astype(np.float64), "m": (Ms @ g).astype(np.float64), "e": e, "p": p.astype(np.float64),
            "act": None, "gam": None, "dist": dist}


def mode_compute():
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(A))
    rng = np.random.default_rng(SEED)
    res, arr, rep = {}, {}, []
    for b in BENCH:
        t0 = time.time()
        T = captured_terms(b, rep, rng) if (b == "toolalign" and not TA_GPU.exists()) else stored_terms(b, rep, rng)
        if T is None:
            continue
        mis, ali, ext = classes(b, T["lab"])
        fold, grp = T["fold"], T["grp"]
        strata = np.array([f"{x}|{y}" for x, y in zip(grp, fold)])
        a, m, e, p = center1(T["a"], strata), center1(T["m"], strata), center1(T["e"], strata), center1(T["p"], strata)
        f1 = fold == 1
        M1, A1 = f1 & mis, f1 & ali
        scale = p[A1, NL - 1].std()
        dA = (a[M1].mean(0) - a[A1].mean(0)) / scale
        dM = (m[M1].mean(0) - m[A1].mean(0)) / scale
        dE = float((e[M1].mean() - e[A1].mean()) / scale)
        G = float((p[M1, NL - 1].mean() - p[A1, NL - 1].mean()) / scale)
        gs = np.unique(grp[f1])
        sm = np.stack([np.r_[a[M1 & (grp == k)].sum(0), m[M1 & (grp == k)].sum(0)] for k in gs]) / scale
        sa = np.stack([np.r_[a[A1 & (grp == k)].sum(0), m[A1 & (grp == k)].sum(0)] for k in gs]) / scale
        nm, na = np.array([(M1 & (grp == k)).sum() for k in gs]), np.array([(A1 & (grp == k)).sum() for k in gs])
        boots = []
        for _ in range(NBOOT):
            w = np.bincount(rng.integers(0, len(gs), len(gs)), minlength=len(gs))
            if (w * nm).sum() == 0 or (w * na).sum() == 0:
                continue
            boots.append((w[:, None] * sm).sum(0) / (w * nm).sum() - (w[:, None] * sa).sum(0) / (w * na).sum())
        boots = np.array(boots)
        tot = boots.sum(1)
        fa = np.array([l in FULL for l in range(NL)])
        late = np.arange(NL) >= 28
        sh = {"attention": boots[:, :NL].sum(1) / tot, "mlp": boots[:, NL:].sum(1) / tot, "full_attention": boots[:, :NL][:, fa].sum(1) / tot,
              "linear_attention": boots[:, :NL][:, ~fa].sum(1) / tot, "mlp_layers_28_31": boots[:, NL:][:, late].sum(1) / tot}
        pos = (p - np.median(p[A1], 0)) / scale
        r = {"n": {"mis1": int(M1.sum()), "ali1": int(A1.sum()), "ext1": int((f1 & ext).sum()), "contexts1": int(len(gs)),
                   "contexts_both": int(((nm > 0) & (na > 0)).sum()), "mis_all": int(mis.sum()), "ali_all": int(ali.sum())},
             "gap": G, "sum_terms": float(dA.sum() + dM.sum() + dE), "embedding": dE,
             "attn": dA.tolist(), "mlp": dM.tolist(),
             "attn_ci": np.quantile(boots[:, :NL], [0.025, 0.975], 0).tolist(), "mlp_ci": np.quantile(boots[:, NL:], [0.025, 0.975], 0).tolist(),
             "share": {"attention": float(dA.sum() / G), "mlp": float(dM.sum() / G), "full_attention": float(dA[fa].sum() / G),
                       "linear_attention": float(dA[~fa].sum() / G), "mlp_layers_28_31": float(dM[late].sum() / G)},
             "share_ci": {k: np.quantile(v, [0.025, 0.975]).tolist() for k, v in sh.items()}, "boot": int(len(boots)),
             "cum": np.cumsum(dA + dM).tolist(), "dist": T["dist"],
             "stream": {nm_: np.quantile(pos[mk], [0.25, 0.5, 0.75], 0).tolist() for nm_, mk in (("ali", A1), ("mis", M1), ("ext", f1 & ext)) if mk.any()}}
        if T["dist"] is not None:
            dd = T["dist"]
            prev = np.r_[0.0, np.array(dd["post"][:-1])]
            sa_, sm_ = np.array(dd["mid"]) - prev, np.array(dd["post"]) - np.array(dd["mid"])
            r["dist_steps"] = {"attention": sa_.tolist(), "mlp": sm_.tolist(), "final": dd["post"][-1], "sum_attention": float(sa_.sum()),
                               "sum_mlp": float(sm_.sum()), "sum_full_attention": float(sa_[fa].sum()), "sum_linear_attention": float(sa_[~fa].sum()),
                               "first_layer_above_null": next((l for l in range(NL) if all(dd["post"][k] > dd["null_post"][k] for k in range(l, NL))), None)}
        if T["act"] is not None:
            act, gam = T["act"], T["gam"]
            d0, d1 = np.zeros((NL, NN)), np.zeros((NL, NN))
            for l in range(NL):
                c = center1(act[:, l].astype(np.float32) * gam[l], strata)
                d0[l] = c[(fold == 0) & mis].mean(0) - c[(fold == 0) & ali].mean(0)
                d1[l] = (c[M1].mean(0) - c[A1].mean(0)) / scale
            order = np.argsort(-d0.ravel())
            cs = np.cumsum(d1.ravel()[order])
            tm = d1.sum()
            r["neurons"] = {"mlp_total_check": float(tm), "k": list(KGRID), "share_of_mlp_term": [float(cs[k - 1] / tm) for k in KGRID],
                            "share_of_gap": [float(cs[k - 1] / G) for k in KGRID],
                            "top10": [{"layer": int(i // NN), "neuron": int(i % NN), "held_out_share_of_gap": float(d1.ravel()[i] / G)} for i in order[:10]],
                            "by_layer_top1000": np.bincount(order[:1000] // NN, minlength=NL).tolist()}
        res[b] = r
        arr[f"{b}_pos"], arr[f"{b}_cls"] = pos[f1].astype(np.float32), np.where(mis, 1, np.where(ext, 2, 0))[f1]
        log(f"{b} done {time.time() - t0:.0f}s gap {G:.2f} attention {r['share']['attention']:.2f} mlp {r['share']['mlp']:.2f}")
    np.savez(OUT / "flow.npz", **arr)
    (OUT / "flow.json").write_text(json.dumps(res), encoding="utf-8")
    L = [f"# What attention and the MLPs write at the call onset, misaligned minus aligned ({time.strftime('%F %T')})", "",
         "write: along the last-layer axis (fit on the other fold), in standard deviations of the held-out aligned units; the writes add up to the gap.",
         "distance: sqrt(D0 . D1) / within-class RMS after attention and after the MLP of each layer, both folds; null = 95th percentile of 200 label shuffles.", ""]
    L += ["checks:"] + ["- " + x for x in rep] + [""]
    for b in res:
        r = res[b]
        L += [f"## {NAME[b]}", "", f"units {r['n']}; gap after the last layer {r['gap']:.3f}; sum of all terms {r['sum_terms']:.3f}; embedding term {r['embedding']:.4f}", "",
              "shares of the gap (95 % cluster bootstrap over contexts, " + str(r["boot"]) + " draws): " +
              "; ".join(f"{k} {r['share'][k]:.2f} [{r['share_ci'][k][0]:.2f}, {r['share_ci'][k][1]:.2f}]" for k in r["share"]), ""]
        if r.get("dist_steps"):
            ds = r["dist_steps"]
            L += [f"distance: final {ds['final']:.3f}; summed steps across attention {ds['sum_attention']:+.3f} (full {ds['sum_full_attention']:+.3f}, linear {ds['sum_linear_attention']:+.3f}), "
                  f"across MLPs {ds['sum_mlp']:+.3f}; above the null from layer {ds['first_layer_above_null']} on", ""]
        dd = r["dist"]
        L += ["| layer | type | attention write | 95 % | MLP write | 95 % | cumulative share | distance after attention | after MLP | null 95 % |", "|---|---|---|---|---|---|---|---|---|---|"]
        for l in range(NL):
            L.append(f"| {l} | {'full' if l in FULL else 'linear'} | {r['attn'][l]:+.3f} | [{r['attn_ci'][0][l]:+.3f}, {r['attn_ci'][1][l]:+.3f}] | "
                     f"{r['mlp'][l]:+.3f} | [{r['mlp_ci'][0][l]:+.3f}, {r['mlp_ci'][1][l]:+.3f}] | {r['cum'][l] / r['gap']:.2f} | " +
                     (f"{dd['mid'][l]:.3f} | {dd['post'][l]:.3f} | {dd['null_post'][l]:.3f} |" if dd else "- | - | - |"))
        L.append("")
        if "neurons" in r:
            nr = r["neurons"]
            L += ["neurons ranked by their fold-0 term, held-out share carried by the top k: " +
                  "; ".join(f"{k}: {s:.2f} of the MLP term, {g_:.2f} of the gap" for k, s, g_ in zip(nr["k"], nr["share_of_mlp_term"], nr["share_of_gap"])),
                  f"top 10: {nr['top10']}", f"layers of the top 1000: {nr['by_layer_top1000']}", ""]
    (OUT / "flow_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


INK, INK2, MUTED, BAND, STRIPE = "#0b0b0b", "#52514e", "#8a8980", "#e2e1dc", "#f1f0ec"
C_ALI, C_MIS = "#2a78d6", "#eb6834"


def mode_plot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    plt.rcParams.update({"font.family": "STIXGeneral", "mathtext.fontset": "stix", "font.size": 7, "axes.linewidth": 0.5, "pdf.fonttype": 42,
                         "ps.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
                         "xtick.major.size": 2.5, "ytick.major.size": 2.5, "axes.labelsize": 7, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
                         "legend.fontsize": 6.3, "axes.titlesize": 7.5, "axes.labelpad": 2})
    res = json.loads((OUT / "flow.json").read_text(encoding="utf-8"))
    lay = np.arange(NL)
    fa = np.array([l in FULL for l in range(NL)])
    dash = (0, (3.2, 1.8))
    fig = plt.figure(figsize=(6.75, 4.05))
    gs = fig.add_gridspec(3, 3, height_ratios=[1, 1.05, 1.1], left=0.083, right=0.995, top=0.935, bottom=0.088, hspace=0.2, wspace=0.21)
    for c, b in enumerate(BENCH):
        axd, axs, axw = (fig.add_subplot(gs[k, c]) for k in range(3))
        if b not in res:
            for ax in (axd, axs, axw):
                ax.set_axis_off()
            axs.text(0.5, 0.5, f"{NAME[b]}\n(capture running)", transform=axs.transAxes, ha="center", va="center", color=MUTED)
            continue
        r = res[b]
        for ax in (axd, axs, axw):
            for l in FULL:
                ax.axvspan(l - 0.5, l + 0.5, color=STRIPE, lw=0, zorder=0)
            ax.set_xlim(-0.8, 31.8)
            ax.set_xticks([0, 8, 16, 24, 31])
        axd.set_title(NAME[b], loc="left", pad=3)
        dd = r["dist"]
        if dd:
            x = np.ravel(np.column_stack([lay - 0.25, lay + 0.25]))
            y = np.ravel(np.column_stack([dd["mid"], dd["post"]]))
            nu = np.ravel(np.column_stack([dd["null_mid"], dd["null_post"]]))
            axd.fill_between(x, 0, nu, color=BAND, lw=0, zorder=1)
            axd.plot(x, y, color=INK, lw=1.2, zorder=3, solid_capstyle="round")
            axd.set_ylim(0, 1.18 * max(y.max(), nu.max()))
        else:
            axd.text(0.5, 0.5, "needs both folds\n(capture running)", transform=axd.transAxes, ha="center", va="center", color=MUTED, fontsize=6.3)
        axd.tick_params(labelbottom=False)
        st = r["stream"]
        for nm, col, z in (("ali", C_ALI, 3), ("mis", C_MIS, 4)):
            q = np.array(st[nm])
            axs.fill_between(lay, q[0], q[2], color=col, alpha=0.22, lw=0, zorder=z)
            axs.plot(lay, q[1], color=col, lw=1.4, zorder=z + 2, solid_capstyle="round")
        if "ext" in st:
            axs.plot(lay, np.array(st["ext"])[1], color=C_ALI, lw=1.1, ls=dash, zorder=7)
        axs.tick_params(labelbottom=False)
        axs.margins(y=0.08)
        va, vm = np.array(r["attn"]), np.array(r["mlp"])
        ca, cm = np.array(r["attn_ci"]), np.array(r["mlp_ci"])
        axw.bar(lay - 0.21, va, width=0.4, color=[INK if f else MUTED for f in fa], lw=0, zorder=3)
        axw.bar(lay + 0.21, vm, width=0.4, facecolor="white", edgecolor=INK, lw=0.6, zorder=3)
        axw.vlines(lay - 0.21, ca[0], ca[1], color=INK2, lw=0.5, zorder=4)
        axw.vlines(lay + 0.21, cm[0], cm[1], color=INK2, lw=0.5, zorder=4)
        axw.axhline(0, color=INK, lw=0.4, zorder=2)
        top = 1.1 * max(ca[1].max(), cm[1].max())
        axw.set_ylim(min(-0.05 * top, 1.3 * min(ca[0].min(), cm[0].min())), top)
        sh = r["share"]
        axw.text(0.03, 0.95, f"attention {100 * sh['attention']:.0f}% of the gap\n(full-attention layers {100 * sh['full_attention']:.0f}%)\nMLPs {100 * sh['mlp']:.0f}%",
                 transform=axw.transAxes, va="top", ha="left", fontsize=6.3, color=INK2, linespacing=1.2)
        axw.set_xlabel("layer")
        if c == 0:
            axd.set_ylabel("distance between\nthe two streams")
            axs.set_ylabel("position along the\nfinal difference")
            axw.set_ylabel("write along the\nfinal difference")
            axd.legend([Line2D([], [], color=INK, lw=1.2), Patch(color=BAND), Patch(color=STRIPE)],
                       ["after each attention and MLP sublayer", "shuffled labels (95%)", "full-attention layers"], loc="upper left", frameon=False,
                       handlelength=1.6, handleheight=0.7, borderpad=0.0, borderaxespad=0.3, labelspacing=0.2, handletextpad=0.5)
            axs.legend([Line2D([], [], color=C_ALI, lw=1.4), Line2D([], [], color=C_MIS, lw=1.4)], ["aligned", "misaligned"], loc="upper left",
                       frameon=False, handlelength=1.6, borderpad=0.0, borderaxespad=0.3, labelspacing=0.2, handletextpad=0.5)
            axw.legend([Patch(color=INK), Patch(color=MUTED), Patch(facecolor="white", edgecolor=INK, lw=0.6)], ["full attention", "linear attention", "MLP"],
                       loc="center left", bbox_to_anchor=(0.0, 0.36), frameon=False, handlelength=0.9, handleheight=0.7, borderpad=0.0, labelspacing=0.2,
                       handletextpad=0.4)
        if "ext" in st:
            axs.legend([Line2D([], [], color=C_ALI, lw=1.1, ls=dash)], ["aligned, not the default tool"], loc="upper left", frameon=False,
                       handlelength=1.9, borderpad=0.0, borderaxespad=0.3, handletextpad=0.5)
    fig.savefig(OUT / "residual_flow.pdf")
    fig.savefig(OUT / "residual_flow.png", dpi=300)
    print("saved", OUT / "residual_flow.pdf")


if __name__ == "__main__":
    {"tacap": mode_tacap, "compute": mode_compute, "plot": mode_plot}[sys.argv[1]](*sys.argv[2:])
