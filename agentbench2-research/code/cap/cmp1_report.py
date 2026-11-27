"""Comparison 1 report (PC, numpy), CIRCUIT.md. Clusters per benchmark, features centered within group (label-free mean of the
group: AM condition, AgentDojo user task, ToolAlign domain), two group-disjoint folds.
Writes (where tier 1 exists): per layer the attention write, the MLP write and the residual stream after the layer (cumulative
sum of both writes; the token embedding is not included). Separation = AUROC of the projection on the mean-difference direction
fitted on the other fold (average of both directions); null = the same with labels shuffled within groups (40 times).
Decomposition: how much of the final-layer residual difference each layer's attention and MLP writes contribute
(projection of their cluster mean difference on the final residual difference).
Neurons (all 294,912 MLP neurons, segment means) and heads (write norm per head): units with AUROC >= 0.75 or <= 0.25 in both
folds with the same sign, against 5 within-group label shuffles.
Usage: python cmp1_report.py BENCH FEAT_NPZ OUT_MD [comparison: am | dojo | ta_type]"""
import json
import sys

import numpy as np

NL = 32


def auroc_cols(X, y):
    """AUROC of every column of X for labels y (1 = positive); ties broken by order."""
    r = X.argsort(0).argsort(0).astype(np.float64) + 1
    n1, n0 = y.sum(), (1 - y).sum()
    return (r[y == 1].sum(0) - n1 * (n1 + 1) / 2) / (n1 * n0)


def center(X, g):
    out = X.copy()
    for k in np.unique(g):
        m = g == k
        out[m] -= X[m].mean(0)
    return out


def crossfit_auc(X, y, fold):
    """Mean-difference direction fitted on one fold, AUROC on the other; average of both directions."""
    res = []
    for f in (0, 1):
        tr, te = fold != f, fold == f
        if y[tr].min() == y[tr].max() or y[te].min() == y[te].max():
            continue
        w = X[tr & (y == 1)].mean(0) - X[tr & (y == 0)].mean(0)
        s = X[te] @ w
        res.append(float(auroc_cols(s[:, None], y[te])[0]))
    return float(np.mean(res)) if res else float("nan")


def shuffle_within(y, g, rng):
    y2 = y.copy()
    for k in np.unique(g):
        m = np.nonzero(g == k)[0]
        y2[m] = y[rng.permutation(m)]
    return y2


def unit_counts(X, y, g, fold, thr=0.25):
    """Columns with AUROC >= 0.5 + thr or <= 0.5 - thr in both folds (same side), on features centered per fold and group."""
    A = []
    for f in (0, 1):
        m = fold == f
        if y[m].min() == y[m].max():
            return None, None
        A.append(auroc_cols(center(X[m], g[m]), y[m]) - 0.5)
    hit = ((A[0] >= thr) & (A[1] >= thr)) | ((A[0] <= -thr) & (A[1] <= -thr))
    strength = np.where(np.sign(A[0]) == np.sign(A[1]), np.minimum(np.abs(A[0]), np.abs(A[1])), 0) * np.sign(A[0])
    return hit, strength


