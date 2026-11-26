"""Distributed decision patterns across ToolAlign, AgentDojo and agentic-misalignment (user 11-25 21:1x: "MLP attention
residual stream 전부 흩어져있대 ... 패턴좀 찾아줘"; OVERNIGHT.md step 1). Neuron-basis view (Goodfire 2026-11-10; Anthropic
Neuron Basis Part 2, 2026-11-23).
capture BENCH OUT : at each CAUSAL-1 decision position, m = max lp(T) - max lp(A) (T = the target side of the CAUSAL-1
    contrast, A = the other side; ToolAlign: T = the domain tools, A = writeInternalLog). One backward per unit.
    Saves OUT/BENCH/dec.npz: act (fp16) and grad (fp32) of every MLP neuron (down_proj input, 32 x 9216), head inputs hin
    (o_proj / out_proj input, 32 x 4096) and their grads, plus uids, labels, folds, groups, m. rows.json: per unit k90
    (neurons for 90 % of sum |grad x act|), distinct layers among the top-100, per-layer attention / MLP / residual
    attributions (output . grad) and per-head attributions.
    References are capped at REFCAP per fold (md5 order of the uid).
analyze OUT : patterns (concentration, layer spread, MLP vs attention, cross-benchmark overlap of the top neurons and
    heads with a layer-matched permutation baseline, target vs reference neurons, J-lens readouts of the shared neurons).
    Neuron scores here are the mean-replacement attribution grad x (act - mu_ref), mu_ref = that benchmark's reference
    mean at the decision position.
transfer OUT : causal check at the decision position. The top-K neurons of two benchmarks (targets) are set to the third
    benchmark's reference mean; flip = m < 0 on a target with m > 0 unedited. Same-layer random neurons as the control.
Usage: AB_PLATFORM=projectb python ab_distrib.py capture am|dojo|toolalign OUT ; analyze OUT ; transfer OUT"""
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_core as C

A = Path("/home/project-b/LJW/agentbench2/ana")
TA = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench")
REFCAP = int(os.environ.get("AB_REFCAP", "60"))
BENCHES = ("toolalign", "dojo", "am")
NL, NN, HD = 32, 9216, 4096


def md5(s):
    return hashlib.md5(s.encode()).hexdigest()


def ta_fold(domain):
    return int(md5(domain), 16) % 2


def cap_refs(xs, key, n):
    by = defaultdict(list)
    for x in sorted(xs, key=lambda x: md5(x[key])):
        if len(by[x["fold"]]) < n:
            by[x["fold"]].append(x)
    return [x for f in sorted(by) for x in by[f]]


def head_counts(model):
    cfg = model.config.get_text_config()
    _, blocks, _, _ = C.text_model(model)
    return {i: (cfg.num_attention_heads if hasattr(b, "self_attn") else cfg.linear_num_value_heads) for i, b in enumerate(blocks)}


def load_items(bench, tok):
    eos = C.eos_ids(tok)
    items = []
    if bench in ("am", "dojo"):
        c1 = json.loads((A / bench / "c1" / "units.json").read_text(encoding="utf-8"))
        U = {u["uid"]: u for u in json.loads((A / bench / "units.json").read_text(encoding="utf-8"))}
        for lab, xs in (("target", c1["targets"]), ("reference", cap_refs(c1["refs"], "uid", REFCAP))):
            for x in xs:
                u = U[x["uid"]]
                ids = list(u["prompt_ids"]) + [t for t in u["completion_ids"] if t not in eos]
                if ids[x["pos"] + 1] != x["next"]:
                    continue
                items.append({"uid": x["uid"], "label": lab, "group": x["group"], "fold": x["fold"], "kind": x["kind"],
                              "seq": ids[:x["pos"] + 1], "T": list(x["T"]), "A": list(x["A"]), "next": x["next"]})
        return items
    sys.path.insert(0, str(TA / "jlens_experiment"))
    from model_profiles import get_profile
    from trace_replay import load_traces, render_replay, select_steps
    prof = get_profile("qwen3.5-4b")
    U = json.loads((TA / "ops/analysis/causal/units.json").read_text(encoding="utf-8"))
    steps = {s.key: s for s in select_steps(load_traces([TA / "runner/results/qwen35-greedy"]), scope="all")}
    w_id = tok.encode("writeInternalLog", add_special_tokens=False)[0]
    refs = [dict(x, fold=ta_fold(x["domain"])) for x in U["refs"]]
    tg = [dict(x, fold=ta_fold(x["domain"])) for x in U["targets"]]
    for lab, xs in (("target", tg), ("reference", cap_refs(refs, "key", REFCAP))):
        for x in xs:
            rep = render_replay(tok, steps[x["key"]], context_mode="trajectory", expected_model_revision=prof.model_revision)
            ids = list(rep.token_ids)
            if ids[x["pos"] + 1] != x["next_id"]:
                continue
            items.append({"uid": x["key"], "label": lab, "group": x["domain"], "fold": x["fold"], "kind": x.get("risk", ""),
                          "seq": ids[:x["pos"] + 1], "T": [c for c in x["cands"] if c != w_id], "A": [w_id], "next": x["next_id"]})
    return items


