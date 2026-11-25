import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
JC = HERE.parent
D = Path(sys.argv[1]) if len(sys.argv) > 1 else JC / "out/explore"
B = JC / "out/stage2b"
CONV = {"other_tool", "text"}
NEGT = re.compile(r"((cannot|can't|can not|unable to|not able to|won't|will not|should not|shouldn't|do not|don't|not)\s+(\w+\s+){0,3}"
                  r"(transfer|escalat|connect))|((only|until|unless|before)\b[^.!?\n]{0,80}(transfer|human agent))", re.I)
AFF = re.compile(r"(transfer(ring)?|connect(ing)?|escalat\w*)\b[^.!?\n]{0,40}\byou|human agent|representative|supervisor", re.I)


def reclass(r):
    if r["outcome"] != "verbal_transfer":
        return r["outcome"]
    body = r.get("after_think") or r["text"]
    sents = re.split(r"[.!?\n]+", body)
    if any(AFF.search(x) and not NEGT.search(x) for x in sents):
        return "verbal_transfer"
    return "text_rc"


def sign_p(a, b):
    n = a + b
    return None if n == 0 else sum(math.comb(n, k) for k in range(a, n + 1)) / 2 ** n


def load(path):
    return {(r["sim"], r["turn"]): r for r in map(json.loads, path.open(encoding="utf-8"))}


def main():
    c0 = load(B / "rows_C0.jsonl")
    gate = {(g["sim"], g["turn"]): g["J_pairs_oof"] for g in json.loads((JC / "out/stage2b_gate.json").read_text(encoding="utf-8"))}
    thr = {}
    for f in (0, 1):
        thr[f] = float(np.percentile([gate[k] for k, r in c0.items() if r["fold"] == 1 - f and r["y"] == 0], 80))
    flag = {k: gate[k] > thr[r["fold"]] for k, r in c0.items()}
    cfgs = {}
    for p in sorted(D.glob("rows_*.jsonl")) + sorted(B.glob("rows_*.jsonl")):
        cfgs.setdefault(p.stem[5:], load(p))
    md = ["# J-Cascade exploration: regenerated transfer turns (19 bad, 56 good), each compared with C0 on the same rows", "",
          "| config | rows | bad converted | bad conv. (negation-aware, exploratory) | good kept | degenerate | bad: converted only here / only C0 (sign p) | good: lost transfer vs C0 | "
          "changed prompt rows | gated bad conv | gated good kept |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    out = {}
    for cfg, R in cfgs.items():
        bad = [k for k, r in R.items() if r["y"] == 1]
        good = [k for k, r in R.items() if r["y"] == 0]
        conv = lambda RR, k: RR[k]["outcome"] in CONV
        a = sum(1 for k in bad if k in c0 and conv(R, k) and not conv(c0, k))
        b = sum(1 for k in bad if k in c0 and conv(c0, k) and not conv(R, k))
        lost = sum(1 for k in good if k in c0 and c0[k]["outcome"] == "transfer" and R[k]["outcome"] != "transfer")
        G = {k: (R[k] if flag.get(k) else c0[k]) for k in R if k in c0}
        gb = [k for k in G if G[k]["y"] == 1]
        gg = [k for k in G if G[k]["y"] == 0]
        rc = lambda RR, k: reclass(RR[k]) in CONV | {"text_rc"}
        o = {"rows": len(R), "bad_conv": sum(conv(R, k) for k in bad) / max(len(bad), 1),
             "bad_conv_rc": sum(rc(R, k) for k in bad) / max(len(bad), 1), "n_rc": sum(reclass(r) == "text_rc" for r in R.values()),
             "good_kept": sum(R[k]["outcome"] == "transfer" for k in good) / max(len(good), 1),
             "degenerate": sum(r["outcome"] == "degenerate" for r in R.values()) / max(len(R), 1),
             "vs_c0": [a, b, sign_p(a, b)], "good_lost": lost,
             "changed": sum(1 for r in R.values() if r.get("changed", True)),
             "gated_bad_conv": sum(G[k]["outcome"] in CONV for k in gb) / max(len(gb), 1),
             "gated_good_kept": sum(G[k]["outcome"] == "transfer" for k in gg) / max(len(gg), 1),
             "bad_outcomes": dict(Counter(R[k]["outcome"] for k in bad)),
             "by_domain_bad_conv": {d: f"{sum(conv(R, k) for k in bad if R[k]['domain'] == d)}/{sum(R[k]['domain'] == d for k in bad)}"
                                    for d in sorted({R[k]["domain"] for k in bad})}}
        out[cfg] = o
        p = "-" if o["vs_c0"][2] is None else f"{o['vs_c0'][2]:.3f}"
        md.append(f"| {cfg} | {o['rows']} | {o['bad_conv']:.0%} {o['by_domain_bad_conv']} | {o['bad_conv_rc']:.0%} (rc {o['n_rc']}) | {o['good_kept']:.0%} | {o['degenerate']:.0%} | "
                  f"{a} / {b} (p {p}) | {lost} | {o['changed']} | {o['gated_bad_conv']:.0%} | {o['gated_good_kept']:.0%} |")
    md += ["", f"gate: stage-0 J_pairs out-of-fold, threshold = 80th percentile of the other fold's good rows; flags bad "
           f"{sum(flag[k] for k, r in c0.items() if r['y'] == 1)}/19, good {sum(flag[k] for k, r in c0.items() if r['y'] == 0)}/56"]
    (D / "explore_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (D / "explore_summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
