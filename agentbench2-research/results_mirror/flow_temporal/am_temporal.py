"""Temporal neuron-flow patterns in agentic-misalignment responses (per-token top-16 per layer, explorer act_scale units).
A key (layer, neuron, sign) is "on" at a token when it is in that layer's top-16 with |score| >= 1.
Per response (model's own text, onset .. event; event = first <tool_use> block, or the first recipient token with --event rcpt):
  rise     = on-rate in the PRE=64 tokens before the event - on-rate in the earlier response tokens (same response)
  state    = on-rate over onset .. event
  slope    = on-rate in the last fifth - on-rate in the first fifth of onset .. event (progression while tokens pass)
Contrast: harmful vs harmless (repo classifier), within the given scenarios. Held-out: keys picked on one fold
(sample_id parity) by the harmful - harmless difference, scored on the other fold (mean over the 30 picked keys), AUC.
Lexical check: for each listed key, the most frequent tokens it fires on (in PRE for rise keys, anywhere before the
event for state / slope keys).
Usage: python am_temporal.py FLOW_DIR CASES_JSON CACHE OUT_MD SCENARIOS(comma) [tool|rcpt]"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer

MODEL = "/workspace/.hf_home/hub/models--Qwen--Qwen3.5-4B/snapshots/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
PRE, MINBASE, MINV, TOPN, PICK, N = 64, 128, 1.0, 12, 30, 9216


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


def main():
    fd, cp, cache, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    scen = set(sys.argv[5].split(","))
    evname = sys.argv[6] if len(sys.argv) > 6 else "tool"
    tok = AutoTokenizer.from_pretrained(MODEL)
    vocab = json.loads((cache / "vocab.json").read_text(encoding="utf-8"))
    vs = lambda t: str(vocab[t]).replace("Ġ", " ").replace("Ċ", "\\n").replace("\n", "\\n").replace("|", "/").strip() or repr(vocab[t])
    ix = {k: dict(np.load(cache / f"{k}_index.npz")) for k in ("steer", "s")}
    cases = [c for c in json.loads(cp.read_text(encoding="utf-8")) if (c["scenario"] in scen or c["condition"] in scen) and c.get("harmful") is not None]
    rows, skipped = [], Counter()
    for c in cases:
        f = fd / f"f_am_{c['condition']}_{c['sample_id']}.npz"
        ev = c["ev"].get(evname)
        if not f.is_file():
            skipped["no flow"] += 1
            continue
        if ev is None:
            skipped[f"no {evname}"] += 1
            continue
        on = c["onset"]
        if ev - on < PRE + MINBASE:
            skipped["short"] += 1
            continue
        z = np.load(f)
        fi, fv = z["flow_idx"][on:ev].astype(np.int64), z["flow_val"][on:ev].astype(np.float32)
        Tn, L, K = fi.shape
        key = np.arange(L)[None, :, None] * 2 * N + fi * 2 + (fv < 0)
        ok = np.abs(fv) >= MINV
        q = Tn // 5
        rows.append({"c": c, "pos": bool(c["harmful"]), "fold": c["fold"], "key": key, "ok": ok, "Tn": Tn, "on": on, "q": q})
    if not rows:
        raise SystemExit("no rows")
    allk = np.unique(np.concatenate([r["key"][r["ok"]] for r in rows]))
    col = {int(k): i for i, k in enumerate(allk)}
    nK = len(allk)

    def rate(r, a, b):
        v = np.zeros(nK, np.float32)
        kk = r["key"][a:b][r["ok"][a:b]]
        if len(kk):
            u, cnt = np.unique(kk, return_counts=True)
            v[np.searchsorted(allk, u)] = cnt / max(1, b - a)
        return v
    PREm = np.stack([rate(r, r["Tn"] - PRE, r["Tn"]) for r in rows])
    BASEm = np.stack([rate(r, 0, r["Tn"] - PRE) for r in rows])
    STm = np.stack([rate(r, 0, r["Tn"]) for r in rows])
    SLm = np.stack([rate(r, r["Tn"] - r["q"], r["Tn"]) - rate(r, 0, r["q"]) for r in rows])
    RISE = PREm - BASEm
    pos = np.array([r["pos"] for r in rows])
    fold = np.array([r["fold"] for r in rows])
    nP, nN = int(pos.sum()), int((~pos).sum())

    def label(k):
        l, rest = divmod(int(k), 2 * N)
        n, neg = divmod(rest, 2)
        pole = "down" if neg else "up"
        return f"L{l}/N{n}{'-' if neg else '+'}", " ".join(vs(t) for t in ix["steer"][pole][l, n, :5]), " ".join(vs(t) for t in ix["s"][pole][l, n, :4])

    sample = rows[::max(1, len(rows) // 40)]

    def fires_on(k, where):
        cnt = Counter()
        for r in (rows if where == "pre" else sample):
            a, b = (r["Tn"] - PRE, r["Tn"]) if where == "pre" else (0, r["Tn"])
            hit = np.unique(np.nonzero((r["key"][a:b] == k) & r["ok"][a:b])[0])
            ids = r["c"]["ids"]
            cnt.update({tok.decode([ids[r["on"] + a + t]]).replace("\n", "\\n").replace("|", "/").strip() or "␣" for t in hit})
        return ", ".join(f"{w}×{c}" for w, c in cnt.most_common(5))

    md = [f"# Neuron-flow patterns while the model writes its response (agentic-misalignment, scenarios {sorted(scen)}, event = {evname})", "",
          f"Responses used: {len(rows)} (harmful {nP}, harmless {nN}); skipped {dict(skipped)}. Response part = onset .. event "
          f"(needs >= {PRE + MINBASE} tokens). 'On' = in the layer's top-16 with |score| >= {MINV}. {nK} keys seen.", ""]

    def table(title, M, order, note, where):
        md.extend([f"## {title}", "", note, "",
                   f"| neuron | harmful (n={nP}) | harmless (n={nN}) | writes (steer lens) | reads (S lens) | fires on (token × responses{'' if where == 'pre' else ', 40-response sample'}) |",
                   "|---|---|---|---|---|---|"])
        for i in order:
            nm, wr, rd = label(allk[i])
            md.append(f"| {nm} | {M[pos, i].mean():+.2f} | {M[~pos, i].mean():+.2f} | {wr} | {rd} | {fires_on(allk[i], where)} |")
        md.append("")

    table("1. Approach pattern: neurons that rise before the action in all responses", RISE,
          np.argsort(-RISE.mean(0))[:TOPN], "Value = mean (on-rate in the 64 tokens before the event - on-rate earlier in the response).", "pre")
    table("2. Persistent state neurons over the response (on-rate)", STm, np.argsort(-STm.mean(0))[:TOPN],
          "Value = mean on-rate from the response start to the event.", "all")
    table("3. Progression: neurons whose on-rate grows from the first to the last fifth of the response", SLm,
          np.argsort(-SLm.mean(0))[:TOPN], "Value = on-rate(last fifth) - on-rate(first fifth).", "all")
    md += ["## 4. Harmful vs harmless, held out by fold", "",
           "Pick the 30 keys with the largest harmful - harmless difference on one fold; score each response of the other fold by "
           "the mean of those keys; AUC harmful vs harmless. Keys picked on both folds are listed under the table.", "",
           "| measure | AUC fold0 -> fold1 | AUC fold1 -> fold0 | keys picked on both folds |", "|---|---|---|---|"]
    both_keys = {}
    for name, M in (("rise before the event", RISE), ("state (on-rate)", STm), ("progression (slope)", SLm)):
        res, picks = [], []
        for tr in (0, 1):
            trm, tem = fold == tr, fold != tr
            if pos[trm].sum() < 3 or (~pos[trm]).sum() < 3 or pos[tem].sum() < 1 or (~pos[tem]).sum() < 1:
                res.append(None)
                picks.append(set())
                continue
            d = M[trm & pos].mean(0) - M[trm & ~pos].mean(0)
            pk = np.argsort(-d)[:PICK]
            picks.append(set(pk.tolist()))
            s = M[tem][:, pk].mean(1)
            res.append(auc(s[pos[tem]], s[~pos[tem]]))
        both = sorted(picks[0] & picks[1], key=lambda i: -(M[pos, i].mean() - M[~pos, i].mean()))
        both_keys[name] = (M, both)
        md.append(f"| {name} | {'-' if res[0] is None else f'{res[0]:.2f}'} | {'-' if res[1] is None else f'{res[1]:.2f}'} | {len(both)} |")
    md.append("")
    for name, (M, both) in both_keys.items():
        if both:
            table(f"4b. Keys picked on both folds: {name}", M, both[:TOPN], "Higher in harmful on both folds independently.",
                  "pre" if name.startswith("rise") else "all")
    md += ["## 5. Cascade before the event (median tokens before the event of each rising key's strongest firing in PRE)", "",
           "| neuron | median tokens before event | responses | writes (steer lens) |", "|---|---|---|---|"]
    lagk = list(dict.fromkeys(np.argsort(-RISE.mean(0))[:TOPN].tolist() + (both_keys["rise before the event"][1][:TOPN])))
    lags = []
    for i in lagk:
        k = allk[i]
        ls_ = []
        for r in rows:
            seg = r["key"][r["Tn"] - PRE:r["Tn"]]
            hit = np.nonzero((seg == k) & r["ok"][r["Tn"] - PRE:r["Tn"]])[0]
            if len(hit):
                ls_.append(PRE - hit.max())
        if ls_:
            lags.append((float(np.median(ls_)), i, len(ls_)))
    for lg, i, c in sorted(lags, reverse=True):
        nm, wr, _ = label(allk[i])
        md.append(f"| {nm} | {lg:.0f} | {c} | {wr} |")
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:6]))


if __name__ == "__main__":
    main()
