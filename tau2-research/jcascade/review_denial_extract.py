"""R3 (project-b GPU 0): decision-point features of denial turns in the same unsteered runs as x15.

A denial turn: no tool call, a refusal phrase in the first 400 characters, no mention of transfer / human agent, and no
completion phrase. Features are extracted exactly like out/x15 (build_topk.Reader, one prefill of the logged input_ids):
J-lens and J++ top-100 at the decision point (all layers), MLP silu(gate)*up L12-31, residual block outputs L0-31.
Output: out/review/denial/rows.json + feat_<k>.npz
"""
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
import torch

R = Path("/home/project-b/LJW/tau2-steer")
sys.path.insert(0, str(R / "probe/topk"))
import build_topk as bt

OUT = R / "probe/jcascade/out/review/denial"
RUNS = {"airline": ["f_detect", "hdetect", "detect", "fitx"] + [f"d7obs_s{i}" for i in range(1, 7)],
        "retail": ["f_detect", "hdetect"], "telecom": ["f_detect"]}
MLP_LAYERS = list(range(12, 32))
DENY = re.compile(r"(I'm sorry|I am sorry|I apologi[sz]e|unfortunately|I'm unable|I am unable|I cannot|I can't|not able to|"
                  r"not possible|against (our|the) policy|not allowed|not eligible|cannot be|does not allow|doesn't allow)", re.I)
DONE = re.compile(r"successfully|has been (booked|cancelled|canceled|updated|modified|changed|processed)|is now (booked|confirmed)", re.I)
XFER = re.compile(r"transfer|human agent|representative|supervisor|escalat", re.I)


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def main():
    want = os.environ.get("JC_GPU_UUID")
    if want and want not in str(torch.cuda.get_device_properties(0).uuid):
        log("wrong GPU; exiting")
        return 2
    os.chdir(R / "tau2-bench")
    snap = "/home/project-b/LJW/.cache/huggingface/hub/models--neuronpedia--jacobian-lens/snapshots/d2527c3cdbaa60dd4b65cbca1604921f044e989a"
    lens_spec = [f"jlens={(R / 'lens_path.txt').read_text().strip()}", f"jpp={snap}/qwen3.5-4b/jpp/Salesforce-wikitext/Qwen3.5-4B_jpp_lens.pt"]
    tok, model = bt.load_model(os.environ["JC_MODEL"], "cuda")
    reader = bt.Reader(model, bt.load_lenses(lens_spec), offload=False)
    blocks = model.model.layers
    cap = {"mlp": {}, "res": {}}

    def mlp_pre(layer):
        def f(module, args):
            cap["mlp"][layer] = args[0][0, -1].detach().float().cpu()
        return f

    def blk_post(layer):
        def f(module, args, out):
            h = out if torch.is_tensor(out) else out[0]
            cap["res"][layer] = h[0, -1].detach().float().cpu()
        return f

    hooks = [blocks[l].mlp.down_proj.register_forward_pre_hook(mlp_pre(l)) for l in MLP_LAYERS]
    hooks += [b.register_forward_hook(blk_post(l)) for l, b in enumerate(blocks)]
    OUT.mkdir(parents=True, exist_ok=True)
    rows, n_ep, t0 = [], 0, time.time()
    for domain, conds in RUNS.items():
        for domain_, cond, task, sim, tel in bt.episodes(Path("data/simulations/pilot"), Path("data/jlens-telemetry/pilot"), [domain], conds):
            n_ep += 1
            reward = (sim.get("reward_info") or {}).get("reward")
            records = sorted((json.loads(line) for line in tel.open(encoding="utf-8")), key=lambda r: r["turn_index"])
            xfer_turns = [int(r["turn_index"]) for r in records if any(c["name"] == "transfer_to_human_agents" for c in r["tool_calls"])]
            for rec in records:
                text = rec.get("generated_text") or ""
                if rec["tool_calls"] or not DENY.search(text[:400]) or DONE.search(text) or XFER.search(text):
                    continue
                ti = int(rec["turn_index"])
                inp = list(rec["input_ids"])
                cap["mlp"].clear()
                cap["res"].clear()
                with reader.hooks():
                    out = reader.turn(inp, [len(inp) - 1], [bt.SEG["decision"]], 4096)
                k = len(rows)
                np.savez_compressed(OUT / f"feat_{k}.npz",
                                    dec_ids_jlens=out["dec_ids_jlens"][0].numpy(), dec_val_jlens=out["dec_val_jlens"][0].numpy(),
                                    dec_ids_jpp=out["dec_ids_jpp"][0].numpy(), dec_val_jpp=out["dec_val_jpp"][0].numpy(),
                                    mlp=torch.stack([cap["mlp"][l] for l in MLP_LAYERS]).half().numpy(),
                                    res=torch.stack([cap["res"][l] for l in range(len(blocks))]).half().numpy())
                rows.append({"k": k, "domain": domain, "cond": cond, "task": task, "sim": sim["id"], "turn": ti, "reward": reward,
                             "ep_pass": (reward or 0) >= 1, "xfer_turns_in_episode": xfer_turns, "text": text[:400]})
            if n_ep % 25 == 0:
                (OUT / "rows.json").write_text(json.dumps(rows, indent=0), encoding="utf-8")
                log(f"episodes {n_ep}, denial rows {len(rows)}, {time.time() - t0:.0f}s")
    (OUT / "rows.json").write_text(json.dumps(rows, indent=0), encoding="utf-8")
    for h in hooks:
        h.remove()
    log(f"DENIAL_DONE episodes {n_ep} rows {len(rows)} {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
