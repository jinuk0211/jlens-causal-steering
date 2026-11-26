"""OVERNIGHT2 (failure-driven search, user 11-26 12:3x). Hard negatives = benign decisions of the same kind in the same
kind of context: dojo, the calls the model makes in attacked episodes it did not follow (function name and first
argument value of the first call) plus the CAUSAL-1 references; am, the CAUSAL-1 references (benign recipients and tools in
the same scenarios).
capture BENCH : per decision unit (targets and hard negatives), MLP acts / head inputs and their gradients at the decision
    position (targets: m = max lp(T) - max lp(A); hard negatives: the logit margin of the chosen token, logit(next) -
    logsumexp(other logits), because lp(next) is saturated near 0 and has no gradient), the residual of every layer and
    the MLP acts at the call-onset token (the token that completes MARK), and the residual of TRAJ_L every TRAJ_STEP
    response tokens up to the onset. -> hn/BENCH/hn.npz, items.json, CAPTURE_DONE
sets BENCH : fold-0 hard-negative statistics, neuron sets (benefit - lam * benign damage, for clamp and mean edits),
    matched random sets, the onset probe (per-layer logistic, group CV on fold 0, threshold at 5 % FPR), the contrast
    direction, and the trajectory decodability curve. -> hn/BENCH/sets.json, stats.npz, sets_report.md, SETS_DONE
run BENCH TAG : regenerations through ab_regen.run_rows with the arms of TAG (ARMS below, or hn/BENCH/arms_TAG.json).
report BENCH TAG... : strict tables (ab_strict) with the OVERNIGHT2 gate per arm and its failure mode.
Usage: AB_PLATFORM=projectb CUDA_VISIBLE_DEVICES=g python ab_hn.py capture dojo"""
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_core as C
import ab_regen as R

A = Path("/home/project-b/LJW/agentbench2/ana")
HN = A / "hn"
NL, NN, D, HD = 32, 9216, 2560, 4096
MARK = {"dojo": "<tool_call>", "am": "<tool_use:"}
TRAJ_L, TRAJ_STEP = (16, 24), 32
NW = int(os.environ.get("AB_NW", "48"))
KAPPA = float(os.environ.get("AB_KAPPA", "1.0"))
ARMS = {"r1": (["base", "hnA1024_cl", "hnR1024_cl", "hnA256_cl", "hnR256_cl", "hnA1024_mn", "hnR1024_mn",
                "p_hnA1024_cl", "p_hnR1024_cl", "dir_cl", "rdir_cl"], 0)}


def onset_of(tok, comp, upto, marker):
    text = tok.decode(comp[:upto])
    i = text.rfind(marker)
    if i < 0:
        return None
    return C.char_to_token(tok, comp[:upto], i + len(marker) - 1)


def hn_items(bench, tok):
    eos = C.eos_ids(tok)
    c1 = json.loads((A / bench / "c1" / "units.json").read_text(encoding="utf-8"))
    U = {u["uid"]: u for u in json.loads((A / bench / "units.json").read_text(encoding="utf-8"))}
    items, seen = [], set()

    def add(u, lab, pos, T, A_, kind, ids, cs, gk):
        if (u["uid"], pos) in seen or pos + 1 >= len(ids):
            return
        seen.add((u["uid"], pos))
        k = onset_of(tok, ids[cs:], pos + 1 - cs, MARK[bench])
        items.append({"uid": u["uid"], "label": lab, "group": u["group"], "fold": u["fold"], "kind": kind, "gk": gk,
                      "seq": ids[:pos + 1], "next": ids[pos + 1], "T": T, "A": A_, "cs": cs,
                      "onset": cs + k if k is not None else pos})

    for lab, xs in (("target", c1["targets"]), ("hn", c1["refs"])):
        for x in xs:
            u = U[x["uid"]]
            P = list(u["prompt_ids"])
            ids = P + [t for t in u["completion_ids"] if t not in eos]
            if ids[x["pos"] + 1] != x["next"]:
                continue
            add(u, lab, x["pos"], list(x["T"]), list(x["A"]), x["kind"], ids, len(P), "m" if lab == "target" else "lp")
    if bench == "dojo":
        for u in U.values():
            if u["label"] != "reference":
                continue
            P = list(u["prompt_ids"])
            comp = [t for t in u["completion_ids"] if t not in eos]
            text = tok.decode(comp)
            m = C.FUNC_RE.search(text)
            if not m:
                continue
            ks = [("hn_name", C.char_to_token(tok, comp, m.start(1)))]
            pm = C.PARAM_RE.search(text, m.end())
            if pm and pm.group(2).strip():
                vs = pm.start(2) + (len(pm.group(2)) - len(pm.group(2).lstrip()))
                ks.append(("hn_value", C.char_to_token(tok, comp, vs)))
            ids = P + comp
            for kind, k in ks:
                if k >= 1:
                    add(u, "hn", len(P) + k - 1, [comp[k]], [], kind, ids, len(P), "lp")
    return items


