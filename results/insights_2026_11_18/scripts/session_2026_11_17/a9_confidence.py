"""Does the model's own output confidence (argument-token logprob) flag harmful writes?"""
import glob, json, os, sys
import numpy as np
from sklearn.metrics import roc_auc_score

tele_root, turns_path = sys.argv[1:3]
rows = {r["record_id"]: r for r in (json.loads(l) for l in open(turns_path, encoding="utf-8"))}
conf = {}
for split in ("train", "validation", "evaluation"):
    for path in glob.glob(os.path.join(tele_root, split, "*.jsonl")):
        for line in open(path, encoding="utf-8"):
            rec = json.loads(line)
            mot = rec["measurement"].get("motorization") or {}
            # first write call's name/args confidence
            out = {}
            for i, c in enumerate(rec["tool_calls"]):
                if c["name"].startswith(("get_", "search_", "list_", "calculate", "think")):
                    continue
                n = mot.get(f"tool_{i}_name", {}).get("mean_final_token_logprob")
                a = mot.get(f"tool_{i}_arguments", {}).get("mean_final_token_logprob")
                out = {"name_lp": n, "args_lp": a}
                break
            conf[rec["record_id"]] = out


def kind(r):
    if r["label"] == "good_write":
        return "good"
    if r["label"] != "bad_write":
        return None
    b = [w for w in r["write_types"] if w["type"] != "match"][0]
    if b["type"] == "unexpected_tool" and b["name"] == "transfer_to_human_agents":
        return "bad_transfer"
    return "bad_" + b["type"]


data = []
for rid, r in rows.items():
    k = kind(r)
    c = conf.get(rid) or {}
    if k and c.get("args_lp") is not None:
        data.append((k, c["name_lp"], c["args_lp"]))
print("n with confidence:", len(data))
for k in ("good", "bad_wrong_args", "bad_unexpected_tool", "bad_transfer"):
    v = [d for d in data if d[0] == k]
    if v:
        print(f"  {k:20s} n={len(v):3d} median args logprob {np.median([d[2] for d in v]):.4f}  median name logprob {np.median([d[1] for d in v]):.5f}")
for pos in (("bad_wrong_args",), ("bad_unexpected_tool",), ("bad_wrong_args", "bad_unexpected_tool")):
    v = [d for d in data if d[0] in pos or d[0] == "good"]
    y = [d[0] in pos for d in v]
    print(f"  {'+'.join(pos):38s} vs good: AUC(low args confidence) {roc_auc_score(y, [-d[2] for d in v]):.3f}   AUC(low name confidence) {roc_auc_score(y, [-d[1] for d in v]):.3f}  (n={sum(y)} v {len(y)-sum(y)})")
