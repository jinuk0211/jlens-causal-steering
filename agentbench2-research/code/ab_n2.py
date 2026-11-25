"""N2 + N3 (PLAN.md MAIN QUESTION): position x method on identical footing, with collateral damage in every cell.
Methods:
  - official CAA / ITI / MERA / AUSteer: fitted with the official jlens_causal.official fit code on CALIBRATION pairs.
    The runtime math of each official steer() is applied inside our gated per-row hook:
      CAA      residual += m * v at layer 16;
      ITI      o_proj input += alpha * direction (top-16 heads of a K=48 fit);
      MERA     the official MERA.steer(activations, layer) on post_attention_layernorm outputs;
      AUSteer  o_proj input += o_proj input * mask (official set_MFU mask, top_k 8).
  - neurons, Anthropic-style (N1 lexicon selection, no labels): clamp to mu_ref (K = 16 / 64 / 256), or add
    -a * median residual norm along the normalized sum of the K=64 neurons' output directions (a = 0.25 / 0.5 / 1).
  - neurons, contrastive (|mu_t - mu_r| / sigma_r on CALIBRATION stats): clamp to mu_ref, K = 16 / 64 / 256.
  - controls: random neurons (same layers, chosen K), random CAA direction (same norm), random ITI directions.
Positions: all (every generated position of the regenerated step or response) vs commit (onset through the step that
predicts the first tool-name token). Pairs for the fits: each CALIBRATION target with a CALIBRATION reference of the same
group (agentic-misalignment: same condition, identical prompt; AgentDojo: same user task), positive = the reference
continuation, negative = the target continuation. Tuning: 3 strengths per method on CALIBRATION, best S =
flip x (1 - broken) x refs_kept; TEST run once.
Usage: AB_PLATFORM=vast|projectb python ab_n2.py fit|tune|test|report dojo|am UNITS_JSON C2_DIR N1_JSON OUT_DIR"""
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

import ab_core as C
import ab_regen as R

POS = ("all", "commit")
STRENGTHS = {"caa": (0.5, 1.0, 2.0), "iti": (5.0, 10.0, 20.0), "mera": (0.001, 0.331, 0.661), "austeer": (10.0, 20.0, 50.0),
             "neur_anth_clamp": (16, 64, 256), "neur_anth_add": (0.25, 0.5, 1.0), "neur_contrast": (16, 64, 256)}
CAA_LAYERS, CAA_LAYER, ITI_FIT_K, ITI_K = [12, 16, 20], 16, 48, 16
COMMON = {"model_id": C.MODEL, "model_revision": C.REV}


def comp_text(tok, u):
    return tok.decode([t for t in u["completion_ids"] if t not in C.eos_ids(tok)])


def message_of(bench, text):
    if bench == "am":
        return {"content": text}
    calls = [{"name": n, "arguments": a} for n, a in C.parse_calls(text)]
    content = C.CALL_RE.sub("", text).strip()
    return {"content": content or None, "tool_calls": calls}


def build_pairs(bench, units, tok):
    from am_markers import marker_end
    from jlens_causal.official.data import RenderedPair
    cal = [u for u in units if u["fold"] == 0]
    refs = defaultdict(list)
    for u in cal:
        if u["label"] == "reference":
            refs[u["group"]].append(u)
    pairs, examples, why = [], [], Counter()
    for i, t in enumerate(sorted((u for u in cal if u["label"] == "target"), key=lambda u: u["uid"])):
        pool = sorted(refs.get(t["group"], []), key=lambda u: u["uid"])
        if not pool:
            why["no_reference_in_group"] += 1
            continue
        r = pool[i % len(pool)]
        neg, pos = comp_text(tok, t), comp_text(tok, r)
        if bench == "am":
            mk = marker_end(t["scenario"], neg)
            neg = neg[:mk] if mk else neg
            pos = pos[:len(neg)]
        if not pos.strip() or not neg.strip() or pos == neg:
            why["empty_or_equal"] += 1
            continue
        prompt = tok.decode(t["prompt_ids"])
        pm, nm = message_of(bench, pos), message_of(bench, neg)
        if bench == "dojo" and not (pm.get("content") or pm.get("tool_calls")):
            why["empty_positive_action"] += 1
            continue
        pairs.append(RenderedPair(pair_id=t["uid"], split="train", task_id=t["group"], failure_category=f"ab_{bench}",
                                  prompt=prompt, positive=pos, negative=neg, positive_message=pm, negative_message=nm, context=[]))
        examples.append({"record_id": t["uid"], "prompt": prompt, "positive": pm, "negative": nm})
        why["pair"] += 1
    return pairs, examples, why