def mode_capture(bench):
    out = (A / "hn_smoke" if os.environ.get("AB_SMOKE") else HN) / bench
    out.mkdir(parents=True, exist_ok=True)
    tok, model = C.load()
    H = C.Hooked(model)
    items = hn_items(bench, tok)
    if os.environ.get("AB_SMOKE"):
        items = [i for i in items if i["label"] == "target"][:1] + [i for i in items if i["label"] == "hn"][:2]
    C.log(f"{bench}: {len(items)} items {Counter((i['label'], i['fold']) for i in items)} {Counter(i['kind'] for i in items)}")
    keep, rec = {}, {"on": False}
    fw = {"on": False, "off": 0, "want": {}, "onset": -1, "res": {}, "act": None}

    def pre(name, i):
        def f(mod, args):
            if rec["on"]:
                x = args[0]
                if x.requires_grad:
                    x.retain_grad()
                keep[(name, i)] = x
            if fw["on"] and name == "act":
                lo, n = fw["off"], args[0].shape[1]
                if lo <= fw["onset"] < lo + n:
                    fw["act"] = fw["act"] if fw["act"] is not None else {}
                    fw["act"][i] = args[0][0, fw["onset"] - lo].detach().float().cpu()
        return f

    def post_res(i):
        def f(mod, args, out_):
            if not fw["on"]:
                return
            o = out_ if torch.is_tensor(out_) else out_[0]
            lo, n = fw["off"], o.shape[1]
            for p in fw["want"].get(i, ()):
                if lo <= p < lo + n:
                    fw["res"][(i, p)] = o[0, p - lo].detach().float().cpu()
        return f

    def emb(mod, a, o):
        if rec["on"]:
            o.requires_grad_(True)

    hs = []
    for i, b in enumerate(H.blocks):
        hs.append(b.mlp.down_proj.register_forward_pre_hook(pre("act", i)))
        att = b.self_attn if hasattr(b, "self_attn") else b.linear_attn
        proj = att.o_proj if hasattr(b, "self_attn") else att.out_proj
        hs.append(proj.register_forward_pre_hook(pre("hin", i)))
        hs.append(b.register_forward_hook(post_res(i)))
    hs.append(H.lm.embed_tokens.register_forward_hook(emb))
    n = len(items)
    ACT = np.zeros((n, NL, NN), np.float16)
    GR = np.zeros((n, NL, NN), np.float32)
    HIN = np.zeros((n, NL, HD), np.float16)
    GH = np.zeros((n, NL, HD), np.float32)
    ORES = np.zeros((n, NL, D), np.float16)
    OACT = np.zeros((n, NL, NN), np.float16)
    TR, TRI, TRD = [], [], []
    meta = []
    dev = C.first_device(model)
    t0 = time.time()
    for k, it in enumerate(items):
        seq, on = it["seq"], it["onset"]
        tpos = list(range(it["cs"], on, TRAJ_STEP))
        fw.update(on=True, onset=on, res={}, act=None, want={i: ([on] + (tpos if i in TRAJ_L else [])) for i in range(NL)})
        with torch.inference_mode():
            cache = None
            for s in range(0, on + 1, 1024):
                fw["off"] = s
                o = model(input_ids=torch.tensor([seq[s:min(s + 1024, on + 1)]], device=dev), past_key_values=cache, use_cache=True,
                          logits_to_keep=1)
                cache = o.past_key_values
            del cache, o
        fw["on"] = False
        ORES[k] = torch.stack([fw["res"][(i, on)] for i in range(NL)]).numpy()
        OACT[k] = torch.stack([fw["act"][i] for i in range(NL)]).numpy()
        for p in tpos:
            TR.append(torch.stack([fw["res"][(i, p)] for i in TRAJ_L]).half().numpy())
            TRI.append(k)
            TRD.append(on - p)
        kk = min(4, len(seq) - 1)
        _, cache = C.prefill(model, seq[:-kk], inference=False)
        keep.clear()
        rec["on"] = True
        with torch.enable_grad():
            o = model(input_ids=torch.tensor([seq[-kk:]], device=dev), past_key_values=cache, use_cache=True, logits_to_keep=1)
            lg = o.logits[0, -1].float()
            lp = torch.log_softmax(lg, -1)
            if it["gk"] == "m":
                m = lp[it["T"]].max() - lp[it["A"]].max()
            else:
                oth = lg.clone()
                oth[it["next"]] = float("-inf")
                m = lg[it["next"]] - torch.logsumexp(oth, -1)
            m.backward()
        rec["on"] = False
        ACT[k] = torch.stack([keep[("act", i)][0, -1].detach().float() for i in range(NL)]).cpu().numpy()
        GR[k] = torch.stack([keep[("act", i)].grad[0, -1].float() for i in range(NL)]).cpu().numpy()
        HIN[k] = torch.stack([keep[("hin", i)][0, -1].detach().float() for i in range(NL)]).cpu().numpy()
        GH[k] = torch.stack([keep[("hin", i)].grad[0, -1].float() for i in range(NL)]).cpu().numpy()
        meta.append({kk_: it[kk_] for kk_ in ("uid", "label", "group", "fold", "kind", "gk", "next", "onset", "cs")}
                    | {"pos": len(seq) - 1, "val": float(m.detach()), "lp_next": float(lp[it["next"]].detach())})
        keep.clear()
        del cache, o, lp, lg, m
        if k % 20 == 0:
            C.log(f"capture {bench} {k + 1}/{n} {it['label']} {it['kind']} onset-pos {len(seq) - 1 - on} {time.time() - t0:.0f}s")
    for h in hs:
        h.remove()
    np.savez(out / "hn.npz", uids=np.array([m_["uid"] for m_ in meta]), labels=np.array([m_["label"] for m_ in meta]),
             folds=np.array([m_["fold"] for m_ in meta]), groups=np.array([m_["group"] for m_ in meta]),
             kinds=np.array([m_["kind"] for m_ in meta]), act=ACT, grad=GR, hin=HIN, ghin=GH, ores=ORES, oact=OACT,
             traj=np.stack(TR) if TR else np.zeros((0, len(TRAJ_L), D), np.float16), traj_item=np.array(TRI, np.int32),
             traj_dist=np.array(TRD, np.int32))
    (out / "items.json").write_text(json.dumps(meta), encoding="utf-8")
    (out / "CAPTURE_DONE").touch()
    C.log(f"CAPTURE_DONE {bench} {n}")


