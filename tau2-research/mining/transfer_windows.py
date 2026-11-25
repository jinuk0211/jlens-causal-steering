"""Unneeded vs legitimate transfer, with J-lens words from every logged position, not only the decision point (CPU, PC).

Rows (278 f_detect episodes): turns whose calls include transfer_to_human_agents; bad = unexpected_transfer in a failed episode
(NL-corrected), good = transfer in a passed episode (19 vs 56, as stage 0).
Windows (J-lens readout; context / agent tokens top-30 per layer, decision point top-100 per layer):
  prev   the 3 previous turns: every user / tool / agent position and their decision points
  ctx    this turn up to the decision: the user / tool messages since the last agent turn, the header, the decision point
  gen    this turn's generated tokens before the <tool_call> token (the preamble, e.g. "I understand ... I will transfer you")
  all    prev + ctx + gen
Features (group, layer, word) and (group, any layer, word); surface baseline = the actual tokens in the same window.
Task-grouped 5-fold CV, both-direction selection (K 10 / 30 / 100) inside the training folds, score = # bad features - # good
features present. Null: within-domain label permutation, selection + CV rerun, 100 permutations. Turn-residualized AUC.
Output: mining/transfer_windows.md
"""
import gzip
import json
from collections import Counter
from pathlib import Path

import numpy as np

import mine

HERE = Path(__file__).resolve().parent
TOPK = HERE.parent.parent / "tau2-topk-20261119"
V = 248320
NL = 33
NPERM = 100


def enc(group, topk):
    if topk.shape[0] == 0:
        return np.zeros(0, np.int64)
    L = np.arange(topk.shape[1], dtype=np.int64)[None, :, None]
    t = topk.astype(np.int64)
    return np.unique(np.concatenate([((group * NL + L) * V + t).ravel(), ((group * NL + 32) * V + t).ravel()]))


