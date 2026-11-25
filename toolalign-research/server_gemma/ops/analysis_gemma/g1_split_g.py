import json
from collections import defaultdict
from pathlib import Path

G = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench/ops/analysis_gemma")
rows = json.loads((G / "causal/rows.json").read_text(encoding="utf-8"))
units = json.loads((G / "causal/units.json").read_text(encoding="utf-8"))["targets"]
ms = {m["key"]: m for m in json.loads((G / "jlens_points/steps.json").read_text(encoding="utf-8"))}
info = []
for u in units:
    m = ms[u["key"]]
    on = [p["pos"] for p in m["positions"] if p["tag"] == "onset"][0]
    info.append({"pre": u["pos"] - on, "reason": "with-reasoning" in m["condition"]})
groups = {"preamble<10": lambda i: info[i]["pre"] < 10, "preamble>=10": lambda i: info[i]["pre"] >= 10,
          "without-reasoning": lambda i: not info[i]["reason"], "with-reasoning": lambda i: info[i]["reason"]}
by = defaultdict(list)
for r in rows:
    if r["set"] == "target" and r["risk"] != "aligned":
        by[r["op"]].append(r)
fam = defaultdict(list)
for op in by:
    fam[op.split("@")[0]].append(op)
md = ["# G1 split: CAUSAL-1 flips (misaligned+boundary targets) by preamble length and condition", "",
      "| op | " + " | ".join(f"{g} (n={sum(1 for i in range(len(units)) if groups[g](i) and units[i]['risk'] != 'aligned')})" for g in groups) + " |",
      "|---|" + "---|" * len(groups)]
def rate(op, g):
    rs = [r for r in by[op] if groups[g](r["unit"])]
    return (sum(r["flip"] for r in rs), len(rs))
show = []
for f, ops in sorted(fam.items()):
    if len(ops) > 1:
        best = max(ops, key=lambda o: sum(r["flip"] for r in by[o]))
        show.append(best)
    else:
        show += ops
for op in show:
    md.append(f"| {op} | " + " | ".join(f"{a}/{b}" for a, b in (rate(op, g) for g in groups)) + " |")
md += ["", "Families with a layer grid show their best layer over all targets (max flips), so read them as optimistic."]
(G / "causal/report_g1.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print("\n".join(md))
