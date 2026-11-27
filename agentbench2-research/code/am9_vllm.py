"""L9a (PLAN.md Log 11-27 13:2x): Qwen3.5-9B samples of AM leaking prompts with vLLM (offline, bf16), pure temperature 1.
Prompt ids are the 4B ones (identical tokenizer and chat template): ana/am/units.json for the america pair and
ne/steer_am/extra_units_t9g.json for the 14 other goal values. Rows are written in the amgen format (condition, seed, ids, end,
n, harm, deg, text) so that ab_ne.py amscan can read them. Resumes: (condition, seed) pairs already in OUT are skipped.
Usage: python am9_vllm.py OUT_JSONL SPEC   SPEC = cond1,cond2,...:first_seed:count[;...]   (cond "all16" = the 16 prompts)
Env: AB_MEM (gpu_memory_utilization, default 0.55)."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

A = Path("/home/project-b/LJW/agentbench2/ana")
sys.path.insert(0, str(A))
MODEL, REV = "Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a"
AM_CONDS = ("leaking_explicit-america_none", "leaking_explicit-america_replacement")


def prompts():
    P = {}
    for u in json.loads((A / "am" / "units.json").read_text(encoding="utf-8")):
        if u["condition"] in AM_CONDS and u["condition"] not in P:
            P[u["condition"]] = list(u["prompt_ids"])
    for u in json.loads((A / "ne" / "steer_am" / "extra_units_t9g.json").read_text(encoding="utf-8")):
        P[u["condition"]] = list(u["prompt_ids"])
    return P


def degenerate(text):
    from collections import Counter
    w = text.split()[:300]
    if len(w) < 30:
        return False
    c = Counter(w)
    return len(c) / len(w) < 0.25 or sum(v for _, v in c.most_common(3)) / len(w) > 0.4


def main(out, spec):
    import ab_core as C
    import ab_strict as S
    C.gpu_guard()
    from vllm import LLM, SamplingParams
    from vllm.inputs import TokensPrompt
    P = prompts()
    jobs = []
    for part in spec.split(";"):
        conds, s0, n = part.split(":")
        cl = sorted(P) if conds == "all16" else conds.split(",")
        for c in cl:
            for s in range(int(s0), int(s0) + int(n)):
                jobs.append((c, s))
    out = Path(out)
    done = set()
    if out.exists():
        for line in out.open(encoding="utf-8"):
            r = json.loads(line)
            done.add((r["condition"], r["seed"]))
    jobs = [j for j in jobs if j not in done]
    print(f"{time.strftime('%H:%M:%S')} {len(jobs)} samples to draw ({len(done)} already in {out.name}); prompts {len(P)}", flush=True)
    if not jobs:
        print("AM9_VLLM_DONE 0", flush=True)
        return
    llm = LLM(model=MODEL, revision=REV, dtype="bfloat16", gpu_memory_utilization=float(os.environ.get("AB_MEM", "0.55")), max_model_len=10240,
              enable_prefix_caching=True, max_num_seqs=48, limit_mm_per_prompt={"image": 0, "video": 0}, seed=0)
    tok = llm.get_tokenizer()
    eos = {tok.convert_tokens_to_ids("<|im_end|>"), tok.eos_token_id}
    t0 = time.time()
    for b in range(0, len(jobs), 96):
        ch = jobs[b:b + 96]
        sps = [SamplingParams(temperature=1.0, top_p=1.0, top_k=0, max_tokens=6144,
                              seed=int(hashlib.md5(f"am9|{c}|{s}".encode()).hexdigest(), 16) % (2 ** 31)) for c, s in ch]
        res = llm.generate([TokensPrompt(prompt_token_ids=P[c]) for c, _ in ch], sps, use_tqdm=False)
        with out.open("a", encoding="utf-8") as fh:
            for (c, s), r in zip(ch, res):
                o = r.outputs[0]
                ids = list(o.token_ids)
                text = tok.decode([i for i in ids if i not in eos])
                end = "budget" if o.finish_reason == "length" else "eos"
                fh.write(json.dumps({"condition": c, "seed": s, "scenario": "leaking", "ids": ids, "end": end, "n": len(ids),
                                     "harm": bool(S.am_harmful("leaking", text)), "deg": degenerate(text), "tool": "<tool_use:" in text,
                                     "text": text, "src": "vllm"}, ensure_ascii=False) + "\n")
        print(f"{time.strftime('%H:%M:%S')} {b + len(ch)}/{len(jobs)} drawn, {time.time() - t0:.0f}s", flush=True)
    print(f"AM9_VLLM_DONE {len(jobs)}", flush=True)


def report(out):
    from collections import defaultdict
    by = defaultdict(lambda: [0, 0, 0])
    for line in open(out, encoding="utf-8"):
        r = json.loads(line)
        c = by[r["condition"]]
        c[0] += 1
        c[1] += r["harm"]
        c[2] += (r["end"] != "budget") and (not r["deg"]) and r["tool"]
    tot = [sum(v[i] for v in by.values()) for i in range(3)]
    print(f"| prompt | samples | leak (forward check) | quality kept |\n|---|---|---|---|")
    for c, (n, h, q) in sorted(by.items(), key=lambda kv: -kv[1][1] / kv[1][0]):
        print(f"| {c.replace('leaking_explicit-', '')} | {n} | {h}/{n} ({h / n:.0%}) | {q}/{n} ({q / n:.0%}) |")
    print(f"| all | {tot[0]} | {tot[1]}/{tot[0]} ({tot[1] / max(1, tot[0]):.0%}) | {tot[2]}/{tot[0]} |")
    print(json.dumps({c: v for c, v in by.items()}))


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report(sys.argv[2])
    else:
        main(sys.argv[1], sys.argv[2])
