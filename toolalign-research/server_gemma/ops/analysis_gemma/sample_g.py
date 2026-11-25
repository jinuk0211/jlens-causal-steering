import json
import random
import sys
from collections import defaultdict
from pathlib import Path

G = Path(sys.argv[1])
CAP = {"clearly-misaligned": 45, "boundary": 30, "aligned": 15}
u = json.loads((G / "causal/units.json").read_text(encoding="utf-8"))
keep = []
for risk, cap in CAP.items():
    byd = defaultdict(list)
    for x in u["targets"]:
        if x["risk"] == risk:
            byd[x["domain"]].append(f"{x['key']}@{x['pos']}")
    rng = random.Random(0)
    for d in byd:
        rng.shuffle(byd[d])
    doms = sorted(byd)
    picked = []
    while len(picked) < cap and any(byd[d] for d in doms):
        for d in doms:
            if byd[d] and len(picked) < cap:
                picked.append(byd[d].pop())
    keep += picked
    print(risk, "available", sum(1 for x in u["targets"] if x["risk"] == risk), "picked", len(picked))
keep += [f"{x['key']}@{x['pos']}" for x in u["refs"]]
(G / "causal2_sample.txt").write_text("\n".join(keep) + "\n", encoding="utf-8")
print("total uids", len(keep))
