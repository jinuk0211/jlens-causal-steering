"""Distributed decision patterns across ToolAlign, AgentDojo and agentic-misalignment (user 11-25 21:1x: "MLP attention
residual stream 전부 흩어져있대 ... 패턴좀 찾아줘"). Neuron-basis view (Goodfire 2026; Anthropic Part 2 2026).
capture BENCH OUT : at each CAUSAL-1 decision position, m = lp(chosen token) - max lp(alternatives) and its first-order
    attribution (gradient x activation) to
      - every MLP neuron (down_proj input x its gradient), 32 x 9216
      - every attention head (o_proj / out_proj input split by head, x its gradient)
      - each layer's attention output, MLP output and residual stream (output . gradient)
    chosen = the token the model produced; alternatives = the other side of the CAUSAL-1 contrast (targets: A;
    references: T) for AgentDojo / AM; ToolAlign targets: writeInternalLog, references: the other domain tools.
    Saves per unit: top-512 neurons, layer sums, head and block attributions; plus the reference mean activation.
analyze OUT : patterns (concentration, layer spread, MLP vs attention, cross-benchmark overlap of top neurons and heads
    with a permutation baseline, target-vs-reference neurons, J-lens readouts of the shared neurons).
transfer OUT : causal check. Neurons shared by two benchmarks (selected on those two only) are set to the third
    benchmark's reference mean at its decision position. Flip = the chosen token loses to an alternative. Compared
    with the same number of random neurons in the same layers.
Usage: AB_PLATFORM=projectb python ab_distrib.py capture am|dojo|toolalign OUT ; analyze OUT ; transfer OUT"""
import copy
import json
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
TOPK = 512
BENCHES = ("toolalign", "dojo", "am")


def load_items(bench, tok):
    eos = C.eos_ids(tok)
    items = []
    if bench in ("am", "dojo"):
        c1 = json.loads((A / bench / "c1" / "units.json").read_text(encoding="utf-8"))
        U = {u["uid"]: u for u in json.loads((A / bench / "units.json").read_text(encoding="utf-8"))}
        for lab, xs in (("target", c1["targets"]), ("reference", c1["refs"])):
            for x in xs:
                u = U[x["uid"]]
                ids = list(u["prompt_ids"]) + [t for t in u["completion_ids"] if t not in eos]
                alts = x["A"] if lab == "target" else x["T"]
                items.append({"uid": x["uid"], "label": lab, "group": x["group"], "kind": x["kind"],
                              "seq": ids[:x["pos"] + 1], "chosen": [x["next"]], "alts": sorted(set(alts) - {x["next"]})})
        return items
    sys.path.insert(0, str(TA / "jlens_experiment"))
    from trace_replay import load_traces, render_replay, select_steps
    U = json.loads((TA / "ops/analysis/causal/units.json").read_text(encoding="utf-8"))
    steps = {s.key: s for s in select_steps(load_traces([TA / "runner/results/qwen35-greedy"]), scope="all")}
    w_id = tok.encode("writeInternalLog", add_special_tokens=False)[0]
    for lab, xs in (("target", U["targets"]), ("reference", U["refs"])):
        for x in xs:
            rep = render_replay(tok, steps[x["key"]], context_mode="trajectory", expected_model_revision=C.REV)
            ids = list(rep.token_ids)
            if ids[x["pos"] + 1] != x["next_id"]:
                continue
            alts = [w_id] if lab == "target" else [c for c in x["cands"] if c != w_id]
            items.append({"uid": x["key"], "label": lab, "group": x["domain"], "kind": x.get("risk", ""),
                          "seq": ids[:x["pos"] + 1], "chosen": [x["next_id"]], "alts": sorted(set(alts) - {x["next_id"]})})
    return items


