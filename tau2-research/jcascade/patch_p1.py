"""R5 (project-b GPU 0): where does the P1 effect enter? Activation patching from the P1 run into the clean run.

P1 inserts a clarifying system message right before the final assistant header, so the clean and the P1 (donor) prompts
differ only after the insertion point: the inserted tokens exist only in the donor, and the header tokens are shared but
shifted. For each row where P1 changes the outcome, the header-position activations of the donor are copied into the
clean run at one layer and one component, then both answers are scored teacher-forced:
  delta = log p(P1 answer) - log p(C0 answer); restoration = (delta_patch - delta_clean) / (delta_donor - delta_clean).
Components per layer: residual (block output) at all header positions, residual at the last position only, attention
output at all header positions, MLP output at all header positions.
Output: out/review/patch_p1.json
"""
import copy
import gzip
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import torch

J = Path(os.environ.get("JC_DIR", "/workspace/jc"))
sys.path.insert(0, str(J / "data"))
OUT = J / "out/review"
CHUNK = 2048
MAX_CONT = 300
SMOKE = bool(os.environ.get("JC_SMOKE"))
REMINDER2 = ("Policy clarification: a request that the policy does not allow is still within the scope of your actions - you handle it "
             "by explaining the policy and denying it. Do not transfer a user to a human agent just because the policy does not allow "
             "their request. Transfer only when the user's issue is allowed but cannot be resolved with your tools.")
NULL_TEXT = ("System note: routine maintenance of the internal reporting dashboard is scheduled for this evening between 9 pm and 10 pm. "
             "The maintenance does not affect any customer-facing tools, reservations, orders, or accounts. No action is needed during "
             "this conversation, and nothing about it should be mentioned to the customer. Thank you for your attention to this note.")
CONV = {"other_tool", "text"}
NEGT = re.compile(r"((cannot|can't|can not|unable to|not able to|won't|will not|should not|shouldn't|do not|don't|not)\s+(\w+\s+){0,3}"
                  r"(transfer|escalat|connect))|((only|until|unless|before)\b[^.!?\n]{0,80}(transfer|human agent))", re.I)
AFF = re.compile(r"(transfer(ring)?|connect(ing)?|escalat\w*)\b[^.!?\n]{0,40}\byou|human agent|representative|supervisor", re.I)


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def converted(r):
    if r["outcome"] in CONV:
        return True
    if r["outcome"] != "verbal_transfer":
        return False
    sents = re.split(r"[.!?\n]+", r["text"])
    return not any(AFF.search(x) and not NEGT.search(x) for x in sents)