def auroc(pos, neg):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if len(pos) == 0 or len(neg) == 0:
        return None
    allv = np.concatenate([pos, neg])
    rk = allv.argsort().argsort().astype(float) + 1
    for v in np.unique(allv):
        mm = allv == v
        rk[mm] = rk[mm].mean()
    return float((rk[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def fit_probe(X, y, groups, C_=0.1):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    mu, sd = X.mean(0), X.std(0) + 1e-4
    Z = (X - mu) / sd
    cv = np.zeros(len(y))
    ng = len(set(groups))
    for tr, te in GroupKFold(n_splits=min(5, ng)).split(Z, y, groups):
        if len(set(y[tr])) < 2:
            cv[te] = 0.0
            continue
        cv[te] = LogisticRegression(C=C_, max_iter=2000).fit(Z[tr], y[tr]).decision_function(Z[te])
    clf = LogisticRegression(C=C_, max_iter=2000).fit(Z, y)
    thr = float(np.quantile(cv[y == 0], 0.95))
    return {"mu": mu, "sd": sd, "w": clf.coef_[0], "b": float(clf.intercept_[0]), "thr_cv": thr, "cv_auc": auroc(cv[y == 1], cv[y == 0]),
            "cv": cv}


def mode_sets(bench):
    out = HN / bench
    d = np.load(out / "hn.npz")
    lab, fol, grp = d["labels"], d["folds"].astype(int), d["groups"]
    T0, N0 = (lab == "target") & (fol == 0), (lab == "hn") & (fol == 0)
    T1, N1 = (lab == "target") & (fol == 1), (lab == "hn") & (fol == 1)
    act, grad = d["act"], d["grad"]
    aN = act[N0].astype(np.float32).reshape(N0.sum(), -1)
    aT = act[T0].astype(np.float32).reshape(T0.sum(), -1)
    gN = grad[N0].reshape(N0.sum(), -1)
    gT = grad[T0].reshape(T0.sum(), -1)
    muN, sdN = aN.mean(0), aN.std(0) + 1e-3
    sign = np.sign((aT - muN).mean(0))
    sign[sign == 0] = 1

    def clamp(a):
        lim = muN + sign * KAPPA * sdN
        return np.where(sign * (a - muN) > KAPPA * sdN, lim, a)
    ben = {"mn": (gT * (aT - muN)).mean(0), "cl": (gT * (aT - clamp(aT))).mean(0)}
    dmg = {"mn": np.abs(gN * (muN - aN)).mean(0), "cl": np.abs(gN * (clamp(aN) - aN)).mean(0)}
    neur, info = {}, {}
    for e in ("cl", "mn"):
        for lam in (1, 3, 10):
            sc = ben[e] - lam * dmg[e]
            order = np.argsort(-sc)
            for K in (64, 256, 1024, 4096):
                top = order[:K]
                rng = np.random.default_rng(K + 7 * lam)
                tag = "" if lam == 1 else f"l{lam}"
                neur[f"hnA{K}{tag}_{e}"] = top.tolist()
                neur[f"hnR{K}{tag}_{e}"] = ((top // NN) * NN + rng.integers(0, NN, K)).tolist()
                info[f"hnA{K}{tag}_{e}"] = {"benefit": float(ben[e][top].sum()), "damage": float(dmg[e][top].sum()),
                                            "layers": Counter(int(x // NN) for x in top).most_common()}
    for e in ("cl", "mn"):
        order = np.argsort(-ben[e])
        neur[f"oldA1024_{e}"] = order[:1024].tolist()
        info[f"oldA1024_{e}"] = {"benefit": float(ben[e][order[:1024]].sum()), "damage": float(dmg[e][order[:1024]].sum())}
    gsum = defaultdict(lambda: np.zeros(NL * NN, np.float64))
    gcnt = Counter()
    for j, g in zip(np.where(N0)[0], grp[N0]):
        gsum[g] += act[j].astype(np.float64).reshape(-1)
        gcnt[g] += 1
    ores = d["ores"].astype(np.float32)
    y_on = np.r_[np.ones(T0.sum()), np.zeros(N0.sum())]
    g_on = np.r_[grp[T0], grp[N0]]
    probes, prow = {}, []
    for l in range(4, NL):
        X0 = np.r_[ores[T0, l], ores[N0, l]]
        p = fit_probe(X0, y_on, g_on)
        s1 = lambda X: ((X - p["mu"]) / p["sd"]) @ p["w"] + p["b"]
        st, sn = s1(ores[T1, l]), s1(ores[N1, l])
        prow.append({"layer": l, "cv_auc": p["cv_auc"], "fold1_auc": auroc(st, sn), "tpr1": float((st > p["thr_cv"]).mean()) if len(st) else None,
                     "fpr1": float((sn > p["thr_cv"]).mean()) if len(sn) else None})
        probes[l] = p
    best = max(prow, key=lambda r: (r["cv_auc"] or 0))
    lp_ = best["layer"]
    pb = probes[lp_]
    dvec = ores[T0, lp_].mean(0) - ores[N0, lp_].mean(0)
    dhat = dvec / (np.linalg.norm(dvec) + 1e-8)
    rng = np.random.default_rng(3)
    rhat = rng.standard_normal(D)
    rhat /= np.linalg.norm(rhat)
    dirs = {}
    for name, v in (("dir", dhat), ("rdir", rhat)):
        pn = ores[N0, lp_] @ v
        dirs[name] = {"layer": lp_, "vec": v.tolist(), "b": float(pn.mean()), "sd": float(pn.std() + 1e-4)}
    nidx = np.array(neur["hnA1024_cl"])
    oa = d["oact"].astype(np.float32).reshape(len(lab), -1)[:, nidx]
    pnr = fit_probe(np.r_[oa[T0], oa[N0]], y_on, g_on)
    s1n = lambda X: ((X - pnr["mu"]) / pnr["sd"]) @ pnr["w"] + pnr["b"]
    neur_probe = {"cv_auc": pnr["cv_auc"], "fold1_auc": auroc(s1n(oa[T1]), s1n(oa[N1]))}
    tr, ti, tdist = d["traj"].astype(np.float32), d["traj_item"], d["traj_dist"]
    curve = []
    if len(tr):
        tl = lab[ti] == "target"
        tf = fol[ti]
        for li, l in enumerate(TRAJ_L):
            for lo, hi in ((0, 64), (64, 256), (256, 1024), (1024, 10 ** 6)):
                mm = (tdist >= lo) & (tdist < hi)
                m0, m1 = mm & (tf == 0), mm & (tf == 1)
                if m0.sum() < 20 or len(set(tl[m0])) < 2 or m1.sum() < 10 or len(set(tl[m1])) < 2:
                    continue
                p = fit_probe(tr[m0, li], tl[m0].astype(int), grp[ti][m0])
                s = ((tr[m1, li] - p["mu"]) / p["sd"]) @ p["w"] + p["b"]
                curve.append({"layer": l, "dist": f"{lo}-{hi}", "n0": int(m0.sum()), "n1": int(m1.sum()), "cv_auc": p["cv_auc"],
                              "fold1_auc": auroc(s[tl[m1]], s[~tl[m1]])})
    np.savez(out / "stats.npz", muN=muN.reshape(NL, NN), sdN=sdN.reshape(NL, NN), sign=sign.reshape(NL, NN),
             gsum=np.stack([gsum[g] for g in sorted(gsum)]).reshape(len(gsum), NL, NN).astype(np.float32),
             gnames=np.array(sorted(gsum)), gcnt=np.array([gcnt[g] for g in sorted(gsum)]))
    sets = {"neur": neur, "info": info, "probe": {"layer": lp_, "mu": pb["mu"].tolist(), "sd": pb["sd"].tolist(), "w": pb["w"].tolist(),
                                                  "b": pb["b"], "thr": pb["thr_cv"]},
            "probe_layers": prow, "neuron_probe": neur_probe, "dirs": dirs, "traj_curve": curve,
            "n": {"T0": int(T0.sum()), "N0": int(N0.sum()), "T1": int(T1.sum()), "N1": int(N1.sum())}, "kappa": KAPPA}
    (out / "sets.json").write_text(json.dumps(sets), encoding="utf-8")
    L = [f"# {bench} hard-negative sets ({time.strftime('%F %T')})", "",
         f"units: fold0 targets {sets['n']['T0']}, hard negatives {sets['n']['N0']}; fold1 targets {sets['n']['T1']}, hard negatives {sets['n']['N1']}",
         "", "## onset probe (residual at the call-onset token, logistic, group CV on fold 0, threshold 5 % FPR)", "",
         "| layer | CV AUROC (fold 0) | fold 1 AUROC | fold 1 TPR | fold 1 FPR |", "|---|---|---|---|---|"]
    for r in prow:
        f = lambda v: "-" if v is None else f"{v:.2f}"
        L.append(f"| {r['layer']} | {f(r['cv_auc'])} | {f(r['fold1_auc'])} | {f(r['tpr1'])} | {f(r['fpr1'])} |")
    L += ["", f"chosen layer (CV): {lp_}", f"neuron probe on hnA1024_cl onset acts: CV {neur_probe['cv_auc']}, fold 1 {neur_probe['fold1_auc']}",
          "", "## decodability before the onset (trajectory residuals)", "", "| layer | tokens before onset | n0 | n1 | CV AUROC | fold 1 AUROC |",
          "|---|---|---|---|---|---|"]
    for r in curve:
        L.append(f"| {r['layer']} | {r['dist']} | {r['n0']} | {r['n1']} | {r['cv_auc']:.2f} | {r['fold1_auc'] if r['fold1_auc'] is None else round(r['fold1_auc'], 2)} |")
    L += ["", "## neuron sets (sum of fold-0 estimated benefit on targets and damage on hard negatives)", "", "| set | benefit | damage | top layers |",
          "|---|---|---|---|"]
    for k, v in info.items():
        if "_" in k and ("1024" in k or "256" in k):
            L.append(f"| {k} | {v['benefit']:.2f} | {v['damage']:.2f} | {v.get('layers', '')[:6] if v.get('layers') else ''} |")
    (out / "sets_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "SETS_DONE").touch()
    C.log(f"SETS_DONE {bench}: probe layer {lp_} CV {best['cv_auc']:.2f} fold1 {best['fold1_auc']}")


class NClamp:
    def __init__(self, idx, mu, sd, sign, kappa):
        self.t = {"i": idx, "m": mu, "s": sd, "g": sign}
        self.kappa, self._c = kappa, {}

    def _on(self, k, dev):
        key = (k, str(dev))
        if key not in self._c:
            v = self.t[k]
            self._c[key] = v.to(dev, torch.long if k == "i" else torch.float32)
        return self._c[key]

    def __call__(self, x):
        dev = x.device
        it, mu, sd, sg = (self._on(k, dev) for k in "imsg")
        x = x.clone()
        v = x[:, it].float()
        lim = mu + sg * self.kappa * sd
        x[:, it] = torch.where(sg * (v - mu) > self.kappa * sd, lim.expand_as(v), v).to(x.dtype)
        return x


class DirClamp:
    def __init__(self, vec, b, sd, kappa):
        self.vec, self.lim, self._c = torch.tensor(vec, dtype=torch.float32), b + kappa * sd, {}

    def __call__(self, x):
        k = str(x.device)
        if k not in self._c:
            self._c[k] = self.vec.to(x.device)
        v = self._c[k]
        xf = x.float()
        ex = (xf @ v - self.lim).clamp_min(0)
        return (xf - ex[:, None] * v).to(x.dtype)


class Probe:
    def __init__(self):
        self.active, self.last, self.thr, self.l = False, None, 0.0, None

    def install(self, H, p):
        self.l, self.thr = p["layer"], p["thr"]
        self.mu = torch.tensor(p["mu"], dtype=torch.float32).cuda()
        self.sd = torch.tensor(p["sd"], dtype=torch.float32).cuda()
        self.w = torch.tensor(p["w"], dtype=torch.float32).cuda()
        self.b = p["b"]
        H.blocks[self.l].register_forward_hook(self._hook)
        self.active = True

    def _hook(self, mod, args, out_):
        o = out_ if torch.is_tensor(out_) else out_[0]
        if self.active and o.shape[1] == 1:
            self.last = (((o[:, -1].float() - self.mu) / self.sd) @ self.w + self.b).tolist()


PROBE = Probe()
FIRES = []
BENCH = {"b": "dojo"}


class HGate(C.Gate):
    def __init__(self, tok, modes, marker):
        super().__init__(tok, modes, marker)
        self.mk = MARK[BENCH["b"]]
        n = len(modes)
        self.on_t, self.fired, self.pend, self.t, self.order = [None] * n, [False] * n, {}, -1, []

    def __call__(self, t, r, ids):
        if t != self.t:
            if self.pend and PROBE.last is not None:
                for rr, j in self.pend.items():
                    if j < len(PROBE.last):
                        self.fired[rr] = PROBE.last[j] > PROBE.thr
                        FIRES.append((rr, PROBE.last[j]))
            self.pend, self.t, self.order = {}, t, []
        j = len(self.order)
        self.order.append(r)
        m = self.modes[r]
        if m not in ("win", "pdet"):
            return super().__call__(t, r, ids)
        if ids:
            a, b = self.tok.decode(ids[-12:]), self.tok.decode(ids[-12:-1])
            if a.count(self.mk) > b.count(self.mk):
                self.on_t[r], self.fired[r] = t, False
                if m == "pdet":
                    self.pend[r] = j
                return False
        if self.on_t[r] is None or t - self.on_t[r] > NW:
            return False
        return m == "win" or self.fired[r]


def arm_list(bench, tag):
    f = HN / bench / f"arms_{tag}.json"
    if f.is_file():
        x = json.loads(f.read_text(encoding="utf-8"))
        return x["arms"], x.get("fold", 0)
    return ARMS[tag]


def mode_run(bench, tag):
    BENCH["b"] = bench
    out = HN / bench
    arms, fold = arm_list(bench, tag)
    units = json.loads((A / bench / "units.json").read_text(encoding="utf-8"))
    sets = json.loads((out / "sets.json").read_text(encoding="utf-8"))
    st = np.load(out / "stats.npz")
    muN, sdN, sign = (torch.tensor(st[k]) for k in ("muN", "sdN", "sign"))
    gidx = {g: i for i, g in enumerate(st["gnames"].tolist())}
    gsum, gcnt = st["gsum"], st["gcnt"]
    tot, ntot = gsum.sum(0), gcnt.sum()
    if bench == "am":
        R.NTGT_AM, R.NREF = (24, 12) if fold == 0 else (24, 24)
        nseeds = 3 if fold == 0 else 2
    else:
        R.NREF = 41 if fold == 0 else 90
        nseeds = 1
    tok, model = C.load()
    H = C.Hooked(model)
    if any(a.startswith("p_") for a in arms):
        PROBE.install(H, sets["probe"])
    C.Gate = HGate
    N = sets["neur"]

    def by_layer(flat):
        b = defaultdict(list)
        for x in flat:
            b[x // NN].append(x % NN)
        return b

    def mu_excl(g):
        if fold == 1 or g not in gidx:
            return muN
        i = gidx[g]
        return torch.tensor((tot - gsum[i]) / max(1, ntot - gcnt[i]))

    def build(name, mu):
        if name == "base":
            return {}
        nm = name[2:] if name.startswith("p_") else name
        if nm in ("dir_cl", "rdir_cl"):
            dd = sets["dirs"][nm[:-3]]
            return {("res", dd["layer"]): C.Edit("fn", fn=DirClamp(dd["vec"], dd["b"], dd["sd"], KAPPA))}
        e = nm.rsplit("_", 1)[1]
        flat = N[nm]
        if e == "mn":
            return {("down", l): C.Edit("neur", idx=torch.tensor(ns), vec=mu[l][ns]) for l, ns in by_layer(flat).items()}
        return {("down", l): C.Edit("fn", fn=NClamp(torch.tensor(ns), mu[l][ns], sdN[l][ns], sign[l][ns], KAPPA)) for l, ns in by_layer(flat).items()}

    def mode_of(name):
        return "base" if name == "base" else ("pdet" if name.startswith("p_") else "win")

    def cfg_fn(u):
        mu = mu_excl(u["group"])
        return [(a, build(a, mu), "all" if a == "base" else mode_of(a)) for a in arms]
    C.log(f"hn run {bench} {tag}: arms {arms}, fold {fold}, seeds {nseeds}, NW {NW}, kappa {KAPPA}")
    R.run_rows(bench, units, out, tok, model, H, tag, cfg_fn, fold, nseeds)
    if FIRES:
        (out / f"fires_{tag}{os.environ.get('AB_ROWS_SUFFIX', '')}.json").write_text(json.dumps(FIRES), encoding="utf-8")
    (out / f"{tag}_DONE").touch()


def fisher_greater(a, n1, b, n2):
    K, Nn = a + b, n1 + n2
    if n1 == 0 or n2 == 0:
        return None
    den = math.comb(Nn, n1)
    return sum(math.comb(K, x) * math.comb(Nn - K, n1 - x) for x in range(a, min(K, n1) + 1)) / den


def matched(name):
    for a, b in (("p_hnA", "p_hnR"), ("hnA", "hnR"), ("oldA", "oldR")):
        if name.startswith(a):
            return b + name[len(a):]
    if name in ("dir_cl", "p_dir_cl"):
        return name.replace("dir_cl", "rdir_cl")
    return None


def mode_report(bench, tags):
    import ab_strict as S
    units = json.loads((A / bench / "units.json").read_text(encoding="utf-8"))
    L = [f"# {bench} OVERNIGHT2 report ({time.strftime('%F %T')})", ""]
    for tag in tags:
        rows = S.rows_of(bench, tag, HN / bench)
        if not rows:
            continue
        by = S.dojo_table(rows, units) if bench == "dojo" else S.am_table(rows)
        prim = "uflip" if bench == "dojo" else "sflip"
        keepk = "kept_same" if bench == "dojo" else "skept"
        L += [f"## {tag}", "", f"| arm | n T | {prim} | flip | broken | n R | {keepk} | write kept | random | gap | p | gate | failure |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for cfg, c in sorted(by.items()):
            nt, nr = c["nt"], c["nr"]
            pf = c[prim] / nt if nt else 0
            kp = c[keepk] / nr if nr else 0
            br = c["broken"] / nt if nt else 0
            mr = matched(cfg)
            gap = p = None
            rk = None
            if mr and mr in by:
                cr = by[mr]
                pr = cr[prim] / cr["nt"] if cr["nt"] else 0
                rk = cr[keepk] / cr["nr"] if cr["nr"] else 0
                gap = pf - pr
                p = fisher_greater(c[prim], nt, cr[prim], cr["nt"])
            fail = []
            if mr:
                if gap is None or gap < 0.15:
                    fail.append("W")
                if pf < 0.20:
                    fail.append("W0")
                if rk is not None and kp < rk - 0.05:
                    fail.append("L")
                if br > 0.15:
                    fail.append("D")
            gate = "-" if not mr else ("PASS" if not fail else "fail")
            wk = f"{c['wkept']}/{c['nw']}" if bench == "dojo" else "-"
            f = lambda v: "-" if v is None else f"{v:.0%}"
            L.append(f"| {cfg} | {nt} | {pf:.0%} | {c['flip'] / nt if nt else 0:.0%} | {br:.0%} | {nr} | {kp:.0%} | {wk} | {mr or '-'} | "
                     f"{f(gap)} | {'-' if p is None else f'{p:.2g}'} | {gate} | {','.join(fail) or '-'} |")
        L.append("")
    (HN / bench / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    mode, bench = sys.argv[1], sys.argv[2]
    if mode == "capture":
        mode_capture(bench)
    elif mode == "sets":
        mode_sets(bench)
    elif mode == "run":
        mode_run(bench, sys.argv[3])
    elif mode == "report":
        mode_report(bench, sys.argv[3:])
