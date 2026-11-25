"""C-LOOP C1 tool: exact per-source attribution through the 24 linear-attention (GatedDeltaNet) layers at the decision position.
GPU 0 only. The gated delta rule is linear in the values once keys, gates and betas are fixed:
S_t = A_t S_{t-1} + beta_t k_t v_t^T, A_t = exp(g_t) (I - beta_t k_t k_t^T) (symmetric), so o_t = S_t^T q_t = sum_s w_s v_s with
w_s = beta_s k_s^T A_{s+1} ... A_t q_t, computed by the backward recursion u <- A_s u. q and k are l2-normalized, q is scaled by
1/sqrt(dk), and each of the 16 key heads serves 2 of the 32 value heads. The gated RMSNorm at the decision position is frozen at its
actual scale, y_h = w_norm * o_h / rms(o_h) * silu(z_h), so every source's share of y_h is exact. Per source position s (after the
causal conv, i.e. a 4-token window ending at s): direct effect (share . W_out^T d, d from C0a) and total effect (share . dm/dy from
C0a hgrad). Check: |sum_s w_s v_s - o_t| / |o_t| per layer.
Usage: env C0_UNITS, C0_OUT (the C0a output dir holding n_<k>.npz), LS_KEYS (comma list of k) or LS_LIMIT. Output <C0_OUT>/ls_<k>.npz"""
import json
import math
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

R = Path("/home/project-b/LJW/tau2-steer")
sys.path.insert(0, str(R / "probe/topk"))
sys.path.insert(0, str(R / "probe/circuit"))
import build_topk as bt
from c0_graph import ROLE, role_codes

OUT = Path(os.environ.get("C0_OUT", str(R / "probe/circuit/out/c0")))
UNITS = Path(os.environ.get("C0_UNITS", str(R / "probe/m1/out/units.json")))
KEYS = [int(x) for x in os.environ.get("LS_KEYS", "").split(",") if x]
LIMIT = int(os.environ.get("LS_LIMIT", "0"))
CHUNK = 4096
TOP = 20


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def l2n(x):
    return x * torch.rsqrt((x * x).sum(-1, keepdim=True) + 1e-6)


