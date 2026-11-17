import json, sys
import numpy as np
from sklearn.metrics import roc_auc_score
R = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
nw = [r for r in R if r["label"] in ("read", "no_call")]
ww = [r for r in R if r["label"] not in ("read", "no_call")]
f = lambda S, c: f"{sum(r['fired'] for r in S if r['user_yes_any'] == c)}/{sum(r['user_yes_any'] == c for r in S)}"
print("baseline (gpt-5.2 user)")
print("  non-write: fire|yes", f(nw, True), "  fire|not yes", f(nw, False))
print("  write:     fire|yes", f(ww, True), "  fire|not yes", f(ww, False))
# How much of 'bad_write vs rest' AUC does a yes-flag + write-flag explain?
y = np.array([r["label"] == "bad_write" for r in R])
yes = np.array([r["user_yes_any"] for r in R], dtype=float)
s = np.array([r["trig_score"] for r in R])
print(f"  bad_write vs rest: trigger AUC {roc_auc_score(y, s):.3f}   'user said yes' flag alone AUC {roc_auc_score(y, yes):.3f}")
# within-stratum AUC of the trigger (does it add anything beyond 'yes'?)
for c in (True, False):
    idx = yes == c
    if len(set(y[idx])) == 2:
        print(f"  within user_yes={c}: trigger AUC bad_write vs rest {roc_auc_score(y[idx], s[idx]):.3f}  (n_bad={y[idx].sum()}, n={idx.sum()})")
W = np.array([r["label"] in ("bad_write", "good_write") for r in R])
for c in (True, False):
    idx = yes == c
    print(f"  within user_yes={c}: trigger AUC write vs non-write {roc_auc_score(W[idx], s[idx]):.3f}  (n_write={W[idx].sum()}, n={idx.sum()})")
