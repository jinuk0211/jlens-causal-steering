"""C2T (work/tau2-research/PLAN.md): the ToolAlign CAUSAL-2 intervention on tau2 agent turns (Qwen3.5-4B), GPU 0.
Modes: stats I N | run | report. Output probe/c2t/out/"""
import copy
import hashlib
import json
import os
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

R = Path("/home/project-b/LJW/tau2-steer")
sys.path.insert(0, str(R / "probe/topk"))
import build_topk as bt

M1 = R / "probe/m1/out"
OUT = R / "probe/c2t/out"
CHUNK = 4096
FUNC = re.compile(r"<function=([^>\n]+)>")
VERBAL = re.compile(r"transfer|human agent|representative|live agent", re.I)
FULL = [3, 7, 11, 15, 19, 23, 27, 31]


def log(m):
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def units():
    us = json.loads((M1 / "units.json").read_text(encoding="utf-8"))
    seen, A, B, L, K = set(), [], [], [], []
    for u in us:
        key = (u["cond"], u["sim"], u["turn"], u["call"])
        if key in seen:
            continue
        seen.add(key)
        x = {k: u[k] for k in ("domain", "cond", "task", "sim", "turn", "call", "label", "kind")}
        x["uid"] = "|".join(map(str, key))
        if u["label"] == "bad" and u["kind"] == "unexpected_transfer":
            A.append(dict(x, group="A"))
        elif u["label"] == "bad" and u["kind"] == "unexpected_write":
            B.append(dict(x, group="B"))
        elif u["label"] == "good" and u["call"] == "transfer_to_human_agents":
            L.append(dict(x, group="L"))
        elif u["label"] == "good":
            K.append(dict(x, group="K"))
    refs = K
    rng = random.Random(0)
    byd = defaultdict(list)
    for x in K:
        byd[x["domain"]].append(x)
    ks = []
    for d in sorted(byd):
        ks += rng.sample(byd[d], min(len(byd[d]), {"airline": 14, "retail": 14, "telecom": 12}.get(d, 12)))
    return A, B, L, ks, refs


def load_seqs(us):
    os.chdir(R / "tau2-bench")
    want = {(u["cond"], u["sim"], u["turn"]) for u in us}
    seqs = {}
    for domain in ("airline", "retail", "telecom"):
        conds = sorted({u["cond"] for u in us if u["domain"] == domain})
        if not conds:
            continue
        for domain_, cond, task, sim, tel in bt.episodes(Path("data/simulations/pilot"), Path("data/jlens-telemetry/pilot"), [domain], conds):
            for line in tel.open(encoding="utf-8"):
                rec = json.loads(line)
                key = (cond, sim["id"], int(rec["turn_index"]))
                if key in want:
                    seqs[key] = (list(rec["input_ids"]), list(rec["generated_ids"]))
    return seqs


def load_model():
    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID" or os.environ.get("CUDA_VISIBLE_DEVICES") != "0" or "c27bc2d7" not in str(torch.cuda.get_device_properties(0).uuid):
        raise SystemExit("GPU 0 (c27bc2d7) only")
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = os.environ["JC_MODEL"]
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.bfloat16, attn_implementation="sdpa", low_cpu_mem_usage=True).cuda().eval()
    for p in model.parameters():
        p.requires_grad_(False)
    return tok, model


class Hooked:
    def __init__(self, model):
        self.lm = model.model if hasattr(model.model, "layers") else model.model.language_model
        self.blocks = self.lm.layers
        self.ops, self.cap = {}, None
        for i, b in enumerate(self.blocks):
            (b.linear_attn if hasattr(b, "linear_attn") else b.self_attn).register_forward_hook(self._hook(i))

    def _hook(self, i):
        def f(mod, args, out):
            o = out if torch.is_tensor(out) else out[0]
            if self.cap is not None:
                self.cap[i] = o[0].float().sum(0).cpu()
                self.cap["n"] = o.shape[1]
            fn = self.ops.get(i)
            if fn is not None:
                o = o.clone()
                o[0, -1] = fn(o[0, -1])
                return o if torch.is_tensor(out) else (o,) + tuple(out[1:])
        return f


