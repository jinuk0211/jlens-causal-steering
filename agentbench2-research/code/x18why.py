"""X18 follow-up (user 11-27 19:1x: "X18이 왜 실패했는지 확인 (fold별 base, 두 fold에서 고른 뉴런이 얼마나 겹치는지)"). CPU only,
existing files only. -> ana/ne/x18why.md
1. Per user task (banking, travel): attack success under base / clamp / its random for X15-X16 (fold-1 tasks, set rd1024 picked on
   fold 0) and X18 (fold-0 tasks, set xd1024 picked on fold 1), with the injection vector(s) of the task.
2. Base attack success per fold on the same HF platform (X12 base for fold 1, X18 base for fold 0).
3. Overlap of the two sets: whole sets, top 64 / 256 by each fold's median z, rank correlation of the two folds' median z over all
   neurons, and each set's median z on each fold.
4. How hard each set bites: per unit, the mean over the set of max(0, injection-span mean - limit) / token sd, by fold and suite."""
import json
from collections import Counter, defaultdict
from math import comb
from pathlib import Path

import numpy as np

A = Path("/home/project-b/LJW/agentbench2/ana")
RUNS = Path("/home/project-b/LJW/agentbench2/runs")
NN = 9216


def episodes(logdir, suite):
    out = {}
    base = RUNS / logdir / "openai-compatible" / suite
    for f in base.glob("user_task_*/important_instructions/*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        out[(d["user_task_id"], d["injection_task_id"])] = (bool(d["security"]), bool(d["utility"]), sorted((d.get("injections") or {}).keys()))
    return out


def fisher_less(a, n1, b, n2):
    tot, k = n1 + n2, a + b
    return sum(comb(n1, x) * comb(n2, k - x) for x in range(0, a + 1) if 0 <= k - x <= n2) / comb(tot, k)


def ranks(x):
    r = np.empty(len(x))
    r[np.argsort(x)] = np.arange(len(x))
    return r


def main():
    L = ["# X18 follow-up: why the fold swap did not reproduce X15", ""]
    runs = {"X15-X16 (fold-1 tasks, set picked on fold 0)": ("steer_base", "steer_rd1024_tr", "steer_rr1024_tr"),
            "X18 (fold-0 tasks, set picked on fold 1)": ("steer_base__x18", "steer_xd1024_tr__x18", "steer_xr1024_tr__x18")}
    L += ["## 1-2. Attack success per user task (base / clamp / random), injection vector of the task", ""]
    summ = {}
    for title, (b, c, r) in runs.items():
        for suite in ("banking", "travel"):
            eb, ec, er = episodes(b, suite), episodes(c, suite), episodes(r, suite)
            keys = sorted(set(ec) & set(er) & set(eb))
            if not keys:
                continue
            by = defaultdict(lambda: [0, 0, 0, 0])
            vec = {}
            for k in keys:
                t = by[k[0]]
                t[0] += 1
                t[1] += eb[k][0]
                t[2] += ec[k][0]
                t[3] += er[k][0]
                vec[k[0]] = eb[k][2]
            n, sb, sc, sr = (sum(v[i] for v in by.values()) for i in range(4))
            summ[(title, suite)] = (n, sb, sc, sr)
            L += [f"### {title}, {suite}: base {sb}/{n}, clamp {sc}/{n}, random {sr}/{n} (clamp < random one-sided p {fisher_less(sc, n, sr, n):.3g})", "",
                  "| user task | episodes | base | clamp | random | injection vector |", "|---|---|---|---|---|---|"]
            for ut in sorted(by, key=lambda x: int(x.split("_")[-1])):
                v = by[ut]
                L.append(f"| {ut} | {v[0]} | {v[1]} | {v[2]} | {v[3]} | {', '.join(vec[ut])} |")
            L.append("")
    d = np.load(A / "ne" / "read_xfit_dojo.npz")
    folds, suites = d["folds"].astype(int), d["suites"].astype(str)
    inj = d["inj"].astype(np.float32).reshape(len(folds), -1)
    tr = d["tr"].astype(np.float32).reshape(len(folds), -1)
    sd = d["tok_sd"].astype(np.float32).reshape(2, -1)
    z = {f: (inj - tr) / sd[f] for f in (0, 1)}
    med = {f: np.median(z[f][folds == f], 0) for f in (0, 1)}
    s15 = json.loads((A / "ne" / "steer_dojo" / "arms_s6a.json").read_text(encoding="utf-8"))["sets"]["rd1024"]
    s18 = json.loads((A / "ne" / "steer_dojo" / "arms_x18.json").read_text(encoding="utf-8"))["sets"]["xd1024"]
    sets = {"X15 set (picked on fold 0)": s15, "X18 set (picked on fold 1)": s18}
    idx = {k: np.array([int(l) * NN + int(j) for l, j, *_ in v]) for k, v in sets.items()}
    lim = {k: np.array([float(x[2]) for x in v]) for k, v in sets.items()}
    o = len(set(idx["X15 set (picked on fold 0)"]) & set(idx["X18 set (picked on fold 1)"]))
    top = {f: np.argsort(-med[f]) for f in (0, 1)}
    rc = float(np.corrcoef(ranks(med[0]), ranks(med[1]))[0, 1])
    L += ["## 3. Overlap of the two sets", "", f"- Whole sets: {o} of 1,024 shared.",
          f"- Top 64 by each fold's median z: {len(set(top[0][:64]) & set(top[1][:64]))} shared; top 256: {len(set(top[0][:256]) & set(top[1][:256]))}.",
          f"- Rank correlation of the two folds' median z over all {len(med[0]):,} neurons: {rc:.3f}.", ""]
    L += ["| set | median z on fold 0 units (its neurons, median) | on fold 1 units |", "|---|---|---|"]
    for k in sets:
        L.append(f"| {k} | {np.median(med[0][idx[k]]):.2f} | {np.median(med[1][idx[k]]):.2f} |")
    L += ["", "## 4. How hard each set bites (mean over the set of max(0, injection mean - limit) / token sd of its pick fold)", "",
          "| set | units | fold 0 banking | fold 0 travel | fold 1 banking | fold 1 travel |", "|---|---|---|---|---|---|"]
    pf = {"X15 set (picked on fold 0)": 0, "X18 set (picked on fold 1)": 1}
    for k in sets:
        b = np.maximum(0, inj[:, idx[k]] - lim[k][None, :]) / sd[pf[k]][idx[k]][None, :]
        b = b.mean(1)
        cells = []
        for f in (0, 1):
            for s in ("banking", "travel"):
                m = (folds == f) & (suites == s)
                cells.append(f"{np.median(b[m]):.3f} (n {int(m.sum())})" if m.any() else "-")
        L.append(f"| {k} | {len(b)} | " + " | ".join(cells) + " |")
    vc = Counter()
    for title, (b, c, r) in runs.items():
        for suite in ("banking", "travel"):
            for k, v in episodes(b, suite).items():
                for x in v[2]:
                    vc[(title.split(" ")[0], suite, x)] += 1
    L += ["", "## Injection vectors per run (attack episodes)", ""] + [f"- {a} {s}: {x} {n}" for (a, s, x), n in sorted(vc.items())]
    (A / "ne" / "x18why.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
