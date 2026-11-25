"""C0 decision units (probe/circuit/out/c0, symmetric contrast) x neuron explorer dictionary.

Per unit: s = act x grad of m = logit(chosen) - logit(alternative) at the decision position, for every MLP neuron (32 x 9216),
normalised by the unit's total |s|. Bad and good units are compared only within the same decision type and the same tool.
Neurons are picked on train tasks (md5(domain|task) % 2 == 0) and checked on eval tasks; a task-level label permutation
gives the chance level of the top train difference.

    python ne_join.py [--cond f_detect] -> out/ne_join[_cond].md, .json
"""
import argparse
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

R = Path("/home/project-b/LJW/tau2-steer/probe")
DICT = Path("/home/project-b/LJW/tau2x-ne/neuron-explorer/explorer/cache")
N, L = 9216, 32
BANDS = [(0, 7), (8, 15), (16, 23), (24, 27), (28, 31)]


def split(u):
    return "train" if int(hashlib.md5(f"{u['domain']}|{u['task']}".encode()).hexdigest(), 16) % 2 == 0 else "eval"


class Dictionary:
    def __init__(self):
        self.vocab = json.load(open(DICT / "vocab.json", encoding="utf-8"))
        self.ix = {k: dict(np.load(DICT / f"{f}.npz")) for k, f in
                   (("steer", "steer_index"), ("logit", "lens_index"), ("R", "r_index"), ("S", "s_index"))}

    def words(self, l, n, pos, k=5):
        side = "up" if pos else "down"
        return {name: [self.vocab[t].replace("\n", "\\n").replace("|", "¦") for t in ix[side][l, n, :k]] for name, ix in self.ix.items()}

    def kl(self, l, n, pos):
        return float(self.ix["steer"]["up_kl" if pos else "down_kl"][l, n])


