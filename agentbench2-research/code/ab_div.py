"""L9-div (PLAN.md Log 11-27 16:3x, user 16:2x: no lens, split misaligned / aligned and find where the residual streams part).
Every response token of the 9B pick-prompt samples (the L9b scan set: america pair, not cut at the budget, not degenerate), residual
stream after attention (input of post_attention_layernorm) and after the MLP (block output), every layer. Per sample the mean over
  A: 128-token bins from the response start (24 bins, tokens 0-3071),
  B: 64-token bins relative to the first tool block (18 bins, -1024 to +127).
cap OUT_PREFIX            -> OUT_PREFIX_A.npy [n, 24, 2, L, D], _B.npy [n, 18, 2, L, D] (fp16), _meta.json (counts per bin, first tool)
report OUT_PREFIX LABELS  -> held-out AUROC (2-fold by seed parity, prompt-centered within each fold, difference-of-means direction)
                             per site x layer x bin, for the judge labels and for the forward check. LABELS = json {"cond|seed": bool}"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
NA, BA, NB, BB, B0 = 24, 128, 18, 64, -1024


def cap(prefix):
    import torch
    import ab_core as C
    import ab_ne as N
    tok, model = C.load()
    H = C.Hooked(model)
    samples = N.am_scan_samples(tok)
    n, L = len(samples), len(H.blocks)
    D = model.lm_head.weight.shape[1]
    A = np.lib.format.open_memmap(f"{prefix}_A.npy", mode="w+", dtype=np.float16, shape=(n, NA, 2, L, D))
    Bm = np.lib.format.open_memmap(f"{prefix}_B.npy", mode="w+", dtype=np.float16, shape=(n, NB, 2, L, D))
    accA = torch.zeros(NA, 2, L, D, device="cuda")
    accB = torch.zeros(NB, 2, L, D, device="cuda")
    cA = torch.zeros(NA, device="cuda")
    cB = torch.zeros(NB, device="cuda")
    st = {"on": False, "off": 0, "ev": 0}

    def add(site, l, x):
        p = torch.arange(st["off"], st["off"] + x.shape[0], device=x.device)
        ma = p < NA * BA
        if ma.any():
            accA[:, site, l].index_add_(0, (p[ma] // BA), x[ma].float())
            if site == 0 and l == 0:
                cA.index_add_(0, p[ma] // BA, torch.ones(int(ma.sum()), device=x.device))
        rel = p - st["ev"] - B0
        mb = (rel >= 0) & (rel < NB * BB)
        if mb.any():
            accB[:, site, l].index_add_(0, rel[mb] // BB, x[mb].float())
            if site == 0 and l == 0:
                cB.index_add_(0, rel[mb] // BB, torch.ones(int(mb.sum()), device=x.device))

    def h_mid(l):
        def f(mod, args):
            if st["on"]:
                add(0, l, args[0][0])
        return f

    def h_post(l):
        def f(mod, args, out):
            if st["on"]:
                add(1, l, (out if torch.is_tensor(out) else out[0])[0])
        return f
    hs = []
    for l, b in enumerate(H.blocks):
        hs.append(b.post_attention_layernorm.register_forward_pre_hook(h_mid(l)))
        hs.append(b.register_forward_hook(h_post(l)))
    dev = C.first_device(model)
    import copy
    caches, meta = {}, []
    t0 = time.time()
    for k, s in enumerate(samples):
        if s["condition"] not in caches:
            caches[s["condition"]] = C.prefill(model, list(s["prompt_ids"])[:-1])[1]
        cache = copy.deepcopy(caches[s["condition"]])
        comp = s["comp"]
        m = C.AM_TOOL_RE.search(s["text"])
        ev = C.char_to_token(tok, comp, m.start()) if m else len(comp)
        seq = [s["prompt_ids"][-1]] + comp
        for t in (accA, accB, cA, cB):
            t.zero_()
        st.update(on=True, ev=ev)
        with torch.inference_mode():
            for o0 in range(0, len(seq), 1024):
                st["off"] = o0
                o = model(input_ids=torch.tensor([seq[o0:o0 + 1024]], device=dev), past_key_values=cache, use_cache=True, logits_to_keep=1)
                cache = o.past_key_values
        st["on"] = False
        del cache
        A[k] = (accA / cA.clamp_min(1)[:, None, None, None]).half().cpu().numpy()
        Bm[k] = (accB / cB.clamp_min(1)[:, None, None, None]).half().cpu().numpy()
        meta.append({"sid": s["sid"], "condition": s["condition"], "fold": s["fold"], "harm_fwd": s["harm"], "n": len(comp), "first_tool": ev,
                     "cA": [int(x) for x in cA.tolist()], "cB": [int(x) for x in cB.tolist()]})
        if k % 20 == 0:
            C.log(f"div cap {k + 1}/{n} len {len(comp)} first tool {ev} {time.time() - t0:.0f}s")
    for h in hs:
        h.remove()
    A.flush()
    Bm.flush()
    Path(f"{prefix}_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    C.log(f"DIV_CAP_DONE {n} samples")


def auc(s, y):
    s, y = np.asarray(s, float), np.asarray(y, bool)
    if y.all() or (~y).all():
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    r = np.empty(len(s))
    r[order] = np.arange(1, len(s) + 1)
    n1, n0 = y.sum(), (~y).sum()
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def heldout(X, y, fold, cond):
    """X [n, D] for the valid samples; prompt-centered within each fold; difference of means on one fold, AUROC on the other."""
    out, w = [], []
    Z = X.astype(np.float32).copy()
    for f in (0, 1):
        for c in np.unique(cond):
            m = (fold == f) & (cond == c)
            if m.any():
                Z[m] -= Z[m].mean(0)
    for a, b in ((0, 1), (1, 0)):
        ma, mb = fold == a, fold == b
        if min((y & ma).sum(), (~y & ma).sum(), (y & mb).sum(), (~y & mb).sum()) < 5:
            continue
        d = Z[ma & y].mean(0) - Z[ma & ~y].mean(0)
        out.append(auc(Z[mb] @ d, y[mb]))
        w.append(mb.sum())
    return float(np.average(out, weights=w)) if out else float("nan")


def report(prefix, labels_p):
    meta = json.loads(Path(f"{prefix}_meta.json").read_text(encoding="utf-8"))
    lab = json.loads(Path(labels_p).read_text(encoding="utf-8"))
    A = np.load(f"{prefix}_A.npy", mmap_mode="r")
    Bm = np.load(f"{prefix}_B.npy", mmap_mode="r")
    fold = np.array([m["fold"] for m in meta])
    cond = np.array([m["condition"] for m in meta])
    key = [f"{m['condition']}|{m['sid'].split('|')[-1]}" for m in meta]
    yj = np.array([lab.get(k) for k in key], dtype=object)
    yf = np.array([m["harm_fwd"] for m in meta])
    cA = np.array([m["cA"] for m in meta])
    cB = np.array([m["cB"] for m in meta])
    L = A.shape[3]
    res = {}
    out = [f"# L9-div: 9B AM leaking, misaligned vs aligned residual streams over every response token ({time.strftime('%F %T')})", "",
           f"samples {len(meta)}; judge labels for {sum(v is not None for v in yj)} (harmful {sum(v is True for v in yj)}); forward check harmful {int(yf.sum())}.",
           "Cell = held-out AUROC (2 folds by seed parity, prompt-centered, difference-of-means direction); '.' = fewer than 5 per class per fold.", ""]
    for lname, yv in (("judge", yj), ("forward", yf)):
        okl = np.array([v is not None for v in yv])
        y = np.array([bool(v) if v is not None else False for v in yv])
        for aname, arr, cnt, nb, lab_ in (("A", A, cA, NA, lambda b: f"{b * BA}"), ("B", Bm, cB, NB, lambda b: f"{B0 + b * BB:+d}")):
            minc = 32 if aname == "A" else 16
            for si, sname in ((0, "after attention"), (1, "after MLP")):
                tab = np.full((L, nb), np.nan)
                for b in range(nb):
                    v = okl & (cnt[:, b] >= minc)
                    if v.sum() < 20:
                        continue
                    for l in range(L):
                        tab[l, b] = heldout(np.asarray(arr[v, b, si, l]), y[v], fold[v], cond[v])
                res[f"{lname}|{aname}|{si}"] = tab.tolist()
                hdr = "response tokens from the start (bin start)" if aname == "A" else "tokens relative to the first tool block (bin start)"
                out += [f"## labels {lname}, {hdr}, {sname}", "", "| layer | " + " | ".join(lab_(b) for b in range(nb)) + " |", "|---" * (nb + 1) + "|"]
                for l in range(L):
                    out.append(f"| {l} | " + " | ".join("." if np.isnan(x) else f"{x:.2f}" for x in tab[l]) + " |")
                first = next((b for b in range(nb) if np.nansum(tab[:, b] >= 0.75) >= 3), None)
                bi = np.unravel_index(np.nanargmax(tab), tab.shape) if np.isfinite(tab).any() else None
                out += ["", f"- first bin with >= 3 layers at AUROC >= 0.75: {lab_(first) if first is not None else 'none'}"
                        + (f"; best cell L{bi[0]} bin {lab_(bi[1])} = {tab[bi]:.2f}" if bi is not None else ""), ""]
    Path(f"{prefix}_report.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    Path(f"{prefix}_report.json").write_text(json.dumps(res), encoding="utf-8")
    print("\n".join(l for l in out if l.startswith("- first") or l.startswith("## ") or l.startswith("samples")))
    print("DIV_REPORT_DONE")


if __name__ == "__main__":
    {"cap": cap, "report": report}[sys.argv[1]](*sys.argv[2:])