def main():
    uuid = str(torch.cuda.get_device_properties(0).uuid)
    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID" or "c27bc2d7" not in uuid:
        log(f"wrong GPU {uuid}; exiting")
        return 2
    os.chdir(R / "tau2-bench")
    torch.set_grad_enabled(False)
    import transformers.models.qwen3_5.modeling_qwen3_5 as mq
    rec = {"on": False, "l": None, "pre": defaultdict(list), "dec": {}, "z": {}}
    orig_chunk = mq.torch_chunk_gated_delta_rule
    orig_rec = mq.torch_recurrent_gated_delta_rule

    def chunk_rec(query, key, value, g=None, beta=None, initial_state=None, **kw):
        out = orig_chunk(query, key, value, g=g, beta=beta, initial_state=None if initial_state is None else initial_state.clone(), **kw)
        if rec["on"]:
            rec["pre"][rec["l"]].append((l2n(key.float())[0, :, ::2].to(torch.bfloat16).cpu(), value[0].to(torch.bfloat16).cpu(),
                                         beta[0].float().cpu(), g[0].float().cpu()))
        return out

    def rec_rec(query, key, value, g=None, beta=None, initial_state=None, **kw):
        out = orig_rec(query, key, value, g=g, beta=beta, initial_state=initial_state, **kw)
        if rec["on"]:
            dk = query.shape[-1]
            rec["dec"][rec["l"]] = dict(q=l2n(query.float())[0, -1] / math.sqrt(dk), k=l2n(key.float())[0, -1], v=value.float()[0, -1],
                                        beta=beta.float()[0, -1], g=g.float()[0, -1], o=out[0].float()[0, -1])
        return out

    mq.torch_chunk_gated_delta_rule = chunk_rec
    mq.torch_recurrent_gated_delta_rule = rec_rec
    tok, model = bt.load_model(os.environ["JC_MODEL"], "cuda")
    blocks = model.model.layers
    lin = [i for i, b in enumerate(blocks) if hasattr(b, "linear_attn")]

    def pre_lin(i):
        def f(module, args, kwargs):
            rec["l"] = i
        return f

    def pre_norm(i):
        def f(module, args):
            if rec["on"] and rec.get("decision"):
                rec["z"][i] = args[1].float()
        return f

    for i in lin:
        blocks[i].linear_attn.register_forward_pre_hook(pre_lin(i), with_kwargs=True)
        blocks[i].linear_attn.norm.register_forward_pre_hook(pre_norm(i))
    units = {u["k"]: u for u in json.loads(UNITS.read_text(encoding="utf-8"))}
    rows = [r for r in json.loads((OUT / "units.json").read_text(encoding="utf-8")) if r["k"] in units]
    if KEYS:
        rows = [r for r in rows if r["k"] in KEYS]
    rows = [r for r in rows if not (OUT / f"ls_{r['k']}.npz").is_file()]
    if LIMIT:
        rows = rows[:LIMIT]
    want = {(r["cond"], r["sim"], r["turn"]): r["k"] for r in rows}
    seqs = {}
    for domain in ("airline", "retail", "telecom"):
        conds = sorted({r["cond"] for r in rows if r["domain"] == domain})
        if not conds:
            continue
        for domain_, cond, task, sim, tel in bt.episodes(Path("data/simulations/pilot"), Path("data/jlens-telemetry/pilot"), [domain], conds):
            for line in tel.open(encoding="utf-8"):
                rr = json.loads(line)
                key = (cond, sim["id"], int(rr["turn_index"]))
                if key in want:
                    seqs[want[key]] = (list(rr["input_ids"]), list(rr["generated_ids"]))
    log(f"{len(rows)} units to do")
    t0 = time.time()
    for n, r in enumerate(rows):
        if r["k"] not in seqs:
            continue
        inp, gen = seqs[r["k"]]
        d = units[r["k"]]["d"]
        seq = inp + gen[:d]
        T = len(seq)
        codes = role_codes(inp, d, tok)[:T]
        z0 = np.load(OUT / f"n_{r['k']}.npz")
        dvec = torch.tensor(z0["dvec"], device="cuda")
        hgrad = torch.tensor(z0["hgrad"].astype(np.float32), device="cuda")
        rec["pre"].clear()
        rec["dec"].clear()
        rec["z"].clear()
        rec["on"] = True
        rec["decision"] = False
        cache = None
        for s in range(0, T - 1, CHUNK):
            cache = model.model(input_ids=torch.tensor([seq[s:min(s + CHUNK, T - 1)]], device="cuda"), past_key_values=cache,
                                use_cache=True).past_key_values
        rec["decision"] = True
        model.model(input_ids=torch.tensor([[seq[-1]]], device="cuda"), past_key_values=cache, use_cache=True)
        rec["on"] = False
        rec["decision"] = False
        del cache
        nl = len(lin)
        K = torch.stack([torch.cat([c[0] for c in rec["pre"][i]], 0) for i in lin]).to("cuda")
        Bt = torch.stack([torch.cat([c[2] for c in rec["pre"][i]], 0) for i in lin]).to("cuda")
        Gt = torch.stack([torch.cat([c[3] for c in rec["pre"][i]], 0) for i in lin]).to("cuda")
        u = torch.stack([rec["dec"][i]["q"] for i in lin])
        W = torch.zeros(nl, T, 32, device="cuda")
        kd_ = torch.stack([rec["dec"][i]["k"] for i in lin])
        bd = torch.stack([rec["dec"][i]["beta"] for i in lin])
        gd = torch.stack([rec["dec"][i]["g"] for i in lin])
        kdot = (kd_ * u).sum(-1)
        W[:, T - 1] = bd * kdot
        u = torch.exp(gd)[..., None] * (u - (bd * kdot)[..., None] * kd_)
        for s in range(T - 2, -1, -1):
            ks = K[:, s].float().repeat_interleave(2, dim=1)
            kdot = (ks * u).sum(-1)
            bs = Bt[:, s]
            W[:, s] = bs * kdot
            u = torch.exp(Gt[:, s])[..., None] * (u - (bs * kdot)[..., None] * ks)
        del K
        tot = np.zeros((nl, T), np.float16)
        dirc = np.zeros((nl, T), np.float16)
        role_tot = np.zeros((nl, 32, len(ROLE)), np.float32)
        role_dir = np.zeros((nl, 32, len(ROLE)), np.float32)
        top_i = np.zeros((nl, TOP), np.int32)
        top_v = np.zeros((nl, TOP), np.float32)
        err = np.zeros(nl, np.float32)
        codes_t = torch.tensor(codes.astype(np.int64), device="cuda")
        for j, i in enumerate(lin):
            V = torch.cat([c[1] for c in rec["pre"][i]], 0).to("cuda")
            Vall = torch.cat([V.float(), rec["dec"][i]["v"][None]], 0)
            o = rec["dec"][i]["o"]
            recon = (W[j][..., None] * Vall).sum(0)
            err[j] = float((recon - o).norm() / o.norm().clamp_min(1e-6))
            mod = blocks[i].linear_attn
            rms = torch.sqrt((o ** 2).mean(-1, keepdim=True) + mod.norm.variance_epsilon)
            scale = mod.norm.weight.float()[None] * torch.nn.functional.silu(rec["z"][i]) / rms
            Wo = mod.out_proj.weight
            u_out = (Wo.t() @ dvec.to(Wo.dtype)).float().view(32, 128)
            e_dir = scale * u_out
            e_tot = scale * hgrad[i].view(32, 128)
            pd = W[j] * (Vall * e_dir[None]).sum(-1)
            pt = W[j] * (Vall * e_tot[None]).sum(-1)
            tot[j] = pt.sum(1).half().cpu().numpy()
            dirc[j] = pd.sum(1).half().cpu().numpy()
            role_tot[j] = torch.zeros(32, len(ROLE), device="cuda").index_add_(1, codes_t, pt.t()).cpu().numpy()
            role_dir[j] = torch.zeros(32, len(ROLE), device="cuda").index_add_(1, codes_t, pd.t()).cpu().numpy()
            s_ = pt.sum(1)
            tv, ti = s_.abs().topk(min(TOP, T))
            top_i[j, :len(ti)] = ti.cpu().numpy()
            top_v[j, :len(ti)] = s_[ti].cpu().numpy()
            del V, Vall
        np.savez(OUT / f"ls_{r['k']}.npz", lin_layers=np.array(lin), tot=tot, dir=dirc, role_tot=role_tot, role_dir=role_dir,
                 top_i=top_i, top_v=top_v, err=err, hdla_check=z0["hdla"][lin], hgxa_check=z0["hgxa"][lin])
        hd_err = float(np.abs(role_dir.sum((2)) - z0["hdla"][lin]).max())
        hg_err = float(np.abs(role_tot.sum((2)) - z0["hgxa"][lin]).max())
        log(f"{n + 1}/{len(rows)} k={r['k']} T={T}: recon err max {err.max():.4f}; head DLA |diff| max {hd_err:.3f}; "
            f"head gxa |diff| max {hg_err:.3f} ({time.time() - t0:.0f}s)")
        rec["pre"].clear()
        torch.cuda.empty_cache()
    log("LS_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
