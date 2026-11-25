"""Neuron activation flow over whole trajectories (neuron-explorer style), ToolAlign-4B units or any seqs json with
ids / onset / pos. One teacher-forced forward pass per unit over the stored trajectory (prompt + response up to the
tool-name position); no environment is needed.
Activations = MLP down_proj inputs, all 32 x 9216 neurons, normalised like neuron-explorer: a / pos_scale when a > 0 and
a / |neg_scale| when a < 0 (act_scale = each neuron's largest + and - value over 10k web-text tokens), so |v| >= 1 means
stronger than anything it did on web text.
Saved per unit (f_{n}.npz):
  flow_idx [T, 32, K] int16, flow_val [T, 32, K] float16: the K strongest neurons by |v| at every token and layer
    (sign kept), T = every position 1 .. pos (position 0, the attention sink, is left as zeros)
  mx, mn [regions, 32, 9216] float16: raw max / min of every neuron over the regions
    input_all (1 .. onset-1), input64, onset, early64, last64 (pre_len >= 70), scaffold; have [regions]
Also 10 risk phrases and 10 neutral agent phrases (fixed before looking at any unit): max / min of every neuron.
Usage: python ta_neuron_flow.py SEQS_JSON ACT_SCALE_NPZ OUT_DIR   (env TJ_FLOW_K, TJ_DTYPE, TJ_ALLOW_PIDS)"""
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
REGIONS = ["input_all", "input64", "onset", "early64", "last64", "scaffold"]
K = int(os.environ.get("TJ_FLOW_K", "16"))
CHUNK = 1024
RISK = [
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
NEUTRAL = [
    "I will write an internal log entry that summarizes today's review.",
    "Let me check the project schedule and list the open tasks for the team.",
    "I'm going to update the meeting notes with the decisions we made.",
    "I'll send the weekly status report to my manager as usual.",
    "I will email the vendor to confirm the delivery date.",
    "With my normal access, I will look up the order history for this customer.",
    "I need to file this report in the shared team folder.",
    "Send the agenda for tomorrow's meeting to the attendees.",
    "I'll turn on the reminder so the task is not forgotten.",
    "Ask the help desk to reset the password for the new account.",
]


def main():
    seqs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    sc = np.load(sys.argv[2])
    out = Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    vis = (os.environ.get("CUDA_VISIBLE_DEVICES") or "0").split(",")[0]
    uuid = os.popen(f"nvidia-smi --query-gpu=uuid --format=csv,noheader -i {vis}").read().strip()
    allow = set((os.environ.get("TJ_ALLOW_PIDS") or "").split(","))
    busy = [l for l in os.popen("nvidia-smi --query-compute-apps=pid,gpu_uuid --format=csv,noheader").read().strip().splitlines()
            if uuid and uuid in l and l.split(",")[0].strip() not in allow]
    if not uuid or busy:
        raise SystemExit(f"GPU guard: GPU {vis} missing or busy {busy}")
    C.patch_gdn()
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(C.MODEL, revision=C.REV, dtype=getattr(torch, os.environ.get("TJ_DTYPE", "float32"))).cuda()
    model.model.visual = None
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    torch.cuda.empty_cache()
    blocks = (model.model.language_model if hasattr(model.model, "language_model") else model.model).layers
    nl, nn = len(blocks), blocks[0].mlp.down_proj.in_features
    ps = torch.tensor(np.maximum(sc["pos"], 1e-2), dtype=torch.float32, device="cuda")
    ng = torch.tensor(np.maximum(np.abs(sc["neg"]), 1e-2), dtype=torch.float32, device="cuda")
    scaf = tok.encode(SCAF, add_special_tokens=False)
    cur = {}

    def hook(i):
        def f(mod, args):
            st = cur.get("st")
            if st is None:
                return
            x = args[0][0].float()
            s0, e0 = cur["s0"], cur["s0"] + x.shape[0]
            if st["flow"]:
                v = torch.where(x > 0, x / ps[i], x / ng[i])
                val, idx = v.abs().topk(K, dim=-1)
                sv = torch.gather(v, 1, idx)
                lo = max(s0, 1)
                st["fi"][lo:e0, i] = idx[lo - s0:].to(torch.int16).cpu()
                st["fv"][lo:e0, i] = sv[lo - s0:].half().cpu()
            for ri, (a, b) in enumerate(st["reg"]):
                a2, b2 = max(a, s0), min(b, e0)
                if a2 < b2:
                    seg = x[a2 - s0:b2 - s0]
                    st["mx"][ri, i] = torch.maximum(st["mx"][ri, i], seg.max(0).values)
                    st["mn"][ri, i] = torch.minimum(st["mn"][ri, i], seg.min(0).values)
        return f
    hs = [b.mlp.down_proj.register_forward_pre_hook(hook(i)) for i, b in enumerate(blocks)]

    def run(ids, reg, flow):
        T = len(ids)
        st = {"reg": reg, "flow": flow,
              "mx": torch.full((len(reg), nl, nn), -torch.inf, device="cuda"), "mn": torch.full((len(reg), nl, nn), torch.inf, device="cuda")}
        if flow:
            st["fi"] = torch.zeros((T, nl, K), dtype=torch.int16)
            st["fv"] = torch.zeros((T, nl, K), dtype=torch.float16)
        cache = None
        with torch.inference_mode():
            for s0 in range(0, T, CHUNK):
                cur.update(st=st, s0=s0)
                o = model(input_ids=torch.tensor([ids[s0:s0 + CHUNK]], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
                cache = o.past_key_values
        cur["st"] = None
        del cache
        return st

    t0 = time.time()
    rows = []
    done = {p.stem for p in out.glob("f_*.npz")}
    for n, u in enumerate(seqs):
        name = f"f_{n}"
        ids = u["ids"][:u["pos"] + 1]
        on, pos = u["onset"], u["pos"]
        tail = ids[pos + 1 - len(scaf):pos + 1]
        ss = pos + 1 - len(scaf) if tail == scaf else pos
        reg = {"input_all": (1, on), "input64": (max(1, on - 64), on), "onset": (on, on + 1),
               "early64": (on + 1, min(on + 65, ss)), "last64": (ss - 64, ss) if ss - on >= 70 else (0, 0),
               "scaffold": (ss, pos + 1)}
        rows.append({"idx": n, "key": u.get("key"), "label": u.get("label"), "risk": u.get("risk"), "domain": u.get("domain"),
                     "type": u.get("type"), "tool": u.get("tool"), "n4": u.get("n4"), "onset": on, "pos": pos, "scaf_start": ss,
                     "pre_len": ss - on, "regions": {k: max(0, b - a) for k, (a, b) in reg.items()}})
        if name in done:
            continue
        st = run(ids, [reg[r] for r in REGIONS], True)
        have = np.array([reg[r][1] > reg[r][0] for r in REGIONS])
        mx = torch.where(torch.isfinite(st["mx"]), st["mx"], 0).half().cpu().numpy()
        mn = torch.where(torch.isfinite(st["mn"]), st["mn"], 0).half().cpu().numpy()
        np.savez_compressed(out / f"{name}.npz", flow_idx=st["fi"].numpy(), flow_val=st["fv"].numpy(), mx=mx, mn=mn, have=have)
        del st
        torch.cuda.empty_cache()
        if n % 10 == 0:
            C.log(f"{n + 1}/{len(seqs)} units, {len(ids)} tokens, {time.time() - t0:.0f}s")
    (out / "units.json").write_text(json.dumps(rows), encoding="utf-8")
    P = np.zeros((len(RISK) + len(NEUTRAL), 2, nl, nn), np.float32)
    for k, ph in enumerate(RISK + NEUTRAL):
        ids = tok.encode(ph, add_special_tokens=False)
        st = run(ids, [(1, len(ids))], False)
        P[k, 0], P[k, 1] = st["mx"][0].cpu().numpy(), st["mn"][0].cpu().numpy()
    np.savez_compressed(out / "phrases.npz", act=P, phrases=np.array(RISK + NEUTRAL), n_risk=len(RISK))
    for h in hs:
        h.remove()
    C.log(f"NEURON_FLOW_DONE {len(seqs)}")


if __name__ == "__main__":
    main()
