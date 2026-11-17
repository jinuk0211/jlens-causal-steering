import json, sys
from collections import Counter, defaultdict
import numpy as np
from sklearn.metrics import roc_auc_score

rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]

def auc(pos, neg):
    if not pos or not neg:
        return float("nan")
    y = [1] * len(pos) + [0] * len(neg)
    return roc_auc_score(y, pos + neg)

print("== reproduce: AUC bad vs rest, fires by label ==")
for sp in ("train", "validation", "evaluation"):
    R = [r for r in rows if r["split"] == sp]
    pos = [r["trig_score"] for r in R if r["label"] == "bad_write"]
    neg = [r["trig_score"] for r in R if r["label"] != "bad_write"]
    fires = {lab: f"{sum(r['fired'] for r in R if r['label']==lab)}/{sum(r['label']==lab for r in R)}" for lab in ("bad_write", "good_write", "read", "no_call")}
    gw = [r["trig_score"] for r in R if r["label"] == "good_write"]
    nonw = [r["trig_score"] for r in R if r["label"] in ("read", "no_call")]
    print(f"{sp:10s} bad-vs-rest {auc(pos,neg):.3f} | bad-vs-good {auc(pos,gw):.3f} | write-vs-nonwrite {auc(pos+gw, nonw):.3f} | {fires}")
ALL = rows
pos = [r["trig_score"] for r in ALL if r["label"] == "bad_write"]
gw = [r["trig_score"] for r in ALL if r["label"] == "good_write"]
nonw = [r["trig_score"] for r in ALL if r["label"] in ("read", "no_call")]
print(f"ALL        bad-vs-good {auc(pos,gw):.3f}  write-vs-nonwrite {auc(pos+gw,nonw):.3f}  n bad={len(pos)} good={len(gw)} nonwrite={len(nonw)}")

print("\n== bad-write taxonomy (per turn; first write call) ==")
tax = Counter()
diffkeys = Counter()
byname = Counter()
for r in rows:
    if r["label"] != "bad_write":
        continue
    bad = [w for w in r["write_types"] if w["type"] != "match"]
    w = bad[0]
    tax[w["type"]] += 1
    byname[(w["type"], w["name"])] += 1
    if w["diff_keys"]:
        diffkeys[tuple(w["diff_keys"])] += 1
print(tax)
for k, v in byname.most_common():
    print("  ", v, k)
print("wrong_args diff keys:")
for k, v in diffkeys.most_common(15):
    print("  ", v, k)

print("\n== context before the write (bad vs good), all splits ==")
feats = ["last_is_user", "user_yes_start", "user_yes_any", "asst_asked", "last_tool_error"]
for lab in ("bad_write", "good_write", "read", "no_call"):
    R = [r for r in rows if r["label"] == lab]
    s = "  ".join(f"{f}={sum(r[f] for r in R)}/{len(R)}" for f in feats)
    print(f"{lab:10s} {s}")
print("\n bad-write by type x context:")
for t in ("unexpected_tool", "wrong_args"):
    R = [r for r in rows if r["label"] == "bad_write" and [w for w in r["write_types"] if w["type"] != "match"][0]["type"] == t]
    s = "  ".join(f"{f}={sum(r[f] for r in R)}/{len(R)}" for f in feats)
    fired = sum(r["fired"] for r in R)
    print(f"{t:16s} n={len(R)} fired={fired}  {s}")
R = [r for r in rows if r["label"] == "good_write"]
print(f"{'good_write':16s} n={len(R)} fired={sum(r['fired'] for r in R)}")

print("\n== does a trivial context rule separate bad vs good writes? (AUC, all splits) ==")
W = [r for r in rows if r["label"] in ("bad_write", "good_write")]
y = np.array([r["label"] == "bad_write" for r in W])
for f in feats:
    x = np.array([r[f] for r in W], dtype=float)
    print(f"  {f:16s} AUC(bad|feature) = {roc_auc_score(y, x):.3f}   (1-AUC if negative assoc: {1-roc_auc_score(y, x):.3f})")
x = np.array([r["trig_score"] for r in W])
print(f"  trigger score    AUC = {roc_auc_score(y, x):.3f}")
x = np.array([r["turn"] for r in W], dtype=float)
print(f"  turn index       AUC = {roc_auc_score(y, x):.3f}")
x = np.array([r["prompt_tokens"] for r in W], dtype=float)
print(f"  prompt tokens    AUC = {roc_auc_score(y, x):.3f}")

print("\n== trigger score vs context among ALL turns (what is the trigger reading?) ==")
for f in feats:
    a = [r["trig_score"] for r in rows if r[f]]
    b = [r["trig_score"] for r in rows if not r[f]]
    print(f"  {f:16s} mean score {np.mean(a):+.2f} (n={len(a)}) vs {np.mean(b):+.2f} (n={len(b)})  AUC={auc(a,b):.3f}  fire {np.mean([s>0.7155 for s in a]):.2f} vs {np.mean([s>0.7155 for s in b]):.2f}")
