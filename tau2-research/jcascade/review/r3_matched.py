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
CASCADE = [(20, {"unable", "cannot", "can't", "无法", "我无法", "无法满足", "不能", "我不能", "impossible"}),
           (24, {"理解", "understand", "understanding", "understands", "understood", "明白", "understandable", "明白了"}),
           (26, {"acknowledge", "acknowledges", "acknowledging", "acknowledgment", "ack", "sincerely", "recognizing", "recognize", "recogn", "honestly"})]


def auc(s, y):
    s, y = np.asarray(s, float), np.asarray(y)
    p, n = s[y == 1], s[y == 0]
    if len(p) == 0 or len(n) == 0:
        return None
    return float(((p[:, None] > n[None]).sum() + 0.5 * (p[:, None] == n[None]).sum()) / (len(p) * len(n)))


def cluster_ci(s, y, cl, rng, B=3000):
    s, y, cl = np.asarray(s, float), np.asarray(y), np.asarray(cl)
    ids = sorted(set(cl.tolist()))
    idx = {c: np.nonzero(cl == c)[0] for c in ids}
    out = []
    for _ in range(B):
        pick = np.concatenate([idx[c] for c in rng.choice(ids, len(ids))])
        a = auc(s[pick], y[pick])
        if a is not None:
            out.append(a)
    return [round(float(np.percentile(out, 2.5)), 3), round(float(np.percentile(out, 97.5)), 3)]


def logistic(Xtr, ytr, Xte, l2=10.0, iters=800, lr=0.2):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
    A, B = (Xtr - mu) / sd, (Xte - mu) / sd
    A = np.hstack([A, np.ones((len(A), 1))])
    B = np.hstack([B, np.ones((len(B), 1))])
    w = np.zeros(A.shape[1])
    pos = max(ytr.mean(), 1e-3)
    sw = np.where(ytr == 1, 0.5 / pos, 0.5 / max(1 - pos, 1e-3))
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(A @ w, -30, 30)))
        g = A.T @ ((p - ytr) * sw) / len(ytr) + l2 * np.r_[w[:-1], 0] / len(ytr)
        w -= lr * g
    return B @ w


def folds_of(groups, k=5):
    return np.array([mine.fold_of(g) % k for g in groups])


def cv_scores(F, y, groups, k_feat=None):
    f = folds_of(groups)
    oof = np.full(len(y), np.nan)
    for q in range(mine.NFOLD):
        tr, te = np.nonzero(f != q)[0], np.nonzero(f == q)[0]
        if len(te) == 0 or len(set(y[tr].tolist())) < 2:
            continue
        X = F
        if k_feat:
            a, b = F[tr][y[tr] == 1], F[tr][y[tr] == 0]
            t = (a.mean(0) - b.mean(0)) / np.sqrt(a.var(0) / len(a) + b.var(0) / len(b) + 1e-6)
            sel = np.argsort(-np.abs(t))[:k_feat]
            X = F[:, sel]
        oof[te] = logistic(X[tr], y[tr].astype(float), X[te])
    return oof


