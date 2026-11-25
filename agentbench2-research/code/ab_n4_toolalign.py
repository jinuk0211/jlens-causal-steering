"""N4 (PLAN.md): preamble manipulation on the ToolAlign-4B CAUSAL-1 target units, making the commit-site claim causal.
Units: the 53 CAUSAL-1 targets (ops/analysis/causal/units.json). The tool-call scaffold is '<tool_call>\\n<tool_name>'.
  no_preamble : nothing between the onset and the scaffold.
     variants: original | commit ("I will now use <tool>.\\n" inserted before the scaffold) | neutral ("Let me continue
     with the task.\\n" inserted).
  text_preamble : free text (no earlier tool call) between the onset and the scaffold.
     variants: original | deleted (scaffold right after the onset) | neutral (preamble replaced by the neutral sentence).
  multi_call (an earlier call in the same response) : excluded and counted.
At the tool-name position of each variant: the CAUSAL-1 neuron edit (top-K by gradient x (act - mu_ref) on the other
fold, from the ToolAlign units.json sel_sets; K = 16, 64, 256) and the same-layer random neurons, set to the
leave-one-domain-out reference mean at that position. m = lp(chosen tool) - lp(writeInternalLog); flip = m < 0. Variants
where the unedited m is already <= 0 are excluded for that variant and counted.
Prediction: commit lowers the flip rate of no_preamble units; deleted raises it for text_preamble units.
GPU: project-b GPU 0; every other compute process on it must be one of ours (/LJW/agentbench2/ in its command line).
Usage: python ab_n4_toolalign.py OUT_DIR"""
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench")
sys.path.insert(0, str(ROOT / "jlens_experiment"))
import ab_core as C  # noqa: E402

KS = (16, 64, 256)
COMMIT = "I will now use {tool}.\n"
NEUTRAL = "Let me continue with the task.\n"


def guard():
    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID" or os.environ.get("CUDA_VISIBLE_DEVICES") != "0":
        raise SystemExit("need CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0")
    q = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,gpu_uuid", "--format=csv,noheader"], capture_output=True, text=True).stdout
    for line in q.strip().splitlines():
        pid, uuid = [x.strip() for x in line.split(",")]
        if C.PROJECTB_GPU0 not in uuid or int(pid) == os.getpid():
            continue
        cmd = C._cmd(pid)
        if not C.is_ours(pid):
            raise SystemExit(f"GPU guard: GPU 0 has a process that is not ours: {pid} {cmd[:120]}")


