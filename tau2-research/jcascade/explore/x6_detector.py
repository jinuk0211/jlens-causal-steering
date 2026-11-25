import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
JC = HERE.parent
RES = JC.parent
sys.path.insert(0, str(RES / "mining"))
import mine

LAYERS = list(range(12, 32))


def logistic_fit(X, y, l2=1.0, iters=1500, lr=0.1):
    Xb = np.hstack([X, np.ones((len(X), 1))])
    w = np.zeros(Xb.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(Xb @ w, -30, 30)))
        g = Xb.T @ (p - y) / len(y) + l2 * np.r_[w[:-1], 0] / len(y)
        w -= lr * g
    return w


def cv_detector(F, y, folds, k):
    oof = np.zeros(len(y))
    for f in range(mine.NFOLD):
        tr, te = np.nonzero(folds != f)[0], np.nonzero(folds == f)[0]
        if len(set(y[tr].tolist())) < 2 or len(te) == 0:
            continue
        mu, sd = F[tr].mean(0), F[tr].std(0) + 1e-6
        Z = (F - mu) / sd
        a, b = Z[tr][y[tr] == 1], Z[tr][y[tr] == 0]
        t = (a.mean(0) - b.mean(0)) / np.sqrt(a.var(0) / max(len(a), 1) + b.var(0) / max(len(b), 1) + 1e-6)
        sel = np.argsort(-np.abs(t))[:k]
        w = logistic_fit(Z[tr][:, sel], y[tr].astype(float), l2=float(k))
        oof[te] = np.hstack([Z[te][:, sel], np.ones((len(te), 1))]) @ w
    return oof


def rank(x):
    return np.argsort(np.argsort(x)) / max(len(x) - 1, 1)


def main():
    turns = json.loads((RES / "mining/cache_turns.json").read_text(encoding="utf-8"))
    lab = {}
    for t in turns:
        if "transfer_to_human_agents" in t["calls"]:
            bad = any(b.startswith("unexpected_transfer") for b in t["bad"])
            y = 1 if (bad and not t["ep_pass"]) else (0 if t["ep_pass"] else None)
            if y is not None:
                lab[(t["domain"], t["sim"], t["turn"])] = (y, f"{t['domain']}|{t['task']}")
    keys = sorted(lab)
    P = np.load(JC / "out/stage2b/prep_np.npz")
    mu, AG, G, keep = P["mu"], P["AG"].astype(np.float32), P["G"].astype(np.float32), P["keep"]
    attr = AG - mu[None] * G
    akeys = [keys[k] for k in keep]
    act = {}
    for f in sorted((JC / "out/neurons").glob("*.npz")):
        z = np.load(f)
        m = json.loads(str(z["meta"]))
        for i, t in enumerate(z["dec_turn"].tolist()):
            k = (m["domain"], m["sim_id"], t)
            if k in lab:
                act[k] = z["dec_a"][i].astype(np.float32)
    rows = [k for k in akeys if k in act]
    y = np.array([lab[k][0] for k in rows])
    folds = np.array([mine.fold_of(lab[k][1]) for k in rows])
    A = np.stack([act[k].ravel() for k in rows])
    T = np.stack([attr[akeys.index(k)].ravel() for k in rows])
    gate = {(g["domain"], g["sim"], g["turn"]): g["J_pairs_oof"] for g in json.loads((JC / "out/stage2b_gate.json").read_text(encoding="utf-8"))}
    jp = np.array([gate[k] for k in rows])
    res = {"n": len(rows), "n_bad": int(y.sum()), "J_pairs_oof": mine.auc(jp, y)}
    lines = ["# X6: can neuron features gate unneeded transfers better than the J-lens word pairs? (5-fold CV grouped by task)", "",
             f"rows {len(rows)} (bad {int(y.sum())}); J_pairs (stage 0, out-of-fold) AUC {res['J_pairs_oof']:.3f}", "",
             "| detector | AUC | rank-average with J_pairs |", "|---|---|---|"]
    best = None
    for name, F in (("activation at decision point", A), ("attribution to transfer tokens", T)):
        for k in (10, 50, 200):
            oof = cv_detector(F, y, folds, k)
            a = mine.auc(oof, y)
            c = mine.auc(rank(oof) + rank(jp), y)
            res[f"{name} k={k}"] = [a, c]
            lines.append(f"| {name}, top-{k} by train-fold t, logistic | {a:.3f} | {c:.3f} |")
            if best is None or a > best[0]:
                best = (a, name, k)
    give = np.zeros((len(LAYERS), 9216), bool)
    for l in range(20, 27):
        give[LAYERS.index(l)] = P[f"give{l}"]
    lines += ["", "label-free scalar scores (no training):", ""]
    for nm, sel in (("attribution summed over give-up readout neurons L20-26", give),
                    ("attribution summed L12-19", np.isin(np.arange(len(LAYERS))[:, None].repeat(9216, 1), [i for i, l in enumerate(LAYERS) if l < 20])),
                    ("attribution summed L20-26", np.isin(np.arange(len(LAYERS))[:, None].repeat(9216, 1), [i for i, l in enumerate(LAYERS) if 20 <= l <= 26])),
                    ("attribution summed L27-31", np.isin(np.arange(len(LAYERS))[:, None].repeat(9216, 1), [i for i, l in enumerate(LAYERS) if l >= 27]))):
        s = np.stack([attr[akeys.index(k)][sel].sum() for k in rows])
        a = mine.auc(s, y)
        res[nm] = a
        lines.append(f"- {nm}: AUC {a:.3f} (bad mean {s[y == 1].mean():.2f}, good mean {s[y == 0].mean():.2f})")
    lines += ["", f"best trained detector: {best[1]} k={best[2]} AUC {best[0]:.3f}. Exploratory: three k values and two feature sets were tried, "
              "so the best number is optimistic."]
    (HERE / "x6_detector.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (HERE / "x6_detector.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
