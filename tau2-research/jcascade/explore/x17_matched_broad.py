"""X17 (CPU, PC): can ANY J-lens word at ANY layer tell an unneeded transfer from a denial in the same task?

Rows exactly as R3 (C) (review/r3_matched.py): bad = unexpected_transfer and the episode not passing (NL-corrected ep_pass for
f_detect), from out/x15; denials from out/review/denial restricted to tasks that have a bad transfer -> 15 bad (12 tasks) vs 26.
Task-grouped 5-fold CV (mine.fold_of), everything selected inside the training folds.
Detectors (decision point):
  J_pairs      mine.select_pairs trained on bad vs denial (bad-direction (layer, word) pairs, K 30)
  broad_{lens} both directions, K in {10, 30, 100}; features = (layer, word) in the top-100 at each of the 32 layers plus
               (any layer, word); lens = J-lens, J++, both
  turn         turn index
  residual Ll  logistic on the residual at L10 / L12 / L14 / L16 / L18 (same CV as R3 (C))
Null: within-task label permutation (counts per task kept), the full selection + CV rerun, 100 permutations per detector.
Also the within-task AUC (pairs of a bad row and a denial row from the same task only).
Output: explore/x17_matched_broad.md, .json
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
JC = HERE.parent
RES = JC.parent
sys.path.insert(0, str(RES / "mining"))
import mine

X15 = JC / "out/x15"
DEN = JC / "out/review/denial"
V = mine.V
NPERM = 100


def logistic(Xtr, ytr, Xte, l2=10.0, iters=800, lr=0.2):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
    A, B = (Xtr - mu) / sd, (Xte - mu) / sd
    A = np.hstack([A, np.ones((len(A), 1))])
    B = np.hstack([B, np.ones((len(B), 1))])
    w = np.zeros(A.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(A @ w, -30, 30)))
        w -= lr * (A.T @ (p - ytr) / len(ytr) + l2 * np.r_[w[:-1], 0] / len(ytr))
    return B @ w


def keys_of(ids):
    L = np.arange(ids.shape[0], dtype=np.int64)[:, None]
    per = ((L * V) + ids.astype(np.int64)).ravel()
    anyl = (32 * V + ids.astype(np.int64)).ravel()
    return np.unique(np.concatenate([per, anyl]))


def broad_scores(keys, y, folds, K):
    oof = np.zeros(len(y))
    for q in range(mine.NFOLD):
        tr, te = np.nonzero(folds != q)[0], np.nonzero(folds == q)[0]
        if len(te) == 0 or len(set(y[tr].tolist())) < 2:
            continue
        cb, cg = Counter(), Counter()
        for i in tr:
            (cb if y[i] else cg).update(keys[i].tolist())
        nb, ng = int(y[tr].sum()), int((1 - y[tr]).sum())
        allk = set(cb) | set(cg)
        lr = {k: np.log((cb.get(k, 0) + 0.5) / (nb + 1)) - np.log((cg.get(k, 0) + 0.5) / (ng + 1)) for k in allk}
        pos = [k for k, _ in sorted(((k, v) for k, v in lr.items() if cb.get(k, 0) >= 3), key=lambda kv: -kv[1])[:K]]
        neg = [k for k, _ in sorted(((k, v) for k, v in lr.items() if cg.get(k, 0) >= 3), key=lambda kv: kv[1])[:K]]
        ps, ns = set(pos), set(neg)
        for i in te:
            s = set(keys[i].tolist())
            oof[i] = len(s & ps) - len(s & ns)
    return oof


def jpairs_scores(keys, y, folds):
    oof = np.zeros(len(y))
    for q in range(mine.NFOLD):
        tr, te = np.nonzero(folds != q)[0], np.nonzero(folds == q)[0]
        if len(te) == 0 or len(set(y[tr].tolist())) < 2:
            continue
        sel, *_ = mine.select_pairs([keys[i] for i in tr], y[tr])
        for i in te:
            oof[i] = mine.score_pairs(keys[i], sel)
    return oof


def logit_scores(F, y, folds):
    oof = np.zeros(len(y))
    for q in range(mine.NFOLD):
        tr, te = np.nonzero(folds != q)[0], np.nonzero(folds == q)[0]
        if len(te) == 0 or len(set(y[tr].tolist())) < 2:
            continue
        oof[te] = logistic(F[tr], y[tr].astype(float), F[te])
    return oof


def within_task_auc(s, y, groups):
    num = den = 0.0
    for g in set(groups):
        m = np.array(groups) == g
        p, n = s[m & (y == 1)], s[m & (y == 0)]
        if len(p) and len(n):
            num += (p[:, None] > n[None]).sum() + 0.5 * (p[:, None] == n[None]).sum()
            den += len(p) * len(n)
    return float(num / den) if den else None


def main():
    rng = np.random.default_rng(11)
    voc = json.loads(__import__("gzip").open(RES / "mining/vocab.json.gz", "rt", encoding="utf-8").read())
    turns = json.loads((RES / "mining/cache_turns.json").read_text(encoding="utf-8"))
    nl_pass = {(t["domain"], t["sim"]): t["ep_pass"] for t in turns}
    xr = json.loads((X15 / "rows.json").read_text(encoding="utf-8"))
    dr = json.loads((DEN / "rows.json").read_text(encoding="utf-8"))
    bad = []
    for r in xr:
        is_bad = any(b.startswith("unexpected_transfer") for b in r["bad"])
        ep_pass = nl_pass.get((r["domain"], r["sim"]), r["ep_pass"]) if r["cond"] == "f_detect" else r["ep_pass"]
        if is_bad and not ep_pass:
            bad.append(("x15", r))
    bad_tasks = {(r["domain"], r["task"]) for _, r in bad}
    den = [("den", r) for r in dr if (r["domain"], r["task"]) in bad_tasks]
    bad = [(s, r) for s, r in bad if (r["domain"], r["task"]) in {(d["domain"], d["task"]) for _, d in den}]
    rows = bad + den
    y = np.array([1] * len(bad) + [0] * len(den))
    groups = [f"{r['domain']}|{r['task']}" for _, r in rows]
    folds = np.array([mine.fold_of(g) for g in groups])
    Z = [np.load((X15 if s == "x15" else DEN) / f"feat_{r['k']}.npz") for s, r in rows]
    turn = np.array([r["turn"] for _, r in rows], float)
    kj = [keys_of(z["dec_ids_jlens"]) for z in Z]
    kp = [keys_of(z["dec_ids_jpp"]) for z in Z]
    kb = [np.unique(np.concatenate([a, b + 33 * V])) for a, b in zip(kj, kp)]
    res_l = {l: np.stack([z["res"][l].astype(np.float32) for z in Z]) for l in (10, 12, 14, 16, 18)}
    dets = {"J_pairs (bad-direction, K30)": lambda yy: jpairs_scores(kj, yy, folds),
            "turn index": lambda yy: turn}
    for K in (10, 30, 100):
        dets[f"broad J-lens K{K}"] = (lambda K: lambda yy: broad_scores(kj, yy, folds, K))(K)
        dets[f"broad J++ K{K}"] = (lambda K: lambda yy: broad_scores(kp, yy, folds, K))(K)
        dets[f"broad J-lens+J++ K{K}"] = (lambda K: lambda yy: broad_scores(kb, yy, folds, K))(K)
    for l, F in res_l.items():
        dets[f"residual L{l} (logistic)"] = (lambda F: lambda yy: logit_scores(F, yy, folds))(F)
    gidx = {g: np.nonzero(np.array(groups) == g)[0] for g in set(groups)}

    def permute():
        yp = y.copy()
        for g, ii in gidx.items():
            yp[ii] = rng.permutation(y[ii])
        return yp

    perms = [permute() for _ in range(NPERM)]
    md = ["# X17: any J-lens word, any layer: unneeded transfer vs same-task denial (R3 (C) rows)", "",
          f"rows: bad {int(y.sum())} ({len({g for g, yy in zip(groups, y) if yy})} tasks), denial {int((1 - y).sum())}, "
          f"task clusters {len(set(groups))}; within-task label-permutation null, {NPERM} permutations, selection + CV rerun each time", "",
          "| detector | AUC (pooled OOF) | within-task AUC | null mean | null 95th pct | null max | p (null >= observed) |",
          "|---|---|---|---|---|---|---|"]
    out = {}
    for name, fn in dets.items():
        s = fn(y)
        a = mine.auc(s, y)
        wa = within_task_auc(s, y, groups)
        if name == "turn index":
            null = [mine.auc(s, yp) for yp in perms]
        else:
            null = [mine.auc(fn(yp), yp) for yp in perms]
        null = np.array([v for v in null if v is not None])
        p = float((null >= a).mean()) if len(null) else None
        out[name] = {"auc": a, "within_task": wa, "null_mean": float(null.mean()), "null_95": float(np.percentile(null, 95)),
                     "null_max": float(null.max()), "p": p}
        md.append(f"| {name} | {a:.3f} | {wa if wa is None else round(wa, 3)} | {null.mean():.3f} | {np.percentile(null, 95):.3f} | {null.max():.3f} | {p:.2f} |")
        print(name, round(a, 3), "p", p, flush=True)
    cb, cg = Counter(), Counter()
    for i in range(len(y)):
        (cb if y[i] else cg).update(kb[i].tolist())
    nb, ng = int(y.sum()), int((1 - y).sum())
    top = sorted(((k, np.log((cb.get(k, 0) + 0.5) / (nb + 1)) - np.log((cg.get(k, 0) + 0.5) / (ng + 1))) for k in set(cb) | set(cg)
                  if cb.get(k, 0) + cg.get(k, 0) >= 4), key=lambda kv: -abs(kv[1]))[:30]

    def dec(k):
        lens = "J++" if k >= 33 * V else "J"
        k = k % (33 * V)
        layer, tok = divmod(k, V)
        return f"{lens}/L{'any' if layer == 32 else layer}/{voc[tok]!r}"

    md += ["", "Most lopsided features on all rows (descriptive only, not cross-validated): "
           + "; ".join(f"{dec(k)} bad {cb.get(k, 0)}/{nb} denial {cg.get(k, 0)}/{ng}" for k, _ in top[:20])]
    (HERE / "x17_matched_broad.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (HERE / "x17_matched_broad.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
