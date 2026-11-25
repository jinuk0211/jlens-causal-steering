"""H1 analysis (PC): name-writing attention heads, where they read from, and whether that separates bad from good calls.

Input: m1/h1_full (pulled probe/m1_heads/full), jcascade/out/x15/rows.json, mining/cache_turns.json (NL-corrected passes).
Transfer labels as X17 / R3 (C): bad = unexpected_transfer and the episode not passing (NL-corrected ep_pass for f_detect);
good = transfer in a passing episode, provisional passes excluded.
A  name-writing heads per group (task-balanced mean DLA), with their J-lens words and main source segment
B  transfers bad vs good: pre-specified head features (the top transfer head from A, chosen without labels), layer totals
   (M1 replication), CV logistic detectors on all head features, turn-only baseline, within-task permutation null
C  writes BW vs GW, matched on the name token
D  source tokens of the top transfer head, bad vs good
Output: m1/h1_report.md, m1/h1_report.json
"""
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE.parent
sys.path.insert(0, str(RES / "mining"))
import mine

H1 = HERE / "h1_full"
X15 = RES / "jcascade/out/x15"
FULL = [3, 7, 11, 15, 19, 23, 27, 31]
SEGS = ["sink", "policy_transfer", "policy_deny", "policy_other", "format_instr", "tool_desc_transfer", "tools_other", "user_last",
        "user_earlier", "tool_results", "assistant_prev", "header_now", "preamble_now"]
NPERM = 200


def logistic(Xtr, ytr, Xte, l2=10.0, iters=600, lr=0.2):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
    A, B = (Xtr - mu) / sd, (Xte - mu) / sd
    A = np.hstack([A, np.ones((len(A), 1))])
    B = np.hstack([B, np.ones((len(B), 1))])
    w = np.zeros(A.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(A @ w, -30, 30)))
        w -= lr * (A.T @ (p - ytr) / len(ytr) + l2 * np.r_[w[:-1], 0] / len(ytr))
    return B @ w


def cv_logit(F, y, folds):
    oof = np.zeros(len(y))
    for q in range(mine.NFOLD):
        tr, te = np.nonzero(folds != q)[0], np.nonzero(folds == q)[0]
        if len(te) == 0 or len(set(y[tr].tolist())) < 2:
            continue
        oof[te] = logistic(F[tr], y[tr].astype(float), F[te])
    return oof


def within_task_auc(s, y, groups):
    num = den = 0.0
    g = np.array(groups)
    for t in set(groups):
        m = g == t
        p, n = s[m & (y == 1)], s[m & (y == 0)]
        if len(p) and len(n):
            num += (p[:, None] > n[None]).sum() + 0.5 * (p[:, None] == n[None]).sum()
            den += len(p) * len(n)
    return float(num / den) if den else None


def resid_on(x, z):
    Z = np.c_[np.ones(len(z)), z, z ** 2]
    beta, *_ = np.linalg.lstsq(Z, x, rcond=None)
    return x - Z @ beta


def task_mean(vals, groups):
    by = defaultdict(list)
    for v, g in zip(vals, groups):
        by[g].append(v)
    return np.mean([np.mean(v, 0) for v in by.values()], 0)


