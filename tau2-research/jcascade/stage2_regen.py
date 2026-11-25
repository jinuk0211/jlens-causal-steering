"""J-Cascade stage 2: offline steering regeneration of logged transfer turns (project-b GPU 0 only).

Rows: transfer_to_human_agents turns; bad = unneeded transfer in a failed episode, good = transfer in a passed episode.
Each turn is regenerated greedily from its logged prompt with neuron-pole interventions at the decision point (last prompt
token) and the first K generated tokens. Neuron sets are chosen on one half of the tasks and applied to the other half
(2-fold cross-fitting by task), so no turn is steered with neurons picked on its own label.

Configs: C0 none; S1 writers -> mean; S2 writers gate closed; S4 readers gate closed; S5 bipolar flip; S6 writers -> mean of
"continue" writes; S7 retry poles -> p99; S47 = S4 + S7; R1 random L20-26 -> mean (control for S1); R47 random L27-31 gate
closed + random L16-28 -> p99 (control for S47).
Outcome per regenerated turn: transfer / other_tool / text / verbal_transfer / degenerate.
Pass (pre-registered, PLAN.md): bad converted >= 40 %, good kept >= 80 %, degenerate <= 5 %, and better than its random control.
Output out/stage2/rows.jsonl, out/stage2/summary.{json,md}
"""
import copy
import gzip
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

J = Path(os.environ.get("JC_DIR", "/workspace/jc"))
sys.path.insert(0, str(J / "data"))
OUT = J / "out/stage2"
LAYERS = list(range(12, 32))
K_SET = int(os.environ.get("JC_K", "16"))
MAX_NEW = 768
K_POS = int(os.environ.get("JC_KPOS", str(MAX_NEW)))
CHUNK = 2048
READS = ("get_", "find_", "list_", "search_", "calculate", "think")
FAM = {
    "inability": {"unable", "cannot", "can't", "无法", "我无法", "无法满足", "不能", "我不能", "impossible", "couldn"},
    "apology": {"apologize", "apologies", "sorry", "抱歉", "unfortunately", "regret", "sadly", "apologized"},
    "understanding": {"理解", "understand", "understanding", "understands", "understood", "明白", "understandable", "明白了"},
    "acknowledgement": {"acknowledge", "acknowledges", "acknowledging", "acknowledgment", "ack", "sincerely", "recognizing",
                        "recognize", "recogn", "honestly"},
    "transfer": {"transfer", "transferring", "human", "specialist", "representative", "escalate", "supervisor", "agent"},
    "retry": {"check", "alternative", "alternatives", "another", "try", "options", "option", "instead", "let", "look", "explore",
              "other", "verify", "retry", "again"},
    "proceed": {"proceed", "confirm", "confirmed", "alright", "okay", "will", "我将", "我来", "确认", "同意", "perfect"},
}
GIVE = {"inability", "understanding", "acknowledgement"}
CONFIGS = ["C0", "S1", "S2", "S4", "S5", "S6", "S7", "S47", "R1", "R47"]


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def fold_of(task_key):
    return int(hashlib.md5(task_key.encode()).hexdigest(), 16) % 2


def fisher_one_sided(a, b, c, d):
    n1, n2, k = a + c, b + d, a + b
    tot = math.comb(n1 + n2, k)
    return sum(math.comb(n1, x) * math.comb(n2, k - x) for x in range(a, min(k, n1) + 1)) / tot


def classify(text, hit_cap):
    calls = re.findall(r"<function=([^>\n]+)>", text)
    words = text.split()
    grams = Counter(tuple(words[i:i + 8]) for i in range(max(len(words) - 7, 0)))
    rep = max(grams.values()) if grams else 0
    if hit_cap or rep >= 3:
        return "degenerate"
    if "transfer_to_human_agents" in calls:
        return "transfer"
    if calls:
        return "other_tool"
    if re.search(r"transfer(ring)? you|human agent|connect you with|representative", text, re.I):
        return "verbal_transfer"
    return "text"


