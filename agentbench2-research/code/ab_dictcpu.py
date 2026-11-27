"""L9 lens check (PLAN.md Log 11-27 13:3x): the J-lens neuron dictionary of ab_ne.mode_dict computed on the CPU from the
safetensors weights (no model forward): score = (W_U * g) @ J_l @ w_j, minus its vocabulary mean, top-10 on both sides;
g = final norm weight (1 + weight for the Qwen3.5 offset norm, as ab_core.Lens). Layers L0..L1 only (others stay zero, so
candidate rules must be restricted to that range); wnorm for every layer. Layers without a Jacobian use the identity.
Usage: python ab_dictcpu.py MODEL REV LENS_PATH OUT_NPZ [L0 L1]"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

TOPK = 10


def tensors(model, rev, names):
    snap = Path(os.environ["HF_HOME"]) / "hub" / f"models--{model.replace('/', '--')}" / "snapshots" / rev
    from safetensors import safe_open
    idx = json.loads((snap / "model.safetensors.index.json").read_text())["weight_map"]
    out = {}
    for n in names:
        if n not in idx:
            continue
        with safe_open(str(snap / idx[n]), framework="pt") as f:
            out[n] = f.get_tensor(n).float()
    return out, idx


def main(model, rev, lens_path, out, l0="8", l1="24"):
    torch.set_num_threads(int(os.environ.get("AB_THREADS", "16")))
    l0, l1 = int(l0), int(l1)
    pre = "model.language_model."
    _, idx = tensors(model, rev, [])
    nl = 1 + max(int(k.split(".layers.")[1].split(".")[0]) for k in idx if ".layers." in k and k.startswith(pre))
    head = "lm_head.weight" if "lm_head.weight" in idx else pre + "embed_tokens.weight"
    T, _ = tensors(model, rev, [head, pre + "norm.weight"])
    g = T[pre + "norm.weight"]
    gw = g if float(g.abs().mean()) > 0.5 else 1 + g
    WUg = T[head] * gw[None, :]
    V = WUg.shape[0]
    import jlens
    J = {int(l): j.float() for l, j in jlens.JacobianLens.load(lens_path).jacobians.items()}
    t0 = time.time()
    W0, _ = tensors(model, rev, [f"{pre}layers.0.mlp.down_proj.weight"])
    NN = W0[f"{pre}layers.0.mlp.down_proj.weight"].shape[1]
    pos_i = np.zeros((nl, NN, TOPK), np.int32)
    neg_i = np.zeros((nl, NN, TOPK), np.int32)
    pos_s = np.zeros((nl, NN, TOPK), np.float16)
    neg_s = np.zeros((nl, NN, TOPK), np.float16)
    wnorm = np.zeros((nl, NN), np.float32)
    with torch.inference_mode():
        for l in range(nl):
            k = f"{pre}layers.{l}.mlp.down_proj.weight"
            W = tensors(model, rev, [k])[0][k]
            wnorm[l] = W.norm(dim=0).numpy()
            if not l0 <= l <= l1:
                continue
            M = WUg @ J[l] if l in J else WUg
            for s in range(0, NN, 1024):
                sc = M @ W[:, s:s + 1024]
                sc = sc - sc.mean(0, keepdim=True)
                tp = torch.topk(sc, TOPK, dim=0)
                tn = torch.topk(-sc, TOPK, dim=0)
                pos_i[l, s:s + 1024], pos_s[l, s:s + 1024] = tp.indices.T.numpy(), tp.values.T.numpy()
                neg_i[l, s:s + 1024], neg_s[l, s:s + 1024] = tn.indices.T.numpy(), tn.values.T.numpy()
                del sc, tp, tn
            del M
            print(f"{time.strftime('%H:%M:%S')} layer {l} ({'J' if l in J else 'identity'}) {time.time() - t0:.0f}s vocab {V}", flush=True)
    np.savez(out, pos_i=pos_i, neg_i=neg_i, pos_s=pos_s, neg_s=neg_s, wnorm=wnorm, jlayers=np.array(sorted(J)), layer_range=np.array([l0, l1]))
    print(f"DICTCPU_DONE {out} layers {l0}-{l1} of {nl}, NN {NN}, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
