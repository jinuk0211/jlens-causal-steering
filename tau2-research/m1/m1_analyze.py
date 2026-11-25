"""M1a (PLAN.md "M1"): layer profile and recurring neurons per failure group vs matched good units. CPU only.
Input probe/m1/out (m1_extract.py). Output probe/m1/out/m1a.md, m1a.json"""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

OUT = Path("/home/project-b/LJW/tau2-steer/probe/m1/out")
TOPU = 50


def group_of(u):
    return f"bad:{u['kind']}:{u['ptype']}" if u["label"] == "bad" else f"good:{u['ptype']}"


def main():
    units = json.loads((OUT / "units.json").read_text(encoding="utf-8"))
    units = [u for u in units if (OUT / f"u_{u['k']}.npz").is_file()]
    acc = defaultdict(lambda: {"n": 0})
    form = defaultdict(list)
    for u in units:
        z = np.load(OUT / f"u_{u['k']}.npz")
        g = group_of(u)
        for name in (g, f"{u['label']}:{u['ptype']}", f"{u['label']}:all"):
            a = acc[name]
            a["n"] += 1
            for key in ("attn", "mlp"):
                a[key] = a.get(key, 0) + z[key].astype(np.float64)
            nd = z["ndla"].astype(np.float32)
            ga = (z["grad"].astype(np.float32) * z["act"].astype(np.float32))
            a["ndla"] = a.get("ndla", 0) + nd
            a["gxa"] = a.get("gxa", 0) + ga
            top = np.argpartition(nd.ravel(), -TOPU)[-TOPU:]
            cnt = a.get("cnt")
            if cnt is None:
                cnt = np.zeros(nd.size, np.int32)
            cnt[top] += 1
            a["cnt"] = cnt
            a.setdefault("m", []).append(u["m"])
        cum = u["emb_dla"] + np.cumsum(z["attn"].astype(np.float64) + z["mlp"].astype(np.float64))
        pos = cum > 0
        L = next((i for i in range(len(cum)) if pos[i:].all()), None) if u["m"] > 0 else None
        form[g].append(L)
        form[f"{u['label']}:{u['ptype']}"].append(L)
    nl = len(next(iter(acc.values()))["attn"])
    res, md = {}, ["# M1a: where the chosen-vs-alternative logit gap is written (teacher-forced, first divergent token)", ""]
    md += ["DLA = direct logit attribution to m = logit(chosen) - logit(alternative). Bad: alternative = the gold token. "
           "Good: alternative = runner-up token.", ""]
    names = sorted(acc, key=lambda k: (k.split(":")[0] != "bad", k))
    md += ["| group | n | mean m | top-3 layers by mean MLP DLA | top-3 by mean attention DLA | formation layer (median, IQR) |",
           "|---|---|---|---|---|---|"]
    for name in names:
        a = acc[name]
        n = a["n"]
        mlp, attn = a["mlp"] / n, a["attn"] / n
        fl = [x for x in form.get(name, []) if x is not None]
        q = np.percentile(fl, [25, 50, 75]).tolist() if fl else None
        res[name] = {"n": n, "mean_m": float(np.mean(a["m"])), "mlp_dla": mlp.round(3).tolist(), "attn_dla": attn.round(3).tolist(),
                     "formation_q": q}
        t_m = np.argsort(-mlp)[:3]
        t_a = np.argsort(-attn)[:3]
        md.append(f"| {name} | {n} | {np.mean(a['m']):.2f} | " + ", ".join(f"L{i} {mlp[i]:.2f}" for i in t_m) + " | "
                  + ", ".join(f"L{i} {attn[i]:.2f}" for i in t_a) + f" | {q} |")
    md += ["", "## Recurring neurons (per group: mean neuron DLA, share of units where the neuron is in the unit's top-50)", ""]
    for name in names:
        if not name.startswith("bad:") or name.endswith(":all"):
            continue
        a = acc[name]
        n = a["n"]
        nd = (a["ndla"] / n).ravel()
        share = a["cnt"] / n
        gname = "good:" + name.split(":")[-1]
        gnd = (acc[gname]["ndla"] / acc[gname]["n"]).ravel() if gname in acc else None
        gshare = acc[gname]["cnt"] / acc[gname]["n"] if gname in acc else None
        top = np.argsort(-nd)[:15]
        rows = []
        for idx in top:
            layer, neuron = divmod(int(idx), nd.size // nl)
            rows.append({"layer": layer, "neuron": neuron, "mean_ndla": round(float(nd[idx]), 3), "share_top50": round(float(share[idx]), 2),
                         "good_mean_ndla": None if gnd is None else round(float(gnd[idx]), 3),
                         "good_share_top50": None if gshare is None else round(float(gshare[idx]), 2)})
        res[name]["top_neurons"] = rows
        md += [f"### {name} (n={n}; matched good: {gname}, n={acc[gname]['n'] if gname in acc else 0})", "",
               "| layer | neuron | mean DLA (bad) | share top-50 (bad) | mean DLA (good) | share top-50 (good) |", "|---|---|---|---|---|---|"]
        md += [f"| L{r['layer']} | {r['neuron']} | {r['mean_ndla']} | {r['share_top50']} | {r['good_mean_ndla']} | {r['good_share_top50']} |" for r in rows]
        if gnd is not None:
            tb = set(np.argsort(-nd)[:200].tolist())
            tg = set(np.argsort(-gnd)[:200].tolist())
            res[name]["top200_overlap_with_good"] = len(tb & tg)
            md += ["", f"- top-200 neuron overlap with the matched good group: {len(tb & tg)}/200", ""]
    meta = json.loads((OUT / "meta.json").read_text()) if (OUT / "meta.json").is_file() else {}
    md += ["", f"- extraction meta: {meta}"]
    (OUT / "m1a.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (OUT / "m1a.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:40]))


if __name__ == "__main__":
    main()
