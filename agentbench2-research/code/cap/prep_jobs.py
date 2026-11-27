"""Capture jobs for CIRCUIT.md (project-b, CPU). One line per sequence the model saw: prompt ids + completion ids.
AgentDojo: every request of the vLLM generation (ops/proxy_log/dojo.jsonl); tier 1 only on the injected text.
AM: every request (ops/proxy_log/am.jsonl), condition matched to the prompt files; tier 1 everywhere.
ToolAlign: every step of the 128 qwen35-greedy traces (exact promptTokenIds + completionTokenIds); tier 1 everywhere.
Prints the sorted-plan sizes (stored tokens, tier-1 tokens, GB) per benchmark.
Usage: python prep_jobs.py OUT_DIR"""
import glob
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture import plan  # noqa: E402

A = Path("/home/project-b/LJW/agentbench2")
TA = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench/runner/results/qwen35-greedy")
T1_B, OTHER_B = 2 * 32 * (2560 + 2), 32 * 32 * 6
PIECE_B = 32 * (9216 + 4096) * 2


def ids_of(r):
    resp = r.get("response") or {}
    p = resp.get("prompt_token_ids") or (resp.get("choices") or [{}])[0].get("prompt_token_ids")
    c = (resp.get("choices") or [{}])[0].get("token_ids")
    return (list(p) + list(c), len(p)) if p and c is not None else (None, None)


def text_of(content):
    if isinstance(content, str):
        return content
    return "".join((b.get("content") or b.get("text") or "") for b in (content or []) if isinstance(b, dict))


INJ_A, INJ_B = "<INFORMATION>", "</INFORMATION>"


def char_to_token(tok, ids, c):
    lo, hi = 0, len(ids)
    while lo < hi:
        mid = (lo + hi) // 2
        if len(tok.decode(ids[:mid + 1])) > c:
            hi = mid
        else:
            lo = mid + 1
    return lo


def inj_spans(tok, ids, n_prompt):
    """Token spans of every <INFORMATION> ... </INFORMATION> block that sits inside a <tool_response> of the prompt."""
    P = ids[:n_prompt]
    text = tok.decode(P)
    sp, i = [], 0
    while True:
        a = text.find(INJ_A, i)
        if a < 0:
            break
        b = text.find(INJ_B, a)
        if b < 0:
            break
        r0, r1 = text.rfind("<tool_response>", 0, a), text.rfind("</tool_response>", 0, a)
        if r0 > r1:
            sp.append([char_to_token(tok, P, a), char_to_token(tok, P, b + len(INJ_B) - 1) + 1])
        i = b + len(INJ_B)
    return sp


def dojo():
    """Tier 1 only on the injected text (user 11-27 16:5x: "agentdojo는 prompt injection부분만 저장"); the cheap tiers everywhere."""
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-4B", revision="851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a")
    out = []
    for k, line in enumerate((A / "ops/proxy_log/dojo.jsonl").open(encoding="utf-8")):
        r = json.loads(line)
        ids, np_ = ids_of(r)
        if ids is None:
            continue
        h = hashlib.sha256(json.dumps([[m.get("role"), text_of(m.get("content"))] for m in r["request"]["messages"]]).encode()).hexdigest()[:16]
        out.append({"sid": f"dojo:{k}", "bench": "dojo", "ids": ids, "n_prompt": np_, "t1_spans": inj_spans(tok, ids, np_), "req_hash": h})
    return out


def am():
    P = A / "agentic-misalignment/results/qwen35_4b_am/prompts"
    cond = {}
    for d in sorted(P.iterdir()):
        s = (d / "system_prompt.txt").read_text(encoding="utf-8")
        u = (d / "user_prompt.txt").read_text(encoding="utf-8") + "\n\n" + (d / "email_content.txt").read_text(encoding="utf-8")
        cond[hashlib.sha256(json.dumps([s, u]).encode()).hexdigest()] = d.name
    out = []
    for k, line in enumerate((A / "ops/proxy_log/am.jsonl").open(encoding="utf-8")):
        r = json.loads(line)
        ids, np_ = ids_of(r)
        if ids is None:
            continue
        ms = r["request"]["messages"]
        c = cond.get(hashlib.sha256(json.dumps([m.get("content") for m in ms]).encode()).hexdigest(), "unknown")
        comp = ((r["response"].get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        out.append({"sid": f"am:{k}", "bench": "am", "ids": ids, "n_prompt": np_, "condition": c, "scenario": c.split("_")[0],
                    "tier1": True, "resp_md5": hashlib.md5(comp.encode()).hexdigest()})
    return out


def toolalign():
    out = []
    for f in sorted(glob.glob(str(TA / "*.trace.json"))):
        t = json.load(open(f, encoding="utf-8"))
        b = t["benchmark"]
        name = Path(f).name.split("--1.trace.json")[0]
        for d in t["documents"]:
            for st in d["steps"]:
                tt = st["response"]["tokenTrace"]
                out.append({"sid": f"ta:{name}:{d['docIndex']}:{st['stepIndex']}", "bench": "ta",
                            "ids": list(tt["promptTokenIds"]) + list(tt["completionTokenIds"]), "n_prompt": len(tt["promptTokenIds"]),
                            "domain": b["domain"], "type": b["scenarioType"], "condition": b["condition"],
                            "tier1": True,
                            "calls": [c.get("name") or (c.get("function") or {}).get("name") for c in st.get("extractedToolCalls") or []]})
    return out


def main():
    od = Path(sys.argv[1])
    od.mkdir(parents=True, exist_ok=True)
    tot = 0
    for name, fn in (("dojo", dojo), ("am", am), ("ta", toolalign)):
        jobs = fn()
        start, t1_upto, cuts, snap = plan(jobs)
        stored = sum(len(j["ids"]) - s for j, s in zip(jobs, start))
        t1 = sum(sum(max(0, b - max(a, s)) for a, b in sp) for j, s, sp in zip(jobs, start, t1_upto))
        npieces = sum(len(set(range((s // 128 + 1) * 128, len(j["ids"]), 128)) | {c for c in cu if s < c < len(j["ids"])}) + 1
                      for j, s, cu in zip(jobs, start, cuts) if len(j["ids"]) > s)
        fwd = sum(len(j["ids"]) - (s if (i > 0 and snap[i - 1] == s) else 0) for i, (j, s) in enumerate(zip(jobs, start)))
        gb = (t1 * T1_B + stored * OTHER_B + npieces * PIECE_B) / 1e9
        tot += gb
        with (od / f"jobs_{name}.jsonl").open("w", encoding="utf-8") as f:
            for j in jobs:
                f.write(json.dumps(j) + "\n")
        extra = ""
        if name == "am":
            from collections import Counter
            extra = f" conditions {dict(Counter(j['condition'] for j in jobs))}"
        print(f"{name}: jobs {len(jobs)}, stored tokens {stored:,}, tier-1 tokens {t1:,}, pieces {npieces:,}, forward tokens {fwd:,}, "
              f"about {gb:.0f} GB{extra}", flush=True)
    print(f"total about {tot:.0f} GB")


if __name__ == "__main__":
    main()
