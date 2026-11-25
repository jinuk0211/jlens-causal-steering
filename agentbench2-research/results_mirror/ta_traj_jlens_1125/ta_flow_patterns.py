"""Shared neuron patterns in failure trajectories (CPU, reads ta_neuron_flow.py output + neuron-explorer dictionary).
Groups: fail = target whose call is clearly-misaligned or boundary; aligned = target with a legit call; ref = reference
(writeInternalLog). A neuron key is (layer, neuron, sign). It is present in a window if it is among the K strongest
neurons of its layer (|v|, act_scale units) at some token of the window.
Windows: doc (whole input; lengths reported), in64 (last 64 input tokens), first64 / last64 (first / last 64 response
tokens before the call, units with >= 70 response tokens only, so every unit has the same window length), scaffold.
1. Descriptive: keys with the largest P(present | fail) - max(P(present | ref), P(present | aligned)), with what the
   neuron writes (steer lens), what it reads (S lens) and how often it is present in each group. Not validated.
2. Validated: leave-one-domain-out, pick 20 keys on the other domains (P(neg) <= 0.25), score a held-out unit by how many
   are present; AUC, recall at train false fire <= 10 %, false fire on aligned targets and references.
   Label-free: count of lexicon neurons (ne_candidates.json write >= 4, pole = sign) present; threshold = 90th percentile
   of references.
3. Per-sentence flow for example units: the strongest uncommon neurons of each response sentence (strength x idf,
   idf from how many units have the key anywhere), for failures and for references of the same domain.
Usage: python ta_flow_patterns.py FLOW_DIR NE_CACHE_DIR SEQS_JSON ne_candidates.json OUT_MD [OUT_VIEWER_JSON]"""
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

NN = 9216
WINDOWS = ["doc", "in64", "first64", "last64", "scaffold"]


def auc(pos, neg):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if not len(pos) or not len(neg):
        return None
    allv = np.concatenate([pos, neg])
    r = np.argsort(np.argsort(allv, kind="mergesort"), kind="mergesort") + 1.0
    for v in np.unique(allv):
        m = allv == v
        r[m] = r[m].mean()
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def keys_of(fi, fv):
    """fi, fv [T, L, K] -> int64 keys layer * 2N + neuron * 2 + (v < 0)."""
    L = fi.shape[1]
    lay = np.arange(L, dtype=np.int64)[None, :, None]
    return lay * 2 * NN + fi.astype(np.int64) * 2 + (fv < 0)


