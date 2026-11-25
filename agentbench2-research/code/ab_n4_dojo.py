"""N4 on AgentDojo (PLAN.md: ToolAlign units first, then AgentDojo). Same design as ab_n4_toolalign.py.
Units: the AgentDojo CAUSAL-1 targets of kind tool / tool_div (dojo/c1/units.json). Scaffold '<tool_call>\\n<function='.
  no_preamble   : nothing between the onset and '<tool_call>'. Variants: original | commit ("I will now use <tool>.\\n"
                  inserted before the call) | neutral ("Let me continue with the task.\\n" inserted).
  text_preamble : text (no earlier call) before the call. Variants: original | deleted | neutral (replaces the text).
At the decision position (the name token, or the first divergent name token for tool_div): the CAUSAL-1 neuron sets
(top-K by gradient x (act - mu_ref) on the other fold, K = 16 / 64 / 256, and same-layer random sets) set to the mean of
the CAUSAL-1 references at their decision positions, leaving out the unit's own group. m = max lp(T) - max lp(A);
flip = m < 0; a variant whose unedited m <= 0 is excluded for that variant and counted.
Usage: AB_PLATFORM=projectb python ab_n4_dojo.py UNITS_JSON C1_DIR OUT_DIR"""
import copy
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

import ab_core as C

KS = (16, 64, 256)
COMMIT = "I will now use {tool}.\n"
NEUTRAL = "Let me continue with the task.\n"


def main():
    units_path, c1, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    units = {u["uid"]: u for u in json.loads(units_path.read_text(encoding="utf-8"))}
    U = json.loads((c1 / "units.json").read_text(encoding="utf-8"))
    sel = {tuple(k.split("|")): v for k, v in U["sel"].items()}
    tok, model = C.load()
    H = C.Hooked(model)
    eos = C.eos_ids(tok)
    tc = tok.encode("<tool_call>", add_special_tokens=False)

    def ids_of(uid):
        u = units[uid]
        return list(u["prompt_ids"]) + [t for t in u["completion_ids"] if t not in eos], len(u["prompt_ids"])

    def act_at(seq):
        _, cache = C.prefill(model, seq[:-1])
        H.store = {}
        H.cap = {"mode": "pos", "pos": [0], "kinds": {"act"}}
        with torch.inference_mode():
            model(input_ids=torch.tensor([[seq[-1]]], device=C.first_device(model)), past_key_values=cache, use_cache=True, logits_to_keep=1)
        H.cap = None
        a = torch.stack([H.store[("act", i)][0] for i in range(H.nl)])
        H.store = {}
        del cache
        return a

    R = [(x["group"], act_at(ids_of(x["uid"])[0][:x["pos"] + 1])) for x in U["refs"]]
    C.log(f"reference acts {len(R)}")

    def mu_excl(g):
        v = [a for gg, a in R if gg != g] or [a for _, a in R]
        return torch.stack(v).mean(0)

    nn = H.nn
    rows, skipped = [], defaultdict(int)
    for n, x in enumerate(U["targets"]):
        if x["kind"] not in ("tool", "tool_div"):
            skipped[f"kind_{x['kind']}"] += 1
            continue
        ids, plen = ids_of(x["uid"])
        on, pos = plen - 1, x["pos"]
        call = next((i for i in range(on + 1, pos + 1) if ids[i:i + len(tc)] == tc), None)
        if call is None:
            skipped["no_call_tag"] += 1
            continue
        pre, head, tail = ids[on + 1:call], ids[:on + 1], ids[call:pos + 1]
        tool = units[x["uid"]].get("inj_fn") or ""
        if not pre:
            kind = "no_preamble"
            variants = {"original": ids[:pos + 1],
                        "commit": head + tok.encode(COMMIT.format(tool=tool), add_special_tokens=False) + tail,
                        "neutral": head + tok.encode(NEUTRAL, add_special_tokens=False) + tail}
        elif "<tool_call>" not in tok.decode(pre):
            kind = "text_preamble"
            variants = {"original": ids[:pos + 1], "deleted": head + tail,
                        "neutral": head + tok.encode(NEUTRAL, add_special_tokens=False) + tail}
        else:
            skipped["multi_call"] += 1
            continue
        mu = mu_excl(x["group"])
        fo = str(1 - x["fold"])
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
        T, A = x["T"], x["A"]
        for vname, seq in variants.items():
            _, cache0 = C.prefill(model, seq[:-1])
            cache = C.cache_expand(copy.deepcopy(cache0), len(ops))
            H.set_rows([e for _, e in ops])
            with torch.inference_mode():
                o = model(input_ids=torch.tensor([[seq[-1]]] * len(ops), device=C.first_device(model)), past_key_values=cache,
                          use_cache=True, logits_to_keep=1)
            H.reset()
            lp = torch.log_softmax(o.logits[:, -1].float(), -1).cpu()
            bm = float(lp[0, T].max() - lp[0, A].max())
            for j, (name, _) in enumerate(ops):
                m = float(lp[j, T].max() - lp[j, A].max())
                rows.append({"uid": x["uid"], "kind": kind, "dkind": x["kind"], "variant": vname, "op": name, "m": m, "base_m": bm,
                             "flip": m < 0, "valid": bm > 0, "preamble_tokens": len(pre)})
            del cache, cache0
        if n % 10 == 0:
            C.log(f"target {n + 1}/{len(U['targets'])}")
    (out / "n4_rows.json").write_text(json.dumps(rows), encoding="utf-8")
    md = ["# N4 on AgentDojo: preamble manipulation, decision-position neuron edits (CAUSAL-1 sets)", "",
          f"- skipped: {dict(skipped)}; references for mu: {len(R)}", "",
          "| kind | variant | op | flip (valid) | n valid | n invalid | mean m |", "|---|---|---|---|---|---|---|"]
    by = defaultdict(list)
    for r in rows:
        by[(r["kind"], r["variant"], r["op"])].append(r)
    for k in sorted(by):
        rs = by[k]
        v = [r for r in rs if r["valid"]]
        if v:
            md.append(f"| {k[0]} | {k[1]} | {k[2]} | {np.mean([r['flip'] for r in v]):.2f} | {len(v)} | {len(rs) - len(v)} | {np.mean([r['m'] for r in v]):+.2f} |")
        else:
            md.append(f"| {k[0]} | {k[1]} | {k[2]} | - | 0 | {len(rs)} | - |")
    md += ["", "Prediction: no_preamble commit < original; text_preamble deleted > original (top-K arms; random arms stay low)."]
    (out / "n4_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    C.log("N4_DOJO_DONE")


if __name__ == "__main__":
    main()
