"""H1 (project-b GPU 2): which attention heads pull the tool name, from where, and what they write (J-lens).

Units (teacher-forced from telemetry): the "=" of "<function=" right before a tool name; the output at that position predicts
the name token. Transfers: every x15 transfer turn (labels joined later on the PC). Writes: f_detect unexpected writes in
failed episodes and good writes (other tools, passed episodes, up to 150).
At the 8 full-attention layers (3, 7, ..., 31) and 16 query heads, per unit:
  mass[layer, head, segment]   attention of the "=" query summed over context segments (SEGS)
  dla_j[layer, head]           head output read through the J-lens, linearized logit of the chosen name token (mean-centred)
  dla_d[layer, head]           the same on the direct path (no lens): standard direct logit attribution
  top_ids[layer, head, 10]     J-lens top-10 tokens of the head output (Reader.normed readout)
  src_pos/src_w/src_tok/src_seg[2, head, 8]  the 8 most attended context tokens of every head at L23 and L27
Output: probe/m1_heads/units.json + u_<k>.npz
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
sys.path.insert(0, str(R / "probe/jcascade/data"))
import build_topk as bt

LIMIT = int(os.environ.get("H1_LIMIT", "0"))
OUT = R / "probe/m1_heads" / ("smoke" if LIMIT else "full")
FULL = [3, 7, 11, 15, 19, 23, 27, 31]
SRC_LAYERS = [23, 27]
SEGS = ["sink", "policy_transfer", "policy_deny", "policy_other", "format_instr", "tool_desc_transfer", "tools_other", "user_last",
        "user_earlier", "tool_results", "assistant_prev", "header_now", "preamble_now"]
RUNS = {"airline": ["f_detect", "hdetect", "detect", "fitx"] + [f"d7obs_s{i}" for i in range(1, 7)], "retail": ["f_detect", "hdetect"],
        "telecom": ["f_detect"]}
CHUNK = 4096


def log(m):
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def find_sub(seq, sub, start=0, end=None):
    end = len(seq) if end is None else end
    n = len(sub)
    first = sub[0]
    for i in range(start, end - n + 1):
        if seq[i] == first and seq[i:i + n] == sub:
            return i
    return None


def main():
    want = os.environ.get("JC_GPU_UUID")
    if want and want not in str(torch.cuda.get_device_properties(0).uuid):
        log("wrong GPU; exiting")
        return 2
    os.chdir(R / "tau2-bench")
    import jlens
    tok, model = bt.load_model(os.environ["JC_MODEL"], "cuda")
    lens = jlens.JacobianLens.load(os.environ["JC_LENS"])
    Js = {l: lens.jacobians[l].float().cuda() for l in FULL if l in lens.jacobians}
    W = model.get_output_embeddings().weight.detach()
    Wf_mean = W.float().mean(0)
    norm = model.model.norm
    g = 1.0 + norm.weight.detach().float()
    eps = float(getattr(norm, "eps", getattr(norm, "variance_epsilon", 1e-6)))
    blocks = model.model.layers
    attn_cfgs = {id(blocks[l].self_attn.config): blocks[l].self_attn.config for l in FULL}
    attn_cfgs[id(model.config)] = model.config
    base_impl = {k: c._attn_implementation for k, c in attn_cfgs.items()}
    cap = {"on": False, "oin": {}, "attn": {}, "final": None}

    def opre(l):
        def f(m, a):
            if cap["on"]:
                cap["oin"][l] = a[0][0, -1].detach().float()
        return f

    def apost(l):
        def f(m, a, o):
            if cap["on"] and isinstance(o, tuple) and len(o) > 1 and o[1] is not None:
                cap["attn"][l] = o[1][0, :, -1].detach().float()
        return f

    def fpost(m, a, o):
        if cap["on"]:
            h = o if torch.is_tensor(o) else o[0]
            cap["final"] = h[0, -1].detach().float()

    for l in FULL:
        blocks[l].self_attn.o_proj.register_forward_pre_hook(opre(l))
        blocks[l].self_attn.register_forward_hook(apost(l))
    blocks[-1].register_forward_hook(fpost)
    Wo = {l: blocks[l].self_attn.o_proj.weight.detach().float() for l in FULL}
    nh, hd = model.config.num_attention_heads, model.config.head_dim
    ids = lambda s: tok.encode(s, add_special_tokens=False)
    t_lt, t_fn, t_eq = ids("<")[0], tok.convert_tokens_to_ids("function"), ids("=")[0]
    im_start = tok.convert_tokens_to_ids("<|im_start|>")
    tr_resp = ids("<tool_response>")
    role_ids = {ids(w)[0]: w for w in ("system", "user", "assistant")}
    log(f"tokens <={t_lt} function={t_fn} '='={t_eq} im_start={im_start} tool_response={tr_resp} roles={role_ids} attn_impl={base_impl}")
    x15 = {(r["domain"], r["cond"], r["sim"], r["turn"]) for r in json.loads((R / "probe/jcascade/out/x15/rows.json").read_text())}
    OUT.mkdir(parents=True, exist_ok=True)
    units = []
    S = {s: i for i, s in enumerate(SEGS)}

    sys_cache = {}

    def system_segments(block):
        key = hash(tuple(block))
        if key in sys_cache:
            return sys_cache[key]
        seg = np.full(len(block), S["policy_other"], np.int8)
        pieces = [tok.decode([t]) for t in block]
        off = np.cumsum([0] + [len(p) for p in pieces])
        text = "".join(pieces)
        found = {}

        def span(c0, c1, name):
            i0 = int(np.searchsorted(off, c0, side="right")) - 1
            i1 = int(np.searchsorted(off, c1, side="left"))
            seg[max(0, i0):i1] = S[name]
            found[name] = i1 - max(0, i0)

        ts, te = text.find("<tools>"), text.find("</tools>")
        if 0 <= ts < te:
            span(ts, te + len("</tools>"), "tools_other")
            p = text.find('{"type": "function", "function": {"name": "transfer_to_human_agents"', ts, te)
            if p >= 0:
                q = text.find("\n", p)
                span(p, te if q < 0 or q > te else q, "tool_desc_transfer")
            ps = text.find("<policy>", te)
            if ps > te:
                span(te + len("</tools>"), ps, "format_instr")
        for anchor, name in (("You should transfer", "policy_transfer"), ("You should deny", "policy_deny")):
            p = text.find(anchor)
            if p >= 0:
                q = text.find("\n", p)
                span(p, len(text) if q < 0 else q, name)
        sys_cache[key] = (seg, found)
        return seg, found

    def segments(inp, n_ctx):
        seg = np.full(n_ctx, S["policy_other"], np.int8)
        starts = [i for i, x in enumerate(inp) if x == im_start] + [len(inp)]
        users = []
        found = {}
        for k in range(len(starts) - 1):
            a, b = starts[k], starts[k + 1]
            role = role_ids.get(inp[a + 1]) if a + 1 < len(inp) else None
            if role == "system":
                s_seg, found = system_segments(inp[a:b])
                seg[a:b] = s_seg
            elif role == "user":
                if find_sub(inp, tr_resp, a, min(b, a + 8)) is not None:
                    seg[a:b] = S["tool_results"]
                else:
                    users.append((a, b))
                    seg[a:b] = S["user_earlier"]
            elif role == "assistant":
                seg[a:b] = S["assistant_prev"]
        if users:
            a, b = users[-1]
            seg[a:b] = S["user_last"]
        seg[starts[-2]:len(inp)] = S["header_now"]
        seg[len(inp):n_ctx] = S["preamble_now"]
        seg[0] = S["sink"]
        return seg, found

    n_gw = 0
    t0 = time.time()
    for domain, conds in RUNS.items():
        for _, cond, task, sim, tel in bt.episodes(Path("data/simulations/pilot"), Path("data/jlens-telemetry/pilot"), [domain], conds):
            reward = (sim.get("reward_info") or {}).get("reward") or 0
            gold = bt.gold_actions(domain, task)
            for line in tel.open(encoding="utf-8"):
                rec = json.loads(line)
                calls = [{"name": c["name"], "arguments": c.get("arguments")} for c in rec.get("tool_calls") or []]
                ti = int(rec["turn_index"])
                label, bad = bt.label_turn(calls, gold)
                gen = list(rec["generated_ids"])
                inp = list(rec["input_ids"])
                eqs = [k + 2 for k in range(len(gen) - 3) if gen[k] == t_lt and gen[k + 1] == t_fn and gen[k + 2] == t_eq]
                for ci, c in enumerate(calls):
                    if ci >= len(eqs):
                        break
                    name = c["name"]
                    if name.startswith(bt.READ_PREFIXES):
                        continue
                    kinds = [b.split(":")[0] for b in bad if b.endswith(":" + name)]
                    group = None
                    if name == "transfer_to_human_agents":
                        if (domain, cond, sim["id"], ti) in x15:
                            group = "transfer"
                    elif cond == "f_detect":
                        if "unexpected_write" in kinds and reward < 1:
                            group = "BW"
                        elif not kinds and reward >= 1 and n_gw < 150:
                            group = "GW"
                            n_gw += 1
                    if group is None:
                        continue
                    eq = eqs[ci]
                    ctx = inp + gen[:eq]
                    seg, found = segments(inp, len(ctx) + 1)
                    with torch.no_grad():
                        cache = None
                        for s in range(0, len(ctx), CHUNK):
                            cache = model.model(input_ids=torch.tensor([ctx[s:s + CHUNK]], device="cuda"), past_key_values=cache,
                                                use_cache=True).past_key_values
                        for c_ in attn_cfgs.values():
                            c_._attn_implementation = "eager"
                        cap["on"] = True
                        cap["oin"].clear()
                        cap["attn"].clear()
                        try:
                            out = model(input_ids=torch.tensor([[gen[eq]]], device="cuda"), past_key_values=cache, use_cache=True,
                                        logits_to_keep=1)
                        finally:
                            cap["on"] = False
                            for k_, c_ in attn_cfgs.items():
                                c_._attn_implementation = base_impl[k_]
                        target = int(gen[eq + 1])
                        top1 = int(out.logits[0, -1].argmax())
                        fin = cap["final"]
                        rms = torch.sqrt(fin.pow(2).mean() + eps)
                        w_t = (W[target].float() - Wf_mean) * g / rms
                        mass = np.zeros((len(FULL), nh, len(SEGS)), np.float32)
                        mass_tgt = np.zeros((len(FULL), nh, len(SEGS)), np.float32)
                        dla_j = np.zeros((len(FULL), nh), np.float32)
                        dla_d = np.zeros((len(FULL), nh), np.float32)
                        top_ids = np.zeros((len(FULL), nh, 10), np.int32)
                        src = {k_: np.zeros((len(SRC_LAYERS), nh, 8), dt) for k_, dt in
                               (("pos", np.int32), ("w", np.float32), ("tok", np.int32), ("seg", np.int8))}
                        segt = torch.tensor(seg, device="cuda").long()
                        ctx_t = torch.tensor(ctx + [gen[eq]], device="cuda")
                        for li, l in enumerate(FULL):
                            x = cap["oin"][l].view(nh, hd)
                            contrib = torch.einsum("dhk,hk->hd", Wo[l].view(-1, nh, hd), x)
                            moved = contrib @ Js[l].T if l in Js else contrib
                            dla_j[li] = (moved @ w_t).cpu().numpy()
                            dla_d[li] = (contrib @ w_t).cpu().numpy()
                            nz = moved * torch.rsqrt(moved.pow(2).mean(-1, keepdim=True) + eps) * g
                            top_ids[li] = torch.topk(nz.to(W.dtype) @ W.T, 10, -1).indices.int().cpu().numpy()
                            A = cap["attn"].get(l)
                            if A is not None:
                                n = A.shape[-1]
                                oh = torch.nn.functional.one_hot(segt[:n], len(SEGS)).float()
                                mass[li] = (A @ oh).cpu().numpy()
                                is_t = (ctx_t[:n] == target).float()[:, None]
                                mass_tgt[li] = (A @ (oh * is_t)).cpu().numpy()
                                if l in SRC_LAYERS:
                                    si = SRC_LAYERS.index(l)
                                    v, p = torch.topk(A, 8, -1)
                                    src["pos"][si] = p.int().cpu().numpy()
                                    src["w"][si] = v.cpu().numpy()
                                    src["tok"][si] = ctx_t[p].int().cpu().numpy()
                                    src["seg"][si] = segt[p].to(torch.int8).cpu().numpy()
                    k = len(units)
                    np.savez_compressed(OUT / f"u_{k}.npz", mass=mass, mass_tgt=mass_tgt, dla_j=dla_j, dla_d=dla_d, top_ids=top_ids,
                                        src_pos=src["pos"], src_w=src["w"], src_tok=src["tok"], src_seg=src["seg"])
                    units.append({"k": k, "group": group, "domain": domain, "cond": cond, "task": task, "sim": sim["id"], "turn": ti,
                                  "call_index": ci, "name": name, "kinds": kinds, "label": label, "reward": reward, "target": target,
                                  "top1": top1, "reproduced": top1 == target, "ctx_len": len(ctx), "n_attn_layers": len(cap["attn"]),
                                  "found": found, "seg_counts": np.bincount(seg, minlength=len(SEGS)).tolist()})
                    del cache
                    if LIMIT and len(units) <= LIMIT:
                        log(f"unit {k} {group} {domain}/{cond}/{task} t{ti} ctx {len(ctx)} target {tok.decode([target])!r} "
                            f"top1 {tok.decode([top1])!r} attn layers {len(cap['attn'])} found {found} segs {units[-1]['seg_counts']}")
                        log("  mass L27 head-mean " + " ".join(f"{s}={v:.3f}" for s, v in zip(SEGS, mass[FULL.index(27)].mean(0))))
                        log("  target-copy mass L27 head-mean " + " ".join(f"{s}={v:.3f}" for s, v in zip(SEGS, mass_tgt[FULL.index(27)].mean(0)) if v > 0.001))
                        top_h = np.argsort(-dla_d[FULL.index(27)])[:3]
                        for h in top_h:
                            log(f"  L27 h{h} dla_d {dla_d[FULL.index(27), h]:.2f} dla_j {dla_j[FULL.index(27), h]:.2f} J-words "
                                f"{[tok.decode([i]) for i in top_ids[FULL.index(27), h, :6]]} src "
                                f"{[(tok.decode([t]), SEGS[s], round(float(w), 3)) for t, s, w in zip(src['tok'][1, h, :4], src['seg'][1, h, :4], src['w'][1, h, :4])]}")
                        log(f"  dla_d by layer {np.round(dla_d.sum(1), 2).tolist()} logit-top1 check")
                    if len(units) % 20 == 0:
                        (OUT / "units.json").write_text(json.dumps(units), encoding="utf-8")
                        log(f"units {len(units)} ({time.time() - t0:.0f}s) reproduced {sum(u['reproduced'] for u in units)}/{len(units)}")
                    if LIMIT and len(units) >= LIMIT:
                        (OUT / "units.json").write_text(json.dumps(units), encoding="utf-8")
                        log(f"H1_SMOKE_DONE {len(units)}")
                        return 0
    (OUT / "units.json").write_text(json.dumps(units), encoding="utf-8")
    log(f"H1_DONE units {len(units)} {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
