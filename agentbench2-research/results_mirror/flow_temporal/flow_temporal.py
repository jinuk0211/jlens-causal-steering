"""Temporal patterns in per-token neuron flow (top-K neurons per layer per token, act_scale units, sign kept).
Key = (layer, neuron, sign); a key is "on" at token t when it is in that layer's top-K at t (|score| >= MINV).
Per sequence, inside the model's own text (onset .. event):
  rise(key)   = on-rate in the PRE tokens just before the event - on-rate in the rest of the response before it (baseline),
                i.e. what changes as the model approaches the action, against the same sequence's own baseline.
  state(key)  = on-rate over the whole response part (persistent 'mode' neurons).
  lag(key)    = tokens before the event of the key's strongest firing inside PRE (for the cascade order).
Groups compared: positive (failure / harmful) vs negative (normal). Rise keys are picked on one fold and tested on the
other (held-out score = mean rise over the picked keys; AUC; picked on fold 0 -> test fold 1 and vice versa).
Datasets:
  toolalign: FLOW_DIR (f_{n}.npz + units.json); event = tool-call start (scaf_start); positive = target with risk != aligned,
             negatives = aligned targets + references; fold = md5(domain) parity.
  am:        DUMP_DIR with flow npz named by case key + CASES_JSON (am_resp_cases.json); event = first tool block (ev.tool),
             positive = harmful; negatives = harmless; fold = sample_id % 2; scenario given by --scenario.
Usage: python flow_temporal.py toolalign FLOW_DIR SEQS_JSON CACHE OUT_MD
       python flow_temporal.py am DUMP_DIR CASES_JSON CACHE OUT_MD [scenario]"""
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

PRE, MINBASE, MINV, TOPN = 64, 128, 1.0, 15


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


def load(kind, a, b):
    items = []
    if kind == "toolalign":
        fd = Path(a)
        units = json.loads((fd / "units.json").read_text(encoding="utf-8"))
        seqs = json.loads(Path(b).read_text(encoding="utf-8"))
        for u in units:
            f = fd / f"f_{u['idx']}.npz"
            if not f.is_file():
                continue
            pos = u["label"] == "target" and u["risk"] != "aligned"
            grp = "fail" if pos else ("aligned" if u["label"] == "target" else "ref")
            items.append({"f": f, "pos": pos, "grp": grp, "onset": u["onset"], "event": u["scaf_start"], "ids": seqs[u["idx"]]["ids"],
                          "fold": int(hashlib.md5(u["domain"].encode()).hexdigest(), 16) % 2, "name": f"#{u['idx']} {u['domain']} {u['tool']}"})
    else:
        dd = Path(a)
        cases = json.loads(Path(b).read_text(encoding="utf-8"))
        scen = sys.argv[6] if len(sys.argv) > 6 else None
        for c in cases:
            f = dd / f"f_{c['key'].replace('|', '_')}.npz"
            if not f.is_file() or c.get("harmful") is None or (scen and c["scenario"] != scen) or c["ev"]["tool"] is None:
                continue
            items.append({"f": f, "pos": bool(c["harmful"]), "grp": "harmful" if c["harmful"] else "harmless", "onset": c["onset"],
                          "event": c["ev"]["tool"], "ids": c["ids"], "fold": c["fold"], "name": c["domain"]})
    return items


