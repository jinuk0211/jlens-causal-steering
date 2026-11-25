"""X15 (project-b GPU 0): decision-point features of every transfer turn in the unsteered Qwen3.5-4B runs.

Runs (agent = the same Qwen3.5-4B, no steering): f_detect (Haiku user, all domains), hdetect (Haiku user, airline + retail),
detect (4B user, airline only; retail detect is excluded because of the zip-auth tool bug), d7obs_s1..6 and fitx (qwen user, airline).
Per transfer turn (a turn whose calls include transfer_to_human_agents), from one prefill of the logged input_ids:
  J-lens and J++ readout at the decision point, all 32 layers, top-100 ids + logits  (build_topk.Reader, same as stage 0)
  MLP activation silu(gate)*up at the decision point, L12-31                         (stage-1 features)
  block output (residual) at the decision point, all 32 layers                        (probe / DoM baselines)
Labels as stage 0: bad = unexpected_transfer in a failed episode, good = transfer in a passed episode; retail passes that are
provisional (NL judge deferred) are flagged.
Output: out/x15/rows.json + out/x15/feat_<k>.npz
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

R = Path("/home/project-b/LJW/tau2-steer")
sys.path.insert(0, str(R / "probe/topk"))
import build_topk as bt

OUT = R / "probe/jcascade/out/x15"
RUNS = {"airline": ["f_detect", "hdetect", "detect", "fitx"] + [f"d7obs_s{i}" for i in range(1, 7)],
        "retail": ["f_detect", "hdetect"], "telecom": ["f_detect"]}
MLP_LAYERS = list(range(12, 32))


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def main():
    want = os.environ.get("JC_GPU_UUID")
    uuid = str(torch.cuda.get_device_properties(0).uuid)
    if want and want not in uuid:
        log(f"wrong GPU {uuid}; exiting")
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
    rows = []
    done = set()
    idx_path = OUT / "rows.json"
    if idx_path.exists():
        rows = json.loads(idx_path.read_text(encoding="utf-8"))
        done = {(r["domain"], r["cond"], r["sim"], r["turn"]) for r in rows}
    t_all = time.time()
    n_ep = 0
    for domain, conds in RUNS.items():
        for domain_, cond, task, sim, tel in bt.episodes(Path("data/simulations/pilot"), Path("data/jlens-telemetry/pilot"), [domain], conds):
            n_ep += 1
            reward_info = sim.get("reward_info") or {}
            reward = reward_info.get("reward")
            provisional = "nl_assertions_deferred" in json.dumps(reward_info, default=str) and (reward or 0) >= 1
            gold = bt.gold_actions(domain, task)
            records = sorted((json.loads(line) for line in tel.open(encoding="utf-8")), key=lambda r: r["turn_index"])
            for rec in records:
                calls = [{"name": c["name"], "arguments": c.get("arguments")} for c in rec["tool_calls"]]
                if not any(c["name"] == "transfer_to_human_agents" for c in calls):
                    continue
                ti = int(rec["turn_index"])
                if (domain, cond, sim["id"], ti) in done:
                    continue
                label, bad = bt.label_turn(calls, gold)
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
                rows.append({"k": k, "domain": domain, "cond": cond, "task": task, "sim": sim["id"], "turn": ti,
                             "label": label, "bad": bad, "reward": reward, "ep_pass": (reward or 0) >= 1, "provisional": provisional,
                             "n_turns": len(records), "prompt_tokens": len(inp), "text": (rec.get("generated_text") or "")[:300]})
                idx_path.write_text(json.dumps(rows, indent=0), encoding="utf-8")
            if n_ep % 20 == 0:
                log(f"episodes {n_ep}, transfer rows {len(rows)}, {time.time() - t_all:.0f}s")
    for h in hooks:
        h.remove()
    log(f"X15_DONE episodes {n_ep} rows {len(rows)} {time.time() - t_all:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