def main():
    rng = np.random.default_rng(5)
    voc = json.loads(gzip.open(RES / "mining/vocab.json.gz", "rt", encoding="utf-8").read())
    units = json.loads((H1 / "units.json").read_text(encoding="utf-8"))
    Z = {u["k"]: np.load(H1 / f"u_{u['k']}.npz") for u in units}
    turns = json.loads((RES / "mining/cache_turns.json").read_text(encoding="utf-8"))
    nl_pass = {(t["domain"], t["sim"]): t["ep_pass"] for t in turns}
    x15 = {(r["domain"], r["cond"], r["sim"], r["turn"]): r for r in json.loads((X15 / "rows.json").read_text(encoding="utf-8"))}
    md = ["# H1: attention heads that write the tool name (teacher-forced at the \"=\" of \"<function=\")", "",
          f"units: {dict(Counter(u['group'] for u in units))}; reproduced (argmax = logged token) {sum(u['reproduced'] for u in units)}/{len(units)}", ""]
    out = {}

    md += ["## A. Name-writing heads (task-balanced mean direct logit attribution to the chosen name token)", ""]
    top_heads = {}
    for grp in ("transfer", "BW", "GW"):
        U = [u for u in units if u["group"] == grp]
        if not U:
            continue
        g = [f"{u['domain']}|{u['task']}" for u in U]
        D = task_mean([Z[u["k"]]["dla_d"] for u in U], g)
        DJ = task_mean([Z[u["k"]]["dla_j"] for u in U], g)
        M = task_mean([Z[u["k"]]["mass"] for u in U], g)
        tot = D.sum()
        md.append(f"### {grp} (n {len(U)}, tasks {len(set(g))}): attention DLA by layer "
                  + ", ".join(f"L{l} {D[i].sum():.2f}" for i, l in enumerate(FULL)) + f"; all heads {tot:.2f}")
        md += ["", "| head | DLA direct | DLA J-lens | share of all-head DLA | J-lens top words (most frequent in top-3) | main source segments (mass) |",
               "|---|---|---|---|---|---|"]
        order = np.dstack(np.unravel_index(np.argsort(-D.ravel()), D.shape))[0][:8]
        top_heads[grp] = [(int(li), int(h)) for li, h in order]
        for li, h in order:
            words = Counter()
            for u in U:
                words.update(voc[i] for i in Z[u["k"]]["top_ids"][li, h, :3])
            segs = sorted(zip(SEGS, M[li, h]), key=lambda kv: -kv[1])[:3]
            md.append(f"| L{FULL[li]}h{h} | {D[li, h]:.2f} | {DJ[li, h]:.2f} | {D[li, h] / tot:.2f} | "
                      f"{', '.join(repr(w) for w, _ in words.most_common(5))} | {', '.join(f'{s} {v:.2f}' for s, v in segs)} |")
        md.append("")
    out["top_heads"] = top_heads

    md += ["## B. Transfers: bad (unneeded, failed episode) vs good (passed episode)", ""]
    rows, y = [], []
    seen = set()
    for u in units:
        if u["group"] != "transfer":
            continue
        key = (u["domain"], u["cond"], u["sim"], u["turn"])
        if key in seen or key not in x15:
            continue
        r = x15[key]
        is_bad = any(b.startswith("unexpected_transfer") for b in r["bad"])
        ep_pass = nl_pass.get((r["domain"], r["sim"]), r["ep_pass"]) if r["cond"] == "f_detect" else r["ep_pass"]
        if is_bad and not ep_pass:
            lab = 1
        elif ep_pass and not r["provisional"]:
            lab = 0
        else:
            continue
        seen.add(key)
        rows.append(u)
        y.append(lab)
    y = np.array(y)
    groups = [f"{u['domain']}|{u['task']}" for u in rows]
    folds = np.array([mine.fold_of(g) for g in groups])
    turn = np.array([u["turn"] for u in rows], float)
    mixed = {g for g in groups if len({yy for gg, yy in zip(groups, y) if gg == g}) == 2}
    md.append(f"rows: bad {int(y.sum())} ({len({g for g, yy in zip(groups, y) if yy})} tasks), good {int((1 - y).sum())} "
              f"({len({g for g, yy in zip(groups, y) if not yy})} tasks); tasks with both labels {len(mixed)}")
    gidx = {g: np.nonzero(np.array(groups) == g)[0] for g in set(groups)}

    def permute():
        yp = y.copy()
        for g, ii in gidx.items():
            yp[ii] = rng.permutation(y[ii])
        return yp

    perms = [permute() for _ in range(NPERM)]
    li27 = FULL.index(27)
    hT = top_heads["transfer"][0]
    feats = {}
    S = lambda u: Z[u["k"]]
    feats[f"L{FULL[hT[0]]}h{hT[1]} DLA direct (top transfer head)"] = np.array([S(u)["dla_d"][hT] for u in rows])
    feats[f"L{FULL[hT[0]]}h{hT[1]} DLA J-lens"] = np.array([S(u)["dla_j"][hT] for u in rows])
    for si, s in enumerate(SEGS):
        feats[f"L{FULL[hT[0]]}h{hT[1]} mass {s}"] = np.array([S(u)["mass"][hT[0], hT[1], si] for u in rows])
    feats[f"L{FULL[hT[0]]}h{hT[1]} mass on copies of 'transfer'"] = np.array([S(u)["mass_tgt"][hT[0], hT[1]].sum() for u in rows])
    for l in (19, 23, 27, 31):
        feats[f"L{l} all-head attention DLA (M1 layer total)"] = np.array([S(u)["dla_d"][FULL.index(l)].sum() for u in rows])
    feats["all full-attn layers, attention DLA total"] = np.array([S(u)["dla_d"].sum() for u in rows])
    for s in ("policy_transfer", "policy_deny", "user_last", "tool_results", "assistant_prev", "tool_desc_transfer"):
        feats[f"L27 all-head mean mass {s}"] = np.array([S(u)["mass"][li27, :, SEGS.index(s)].mean() for u in rows])
        feats[f"L23 all-head mean mass {s}"] = np.array([S(u)["mass"][FULL.index(23), :, SEGS.index(s)].mean() for u in rows])
    feats["turn index"] = turn
    md += ["", "Pre-specified single features (no fitting). AUC > 0.5 = higher in bad. Turn-controlled = residual after a quadratic in turn index.",
           "p = within-task label permutation (counts per task kept).", "",
           "| feature | mean bad | mean good | AUC | task-cluster 95% CI | within-task AUC | turn-controlled AUC | p |", "|---|---|---|---|---|---|---|---|"]
    out["single"] = {}
    for name, f in feats.items():
        a = mine.auc(f, y)
        ci = mine.boot_ci(f, y, groups, np.random.default_rng(0))
        wa = within_task_auc(f, y, groups)
        ra = mine.auc(resid_on(f, turn), y) if name != "turn index" else None
        null = np.array([mine.auc(f, yp) for yp in perms])
        p = float((np.abs(null - 0.5) >= abs(a - 0.5)).mean())
        out["single"][name] = {"auc": a, "ci": ci, "within": wa, "turn_ctrl": ra, "p": p,
                               "mean_bad": float(f[y == 1].mean()), "mean_good": float(f[y == 0].mean())}
        md.append(f"| {name} | {f[y == 1].mean():.3f} | {f[y == 0].mean():.3f} | {a:.3f} | {ci} | "
                  f"{'-' if wa is None else round(wa, 3)} | {'-' if ra is None else round(ra, 3)} | {p:.3f} |")
    n_single = len(feats)
    md.append(f"\n{n_single} features tested: at p < 0.05 about {0.05 * n_single:.1f} are expected by chance.")

    F_all = np.stack([np.concatenate([S(u)["mass"].ravel(), S(u)["dla_d"].ravel(), S(u)["dla_j"].ravel()]) for u in rows])
    sel = [FULL.index(23), FULL.index(27)]
    F_2327 = np.stack([np.concatenate([S(u)["mass"][sel].ravel(), S(u)["dla_d"][sel].ravel()]) for u in rows])
    F_top = np.stack([np.concatenate([S(u)["mass"][hT[0], hT[1]], [S(u)["dla_d"][hT], S(u)["dla_j"][hT]]]) for u in rows])
    dets = {"logistic, all 8x16 heads (mass x13 segments + DLA direct + DLA J-lens)": F_all,
            "logistic, L23+L27 heads (mass + DLA direct)": F_2327,
            f"logistic, top transfer head L{FULL[hT[0]]}h{hT[1]} only (13 masses + 2 DLA)": F_top,
            "logistic, turn index only": turn[:, None]}
    md += ["", "Cross-validated detectors (task-grouped 5-fold, the same folds as X16/X17), within-task permutation null with refitting:", "",
           "| detector | AUC (OOF) | within-task AUC | turn-controlled AUC | null mean | null 95th | p |", "|---|---|---|---|---|---|---|"]
    out["cv"] = {}
    for name, F in dets.items():
        s = cv_logit(F, y, folds)
        a = mine.auc(s, y)
        null = np.array([mine.auc(cv_logit(F, yp, folds), yp) for yp in perms[:100]])
        p = float((null >= a).mean())
        ra = mine.auc(resid_on(s, turn), y)
        out["cv"][name] = {"auc": a, "within": within_task_auc(s, y, groups), "turn_ctrl": ra, "null_mean": float(null.mean()),
                           "null95": float(np.percentile(null, 95)), "p": p}
        md.append(f"| {name} | {a:.3f} | {within_task_auc(s, y, groups):.3f} | {ra:.3f} | {null.mean():.3f} | {np.percentile(null, 95):.3f} | {p:.2f} |")
        print(name, round(a, 3), "p", p, flush=True)

    md += ["", "## C. Writes: unexpected write in a failed episode (BW) vs good write (GW), same name token only", ""]
    W_ = [u for u in units if u["group"] in ("BW", "GW")]
    names = Counter((u["target"], u["group"]) for u in W_)
    shared = sorted({t for t, _ in names if names[(t, "BW")] and names[(t, "GW")]})
    md.append("name tokens with both groups: " + ", ".join(f"{voc[t]!r} BW {names[(t, 'BW')]} / GW {names[(t, 'GW')]}" for t in shared))
    md += ["", "| name token | top name head (label-free, from both groups) | DLA bad | DLA good | within-name AUC of DLA | "
               "mass user_last bad/good | mass tool_results bad/good |", "|---|---|---|---|---|---|---|"]
    for t in shared:
        V = [u for u in W_ if u["target"] == t]
        D = np.mean([Z[u["k"]]["dla_d"] for u in V], 0)
        li, h = np.unravel_index(np.argmax(D), D.shape)
        yy = np.array([u["group"] == "BW" for u in V], int)
        d = np.array([Z[u["k"]]["dla_d"][li, h] for u in V])
        mu = np.array([Z[u["k"]]["mass"][li, h, SEGS.index("user_last")] for u in V])
        mt = np.array([Z[u["k"]]["mass"][li, h, SEGS.index("tool_results")] for u in V])
        md.append(f"| {voc[t]!r} | L{FULL[li]}h{h} | {d[yy == 1].mean():.2f} | {d[yy == 0].mean():.2f} | {mine.auc(d, yy):.3f} | "
                  f"{mu[yy == 1].mean():.3f}/{mu[yy == 0].mean():.3f} | {mt[yy == 1].mean():.3f}/{mt[yy == 0].mean():.3f} |")

    md += ["", f"## D. Source tokens of L{FULL[hT[0]]}h{hT[1]} (top-8 attended positions; recorded at L23 and L27 only)", ""]
    if FULL[hT[0]] in (23, 27):
        si = (23, 27).index(FULL[hT[0]])
        for lab, nm in ((1, "bad"), (0, "good")):
            seg_c, tok_c = Counter(), Counter()
            R_ = [u for u, yy in zip(rows, y) if yy == lab]
            for u in R_:
                z = Z[u["k"]]
                for t, s_, w in zip(z["src_tok"][si, hT[1]], z["src_seg"][si, hT[1]], z["src_w"][si, hT[1]]):
                    seg_c[SEGS[s_]] += float(w) / len(R_)
                    tok_c[(voc[t], SEGS[s_])] += float(w) / len(R_)
            md.append(f"- {nm} (n {len(R_)}): top-8 weight by segment " + ", ".join(f"{s} {v:.3f}" for s, v in seg_c.most_common(6)))
            md.append(f"  tokens: " + ", ".join(f"{t!r}@{s} {v:.3f}" for (t, s), v in tok_c.most_common(10)))
    (HERE / "h1_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (HERE / "h1_report.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