def main():
    global OUT
    want = os.environ.get("JC_GPU_UUID")
    uuid = str(torch.cuda.get_device_properties(0).uuid)
    if want and want not in uuid:
        log(f"wrong GPU {uuid}, expected {want}; exiting")
        return 2
    from safetensors import safe_open
    from transformers import AutoTokenizer, Qwen3_5Config, Qwen3_5ForCausalLM
    import jlens
    from jlens_causal.vocab_trigger import load_readout_head

    mp = Path(os.environ["JC_MODEL"])
    tok = AutoTokenizer.from_pretrained(mp)
    voc = json.loads(gzip.open(J / "data/vocab.json.gz", "rt", encoding="utf-8").read())
    norm = [v.strip().lower() for v in voc]
    turns = json.loads((J / "data/cache_turns.json").read_text(encoding="utf-8"))
    lab = {}
    cont = {}
    for t in turns:
        key = (t["domain"], t["sim"], t["turn"])
        if "transfer_to_human_agents" in t["calls"]:
            bad = any(b.startswith("unexpected_transfer") for b in t["bad"])
            y = 1 if (bad and not t["ep_pass"]) else (0 if t["ep_pass"] else None)
            if y is not None:
                lab[key] = (y, f"{t['domain']}|{t['task']}")
        elif t["label"] == "good_write" and t["ep_pass"]:
            cont[key] = f"{t['domain']}|{t['task']}"

    # neuron statistics from stage 1
    ref, dec_tr, tn_tr, dec_cont = [], [], [], []
    for f in sorted((J / "out/neurons").glob("*.npz")):
        z = np.load(f)
        m = json.loads(str(z["meta"]))
        ref.append(z["dec_a"])
        for i, t in enumerate(z["dec_turn"].tolist()):
            k = (m["domain"], m["sim_id"], t)
            if k in lab:
                dec_tr.append((lab[k][0], fold_of(lab[k][1]), z["dec_a"][i]))
            if k in cont:
                dec_cont.append((fold_of(cont[k]), z["dec_a"][i]))
        for i, t in enumerate(z["tn_turn"].tolist()):
            k = (m["domain"], m["sim_id"], t)
            if k in lab:
                tn_tr.append((lab[k][0], fold_of(lab[k][1]), z["tn_a"][i]))
    ref = np.concatenate(ref).astype(np.float32)
    p1, p3, p97, p99 = (np.percentile(ref, q, axis=0) for q in (1, 3, 97, 99))
    mean = ref.mean(0)
    del ref
    log(f"stats: transfer dec {len(dec_tr)}, toolname {len(tn_tr)}, continue {len(dec_cont)}")

    # label-free J-lens readout families of every pole
    head = load_readout_head(mp)
    lens = jlens.JacobianLens.load(os.environ["JC_LENS"])
    U = head.unembed.float().cuda()
    index = json.loads((mp / "model.safetensors.index.json").read_text())["weight_map"]
    pre = "model.language_model." if any(k.startswith("model.language_model.") for k in index) else "model."
    tid_transfer = tok.encode("transfer_to_human_agents", add_special_tokens=False)[0]
    fam_pos, fam_neg, eff = {}, {}, {}

    def family(ids):
        c = Counter()
        for i in ids[:15]:
            for fname, ws in FAM.items():
                if norm[i] in ws:
                    c[fname] += 1
        return c.most_common(1)[0][0] if c else None

    for layer in LAYERS:
        name = f"{pre}layers.{layer}.mlp.down_proj.weight"
        with safe_open(mp / index[name], framework="pt") as h:
            D = h.get_tensor(name).float().cuda().T
        moved = lens.transport(D, layer) if layer in lens.jacobians else D
        fp, fn, ef = [], [], []
        for s in range(0, D.shape[0], 512):
            lg = head.norm(moved[s:s + 512].cpu()).cuda() @ U.T
            tp, tn_ = lg.topk(15, -1).indices.cpu().numpy(), (-lg).topk(15, -1).indices.cpu().numpy()
            fp += [family(r) for r in tp]
            fn += [family(r) for r in tn_]
            ef.append((lg[:, tid_transfer] - lg.mean(-1)).cpu().numpy())
        fam_pos[layer], fam_neg[layer], eff[layer] = fp, fn, np.concatenate(ef)
        del D, moved
    log("readout families ready")

    def firing(rows, sign):
        A = np.stack([r[-1] for r in rows]).astype(np.float32)
        return (A >= p97[None]) if sign == "+" else (A <= p3[None])

    def ranked(rows, train_fold, layer_set, allow, metric="fisher"):
        tr = [r for r in rows if r[1] == train_fold]
        y = np.array([r[0] for r in tr])
        NB, NG = int(y.sum()), int((1 - y).sum())
        out = []
        for sign in ("+", "-"):
            F = firing(tr, sign)
            nb, ng = F[y == 1].sum(0), F[y == 0].sum(0)
            for li, layer in enumerate(LAYERS):
                if layer not in layer_set:
                    continue
                fams = fam_pos[layer] if sign == "+" else fam_neg[layer]
                for n in np.nonzero(nb[li] >= 2)[0]:
                    if not allow(layer, n, sign, fams[n]):
                        continue
                    a, b = int(nb[li, n]), int(ng[li, n])
                    if a / max(NB, 1) <= b / max(NG, 1):
                        continue
                    out.append((fisher_one_sided(a, b, NB - a, NG - b), layer, int(n), sign))
        out.sort()
        return out

    def neuron_sets(train_fold):
        sets = {}
        w = ranked(dec_tr, train_fold, set(range(20, 27)), lambda l, n, s, f: f in GIVE)
        if len(w) < K_SET:
            w += [x for x in ranked(dec_tr, train_fold, set(range(20, 27)), lambda l, n, s, f: True) if x not in w]
        sets["writers"] = [(l, n, s) for _, l, n, s in w[:K_SET]]
        r = ranked(tn_tr, train_fold, set(range(27, 32)),
                   lambda l, n, s, f: (eff[l][n] if s == "+" else -eff[l][n]) > 0)
        sets["readers"] = [(l, n, s) for _, l, n, s in r[:K_SET]]
        bip = ranked(dec_tr, train_fold, set(LAYERS),
                     lambda l, n, s, f: f in GIVE and (fam_neg[l][n] if s == "+" else fam_pos[l][n]) in {"retry", "proceed"})
        sets["bipolar"] = [(l, n, s) for _, l, n, s in bip[:K_SET]]
        trc = [r for r in dec_cont if r[0] == train_fold]
        A = np.stack([r[1] for r in trc]).astype(np.float32) if trc else None
        cand = []
        for li, layer in enumerate(LAYERS):
            if not 16 <= layer <= 28:
                continue
            for sign, fams in (("+", fam_pos[layer]), ("-", fam_neg[layer])):
                for n, f in enumerate(fams):
                    if f == "retry" and A is not None:
                        fire = (A[:, li, n] >= p97[li, n]).mean() if sign == "+" else (A[:, li, n] <= p3[li, n]).mean()
                        cand.append((-fire, layer, n, sign))
        cand.sort()
        sets["retry"] = [(l, n, s) for _, l, n, s in cand[:K_SET]]
        sets["cont_mean"] = {}
        if A is not None:
            for (l, n, s) in sets["writers"]:
                sets["cont_mean"][(l, n)] = float(A[:, LAYERS.index(l), n].mean())
        rng = np.random.default_rng(100 + train_fold)
        sets["rand_w"] = [(int(l), int(n), "+") for l, n in zip(rng.choice(range(20, 27), K_SET), rng.choice(9216, K_SET))]
        sets["rand_r"] = [(int(l), int(n), "+") for l, n in zip(rng.choice(range(27, 32), K_SET), rng.choice(9216, K_SET))]
        sets["rand_t"] = [(int(l), int(n), "+" if rng.random() < .5 else "-") for l, n in zip(rng.choice(range(16, 29), K_SET), rng.choice(9216, K_SET))]
        return sets

    def ops_for(cfg, S):
        li = LAYERS.index
        ops = defaultdict(list)
        mean_v = lambda l, n: float(mean[li(l), n])
        p99v = lambda l, n, s: float(p99[li(l), n] if s == "+" else p1[li(l), n])
        if cfg == "S1":
            for l, n, s in S["writers"]:
                ops[l].append(("act", n, mean_v(l, n)))
        if cfg == "S2":
            for l, n, s in S["writers"]:
                ops[l].append(("gate", n, -4.0))
        if cfg in ("S4", "S47"):
            for l, n, s in S["readers"]:
                ops[l].append(("gate", n, -4.0))
        if cfg == "S5":
            for l, n, s in S["bipolar"]:
                ops[l].append(("flip", n, 1.0 if s == "+" else -1.0))
        if cfg == "S6":
            for l, n, s in S["writers"]:
                ops[l].append(("act", n, S["cont_mean"].get((l, n), mean_v(l, n))))
        if cfg in ("S7", "S47"):
            for l, n, s in S["retry"]:
                ops[l].append(("act", n, p99v(l, n, s)))
        if cfg == "R1":
            for l, n, s in S["rand_w"]:
                ops[l].append(("act", n, mean_v(l, n)))
        if cfg == "R47":
            for l, n, s in S["rand_r"]:
                ops[l].append(("gate", n, -4.0))
            for l, n, s in S["rand_t"]:
                ops[l].append(("act", n, p99v(l, n, s)))
        return ops

    config = Qwen3_5Config.from_pretrained(mp).text_config
    model = Qwen3_5ForCausalLM.from_pretrained(mp, config=config, dtype=torch.bfloat16,
                                               key_mapping={r"^model\.language_model\.": "model."}).to("cuda").eval()
    blocks = model.model.layers
    state = {"on": False, "ops": {}}

    def gate_hook(layer):
        def f(module, args, out):
            if not state["on"]:
                return out
            for kind, n, v in state["ops"].get(layer, ()):
                if kind == "gate":
                    out[:, -1, n] = v
            return out
        return f

    def act_hook(layer):
        def f(module, args):
            if not state["on"]:
                return None
            x = args[0]
            for kind, n, v in state["ops"].get(layer, ()):
                if kind == "act":
                    x[:, -1, n] = v
                elif kind == "flip":
                    cur = x[:, -1, n]
                    x[:, -1, n] = torch.where(cur * v > 0, -cur, cur)
            return (x,)
        return f

    for layer in LAYERS:
        blocks[layer].mlp.gate_proj.register_forward_hook(gate_hook(layer))
        blocks[layer].mlp.down_proj.register_forward_pre_hook(act_hook(layer))
    end_ids = {tok.convert_tokens_to_ids("<|im_end|>"), tok.eos_token_id}

    def pieces(n):
        out, s = [], 0
        while n - s >= CHUNK:
            out.append((s, s + CHUNK))
            s += CHUNK
        size = CHUNK // 2
        while s < n:
            while size > n - s:
                size //= 2
            out.append((s, s + size))
            s += size
        return out

    @torch.no_grad()
    def generate(prompt, ops):
        state["ops"] = ops
        cache = None
        ps = pieces(len(prompt))
        for k, (s, e) in enumerate(ps):
            last = k == len(ps) - 1
            state["on"] = bool(ops) and last
            ids = torch.tensor([prompt[s:e]], device="cuda")
            out = model(input_ids=ids, past_key_values=cache, use_cache=True, logits_to_keep=1)
            cache = out.past_key_values
        gen = []
        nxt = int(out.logits[0, -1].argmax())
        for step in range(MAX_NEW):
            gen.append(nxt)
            if nxt in end_ids:
                break
            state["on"] = bool(ops) and step < K_POS
            out = model(input_ids=torch.tensor([[nxt]], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
            cache = out.past_key_values
            nxt = int(out.logits[0, -1].argmax())
        state["on"] = False
        return gen, len(gen) >= MAX_NEW

    # transfer turns with their prompts
    eps = {}
    for f in sorted((J / "data/episodes").glob("*.json.gz")):
        ep = json.loads(gzip.open(f, "rt").read())
        eps[(ep["domain"], ep["sim_id"])] = ep
    rows = []
    for (d, sim, turn), (y, task) in sorted(lab.items()):
        ep = eps.get((d, sim))
        if ep is None:
            continue
        prev = []
        for t in ep["turns"]:
            ids = prev[:t["lcp"]] + t["tail"]
            prev = ids
            if t["turn"] == turn:
                rows.append({"domain": d, "sim": sim, "turn": turn, "y": y, "task": task, "fold": fold_of(task), "prompt": ids,
                             "orig_text": tok.decode(t["gen"])[:300]})
                break
    log(f"transfer rows {len(rows)}: bad {sum(r['y'] for r in rows)}, good {sum(1 - r['y'] for r in rows)}")
    sets = {f: neuron_sets(f) for f in (0, 1)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "neuron_sets.json").write_text(json.dumps({str(f): {k: (v if k != "cont_mean" else {f"{a}:{b}": c for (a, b), c in v.items()})
                                                              for k, v in s.items()} for f, s in sets.items()}, default=str), encoding="utf-8")
    shard = os.environ.get("JC_SHARD")
    cfgs = CONFIGS
    if os.environ.get("JC_SMOKE"):
        OUT = J / "out/stage2_smoke"
        OUT.mkdir(parents=True, exist_ok=True)
        rows = [r for r in rows if r["y"] == 1][:1] + [r for r in rows if r["y"] == 0][:1]
        cfgs = ["C0", "S1", "S47", "R47"]
        shard = None
    if shard:
        si, sn = (int(x) for x in shard.split("/"))
        cfgs = [c for k, c in enumerate(CONFIGS) if k % sn == si]
    for cfg in cfgs:
        path = OUT / f"rows_{cfg}.jsonl"
        done = set()
        if path.exists():
            done = {(r["sim"], r["turn"]) for r in map(json.loads, path.open())}
        with path.open("a", encoding="utf-8") as fh:
            for r in rows:
                if (r["sim"], r["turn"]) in done:
                    continue
                S = sets[1 - r["fold"]]
                ops = ops_for(cfg, S) if cfg != "C0" else {}
                t0 = time.time()
                gen, cap = generate(r["prompt"], ops)
                text = tok.decode(gen)
                fh.write(json.dumps({"cfg": cfg, "sim": r["sim"], "turn": r["turn"], "domain": r["domain"], "y": r["y"], "fold": r["fold"],
                                     "outcome": classify(text, cap), "n_gen": len(gen), "text": text[:600], "orig": r["orig_text"],
                                     "n_ops": sum(len(v) for v in ops.values()), "sec": round(time.time() - t0, 1)}) + "\n")
                fh.flush()
        log(f"config {cfg} done")
    log("STAGE2_SHARD_DONE")


if __name__ == "__main__":
    sys.exit(main())
