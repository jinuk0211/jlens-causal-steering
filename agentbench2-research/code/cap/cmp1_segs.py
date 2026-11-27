"""Samples, clusters and token segments for CIRCUIT.md comparison 1 (project-b, CPU; only jobs that were captured).
AM: each response of the captured conditions; cluster = Haiku verdict (harmful / not); segments = response windows by token
    index from the response start (0-256, 256-512, 512-768, 768-1024, 1024-1536, 1536-2048, 2048-3072, 3072-4096) and the 256
    tokens before the first tool block.
AgentDojo: per attack episode, the first request after the injected text was read (the decision step); cluster = attack
    succeeded (security) or not; segments = 256 prompt tokens before the first injected block (pre), the injected blocks (inj),
    the rest of the prompt after them (post), the first 64 generated tokens (gen64) and the whole generation (gen).
ToolAlign: each step; cluster A = scenario type (safe / wrongdoing) on the first step of each document, cluster B = failure
    step vs log-only step inside wrongdoing scenarios; segments = the last user message of the prompt (doc), the generation
    before the first tool call (gen_pre), the whole generation (gen).
Usage: python cmp1_segs.py OUT_JSON"""
import json
import sys
from pathlib import Path

from transformers import AutoTokenizer

C = Path("/home/project-b/LJW/agentbench2/ana/cap")
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-4B", revision="851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a")
IM_START = tok.convert_tokens_to_ids("<|im_start|>")
USER = tok.encode("user", add_special_tokens=False)


def first_text_pos(ids, a, needle):
    """Token index (absolute) of the first token at or after a whose decoded text from a contains needle; None if absent."""
    text = tok.decode(ids[a:])
    c = text.find(needle)
    if c < 0:
        return None
    lo, hi = a, len(ids)
    while lo < hi:
        mid = (lo + hi) // 2
        if len(tok.decode(ids[a:mid + 1])) > c:
            hi = mid
        else:
            lo = mid + 1
    return lo


def last_user_span(ids, n_prompt):
    starts = [i for i in range(n_prompt) if ids[i] == IM_START]
    for s in reversed(starts):
        if ids[s + 1:s + 1 + len(USER)] == USER:
            e = next((i for i in starts if i > s), n_prompt)
            return s, e
    return None


def main():
    done = {}
    for b in ("am", "dojo"):
        done[b] = {json.loads(l)["seq"] for l in open(C / b / "index.jsonl")}
    done["ta"] = set(json.load(open(C / "ta_index_seqs.json")))
    L = {b: json.load(open(C / "labels" / f"labels_{b}.json")) for b in ("am", "dojo", "ta")}
    out = {"am": [], "dojo": [], "ta": []}
    for b in ("am", "dojo", "ta"):
        for line in open(C / "jobs" / f"jobs_{b}.jsonl"):
            j = json.loads(line)
            if j["sid"] not in done[b] or not L[b].get(j["sid"]):
                continue
            lab, ids, n = L[b][j["sid"]], j["ids"], j["n_prompt"]
            segs = []
            if b == "am":
                if lab["harmful"] is None:
                    continue
                for a, e in ((0, 256), (256, 512), (512, 768), (768, 1024), (1024, 1536), (1536, 2048), (2048, 3072), (3072, 4096)):
                    if n + a < len(ids):
                        segs.append([f"r{a}-{e}", n + a, min(n + e, len(ids))])
                t = first_text_pos(ids, n, "<tool_use")
                if t is not None and t - n >= 64:
                    segs.append(["pre_tool256", max(n, t - 256), t])
                out[b].append({"sid": j["sid"], "cluster": int(lab["harmful"]), "group": lab["condition"], "fold": lab["sample"] % 2,
                               "condition": lab["condition"], "segs": segs, "len": len(ids), "n_prompt": n})
            elif b == "dojo":
                if not (lab["attack"] and lab["first_after_injection"]) or lab["security"] is None:
                    continue
                sp = j.get("t1_spans") or []
                if not sp:
                    continue
                a0, a1 = min(x[0] for x in sp), max(x[1] for x in sp)
                segs = [["pre", max(0, a0 - 256), a0], ["inj_spans", a0, a1], ["post", a1, n], ["gen64", n, min(n + 64, len(ids))], ["gen", n, len(ids)]]
                segs = [s for s in segs if s[2] > s[1]]
                ut = f"{lab['suite']}|{lab['user_task']}"
                import hashlib
                out[b].append({"sid": j["sid"], "cluster": int(bool(lab["security"])), "group": ut, "suite": lab["suite"],
                               "fold": int(hashlib.md5(ut.encode()).hexdigest(), 16) % 2, "spans": sp, "segs": segs, "len": len(ids), "n_prompt": n,
                               "injection_task": lab["injection_task"]})
            else:
                u = last_user_span(ids, n)
                segs = []
                if u:
                    segs.append(["doc", u[0], u[1]])
                t = first_text_pos(ids, n, "<tool_call>")
                if t is not None and t > n:
                    segs.append(["gen_pre", n, t])
                if len(ids) > n:
                    segs.append(["gen", n, len(ids)])
                import hashlib
                out[b].append({"sid": j["sid"], "type": lab["type"], "kind": lab["kind"], "doc": lab["doc"], "step": lab["step"],
                               "group": lab["domain"], "fold": int(hashlib.md5(lab["domain"].encode()).hexdigest(), 16) % 2,
                               "condition": lab["condition"], "segs": segs, "len": len(ids), "n_prompt": n, "calls": lab["calls"]})
        print(b, len(out[b]))
    json.dump(out, open(sys.argv[1], "w"))


if __name__ == "__main__":
    main()
