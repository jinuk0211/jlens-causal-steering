"""J-Cascade stage 1b (vast box): neuron map for transfer decisions.
Reference: every decision point of the 278 unsteered episodes -> per-neuron p3 / p97 / mean (layers 12-31).
Transfer rows: bad = unneeded transfer in a failed episode, good = transfer in a passed episode (as stage 0).
Per pole (neuron, sign): fires = value beyond its p97 (+) or p3 (-); firing rate bad vs good at the decision point and at the
tool-name point; smoothed log ratio, one-sided Fisher p, and a label-permutation null for the number of poles below p < 0.001.
Write direction of each pole read through the J-lens (W_U Norm(J_l W_down[:, n] * sign)): top words, word families, direct logit
on the transfer tool-name token and on <tool_call>.
Output /workspace/jc/out/neuron_map.json + neuron_map.md
"""
import glob
import gzip
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

J = Path(__import__("os").environ.get("JC_DIR", "/workspace/jc"))
sys.path.insert(0, str(J / "data"))
LAYERS = list(range(12, 32))
FAM = {
    "inability": {"unable", "cannot", "can't", "无法", "我无法", "无法满足", "不能", "我不能", "impossible", "couldn"},
    "apology": {"apologize", "apologies", "sorry", "抱歉", "unfortunately", "regret", "sadly", "apologized"},
    "understanding": {"理解", "understand", "understanding", "understands", "understood", "明白", "understandable", "明白了"},
    "acknowledgement": {"acknowledge", "acknowledges", "acknowledging", "acknowledgment", "ack", "sincerely", "recognizing",
                        "recognize", "recogn", "honestly"},
    "transfer": {"transfer", "transferring", "human", "specialist", "representative", "escalate", "supervisor", "agent"},
    "retry": {"check", "alternative", "alternatives", "another", "try", "options", "option", "instead", "let", "look", "explore",
              "other", "verify", "retry", "again"},
    "proceed": {"proceed", "confirm", "confirmed", "alright", "okay", "will", "我将", "我来", "确认", "同意", "perfect"},
}


def fisher_one_sided(a, b, c, d):
    # P(X >= a) for the 2x2 table [[a, b], [c, d]] (rows: fired / not, cols: bad / good)
    n1, n2, k = a + c, b + d, a + b
    tot = math.comb(n1 + n2, k)
    return sum(math.comb(n1, x) * math.comb(n2, k - x) for x in range(a, min(k, n1) + 1)) / tot


