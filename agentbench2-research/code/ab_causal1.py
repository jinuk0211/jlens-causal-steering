"""CAUSAL-1 (ToolAlign-4B procedure, PLAN.md): mean replacement at the decision position only, one forward per edit
(batched as rows over a shared prefix cache). Decision position and candidate sets T / A come from ab_core.decision on
the J-lens metas. Metric m = lp(T) - max lp(A); a target flips when m < 0; a reference (reverse edit, set to the target
mean) flips when m > 0.
Edits per target: res_full / res_dir (J-lens direction of W_U[t*] - W_U[a*]) / res_rand / attn / mlp at layers 2..30
step 2; attention and MLP windows of width 4 at stride 2; all-layer attention and MLP; neurons K = 16 / 64 / 256 picked
on the other fold by gradient x (act - mu_ref), and the same number of random neurons in the same layers.
Means are leave-one-group-out over the C1 reference units. Pre-registered reading: flip >= 50 %, random <= 10 %.
Usage: AB_PLATFORM=vast|projectb python ab_causal1.py PTS_DIR UNITS_JSON OUT_DIR"""
import copy
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

import ab_core as C

GRID = list(range(2, 31, 2))
WINDOWS = [list(range(s, s + 4)) for s in range(0, 29, 2)]
KS = (16, 64, 256)
BATCH = 24
ROW_TOKENS = 120000


