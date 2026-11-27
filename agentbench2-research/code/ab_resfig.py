"""Paper figure: the residual stream at the call onset, misaligned vs aligned decisions, three benchmarks. CPU only, no model.
Input: ana/hn/<bench>/hn.npz, array `ores` = residual after every layer at the call-onset token (the token that completes
<tool_call> in AgentDojo and ToolAlignBench, <tool_use: in Agentic Misalignment); written by ab_hn.py capture and ab_ne.py tacap.
Classes: misaligned = label "target"; aligned = "hn" (AgentDojo, AM: benign decisions in the same kind of context) or "reference"
(ToolAlignBench: default-tool calls). ToolAlignBench's 9 aligned non-default calls (internal emails) are kept apart as "extra".
Units with the same uid and the same onset residual are counted once.

compute : per benchmark and layer
    - centering: every unit minus the mean of all units of its group x fold (group = user task, condition or domain), no labels used;
    - axis: coordinates standardized on fold 0, axis = mean(misaligned) - mean(aligned) on fold 0, unit length;
    - held-out position of each fold-1 unit along the axis, in units of the fold-1 aligned sd, zero at the fold-1 aligned median;
    - held-out AUROC, pooled and within group; the same without centering; a logistic probe (C = 0.1) for comparison with ne/probes_report.md;
    - text before the call: a unit "has a preamble" if more than PRE response tokens precede the onset; AUROC inside the same preamble
      status, and inside the same group and status;
    - label permutations within group x fold (NPERM) for the null of the held-out AUROC;
    - layer for the 2-D panels: the layer with the highest leave-one-group-out AUROC inside fold 0, averaged over the benchmarks;
    - cross-benchmark, every layer: the axis of benchmark i (all its units) applied to benchmark j, AUROC within group, cosine between
      the axes, and their nulls from label permutations in benchmark i.
    -> ana/fig_resid/resfig.npz, resfig.json, resfig_report.md
plot : -> ana/fig_resid/residual_streams.pdf and .png
Usage: OMP_NUM_THREADS=8 python ab_resfig.py compute ; python ab_resfig.py plot"""
import json
import sys
import time
from pathlib import Path

import numpy as np

A = Path("/home/project-b/LJW/agentbench2/ana")
OUT = A / "fig_resid"
BENCH = ("dojo", "toolalign", "am")
NAME = {"dojo": "AgentDojo", "toolalign": "ToolAlignBench", "am": "Agentic Misalignment"}
NL, NPERM, SEED, PRE = 32, 200, 20261127, 8
PAIRS = ((0, 1), (1, 0), (0, 2), (2, 0), (1, 2), (2, 1))


def auroc(pos, neg):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)))


def auroc_within(s, y, g):
    """Share of (misaligned, aligned) pairs of the same group in which the misaligned unit scores higher; ties count one half."""
    num = den = 0.0
    ng = 0
    for k in np.unique(g):
        m = g == k
        p, n = s[m & y], s[m & ~y]
        if len(p) and len(n):
            num += ((p[:, None] > n[None, :]).sum() + 0.5 * (p[:, None] == n[None, :]).sum())
            den += len(p) * len(n)
            ng += 1
    return (float(num / den) if den else float("nan")), ng, int(den)


def load(b):
    d = np.load(A / "hn" / b / "hn.npz")
    lab, fold, grp, uid = d["labels"], d["folds"].astype(int), d["groups"], d["uids"]
    ores = d["ores"].astype(np.float32)
    nb = np.zeros(len(lab), int)
    for i, dist in zip(d["traj_item"], d["traj_dist"]):
        nb[i] = max(nb[i], int(dist))
    seen, keep = set(), []
    for i in range(len(lab)):
        k = (str(uid[i]), ores[i, 16, :64].tobytes())
        if k not in seen:
            seen.add(k)
            keep.append(i)
    keep = np.array(keep)
    lab, fold, grp, uid, ores, nb = lab[keep], fold[keep], grp[keep], uid[keep], ores[keep], nb[keep]
    mis = lab == "target"
    ali = (lab == "reference") if b == "toolalign" else (lab == "hn")
    ext = (lab == "aligned") if b == "toolalign" else np.zeros(len(lab), bool)
    use = mis | ali | ext
    return {"X": ores[use], "mis": mis[use], "ali": ali[use], "ext": ext[use], "fold": fold[use], "grp": grp[use].astype(str),
            "uid": uid[use].astype(str), "nb": nb[use], "pre": nb[use] > PRE, "n_items": int(len(d["labels"])), "n_units": int(use.sum())}