def main():
    kind, a, b, cache, out = sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4]), Path(sys.argv[5])
    items = load(kind, a, b)
    N = 9216
    vocab = json.loads((cache / "vocab.json").read_text(encoding="utf-8"))
    vs = lambda t: str(vocab[t]).replace("Ġ", " ").replace("Ċ", "\\n").replace("\n", "\\n").replace("|", "/").strip() or repr(vocab[t])
    ix = {k: dict(np.load(cache / f"{k}_index.npz")) for k in ("steer", "s")}
    rows = []
    for it in items:
        z = np.load(it["f"])
        fi, fv = z["flow_idx"].astype(np.int64), z["flow_val"].astype(np.float32)
        on, ev = it["onset"], it["event"]
        if ev - on < PRE + MINBASE:
            continue
        T, L, K = fi.shape
        lay = np.arange(L)[None, :, None]
        key = lay * 2 * N + fi * 2 + (fv < 0)
        valid = np.abs(fv) >= MINV
        pre_k, pre_c = np.unique(key[ev - PRE:ev][valid[ev - PRE:ev]], return_counts=True)
        base_k, base_c = np.unique(key[on:ev - PRE][valid[on:ev - PRE]], return_counts=True)
        st_k, st_c = np.unique(key[on:ev][valid[on:ev]], return_counts=True)
        seg = key[ev - PRE:ev]
        segv = np.where(valid[ev - PRE:ev], np.abs(fv[ev - PRE:ev]), 0)
        rows.append({**{k: it[k] for k in ("pos", "grp", "fold", "name", "onset", "event")}, "ids": it["ids"],
                     "pre": dict(zip(pre_k.tolist(), (pre_c / PRE).tolist())),
                     "base": dict(zip(base_k.tolist(), (base_c / (ev - PRE - on)).tolist())),
                     "state": dict(zip(st_k.tolist(), (st_c / (ev - on)).tolist())),
                     "seg": seg, "segv": segv})
        del z, fi, fv, key, valid
    G = Counter(r["grp"] for r in rows)

    def rise(r, k):
        return r["pre"].get(k, 0.0) - r["base"].get(k, 0.0)

    def label(k):
        l, rest = divmod(int(k), 2 * N)
        n, neg = divmod(rest, 2)
        pole = "down" if neg else "up"
        return f"L{l}/N{n}{'-' if neg else '+'}", " ".join(vs(t) for t in ix["steer"][pole][l, n, :5]), " ".join(vs(t) for t in ix["s"][pole][l, n, :4])

    def mean_over(rs, f, keys):
        return {k: float(np.mean([f(r, k) for r in rs])) if rs else 0.0 for k in keys}

    md = [f"# Temporal flow patterns before the action ({kind})", "",
          f"Sequences with >= {PRE + MINBASE} response tokens before the action: {len(rows)} ({dict(G)}). PRE = the {PRE} tokens before "
          "the action; baseline = the earlier response tokens of the same sequence. A neuron is 'on' at a token when it is in its "
          f"layer's top-16 with |score| >= {MINV} (act_scale units).", ""]
    allk = set()
    for r in rows:
        allk |= set(r["pre"]) | set(r["state"])
    allk = np.array(sorted(allk))
    P = [r for r in rows if r["pos"]]
    Nn = [r for r in rows if not r["pos"]]

    def table(title, vals_by_group, order, extra=None):
        md.extend([f"## {title}", "", "| neuron | " + " | ".join(f"{g} (n={G[g]})" for g in vals_by_group) + " | writes (steer lens) | reads (S lens) |",
                   "|---|" + "---|" * len(vals_by_group) + "---|---|"])
        for k in order:
            nm, wr, rd = label(k)
            md.append(f"| {nm} | " + " | ".join(f"{vals_by_group[g][k]:+.2f}" for g in vals_by_group) + f" | {wr} | {rd} |")
        md.append("")

    grps = [g for g in G]
    R = {g: mean_over([r for r in rows if r["grp"] == g], rise, allk) for g in grps}
    pos_g = [g for g in grps if g in ("fail", "harmful")]
    neg_g = [g for g in grps if g not in pos_g]
    wt = {g: G[g] / len(rows) for g in grps}
    common = sorted(allk, key=lambda k: -sum(wt[g] * R[g][k] for g in grps))[:TOPN]
    table("1. Neurons that rise before the action in every group (approach-the-call pattern, all sequences)", R, common)
    spec = sorted(allk, key=lambda k: -(R[pos_g[0]][k] - max(R[g][k] for g in neg_g)))[:TOPN] if pos_g and neg_g else []
    if spec:
        table(f"2. Rise specific to {pos_g[0]} (descriptive, all sequences)", R, spec)
    S = {g: mean_over([r for r in rows if r["grp"] == g], lambda r, k: r["state"].get(k, 0.0), allk) for g in grps}
    stk = sorted(allk, key=lambda k: -sum(wt[g] * S[g][k] for g in grps))[:TOPN]
    md.append("State neurons below: on-rate over the whole response part before the action (not a rise).")
    table("3. Persistent 'state' neurons over the response", S, stk)
    md += ["## 4. Held-out test of the failure-specific rise (pick 30 keys on one fold, score the other)", "",
           "| train fold -> test fold | n pos / neg in test | AUC (mean rise over picked keys) |", "|---|---|---|"]
    for tr in (0, 1):
        trp = [r for r in P if r["fold"] == tr]
        trn = [r for r in Nn if r["fold"] == tr]
        te = [r for r in rows if r["fold"] != tr]
        if len(trp) < 3 or len(trn) < 3:
            md.append(f"| {tr} -> {1 - tr} | too few training sequences | - |")
            continue
        d = {k: np.mean([rise(r, k) for r in trp]) - np.mean([rise(r, k) for r in trn]) for k in allk}
        pick = sorted(d, key=lambda k: -d[k])[:30]
        sc = [np.mean([rise(r, k) for k in pick]) for r in te]
        a_ = auc([s for s, r in zip(sc, te) if r["pos"]], [s for s, r in zip(sc, te) if not r["pos"]])
        md.append(f"| {tr} -> {1 - tr} | {sum(r['pos'] for r in te)} / {sum(not r['pos'] for r in te)} | {'-' if a_ is None else f'{a_:.2f}'} |")
    md += ["", "## 5. Cascade: when the rising neurons fire, in tokens before the action (median over sequences where the key fires in PRE)", "",
           "| neuron | median tokens before action | sequences | writes (steer lens) |", "|---|---|---|---|"]
    lagk = list(dict.fromkeys(common + spec))
    lags = []
    for k in lagk:
        ls_ = []
        for r in rows:
            hit = np.nonzero(r["seg"] == k)
            if len(hit[0]):
                t = hit[0][np.argmax(r["segv"][hit])]
                ls_.append(PRE - t)
        if ls_:
            lags.append((float(np.median(ls_)), k, len(ls_)))
    for lg, k, c in sorted(lags, reverse=True):
        nm, wr, _ = label(k)
        md.append(f"| {nm} | {lg:.0f} | {c} | {wr} |")
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:12]))


if __name__ == "__main__":
    main()
