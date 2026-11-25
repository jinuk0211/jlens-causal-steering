"""C-LOOP C0a (PLAN.md "C-LOOP"): attribution-graph nodes at the decision position, symmetric contrast. GPU 0 only.
Per unit (probe/m1/out/units.json): m = logit(c) - logit(g), g by the symmetric rule (tool-name start: best other tool-name first
token; otherwise best top-64 non-variant alnum token). One cached-prefix grad step (last 4 tokens, eager attention).
Saved: MLP neuron act and grad x act (32 x 9216); attention head inputs, head DLA and head grad x act (full attention 16 x 256,
linear attention 32 x 128); exact per-source DLA for the 8 full-attention layers from the attention weights, the per-head output
gate and the cached values; role-grouped source DLA. Output probe/circuit/out/c0/units.json + n_<k>.npz."""
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

OUT = Path(os.environ.get("C0_OUT", str(R / "probe/circuit/out/c0")))
UNITS = Path(os.environ.get("C0_UNITS", str(R / "probe/m1/out/units.json")))
CHUNK = 4096
KK = 4
LIMIT = int(os.environ.get("C0_LIMIT", "0"))
ONLY = os.environ.get("C0_ONLY", "")
ROLE = {"system": 0, "user_earlier": 1, "user_last": 2, "tool_earlier": 3, "tool_last": 4, "assistant_earlier": 5,
        "header": 6, "gen": 7, "other": 8}
CONCEPT = ("transfer", "escalat", "connect", "refer", "redirect", "forward", "route", "hand", "pass", "human", "supervisor",
           "manager", "representative", "specialist")
V2 = os.environ.get("C0_RULE", "v2") == "v2"


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def is_read(name):
    return name.startswith(bt.READ_PREFIXES)


def role_codes(inp, n_gen, tok):
    im = tok.convert_tokens_to_ids("<|im_start|>")
    tr = tok.convert_tokens_to_ids("<tool_response>")
    names = {tok.encode(w, add_special_tokens=False)[0]: w for w in ("system", "user", "assistant")}
    starts = [i for i, x in enumerate(inp) if x == im]
    blocks = []
    for k, a in enumerate(starts):
        b = starts[k + 1] if k + 1 < len(starts) else len(inp)
        role = names.get(inp[a + 1], "other") if a + 1 < len(inp) else "other"
        if role == "user" and tr in inp[a:a + 8]:
            role = "tool"
        blocks.append([role, a, b])
    codes = np.full(len(inp) + n_gen, ROLE["other"], np.int8)
    last = {r: max((i for i, bl in enumerate(blocks[:-1]) if bl[0] == r), default=None) for r in ("user", "tool")}
    for i, (role, a, b) in enumerate(blocks):
        if i == len(blocks) - 1:
            codes[a:b] = ROLE["header"]
        elif role in ("user", "tool"):
            codes[a:b] = ROLE[f"{role}_last" if i == last[role] else f"{role}_earlier"]
        elif role == "assistant":
            codes[a:b] = ROLE["assistant_earlier"]
        elif role == "system":
            codes[a:b] = ROLE["system"]
    codes[len(inp):] = ROLE["gen"]
    return codes


