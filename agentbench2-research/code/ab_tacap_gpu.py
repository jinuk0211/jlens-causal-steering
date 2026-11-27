"""ToolAlign components at the call onset on the GPU (user 11-27 13:2x: "gpu로 ... forward", for the paper's residual-flow figure).
Units and onset as ab_ne.py tacap (ana/ta/units.json; onset = the token that completes <tool_call>; one unit per uid), so the
units are those of hn/toolalign/hn.npz. At the onset token, for every layer: embedding output, token-mixer output (attn: o_proj or
out_proj output), MLP activation (down_proj input), MLP output (down_proj output) and the residual after the layer.
Identity check per unit: res(l) - res(l-1) - attn(l) - mlp(l), relative to |res(l)|.
-> ana/fig_flow/ta_gpu_onset.npz, ta_gpu_onset.log
Usage: CUDA_VISIBLE_DEVICES=g python ab_tacap_gpu.py"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_core as C

A = Path("/home/project-b/LJW/agentbench2/ana")
OUT = A / "fig_flow" / "ta_gpu_onset.npz"
NL = 32


def main():
    if OUT.exists():
        raise SystemExit(f"{OUT} exists; not overwritten")
    tok, model = C.load()
    H = C.Hooked(model)
    units = json.loads((A / "ta" / "units.json").read_text(encoding="utf-8"))
    seen, items = set(), []
    for u in units:
        if u["uid"] in seen:
            continue
        seen.add(u["uid"])
        comp = list(u["completion_ids"])
        text = tok.decode(comp)
        i = text.find("<tool_call>")
        if i < 0:
            continue
        k = C.char_to_token(tok, comp, i + len("<tool_call>") - 1)
        items.append((u, len(u["prompt_ids"]), len(u["prompt_ids"]) + k))
    st = {"on": False, "off": 0, "pos": -1, "rec": {}}

    def grab(name, li, x):
        if not st["on"]:
            return
        lo, n = st["off"], x.shape[1]
        if lo <= st["pos"] < lo + n:
            st["rec"][(name, li)] = x[0, st["pos"] - lo].detach().float().cpu()

    hs = [H.lm.embed_tokens.register_forward_hook(lambda m, a, o: grab("emb", 0, o))]
    for li, b in enumerate(H.blocks):
        proj = b.self_attn.o_proj if hasattr(b, "self_attn") else b.linear_attn.out_proj
        hs.append(proj.register_forward_hook(lambda m, a, o, li=li: grab("attn", li, o)))
        hs.append(b.mlp.down_proj.register_forward_pre_hook(lambda m, a, li=li: grab("act", li, a[0])))
        hs.append(b.mlp.down_proj.register_forward_hook(lambda m, a, o, li=li: grab("mlp", li, o)))
        hs.append(b.register_forward_hook(lambda m, a, o, li=li: grab("res", li, o if torch.is_tensor(o) else o[0])))
    dev = C.first_device(model)
    R = {k: [] for k in ("emb", "attn", "act", "mlp", "res")}
    meta, err = [], []
    t0 = time.time()
    for n, (u, cs, on) in enumerate(items):
        seq = list(u["prompt_ids"]) + list(u["completion_ids"])
        st.update(on=True, pos=on, rec={})
        with torch.inference_mode():
            cache = None
            for s in range(0, on + 1, 1024):
                st["off"] = s
                o = model(input_ids=torch.tensor([seq[s:min(s + 1024, on + 1)]], device=dev), past_key_values=cache, use_cache=True, logits_to_keep=1)
                cache = o.past_key_values
            del cache, o
        st["on"] = False
        rec = st["rec"]
        R["emb"].append(rec[("emb", 0)].numpy())
        for key in ("attn", "act", "mlp", "res"):
            R[key].append(torch.stack([rec[(key, l)] for l in range(NL)]).numpy())
        res, att, mlp, emb = R["res"][-1], R["attn"][-1], R["mlp"][-1], R["emb"][-1]
        prev = np.vstack([emb[None], res[:-1]])
        e = np.linalg.norm(res - prev - att - mlp, axis=1) / np.linalg.norm(res, axis=1)
        err.append(float(e.max()))
        meta.append({"uid": u["uid"], "label": u["label"], "fold": u["fold"], "group": u["group"], "risk": u.get("risk") or "", "onset": on, "tok": seq[on]})
        if n % 20 == 0 or n == len(items) - 1:
            C.log(f"tagpu {n + 1}/{len(items)} {u['label']} onset {on} max identity error {err[-1]:.2e} {time.time() - t0:.0f}s")
    for h in hs:
        h.remove()
    ref = np.load(A / "hn" / "toolalign" / "hn.npz")
    ru = [str(x) for x in ref["uids"]]
    pos = {m["uid"]: i for i, m in enumerate(meta)}
    if set(ru) != set(pos) or len(ru) != len(pos):
        raise SystemExit(f"unit sets differ: hn {len(ru)}, here {len(pos)}")
    order = np.array([pos[u] for u in ru])
    S = {k: np.stack(v)[order] for k, v in R.items()}
    ores = S["res"].astype(np.float16)
    old = ref["ores"].astype(np.float32)
    d = np.abs(ores.astype(np.float32) - old)
    cor = [np.corrcoef(ores[i].astype(np.float32).ravel(), old[i].ravel())[0, 1] for i in range(len(ru))]
    rel = np.linalg.norm(ores.astype(np.float32) - old, axis=2) / np.linalg.norm(old, axis=2)
    tmp = OUT.with_suffix(".tmp.npz")
    np.savez(tmp, uids=ref["uids"], labels=ref["labels"], folds=ref["folds"], groups=ref["groups"], kinds=ref["kinds"],
             ores=ores, oact=S["act"].astype(np.float16), tok=np.array([meta[i]["tok"] for i in order]),
             on=np.array([meta[i]["onset"] for i in order]), attn=S["attn"], mlp=S["mlp"], emb=S["emb"], res32=S["res"],
             identity_err=np.array(err)[order])
    tmp.rename(OUT)
    C.log(f"ores vs hn/toolalign/hn.npz: max abs diff {d.max():.3g}, max relative diff per (unit, layer) {rel.max():.3g}, "
          f"median {np.median(rel):.3g}, min per-unit correlation {min(cor):.6f}")
    C.log(f"TAGPU_DONE {len(meta)} units, identity error max {max(err):.2e}, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
