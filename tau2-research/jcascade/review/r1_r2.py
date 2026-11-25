import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
JC = HERE.parent
RES = JC.parent
sys.path.insert(0, str(RES / "mining"))
import mine

Z = 1.96 + 0.84


def auc(s, y):
    s, y = np.asarray(s, float), np.asarray(y)
    p, n = s[y == 1], s[y == 0]
    return float(((p[:, None] > n[None]).sum() + 0.5 * (p[:, None] == n[None]).sum()) / (len(p) * len(n)))


def cluster_ci(s, y, cl, rng, B=4000):
    s, y, cl = np.asarray(s, float), np.asarray(y), np.asarray(cl)
    ids = sorted(set(cl.tolist()))
    idx = {c: np.nonzero(cl == c)[0] for c in ids}
    out = []
    for _ in range(B):
        pick = np.concatenate([idx[c] for c in rng.choice(ids, len(ids))])
        if len(set(y[pick].tolist())) < 2:
            continue
        out.append(auc(s[pick], y[pick]))
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def r2():
    gate = json.loads((JC / "out/stage2b_gate.json").read_text(encoding="utf-8"))
    turns = json.loads((RES / "mining/cache_turns.json").read_text(encoding="utf-8"))
    task = {(t["domain"], t["sim"], t["turn"]): t["task"] for t in turns}
    s = np.array([g["J_pairs_oof"] for g in gate])
    y = np.array([g["y"] for g in gate])
    keys = [(g["domain"], g["sim"], g["turn"]) for g in gate]
    cl_task = [f"{k[0]}|{task[k]}" for k in keys]
    cl_tel = [("telecom|ALL" if k[0] == "telecom" else c) for k, c in zip(keys, cl_task)]
    cl_telbad = [("telecom|MMS_BAD" if (k[0] == "telecom" and yy == 1) else c) for k, c, yy in zip(keys, cl_task, y)]
    rng = np.random.default_rng(11)
    res = {"auc": auc(s, y), "n_bad": int(y.sum()), "n_good": int((1 - y).sum()),
           "eff_bad_clusters": len({c for c, yy in zip(cl_telbad, y) if yy == 1}),
           "ci_task_clusters": cluster_ci(s, y, cl_task, rng),
           "ci_telecom_bad_one_cluster": cluster_ci(s, y, cl_telbad, rng),
           "ci_telecom_all_one_cluster": cluster_ci(s, y, cl_tel, rng)}
    nb, ng = res["n_bad"], res["n_good"]
    a = res["auc"]
    q1, q2 = a / (2 - a), 2 * a * a / (1 + a)
    res["hanley_mcneil_se"] = math.sqrt((a * (1 - a) + (nb - 1) * (q1 - a * a) + (ng - 1) * (q2 - a * a)) / (nb * ng))
    for d in ("airline", "retail", "telecom"):
        m = np.array([k[0] == d for k in keys])
        res[f"auc_{d}"] = auc(s[m], y[m]) if len(set(y[m].tolist())) == 2 else None
    m = np.array([k[0] != "telecom" for k in keys])
    res["auc_without_telecom"] = auc(s[m], y[m])
    return res


def r1():
    var_task = {"airline": 4.0 / 50, "retail": 2.4 ** 2 / 50, "telecom": 0.10}
    n_task = {"airline": 50, "retail": 114, "telecom": 114}
    var_draw = sum(var_task[d] * n_task[d] for d in n_task)
    sd_draw = math.sqrt(var_draw)
    full = []
    for c in (0.2, 0.3, 0.4, 0.6):
        for s in (0.3, 0.5, 0.8, 1.0):
            for h in (0.0, 0.05, 0.10):
                delta = 19 * c * s - 56 * h * 0.7
                n = math.inf if delta <= 0 else 2 * var_draw * Z * Z / delta ** 2
                full.append({"c": c, "s": s, "h": h, "delta_pass_per_draw": round(delta, 2), "draws_per_arm": None if n == math.inf else math.ceil(n)})
    rng = np.random.default_rng(5)
    nb, ng = 13, 12
    branch = []
    for c in (0.2, 0.3, 0.4, 0.6):
        for s in (0.3, 0.5, 0.8):
            for h in (0.0, 0.1, 0.2):
                for K in (1, 3, 5, 10):
                    p_bad_ctl, p_bad_trt = 0.03, 0.03 + c * s
                    p_good_ctl = 0.86
                    p_good_trt = p_good_ctl * (1 - h * 0.7)
                    hits = 0
                    R = 1500
                    for _ in range(R):
                        bc = rng.binomial(K, p_bad_ctl, nb) / K
                        bt = rng.binomial(K, p_bad_trt, nb) / K
                        gc = rng.binomial(K, p_good_ctl, ng) / K
                        gt = rng.binomial(K, p_good_trt, ng) / K
                        d = np.concatenate([bt - bc, gt - gc])
                        se = d.std(ddof=1) / math.sqrt(len(d)) if d.std() > 0 else 1e-9
                        hits += (d.mean() / se) > 1.645
                    branch.append({"c": c, "s": s, "h": h, "K": K, "episodes": 2 * K * (nb + ng), "power": round(hits / R, 3),
                                   "expected_net_gain_per_25_branches": round(nb * c * s - ng * p_good_ctl * h * 0.7, 2)})
    return {"sd_pass_count_per_full_draw": round(sd_draw, 2), "full_reruns": full, "branch": branch}


