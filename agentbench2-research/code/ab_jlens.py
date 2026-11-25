"""J-lens at decision points (ToolAlign-4B procedure, PLAN.md), exact recorded token ids, one forward per unit.
Positions (the position whose output predicts the token):
  onset = last prompt token;
  dojo: name_k before each <function=NAME> name, arg_<param> before each parameter value of the first call;
  am: tool_k before each <tool_use:NAME> name, to_k before each email/forward recipient, code_k before '4429' in a block.
Per position and lens layer (+ final logits): lp of a fixed candidate set (same tokens for every unit of a suite or
scenario: tool first tokens, '<tool_call>'/'<', recipient and argument value first tokens), the actual next token's lp,
and the top-N tokens (AB_TOPN, 50 from 11-25 16:4x by user request; was 30).
Usage: AB_PLATFORM=vast|projectb python ab_jlens.py dojo|am UNITS_JSON OUTDIR"""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import torch

import ab_core as C

TOPN = int(os.environ.get("AB_TOPN", "50"))
CHUNK = 1024
ADDR_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
AM_TOOLS = ["email", "forward", "cancel_alert"]


def first_tok(tok, s, ctx=""):
    a = tok.encode(ctx, add_special_tokens=False) if ctx else []
    b = tok.encode(ctx + s, add_special_tokens=False)
    return b[len(a)] if len(b) > len(a) and b[:len(a)] == a else b[0]


def dojo_cands(tok, suite_tools, unit):
    names = sorted(suite_tools)
    c = [("tool:" + n, first_tok(tok, n)) for n in names] + [("<tool_call>", tok.convert_tokens_to_ids("<tool_call>"))]
    for v in unit.get("v_inj", [])[:12]:
        c.append(("inj:" + v[:40], first_tok(tok, v, "\n")))
    for v in unit.get("v_user", [])[:12]:
        c.append(("user:" + v[:40], first_tok(tok, v, "\n")))
    return c


def am_cands(tok, prompt_text):
    from am_markers import KYLE, LEAK
    c = [("tool:" + n, first_tok(tok, n, "<tool_use:")) for n in AM_TOOLS] + [("<", first_tok(tok, "<"))]
    addrs = sorted(set(ADDR_RE.findall(prompt_text)) | set(KYLE) | set(LEAK))
    for a in addrs:
        kind = "kyle" if a in KYLE else ("leak" if a in LEAK else "addr")
        c.append((f"{kind}:{a}", first_tok(tok, a, 'to: "')))
        c.append((f"{kind}_nq:{a}", first_tok(tok, " " + a, "to:")))
    return c


def positions_dojo(tok, comp, base):
    text = tok.decode(comp)
    pos = [("onset", base - 1, None)]
    for k, m in enumerate(C.FUNC_RE.finditer(text)):
        if k >= 4:
            break
        j = C.char_to_token(tok, comp, m.start(1))
        pos.append((f"name_{k}", base + j - 1, m.group(1).strip()))
    first = C.CALL_RE.search(text)
    if first:
        for m in C.ARG_RE.finditer(text, first.start(), first.end()):
            j = C.char_to_token(tok, comp, m.end())
            pos.append((f"arg_{m.group(1).strip()}", base + j - 1, m.group(1).strip()))
    return pos


def positions_am(tok, comp, base):
    from am_markers import BLOCK
    text = tok.decode(comp)
    pos = [("onset", base - 1, None)]
    for k, m in enumerate(C.AM_TOOL_RE.finditer(text)):
        if k >= 6:
            break
        pos.append((f"tool_{k}", base + C.char_to_token(tok, comp, m.start(1)) - 1, m.group(1)))
    nt = nc = 0
    for m in BLOCK.finditer(text):
        if m.group(1) in ("email", "forward") and nt < 6:
            t = C.AM_TO_RE.search(m.group(2))
            if t:
                c0 = m.start(2) + t.end()
                pos.append((f"to_{nt}", base + C.char_to_token(tok, comp, c0) - 1, m.group(2)[t.end():t.end() + 60].split("\n")[0]))
                nt += 1
        i = m.group(0).find("4429")
        if i >= 0 and nc < 2:
            pos.append((f"code_{nc}", base + C.char_to_token(tok, comp, m.start(0) + i) - 1, m.group(1)))
            nc += 1
    return pos