def mode_stats(wi, wn):
    A, B, L, K, refs = units()
    mine = [u for i, u in enumerate(refs) if i % wn == wi]
    seqs = load_seqs(mine)
    tok, model = load_model()
    H = Hooked(model)
    OUT.mkdir(parents=True, exist_ok=True)
    nl = len(H.blocks)
    res = {}
    t0 = time.time()
    for n, u in enumerate(mine):
        inp, gen = seqs[(u["cond"], u["sim"], u["turn"])]
        pre, span = inp[:-1], [inp[-1]] + gen[:-1]
        with torch.no_grad():
            cache = None
            for s in range(0, len(pre), CHUNK):
                cache = H.lm(input_ids=torch.tensor([pre[s:s + CHUNK]], device="cuda"), past_key_values=cache, use_cache=True).past_key_values
            H.cap = {}
            H.lm(input_ids=torch.tensor([span], device="cuda"), past_key_values=cache, use_cache=True)
            cap, H.cap = H.cap, None
        res[u["uid"]] = (torch.stack([cap[i] for i in range(nl)]) / cap["n"]).half().numpy()
        del cache
        if n % 20 == 0:
            log(f"stats {wi}/{wn}: {n}/{len(mine)} {time.time() - t0:.0f}s")
    np.savez(OUT / f"stats_{wi}.npz", uids=np.array(list(res)), attn=np.stack(list(res.values())))
    log("STATS_DONE")