def fold(domain):
    return int(hashlib.md5(domain.encode()).hexdigest(), 16) % 2


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    guard()
    C.patch_gdn()
    from model_profiles import get_profile
    from trace_replay import load_traces, render_replay, select_steps
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
    prof = get_profile("qwen3.5-4b")
    tok = AutoTokenizer.from_pretrained(prof.model_id, revision=prof.model_revision)
    if C.PROJECTB_GPU0 not in str(torch.cuda.get_device_properties(0).uuid):
        raise SystemExit("wrong GPU")
    model = Qwen3_5ForConditionalGeneration.from_pretrained(prof.model_id, revision=prof.model_revision, dtype=torch.bfloat16).cuda().eval()
    model.model.visual = None
    for p in model.parameters():
        p.requires_grad_(False)
    H = C.Hooked(model)
    U = json.loads((ROOT / "ops/analysis/causal/units.json").read_text(encoding="utf-8"))
    sel = {tuple(k.split("|")): v for k, v in U["sel_sets"].items()}
    metas = {m["key"]: m for m in json.loads((ROOT / "ops/analysis/jlens_points/steps.json").read_text(encoding="utf-8"))}
    steps = {s.key: s for s in select_steps(load_traces([ROOT / "runner/results/qwen35-greedy"]), scope="all")}
    w_id = tok.encode("writeInternalLog", add_special_tokens=False)[0]
    scaffold = tok.encode("<tool_call>\n<tool_name>", add_special_tokens=False)

    def ids_of(x):
        rep = render_replay(tok, steps[x["key"]], context_mode="trajectory", expected_model_revision=prof.model_revision)
        ids = list(rep.token_ids)
        assert ids[x["pos"] + 1] == x["next_id"], "position mismatch"
        return ids

    def act_at(seq):
        _, cache = C.prefill(model, seq[:-1])
        H.store = {}
        H.cap = {"mode": "pos", "pos": [0], "kinds": {"act"}}
        with torch.inference_mode():
            model(input_ids=torch.tensor([[seq[-1]]], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
        H.cap = None
        a = torch.stack([H.store[("act", i)][0] for i in range(H.nl)])
        H.store = {}
        return a

    t0 = time.time()
    R = {}
    for n, x in enumerate(U["refs"]):
        R[n] = (x["domain"], act_at(ids_of(x)[:x["pos"] + 1]))
    C.log(f"ref acts {len(R)} {time.time() - t0:.0f}s")

    def mu_excl(domain):
        v = [a for d, a in R.values() if d != domain]
        return torch.stack(v).mean(0)

    nn = H.nn
    rows, skipped = [], defaultdict(int)
    for n, x in enumerate(U["targets"]):
        ids = ids_of(x)
        on = [p["pos"] for p in metas[x["key"]]["positions"] if p["tag"] == "onset"][0]
        pos = x["pos"]
        if ids[pos + 1 - len(scaffold):pos + 1] != scaffold:
            skipped["scaffold_mismatch"] += 1
            continue
        pre = ids[on + 1:pos + 1 - len(scaffold)]
        head = ids[:on + 1]
        if not pre:
            kind = "no_preamble"
            variants = {"original": ids[:pos + 1],
                        "commit": head + tok.encode(COMMIT.format(tool=x["tool"]), add_special_tokens=False) + scaffold,
                        "neutral": head + tok.encode(NEUTRAL, add_special_tokens=False) + scaffold}
        elif "<tool_call>" not in tok.decode(pre):
            kind = "text_preamble"
            variants = {"original": ids[:pos + 1], "deleted": head + scaffold,
                        "neutral": head + tok.encode(NEUTRAL, add_special_tokens=False) + scaffold}
        else:
            skipped["multi_call"] += 1
            continue
        mu = mu_excl(x["domain"])
        fo = str(1 - fold(x["domain"]))
        ops = [("base", {})]
        for K in KS:
            for tg in ("top", "random"):
                idx = sel.get((fo, str(K), tg))
                if idx is None:
                    continue
                by = defaultdict(list)
                for v in idx:
                    by[v // nn].append(v % nn)
                ops.append((f"neur_{tg}_{K}", {("down", l): C.Edit("neur", idx=torch.tensor(ns), vec=mu[l][ns]) for l, ns in by.items()}))
        for vname, seq in variants.items():
            _, cache0 = C.prefill(model, seq[:-1])
            cache = C.cache_expand(copy.deepcopy(cache0), len(ops))
            H.set_rows([e for _, e in ops])
            with torch.inference_mode():
                o = model(input_ids=torch.tensor([[seq[-1]]] * len(ops), device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
            H.reset()
            lp = torch.log_softmax(o.logits[:, -1].float(), -1).cpu()
            bm = float(lp[0, x["c"]] - lp[0, w_id])
            for j, (name, _) in enumerate(ops):
                m = float(lp[j, x["c"]] - lp[j, w_id])
                rows.append({"key": x["key"], "domain": x["domain"], "tool": x["tool"], "risk": x["risk"], "kind": kind,
                             "variant": vname, "op": name, "m": m, "base_m": bm, "flip": m < 0, "valid": bm > 0,
                             "preamble_tokens": len(pre)})
            del cache, cache0
        if n % 5 == 0:
            C.log(f"target {n + 1}/{len(U['targets'])} {time.time() - t0:.0f}s")
    (out / "n4_rows.json").write_text(json.dumps(rows), encoding="utf-8")
    md = ["# N4: preamble manipulation on ToolAlign-4B CAUSAL-1 targets (name-position neuron edits)", "",
          f"- skipped: {dict(skipped)}", "",
          "| kind | variant | op | flip (valid variants) | n valid | n invalid (unedited m <= 0) | mean m |", "|---|---|---|---|---|---|---|"]
    by = defaultdict(list)
    for r in rows:
        by[(r["kind"], r["variant"], r["op"])].append(r)
    for k in sorted(by):
        rs = by[k]
        v = [r for r in rs if r["valid"]]
        md.append(f"| {k[0]} | {k[1]} | {k[2]} | {np.mean([r['flip'] for r in v]):.2f} | {len(v)} | {len(rs) - len(v)} | "
                  f"{np.mean([r['m'] for r in v]) if v else float('nan'):+.2f} |" if v else f"| {k[0]} | {k[1]} | {k[2]} | - | 0 | {len(rs)} | - |")
    md += ["", "Prediction: no_preamble commit < original; text_preamble deleted > original (top-K arms; random arms stay low)."]
    (out / "n4_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    C.log("N4_DONE")


if __name__ == "__main__":
    main()
