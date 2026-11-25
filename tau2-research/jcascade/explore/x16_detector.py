import gzip
import hashlib
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
HAIKU = {"f_detect", "hdetect"}
FAM = {
    "inability": {"unable", "cannot", "can't", "无法", "我无法", "无法满足", "不能", "我不能", "impossible", "couldn"},
    "apology": {"apologize", "apologies", "sorry", "抱歉", "unfortunately", "regret", "sadly", "apologized"},
    "understanding": {"理解", "understand", "understanding", "understands", "understood", "明白", "understandable", "明白了"},
    "acknowledgement": {"acknowledge", "acknowledges", "acknowledging", "acknowledgment", "ack", "sincerely", "recognizing",
                        "recognize", "recogn", "honestly"},
    "transfer": {"transfer", "transferring", "human", "specialist", "representative", "escalate", "supervisor", "agent"},
    "retry": {"check", "alternative", "alternatives", "another", "try", "options", "option", "instead", "let", "look", "explore",
              "other", "verify", "retry", "again"},
    "proceed": {"proceed", "confirm", "confirmed", "alright", "okay", "will", "我将", "我来", "确认", "同意", "perfect"},
    "refusal": {"unfortunately", "cannot", "can't", "unable", "sorry", "apologize", "apologies", "regret", "not"},
    "hesitate": {"wait", "actually", "hmm", "however", "but", "although", "though", "instead"},
    "verify": {"confirm", "verify", "check", "double", "ensure", "sure", "confirmation"},
    "ask": {"could", "would", "please", "?", "question", "clarify", "which"},
    "error": {"error", "failed", "fail", "invalid", "issue", "problem", "wrong", "incorrect"},
    "policy": {"policy", "policies", "rule", "rules", "allowed", "eligible", "permitted", "政策", "规定"},
}
FAMS = list(FAM)


def ihash(x):
    return int(hashlib.md5(('inner|' + x).encode()).hexdigest(), 16)


def logistic_fit(X, y, l2=1.0, iters=800, lr=0.2):
    Xb = np.hstack([X, np.ones((len(X), 1))])
    w = np.zeros(Xb.shape[1])
    pos = max(y.mean(), 1e-3)
    sw = np.where(y == 1, 0.5 / pos, 0.5 / max(1 - pos, 1e-3))
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(Xb @ w, -30, 30)))
        g = Xb.T @ ((p - y) * sw) / len(y) + l2 * np.r_[w[:-1], 0] / len(y)
        w -= lr * g
    return w


def fit_score(Ftr, ytr, Fte, k, l2):
    mu, sd = Ftr.mean(0), Ftr.std(0) + 1e-6
    Ztr, Zte = (Ftr - mu) / sd, (Fte - mu) / sd
    a, b = Ztr[ytr == 1], Ztr[ytr == 0]
    t = (a.mean(0) - b.mean(0)) / np.sqrt(a.var(0) / max(len(a), 1) + b.var(0) / max(len(b), 1) + 1e-6)
    sel = np.argsort(-np.abs(t))[:k]
    w = logistic_fit(Ztr[:, sel], ytr.astype(float), l2=l2)
    return np.hstack([Zte[:, sel], np.ones((len(Zte), 1))]) @ w


def inner_oof(F, y, groups, k, l2, nf=3):
    g = np.array([ihash(x) % nf for x in groups])
    oof = np.zeros(len(y))
    for f in range(nf):
        tr, te = np.nonzero(g != f)[0], np.nonzero(g == f)[0]
        if len(te) == 0 or len(set(y[tr].tolist())) < 2:
            continue
        oof[te] = fit_score(F[tr], y[tr], F[te], k, l2)
    return oof


