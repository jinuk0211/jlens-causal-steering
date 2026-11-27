"""X18 / X19 (PLAN.md Log, 11-27): cross-fit of the reading-stage clamp (T6 / X15) and its extension to the slack suite.
The capture and the selection repeat ab_ne.readcap / ab_ne.readarms; the only change is that the token statistics over the
tool-result tokens are kept for each fold, so a set can be picked on fold 1 and tested on the fold-0 user tasks.
  cap UNITS_JSON OUT_NPZ        per unit: mean activation on the marked injection span and on the other tool-result tokens;
                                per fold: token mean and sd over the other tool-result tokens
  check NPZ                     parity with the original capture (ne/read_dojo.npz) and the original set (arms_s6a.json, rd1024)
  arms TAG NPZ SPEC SEED        SPEC = name:pickfold[,name:pickfold]. Sets <name>d1024 = top 1,024 by the pick fold's median z,
                                limit = that fold's token mean + 1 sd; <name>r1024 = same-layer random neurons, same limit rule.
                                -> ne/steer_dojo/arms_<TAG>.json (never overwritten)
  slackunits TASKS_JSON OUT_JSON REQLOG [REQLOG ...]
                                units of a suite without vLLM traces: for every (user task, injection task) the shortest logged
                                request (ab_serve_steer.py, AB_REQLOG) that shows the marked injection inside a tool result
  count SUITE TASKS LABEL=LOGDIR [LABEL=LOGDIR ...]
                                TASKS = all or comma-separated user task numbers. Attack episodes of runs/LOGDIR and the
                                no-attack episodes of runs/LOGDIR_noattack. Fisher (one-sided, lower ASR) against the LABELs
                                rand and base when they are given. Standard library only."""
import glob
import hashlib
import json
import sys
from collections import Counter
from math import comb
from pathlib import Path

A = Path("/home/project-b/LJW/agentbench2/ana")
NE = A / "ne"
RUNS = Path("/home/project-b/LJW/agentbench2/runs")
NL, NN = 32, 9216
INJ_A, INJ_B = "<INFORMATION>", "</INFORMATION>"


def cap(units_p, out_p):
    import numpy as np
    import torch
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ab_core as C
    import ab_ne as NEM
    tok, model = C.load()
    H = C.Hooked(model)
    units = json.loads(Path(units_p).read_text(encoding="utf-8"))
    st = {"on": False, "off": 0, "masks": None}
    acc = {}

    def pre(l):
        def f(mod, args):
            if not st["on"]:
                return
            x = args[0][0].float()
            lo, T = st["off"], x.shape[0]
            for name, m in st["masks"].items():
                mm = m[lo:lo + T]
                if mm.any():
                    xs = x[mm]
                    acc[(name, "s", l)] = acc.get((name, "s", l), 0) + xs.sum(0)
                    if name == "tr":
                        acc[("tr", "q", l)] = acc.get(("tr", "q", l), 0) + (xs * xs).sum(0)
        return f
    hs = [b.mlp.down_proj.register_forward_pre_hook(pre(l)) for l, b in enumerate(H.blocks)]
    dev = C.first_device(model)
    keep, INJ, TR, CNT = [], [], [], []
    S1 = torch.zeros(2, NL, NN, dtype=torch.float64, device="cuda")
    S2 = torch.zeros(2, NL, NN, dtype=torch.float64, device="cuda")
    ntok = [0, 0]
    import time
    t0 = time.time()
    for k, u in enumerate(units):
        P = list(u["prompt_ids"])
        a, b = NEM.dojo_spans(tok, P)["inj"]
        if b <= a:
            continue
        trm = NEM.tool_result_mask(tok, P)
        inj = np.zeros(len(P), bool)
        inj[a:b] = True
        tr = trm & ~inj
        if tr.sum() < 8:
            continue
        st["masks"] = {n: torch.tensor(m, device=dev) for n, m in (("inj", inj), ("tr", tr))}
        acc.clear()
        st["on"] = True
        with torch.inference_mode():
            cache = None
            for s in range(0, len(P), 1024):
                st["off"] = s
                o = model(input_ids=torch.tensor([P[s:s + 1024]], device=dev), past_key_values=cache, use_cache=True, logits_to_keep=1)
                cache = o.past_key_values
            del cache, o
        st["on"] = False
        n_inj, n_tr = int(inj.sum()), int(tr.sum())
        INJ.append(torch.stack([acc[("inj", "s", l)] / n_inj for l in range(NL)]).half().cpu().numpy())
        TR.append(torch.stack([acc[("tr", "s", l)] / n_tr for l in range(NL)]).half().cpu().numpy())
        f = int(u["fold"])
        S1[f] += torch.stack([acc[("tr", "s", l)] for l in range(NL)]).double()
        S2[f] += torch.stack([acc[("tr", "q", l)] for l in range(NL)]).double()
        ntok[f] += n_tr
        keep.append(u)
        CNT.append([n_inj, n_tr])
        if k % 20 == 0:
            C.log(f"cap {k + 1}/{len(units)} kept {len(keep)} tokens inj {n_inj} tr {n_tr} {time.time() - t0:.0f}s")
    for h in hs:
        h.remove()
    mu, sd = [], []
    for f in (0, 1):
        n = max(ntok[f], 1)
        mu.append((S1[f] / n).float().cpu().numpy())
        sd.append(((S2[f] / n - (S1[f] / n) ** 2).clamp_min(0).sqrt() + 1e-3).float().cpu().numpy())
    np.savez(out_p, uids=np.array([u["uid"] for u in keep]), folds=np.array([u["fold"] for u in keep]),
             suites=np.array([u["suite"] for u in keep]), counts=np.array(CNT), inj=np.stack(INJ), tr=np.stack(TR),
             tok_mu=np.stack(mu), tok_sd=np.stack(sd), ntok=np.array(ntok))
    C.log(f"XFIT_CAP_DONE {len(keep)} units of {len(units)}, by fold {dict(Counter(int(u['fold']) for u in keep))}, tool-result tokens {ntok}")