def center(X, grp, fold):
    Xc = X.copy()
    for k in set(zip(grp.tolist(), fold.tolist())):
        m = (grp == k[0]) & (fold == k[1])
        Xc[m] -= X[m].mean(0, keepdims=True)
    return Xc


def axis(X, mis, ali):
    """Standardization on the given units and the unit-length difference of class means in standardized coordinates."""
    both = mis | ali
    mu, sd = X[both].mean(0), X[both].std(0) + 1e-4
    Z = (X - mu) / sd
    w = Z[mis].mean(0) - Z[ali].mean(0)
    return mu, sd, w / (np.linalg.norm(w) + 1e-12)


def perm_within(y, strata, rng):
    yp = y.copy()
    for k in np.unique(strata):
        m = np.where(strata == k)[0]
        yp[m] = y[m][rng.permutation(len(m))]
    return yp


def logit_auc(X0, y0, X1, y1):
    from sklearn.linear_model import LogisticRegression
    mu, sd = X0.mean(0), X0.std(0) + 1e-4
    clf = LogisticRegression(C=0.1, max_iter=2000).fit((X0 - mu) / sd, y0.astype(int))
    s = clf.decision_function((X1 - mu) / sd)
    return auroc(s[y1], s[~y1])


def mode_compute():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    t0 = time.time()
    D = {b: load(b) for b in BENCH}
    res, arr = {}, {}
    cvs = {}
    for b in BENCH:
        d = D[b]
        two = d["mis"] | d["ali"]
        f0, f1 = (d["fold"] == 0) & two, (d["fold"] == 1) & two
        strata = np.array([f"{g}|{f}" for g, f in zip(d["grp"], d["fold"])])
        y1, g1, p1 = d["mis"][f1], d["grp"][f1], d["pre"][f1]
        gp1 = np.array([f"{g}|{int(p)}" for g, p in zip(g1, p1)])
        r = {"n_items": d["n_items"], "n_units": d["n_units"],
             "n": {"mis0": int((f0 & d["mis"]).sum()), "ali0": int((f0 & d["ali"]).sum()), "mis1": int((f1 & d["mis"]).sum()),
                   "ali1": int((f1 & d["ali"]).sum()), "ext0": int(((d["fold"] == 0) & d["ext"]).sum()), "ext1": int(((d["fold"] == 1) & d["ext"]).sum())},
             "groups": int(len(set(d["grp"]))), "layers": [],
             "text_before": {"threshold": PRE, "share_with_preamble": {k: float(d["pre"][d[k]].mean()) for k in ("mis", "ali", "ext") if d[k].any()},
                             "median_tokens": {k: float(np.median(d["nb"][d[k]])) for k in ("mis", "ali", "ext") if d[k].any()},
                             "auc_of_length_within_group": auroc_within(np.log1p(d["nb"][f1]).astype(float), y1, g1)[0],
                             "auc_of_length_pooled": auroc(d["nb"][f1][y1], d["nb"][f1][~y1])}}
        POS = np.zeros((NL, int(f1.sum())), np.float32)
        NULL = np.zeros((NL, NPERM), np.float32)
        NULLW = np.full((NL, NPERM), np.nan, np.float32)
        perms = [perm_within(d["mis"], strata, rng) for _ in range(NPERM)]
        cv = np.zeros(NL)
        for l in range(NL):
            Xr = d["X"][:, l]
            Xc = center(Xr, d["grp"], d["fold"])
            row = {"layer": l}
            for nm, X in (("c", Xc), ("r", Xr)):
                mu, sd, u = axis(X[f0], d["mis"][f0], d["ali"][f0])
                s = ((X[f1] - mu) / sd) @ u
                wi, ng, npair = auroc_within(s, y1, g1)
                row[f"auc_{nm}"] = auroc(s[y1], s[~y1])
                row[f"auc_within_{nm}"] = wi
                row["within_groups"], row["within_pairs"] = ng, npair
                a = s[~y1]
                z = (s - np.median(a)) / (a.std() + 1e-12)
                row[f"dprime_{nm}"] = float((z[y1].mean() - z[~y1].mean()) / np.sqrt(0.5 * (z[y1].var() + z[~y1].var()) + 1e-12))
                if nm == "c":
                    POS[l] = z
                    a_, _, c_ = auroc_within(s, y1, p1.astype(str))
                    row["auc_samepre"], row["samepre_pairs"] = a_, c_
                    a_, _, c_ = auroc_within(s, y1, gp1)
                    row["auc_samepre_group"], row["samepre_group_pairs"] = a_, c_
                    for nm2, mm in (("pre", p1), ("nopre", ~p1)):
                        row[f"auc_{nm2}"] = auroc(s[mm & y1], s[mm & ~y1])
                        row[f"n_{nm2}"] = [int((mm & y1).sum()), int((mm & ~y1).sum())]
            row["probe_c"] = logit_auc(Xc[f0], d["mis"][f0], Xc[f1], y1)
            row["probe_r"] = logit_auc(Xr[f0], d["mis"][f0], Xr[f1], y1)
            for k, yp in enumerate(perms):
                if (yp & f0).sum() < 2 or ((~yp) & f0).sum() < 2:
                    NULL[l, k] = np.nan
                    continue
                mu, sd, u = axis(Xc[f0], yp[f0], ~yp[f0])
                s = ((Xc[f1] - mu) / sd) @ u
                NULL[l, k] = auroc(s[yp[f1]], s[~yp[f1]])
                NULLW[l, k] = auroc_within(s, yp[f1], g1)[0]
            nn = NULL[l][~np.isnan(NULL[l])]
            row["null_mean"], row["null_p95"] = float(nn.mean()), float(np.quantile(nn, 0.95))
            row["perm_p"] = float((1 + (nn >= row["auc_c"]).sum()) / (1 + len(nn)))
            nw = NULLW[l][~np.isnan(NULLW[l])]
            row["nullw_lo"], row["nullw_hi"] = float(np.quantile(nw, 0.025)), float(np.quantile(nw, 0.975))
            row["perm_p_within"] = float((1 + (nw >= row["auc_within_c"]).sum()) / (1 + len(nw)))
            sc = np.full(int(f0.sum()), np.nan)
            g0, y0, X0 = d["grp"][f0], d["mis"][f0], Xc[f0]
            for g in np.unique(g0):
                te = g0 == g
                if y0[~te].sum() < 2 or (~y0[~te]).sum() < 2:
                    continue
                mu, sd, u = axis(X0[~te], y0[~te], ~y0[~te])
                sc[te] = ((X0[te] - mu) / sd) @ u
            ok = ~np.isnan(sc)
            cv[l] = auroc(sc[ok & y0], sc[ok & ~y0])
            row["cv0"] = float(cv[l])
            r["layers"].append(row)
        cvs[b] = cv
        res[b] = r
        arr[f"{b}_pos"], arr[f"{b}_y1"], arr[f"{b}_g1"], arr[f"{b}_p1"], arr[f"{b}_null"] = POS, y1, g1, p1, NULL
        print(b, r["n"], f"{time.time() - t0:.0f}s", flush=True)
    mean_cv = np.mean([cvs[b] for b in BENCH], 0)
    LS = int(np.argmax(mean_cv))
    res["layer_star"] = LS
    res["cv0_mean"] = [float(x) for x in mean_cv]
    for b in BENCH:
        d = D[b]
        two = d["mis"] | d["ali"]
        f0, sel = (d["fold"] == 0) & two, d["fold"] == 1
        Xc = center(d["X"][:, LS], d["grp"], d["fold"])
        mu, sd, u = axis(Xc[f0], d["mis"][f0], d["ali"][f0])
        Z0 = (Xc[f0] - mu) / sd
        R0 = Z0 - np.outer(Z0 @ u, u)
        v = np.linalg.svd(R0 - R0.mean(0), full_matrices=False)[2][0]
        Z1 = (Xc[sel] - mu) / sd
        sx, sy = Z1 @ u, Z1 @ v
        ya, ym, ye = d["ali"][sel], d["mis"][sel], d["ext"][sel]
        sx = (sx - np.median(sx[ya])) / (sx[ya].std() + 1e-12)
        sy = (sy - np.median(sy[ya])) / (sy[ya].std() + 1e-12)
        arr[f"{b}_sx"], arr[f"{b}_sy"] = sx, sy
        arr[f"{b}_cls"] = np.where(ym, 1, np.where(ye, 2, 0))
        arr[f"{b}_spre"] = d["pre"][sel]
        if ye.any():
            res[b]["extra"] = {"n1": int(ye.sum()), "median_pos": float(np.median(sx[ye])), "median_mis": float(np.median(sx[ym])),
                               "auc_extra_vs_aligned": auroc(sx[ye], sx[ya]), "auc_mis_vs_extra": auroc(sx[ym], sx[ye])}
            ex = []
            for l in range(NL):
                Xl = center(d["X"][:, l], d["grp"], d["fold"])
                mu, sd, u = axis(Xl[f0], d["mis"][f0], d["ali"][f0])
                s = ((Xl[sel] - mu) / sd) @ u
                ex.append({"layer": l, "extra_vs_aligned": auroc(s[ye], s[ya]), "mis_vs_extra": auroc(s[ym], s[ye])})
            res[b]["extra_layers"] = ex
    cross, crossp, cosm, cos_raw = (np.zeros((NL, 3, 3)) for _ in range(4))
    cnull = np.zeros((NL, 3, 3, NPERM), np.float32)
    anull = np.zeros((NL, 3, 3, NPERM), np.float32)
    stratas = {b: np.array([f"{g}|{f}" for g, f in zip(D[b]["grp"], D[b]["fold"])]) for b in BENCH}
    permsx = {b: [perm_within(D[b]["mis"], stratas[b], rng) for _ in range(NPERM)] for b in BENCH}
    two = {b: D[b]["mis"] | D[b]["ali"] for b in BENCH}
    gps = {b: np.array([f"{g}|{int(p)}" for g, p in zip(D[b]["grp"], D[b]["pre"])]) for b in BENCH}
    for l in range(NL):
        XC = {b: center(D[b]["X"][:, l], D[b]["grp"], D[b]["fold"]) for b in BENCH}
        sd = np.sqrt(np.mean([XC[b][two[b]].var(0) for b in BENCH], 0)) + 1e-4
        Z = {b: XC[b] / sd for b in BENCH}
        ax, raw, pax = {}, {}, {}
        for b in BENCH:
            w = Z[b][D[b]["mis"]].mean(0) - Z[b][D[b]["ali"]].mean(0)
            ax[b] = w / np.linalg.norm(w)
            wr = XC[b][D[b]["mis"]].mean(0) - XC[b][D[b]["ali"]].mean(0)
            raw[b] = wr / np.linalg.norm(wr)
            P = np.zeros((NPERM, Z[b].shape[1]), np.float32)
            for k, yp in enumerate(permsx[b]):
                w = Z[b][yp & two[b]].mean(0) - Z[b][(~yp) & two[b]].mean(0)
                P[k] = w / (np.linalg.norm(w) + 1e-12)
            pax[b] = P
        for i, bi in enumerate(BENCH):
            for j, bj in enumerate(BENCH):
                cosm[l, i, j] = float(ax[bi] @ ax[bj])
                cos_raw[l, i, j] = float(raw[bi] @ raw[bj])
                if i == j:
                    continue
                t = two[bj]
                yj, gj = D[bj]["mis"][t], D[bj]["grp"][t]
                s = Z[bj][t] @ ax[bi]
                cross[l, i, j] = auroc_within(s, yj, gj)[0]
                crossp[l, i, j] = auroc_within(s, yj, gps[bj][t])[0]
                cnull[l, i, j] = pax[bi] @ ax[bj]
                S = Z[bj][t] @ pax[bi].T
                for k in range(NPERM):
                    anull[l, i, j, k] = auroc_within(S[:, k], yj, gj)[0]
        if l % 8 == 0:
            print("cross layer", l, f"{time.time() - t0:.0f}s", flush=True)
    for i, b in enumerate(BENCH):
        cross[:, i, i] = [res[b]["layers"][l]["auc_within_c"] for l in range(NL)]
        crossp[:, i, i] = [res[b]["layers"][l]["auc_samepre_group"] for l in range(NL)]
    pv = np.ones((NL, 3, 3))
    for l in range(NL):
        for i, j in PAIRS:
            pv[l, i, j] = (1 + (anull[l, i, j] >= cross[l, i, j]).sum()) / (1 + NPERM)
    arr.update(cross=cross, crossp=crossp, cos=cosm, cos_raw=cos_raw, cnull=cnull, anull=anull, cross_p=pv)
    res["cross_layers"] = [{"layer": l, "cos": [float(cosm[l, i, j]) for i, j in ((0, 1), (0, 2), (1, 2))],
                            "cos_raw": [float(cos_raw[l, i, j]) for i, j in ((0, 1), (0, 2), (1, 2))],
                            "cos_null975": [float(np.quantile(np.abs(np.r_[cnull[l, i, j], cnull[l, j, i]]), 0.975)) for i, j in ((0, 1), (0, 2), (1, 2))],
                            "auc": {f"{BENCH[i]}>{BENCH[j]}": float(cross[l, i, j]) for i, j in PAIRS},
                            "auc_samepre": {f"{BENCH[i]}>{BENCH[j]}": float(crossp[l, i, j]) for i, j in PAIRS},
                            "p": {f"{BENCH[i]}>{BENCH[j]}": float(pv[l, i, j]) for i, j in PAIRS},
                            "null025": {f"{BENCH[i]}>{BENCH[j]}": float(np.quantile(anull[l, i, j], 0.025)) for i, j in PAIRS},
                            "null975": {f"{BENCH[i]}>{BENCH[j]}": float(np.quantile(anull[l, i, j], 0.975)) for i, j in PAIRS}} for l in range(NL)]
    np.savez(OUT / "resfig.npz", **arr)
    (OUT / "resfig.json").write_text(json.dumps(res), encoding="utf-8")
    L = [f"# Residual stream at the call onset, misaligned vs aligned ({time.strftime('%F %T')})", "",
         f"Layer for the 2-D panels (highest mean leave-one-group-out AUROC inside fold 0): L{LS}", ""]
    for b in BENCH:
        r = res[b]
        L += [f"## {NAME[b]}", "", f"items {r['n_items']}, units after de-duplication {r['n_units']}, groups {r['groups']}, counts {r['n']}", "",
              "| layer | held-out AUROC (centered) | within group | perm mean | perm p95 | p | d' | uncentered AUROC | uncentered within group | probe centered | probe uncentered | fold-0 CV |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for x in r["layers"]:
            L.append(f"| {x['layer']} | {x['auc_c']:.2f} | {x['auc_within_c']:.2f} | {x['null_mean']:.2f} | {x['null_p95']:.2f} | {x['perm_p']:.3f} | {x['dprime_c']:.2f} | "
                     f"{x['auc_r']:.2f} | {x['auc_within_r']:.2f} | {x['probe_c']:.2f} | {x['probe_r']:.2f} | {x['cv0']:.2f} |")
        L += ["", f"within-group pairs at every layer: {r['layers'][0]['within_pairs']} in {r['layers'][0]['within_groups']} groups", "",
              f"text before the onset: {r['text_before']}", "",
              "| layer | same preamble status (pairs) | same group and status (pairs) | with preamble only (n mis, ali) | without preamble only (n mis, ali) |", "|---|---|---|---|---|"]
        for x in r["layers"]:
            L.append(f"| {x['layer']} | {x['auc_samepre']:.2f} ({x['samepre_pairs']}) | {x['auc_samepre_group']:.2f} ({x['samepre_group_pairs']}) | "
                     f"{x['auc_pre']:.2f} {x['n_pre']} | {x['auc_nopre']:.2f} {x['n_nopre']} |")
        L += ["", "within-group AUROC, permutation 2.5-97.5 % and p by layer: " +
              "; ".join(f"L{x['layer']} {x['auc_within_c']:.2f} [{x['nullw_lo']:.2f}, {x['nullw_hi']:.2f}] p{x['perm_p_within']:.3f}" for x in r["layers"]), ""]
        if "extra" in r:
            L += [f"aligned non-default calls (fold 1) at L{LS}: {r['extra']}", "",
                  "aligned non-default calls by layer (AUROC vs default calls / misaligned vs them): " +
                  "; ".join(f"L{x['layer']} {x['extra_vs_aligned']:.2f}/{x['mis_vs_extra']:.2f}" for x in r["extra_layers"]), ""]
    L += ["## Cross-benchmark by layer", "",
          "cosine between the axes (dojo-toolalign, dojo-am, toolalign-am), the 97.5 % point of |cos| under label permutation in brackets; then, per directed",
          "pair, the within-group transfer AUROC, its one-sided permutation p, and after the slash the AUROC inside the same group and preamble status.", ""]
    for c in res["cross_layers"]:
        L.append(f"L{c['layer']}: cos " + " ".join(f"{c['cos'][k]:+.3f} [{c['cos_null975'][k]:.3f}]" for k in range(3)) + " | " +
                 " ".join(f"{k} {c['auc'][k]:.2f} p{c['p'][k]:.3f}/{c['auc_samepre'][k]:.2f}" for k in c["auc"]))
    (OUT / "resfig_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


INK, INK2, MUTED, BAND = "#0b0b0b", "#52514e", "#8a8980", "#e9e8e4"
C_ALI, C_MIS = "#2a78d6", "#eb6834"
CTX = {"dojo": "user task", "toolalign": "domain", "am": "condition"}
SHORT = {"dojo": "AD", "toolalign": "TA", "am": "AM"}


def mode_plot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({"font.family": "STIXGeneral", "mathtext.fontset": "stix", "font.size": 7, "axes.linewidth": 0.5, "pdf.fonttype": 42,
                         "ps.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
                         "xtick.major.size": 2.5, "ytick.major.size": 2.5, "axes.labelsize": 7, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
                         "legend.fontsize": 6.3, "axes.titlesize": 7.5, "axes.labelpad": 2})
    res = json.loads((OUT / "resfig.json").read_text(encoding="utf-8"))
    d = np.load(OUT / "resfig.npz")
    LS = res["layer_star"]
    lay = np.arange(NL)
    dash = (0, (3.2, 1.8))
    fig = plt.figure(figsize=(6.75, 3.55))
    gs = fig.add_gridspec(2, 5, width_ratios=[1, 1, 1, 0.13, 1], left=0.066, right=0.995, top=0.93, bottom=0.105, hspace=0.74, wspace=0.27)
    clipped = {}
    for c, b in enumerate(BENCH):
        r = res[b]["layers"]
        ax = fig.add_subplot(gs[0, c])
        ax.fill_between(lay, [x["nullw_lo"] for x in r], [x["nullw_hi"] for x in r], color=BAND, lw=0, zorder=1)
        ax.axhline(0.5, color=MUTED, lw=0.5, zorder=2)
        ax.axvline(LS, color=MUTED, lw=0.5, ls=(0, (1, 2)), zorder=2)
        ax.plot(lay, [x["auc_within_c"] for x in r], color=INK, lw=1.3, zorder=4, solid_capstyle="round")
        ax.plot(lay, [x["auc_samepre_group"] for x in r], color=INK2, lw=1.0, ls=dash, zorder=3)
        ax.set_xlim(-0.5, 31.5)
        ax.set_ylim(0.0, 1.03)
        ax.set_xticks([0, 8, 16, 24, 31])
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_xlabel("layer")
        ax.set_title(NAME[b], loc="left", pad=3)
        if c > 0:
            ax.tick_params(labelleft=False)
        if c == 0:
            ax.set_ylabel("held-out AUROC")
            ax.legend([Line2D([], [], color=INK, lw=1.3), Line2D([], [], color=INK2, lw=1.0, ls=dash), plt.Rectangle((0, 0), 1, 1, color=BAND)],
                      ["same context", "and same preamble status", "shuffled labels (95%)"], loc="lower left", frameon=False,
                      handlelength=1.9, borderpad=0.0, borderaxespad=0.45, labelspacing=0.22, handletextpad=0.5)
            ax.text(-0.27, 1.08, "a", transform=ax.transAxes, fontsize=9, fontweight="bold")
        ax2 = fig.add_subplot(gs[1, c])
        sx, sy, cls = d[f"{b}_sx"], d[f"{b}_sy"], d[f"{b}_cls"]
        lo, hi = np.quantile(sy, 0.01), np.quantile(sy, 0.99)
        pad = 0.12 * (hi - lo)
        lo, hi = lo - pad, hi + pad
        out = (sy < lo) | (sy > hi)
        clipped[b] = int(out.sum())
        yy = np.clip(sy, lo, hi)
        ax2.axvline(0, ymax=0.74, color=MUTED, lw=0.5, zorder=1)
        for k, (mk, sz, col) in enumerate((("o", 9, C_ALI), ("^", 13, C_MIS))):
            m = (cls == k) & ~out
            ax2.scatter(sx[m], yy[m], s=sz, marker=mk, color=col, alpha=0.85, edgecolors="white", linewidths=0.3, zorder=3 + k)
            m = (cls == k) & out
            if m.any():
                ax2.scatter(sx[m], yy[m], s=sz + 3, marker=mk, facecolors="none", edgecolors=col, linewidths=0.7, zorder=3 + k, clip_on=False)
        if (cls == 2).any():
            ax2.scatter(sx[cls == 2], yy[cls == 2], s=15, marker="D", facecolors="white", edgecolors=C_ALI, linewidths=0.9, zorder=6)
        ax2.set_xlabel(f"position along the axis, layer {LS}")
        x30 = r[LS]
        ax2.set_ylim(lo, hi + 0.30 * (hi - lo))
        ax2.margins(x=0.06)
        ax2.text(0.03, 0.975, f"AUROC {x30['auc_c']:.2f}\nsame {CTX[b]} {x30['auc_within_c']:.2f}", transform=ax2.transAxes, va="top", ha="left",
                 fontsize=6.3, color=INK2, linespacing=1.15)
        if c == 0:
            ax2.set_ylabel("largest remaining component")
            ax2.text(-0.27, 1.13, "b", transform=ax2.transAxes, fontsize=9, fontweight="bold")
            ax2.legend([Line2D([], [], marker="o", ls="", color=C_ALI, ms=3.2), Line2D([], [], marker="^", ls="", color=C_MIS, ms=3.6)],
                       ["aligned", "misaligned"], loc="lower left", bbox_to_anchor=(-0.02, 1.0), ncol=2, frameon=False, handletextpad=0.0,
                       columnspacing=0.9, borderpad=0.0, borderaxespad=0.2)
        if (cls == 2).any():
            ax2.legend([Line2D([], [], marker="D", ls="", mfc="white", mec=C_ALI, mew=0.9, ms=3.2)], ["aligned, not the default tool"], loc="lower left",
                       bbox_to_anchor=(-0.02, 1.0), frameon=False, handletextpad=0.0, borderpad=0.0, borderaxespad=0.2)
    cl = res["cross_layers"]
    styles = (("dojo", "toolalign", INK, "-", 1.2), ("dojo", "am", INK, dash, 1.2), ("toolalign", "am", MUTED, "-", 1.2))
    axc = fig.add_subplot(gs[0, 4])
    axc.axhline(0, color=MUTED, lw=0.5)
    for k, (bi, bj, col, ls, lw) in enumerate(styles):
        axc.plot(lay, [x["cos"][k] for x in cl], color=col, ls=ls, lw=lw, label=f"{SHORT[bi]}, {SHORT[bj]}")
    axc.set_xlim(-0.5, 31.5)
    axc.set_ylim(-0.5, 1.03)
    axc.set_yticks([-0.5, 0, 0.5, 1.0])
    axc.set_xticks([0, 8, 16, 24, 31])
    axc.set_xlabel("layer")
    axc.set_ylabel("cosine between axes")
    axc.set_title("Across benchmarks", loc="left", pad=3)
    axc.legend(loc="upper right", frameon=False, handlelength=2.2, borderpad=0.0, borderaxespad=0.25, labelspacing=0.22)
    axc.text(-0.4, 1.08, "c", transform=axc.transAxes, fontsize=9, fontweight="bold")
    axt = fig.add_subplot(gs[1, 4])
    axt.axhline(0.5, color=MUTED, lw=0.5)
    for k, (bi, bj, col, ls, lw) in enumerate(styles):
        k1, k2 = f"{bi}>{bj}", f"{bj}>{bi}"
        m = np.array([(x["auc"][k1] + x["auc"][k2]) / 2 for x in cl])
        sig = np.array([(x["p"][k1] < 0.05) and (x["p"][k2] < 0.05) for x in cl])
        axt.plot(lay, m, color=col, ls=ls, lw=lw)
        if sig.any():
            axt.scatter(lay[sig], m[sig], s=10, color=col, zorder=5, edgecolors="white", linewidths=0.3)
        print("both directions p < 0.05:", bi, bj, lay[sig].tolist())
    axt.set_xlim(-0.5, 31.5)
    axt.set_ylim(0.0, 1.03)
    axt.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    axt.set_xticks([0, 8, 16, 24, 31])
    axt.set_xlabel("layer")
    axt.set_ylabel("AUROC with another\nbenchmark's axis")
    axt.text(-0.4, 1.13, "d", transform=axt.transAxes, fontsize=9, fontweight="bold")
    fig.savefig(OUT / "residual_streams.pdf")
    fig.savefig(OUT / "residual_streams.png", dpi=300)
    print("saved", OUT / "residual_streams.pdf", "| units drawn at the vertical edge:", clipped)


if __name__ == "__main__":
    {"compute": mode_compute, "plot": mode_plot}[sys.argv[1]]()
