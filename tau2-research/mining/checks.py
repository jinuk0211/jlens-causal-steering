"""Confound checks for mine.py (CPU): is the decision-point (layer, word) signal just the tool being called?
1. W_clean without transfer_to_human_agents turns (bad and good).
2. W_clean, wrong_args / unexpected_write bad kinds only (transfers removed).
3. Tool-name-only baseline under the same folds: score = training-fold bad rate of the called tool.
4. Within-tool: A_pairs AUC averaged over tools that have both labels (test folds).
Output: mining/checks.md, mining/checks.json
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import mine

HERE = Path(__file__).resolve().parent


def rows_clean(turns, keep):
    out = []
    for t in turns:
        if "dec_row" not in t or not keep(t):
            continue
        if t["label"] == "bad_write" and not t["ep_pass"]:
            out.append((t, 1))
        elif t["label"] == "good_write" and t["ep_pass"]:
            out.append((t, 0))
    return out


def tool_of(t):
    w = [c for c in t["calls"] if not c.startswith(("get_", "find_", "list_", "search_", "calculate", "think"))]
    return w[0] if w else (t["calls"][0] if t["calls"] else "none")


def evaluate(rows, dec, rng):
    y = np.array([lab for _, lab in rows])
    g = np.array([f"{t['domain']}|{t['task']}" for t, _ in rows])
    dom = np.array([t["domain"] for t, _ in rows])
    tools = np.array([tool_of(t) for t, _ in rows])
    folds = np.array([mine.fold_of(x) for x in g])
    keys = [mine.pair_keys(dec[t["dec_row"]]) for t, _ in rows]
    oof_a, oof_tool, oof_b = np.zeros(len(rows)), np.zeros(len(rows)), np.zeros(len(rows))
    fams = list(rows[0][0]["fam_rank"].keys())
    for f in range(mine.NFOLD):
        tr, te = np.nonzero(folds != f)[0], np.nonzero(folds == f)[0]
        sel, *_ = mine.select_pairs([keys[i] for i in tr], y[tr])
        rate = defaultdict(lambda: [0, 0])
        for i in tr:
            rate[tools[i]][0] += y[i]
            rate[tools[i]][1] += 1
        prior = y[tr].mean()
        best, best_auc = None, -1
        for fam in fams:
            for layer in range(32):
                a = mine.auc(np.array([-rows[i][0]["fam_rank"][fam][layer] for i in tr]), y[tr])
                if a is not None and a > best_auc:
                    best, best_auc = (fam, layer), a
        for i in te:
            oof_a[i] = mine.score_pairs(keys[i], sel)
            b, n = rate.get(tools[i], [0, 0])
            oof_tool[i] = (b + prior) / (n + 1)
            oof_b[i] = -rows[i][0]["fam_rank"][best[0]][best[1]]
    out = {"n_bad": int(y.sum()), "n_good": int((1 - y).sum())}
    for tag, s in (("A_pairs", oof_a), ("B_family", oof_b), ("tool_only", oof_tool), ("A_plus_tool_rank", mine.rank_avg(oof_a) + mine.rank_avg(oof_tool))):
        out[tag] = {"auc": mine.auc(s, y), "ci": mine.boot_ci(s, y, g, rng),
                    "by_domain": {d: mine.auc(s[dom == d], y[dom == d]) for d in ("airline", "retail", "telecom")}}
    within = []
    for tool in sorted(set(tools.tolist())):
        m = tools == tool
        a = mine.auc(oof_a[m], y[m])
        if a is not None:
            within.append((tool, int(y[m].sum()), int((1 - y[m]).sum()), round(a, 3)))
    w = [(nb + ng, a) for _, nb, ng, a in within]
    out["within_tool"] = within
    out["within_tool_weighted_auc"] = round(sum(n * a for n, a in w) / sum(n for n, _ in w), 3) if w else None
    out["bad_tools"] = dict(Counter(tools[y == 1].tolist()).most_common(8))
    return out


def main():
    rng = np.random.default_rng(1)
    turns = json.loads((HERE / "cache_turns.json").read_text(encoding="utf-8"))
    dec = np.load(HERE / "cache_dec.npy")
    variants = {
        "W_clean_all": lambda t: True,
        "W_clean_no_transfer": lambda t: "transfer_to_human_agents" not in t["calls"],
        "W_clean_wrong_args_or_unexpected_write": lambda t: "transfer_to_human_agents" not in t["calls"] and (
            t["label"] == "good_write" or any(b.split(":")[0] in ("wrong_args", "unexpected_write") for b in t["bad"])),
    }
    res = {name: evaluate(rows_clean(turns, keep), dec, rng) for name, keep in variants.items()}
    md = ["# Confound checks (out-of-fold AUC, 5 folds grouped by task)", ""]
    for name, o in res.items():
        md += [f"## {name}: bad {o['n_bad']}, good {o['n_good']}", "", "| score | AUC | 95% CI | airline | retail | telecom |",
               "|---|---|---|---|---|---|"]
        for tag in ("A_pairs", "B_family", "tool_only", "A_plus_tool_rank"):
            x = o[tag]
            md.append(f"| {tag} | {None if x['auc'] is None else round(x['auc'], 3)} | {x['ci']} | "
                      + " | ".join(str(None if x['by_domain'][d] is None else round(x['by_domain'][d], 3)) for d in ("airline", "retail", "telecom")) + " |")
        md += ["", f"- bad turns by tool: {o['bad_tools']}", f"- within-tool A_pairs AUC (tools with both labels): {o['within_tool']}",
               f"- weighted within-tool AUC: {o['within_tool_weighted_auc']}", ""]
    (HERE / "checks.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (HERE / "checks.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