def auc(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if not len(a) or not len(b):
        return None
    return float(((a[:, None] > b[None]).sum() + 0.5 * (a[:, None] == b[None]).sum()) / (len(a) * len(b)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cond", default=None, help="only units of this condition (e.g. f_detect)")
    ap.add_argument("--min-m", type=float, default=0.5)
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--perm", type=int, default=500)
    a = ap.parse_args()
    units = json.load(open(R / "circuit/out/c0/units.json"))
    units = [u for u in units if u["m"] >= a.min_m and (a.cond is None or u["cond"] == a.cond)
             and (R / f"circuit/out/c0/n_{u['k']}.npz").exists() and (R / f"m1/out/u_{u['k']}.npz").exists()]
    S, layer_share = {}, {}
    for u in units:
        g = np.load(R / f"circuit/out/c0/n_{u['k']}.npz")["grad"].astype(np.float32)
        act = np.load(R / f"m1/out/u_{u['k']}.npz")["act"].astype(np.float32)
        s = act * g
        tot = np.abs(s).sum()
        S[u["k"]] = (s / max(tot, 1e-9)).ravel()
        layer_share[u["k"]] = np.abs(s).sum(1) / max(tot, 1e-9)
    D = Dictionary()
    rng = np.random.default_rng(0)
    groups = defaultdict(list)
    for u in units:
        groups[(u["ptype"], u["call"])].append(u)
        if u["ptype"] == "T-call":
            groups[("T-call", "모든 툴")].append(u)
    md, js = [], {"cond": a.cond, "n_units": len(units), "groups": {}}
    w = md.append
    title = f"condition {a.cond}" if a.cond else "all conditions"
    w(f"# 실패 결정의 뉴런 (C0 grad×act × neuron explorer 사전, {title})\n")
    lab = defaultdict(int)
    for u in units:
        lab[(u["label"], u["ptype"])] += 1
    w(f"unit {len(units)}개 (결정이 재현되고 m ≥ {a.min_m}인 것): " + ", ".join(f"{k[0]} {k[1]} {v}" for k, v in sorted(lab.items())) + ".")
    w("점수 m = logit(고른 토큰) − logit(대안), 대안은 bad/good 모두 같은 규칙(C0 대칭 contrast). 뉴런 기여 s = 활성 × ∂m/∂활성, unit마다 Σ|s|로 나눔.\n")

    w("## 1. 레이어별 기여 비중 (bad vs good, 같은 결정 종류)\n")
    w("| 결정 | 라벨 | unit | task | " + " | ".join(f"L{x}–{y}" for x, y in BANDS) + " |")
    w("|---|---|---|---|" + "---|" * len(BANDS))
    for ptype in ("T-call", "T-name", "T-args"):
        for label in ("bad", "good"):
            us = [u for u in units if u["ptype"] == ptype and u["label"] == label]
            if not us:
                continue
            per = defaultdict(list)
            for u in us:
                per[(u["domain"], u["task"])].append(layer_share[u["k"]])
            prof = np.mean([np.mean(v, 0) for v in per.values()], 0)
            w(f"| {ptype} | {label} | {len(us)} | {len(per)} | " + " | ".join(f"{prof[x:y + 1].sum():.0%}" for x, y in BANDS) + " |")

    w("\n## 2. 같은 툴 안에서 bad 쪽으로 더 미는 뉴런\n")
    w("train task에서 (bad task 평균 s − good task 평균 s)가 큰 뉴런을 고르고, eval task에서 같은 방향인지(AUC, bad > good이면 0.5 초과) 봅니다. "
      f"우연 수준 = task 라벨을 {a.perm}번 섞었을 때 train 최대 차이의 95번째 백분위수.\n")
    for (ptype, tool), us in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        tr = {lb: [u for u in us if u["label"] == lb and split(u) == "train"] for lb in ("bad", "good")}
        ev = {lb: [u for u in us if u["label"] == lb and split(u) == "eval"] for lb in ("bad", "good")}
        ntask = lambda xs: len({(u["domain"], u["task"]) for u in xs})
        head = (f"\n### {ptype} · {tool} — train bad {len(tr['bad'])} unit/{ntask(tr['bad'])} task, good {len(tr['good'])}/{ntask(tr['good'])}; "
                f"eval bad {len(ev['bad'])}/{ntask(ev['bad'])}, good {len(ev['good'])}/{ntask(ev['good'])}\n")
        if ntask(tr["bad"]) < 3 or ntask(tr["good"]) < 3:
            continue
        w(head)

        def task_matrix(xs):
            per = defaultdict(list)
            for u in xs:
                per[(u["domain"], u["task"])].append(S[u["k"]])
            keys = sorted(per)
            return keys, np.stack([np.mean(per[k], 0) for k in keys])

        kb, Xb = task_matrix(tr["bad"])
        kg, Xg = task_matrix(tr["good"])
        diff = Xb.mean(0) - Xg.mean(0)
        X = np.concatenate([Xb, Xg])
        nb = len(Xb)
        null = []
        for _ in range(a.perm):
            p = rng.permutation(len(X))
            null.append((X[p[:nb]].mean(0) - X[p[nb:]].mean(0)).max())
        thr = float(np.percentile(null, 95))
        top = np.argsort(-diff)[: a.top]
        w(f"train 최대 차이 {diff.max():.4f}, 우연 수준(95%) {thr:.4f} → " + ("**우연보다 큼**" if diff.max() > thr else "우연과 구분 안 됨") + "\n")
        w("| 뉴런 | train 차이 | 우연 초과 | eval AUC | bad 평균 / good 평균 (eval) | 활성(bad) | explorer 사전 (밀면 · 직접 쓰는 말 · R · 읽는 말) | steer KL |")
        w("|---|---|---|---|---|---|---|---|")
        rows = []
        for i in top:
            l, n = int(i) // N, int(i) % N
            eb = [S[u["k"]][i] for u in ev["bad"]]
            eg = [S[u["k"]][i] for u in ev["good"]]
            acts = [float(np.load(R / f"m1/out/u_{u['k']}.npz")["act"][l, n]) for u in tr["bad"][:20]]
            pos = np.mean(acts) >= 0
            wd = D.words(l, n, pos)
            au = auc(eb, eg)
            w(f"| L{l}/N{n}{'+' if pos else '−'} | {diff[i]:.4f} | {'예' if diff[i] > thr else '아니오'} | {'–' if au is None else f'{au:.2f}'} | "
              f"{np.mean(eb) if eb else float('nan'):.4f} / {np.mean(eg) if eg else float('nan'):.4f} | {np.mean(acts):+.2f} | "
              + " · ".join(f"{k}: {' '.join(v)}" for k, v in wd.items()) + f" | {D.kl(l, n, pos):.2f} |")
            rows.append({"l": l, "n": n, "pole": "+" if pos else "-", "train_diff": float(diff[i]), "above_chance": bool(diff[i] > thr),
                         "eval_auc": au, "words": wd, "kl": D.kl(l, n, pos)})
        lay = np.bincount(top // N, minlength=L)
        js["groups"][f"{ptype}/{tool}"] = {"train_max": float(diff.max()), "chance95": thr, "top": rows,
                                           "n": {k: len(v) for k, v in {**{"train_" + x: tr[x] for x in tr}, **{"eval_" + x: ev[x] for x in ev}}.items()}}
        w(f"\n상위 {a.top}개의 레이어: " + ", ".join(f"L{l} {c}" for l, c in enumerate(lay) if c))
    w("\n## 3. 사전 단어로 묶은 뉴런 묶음의 기여 (bad vs good)\n")
    w("뉴런이 밀면·직접 쓰는 말·R lens 상위 12개 토큰 중 하나에 어간을 담고 있으면 그 묶음에 넣습니다(극별로; 활성 부호가 그 극일 때만 셈). "
      "unit의 묶음 기여 = 묶음 뉴런 s의 합(Σ|s|=1로 정규화). task마다 평균을 낸 뒤 bad vs good AUC(>0.5면 bad에서 더 큼)와 task bootstrap 95% 구간.\n")
    fams = {"transfer·human·agent": ("transfer", "human", "agent", "escalat", "supervisor", "representative"),
            "cancel": ("cancel",), "update·modify·change": ("update", "modif", "change"), "book·reserve": ("book", "reserv"),
            "sorry·unable·cannot": ("sorry", "apolog", "unable", "cannot", "can't"), "refund·compensat": ("refund", "compens", "certificate")}
    vl = [v.strip().lower() for v in D.vocab]
    masks = {}
    for name, stems in fams.items():
        for side, sgn in (("up", 1), ("down", -1)):
            hit = np.zeros((L, N), bool)
            for k in ("steer", "logit", "R"):
                ids = D.ix[k][side][:, :, :12]
                tokhit = np.array([any(s in t for s in stems) for t in vl])
                hit |= tokhit[ids].any(-1)
            masks[(name, sgn)] = hit.ravel()
    w("| 묶음 | 뉴런 수(+극/−극) | 결정 · 툴 | bad unit/task | good unit/task | bad 평균 | good 평균 | AUC [95%] |")
    w("|---|---|---|---|---|---|---|---|")
    acts = {u["k"]: np.load(R / f"m1/out/u_{u['k']}.npz")["act"].astype(np.float32).ravel() for u in units}
    for name in fams:
        mp, mn = masks[(name, 1)], masks[(name, -1)]
        for (ptype, tool), us in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            per = {lb: defaultdict(list) for lb in ("bad", "good")}
            for u in us:
                s, ac = S[u["k"]], acts[u["k"]]
                per[u["label"]][(u["domain"], u["task"])].append(float(s[mp & (ac > 0)].sum() + s[mn & (ac < 0)].sum()))
            vb = np.array([np.mean(v) for v in per["bad"].values()])
            vg = np.array([np.mean(v) for v in per["good"].values()])
            if len(vb) < 3 or len(vg) < 3:
                continue
            bs = [auc(rng.choice(vb, len(vb)), rng.choice(vg, len(vg))) for _ in range(1000)]
            au = auc(vb, vg)
            w(f"| {name} | {mp.sum()}/{mn.sum()} | {ptype} · {tool} | {sum(len(v) for v in per['bad'].values())}/{len(vb)} | "
              f"{sum(len(v) for v in per['good'].values())}/{len(vg)} | {vb.mean():+.4f} | {vg.mean():+.4f} | {au:.2f} [{np.percentile(bs, 2.5):.2f}, {np.percentile(bs, 97.5):.2f}] |")
            js.setdefault("families", {})[f"{name}|{ptype}/{tool}"] = {"auc": au, "ci": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                                                                       "bad": float(vb.mean()), "good": float(vg.mean()), "n_bad_tasks": len(vb), "n_good_tasks": len(vg)}

    od = Path("/home/project-b/LJW/tau2x-ne/ne_join")
    od.mkdir(parents=True, exist_ok=True)
    out = od / (f"ne_join_{a.cond}" if a.cond else "ne_join")
    open(str(out) + ".md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump(js, open(str(out) + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
