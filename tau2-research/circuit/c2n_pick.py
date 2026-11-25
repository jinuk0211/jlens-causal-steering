"""C-LOOP C2-N selection (PLAN.md 17:0x, same tie-break as C1-M): from out/c2n/rows_select.jsonl pick the neuron setting with the
most conversions (text / other_tool) on train bad turns, then fewer degenerate (degenerate + capped), then smaller lambda, then
smaller K; degenerate must be <= 10 %. Prints the setting or NONE; writes out/c2n/pick.json."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path("/home/project-b/LJW/tau2-steer/probe/circuit/out/c2n")


def main():
    rows = [json.loads(line) for line in (OUT / "rows_select.jsonl").open(encoding="utf-8")]
    by = defaultdict(Counter)
    for r in rows:
        by[r["cond"]][r["outcome"]] += 1
    base = by["base"]
    repro = base["transfer"] / max(1, sum(base.values()))
    cand = []
    for cond, c in by.items():
        if not cond.endswith(":neuron"):
            continue
        s = cond.split(":")[0]
        Ks, ls = s.split("_")
        conv = c["text"] + c["other_tool"]
        deg = c["degenerate"] + c["capped"]
        n = sum(c.values())
        rc = by.get(f"{s}:rand", Counter())
        cand.append(((-conv, deg, float(ls[1:]), int(Ks[1:])), s, conv, deg, n, rc["text"] + rc["other_tool"], rc["degenerate"] + rc["capped"]))
    cand.sort()
    ok = [c for c in cand if c[2] > 0 and c[3] / max(1, c[4]) <= 0.10]
    pick = ok[0][1] if (ok and repro >= 0.9) else None
    reason = "" if pick else ("base reproduction < 0.90" if repro < 0.9 else "no setting with conversions and degenerate <= 10 %")
    table = [{"setting": s, "converted": conv, "degenerate": deg, "n": n, "rand_converted": rc, "rand_degenerate": rd}
             for _, s, conv, deg, n, rc, rd in cand]
    (OUT / "pick.json").write_text(json.dumps({"base": dict(base), "repro": repro, "pick": pick, "reason": reason, "table": table}, indent=1),
                                   encoding="utf-8")
    print(pick or "NONE")
    print(json.dumps({"repro": repro, "reason": reason, "table": table}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
