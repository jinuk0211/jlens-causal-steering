"""Natural activation of the steering-set neurons in the stored agentic-misalignment responses (no steering).
For each response of the chosen scenarios (am_resp_cases.json, the original vLLM samples with the classifier label):
teacher-forced pass over prompt + response, the 60 set neurons (sets.json) recorded; windows prompt [1, onset),
pre_tool [onset, first tool_use) (or to the end if none), resp [onset, end). Output one json line per response.
Usage: python3 ntrace_am.py CASES_JSON SETS_JSON SCENARIOS(comma) OUT_JSONL"""
import json
import os
import sys
import time
import urllib.request

API = "http://127.0.0.1:8791"


def main():
    cases = json.load(open(sys.argv[1], encoding="utf-8"))
    sets = json.load(open(sys.argv[2]))
    scen = sys.argv[3].split(",")
    out = sys.argv[4]
    neurons, names = [], []
    for s, v in sets.items():
        for l, n, p in v:
            neurons.append([l, n, p])
            names.append(f"{s}:L{l}/N{n}{'+' if p > 0 else '-'}")
    done = set()
    if os.path.exists(out):
        done = {json.loads(x)["key"] for x in open(out, encoding="utf-8")}
    todo = [c for c in cases if c["scenario"] in scen and c["key"] not in done]
    t0 = time.time()
    for k, c in enumerate(todo):
        ids = c["ids"][:c["pos"] + 1]
        on, tool = c["onset"], (c.get("ev") or {}).get("tool")
        wins = {"prompt": [1, on], "pre_tool": [on, tool if tool else len(ids)], "resp": [on, len(ids)]}
        r = urllib.request.Request(API + "/api/ntrace", data=json.dumps({"ids": ids, "neurons": neurons, "windows": wins}).encode(),
                                   headers={"Content-Type": "application/json"})
        res = json.loads(urllib.request.urlopen(r, timeout=3600).read())
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": c["key"], "condition": c["condition"], "scenario": c["scenario"], "harmful": c["harmful"],
                                "marker": c["marker"], "truncated": c.get("truncated"), "tokens": len(ids), "onset": on, "tool": tool,
                                "names": names, "w": res}) + "\n")
        if k % 10 == 0:
            print(f"{time.strftime('%H:%M:%S')} {k + 1}/{len(todo)} {len(ids)} tok {time.time() - t0:.0f}s", flush=True)
    print("NTRACE_DONE", flush=True)


if __name__ == "__main__":
    main()
