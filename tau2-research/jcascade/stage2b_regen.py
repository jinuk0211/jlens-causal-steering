"""J-Cascade stage 2b (project-b GPU 0 only): causal neuron selection and paired-prompt DoM steering on logged transfer turns.

Detection is unchanged (stage-0 J-lens layer-word pattern, applied offline as a gate). Only the intervention differs from stage 2:
  A*  neurons ranked by sum_t (a - mu) * dL/da, L = log p of the transfer tokens of the teacher-forced turn (label-free), mean-ablated
  AG20 the same ranking restricted to L20-26 neurons whose J-lens readout of W_down is a give-up family
  B*  alpha * paired-prompt DoM at L20/L24/L26 (prompt with vs without a verbatim policy reminder, last prompt position)
  P0  the reminder prompt itself (flippability bound), RA20 / RB8 random controls, C0 none
Selection on task fold f, application on fold 1 - f (md5(task) % 2). Pre-registration: PLAN.md, J-Cascade STAGE 2b.
JC_PHASE=prep writes out/stage2b/prep.pt + prep.json; JC_PHASE=gen (JC_SHARD=i/n) writes out/stage2b/rows_<cfg>.jsonl.
"""
import copy
import gzip
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch

J = Path(os.environ.get("JC_DIR", "/workspace/jc"))
sys.path.insert(0, str(J / "data"))
SMOKE = bool(os.environ.get("JC_SMOKE"))
OUT = J / os.environ.get("JC_OUTSUB", "out/stage2b_smoke" if SMOKE else "out/stage2b")
LAYERS = list(range(12, 32))
STEER = [20, 24, 26]
MAX_NEW = 768
CHUNK = 2048
FAM = {
    "inability": {"unable", "cannot", "can't", "无法", "我无法", "无法满足", "不能", "我不能", "impossible", "couldn"},
    "understanding": {"理解", "understand", "understanding", "understands", "understood", "明白", "understandable", "明白了"},
    "acknowledgement": {"acknowledge", "acknowledges", "acknowledging", "acknowledgment", "ack", "sincerely", "recognizing",
                        "recognize", "recogn", "honestly"},
}
REMINDER = ("Policy reminder: You should deny user requests that are against this policy. You should transfer the user to a "
            "human agent if and only if the request cannot be handled within the scope of your actions.")
CONFIGS = ["C0", "P0", "A5", "A20", "A100", "AG20", "RA20", "RA100", "B05", "B1", "B3", "B8", "RB1", "RB8"]
ALPHA = {"B05": 0.5, "B1": 1.0, "B3": 3.0, "B8": 8.0}
ABL = ("A5", "A20", "A100", "AG20", "RA20", "RA100")
PREFIX = {"PF_pc": "Let me first check what the policy says about this request.", "PF_deny": "I'm sorry, but according to our policy,",
          "PF_help": "I can help you with that.", "PF_neutral": "Thank you for your patience.",
          "PF_alt": "I'm sorry, but I can't do that under our policy. Here is what I can do instead:",
          "PF_clarify": "Before we go further, let me make sure I understand your request.",
          "PF_self": "Let me check the policy to see whether this is something I can handle myself.",
          "PF_denyhelp": "I'm sorry, but according to our policy, I can't do that. However, I can help you with"}
THINK_TAIL = "<think>\n\n</think>\n\n"
THINK = {"TH_free": "<think>\n",
         "TH_pc": "<think>\nLet me check whether the policy allows this request, or whether transferring to a human agent is really needed.\n"}
THINK_MAX = 2048
DESC_ALL = ("\\n\\nOnly transfer if\\n -  the user explicitly asks for a human agent\\n -  given the policy and the available tools, "
            "you cannot solve the user's issue.")
DESC_ASK = "\\n -  the user explicitly asks for a human agent"
POLICY_TRANSFER = "You should transfer the user to a human agent if and only if the request cannot be handled within the scope of your actions. "
HUMAN_RE = re.compile(r"\b(human|real person|representative|supervisor|manager|escalate|escalation|transfer)\b", re.I)


