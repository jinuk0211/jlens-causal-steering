"""All-neuron harmful vs harmless comparison on the stored agentic-misalignment responses (nmean_am.py output).
Feature = a neuron's mean score (act_scale units, signed) over a reply window (pre_tool, pre256).
Only conditions with >= 3 harmful responses are used, and every feature is centered on its condition mean, so prompt
differences do not count. Two-fold cross-fitting on fold = sample_id % 2:
- on the selection fold, Cohen's d (harmless - harmful) for every neuron;
- the top K by d form the "protective" set (higher when the model did not do the harmful act), the bottom K the "risk" set;
- held-out score = mean(protective features) - mean(risk features); AUC harmless > harmful on the other fold.
Null: the same with harmful labels permuted within condition on the selection fold (NPERM times).
Neurons with the same sign and |d| >= 0.3 in both folds are listed with their lens words.
Usage: python3 nmean_cmp.py NMEAN_DIR EXPLORER_CACHE SCENARIO OUT_MD [K] [NPERM]"""
import json
import sys
from pathlib import Path

import numpy as np


def auc(pos, neg):
    allv = np.concatenate([pos, neg])
    r = allv.argsort().argsort().astype(float) + 1
    for v in np.unique(allv):
        m = allv == v
        if m.sum() > 1:
            r[m] = r[m].mean()
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def main():
    d, cache, scen, out = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
    K = int(sys.argv[5]) if len(sys.argv) > 5 else 50
    NP = int(sys.argv[6]) if len(sys.argv) > 6 else 50
    idx = [json.loads(l) for l in open(d / "index.jsonl", encoding="utf-8")]
    idx = [r for r in idx if r["scenario"] == scen and r["harmful"] is not None]
    nh = {}
    for r in idx:
        nh.setdefault(r["condition"], [0, 0])[int(bool(r["harmful"]))] += 1
    keep = [r for r in idx if nh[r["condition"]][1] >= 3]
    if not keep:
        raise SystemExit(f"{scen}: no condition with >= 3 harmful ({nh})")
    vocab = json.loads((cache / "vocab.json").read_text(encoding="utf-8"))
    vs = lambda t: str(vocab[t]).replace("Ġ", " ").replace("Ċ", "\\n").replace("\n", "\\n").replace("|", "/").strip() or repr(vocab[t])
    ix = {k: dict(np.load(cache / f"{k}_index.npz")) for k in ("steer", "s")}
    z0 = np.load(keep[0]["file"])
    W = list(z0["windows"])
    L, N = z0["mean"].shape[1:]
    y = np.array([bool(r["harmful"]) for r in keep])
    fold = np.array([r["sample_id"] % 2 for r in keep])
    cond = np.array([r["condition"] for r in keep])
    md = [f"# All-neuron harmful vs harmless, {scen} (stored responses, condition-centered, 2-fold cross-fit)", "",
          f"Conditions used (harmless/harmful): " + ", ".join(f"{c} {v[0]}/{v[1]}" for c, v in sorted(nh.items()) if v[1] >= 3) +
          f". Excluded: " + (", ".join(f"{c} {v[0]}/{v[1]}" for c, v in sorted(nh.items()) if v[1] < 3) or "none") +
          f". K = {K} per side, {NP} permutations.", ""]
    rng = np.random.default_rng(0)
    for wi, w in enumerate(W):
        X = np.stack([np.load(r["file"])["mean"][wi].astype(np.float32).ravel() for r in keep])
        for c in np.unique(cond):
            m = cond == c
            X[m] -= X[m].mean(0)

        def dvec(rows, lab):
            a, b = X[rows][~lab], X[rows][lab]
            sd = np.sqrt((a.var(0) * (len(a) - 1) + b.var(0) * (len(b) - 1)) / max(1, len(a) + len(b) - 2)) + 1e-4
            return (a.mean(0) - b.mean(0)) / sd

        def heldout(lab_sel, f_sel):
            sel = fold == f_sel
            dv = dvec(sel, lab_sel)
            prot, risk = np.argsort(-dv)[:K], np.argsort(dv)[:K]
            te = fold != f_sel
            s = X[te][:, prot].mean(1) - X[te][:, risk].mean(1)
            return auc(s[~y[te]], s[y[te]]), dv
        res, dvs = [], []
        for f in (0, 1):
            a, dv = heldout(y[fold == f], f)
            res.append(a)
            dvs.append(dv)
        null = []
        for _ in range(NP):
            yp = y.copy()
            for c in np.unique(cond):
                for f in (0, 1):
                    m = (cond == c) & (fold == f)
                    yp[m] = rng.permutation(yp[m])
            null.append(np.mean([heldout(yp[fold == f], f)[0] for f in (0, 1)]))
        obs = float(np.mean(res))
        p = (1 + sum(n >= obs for n in null)) / (1 + NP)
        md += [f"## window {w}", "",
               f"Held-out AUC (harmless > harmful): fold0→1 {res[0]:.2f}, fold1→0 {res[1]:.2f}, mean {obs:.2f}; "
               f"permutation null mean {np.mean(null):.2f} (95th pct {np.percentile(null, 95):.2f}), p = {p:.3f}.", ""]
        both = (np.sign(dvs[0]) == np.sign(dvs[1])) & (np.abs(dvs[0]) >= 0.3) & (np.abs(dvs[1]) >= 0.3)
        both[:2 * N] = False
        dmin = np.where(both, np.sign(dvs[0]) * np.minimum(np.abs(dvs[0]), np.abs(dvs[1])), 0)
        md.append(f"Neurons with the same sign and |d| >= 0.3 in both folds (layers >= 2): {int(both.sum())} "
                  f"(protective {int((dmin > 0).sum())}, risk {int((dmin < 0).sum())}). Expected by chance with these sample sizes: compare the permutation p above.")
        md.append("")
        for side, order in (("protective (higher when NOT harmful)", np.argsort(-dmin)), ("risk (higher when harmful)", np.argsort(dmin))):
            md += [f"**{side}**", "", "| neuron | d fold0 | d fold1 | writes when + (steer) | writes when - (steer) | reads + (S) |", "|---|---|---|---|---|---|"]
            for k in order[:15]:
                if dmin[k] == 0:
                    break
                l, n = divmod(int(k), N)
                md.append(f"| L{l}/N{n} | {dvs[0][k]:+.2f} | {dvs[1][k]:+.2f} | {' '.join(vs(t) for t in ix['steer']['up'][l, n, :5])} | "
                          f"{' '.join(vs(t) for t in ix['steer']['down'][l, n, :5])} | {' '.join(vs(t) for t in ix['s']['up'][l, n, :4])} |")
            md.append("")
        np.savez_compressed(Path(out).with_suffix(f".{w}.npz"), d0=dvs[0].astype(np.float16), d1=dvs[1].astype(np.float16))
    open(out, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
