"""Steering sets for the AM loop, from am18_types.json (whole-prompt window, top 12 per level, layers >= 2):
REP = urgency replacement, RES = urgency restriction, CALM = urgency none, AMER = goal explicit-america.
RAND = 12 neurons drawn (numpy seed 0) with the pooled layer histogram of the four sets, random pole, none of them in a set.
Each entry [layer, neuron, pole_sign]: pole_sign +1 for a neuron that fires on its + side, -1 for the - side, so a "+" arm
pushes every neuron the way it fires on that prompt type.
Usage: python am_make_sets.py AM18_TYPES_JSON OUT_JSON"""
import json
import sys

import numpy as np

SRC = {"REP": "prompt|urgency|replacement", "RES": "prompt|urgency|restriction", "CALM": "prompt|urgency|none",
       "AMER": "prompt|goal|explicit-america"}


def main():
    js = json.load(open(sys.argv[1], encoding="utf-8"))
    sets = {}
    for k, key in SRC.items():
        sets[k] = [[r["layer"], r["n"], 1 if r["sign"] == "+" else -1] for r in js[key]["top"][:12]]
    used = {(l, n) for v in sets.values() for l, n, _ in v}
    layers = [l for v in sets.values() for l, _, _ in v]
    rng = np.random.default_rng(0)
    rand = []
    for l in rng.choice(layers, 12, replace=False):
        while True:
            n = int(rng.integers(0, 9216))
            if (int(l), n) not in used:
                break
        used.add((int(l), n))
        rand.append([int(l), n, int(rng.choice([1, -1]))])
    sets["RAND"] = rand
    json.dump(sets, open(sys.argv[2], "w"), indent=1)
    for k, v in sets.items():
        print(k, v)


if __name__ == "__main__":
    main()
