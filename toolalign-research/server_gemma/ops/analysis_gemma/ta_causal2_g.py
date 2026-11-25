"""CAUSAL-2 (work/toolalign-research/PLAN.md): interventions over the whole response with greedy regeneration.
Modes: stats | run WORKER NWORKERS | report. GPU 1 or GPU 2. Output ops/analysis/causal2/"""
import copy
import hashlib
import json
import os
import random
import re
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

PTS = ROOT / "ops/analysis_gemma/jlens_points"
C1 = ROOT / "ops/analysis_gemma/causal"
OUT = ROOT / "ops/analysis_gemma/causal2"
RES = ROOT / "runner/results/gemma4-greedy"
CHUNK = 4096
GPUS = {"0": "c27bc2d7"}
NAME_RE = re.compile(r"<tool_name>\s*([^<\s]+)\s*</tool_name>")
BANDS = {"16_26": list(range(16, 27)), "28_38": list(range(28, 39))}


def _softcap(model):
    cfg = model.config.get_text_config() if hasattr(model.config, "get_text_config") else model.config
    return getattr(cfg, "final_logit_softcapping", None)


def capped(logits, cap):
    return logits if not cap else cap * torch.tanh(logits / cap)


def log(m):
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def fold(domain):
    return int(hashlib.md5(domain.encode()).hexdigest(), 16) % 2


def load():
    dev = os.environ.get("CUDA_VISIBLE_DEVICES")
    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID" or dev not in GPUS or GPUS[dev] not in str(torch.cuda.get_device_properties(0).uuid):
        raise SystemExit(f"need CUDA_DEVICE_ORDER=PCI_BUS_ID and CUDA_VISIBLE_DEVICES in {sorted(GPUS)} (got {dev})")
    from transformers import AutoModelForCausalLM, AutoTokenizer
    prof = get_profile("gemma-4-e4b")
    tok = AutoTokenizer.from_pretrained(prof.model_id, revision=prof.model_revision)
    model = AutoModelForCausalLM.from_pretrained(prof.model_id, revision=prof.model_revision, dtype=torch.bfloat16,
                                                 attn_implementation={"text_config": "sdpa", "vision_config": "eager", "audio_config": "eager", "": "sdpa"}, low_cpu_mem_usage=True).cuda().eval()
    for p in model.parameters():
        p.requires_grad_(False)
    return prof, tok, model


def units_all():
    u = json.loads((C1 / "units.json").read_text(encoding="utf-8"))
    ms = {m["key"]: m for m in json.loads((PTS / "steps.json").read_text(encoding="utf-8"))}
    for x in u["targets"] + u["refs"]:
        m = ms[x["key"]]
        x["onset"] = [p["pos"] for p in m["positions"] if p["tag"] == "onset"][0]
        x["uid"] = f"{x['key']}@{x['pos']}"
    if os.environ.get("C2_ONLY"):
        keep = set(Path(os.environ["C2_ONLY"]).read_text(encoding="utf-8").split())
        u["targets"] = [x for x in u["targets"] if x["uid"] in keep]
    rng = random.Random(1)
    byd = defaultdict(list)
    for x in u["refs"]:
        byd[x["domain"]].append(x)
    run_refs = []
    doms = sorted(byd)
    for i, d in enumerate(doms):
        run_refs += rng.sample(byd[d], min(3 if i < 8 else 2, len(byd[d])))
    return u["targets"], u["refs"], run_refs


class Hooked:
    def __init__(self, model):
        self.model = model
        self.lm = model.model if hasattr(model.model, "layers") else model.model.language_model
        self.blocks = self.lm.layers
        self.ops = {}
        self.cap = None
        for i, b in enumerate(self.blocks):
            (b.linear_attn if hasattr(b, "linear_attn") else b.self_attn).register_forward_hook(self._out_hook("attn", i))
            b.mlp.register_forward_hook(self._out_hook("mlp", i))
            b.mlp.down_proj.register_forward_pre_hook(self._down_hook(i))

    def _out_hook(self, kind, i):
        def f(mod, args, out):
            o = out if torch.is_tensor(out) else out[0]
            if self.cap is not None:
                self.cap[(kind, i)] = o[0].float().mean(0).cpu()
            fn = self.ops.get((kind, i))
            if fn is not None:
                o = o.clone()
                o[0, -1] = fn(o[0, -1])
                return o if torch.is_tensor(out) else (o,) + tuple(out[1:])
        return f

    def _down_hook(self, i):
        def f(mod, args):
            x = args[0]
            if self.cap is not None:
                self.cap[("act", i)] = x[0].float().mean(0).cpu()
            fn = self.ops.get(("down", i))
            if fn is not None:
                x = x.clone()
                x[0, -1] = fn(x[0, -1])
                return (x,)
        return f


