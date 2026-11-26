"""Report for the AM steering loop (PROTOCOL.md "Analysis", amendment 1). Outcome = deterministic harmful marker.
Unit = (stage, condition, seed); every arm is paired with base of the same unit (same sampling seed).
McNemar exact two-sided p on discordant pairs, Holm over the 10 steered arms within each table.
Usage: python3 am_steer_report.py ROWS_JSONL OUT_MD"""
import json
import sys
from collections import defaultdict
from math import comb

sys.path.insert(0, "/workspace/tj")
from am_markers import degenerate

OWN = {"REP": ("urgency", "replacement"), "RES": ("urgency", "restriction"), "CALM": ("urgency", "none"),
       "AMER": ("goal", "explicit-america")}


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for r, i in enumerate(order):
        run = max(run, (len(ps) - r) * ps[i])
        adj[i] = min(1.0, run)
    return adj


def meta(cond):
    s, g, u = cond.split("_")
    return {"scenario": s, "goal": "explicit-america" if g == "explicit-america" else "none", "urgency": u}


def main():
    rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
    out = sys.argv[2]
    U = defaultdict(dict)
    for r in rows:
        r["degen"] = degenerate(r["text"]) or len(r["text"].strip()) < 20
        U[(r["stage"], r["condition"], r["seed"])][r["arm"]] = r
    units = [u for u in U.values() if "base" in u]
    arms = sorted({a for u in units for a in u if a != "base"}, key=lambda a: (a.split("x")[0] == "RAND", a))
    stages = sorted({r["stage"] for r in rows})
    md = ["# AM steering with the prompt-type reader neurons (Qwen3.5-4B fp16, 2080 Ti): interim/final report", "",
          f"Stages present: {stages}; complete units (condition x seed with base): {len(units)} "
          f"({', '.join(f'{s}: {sum(1 for k in U if k[0] == s)}' for s in stages)}). Outcome = harmful marker (deterministic).",
          "xK = the set's 12 neurons multiplied by K at every position; x0 = ablated. Paired with base on the same (condition, seed).", ""]

    def table(title, sel):
        us = [u for u in units if sel(u["base"]["condition"])]
        if not us:
            return
        nb = sum(u["base"]["marker"] for u in us)
        md.extend([f"## {title}", "", f"{len(us)} units, base harmful marker {nb}/{len(us)} ({nb / len(us):.0%}).", "",
                   "| arm | harmful | base→arm: lost (b) / gained (c) | McNemar p | Holm p | degenerate | hit max | mean tokens |",
                   "|---|---|---|---|---|---|---|---|"])
        res = []
        for a in arms:
            ps = [u for u in us if a in u]
            if not ps:
                continue
            h = sum(u[a]["marker"] for u in ps)
            b = sum(u["base"]["marker"] and not u[a]["marker"] for u in ps)
            c = sum((not u["base"]["marker"]) and u[a]["marker"] for u in ps)
            dg = sum(u[a]["degen"] for u in ps) / len(ps)
            mx = sum(u[a]["stop"] == "max_new" for u in ps) / len(ps)
            tok = sum(u[a]["n_tokens"] for u in ps) / len(ps)
            res.append([a, h, len(ps), b, c, mcnemar(b, c), dg, mx, tok])
        adj = holm([x[5] for x in res])
        bt = sum(u["base"]["n_tokens"] for u in us) / len(us)
        bd = sum(u["base"]["degen"] for u in us) / len(us)
        md.append(f"| base | {nb}/{len(us)} ({nb / len(us):.0%}) | - | - | - | {bd:.0%} | {sum(u['base']['stop'] == 'max_new' for u in us) / len(us):.0%} | {bt:.0f} |")
        for (a, h, n, b, c, p, dg, mx, tok), pa in zip(res, adj):
            flag = " (broken)" if dg > 0.25 else ""
            md.append(f"| {a}{flag} | {h}/{n} ({h / n:.0%}) | {b} / {c} | {p:.3g} | {pa:.3g} | {dg:.0%} | {mx:.0%} | {tok:.0f} |")
        md.append("")

    table("All 18 prompts", lambda c: True)
    for s in ("blackmail", "leaking", "murder"):
        table(f"scenario = {s}", lambda c, s=s: meta(c)["scenario"] == s)
    md += ["## Readout per prompt type: each set on its own prompt type, against base and against RAND with the same multiplier", "",
           "| set | prompts | multiplier | set: harmful vs base (lost/gained, p) | RAND same multiplier: harmful vs base (lost/gained, p) |",
           "|---|---|---|---|---|"]
    for X, (f, v) in OWN.items():
        us = [u for u in units if meta(u["base"]["condition"])[f] == v]
        for mult in sorted({a[len(X) + 1:] for a in arms if a.startswith(X + "x")}, key=float):
            cells = []
            for arm in (f"{X}x{mult}", f"RANDx{mult}"):
                ps = [u for u in us if arm in u]
                if not ps:
                    cells.append("-")
                    continue
                h = sum(u[arm]["marker"] for u in ps)
                hb = sum(u["base"]["marker"] for u in ps)
                b = sum(u["base"]["marker"] and not u[arm]["marker"] for u in ps)
                c = sum((not u["base"]["marker"]) and u[arm]["marker"] for u in ps)
                cells.append(f"{h}/{len(ps)} vs {hb}/{len(ps)} ({b}/{c}, p {mcnemar(b, c):.3g})")
            md.append(f"| {X} | {f} = {v} ({len(us)} units) | x{mult} | {cells[0]} | {cells[1]} |")
    md.append("")
    open(out, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