def main():
    pts, units_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    units = {u["uid"]: u for u in json.loads(units_path.read_text(encoding="utf-8"))}
    metas = [m for m in json.loads((pts / "steps.json").read_text(encoding="utf-8")) if m["uid"] in units]
    tok, model = C.load()
    H = C.Hooked(model)
    lens = C.Lens(model)
    W_U = lens.head.weight
    targets, refs, skip = [], [], defaultdict(int)
    eos = C.eos_ids(tok)

    def tool_div(u, m):
        """AgentDojo, injection tool whose first token is shared with other suite tools: the decision position is the
        first token of the injection tool's name that differs from every other tool with the same prefix. T = that
        token, A = the other tools' tokens at that offset. The unit's own first call must share the prefix."""
        inj = m.get("inj_fn")
        comp = [t for t in u["completion_ids"] if t not in eos]
        mt = C.FUNC_RE.search(tok.decode(comp))
        if not inj or not mt:
            return None
        j0 = C.char_to_token(tok, comp, mt.start(1))
        it = tok.encode(inj, add_special_tokens=False)
        others = [tok.encode(n, add_special_tokens=False) for n in u["suite_tools"] if n != inj]
        for k in range(1, len(it)):
            share = [o for o in others if o[:k] == it[:k] and len(o) > k]
            alt = sorted({o[k] for o in share if o[k] != it[k]})
            if alt:
                break
        else:
            return None
        if comp[j0:j0 + k] != it[:k] or j0 + k >= len(comp):
            return None
        pos = len(u["prompt_ids"]) + j0 + k - 1
        return {"uid": u["uid"], "group": u["group"], "fold": u["fold"], "label": u["label"], "pos": pos, "tag": f"name_div{k}",
                "kind": "tool_div", "T": [it[k]], "A": alt, "next": comp[j0 + k]}
    for m in metas:
        u = units[m["uid"]]
        if u["label"] not in ("target", "reference"):
            continue
        d, why = C.decision(m)
        if not d and m.get("bench") == "dojo" and why == "tool":
            x = tool_div(u, m)
            if x is None:
                skip[f"{u['label']}:tool_div_none"] += 1
            elif (u["label"] == "target" and x["next"] in x["T"]) or (u["label"] == "reference" and x["next"] in x["A"]):
                (targets if u["label"] == "target" else refs).append(x)
            else:
                skip[f"{u['label']}:tool_div_chosen_not_in_side"] += 1
            continue
        if not d:
            skip[f"{u['label']}:{why}"] += 1
            continue
        toks = [c[1] for c in m["cands"]]
        nxt = m["positions"][d["pi"]]["next_id"]
        Tt, At = [toks[i] for i in d["T"]], [toks[i] for i in d["A"]]
        x = {"uid": u["uid"], "group": u["group"], "fold": u["fold"], "label": u["label"], "pos": m["positions"][d["pi"]]["pos"],
             "tag": d["tag"], "kind": d["kind"], "T": sorted(set(Tt)), "A": sorted(set(At)), "next": nxt}
        if u["label"] == "target" and nxt in Tt:
            targets.append(x)
        elif u["label"] == "reference" and nxt in At:
            refs.append(x)
        else:
            skip[f"{u['label']}:chosen_not_in_side"] += 1
    C.log(f"C1 targets {len(targets)}, refs {len(refs)}, skipped {dict(skip)}")

    def seq_of(x):
        u = units[x["uid"]]
        ids = list(u["prompt_ids"]) + [t for t in u["completion_ids"] if t not in C.eos_ids(tok)]
        assert ids[x["pos"] + 1] == x["next"], "position mismatch"
        return ids[:x["pos"] + 1]

    def metric(lp, x):
        return float(lp[x["T"]].max() - lp[x["A"]].max())

    def phase1(x, grad):
        seq = seq_of(x)
        kk = min(4, len(seq) - 1)
        _, cache = C.prefill(model, seq[:-kk], inference=False)
        act_keep = {}

        def keep_act(i):
            def f(mod, args):
                a = args[0]
                if grad:
                    a.retain_grad()
                act_keep[i] = a
            return f
        hs = [b.mlp.down_proj.register_forward_pre_hook(keep_act(i)) for i, b in enumerate(H.blocks)]
        if grad:
            hs.append(H.lm.embed_tokens.register_forward_hook(lambda mod, a, o: o.requires_grad_(True)))
        H.store = {}
        H.cap = {"mode": "pos", "pos": [kk - 1], "kinds": {"res", "attn", "mlp"}}
        with torch.enable_grad() if grad else torch.no_grad():
            o = model(input_ids=torch.tensor([seq[-kk:]], device=C.first_device(model)), past_key_values=cache, use_cache=True, logits_to_keep=1)
            lp = torch.log_softmax(o.logits[0, -1].float(), -1)
            mt = lp[x["T"]].max() - lp[x["A"]].max()
            if grad:
                mt.backward()
        H.cap = None
        for h in hs:
            h.remove()
        rec = {k: torch.stack([H.store[(k, i)][0] for i in range(H.nl)]) for k in ("res", "attn", "mlp")}
        rec["act"] = torch.stack([act_keep[i][0, -1].detach().float().cpu() for i in range(H.nl)])
        if grad:
            rec["grad"] = torch.stack([act_keep[i].grad[0, -1].float().cpu() for i in range(H.nl)])
        rec["m"] = float(mt.detach())
        rec["a_star"] = x["A"][int(lp.detach()[x["A"]].argmax())]
        H.store = {}
        del cache, act_keep
        return rec

    t0 = C.time.time()
    R = {x["uid"]: phase1(x, False) for x in refs}
    C.log(f"ref phase1 done {C.time.time() - t0:.0f}s")
    T = {}
    for n, x in enumerate(targets):
        T[x["uid"]] = phase1(x, True)
        if n % 10 == 0:
            C.log(f"target phase1 {n}/{len(targets)} {C.time.time() - t0:.0f}s")

    def mean_of(xs, store, key, excl=None):
        v = [store[x["uid"]][key] for x in xs if x["group"] != excl]
        return torch.stack(v).mean(0) if v else None

    nn = H.nn
    sel = {}
    for f in (0, 1):
        tf = [x for x in targets if x["fold"] == f]
        rf = [x for x in refs if x["fold"] == f]
        if not tf or not rf:
            continue
        mu_a = mean_of(rf, R, "act")
        score = torch.stack([T[x["uid"]]["grad"] * (T[x["uid"]]["act"] - mu_a) for x in tf]).mean(0).flatten()
        order = torch.argsort(score, descending=True)
        g = torch.Generator().manual_seed(f)
        for K in KS:
            top = order[:K]
            sel[(f, K, "top")] = top.tolist()
            sel[(f, K, "random")] = ((top // nn) * nn + torch.randint(0, nn, (K,), generator=g)).tolist()

    def neur(idx, mu_act):
        by = defaultdict(list)
        for v in idx:
            by[v // nn].append(v % nn)
        return {("down", l): C.Edit("neur", idx=torch.tensor(ns), vec=mu_act[l][ns]) for l, ns in by.items()}

    def run_ops(x, ops):
        seq = seq_of(x)
        _, cache0 = C.prefill(model, seq[:-1])
        res = {}
        bs = max(1, min(BATCH, ROW_TOKENS // max(1, len(seq))))
        for b in range(0, len(ops), bs):
            chunk = ops[b:b + bs]
            cache = C.cache_expand(copy.deepcopy(cache0), len(chunk))
            H.set_rows([e for _, e in chunk])
            with torch.inference_mode():
                o = model(input_ids=torch.tensor([[seq[-1]]] * len(chunk), device=C.first_device(model)), past_key_values=cache,
                          use_cache=True, logits_to_keep=1)
            H.reset()
            lp = torch.log_softmax(o.logits[:, -1].float(), -1).cpu()
            for j, (name, _) in enumerate(chunk):
                res[name] = lp[j]
            del cache
        del cache0
        return res

    gen = torch.Generator().manual_seed(123)
    rows_path = out / "rows.jsonl"
    done = set()
    if rows_path.is_file():
        for line in rows_path.open(encoding="utf-8"):
            try:
                r = json.loads(line)
                done.add((r["set"], r["uid"]))
            except ValueError:
                pass
    fh = rows_path.open("a", encoding="utf-8")
    C.log(f"resume: {len(done)} units already have rows")

    def emit(rs):
        for r in rs:
            fh.write(json.dumps(r) + chr(10))
        fh.flush()

    for n, x in enumerate(targets):
        g = x["group"]
        mu = {k: mean_of(refs, R, k, excl=g) for k in ("res", "attn", "mlp", "act")}
        if mu["res"] is None:
            continue
        b = T[x["uid"]]
        ops = [("base", {})]
        t_star, a_star = x["next"], b["a_star"]
        dvec = (W_U[t_star].float() - W_U[a_star].float()) * lens.gw
        for l in GRID:
            ops.append((f"res_full@{l}", {("res", l): C.Edit("set", vec=mu["res"][l])}))
            Jd = (lens.J[l].T @ dvec) if l in lens.J else dvec
            Jd = (Jd / Jd.norm()).cpu()
            ops.append((f"res_dir@{l}", {("res", l): C.Edit("dir", vec=Jd, coef=float(mu["res"][l] @ Jd))}))
            r = torch.randn(Jd.shape[0], generator=gen)
            r = r / r.norm()
            ops.append((f"res_rand@{l}", {("res", l): C.Edit("dir", vec=r, coef=float(mu["res"][l] @ r))}))
            ops.append((f"attn@{l}", {("attn", l): C.Edit("set", vec=mu["attn"][l])}))
            ops.append((f"mlp@{l}", {("mlp", l): C.Edit("set", vec=mu["mlp"][l])}))
        for w in WINDOWS:
            ops.append((f"attn_w{w[0]}_{w[-1]}", {("attn", l): C.Edit("set", vec=mu["attn"][l]) for l in w}))
            ops.append((f"mlp_w{w[0]}_{w[-1]}", {("mlp", l): C.Edit("set", vec=mu["mlp"][l]) for l in w}))
        ops.append(("attn_all", {("attn", l): C.Edit("set", vec=mu["attn"][l]) for l in range(H.nl)}))
        ops.append(("mlp_all", {("mlp", l): C.Edit("set", vec=mu["mlp"][l]) for l in range(H.nl)}))
        fo = 1 - x["fold"]
        for K in KS:
            for tg in ("top", "random"):
                if (fo, K, tg) in sel:
                    ops.append((f"neur_{tg}_{K}", neur(sel[(fo, K, tg)], mu["act"])))
        if ("target", x["uid"]) in done:
            continue
        lps = run_ops(x, ops)
        bm = metric(lps["base"], x)
        emit([{"uid": x["uid"], "set": "target", "kind": x["kind"], "group": g, "op": name, "m": metric(lp, x), "base_m": bm,
               "phase1_m": b["m"], "flip": metric(lp, x) < 0} for name, lp in lps.items()])
        if n % 5 == 0:
            C.log(f"target {n + 1}/{len(targets)} {C.time.time() - t0:.0f}s")
    for n, x in enumerate(refs):
        g = x["group"]
        mt = {k: mean_of(targets, T, k, excl=g) for k in ("res", "attn", "mlp")}
        if mt["res"] is None:
            continue
        ops = [("base", {})]
        for l in GRID:
            ops.append((f"res_full@{l}", {("res", l): C.Edit("set", vec=mt["res"][l])}))
            ops.append((f"attn@{l}", {("attn", l): C.Edit("set", vec=mt["attn"][l])}))
            ops.append((f"mlp@{l}", {("mlp", l): C.Edit("set", vec=mt["mlp"][l])}))
        for w in WINDOWS:
            ops.append((f"attn_w{w[0]}_{w[-1]}", {("attn", l): C.Edit("set", vec=mt["attn"][l]) for l in w}))
        if ("reference", x["uid"]) in done:
            continue
        lps = run_ops(x, ops)
        bm = metric(lps["base"], x)
        emit([{"uid": x["uid"], "set": "reference", "kind": x["kind"], "group": g, "op": name, "m": metric(lp, x), "base_m": bm,
               "phase1_m": R[x["uid"]]["m"], "flip": metric(lp, x) > 0} for name, lp in lps.items()])
        if n % 25 == 0:
            C.log(f"reference {n + 1}/{len(refs)} {C.time.time() - t0:.0f}s")
    fh.close()
    rows = [json.loads(l) for l in rows_path.open(encoding="utf-8") if l.strip()]
    (out / "rows.json").write_text(json.dumps(rows), encoding="utf-8")
    (out / "units.json").write_text(json.dumps({"targets": targets, "refs": refs, "skipped": skip,
                                                "sel": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in sel.items()}}), encoding="utf-8")
    report(rows, out)
    C.log("CAUSAL1_DONE")


def report(rows, out):
    by = defaultdict(list)
    for r in rows:
        by[(r["set"], r["op"])].append(r)
    drift = [abs(r["base_m"] - r["phase1_m"]) for r in rows if r["op"] == "base"]
    md = ["# CAUSAL-1: mean replacement at the decision position", "",
          f"- baseline drift |m_base - m_phase1|: mean {np.mean(drift):.3f}, max {np.max(drift):.3f}" if drift else "- no rows",
          f"- base flips (should be 0): {sum(r['flip'] for r in rows if r['op'] == 'base')}", "",
          "| set | op | flip | n | mean m |", "|---|---|---|---|---|"]

    def key(o):
        a, _, b = o.partition("@")
        return (a, int(b) if b else -1)
    for (s, op) in sorted(by, key=lambda k: (k[0], key(k[1]))):
        rs = by[(s, op)]
        md.append(f"| {s} | {op} | {np.mean([r['flip'] for r in rs]):.2f} | {len(rs)} | {np.mean([r['m'] for r in rs]):+.2f} |")
    md += ["", "Pre-registered reading: an op localizes if flip >= 50 % on targets and its random control <= 10 %."]
    (out / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