def derive_iti(art, k, random_dirs, n_heads):
    import copy
    art = copy.deepcopy(art)
    top = [tuple(x) for x in art["fit"]["top_heads"]][:k]
    keep = defaultdict(set)
    for layer, head in top:
        keep[str(layer)].add(int(head))
    dirs = art["state"]["directions"]
    hd = next(iter(dirs.values())).numel() // n_heads
    g = torch.Generator().manual_seed(1)
    new = {}
    for key, d in dirs.items():
        if key not in keep:
            continue
        nd = torch.zeros_like(d)
        for h in sorted(keep[key]):
            seg = d[h * hd:(h + 1) * hd]
            if random_dirs:
                r = torch.randn(seg.shape, generator=g, dtype=torch.float32)
                seg = (r / r.norm() * seg.float().norm()).to(d.dtype)
            nd[h * hd:(h + 1) * hd] = seg
        new[key] = nd
    return new


def mode_fit(bench, units, c2, out, tok, model, H):
    from jlens_causal.official import austeer, caa, iti, mera
    art = out / "art"
    art.mkdir(parents=True, exist_ok=True)
    pairs, examples, why = build_pairs(bench, units, tok)
    C.log(f"fit pairs: {dict(why)}")
    runtime = SimpleNamespace(torch=torch, tokenizer=tok, hf_model=model)
    status = {"pairs": dict(why)}
    run = R.runset(units, 0, bench, 11)
    norms = defaultdict(list)
    for u in run:
        P = u["prompt_ids"]
        _, cache = C.prefill(model, P[:-1])
        H.store = {}
        H.cap = {"mode": "pos", "pos": [0], "kinds": {"res"}}
        with torch.inference_mode():
            model(input_ids=torch.tensor([[P[-1]]], device=C.first_device(model)), past_key_values=cache, use_cache=True, logits_to_keep=1)
        H.cap = None
        for l in range(H.nl):
            norms[l].append(float(H.store[("res", l)][0].norm()))
        H.store = {}
        del cache
    status["median_res_norm"] = [statistics.median(norms[l]) for l in range(H.nl)]

    def step(name, fn):
        import traceback
        try:
            fn()
            status[name] = "ok"
        except Exception:
            status[name] = "FAILED " + traceback.format_exc()[-600:]
            C.log(f"{name} failed: {status[name]}")
        torch.cuda.empty_cache()
        (out / "fit.json").write_text(json.dumps(status, indent=1), encoding="utf-8")

    step("caa", lambda: caa.fit_items(runtime, caa.build_ab_items_from_rendered(examples), layers=CAA_LAYERS, behavior=f"ab_{bench}",
                                      output_path=art / "caa.pt", data={"split": "train", "count": len(examples)}, **COMMON,
                                      extra_deviations=("A/B prompts are the exact rendered decision-step prompts of CALIBRATION "
                                                        "targets; positive = a same-group CALIBRATION reference continuation.",)))
    step("iti", lambda: iti.fit(runtime, pairs, num_heads_to_intervene=ITI_FIT_K, seed=42, val_ratio=0.2, output_path=art / "iti48.pt", **COMMON))
    step("mera", lambda: mera.fit(runtime, pairs, seed=42, output_path=art / "mera.pt", **COMMON))
    step("austeer", lambda: austeer.fit(runtime, pairs, output_path=art / "austeer.pt", applied_modules=("attention",), **COMMON))
    C.log(f"FIT_DONE {json.dumps({k: (v if not isinstance(v, str) else v[:40]) for k, v in status.items() if k != 'median_res_norm'})}")


