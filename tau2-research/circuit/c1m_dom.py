"""C-LOOP C1-M (PLAN.md "C-LOOP", pre-registered 11-24 15:3x): is the transfer decision carried by a mid-layer direction at the
decision point (the last input position of the turn)? GPU 0 only.
Data (read-only): jcascade/out/x15 (transfer turns) and jcascade/out/review/denial (denial turns), residual at the decision point.
Direction v_L = mean(res_L | denial turns of passed episodes, train tasks) - mean(res_L | bad transfer turns, train tasks).
Added as alpha * |h_L| * v_L / |v_L| at block L output, scope D (decision point only) or A (decision point and every generated
position). Random control: a seed-0 random unit direction per layer with the same alpha * |h_L| norm.
Outcome: greedy regeneration of the turn, stopped once the first tool name is complete, at <|im_end|>, or at MAX_NEW tokens.
transfer = the first call is transfer_to_human_agents. Phase "select": bad train turns, all settings. Phase "confirm": eval bad,
legit, harmless and denial turns, for C1M_SETTING (e.g. L14_a0.2_A). Output probe/circuit/out/c1m/rows_<phase>.jsonl"""
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
OUT = R / "probe/circuit/out/c1m"
LAYERS = [10, 14, 18]
ALPHAS = [0.1, 0.2]
SCOPES = ["D", "A"]
MAX_NEW = 480
CHUNK = 4096
PHASE = os.environ.get("C1M_PHASE", "select")
SETTING = os.environ.get("C1M_SETTING", "")
LIMIT = int(os.environ.get("C1M_LIMIT", "0"))
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
    res = {t["key"]: np.load(t["feat"])["res"].astype(np.float32) for t in turns}
    dom = {}
    for L in LAYERS:
        d_mean = np.mean([res[t["key"]][L] for t in turns if t["cat"] == "denial" and t["split"] == "train"], axis=0)
        b_mean = np.mean([res[t["key"]][L] for t in turns if t["cat"] == "bad" and t["split"] == "train"], axis=0)
        v = d_mean - b_mean
        dom[L] = v / np.linalg.norm(v)
    rng = np.random.default_rng(0)
    rnd = {L: (lambda u: u / np.linalg.norm(u))(rng.standard_normal(2560)) for L in LAYERS}
    counts = Counter((t["cat"], t["split"]) for t in turns)
    log(f"turns {dict(counts)}; |DoM| cos to random { {L: round(float(dom[L] @ rnd[L]), 3) for L in LAYERS} }")
    settings = [f"L{L}_a{a}_{s}" for L in LAYERS for a in ALPHAS for s in SCOPES]
    if PHASE == "select":
        todo = [t for t in turns if t["cat"] == "bad" and t["split"] == "train"]
        conds = ["base"] + [f"{s}:{kind}" for s in settings for kind in ("dom", "rand")]
    else:
        assert SETTING in settings, SETTING
        pick = np.random.default_rng(1)
        todo = [t for t in turns if t["cat"] in ("bad", "legit")]
        todo = [t for t in todo if not (t["cat"] == "bad" and t["split"] == "train")]
        for cat in ("harmless", "denial"):
            pool = [t for t in turns if t["cat"] == cat]
            idx = pick.choice(len(pool), size=min(20, len(pool)), replace=False)
            todo += [pool[i] for i in sorted(idx)]
        conds = ["base", f"{SETTING}:dom", f"{SETTING}:rand"]
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
    st = {"on": False, "L": None, "vec": None, "alpha": 0.0}

    def post(layer):
        def f(module, args, out):
            if st["on"] and st["L"] == layer:
                h = out if torch.is_tensor(out) else out[0]
                x = h[0, -1].float()
                h[0, -1] = (x + st["alpha"] * x.norm() * st["vec"]).to(h.dtype)
                return h if torch.is_tensor(out) else (h,) + tuple(out[1:])
            return out
        return f

    for L in LAYERS:
        blocks[L].register_forward_hook(post(L))
    vecs = {L: {"dom": torch.tensor(dom[L], device="cuda"), "rand": torch.tensor(rnd[L], device="cuda")} for L in LAYERS}
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"rows_{PHASE}{'_' + SETTING if SETTING else ''}.jsonl"
    done = set()
    if path.exists():
        done = {(r["key"], r["cond"]) for r in map(json.loads, path.open(encoding="utf-8"))}
    t0 = time.time()
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
                    L, alpha, scope, kind = None, 0.0, "D", None
                else:
                    sname, kind = cond.split(":")
                    Ls, a, scope = sname.split("_")
                    L, alpha = int(Ls[1:]), float(a[1:])
                st.update(L=L, alpha=alpha, vec=vecs[L][kind] if L is not None else None)
                cache = copy.deepcopy(cache0)
                st["on"] = L is not None
                out = model(input_ids=torch.tensor([[ids[-1]]], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
                st["on"] = False
                gen = []
                nxt = int(out.logits[0, -1].argmax())
                text = ""
                for step in range(MAX_NEW):
                    gen.append(nxt)
                    if nxt in end_ids:
                        break
                    if step % 4 == 0 or nxt == tok.convert_tokens_to_ids("</tool_call>"):
                        text = tok.decode(gen)
                        m = re.search(r"<function=([^>\n]+)>", text)
                        if m:
                            break
                    st["on"] = scope == "A" and L is not None
                    out = model(input_ids=torch.tensor([[nxt]], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
                    st["on"] = False
                    nxt = int(out.logits[0, -1].argmax())
                text = tok.decode(gen)
                capped = len(gen) >= MAX_NEW and not re.search(r"<function=", text)
                outcome = classify(text, capped)
                del cache
                fh.write(json.dumps({"key": t["key"], "cat": t["cat"], "split": t["split"], "domain": t["domain"], "task": t["task"],
                                     "cond": cond, "outcome": outcome, "n_gen": len(gen), "text": text[:700],
                                     "orig": (t.get("text") or "")[:300]}) + "\n")
                fh.flush()
            del cache0
            log(f"{n + 1}/{len(todo)} {t['key']} {t['cat']} {t['split']} done ({time.time() - t0:.0f}s)")
    rows = [json.loads(line) for line in path.open(encoding="utf-8")]
    agg = defaultdict(Counter)
    for r in rows:
        agg[(r["cond"], r["cat"], r["split"])][r["outcome"]] += 1
    lines = [f"# C1-M {PHASE} {SETTING}", "", "| cond | cat | split | n | transfer | other_tool | text | verbal | degenerate | capped |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for (cond, cat, sp), c in sorted(agg.items()):
        n = sum(c.values())
        lines.append(f"| {cond} | {cat} | {sp} | {n} | {c['transfer']} | {c['other_tool']} | {c['text']} | {c['verbal_transfer']} | "
                     f"{c['degenerate']} | {c['capped']} |")
    (OUT / f"summary_{PHASE}{'_' + SETTING if SETTING else ''}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"C1M_DONE {PHASE}")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
