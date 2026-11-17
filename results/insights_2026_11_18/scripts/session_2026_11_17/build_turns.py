"""Build a turn table from the baseline tau2 airline telemetry (Qwen3.5-4B, gpt-5.2 user).

Outputs (in out_dir):
  turns.jsonl   one row per agent turn: label, write type, context features, trigger score
  resid.npz     residual vectors keyed "<site>_L<layer>" -> [n_turns, d] (NaN when absent)
"""
import glob
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import torch

from jlens_causal.vocab_trigger import TriggerSpec, is_write, label_calls, load_readout_head

tele_root, tasks_path, model_dir, lens_path, trig_path, out_dir = sys.argv[1:7]
out = Path(out_dir)
out.mkdir(parents=True, exist_ok=True)
tasks = {str(t["id"]): t for t in json.loads(Path(tasks_path).read_text(encoding="utf-8"))}

YES = re.compile(r"^\W*(yes|yeah|yep|sure|ok(ay)?|correct|confirm(ed)?|go ahead|please (do|proceed|go ahead)|proceed|that'?s (right|correct)|sounds good)\b", re.I)
YES_ANY = re.compile(r"\b(yes|confirm(ed)?|go ahead|proceed)\b", re.I)


def split_messages(ctx: str):
    msgs = []
    for seg in ctx.split("<|im_start|>")[1:]:
        role, _, body = seg.partition("\n")
        body = body.replace("<|im_end|>", "").strip()
        if role == "user" and body.startswith("<tool_response>"):
            role = "tool"
        msgs.append((role, body))
    return msgs


def write_type(call, gold):
    name = call["name"]
    same = [a for a in gold if a["name"] == name]
    if not same:
        return "unexpected_tool", None
    if name == "transfer_to_human_agents":
        return "match", None
    args = call.get("arguments") or {}
    best = None
    for a in same:
        ga = a.get("arguments") or {}
        keys = set(ga) | set(args)
        diff = sorted(k for k in keys if json.dumps(ga.get(k), sort_keys=True) != json.dumps(args.get(k), sort_keys=True))
        if best is None or len(diff) < len(best):
            best = diff
    return ("match" if not best else "wrong_args"), best


rows = []
vecs: dict[str, list] = {}
SITES = ["initial_decision", "tool_0_name", "tool_0_arguments"]
LAYERS = [8, 16, 31]
for split in ("train", "validation", "evaluation"):
    for path in sorted(glob.glob(os.path.join(tele_root, split, "*.jsonl"))):
        sim = Path(path).stem
        for line in open(path, encoding="utf-8"):
            rec = json.loads(line)
            tid = str(rec["task_id"])
            gold = tasks[tid]["evaluation_criteria"]["actions"]
            calls = rec["tool_calls"]
            label = label_calls(calls, gold)
            wtypes = []
            for c in calls:
                if is_write(c["name"]):
                    wt, diff = write_type(c, gold)
                    wtypes.append({"name": c["name"], "type": wt, "diff_keys": diff})
            msgs = split_messages(rec["rendered_context"])
            # msgs[-1] is the open assistant turn being generated
            prev = [m for m in msgs[:-1] if m[0] != "system"]
            last_role, last_body = prev[-1] if prev else ("none", "")
            last_user = next((b for r, b in reversed(prev) if r == "user"), "")
            last_asst = next((b for r, b in reversed(prev) if r == "assistant"), "")
            tool_tail = []
            for r, b in reversed(prev):
                if r != "tool":
                    break
                tool_tail.append(b)
            row = {
                "idx": len(rows), "split": split, "sim": sim, "task_id": tid,
                "turn": rec["turn_index"], "record_id": rec["record_id"], "label": label,
                "calls": [{"name": c["name"], "arguments": c.get("arguments")} for c in calls],
                "write_types": wtypes,
                "gold_write_names": sorted({a["name"] for a in gold if is_write(a["name"])}),
                "n_gold_writes": sum(is_write(a["name"]) for a in gold),
                "prompt_tokens": rec["prompt_tokens"], "completion_tokens": rec["completion_tokens"],
                "last_role": last_role,
                "last_is_user": last_role == "user",
                "last_tool_error": any(re.match(r"\s*<tool_response>\s*Error", b) for b in tool_tail),
                "user_yes_start": bool(last_role == "user" and YES.match(last_body)),
                "user_yes_any": bool(last_role == "user" and YES_ANY.search(last_body)),
                "asst_asked": bool(last_asst.rstrip().endswith("?")) or bool(re.search(r"(confirm|proceed)[^.?!]*\?", last_asst, re.I)),
                "n_user_msgs": sum(r == "user" for r, _ in prev),
                "n_tool_msgs": sum(r == "tool" for r, _ in prev),
                "last_user": last_user[:600],
                "last_asst_tail": last_asst[-400:],
                "gen": rec["generated_text"][:1200],
            }
            res = {}
            for item in rec["measurement"].get("residuals", []):
                key = (item["label"], int(item["layer"]))
                res.setdefault(key, []).append((int(item["position"]), item["vector"]))
            for site in SITES:
                for layer in LAYERS:
                    got = sorted(res.get((site, layer), []))
                    for which in ("first", "last"):
                        if site == "initial_decision" and which == "last":
                            continue
                        k = f"{site}_{which}_L{layer}"
                        v = (got[0][1] if which == "first" else got[-1][1]) if got else None
                        vecs.setdefault(k, []).append(v)
            row["n_res_positions"] = {f"{s}_L{l}": len(v) for (s, l), v in res.items()}
            rows.append(row)
    print(split, len(rows), flush=True)

d = 2560
arrays = {}
for k, lst in vecs.items():
    a = np.full((len(lst), d), np.nan, dtype=np.float32)
    for i, v in enumerate(lst):
        if v is not None:
            a[i] = np.asarray(v, dtype=np.float32)
    arrays[k] = a

# J-lens L16 trigger score at the decision point, plus at the tool-name position
import jlens

spec = TriggerSpec.load(trig_path)
head = load_readout_head(model_dir)
lens = jlens.JacobianLens.load(lens_path)
with torch.no_grad():
    for site_key, field in (("initial_decision_first_L16", "trig_score"), ("tool_0_name_first_L16", "trig_score_name")):
        a = arrays[site_key]
        for i, row in enumerate(rows):
            row[field] = None if np.isnan(a[i, 0]) else spec.score_hidden(lens, head, torch.from_numpy(a[i]), 16)
for row in rows:
    row["fired"] = row["trig_score"] is not None and row["trig_score"] > spec.threshold

np.savez_compressed(out / "resid.npz", **arrays)
with open(out / "turns.jsonl", "w", encoding="utf-8") as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
print("done", len(rows))