def nested_cv(F, y, groups, folds, grid):
    oof, thr_flag, chosen = np.zeros(len(y)), np.zeros(len(y), bool), []
    for f in range(mine.NFOLD):
        tr, te = np.nonzero(folds != f)[0], np.nonzero(folds == f)[0]
        if len(te) == 0:
            continue
        best = None
        for k, l2 in grid:
            io = inner_oof(F[tr], y[tr], groups[tr], k, l2)
            a = mine.auc(io, y[tr]) or 0
            if best is None or a > best[0]:
                best = (a, k, l2, io)
        _, k, l2, io = best
        chosen.append((k, l2))
        oof[te] = fit_score(F[tr], y[tr], F[te], k, l2)
        thr = np.percentile(io[y[tr] == 0], 80)
        thr_flag[te] = oof[te] > thr
    return oof, thr_flag, chosen


def jpairs_cv(ids, y, groups, folds):
    keys = [mine.pair_keys(x) for x in ids]
    oof, flag = np.zeros(len(y)), np.zeros(len(y), bool)
    for f in range(mine.NFOLD):
        tr, te = np.nonzero(folds != f)[0], np.nonzero(folds == f)[0]
        if len(te) == 0 or len(set(y[tr].tolist())) < 2:
            continue
        sel, *_ = mine.select_pairs([keys[i] for i in tr], y[tr])
        g = np.array([ihash(x) % 3 for x in groups[tr]])
        io = np.zeros(len(tr))
        for h in range(3):
            a, b = np.nonzero(g != h)[0], np.nonzero(g == h)[0]
            if len(b) == 0 or len(set(y[tr][a].tolist())) < 2:
                continue
            s2, *_ = mine.select_pairs([keys[tr[i]] for i in a], y[tr][a])
            io[b] = [mine.score_pairs(keys[tr[i]], s2) for i in b]
        oof[te] = [mine.score_pairs(keys[i], sel) for i in te]
        flag[te] = oof[te] > np.percentile(io[y[tr] == 0], 80)
    return oof, flag


def fam_features(ids, vals, masks):
    n, L, K = ids.shape
    out = np.zeros((n, L, len(FAMS), 2), np.float32)
    rel = vals.astype(np.float32) - vals[:, :, :1].astype(np.float32)
    floor = rel[:, :, -1:] - 1.0
    for fi, f in enumerate(FAMS):
        hit = masks[f][ids]
        rank = np.where(hit.any(-1), hit.argmax(-1), K)
        out[:, :, fi, 0] = (K - rank) / K
        out[:, :, fi, 1] = np.where(hit, rel, floor).max(-1)
    return out.reshape(n, -1)


