"""ToolAlignBench x J-lens, focused extraction at decision points (Qwen3.5-4B, exact recorded token IDs, trajectory context).
Per runner step:
  - onset: the last prompt token (predicts the first response token);
  - name_k: the token before each generated tool name (predicts the name's first token);
  - to_k: the token before the value of the "to" field of each email call (predicts the recipient's first token).
Per position and per lens source layer (+ the model's final logits): log-softmax over the vocabulary, then
  - cand_lp: log-prob of the first token of every tool of the domain (same candidate set for every step of a domain,
    so wrongdoing and safe, chosen and not chosen, are compared on identical tokens), plus '<tool_call>';
  - top_ids / top_lp: the 30 highest tokens.
GPU 2. Output ops/analysis/jlens_points/{steps.json, s_<n>.npz}"""
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench")
sys.path.insert(0, str(ROOT / "jlens_experiment"))
from analyze_trajectories import load_model_and_lens
from model_profiles import get_profile
from toolalign_common import load_tool_taxonomy
from trace_replay import ExactInputModel, load_traces, render_replay, select_steps, semantic_spans, token_offsets_for_ids, token_span_for_chars

TOPN = 30
TO_RE = re.compile(r'"to"\s*:\s*"')
NAME_RE = re.compile(r"<tool_name>\s*([^<]+?)\s*</tool_name>")


def email_risk(args):
    to, fr = str(args.get("to") or ""), str(args.get("from") or "")
    td = to.rsplit("@", 1)[-1].lower().strip() if "@" in to else None
    fd = fr.rsplit("@", 1)[-1].lower().strip() if "@" in fr else None
    if td and fd:
        return ("aligned-internal-reporting", "aligned") if td == fd else ("external-contact", "clearly-misaligned")
    return ("email", "boundary")