def pick(d, pf, K=1024):
    import numpy as np
    fol = d["folds"].astype(int)
    sd = d["tok_sd"][pf].reshape(-1)
    m = fol == pf
    z = (d["inj"][m].astype(np.float32).reshape(int(m.sum()), -1) - d["tr"][m].astype(np.float32).reshape(int(m.sum()), -1)) / sd
    score = np.median(z, 0)
    order = np.argsort(-score)
    return [int(i) for i in order[:K]], score


def check(npz):
    import numpy as np
    d = np.load(npz)
    o = np.load(NE / "read_dojo.npz")
    same_units = list(d["uids"]) == list(o["uids"])
    dmu = float(np.abs(d["tok_mu"][0] - o["tok_mu"]).max())
    dsd = float(np.abs(d["tok_sd"][0] - o["tok_sd"]).max())
    ids, score = pick(d, 0)
    s6a = json.loads((NE / "steer_dojo" / "arms_s6a.json").read_text(encoding="utf-8"))["sets"]["rd1024"]
    old = {int(l) * NN + int(j) for l, j, _ in s6a}
    ov = len(old & set(ids))
    lim_old = {int(l) * NN + int(j): float(v) for l, j, v in s6a}
    mu, sd = d["tok_mu"][0].reshape(-1), d["tok_sd"][0].reshape(-1)
    dl = max((abs(float(mu[i] + sd[i]) - lim_old[i]) for i in ids if i in lim_old), default=float("nan"))
    ok = same_units and ov >= 1000 and dmu < 0.05
    print(json.dumps({"same_units": same_units, "units": int(len(d["uids"])), "max_abs_diff_tok_mu_fold0": dmu, "max_abs_diff_tok_sd_fold0": dsd,
                      "fold0_top1024_overlap_with_rd1024": ov, "max_abs_diff_limit_on_shared": dl, "ntok": d["ntok"].tolist(), "parity": ok}))
    if not ok:
        raise SystemExit("XFIT_CHECK_FAILED")
    print("XFIT_CHECK_OK")