def seq_of(tok, prof, sel_by_key, u):
    sel = sel_by_key[u["key"]]
    rep = render_replay(tok, sel, context_mode="trajectory", expected_model_revision=prof.model_revision)
    ids = list(rep.token_ids)
    assert ids[u["pos"] + 1] == u["next_id"], "position mismatch"
    return ids


def mode_stats():
    prof, tok, model = load()
    H = Hooked(model)
    targets, refs, _ = units_all()
    sel_by_key = {s.key: s for s in select_steps(load_traces([RES]), scope="all")}
    OUT.mkdir(parents=True, exist_ok=True)
    stats = {}
    t0 = time.time()
    for n, u in enumerate(targets + refs):
        ids = seq_of(tok, prof, sel_by_key, u)
        pre, span = ids[:u["onset"]], ids[u["onset"]:u["pos"] + 1]
        cache = None
        with torch.no_grad():
            for s in range(0, len(pre), CHUNK):
                cache = H.lm(input_ids=torch.tensor([pre[s:s + CHUNK]], device="cuda"), past_key_values=cache, use_cache=True).past_key_values
            H.cap = {}
            H.lm(input_ids=torch.tensor([span], device="cuda"), past_key_values=cache, use_cache=True)
            cap, H.cap = H.cap, None
        nl = len(H.blocks)
        stats[u["uid"]] = {k: torch.stack([cap[(k, i)] for i in range(nl)]).half().numpy() for k in ("act", "attn", "mlp")}
        del cache
        if n % 20 == 0:
            log(f"stats {n}/{len(targets) + len(refs)} {time.time() - t0:.0f}s")
    np.savez(OUT / "stats.npz", uids=np.array(list(stats)), **{k: np.stack([v[k] for v in stats.values()]) for k in ("act", "attn", "mlp")})
    log("STATS_DONE")


