"""M1 re-contrast check (copy of m1_extract.py measure()). Transfer T-name units, bad AND good, measured with the SAME contrast: g = best alternative TOOL-NAME token (first tokens of the domain's write tools, minus the chosen one). Tests whether the M1a transfer neuron signature is failure-specific or a contrast artifact (good units used runner-up = spelling variant).
ORIGINAL DOC: M1 (PLAN.md "M1"): where does each failure form? Per write-call unit at the first divergent token, teacher-forced:
m = logit(c) - logit(g); DLA of embedding / every attention and MLP output; per-neuron DLA and grad x act (32 x 9216).
GPU 2 only. Output probe/m1/out/units.json + probe/m1/out/u_<k>.npz"""
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import numpy as np
import torch

R = Path("/home/project-b/LJW/tau2-steer")
sys.path.insert(0, str(R / "probe/topk"))
import build_topk as bt

OUT = R / "probe/m1/out"
RUNS = {"airline": ["f_detect", "hdetect", "detect", "fitx"] + [f"d7obs_s{i}" for i in range(1, 7)],
        "retail": ["f_detect", "hdetect"], "telecom": ["f_detect"]}
FUNC = re.compile(r"<function=([^>\n]+)>(.*?)</function>", re.S)
PARAM = re.compile(r"<parameter=([^>\n]+)>\n(.*?)\n</parameter>", re.S)
CHUNK = 4096
LIMIT = int(os.environ.get("M1_LIMIT", "0"))


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def is_read(name):
    return name.startswith(bt.READ_PREFIXES)


