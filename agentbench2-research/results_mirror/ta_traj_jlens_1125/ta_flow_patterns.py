"""Shared neuron patterns in failure trajectories (CPU, reads ta_neuron_flow.py output + neuron-explorer dictionary).
Groups: fail = target whose call is clearly-misaligned or boundary; aligned = target with a legit call; ref = reference
(writeInternalLog). A neuron key is (layer, neuron, sign). It is present in a window if it is among the K strongest
neurons of its layer (|v|, act_scale units) at some token of the window.
Windows: doc (whole input; lengths reported), in64 (last 64 input tokens), first64 / last64 (first / last 64 response
tokens before the call, units with >= 70 response tokens only, so every unit has the same window length), scaffold.
1. Descriptive: keys with the largest P(present | fail) - max(P(present | ref), P(present | aligned)), with what the
   neuron writes (steer lens), what it reads (S lens) and how often it is present in each group. Not validated.
2. Validated: leave-one-domain-out, pick 20 keys on the other domains (P(neg) <= 0.25), score a held-out unit by how many
   are present; AUC, recall and false fire at the 90th percentile of the training negatives.
   Label-free: how many lexicon neurons (ne_candidates.json write >= 4, pole = sign) or risk-phrase neurons (top 200 by
   risk-phrase minus neutral-phrase activation, act_scale units, layers >= 4) are present; threshold = 90th percentile of
   references.
3. Per-sentence flow for example units: the strongest uncommon neurons of each response sentence (strength x idf, idf from
   how many units have the key anywhere), for failures and for references of the same domain.
Usage: python ta_flow_patterns.py FLOW_DIR NE_CACHE_DIR SEQS_JSON ne_candidates.json OUT_MD [OUT_VIEWER_JSON]"""
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

NN = 9216
WINDOWS = ["doc", "in64", "first64", "last64", "scaffold"]
GRPS = ("fail", "aligned", "ref")


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
    """fi, fv [T, L, K] -> int32 keys layer * 2N + neuron * 2 + (v < 0)."""
    lay = np.arange(fi.shape[1], dtype=np.int32)[None, :, None]
    return lay * 2 * NN + fi.astype(np.int32) * 2 + (fv < 0)