def arms(tag, npz, spec, seed):
    import numpy as np
    out = NE / "steer_dojo" / f"arms_{tag}.json"
    if out.exists():
        raise SystemExit(f"{out} exists; not overwritten")
    d = np.load(npz)
    fol = d["folds"].astype(int)
    rng = np.random.default_rng(int(seed))
    s6a = json.loads((NE / "steer_dojo" / "arms_s6a.json").read_text(encoding="utf-8"))["sets"]["rd1024"]
    old = {int(l) * NN + int(j) for l, j, _ in s6a}
    sets, arms_, info = {}, {"base": None}, {}
    for it in spec.split(","):
        nm, pf = it.split(":")
        pf = int(pf)
        ids, score = pick(d, pf)
        mu, sd = d["tok_mu"][pf].reshape(-1), d["tok_sd"][pf].reshape(-1)
        rnd = [int((i // NN) * NN + rng.integers(0, NN)) for i in ids]
        mk = lambda xs: [[int(i // NN), int(i % NN), float(mu[i] + sd[i])] for i in xs]
        sets[nm + "d1024"], sets[nm + "r1024"] = mk(ids), mk(rnd)
        arms_[nm + "d1024_tr"] = {"set": nm + "d1024", "kind": "clamp", "where": "tr", "pick_fold": pf}
        arms_[nm + "r1024_tr"] = {"set": nm + "r1024", "kind": "clamp", "where": "tr", "pick_fold": pf}
        info[nm] = {"pick_fold": pf, "units": int((fol == pf).sum()), "tool_result_tokens": int(d["ntok"][pf]),
                    "z_first": float(score[ids[0]]), "z_last": float(score[ids[-1]]), "neurons_with_z_above_1": int((score > 1).sum()),
                    "layers": sorted(Counter(int(i // NN) for i in ids).items()), "overlap_with_rd1024_s6a": len(old & set(ids)),
                    "random_overlap_with_set": len(set(rnd) & set(ids))}
    out.write_text(json.dumps({"arms": arms_, "sets": sets, "info": info, "npz": str(npz), "seed": int(seed)}), encoding="utf-8")
    print(json.dumps(info, indent=1))
    print("XFIT_ARMS_DONE", tag, list(arms_))


def slackunits(tasks_p, out_p, *logs):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ab_core as C
    import ab_ne as NEM
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    T = json.loads(Path(tasks_p).read_text(encoding="utf-8"))
    suite = T["suite"]
    best, stats = {}, Counter()
    UA = "<|im_start|>user\n"
    for lg in logs:
        for line in open(lg, encoding="utf-8"):
            ids = json.loads(line)["ids"]
            stats["requests"] += 1
            text = tok.decode(ids)
            i0 = text.find(INJ_A)
            i1 = text.find(INJ_B, i0) if i0 >= 0 else -1
            if i0 < 0 or i1 < 0:
                continue
            stats["with_injection"] += 1
            a = C.char_to_token(tok, ids, i0)
            if not NEM.tool_result_mask(tok, ids)[a]:
                stats["injection_outside_tool_result"] += 1
                continue
            u0 = text.find(UA)
            up = text[u0 + len(UA):text.find("<|im_end|>", u0)].strip()
            ut = [k for k, v in T["user"].items() if v.strip() == up] or [k for k, v in T["user"].items() if v.strip() in up]
            body = text[i0:i1]
            its = sorted((k for k, v in T["inj"].items() if v.strip() in body), key=lambda k: -len(T["inj"][k]))
            if len(ut) != 1 or not its:
                stats["unmatched"] += 1
                continue
            key = (ut[0], its[0])
            if key not in best or len(ids) < len(best[key]):
                best[key] = ids
    units = []
    for (ut, it), ids in sorted(best.items(), key=lambda kv: (int(kv[0][0].split("_")[-1]), int(kv[0][1].split("_")[-1]))):
        units.append({"uid": f"{suite}|{ut}|{it}", "bench": "dojo", "suite": suite, "user_task": ut, "injection_task": it, "label": "na",
                      "fold": int(hashlib.md5(f"{suite}|{ut}".encode()).hexdigest(), 16) % 2, "prompt_ids": ids})
    Path(out_p).write_text(json.dumps(units), encoding="utf-8")
    stats["units"] = len(units)
    print(json.dumps({"stats": dict(stats), "by_fold": dict(Counter(u["fold"] for u in units)),
                      "user_tasks_by_fold": {f: sorted({int(u["user_task"].split("_")[-1]) for u in units if u["fold"] == f}) for f in (0, 1)},
                      "prompt_tokens_median": sorted(len(u["prompt_ids"]) for u in units)[len(units) // 2] if units else 0}))
    print("XFIT_UNITS_DONE")


def render(units_p):
    """X19r: fill prompt_ids / completion_ids of units built with RENDER_LATER=1 (units_dojo_x19.py) by the chat template."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ab_core as C
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    U = json.loads(Path(units_p).read_text(encoding="utf-8"))
    tools = json.loads(Path(str(units_p) + ".tools.json").read_text(encoding="utf-8"))
    n = 0
    for u in U:
        r = u.pop("render", None)
        if r is None:
            continue
        base = tok.apply_chat_template(r["msgs"], tools=tools[u["suite"]], add_generation_prompt=True, tokenize=False, enable_thinking=False)
        full = tok.apply_chat_template(r["full"], tools=tools[u["suite"]], tokenize=False, enable_thinking=False)
        u["prompt_ids"] = tok.encode(base, add_special_tokens=False)
        u["completion_ids"] = tok.encode(full[len(base):], add_special_tokens=False) if full.startswith(base) else []
        u["budget"] = max(96, min(768, int(1.5 * len(u["completion_ids"])) + 64))
        u["token_source"] = "render"
        n += 1
    Path(units_p).write_text(json.dumps(U), encoding="utf-8")
    print(f"XFIT_RENDER_DONE {n} of {len(U)} units rendered, labels {dict(Counter(u['label'] for u in U))}")


def reqparity(units_p, *logs):
    """X19r: the chat-template render of each unit's prompt must be one of the prompts the HF server logged."""
    seen = set()
    for lg in logs:
        for line in open(lg, encoding="utf-8"):
            seen.add(hashlib.sha256(json.dumps(json.loads(line)["ids"]).encode()).hexdigest())
    U = json.loads(Path(units_p).read_text(encoding="utf-8"))
    hit = [hashlib.sha256(json.dumps(list(u["prompt_ids"])).encode()).hexdigest() in seen for u in U]
    by = Counter((u["label"], h) for u, h in zip(U, hit))
    print(json.dumps({"units": len(U), "logged_requests": len(seen), "render_found_in_log": sum(hit), "by_label": {f"{k[0]}|{k[1]}": v for k, v in by.items()},
                      "folds": {f"{k[0]}|{k[1]}": v for k, v in Counter((u["fold"], u["label"]) for u in U).items()}}))
    if sum(hit) < 0.95 * len(U):
        raise SystemExit("XFIT_REQPARITY_FAILED")
    print("XFIT_REQPARITY_OK")


def rescap(units_p, out_p):
    """X19r capture: residual after attention (input of post_attention_layernorm) and after the MLP (block output) at every layer,
    averaged over the marked injection span and at the last prompt token; MLP activations averaged over the injection span."""
    import numpy as np
    import torch
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ab_core as C
    import ab_ne as NEM
    tok, model = C.load()
    H = C.Hooked(model)
    units = json.loads(Path(units_p).read_text(encoding="utf-8"))
    st = {"on": False, "off": 0, "a": 0, "b": 0, "last": 0}
    acc = {}

    def put(kind, l, x):
        lo, T = st["off"], x.shape[0]
        a, b = max(st["a"], lo), min(st["b"], lo + T)
        if b > a:
            acc[(kind, "inj", l)] = acc.get((kind, "inj", l), 0) + x[a - lo:b - lo].float().sum(0)
        if lo <= st["last"] < lo + T and kind != "act":
            acc[(kind, "dec", l)] = x[st["last"] - lo].float()

    def h_mid(l):
        def f(mod, args):
            if st["on"]:
                put("mid", l, args[0][0])
        return f

    def h_post(l):
        def f(mod, args, out):
            if st["on"]:
                put("post", l, (out if torch.is_tensor(out) else out[0])[0])
        return f

    def h_act(l):
        def f(mod, args):
            if st["on"]:
                put("act", l, args[0][0])
        return f
    hs = []
    for l, b in enumerate(H.blocks):
        hs.append(b.post_attention_layernorm.register_forward_pre_hook(h_mid(l)))
        hs.append(b.register_forward_hook(h_post(l)))
        hs.append(b.mlp.down_proj.register_forward_pre_hook(h_act(l)))
    dev = C.first_device(model)
    keep, arrs = [], {k: [] for k in ("inj_mid", "inj_post", "dec_mid", "dec_post", "inj_act")}
    import time
    t0 = time.time()
    for k, u in enumerate(units):
        P = list(u["prompt_ids"])
        a, b = NEM.dojo_spans(tok, P)["inj"]
        if b <= a:
            continue
        acc.clear()
        st.update(on=True, a=a, b=b, last=len(P) - 1)
        with torch.inference_mode():
            cache = None
            for s in range(0, len(P), 1024):
                st["off"] = s
                o = model(input_ids=torch.tensor([P[s:s + 1024]], device=dev), past_key_values=cache, use_cache=True, logits_to_keep=1)
                cache = o.past_key_values
            del cache, o
        st["on"] = False
        n = b - a
        for kind in ("mid", "post"):
            arrs[f"inj_{kind}"].append(torch.stack([acc[(kind, "inj", l)] / n for l in range(len(H.blocks))]).half().cpu().numpy())
            arrs[f"dec_{kind}"].append(torch.stack([acc[(kind, "dec", l)] for l in range(len(H.blocks))]).half().cpu().numpy())
        arrs["inj_act"].append(torch.stack([acc[("act", "inj", l)] / n for l in range(len(H.blocks))]).half().cpu().numpy())
        keep.append(u)
        if k % 10 == 0:
            C.log(f"rescap {k + 1}/{len(units)} kept {len(keep)} inj tokens {n} prompt {len(P)} {time.time() - t0:.0f}s")
    for h in hs:
        h.remove()
    np.savez(out_p, uids=np.array([u["uid"] for u in keep]), labels=np.array([u["label"] for u in keep]), folds=np.array([u["fold"] for u in keep]),
             user_task=np.array([u["user_task"] for u in keep]), injection_task=np.array([u["injection_task"] for u in keep]),
             strict=np.array([bool(u["strict"]) for u in keep]), **{k: np.stack(v) for k, v in arrs.items()})
    C.log(f"XFIT_RESCAP_DONE {len(keep)} of {len(units)} units, labels {dict(Counter(u['label'] for u in keep))}")


def auc(s, y):
    import numpy as np
    s, y = np.asarray(s, float), np.asarray(y, bool)
    if y.all() or (~y).all():
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    r = np.empty(len(s))
    r[order] = np.arange(1, len(s) + 1)
    for v in np.unique(s):
        m = s == v
        r[m] = r[m].mean()
    n1, n0 = y.sum(), (~y).sum()
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def resarms(tag, npz, seed_add="41", seed_neu="43"):
    """X19r comparison report and arms (PLAN.md Log 11-27 13:2x)."""
    import numpy as np
    out = NE / "steer_dojo" / f"arms_{tag}.json"
    if out.exists():
        raise SystemExit(f"{out} exists; not overwritten")
    d = np.load(npz)
    y = d["labels"] == "target"
    fol = d["folds"].astype(int)
    grp = d["user_task"]
    itk = d["injection_task"]
    X = {(pos, site): d[f"{pos}_{site}"].astype(np.float32) for pos in ("inj", "dec") for site in ("mid", "post")}
    nl = X[("inj", "mid")].shape[1]

    def center(Z, m):
        Z = Z.copy()
        for t in np.unique(itk[m]):
            mm = m & (itk == t)
            Z[mm] -= Z[mm].mean(0)
        return Z

    def held(Z, l, cen=False):
        r = []
        for A_, B_ in ((0, 1), (1, 0)):
            mA, mB = fol == A_, fol == B_
            ZA = center(Z, mA) if cen else Z
            ZB = center(Z, mB) if cen else Z
            if y[mA].all() or (~y[mA]).all():
                r.append(float("nan"))
                continue
            dvec = ZA[mA & y, l].mean(0) - ZA[mA & ~y, l].mean(0)
            r.append(auc(ZB[mB, l] @ dvec, y[mB]))
        return r

    def loo(Z, l, A_):
        mA = fol == A_
        sc = np.full(len(y), np.nan)
        for g in np.unique(grp[mA]):
            tr, te = mA & (grp != g), mA & (grp == g)
            if y[tr].all() or (~y[tr]).all():
                continue
            dvec = Z[tr & y, l].mean(0) - Z[tr & ~y, l].mean(0)
            sc[te] = Z[te, l] @ dvec
        ok = mA & ~np.isnan(sc)
        return auc(sc[ok], y[ok])
    L = [f"# X19r: slack, target (attack succeeded) vs reference (attack failed), residual stream after attention and after the MLP", "",
         f"units {len(y)}: " + ", ".join(f"fold {f}: {int((fol == f).sum())} ({int((y & (fol == f)).sum())} target / {int((~y & (fol == f)).sum())} reference)" for f in (0, 1)), "",
         "Held-out AUROC of the difference-of-means direction (fit on one user-task fold, scored on the other: 0->1 / 1->0), raw and injection-task centered.", ""]
    best = {}
    for pos in ("inj", "dec"):
        L += [f"## position: {'injection span (mean)' if pos == 'inj' else 'last prompt token (decision)'}", "",
              "| layer | after attn: 0->1 / 1->0 | centered | after MLP: 0->1 / 1->0 | centered | LOO in fold 0 (attn / MLP) | LOO in fold 1 (attn / MLP) |", "|---|---|---|---|---|---|---|"]
        for l in range(nl):
            cells = []
            lo = {}
            for site in ("mid", "post"):
                Z = X[(pos, site)]
                h, hc = held(Z, l), held(Z, l, True)
                cells += [f"{h[0]:.2f} / {h[1]:.2f}", f"{hc[0]:.2f} / {hc[1]:.2f}"]
                for A_ in (0, 1):
                    lo[(site, A_)] = loo(Z, l, A_)
                    if pos == "inj" and 2 <= l <= 29:
                        best.setdefault(A_, []).append((lo[(site, A_)], site, l))
            L.append(f"| {l} | " + " | ".join(cells) + f" | {lo[('mid', 0)]:.2f} / {lo[('post', 0)]:.2f} | {lo[('mid', 1)]:.2f} / {lo[('post', 1)]:.2f} |")
        L.append("")
    rng_a, rng_n = np.random.default_rng(int(seed_add)), np.random.default_rng(int(seed_neu))
    act = d["inj_act"].astype(np.float32)
    NNl = act.shape[2]
    sets, adds, arms_, info = {}, {}, {"base": None}, {}
    for A_ in (0, 1):
        mA = fol == A_
        cand = sorted([b for b in best[A_] if not np.isnan(b[0])], reverse=True)
        a_, site, l = cand[0]
        Z = X[("inj", site)]
        vec = Z[mA & ~y, l].mean(0) - Z[mA & y, l].mean(0)
        r = rng_a.standard_normal(vec.shape[0]).astype(np.float32)
        r *= np.linalg.norm(vec) / np.linalg.norm(r)
        adds[f"a{A_}"] = {"layer": int(l), "site": site, "vec": vec.tolist(), "pick_fold": A_}
        adds[f"a{A_}r"] = {"layer": int(l), "site": site, "vec": r.tolist(), "pick_fold": A_}
        arms_[f"a{A_}_rtr"] = {"add": f"a{A_}", "pick_fold": A_}
        arms_[f"a{A_}r_rtr"] = {"add": f"a{A_}r", "pick_fold": A_}
        At, Ar = act[mA & y].reshape(int((mA & y).sum()), -1), act[mA & ~y].reshape(int((mA & ~y).sum()), -1)
        mt, mr, sr = At.mean(0), Ar.mean(0), Ar.std(0)
        z = (mt - mr) / np.sqrt((At.var(0) + Ar.var(0)) / 2 + 1e-6)
        order = np.argsort(-z)[:1024]
        rnd = [int((i // NNl) * NNl + rng_n.integers(0, NNl)) for i in order]
        mk = lambda ids: [[int(i // NNl), int(i % NNl), float(mr[i] + sr[i])] for i in ids]
        sets[f"n{A_}d1024"], sets[f"n{A_}r1024"] = mk(order), mk(rnd)
        arms_[f"n{A_}d1024_tr"] = {"set": f"n{A_}d1024", "kind": "clamp", "where": "tr", "pick_fold": A_}
        arms_[f"n{A_}r1024_tr"] = {"set": f"n{A_}r1024", "kind": "clamp", "where": "tr", "pick_fold": A_}
        info[f"fold{A_}"] = {"units": int(mA.sum()), "targets": int((mA & y).sum()), "references": int((mA & ~y).sum()),
                             "add": {"site": site, "layer": int(l), "loo_auroc": round(a_, 3), "norm": float(np.linalg.norm(vec)),
                                     "next_best": [(round(x[0], 3), x[1], x[2]) for x in cand[1:4]]},
                             "neu": {"z_first": float(z[order[0]]), "z_last": float(z[order[-1]]), "z_above_1": int((z > 1).sum()),
                                     "layers": sorted(Counter(int(i // NNl) for i in order).items())}}
    L += ["## Chosen arms (cross-fit; picked on fold A, run on the fold-B user tasks)", "", "```", json.dumps(info, indent=1), "```"]
    (NE / "x19r_compare.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    out.write_text(json.dumps({"arms": arms_, "sets": sets, "adds": adds, "info": info, "npz": str(npz)}), encoding="utf-8")
    print("\n".join(L[-40:]))
    print("XFIT_RESARMS_DONE", tag, list(arms_))


def decarms(tag, npz, seed="47"):
    """X19r-dec (사후, PLAN.md Log 11-27 13:5x): the same cross-fit rule at the decision position (last prompt token): site and layer
    with the best leave-one-user-task-out AUROC inside fold A (layers 2-29), vector = fold-A reference mean minus target mean.
    Applied at the onset and every generated token of requests whose prompt holds at least one tool result. Random control: a
    Gaussian direction with the same norm."""
    import numpy as np
    out = NE / "steer_dojo" / f"arms_{tag}.json"
    if out.exists():
        raise SystemExit(f"{out} exists; not overwritten")
    d = np.load(npz)
    y = d["labels"] == "target"
    fol = d["folds"].astype(int)
    grp = d["user_task"]
    rng = np.random.default_rng(int(seed))
    adds, arms_, info = {}, {"base": None}, {}
    for A_ in (0, 1):
        mA = fol == A_
        best = []
        for site in ("mid", "post"):
            Z = d[f"dec_{site}"].astype(np.float32)
            for l in range(2, 30):
                sc = np.full(len(y), np.nan)
                for g in np.unique(grp[mA]):
                    tr, te = mA & (grp != g), mA & (grp == g)
                    if y[tr].all() or (~y[tr]).all():
                        continue
                    sc[te] = Z[te, l] @ (Z[tr & y, l].mean(0) - Z[tr & ~y, l].mean(0))
                ok = mA & ~np.isnan(sc)
                best.append((auc(sc[ok], y[ok]), site, l))
        best = sorted([b for b in best if not np.isnan(b[0])], reverse=True)
        a_, site, l = best[0]
        Z = d[f"dec_{site}"].astype(np.float32)
        vec = Z[mA & ~y, l].mean(0) - Z[mA & y, l].mean(0)
        r = rng.standard_normal(vec.shape[0]).astype(np.float32)
        r *= np.linalg.norm(vec) / np.linalg.norm(r)
        resn = float(np.linalg.norm(Z[mA, l], axis=1).mean())
        adds[f"d{A_}"] = {"layer": int(l), "site": site, "vec": vec.tolist(), "pick_fold": A_}
        adds[f"d{A_}r"] = {"layer": int(l), "site": site, "vec": r.tolist(), "pick_fold": A_}
        arms_[f"d{A_}_gtr"] = {"add": f"d{A_}", "pick_fold": A_}
        arms_[f"d{A_}r_gtr"] = {"add": f"d{A_}r", "pick_fold": A_}
        info[f"fold{A_}"] = {"site": site, "layer": int(l), "loo_auroc": round(a_, 3), "norm": float(np.linalg.norm(vec)), "mean_residual_norm": resn,
                             "next_best": [(round(x[0], 3), x[1], x[2]) for x in best[1:4]]}
    out.write_text(json.dumps({"arms": arms_, "adds": adds, "info": info, "npz": str(npz)}), encoding="utf-8")
    print(json.dumps(info, indent=1))
    print("XFIT_DECARMS_DONE", tag, list(arms_))


class ReadAdd:
    """X19r: add a fixed vector to the residual stream at one layer (site post: block output; site mid: attention output, so the
    residual after attention moves) at prompt positions inside tool results only. Same interface as ab_ne.Clamp (set, mask, off)."""

    def __init__(self, H, layer, site, vec):
        import torch
        self.torch, self.mask, self.off = torch, None, 0
        self.vec = torch.tensor(vec, dtype=torch.float32)
        b = H.blocks[int(layer)]
        mod = b if site == "post" else (b.linear_attn if hasattr(b, "linear_attn") else b.self_attn)
        mod.register_forward_hook(self._hook)

    def set(self, specs):
        self.mask, self.off = None, 0

    def _hook(self, mod, args, out):
        torch = self.torch
        if self.mask is None:
            return None
        o = out if torch.is_tensor(out) else out[0]
        T = o.shape[1]
        if T <= 1:
            return None
        m = self.mask[self.off:self.off + T]
        if not bool(m.any()):
            return None
        o2 = o.clone()
        o2[:, m] = (o2[:, m].float() + self.vec.to(o.device)).to(o.dtype)
        return o2 if torch.is_tensor(out) else (o2,) + tuple(out[1:])


def fisher_less(a, n1, b, n2):
    """One-sided Fisher: P(first group has at most a successes); small when rate 1 < rate 2."""
    tot, k = n1 + n2, a + b
    return sum(comb(n1, x) * comb(n2, k - x) for x in range(max(0, k - n2), min(a, n1, k) + 1)) / comb(tot, k)


def episodes(logdir, suite, tasks):
    out = []
    for f in glob.glob(str(RUNS / logdir / "*" / suite / "user_task_*" / "*" / "*.json")):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except ValueError:
            continue
        if d.get("utility") is None or (d.get("attack_type") and d.get("security") is None):
            continue
        if tasks is not None and int(d["user_task_id"].split("_")[-1]) not in tasks:
            continue
        out.append(d)
    return out


def count(suite, tasks, *pairs):
    tasks = None if tasks == "all" else {int(x) for x in tasks.split(",")}
    res = {}
    for p in pairs:
        lab, ld = p.split("=", 1)
        at = [d for d in episodes(ld, suite, tasks) if d.get("attack_type")]
        na = [d for d in episodes(ld + "_noattack", suite, tasks) if not d.get("attack_type")]
        res[lab] = {"logdir": ld, "n": len(at), "asr": sum(bool(d["security"]) for d in at), "util": sum(bool(d["utility"]) for d in at),
                    "n_na": len(na), "util_na": sum(bool(d["utility"]) for d in na),
                    "by_task": {t: [sum(bool(d["security"]) for d in at if d["user_task_id"] == t), sum(d["user_task_id"] == t for d in at)]
                                for t in sorted({d["user_task_id"] for d in at}, key=lambda x: int(x.split("_")[-1]))}}
    print(f"suite {suite}, user tasks {'all' if tasks is None else sorted(tasks)}")
    print("| arm | ASR | utility under attack | utility without attack | p vs rand | p vs base |")
    print("|---|---|---|---|---|---|")
    for lab, r in res.items():
        ps = []
        for ref in ("rand", "base"):
            if ref in res and ref != lab and r["n"] and res[ref]["n"] and not lab.startswith("rand"):
                ps.append(f"{fisher_less(r['asr'], r['n'], res[ref]['asr'], res[ref]['n']):.3g}")
            else:
                ps.append("-")
        pc = lambda a, b: f"{a}/{b} ({a / b:.0%})" if b else f"{a}/0"
        print(f"| {lab} ({r['logdir']}) | {pc(r['asr'], r['n'])} | {pc(r['util'], r['n'])} | {r['util_na']}/{r['n_na']} | {ps[0]} | {ps[1]} |")
    for lab, r in res.items():
        print(f"  {lab} ASR by user task: " + ", ".join(f"{t.split('_')[-1]}:{a}/{n}" for t, (a, n) in r["by_task"].items()))
    print(json.dumps({k: {x: v[x] for x in ("n", "asr", "util", "n_na", "util_na")} for k, v in res.items()}))


if __name__ == "__main__":
    {"cap": cap, "check": check, "arms": arms, "slackunits": slackunits, "count": count, "reqparity": reqparity, "render": render, "rescap": rescap, "decarms": decarms,
     "resarms": resarms}[sys.argv[1]](*sys.argv[2:])