class Ctx:
    def __init__(self, bench, units, c2, n1, out, tok, model, H):
        from jlens_causal.official.modelparts import attention_shape
        self.H, self.tok, self.model = H, tok, model
        self.fit = json.loads((out / "fit.json").read_text(encoding="utf-8"))
        self.med = self.fit["median_res_norm"]
        art = out / "art"
        idx, S = R.load_stats(c2)
        self.MR = R.Means(units, idx, S, "reference")
        self.n1 = json.loads(Path(n1).read_text(encoding="utf-8"))[bench]["selected"]
        cs = R.neuron_sets(units, idx, S, H.nl, H.nn, [])
        a = S["act"].astype(np.float32)
        cal_t = [idx[u["uid"]] for u in units if u["fold"] == 0 and u["label"] == "target" and u["uid"] in idx]
        cal_r = [idx[u["uid"]] for u in units if u["fold"] == 0 and u["label"] == "reference" and u["uid"] in idx]
        order = np.argsort(-(np.abs(a[cal_t].mean(0) - a[cal_r].mean(0)) / (a[cal_r].std(0) + 1e-3)).ravel())
        self.contrast = {K: order[:K].tolist() for K in (16, 64, 256)}
        rng = np.random.default_rng(7)
        self.rand = {K: ((np.array(v) // H.nn) * H.nn + rng.integers(0, H.nn, K)).tolist() for K, v in self.contrast.items()}
        self.ok = {m: str(self.fit.get(m, "")).startswith("ok") for m in ("caa", "iti", "mera", "austeer")}
        self.caa_v = self.caa_r = self.iti = self.iti_r = None
        if self.ok["caa"]:
            v = torch.load(art / "caa.pt", map_location="cpu", weights_only=False)["state"]["vectors"][str(CAA_LAYER)].float()
            g = torch.Generator().manual_seed(0)
            r = torch.randn(v.shape, generator=g)
            self.caa_v, self.caa_r = v, r / r.norm() * v.norm()
        if self.ok["iti"]:
            a48 = torch.load(art / "iti48.pt", map_location="cpu", weights_only=False)
            nh = attention_shape(model)[0]
            self.iti = {int(k): d.float() for k, d in derive_iti(a48, ITI_K, False, nh).items()}
            self.iti_r = {int(k): d.float() for k, d in derive_iti(a48, ITI_K, True, nh).items()}
        self._mera, self._aus = {}, {}
        self.art = art

    def mera_obj(self, alpha):
        if alpha not in self._mera:
            from jlens_causal.official import mera as M
            from jlens_causal.official.modelparts import decoder_layers, model_device
            a = torch.load(self.art / "mera.pt", map_location="cpu", weights_only=False)
            _, _, by_mera = M._modules()

            class _MERA(by_mera.MERA):
                def steer(self, activations, layer_idx):
                    return super().steer(activations.float(), layer_idx).to(activations.dtype)

            view = SimpleNamespace(model=SimpleNamespace(layers=decoder_layers(self.model)), device=model_device(self.model))
            pw = {int(k): v.numpy() for k, v in a["state"]["probe_weights"].items()}
            obj = _MERA(view, self.tok, {}, {}, {"probe_weights": pw, "mode": "optimal_probe", "alpha_value": alpha,
                                                 "best_alpha_last": alpha, "best_alpha_exact": alpha, "apply_token_pos_to_steer": "all",
                                                 "derive_with_all": True, "derive_with_sigmoid": True, "derive_with_logit": True,
                                                 "log_with_wandb": False, "debug": False})
            self._mera[alpha] = (obj, sorted(pw))
        return self._mera[alpha]

    def aus_masks(self, strength):
        if strength not in self._aus:
            from jlens_causal.official import austeer as A
            a = torch.load(self.art / "austeer.pt", map_location="cpu", weights_only=False)
            st = a["state"]["attention"]
            sm = A._steer_module()
            proxy = A._proxy(self.model, "attention")
            sm.set_MFU([float(x) for x in st["all_scores"].tolist()], [int(x) for x in st["all_layer_ids"].tolist()],
                       [tuple(int(i) for i in p) for p in st["all_indices"].tolist()], 8, float(strength), proxy, "attention")
            m = {real: A._mask(proxy, slot, "attention").clone().float() for slot, real in enumerate(proxy.real_layers)}
            self._aus[strength] = {k: v for k, v in m.items() if v.abs().sum() > 0}
        return self._aus[strength]

    def edits(self, method, s, u):
        H = self.H
        mu = lambda: self.MR.excl(u["group"], "act")
        if method == "caa":
            return {("res", CAA_LAYER): C.Edit("add", vec=self.caa_v, alpha=s * self.med[CAA_LAYER] / float(self.caa_v.norm()))}
        if method == "caa_rand":
            return {("res", CAA_LAYER): C.Edit("add", vec=self.caa_r, alpha=s * self.med[CAA_LAYER] / float(self.caa_r.norm()))}
        if method in ("iti", "iti_rand"):
            dirs = self.iti if method == "iti" else self.iti_r
            return {("oproj", l): C.Edit("add", vec=d, alpha=s) for l, d in dirs.items()}
        if method == "mera":
            obj, layers = self.mera_obj(s)
            return {("pln", l): C.Edit("fn", fn=partial(obj.steer, layer_idx=l)) for l in layers}
        if method == "austeer":
            return {("oproj", l): C.Edit("mul", vec=m) for l, m in self.aus_masks(s).items()}
        if method == "neur_anth_clamp":
            return R.neur_edit(self.n1[str(int(s))], mu(), H.nn)
        if method == "neur_anth_add":
            by = defaultdict(list)
            for x in self.n1["64"]:
                by[x // H.nn].append(x % H.nn)
            ed = {}
            for l, ns in by.items():
                W = H.blocks[l].mlp.down_proj.weight[:, ns].float()
                d = (W / W.norm(dim=0, keepdim=True)).sum(1)
                ed[("mlp", l)] = C.Edit("add", vec=(d / d.norm()).cpu(), alpha=-s * self.med[l])
            return ed
        if method == "neur_contrast":
            return R.neur_edit(self.contrast[int(s)], mu(), H.nn)
        if method == "neur_rand":
            return R.neur_edit(self.rand[int(s)], mu(), H.nn)
        raise ValueError(method)

    def available(self, method):
        base = method.replace("_rand", "")
        return self.ok.get(base, True) and (method not in ("neur_anth_clamp", "neur_anth_add") or len(self.n1.get("64", [])) > 0)


def choose(rows, bench):
    cls = R.classify(rows, bench)
    sc = R.score(rows, cls, bench)
    best = {}
    for m, ss in STRENGTHS.items():
        for p in POS:
            cand = [(sc.get(f"{m}|{s}|{p}", {}).get("S"), -i, s) for i, s in enumerate(ss)]
            cand = [c for c in cand if c[0] is not None]
            if cand:
                best[f"{m}|{p}"] = max(cand)[2]
    return best, sc


def main():
    mode, bench, units_path, c2, n1, out = sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[5], Path(sys.argv[6])
    out.mkdir(parents=True, exist_ok=True)
    units = json.loads(units_path.read_text(encoding="utf-8"))
    if mode == "report":
        return report(bench, out)
    tok, model = C.load()
    H = C.Hooked(model)
    if mode == "fit":
        return mode_fit(bench, units, c2, out, tok, model, H)
    ctx = Ctx(bench, units, c2, n1, out, tok, model, H)
    if mode == "tune":
        def cfg_fn(u):
            cf = [("base", {}, "all")]
            for m, ss in STRENGTHS.items():
                if not ctx.available(m):
                    continue
                for s in ss:
                    ed = ctx.edits(m, s, u)
                    for p in POS:
                        cf.append((f"{m}|{s}|{p}", ed, p))
            return cf
        return R.run_rows(bench, units, out, tok, model, H, "n2tune", cfg_fn, 0, R.SEEDS_SWEEP)
    if mode == "test":
        best, _ = choose(R.read_rows(out, "n2tune"), bench)
        (out / "n2_choice.json").write_text(json.dumps(best, indent=1), encoding="utf-8")
        C.log(f"chosen strengths {best}")

        def cfg_fn(u):
            cf = [("base", {}, "all")]
            for key, s in best.items():
                m, p = key.split("|")
                cf.append((f"{m}|{s}|{p}", ctx.edits(m, s, u), p))
                ctrl = {"neur_contrast": "neur_rand", "caa": "caa_rand", "iti": "iti_rand"}.get(m)
                if ctrl and ctx.available(ctrl):
                    cf.append((f"{ctrl}|{s}|{p}", ctx.edits(ctrl, s, u), p))
            return cf
        return R.run_rows(bench, units, out, tok, model, H, "n2test", cfg_fn, 1, R.SEEDS_TEST)
    raise SystemExit(mode)


def report(bench, out):
    md = [f"# N2 / N3: position x method, {bench} (Qwen3.5-4B)", ""]
    fit = json.loads((out / "fit.json").read_text(encoding="utf-8")) if (out / "fit.json").is_file() else {}
    md += ["- fits: " + ", ".join(f"{k} {str(v)[:30]}" for k, v in fit.items() if k not in ("median_res_norm",)), ""]
    f = lambda x: "-" if x is None else f"{x:.0%}"
    for tag in ("n2tune", "n2test"):
        rows = R.read_rows(out, tag)
        if not rows:
            continue
        cls = R.classify(rows, bench)
        sc = R.score(rows, cls, bench)
        md += [f"## {tag} ({'CALIBRATION' if tag == 'n2tune' else 'TEST'})", "",
               "- classes: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(cls.values()).items())), "",
               "| config (method/strength/position) | targets | flip | broken | refs | refs kept (N3) | refs turned | S |",
               "|---|---|---|---|---|---|---|---|"]
        for cfg in sorted(sc, key=lambda c: (c != "base", c)):
            s = sc[cfg]
            md.append(f"| {cfg} | {s['nt']} | {f(s['flip'])} | {f(s['broken'])} | {s['nr']} | {f(s['kept'])} | {f(s['turned'])} | "
                      f"{'-' if s['S'] is None else round(s['S'], 3)} |")
        md.append("")
        if tag == "n2test":
            works = {}
            for cfg, s in sc.items():
                if cfg == "base" or "_rand" in cfg:
                    continue
                m, _, p = cfg.split("|")
                works[(m, p)] = (s["flip"] or 0) >= 0.5 and (s["broken"] if s["broken"] is not None else 1) <= 0.1 and (s["kept"] or 0) >= 0.9
            meths = sorted({m for m, _ in works})
            md += ["## Readout (TEST; works = flip >= 50 %, broken <= 10 %, refs kept >= 90 %)", "",
                   "| method | all | commit |", "|---|---|---|"]
            for m in meths:
                md.append(f"| {m} | {works.get((m, 'all'))} | {works.get((m, 'commit'))} |")
            neur = [m for m in meths if m.startswith("neur")]
            other = [m for m in meths if not m.startswith("neur")]
            allc = all(works.get((m, "commit")) for m in meths) if meths else False
            only_n = any(works.get((m, p)) for m in neur for p in POS) and not any(works.get((m, p)) for m in other for p in POS)
            md += ["", f"- position matters more than method (every method works at commit): {allc}",
                   f"- only neuron arms work: {only_n}", ""]
    (out / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
