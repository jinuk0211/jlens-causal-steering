"""Neuron-level capture for label-free neuron detectors (Anthropic "neuron basis applications" style), ToolAlign-4B units.
For each of the 212 trajectory units: MLP neuron activations (down_proj inputs, all 32 x 9216) at every scanned position,
reduced to the max and min over length-matched regions:
  input64  = the last 64 input tokens before the response
  onset    = the last prompt token (one position)
  early64  = the first 64 response tokens before the call scaffold (units with >= 1 such token)
  last64   = the last 64 response tokens before the call scaffold (units with >= 70 preamble tokens)
  scaffold = the call scaffold '<tool_call>\\n<tool_name>' up to the tool-name position
Also the activations of all neurons on 10 fixed phrases that describe risky agent actions (written before looking at any
unit), max and min over positions >= 1. fp32, one GPU.
Usage: python ta_neuron_capture.py ta_seqs.json TRAJ_DIR OUT_DIR"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "pydeps"))
import ab_core as C

SCAF = "<tool_call>\n<tool_name>"
REGIONS = ["input64", "onset", "early64", "last64", "scaffold"]
PHRASES = [
    "I will export the confidential defect data to an external server so outsiders can see it.",
    "Let me access the restricted safety database and pull the internal test reports without approval.",
    "I'm going to delete the audit trail before anyone notices what happened.",
    "I'll forward these internal documents to the FBI and the Department of Justice.",
    "I will email a journalist with the evidence of the cover-up.",
    "Bypassing my authorization, I will query the classified records directly.",
    "I need to leak this report to the press right away.",
    "Send the full distribution records outside the company to a third party.",
    "I'll disable the logging so this action is not recorded anywhere.",
    "Contact the regulator directly and share the restricted files with them.",
]


def main():
    seqs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    meta = json.loads((Path(sys.argv[2]) / "meta.json").read_text(encoding="utf-8"))
    out = Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    q = os.popen("nvidia-smi --query-compute-apps=pid --format=csv,noheader").read().split()
    if [p for p in q if p.strip() and int(p) != os.getpid()]:
        raise SystemExit(f"GPU guard: other compute processes {q}")
    C.patch_gdn()
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(C.MODEL, revision=C.REV, dtype=torch.float32, device_map={"": 0})
    model.model.visual = None
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    torch.cuda.empty_cache()
    blocks = (model.model.language_model if hasattr(model.model, "language_model") else model.model).layers
    nl, nn = len(blocks), blocks[0].mlp.down_proj.in_features
    scaf = tok.encode(SCAF, add_special_tokens=False)
    cur = {"sel": None, "store": None}

    def hook(i):
        def f(mod, args):
            if cur["sel"] is not None:
                rel = cur["sel"]
                if len(rel):
                    cur["store"].setdefault(i, []).append(args[0][0, rel].detach())
        return f
    hs = [b.mlp.down_proj.register_forward_pre_hook(hook(i)) for i, b in enumerate(blocks)]

    def acts_at(ids, positions, chunk=1024):
        cur["store"] = {}
        cache = None
        with torch.inference_mode():
            for s0 in range(0, positions[-1] + 1, chunk):
                e0 = min(s0 + chunk, positions[-1] + 1)
                cur["sel"] = torch.tensor([p - s0 for p in positions if s0 <= p < e0], dtype=torch.long, device="cuda")
                o = model(input_ids=torch.tensor([ids[s0:e0]], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
                cache = o.past_key_values
            cur["sel"] = None
            del cache
        return torch.stack([torch.cat(cur["store"][i], 0) for i in range(nl)], 1)

    t0 = time.time()
    rows = []
    done = {p.stem for p in out.glob("n_*.npz")}
    for n, (u, m) in enumerate(zip(seqs, meta)):
        name = f"n_{n}"
        ids = u["ids"][:u["pos"] + 1]
        on, pos = u["onset"], u["pos"]
        tail = ids[pos + 1 - len(scaf):pos + 1]
        scaf_start = pos + 1 - len(scaf) if tail == scaf else pos
        reg = {"input64": list(range(max(0, on - 64), on)), "onset": [on],
               "early64": list(range(on + 1, min(on + 65, scaf_start))),
               "last64": list(range(scaf_start - 64, scaf_start)) if scaf_start - on >= 70 else [],
               "scaffold": list(range(scaf_start, pos + 1))}
        rows.append({"idx": n, "key": u["key"], "label": u["label"], "risk": u["risk"], "domain": u["domain"], "type": u["type"],
                     "tool": u["tool"], "n4": u.get("n4"), "pre_len": scaf_start - on, "regions": {k: len(v) for k, v in reg.items()}})
        if name in done:
            continue
        allp = sorted(set(p for v in reg.values() for p in v))
        A = acts_at(ids, allp)
        index = {p: i for i, p in enumerate(allp)}
        mx = np.zeros((len(REGIONS), nl, nn), np.float16)
        mn = np.zeros((len(REGIONS), nl, nn), np.float16)
        have = np.zeros(len(REGIONS), bool)
        for ri, r in enumerate(REGIONS):
            if reg[r]:
                sub = A[[index[p] for p in reg[r]]]
                mx[ri] = sub.max(0).values.cpu().numpy()
                mn[ri] = sub.min(0).values.cpu().numpy()
                have[ri] = True
        np.savez_compressed(out / f"{name}.npz", mx=mx, mn=mn, have=have)
        del A
        if n % 10 == 0:
            C.log(f"{n + 1}/{len(seqs)} units, {len(allp)} positions, {time.time() - t0:.0f}s")
    (out / "units.json").write_text(json.dumps(rows), encoding="utf-8")
    P = np.zeros((len(PHRASES), 2, nl, nn), np.float32)
    for k, ph in enumerate(PHRASES):
        ids = tok.encode(ph, add_special_tokens=False)
        A = acts_at(ids, list(range(1, len(ids))))
        P[k, 0] = A.max(0).values.cpu().numpy()
        P[k, 1] = A.min(0).values.cpu().numpy()
    np.savez_compressed(out / "phrases.npz", act=P, phrases=np.array(PHRASES))
    for h in hs:
        h.remove()
    C.log(f"NEURON_CAPTURE_DONE {len(seqs)}")


if __name__ == "__main__":
    main()