def capture(bench, out):
    out = Path(out) / bench
    out.mkdir(parents=True, exist_ok=True)
    tok, model = C.load()
    H = C.Hooked(model)
    nheads = head_counts(model)
    items = load_items(bench, tok)
    if os.environ.get("AB_SMOKE"):
        items = ([i for i in items if i["label"] == "target" and i["fold"] == 0][:1] + [i for i in items if i["label"] == "target" and i["fold"] == 1][:1]
                 + [i for i in items if i["label"] == "reference"][:2])
    C.log(f"{bench}: {len(items)} decision units {Counter((i['label'], i['fold']) for i in items)}")
    keep, rec = {}, {"on": False}

    def pre(name, i):
        def f(mod, args):
            if not rec["on"]:
                return
            x = args[0]
            if x.requires_grad:
                x.retain_grad()
            keep[(name, i)] = x
        return f

    def post(name, i):
        def f(mod, args, out_):
            if not rec["on"]:
                return
            o = out_ if torch.is_tensor(out_) else out_[0]
            if o.requires_grad:
                o.retain_grad()
            keep[(name, i)] = o
        return f

    def emb(mod, a, o):
        if rec["on"]:
            o.requires_grad_(True)

    hs = []
    for i, b in enumerate(H.blocks):
        hs.append(b.mlp.down_proj.register_forward_pre_hook(pre("act", i)))
        hs.append(b.mlp.register_forward_hook(post("mlp", i)))
        hs.append(b.register_forward_hook(post("res", i)))
        att = b.self_attn if hasattr(b, "self_attn") else b.linear_attn
        proj = att.o_proj if hasattr(b, "self_attn") else att.out_proj
        hs.append(proj.register_forward_pre_hook(pre("hin", i)))
        hs.append(att.register_forward_hook(post("attn", i)))
    hs.append(H.lm.embed_tokens.register_forward_hook(emb))
    n = len(items)
    ACT = np.zeros((n, NL, NN), np.float16)
    GR = np.zeros((n, NL, NN), np.float32)
    HIN = np.zeros((n, NL, HD), np.float16)
    GH = np.zeros((n, NL, HD), np.float32)
    rows = []
    t0 = time.time()
    for k, it in enumerate(items):
        seq = it["seq"]
        kk = min(4, len(seq) - 1)
        rec["on"] = False
        _, cache = C.prefill(model, seq[:-kk], inference=False)
        keep.clear()
        rec["on"] = True
        with torch.enable_grad():
            o = model(input_ids=torch.tensor([seq[-kk:]], device=C.first_device(model)), past_key_values=cache, use_cache=True,
                      logits_to_keep=1)
            lp = torch.log_softmax(o.logits[0, -1].float(), -1)
            m = lp[it["T"]].max() - lp[it["A"]].max()
            m.backward()
        rec["on"] = False
        act = torch.stack([keep[("act", i)][0, -1].detach().float() for i in range(NL)])
        gact = torch.stack([keep[("act", i)].grad[0, -1].float() for i in range(NL)])
        hin = torch.stack([keep[("hin", i)][0, -1].detach().float() for i in range(NL)])
        gh = torch.stack([keep[("hin", i)].grad[0, -1].float() for i in range(NL)])
        ACT[k], GR[k], HIN[k], GH[k] = act.cpu().numpy(), gact.cpu().numpy(), hin.cpu().numpy(), gh.cpu().numpy()
        attr = (act * gact).flatten()
        srt = attr.abs().sort(descending=True).values
        cs = srt.cumsum(0) / srt.sum()
        k90 = int((cs < 0.9).sum()) + 1
        top100 = torch.topk(attr.abs(), 100).indices
        blk = {c: [float((keep[(c, i)][0, -1].float() * keep[(c, i)].grad[0, -1].float()).sum()) for i in range(NL)]
               for c in ("attn", "mlp", "res")}
        heads = [(hin[i] * gh[i]).view(nheads[i], -1).sum(-1).cpu().tolist() for i in range(NL)]
        rows.append({"uid": it["uid"], "label": it["label"], "group": it["group"], "fold": it["fold"], "kind": it["kind"],
                     "m": float(m.detach()), "k90": k90, "layers_top100": len(set((top100 // NN).tolist())),
                     "attn": blk["attn"], "mlp": blk["mlp"], "res": blk["res"], "heads": heads})
        keep.clear()
        del cache, o, lp, m
        if k % 20 == 0:
            C.log(f"{bench} {k + 1}/{n} m={rows[-1]['m']:+.2f} k90={k90} {time.time() - t0:.0f}s")
    for h in hs:
        h.remove()
    np.savez(out / "dec.npz", uids=np.array([r["uid"] for r in rows]), labels=np.array([r["label"] for r in rows]),
             folds=np.array([r["fold"] for r in rows]), groups=np.array([r["group"] for r in rows]),
             m=np.array([r["m"] for r in rows], np.float32), act=ACT, grad=GR, hin=HIN, ghin=GH)
    (out / "rows.json").write_text(json.dumps(rows), encoding="utf-8")
    (out / "heads_meta.json").write_text(json.dumps({str(i): nheads[i] for i in nheads}), encoding="utf-8")
    (out / "CAPTURE_DONE").touch()
    C.log(f"CAPTURE_DONE {bench} {len(rows)}")


def load_dec(out, b):
    p = Path(out) / b
    if not (p / "CAPTURE_DONE").exists():
        return None
    z = np.load(p / "dec.npz")
    d = {k: z[k] for k in z.files}
    d["rows"] = json.loads((p / "rows.json").read_text(encoding="utf-8"))
    d["nheads"] = {int(k): v for k, v in json.loads((p / "heads_meta.json").read_text()).items()}
    return d


def mr_scores(d):
    """mean-replacement attribution per unit: grad x (act - mu_ref), mu_ref = mean over this benchmark's references."""
    ref = d["labels"] == "reference"
    mu = d["act"][ref].astype(np.float32).mean(0)
    s = d["grad"] * (d["act"].astype(np.float32) - mu)
    muh = d["hin"][ref].astype(np.float32).mean(0)
    sh = d["ghin"] * (d["hin"].astype(np.float32) - muh)
    return s.reshape(len(s), -1), sh, mu


def head_sum(sh, nheads):
    return [sh[:, l].reshape(len(sh), nheads[l], -1).sum(-1) for l in range(NL)]


def analyze(out):
    from transformers import AutoTokenizer
    out = Path(out)
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    D = {}
    for b in BENCHES:
        d = load_dec(out, b)
        if d is not None:
            D[b] = d
    md = ["# Distributed decision patterns (Qwen3.5-4B): ToolAlign, AgentDojo, agentic-misalignment", "",
          "m = max lp(T) - max lp(A) at the CAUSAL-1 decision position (T = target side). k90 and block shares use grad x act; "
          "neuron and head rankings use the mean-replacement attribution grad x (act - mu_ref).", ""]
    res = {}
    md += ["## 1. Concentration", "",
           "| benchmark | class | units | neurons for 90 % of sum abs(grad x act), median [IQR] | % of 294,912 | layers among top-100 (median) |",
           "|---|---|---|---|---|---|"]
    for b, d in D.items():
        for lab in ("target", "reference"):
            rs = [r for r in d["rows"] if r["label"] == lab]
            if not rs:
                continue
            q = np.percentile([r["k90"] for r in rs], [25, 50, 75])
            ly = float(np.median([r["layers_top100"] for r in rs]))
            md.append(f"| {b} | {lab} | {len(rs)} | {q[1]:.0f} [{q[0]:.0f}, {q[2]:.0f}] | {100 * q[1] / (NL * NN):.2f} % | {ly:.0f} |")
            res[f"conc_{b}_{lab}"] = {"k90_q": q.tolist(), "layers_top100": ly}
    md += ["", "## 2. Share of abs(attribution) by layer quarter, targets (attention output vs MLP output)", "",
           "| benchmark | component | L0-7 | L8-15 | L16-23 | L24-31 |", "|---|---|---|---|---|---|"]
    for b, d in D.items():
        rs = [r for r in d["rows"] if r["label"] == "target"]
        tot = np.array([np.abs(r["attn"]).sum() + np.abs(r["mlp"]).sum() for r in rs])[:, None]
        for comp in ("attn", "mlp"):
            sh = (np.array([np.abs(r[comp]) for r in rs]) / tot).mean(0)
            md.append(f"| {b} | {comp} | " + " | ".join(f"{100 * sh[s:s + 8].sum():.0f} %" for s in range(0, 32, 8)) + " |")
            res[f"share_{b}_{comp}"] = sh.tolist()
        hs = np.array([[sum(abs(x) for x in h) for h in r["heads"]] for r in rs])
        full = [l for l in range(NL) if D[b]["nheads"][l] == 16]
        md.append(f"| {b} | heads: full-attention layers {full} hold {100 * hs[:, full].sum() / hs.sum():.0f} % of head abs(attr) | | | | |")
    S, SH, TOP, TOPH = {}, {}, {}, {}
    for b, d in D.items():
        s, sh, _ = mr_scores(d)
        t = d["labels"] == "target"
        S[b] = s[t].mean(0)
        S[b + ":ref"] = s[~t].mean(0)
        TOP[b] = set(np.argsort(-S[b])[:200].tolist())
        hsum = head_sum(sh[t], d["nheads"])
        SH[b] = {(l, h): float(hsum[l][:, h].mean()) for l in range(NL) for h in range(hsum[l].shape[1])}
        TOPH[b] = set(sorted(SH[b], key=lambda k: -SH[b][k])[:20])
    rng = np.random.default_rng(0)
    bs = list(D)
    pairs = [(a, c) for i, a in enumerate(bs) for c in bs[i + 1:]]
    md += ["", "## 3. Cross-benchmark overlap (targets): top-200 neurons and top-20 heads", "",
           "| pair | neurons shared | chance (layer-matched permutation, mean of 500) | p (perm) | heads shared | chance |", "|---|---|---|---|---|---|"]
    for a, c in pairs:
        ov = len(TOP[a] & TOP[c])
        lay = np.array(sorted(TOP[c])) // NN
        perm = np.array([len(TOP[a] & set((lay * NN + rng.integers(0, NN, len(lay))).tolist())) for _ in range(500)])
        hl = [k[0] for k in TOPH[c]]
        hperm = np.array([len(TOPH[a] & {(l, int(rng.integers(0, D[c]["nheads"][l]))) for l in hl}) for _ in range(500)])
        ovh = len(TOPH[a] & TOPH[c])
        md.append(f"| {a} x {c} | {ov} | {perm.mean():.2f} | {(perm >= ov).mean():.3f} | {ovh} | {hperm.mean():.2f} |")
        res[f"overlap_{a}_{c}"] = {"neurons": ov, "chance": float(perm.mean()), "p": float((perm >= ov).mean()), "heads": ovh,
                                   "heads_chance": float(hperm.mean())}
    common = set.intersection(*TOP.values()) if TOP else set()
    md += ["", f"- neurons in the top-200 of all {len(D)} benchmarks: {len(common)}; heads in the top-20 of all: "
           f"{sorted(set.intersection(*TOPH.values())) if TOPH else []}", ""]
    per_b = {b: [int(x) for x in np.argsort(-S[b])[:12]] for b in bs}
    want = sorted({int(x) for x in common} | {x for v in per_b.values() for x in v})
    readout = {}
    try:
        from huggingface_hub import hf_hub_download
        from safetensors import safe_open
        import jlens
        lens = jlens.JacobianLens.load(hf_hub_download(C.LENS_REPO, C.LENS_FILE, revision=C.LENS_REV))
        snap = Path(hf_hub_download(C.MODEL, "model.safetensors.index.json", revision=C.REV)).parent
        index = json.loads((snap / "model.safetensors.index.json").read_text())["weight_map"]

        def tensor(name):
            with safe_open(str(snap / index[name]), framework="pt") as f:
                return f.get_tensor(name).float()
        pre = "model.language_model."
        W_U = tensor("lm_head.weight") if "lm_head.weight" in index else tensor(pre + "embed_tokens.weight")
        g = tensor(pre + "norm.weight")
        gw = g if g.abs().mean() > 0.5 else 1 + g
        for x in want:
            l, j = x // NN, x % NN
            w = tensor(f"{pre}layers.{l}.mlp.down_proj.weight")[:, j]
            if l in lens.jacobians:
                w = lens.jacobians[l].float() @ w
            readout[x] = [tok.decode([t]) for t in torch.topk(W_U @ (gw * w), 10).indices.tolist()]
    except Exception as exc:
        md.append(f"- readout unavailable: {exc!r}"[:300])
    md += ["## 4. Shared neurons and the strongest per benchmark, with J-lens readouts of the output vector (+w)", "",
           "| neuron | " + " | ".join(f"{b} (target mean)" for b in bs) + " | readout of +w (top-10) |", "|---|" + "---|" * len(bs) + "---|"]
    for x in sorted(common, key=lambda x: -sum(S[b][x] for b in bs))[:30]:
        md.append(f"| L{x // NN}/N{x % NN} | " + " | ".join(f"{S[b][x]:+.4f}" for b in bs) + f" | {readout.get(int(x), '-')} |")
    for b in bs:
        md += ["", f"### strongest in {b}", "", "| neuron | target mean | reference mean | readout of +w |", "|---|---|---|---|"]
        for x in per_b[b]:
            md.append(f"| L{x // NN}/N{x % NN} | {S[b][x]:+.4f} | {S[b + ':ref'][x]:+.4f} | {readout.get(x, '-')} |")
    md += ["", "## 5. Top heads per benchmark (mean-replacement attribution, targets)", ""]
    for b in bs:
        top = sorted(SH[b], key=lambda k: -SH[b][k])[:12]
        res[f"heads_{b}"] = [[k[0], k[1], SH[b][k]] for k in top]
        md.append(f"- {b}: " + ", ".join(f"L{l}H{h} ({SH[b][(l, h)]:+.3f})" for l, h in top))
    md += ["", "## 6. Layer spread of the top-200 neurons (count per layer quarter)", ""]
    for b in bs:
        lay = np.array(sorted(TOP[b])) // NN
        md.append(f"- {b}: " + ", ".join(f"L{s}-{s + 7}: {int(((lay >= s) & (lay < s + 8)).sum())}" for s in range(0, 32, 8)))
    (out / "report.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


def transfer(out):
    out = Path(out)
    tok, model = C.load()
    H = C.Hooked(model)
    D = {}
    for b in BENCHES:
        d = load_dec(out, b)
        if d is not None:
            D[b] = d
    S = {}
    for b, d in D.items():
        s, _, mu = mr_scores(d)
        S[b] = (s[d["labels"] == "target"].mean(0), torch.tensor(mu))
    md = ["# Cross-benchmark transfer: top-K target neurons of the other two benchmarks, set to the held-out benchmark's reference "
          "mean at its decision position", "", "| held-out | K | flip (shared) | flip (same-layer random) | targets |", "|---|---|---|---|---|"]
    rng = np.random.default_rng(1)
    for held in D:
        others = [b for b in D if b != held]
        if not others:
            continue
        s = sum(S[b][0] / (np.abs(S[b][0]).sum() + 1e-12) for b in others)
        items = [it for it in load_items(held, tok) if it["label"] == "target"]
        mu = S[held][1]
        for K in (64, 256, 1024):
            top = np.argsort(-s)[:K]
            rand = (top // NN) * NN + rng.integers(0, NN, K)
            r = {}
            for name, sel in (("shared", top), ("random", rand)):
                by = defaultdict(list)
                for x in sel.tolist():
                    by[x // NN].append(x % NN)
                ed = {("down", l): C.Edit("neur", idx=torch.tensor(ns), vec=mu[l][ns]) for l, ns in by.items()}
                flips, n = 0, 0
                for it in items:
                    seq = it["seq"]
                    _, cache = C.prefill(model, seq[:-1])
                    cache = C.cache_expand(cache, 2)
                    H.set_rows([{}, ed])
                    with torch.inference_mode():
                        o = model(input_ids=torch.tensor([[seq[-1]]] * 2, device=C.first_device(model)), past_key_values=cache,
                                  use_cache=True, logits_to_keep=1)
                    H.reset()
                    lp = torch.log_softmax(o.logits[:, -1].float(), -1)
                    m0 = float(lp[0, it["T"]].max() - lp[0, it["A"]].max())
                    m1 = float(lp[1, it["T"]].max() - lp[1, it["A"]].max())
                    if m0 > 0:
                        n += 1
                        flips += int(m1 < 0)
                    del cache, o
                r[name] = (flips, n)
            md.append(f"| {held} | {K} | {r['shared'][0]}/{r['shared'][1]} | {r['random'][0]}/{r['random'][1]} | {len(items)} |")
            C.log(md[-1])
    (out / "transfer.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    C.log("TRANSFER_DONE")


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "capture":
        capture(sys.argv[2], sys.argv[3])
    elif mode == "analyze":
        analyze(sys.argv[2])
    else:
        transfer(sys.argv[2])