def main():
    voc = json.loads(__import__("gzip").open(RES / "mining/vocab.json.gz", "rt", encoding="utf-8").read())
    norm = np.array([v.strip().lower() for v in voc], dtype=object)
    masks = [(l, np.array([w in ws for w in norm])) for l, ws in CASCADE]
    turns = json.loads((RES / "mining/cache_turns.json").read_text(encoding="utf-8"))
    nl_pass = {(t["domain"], t["sim"]): t["ep_pass"] for t in turns}
    xr = json.loads((X15 / "rows.json").read_text(encoding="utf-8"))
    dr = json.loads((DEN / "rows.json").read_text(encoding="utf-8"))

    def label(r):
        bad = any(b.startswith("unexpected_transfer") for b in r["bad"])
        ep_pass = nl_pass.get((r["domain"], r["sim"]), r["ep_pass"]) if r["cond"] == "f_detect" else r["ep_pass"]
        if bad and not ep_pass:
            return 1
        if ep_pass and not (r.get("provisional") and r["cond"] != "f_detect"):
            return 0
        return None

    def feats(path):
        z = np.load(path)
        return z["dec_ids_jlens"], z["mlp"].astype(np.float32), z["res"].astype(np.float32)

    X = []
    for r in xr:
        y = label(r)
        if y is None:
            continue
        ids, mlp, res = feats(X15 / f"feat_{r['k']}.npz")
        X.append({"src": "transfer", "y": y, "domain": r["domain"], "task": r["task"], "cond": r["cond"], "sim": r["sim"], "turn": r["turn"],
                  "ids": ids, "mlp": mlp, "res": res})
    D = []
    for r in dr:
        ids, mlp, res = feats(DEN / f"feat_{r['k']}.npz")
        D.append({"src": "denial", "y": 0, "domain": r["domain"], "task": r["task"], "cond": r["cond"], "sim": r["sim"], "turn": r["turn"],
                  "ids": ids, "mlp": mlp, "res": res, "xfer_later": any(t > r["turn"] for t in r["xfer_turns_in_episode"])})
    bad_tasks = {(x["domain"], x["task"]) for x in X if x["y"] == 1}
    md = ["# R3: situation-matched comparison (x15 transfer turns + denial turns from the same unsteered runs)", "",
          f"- transfer rows with a label: bad {sum(x['y'] for x in X)} ({len({(x['domain'], x['task']) for x in X if x['y'] == 1})} tasks), "
          f"good {sum(1 - x['y'] for x in X)}; by cond {dict(Counter(x['cond'] for x in X if x['y'] == 1))} (bad)",
          f"- denial rows {len(D)}; in a bad task {sum((d['domain'], d['task']) in bad_tasks for d in D)}; "
          f"followed by a transfer later in the same episode {sum(d['xfer_later'] for d in D)}", ""]
    rng = np.random.default_rng(3)

    def cascade(ids):
        s = 0.0
        for l, m in masks:
            hit = m[ids[l]]
            s += (101 - (int(hit.argmax()) + 1 if hit.any() else 101)) / 100
        return s

    # (A) stage-0 detector on the bigger sample
    y = np.array([x["y"] for x in X])
    g = [f"{x['domain']}|{x['task']}" for x in X]
    keys = [mine.pair_keys(x["ids"]) for x in X]
    f = folds_of(g)
    jp = np.zeros(len(X))
    sel_by_fold = {}
    for q in range(mine.NFOLD):
        tr, te = np.nonzero(f != q)[0], np.nonzero(f == q)[0]
        if len(set(y[tr].tolist())) < 2:
            continue
        sel, *_ = mine.select_pairs([keys[i] for i in tr], y[tr])
        sel_by_fold[q] = sel
        for i in te:
            jp[i] = mine.score_pairs(keys[i], sel)
    cas = np.array([cascade(x["ids"]) for x in X])
    md += ["## (A) bad vs good transfer, bigger sample (task-grouped 5-fold)", "",
           f"- J_pairs AUC {auc(jp, y):.3f}, cluster CI {cluster_ci(jp, y, g, rng)}",
           f"- a-priori cascade (L20 inability + L24 understanding + L26 acknowledgement) AUC {auc(cas, y):.3f}, cluster CI {cluster_ci(cas, y, g, rng)}", ""]
    # (B) does the detector separate a bad transfer from a denial in the same refusal situation?
    dk = [mine.pair_keys(d["ids"]) for d in D]
    dg = [f"{d['domain']}|{d['task']}" for d in D]
    df = folds_of(dg)
    djp = np.array([mine.score_pairs(dk[i], sel_by_fold.get(df[i], {})) if df[i] in sel_by_fold else 0.0 for i in range(len(D))])
    dcas = np.array([cascade(d["ids"]) for d in D])
    bad_idx = [i for i, x in enumerate(X) if x["y"] == 1]
    md += ["## (B) bad transfer vs denial (y=1 bad transfer, y=0 denial)", "",
           "| comparison | n bad / n denial | J_pairs AUC (cluster CI) | cascade AUC (cluster CI) |", "|---|---|---|---|"]
    res_b = {}
    d_task = [i for i, d in enumerate(D) if (d["domain"], d["task"]) in bad_tasks]
    d_ep = [i for i, d in enumerate(D) if any(X[b]["sim"] == d["sim"] and X[b]["turn"] > d["turn"] for b in bad_idx)]
    comps = (("same task (any run)", d_task, [i for i in bad_idx if g[i] in {dg[j] for j in d_task}]),
             ("same episode, earlier turn, before the transfer", d_ep, [i for i in bad_idx if X[i]["sim"] in {D[j]["sim"] for j in d_ep}]),
             ("same domain (all denials)", list(range(len(D))), bad_idx))
    for name, dsel, bsel in comps:
        if not dsel or not bsel or (name.startswith("same episode") and len(bsel) < 8):
            md.append(f"| {name} | {len(bsel)} / {len(dsel)} | - | - |")
            continue
        s1 = np.r_[jp[bsel], djp[dsel]]
        s2 = np.r_[cas[bsel], dcas[dsel]]
        yy = np.r_[np.ones(len(bsel)), np.zeros(len(dsel))]
        cl = [g[i] for i in bsel] + [dg[i] for i in dsel]
        a1, a2 = auc(s1, yy), auc(s2, yy)
        ci1, ci2 = cluster_ci(s1, yy, cl, rng), cluster_ci(s2, yy, cl, rng)

        def verdict(a, ci):
            if a <= 0.655 or ci[1] < 0.70:
                return "reads the situation"
            if ci[0] >= 0.60:
                return "decision visible"
            return "inconclusive"
        n_tasks = len({g[i] for i in bsel})
        res_b[name] = {"n": [len(bsel), len(dsel)], "bad_tasks": n_tasks, "jp": a1, "jp_ci": ci1, "cas": a2, "cas_ci": ci2,
                       "verdict_jp": verdict(a1, ci1), "verdict_cas": verdict(a2, ci2)}
        md.append(f"| {name} | {len(bsel)} ({n_tasks} tasks) / {len(dsel)} | {a1:.3f} {ci1} -> {verdict(a1, ci1)} | "
                  f"{a2:.3f} {ci2} -> {verdict(a2, ci2)} |")
    good_idx = [i for i, x in enumerate(X) if x["y"] == 0]
    s = np.r_[jp[good_idx], djp]
    yy = np.r_[np.ones(len(good_idx)), np.zeros(len(D))]
    md += ["", f"- reference: good transfer vs all denials, J_pairs AUC {auc(s, yy):.3f}", "",
           "Pre-registered rule (PLAN amendment 11-24): 'reads the situation' if AUC <= 0.655 or the CI upper bound < 0.70; "
           "'decision visible' if the CI lower bound >= 0.60; else inconclusive. M1 = same task, M2 = same episode (reported if >= 8 bad rows).", ""]
    # (C) where is the transfer-vs-deny decision readable at the decision point? (bad transfer vs same-task denial, trained)
    dsel = [i for i, d in enumerate(D) if (d["domain"], d["task"]) in bad_tasks]
    if dsel:
        rows = [X[i] for i in bad_idx if g[i] in {dg[j] for j in dsel}] + [D[j] for j in dsel]
        yy = np.array([1] * (len(rows) - len(dsel)) + [0] * len(dsel))
        grp = [f"{r['domain']}|{r['task']}" for r in rows]
        md += ["## (C) trained probe: bad transfer vs same-task denial, task-grouped CV (where is the decision linearly readable?)", "",
               f"rows: bad {int(yy.sum())}, denial {int((1 - yy).sum())}, task clusters {len(set(grp))}", "",
               "| feature | AUC |", "|---|---|"]
        for l in range(0, 32, 2):
            F = np.stack([r["res"][l] for r in rows])
            md.append(f"| residual L{l} | {auc(cv_scores(F, yy, grp), yy):.3f} |")
        F = np.stack([r["mlp"].ravel() for r in rows])
        md.append(f"| MLP L12-31 top-200 by t | {auc(cv_scores(F, yy, grp, 200), yy):.3f} |")
    (HERE / "r3_matched.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (HERE / "r3_matched.json").write_text(json.dumps(res_b, indent=1), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