def drop_user_human(txt):
    segs = txt.split("<|im_start|>")
    out = []
    for s_ in segs:
        if s_.startswith("user\n") and "<tool_response>" not in s_ and "<|im_end|>" in s_:
            body, rest = s_[5:].split("<|im_end|>", 1)
            sents = re.split(r"(?<=[.!?])\s+", body)
            kept = [x for x in sents if not HUMAN_RE.search(x)]
            s_ = "user\n" + (" ".join(kept) if kept else "Okay.") + "<|im_end|>" + rest
        out.append(s_)
    return "<|im_start|>".join(out)


OCCL = {"O_desc": lambda t: t.replace(DESC_ALL, ""), "O_ask": lambda t: t.replace(DESC_ASK, ""),
        "O_policy": lambda t: t.replace(POLICY_TRANSFER, ""), "O_userhuman": drop_user_human}
TRANSFORM_PREFIXES = ("PF_", "TH_", "O_", "S07", "TM", "MID", "P1")
MID_TEXT = ("\n\nWait. The policy says I should deny user requests that are against the policy, and transfer only if the request "
            "cannot be handled within the scope of my actions. Let me reconsider whether a transfer is really needed here.\n\n")
REMINDER2 = ("Policy clarification: a request that the policy does not allow is still within the scope of your actions - you handle it "
             "by explaining the policy and denying it. Do not transfer a user to a human agent just because the policy does not allow "
             "their request. Transfer only when the user's issue is allowed but cannot be resolved with your tools.")
MID_TEXT2 = ("\n\nWait. A request that the policy does not allow is still within the scope of my actions: I handle it by explaining "
             "the policy and denying it, not by transferring. Let me reconsider whether a transfer is really needed here.\n\n")
