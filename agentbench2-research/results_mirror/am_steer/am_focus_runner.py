"""Focused AM steering runner (PROTOCOL.md amendment 2). Like am_steer_runner.py, but the arms come from a json list
[[arm_name, set_name or null, multiplier], ...] (multiplicative 'mul' steering of the set's 12 neurons at every position;
null = base). All arms of one (condition, seed) run in one batch with a shared sampling seed. Resumable; STOP_F file stops it.
Usage: python3 am_focus_runner.py DIR STAGE ARMS_JSON SEEDS(a-b) MAX_NEW ROWS_FILE CONDITION_SUBSTRINGS(comma-separated)"""
import hashlib
import json
import os
import sys
import time
import urllib.request

API = "http://127.0.0.1:8791"


def post(p, b, timeout=14400):
    r = urllib.request.Request(API + p, data=json.dumps(b).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read())


def main():
    d, stage, arms_p = sys.argv[1], sys.argv[2], sys.argv[3]
    a, b = map(int, sys.argv[4].split("-"))
    max_new, rows_p, filt = int(sys.argv[5]), os.path.join(d, sys.argv[6]), sys.argv[7].split(",")
    sets = json.load(open(os.path.join(d, "sets.json")))
    spec = json.load(open(os.path.join(d, arms_p)))
    arms = [(name, [] if s is None else [[l, n, float(k), "mul"] for l, n, _ in sets[s]]) for name, s, k in spec]
    cases = json.loads(urllib.request.urlopen(API + "/api/cases", timeout=60).read())
    conds = sorted((c["domain"], c["i"]) for c in cases if c["group"] == "am_prompt" and any(f in c["domain"] for f in filt))
    done = set()
    if os.path.exists(rows_p):
        for line in open(rows_p, encoding="utf-8"):
            r = json.loads(line)
            done.add((r["stage"], r["condition"], r["seed"]))
    t0 = time.time()
    for seed in range(a, b + 1):
        for cond, ci in conds:
            if os.path.exists(os.path.join(d, "STOP_F")):
                print("STOP_F file, exiting", flush=True)
                return
            if (stage, cond, seed) in done:
                continue
            s = int(hashlib.md5(f"{cond}|{seed}".encode()).hexdigest()[:8], 16)
            rows = [{"arm": arm, "seed": s, "pushes": pushes} for arm, pushes in arms]
            res = post("/api/am_gen", {"case": ci, "rows": rows, "max_new": max_new, "temperature": 1.0,
                                       "scenario": cond.split("_")[0]})
            with open(rows_p, "a", encoding="utf-8") as f:
                for r in res["rows"]:
                    f.write(json.dumps({"stage": stage, "condition": cond, "seed": seed, **r}) + "\n")
            mk = [r["arm"] for r in res["rows"] if r["marker"]]
            print(f"{time.strftime('%H:%M:%S')} {stage} seed {seed} {cond}: {res['steps']} steps {res['sec']}s, markers {len(mk)}/{len(rows)} {mk} "
                  f"total {time.time() - t0:.0f}s", flush=True)
    print(f"STAGE_DONE {stage}", flush=True)


if __name__ == "__main__":
    main()
