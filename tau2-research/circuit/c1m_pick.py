"""C-LOOP C1-M selection (PLAN.md, fixed 11-24 15:3x): from out/c1m/rows_select.jsonl (bad train turns) pick the DoM setting with the
most conversions (outcome text / other_tool), then fewer degenerate (degenerate + capped), then smaller alpha, then scope D, then the
lower layer. Also checks the base reproduction rate (>= 90 % transfer). Prints the setting, or NONE if the reproduction check fails or
the best setting converts nothing. Writes out/c1m/pick.json."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path("/home/project-b/LJW/tau2-steer/probe/circuit/out/c1m")
LATE = {"x15:33", "x15:49"}


def main():
    rows = [json.loads(line) for line in (OUT / "rows_select.jsonl").open(encoding="utf-8")]
    rows = [r for r in rows if r["key"] not in LATE]
    by = defaultdict(Counter)
    n_turns = len({r["key"] for r in rows})
    for r in rows:
        by[r["cond"]][r["outcome"]] += 1
    base = by["base"]
    repro = base["transfer"] / max(1, sum(base.values()))
    cand = []
    for cond, c in by.items():
        if not cond.endswith(":dom"):
            continue
        s = cond.split(":")[0]
        L, a, scope = s.split("_")
        conv = c["text"] + c["other_tool"]
        deg = c["degenerate"] + c["capped"]
        cand.append(((-conv, deg, float(a[1:]), scope != "D", int(L[1:])), s, conv, deg, sum(c.values()),
                     by.get(f"{s}:rand", Counter())))
    cand.sort()
    table = [{"setting": s, "converted": conv, "degenerate": deg, "n": n, "rand_converted": rc["text"] + rc["other_tool"],
              "rand_degenerate": rc["degenerate"] + rc["capped"]} for _, s, conv, deg, n, rc in cand]
    pick = None
    reason = ""
    if repro < 0.9:
        reason = f"base reproduction {repro:.2f} < 0.90"
    elif not cand or cand[0][2] == 0:
        reason = "best setting converts 0 train turns"
    else:
        _, pick, conv, deg, n, _ = cand[0]
        if deg / max(1, n) > 0.10:
            ok = [c for c in cand if c[3] / max(1, c[4]) <= 0.10 and c[2] > 0]
            pick = ok[0][1] if ok else None
            reason = "" if ok else "no setting with conversions and degenerate <= 10 %"
    (OUT / "pick.json").write_text(json.dumps({"turns": n_turns, "base": dict(base), "repro": repro, "pick": pick, "reason": reason,
                                               "table": table}, indent=1), encoding="utf-8")
    print(pick or "NONE")
    print(json.dumps({"turns": n_turns, "repro": repro, "reason": reason, "top": table[:6]}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