def flat(x, p=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from flat(v, f"{p}.{k}" if p else k)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from flat(v, f"{p}[{i}]")
    else:
        yield p, x


def norm(v):
    if isinstance(v, bool):
        return str(v).lower()
    if v is None:
        return "null"
    s = str(v).strip()
    try:
        return repr(float(s))
    except ValueError:
        return s


def leaf_spans(body, base, args):
    out = []
    for m in PARAM.finditer(body):
        key, text = m.group(1).strip(), m.group(2)
        a0 = base + m.start(2)
        val = (args or {}).get(key)
        if isinstance(val, (dict, list)):
            try:
                parsed = json.loads(text)
            except ValueError:
                continue
            cur = 0
            for p, v in flat(parsed, key):
                needle = json.dumps(v)
                j = text.find(needle, cur)
                if j < 0:
                    continue
                s, e = (j + 1, j + len(needle) - 1) if isinstance(v, str) else (j, j + len(needle))
                out.append((p, v, a0 + s, a0 + e))
                cur = j + len(needle)
        else:
            lead = len(text) - len(text.lstrip())
            out.append((key, val, a0 + lead, a0 + len(text.rstrip())))
    return out


def main():
    uuid = str(torch.cuda.get_device_properties(0).uuid)
    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID" or os.environ.get("M1_GPU_UUID", "c27bc2d7") not in uuid:
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
    blocks = model.model.layers
    nl = len(blocks)
    W_U = model.lm_head.weight
    fnorm = model.model.norm
    tc_id = tok.convert_tokens_to_ids("<tool_call>")
    cap = {}

    def pre_down(i):
        def f(module, args):
            if cap.get("on"):
                x = args[0]
                if x.requires_grad:
                    x.retain_grad()
                cap.setdefault("act", {})[i] = x
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
    model.model.embed_tokens.register_forward_hook(post_emb)

    def measure(seq, c, g):
        cap.clear()
        cache = None
        kk = min(4, len(seq) - 1)
        with torch.no_grad():
            for s in range(0, len(seq) - kk, CHUNK):
                ids = torch.tensor([seq[s:min(s + CHUNK, len(seq) - kk)]], device="cuda")
                cache = model.model(input_ids=ids, past_key_values=cache, use_cache=True).past_key_values
        cap["on"] = True
        with torch.enable_grad():
            out = model.model(input_ids=torch.tensor([seq[-kk:]], device="cuda"), past_key_values=cache, use_cache=True)
            logits = model.lm_head(out.last_hidden_state[0, -1]).float()
            if g is None:
                masked = logits.clone()
                masked[c] = -1e9
                g = int(masked.argmax())
            elif isinstance(g, list):
                cand = torch.tensor(g, device=logits.device)
                g = int(cand[logits[cand].argmax()])
            m = logits[c] - logits[g]
            m.backward()
        cap["on"] = False
        x_final = cap["bout"][nl - 1][0, -1].float()
        eps = getattr(fnorm, "variance_epsilon", getattr(fnorm, "eps", 1e-6))
        rms = torch.sqrt((x_final ** 2).mean() + eps)
        n_mod = fnorm(cap["bout"][nl - 1][:, -1:]).float()[0, -1]
        w = (fnorm.weight.float())
        we = w if (x_final / rms * w - n_mod).abs().max() < (x_final / rms * (1 + w) - n_mod).abs().max() else 1 + w
        dvec = (W_U[c].float() - W_U[g].float()) * we / rms
        emb_dla = float(cap["emb"][0, -1].detach().float() @ dvec)
        attn, mlp = np.zeros(nl, np.float32), np.zeros(nl, np.float32)
        act = np.zeros((nl, blocks[0].mlp.down_proj.in_features), np.float16)
        grad = np.zeros_like(act)
        ndla = np.zeros_like(act)
        for i in range(nl):
            mo = cap["mout"][i][0, -1].float()
            bo = cap["bout"][i][0, -1].float()
            bi = cap["bin"][i][0, -1].float()
            mlp[i] = float(mo @ dvec)
            attn[i] = float((bo - bi - mo) @ dvec)
            a = cap["act"][i]
            av = a[0, -1].detach().float()
            act[i] = av.cpu().numpy()
            grad[i] = (a.grad[0, -1].float().cpu().numpy() if a.grad is not None else 0)
            proj = (blocks[i].mlp.down_proj.weight.t() @ dvec.to(blocks[i].mlp.down_proj.weight.dtype)).float()
            ndla[i] = (av * proj).cpu().numpy()
        lin = emb_dla + float(attn.sum() + mlp.sum())
        rank_c = int((logits > logits[c]).sum()) + 1
        rank_g = int((logits > logits[g]).sum()) + 1
        res = dict(m=float(m.detach()), m_lin=lin, emb_dla=emb_dla, c=int(c), g=int(g), rank_c=rank_c, rank_g=rank_g)
        del cache
        cap.clear()
        return res, attn, mlp, act, grad, ndla

    M1OUT = R / "probe/m1/out"
    RC = R / "probe/m1/out_recontrast"
    RC.mkdir(parents=True, exist_ok=True)
    units = [u for u in json.loads((M1OUT / "units.json").read_text(encoding="utf-8"))]
    sel = [u for u in units if u["ptype"] == "T-name" and u["call"] == "transfer_to_human_agents"]
    names = {}
    for u in units:
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
    first = {d: {tok.encode(n, add_special_tokens=False)[0] for n in ns} for d, ns in names.items()}
    log(f"{len(sel)} transfer T-name units; candidate tool tokens per domain: { {d: len(v) for d, v in first.items()} }")
    want = {(u["cond"], u["sim"], u["turn"]) for u in sel}
    seqs = {}
    for domain in ("airline", "retail", "telecom"):
        conds = sorted({u["cond"] for u in sel if u["domain"] == domain})
        if not conds:
            continue
        for domain_, cond, task, sim, tel in bt.episodes(Path("data/simulations/pilot"), Path("data/jlens-telemetry/pilot"), [domain], conds):
            for line in tel.open(encoding="utf-8"):
                rec = json.loads(line)
                key = (cond, sim["id"], int(rec["turn_index"]))
                if key in want:
                    seqs[key] = (rec["input_ids"], rec["generated_ids"])
    rows = []
    for n, u in enumerate(sel):
        inp, gen = seqs[(u["cond"], u["sim"], u["turn"])]
        seq = list(inp) + list(gen[:u["d"]])
        cands = sorted(first[u["domain"]] - {u["c"]})
        res, attn, mlp, act, grad, ndla = measure(seq, u["c"], cands)
        np.savez(RC / f"rc_{u['k']}.npz", attn=attn, mlp=mlp, ndla=ndla)
        rows.append({k: u[k] for k in ("k", "label", "kind", "domain", "task", "cond", "m")} | {"m_rc": res["m"], "m_lin_rc": res["m_lin"], "emb_dla": res["emb_dla"],
                     "g_rc": tok.decode([res["g"]]), "g_orig": u["g_tok"]})
        if n % 10 == 0:
            log(f"{n}/{len(sel)}")
    (RC / "rows.json").write_text(json.dumps(rows, indent=0), encoding="utf-8")
    log("RECONTRAST_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
