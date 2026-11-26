"""AM steering loop runner (2080 Ti, explorer server /api/am_gen). PROTOCOL.md in the same directory fixes the design.
sets.json: {"REP": [[layer, n, pole_sign], ...], ...}. Arms per batch: base, then for every set SETx0 (the set's
activations multiplied by 0 = ablated) and SETxK (multiplied by K = amplified where they fire), at every position.
All arms of one (condition, seed) run in one batch and share the sampling seed (Gumbel-max, per-row CUDA generator).
Order is seed-major (every condition gets seed a first). Resumable: (stage, condition, seed) already in the rows file is
skipped. A file STOP in DIR stops the runner after the current batch.
Usage: python3 am_steer_runner.py DIR STAGE K SEEDS(a-b) MAX_NEW ROWS_FILE [CONDITION_SUBSTRINGS comma-separated]"""
import hashlib
import json
import os
import sys
import time
import urllib.request

API = "http://127.0.0.1:8791"


def post(p, b, timeout=7200):
    r = urllib.request.Request(API + p, data=json.dumps(b).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read())


def main():
    d, stage, k = sys.argv[1], sys.argv[2], float(sys.argv[3])
    a, b = map(int, sys.argv[4].split("-"))
    max_new, rows_p = int(sys.argv[5]), os.path.join(d, sys.argv[6])
    filt = sys.argv[7].split(",") if len(sys.argv) > 7 else None
    sets = json.load(open(os.path.join(d, "sets.json")))
    cases = json.loads(urllib.request.urlopen(API + "/api/cases", timeout=60).read())
    conds = sorted((c["domain"], c["i"]) for c in cases if c["group"] == "am_prompt" and (not filt or any(f in c["domain"] for f in filt)))
    done = set()
    if os.path.exists(rows_p):
        for line in open(rows_p, encoding="utf-8"):
            r = json.loads(line)
            done.add((r["stage"], r["condition"], r["seed"]))
    kt = f"{k:g}"
    arms = [("base", [])]
    for name, neurons in sets.items():
        arms.append((f"{name}x0", [[l, n, 0.0, "mul"] for l, n, _ in neurons]))
        arms.append((f"{name}x{kt}", [[l, n, k, "mul"] for l, n, _ in neurons]))
    t0 = time.time()
    for seed in range(a, b + 1):
        for cond, ci in conds:
            if os.path.exists(os.path.join(d, "STOP")):
                print("STOP file, exiting", flush=True)
                return
            if (stage, cond, seed) in done:
                continue
            s = int(hashlib.md5(f"{cond}|{seed}".encode()).hexdigest()[:8], 16)
            rows = [{"arm": arm, "seed": s, "pushes": pushes} for arm, pushes in arms]
            res = post("/api/am_gen", {"case": ci, "rows": rows, "max_new": max_new, "temperature": 1.0,
                                       "scenario": cond.split("_")[0]})
            with open(rows_p, "a", encoding="utf-8") as f:
                for r in res["rows"]:
                    f.write(json.dumps({"stage": stage, "k": k, "condition": cond, "seed": seed, **r}) + "\n")
            mk = [r["arm"] for r in res["rows"] if r["marker"]]
            print(f"{time.strftime('%H:%M:%S')} {stage} seed {seed} {cond}: {res['steps']} steps {res['sec']}s (fwd {res.get('fwd_sec')}s), "
                  f"markers {len(mk)}/{len(rows)} {mk} total {time.time() - t0:.0f}s", flush=True)
    print(f"STAGE_DONE {stage}", flush=True)


if __name__ == "__main__":
    main()
