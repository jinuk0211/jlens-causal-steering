"""J-lens readout of the M1 neurons' write directions (server, CPU only): W_U Norm(J_l W_down[:, n]) for each neuron, both signs.
Output: /home/project-b/LJW/tau2-steer/probe/baseline_why/m1_neuron_words.json
"""
import json
import os
import sys
from pathlib import Path

import torch

R = Path("/home/project-b/LJW/tau2-steer")
J = R / "probe/jcascade"
sys.path.insert(0, str(J / "data"))
NEURONS = {
    "unexpected_transfer T-name, failure-only": ["31/1257", "31/2776", "26/1006", "31/1826", "31/826", "31/3377", "30/1922"],
    "unexpected_write T-name, failure-only": ["31/315"],
    "shared by correct and failing calls (T-call)": ["31/844", "31/66", "31/4074", "30/1269"],
    "T-call exception": ["30/856"],
    "wrong_args T-args, most frequent": ["29/121"],
}


def main():
    import jlens
    from jlens_causal.vocab_trigger import load_readout_head
    from safetensors import safe_open
    from transformers import AutoTokenizer

    mp = Path(os.environ["JC_MODEL"])
    tok = AutoTokenizer.from_pretrained(mp)
    head = load_readout_head(mp)
    lens = jlens.JacobianLens.load(os.environ["JC_LENS"])
    U = head.unembed.float()
    index = json.loads((mp / "model.safetensors.index.json").read_text())["weight_map"]
    pre = "model.language_model." if any(k.startswith("model.language_model.") for k in index) else "model."
    tid = tok.encode("transfer", add_special_tokens=False)[0]
    out = {}
    cache = {}
    for group, items in NEURONS.items():
        for item in items:
            layer, n = (int(x) for x in item.split("/"))
            if layer not in cache:
                name = f"{pre}layers.{layer}.mlp.down_proj.weight"
                with safe_open(mp / index[name], framework="pt") as h:
                    cache[layer] = h.get_tensor(name).float()
            d = cache[layer][:, n]
            moved = lens.transport(d[None], layer)[0] if layer in lens.jacobians else d
            lg = (head.norm(moved[None]) @ U.T)[0]
            rel = lg - lg.mean()
            out[item] = {"group": group,
                         "plus": [tok.decode([i]) for i in torch.topk(lg, 15).indices.tolist()],
                         "minus": [tok.decode([i]) for i in torch.topk(-lg, 15).indices.tolist()],
                         "transfer_logit_rel": round(float(rel[tid]), 3),
                         "transfer_rank_plus": int((lg > lg[tid]).sum())}
            print(item, group, out[item]["plus"][:8], "|", out[item]["minus"][:6], "| transfer rank", out[item]["transfer_rank_plus"], flush=True)
    (R / "probe/baseline_why/m1_neuron_words.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