def main():
    fd, cache, seqs_p, cand_p, out_md = (Path(a) for a in sys.argv[1:6])
    viewer_p = Path(sys.argv[6]) if len(sys.argv) > 6 else None
    toks = {n: u["ids"] for n, u in enumerate(json.loads(seqs_p.read_text(encoding="utf-8")))}
    units = json.loads((fd / "units.json").read_text(encoding="utf-8"))
    vocab = json.loads((cache / "vocab.json").read_text(encoding="utf-8"))
    vs = lambda t: str(vocab[t]).replace("Ġ", " ").replace("Ċ", "\\n").replace("\n", "\\n").replace("|", "¦") if 0 <= t < len(vocab) else "?"
    ix = {k: np.load(cache / f"{k}_index.npz") for k in ("steer", "s")}
    nl = ix["steer"]["up"].shape[0]
    NK = nl * 2 * NN
    cand = json.loads(cand_p.read_text(encoding="utf-8"))
    lex = np.array(sorted({c["layer"] * 2 * NN + c["neuron"] * 2 + (c["pole"] == "-") for c in cand if c["write"] >= 4}), np.int64)
    sets = {f"lexicon neurons ({len(lex)})": lex}
    ph = fd / "phrases.npz"
    if ph.is_file():
        z = np.load(ph)
        P, nr = z["act"], int(z["n_risk"])
        sc = np.load(cache / "act_scale.npz")
        ps, ng = np.maximum(sc["pos"], 1e-2), np.maximum(np.abs(sc["neg"]), 1e-2)
        up = P[:, 0] / ps
        dn = -P[:, 1] / ng
        d = np.stack([up[:nr].mean(0) - up[nr:].mean(0), dn[:nr].mean(0) - dn[nr:].mean(0)], -1)
        d[:4] = -np.inf
        flat = d.reshape(-1)
        sets["risk-phrase neurons (200)"] = np.sort(np.argsort(-flat)[:200]).astype(np.int64)

    def label(key, k=5):
        l, rest = divmod(int(key), 2 * NN)
        n, neg = divmod(rest, 2)
        pole = "down" if neg else "up"
        return (f"L{l}/N{n}{'-' if neg else '+'}", " ".join(vs(t) for t in ix["steer"][pole][l, n, :k]),
                " ".join(vs(t) for t in ix["s"][pole][l, n, :k]))

    U, sent_data = [], {}
    df = np.zeros(NK, np.int32)
    for u in units:
        f = fd / f"f_{u['idx']}.npz"
        if not f.is_file():
            continue
        z = np.load(f)
        fv = z["flow_val"]
        keys = keys_of(z["flow_idx"], fv)
        on, ss, pos = u["onset"], u["scaf_start"], u["pos"]
        win = {"doc": (1, on), "in64": (max(1, on - 64), on), "scaffold": (ss, pos + 1)}
        if ss - on >= 70:
            win["first64"] = (on + 1, on + 65)
            win["last64"] = (ss - 64, ss)
        pres = {w: np.unique(keys[a:b]) for w, (a, b) in win.items()}
        df[np.unique(np.concatenate(list(pres.values())))] += 1
        grp = "fail" if u["label"] == "target" and u["risk"] != "aligned" else ("aligned" if u["label"] == "target" else "ref")
        U.append({"u": u, "grp": grp, "pres": pres, "doc_len": on - 1, "pre": ss - on})
        sent_data[u["idx"]] = (keys[on:ss + 1].copy(), np.abs(fv[on:ss + 1].astype(np.float32)))
        del z, fv, keys
    if not U:
        raise SystemExit("no flow files")
    nU = len(U)
    G = Counter(x["grp"] for x in U)
    md = ["# Shared neuron patterns in failure trajectories (ToolAlign-4B, per-token top-K neurons, act_scale units)", "",
          f"Units: {nU} ({dict(G)}). Doc length median: " + ", ".join(
              f"{g} {int(np.median([x['doc_len'] for x in U if x['grp'] == g]))}" for g in GRPS if G[g]) +
          ". Units with >= 70 response tokens: " + ", ".join(f"{g} {sum(1 for x in U if x['grp'] == g and x['pre'] >= 70)}" for g in GRPS), ""]
    sec1 = ["## 1. Keys most specific to failures (descriptive, all units, not validated)", "",
            "| window | neuron | fail | aligned | ref | writes (steer lens) | reads (S lens) |", "|---|---|---|---|---|---|---|"]
    sec2 = ["## 2. Held-out detection (leave-one-domain-out)", "",
            "| window | detector | n fail / aligned / ref | AUC fail vs rest | recall | false fire aligned | false fire ref | keys picked in most folds |",
            "|---|---|---|---|---|---|---|---|"]
    rr = lambda v: f"{np.mean(v):.0%}" if len(v) else "-"
    fires_out = {}
    for w in WINDOWS:
        xs = [x for x in U if w in x["pres"]]
        grp = np.array([x["grp"] for x in xs])
        dom = np.array([x["u"]["domain"] for x in xs])
        nf, nrf = int((grp == "fail").sum()), int((grp == "ref").sum())
        if nf < 3 or nrf < 5:
            sec1.append(f"| {w} | (skipped: {nf} fail, {nrf} ref) | | | | | |")
            sec2.append(f"| {w} | (skipped: {nf} fail, {nrf} ref) | | | | | | |")
            continue
        M = np.zeros((len(xs), NK), bool)
        for r, x in enumerate(xs):
            M[r, x["pres"][w]] = True
        Pg = {g: M[grp == g].mean(0) if (grp == g).any() else np.zeros(NK) for g in GRPS}
        spec = Pg["fail"] - np.maximum(Pg["aligned"], Pg["ref"])
        for key in np.argsort(-spec)[:12]:
            nm, wr, rd = label(key)
            sec1.append(f"| {w} | {nm} | {Pg['fail'][key]:.0%} ({nf}) | {Pg['aligned'][key]:.0%} ({int((grp == 'aligned').sum())}) | "
                        f"{Pg['ref'][key]:.0%} ({nrf}) | {wr} | {rd} |")
        score = np.full(len(xs), np.nan)
        fire = np.zeros(len(xs), bool)
        picked = Counter()
        for d in sorted(set(dom)):
            tr = dom != d
            tp, tn = tr & (grp == "fail"), tr & (grp != "fail")
            if tp.sum() < 3 or tn.sum() < 3:
                continue
            pp, pn = M[tp].mean(0), M[tn].mean(0)
            diff = np.where(pn <= 0.25, pp - pn, -np.inf)
            sel = np.argsort(-diff)[:20]
            sel = sel[diff[sel] > 0]
            picked.update(sel.tolist())
            th = np.percentile(M[tn][:, sel].sum(1), 90)
            te = dom == d
            s = M[te][:, sel].sum(1)
            score[te], fire[te] = s, s > th
        ok = ~np.isnan(score)
        fires_out[w] = {str(xs[r]["u"]["idx"]): [None if np.isnan(score[r]) else float(score[r]), bool(fire[r]), xs[r]["grp"]]
                        for r in range(len(xs))}
        g = lambda name, arr: arr[ok & (grp == name)]
        a = auc(g("fail", score), np.concatenate([g("aligned", score), g("ref", score)]))
        ex = "; ".join(label(k)[0] + " " + label(k, 3)[1] for k, _ in picked.most_common(4))
        sec2.append(f"| {w} | LODO 20 keys | {len(g('fail', score))}/{len(g('aligned', score))}/{len(g('ref', score))} | "
                    f"{'-' if a is None else f'{a:.2f}'} | {rr(g('fail', fire))} | {rr(g('aligned', fire))} | {rr(g('ref', fire))} | {ex} |")
        for sname, keyset in sets.items():
            cnt = M[:, keyset].sum(1)
            th = np.percentile(cnt[grp == "ref"], 90)
            lf = cnt > th
            a = auc(cnt[grp == "fail"], cnt[grp != "fail"])
            top = np.argsort(-(Pg["fail"][keyset] - np.maximum(Pg["aligned"][keyset], Pg["ref"][keyset])))[:3]
            ex = "; ".join(label(keyset[k])[0] + " " + label(keyset[k], 3)[1] for k in top)
            sec2.append(f"| {w} | {sname} | {nf}/{int((grp == 'aligned').sum())}/{nrf} | {'-' if a is None else f'{a:.2f}'} | "
                        f"{rr(lf[grp == 'fail'])} | {rr(lf[grp == 'aligned'])} | {rr(lf[grp == 'ref'])} | label-free; most fail-specific: {ex} |")
        del M
    md += sec1 + [""] + sec2 + [""]
    out_md.with_name(out_md.stem + "_fires.json").write_text(json.dumps(fires_out), encoding="utf-8")

    idf = np.log((nU + 1) / np.maximum(df, 1)).astype(np.float32)
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
        keys, av = sent_data[u["idx"]]
        ids = toks.get(u["idx"])
        bounds, a = [], 0
        for t in range(keys.shape[0]):
            piece = vs(ids[u["onset"] + t])
            if re.search(r"[.!?。]\s*$", piece) or "\\n" in piece or t == keys.shape[0] - 1:
                if t + 1 > a:
                    bounds.append((a, t + 1))
                a = t + 1
        md.append(f"### unit {u['idx']} ({x['grp']}, {u['domain']}, tool {u['tool']}, risk {u['risk']}, {x['pre']} response tokens)")
        md.append("")
        rows = []
        for a, b in bounds:
            kk, sv = keys[a:b].ravel(), (av[a:b] * idf[keys[a:b]]).ravel()
            best = {}
            for k_, s_ in zip(kk.tolist(), sv.tolist()):
                if s_ > best.get(k_, -1.0):
                    best[k_] = s_
            top = sorted(best.items(), key=lambda kv: -kv[1])[:4]
            text = "".join(vs(ids[u["onset"] + t]) for t in range(a, b)).replace("\n", " ")[:90]
            if not text.strip(" \\n"):
                continue
            md.append(f"- `{text}` → " + "; ".join(f"{label(k)[0]} ({label(k, 3)[1]})" for k, _ in top))
            rows.append({"text": text, "neurons": [{"id": label(k)[0], "writes": label(k)[1], "reads": label(k)[2], "score": round(s, 2)} for k, s in top]})
        md.append("")
        viewer.append({"idx": u["idx"], "grp": x["grp"], "domain": u["domain"], "tool": u["tool"], "risk": u["risk"], "sentences": rows})
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    if viewer_p:
        viewer_p.write_text(json.dumps(viewer, ensure_ascii=False), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
