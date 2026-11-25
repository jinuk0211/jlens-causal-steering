"""Analyses B-F of the ToolAlign-4B procedure on ab_jlens output, plus the J-lens AUC profile (PLAN "Boundary rule" 4,
reported next to the band, never used to pick it). CPU only. Clusters for CIs and leave-one-out: unit["group"]
(AgentDojo: suite|user_task; agentic-misalignment: condition). The same candidate tokens are used for both classes.
B: words in the onset top-30 for >= 9/16 of target groups and <= 3/16 of reference groups, held-out-group presence.
C: decision-position margin lp(T) - max lp(A) by layer, target - reference, group-clustered bootstrap CI.
D: lock-in layer of the chosen candidate at the decision position, by class.
E: onset lp('<tool_call>') (dojo) or lp('<') (am) by layer, target - reference.
F: top words at recipient / argument positions by class.
AUC: per layer AUC of the C margin, targets vs references, CALIBRATION fold; onset layer = first layer with AUC >= 0.75
that stays >= 0.75.
Usage: python ab_analyze.py PTS_DIR OUT_DIR [UNITS_JSON]  (UNITS_JSON overrides label, fold and group by uid)"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import ab_core as C

RNG = np.random.default_rng(0)


def boot(per_group, n=2000):
    gs = [g for g in per_group if per_group[g]]
    if len(gs) < 2:
        return None
    st = []
    for _ in range(n):
        pick = RNG.choice(len(gs), len(gs), replace=True)
        st.append(np.mean([v for i in pick for v in per_group[gs[i]]], axis=0))
    return np.percentile(st, [2.5, 97.5], axis=0)


def auc(pos, neg):
    pos, neg = np.asarray(pos), np.asarray(neg)
    if not len(pos) or not len(neg):
        return None
    r = np.argsort(np.argsort(np.concatenate([pos, neg]))) + 1
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def diff_by_group(rows):
    """rows: (group, label, vec). Per group with both classes: mean(target) - mean(reference)."""
    by = defaultdict(lambda: {"target": [], "reference": []})
    for g, lab, v in rows:
        by[g][lab].append(v)
    out = {}
    for g, d in by.items():
        if d["target"] and d["reference"]:
            out[g] = [np.mean(d["target"], 0) - np.mean(d["reference"], 0)]
    return out


def main():
    from transformers import AutoTokenizer
    pts, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    metas = json.loads((pts / "steps.json").read_text(encoding="utf-8"))
    if len(sys.argv) > 3:
        lab = {u["uid"]: u for u in json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))}
        metas = [{**m, "label": lab[m["uid"]]["label"], "fold": lab[m["uid"]]["fold"], "group": lab[m["uid"]]["group"]}
                 for m in metas if m["uid"] in lab and lab[m["uid"]]["label"] in ("target", "reference")]
    bench = metas[0]["bench"]
    L = [str(x) for x in metas[0]["layers"]]
    nl = len(L)
    data = {m["sid"]: dict(np.load(pts / f"s_{m['sid']}.npz")) for m in metas}
    res, md = {}, [f"# J-lens analyses B-F, {bench} (Qwen3.5-4B)", "",
                   f"{len(metas)} units: " + ", ".join(f"{k} {v}" for k, v in Counter(m['label'] for m in metas).items()) +
                   f"; {len({m['group'] for m in metas})} groups; layers {L[0]}..{L[-2]} + final.", ""]

    def row_txt(v, ci=None):
        sel = list(range(0, nl - 1, 3)) + [nl - 1]
        s = "| mean | " + " | ".join(f"{v[i]:+.2f}" for i in sel) + " |"
        if ci is not None:
            s += "\n| 95% CI | " + " | ".join(f"[{ci[0][i]:+.2f},{ci[1][i]:+.2f}]" for i in sel) + " |"
        return "| layer | " + " | ".join(L[i] for i in sel) + " |\n|---|" + "---|" * len(sel) + "\n" + s

    dec, why = {}, Counter()
    for m in metas:
        d, r = C.decision(m)
        why[(m["label"], r if d else "skip:" + r)] += 1
        if d:
            cl = data[m["sid"]]["cand_lp"][d["pi"]].astype(np.float32)
            d["margin"] = cl[:, d["T"]].max(1) - cl[:, d["A"]].max(1)
            dec[m["sid"]] = d
    md += ["## Decision positions (one structural rule for both classes)", "",
           "; ".join(f"{k[0]} {k[1]}: {v}" for k, v in sorted(why.items())), ""]

    rows = [(m["group"], m["label"], dec[m["sid"]]["margin"]) for m in metas if m["sid"] in dec]
    per = diff_by_group(rows)
    if per:
        v = np.mean([x for xs in per.values() for x in xs], 0)
        ci = boot(per)
        sig = [L[i] for i in range(nl) if ci is not None and (ci[0][i] > 0 or ci[1][i] < 0)]
        res["C"] = {"groups": len(per), "mean": v.round(3).tolist(), "ci": None if ci is None else ci.round(3).tolist(), "sig": sig}
        md += ["## C. Decision-position margin lp(T) - max lp(A), target - reference within group", "", row_txt(v, ci), "",
               f"- {len(per)} groups with both classes; CI excludes 0 at layers {sig}", ""]
    for kind in sorted({d["kind"] for d in dec.values()}):
        pk = diff_by_group([(m["group"], m["label"], dec[m["sid"]]["margin"]) for m in metas if m["sid"] in dec and dec[m["sid"]]["kind"] == kind])
        if pk:
            v = np.mean([x for xs in pk.values() for x in xs], 0)
            md += [f"- kind {kind}: {len(pk)} groups, final {v[-1]:+.2f}, L16 {v[L.index('16')]:+.2f}, L24 {v[L.index('24')]:+.2f}"]
    md.append("")

    cal = [m for m in metas if m["sid"] in dec and m["fold"] == 0]
    aucs = [auc([dec[m["sid"]]["margin"][i] for m in cal if m["label"] == "target"],
                [dec[m["sid"]]["margin"][i] for m in cal if m["label"] == "reference"]) for i in range(nl)]
    onset = next((L[i] for i in range(nl - 1) if aucs[i] is not None and all(a is not None and a >= 0.75 for a in aucs[i:nl - 1])), None)
    res["AUC"] = {"calibration_units": len(cal), "auc": [None if a is None else round(a, 3) for a in aucs], "onset_layer": onset}
    md += ["## AUC profile (CALIBRATION fold, PLAN boundary rule 4; reported, not used to pick the band)", "",
           "| layer | " + " | ".join(L) + " |", "|---|" + "---|" * nl,
           "| AUC | " + " | ".join("-" if a is None else f"{a:.2f}" for a in aucs) + " |", "",
           f"- onset layer (first layer with AUC >= 0.75 that stays there): {onset}", ""]

    md += ["## D. Lock-in layer of the chosen candidate at the decision position", "",
           "| class | kind | n | lock-in median [IQR] | never locked |", "|---|---|---|---|---|"]
    lk = defaultdict(list)
    for m in metas:
        d = dec.get(m["sid"])
        if not d:
            continue
        p = m["positions"][d["pi"]]
        toks = [c[1] for c in m["cands"]]
        pool = d["T"] + d["A"]
        if p["next_id"] not in [toks[i] for i in pool]:
            continue
        cl = data[m["sid"]]["cand_lp"][d["pi"]].astype(np.float32)[:, pool]
        ch = [toks[i] for i in pool].index(p["next_id"])
        r1 = cl.argmax(1) == ch
        lk[(m["label"], d["kind"])].append(next((i for i in range(nl) if r1[i:].all()), None))
    res["D"] = {}
    for k, v in sorted(lk.items()):
        got = [x for x in v if x is not None]
        q = np.percentile(got, [25, 50, 75]).round(1).tolist() if got else None
        res["D"][f"{k[0]}:{k[1]}"] = {"n": len(v), "q": q, "never": len(v) - len(got)}
        md.append(f"| {k[0]} | {k[1]} | {len(v)} | {q} | {len(v) - len(got)} |")
    md.append("")

    et = "<tool_call>" if bench == "dojo" else "<"
    rows = []
    for m in metas:
        names = [c[0] for c in m["cands"]]
        if et in names:
            rows.append((m["group"], m["label"], data[m["sid"]]["cand_lp"][0, :, names.index(et)].astype(np.float32)))
    per = diff_by_group(rows)
    if per:
        v = np.mean([x for xs in per.values() for x in xs], 0)
        ci = boot(per)
        res["E"] = {"groups": len(per), "mean": v.round(3).tolist(), "ci": None if ci is None else ci.round(3).tolist()}
        md += [f"## E. Onset lp({et!r}), target - reference within group", "", row_txt(v, ci), ""]

    gl = defaultdict(set)
    for m in metas:
        gl[m["label"]].add(m["group"])
    nt, nr = len(gl["target"]), len(gl["reference"])
    width = data[metas[0]["sid"]]["top_ids"].shape[-1]
    for K in sorted({30, width} if width >= 30 else {width}):
      pres = {"target": defaultdict(lambda: defaultdict(set)), "reference": defaultdict(lambda: defaultdict(set))}
      for m in metas:
        ti = data[m["sid"]]["top_ids"][0][:, :K]
        for l in range(nl):
            for t in set(ti[l].tolist()):
                pres[m["label"]][l][t].add(m["group"])
      md += [f"## B (top-{K}). Onset words: in >= 9/16 of target groups ({nt}) and <= 3/16 of reference groups ({nr}); held-out group presence", ""]
      res[f"B_top{K}"] = {}
      for l in range(nl):
          words = [t for t, gs in pres["target"][l].items() if len(gs) >= 9 / 16 * nt and len(pres["reference"][l].get(t, ())) <= 3 / 16 * nr]
          if not words:
              continue
          hw, hr = [], []
          for hg in sorted(gl["target"] | gl["reference"]):
              ws = {t for t, gs in pres["target"][l].items() if len(gs - {hg}) >= 9 / 16 * (nt - (hg in gl["target"]))
                    and len(pres["reference"][l].get(t, set()) - {hg}) <= 3 / 16 * (nr - (hg in gl["reference"]))}
              if not ws:
                  continue
              for m in metas:
                  if m["group"] == hg:
                      (hw if m["label"] == "target" else hr).append(bool(ws & set(data[m["sid"]]["top_ids"][0][l][:K].tolist())))
          txt = [tok.decode([t]) for t in sorted(words, key=lambda t: -len(pres["target"][l][t]))[:12]]
          res[f"B_top{K}"][L[l]] = {"words": txt, "held_out_target": float(np.mean(hw)) if hw else None, "held_out_reference": float(np.mean(hr)) if hr else None}
          rb = res[f"B_top{K}"][L[l]]
          md.append(f"- L{L[l]}: {txt} | held-out presence: target {rb['held_out_target']}, reference {rb['held_out_reference']}")
      md.append("")

    md += ["## F. Top words at recipient / argument positions (first 10 of top-30, counts)", ""]
    fw = defaultdict(lambda: defaultdict(Counter))
    nf = Counter()
    for m in metas:
        for pi, p in enumerate(m["positions"]):
            if not p["tag"].startswith(("to_", "arg_")):
                continue
            g = (m["label"], p["tag"] if bench == "dojo" else "to")
            nf[g] += 1
            ti = data[m["sid"]]["top_ids"][pi]
            for l in (8, 12, 16, 20, 24, 28, nl - 1):
                for t in ti[l][:10].tolist():
                    fw[g][l][t] += 1
    res["F"] = {}
    for g in sorted(fw, key=lambda g: -nf[g])[:12]:
        res["F"][f"{g[0]}:{g[1]}"] = {L[l]: [(tok.decode([t]), c) for t, c in fw[g][l].most_common(6)] for l in fw[g]}
        md.append(f"- {g[0]} {g[1]} (n={nf[g]}): " + "; ".join(f"L{L[l]} " + ", ".join(repr(tok.decode([t])) for t, _ in fw[g][l].most_common(5)) for l in sorted(fw[g])))
    (out / "report.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