def main():
    voc = json.loads(gzip.open(RES / "mining/vocab.json.gz", "rt", encoding="utf-8").read())
    norm = np.array([v.strip().lower() for v in voc], dtype=object)
    masks = {f: np.array([w in ws for w in norm]) for f, ws in FAM.items()}
    rows = json.loads((X15 / "rows.json").read_text(encoding="utf-8"))
    keep, y = [], []
    for r in rows:
        bad = any(b.startswith("unexpected_transfer") for b in r["bad"])
        if bad and not r["ep_pass"]:
            keep.append(r)
            y.append(1)
        elif r["ep_pass"] and not r["provisional"]:
            keep.append(r)
            y.append(0)
    y = np.array(y)
    groups = np.array([f"{r['domain']}|{r['task']}" for r in keep])
    folds = np.array([mine.fold_of(g) for g in groups])
    haiku = np.array([r["cond"] in HAIKU for r in keep])
    Z = [np.load(X15 / f"feat_{r['k']}.npz") for r in keep]
    ids_j = np.stack([z["dec_ids_jlens"] for z in Z])
    val_j = np.stack([z["dec_val_jlens"] for z in Z])
    ids_p = np.stack([z["dec_ids_jpp"] for z in Z])
    val_p = np.stack([z["dec_val_jpp"] for z in Z])
    F_j = fam_features(ids_j, val_j, masks)
    F_jp = np.hstack([F_j, fam_features(ids_p, val_p, masks)])
    F_n = np.stack([z["mlp"].astype(np.float32).ravel() for z in Z])
    F_r = np.stack([z["res"][[20, 24, 26]].astype(np.float32).ravel() for z in Z])
    grid = [(k, l2) for k in (10, 30, 100) for l2 in (1.0, 10.0)]
    res = {}
    res["D1_J_pairs"] = jpairs_cv(ids_j, y, groups, folds)
    for name, F in (("D2_Jlens_families", F_j), ("D3_Jlens_Jpp_families", F_jp), ("D4_neurons", F_n), ("D5_residual_probe", F_r)):
        oof, flag, chosen = nested_cv(F, y, groups, folds, grid)
        res[name] = (oof, flag)
        print(name, "chosen", Counter(chosen).most_common(3), flush=True)

    def rank(x):
        return np.argsort(np.argsort(x)) / max(len(x) - 1, 1)

    jbest = max(("D1_J_pairs", "D2_Jlens_families", "D3_Jlens_Jpp_families"), key=lambda k: mine.auc(res[k][0][haiku], y[haiku]) or 0)
    ens = rank(res[jbest][0]) + rank(res["D4_neurons"][0])
    res["D6_best_J_plus_neurons"] = (ens, None)
    md = ["# X16: detector comparison for unneeded transfers (decision point, unsteered 4B runs)", "",
          f"rows: {len(keep)} (bad {int(y.sum())}, good {int((1 - y).sum())}); by run: "
          + str(dict(Counter((r["cond"].split("_s")[0] if r["cond"].startswith("d7obs") else r["cond"], int(yy)) for r, yy in zip(keep, y)))),
          f"primary set = Haiku-user rows (f_detect + hdetect): bad {int(y[haiku].sum())}, good {int((1 - y[haiku]).sum())}", "",
          "| detector | AUC all | AUC primary | TPR at train-set 20 % FPR (primary) | FPR on primary good |", "|---|---|---|---|---|"]
    for name, (oof, flag) in res.items():
        a_all, a_p = mine.auc(oof, y), mine.auc(oof[haiku], y[haiku])
        if flag is not None:
            tpr = flag[haiku & (y == 1)].mean()
            fpr = flag[haiku & (y == 0)].mean()
            md.append(f"| {name} | {a_all:.3f} | {a_p:.3f} | {tpr:.2f} | {fpr:.2f} |")
        else:
            md.append(f"| {name} | {a_all:.3f} | {a_p:.3f} | - | - |")
    md += ["", f"best J-lens detector on the primary set: {jbest}"]
    c0 = {(r["sim"], r["turn"]): r for r in map(json.loads, (JC / "out/stage2b/rows_C0.jsonl").open(encoding="utf-8"))}
    conv = {"other_tool", "text"}
    md += ["", "system estimate on the 75 f_detect rows (flagged rows take the intervention outcome, others C0):", "",
           "| detector | intervention | flags bad / good | gated bad converted | gated good kept |", "|---|---|---|---|---|"]
    for cfg in ("P1", "P1PF_self", "PF_self", "MID2"):
        p = JC / f"out/explore/rows_{cfg}.jsonl"
        if not p.exists():
            continue
        R = {(r["sim"], r["turn"]): r for r in map(json.loads, p.open(encoding="utf-8"))}
        for name in (jbest, "D4_neurons"):
            flag = res[name][1]
            idx = {(r["sim"], r["turn"]): i for i, r in enumerate(keep) if r["cond"] == "f_detect"}
            nb = ng = cb = kg = fb = fg = 0
            for key, r0 in c0.items():
                i = idx.get(key)
                if i is None:
                    continue
                fl = bool(flag[i])
                out = (R[key] if fl else r0)["outcome"]
                if r0["y"] == 1:
                    nb += 1; fb += fl; cb += out in conv
                else:
                    ng += 1; fg += fl; kg += out == "transfer"
            md.append(f"| {name} | {cfg} | {fb}/{nb} / {fg}/{ng} | {cb / max(nb, 1):.0%} | {kg / max(ng, 1):.0%} |")
    (HERE / "x16_detector.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    np.savez(HERE / "x16_oof.npz", y=y, haiku=haiku, **{k: v[0] for k, v in res.items()})
    print("\n".join(md))


if __name__ == "__main__":
    main()
