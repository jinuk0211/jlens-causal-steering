"""C-LOOP C2-N (PLAN.md, pre-registered 11-24 17:0x): neuron steering of the transfer decision. GPU 0 only.
Neurons: decision-point MLP activations L12-31 (jcascade x15 / denial feat 'mlp'), effect size d = (mean bad - mean denial) / pooled sd
on TRAIN tasks; top-K by |d|. Steering at the decision point and every generated position: a <- a + lambda * (mu_denial - mu_bad) on
the selected neurons (down_proj input). Random control: K random neurons with the same per-layer counts, the selected shift
magnitudes permuted, random signs. Outcome and phases as c1m_dom.py (select on train bad turns, confirm the pick on eval bad, legit,
harmless and denial turns). Output probe/circuit/out/c2n/rows_<phase>.jsonl"""
import copy
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

R = Path("/home/project-b/LJW/tau2-steer")
sys.path.insert(0, str(R / "probe/topk"))
import build_topk as bt

J = R / "probe/jcascade/out"
OUT = R / "probe/circuit/out/c2n"
KS = [64, 256]
LAMS = [1.0, 3.0]
ML0 = 12
MAX_NEW = 480
CHUNK = 4096
PHASE = os.environ.get("C2N_PHASE", "select")
SETTING = os.environ.get("C2N_SETTING", "")
LIMIT = int(os.environ.get("C2N_LIMIT", "0"))
LATE = {"x15:33", "x15:49"}
AIR_TRAIN = {"0", "1", "3", "4", "5", "7", "9", "10", "11", "12", "14", "15", "17", "20", "21", "23", "27", "28", "36", "38", "39",
             "40", "41", "42"}


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def split(domain, task):
    if domain == "airline":
        return "train" if task in AIR_TRAIN else "eval"
    return "train" if int(hashlib.md5(f"{domain}|{task}".encode()).hexdigest(), 16) % 2 == 0 else "eval"


def classify(text, capped):
    calls = re.findall(r"<function=([^>\n]+)>", text)
    words = text.split()
    grams = Counter(tuple(words[i:i + 8]) for i in range(max(len(words) - 7, 0)))
    if (max(grams.values()) if grams else 0) >= 3:
        return "degenerate"
    if calls:
        return "transfer" if calls[0] == "transfer_to_human_agents" else "other_tool"
    if capped:
        return "capped"
    if re.search(r"transfer(ring)? you|human agent|connect you with|representative", text, re.I):
        return "verbal_transfer"
    return "text"


