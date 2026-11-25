"""Layer-pattern mining on the full unsteered tau2 run (airline 50 + retail 114 + telecom 114), CPU only.

Labels
  W_clean: bad_write in a failed episode (1) vs good_write in a passed episode (0)   [primary]
  W_all:   bad_write (1) vs good_write (0)
  E:       failed (1) vs passed (0) episode
Evaluation: 5-fold cross-validation grouped by (domain, task); anything chosen from data is chosen inside the training folds.
(A) data-driven (layer, word) pairs at the decision point: top-K log-ratio pairs (bad vs good) from the training folds;
    test score = sum of the selected pairs' log-ratios present in the turn's J-lens top-100.
(B) a-priori word families at the decision point: best (family, layer) chosen on the training folds by AUC.
(C) generated-text statistics: L20 top-1 missing from the L31 top-30 (rev20_rate), commitment layer (mean, rate >= L28).
Output: mining/report.md, mining/results.json
"""
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
V = 248320
K_PAIRS = 30
MIN_BAD = 4
SMOOTH = 0.01
NFOLD = 5
NBOOT = 1000


def rank_avg(x):
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), float)
    xs = x[order]
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and xs[j + 1] == xs[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def auc(s, y):
    s, y = np.asarray(s, float), np.asarray(y, int)
    n1, n0 = int(y.sum()), int((1 - y).sum())
    if n1 == 0 or n0 == 0:
        return None
    r = rank_avg(s)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def boot_ci(s, y, g, rng):
    s, y, g = np.asarray(s, float), np.asarray(y, int), np.asarray(g)
    groups = np.array(sorted(set(g.tolist())))
    idx = {x: np.nonzero(g == x)[0] for x in groups}
    vals = []
    for _ in range(NBOOT):
        pick = np.concatenate([idx[x] for x in rng.choice(groups, len(groups))])
        a = auc(s[pick], y[pick])
        if a is not None:
            vals.append(a)
    return [round(float(np.percentile(vals, 2.5)), 3), round(float(np.percentile(vals, 97.5)), 3)] if vals else None


def fold_of(group):
    return int(hashlib.md5(group.encode()).hexdigest(), 16) % NFOLD


def pair_keys(dec):
    layers = np.arange(32, dtype=np.int64)[:, None] * V
    return np.unique((dec.astype(np.int64) + layers).ravel())


def select_pairs(keys_list, y):
    cb, cg = Counter(), Counter()
    nb, ng = int(sum(y)), int(len(y) - sum(y))
    for ks, lab in zip(keys_list, y):
        (cb if lab else cg).update(ks.tolist())
    lr = {}
    for k, c in cb.items():
        if c >= MIN_BAD:
            lr[k] = np.log((c / nb + SMOOTH) / (cg.get(k, 0) / ng + SMOOTH))
    top = sorted(lr.items(), key=lambda kv: -kv[1])[:K_PAIRS]
    return dict(top), cb, cg, nb, ng


def score_pairs(keys, sel):
    return float(sum(sel.get(k, 0.0) for k in keys.tolist()))


def main():
    rng = np.random.default_rng(0)
    turns = json.loads((HERE / "cache_turns.json").read_text(encoding="utf-8"))
    dec = np.load(HERE / "cache_dec.npy")
    voc = json.loads(gzip.open(HERE / "vocab.json.gz", "rt", encoding="utf-8").read())
    fams = list(next(t for t in turns if "fam_rank" in t)["fam_rank"].keys())
    res = {"counts": {}}
    md = ["# J-lens layer-pattern mining: full unsteered tau2 (airline 50 + retail 114 + telecom 114)", ""]

    sets = {}
    for name in ("W_clean", "W_all"):
        rows = []
        for t in turns:
            if "dec_row" not in t:
                continue
            if name == "W_clean":
                if t["label"] == "bad_write" and not t["ep_pass"]:
                    rows.append((t, 1))
                elif t["label"] == "good_write" and t["ep_pass"]:
                    rows.append((t, 0))
            else:
                rows.append((t, 1 if t["label"] == "bad_write" else 0))
        sets[name] = rows
        c = Counter((t["domain"], y) for t, y in rows)
        res["counts"][name] = {f"{d}_{'bad' if y else 'good'}": n for (d, y), n in sorted(c.items())}
    md += [f"- counts: {json.dumps(res['counts'])}", ""]

    for name, rows in sets.items():
        y = np.array([lab for _, lab in rows])
        g = np.array([f"{t['domain']}|{t['task']}" for t, _ in rows])
        dom = np.array([t["domain"] for t, _ in rows])
        folds = np.array([fold_of(x) for x in g])
        keys = [pair_keys(dec[t["dec_row"]]) for t, _ in rows]
        oof_a = np.zeros(len(rows))
        oof_b = np.zeros(len(rows))
        chosen_b = []
        stability = Counter()
        for f in range(NFOLD):
            tr, te = np.nonzero(folds != f)[0], np.nonzero(folds == f)[0]
            sel, *_ = select_pairs([keys[i] for i in tr], y[tr])
            stability.update(sel.keys())
            for i in te:
                oof_a[i] = score_pairs(keys[i], sel)
            best, best_auc = None, -1
            for fam in fams:
                for layer in range(32):
                    s = np.array([-rows[i][0]["fam_rank"][fam][layer] for i in tr])
                    a = auc(s, y[tr])
                    if a is not None and a > best_auc:
                        best, best_auc = (fam, layer), a
            chosen_b.append(best)
            for i in te:
                oof_b[i] = -rows[i][0]["fam_rank"][best[0]][best[1]]
        out = {}
        for tag, s in (("A_pairs", oof_a), ("B_family", oof_b)):
            out[tag] = {"oof_auc": auc(s, y), "ci": boot_ci(s, y, g, rng),
                        "by_domain": {d: auc(s[dom == d], y[dom == d]) for d in sorted(set(dom))}}
        for feat in ("rev20_rate", "commit_mean", "late_commit_rate"):
            s = np.array([t.get(feat, np.nan) for t, _ in rows], float)
            ok = ~np.isnan(s)
            out[f"C_{feat}"] = {"auc": auc(s[ok], y[ok]), "ci": boot_ci(s[ok], y[ok], g[ok], rng),
                                "by_domain": {d: auc(s[ok & (dom == d)], y[ok & (dom == d)]) for d in sorted(set(dom))}}
        fam_table = {}
        for fam in fams:
            fam_table[fam] = [auc(np.array([-t["fam_rank"][fam][layer] for t, _ in rows]), y) for layer in range(32)]
        sel_all, cb, cg, nb, ng = select_pairs(keys, y)
        top_pairs = [{"layer": int(k // V), "word": voc[int(k % V)], "bad_rate": round(cb[k] / nb, 3),
                      "good_rate": round(cg.get(k, 0) / ng, 3), "log_ratio": round(float(v), 2), "folds_selected": stability[k]}
                     for k, v in sel_all.items()]
        layer_hist = Counter(p["layer"] for p in top_pairs)
        out["B_chosen_per_fold"] = chosen_b
        out["family_auc_by_layer"] = fam_table
        out["top_pairs_full_fit"] = top_pairs
        out["pair_layer_histogram"] = dict(sorted(layer_hist.items()))
        res[name] = out
        md += [f"## {name}", "",
               "| score | AUC (out-of-fold) | 95% CI | airline | retail | telecom |", "|---|---|---|---|---|---|"]
        for tag in ("A_pairs", "B_family", "C_rev20_rate", "C_commit_mean", "C_late_commit_rate"):
            o = out[tag]
            a = o.get("oof_auc", o.get("auc"))
            bd = o["by_domain"]
            md.append(f"| {tag} | {a if a is None else round(a, 3)} | {o['ci']} | "
                      + " | ".join(str(None if bd.get(d) is None else round(bd[d], 3)) for d in ("airline", "retail", "telecom")) + " |")
        md += ["", f"- B: (family, layer) chosen per fold: {chosen_b}",
               "- A: layer histogram of the 30 full-fit pairs: " + json.dumps(out["pair_layer_histogram"]),
               "", "| layer | word | bad rate | good rate | log ratio | folds |", "|---|---|---|---|---|---|"]
        md += [f"| L{p['layer']} | {p['word']!r} | {p['bad_rate']} | {p['good_rate']} | {p['log_ratio']} | {p['folds_selected']}/5 |"
               for p in top_pairs]
        md += ["", "family AUC by layer (decision point, higher rank = more present):", "",
               "| family | " + " | ".join(f"L{l}" for l in range(0, 32, 4)) + " | best layer |", "|---" * 10 + "|"]
        for fam in fams:
            v = fam_table[fam]
            bl = int(np.nanargmax([x if x is not None else np.nan for x in v]))
            md.append(f"| {fam} | " + " | ".join(str(None if v[l] is None else round(v[l], 2)) for l in range(0, 32, 4))
                      + f" | L{bl} {round(v[bl], 3)} |")
        md.append("")

    ep = defaultdict(lambda: {"rows": []})
    for t in turns:
        e = ep[(t["domain"], t["task"], t["sim"])]
        e["rows"].append(t)
        e["fail"] = not t["ep_pass"]
    keys_e = sorted(ep)
    y = np.array([int(ep[k]["fail"]) for k in keys_e])
    g = np.array([f"{k[0]}|{k[1]}" for k in keys_e])
    dom = np.array([k[0] for k in keys_e])
    out = {}
    for feat in ("rev20_rate", "late_commit_rate", "commit_mean"):
        s = np.array([np.nanmean([t.get(feat, np.nan) for t in ep[k]["rows"]] or [np.nan]) for k in keys_e])
        ok = ~np.isnan(s)
        out[f"mean_{feat}"] = {"auc": auc(s[ok], y[ok]), "ci": boot_ci(s[ok], y[ok], g[ok], rng),
                               "by_domain": {d: auc(s[ok & (dom == d)], y[ok & (dom == d)]) for d in ("airline", "retail", "telecom")}}
    for fam in fams:
        best = None
        for layer in range(32):
            s = np.array([max(-t["fam_rank"][fam][layer] for t in ep[k]["rows"] if "fam_rank" in t) for k in keys_e])
            a = auc(s, y)
            if a is not None and (best is None or a > best[1]):
                best = (layer, a)
        out[f"family_{fam}_best_layer_insample"] = best
    res["E_episode"] = out
    md += ["## E: failed vs passed episode", "", f"- episodes: fail {int(y.sum())}, pass {int((1 - y).sum())}", "",
           "| score | AUC | 95% CI | airline | retail | telecom |", "|---|---|---|---|---|---|"]
    for k2, o in out.items():
        if isinstance(o, dict):
            bd = o["by_domain"]
            md.append(f"| {k2} | {o['auc'] if o['auc'] is None else round(o['auc'], 3)} | {o['ci']} | "
                      + " | ".join(str(None if bd.get(d) is None else round(bd[d], 3)) for d in ("airline", "retail", "telecom")) + " |")
    md += ["", "- in-sample best layer per family (max over turns; descriptive only): "
           + json.dumps({k2: (v[0], round(v[1], 3)) for k2, v in out.items() if not isinstance(v, dict)})]
    (HERE / "results.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (HERE / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
