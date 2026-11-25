import json
import shutil
import sys
from pathlib import Path

G = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench/ops/analysis_q9")
out = G / "jlens_points"
out.mkdir(exist_ok=True)
metas = []
for wd in sorted(G.glob("jlens_points_w*")):
    for m in json.loads((wd / "steps.json").read_text(encoding="utf-8")):
        src = wd / f"s_{m['sid']}.npz"
        m = dict(m)
        m["sid"] = len(metas)
        shutil.copyfile(src, out / f"s_{m['sid']}.npz")
        metas.append(m)
(out / "steps.json").write_text(json.dumps(metas, indent=0), encoding="utf-8")
print("merged", len(metas))