def main():
    bench, units_path, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    units = json.loads(units_path.read_text(encoding="utf-8"))
    tok, model = C.load()
    H = C.Hooked(model)
    lens = C.Lens(model)
    layers = lens.layers
    suite_tools = {}
    if bench == "dojo":
        for u in units:
            suite_tools.setdefault(u["suite"], u["suite_tools"])
    meta_path = out / "steps.json"
    metas = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else []
    done = {m["uid"] for m in metas}
    C.log(f"{len(units)} units, {len(done)} done, layers {layers[0]}..{layers[-1]}")
    for n, u in enumerate(units):
        if u["uid"] in done:
            continue
        P, comp = list(u["prompt_ids"]), [t for t in u["completion_ids"] if t not in C.eos_ids(tok)]
        ids = P + comp
        if bench == "dojo":
            pos = positions_dojo(tok, comp, len(P))
            cands = dojo_cands(tok, suite_tools[u["suite"]], u)
        else:
            pos = positions_am(tok, comp, len(P))
            cands = am_cands(tok, tok.decode(P))
        positions = [p for _, p, _ in pos]
        got = {}
        cache = None
        uniq = sorted(set(positions))
        with torch.inference_mode():
            for s0 in range(0, uniq[-1] + 1, CHUNK):
                e0 = min(s0 + CHUNK, uniq[-1] + 1)
                absp = [p for p in uniq if s0 <= p < e0]
                H.store = {}
                H.cap = {"mode": "pos", "pos": [p - s0 for p in absp], "kinds": {"res"}} if absp else None
                o = model(input_ids=torch.tensor([ids[s0:e0]], device=C.first_device(model)), past_key_values=cache, use_cache=True, logits_to_keep=1)
                cache = o.past_key_values
                for k, v in H.store.items():
                    for j, p in enumerate(absp):
                        got[(k, p)] = v[j]
            H.cap = None
            del cache
        H.store = {("res", l): torch.stack([got[(("res", l), p)] for p in positions]) for l in range(H.nl)}
        cid = torch.tensor([c for _, c in cands], device=lens.dev)
        nxt = torch.tensor([ids[p + 1] if p + 1 < len(ids) else 0 for p in positions], device=lens.dev)
        L = layers + ["final"]
        cand_lp = np.zeros((len(positions), len(L), len(cands)), np.float16)
        next_lp = np.zeros((len(positions), len(L)), np.float16)
        top_ids = np.zeros((len(positions), len(L), TOPN), np.int32)
        top_lp = np.zeros((len(positions), len(L), TOPN), np.float16)
        with torch.inference_mode():
            for li, l in enumerate(L):
                h = H.store[("res", l if l != "final" else H.nl - 1)]
                lp = torch.log_softmax(lens.logits(h, l), -1)
                cand_lp[:, li] = lp[:, cid].cpu().numpy()
                next_lp[:, li] = lp.gather(1, nxt[:, None])[:, 0].cpu().numpy()
                v, i = torch.topk(lp, TOPN, -1)
                top_ids[:, li], top_lp[:, li] = i.cpu().numpy(), v.cpu().numpy()
        sid = len(metas)
        np.savez_compressed(out / f"s_{sid}.npz", cand_lp=cand_lp, next_lp=next_lp, top_ids=top_ids, top_lp=top_lp)
        keep = {k: u[k] for k in u if k not in ("prompt_ids", "completion_ids")}
        metas.append({**keep, "sid": sid, "n_tokens": len(ids), "layers": L,
                      "positions": [{"tag": t, "pos": p, "info": i, "next_id": ids[p + 1] if p + 1 < len(ids) else None} for t, p, i in pos],
                      "cands": [[name, c] for name, c in cands]})
        H.store = {}
        if len(metas) % 10 == 0 or n == len(units) - 1:
            meta_path.write_text(json.dumps(metas), encoding="utf-8")
            C.log(f"{n + 1}/{len(units)} units, last {len(ids)} tokens, {len(positions)} positions")
    meta_path.write_text(json.dumps(metas), encoding="utf-8")
    C.log(f"JLENS_DONE {len(metas)}")


if __name__ == "__main__":
    main()
