"""C-LOOP C1 profile test (PLAN.md C1 gate): is there a node, head or source group whose attribution separates bad from good
decisions? Features from C0a (out/c0, symmetric contrast), all divided by m so they are shares of the margin:
layer attention / MLP DLA (64), head total effect grad x input (896 valid heads), total source effect by role summed over the 8
full-attention layers (9) and by layer x role (72), direct source effect by layer x role (72).
Comparison per position type (T-call, T-name with the tool_first rule, T-args) and within each, bad vs good units.
Selection on train tasks (top 10 by |AUC - 0.5|), confirmation on eval tasks: AUC >= 0.75 (or <= 0.25) with the task-cluster
bootstrap CI excluding 0.6 (0.4). Also the per-domain AUC on eval for the selected features. CPU only.
Output probe/circuit/out/c1/profile.md"""
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

C0 = Path("/home/project-b/LJW/tau2-steer/probe/circuit/out/c0")
OUT = Path("/home/project-b/LJW/tau2-steer/probe/circuit/out/c1")
ROLES = ["system", "user_earlier", "user_last", "tool_earlier", "tool_last", "assistant_earlier", "header", "gen", "other"]
FULL = [3, 7, 11, 15, 19, 23, 27, 31]
AIR_TRAIN = {"0", "1", "3", "4", "5", "7", "9", "10", "11", "12", "14", "15", "17", "20", "21", "23", "27", "28", "36", "38", "39",
             "40", "41", "42"}
B = 1000


def split(domain, task):
    if domain == "airline":
        return "train" if task in AIR_TRAIN else "eval"
    return "train" if int(hashlib.md5(f"{domain}|{task}".encode()).hexdigest(), 16) % 2 == 0 else "eval"


def auc(pos, neg):
    pos, neg = np.asarray(pos), np.asarray(neg)
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    allv = np.concatenate([pos, neg])
    order = allv.argsort(kind="mergesort")
    ranks = np.empty(len(allv))
    ranks[order] = np.arange(1, len(allv) + 1)
    for v in np.unique(allv):
        idx = allv == v
        if idx.sum() > 1:
            ranks[idx] = ranks[idx].mean()
    return (ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def boot_ci(x, y, task, rng):
    tasks = np.unique(task)
    by = {t: np.where(task == t)[0] for t in tasks}
    vals = []
    for _ in range(B):
        pick = rng.choice(tasks, size=len(tasks), replace=True)
        idx = np.concatenate([by[t] for t in pick])
        vals.append(auc(x[idx][y[idx] == 1], x[idx][y[idx] == 0]))
    vals = np.array(vals)
    vals = vals[~np.isnan(vals)]
    return (np.percentile(vals, 2.5), np.percentile(vals, 97.5)) if len(vals) else (np.nan, np.nan)


def main():
    rows = json.loads((C0 / "units.json").read_text(encoding="utf-8"))
    names = ([f"attnDLA_L{i}" for i in range(32)] + [f"mlpDLA_L{i}" for i in range(32)]
             + [f"head_L{i}h{h}" for i in range(32) for h in range(16 if i in FULL else 32)]
             + [f"tsrc_{r}" for r in ROLES] + [f"tsrc_L{l}_{r}" for l in FULL for r in ROLES]
             + [f"dsrc_L{l}_{r}" for l in FULL for r in ROLES])
    X, meta = [], []
    for r in rows:
        z = np.load(C0 / f"n_{r['k']}.npz")
        m = r["m"] if abs(r["m"]) > 1e-3 else 1e-3
        heads = np.concatenate([z["hgxa"][i, :(16 if i in FULL else 32)] for i in range(32)])
        tr = z["tsrc_role"].sum(1)
        dr = z["src_role"].sum(1)
        f = np.concatenate([z["attn_dla"], z["mlp_dla"], heads, tr.sum(0), tr.ravel(), dr.ravel()]) / m
        X.append(f.astype(np.float32))
        meta.append(dict(k=r["k"], label=r["label"], ptype=r["ptype"], rule=r["rule"], domain=r["domain"], task=str(r["task"]),
                         split=split(r["domain"], str(r["task"])), kind=r["kind"]))
    X = np.stack(X)
    rng = np.random.default_rng(0)
    md = ["# C1 profile test: bad vs good attribution shares (C0a, symmetric contrast)", "",
          f"{len(rows)} units; features: {X.shape[1]}", ""]
    verdicts = []
    for pt, rule in (("T-call", "runnerup"), ("T-name", "tool_first"), ("T-name", "novariant"), ("T-args", "novariant")):
        sel = np.array([m_["ptype"] == pt and m_["rule"] == rule for m_ in meta])
        y = np.array([m_["label"] == "bad" for m_ in meta]).astype(int)
        task = np.array([f"{m_['domain']}|{m_['task']}" for m_ in meta])
        sp = np.array([m_["split"] for m_ in meta])
        dom = np.array([m_["domain"] for m_ in meta])
        tr_ = sel & (sp == "train")
        ev = sel & (sp == "eval")
        nb_tr, ng_tr = int((y[tr_] == 1).sum()), int((y[tr_] == 0).sum())
        nb_ev, ng_ev = int((y[ev] == 1).sum()), int((y[ev] == 0).sum())
        md += [f"## {pt} ({rule}): train bad {nb_tr} / good {ng_tr}; eval bad {nb_ev} / good {ng_ev}", ""]
        if min(nb_tr, ng_tr, nb_ev, ng_ev) < 3:
            md += ["too few units for the train / eval test", ""]
            continue
        a_tr = np.array([auc(X[tr_ & (y == 1), j], X[tr_ & (y == 0), j]) for j in range(X.shape[1])])
        top = np.argsort(-np.abs(np.nan_to_num(a_tr, nan=0.5) - 0.5))[:10]
        md += ["| feature | AUC train | AUC eval | eval CI | eval airline | eval retail | eval telecom | pass |", "|---|---|---|---|---|---|---|---|"]
        for j in top:
            a_ev = auc(X[ev & (y == 1), j], X[ev & (y == 0), j])
            lo, hi = boot_ci(X[ev, j], y[ev], task[ev], rng)
            per = []
            for d in ("airline", "retail", "telecom"):
                msk = ev & (dom == d)
                per.append(auc(X[msk & (y == 1), j], X[msk & (y == 0), j]))
            hi_side = a_tr[j] >= 0.5
            ok = (a_ev >= 0.75 and lo >= 0.6) if hi_side else (a_ev <= 0.25 and hi <= 0.4)
            verdicts.append((pt, rule, names[j], ok))
            md.append(f"| {names[j]} | {a_tr[j]:.2f} | {a_ev:.2f} | {lo:.2f}-{hi:.2f} | " + " | ".join(
                "nan" if np.isnan(p) else f"{p:.2f}" for p in per) + f" | {'PASS' if ok else '-'} |")
        md.append("")
    n_pass = sum(v[3] for v in verdicts)
    md += ["## Verdict", "", f"- {n_pass} of {len(verdicts)} selected features pass on eval (AUC >= 0.75 with CI lower >= 0.6, or the mirror)."]
    md += [f"- PASS: {pt} {rule} {nm}" for pt, rule, nm, ok in verdicts if ok]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "profile.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
