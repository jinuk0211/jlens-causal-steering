"""M1b (PLAN.md "M1", pre-registered): causal test of the neurons M1a points to. GPU 2 only, forward-only.
Per failure group with >= 8 bad units: 2 folds by md5(task) % 2. Select the top-K neurons by mean grad x (act - mu_good) over
the fold-A bad units (mu_good = mean activation of good units with the same position type); mean-ablate them at the unit's
position on fold-B units (bad and good of that position type); K in {16, 64, 256}; control = K random neurons drawn from the
same layers. Bad flip = m' < 0 (the gold token wins); good kept = m' > 0 (the chosen token stays ahead of its runner-up).
Output probe/m1/out/m1b.json, m1b.md"""
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

R = Path("/home/project-b/LJW/tau2-steer")
sys.path.insert(0, str(R / "probe/topk"))
import build_topk as bt

OUT = R / "probe/m1/out"
KS = (16, 64, 256)
CHUNK = 4096
MIN_BAD = 8


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def fold(task_key):
    return int(hashlib.md5(task_key.encode()).hexdigest(), 16) % 2


def main():
    uuid = str(torch.cuda.get_device_properties(0).uuid)
    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID" or "4c593ff4" not in uuid:
        log(f"wrong GPU {uuid}; exiting")
        return 2
    os.chdir(R / "tau2-bench")
    units = [u for u in json.loads((OUT / "units.json").read_text(encoding="utf-8")) if (OUT / f"u_{u['k']}.npz").is_file()]
    by_group = defaultdict(list)
    for u in units:
        if u["label"] == "bad":
            by_group[f"{u['kind']}:{u['ptype']}"].append(u)
            by_group[f"all:{u['ptype']}"].append(u)
    groups = {g: us for g, us in by_group.items() if len(us) >= MIN_BAD}
    goods = defaultdict(list)
    for u in units:
        if u["label"] == "good":
            goods[u["ptype"]].append(u)
    acts = {}

    def act(u):
        if u["k"] not in acts:
            z = np.load(OUT / f"u_{u['k']}.npz")
            acts[u["k"]] = (z["act"].astype(np.float32), z["grad"].astype(np.float32))
        return acts[u["k"]]

    mu = {pt: np.mean([act(u)[0] for u in us], axis=0) for pt, us in goods.items()}
    nl, nn = next(iter(mu.values())).shape
    rng = np.random.default_rng(0)
    plan = []
    for g, us in groups.items():
        pt = g.split(":")[1]
        if pt not in mu:
            continue
        for f in (0, 1):
            sel_units = [u for u in us if fold(f"{u['domain']}|{u['task']}") == f]
            test_bad = [u for u in us if fold(f"{u['domain']}|{u['task']}") != f]
            test_good = [u for u in goods[pt] if fold(f"{u['domain']}|{u['task']}") != f]
            if not sel_units or not test_bad:
                continue
            score = np.mean([act(u)[1] * (act(u)[0] - mu[pt]) for u in sel_units], axis=0).ravel()
            order = np.argsort(-score)
            for K in KS:
                top = order[:K]
                layers = top // nn
                rand = np.array([int(l) * nn + int(rng.integers(nn)) for l in layers])
                for tag, idx in (("top", top), ("random", rand)):
                    plan.append({"group": g, "ptype": pt, "fold": f, "K": K, "set": tag, "idx": idx.tolist(),
                                 "bad": [u["k"] for u in test_bad], "good": [u["k"] for u in test_good]})
    log(f"groups {sorted(groups)}; {len(plan)} ablation sets")
    need = sorted({k for p in plan for k in p["bad"] + p["good"]})
    byk = {u["k"]: u for u in units}
    want = {(byk[k]["cond"], byk[k]["sim"], byk[k]["turn"]) for k in need}
    seqs = {}
    for domain in ("airline", "retail", "telecom"):
        conds = sorted({byk[k]["cond"] for k in need if byk[k]["domain"] == domain})
        if not conds:
            continue
        for domain_, cond, task, sim, tel in bt.episodes(Path("data/simulations/pilot"), Path("data/jlens-telemetry/pilot"), [domain], conds):
            for line in tel.open(encoding="utf-8"):
                rec = json.loads(line)
                key = (cond, sim["id"], int(rec["turn_index"]))
                if key in want:
                    seqs[key] = (rec["input_ids"], rec["generated_ids"])
    tok, model = bt.load_model(os.environ["JC_MODEL"], "cuda")
    blocks = model.model.layers
    state = {"abl": None}

    def pre_down(i):
        def f(module, args):
            if state["abl"] is not None and i in state["abl"]:
                x = args[0].clone()
                idx, val = state["abl"][i]
                x[0, -1, idx] = val
                return (x,)
        return f

    for i, b in enumerate(blocks):
        b.mlp.down_proj.register_forward_pre_hook(pre_down(i))
    results = defaultdict(dict)
    prefix_cache = {}

    def run(k, abl):
        u = byk[k]
        inp, gen = seqs[(u["cond"], u["sim"], u["turn"])]
        seq = list(inp) + list(gen[:u["d"]])
        state["abl"] = None
        with torch.no_grad():
            if k not in prefix_cache:
                cache = None
                for s in range(0, len(seq) - 1, CHUNK):
                    ids = torch.tensor([seq[s:min(s + CHUNK, len(seq) - 1)]], device="cuda")
                    cache = model.model(input_ids=ids, past_key_values=cache, use_cache=True).past_key_values
                prefix_cache.clear()
                prefix_cache[k] = cache
            import copy
            cache = copy.deepcopy(prefix_cache[k])
            state["abl"] = abl
            out = model.model(input_ids=torch.tensor([[seq[-1]]], device="cuda"), past_key_values=cache, use_cache=True)
            state["abl"] = None
            logits = model.lm_head(out.last_hidden_state[0, -1]).float()
        return float(logits[u["c"]] - logits[u["g"]])

    def abl_of(p):
        idx = np.array(p["idx"])
        d = defaultdict(list)
        for x in idx:
            d[int(x) // nn].append(int(x) % nn)
        pt = p["ptype"]
        return {l: (torch.tensor(ns, device="cuda"), torch.tensor(mu[pt][l, ns], device="cuda", dtype=torch.bfloat16)) for l, ns in d.items()}

    by_unit = defaultdict(list)
    for pi, p in enumerate(plan):
        for k in p["bad"] + p["good"]:
            by_unit[k].append(pi)
    t0 = time.time()
    base = {}
    for n, (k, pis) in enumerate(sorted(by_unit.items())):
        base[k] = run(k, None)
        for pi in pis:
            results[pi][k] = run(k, abl_of(plan[pi]))
        if n % 20 == 0:
            log(f"units {n}/{len(by_unit)}, {time.time() - t0:.0f}s")
    drift = [abs(base[k] - byk[k]["m"]) for k in base]
    log(f"baseline check: mean |m_base - m_extract| = {np.mean(drift):.3f}, max {np.max(drift):.3f}")
    rows = []
    for pi, p in enumerate(plan):
        r = results[pi]
        fb = np.mean([r[k] < 0 for k in p["bad"]]) if p["bad"] else None
        kg = np.mean([r[k] > 0 for k in p["good"]]) if p["good"] else None
        dm = np.mean([r[k] - base[k] for k in p["bad"]]) if p["bad"] else None
        rows.append({k: p[k] for k in ("group", "ptype", "fold", "K", "set")} | {
            "n_bad": len(p["bad"]), "n_good": len(p["good"]), "bad_flip": fb, "good_kept": kg, "bad_dm": dm,
            "base_bad_flip": float(np.mean([base[k] < 0 for k in p["bad"]])),
            "layers": sorted({int(x) // nn for x in p["idx"]})})
    agg = defaultdict(lambda: defaultdict(list))
    for r in rows:
        agg[(r["group"], r["K"])][r["set"]].append(r)
    md = ["# M1b: mean-ablating the attributed neurons (selected out of fold) vs random neurons from the same layers", "",
          "| group | K | bad flip (top) | bad flip (random) | good kept (top) | good kept (random) | mean dm bad (top) | layers (top) | localized? |",
          "|---|---|---|---|---|---|---|---|---|"]
    verdict = {}
    for (g, K), d in sorted(agg.items()):
        def w(rs, key):
            num = sum((r[key] or 0) * (r["n_bad"] if key != "good_kept" else r["n_good"]) for r in rs)
            den = sum((r["n_bad"] if key != "good_kept" else r["n_good"]) for r in rs)
            return num / den if den else None
        tb, rb = w(d["top"], "bad_flip"), w(d["random"], "bad_flip")
        tg, rg = w(d["top"], "good_kept"), w(d["random"], "good_kept")
        tdm = np.mean([r["bad_dm"] for r in d["top"]])
        loc = tb is not None and tb >= 0.30 and (rb or 0) <= 0.05 and (tg or 0) >= 0.90
        verdict.setdefault(g, False)
        verdict[g] = verdict[g] or loc
        lay = sorted({l for r in d["top"] for l in r["layers"]})
        md.append(f"| {g} | {K} | {tb:.2f} | {rb:.2f} | {tg if tg is None else round(tg, 2)} | {rg if rg is None else round(rg, 2)} | {tdm:.2f} | {lay[:12]} | {'YES' if loc else 'no'} |")
    md += ["", f"- baseline check: mean |m_base - m_extract| = {np.mean(drift):.3f}", "", "## Verdict (pre-registered: flip >= 30 %, random <= 5 %, good kept >= 90 % at some K)", ""]
    md += [f"- {g}: {'LOCALIZED' if v else 'not localized to a sparse neuron set'}" for g, v in sorted(verdict.items())]
    (OUT / "m1b.json").write_text(json.dumps({"rows": rows, "verdict": verdict}, indent=1, default=float), encoding="utf-8")
    (OUT / "m1b.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log("M1B_DONE")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
