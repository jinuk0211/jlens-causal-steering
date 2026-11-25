"""J-Cascade stage 0 (pre-registered 11-20, PLAN.md): is the 5-layer J-lens cascade at transfer decisions better than simple cues?
Rows: transfer_to_human_agents decision turns. bad = flagged unexpected_transfer in a failed episode; good = transfer in a passed episode.
Scores (5-fold CV grouped by task):
  J_cascade  a-priori: L20 inability, L22 apology, L24 understanding, L26 acknowledgement, L29 justification;
             per layer (101 - best family rank) / 100 from the J-lens decision-point top-100, summed.
  J_pairs    data-driven (layer, word) pairs selected on transfer turns of the training folds (mine.select_pairs).
  baselines  user asked for a human / domain / relative turn position / prior tool errors; and a logistic model on all four.
PASS: best J score AUC >= 0.75 and >= best baseline AUC + 0.05.
Output: mining/stage0.md, stage0.json"""
import gzip
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np

import mine

HERE = Path(__file__).resolve().parent
TOPK = Path(r"C:\Users\h\Documents\ChatGPT\vlm interpretability\work\tau2-topk-20261119")
CASCADE = [
    (20, "inability", {"unable", "cannot", "can't", "无法", "我无法", "无法满足", "不能", "我不能", "impossible"}),
    (22, "apology", {"apologize", "apologies", "sorry", "抱歉", "unfortunately", "regret", "sadly", "apologized"}),
    (24, "understanding", {"理解", "understand", "understanding", "understands", "understood", "明白", "understandable", "明白了"}),
    (26, "acknowledgement", {"acknowledge", "acknowledges", "acknowledging", "acknowledgment", "ack", "sincerely", "recognizing",
                             "recognize", "recogn", "honestly"}),
    (29, "justification", {"given", "based", "since", "既然", "根据您的"}),
]
HUMAN = re.compile(r"\b(human|real person|person|representative|supervisor|manager|agent|transfer|someone else)\b", re.I)


def logistic_fit(X, y, l2=1.0, iters=2000, lr=0.1):
    Xb = np.hstack([X, np.ones((len(X), 1))])
    w = np.zeros(Xb.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-Xb @ w))
        g = Xb.T @ (p - y) / len(y) + l2 * np.r_[w[:-1], 0] / len(y)
        w -= lr * g
    return w


def logistic_score(X, w):
    return np.hstack([X, np.ones((len(X), 1))]) @ w