def capture(bench, out):
    out = Path(out) / bench
    out.mkdir(parents=True, exist_ok=True)
    tok, model = C.load()
    H = C.Hooked(model)
    lm = H.lm
    cfg = model.config.get_text_config()
    items = [it for it in load_items(bench, tok) if it["alts"]]
    C.log(f"{bench}: {len(items)} decision units ({Counter(i['label'] for i in items)})")
    nl, nn = H.nl, H.nn
    keep = {}

    def pre(name, i):
        def f(mod, args):
            x = args[0]
            if x.requires_grad:
                x.retain_grad()
            keep[(name, i)] = x
        return f

    def post(name, i):
        def f(mod, args, out_):
            o = out_ if torch.is_tensor(out_) else out_[0]
            if o.requires_grad:
                o.retain_grad()
            keep[(name, i)] = o
        return f

    hs = []
    heads = {}
    for i, b in enumerate(H.blocks):
        hs.append(b.mlp.down_proj.register_forward_pre_hook(pre("act", i)))
        hs.append(b.mlp.register_forward_hook(post("mlp", i)))
        hs.append(b.register_forward_hook(post("res", i)))
        if hasattr(b, "self_attn"):
            hs.append(b.self_attn.o_proj.register_forward_pre_hook(pre("hin", i)))
            hs.append(b.self_attn.register_forward_hook(post("attn", i)))
            heads[i] = (cfg.num_attention_heads, "full")
        else:
            hs.append(b.linear_attn.out_proj.register_forward_pre_hook(pre("hin", i)))
            hs.append(b.linear_attn.register_forward_hook(post("attn", i)))
            heads[i] = (cfg.linear_num_value_heads, "linear")
    hs.append(lm.embed_tokens.register_forward_hook(lambda mod, a, o: o.requires_grad_(True)))
    rows, ref_act_sum, ref_n = [], torch.zeros(nl, nn), 0
    top_idx, top_val, sums = [], [], []
    t0 = time.time()
    for n, it in enumerate(items):
        seq = it["seq"]
        kk = min(4, len(seq) - 1)
        _, cache = C.prefill(model, seq[:-kk], inference=False)
        keep.clear()
        with torch.enable_grad():
            o = model(input_ids=torch.tensor([seq[-kk:]], device=C.first_device(model)), past_key_values=cache, use_cache=True,
                      logits_to_keep=1)
            lp = torch.log_softmax(o.logits[0, -1].float(), -1)
            m = lp[it["chosen"]].max() - lp[it["alts"]].max()
            m.backward()
        act = torch.stack([keep[("act", i)][0, -1].detach().float().cpu() for i in range(nl)])
        gact = torch.stack([keep[("act", i)].grad[0, -1].float().cpu() for i in range(nl)])
        attr = act * gact
        blk = {k: [float((keep[(k, i)][0, -1].float() * keep[(k, i)].grad[0, -1].float()).sum()) for i in range(nl)]
               for k in ("attn", "mlp", "res")}
        hd = []
        for i in range(nl):
            x, g = keep[("hin", i)][0, -1].float(), keep[("hin", i)].grad[0, -1].float()
            nh = heads[i][0]
            hd.append((x * g).view(nh, -1).sum(-1).cpu().tolist())
        flat = attr.flatten()
        v, ix = torch.topk(flat.abs(), TOPK)
        top_idx.append(ix.numpy().astype(np.int32))
        top_val.append(flat[ix].numpy().astype(np.float32))
        sums.append([float(attr[i].sum()) for i in range(nl)] + [float(attr[i].abs().sum()) for i in range(nl)])
        srt = flat.abs().sort(descending=True).values
        cs = srt.cumsum(0) / srt.sum()
        k90 = int((cs < 0.9).sum()) + 1
        rows.append({"uid": it["uid"], "label": it["label"], "group": it["group"], "kind": it["kind"], "m": float(m.detach()),
                     "k90": k90, "layers_top100": len({int(i) // nn for i in ix[:100].tolist()}),
                     "attn": blk["attn"], "mlp": blk["mlp"], "res": blk["res"], "heads": hd,
                     "mlp_neuron_sum": float(attr.sum()), "mlp_neuron_abs": float(attr.abs().sum())})
        if it["label"] == "reference":
            ref_act_sum += act
            ref_n += 1
        keep.clear()
        del cache, o, lp, m
        if n % 20 == 0:
            C.log(f"{bench} {n + 1}/{len(items)} k90={k90} {time.time() - t0:.0f}s")
    for h in hs:
        h.remove()
    np.savez_compressed(out / "attr_top.npz", idx=np.stack(top_idx), val=np.stack(top_val), sums=np.array(sums, np.float32),
                        ref_act_mean=(ref_act_sum / max(1, ref_n)).numpy().astype(np.float32))
    (out / "rows.json").write_text(json.dumps(rows), encoding="utf-8")
    (out / "heads_meta.json").write_text(json.dumps({str(i): heads[i] for i in heads}), encoding="utf-8")
    C.log(f"CAPTURE_DONE {bench} {len(rows)}")


def per_bench_scores(d, nl, nn, label):
    rows = d["rows"]
    idx, val = d["idx"], d["val"]
    score = np.zeros(nl * nn, np.float64)
    freq = np.zeros(nl * nn, np.int32)
    cnt = 0
    for r, ix, vv in zip(rows, idx, val):
        if r["label"] != label:
            continue
        cnt += 1
        np.add.at(score, ix, vv)
        freq[ix[:100]] += 1
    return score / max(1, cnt), freq, cnt


def analyze(out):
    from transformers import AutoTokenizer
    out = Path(out)
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    nl, nn = 32, 9216
    D = {}
    for b in BENCHES:
        p = out / b
        if not (p / "rows.json").is_file():
            continue
        z = np.load(p / "attr_top.npz")
        D[b] = {"rows": json.loads((p / "rows.json").read_text(encoding="utf-8")), "idx": z["idx"], "val": z["val"], "sums": z["sums"]}
    md = ["# Distributed decision patterns (Qwen3.5-4B): ToolAlign, AgentDojo, agentic-misalignment", "",
          "m = lp(chosen) - max lp(alternatives) at the CAUSAL-1 decision position; attribution = gradient x activation.", ""]
    res = {}
    md += ["## 1. How concentrated is the neuron attribution?", "",
           "| benchmark | class | units | neurons for 90 % of sum |attr| (median [IQR]) | as % of 294,912 | distinct layers among the top-100 neurons (median) |",
           "|---|---|---|---|---|---|"]
    for b, d in D.items():
        for lab in ("target", "reference"):
            rs = [r for r in d["rows"] if r["label"] == lab]
            if not rs:
                continue
            k = np.array([r["k90"] for r in rs])
            q = np.percentile(k, [25, 50, 75])
            md.append(f"| {b} | {lab} | {len(rs)} | {q[1]:.0f} [{q[0]:.0f}, {q[2]:.0f}] | {100 * q[1] / (nl * nn):.2f} % | "
                      f"{np.median([r['layers_top100'] for r in rs]):.0f} |")
            res[f"conc_{b}_{lab}"] = {"k90_q": q.tolist(), "layers_top100": float(np.median([r["layers_top100"] for r in rs]))}
    md += ["", "## 2. Where does the margin come from? Share of |attribution| per layer band (targets, mean over units)", "",
           "| benchmark | component | L0-7 | L8-15 | L16-23 | L24-31 |", "|---|---|---|---|---|---|"]
    for b, d in D.items():
        rs = [r for r in d["rows"] if r["label"] == "target"]
        if not rs:
            continue
        for comp in ("attn", "mlp"):
            a = np.array([np.abs(r[comp]) for r in rs])
            tot = np.array([np.abs(r["attn"]).sum() + np.abs(r["mlp"]).sum() for r in rs])[:, None]
            sh = (a / tot).mean(0)
            md.append(f"| {b} | {comp} | " + " | ".join(f"{100 * sh[s:s + 8].sum():.0f} %" for s in range(0, 32, 8)) + " |")
        hs = np.array([[sum(abs(x) for x in h) for h in r["heads"]] for r in rs])
        md.append(f"| {b} | (heads, full-attn layers 3,7,..,31 share of head |attr|) | "
                  f"{100 * hs[:, [3, 7, 11, 15, 19, 23, 27, 31]].sum() / hs.sum():.0f} % of head |attr| from 8 full-attention layers | | | |")
    md += ["", "## 3. Shared neurons across benchmarks (top-200 by mean signed attribution toward the chosen token)", ""]
    tops, scores = {}, {}
    for b, d in D.items():
        for lab in ("target", "reference"):
            s, f, cnt = per_bench_scores(d, nl, nn, lab)
            scores[(b, lab)] = s
            tops[(b, lab)] = set(np.argsort(-s)[:200].tolist())
    rng = np.random.default_rng(0)
    pairs = [(a, b) for i, a in enumerate(D) for b in list(D)[i + 1:]]
    md += ["| pair (targets) | overlap of top-200 | expected by chance (layer-matched permutation, mean of 200) |", "|---|---|---|"]
    for a, b in pairs:
        ov = len(tops[(a, "target")] & tops[(b, "target")])
        lay = np.array(sorted(tops[(b, "target")])) // nn
        perm = [len(tops[(a, "target")] & set((lay * nn + rng.integers(0, nn, len(lay))).tolist())) for _ in range(200)]
        md.append(f"| {a} × {b} | {ov} | {np.mean(perm):.2f} |")
        res[f"overlap_{a}_{b}"] = {"overlap": ov, "chance": float(np.mean(perm))}
    common = set.intersection(*[tops[(b, "target")] for b in D]) if D else set()
    md += ["", f"- neurons in the top-200 of all {len(D)} benchmarks (targets): {len(common)}", ""]
    lens_ok = True
    try:
        import jlens  # noqa: F401
    except ImportError:
        lens_ok = False
    md += ["## 4. The shared neurons and the strongest per-benchmark neurons, with J-lens readouts of their output vectors", ""]
    show = sorted(common, key=lambda x: -sum(scores[(b, "target")][x] for b in D))[:30]
    per_b = {b: list(np.argsort(-scores[(b, "target")])[:12]) for b in D}
    want = sorted(set(show) | {int(x) for v in per_b.values() for x in v})
    readout = {}
    if lens_ok and want:
        from huggingface_hub import hf_hub_download
        import jlens
        from safetensors import safe_open
        lensobj = jlens.JacobianLens.load(hf_hub_download(C.LENS_REPO, C.LENS_FILE, revision=C.LENS_REV))
        snap = Path(hf_hub_download(C.MODEL, "model.safetensors.index.json", revision=C.REV)).parent
        index = json.loads((snap / "model.safetensors.index.json").read_text())["weight_map"]

        def tensor(name):
            with safe_open(str(snap / index[name]), framework="pt") as f:
                return f.get_tensor(name).float()
        W_U = tensor("lm_head.weight") if "lm_head.weight" in index else tensor("model.language_model.embed_tokens.weight")
        gname = "model.language_model.norm.weight"
        gam = tensor(gname)
        gw = gam if gam.abs().mean() > 0.5 else 1 + gam
        for x in want:
            l, nidx = x // nn, x % nn
            w = tensor(f"model.language_model.layers.{l}.mlp.down_proj.weight")[:, nidx]
            if l in lensobj.jacobians and l < 31:
                w = lensobj.jacobians[l].float() @ w
            lg = W_U @ (w * gw / w.pow(2).mean().sqrt())
            readout[x] = [tok.decode([t]) for t in torch.topk(lg, 10).indices.tolist()]
    md += ["| neuron | " + " | ".join(f"{b} mean attr (target)" for b in D) + " | readout (J-lens top-10) |",
           "|---|" + "---|" * len(D) + "---|"]
    for x in show:
        md.append(f"| L{x // nn}/N{x % nn} | " + " | ".join(f"{scores[(b, 'target')][x]:+.3f}" for b in D) + f" | {readout.get(x, '-')} |")
    for b in D:
        md += ["", f"### strongest in {b} (targets)", "", "| neuron | mean attr | in top-100 of % of units | readout |", "|---|---|---|---|"]
        s, f, cnt = per_bench_scores(D[b], nl, nn, "target")
        for x in per_b[b]:
            md.append(f"| L{x // nn}/N{x % nn} | {s[x]:+.3f} | {100 * f[x] / max(1, cnt):.0f} % | {readout.get(int(x), '-')} |")
    md += ["", "## 5. Target − reference: neurons that separate harmful commits from normal ones (AgentDojo, AM)", ""]
    for b in ("dojo", "am"):
        if b not in D:
            continue
        diff = scores[(b, "target")] - scores[(b, "reference")]
        top = np.argsort(-np.abs(diff))[:10]
        md.append(f"- {b}: " + ", ".join(f"L{x // nn}/N{x % nn} ({diff[x]:+.3f})" for x in top))
    md += ["", "## 6. Heads shared across benchmarks (mean signed attribution of each head, targets; top-10 per benchmark)", ""]
    for b, d in D.items():
        rs = [r for r in d["rows"] if r["label"] == "target"]
        if not rs:
            continue
        flat = defaultdict(float)
        for r in rs:
            for l, hs_ in enumerate(r["heads"]):
                for h, v in enumerate(hs_):
                    flat[(l, h)] += v / len(rs)
        top = sorted(flat, key=lambda k: -flat[k])[:10]
        res[f"heads_{b}"] = [[k[0], k[1], flat[k]] for k in top]
        md.append(f"- {b}: " + ", ".join(f"L{l}H{h} ({flat[(l, h)]:+.2f})" for l, h in top))
    (out / "report.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


def transfer(out):
    out = Path(out)
    tok, model = C.load()
    H = C.Hooked(model)
    nl, nn = H.nl, H.nn
    D = {}
    for b in BENCHES:
        p = out / b
        if (p / "rows.json").is_file():
            z = np.load(p / "attr_top.npz")
            D[b] = {"rows": json.loads((p / "rows.json").read_text(encoding="utf-8")), "idx": z["idx"], "val": z["val"],
                    "mu": torch.tensor(z["ref_act_mean"])}
    md = ["# Cross-benchmark transfer of shared commit neurons (decision position, mean replacement)", "",
          "| held-out benchmark | K | flip (shared neurons from the other two) | flip (random, same layers) | units |", "|---|---|---|---|---|"]
    rng = np.random.default_rng(1)
    for held in D:
        others = [b for b in D if b != held]
        if not others:
            continue
        s = sum(per_bench_scores(D[b], nl, nn, "target")[0] for b in others)
        items = [it for it in load_items(held, tok) if it["alts"] and it["label"] == "target"]
        for K in (64, 256):
            top = np.argsort(-s)[:K]
            rand = (top // nn) * nn + rng.integers(0, nn, K)
            res = {}
            for name, sel in (("shared", top), ("random", rand)):
                by = defaultdict(list)
                for x in sel.tolist():
                    by[x // nn].append(x % nn)
                ed = {("down", l): C.Edit("neur", idx=torch.tensor(ns), vec=D[held]["mu"][l][ns]) for l, ns in by.items()}
                flips = 0
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
                    m0 = float(lp[0, it["chosen"]].max() - lp[0, it["alts"]].max())
                    m1 = float(lp[1, it["chosen"]].max() - lp[1, it["alts"]].max())
                    flips += int(m0 > 0 and m1 < 0)
                    del cache
                res[name] = flips / max(1, len(items))
            md.append(f"| {held} | {K} | {res['shared']:.0%} | {res['random']:.0%} | {len(items)} |")
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
