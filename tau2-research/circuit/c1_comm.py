"""C-LOOP C1-N (PLAN.md, pre-registered 11-24 15:5x): neuron communities from the co-occurrence of top attribution neurons
(arXiv 2611.23112), and a bad-vs-good specificity test in matched groups. CPU only.
Score per unit: s = grad x act at the decision position (C0a grad, symmetric contrast; M1 act). Top-K neurons by |s|.
Graph from TRAIN units: neurons in >= MIN_UNITS train top-K lists; edge if z >= Z and n_ij >= 3, z = (n_ij - N p_i p_j) /
sqrt(N p_i p_j (1 - p_i p_j)); networkx Leiden (seed 0, resolution 1) and Louvain as a cross-check; communities >= 5 neurons.
Unit score per community = share of the unit's top-K |s| mass inside the community.
Groups: transfer T-name (bad vs good transfers), T-args (bad vs good of the same tools), T-call (bad vs good of the same tools).
Per group: the community with the largest |AUC - 0.5| on train, tested on eval (AUC >= 0.75 or <= 0.25, task-cluster CI excluding
0.6 / 0.4), plus per-domain eval AUCs. Output probe/circuit/out/c1n/{communities.json, comm.md}"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import numpy as np
from scipy import sparse

sys.path.insert(0, "/home/project-b/LJW/tau2-steer/probe/circuit")
from c1_profile import auc, boot_ci, split

C0 = Path("/home/project-b/LJW/tau2-steer/probe/circuit/out/c0")
M1 = Path("/home/project-b/LJW/tau2-steer/probe/m1/out")
OUT = Path("/home/project-b/LJW/tau2-steer/probe/circuit/out/c1n")
K = 100
MIN_UNITS = 5
Z = 3.0
NN = 9216


def main():
    rows = json.loads((C0 / "units.json").read_text(encoding="utf-8"))
    rows = [r for r in rows if (M1 / f"u_{r['k']}.npz").is_file()]
    top, val = {}, {}
    for r in rows:
        g = np.load(C0 / f"n_{r['k']}.npz")["grad"].astype(np.float32)
        a = np.load(M1 / f"u_{r['k']}.npz")["act"].astype(np.float32)
        s = np.abs((g * a).ravel())
        idx = np.argpartition(-s, K)[:K]
        top[r["k"]] = idx
        val[r["k"]] = s[idx]
        r["split"] = split(r["domain"], str(r["task"]))
    train = [r for r in rows if r["split"] == "train"]
    cnt = Counter(int(i) for r in train for i in top[r["k"]])
    keep = sorted(i for i, c in cnt.items() if c >= MIN_UNITS)
    col = {n: j for j, n in enumerate(keep)}
    data, ri, ci = [], [], []
    for u, r in enumerate(train):
        for i in top[r["k"]]:
            j = col.get(int(i))
            if j is not None:
                ri.append(u)
                ci.append(j)
                data.append(1)
    X = sparse.csr_matrix((data, (ri, ci)), shape=(len(train), len(keep)), dtype=np.float32)
    N = len(train)
    co = (X.T @ X).toarray()
    p = np.diag(co) / N
    E = N * np.outer(p, p)
    var = E * (1 - np.outer(p, p))
    z = (co - E) / np.sqrt(np.maximum(var, 1e-9))
    np.fill_diagonal(z, 0)
    ii, jj = np.where(np.triu((z >= Z) & (co >= 3), 1))
    G = nx.Graph()
    G.add_nodes_from(range(len(keep)))
    G.add_weighted_edges_from((int(a), int(b), float(z[a, b])) for a, b in zip(ii, jj))
    lei = [c for c in nx.community.leiden_communities(G, weight="weight", resolution=1, seed=0) if len(c) >= 5]
    lou = [c for c in nx.community.louvain_communities(G, weight="weight", resolution=1, seed=0) if len(c) >= 5]
    comms = [sorted(keep[j] for j in c) for c in sorted(lei, key=len, reverse=True)]
    lou_sets = [set(keep[j] for j in c) for c in lou]

    def best_jaccard(c):
        c = set(c)
        return max((len(c & s) / len(c | s) for s in lou_sets), default=0.0)

    score = {}
    for r in rows:
        tot = val[r["k"]].sum()
        pos = {int(i): v for i, v in zip(top[r["k"]], val[r["k"]])}
        score[r["k"]] = np.array([sum(pos.get(n, 0.0) for n in c) / tot for c in comms])
    md = ["# C1-N neuron communities (co-occurrence of top-100 |grad x act| neurons, train units)", "",
          f"- units {len(rows)} (train {N}); neurons in >= {MIN_UNITS} train top-{K}: {len(keep)}; edges (z >= {Z}): {G.number_of_edges()}",
          f"- Leiden communities >= 5 neurons: {len(comms)}; Louvain: {len(lou)}", ""]
    md += ["| # | size | layers (count) | Louvain best Jaccard | mean share bad | mean share good | share in transfer units | share in other units |",
           "|---|---|---|---|---|---|---|---|"]
    lab = np.array([r["label"] == "bad" for r in rows])
    is_tr = np.array([r["call"] == "transfer_to_human_agents" for r in rows])
    S = np.stack([score[r["k"]] for r in rows]) if comms else np.zeros((len(rows), 0))
    for ci_, c in enumerate(comms[:30]):
        layers = Counter(n // NN for n in c)
        md.append(f"| {ci_} | {len(c)} | {dict(sorted(layers.items()))} | {best_jaccard(c):.2f} | {S[lab, ci_].mean():.3f} | "
                  f"{S[~lab, ci_].mean():.3f} | {S[is_tr, ci_].mean():.3f} | {S[~is_tr, ci_].mean():.3f} |")
    md.append("")
    groups = {}
    bad_tools_args = {r["call"] for r in rows if r["label"] == "bad" and r["ptype"] == "T-args"}
    bad_tools_call = {r["call"] for r in rows if r["label"] == "bad" and r["ptype"] == "T-call"}
    groups["transfer T-name"] = [i for i, r in enumerate(rows) if r["ptype"] == "T-name" and r["rule"] == "tool_first"
                                 and r["call"] == "transfer_to_human_agents"]
    groups["T-args same tools"] = [i for i, r in enumerate(rows) if r["ptype"] == "T-args" and r["call"] in bad_tools_args]
    groups["T-call same tools"] = [i for i, r in enumerate(rows) if r["ptype"] == "T-call" and r["call"] in bad_tools_call]
    rng = np.random.default_rng(0)
    verdict = []
    for gname, idx in groups.items():
        idx = np.array(idx)
        y = lab[idx].astype(int)
        sp = np.array([rows[i]["split"] for i in idx])
        task = np.array([f"{rows[i]['domain']}|{rows[i]['task']}" for i in idx])
        dom = np.array([rows[i]["domain"] for i in idx])
        tr, ev = sp == "train", sp == "eval"
        md.append(f"## {gname}: train bad {int(y[tr].sum())} / good {int((1 - y[tr]).sum())}; eval bad {int(y[ev].sum())} / good {int((1 - y[ev]).sum())}")
        if min(y[tr].sum(), (1 - y[tr]).sum(), y[ev].sum(), (1 - y[ev]).sum()) < 3 or not comms:
            md += ["too few units", ""]
            continue
        a_tr = np.array([auc(S[idx][tr & (y == 1), c], S[idx][tr & (y == 0), c]) for c in range(len(comms))])
        best = int(np.argmax(np.abs(np.nan_to_num(a_tr, nan=0.5) - 0.5)))
        x = S[idx][:, best]
        a_ev = auc(x[ev & (y == 1)], x[ev & (y == 0)])
        lo, hi = boot_ci(x[ev], y[ev], task[ev], rng)
        hi_side = a_tr[best] >= 0.5
        ok = (a_ev >= 0.75 and lo >= 0.6) if hi_side else (a_ev <= 0.25 and hi <= 0.4)
        per = {d: auc(x[ev & (dom == d) & (y == 1)], x[ev & (dom == d) & (y == 0)]) for d in ("airline", "retail", "telecom")}
        verdict.append((gname, best, ok))
        md += [f"- selected community #{best} (size {len(comms[best])}): train AUC {a_tr[best]:.2f}; eval AUC {a_ev:.2f} "
               f"[{lo:.2f}, {hi:.2f}]; per domain " + ", ".join(f"{d} {v:.2f}" for d, v in per.items()) + f" -> {'PASS' if ok else 'fail'}",
               f"- top-5 train AUCs: " + ", ".join(f"#{c} {a_tr[c]:.2f}" for c in np.argsort(-np.abs(np.nan_to_num(a_tr, nan=0.5) - 0.5))[:5]), ""]
    md += ["## Verdict", ""] + [f"- {g}: community #{c} {'PASSES' if ok else 'does not pass'}" for g, c, ok in verdict]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "communities.json").write_text(json.dumps({"K": K, "keep": len(keep), "edges": G.number_of_edges(),
                                                      "communities": comms, "verdict": verdict}, default=int), encoding="utf-8")
    np.savez(OUT / "scores.npz", S=S, k=np.array([r["k"] for r in rows]))
    (OUT / "comm.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