def main():
    from huggingface_hub import snapshot_download
    from safetensors import safe_open
    from transformers import AutoTokenizer
    import jlens
    from jlens_causal.vocab_trigger import load_readout_head

    import os
    mp = Path(os.environ.get("JC_MODEL") or snapshot_download("Qwen/Qwen3.5-4B", revision="851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"))
    lp = os.environ.get("JC_LENS") or glob.glob(str(J / "hf/hub/models--neuronpedia--jacobian-lens/snapshots/*/qwen3.5-4b/jlens/Salesforce-wikitext/*n1000.pt"))[0]
    tok = AutoTokenizer.from_pretrained(mp)
    voc = json.loads(gzip.open(J / "data/vocab.json.gz", "rt", encoding="utf-8").read())
    norm = [v.strip().lower() for v in voc]
    turns = json.loads((J / "data/cache_turns.json").read_text(encoding="utf-8"))
    lab = {}
    for t in turns:
        if "transfer_to_human_agents" not in t["calls"]:
            continue
        bad = any(b.startswith("unexpected_transfer") for b in t["bad"])
        y = 1 if (bad and not t["ep_pass"]) else (0 if t["ep_pass"] else None)
        if y is not None:
            lab[(t["domain"], t["sim"], t["turn"])] = y
    ref, dec_rows, tn_rows = [], [], []
    for f in sorted((J / "out/neurons").glob("*.npz")):
        z = np.load(f)
        m = json.loads(str(z["meta"]))
        ref.append(z["dec_a"])
        for i, t in enumerate(z["dec_turn"].tolist()):
            y = lab.get((m["domain"], m["sim_id"], t))
            if y is not None:
                dec_rows.append((y, m["domain"], m["task_id"], z["dec_a"][i]))
        for i, t in enumerate(z["tn_turn"].tolist()):
            y = lab.get((m["domain"], m["sim_id"], t))
            if y is not None:
                tn_rows.append((y, m["domain"], m["task_id"], z["tn_a"][i]))
    ref = np.concatenate(ref).astype(np.float32)
    p3, p97, mean = np.percentile(ref, 3, axis=0), np.percentile(ref, 97, axis=0), ref.mean(0)
    print("reference decision points", ref.shape, "transfer rows dec", len(dec_rows), "tn", len(tn_rows), flush=True)
    del ref

    head = load_readout_head(mp)
    lens = jlens.JacobianLens.load(lp)
    U = head.unembed.float().cuda()
    index = json.loads((mp / "model.safetensors.index.json").read_text())["weight_map"]
    pre = "model.language_model." if any(k.startswith("model.language_model.") for k in index) else "model."
    tid_transfer = tok.encode("transfer_to_human_agents", add_special_tokens=False)[0]
    tid_call = tok.convert_tokens_to_ids("<tool_call>")
    readout = {}
    for li, layer in enumerate(LAYERS):
        name = f"{pre}layers.{layer}.mlp.down_proj.weight"
        with safe_open(mp / index[name], framework="pt") as h:
            W = h.get_tensor(name).float().cuda()  # [hidden, 9216]
        D = W.T  # neuron write directions
        moved = lens.transport(D, layer) if layer in lens.jacobians else D
        top_p, top_n, eff = [], [], []
        for s in range(0, D.shape[0], 512):
            lg = head.norm(moved[s:s + 512].cpu()).cuda() @ U.T
            top_p.append(lg.topk(15, -1).indices.cpu())
            top_n.append((-lg).topk(15, -1).indices.cpu())
            eff.append(torch.stack([lg[:, tid_transfer] - lg.mean(-1), lg[:, tid_call] - lg.mean(-1)], 1).cpu())
        readout[layer] = (torch.cat(top_p).numpy(), torch.cat(top_n).numpy(), torch.cat(eff).numpy())
        print("readout layer", layer, flush=True)

    def family(ids):
        c = Counter()
        for i in ids[:15]:
            for f, ws in FAM.items():
                if norm[i] in ws:
                    c[f] += 1
        return c.most_common(1)[0][0] if c else None

    def pole_stats(rows, rng=None):
        y = np.array([r[0] for r in rows])
        A = np.stack([r[3] for r in rows]).astype(np.float32)
        if rng is not None:
            y = y.copy()
            dom = np.array([r[1] for r in rows])
            for d in set(dom.tolist()):
                k = np.nonzero(dom == d)[0]
                y[k] = rng.permutation(y[k])
        fpos, fneg = A >= p97[None], A <= p3[None]
        out = {}
        for sign, F in (("+", fpos), ("-", fneg)):
            nb, ng = F[y == 1].sum(0), F[y == 0].sum(0)
            out[sign] = (nb, ng)
        return y, out

    res = {}
    rng = np.random.default_rng(0)
    for point, rows in (("decision", dec_rows), ("toolname", tn_rows)):
        y, st = pole_stats(rows)
        NB, NG = int(y.sum()), int((1 - y).sum())
        cands = []
        for sign in ("+", "-"):
            nb, ng = st[sign]
            lr = np.log((nb / NB + 0.03) / (ng / NG + 0.03))
            order = np.argsort(-lr.ravel())[:400]
            for flat in order:
                li, n = divmod(int(flat), 9216)
                a, b = int(nb[li, n]), int(ng[li, n])
                if a < 4:
                    continue
                p = fisher_one_sided(a, b, NB - a, NG - b)
                tp, tn_, eff = readout[LAYERS[li]]
                words = tp[n] if sign == "+" else tn_[n]
                cands.append({"layer": LAYERS[li], "neuron": n, "pole": sign, "bad": f"{a}/{NB}", "good": f"{b}/{NG}",
                              "log_ratio": round(float(lr[li, n]), 2), "fisher_p": float(p),
                              "family": family(words), "words": [voc[i] for i in words[:10]],
                              "eff_transfer": round(float(eff[n, 0] * (1 if sign == "+" else -1)), 3),
                              "eff_toolcall": round(float(eff[n, 1] * (1 if sign == "+" else -1)), 3)})
        cands.sort(key=lambda c: c["fisher_p"])
        null = []
        for _ in range(20):
            yp, stp = pole_stats(rows, rng)
            cnt = 0
            for sign in ("+", "-"):
                nb, ng = stp[sign]
                lr = np.log((nb / NB + 0.03) / (ng / NG + 0.03))
                for flat in np.argsort(-lr.ravel())[:400]:
                    li, n = divmod(int(flat), 9216)
                    a, b = int(nb[li, n]), int(ng[li, n])
                    if a >= 4 and fisher_one_sided(a, b, NB - a, NG - b) < 1e-3:
                        cnt += 1
            null.append(cnt)
        real = sum(1 for c in cands if c["fisher_p"] < 1e-3)
        res[point] = {"n_bad": NB, "n_good": NG, "n_poles_p001": real, "null_p001_mean": float(np.mean(null)), "null_p001_max": int(max(null)),
                      "top": cands[:60], "layer_hist_p001": dict(Counter(c["layer"] for c in cands if c["fisher_p"] < 1e-3))}
        print(point, "real", real, "null", np.mean(null), flush=True)
    retry, bipolar = [], []
    for layer in LAYERS:
        tp, tn_, eff = readout[layer]
        for n in range(9216):
            fp, fn = family(tp[n]), family(tn_[n])
            if fp == "retry" or fn == "retry":
                retry.append({"layer": layer, "neuron": n, "pole": "+" if fp == "retry" else "-",
                              "words": [voc[i] for i in (tp[n] if fp == "retry" else tn_[n])[:10]]})
            give = {"inability", "apology", "understanding", "acknowledgement", "transfer"}
            go = {"retry", "proceed"}
            if (fp in give and fn in go) or (fn in give and fp in go):
                bipolar.append({"layer": layer, "neuron": n, "plus": fp, "minus": fn,
                                "plus_words": [voc[i] for i in tp[n][:8]], "minus_words": [voc[i] for i in tn_[n][:8]]})
    res["retry_neurons"] = retry[:200]
    res["n_retry_neurons"] = len(retry)
    res["bipolar_neurons"] = bipolar[:200]
    res["n_bipolar"] = len(bipolar)
    (J / "out/neuron_map.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    md = ["# J-Cascade stage 1b: neuron map (transfer decisions)", ""]
    for point in ("decision", "toolname"):
        r = res[point]
        md += [f"## {point} point: bad {r['n_bad']} vs good {r['n_good']}",
               f"- poles with one-sided Fisher p < 0.001: {r['n_poles_p001']} (label-permutation null mean {r['null_p001_mean']}, max {r['null_p001_max']})",
               f"- layers of those poles: {r['layer_hist_p001']}", "",
               "| layer | neuron | pole | bad | good | p | family | J-lens words | eff transfer | eff <tool_call> |", "|---|---|---|---|---|---|---|---|---|---|"]
        md += [f"| L{c['layer']} | {c['neuron']} | {c['pole']} | {c['bad']} | {c['good']} | {c['fisher_p']:.1e} | {c['family']} | "
               + " · ".join(repr(w) for w in c["words"][:6]).replace("|", "/") + f" | {c['eff_transfer']} | {c['eff_toolcall']} |" for c in r["top"][:30]]
        md.append("")
    md += [f"## retry-family poles: {res['n_retry_neurons']}; bipolar give-up/go poles: {res['n_bipolar']}", ""]
    md += [f"- L{b['layer']} N{b['neuron']}: + {b['plus']} {b['plus_words'][:5]} / - {b['minus']} {b['minus_words'][:5]}" for b in bipolar[:30]]
    (J / "out/neuron_map.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("STAGE1B_DONE", flush=True)


if __name__ == "__main__":
    main()
