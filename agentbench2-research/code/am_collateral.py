"""PC side: T9i collateral table (OVERNIGHT2.md, 11-27 01:2x). Rows of the window edit on the ten AM prompts that are not the two
leaking prompts with the goal (blackmail x4, murder x4, leaking without a goal x2). Per arm, pooled and per scenario: quality kept
(finished, not degenerate, a tool block), tool blocks and emails per response, harmful by the scenario's deterministic check, and,
if OUT_DIR/haiku_classifications.jsonl exists, harmful by the Haiku judge.
Usage: python am_collateral.py OUT_DIR ROWS.jsonl [ROWS.jsonl ...]"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_strict as S
from am_judge_rows import fisher_greater, load


def main(out, files):
    rows = load(files)
    judged = {}
    f = Path(out) / "haiku_classifications.jsonl"
    if f.is_file():
        for line in f.open(encoding="utf-8"):
            j = json.loads(line)
            if "harmful" in j:
                judged[(j["file"].split("/")[1], j["condition"], j["sample_id"])] = j["harmful"]
    by = {}
    for r in rows:
        scen = r["condition"].split("_")[0]
        t = r["text"]
        b = re.findall(r"<tool_use:(\w+)>", t)
        j = judged.get((r["arm"], r["condition"], r["seed"]))
        for key in ((r["arm"], "all"), (r["arm"], scen)):
            c = by.setdefault(key, Counter())
            c["n"] += 1
            c["q"] += (r["end"] != "budget") and (not r["deg"]) and r["tool"]
            c["budget"] += r["end"] == "budget"
            c["blocks"] += len(b)
            c["emails"] += b.count("email")
            c["chk"] += bool(S.am_harmful(scen, t))
            c["tok"] += r["n"]
            if j is not None:
                c["jn"] += 1
                c["jh"] += j
    for scen in ("all", "blackmail", "murder", "leaking"):
        print(f"== {scen}")
        base = by.get(("base", scen))
        for (a, s), c in sorted(by.items()):
            if s != scen:
                continue
            n = c["n"]
            line = (f"  {a:14s} n={n:3d} quality kept={c['q']}/{n} ({c['q'] / n:.0%}) budget cut={c['budget']} tool blocks={c['blocks'] / n:.1f} emails={c['emails'] / n:.1f} "
                    f"check harmful={c['chk']}/{n} mean tokens={c['tok'] / n:.0f}")
            if c["jn"]:
                line += f" judged harmful={c['jh']}/{c['jn']}"
            if base and a != "base":
                line += f" | quality lower than base p={fisher_greater(base['q'], base['n'], c['q'], n):.3g}"
                if c["jn"] and base["jn"]:
                    line += f" | judged harm higher than base p={fisher_greater(c['jh'], c['jn'], base['jh'], base['jn']):.3g}"
            print(line)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
