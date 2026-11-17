"""Replicate on the 4B-user detect episodes: trigger vs write imminence vs 'user said yes'."""
import glob, json, os, re, sys
from collections import Counter
import numpy as np
from sklearn.metrics import roc_auc_score
from jlens_causal.vocab_trigger import is_write, label_calls

ep_root, tasks_path = sys.argv[1:3]
tasks = {str(t["id"]): t for t in json.load(open(tasks_path, encoding="utf-8"))}
YES_ANY = re.compile(r"\b(yes|confirm(ed)?|go ahead|proceed)\b", re.I)


def last_msg(ctx):
    segs = ctx.split("<|im_start|>")[1:-1]
    role, _, body = segs[-1].partition("\n")
    body = body.replace("<|im_end|>", "").strip()
    if role == "user" and body.startswith("<tool_response>"):
        role = "tool"
    return role, body


def kind(calls, gold):
    lab = label_calls(calls, gold)
    if lab != "bad_write":
        return lab
    for c in calls:
        if not is_write(c["name"]):
            continue
        same = [a for a in gold if a["name"] == c["name"]]
        if not same:
            return "bad_transfer" if c["name"] == "transfer_to_human_agents" else "bad_harmful"
        if c["name"] != "transfer_to_human_agents":
            return "bad_harmful"
    return "bad_harmful"


for cond in ("detect",):
    rows = []
    for f in glob.glob(os.path.join(ep_root, "s*", "jlens-telemetry", "vt-heldout", cond, "*.jsonl")):
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            vt = (r.get("intervention") or {}).get("vocab_trigger") or {}
            if vt.get("score") is None:
                continue
            gold = tasks[str(r["task_id"])]["evaluation_criteria"]["actions"]
            role, body = last_msg(r["rendered_context"])
            rows.append({"task": str(r["task_id"]), "k": kind(r["tool_calls"], gold), "score": vt["score"], "fired": vt["triggered"],
                         "yes": role == "user" and bool(YES_ANY.search(body))})
    print(f"[{cond}] turns={len(rows)}  kinds={Counter(r['k'] for r in rows)}")
    s = np.array([r["score"] for r in rows]); k = [r["k"] for r in rows]
    W = np.array([x in ("good_write", "bad_transfer", "bad_harmful") for x in k])
    print(f"  write vs non-write AUC {roc_auc_score(W, s):.3f}")
    for pos in (("bad_transfer", "bad_harmful"), ("bad_harmful",), ("bad_transfer",)):
        idx = [i for i, x in enumerate(k) if x in pos or x == "good_write"]
        y = [k[i] in pos for i in idx]
        print(f"  {'+'.join(pos):26s} vs good_write: AUC {roc_auc_score(y, s[idx]):.3f}  (n={sum(y)} v {len(y)-sum(y)})")
    for kk in ("bad_harmful", "bad_transfer", "good_write", "read", "no_call"):
        R = [r for r in rows if r["k"] == kk]
        if R:
            print(f"  fire rate {kk:12s} {sum(r['fired'] for r in R)}/{len(R)}")
    yes = np.array([r["yes"] for r in rows])
    print(f"  'user said yes/confirm/proceed' vs not, ALL turns: score AUC {roc_auc_score(yes, s):.3f}; fire {np.mean([r['fired'] for r in rows if r['yes']]):.2f} vs {np.mean([r['fired'] for r in rows if not r['yes']]):.2f} (n_yes={yes.sum()})")
    nw = [r for r in rows if r["k"] in ("read", "no_call")]
    print(f"  among NON-write turns: fire | yes = {sum(r['fired'] for r in nw if r['yes'])}/{sum(r['yes'] for r in nw)}   fire | not yes = {sum(r['fired'] for r in nw if not r['yes'])}/{sum(not r['yes'] for r in nw)}")
    ww = [r for r in rows if r["k"] not in ("read", "no_call")]
    print(f"  among write turns:     fire | yes = {sum(r['fired'] for r in ww if r['yes'])}/{sum(r['yes'] for r in ww)}   fire | not yes = {sum(r['fired'] for r in ww if not r['yes'])}/{sum(not r['yes'] for r in ww)}")