def build_configs(targets, refs, nl, nn):
    z = np.load(OUT / "stats.npz")
    idx = {u: i for i, u in enumerate(z["uids"].tolist())}
    act = z["act"].astype(np.float32)
    sets = {}
    rng = np.random.default_rng(7)
    for f in (0, 1):
        ta = [idx[u["uid"]] for u in targets if fold(u["domain"]) == f and u["risk"] != "aligned"]
        ra = [idx[u["uid"]] for u in refs if fold(u["domain"]) == f]
        if not ta or not ra:
            continue
        mt, mr, sr = act[ta].mean(0), act[ra].mean(0), act[ra].std(0)
        score = (np.abs(mt - mr) / (sr + 1e-3)).ravel()
        order = np.argsort(-score)
        lay = np.arange(nl).repeat(nn)
        band = np.isin(lay, BANDS["16_26"])
        order_band = order[band[order]]
        for K in (64, 256, 1024):
            top = order[:K]
            sets[(f, f"neur_top_{K}")] = top
            sets[(f, f"neur_rand_{K}")] = (top // nn) * nn + rng.integers(0, nn, K)
        top = order_band[:256]
        sets[(f, "neur_top_256_L16_26")] = top
        sets[(f, "neur_rand_256_L16_26")] = (top // nn) * nn + rng.integers(0, nn, 256)
    return z, idx, sets


def mode_run(wid, nw):
    prof, tok, model = load()
    H = Hooked(model)
    targets, refs, run_refs = units_all()
    sel_by_key = {s.key: s for s in select_steps(load_traces([RES]), scope="all")}
    nl, nn = len(H.blocks), H.blocks[0].mlp.down_proj.in_features
    z, idx, sets = build_configs(targets, refs, nl, nn)
    act, attn, mlp = (z[k].astype(np.float32) for k in ("act", "attn", "mlp"))
    ge = model.generation_config.eos_token_id
    eos = {tok.eos_token_id} | set(ge if isinstance(ge, list) else [ge])
    CAP = _softcap(model)
    runlist = [("target", u) for u in targets] + [("reference", u) for u in run_refs]
    dyn = os.environ.get("C2_WID")
    if os.environ.get("C2_ONLY"):
        keep = set(Path(os.environ["C2_ONLY"]).read_text(encoding="utf-8").split())
        runlist = [x for x in runlist if x[1]["uid"] in keep]
    mine = runlist if dyn else [x for i, x in enumerate(runlist) if i % nw == wid]
    out_path = OUT / (f"rows_{dyn}.jsonl" if dyn else f"rows_w{wid}.jsonl")
    claims = OUT / "claims_v2"
    claims.mkdir(exist_ok=True)

    def all_done():
        d = set()
        for p in OUT.glob("rows_*.jsonl"):
            for line in p.open(encoding="utf-8"):
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                d.add((r["uid"], r["config"]))
        return d

    done = all_done()
    fh = out_path.open("a", encoding="utf-8")
    log(f"worker {dyn or wid}: {len(mine)} units in list, {len(done)} rows done (all files)")
    t0 = time.time()

    def setter(v):
        vt = torch.tensor(v, device="cuda")
        return lambda x: vt.to(x.dtype)

    def neur(by_l_idx, mu_act):
        fns = {}
        for l, ns in by_l_idx.items():
            it = torch.tensor(ns, device="cuda")
            vt = torch.tensor(mu_act[l, ns], device="cuda")

            def f(x, it=it, vt=vt):
                x = x.clone()
                x[it] = vt.to(x.dtype)
                return x
            fns[("down", l)] = f
        return fns

    for n, (kind, u) in enumerate(mine):
        ri = [idx[r["uid"]] for r in refs if r["domain"] != u["domain"]]
        mu_act, mu_attn, mu_mlp = act[ri].mean(0), attn[ri].mean(0), mlp[ri].mean(0)
        f_sel = 1 - fold(u["domain"])
        cfgs = [("base", {})]
        for name in ("neur_top_64", "neur_rand_64", "neur_top_256", "neur_rand_256", "neur_top_1024", "neur_rand_1024",
                     "neur_top_256_L16_26", "neur_rand_256_L16_26"):
            s = sets.get((f_sel, name))
            if s is None:
                continue
            by_l = defaultdict(list)
            for x in s.tolist():
                by_l[x // nn].append(x % nn)
            cfgs.append((name, neur(by_l, mu_act)))
        for bname, layers in BANDS.items():
            cfgs.append((f"attn_band_{bname}", {("attn", l): setter(mu_attn[l]) for l in layers}))
            cfgs.append((f"mlp_band_{bname}", {("mlp", l): setter(mu_mlp[l]) for l in layers}))
        if os.environ.get("C2_EXTRA") == "1":
            ltypes = model.config.get_text_config().layer_types
            full = [l for l in range(16, 27) if ltypes[l] == "full_attention"]
            slid = [l for l in range(16, 27) if ltypes[l] != "full_attention"]
            extra = {"attn_band_4_14": list(range(4, 15)), f"attn_full_{'_'.join(map(str, full))}": full,
                     "attn_sliding_16_26": slid, "attn_band_16_21": list(range(16, 22)), "attn_band_21_26": list(range(21, 27))}
            for ename, layers in extra.items():
                cfgs.append((ename, {("attn", l): setter(mu_attn[l]) for l in layers}))
        if os.environ.get("C2_CTRL") == "1":
            ltypes = model.config.get_text_config().layer_types
            band = list(range(16, 27))
            outside = [l for l in range(nl) if l not in band]
            full_in = [l for l in band if ltypes[l] == "full_attention"]
            full_out = [l for l in outside if ltypes[l] == "full_attention"]
            for d in range(3):
                r = random.Random(1000 + d)
                l11 = sorted(r.sample(outside, len(band)))
                fo = sorted(r.sample(full_out, len(full_in)))
                cfgs.append((f"attn_rand11_d{d}", {("attn", l): setter(mu_attn[l]) for l in l11}))
                cfgs.append((f"attn_randfull_d{d}", {("attn", l): setter(mu_attn[l]) for l in fo}))
            cfgs.append(("attn_band_16_26_onset", {("attn", l): setter(mu_attn[l]) for l in band}, "onset"))
            cfgs.append(("attn_band_16_26_after", {("attn", l): setter(mu_attn[l]) for l in band}, "after"))
            if kind == "reference":
                ti = [idx[x["uid"]] for x in targets if x["domain"] != u["domain"] and x["risk"] != "aligned"]
                if ti:
                    mt_attn = attn[ti].mean(0)
                    cfgs.append(("rev_attn_band_16_26", {("attn", l): setter(mt_attn[l]) for l in band}))
                    cfgs.append((f"rev_attn_full_{'_'.join(map(str, full_in))}", {("attn", l): setter(mt_attn[l]) for l in full_in}))
        cfgs = [c if len(c) == 3 else (c[0], c[1], "all") for c in cfgs]
        if dyn:
            done = all_done()
        cfgs = [c for c in cfgs if (u["uid"], c[0]) not in done]
        if not cfgs:
            continue
        if dyn and os.environ.get("C2_SWEEP") != "1":
            cid = hashlib.md5((u["uid"] + ("|x" if os.environ.get("C2_EXTRA") == "1" else "") + ("|c" if os.environ.get("C2_CTRL") == "1" else "")).encode()).hexdigest()
            try:
                os.close(os.open(claims / f"{cid}.claim", os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            except FileExistsError:
                continue
        ids = seq_of(tok, prof, sel_by_key, u)
        prompt = ids[:u["onset"] + 1]
        L = u["pos"] - u["onset"]
        budget = min(1024, int(1.5 * L) + 64)
        with torch.no_grad():
            cache0 = None
            pre = prompt[:-1]
            for s in range(0, len(pre), CHUNK):
                cache0 = H.lm(input_ids=torch.tensor([pre[s:s + CHUNK]], device="cuda"), past_key_values=cache0, use_cache=True).past_key_values
            orig_pre = tok.decode(ids[u["onset"] + 1:u["pos"] + 1])
            for cname, od, when in cfgs:
                cache = copy.deepcopy(cache0)
                cur, gen, tool = prompt[-1], [], None
                for t in range(budget):
                    H.ops = od if (when == "all" or (when == "onset" and t == 0) or (when == "after" and t > 0)) else {}
                    o = H.lm(input_ids=torch.tensor([[cur]], device="cuda"), past_key_values=cache, use_cache=True)
                    cache = o.past_key_values
                    cur = int(capped(model.lm_head(o.last_hidden_state[0, -1]).float(), CAP).argmax())
                    gen.append(cur)
                    if cur in eos:
                        break
                    if t % 4 == 3 or t == budget - 1:
                        mt = NAME_RE.search(tok.decode(gen[-80:] if len(gen) > 80 else gen))
                        if mt:
                            tool = mt.group(1)
                            break
                H.ops = {}
                if tool is None:
                    mt = NAME_RE.search(tok.decode(gen))
                    tool = mt.group(1) if mt else None
                text = tok.decode(gen)
                row = {"uid": u["uid"], "set": kind, "risk": u["risk"], "category": u["category"], "domain": u["domain"],
                       "type": u["type"], "condition": u["condition"], "orig_tool": u["tool"], "config": cname, "gen_tool": tool,
                       "n_gen": len(gen), "budget": budget, "orig_len": L, "same_prefix_chars": next((i for i, (a, b) in enumerate(zip(text, orig_pre)) if a != b), min(len(text), len(orig_pre))),
                       "text_head": text[:300]}
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                del cache
            del cache0
        log(f"w{wid} unit {n + 1}/{len(mine)} {kind} {u['tool']} {time.time() - t0:.0f}s")
    log("RUN_DONE")


def mode_report():
    rows, seen = [], set()
    for p in sorted(OUT.glob("rows_*.jsonl")):
        for x in p.open(encoding="utf-8"):
            try:
                r = json.loads(x)
            except ValueError:
                continue
            if (r["uid"], r["config"]) in seen:
                continue
            seen.add((r["uid"], r["config"]))
            rows.append(r)
    base = {r["uid"]: r for r in rows if r["config"] == "base"}
    ok_t = {u for u, r in base.items() if r["set"] == "target" and r["gen_tool"] == r["orig_tool"]}
    ok_r = {u for u, r in base.items() if r["set"] == "reference" and r["gen_tool"] == "writeInternalLog"}
    nt = sum(1 for r in base.values() if r["set"] == "target")
    nr = sum(1 for r in base.values() if r["set"] == "reference")
    excl = {}
    for r in base.values():
        if r["set"] == "target":
            k = r["risk"]
            excl.setdefault(k, [0, 0])
            excl[k][1] += 1
            excl[k][0] += r["uid"] not in ok_t
    md = ["# CAUSAL-2 (Gemma-4-E4B-it): interventions over the whole response, greedy regeneration", "",
          f"- base reproduces the original tool: targets {len(ok_t)}/{nt}, references {len(ok_r)}/{nr}. Only reproducing units are scored.",
          "- targets excluded (base did not reproduce), by risk: " + ", ".join(f"{k} {a}/{b}" for k, (a, b) in sorted(excl.items())),
          "- rev_* rows are on references only: 'refs kept' = still writeInternalLog; 1 - kept = deviation caused by the target-mean attention.", "",
          "| config | flip mis+bnd | flip misaligned | flip boundary | flip aligned email | broken (targets) | other tool (targets) | refs kept | refs broken |",
          "|---|---|---|---|---|---|---|---|---|"]
    by = defaultdict(list)
    for r in rows:
        if (r["set"] == "target" and r["uid"] in ok_t) or (r["set"] == "reference" and r["uid"] in ok_r):
            by[r["config"]].append(r)
    verdict = []
    for cfg in sorted(by, key=lambda c: (c != "base", c)):
        rs = by[cfg]
        t = [r for r in rs if r["set"] == "target"]
        f = lambda xs: (sum(r["gen_tool"] == "writeInternalLog" for r in xs), len(xs))
        mb = f([r for r in t if r["risk"] != "aligned"])
        mi = f([r for r in t if r["risk"] == "clearly-misaligned"])
        bd = f([r for r in t if r["risk"] == "boundary"])
        ae = f([r for r in t if r["risk"] == "aligned"])
        br = (sum(r["gen_tool"] is None for r in t), len(t))
        ot = (sum(r["gen_tool"] not in (None, "writeInternalLog", r["orig_tool"]) for r in t), len(t))
        rf = [r for r in rs if r["set"] == "reference"]
        kept = (sum(r["gen_tool"] == "writeInternalLog" for r in rf), len(rf))
        rbr = (sum(r["gen_tool"] is None for r in rf), len(rf))
        g = lambda x: f"{x[0]}/{x[1]}" + (f" ({x[0] / x[1]:.0%})" if x[1] else "")
        md.append(f"| {cfg} | {g(mb)} | {g(mi)} | {g(bd)} | {g(ae)} | {g(br)} | {g(ot)} | {g(kept)} | {g(rbr)} |")
        verdict.append((cfg, mb, br, kept))
    md += ["", "## Verdict (flip ≥ 50 % mis+bnd, matched random ≤ 10 %, broken ≤ 10 %, refs kept ≥ 90 %)", ""]
    vd = {c: (mb, br, kept) for c, mb, br, kept in verdict}
    for c, (mb, br, kept) in vd.items():
        if not c.startswith(("neur_top", "attn_band", "mlp_band")):
            continue
        rnd = vd.get(c.replace("neur_top", "neur_rand")) if c.startswith("neur_top") else None
        rate = lambda x: x[0] / x[1] if x[1] else 0
        ok = rate(mb) >= 0.5 and rate(br) <= 0.1 and rate(kept) >= 0.9 and (rnd is None or rate(rnd[0]) <= 0.1)
        if c.startswith(("attn_band", "mlp_band")):
            ok = ok and False
            note = " (band edit: no matched random control, reported descriptively)"
        else:
            note = ""
        md.append(f"- {c}: {'LOCALIZED' if ok else 'no'}{note}")
    (OUT / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    m = sys.argv[1]
    if m == "stats":
        mode_stats()
    elif m == "run":
        mode_run(int(sys.argv[2]), int(sys.argv[3]))
    else:
        mode_report()
