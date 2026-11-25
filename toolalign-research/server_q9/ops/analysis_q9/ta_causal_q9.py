"""CAUSAL-1 (work/toolalign-research/PLAN.md): mean-matching interventions at the tool-name decision position.
GPU 2. Output ops/analysis/causal/{rows.json, units.json, report.md}"""
import copy
import hashlib
import json
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

ROOT = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench")
sys.path.insert(0, str(ROOT / "jlens_experiment"))
from model_profiles import get_profile
from trace_replay import load_traces, render_replay, select_steps

PTS = ROOT / "ops/analysis_q9/jlens_points"
OUT = ROOT / "ops/analysis_q9/causal"
RES = ROOT / "runner/results/qwen9-greedy"
GRID = list(range(2, 31, 2))
BAND = list(range(12, 21))
KS = (16, 64, 256)
CHUNK = 4096
REF_PER_DOMAIN = 10


def log(m):
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def fold(domain):
    return int(hashlib.md5(domain.encode()).hexdigest(), 16) % 2


def main():
    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID" or os.environ.get("CUDA_VISIBLE_DEVICES") != "0":
        log("need CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0")
        return 2
    if "c27bc2d7" not in str(torch.cuda.get_device_properties(0).uuid):
        log("wrong GPU")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    import transformers.models.qwen3_5.modeling_qwen3_5 as mq
    orig_chunk = mq.torch_chunk_gated_delta_rule

    def chunk_clone(*a, initial_state=None, **kw):
        return orig_chunk(*a, initial_state=None if initial_state is None else initial_state.clone(), **kw)

    mq.torch_chunk_gated_delta_rule = chunk_clone
    import jlens
    from transformers import AutoModelForCausalLM, AutoTokenizer
    prof = get_profile("qwen3.5-9b")
    tok = AutoTokenizer.from_pretrained(prof.model_id, revision=prof.model_revision)
    model = AutoModelForCausalLM.from_pretrained(prof.model_id, revision=prof.model_revision, dtype=torch.bfloat16,
                                                 attn_implementation="sdpa", low_cpu_mem_usage=True).cuda().eval()
    for p in model.parameters():
        p.requires_grad_(False)
    lens = jlens.JacobianLens.from_pretrained(prof.lens_repo, filename=prof.lens_file, revision=prof.lens_revision)
    lm = model.model if hasattr(model.model, "layers") else model.model.language_model
    blocks = lm.layers
    nl = len(blocks)
    fnorm = lm.norm
    W_U = model.lm_head.weight
    gamma = fnorm.weight.float()
    gw = gamma if gamma.abs().mean() > 0.5 else 1 + gamma

    metas = json.loads((PTS / "steps.json").read_text(encoding="utf-8"))
    w_id = tok.encode("writeInternalLog", add_special_tokens=False)[0]
    targets, refs = [], []
    for m in metas:
        ni = 0
        for p in m["positions"]:
            if not p["tag"].startswith("name_"):
                continue
            call = m["calls"][ni] if ni < len(m["calls"]) else None
            ni += 1
            if call is None:
                continue
            c_id = tok.encode(call["name"], add_special_tokens=False)[0]
            u = {"key": m["key"], "domain": m["domain"], "type": m["type"], "condition": m["condition"], "pos": p["pos"],
                 "next_id": p["next_id"], "tool": call["name"], "risk": call["risk"], "category": call["category"],
                 "c": c_id, "cands": [i for i in m["cand_first_ids"][:-1]]}
            if call["name"] == "writeInternalLog":
                refs.append(u)
            elif c_id != w_id and p["next_id"] == c_id:
                targets.append(u)
    rng = random.Random(0)
    byd = defaultdict(list)
    for u in refs:
        byd[u["domain"]].append(u)
    refs = [u for d in sorted(byd) for u in rng.sample(byd[d], min(REF_PER_DOMAIN, len(byd[d])))]
    lim = int(os.environ.get("CAUSAL_LIMIT", "0"))
    if lim:
        targets = [u for u in targets if u["risk"] != "aligned"][:lim] + [u for u in targets if u["risk"] == "aligned"][:1]
        refs = refs[::max(1, len(refs) // (2 * lim))][:2 * lim]
        OUT_ = OUT / "smoke"
    else:
        OUT_ = OUT
    log(f"targets {len(targets)} ({dict((k, sum(1 for u in targets if u['risk'] == k)) for k in ('clearly-misaligned', 'boundary', 'aligned'))}), refs {len(refs)}")
    traces = load_traces([RES])
    sel_by_key = {s.key: s for s in select_steps(traces, scope="all")}

    cap = {"on": False}
    ops = {}

    def put(store, key, t):
        if cap.get("on"):
            store[key] = t

    def h_block(i):
        def f(mod, args, out):
            o = out if torch.is_tensor(out) else out[0]
            if cap.get("on"):
                cap.setdefault("res", {})[i] = o[0, -1].detach().float().cpu()
            fn = ops.get(("block", i))
            if fn is not None:
                o = o.clone()
                o[0, -1] = fn(o[0, -1])
                return o if torch.is_tensor(out) else (o,) + tuple(out[1:])
        return f

    def h_attn(i):
        def f(mod, args, out):
            o = out if torch.is_tensor(out) else out[0]
            if cap.get("on"):
                cap.setdefault("attn", {})[i] = o[0, -1].detach().float().cpu()
            fn = ops.get(("attn", i))
            if fn is not None:
                o = o.clone()
                o[0, -1] = fn(o[0, -1])
                return o if torch.is_tensor(out) else (o,) + tuple(out[1:])
        return f

    def h_mlp(i):
        def f(mod, args, out):
            if cap.get("on"):
                cap.setdefault("mlp", {})[i] = out[0, -1].detach().float().cpu()
            fn = ops.get(("mlp", i))
            if fn is not None:
                o = out.clone()
                o[0, -1] = fn(o[0, -1])
                return o
        return f

    def h_down(i):
        def f(mod, args):
            x = args[0]
            if cap.get("on"):
                if x.requires_grad:
                    x.retain_grad()
                cap.setdefault("act", {})[i] = x
            fn = ops.get(("down", i))
            if fn is not None:
                x = x.clone()
                x[0, -1] = fn(x[0, -1])
                return (x,)
        return f

    def h_emb(mod, args, out):
        if cap.get("grad"):
            out.requires_grad_(True)
        return out

    lm.embed_tokens.register_forward_hook(h_emb)
    for i, b in enumerate(blocks):
        b.register_forward_hook(h_block(i))
        (b.linear_attn if hasattr(b, "linear_attn") else b.self_attn).register_forward_hook(h_attn(i))
        b.mlp.register_forward_hook(h_mlp(i))
        b.mlp.down_proj.register_forward_pre_hook(h_down(i))

    def seq_of(u):
        sel = sel_by_key[u["key"]]
        rep = render_replay(tok, sel, context_mode="trajectory", expected_model_revision=prof.model_revision)
        ids = list(rep.token_ids)
        assert ids[u["pos"] + 1] == u["next_id"], "position mismatch"
        return ids[:u["pos"] + 1]

    def metric(lp, u):
        if u["tool"] == "writeInternalLog":
            others = [c for c in u["cands"] if c != w_id]
            return float(lp[w_id] - lp[others].max())
        return float(lp[u["c"]] - lp[w_id])

    def phase1(u, grad):
        seq = seq_of(u)
        kk = min(4, len(seq) - 1)
        cache = None
        with torch.no_grad():
            for s in range(0, len(seq) - kk, CHUNK):
                ids = torch.tensor([seq[s:min(s + CHUNK, len(seq) - kk)]], device="cuda")
                cache = lm(input_ids=ids, past_key_values=cache, use_cache=True).past_key_values
        cap.clear()
        cap["on"] = True
        cap["grad"] = grad
        with torch.enable_grad() if grad else torch.no_grad():
            out = lm(input_ids=torch.tensor([seq[-kk:]], device="cuda"), past_key_values=cache, use_cache=True)
            lp = torch.log_softmax(model.lm_head(out.last_hidden_state[0, -1]).float(), -1)
            m = (lp[u["c"]] - lp[w_id]) if u["tool"] != "writeInternalLog" else None
            if grad and m is not None:
                m.backward()
        cap["on"] = False
        rec = {k: torch.stack([cap[k][i] for i in range(nl)]) for k in ("res", "attn", "mlp")}
        rec["act"] = torch.stack([cap["act"][i][0, -1].detach().float().cpu() for i in range(nl)])
        if grad and m is not None:
            rec["grad"] = torch.stack([cap["act"][i].grad[0, -1].float().cpu() for i in range(nl)])
        rec["m"] = metric(lp.detach(), u)
        cap.clear()
        del cache
        return rec

    t0 = time.time()
    R = {}
    for n, u in enumerate(refs):
        R[id(u)] = phase1(u, False)
        if n % 20 == 0:
            log(f"ref phase1 {n}/{len(refs)} {time.time() - t0:.0f}s")
    T = {}
    for n, u in enumerate(targets):
        T[id(u)] = phase1(u, True)
        if n % 10 == 0:
            log(f"target phase1 {n}/{len(targets)} {time.time() - t0:.0f}s")

    def mean_of(units, store, key, excl=None, keep=None):
        xs = [store[id(v)][key] for v in units if (excl is None or v["domain"] != excl) and (keep is None or keep(v))]
        return torch.stack(xs).mean(0) if xs else None

    nn = T[id(targets[0])]["act"].shape[1] if targets else 9216
    sel_sets = {}
    for f in (0, 1):
        tf = [u for u in targets if fold(u["domain"]) == f and u["risk"] != "aligned"]
        mu_a = mean_of(refs, R, "act", keep=lambda v: fold(v["domain"]) == f)
        if not tf or mu_a is None:
            continue
        score = torch.stack([T[id(u)]["grad"] * (T[id(u)]["act"] - mu_a) for u in tf]).mean(0).flatten()
        order = torch.argsort(score, descending=True)
        g = torch.Generator().manual_seed(f)
        for K in KS:
            top = order[:K]
            layers = top // nn
            rand = layers * nn + torch.randint(0, nn, (K,), generator=g)
            sel_sets[(f, K, "top")] = top.tolist()
            sel_sets[(f, K, "random")] = rand.tolist()

    def one_step(seq, opsd):
        cache = None
        with torch.no_grad():
            for s in range(0, len(seq) - 1, CHUNK):
                ids = torch.tensor([seq[s:min(s + CHUNK, len(seq) - 1)]], device="cuda")
                cache = lm(input_ids=ids, past_key_values=cache, use_cache=True).past_key_values
        res = {}
        for name, od in opsd:
            ops.clear()
            ops.update(od)
            with torch.no_grad():
                out = lm(input_ids=torch.tensor([[seq[-1]]], device="cuda"), past_key_values=copy.deepcopy(cache), use_cache=True)
                lp = torch.log_softmax(model.lm_head(out.last_hidden_state[0, -1]).float(), -1)
            ops.clear()
            res[name] = lp
        del cache
        return res

    def setter(vec):
        v = vec.cuda()
        return lambda x: v.to(x.dtype)

    def dir_matcher(d, coef):
        d = d.cuda()

        def f(x):
            xf = x.float()
            return (xf + (coef - xf @ d) * d).to(x.dtype)
        return f

    def neuron_setter(idx, vals):
        idx_t = torch.tensor(idx, device="cuda")
        v = vals.cuda()

        def f(x):
            x = x.clone()
            x[idx_t] = v.to(x.dtype)
            return x
        return f

    rows = []
    gen = torch.Generator().manual_seed(123)
    for n, u in enumerate(targets):
        d0 = u["domain"]
        mu = {k: mean_of(refs, R, k, excl=d0) for k in ("res", "attn", "mlp", "act")}
        opl = [("base", {})]
        dvec = (W_U[u["c"]].float() - W_U[w_id].float()) * gw
        for l in GRID:
            opl.append((f"res_full@{l}", {("block", l): setter(mu["res"][l])}))
            Jd = (lens.jacobians[l].to(dvec.device).T @ dvec) if l in lens.jacobians else dvec
            Jd = (Jd / Jd.norm()).cpu()
            opl.append((f"res_dir@{l}", {("block", l): dir_matcher(Jd, float(mu["res"][l] @ Jd))}))
            r = torch.randn(Jd.shape[0], generator=gen)
            r = r / r.norm()
            opl.append((f"res_rand@{l}", {("block", l): dir_matcher(r, float(mu["res"][l] @ r))}))
            opl.append((f"attn@{l}", {("attn", l): setter(mu["attn"][l])}))
            opl.append((f"mlp@{l}", {("mlp", l): setter(mu["mlp"][l])}))
        opl.append(("attn_band", {("attn", l): setter(mu["attn"][l]) for l in BAND}))
        opl.append(("mlp_band", {("mlp", l): setter(mu["mlp"][l]) for l in BAND}))
        opl.append(("attn_all", {("attn", l): setter(mu["attn"][l]) for l in range(nl)}))
        opl.append(("mlp_all", {("mlp", l): setter(mu["mlp"][l]) for l in range(nl)}))
        f_sel = 1 - fold(d0)
        for K in KS:
            for tag in ("top", "random"):
                idx = sel_sets.get((f_sel, K, tag))
                if idx is None:
                    continue
                by_l = defaultdict(list)
                for x in idx:
                    by_l[x // nn].append(x % nn)
                opl.append((f"neur_{tag}_{K}", {("down", l): neuron_setter(ns, mu["act"][l][ns]) for l, ns in by_l.items()}))
        lps = one_step(seq_of(u), opl)
        base_m = metric(lps["base"], u)
        for name, lp in lps.items():
            mm = metric(lp, u)
            cands = torch.tensor(u["cands"], device=lp.device)
            rows.append({"unit": n, "set": "target", "risk": u["risk"], "category": u["category"], "domain": d0, "tool": u["tool"],
                         "type": u["type"], "op": name, "m": mm, "base_m": base_m, "phase1_m": T[id(u)]["m"],
                         "flip": mm < 0, "w_top": int(cands[lp[cands].argmax()]) == w_id})
        if n % 5 == 0:
            log(f"target {n}/{len(targets)} {time.time() - t0:.0f}s")
    for n, u in enumerate(refs):
        d0 = u["domain"]
        mu_t = {k: mean_of(targets, T, k, excl=d0, keep=lambda v: v["risk"] != "aligned") for k in ("res", "attn", "mlp")}
        if mu_t["res"] is None:
            continue
        opl = [("base", {})]
        for l in GRID:
            opl.append((f"res_full@{l}", {("block", l): setter(mu_t["res"][l])}))
            opl.append((f"attn@{l}", {("attn", l): setter(mu_t["attn"][l])}))
            opl.append((f"mlp@{l}", {("mlp", l): setter(mu_t["mlp"][l])}))
        lps = one_step(seq_of(u), opl)
        base_m = metric(lps["base"], u)
        for name, lp in lps.items():
            mm = metric(lp, u)
            rows.append({"unit": n, "set": "reference", "risk": u["risk"], "category": u["category"], "domain": d0, "tool": u["tool"],
                         "type": u["type"], "op": name, "m": mm, "base_m": base_m, "phase1_m": R[id(u)]["m"], "flip": mm < 0})
        if n % 20 == 0:
            log(f"reference {n}/{len(refs)} {time.time() - t0:.0f}s")
    OUT_.mkdir(parents=True, exist_ok=True)
    (OUT_ / "rows.json").write_text(json.dumps(rows), encoding="utf-8")
    (OUT_ / "units.json").write_text(json.dumps({"targets": targets, "refs": refs,
                                                "sel_sets": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in sel_sets.items()}}, default=str), encoding="utf-8")
    summarize(rows, OUT_)
    log("CAUSAL1_DONE")
    return 0


def summarize(rows, out_dir):
    import collections
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["set"], r["op"])].append(r)
    drift = [abs(r["base_m"] - r["phase1_m"]) for r in rows if r["op"] == "base"]
    md = ["# CAUSAL-1 (Qwen3.5-9B, J++ lens): mean-matching at the tool-name position", "",
          f"- baseline drift |m_base - m_phase1|: mean {np.mean(drift):.3f}, max {np.max(drift):.3f}",
          f"- base flips (should be 0): {sum(r['flip'] for r in rows if r['op'] == 'base' and r['set'] == 'target')}", ""]

    def rate(rs, pred):
        rs = [r for r in rs if pred(r)]
        return (sum(r["flip"] for r in rs) / len(rs), len(rs)) if rs else (None, 0)

    md += ["## Targets (non-writeInternalLog choices): flip rate = share where writeInternalLog's first token overtakes the chosen tool's", "",
           "| op | misaligned+boundary | clearly-misaligned | boundary | aligned email | mean m' (mis+bnd) |", "|---|---|---|---|---|---|"]
    ops_order = sorted({op for (s, op) in by if s == "target"}, key=lambda o: (o.split("@")[0], int(o.split("@")[1]) if "@" in o else -1))
    for op in ops_order:
        rs = by[("target", op)]
        a = rate(rs, lambda r: r["risk"] != "aligned")
        b = rate(rs, lambda r: r["risk"] == "clearly-misaligned")
        c = rate(rs, lambda r: r["risk"] == "boundary")
        e = rate(rs, lambda r: r["risk"] == "aligned")
        mm = np.mean([r["m"] for r in rs if r["risk"] != "aligned"])
        f = lambda x: "-" if x[0] is None else f"{x[0]:.2f} (n={x[1]})"
        md.append(f"| {op} | {f(a)} | {f(b)} | {f(c)} | {f(e)} | {mm:.2f} |")
    md += ["", "## Reference (writeInternalLog choices) set to the TARGET mean: flip rate = writeInternalLog loses to another tool", "",
           "| op | flip rate | mean m_ref' |", "|---|---|---|"]
    for op in sorted({op for (s, op) in by if s == "reference"}, key=lambda o: (o.split("@")[0], int(o.split("@")[1]) if "@" in o else -1)):
        rs = by[("reference", op)]
        md.append(f"| {op} | {np.mean([r['flip'] for r in rs]):.2f} (n={len(rs)}) | {np.mean([r['m'] for r in rs]):.2f} |")
    (OUT / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    sys.exit(main())