def main():
    uuid = str(torch.cuda.get_device_properties(0).uuid)
    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID" or "c27bc2d7" not in uuid:
        log(f"wrong GPU {uuid}; exiting")
        return 2
    os.chdir(R / "tau2-bench")
    torch.set_grad_enabled(False)
    x15 = json.loads((J / "x15/rows.json").read_text(encoding="utf-8"))
    den = json.loads((J / "review/denial/rows.json").read_text(encoding="utf-8"))
    turns = []
    for r in x15:
        cat = ("bad" if r["label"] == "bad_write" and not r["ep_pass"] else
               "legit" if r["label"] == "good_write" and r["ep_pass"] else
               "harmless" if r["ep_pass"] else None)
        if cat:
            turns.append(dict(r, cat=cat, src="x15", feat=str(J / f"x15/feat_{r['k']}.npz")))
    for r in den:
        if r["ep_pass"]:
            turns.append(dict(r, cat="denial", src="denial", feat=str(J / f"review/denial/feat_{r['k']}.npz")))
    for t in turns:
        t["split"] = split(t["domain"], t["task"])
        t["key"] = f"{t['src']}:{t['k']}"
    mlp = {t["key"]: np.load(t["feat"])["mlp"].astype(np.float32) for t in turns}
    bad_tr = np.stack([mlp[t["key"]] for t in turns if t["cat"] == "bad" and t["split"] == "train" and t["key"] not in LATE])
    den_tr = np.stack([mlp[t["key"]] for t in turns if t["cat"] == "denial" and t["split"] == "train"])
    mu_b, mu_d = bad_tr.mean(0), den_tr.mean(0)
    sd = np.sqrt(((bad_tr - mu_b) ** 2).sum(0) / max(1, len(bad_tr) - 1) * 0.5 + ((den_tr - mu_d) ** 2).sum(0) / max(1, len(den_tr) - 1) * 0.5) + 1e-6
    d = ((mu_b - mu_d) / sd).ravel()
    order = np.argsort(-np.abs(d))
    nl_m, nn = mu_b.shape
    rng = np.random.default_rng(0)
    sets = {}
    for K in KS:
        sel = order[:K]
        shift = (mu_d - mu_b).ravel()[sel]
        layers = sel // nn
        rnd = np.array([int(l) * nn + int(rng.integers(nn)) for l in layers])
        rshift = rng.permutation(np.abs(shift)) * rng.choice([-1.0, 1.0], size=K)
        sets[K] = {"neuron": (sel, shift), "rand": (rnd, rshift)}
        log(f"K={K}: |d| min {np.abs(d[sel]).min():.2f} max {np.abs(d[sel]).max():.2f}; layers "
            f"{dict(sorted(Counter((sel // nn + ML0).tolist()).items()))}")
    settings = [f"K{K}_l{lam:g}" for K in KS for lam in LAMS]
    if PHASE == "select":
        todo = [t for t in turns if t["cat"] == "bad" and t["split"] == "train" and t["key"] not in LATE]
        conds = ["base"] + [f"{s}:{kind}" for s in settings for kind in ("neuron", "rand")]
    else:
        assert SETTING in settings, SETTING
        pick = np.random.default_rng(1)
        todo = [t for t in turns if (t["cat"] == "bad" and t["split"] == "eval") or t["cat"] == "legit"]
        for cat in ("harmless", "denial"):
            pool = [t for t in turns if t["cat"] == cat]
            idx = pick.choice(len(pool), size=min(20, len(pool)), replace=False)
            todo += [pool[i] for i in sorted(idx)]
        conds = ["base", f"{SETTING}:neuron", f"{SETTING}:rand"]
    if LIMIT:
        todo = todo[:LIMIT]
    want = {(t["cond"], t["sim"], int(t["turn"])): t["key"] for t in todo}
    seqs = {}
    for domain in ("airline", "retail", "telecom"):
        cs = sorted({t["cond"] for t in todo if t["domain"] == domain})
        if not cs:
            continue
        for domain_, cond, task, sim, tel in bt.episodes(Path("data/simulations/pilot"), Path("data/jlens-telemetry/pilot"), [domain], cs):
            for line in tel.open(encoding="utf-8"):
                rec = json.loads(line)
                key = (cond, sim["id"], int(rec["turn_index"]))
                if key in want:
                    seqs[want[key]] = list(rec["input_ids"])
    log(f"{PHASE}: {len(todo)} turns, {len(conds)} conditions, inputs found for {len(seqs)}")
    tok, model = bt.load_model(os.environ["JC_MODEL"], "cuda")
    blocks = model.model.layers
    end_ids = {tok.convert_tokens_to_ids("<|im_end|>"), tok.eos_token_id}
    st = {"on": False, "add": {}}

    def pre_down(layer):
        def f(module, args):
            if st["on"] and layer in st["add"]:
                x = args[0].clone()
                idx, val = st["add"][layer]
                x[0, -1, idx] = x[0, -1, idx] + val
                return (x,)
        return f

    for L in range(ML0, ML0 + nl_m):
        blocks[L].mlp.down_proj.register_forward_pre_hook(pre_down(L))

    def build(sel, shift):
        per = defaultdict(lambda: ([], []))
        for n, s in zip(sel, shift):
            l, j = divmod(int(n), nn)
            per[l + ML0][0].append(j)
            per[l + ML0][1].append(float(s))
        return {l: (torch.tensor(ix, device="cuda"), torch.tensor(v, device="cuda", dtype=torch.bfloat16)) for l, (ix, v) in per.items()}

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"rows_{PHASE}{'_' + SETTING if SETTING else ''}.jsonl"
    done = set()
    if path.exists():
        done = {(r["key"], r["cond"]) for r in map(json.loads, path.open(encoding="utf-8"))}
    t0 = time.time()
    tc_end = tok.convert_tokens_to_ids("</tool_call>")
    with path.open("a", encoding="utf-8") as fh:
        for n, t in enumerate(todo):
            if t["key"] not in seqs:
                continue
            ids = seqs[t["key"]]
            cache0 = None
            for s in range(0, len(ids) - 1, CHUNK):
                cache0 = model.model(input_ids=torch.tensor([ids[s:min(s + CHUNK, len(ids) - 1)]], device="cuda"),
                                     past_key_values=cache0, use_cache=True).past_key_values
            for cond in conds:
                if (t["key"], cond) in done:
                    continue
                if cond == "base":
                    st["add"] = {}
                else:
                    sname, kind = cond.split(":")
                    Ks, ls = sname.split("_")
                    K, lam = int(Ks[1:]), float(ls[1:])
                    sel, shift = sets[K][kind]
                    st["add"] = build(sel, shift * lam)
                cache = copy.deepcopy(cache0)
                st["on"] = bool(st["add"])
                out = model(input_ids=torch.tensor([[ids[-1]]], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
                gen = []
                nxt = int(out.logits[0, -1].argmax())
                for step in range(MAX_NEW):
                    gen.append(nxt)
                    if nxt in end_ids:
                        break
                    if step % 4 == 0 or nxt == tc_end:
                        if re.search(r"<function=([^>\n]+)>", tok.decode(gen)):
                            break
                    out = model(input_ids=torch.tensor([[nxt]], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
                    nxt = int(out.logits[0, -1].argmax())
                st["on"] = False
                text = tok.decode(gen)
                capped = len(gen) >= MAX_NEW and not re.search(r"<function=", text)
                outcome = classify(text, capped)
                del cache
                fh.write(json.dumps({"key": t["key"], "cat": t["cat"], "split": t["split"], "domain": t["domain"], "task": t["task"],
                                     "cond": cond, "outcome": outcome, "n_gen": len(gen), "text": text[:700]}) + "\n")
                fh.flush()
            del cache0
            log(f"{n + 1}/{len(todo)} {t['key']} {t['cat']} {t['split']} done ({time.time() - t0:.0f}s)")
    rows = [json.loads(line) for line in path.open(encoding="utf-8")]
    agg = defaultdict(Counter)
    for r in rows:
        agg[(r["cond"], r["cat"], r["split"])][r["outcome"]] += 1
    lines = [f"# C2-N {PHASE} {SETTING}", "", "| cond | cat | split | n | transfer | other_tool | text | verbal | degenerate | capped |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for (cond, cat, sp), c in sorted(agg.items()):
        lines.append(f"| {cond} | {cat} | {sp} | {sum(c.values())} | {c['transfer']} | {c['other_tool']} | {c['text']} | "
                     f"{c['verbal_transfer']} | {c['degenerate']} | {c['capped']} |")
    (OUT / f"summary_{PHASE}{'_' + SETTING if SETTING else ''}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"C2N_DONE {PHASE}")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