def main():
    want = os.environ.get("JC_GPU_UUID")
    if want and want not in str(torch.cuda.get_device_properties(0).uuid):
        log("wrong GPU; exiting")
        return 2
    from transformers import AutoTokenizer, Qwen3_5Config, Qwen3_5ForCausalLM

    mp = Path(os.environ["JC_MODEL"])
    tok = AutoTokenizer.from_pretrained(mp)
    load = lambda p: {(r["sim"], r["turn"]): r for r in map(json.loads, p.open(encoding="utf-8"))}
    c0 = load(J / "out/stage2b/rows_C0.jsonl")
    p1 = load(J / "out/explore/rows_P1.jsonl")
    pick = [k for k in c0 if k in p1 and c0[k]["outcome"] == "transfer" and converted(p1[k])]
    log(f"rows where C0 transfers and P1 does not: {len(pick)} (bad {sum(c0[k]['y'] for k in pick)})")
    eps = {}
    for f in sorted((J / "data/episodes").glob("*.json.gz")):
        ep = json.loads(gzip.open(f, "rt").read())
        eps[(ep["domain"], ep["sim_id"])] = ep
    im_start = tok.convert_tokens_to_ids("<|im_start|>")
    rem2 = tok.encode("<|im_start|>system" + chr(10) + REMINDER2 + "<|im_end|>" + chr(10), add_special_tokens=False)
    head_ids = tok.encode("<|im_start|>system" + chr(10), add_special_tokens=False)
    tail_ids = tok.encode("<|im_end|>" + chr(10), add_special_tokens=False)
    body = tok.encode(NULL_TEXT, add_special_tokens=False)[:len(rem2) - len(head_ids) - len(tail_ids)]
    null_ids = head_ids + body + tail_ids
    log(f"P1 message {len(rem2)} tokens, null message {len(null_ids)} tokens")
    rows = []
    for k in pick:
        r0 = c0[k]
        ep = eps[(r0["domain"], r0["sim"])]
        prev = []
        for t in ep["turns"]:
            ids = prev[:t["lcp"]] + t["tail"]
            prev = ids
            if t["turn"] == r0["turn"]:
                last = max(i for i, x in enumerate(ids) if x == im_start)
                rows.append({"key": k, "domain": r0["domain"], "y": r0["y"], "prefix": ids[:last], "header": ids[last:], "rem": rem2, "null": null_ids,
                             "a": tok.encode(r0["text"], add_special_tokens=False)[:MAX_CONT],
                             "b": tok.encode(p1[k]["text"], add_special_tokens=False)[:MAX_CONT]})
                break
    if SMOKE:
        rows = rows[:2]

    config = Qwen3_5Config.from_pretrained(mp).text_config
    model = Qwen3_5ForCausalLM.from_pretrained(mp, config=config, dtype=torch.bfloat16,
                                               key_mapping={r"^model\.language_model\.": "model."}).to("cuda").eval()
    model.requires_grad_(False)
    blocks = model.model.layers
    nl = len(blocks)
    st = {"mode": None, "comp": None, "layers": set(), "sel": None}
    store = {}

    def attn_of(b):
        return b.linear_attn if hasattr(b, "linear_attn") else b.self_attn

    def mk(comp, layer):
        def f(module, args, out):
            h = out[0] if isinstance(out, tuple) else out
            if st["mode"] == "capture":
                store[(comp, layer)] = h[0].detach().clone()
            elif st["mode"] == "patch" and st["comp"] == comp and layer in st["layers"]:
                h = h.clone()
                src = store[(comp, layer)]
                if st["sel"] == "last":
                    h[0, -1] = src[-1]
                else:
                    h[0, :] = src
                return (h,) + tuple(out[1:]) if isinstance(out, tuple) else h
            return None
        return f

    for l, b in enumerate(blocks):
        b.register_forward_hook(mk("resid", l))
        attn_of(b).register_forward_hook(mk("attn", l))
        b.mlp.register_forward_hook(mk("mlp", l))

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
    def prefill(ids):
        cache = None
        for s, e in pieces(len(ids)):
            cache = model(input_ids=torch.tensor([ids[s:e]], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1).past_key_values
        return cache

    @torch.no_grad()
    def score(cache, header, a, b):
        out = model(input_ids=torch.tensor([header], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
        st["mode"] = None
        first = out.logits[0, -1].float().log_softmax(-1)
        base = out.past_key_values
        res = []
        for seq in (a, b):
            c = copy.deepcopy(base)
            lg = model(input_ids=torch.tensor([seq[:-1]], device="cuda"), past_key_values=c, use_cache=True).logits[0].float().log_softmax(-1)
            res.append(float(first[seq[0]] + lg.gather(1, torch.tensor(seq[1:], device="cuda")[:, None]).sum()))
            del c, lg
        return res[1] - res[0]

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / ("patch_p1_smoke.json" if SMOKE else "patch_p1.json")
    results = []
    t_all = time.time()
    for n, r in enumerate(rows):
        t0 = time.time()
        donor_prefix = prefill(r["prefix"] + r["rem"])
        st["mode"] = "capture"
        store.clear()
        d_donor = score(donor_prefix, r["header"], r["a"], r["b"])
        del donor_prefix
        clean_prefix = prefill(r["prefix"])
        st["mode"] = None
        d_clean = score(copy.deepcopy(clean_prefix), r["header"], r["a"], r["b"])
        rec = {"domain": r["domain"], "y": r["y"], "sim": r["key"][0], "turn": r["key"][1], "delta_clean": d_clean, "delta_donor": d_donor,
               "patch": {}}
        span = d_donor - d_clean
        for comp, sel in (("resid", "all"), ("resid", "last"), ("attn", "all"), ("mlp", "all")):
            vals = []
            for l in range(nl):
                st.update(mode="patch", comp=comp, layers={l}, sel=sel)
                d = score(copy.deepcopy(clean_prefix), r["header"], r["a"], r["b"])
                vals.append(round((d - d_clean) / span, 4) if abs(span) > 1e-6 else None)
            rec["patch"][f"{comp}_{sel}"] = vals
        for l0 in (0, 8, 12, 16, 20, 24):
            st.update(mode="patch", comp="resid", layers=set(range(l0, nl)), sel="all")
            d = score(copy.deepcopy(clean_prefix), r["header"], r["a"], r["b"])
            rec["patch"][f"resid_all_from_L{l0}"] = round((d - d_clean) / span, 4) if abs(span) > 1e-6 else None
        st["mode"] = None
        null_prefix = prefill(r["prefix"] + r["null"])
        st["mode"] = "capture"
        store.clear()
        d_null = score(null_prefix, r["header"], r["a"], r["b"])
        del null_prefix
        rec["delta_null_donor"] = d_null
        vals = []
        for l in range(nl):
            st.update(mode="patch", comp="resid", layers={l}, sel="all")
            d = score(copy.deepcopy(clean_prefix), r["header"], r["a"], r["b"])
            vals.append(round((d - d_clean) / span, 4) if abs(span) > 1e-6 else None)
        rec["patch"]["null_resid_all"] = vals
        st["mode"] = None
        del clean_prefix
        torch.cuda.empty_cache()
        results.append(rec)
        out_path.write_text(json.dumps(results, indent=1), encoding="utf-8")
        best = max(range(nl), key=lambda l: rec["patch"]["resid_all"][l] or -9)
        log(f"{n + 1}/{len(rows)} {r['domain']} y={r['y']} clean {d_clean:.1f} donor {d_donor:.1f} null {rec['delta_null_donor']:.1f} "
            f"resid_all best L{best} {rec['patch']['resid_all'][best]} {time.time() - t0:.0f}s")
    log(f"PATCH_DONE rows {len(results)} {time.time() - t_all:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