def main():
    res = {"R2": r2(), "R1": r1()}
    (HERE / "r1_r2.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    R2, R1 = res["R2"], res["R1"]
    md = ["# R1 power and R2 sample size", "",
          "## R2: stage-0 detector AUC with honest uncertainty", "",
          f"- AUC {R2['auc']:.3f} on {R2['n_bad']} bad / {R2['n_good']} good. Telecom bad rows form one MMS scenario, so the effective "
          f"number of bad clusters is {R2['eff_bad_clusters']}.",
          f"- Hanley-McNeil SE {R2['hanley_mcneil_se']:.3f} (about ±{1.96 * R2['hanley_mcneil_se']:.2f} for a 95 % interval).",
          f"- 95 % cluster bootstrap: task clusters {R2['ci_task_clusters']}, telecom bad as one cluster {R2['ci_telecom_bad_one_cluster']}, "
          f"all telecom as one cluster {R2['ci_telecom_all_one_cluster']}.",
          f"- By domain: airline {R2['auc_airline']}, retail {R2['auc_retail']}, telecom {R2['auc_telecom']}; without telecom {R2['auc_without_telecom']:.3f}.",
          "", "## R1: how many runs are needed", "",
          f"Noise model from the 7-draw airline data (score 36.1 ± 2.0 over 50 tasks) and retail (38.0 ± 2.4): "
          f"SD of the pass count over all 278 tasks per draw ≈ {R1['sd_pass_count_per_full_draw']}.", "",
          "(a) Full reruns of all 278 tasks, two arms, 80 % power, two-sided α 0.05. c = share of unneeded transfers converted, "
          "s = share of converted episodes that then pass, h = share of the 56 legitimate transfers lost (70 % of those then fail).", "",
          "| c | s | h | expected Δ pass count per draw | draws per arm |", "|---|---|---|---|---|"]
    md += [f"| {r['c']} | {r['s']} | {r['h']} | {r['delta_pass_per_draw']} | {r['draws_per_arm'] if r['draws_per_arm'] else 'never'} |"
           for r in R1["full_reruns"] if r["h"] in (0.0, 0.05)]
    md += ["", "(b) Branch at the flagged turn: replay the logged prefix, then K continuations per arm (with / without the intervention), "
           "only for the 25 flagged transfer turns (13 bad, 12 good). One-sided paired z test over branch points, α 0.05.", "",
           "| c | s | h | K | Haiku continuation episodes | power | expected net gain over 25 branches |", "|---|---|---|---|---|---|---|"]
    md += [f"| {r['c']} | {r['s']} | {r['h']} | {r['K']} | {r['episodes']} | {r['power']} | {r['expected_net_gain_per_25_branches']} |"
           for r in R1["branch"] if r["s"] in (0.5, 0.8) and r["h"] in (0.0, 0.1)]
    (HERE / "r1_r2.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:12]))
    print("full reruns (h=0):", [(r["c"], r["s"], r["draws_per_arm"]) for r in R1["full_reruns"] if r["h"] == 0.0])
    print("branch power K=5,h=0:", [(r["c"], r["s"], r["power"]) for r in R1["branch"] if r["K"] == 5 and r["h"] == 0.0])
    print("branch power K=5,h=0.1:", [(r["c"], r["s"], r["power"]) for r in R1["branch"] if r["K"] == 5 and r["h"] == 0.1])


if __name__ == "__main__":
    main()
