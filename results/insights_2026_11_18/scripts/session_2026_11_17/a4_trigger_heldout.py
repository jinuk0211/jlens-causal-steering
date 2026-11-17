import json, sys
import numpy as np
from sklearn.metrics import roc_auc_score

rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
eps = {e["sim"]: e for e in (json.loads(l) for l in open(sys.argv[2], encoding="utf-8"))}
rng = np.random.default_rng(0)


def first_bad(r):
    b = [w for w in r["write_types"] if w["type"] != "match"]
    return b[0] if b else None


def kind(r):
    if r["label"] == "good_write":
        return "good"
    if r["label"] != "bad_write":
        return r["label"]
    w = first_bad(r)
    if w["type"] == "unexpected_tool" and w["name"] == "transfer_to_human_agents":
        return "bad_transfer"
    return "bad_harmful"


def boot_auc(pos, neg, n=2000):
    pos, neg = np.array(pos), np.array(neg)
    y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
    base = roc_auc_score(y, np.r_[pos, neg])
    bs = []
    for _ in range(n):
        p = rng.choice(pos, len(pos)); q = rng.choice(neg, len(neg))
        bs.append(roc_auc_score(y, np.r_[p, q]))
    return base, np.percentile(bs, 2.5), np.percentile(bs, 97.5)


for splits in (("train",), ("validation", "evaluation")):
    R = [r for r in rows if r["split"] in splits]
    pos = [r["trig_score"] for r in R if kind(r) == "bad_harmful"]
    tr = [r["trig_score"] for r in R if kind(r) == "bad_transfer"]
    neg = [r["trig_score"] for r in R if kind(r) == "good"]
    a, lo, hi = boot_auc(pos, neg)
    b, blo, bhi = boot_auc(tr, neg)
    fh = np.mean([s > 0.7155 for s in pos]); ft = np.mean([s > 0.7155 for s in tr]); fg = np.mean([s > 0.7155 for s in neg])
    print(f"{'+'.join(splits):22s} harmful-vs-good AUC {a:.3f} [{lo:.2f},{hi:.2f}] (n={len(pos)} v {len(neg)})   transfer-vs-good {b:.3f} [{blo:.2f},{bhi:.2f}] (n={len(tr)})   fire: harmful {fh:.2f} transfer {ft:.2f} good {fg:.2f}")

print("\n== which tasks contribute the harmful bad writes? (task: n harmful turns, episode reward) ==")
from collections import defaultdict
per = defaultdict(list)
for r in rows:
    if kind(r) == "bad_harmful":
        per[(r["split"], r["task_id"])].append((r["turn"], first_bad(r)["name"], first_bad(r)["type"], first_bad(r)["diff_keys"], r["fired"], eps.get(r["sim"], {}).get("reward")))
for k, v in sorted(per.items(), key=lambda kv: -len(kv[1])):
    print(f"  {k}: {len(v)}  {v}")

print("\n== harmful bad writes: was the user's last message a 'yes'? did the agent ask before? ==")
H = [r for r in rows if kind(r) == "bad_harmful"]
G = [r for r in rows if kind(r) == "good"]
for f in ("user_yes_any", "user_yes_start", "asst_asked", "last_is_user"):
    print(f"  {f:15s} harmful {sum(r[f] for r in H)}/{len(H)}   good {sum(r[f] for r in G)}/{len(G)}")

print("\n== sample harmful bad-write turns: last user msg -> generated ==")
for r in H[:14]:
    print(f"--- task {r['task_id']} turn {r['turn']} ({r['split']}) fired={r['fired']} score={r['trig_score']:+.2f} {first_bad(r)['name']} {first_bad(r)['type']} diff={first_bad(r)['diff_keys']}")
    print("   USER:", r["last_user"][:300].replace("\n", " "))
    print("   GEN :", r["gen"][:300].replace("\n", " "))
