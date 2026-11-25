"""M1 (PLAN.md "M1"): where does each failure form? Per write-call unit at the first divergent token, teacher-forced:
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
    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID" or "4c593ff4" not in uuid:
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

    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(0)
    units, seen = [], set()
    if (OUT / "units.json").is_file():
        units = [u for u in json.loads((OUT / "units.json").read_text(encoding="utf-8")) if (OUT / f"u_{u['k']}.npz").is_file()]
        seen = {(u["sha"], u["gsha"], u["d"], u["ptype"]) for u in units}
        log(f"resume: {len(units)} units")
    n_ep = n_missing = 0
    t0 = time.time()
    for domain, conds in RUNS.items():
        for domain_, cond, task, sim, tel in bt.episodes(Path("data/simulations/pilot"), Path("data/jlens-telemetry/pilot"), [domain], conds):
            n_ep += 1
            reward = (sim.get("reward_info") or {}).get("reward")
            passed = (reward or 0) >= 1
            gold = [a for a in bt.gold_actions(domain, task) if not is_read(a["name"])]
            matched = set()
            recs = sorted((json.loads(x) for x in tel.open(encoding="utf-8")), key=lambda r: r["turn_index"])
            cand = []
            any_bad = False
            for rec in recs:
                def add(u, rec=rec):
                    u["inp_len"] = len(rec["input_ids"])
                    u["_seq"] = list(rec["input_ids"]) + rec["generated_ids"][:u["d"]]
                    cand.append(u)

                calls = rec.get("tool_calls") or []
                gen = rec["generated_ids"]
                text = None
                for ci, call in enumerate(calls):
                    name = call["name"]
                    if is_read(name):
                        continue
                    pend = [j for j in range(len(gold)) if j not in matched]
                    expected = gold[pend[0]] if pend else None
                    same = [j for j in pend if gold[j]["name"] == name and (name == "transfer_to_human_agents" or bt.args_key(gold[j]) == bt.args_key(call))]
                    ok = bool(same)
                    if ok:
                        matched.add(same[0])
                    if text is None:
                        text = tok.decode(gen)
                        pieces = tok.batch_decode([[t] for t in gen])
                        starts = [0]
                        for pc in pieces:
                            starts.append(starts[-1] + len(pc))
                        if "".join(pieces) != text:
                            starts = [len(tok.decode(gen[:i])) for i in range(len(gen) + 1)]
                        funcs = list(FUNC.finditer(text))
                    if len(funcs) != len(calls) or funcs[ci].group(1).strip() != name:
                        continue
                    f = funcs[ci]

                    def tok_at(ch):
                        return next((i for i in range(len(gen)) if starts[i] <= ch < starts[i + 1]), None)

                    base = {"domain": domain, "cond": cond, "task": task, "sim": sim["id"], "turn": int(rec["turn_index"]),
                            "call": name, "passed": passed, "reward": reward, "sha": rec.get("input_ids_sha256"),
                            "gsha": rec.get("generated_ids_sha256")}
                    nm0 = f.start(1)
                    tc_pos = max((i for i in range(len(gen)) if gen[i] == tc_id and starts[i] <= nm0), default=None)
                    if not ok and not passed:
                        any_bad = True
                        kind = "unexpected_transfer" if name == "transfer_to_human_agents" else ("wrong_args" if any(a["name"] == name for a in gold) else "unexpected_write")
                        if expected is None:
                            if tc_pos is not None:
                                add(dict(base, label="bad", kind=kind, ptype="T-call", d=tc_pos, c=tc_id, g=None))
                        elif expected["name"] != name:
                            en = expected["name"]
                            k = 0
                            while k < min(len(en), len(name)) and en[k] == name[k]:
                                k += 1
                            d = tok_at(nm0 + k)
                            if d is not None and d > 0:
                                gt = tok.encode(text[starts[d]:nm0 + k] + en[k:], add_special_tokens=False)
                                if gt and gt[0] != gen[d]:
                                    add(dict(base, label="bad", kind=kind, ptype="T-name", d=d, c=gen[d], g=gt[0], expected=en))
                        else:
                            gl = {p: v for p, v in flat(expected.get("arguments") or {})}
                            for p, v, a, b in leaf_spans(f.group(2), f.start(2), call.get("arguments")):
                                gv = gl.get(p, "__absent__")
                                if gv == "__absent__" or norm(gv) == norm(v):
                                    continue
                                cs, gs = str(v), str(gv)
                                k = 0
                                while k < min(len(cs), len(gs)) and cs[k] == gs[k]:
                                    k += 1
                                d = tok_at(a + k)
                                if d is not None and d > 0:
                                    gt = tok.encode(text[starts[d]:a + k] + gs[k:], add_special_tokens=False)
                                    if gt and gt[0] != gen[d]:
                                        add(dict(base, label="bad", kind=kind, ptype="T-args", d=d, c=gen[d], g=gt[0], path=p, value=cs, gold=gs))
                                break
                    elif ok and passed:
                        opts = []
                        d = tok_at(nm0)
                        if d is not None and d > 0:
                            opts.append(dict(base, label="good", kind="good_write", ptype="T-name", d=d, c=gen[d], g=None))
                        if tc_pos is not None:
                            opts.append(dict(base, label="good", kind="good_write", ptype="T-call", d=tc_pos, c=tc_id, g=None))
                        leaves = leaf_spans(f.group(2), f.start(2), call.get("arguments"))
                        if leaves:
                            p, v, a, b = leaves[rng.randrange(len(leaves))]
                            d = tok_at(a)
                            if d is not None and d > 0:
                                opts.append(dict(base, label="good", kind="good_write", ptype="T-args", d=d, c=gen[d], g=None, path=p))
                        for o in opts:
                            o["inp_len"] = len(rec["input_ids"])
                            o["_seq"] = list(rec["input_ids"]) + gen[:o["d"]]
                        cand.append(("good_group", opts))
            if not passed and not any_bad:
                n_missing += 1
            goods = [x for x in cand if isinstance(x, tuple)]
            bads = [x for x in cand if isinstance(x, dict)]
            todo = bads + (goods[rng.randrange(len(goods))][1] if goods else [])
            for u in todo:
                key = (u["sha"], u["gsha"], u["d"], u["ptype"])
                if key in seen or "_seq" not in u:
                    continue
                seen.add(key)
                seq = u.pop("_seq")
                res, attn, mlp, act, grad, ndla = measure(seq, u["c"], u["g"])
                u.update(res)
                u["k"] = len(units)
                u["c_tok"], u["g_tok"] = tok.decode([u["c"]]), tok.decode([u["g"]])
                np.savez(OUT / f"u_{u['k']}.npz", attn=attn, mlp=mlp, act=act, grad=grad, ndla=ndla)
                units.append(u)
                (OUT / "units.json").write_text(json.dumps(units, indent=0, default=str), encoding="utf-8")
                if LIMIT and len(units) >= LIMIT:
                    log(f"LIMIT reached: {len(units)} units, episodes {n_ep}")
                    return 0
            if n_ep % 20 == 0:
                nb = sum(u["label"] == "bad" for u in units)
                log(f"episodes {n_ep}, units {len(units)} (bad {nb}), missing-write failures {n_missing}, {time.time() - t0:.0f}s")
    (OUT / "meta.json").write_text(json.dumps({"episodes": n_ep, "missing_write_failures": n_missing, "units": len(units)}), encoding="utf-8")
    log(f"M1_EXTRACT_DONE episodes {n_ep} units {len(units)} missing {n_missing} {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