SAMPLE = {"S07a": (0.7, 1), "S07b": (0.7, 2), "S07c": (0.7, 3), "S07d": (0.7, 4)}


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def fold_of(task_key):
    return int(hashlib.md5(task_key.encode()).hexdigest(), 16) % 2


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
    want = os.environ.get("JC_GPU_UUID")
    uuid = str(torch.cuda.get_device_properties(0).uuid)
    if want and want not in uuid:
        log(f"wrong GPU {uuid}, expected {want}; exiting")
        return 2
    phase = os.environ.get("JC_PHASE", "prep")
    from transformers import AutoTokenizer, Qwen3_5Config, Qwen3_5ForCausalLM

    mp = Path(os.environ["JC_MODEL"])
    tok = AutoTokenizer.from_pretrained(mp)
    turns = json.loads((J / "data/cache_turns.json").read_text(encoding="utf-8"))
    lab = {}
    for t in turns:
        if "transfer_to_human_agents" in t["calls"]:
            bad = any(b.startswith("unexpected_transfer") for b in t["bad"])
            y = 1 if (bad and not t["ep_pass"]) else (0 if t["ep_pass"] else None)
            if y is not None:
                lab[(t["domain"], t["sim"], t["turn"])] = (y, f"{t['domain']}|{t['task']}")
    eps = {}
    for f in sorted((J / "data/episodes").glob("*.json.gz")):
        ep = json.loads(gzip.open(f, "rt").read())
        eps[(ep["domain"], ep["sim_id"])] = ep
    im_start = tok.convert_tokens_to_ids("<|im_start|>")
    rem_ids = tok.encode("<|im_start|>system\n" + REMINDER + "<|im_end|>\n", add_special_tokens=False)
    name_ids = tok.encode("transfer_to_human_agents", add_special_tokens=False)
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
                last = max(i for i, x in enumerate(ids) if x == im_start)
                gen = t["gen"]
                j0 = next((s for s in range(len(gen)) if gen[s:s + len(name_ids)] == name_ids), None)
                targets = []
                if j0 is not None:
                    targets = [i for i in range(j0) if tok.decode([gen[i]]).strip().lower().startswith("transfer")] + [j0]
                rows.append({"domain": d, "sim": sim, "turn": turn, "y": y, "task": task, "fold": fold_of(task), "prompt": ids,
                             "rem_prompt": ids[:last] + rem_ids + ids[last:], "gen": gen, "j0": j0, "targets": targets,
                             "orig_text": tok.decode(gen)[:300]})
                break
    if SMOKE:
        rows = [r for r in rows if r["fold"] == 0][:2] + [r for r in rows if r["fold"] == 1][:2]
    log(f"transfer rows {len(rows)}: bad {sum(r['y'] for r in rows)}, good {sum(1 - r['y'] for r in rows)}, "
        f"no tool-name position {sum(r['j0'] is None for r in rows)}")

    config = Qwen3_5Config.from_pretrained(mp).text_config
    model = Qwen3_5ForCausalLM.from_pretrained(mp, config=config, dtype=torch.bfloat16,
                                               key_mapping={r"^model\.language_model\.": "model."}).to("cuda").eval()
    model.requires_grad_(False)
    blocks = model.model.layers
    state = {"on": False, "allpos": False, "abl": {}, "add": {}, "cap": False, "caph": None}
    cap, caph = {}, {}

    def mlp_pre(layer):
        def f(module, args):
            x = args[0]
            if state["cap"]:
                if x.requires_grad:
                    x.retain_grad()
                cap[layer] = x
            if state["on"] and layer in state["abl"]:
                idx, vals = state["abl"][layer]
                x = x.clone()
                if state["allpos"]:
                    x[:, :, idx] = vals
                else:
                    x[:, -1, idx] = vals
                return (x,)
            return None
        return f

    def block_post(layer):
        def f(module, args, out):
            h = out[0] if isinstance(out, tuple) else out
            if state["caph"] is not None:
                caph[layer] = h[0, state["caph"]].detach().float().cpu()
            if state["on"] and layer in state["add"]:
                h = h.clone()
                if state["allpos"]:
                    h[:, :] += state["add"][layer]
                else:
                    h[:, -1] += state["add"][layer]
                return (h,) + tuple(out[1:]) if isinstance(out, tuple) else h
            return out
        return f

    for layer in LAYERS:
        blocks[layer].mlp.down_proj.register_forward_pre_hook(mlp_pre(layer))
    for layer in STEER:
        blocks[layer].register_forward_hook(block_post(layer))
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
    def prefill(ids, on_last=False, caph_last=False):
        cache, out = None, None
        ps = pieces(len(ids))
        for k, (s, e) in enumerate(ps):
            lastp = k == len(ps) - 1
            state["on"] = on_last and lastp
            state["caph"] = -1 if (caph_last and lastp) else None
            out = model(input_ids=torch.tensor([ids[s:e]], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
            cache = out.past_key_values
        state["on"], state["caph"] = False, None
        return cache, out

    OUT.mkdir(parents=True, exist_ok=True)
    if phase == "prep":
        return prep(rows, model, tok, state, cap, caph, prefill, mp)
    if phase == "natdom":
        return natdom(rows, turns, eps, tok, caph, prefill)
    if phase == "tfcheck":
        return tfcheck(rows, model, tok, prefill)
    return gen_phase(rows, model, tok, state, prefill, end_ids)


def tfcheck(rows, model, tok, prefill):
    out = []
    for r in rows:
        cache, _ = prefill(r["prompt"][:-1])
        ids = torch.tensor([[r["prompt"][-1]] + r["gen"][:-1]], device="cuda")
        with torch.no_grad():
            lg = model(input_ids=ids, past_key_values=cache, use_cache=True).logits[0].float().log_softmax(-1)
        gen = torch.tensor(r["gen"], device="cuda")
        top = lg.argmax(-1)
        lp_logged = lg.gather(1, gen[:, None])[:, 0]
        lp_top = lg.max(-1).values
        mism = (top != gen).nonzero()
        first = int(mism[0]) if len(mism) else None
        rec = {"domain": r["domain"], "sim": r["sim"], "turn": r["turn"], "y": r["y"], "n_gen": len(r["gen"]),
               "n_mismatch": int(len(mism)), "first_mismatch": first}
        if first is not None:
            rank = int((lg[first] > lg[first, gen[first]]).sum())
            rec.update({"gap_at_first": float(lp_top[first] - lp_logged[first]), "rank_at_first": rank,
                        "logged_tok": tok.decode([int(gen[first])]), "top_tok": tok.decode([int(top[first])]),
                        "min_gap_any_mismatch": float((lp_top - lp_logged)[mism[:, 0]].min()),
                        "max_gap_any_mismatch": float((lp_top - lp_logged)[mism[:, 0]].max())})
        out.append(rec)
        del cache, lg
        torch.cuda.empty_cache()
        log(f"tfcheck {len(out)}/{len(rows)} mismatches {rec['n_mismatch']} first {first}")
    (OUT / "tfcheck.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    log("TFCHECK_DONE")
    return 0


DENY = re.compile(r"(I'm sorry|I am sorry|I apologi[sz]e|unfortunately|I'm unable|I am unable|I cannot|I can't|not able to|"
                  r"not possible|against (our|the) policy|not allowed|not eligible|cannot be)", re.I)
NAT = {"N10": 0.1, "N20": 0.2, "RN20": 0.2}
DONE_RE = re.compile(r"successfully|has been (booked|cancelled|canceled|updated|modified|changed|processed)|is now (booked|confirmed)", re.I)


def natdom(rows, turns, eps, tok, caph, prefill):
    want = {(t["domain"], t["sim"], t["turn"]): t for t in turns if t["ep_pass"] and not t["calls"]}
    cand = []
    for (d, sim), ep in sorted(eps.items()):
        prev = []
        for t in ep["turns"]:
            ids = prev[:t["lcp"]] + t["tail"]
            prev = ids
            ct = want.get((d, sim, t["turn"]))
            if ct is None:
                continue
            text = tok.decode(t["gen"])
            if os.environ.get("JC_DENY_STRICT"):
                ok = (DENY.search(text[:400]) and not DONE_RE.search(text) and "transfer" not in text.lower()
                      and "human agent" not in text.lower())
            else:
                ok = DENY.search(text) and "transfer" not in text.lower() and "human agent" not in text.lower()
            if ok:
                cand.append({"domain": d, "task": f"{d}|{ct['task']}", "prompt": ids, "text": text[:300]})
    rng = np.random.default_rng(7)
    by_dom = {}
    for c in cand:
        by_dom.setdefault(c["domain"], []).append(c)
    pick = []
    for d, cs in sorted(by_dom.items()):
        idx = rng.permutation(len(cs))[:40]
        pick += [cs[i] for i in idx]
    log(f"denial candidates {len(cand)} " + str({d: len(v) for d, v in by_dom.items()}) + f", picked {len(pick)}")

    def h_last(ids):
        prefill(ids, caph_last=True)
        return torch.stack([caph[l] for l in STEER])

    H_deny = [(fold_of(c["task"]), h_last(c["prompt"])) for c in pick]
    H_tr = [(r["fold"], h_last(r["prompt"])) for r in rows]
    v, rand = {}, {}
    for f in (0, 1):
        a = torch.stack([h for ff, h in H_deny if ff == f]).mean(0)
        b = torch.stack([h for ff, h in H_tr if ff == f]).mean(0)
        v[f] = a - b
        g = torch.Generator().manual_seed(400 + f)
        rnd = torch.randn(v[f].shape, generator=g)
        rand[f] = rnd / rnd.norm(dim=-1, keepdim=True)
    hn = torch.stack([h for _, h in H_tr]).norm(dim=-1).mean(0)
    summ = {"n_deny": len(pick), "n_deny_by_fold": [sum(1 for ff, _ in H_deny if ff == f) for f in (0, 1)],
            "dom_norm": {f: [float(x) for x in v[f].norm(dim=-1)] for f in (0, 1)}, "h_norm": [float(x) for x in hn],
            "cos_folds": [float(torch.nn.functional.cosine_similarity(v[0][i], v[1][i], dim=0)) for i in range(len(STEER))],
            "examples": [c["text"] for c in pick[:8]]}
    torch.save({"v": v, "rand": rand, "hn": hn}, OUT / "natdom.tmp")
    (OUT / "natdom.tmp").rename(OUT / "natdom.pt")
    (OUT / "natdom.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    log("natdom " + json.dumps({k: summ[k] for k in ("n_deny", "n_deny_by_fold", "dom_norm", "h_norm", "cos_folds")}))
    log("NATDOM_DONE")
    return 0


def assign_recurrent(self, recurrent_states, state_idx=0, **kwargs):
    if not self.is_recurrent_states_initialized[state_idx]:
        self.lazy_initialization(recurrent_states=recurrent_states, state_idx=state_idx)
    self.recurrent_states[state_idx] = recurrent_states
    return recurrent_states


def prep(rows, model, tok, state, cap, caph, prefill, mp):
    import jlens
    from jlens_causal.vocab_trigger import load_readout_head
    from safetensors import safe_open

    voc = json.loads(gzip.open(J / "data/vocab.json.gz", "rt", encoding="utf-8").read())
    norm = [v.strip().lower() for v in voc]
    head = load_readout_head(mp)
    lens = jlens.JacobianLens.load(os.environ["JC_LENS"])
    U = head.unembed.float().cuda()
    index = json.loads((mp / "model.safetensors.index.json").read_text())["weight_map"]
    pre = "model.language_model." if any(k.startswith("model.language_model.") for k in index) else "model."
    give = {}
    for layer in range(20, 27):
        name = f"{pre}layers.{layer}.mlp.down_proj.weight"
        with safe_open(mp / index[name], framework="pt") as h:
            D = h.get_tensor(name).float().cuda().T
        moved = lens.transport(D, layer) if layer in lens.jacobians else D
        flags = []
        for s in range(0, D.shape[0], 512):
            lg = head.norm(moved[s:s + 512].cpu()).cuda() @ U.T
            tp, tn_ = lg.topk(15, -1).indices.cpu().numpy(), (-lg).topk(15, -1).indices.cpu().numpy()
            for a, b in zip(tp, tn_):
                hit = any(norm[i] in ws for i in a for ws in FAM.values()) or any(norm[i] in ws for i in b for ws in FAM.values())
                flags.append(hit)
        give[layer] = np.array(flags)
        del D, moved
    del U
    torch.cuda.empty_cache()
    log("give-up readout flags: " + ", ".join(f"L{l} {int(v.sum())}" for l, v in give.items()))

    nl = len(LAYERS)
    a_sum = torch.zeros(nl, 9216, dtype=torch.float64)
    n_pos = 0
    AG, G, diff, hnorm, keep = [], [], [], [], []
    for k, r in enumerate(rows):
        t0 = time.time()
        if r["j0"] is None:
            continue
        cache, _ = prefill(r["prompt"][:-1])
        ids = torch.tensor([[r["prompt"][-1]] + r["gen"][:r["j0"]]], device="cuda")
        emb = model.model.embed_tokens(ids).detach().requires_grad_(True)
        cap.clear()
        lin_types = {type(x) for x in cache.layers if hasattr(x, "recurrent_states")}
        orig = {T: T.update_recurrent_state for T in lin_types}
        for T in lin_types:
            T.update_recurrent_state = assign_recurrent
        try:
            state["cap"], state["caph"] = True, 0
            out = model(inputs_embeds=emb, past_key_values=cache, use_cache=True)
            state["cap"] = False
            state["caph"] = None
            h_plain = {l: caph[l].clone() for l in STEER}
            lp = out.logits[0].float().log_softmax(-1)
            L = sum(lp[i, r["gen"][i]] for i in r["targets"])
            L.backward()
        finally:
            state["cap"], state["caph"] = False, None
            for T, fn in orig.items():
                T.update_recurrent_state = fn
        ag = torch.zeros(nl, 9216)
        gg = torch.zeros(nl, 9216)
        for li, layer in enumerate(LAYERS):
            a = cap[layer][0].detach().float()
            g = cap[layer].grad[0].float()
            ag[li] = (a * g).sum(0).cpu()
            gg[li] = g.sum(0).cpu()
            a_sum[li] += a.sum(0).double().cpu()
        n_pos += ids.shape[1]
        del out, lp, L, emb, cache
        cap.clear()
        _, _ = prefill(r["rem_prompt"], caph_last=True)
        diff.append(torch.stack([caph[l] - h_plain[l] for l in STEER]))
        hnorm.append(torch.stack([h_plain[l].norm() for l in STEER]))
        AG.append(ag)
        G.append(gg)
        keep.append(k)
        torch.cuda.empty_cache()
        log(f"prep {k + 1}/{len(rows)} {r['domain']} sim {r['sim'][:8]} turn {r['turn']} chunk {ids.shape[1]} targets {len(r['targets'])} "
            f"{time.time() - t0:.0f}s")
    mu = (a_sum / max(n_pos, 1)).float()
    AG, G, diff, hnorm = torch.stack(AG), torch.stack(G), torch.stack(diff), torch.stack(hnorm)
    folds = torch.tensor([rows[k]["fold"] for k in keep])
    score = AG - mu[None] * G
    sets, dom = {}, {}
    for f in (0, 1):
        sf = score[folds == f].mean(0)
        S = {}
        for kk in (5, 20, 100):
            S[f"A{kk}"] = {LAYERS[li]: [int(n) for n in torch.topk(sf[li], kk).indices if sf[li, n] > 0] for li in range(nl)}
        S["AG20"] = {}
        for layer in range(20, 27):
            li = LAYERS.index(layer)
            cand = np.nonzero(give[layer])[0]
            vals = sf[li][torch.from_numpy(cand)].numpy()
            order = cand[np.argsort(-vals)]
            S["AG20"][layer] = [int(n) for n in order[:20] if sf[li, n] > 0]
        rng = np.random.default_rng(200 + f)
        S["RA20"] = {layer: [int(n) for n in rng.choice(9216, 20, replace=False)] for layer in LAYERS}
        S["RA100"] = {layer: [int(n) for n in rng.choice(9216, 100, replace=False)] for layer in LAYERS}
        sets[f] = S
        v = diff[folds == f].mean(0)
        g = torch.Generator().manual_seed(300 + f)
        rnd = torch.randn(v.shape, generator=g)
        rnd = rnd / rnd.norm(dim=-1, keepdim=True) * v.norm(dim=-1, keepdim=True)
        dom[f] = {"v": v, "rand1": rnd, "rand8": rnd * 8.0}
    log("dom norms " + str({f: [round(float(x), 2) for x in dom[f]["v"].norm(dim=-1)] for f in (0, 1)})
        + " h norms " + str([round(float(x), 1) for x in hnorm.mean(0)]))

    # necessity check: teacher-forced change of L on the other fold
    nec = []
    for k in keep:
        r = rows[k]
        S = sets[1 - r["fold"]]
        cache0, _ = prefill(r["prompt"][:-1])
        ids = torch.tensor([[r["prompt"][-1]] + r["gen"][:r["j0"]]], device="cuda")
        res = {"domain": r["domain"], "sim": r["sim"], "turn": r["turn"], "y": r["y"], "fold": r["fold"]}
        for cfg in ("none",) + ABL:
            cache = copy.deepcopy(cache0)
            if cfg != "none":
                state["abl"] = {l: (torch.tensor(ns, device="cuda"), mu[LAYERS.index(l), ns].to("cuda", torch.bfloat16))
                                for l, ns in S[cfg].items() if ns}
                state["on"], state["allpos"] = True, True
            with torch.no_grad():
                out = model(input_ids=ids, past_key_values=cache, use_cache=True)
            state["on"], state["allpos"], state["abl"] = False, False, {}
            lp = out.logits[0].float().log_softmax(-1)
            res[cfg] = float(sum(lp[i, r["gen"][i]] for i in r["targets"]))
            res[cfg + "_top1"] = bool(int(lp[r["j0"]].argmax()) == r["gen"][r["j0"]])
            del out, cache, lp
        nec.append(res)
        del cache0
        torch.cuda.empty_cache()
    summ = {"n_rows": len(keep), "n_pos": n_pos,
            "set_sizes": {f: {c: sum(len(v) for v in S.values()) for c, S in sets[f].items()} for f in (0, 1)},
            "dom_norm": {f: [float(x) for x in dom[f]["v"].norm(dim=-1)] for f in (0, 1)},
            "h_norm_mean": [float(x) for x in hnorm.mean(0)],
            "dom_cos_folds": [float(torch.nn.functional.cosine_similarity(dom[0]["v"][i], dom[1]["v"][i], dim=0)) for i in range(len(STEER))],
            "necessity_mean_dL": {c: float(np.mean([x[c] - x["none"] for x in nec])) for c in ABL},
            "necessity_top1_kept": {c: f"{sum(x[c + '_top1'] for x in nec)}/{len(nec)}" for c in ("none",) + ABL}}
    torch.save({"mu": mu, "sets": sets, "dom": dom, "AG": AG.half(), "G": G.half(), "keep": keep, "folds": folds,
                "give": {l: torch.tensor(v) for l, v in give.items()}}, OUT / "prep.tmp")
    (OUT / "prep.json").write_text(json.dumps({"summary": summ, "necessity": nec,
                                               "sets": {str(f): {c: {str(l): ns for l, ns in S.items()} for c, S in sets[f].items()} for f in (0, 1)}},
                                              indent=1), encoding="utf-8")
    (OUT / "prep.tmp").rename(OUT / "prep.pt")
    log("necessity " + json.dumps(summ["necessity_mean_dL"]) + " top1 " + json.dumps(summ["necessity_top1_kept"]))
    log("STAGE2B_PREP_DONE")
    return 0


def gen_phase(rows, model, tok, state, prefill, end_ids):
    P = {}

    def load_prep():
        while not (OUT / "prep.pt").exists():
            time.sleep(30)
        time.sleep(10)
        P.update(torch.load(OUT / "prep.pt", weights_only=False))
        log("prep loaded")

    def setup(cfg, fold_src):
        state["abl"], state["add"] = {}, {}
        if cfg in ("C0", "P0") or cfg.startswith(TRANSFORM_PREFIXES):
            return False
        if cfg in NAT:
            if "nat" not in P:
                P["nat"] = torch.load(OUT / "natdom.pt", weights_only=False)
            N = P["nat"]
            unit = N["rand"][fold_src] if cfg.startswith("RN") else N["v"][fold_src] / N["v"][fold_src].norm(dim=-1, keepdim=True)
            state["add"] = {l: (NAT[cfg] * N["hn"][i] * unit[i]).to("cuda", torch.bfloat16) for i, l in enumerate(STEER)}
            return True
        if "mu" not in P:
            load_prep()
        mu, S, Dv = P["mu"], P["sets"][fold_src], P["dom"][fold_src]
        if cfg in ABL:
            state["abl"] = {l: (torch.tensor(ns, device="cuda"), mu[LAYERS.index(l), ns].to("cuda", torch.bfloat16))
                            for l, ns in S[cfg].items() if ns}
        if cfg in ALPHA:
            state["add"] = {l: (ALPHA[cfg] * Dv["v"][i]).to("cuda", torch.bfloat16) for i, l in enumerate(STEER)}
        if cfg in ("RB1", "RB8"):
            key = "rand1" if cfg == "RB1" else "rand8"
            state["add"] = {l: Dv[key][i].to("cuda", torch.bfloat16) for i, l in enumerate(STEER)}
        return bool(state["abl"] or state["add"])

    def build(cfg, r):
        if cfg == "P0":
            return r["rem_prompt"], MAX_NEW, "", True
        if cfg == "P1":
            last = max(i for i, x in enumerate(r["prompt"]) if x == im_start_id)
            return r["prompt"][:last] + rem2_ids + r["prompt"][last:], MAX_NEW, "", True
        if cfg.startswith("P1PF_"):
            last = max(i for i, x in enumerate(r["prompt"]) if x == im_start_id)
            pre = PREFIX[cfg[2:]]
            return r["prompt"][:last] + rem2_ids + r["prompt"][last:] + tok.encode(pre, add_special_tokens=False), MAX_NEW, pre, True
        if cfg in PREFIX:
            pre = PREFIX[cfg]
            return r["prompt"] + tok.encode(pre, add_special_tokens=False), MAX_NEW, pre, True
        if cfg in THINK:
            tail = tok.encode(THINK_TAIL, add_special_tokens=False)
            assert r["prompt"][-len(tail):] == tail, "prompt does not end with the empty think block"
            return r["prompt"][:-len(tail)] + tok.encode(THINK[cfg], add_special_tokens=False), THINK_MAX, THINK[cfg], True
        if cfg in OCCL:
            txt = tok.decode(r["prompt"])
            new = OCCL[cfg](txt)
            return (tok.encode(new, add_special_tokens=False), MAX_NEW, "", new != txt)
        return r["prompt"], MAX_NEW, "", True

    tool_call_id = tok.convert_tokens_to_ids("<tool_call>")

    def pick(logits, samp, ban):
        logits = logits.float()
        if ban:
            logits[tool_call_id] = -1e9
        if samp is None:
            return int(logits.argmax())
        temp, g = samp
        probs = torch.softmax(logits / temp, -1)
        sp, si = probs.sort(descending=True)
        keep = sp.cumsum(-1) - sp < 0.95
        sp = sp * keep
        return int(si[torch.multinomial(sp / sp.sum(), 1, generator=g)])

    name_ids = tok.encode("transfer_to_human_agents", add_special_tokens=False)
    mid_ids = tok.encode(MID_TEXT, add_special_tokens=False)
    mid2_ids = tok.encode(MID_TEXT2, add_special_tokens=False)
    im_start_id = tok.convert_tokens_to_ids("<|im_start|>")
    rem2_ids = tok.encode("<|im_start|>system" + chr(10) + REMINDER2 + "<|im_end|>" + chr(10), add_special_tokens=False)

    @torch.no_grad()
    def heads_to_transfer(cache, first):
        c = copy.deepcopy(cache)
        seq, t = [first], first
        for _ in range(len(name_ids) + 4):
            o = model(input_ids=torch.tensor([[t]], device="cuda"), past_key_values=c, use_cache=True, logits_to_keep=1)
            c = o.past_key_values
            t = int(o.logits[0, -1].argmax())
            seq.append(t)
        del c
        return any(seq[i:i + len(name_ids)] == name_ids for i in range(len(seq)))

    @torch.no_grad()
    def generate(prompt, active, max_new=MAX_NEW, samp=None, ban=False, mid=None):
        cache, out = prefill(prompt, on_last=active)
        gen = []
        nxt = pick(out.logits[0, -1], samp, ban)
        injected = False
        for step in range(max_new):
            if mid and not injected and nxt == tool_call_id and heads_to_transfer(cache, nxt):
                injected = True
                gen += mid
                out = model(input_ids=torch.tensor([mid], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
                cache = out.past_key_values
                nxt = pick(out.logits[0, -1], samp, ban)
            gen.append(nxt)
            if nxt in end_ids:
                break
            state["on"] = active
            out = model(input_ids=torch.tensor([[nxt]], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
            state["on"] = False
            cache = out.past_key_values
            nxt = pick(out.logits[0, -1], samp, ban)
        return gen, len(gen) >= max_new

    cfgs = CONFIGS
    shard = os.environ.get("JC_SHARD")
    if os.environ.get("JC_CFGS"):
        cfgs = os.environ["JC_CFGS"].split(",")
    elif SMOKE:
        cfgs = ["C0", "P0", "A20", "B3"]
    elif shard:
        si, sn = (int(x) for x in shard.split("/"))
        cfgs = [c for k, c in enumerate(CONFIGS) if k % sn == si]
    for cfg in cfgs:
        path = OUT / f"rows_{cfg}.jsonl"
        done = set()
        if path.exists():
            done = {(r["sim"], r["turn"]) for r in map(json.loads, path.open())}
        with path.open("a", encoding="utf-8") as fh:
            base = re.sub(r"_r[0-9]+$", "", cfg)
            for r in rows:
                if (r["sim"], r["turn"]) in done:
                    continue
                active = setup(base, 1 - r["fold"])
                t0 = time.time()
                prompt, max_new, pre, changed = build(base, r)
                samp = None
                if base in SAMPLE:
                    g_ = torch.Generator(device="cuda")
                    g_.manual_seed(int(hashlib.md5(f"{r['sim']}|{r['turn']}|{SAMPLE[base][1]}".encode()).hexdigest(), 16) % (2 ** 31))
                    samp = (SAMPLE[base][0], g_)
                g, capped = generate(prompt, active, max_new, samp=samp, ban=base == "TM", mid={"MID": mid_ids, "MID2": mid2_ids}.get(base))
                text = pre + tok.decode(g)
                body, closed = text, True
                if base in THINK:
                    closed = "</think>" in text
                    body = text.split("</think>", 1)[1] if closed else ""
                outcome = classify(body, capped and not (base in THINK and closed and not body.strip() == ""))
                if base in THINK and not closed:
                    outcome = "degenerate"
                fh.write(json.dumps({"cfg": cfg, "sim": r["sim"], "turn": r["turn"], "domain": r["domain"], "y": r["y"], "fold": r["fold"],
                                     "base": base, "outcome": outcome, "n_gen": len(g), "text": text[:1500], "text_full": text,
                                     "after_think": body[:800] if base in THINK else None,
                                     "changed": changed, "orig": r["orig_text"],
                                     "n_abl": sum(len(v[0]) for v in state["abl"].values()), "n_add": len(state["add"]),
                                     "sec": round(time.time() - t0, 1)}) + "\n")
                fh.flush()
        log(f"config {cfg} done")
    log("STAGE2B_SHARD_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
