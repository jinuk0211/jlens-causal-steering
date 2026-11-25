"""CPU: token ids of the ToolAlign-4B CAUSAL-1 units (53 targets + 159 references) up to the tool-name position, with
the onset, the name position and a context start 300 tokens before the onset, for the trajectory J-lens scan."""
import json
import sys
from pathlib import Path

ROOT = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench")
sys.path.insert(0, str(ROOT / "jlens_experiment"))
from model_profiles import get_profile
from trace_replay import load_traces, render_replay, select_steps
from transformers import AutoTokenizer

out = Path(sys.argv[1])
prof = get_profile("qwen3.5-4b")
tok = AutoTokenizer.from_pretrained(prof.model_id, revision=prof.model_revision)
U = json.loads((ROOT / "ops/analysis/causal/units.json").read_text(encoding="utf-8"))
metas = {m["key"]: m for m in json.loads((ROOT / "ops/analysis/jlens_points/steps.json").read_text(encoding="utf-8"))}
n4 = {}
p4 = Path("/home/project-b/LJW/agentbench2/ana/n4/n4_rows.json")
if p4.is_file():
    for r in json.loads(p4.read_text(encoding="utf-8")):
        if r["variant"] == "original":
            n4.setdefault(r["key"], {"kind": r["kind"], "preamble_tokens": r["preamble_tokens"]})[r["op"]] = r["flip"]
steps = {s.key: s for s in select_steps(load_traces([ROOT / "runner/results/qwen35-greedy"]), scope="all")}
w_id = tok.encode("writeInternalLog", add_special_tokens=False)[0]
rows = []
for label, xs in (("target", U["targets"]), ("reference", U["refs"])):
    for x in xs:
        m = metas[x["key"]]
        rep = render_replay(tok, steps[x["key"]], context_mode="trajectory", expected_model_revision=prof.model_revision)
        ids = list(rep.token_ids)
        assert ids[x["pos"] + 1] == x["next_id"]
        on = [p["pos"] for p in m["positions"] if p["tag"] == "onset"][0]
        rows.append({"key": x["key"], "label": label, "domain": x["domain"], "type": x["type"], "tool": x["tool"],
                     "risk": x["risk"], "category": x["category"], "c": x["c"], "w": w_id,
                     "cand_ids": m["cand_first_ids"][:-1], "cand_names": m["cand_first_names"][:-1],
                     "onset": on, "pos": x["pos"], "ctx_start": max(0, on - 300), "ids": ids[:x["pos"] + 2],
                     "n4": n4.get(x["key"])})
out.write_text(json.dumps(rows), encoding="utf-8")
print(len(rows), "units;", sum(r["label"] == "target" for r in rows), "targets;",
      "mean scanned tokens", sum(r["pos"] - r["ctx_start"] + 1 for r in rows) / len(rows))