def main():
    uuid = str(torch.cuda.get_device_properties(0).uuid)
    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID" or "c27bc2d7" not in uuid:
        log(f"wrong GPU {uuid}; exiting")
        return 2
    os.chdir(R / "tau2-bench")
    import transformers.models.qwen3_5.modeling_qwen3_5 as mq
    orig_chunk = mq.torch_chunk_gated_delta_rule

    def chunk_clone(*a, initial_state=None, **kw):
        return orig_chunk(*a, initial_state=None if initial_state is None else initial_state.clone(), **kw)

    mq.torch_chunk_gated_delta_rule = chunk_clone
    tok, model = bt.load_model(os.environ["JC_MODEL"], "cuda")
    for p in model.parameters():
        p.requires_grad_(False)
    torch.set_grad_enabled(False)
    cfg = model.config
    blocks = model.model.layers
    nl = len(blocks)
    full = [i for i, b in enumerate(blocks) if hasattr(b, "self_attn")]
    W_U = model.lm_head.weight
    fnorm = model.model.norm
    cap = {}

    def pre_down(i):
        def f(module, args):
            if cap.get("on"):
                x = args[0]
                if x.requires_grad:
                    x.retain_grad()
                cap.setdefault("act", {})[i] = x
        return f

    def pre_oproj(i):
        def f(module, args):
            if cap.get("on"):
                x = args[0]
                if x.requires_grad:
                    x.retain_grad()
                cap.setdefault("hin", {})[i] = x
        return f

    def pre_attn(i):
        def f(module, args, kwargs):
            if cap.get("on"):
                h = args[0] if args else kwargs.get("hidden_states")
                cap.setdefault("ain", {})[i] = h.detach()
        return f

    def post_attn(i):
        def f(module, args, out):
            if cap.get("on") and isinstance(out, tuple) and len(out) > 1 and out[1] is not None:
                cap.setdefault("aw", {})[i] = out[1].detach()
        return f

    def pre_blk(i):
        def f(module, args, kwargs):
            if cap.get("on"):
                h = args[0] if args else kwargs.get("hidden_states")
                cap.setdefault("bin", {})[i] = h.detach()
        return f

    def post_blk(i):
        def f(module, args, out):
            if cap.get("on"):
                cap.setdefault("bout", {})[i] = (out if torch.is_tensor(out) else out[0]).detach()
        return f

    def post_mlp(i):
        def f(module, args, out):
            if cap.get("on"):
                cap.setdefault("mout", {})[i] = out.detach()
        return f

    def post_emb(module, args, out):
        if cap.get("on"):
            out.requires_grad_(True)
            cap["emb"] = out
        return out

    for i, b in enumerate(blocks):
        b.mlp.down_proj.register_forward_pre_hook(pre_down(i))
        b.register_forward_pre_hook(pre_blk(i), with_kwargs=True)
        b.register_forward_hook(post_blk(i))
        b.mlp.register_forward_hook(post_mlp(i))
        if i in full:
            b.self_attn.o_proj.register_forward_pre_hook(pre_oproj(i))
            b.self_attn.register_forward_pre_hook(pre_attn(i), with_kwargs=True)
            b.self_attn.register_forward_hook(post_attn(i))
        else:
            b.linear_attn.out_proj.register_forward_pre_hook(pre_oproj(i))
    model.model.embed_tokens.register_forward_hook(post_emb)

    def cache_values(cache, li):
        lay = cache.layers[li] if hasattr(cache, "layers") else None
        if lay is not None and hasattr(lay, "values"):
            return lay.values
        return cache.value_cache[li]

    def set_attn(impl):
        cfg._attn_implementation = impl
        for i in full:
            blocks[i].self_attn.config._attn_implementation = impl

    def pick_g(logits, c, rule, cands):
        if rule == "tool_first" and cands:
            cand = torch.tensor(cands, device=logits.device)
            return int(cand[logits[cand].argmax()])
        if rule == "runnerup":
            masked = logits.clone()
            masked[c] = -1e9
            return int(masked.argmax())
        craw = tok.decode([c]).strip().lower()
        cs = re.sub(r"[^0-9a-z]", "", craw) if V2 else craw
        need_an = any(ch.isalnum() for ch in craw)
        for t in torch.topk(logits, 64).indices.tolist():
            if t == c:
                continue
            raw = tok.decode([t]).strip().lower()
            if V2 and ((raw.startswith("<") and raw.endswith(">")) or (craw.isascii() and not raw.isascii())):
                continue
            s = re.sub(r"[^0-9a-z]", "", raw) if V2 else raw
            if not raw or (need_an and not any(ch.isalnum() for ch in raw)) or (V2 and need_an and not s):
                continue
            if cs and (s == cs or s.startswith(cs) or cs.startswith(s)):
                continue
            if rule == "concept" and (not raw.isascii() or not any(ch.isalpha() for ch in raw)
                                      or any(s.startswith(w) or (len(s) >= 3 and w.startswith(s)) for w in CONCEPT)
                                      or len(os.path.commonprefix([s, cs])) >= 4):
                continue
            return int(t)
        masked = logits.clone()
        masked[c] = -1e9
        return int(masked.argmax())

    def measure(seq, c, rule, cands, g_gold):
        cap.clear()
        cache = None
        kk = min(KK, len(seq) - 1)
        set_attn("sdpa")
        with torch.no_grad():
            for s in range(0, len(seq) - kk, CHUNK):
                ids = torch.tensor([seq[s:min(s + CHUNK, len(seq) - kk)]], device="cuda")
                cache = model.model(input_ids=ids, past_key_values=cache, use_cache=True).past_key_values
        set_attn("eager")
        cap["on"] = True
        with torch.enable_grad():
            out = model.model(input_ids=torch.tensor([seq[-kk:]], device="cuda"), past_key_values=cache, use_cache=True)
            logits = model.lm_head(out.last_hidden_state[0, -1]).float()
            g = pick_g(logits.detach(), c, rule, cands)
            m = logits[c] - logits[g]
            m.backward()
        cap["on"] = False
        set_attn("sdpa")
        lg = logits.detach()
        m_gold = float(lg[c] - lg[g_gold]) if g_gold is not None else None
        x_final = cap["bout"][nl - 1][0, -1].float()
        eps = getattr(fnorm, "variance_epsilon", getattr(fnorm, "eps", 1e-6))
        rms = torch.sqrt((x_final ** 2).mean() + eps)
        n_mod = fnorm(cap["bout"][nl - 1][:, -1:]).float()[0, -1]
        w = fnorm.weight.float()
        we = w if (x_final / rms * w - n_mod).abs().max() < (x_final / rms * (1 + w) - n_mod).abs().max() else 1 + w
        dvec = (W_U[c].float() - W_U[g].float()) * we / rms
        emb_dla = float(cap["emb"][0, -1].detach().float() @ dvec)
        T = len(seq)
        attn_dla = np.zeros(nl, np.float32)
        mlp_dla = np.zeros(nl, np.float32)
        ndla = np.zeros((nl, blocks[0].mlp.down_proj.in_features), np.float16)
        grad = np.zeros_like(ndla)
        hin = np.zeros((nl, 4096), np.float16)
        hgrad = np.zeros_like(hin)
        hdla = np.zeros((nl, 32), np.float32)
        hgxa = np.zeros((nl, 32), np.float32)
        src_role = np.zeros((len(full), 16, len(ROLE)), np.float32)
        src_pos = np.zeros((len(full), T), np.float16)
        src_top_i = np.zeros((len(full), 16, 20), np.int32)
        src_top_v = np.zeros((len(full), 16, 20), np.float32)
        tsrc_role = np.zeros_like(src_role)
        tsrc_pos = np.zeros_like(src_pos)
        tsrc_top_i = np.zeros_like(src_top_i)
        tsrc_top_v = np.zeros_like(src_top_v)
        checks = {"head_vs_attn": [], "src_vs_head": []}
        codes = cap_codes["codes"]
        codes_t = torch.tensor(codes[:T].astype(np.int64), device="cuda")
        for i in range(nl):
            mo = cap["mout"][i][0, -1].float()
            bo = cap["bout"][i][0, -1].float()
            bi = cap["bin"][i][0, -1].float()
            mlp_dla[i] = float(mo @ dvec)
            attn_dla[i] = float((bo - bi - mo) @ dvec)
            a = cap["act"][i]
            av = a[0, -1].detach().float()
            Wd = blocks[i].mlp.down_proj.weight
            ndla[i] = (av * (Wd.t() @ dvec.to(Wd.dtype)).float()).cpu().numpy()
            grad[i] = (a.grad[0, -1].float().cpu().numpy() if a.grad is not None else 0)
            x = cap["hin"][i]
            xv = x[0, -1].detach().float()
            hin[i] = xv.cpu().numpy()
            Wo = (blocks[i].self_attn.o_proj if i in full else blocks[i].linear_attn.out_proj).weight
            u = (Wo.t() @ dvec.to(Wo.dtype)).float()
            nh, hd = (16, 256) if i in full else (32, 128)
            per = (xv * u).view(nh, hd).sum(1)
            hdla[i, :nh] = per.cpu().numpy()
            if x.grad is not None:
                hgrad[i] = x.grad[0, -1].float().cpu().numpy()
                hgxa[i, :nh] = (x.grad[0, -1].float() * xv).view(nh, hd).sum(1).cpu().numpy()
            checks["head_vs_attn"].append(abs(float(per.sum()) - attn_dla[i]))
            if i in full:
                fi = full.index(i)
                sa = blocks[i].self_attn
                aw = cap["aw"][i][0, :, -1, :].float()
                V = cache_values(cache, i)[0].float()
                h_in = cap["ain"][i][:, -1:]
                q = sa.q_proj(h_in).view(1, 1, -1, sa.head_dim * 2)
                _, gate = torch.chunk(q, 2, dim=-1)
                sig = torch.sigmoid(gate.reshape(16, sa.head_dim).float())
                uh = u.view(16, 256)
                rep = 16 // V.shape[0]
                contrib = torch.stack([aw[h, :T] * (V[h // rep, :T] @ (sig[h] * uh[h])) for h in range(16)])
                src_pos[fi] = contrib.sum(0).half().cpu().numpy()
                rs = torch.zeros(16, len(ROLE), device="cuda").index_add_(1, codes_t, contrib)
                src_role[fi] = rs.cpu().numpy()
                tv, ti = contrib.abs().topk(min(20, T), dim=1)
                src_top_i[fi, :, :ti.shape[1]] = ti.cpu().numpy()
                src_top_v[fi, :, :ti.shape[1]] = torch.gather(contrib, 1, ti).cpu().numpy()
                checks["src_vs_head"].append(float((contrib.sum(1) - per).abs().sum() / per.abs().sum().clamp_min(1e-3)))
                if x.grad is not None:
                    gh = x.grad[0, -1].float().view(16, 256)
                    tot = torch.stack([aw[h, :T] * (V[h // rep, :T] @ (sig[h] * gh[h])) for h in range(16)])
                    tsrc_pos[fi] = tot.sum(0).half().cpu().numpy()
                    tsrc_role[fi] = torch.zeros(16, len(ROLE), device="cuda").index_add_(1, codes_t, tot).cpu().numpy()
                    tv, ti = tot.abs().topk(min(20, T), dim=1)
                    tsrc_top_i[fi, :, :ti.shape[1]] = ti.cpu().numpy()
                    tsrc_top_v[fi, :, :ti.shape[1]] = torch.gather(tot, 1, ti).cpu().numpy()
        lin = emb_dla + float(attn_dla.sum() + mlp_dla.sum())
        res = dict(m=float(m.detach()), m_lin=lin, m_gold=m_gold, emb_dla=emb_dla, c=int(c), g=int(g), g_tok=tok.decode([g]),
                   rank_c=int((lg > lg[c]).sum()) + 1, rank_g=int((lg > lg[g]).sum()) + 1, T=T,
                   chk_head_vs_attn=float(max(checks["head_vs_attn"])), chk_src_vs_head=float(max(checks["src_vs_head"])))
        arrs = dict(ndla=ndla, grad=grad, hin=hin, hgrad=hgrad, hdla=hdla, hgxa=hgxa, attn_dla=attn_dla, mlp_dla=mlp_dla,
                    dvec=dvec.cpu().numpy().astype(np.float32), src_role=src_role, src_pos=src_pos, src_top_i=src_top_i,
                    src_top_v=src_top_v, tsrc_role=tsrc_role, tsrc_pos=tsrc_pos, tsrc_top_i=tsrc_top_i, tsrc_top_v=tsrc_top_v,
                    codes=codes[:T])
        del cache
        cap.clear()
        return res, arrs

    cap_codes = {}
    m1_units = json.loads((R / "probe/m1/out/units.json").read_text(encoding="utf-8"))
    all_units = json.loads(UNITS.read_text(encoding="utf-8"))
    units = sorted(all_units, key=lambda u: (u["label"] != "bad", u["k"]))
    if ONLY == "transfer":
        units = [u for u in units if u["call"] == "transfer_to_human_agents" and u["ptype"] == "T-name"]
    names = {}
    for u in m1_units:
        if u["ptype"] != "T-name":
            continue
        names.setdefault(u["domain"], set()).add(u["call"])
        if u.get("expected"):
            names[u["domain"]].add(u["expected"])
    for d in ("airline", "retail", "telecom"):
        for task in [str(t["id"]) for t in json.loads(Path(f"data/tau2/domains/{d}/tasks.json").read_text(encoding="utf-8"))]:
            for a in bt.gold_actions(d, task):
                if not is_read(a["name"]):
                    names.setdefault(d, set()).add(a["name"])
    first = {d: sorted({tok.encode(n, add_special_tokens=False)[0] for n in ns}) for d, ns in names.items()}
    want = {(u["cond"], u["sim"], u["turn"]) for u in units}
    seqs = {}
    for domain in ("airline", "retail", "telecom"):
        conds = sorted({u["cond"] for u in units if u["domain"] == domain})
        if not conds:
            continue
        for domain_, cond, task, sim, tel in bt.episodes(Path("data/simulations/pilot"), Path("data/jlens-telemetry/pilot"), [domain], conds):
            for line in tel.open(encoding="utf-8"):
                rec = json.loads(line)
                key = (cond, sim["id"], int(rec["turn_index"]))
                if key in want:
                    seqs[key] = (rec["input_ids"], rec["generated_ids"])
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    done = set()
    if (OUT / "units.json").is_file():
        rows = json.loads((OUT / "units.json").read_text(encoding="utf-8"))
        done = {r["k"] for r in rows if (OUT / f"n_{r['k']}.npz").is_file()}
        rows = [r for r in rows if r["k"] in done]
    log(f"{len(units)} units, {len(done)} done; tool-first candidates { {d: len(v) for d, v in first.items()} }")
    t0 = time.time()
    n_new = 0
    for u in units:
        if u["k"] in done:
            continue
        key = (u["cond"], u["sim"], u["turn"])
        if key not in seqs:
            continue
        inp, gen = seqs[key]
        seq = list(inp) + list(gen[:u["d"]])
        cap_codes["codes"] = role_codes(list(inp), u["d"], tok)
        if u["ptype"] == "T-name" and tok.encode(u["call"], add_special_tokens=False)[0] == u["c"]:
            rule, cands = "tool_first", [t for t in first[u["domain"]] if t != u["c"]]
        elif u["ptype"] == "T-call":
            rule, cands = "runnerup", None
        elif u["ptype"] == "U-text":
            rule, cands = "concept", None
        else:
            rule, cands = "novariant", None
        g_gold = u["g"] if u["label"] == "bad" and u.get("g") is not None else None
        res, arrs = measure(seq, u["c"], rule, cands, g_gold)
        np.savez(OUT / f"n_{u['k']}.npz", **arrs)
        rows.append({k: u[k] for k in ("k", "label", "kind", "ptype", "call", "domain", "task", "cond", "sim", "turn", "d", "c_tok")}
                    | res | {"rule": rule, "m_m1": u["m"], "g_m1": u["g_tok"], "expected": u.get("expected"),
                             "g_is_gold": bool(g_gold is not None and res["g"] == g_gold)})
        n_new += 1
        if n_new % 10 == 0 or n_new <= 3:
            (OUT / "units.json").write_text(json.dumps(rows, indent=0), encoding="utf-8")
            log(f"{len(rows)}/{len(units)} units, {time.time() - t0:.0f}s, last m {res['m']:.2f} lin {res['m_lin']:.2f} "
                f"chk head {res['chk_head_vs_attn']:.3f} src {res['chk_src_vs_head']:.3f}")
        if LIMIT and n_new >= LIMIT:
            break
    (OUT / "units.json").write_text(json.dumps(rows, indent=0), encoding="utf-8")
    log(f"C0A_DONE {len(rows)} units {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
