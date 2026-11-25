"""M1a task-balanced: each (domain, task) weighs once inside a group (unit values averaged within task first).
Neuron recurrence = share of TASKS whose task-mean neuron DLA puts the neuron in the top-50. CPU only.
Output probe/m1/out/m1a_taskbal.md, m1a_taskbal.json"""
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

OUT = Path("/home/project-b/LJW/tau2-steer/probe/m1/out")
TOPU = 50


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(os.environ["JC_MODEL"])
    units = [u for u in json.loads((OUT / "units.json").read_text(encoding="utf-8")) if (OUT / f"u_{u['k']}.npz").is_file()]
    groups = defaultdict(lambda: defaultdict(list))
    for u in units:
        t = f"{u['domain']}|{u['task']}"
        if u["label"] == "bad":
            for g in (f"bad:{u['kind']}:{u['ptype']}", f"bad:all:{u['ptype']}", "bad:all:all"):
                groups[g][t].append(u)
        else:
            for g in (f"good:{u['ptype']}", "good:all"):
                groups[g][t].append(u)
    cache = {}

    def z(u):
        if u["k"] not in cache:
            d = np.load(OUT / f"u_{u['k']}.npz")
            cache[u["k"]] = {k: d[k].astype(np.float32) for k in ("attn", "mlp", "ndla")}
        return cache[u["k"]]

    res = {}
    for g, bytask in groups.items():
        tm = {}
        for t, us in bytask.items():
            tm[t] = {k: np.mean([z(u)[k] for u in us], axis=0) for k in ("attn", "mlp", "ndla")}
            tm[t]["m"] = float(np.mean([u["m"] for u in us]))
            tm[t]["emb"] = float(np.mean([u["emb_dla"] for u in us]))
        T = len(tm)
        mlp = np.mean([v["mlp"] for v in tm.values()], axis=0)
        attn = np.mean([v["attn"] for v in tm.values()], axis=0)
        nd = np.mean([v["ndla"] for v in tm.values()], axis=0).ravel()
        cnt = np.zeros(nd.size)
        for v in tm.values():
            cnt[np.argpartition(v["ndla"].ravel(), -TOPU)[-TOPU:]] += 1
        tot = float(np.mean([v["m"] for v in tm.values()]))
        late = float(mlp[27:].sum() + attn[27:].sum())
        pairs = defaultdict(int)
        for us in bytask.values():
            for u in us:
                pairs[(u["c_tok"] if isinstance(u.get("c_tok"), str) else tok.decode([u["c"]]),
                       u["g_tok"] if isinstance(u.get("g_tok"), str) else tok.decode([u["g"]]))] += 1
        res[g] = {"n_units": sum(len(v) for v in bytask.values()), "n_tasks": T, "mean_m": tot,
                  "mlp": mlp.round(3).tolist(), "attn": attn.round(3).tolist(), "late_share_L27_31": late / tot if tot else None,
                  "nd": nd, "cnt": cnt / T, "pairs": sorted(pairs.items(), key=lambda x: -x[1])[:5]}
    nn = 9216
    md = ["# M1a task-balanced (each task counts once inside a group)", "",
          "| group | units | tasks | mean m | share of m written in L27-31 | top-3 MLP layers | top-3 attention layers | most common (chosen, alternative) tokens |",
          "|---|---|---|---|---|---|---|---|"]
    order = sorted(res, key=lambda k: (not k.startswith("bad"), k))
    for g in order:
        r = res[g]
        tm_ = np.argsort(-np.array(r["mlp"]))[:3]
        ta_ = np.argsort(-np.array(r["attn"]))[:3]
        pr = "; ".join(f"{a!r}>{b!r} x{n}" for (a, b), n in r["pairs"][:3])
        md.append(f"| {g} | {r['n_units']} | {r['n_tasks']} | {r['mean_m']:.2f} | {r['late_share_L27_31']:.2f} | "
                  + ", ".join(f"L{i} {r['mlp'][i]:.2f}" for i in tm_) + " | " + ", ".join(f"L{i} {r['attn'][i]:.2f}" for i in ta_) + f" | {pr} |")
    md += ["", "## Neurons recurring across tasks (share of the group's tasks in which the neuron is top-50 by task-mean DLA)", ""]
    for g in order:
        if not g.startswith("bad:"):
            continue
        r = res[g]
        pt = g.split(":")[-1]
        gg = res.get(f"good:{pt}") if pt != "all" else res.get("good:all")
        top = np.argsort(-r["cnt"] - 1e-3 * r["nd"])[:12]
        md += [f"### {g} ({r['n_tasks']} tasks, {r['n_units']} units)", "",
               "| layer | neuron | task share top-50 (bad) | mean DLA (bad, task-bal.) | task share top-50 (good) | mean DLA (good) |", "|---|---|---|---|---|---|"]
        for i in top:
            l, n = divmod(int(i), nn)
            md.append(f"| L{l} | {n} | {r['cnt'][i]:.2f} | {r['nd'][i]:.3f} | {gg['cnt'][i]:.2f} | {gg['nd'][i]:.3f} |")
        spec = [i for i in np.argsort(-r["cnt"]) if r["cnt"][i] >= 0.5 and gg["cnt"][i] <= 0.1]
        md += ["", f"- neurons in top-50 for >= 50 % of bad tasks but <= 10 % of good tasks: {len(spec)}"
               + (": " + ", ".join(f"L{int(i) // nn}/{int(i) % nn}" for i in spec[:10]) if spec else ""), ""]
    for r in res.values():
        r.pop("nd")
        r["cnt_top"] = None
        r.pop("cnt")
    (OUT / "m1a_taskbal.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (OUT / "m1a_taskbal.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
