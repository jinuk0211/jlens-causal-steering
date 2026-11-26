"""One pilot batch (not part of the results): all arms on one condition and seed, to check speed and output sanity.
Usage: python3 am_pilot.py DIR CONDITION DOSE SEED MAX_NEW OUT_JSON"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, "/workspace/tj")
from am_markers import degenerate

API = "http://127.0.0.1:8791"


def main():
    d, cond, dose, seed, max_new, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
    sets = json.load(open(os.path.join(d, "sets.json")))
    cases = json.loads(urllib.request.urlopen(API + "/api/cases", timeout=60).read())
    ci = next(c["i"] for c in cases if c["group"] == "am_prompt" and c["domain"] == cond)
    rows = [{"arm": "base", "seed": seed, "pushes": []}]
    for name, neurons in sets.items():
        for sg, tag in ((1, "+"), (-1, "-")):
            rows.append({"arm": name + tag, "seed": seed, "pushes": [[l, n, sg * p * dose] for l, n, p in neurons]})
    r = urllib.request.Request(API + "/api/am_gen", data=json.dumps({"case": ci, "rows": rows, "max_new": max_new, "temperature": 1.0,
                               "scenario": cond.split("_")[0]}).encode(), headers={"Content-Type": "application/json"})
    res = json.loads(urllib.request.urlopen(r, timeout=7200).read())
    json.dump(res, open(out, "w"))
    print("steps", res["steps"], "sec", res["sec"], "ms/step", round(1000 * res["sec"] / res["steps"], 1))
    for x in res["rows"]:
        print(f"{x['arm']:7s} {x['stop']:8s} n={x['n_tokens']:5d} marker={x['marker']} degen={degenerate(x['text'])} | "
              + x["text"][:160].replace("\n", " "))


if __name__ == "__main__":
    main()
