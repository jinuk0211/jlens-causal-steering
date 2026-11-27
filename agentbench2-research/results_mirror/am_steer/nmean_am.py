"""All-neuron mean activation over the reasoning of every stored agentic-misalignment response (/api/nmean).
Windows: pre_tool = [onset, first tool_use) (whole reply if no tool use), pre256 = the last 256 tokens of pre_tool.
One npz per response under NE_DUMP_DIR/nmean (resumable), plus index.jsonl with the labels.
Usage: python3 nmean_am.py CASES_JSON OUT_DIR"""
import json
import os
import sys
import time
import urllib.request

API = "http://127.0.0.1:8791"


def main():
    cases = json.load(open(sys.argv[1], encoding="utf-8"))
    od = sys.argv[2]
    os.makedirs(od, exist_ok=True)
    idx_p = os.path.join(od, "index.jsonl")
    done = set()
    if os.path.exists(idx_p):
        done = {json.loads(x)["key"] for x in open(idx_p, encoding="utf-8")}
    t0 = time.time()
    todo = [c for c in cases if c["key"] not in done]
    for k, c in enumerate(todo):
        ids = c["ids"][:c["pos"] + 1]
        on, tool = c["onset"], (c.get("ev") or {}).get("tool")
        end = tool if tool else len(ids)
        wins = {"pre_tool": [on, end], "pre256": [max(on, end - 256), end]}
        name = "am_" + c["key"].split("|", 1)[1].replace("|", "_") + ".npz"
        r = urllib.request.Request(API + "/api/nmean", data=json.dumps({"ids": ids, "windows": wins, "out": name}).encode(),
                                   headers={"Content-Type": "application/json"})
        res = json.loads(urllib.request.urlopen(r, timeout=3600).read())
        with open(idx_p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": c["key"], "file": res["out"], "condition": c["condition"], "scenario": c["scenario"],
                                "sample_id": c["sample_id"], "harmful": c["harmful"], "marker": c["marker"],
                                "tool": tool, "onset": on, "tokens": len(ids)}) + "\n")
        if k % 20 == 0:
            print(f"{time.strftime('%H:%M:%S')} {k + 1}/{len(todo)} {len(ids)} tok {time.time() - t0:.0f}s", flush=True)
    print("NMEAN_DONE", flush=True)


if __name__ == "__main__":
    main()