def main():
    rng = np.random.default_rng(21)
    voc = json.loads(gzip.open(HERE / "vocab.json.gz", "rt", encoding="utf-8").read())
    tc = voc.index("<tool_call>")
    nl = json.loads((HERE.parent / "nl_judge/nl_verdicts.json").read_text(encoding="utf-8"))["records"]
    rows = []
    for jf in sorted(TOPK.glob("*.json")):
        m = json.loads(jf.read_text(encoding="utf-8"))
        if m.get("cond") != "f_detect":
            continue
        r = float(m["reward"] or 0)
        key = f"f_detect|{m['domain']}|{m['task']}|{m['sim_id']}"
        if m["domain"] == "retail" and key in nl:
            r = float(nl[key]["corrected_reward"])
        ok = r >= 1
        tr = [t for t in m["turns"] if any(c["name"] == "transfer_to_human_agents" for c in t["calls"])]
        if not tr:
            continue
        z = None
        for t in tr:
            bad = any(b.startswith("unexpected_transfer") for b in t["bad"])
            y = 1 if (bad and not ok) else (0 if ok else None)
            if y is None:
                continue
            if z is None:
                z = np.load(jf.with_suffix(".npz"))
            ti = int(t["turn"])
            at, aseg, apos, atok = z["agent_turn"], z["agent_seg"], z["agent_pos"], z["agent_tok"]
            ct = z["ctx_turn"]
            prev_turns = [ti - 3, ti - 2, ti - 1]
            pm_c = np.isin(ct, prev_turns)
            pm_a = np.isin(at, prev_turns) & (aseg != 3)
            pm_d = np.isin(z["dec_turn"], prev_turns)
            prev = np.unique(np.concatenate([enc(0, z["ctx_topk_jlens"][pm_c]), enc(1, z["agent_topk_jlens"][pm_a]),
                                             enc(2, z["dec_ids_jlens"][pm_d])]))
            prev_s = np.unique(np.concatenate([0 * V + z["ctx_tok"][pm_c].astype(np.int64), 1 * V + atok[pm_a].astype(np.int64)]))
            cm_c = ct == ti
            cm_a = (at == ti) & (aseg == 2)
            cm_d = z["dec_turn"] == ti
            ctx = np.unique(np.concatenate([enc(0, z["ctx_topk_jlens"][cm_c]), enc(1, z["agent_topk_jlens"][cm_a]),
                                            enc(2, z["dec_ids_jlens"][cm_d])]))
            ctx_s = np.unique(np.concatenate([0 * V + z["ctx_tok"][cm_c].astype(np.int64), 1 * V + atok[cm_a].astype(np.int64)]))
            g = np.nonzero((at == ti) & (aseg == 4))[0]
            g = g[np.argsort(apos[g])]
            stop = next((k for k, i in enumerate(g) if atok[i] == tc), len(g))
            g = g[:stop]
            gen = enc(3, z["agent_topk_jlens"][g])
            gen_s = np.unique(3 * V + atok[g].astype(np.int64))
            rows.append({"y": y, "group": f"{m['domain']}|{m['task']}", "domain": m["domain"], "turn": ti, "n_gen": int(len(g)),
                         "lens": {"prev": prev, "ctx": ctx, "gen": gen, "all": np.unique(np.concatenate([prev, ctx, gen]))},
                         "surf": {"prev": prev_s, "ctx": ctx_s, "gen": gen_s, "all": np.unique(np.concatenate([prev_s, ctx_s, gen_s]))}})
    y = np.array([r["y"] for r in rows])
    groups = [r["group"] for r in rows]
    folds = np.array([mine.fold_of(g) for g in groups])
    dom = np.array([r["domain"] for r in rows])
    turn = np.array([r["turn"] for r in rows], float)

    def prep(keys):
        allc, df = np.unique(np.concatenate(keys), return_counts=True)
        cand = allc[df >= 3]
        return cand, [np.searchsorted(cand, k[np.isin(k, cand, assume_unique=True)]).astype(np.int32) for k in keys]

    def broad_all(idx, n_cand, yy, Ks=(10, 30, 100)):
        oof = {K: np.zeros(len(yy)) for K in Ks}
        for q in range(mine.NFOLD):
            tr, te = np.nonzero(folds != q)[0], np.nonzero(folds == q)[0]
            if len(te) == 0 or len(set(yy[tr].tolist())) < 2:
                continue
            a = np.bincount(np.concatenate([idx[i] for i in tr if yy[i] == 1]), minlength=n_cand)
            b = np.bincount(np.concatenate([idx[i] for i in tr if yy[i] == 0]), minlength=n_cand)
            nb, ng = int(yy[tr].sum()), int((1 - yy[tr]).sum())
            lr = np.log((a + 0.5) / (nb + 1)) - np.log((b + 0.5) / (ng + 1))
            pi, ni = np.where(a >= 3)[0], np.where(b >= 3)[0]
            op, on = pi[np.argsort(-lr[pi])], ni[np.argsort(lr[ni])]
            for K in Ks:
                pm = np.zeros(n_cand, bool)
                pm[op[:K]] = True
                nm = np.zeros(n_cand, bool)
                nm[on[:K]] = True
                for i in te:
                    oof[K][i] = pm[idx[i]].sum() - nm[idx[i]].sum()
        return oof

    def perm():
        yp = y.copy()
        for d in set(dom.tolist()):
            ii = np.nonzero(dom == d)[0]
            yp[ii] = rng.permutation(y[ii])
        return yp

    perms = [perm() for _ in range(NPERM)]

    def resid(s):
        A = np.vstack([turn, np.ones_like(turn)]).T
        return s - A @ np.linalg.lstsq(A, s, rcond=None)[0]

    md = ["# Unneeded vs legitimate transfer with J-lens words from every logged position (278 f_detect episodes)", "",
          f"rows: bad {int(y.sum())} ({len({g for g, yy in zip(groups, y) if yy})} tasks), good {int((1 - y).sum())}; "
          f"turn index alone AUC {mine.auc(turn, y):.3f}; mean preamble length (tokens before <tool_call>): bad "
          f"{np.mean([r['n_gen'] for r in rows if r['y']]):.0f}, good {np.mean([r['n_gen'] for r in rows if not r['y']]):.0f}", "",
          "| window | features | K | AUC | turn-residualized | null mean / 95th / max | p |", "|---|---|---|---|---|---|---|"]
    for w in ("prev", "ctx", "gen", "all"):
        for kind in ("lens", "surf"):
            cand, idx = prep([r[kind][w] for r in rows])
            real = broad_all(idx, len(cand), y)
            nulls = [broad_all(idx, len(cand), yp) for yp in perms]
            for K in (10, 30, 100):
                s_ = real[K]
                a_ = mine.auc(s_, y)
                null = np.array([mine.auc(nv[K], yp) for nv, yp in zip(nulls, perms)])
                md.append(f"| {w} | {'J-lens words' if kind == 'lens' else 'surface tokens'} | {K} | {a_:.3f} | {mine.auc(resid(s_), y):.3f} | "
                          f"{null.mean():.3f} / {np.percentile(null, 95):.3f} / {null.max():.3f} | {(null >= a_).mean():.2f} |")
                print(md[-1], flush=True)
    md += ["", "Most lopsided J-lens words per window (all rows, descriptive; count = rows with the word, bad of "
           f"{int(y.sum())} vs good of {int((1 - y).sum())}):", ""]
    nb, ng = int(y.sum()), int((1 - y).sum())
    for w in ("prev", "ctx", "gen"):
        ca, cb = Counter(), Counter()
        for r in rows:
            (ca if r["y"] else cb).update(r["lens"][w].tolist())
        keys = [k for k in set(ca) | set(cb) if ca[k] + cb[k] >= 5]
        sc = sorted(keys, key=lambda k: -((ca[k] + 0.5) / (nb + 1)) / ((cb[k] + 0.5) / (ng + 1)))

        def name(k):
            g, rest = divmod(k, NL * V)
            layer, tok = divmod(rest, V)
            return f"{'CADG'[g]}/L{'any' if layer == 32 else layer} {voc[tok]!r}"
        md.append(f"- {w}, more in BAD: " + "; ".join(f"{name(k)} {ca[k]}/{nb} vs {cb[k]}/{ng}" for k in sc[:12]))
        md.append(f"- {w}, more in GOOD: " + "; ".join(f"{name(k)} {ca[k]}/{nb} vs {cb[k]}/{ng}" for k in sc[::-1][:12]))
    (HERE / "transfer_windows.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[-6:]))


if __name__ == "__main__":
    main()
