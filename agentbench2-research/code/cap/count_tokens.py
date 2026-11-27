"""Token inventory for the full capture: sequences (prompt + completion ids as the model saw them), total tokens, and
unique tokens under exact prefix sharing (activations at a position depend only on the tokens up to it)."""
import glob
import json
import sys
from collections import Counter

M = (1 << 61) - 1


def add(seen, ids):
    h, new = 0, 0
    for t in ids:
        h = (h * 1000003 + t + 1) % M
        if h not in seen:
            seen.add(h)
            new += 1
    return new


def report(name, seqs):
    seen = set()
    tot = sum(len(s) for s in seqs)
    uniq = sum(add(seen, s) for s in seqs)
    L = sorted(len(s) for s in seqs)
    print(f"{name}: sequences {len(seqs)}, tokens {tot:,}, unique under prefix sharing {uniq:,}, "
          f"length median {L[len(L) // 2]:,} max {L[-1]:,}", flush=True)
    return uniq


def proxy(path, keep=None):
    seqs, src = [], Counter()
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        resp = r.get("response") or {}
        p = resp.get("prompt_token_ids") or (resp.get("choices") or [{}])[0].get("prompt_token_ids")
        c = (resp.get("choices") or [{}])[0].get("token_ids")
        if p and c is not None:
            seqs.append(list(p) + list(c))
            src["ids"] += 1
        else:
            src["no_ids"] += 1
    print(path, dict(src))
    return seqs


def toolalign(d):
    seqs = []
    for f in sorted(glob.glob(d + "/*.trace.json")):
        t = json.load(open(f, encoding="utf-8"))
        for doc in t["documents"]:
            for st in doc["steps"]:
                tt = st["response"]["tokenTrace"]
                seqs.append(list(tt["promptTokenIds"]) + list(tt["completionTokenIds"]))
    return seqs


if __name__ == "__main__":
    A = "/home/project-b/LJW/agentbench2"
    out = {}
    out["dojo"] = report("AgentDojo (proxy log, every request)", proxy(A + "/ops/proxy_log/dojo.jsonl"))
    out["am"] = report("AM (proxy log, every request)", proxy(A + "/ops/proxy_log/am.jsonl"))
    out["ta"] = report("ToolAlign qwen35-greedy (128 traces, every step)",
                       toolalign("/home/project-b/LJW/tau2-steer/ToolAlignBench/runner/results/qwen35-greedy"))
    print(json.dumps(out))
