import json
import math
import sys
from collections import Counter
from pathlib import Path

D = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "out/stage2"
CONTROL = {"S1": "R1", "S2": "R1", "S5": "R1", "S6": "R1", "S4": "R47", "S7": "R47", "S47": "R47"}
ORDER = ["C0", "S1", "S2", "S4", "S5", "S6", "S7", "S47", "R1", "R47"]
CONVERTED = {"other_tool", "text"}


def sign_test(a, b):
    n = a + b
    if n == 0:
        return None
    return sum(math.comb(n, k) for k in range(a, n + 1)) / 2 ** n


def main():
    rows = {}
    for f in sorted(D.glob("rows_*.jsonl")):
        for r in map(json.loads, f.open(encoding="utf-8")):
            rows.setdefault(r["cfg"], {})[(r["sim"], r["turn"])] = r
    c0 = rows.get("C0", {})
    res, md = {}, ["# J-Cascade stage 2: offline regeneration of transfer turns", "",
                   f"source {D}; configs present: {sorted(rows, key=ORDER.index)}", ""]
    md += ["| config | n bad | n good | bad converted | good kept transfer | degenerate | bad outcomes | good outcomes | "
           "vs C0 (bad, conv only in cfg / only in C0, sign p) |", "|---|---|---|---|---|---|---|---|---|"]
    for cfg in [c for c in ORDER if c in rows]:
        R = rows[cfg]
        bad = [r for r in R.values() if r["y"] == 1]
        good = [r for r in R.values() if r["y"] == 0]
        conv = sum(r["outcome"] in CONVERTED for r in bad)
        kept = sum(r["outcome"] == "transfer" for r in good)
        deg = sum(r["outcome"] == "degenerate" for r in R.values())
        a = b = 0
        for k, r in R.items():
            if r["y"] != 1 or k not in c0:
                continue
            x, y = r["outcome"] in CONVERTED, c0[k]["outcome"] in CONVERTED
            a += x and not y
            b += y and not x
        res[cfg] = {"n_bad": len(bad), "n_good": len(good), "bad_converted": conv / max(len(bad), 1),
                    "good_kept": kept / max(len(good), 1), "degenerate": deg / max(len(R), 1),
                    "bad_outcomes": dict(Counter(r["outcome"] for r in bad)),
                    "good_outcomes": dict(Counter(r["outcome"] for r in good)),
                    "vs_c0": [a, b, sign_test(a, b)],
                    "by_domain_bad_converted": {d: f"{sum(r['outcome'] in CONVERTED for r in bad if r['domain'] == d)}/"
                                                   f"{sum(r['domain'] == d for r in bad)}" for d in sorted({r['domain'] for r in bad})},
                    "mean_gen": sum(r["n_gen"] for r in R.values()) / max(len(R), 1)}
        o = res[cfg]
        p = "-" if o["vs_c0"][2] is None else f"{o['vs_c0'][2]:.3f}"
        md.append(f"| {cfg} | {o['n_bad']} | {o['n_good']} | {o['bad_converted']:.0%} | {o['good_kept']:.0%} | {o['degenerate']:.0%} | "
                  f"{o['bad_outcomes']} | {o['good_outcomes']} | {o['vs_c0'][0]} / {o['vs_c0'][1]}, p {p} |")
    md += ["", "C0 determinism: share of C0 turns that still call the transfer tool (all rows were logged transfers): "
           + (f"{sum(r['outcome'] == 'transfer' for r in c0.values())}/{len(c0)}" if c0 else "C0 missing"), ""]
    md += ["Pre-registered PASS per config: bad converted >= 40 %, good kept >= 80 %, degenerate <= 5 %, "
           "bad converted above C0 and above its random control (S1/S2/S5/S6 -> R1; S4/S7/S47 -> R47).", ""]
    for cfg in [c for c in ORDER if c in rows and c.startswith("S")]:
        o, ctl = res[cfg], res.get(CONTROL[cfg])
        checks = {"conv>=40%": o["bad_converted"] >= 0.40, "kept>=80%": o["good_kept"] >= 0.80, "degen<=5%": o["degenerate"] <= 0.05,
                  "conv>C0": "C0" in res and o["bad_converted"] > res["C0"]["bad_converted"],
                  f"conv>{CONTROL[cfg]}": ctl is not None and o["bad_converted"] > ctl["bad_converted"]}
        complete = o["n_bad"] == 19 and o["n_good"] == 56 and ctl is not None and ctl["n_bad"] == 19 and "C0" in res and res["C0"]["n_bad"] == 19
        o["checks"], o["pass"], o["complete"] = checks, all(checks.values()), complete
        md.append(f"- {cfg}: {'PASS' if o['pass'] else 'FAIL'}{'' if complete else ' (incomplete rows)'}; "
                  + ", ".join(f"{k} {'ok' if v else 'no'}" for k, v in checks.items()) + f"; bad converted by domain {o['by_domain_bad_converted']}")
    (D / "summary.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (D / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