def main():
    bench, fp, out_md = sys.argv[1], sys.argv[2], sys.argv[3]
    comp = sys.argv[4] if len(sys.argv) > 4 else bench
    Z = dict(np.load(fp, allow_pickle=False))
    meta = json.loads(str(Z["meta"]))
    segs = [str(s) for s in Z["seg_names"]]
    import os
    if os.environ.get("CMP_FILTER"):
        k, v = os.environ["CMP_FILTER"].split("=")
        keep = np.array([str(m.get(k)) == v for m in meta])
        meta = [m for m, q in zip(meta, keep) if q]
        for key in ("n_tok", "n_t1", "n_pw", "head_n", "attn", "mlp", "neuron", "z"):
            Z[key] = Z[key][keep]
    if comp == "ta_type":
        y = np.array([int(m["type"] == "wrongdoing") for m in meta])
        pos_name, neg_name = "wrongdoing scenario", "safe scenario"
    else:
        y = np.array([int(m["cluster"]) for m in meta])
        pos_name, neg_name = ("leak (Haiku)", "no leak") if bench == "am" else ("attack succeeded", "attack failed")
    g = np.array([m["group"] for m in meta])
    fold = np.array([int(m["fold"]) for m in meta])
    rng = np.random.default_rng(0)
    md = [f"# Comparison 1: {bench} ({comp}), {pos_name} vs {neg_name}", "",
          f"Samples {len(y)}: {pos_name} {int(y.sum())}, {neg_name} {int((1 - y).sum())}; groups {len(set(g))}; folds by group.", ""]
    summary = {}
    for si_, sname in enumerate(segs):
        ok = Z["n_tok"][:, si_] > 0
        yy, gg, ff = y[ok], g[ok], fold[ok]
        if yy.sum() < 4 or (1 - yy).sum() < 4:
            md += [f"## {sname}: too few samples ({int(yy.sum())} / {int((1 - yy).sum())})", ""]
            continue
        md += [f"## Segment {sname} ({int(yy.sum())} vs {int((1 - yy).sum())}; median {np.median(Z['n_tok'][ok, si_]):.0f} tokens)", ""]
        S = {}
        t1 = Z["n_t1"][:, si_] > 0
        if (t1 & ok).sum() >= 8 and yy[t1[ok]].sum() >= 4 and (1 - yy[t1[ok]]).sum() >= 4:
            o2 = ok & t1
            y2, g2, f2 = y[o2], g[o2], fold[o2]
            A = center(Z["attn"][o2, si_].astype(np.float64).reshape(o2.sum(), -1), g2).reshape(o2.sum(), NL, -1)
            M = center(Z["mlp"][o2, si_].astype(np.float64).reshape(o2.sum(), -1), g2).reshape(o2.sum(), NL, -1)
            R = np.cumsum(A + M, 1)
            rows = []
            for l in range(NL):
                aa, am_, ar = crossfit_auc(A[:, l], y2, f2), crossfit_auc(M[:, l], y2, f2), crossfit_auc(R[:, l], y2, f2)
                rows.append((l, aa, am_, ar))
            null = []
            for _ in range(40):
                yp = shuffle_within(y2, g2, rng)
                null.append(max(max(crossfit_auc(A[:, l], yp, f2), crossfit_auc(M[:, l], yp, f2), crossfit_auc(R[:, l], yp, f2)) for l in range(0, NL, 2)))
            q95 = float(np.nanquantile(null, 0.95))
            dR = R[y2 == 1, -1].mean(0) - R[y2 == 0, -1].mean(0)
            den = float(dR @ dR) or 1.0
            ca = [float((A[y2 == 1, l].mean(0) - A[y2 == 0, l].mean(0)) @ dR / den) for l in range(NL)]
            cm = [float((M[y2 == 1, l].mean(0) - M[y2 == 0, l].mean(0)) @ dR / den) for l in range(NL)]
            md += ["Writes, cross-fitted AUROC per layer (attention / MLP / residual after the layer); "
                   f"null max over layers, 95th percentile = {q95:.2f}:", "",
                   "| layer | attn | mlp | resid | share of final residual difference: attn | mlp |", "|---|---|---|---|---|---|"]
            for l, aa, am_, ar in rows:
                md.append(f"| {l} | {aa:.2f} | {am_:.2f} | {ar:.2f} | {ca[l]:+.3f} | {cm[l]:+.3f} |")
            best = max(rows, key=lambda r: max(r[1:]))
            first = next((r[0] for r in rows if r[3] >= max(0.75, q95)), None)
            md += ["", f"- best: layer {best[0]} (attn {best[1]:.2f}, mlp {best[2]:.2f}, resid {best[3]:.2f}); first layer with resid AUROC >= "
                   f"max(0.75, null p95): {first}; attention share {sum(ca):+.2f}, MLP share {sum(cm):+.2f} (sum = 1)", ""]
            top_a = sorted(range(NL), key=lambda l: -abs(ca[l]))[:5]
            top_m = sorted(range(NL), key=lambda l: -abs(cm[l]))[:5]
            md += [f"- largest contributions: attention layers {[(l, round(ca[l], 3)) for l in top_a]}; MLP layers {[(l, round(cm[l], 3)) for l in top_m]}", ""]
            S["writes"] = {"rows": rows, "null_q95": q95, "share_attn": ca, "share_mlp": cm, "first_layer": first}
        X = Z["neuron"][ok, si_].astype(np.float32).reshape(ok.sum(), -1)
        hit, st = unit_counts(X, yy, gg, ff)
        if hit is not None:
            nulls = []
            for _ in range(5):
                hp, _ = unit_counts(X, shuffle_within(yy, gg, rng), gg, ff)
                nulls.append(int(hp.sum()))
            per_layer = hit.reshape(NL, -1).sum(1)
            top = np.argsort(-np.abs(st))[:12]
            md += [f"Neurons (MLP, 294,912): {int(hit.sum())} pass in both folds; label shuffles {nulls}.",
                   f"- by layer: {', '.join(f'L{l} {int(c)}' for l, c in enumerate(per_layer) if c)}",
                   f"- strongest: {', '.join(f'L{int(i) // 9216}/N{int(i) % 9216} {st[i]:+.2f}' for i in top)}", ""]
            S["neurons"] = {"n": int(hit.sum()), "null": nulls, "per_layer": per_layer.tolist(), "top": [[int(i) // 9216, int(i) % 9216, float(st[i])] for i in top]}
        H = Z["head_n"][ok, si_].astype(np.float32).reshape(ok.sum(), -1)
        valid = np.array([(h < 16) or (l % 4 != 3) for l in range(NL) for h in range(32)])
        hit, st = unit_counts(H[:, valid], yy, gg, ff)
        if hit is not None:
            names = [(l, h) for l in range(NL) for h in range(32) if (h < 16) or (l % 4 != 3)]
            nulls = []
            for _ in range(5):
                hp, _ = unit_counts(H[:, valid], shuffle_within(yy, gg, rng), gg, ff)
                nulls.append(int(hp.sum()))
            top = np.argsort(-np.abs(st))[:10]
            md += [f"Heads (write norm, {valid.sum()} heads): {int(hit.sum())} pass in both folds; label shuffles {nulls}.",
                   f"- strongest: {', '.join(f'L{names[i][0]}H{names[i][1]} {st[i]:+.2f}' for i in top)}", ""]
            S["heads"] = {"n": int(hit.sum()), "null": nulls, "top": [[names[i][0], names[i][1], float(st[i])] for i in top]}
        summary[sname] = S
    open(out_md, "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump(summary, open(out_md.replace(".md", ".json"), "w"))
    print("\n".join(md))


if __name__ == "__main__":
    main()
