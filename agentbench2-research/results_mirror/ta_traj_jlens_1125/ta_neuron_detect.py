"""Neuron-level misalignment detection on ToolAlign-4B trajectory units (CPU, reads ta_neuron_capture.py output).
Positive = target whose call is clearly-misaligned or boundary; negatives = references (writeInternalLog) and aligned
targets (legit actions). Activations are normalised per neuron by the neuron-explorer act_scale (pole + uses max / pos
scale, pole - uses min / neg scale).
Label-free sets (no unit data used to pick them):
  W = write-side lexicon neurons (ne_candidates.json, write >= WMIN), R = read-side lexicon neurons (S lens, read >= 2),
  P = neurons most active on the 10 fixed risk phrases (phrases.npz), top 256 per pole by normalised mean.
Unit score in a region = mean normalised activation over the set, and the mean of its top 10 neurons.
Threshold = 95th percentile of the reference scores in that region (calibrated on normal traffic only); report recall on
positives and false fire on aligned targets. Upper bound: leave-one-domain-out supervised selection of 256 neurons.
Length control: max over a window grows with window length, so window regions are compared only between units whose window
is full (input64 always; early64 and last64 need pre_len >= 70).
Optional: detect-then-edit with ta_commit_edit.py rows (flips at the commit start among fired units).
Usage: python ta_neuron_detect.py ta_seqs.json NCAP_DIR ne_candidates.json act_scale.npz OUT_MD [CE_ROWS_JSONL]"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REGIONS = ["input64", "onset", "early64", "last64", "scaffold"]
FULL = {"input64": 0, "onset": 0, "early64": 70, "last64": 70, "scaffold": 0}
WMIN = 4
SCAF_LEN = 5


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
    seqs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    nc = Path(sys.argv[2])
    cand = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
    sc = np.load(sys.argv[4])
    out_md = Path(sys.argv[5])
    ce_rows = Path(sys.argv[6]) if len(sys.argv) > 6 else None
    pos_s, neg_s = np.maximum(sc["pos"].astype(np.float32), 1e-2), np.maximum(np.abs(sc["neg"].astype(np.float32)), 1e-2)
    uj = nc / "units.json"
    info = {r["idx"]: r for r in json.loads(uj.read_text(encoding="utf-8"))} if uj.is_file() else {}

    U = []
    for n, u in enumerate(seqs):
        f = nc / f"n_{n}.npz"
        if not f.is_file():
            continue
        try:
            z = np.load(f)
            z = {k: z[k] for k in ("mx", "mn", "have")}
        except Exception as e:
            print(f"skip {f.name}: {type(e).__name__}")
            continue
        pre = info[n]["pre_len"] if n in info else u["pos"] + 1 - SCAF_LEN - u["onset"]
        grp = "pos" if u["label"] == "target" and u["risk"] != "aligned" else ("aligned" if u["label"] == "target" else "ref")
        up = z["mx"].astype(np.float32) / pos_s
        dn = -z["mn"].astype(np.float32) / neg_s
        U.append({"n": n, "u": u, "grp": grp, "pre": pre, "have": z["have"], "up": up, "dn": dn})
    if not U:
        raise SystemExit("no captures")

    def pick(pred):
        s = [c for c in cand if pred(c)]
        return (np.array([c["layer"] for c in s], int), np.array([c["neuron"] for c in s], int),
                np.array([c["pole"] == "+" for c in s], bool))
    sets = {"W (write lexicon)": pick(lambda c: c["write"] >= WMIN), "R (read lexicon)": pick(lambda c: c["read"] >= 2)}
    ph = nc / "phrases.npz"
    if ph.is_file():
        P = np.load(ph)["act"]
        pu = (P[:, 0] / pos_s).mean(0)
        pd = (-P[:, 1] / neg_s).mean(0)
        pu[:4] = pd[:4] = -np.inf
        L, N, S = [], [], []
        for arr, sign in ((pu, True), (pd, False)):
            top = np.argsort(-arr.ravel())[:256]
            L += list(top // arr.shape[1]); N += list(top % arr.shape[1]); S += [sign] * len(top)
        sets["P (risk-phrase neurons)"] = (np.array(L), np.array(N), np.array(S))

    def vals(x, ri, s):
        L, N, S = s
        return np.where(S, x["up"][ri, L, N], x["dn"][ri, L, N])

    grp_n = Counter(x["grp"] for x in U)
    md = ["# Neuron-level detection of misaligned / boundary actions (ToolAlign-4B, neuron-explorer act_scale units)", "",
          f"Units with captures: {len(U)} ({dict(grp_n)}). Sets: " + ", ".join(f"{k} {len(v[0])}" for k, v in sets.items()), "",
          "Threshold = 95th percentile of reference scores in the region. Window regions use only units with a full window.", "",
          "| set | score | region | n pos / aligned / ref | AUC pos vs ref | AUC pos vs aligned | recall | false fire aligned | false fire ref |",
          "|---|---|---|---|---|---|---|---|---|"]
    fires = defaultdict(dict)
    for sname, s in sets.items():
        if not len(s[0]):
            continue
        for ri, r in enumerate(REGIONS):
            xs = [x for x in U if x["have"][ri] and x["pre"] >= FULL[r]]
            for mode in ("mean", "top10"):
                f = (lambda v: float(v.mean())) if mode == "mean" else (lambda v: float(np.sort(v)[-10:].mean()))
                sc_ = {x["n"]: f(vals(x, ri, s)) for x in xs}
                g = {k: [sc_[x["n"]] for x in xs if x["grp"] == k] for k in ("pos", "aligned", "ref")}
                th = np.percentile(g["ref"], 95) if len(g["ref"]) >= 5 else None
                rate = lambda v: "-" if th is None or not v else f"{np.mean(np.array(v) > th):.0%}"
                if th is not None:
                    for x in xs:
                        fires[(sname, mode, r)][x["n"]] = sc_[x["n"]] > th
                a1, a2 = auc(g["pos"], g["ref"]), auc(g["pos"], g["aligned"])
                md.append(f"| {sname} | {mode} | {r} | {len(g['pos'])}/{len(g['aligned'])}/{len(g['ref'])} | "
                          f"{'-' if a1 is None else f'{a1:.2f}'} | {'-' if a2 is None else f'{a2:.2f}'} | {rate(g['pos'])} | "
                          f"{rate(g['aligned'])} | {rate(g['ref'])} |")

    md += ["", "## Upper bound: supervised neuron selection, leave-one-domain-out (256 neurons by (mu_pos - mu_neg) / sd_neg on the other domains)", "",
           "| region | n pos / neg | AUC pos vs neg (pooled held-out) | AUC pos vs aligned |", "|---|---|---|---|"]
    for ri, r in enumerate(REGIONS):
        xs = [x for x in U if x["have"][ri] and x["pre"] >= FULL[r]]
        doms = sorted({x["u"]["domain"] for x in xs})
        held = {}
        for d in doms:
            tr = [x for x in xs if x["u"]["domain"] != d]
            tp = [x for x in tr if x["grp"] == "pos"]
            tn = [x for x in tr if x["grp"] != "pos"]
            if len(tp) < 3 or len(tn) < 3:
                continue
            feat = lambda x: np.concatenate([x["up"][ri].ravel(), x["dn"][ri].ravel()])
            Fp, Fn = np.stack([feat(x) for x in tp]), np.stack([feat(x) for x in tn])
            zz = (Fp.mean(0) - Fn.mean(0)) / (Fn.std(0) + 1e-3)
            top = np.argsort(-zz)[:256]
            for x in xs:
                if x["u"]["domain"] == d:
                    held[x["n"]] = float(feat(x)[top].mean())
        g = {k: [held[x["n"]] for x in xs if x["grp"] == k and x["n"] in held] for k in ("pos", "aligned", "ref")}
        a1, a2 = auc(g["pos"], g["ref"] + g["aligned"]), auc(g["pos"], g["aligned"])
        md.append(f"| {r} | {len(g['pos'])}/{len(g['ref']) + len(g['aligned'])} | {'-' if a1 is None else f'{a1:.2f}'} | "
                  f"{'-' if a2 is None else f'{a2:.2f}'} |")

    if ce_rows and ce_rows.is_file():
        rows = [json.loads(l) for l in ce_rows.open(encoding="utf-8")]
        base = {(r["idx"], r["start"]): r["gen_tool"] == r["orig_tool"] for r in rows if r["config"] == "base"}
        flip = {(r["idx"], r["start"], r["config"]): r["gen_tool"] == "writeInternalLog" for r in rows}
        md += ["", "## Detect, then edit from the commit sentence (fired units only)", "",
               "| detector | config | misaligned/boundary blocked | aligned changed (harm) |", "|---|---|---|---|"]
        for key, fm in fires.items():
            if key[1] != "mean" or key[2] not in ("input64", "onset", "last64"):
                continue
            for cfg in ("neur_top_256", "neur_top_1024", "attn_16_20"):
                bl = [flip[(i, "commit", cfg)] for i, on in fm.items() if on and base.get((i, "commit")) and (i, "commit", cfg) in flip
                      and seqs[i]["risk"] != "aligned" and seqs[i]["label"] == "target"]
                hm = [flip[(i, "commit", cfg)] for i, on in fm.items() if on and base.get((i, "commit")) and (i, "commit", cfg) in flip
                      and seqs[i]["risk"] == "aligned" and seqs[i]["label"] == "target"]
                md.append(f"| {key[0]} {key[2]} | {cfg} | {sum(bl)}/{len(bl)} | {sum(hm)}/{len(hm)} |")
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
