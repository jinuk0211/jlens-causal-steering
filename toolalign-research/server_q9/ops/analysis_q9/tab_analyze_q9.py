"""Pre-registered analyses B-F (work/toolalign-research/PLAN.md) on ops/analysis/jlens_points. CPU only.
Output ops/analysis/report/{report.md, report.json}"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench")
sys.path.insert(0, str(ROOT / "jlens_experiment"))
from toolalign_common import load_tool_taxonomy

PTS = ROOT / "ops/analysis_q9/jlens_points"
OUT = ROOT / "ops/analysis_q9/report"
RNG = np.random.default_rng(0)


def boot_ci(per_domain_vals, n=2000):
    doms = list(per_domain_vals)
    if len(doms) < 2:
        return None
    stats = []
    for _ in range(n):
        pick = RNG.choice(len(doms), len(doms), replace=True)
        vals = [v for i in pick for v in per_domain_vals[doms[i]]]
        stats.append(np.mean(vals, axis=0))
    return np.percentile(stats, [2.5, 97.5], axis=0)


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-9B", revision="c202236235762e1c871ad0ccb60c8ee5ba337b9a")
    OUT.mkdir(parents=True, exist_ok=True)
    tax = load_tool_taxonomy(ROOT)
    risk = {d: {s.name: s.risk_level for s in specs} for d, specs in tax.items()}
    metas = json.loads((PTS / "steps.json").read_text(encoding="utf-8"))
    nl = len(metas[0]["layers"])
    lay_names = [str(x) for x in metas[0]["layers"]]
    data = {}
    for m in metas:
        z = np.load(PTS / f"s_{m['sid']}.npz")
        data[m["sid"]] = {k: z[k] for k in ("cand_lp", "top_ids", "top_lp")}
    md = ["# ToolAlignBench × J-lens: pre-registered analyses B-F (Qwen3.5-9B, J++ lens, greedy)", "",
          f"{len(metas)} steps, layers {lay_names[0]}..{lay_names[-2]} + final. Same candidate tokens in every comparison.", ""]
    res = {}

    def cidx(m, name):
        for i, names in enumerate(m["cand_first_names"]):
            if name in names:
                return i
        return None

    def mis_idx(m):
        return [i for i, names in enumerate(m["cand_first_names"]) if any(risk[m["domain"]].get(n) == "clearly-misaligned" for n in names)
                and not any(risk[m["domain"]].get(n) == "aligned" or n == "email" for n in names)]

    first_name = {}
    for m in sorted(metas, key=lambda x: (x["trace"], x["doc_index"], x["step"])):
        k = (m["domain"], m["type"], m["condition"], m["doc_index"])
        if k in first_name:
            continue
        for pi, p in enumerate(m["positions"]):
            if p["tag"].startswith("name_"):
                first_name[k] = (m, pi)
                break

    def deltas(m, pi):
        cl = data[m["sid"]]["cand_lp"][pi].astype(np.float32)
        w, e = cidx(m, "writeInternalLog"), cidx(m, "email")
        mi = mis_idx(m)
        de = cl[:, e] - cl[:, w] if e is not None and w is not None else None
        dm = cl[:, mi].max(axis=1) - cl[:, w] if mi and w is not None else None
        return de, dm

    md += ["## C. Action pressure at the first tool-name position of each document (paired wrongdoing − safe)", ""]
    pairs = defaultdict(lambda: defaultdict(list))
    for (d, ty, cond, doc), (m, pi) in first_name.items():
        if ty != "wrongdoing":
            continue
        s = first_name.get((d, "safe", cond, doc))
        if not s:
            continue
        dw, mw = deltas(m, pi)
        ds, ms = deltas(*s)
        if dw is not None and ds is not None:
            pairs["email"][d].append(dw - ds)
        if mw is not None and ms is not None:
            pairs["misaligned"][d].append(mw - ms)
    for key in ("email", "misaligned"):
        per = pairs[key]
        allv = np.array([v for vs in per.values() for v in vs])
        if not len(allv):
            md.append(f"- Δ_{key}: no pairs")
            continue
        ci = boot_ci(per)
        mean = allv.mean(axis=0)
        sig = [lay_names[i] for i in range(nl) if ci is not None and (ci[0][i] > 0 or ci[1][i] < 0)]
        res[f"C_{key}"] = {"n_pairs": len(allv), "n_domains": len(per), "mean": mean.round(3).tolist(),
                           "ci": None if ci is None else ci.round(3).tolist(), "sig_layers": sig}
        md += [f"### Δ_{key} = lp({'email' if key == 'email' else 'best clearly-misaligned tool'}) − lp(writeInternalLog); "
               f"wrongdoing − safe, {len(allv)} pairs from {len(per)} domains", "",
               "| layer | " + " | ".join(lay_names[i] for i in range(0, nl, 3)) + f" | {lay_names[-1]} |",
               "|---|" + "---|" * (len(range(0, nl, 3)) + 1),
               "| mean | " + " | ".join(f"{mean[i]:+.2f}" for i in range(0, nl, 3)) + f" | {mean[-1]:+.2f} |"]
        if ci is not None:
            md.append("| 95% CI | " + " | ".join(f"[{ci[0][i]:+.2f},{ci[1][i]:+.2f}]" for i in range(0, nl, 3)) + f" | [{ci[0][-1]:+.2f},{ci[1][-1]:+.2f}] |")
        md += ["", f"- layers whose domain-clustered CI excludes 0: {sig}", ""]

    md += ["## C/D. Lock-in layer and profile by final choice (all tool-name positions)", ""]
    groups = defaultdict(list)
    for m in metas:
        ni = 0
        for pi, p in enumerate(m["positions"]):
            if not p["tag"].startswith("name_"):
                continue
            call = m["calls"][ni] if ni < len(m["calls"]) else None
            ni += 1
            if call is None:
                continue
            ch = cidx(m, call["name"])
            if ch is None:
                continue
            cl = data[m["sid"]]["cand_lp"][pi].astype(np.float32)[:, :-1]
            rank1 = cl.argmax(axis=1) == ch
            lock = next((i for i in range(nl) if rank1[i:].all()), None)
            de, dm = deltas(m, pi)
            g = f"{m['type']}:{call['risk']}:{call['category']}"
            groups[g].append({"domain": m["domain"], "lock": lock, "de": de, "dm": dm, "tool": call["name"]})
    md += ["| group (type:risk:category) | calls | domains | lock-in layer median [IQR] | Δ_email L12 / L20 / L26 / final | Δ_mis L12 / L20 / L26 / final |",
           "|---|---|---|---|---|---|"]
    li = {n: i for i, n in enumerate(lay_names)}
    for g, rows in sorted(groups.items()):
        locks = [r["lock"] for r in rows if r["lock"] is not None]
        q = np.percentile(locks, [25, 50, 75]).round(1).tolist() if locks else None
        de = np.array([r["de"] for r in rows if r["de"] is not None])
        dm = np.array([r["dm"] for r in rows if r["dm"] is not None])
        f = lambda a: " / ".join(f"{a[:, li[x]].mean():+.2f}" for x in ("12", "20", "26", "final")) if len(a) else "-"
        res[f"D_{g}"] = {"n": len(rows), "domains": len({r['domain'] for r in rows}), "lock_q": q,
                         "de_mean": de.mean(axis=0).round(3).tolist() if len(de) else None,
                         "dm_mean": dm.mean(axis=0).round(3).tolist() if len(dm) else None,
                         "tools": Counter(r["tool"] for r in rows).most_common(5)}
        md.append(f"| {g} | {len(rows)} | {len({r['domain'] for r in rows})} | {q} | {f(de)} | {f(dm)} |")
    md += ["", "Lock-in layer = first layer from which the chosen tool's first token ranks first among the domain's tool tokens "
           "and stays first through the final logits.", ""]

    md += ["## E. Onset: lp(<tool_call>) by layer, wrongdoing − safe (paired by domain, doc, condition, step 0)", ""]
    onset = {}
    for m in metas:
        if m["step"] != 0:
            continue
        onset[(m["domain"], m["type"], m["condition"], m["doc_index"])] = m
    per = defaultdict(list)
    for (d, ty, cond, doc), m in onset.items():
        if ty != "wrongdoing" or (d, "safe", cond, doc) not in onset:
            continue
        s = onset[(d, "safe", cond, doc)]
        a = data[m["sid"]]["cand_lp"][0, :, -1].astype(np.float32)
        b = data[s["sid"]]["cand_lp"][0, :, -1].astype(np.float32)
        per[d].append(a - b)
    if per:
        allv = np.array([v for vs in per.values() for v in vs])
        ci = boot_ci(per)
        mean = allv.mean(axis=0)
        res["E"] = {"n_pairs": len(allv), "mean": mean.round(3).tolist(), "ci": None if ci is None else ci.round(3).tolist()}
        md += ["| layer | " + " | ".join(lay_names[i] for i in range(0, nl, 3)) + f" | {lay_names[-1]} |",
               "|---|" + "---|" * (len(range(0, nl, 3)) + 1),
               "| mean | " + " | ".join(f"{mean[i]:+.2f}" for i in range(0, nl, 3)) + f" | {mean[-1]:+.2f} |"]
        if ci is not None:
            md.append("| 95% CI | " + " | ".join(f"[{ci[0][i]:+.2f},{ci[1][i]:+.2f}]" for i in range(0, nl, 3)) + f" | [{ci[0][-1]:+.2f},{ci[1][-1]:+.2f}] |")
        md.append(f"\n- {len(allv)} pairs from {len(per)} domains\n")

    md += ["## B. Words read out at the end of each document (onset, step 0): in top-30 for >= 9/16 domains in wrongdoing, "
           "<= 3/16 in safe; leave-one-domain-out presence", ""]
    pres = {ty: defaultdict(lambda: defaultdict(set)) for ty in ("wrongdoing", "safe")}
    per_unit = []
    for (d, ty, cond, doc), m in onset.items():
        ti = data[m["sid"]]["top_ids"][0]
        per_unit.append((d, ty, ti))
        for l in range(nl):
            for t in set(ti[l].tolist()):
                pres[ty][l][t].add(d)
    doms = sorted({d for d, _, _ in per_unit})
    res["B"] = {}
    for l in range(nl):
        words = [t for t, ds in pres["wrongdoing"][l].items() if len(ds) >= 9 and len(pres["safe"][l].get(t, ())) <= 3]
        if not words:
            continue
        hold_w, hold_s = [], []
        for hd in doms:
            others_w = {t for t, ds in pres["wrongdoing"][l].items() if len(ds - {hd}) >= 9 * 15 / 16 and len(pres["safe"][l].get(t, set()) - {hd}) <= 3}
            if not others_w:
                continue
            for d, ty, ti in per_unit:
                if d != hd:
                    continue
                hit = bool(others_w & set(ti[l].tolist()))
                (hold_w if ty == "wrongdoing" else hold_s).append(hit)
        wtxt = [tok.decode([t]) for t in sorted(words, key=lambda t: -len(pres["wrongdoing"][l][t]))[:12]]
        res["B"][lay_names[l]] = {"words": wtxt, "lodo_wrong": float(np.mean(hold_w)) if hold_w else None,
                                  "lodo_safe": float(np.mean(hold_s)) if hold_s else None}
        md.append(f"- L{lay_names[l]}: {wtxt} | held-out domain presence: wrongdoing "
                  f"{res['B'][lay_names[l]]['lodo_wrong'] if hold_w else '-'}, safe {res['B'][lay_names[l]]['lodo_safe'] if hold_s else '-'}")
    md.append("")

    md += ["## F. Email recipient position: top J-lens words (external vs internal recipients)", ""]
    fw = defaultdict(lambda: defaultdict(Counter))
    nf = Counter()
    for m in metas:
        tos = [p for p in m["positions"] if p["tag"].startswith("to_")]
        emails = [c for c in m["calls"] if c["name"] == "email"]
        for p, c in zip(tos, emails):
            pi = m["positions"].index(p)
            g = c["category"]
            nf[g] += 1
            ti = data[m["sid"]]["top_ids"][pi]
            for l in (10, 16, 20, 24, 28, nl - 1):
                for t in ti[l][:10].tolist():
                    fw[g][l][t] += 1
    for g, byl in fw.items():
        md.append(f"- {g} (n={nf[g]}): " + "; ".join(f"L{lay_names[l]} " + ", ".join(repr(tok.decode([t])) for t, _ in byl[l].most_common(6)) for l in sorted(byl)))
    (OUT / "report.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (OUT / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
