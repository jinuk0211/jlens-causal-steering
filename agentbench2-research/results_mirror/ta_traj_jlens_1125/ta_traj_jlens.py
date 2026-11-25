"""Trajectory J-lens on ToolAlign-4B CAUSAL-1 units (user 11-25: not only fixed positions; every token of the end of the
input, the preamble sentences before the call, and the call scaffold up to the tool-name position).
For every scanned position and every lens layer 0..30 + final: log-probs of the domain's tool first tokens (same set for
every unit of a domain) and the top-50 tokens. fp32 on one GPU (RTX 2080 Ti box).
Usage: python ta_traj_jlens.py ta_seqs.json OUT_DIR"""
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

TOPN = 50
CHUNK = 1024
POSB = 256


def main():
    units = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
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
    H = C.Hooked(model)
    lens = C.Lens(model)
    L = lens.layers + ["final"]
    done = {p.stem for p in out.glob("u_*.npz")}
    t0 = time.time()
    meta = []
    for n, u in enumerate(units):
        name = f"u_{n}"
        span = list(range(u["ctx_start"], u["pos"] + 1))
        meta.append({k: u[k] for k in u if k != "ids"} | {"idx": n, "span": [span[0], span[-1]],
                                                          "span_ids": u["ids"][span[0]:span[-1] + 2]})
        if name in done:
            continue
        ids = u["ids"][:u["pos"] + 1]
        got = {}
        cache = None
        with torch.inference_mode():
            for s0 in range(0, len(ids), CHUNK):
                e0 = min(s0 + CHUNK, len(ids))
                absp = [p for p in span if s0 <= p < e0]
                H.store = {}
                H.cap = {"mode": "pos", "pos": [p - s0 for p in absp], "kinds": {"res"}} if absp else None
                o = model(input_ids=torch.tensor([ids[s0:e0]], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
                cache = o.past_key_values
                for (k, l), v in H.store.items():
                    got.setdefault(l, []).append(v)
            H.cap = None
            del cache
        res = {l: torch.cat(v, 0) for l, v in got.items()}
        cid = torch.tensor(u["cand_ids"], device=lens.dev)
        npos = len(span)
        cand_lp = np.zeros((npos, len(L), len(u["cand_ids"])), np.float16)
        top_ids = np.zeros((npos, len(L), TOPN), np.int32)
        top_lp = np.zeros((npos, len(L), TOPN), np.float16)
        with torch.inference_mode():
            for li, l in enumerate(L):
                h = res[l if l != "final" else H.nl - 1]
                for b in range(0, npos, POSB):
                    lp = torch.log_softmax(lens.logits(h[b:b + POSB], l), -1)
                    cand_lp[b:b + POSB, li] = lp[:, cid].cpu().numpy()
                    v, i = torch.topk(lp, TOPN, -1)
                    top_ids[b:b + POSB, li], top_lp[b:b + POSB, li] = i.cpu().numpy(), v.cpu().numpy()
                    del lp
        np.savez_compressed(out / f"{name}.npz", cand_lp=cand_lp, top_ids=top_ids, top_lp=top_lp)
        del res
        if n % 10 == 0:
            (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
            C.log(f"{n + 1}/{len(units)} units, {npos} positions, {time.time() - t0:.0f}s")
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    C.log(f"TRAJ_DONE {len(units)}")


if __name__ == "__main__":
    main()