def mode_run():
    A, B, L, K, refs = units()
    runlist = A + B + L + K
    wid = os.environ["C2_WID"]
    stats = {}
    for p in sorted(OUT.glob("stats_*.npz")):
        z = np.load(p)
        for uid, a in zip(z["uids"].tolist(), z["attn"]):
            stats[uid] = a.astype(np.float32)
    ref_task = {u["uid"]: f"{u['domain']}|{u['task']}" for u in refs}
    seqs = load_seqs(runlist)
    tok, model = load_model()
    H = Hooked(model)
    nl = len(H.blocks)
    eos = {tok.eos_token_id, tok.convert_tokens_to_ids("<|im_end|>")}
    band = list(range(12, 21))
    outside = [l for l in range(nl) if l not in band]
    full_out = [l for l in outside if l in FULL]
    claims = OUT / "claims"
    claims.mkdir(exist_ok=True)
    fh = (OUT / f"rows_{wid}.jsonl").open("a", encoding="utf-8")

    def done_set():
        d = set()
        for p in OUT.glob("rows_*.jsonl"):
            for line in p.open(encoding="utf-8"):
                try:
                    r = json.loads(line)
                    d.add((r["uid"], r["config"]))
                except ValueError:
                    pass
        return d

    def setter(v):
        vt = torch.tensor(v, device="cuda")
        return lambda x: vt.to(x.dtype)

    log(f"worker {wid}: {len(runlist)} units, {len(stats)} reference stats")
    t0 = time.time()
    for n, u in enumerate(runlist):
        task = f"{u['domain']}|{u['task']}"
        ri = [stats[k] for k, t in ref_task.items() if t != task and k in stats]
        mu = np.mean(ri, axis=0)
        cfgs = [("base", {}, "all")]
        for name, layers in (("attn_band_16_20", range(16, 21)), ("attn_band_12_20", band), ("attn_band_3_11", range(3, 12)),
                             ("attn_band_21_29", range(21, 30)), ("attn_full_15_19", [15, 19]),
                             ("attn_lin_12_20", [l for l in band if l not in FULL])):
            cfgs.append((name, {l: setter(mu[l]) for l in layers}, "all"))
        for d in range(3):
            r = random.Random(2000 + d)
            l5 = sorted(r.sample(outside, 5))
            fo = sorted(r.sample(full_out, 2))
            cfgs.append((f"attn_rand5_d{d}", {l: setter(mu[l]) for l in l5}, "all"))
            cfgs.append((f"attn_randfull_d{d}", {l: setter(mu[l]) for l in fo}, "all"))
        cfgs.append(("attn_band_10_18", {l: setter(mu[l]) for l in range(10, 19)}, "all"))
        cfgs.append(("attn_27", {27: setter(mu[27])}, "all"))
        b2 = {l: setter(mu[l]) for l in range(16, 21)}
        cfgs.append(("attn_band_16_20_onset", b2, "onset"))
        cfgs.append(("attn_band_16_20_after", b2, "after"))
        allowed = os.environ.get("C2_CONFIGS")
        if allowed:
            keep = set(allowed.split(","))
            cfgs = [c for c in cfgs if c[0] in keep]
        dn = done_set()
        cfgs = [c for c in cfgs if (u["uid"], c[0]) not in dn]
        if not cfgs:
            continue
        cid = hashlib.md5((u["uid"] + "|" + os.environ.get("C2_CONFIGS", "")).encode()).hexdigest()
        if os.environ.get("C2_SWEEP") != "1":
            try:
                os.close(os.open(claims / f"{cid}.claim", os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            except FileExistsError:
                continue
        inp, gen = seqs[(u["cond"], u["sim"], u["turn"])]
        budget = min(1536, int(1.5 * len(gen)) + 64)
        with torch.no_grad():
            cache0 = None
            pre = inp[:-1]
            for s in range(0, len(pre), CHUNK):
                cache0 = H.lm(input_ids=torch.tensor([pre[s:s + CHUNK]], device="cuda"), past_key_values=cache0, use_cache=True).past_key_values
            for cname, od, when in cfgs:
                cache = copy.deepcopy(cache0)
                cur, out_ids, ended = inp[-1], [], False
                for t in range(budget):
                    H.ops = od if (when == "all" or (when == "onset" and t == 0) or (when == "after" and t > 0)) else {}
                    o = H.lm(input_ids=torch.tensor([[cur]], device="cuda"), past_key_values=cache, use_cache=True)
                    cache = o.past_key_values
                    cur = int(model.lm_head(o.last_hidden_state[0, -1]).argmax())
                    if cur in eos:
                        ended = True
                        break
                    out_ids.append(cur)
                H.ops = {}
                text = tok.decode(out_ids)
                names = FUNC.findall(text)
                row = {"uid": u["uid"], "group": u["group"], "domain": u["domain"], "task": u["task"], "orig_call": u["call"],
                       "config": cname, "names": names, "ended": ended, "n_gen": len(out_ids), "budget": budget,
                       "orig_len": len(gen), "same": u["call"] in names,
                       "verbal_transfer": (not any(x == "transfer_to_human_agents" for x in names)) and bool(VERBAL.search(text)),
                       "text_head": text[:300]}
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                del cache
            del cache0
        log(f"{wid} unit {n + 1}/{len(runlist)} {u['group']} {u['call']} {time.time() - t0:.0f}s")
    log("RUN_DONE")


def mode_report():
    rows, seen = [], set()
    for p in sorted(OUT.glob("rows_*.jsonl")):
        for line in p.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if (r["uid"], r["config"]) in seen:
                continue
            seen.add((r["uid"], r["config"]))
            rows.append(r)
    allowed = os.environ.get("C2_CONFIGS")
    if allowed:
        keep = set(allowed.split(","))
        rows = [r for r in rows if r["config"] in keep]
    base = {r["uid"]: r for r in rows if r["config"] == "base"}
    ok = {u for u, r in base.items() if r["same"] and r["ended"]}
    tot = defaultdict(lambda: [0, 0])
    for u, r in base.items():
        tot[r["group"]][1] += 1
        tot[r["group"]][0] += u in ok
    md = ["# C2T: ToolAlign CAUSAL-2 intervention on tau2 (Qwen3.5-4B, greedy regeneration of one agent turn)", "",
          "- base reproduces the original call (and ends): " + ", ".join(f"{g} {a}/{b}" for g, (a, b) in sorted(tot.items())) + ". Only reproducing units are scored.",
          "- A = unneeded transfers, B = unexpected writes, L = legitimate transfers, K = correct non-transfer writes.",
          "- flip = original call absent and the turn ended; unfinished = budget hit; verbal = no transfer call but transfer language in the text.", "",
          "| config | A flip | A unfinished | A verbal-of-flips | B flip | L flip (legit transfers) | K kept | K unfinished |", "|---|---|---|---|---|---|---|---|"]
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["uid"] in ok:
            by[r["config"]][r["group"]].append(r)
    for cfg in sorted(by, key=lambda c: (c != "base", c)):
        g = by[cfg]
        f = lambda rs: (sum((not r["same"]) and r["ended"] for r in rs), len(rs))
        un = lambda rs: (sum(not r["ended"] for r in rs), len(rs))
        a, b, l, k = g["A"], g["B"], g["L"], g["K"]
        fa = f(a)
        verbal = (sum(r["verbal_transfer"] for r in a if (not r["same"]) and r["ended"]), fa[0])
        kept = (sum(r["same"] for r in k), len(k))
        s = lambda x: f"{x[0]}/{x[1]}" + (f" ({x[0] / x[1]:.0%})" if x[1] else "")
        md.append(f"| {cfg} | {s(fa)} | {s(un(a))} | {s(verbal)} | {s(f(b))} | {s(f(l))} | {s(kept)} | {s(un(k))} |")
    (OUT / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    m = sys.argv[1]
    if m == "stats":
        mode_stats(int(sys.argv[2]), int(sys.argv[3]))
    elif m == "run":
        mode_run()
    else:
        mode_report()