def main():
    fd, cache, seqs_p, cand_p, out_md = (Path(a) for a in sys.argv[1:6])
    viewer_p = Path(sys.argv[6]) if len(sys.argv) > 6 else None
    toks = {n: u["ids"] for n, u in enumerate(json.loads(seqs_p.read_text(encoding="utf-8")))}
    units = json.loads((fd / "units.json").read_text(encoding="utf-8"))
    vocab = json.loads((cache / "vocab.json").read_text(encoding="utf-8"))
    vs = lambda t: str(vocab[t]).replace("Ġ", " ").replace("Ċ", "\\n").replace("\n", "\\n").replace("|", "¦") if 0 <= t < len(vocab) else "?"
    ix = {k: np.load(cache / f"{k}_index.npz") for k in ("steer", "s")}
    cand = json.loads(cand_p.read_text(encoding="utf-8"))
    lex = {c["layer"] * 2 * NN + c["neuron"] * 2 + (c["pole"] == "-") for c in cand if c["write"] >= 4}

    def label(key, k=5):
        l, rest = divmod(int(key), 2 * NN)
        n, neg = divmod(rest, 2)
        pole = "down" if neg else "up"
        return (f"L{l}/N{n}{'-' if neg else '+'}", " ".join(vs(t) for t in ix["steer"][pole][l, n, :k]),
                " ".join(vs(t) for t in ix["s"][pole][l, n, :k]))

    U, sent_data = [], {}
    df = Counter()
    for u in units:
        f = fd / f"f_{u['idx']}.npz"
        if not f.is_file():
            continue
        z = np.load(f)
        fi, fv = z["flow_idx"], z["flow_val"]
        keys = keys_of(fi, fv)
        on, ss, pos = u["onset"], u["scaf_start"], u["pos"]
        win = {"doc": (1, on), "in64": (max(1, on - 64), on), "scaffold": (ss, pos + 1)}
        if ss - on >= 70:
            win["first64"] = (on + 1, on + 65)
            win["last64"] = (ss - 64, ss)
        pres = {w: set(np.unique(keys[a:b]).tolist()) for w, (a, b) in win.items()}
        allk = set().union(*pres.values())
        df.update(allk)
        grp = "fail" if u["label"] == "target" and u["risk"] != "aligned" else ("aligned" if u["label"] == "target" else "ref")
        U.append({"u": u, "grp": grp, "pres": pres, "doc_len": on - 1, "pre": ss - on})
        sent_data[u["idx"]] = (keys[on:ss + 1], np.abs(fv[on:ss + 1].astype(np.float32)), z["flow_val"].shape[0])
    if not U:
        raise SystemExit("no flow files")
    nU = len(U)
    G = Counter(x["grp"] for x in U)
    md = ["# Shared neuron patterns in failure trajectories (ToolAlign-4B, per-token top-K neurons, act_scale units)", "",
          f"Units: {nU} ({dict(G)}). Doc length median: " + ", ".join(
              f"{g} {int(np.median([x['doc_len'] for x in U if x['grp'] == g]))}" for g in ("fail", "aligned", "ref") if G[g]) +
          ". Units with >= 70 response tokens: " + ", ".join(f"{g} {sum(1 for x in U if x['grp'] == g and x['pre'] >= 70)}" for g in ("fail", "aligned", "ref")), ""]

    def rates(xs, w, key):
        out = {}
        for g in ("fail", "aligned", "ref"):
            v = [key in x["pres"][w] for x in xs if x["grp"] == g and w in x["pres"]]
            out[g] = (float(np.mean(v)) if v else float("nan"), len(v))
        return out

    md += ["## 1. Keys most specific to failures (descriptive, all units, not validated)", "",
           "| window | neuron | fail | aligned | ref | writes (steer lens) | reads (S lens) |", "|---|---|---|---|---|---|---|"]
    for w in WINDOWS:
        xs = [x for x in U if w in x["pres"]]
        nf, nr = sum(1 for x in xs if x["grp"] == "fail"), sum(1 for x in xs if x["grp"] == "ref")
        if nf < 3 or nr < 5:
            md.append(f"| {w} | (skipped: {nf} fail, {nr} ref) | | | | | |")
            continue
        cnt = {g: Counter() for g in ("fail", "aligned", "ref")}
        ng = Counter(x["grp"] for x in xs)
        for x in xs:
            cnt[x["grp"]].update(x["pres"][w])
        sc = []
        for key, c in cnt["fail"].items():
            pf = c / ng["fail"]
            pa = cnt["aligned"][key] / ng["aligned"] if ng["aligned"] else 0.0
            pr = cnt["ref"][key] / ng["ref"] if ng["ref"] else 0.0
            sc.append((pf - max(pa, pr), key, pf, pa, pr))
        sc.sort(reverse=True)
        for d, key, pf, pa, pr in sc[:12]:
            nm, wr, rd = label(key)
            md.append(f"| {w} | {nm} | {pf:.0%} ({ng['fail']}) | {pa:.0%} ({ng['aligned']}) | {pr:.0%} ({ng['ref']}) | {wr} | {rd} |")
    md.append("")

    md += ["## 2. Held-out detection (leave-one-domain-out)", "",
           "| window | detector | n fail / aligned / ref | AUC fail vs rest | recall | false fire aligned | false fire ref | keys picked in most folds |",
           "|---|---|---|---|---|---|---|---|"]
    for w in WINDOWS:
        xs = [x for x in U if w in x["pres"]]
        if sum(1 for x in xs if x["grp"] == "fail") < 3:
            continue
        doms = sorted({x["u"]["domain"] for x in xs})
        score, fire, picked = {}, {}, Counter()
        for d in doms:
            tr = [x for x in xs if x["u"]["domain"] != d]
            tp = [x for x in tr if x["grp"] == "fail"]
            tn = [x for x in tr if x["grp"] != "fail"]
            if len(tp) < 3 or len(tn) < 3:
                continue
            cp, cn = Counter(), Counter()
            for x in tp:
                cp.update(x["pres"][w])
            for x in tn:
                cn.update(x["pres"][w])
            cands = [(cp[k] / len(tp) - cn[k] / len(tn), k) for k in cp if cn[k] / len(tn) <= 0.25]
            sel = [k for _, k in sorted(cands, reverse=True)[:20]]
            picked.update(sel)
            trs = [sum(k in x["pres"][w] for k in sel) for x in tn]
            th = np.percentile(trs, 90) if trs else 0
            for x in xs:
                if x["u"]["domain"] == d:
                    s = sum(k in x["pres"][w] for k in sel)
                    score[x["u"]["idx"]], fire[x["u"]["idx"]] = s, s > th
        g = lambda grp, dct: [dct[x["u"]["idx"]] for x in xs if x["grp"] == grp and x["u"]["idx"] in dct]
        a = auc(g("fail", score), g("aligned", score) + g("ref", score))
        rr = lambda v: f"{np.mean(v):.0%}" if v else "-"
        ex = "; ".join(label(k)[0] + " " + label(k, 3)[1] for k, _ in picked.most_common(4))
        md.append(f"| {w} | LODO 20 keys | {len(g('fail', score))}/{len(g('aligned', score))}/{len(g('ref', score))} | "
                  f"{'-' if a is None else f'{a:.2f}'} | {rr(g('fail', fire))} | {rr(g('aligned', fire))} | {rr(g('ref', fire))} | {ex} |")
        ls = {x["u"]["idx"]: len(x["pres"][w] & lex) for x in xs}
        refv = [ls[x["u"]["idx"]] for x in xs if x["grp"] == "ref"]
        th = np.percentile(refv, 90) if refv else 0
        lf = {i: v > th for i, v in ls.items()}
        a = auc(g("fail", ls), g("aligned", ls) + g("ref", ls))
        md.append(f"| {w} | lexicon neurons ({len(lex)}) | {len(g('fail', ls))}/{len(g('aligned', ls))}/{len(g('ref', ls))} | "
                  f"{'-' if a is None else f'{a:.2f}'} | {rr(g('fail', lf))} | {rr(g('aligned', lf))} | {rr(g('ref', lf))} | label-free |")
    md.append("")

    idf = {k: math.log((nU + 1) / c) for k, c in df.items()}
    md += ["## 3. Per-sentence flow, example units (strongest uncommon neurons: max |v| x idf over the sentence)", ""]
    viewer = []
    fails = [x for x in U if x["grp"] == "fail" and x["pre"] >= 30]
    picks = fails[:6]
    for x in list(picks):
        refs = [y for y in U if y["grp"] == "ref" and y["u"]["domain"] == x["u"]["domain"]]
        if refs:
            picks.append(max(refs, key=lambda y: y["pre"]))
    for x in picks:
        u = x["u"]
        keys, av, _ = sent_data[u["idx"]]
        ids = toks.get(u["idx"])
        bounds, a = [], 0
        for t in range(keys.shape[0]):
            piece = vs(ids[u["onset"] + t]) if ids else ""
            if ids and (re.search(r"[.!?。]\s*$", piece) or "\\n" in piece) or t == keys.shape[0] - 1:
                bounds.append((a, t + 1))
                a = t + 1
        if not ids:
            bounds = [(s, min(s + 32, keys.shape[0])) for s in range(0, keys.shape[0], 32)]
        md.append(f"### unit {u['idx']} ({x['grp']}, {u['domain']}, tool {u['tool']}, risk {u['risk']}, {x['pre']} response tokens)")
        md.append("")
        rows = []
        for a, b in bounds:
            best = {}
            for t in range(a, b):
                for kk, vv in zip(keys[t].ravel().tolist(), av[t].ravel().tolist()):
                    s = vv * idf.get(kk, 0.0)
                    if s > best.get(kk, 0.0):
                        best[kk] = s
            top = sorted(best.items(), key=lambda kv: -kv[1])[:4]
            text = "".join(vs(ids[u["onset"] + t]) for t in range(a, b)) if ids else f"tokens {a}-{b}"
            text = text.replace("\n", " ")[:90]
            nl = "; ".join(f"{label(k)[0]} ({label(k, 3)[1]})" for k, _ in top)
            md.append(f"- `{text}` → {nl}")
            rows.append({"text": text, "neurons": [{"id": label(k)[0], "writes": label(k)[1], "reads": label(k)[2], "score": round(s, 2)} for k, s in top]})
        md.append("")
        viewer.append({"idx": u["idx"], "grp": x["grp"], "domain": u["domain"], "tool": u["tool"], "risk": u["risk"], "sentences": rows})
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    if viewer_p:
        viewer_p.write_text(json.dumps(viewer, ensure_ascii=False), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
