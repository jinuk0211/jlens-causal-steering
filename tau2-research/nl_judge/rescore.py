import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sims = json.loads((HERE / "retail_all.json").read_text(encoding="utf-8"))
grades = json.loads((HERE / "nl_grades.json").read_text(encoding="utf-8"))
models = sys.argv[1].split(",") if len(sys.argv) > 1 else ["haiku", "sonnet"]


def nl_pass(model, sim_id):
    g = grades.get(f"{model}|{sim_id}")
    if not g or "error" in g:
        return None
    return all(r["metExpectation"] for r in g["results"])


rows = collections.defaultdict(lambda: {"n": 0, "stored": 0, "deferred": 0, "pending": 0,
                                        **{m: 0 for m in models}, **{f"flip_{m}": 0 for m in models}})
agree = collections.Counter()
for s in sims:
    r = rows[s["cond"]]
    r["n"] += 1
    stored = s["reward"] == 1.0
    r["stored"] += stored
    if not s["deferred"]:
        for m in models:
            r[m] += stored
        continue
    r["deferred"] += 1
    verdicts = {}
    for m in models:
        v = nl_pass(m, s["sim_id"])
        verdicts[m] = v
        if v is None:
            r["pending"] += 1 if m == models[0] else 0
            r[m] += stored
            continue
        new = stored and v
        r[m] += new
        r[f"flip_{m}"] += stored and not v
    if len(models) == 2 and None not in verdicts.values():
        agree["agree" if verdicts[models[0]] == verdicts[models[1]] else "disagree"] += 1

print(f"{'cond':16} {'n':>3} {'stored':>7} " + " ".join(f"{m:>8}" for m in models) + "  deferred  flips(" + ",".join(models) + ")")
for cond, r in sorted(rows.items()):
    print(f"{cond:16} {r['n']:3d} {r['stored']:3d} ({r['stored']/r['n']:.0%}) " +
          " ".join(f"{r[m]:3d} ({r[m]/r['n']:.0%})" for m in models) +
          f"  {r['deferred']:3d}      " + ",".join(str(r[f'flip_{m}']) for m in models) +
          (f"  ungraded {r['pending']}" if r["pending"] else ""))
print("judge agreement on deferred sims:", dict(agree))
