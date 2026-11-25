import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
D = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out/stage2b"
ORDER = ["C0", "P0", "A5", "A20", "A100", "AG20", "RA20", "RA100", "B05", "B1", "B3", "B8", "RB1", "RB8"]
CONTROL = {"A5": "RA20", "A20": "RA20", "AG20": "RA20", "A100": "RA100", "B05": "RB1", "B1": "RB1", "B3": "RB8", "B8": "RB8",
           "P0": "C0", "RA20": "C0", "RA100": "C0", "RB1": "C0", "RB8": "C0"}
METHODS = ["A5", "A20", "A100", "AG20", "B05", "B1", "B3", "B8"]
CONV = {"other_tool", "text"}


def sign_p(a, b):
    n = a + b
    return None if n == 0 else sum(math.comb(n, k) for k in range(a, n + 1)) / 2 ** n


def main():
    rows = {}
    for f in sorted(D.glob("rows_*.jsonl")):
        for r in map(json.loads, f.open(encoding="utf-8")):
            rows.setdefault(r["cfg"], {})[(r["sim"], r["turn"])] = r
    gate = {(g["sim"], g["turn"]): g["J_pairs_oof"] for g in json.loads((HERE / "out/stage2b_gate.json").read_text(encoding="utf-8"))}
    c0 = rows.get("C0", {})
    fold = {k: r["fold"] for k, r in c0.items()}
    thr = {}
    for f in (0, 1):
        good_other = [gate[k] for k, r in c0.items() if r["fold"] == 1 - f and r["y"] == 0 and k in gate]
        thr[f] = float(np.percentile(good_other, 80)) if good_other else float("inf")
    flag = {k: gate.get(k, -1e9) > thr[fold[k]] for k in c0}
    nb = sum(r["y"] == 1 for r in c0.values())
    res = {"threshold": thr, "flagged_bad": f"{sum(flag[k] for k, r in c0.items() if r['y'] == 1)}/{nb}",
           "flagged_good": f"{sum(flag[k] for k, r in c0.items() if r['y'] == 0)}/{len(c0) - nb}", "configs": {}}
    md = ["# J-Cascade stage 2b: causal neuron ablation and paired-prompt DoM steering", "",
          f"gate (stage-0 J_pairs, out-of-fold; threshold = 80th percentile of the other fold's good rows): flags bad {res['flagged_bad']}, "
          f"good {res['flagged_good']}", "",
          "| config | bad converted | good kept | degenerate | vs control (conv only cfg / only control, sign p) | gated bad converted | gated good kept | gated degenerate |",
          "|---|---|---|---|---|---|---|---|"]
    for cfg in [c for c in ORDER if c in rows]:
        R = rows[cfg]
        bad = [k for k, r in R.items() if r["y"] == 1]
        good = [k for k, r in R.items() if r["y"] == 0]
        conv = lambda k, RR: RR[k]["outcome"] in CONV
        o = {"n": len(R), "bad_converted": sum(conv(k, R) for k in bad) / max(len(bad), 1),
             "good_kept": sum(R[k]["outcome"] == "transfer" for k in good) / max(len(good), 1),
             "degenerate": sum(r["outcome"] == "degenerate" for r in R.values()) / max(len(R), 1),
             "bad_outcomes": dict(Counter(R[k]["outcome"] for k in bad)), "good_outcomes": dict(Counter(R[k]["outcome"] for k in good))}
        ctl = rows.get(CONTROL.get(cfg, ""), {})
        a = sum(1 for k in bad if k in ctl and conv(k, R) and not conv(k, ctl))
        b = sum(1 for k in bad if k in ctl and conv(k, ctl) and not conv(k, R))
        o["vs_control"] = [a, b, sign_p(a, b)]
        G = {k: (R[k] if flag.get(k) else c0[k]) for k in R if k in c0}
        gb = [k for k in G if G[k]["y"] == 1]
        gg = [k for k in G if G[k]["y"] == 0]
        o["gated_bad_converted"] = sum(G[k]["outcome"] in CONV for k in gb) / max(len(gb), 1)
        o["gated_good_kept"] = sum(G[k]["outcome"] == "transfer" for k in gg) / max(len(gg), 1)
        o["gated_degenerate"] = sum(G[k]["outcome"] == "degenerate" for k in G) / max(len(G), 1)
        res["configs"][cfg] = o
        p = "-" if o["vs_control"][2] is None else f"{o['vs_control'][2]:.3f}"
        md.append(f"| {cfg} | {o['bad_converted']:.0%} ({o['bad_outcomes']}) | {o['good_kept']:.0%} | {o['degenerate']:.0%} | "
                  f"{CONTROL.get(cfg, '-')}: {a} / {b}, p {p} | {o['gated_bad_converted']:.0%} | {o['gated_good_kept']:.0%} | {o['gated_degenerate']:.0%} |")
    md += ["", "PASS (pre-registered): ungated conversion >= 40 % and >= control + 4/19 with sign p < 0.05; gated conversion >= 40 %, "
           "gated good kept >= 80 %, gated degenerate <= 5 %.", ""]
    for cfg in [c for c in METHODS if c in res["configs"]]:
        o = res["configs"][cfg]
        ctl = res["configs"].get(CONTROL[cfg])
        a, b, p = o["vs_control"]
        checks = {"conv>=40%": o["bad_converted"] >= 0.40, "conv>=ctl+4": ctl is not None and a - b >= 4,
                  "sign p<0.05": p is not None and p < 0.05, "gated conv>=40%": o["gated_bad_converted"] >= 0.40,
                  "gated kept>=80%": o["gated_good_kept"] >= 0.80, "gated degen<=5%": o["gated_degenerate"] <= 0.05}
        o["checks"], o["pass"] = checks, all(checks.values())
        complete = o["n"] == 75 and ctl is not None and ctl["n"] == 75 and len(c0) == 75
        md.append(f"- {cfg}: {'PASS' if o['pass'] else 'FAIL'}{'' if complete else ' (incomplete rows)'}; "
                  + ", ".join(f"{k} {'ok' if v else 'no'}" for k, v in checks.items()))
    prep = D / "prep.json"
    if prep.exists():
        s = json.loads(prep.read_text(encoding="utf-8"))["summary"]
        md += ["", f"necessity (teacher-forced, other fold): mean change of transfer-token log p {s['necessity_mean_dL']}; "
               f"tool-name token still top-1 {s['necessity_top1_kept']}",
               f"set sizes {s['set_sizes']}; paired-DoM norms {s['dom_norm']} vs residual norms {s['h_norm_mean']}; "
               f"DoM cosine between folds {s['dom_cos_folds']}"]
    (D / "summary.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (D / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