def main():
    rng = np.random.default_rng(2)
    voc = json.loads(gzip.open(HERE / "vocab.json.gz", "rt", encoding="utf-8").read())
    norm = np.array([v.strip().lower() for v in voc], dtype=object)
    fam_mask = []
    for layer, name, words in CASCADE:
        m = np.array([w in words for w in norm])
        fam_mask.append((layer, name, m))
    turns = json.loads((HERE / "cache_turns.json").read_text(encoding="utf-8"))
    dec = np.load(HERE / "cache_dec.npy")
    meta = {}
    for jf in TOPK.glob("*.json"):
        m = json.loads(jf.read_text(encoding="utf-8"))
        meta[(m["domain"], str(m["task"]), m["sim_id"])] = jf
    rows = []
    by_ep = {}
    for t in turns:
        by_ep.setdefault((t["domain"], t["task"], t["sim"]), []).append(t)
    for key, ts in by_ep.items():
        n_turns = max(x["turn"] for x in ts) + 1
        tr = [t for t in ts if "transfer_to_human_agents" in t["calls"] and "dec_row" in t]
        if not tr:
            continue
        z = np.load(meta[key].with_suffix(".npz"))
        for t in tr:
            bad = any(b.startswith("unexpected_transfer") for b in t["bad"])
            if bad and not t["ep_pass"]:
                y = 1
            elif t["ep_pass"]:
                y = 0
            else:
                continue
            sel_u = np.nonzero((z["ctx_turn"] == t["turn"]) & (z["ctx_seg"] == 0))[0]
            user = "".join(voc[i] for i in z["ctx_tok"][sel_u][np.argsort(z["ctx_pos"][sel_u])])
            sel_t = np.nonzero((z["ctx_turn"] <= t["turn"]) & (z["ctx_seg"] == 1))[0]
            tool_txt = "".join(voc[i] for i in z["ctx_tok"][sel_t])
            ids = dec[t["dec_row"]]
            cas = 0.0
            per = {}
            for layer, name, m in fam_mask:
                hit = m[ids[layer]]
                r = int(hit.argmax() + 1) if hit.any() else 101
                per[name] = r
                cas += (101 - r) / 100
            rows.append({"t": t, "y": y, "group": f"{t['domain']}|{t['task']}", "domain": t["domain"],
                         "user_human": int(bool(HUMAN.search(user))), "rel_pos": t["turn"] / max(n_turns, 1),
                         "tool_errors": tool_txt.count("Error"), "cascade": cas, "ranks": per,
                         "keys": mine.pair_keys(ids)})
    y = np.array([r["y"] for r in rows])
    g = np.array([r["group"] for r in rows])
    dom = np.array([r["domain"] for r in rows])
    folds = np.array([mine.fold_of(x) for x in g])
    doms = sorted(set(dom.tolist()))
    X = np.array([[r["user_human"], r["rel_pos"], np.log1p(r["tool_errors"])] + [float(r["domain"] == d) for d in doms] for r in rows])
    oof = {k: np.zeros(len(rows)) for k in ("J_pairs", "B_logistic", "B_domain")}
    for f in range(mine.NFOLD):
        tr, te = np.nonzero(folds != f)[0], np.nonzero(folds == f)[0]
        if len(set(y[tr].tolist())) < 2:
            continue
        sel, *_ = mine.select_pairs([rows[i]["keys"] for i in tr], y[tr])
        for i in te:
            oof["J_pairs"][i] = mine.score_pairs(rows[i]["keys"], sel)
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-6
        w = logistic_fit((X[tr] - mu) / sd, y[tr])
        oof["B_logistic"][te] = logistic_score((X[te] - mu) / sd, w)
        rate = {d: (y[tr][dom[tr] == d].sum() + y[tr].mean()) / ((dom[tr] == d).sum() + 1) for d in doms}
        oof["B_domain"][te] = [rate[dom[i]] for i in te]
    scores = {"J_cascade": np.array([r["cascade"] for r in rows]), "J_pairs": oof["J_pairs"],
              "B_user_asked_human": np.array([r["user_human"] for r in rows], float),
              "B_rel_pos": np.array([r["rel_pos"] for r in rows]), "B_tool_errors": np.array([r["tool_errors"] for r in rows], float),
              "B_domain": oof["B_domain"], "B_logistic_all": oof["B_logistic"]}
    res = {"n_bad": int(y.sum()), "n_good": int((1 - y).sum()), "by_domain": {f"{d}_{'bad' if l else 'good'}": n for (d, l), n in Counter(zip(dom.tolist(), y.tolist())).items()}, "scores": {}}
    for k, s in scores.items():
        res["scores"][k] = {"auc": mine.auc(s, y), "ci": mine.boot_ci(s, y, g, rng),
                            "by_domain": {d: mine.auc(s[dom == d], y[dom == d]) for d in doms}}
    jbest = max(("J_cascade", "J_pairs"), key=lambda k: res["scores"][k]["auc"] or 0)
    bbest = max((k for k in scores if k.startswith("B_")), key=lambda k: res["scores"][k]["auc"] or 0)
    ja, ba = res["scores"][jbest]["auc"], res["scores"][bbest]["auc"]
    res["pass"] = bool(ja is not None and ja >= 0.75 and ba is not None and ja >= ba + 0.05)
    res["best_j"], res["best_baseline"] = jbest, bbest
    res["layer_rank_medians"] = {name: {"bad": float(np.median([r["ranks"][name] for r in rows if r["y"] == 1])),
                                        "good": float(np.median([r["ranks"][name] for r in rows if r["y"] == 0]))}
                                 for _, name, _ in CASCADE}
    res["user_human_rate"] = {"bad": float(np.mean([r["user_human"] for r in rows if r["y"] == 1])),
                              "good": float(np.mean([r["user_human"] for r in rows if r["y"] == 0]))}
    md = ["# J-Cascade stage 0: transfer decisions only", "",
          f"- bad (unneeded transfer, failed episode) {res['n_bad']}, good (transfer in passed episode) {res['n_good']}; by (domain, label): {res['by_domain']}",
          f"- user asked for a human: bad {res['user_human_rate']['bad']:.2f}, good {res['user_human_rate']['good']:.2f}",
          "", "| score | AUC | 95% CI | " + " | ".join(doms) + " |", "|---|---|---|" + "---|" * len(doms)]
    for k, o in res["scores"].items():
        md.append(f"| {k} | {None if o['auc'] is None else round(o['auc'], 3)} | {o['ci']} | "
                  + " | ".join(str(None if o['by_domain'][d] is None else round(o['by_domain'][d], 3)) for d in doms) + " |")
    md += ["", f"- PRE-REGISTERED PASS (best J >= 0.75 and >= best baseline + 0.05): **{res['pass']}** (best J {jbest} {ja}, best baseline {bbest} {ba})",
           "", "median family rank at its layer (101 = absent):", ""]
    md += [f"- L{l} {name}: bad {res['layer_rank_medians'][name]['bad']}, good {res['layer_rank_medians'][name]['good']}" for l, name, _ in CASCADE]
    (HERE / "stage0.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (HERE / "stage0.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