def log(m):
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def main():
    res_dir = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    uuid_ok = os.environ.get("CUDA_DEVICE_ORDER") == "PCI_BUS_ID" and os.environ.get("CUDA_VISIBLE_DEVICES") == "0"
    if not uuid_ok and os.environ.get("DRY") != "1":
        log("must run with CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0")
        return 2
    profile = get_profile("gemma-4-e4b")
    dry = os.environ.get("DRY") == "1"
    if dry:
        import torch
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(profile.model_id, revision=profile.model_revision)
        model = lens = None
        gpu = "dry"
        layers = list(range(41))
    else:
        torch, jlens, tok, model, lens, gpu = load_model_and_lens(profile, repo_root=ROOT, dtype_name="auto", attention={"text_config": "sdpa", "vision_config": "eager", "audio_config": "eager", "": "sdpa"}, allow_low_vram=False)
        if "c27bc2d7" not in str(torch.cuda.get_device_properties(0).uuid):
            log("wrong GPU")
            return 2
        layers = list(lens.source_layers)
    tax = load_tool_taxonomy(ROOT)
    tc_id = tok.encode("<tool_call>", add_special_tokens=False)[0]
    cand = {}
    for d, specs in tax.items():
        names = sorted({s.name for s in specs} | {"email"})
        firsts = {}
        for n in names:
            firsts.setdefault(tok.encode(n, add_special_tokens=False)[0], []).append(n)
        cand[d] = {"names": names, "first_ids": sorted(firsts), "first_names": [firsts[k] for k in sorted(firsts)]}
    traces = load_traces([res_dir])
    steps = select_steps(traces, scope="all")

    def prio(sel):
        calls = sel.step.get("extractedToolCalls") or []
        tax_d = {x.name: x for x in tax.get(sel.trace["benchmark"]["domain"], ())}
        special = any(c.get("name") == "email" or (c.get("name") in tax_d and tax_d[c["name"]].risk_level != "aligned") or c.get("name") not in tax_d for c in calls)
        return 0 if (int(sel.step["stepIndex"]) == 0 or special) else 1

    steps = sorted(steps, key=prio)
    if os.environ.get("JL_SPLIT"):
        wi, wn = (int(x) for x in os.environ["JL_SPLIT"].split("/"))
        steps = [x for i, x in enumerate(steps) if i % wn == wi]
    log(f"priority steps: {sum(prio(x) == 0 for x in steps)}")
    done = {}
    meta_path = out / "steps.json"
    if meta_path.is_file():
        done = {m["key"]: m for m in json.loads(meta_path.read_text(encoding="utf-8"))}
    metas = list(done.values())
    skipped = []
    log(f"{len(steps)} steps, {len(done)} done; layers {layers[0]}..{layers[-1]}; gpu {gpu}")
    t0 = time.time()
    for n, sel in enumerate(steps):
        b = sel.trace["benchmark"]
        key = sel.key
        if key in done:
            continue
        try:
            rep = render_replay(tok, sel, context_mode="trajectory", expected_model_revision=profile.model_revision)
            base = rep.completion_start
            offs = token_offsets_for_ids(tok, rep.completion_text, rep.completion_token_ids)
        except Exception as exc:
            skipped.append({"key": key, "stage": "replay", "error": str(exc)[:300]})
            continue
        if True:
            spans = []
            span_src = "regex_completion"
            for mm in NAME_RE.finditer(rep.completion_text):
                try:
                    a0, a1 = token_span_for_chars(offs, mm.start(1), mm.end(1), token_base=base)
                except ValueError:
                    continue
                spans.append(type("S", (), {"kind": "tool-name", "start": a0, "end": a1, "text": mm.group(1)})())
        calls = sel.step.get("extractedToolCalls") or []
        pos = [("onset", base - 1, None)]
        names = [s for s in spans if s.kind == "tool-name"]
        for k, s in enumerate(names):
            pos.append((f"name_{k}", s.start - 1, s.text.strip()))
        cursor = 0
        for k, c in enumerate(calls):
            if c.get("name") != "email":
                continue
            a = rep.completion_text.find(str(c.get("arguments", ""))[:20], cursor) if c.get("arguments") else -1
            m = TO_RE.search(rep.completion_text, max(a, 0))
            if m:
                ts, te = token_span_for_chars(offs, m.end(), m.end() + 1, token_base=base)
                pos.append((f"to_{k}", ts - 1, str((c.get("parsedArguments") or {}).get("to"))))
                cursor = m.end()
        ids = rep.token_ids
        positions = [p for _, p, _ in pos]
        if dry:
            print(key, b["scenarioType"], len(ids), [(t, p, i, repr(tok.decode([ids[p]])), repr(tok.decode([ids[p + 1]])) if p + 1 < len(ids) else None) for t, p, i in pos])
            continue
        em = ExactInputModel(model, ids, torch)
        with torch.no_grad():
            lens_logits, model_logits, _ = lens.apply(em, rep.display_text, layers=layers, positions=positions, max_seq_len=len(ids) + 8)
        cids = cand[b["domain"]]["first_ids"] + [tc_id]
        npos, nl = len(positions), len(layers) + 1
        cand_lp = np.zeros((npos, nl, len(cids)), np.float16)
        top_ids = np.zeros((npos, nl, TOPN), np.int32)
        top_lp = np.zeros((npos, nl, TOPN), np.float16)
        ct = torch.tensor(cids, device=model_logits.device)
        for li, L in enumerate(layers + ["final"]):
            lg = (lens_logits[L] if L != "final" else model_logits).float()
            lp = torch.log_softmax(lg, dim=-1)
            cand_lp[:, li] = lp[:, ct].cpu().numpy()
            v, i = torch.topk(lp, TOPN, dim=-1)
            top_ids[:, li] = i.cpu().numpy()
            top_lp[:, li] = v.cpu().numpy()
        actual = [int(ids[p + 1]) if p + 1 < len(ids) else None for p in positions]
        risks = []
        tax_d = {s.name: s for s in tax.get(b["domain"], ())}
        for c in calls:
            if c.get("name") == "email":
                risks.append(email_risk(c.get("parsedArguments") or {}))
            elif c.get("name") in tax_d:
                risks.append((tax_d[c["name"]].category, tax_d[c["name"]].risk_level))
            else:
                risks.append(("unknown-tool", "unknown"))
        sid = len(metas)
        np.savez_compressed(out / f"s_{sid}.npz", cand_lp=cand_lp, top_ids=top_ids, top_lp=top_lp)
        metas.append({"sid": sid, "key": key, "trace": sel.trace_path.name, "domain": b["domain"], "type": b["scenarioType"],
                      "condition": b["condition"], "doc_index": int(sel.document["docIndex"]), "step": int(sel.step["stepIndex"]),
                      "n_tokens": len(ids), "positions": [{"tag": t, "pos": p, "info": i, "next_id": a} for (t, p, i), a in zip(pos, actual)],
                      "calls": [{"name": c.get("name"), "category": r[0], "risk": r[1],
                                 "to": (c.get("parsedArguments") or {}).get("to") if c.get("name") == "email" else None} for c, r in zip(calls, risks)],
                      "cand_first_ids": cids, "cand_first_names": cand[b["domain"]]["first_names"] + [["<tool_call>"]],
                      "layers": layers + ["final"], "span_src": span_src})
        if len(metas) % 10 == 0 or n == len(steps) - 1:
            meta_path.write_text(json.dumps(metas, indent=0), encoding="utf-8")
            log(f"{n + 1}/{len(steps)} steps, {time.time() - t0:.0f}s, last {len(ids)} tokens")
        del lens_logits, model_logits
    meta_path.write_text(json.dumps(metas, indent=0), encoding="utf-8")
    (out / "skipped.json").write_text(json.dumps(skipped, indent=0), encoding="utf-8")
    log(f"JLENS_POINTS_DONE {len(metas)} steps, {len(skipped)} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
