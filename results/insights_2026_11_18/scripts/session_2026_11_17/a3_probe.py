"""Is bad-vs-good write information present in the raw residual (not just the J-lens vocab)?

Logistic-regression probes on raw residuals, cross-validated with folds grouped by task
(no task in both train and test), repeated over 5 random groupings; permutation null.
"""
import json, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

turns_path, npz_path = sys.argv[1:3]
rows = [json.loads(l) for l in open(turns_path, encoding="utf-8")]
R = np.load(npz_path)
groups_all = np.array([r["task_id"] for r in rows])
trig = np.array([r["trig_score"] for r in rows], dtype=float)
rng = np.random.default_rng(0)


def first_bad(r):
    b = [w for w in r["write_types"] if w["type"] != "match"]
    return b[0] if b else None


def harmful(r):
    w = first_bad(r)
    return w is not None and not (w["type"] == "unexpected_tool" and w["name"] == "transfer_to_human_agents")


def is_transfer_bad(r):
    w = first_bad(r)
    return w is not None and w["type"] == "unexpected_tool" and w["name"] == "transfer_to_human_agents"


def cv_auc(X, y, g, reps=5, C=0.05, pca=None):
    aucs = []
    for rep in range(reps):
        ug = np.unique(g)
        perm = rng.permutation(len(ug))
        remap = {u: perm[i] for i, u in enumerate(ug)}
        gg = np.array([remap[x] for x in g])
        pred = np.zeros(len(y))
        for tr, te in GroupKFold(5).split(X, y, gg):
            if len(np.unique(y[tr])) < 2:
                pred[te] = 0.5
                continue
            steps = [StandardScaler()]
            if pca:
                steps.append(PCA(n_components=min(pca, len(tr) - 1), random_state=0))
            steps.append(LogisticRegression(C=C, max_iter=3000, class_weight="balanced"))
            m = make_pipeline(*steps).fit(X[tr], y[tr])
            pred[te] = m.predict_proba(X[te])[:, 1]
        aucs.append(roc_auc_score(y, pred))
    return float(np.mean(aucs)), float(np.std(aucs))


def perm_null(X, y, g, n=20, **kw):
    vals = []
    for _ in range(n):
        yp = rng.permutation(y)
        vals.append(cv_auc(X, yp, g, reps=1, **kw)[0])
    return np.array(vals)


tasks = {
    "write vs non-write": (lambda r: True, lambda r: r["label"] in ("bad_write", "good_write")),
    "bad vs good write": (lambda r: r["label"] in ("bad_write", "good_write"), lambda r: r["label"] == "bad_write"),
    "harmful-bad vs good": (lambda r: harmful(r) or r["label"] == "good_write", lambda r: harmful(r)),
    "transfer-bad vs good": (lambda r: is_transfer_bad(r) or r["label"] == "good_write", lambda r: is_transfer_bad(r)),
}
sites = ["initial_decision_first_L8", "initial_decision_first_L16", "initial_decision_first_L31",
         "tool_0_name_first_L16", "tool_0_name_first_L31", "tool_0_arguments_last_L16", "tool_0_arguments_last_L31"]

print(f"{'task':22s} {'n+':>4s} {'n-':>4s}  {'L16 trigger':>11s}  " + "  ".join(f"{s.replace('initial_decision_first','dec').replace('tool_0_name_first','name').replace('tool_0_arguments_last','args'):>12s}" for s in sites))
for tname, (sel, lab) in tasks.items():
    idx = np.array([i for i, r in enumerate(rows) if sel(r)])
    y = np.array([lab(rows[i]) for i in idx], dtype=int)
    g = groups_all[idx]
    tr_auc = roc_auc_score(y, trig[idx])
    cells = []
    for s in sites:
        X = R[s][idx]
        ok = ~np.isnan(X[:, 0])
        if ok.sum() < 20 or len(np.unique(y[ok])) < 2 or (tname == "write vs non-write" and not s.startswith("initial")):
            cells.append(f"{'-':>12s}")
            continue
        m, sd = cv_auc(X[ok], y[ok], g[ok])
        cells.append(f"{m:6.3f}±{sd:.3f}")
    print(f"{tname:22s} {y.sum():4d} {len(y)-y.sum():4d}  {tr_auc:11.3f}  " + "  ".join(cells), flush=True)

print("\npermutation null (label-shuffled, grouped CV) for 'bad vs good write' at dec L16 and name L16:")
for s in ("initial_decision_first_L16", "tool_0_name_first_L16"):
    sel, lab = tasks["bad vs good write"]
    idx = np.array([i for i, r in enumerate(rows) if sel(r)])
    X = R[s][idx]
    ok = ~np.isnan(X[:, 0])
    y = np.array([lab(rows[i]) for i in idx], dtype=int)[ok]
    null = perm_null(X[ok], y, groups_all[idx][ok], n=20)
    print(f"  {s}: null mean {null.mean():.3f}  95th pct {np.percentile(null,95):.3f}  max {null.max():.3f}")

print("\nsame tool only (control for tool identity): bad vs good among update_reservation_flights / cancel_reservation writes")
for tool in ("update_reservation_flights", "cancel_reservation"):
    idx = np.array([i for i, r in enumerate(rows) if r["label"] in ("bad_write", "good_write") and any(w["name"] == tool for w in r["write_types"])])
    y = np.array([rows[i]["label"] == "bad_write" for i in idx], dtype=int)
    out = [f"{tool}: n_bad={y.sum()} n_good={len(y)-y.sum()} trigger AUC={roc_auc_score(y, trig[idx]):.3f}"]
    for s in ("initial_decision_first_L16", "tool_0_name_first_L16", "tool_0_arguments_last_L16"):
        X = R[s][idx]
        ok = ~np.isnan(X[:, 0])
        if len(np.unique(y[ok])) < 2:
            continue
        m, sd = cv_auc(X[ok], y[ok], groups_all[idx][ok])
        out.append(f"{s.split('_L')[0][:14]}:{m:.3f}")
    print("  " + "  ".join(out))
