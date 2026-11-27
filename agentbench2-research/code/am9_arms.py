"""L9c arms (PLAN.md Log 11-27 13:2x): the 4B concept-neuron procedure (am_concept_arms.py, vio8) on Qwen3.5-9B.
Candidates: layers 8-24, J-lens dictionary words (ne9/dict.npz, Qwen3.5-9B-Base J-lens) about violation (>= 3 of the top-10 +w words
or >= 2 of the top-3 start with one of STEMS). vio8_9b = the 8 candidates with the lowest harmful-vs-benign AUROC of the window
mean at response tokens 256-512 (ne9/amscan_s1.npy, pick prompts). Edit: add-dose 0.1 x layer residual norm / ||w|| at
generation steps 128-640. Random sets r1, r2: 8 random neurons of the same layers, same dose rule (seeds 91, 92).
Test prompts: the transfer prompts (not the pick prompts) with an L9a rate >= 4/16, at least the top 4; plus the pick prompts.
Usage: python am9_arms.py TAG L9A_JSONL PICK_CONDS(comma)  -> ne9/steer_am/arms_TAG.json"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_core as C
import ab_ne as N
from am_concept_arms import STEMS

T0, T1 = 128, 640


def main(tag, l9a, pick):
    NE = N.NE
    out = NE / "steer_am" / f"arms_{tag}.json"
    if out.exists():
        raise SystemExit(f"{out} exists; not overwritten")
    pick = pick.split(",")
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    dic = np.load(NE / os.environ.get("AB_DICT", "dict.npz"))
    pos, wn = dic["pos_i"], dic["wnorm"]
    V = int(pos.max()) + 1
    strs = [s.strip().lower() for s in tok.batch_decode([[i] for i in range(V)])]
    hit = np.array([any(s.startswith(st) for st in STEMS) for s in strs])
    cnt = hit[pos].sum(-1)
    top3 = hit[pos[:, :, :3]].sum(-1)
    cand = [(int(l), int(j)) for l, j in np.argwhere((cnt >= 3) | (top3 >= 2)) if 8 <= l <= 24]
    arr = np.load(NE / "amscan_s1.npy", mmap_mode="r")
    meta = json.loads((NE / "amscan_s1_meta.json").read_text(encoding="utf-8"))
    y = np.array([m["harm"] for m in meta]).astype(int)
    ok = np.array([m["bins"][1] for m in meta]) >= 128
    auc = {(l, j): N.auc1(np.asarray(arr[ok, 1, l, j], dtype=np.float32), y[ok]) for l, j in cand}
    vio8 = sorted(cand, key=lambda k: auc[k])[:8]
    rn = np.load(NE / "amscan_s1_resnorm.npy")
    sets, arms, info = {}, {"base": None}, {}

    def mk(ns, dose=0.1):
        return [[l, j, float(dose * rn[l] / wn[l, j]), 2.0] for l, j in ns]
    sets["vio8_9b"] = mk(vio8)
    arms["vio8_9b"] = {"set": "vio8_9b", "t0": T0, "t1": T1}
    used = set(vio8)
    for k, seed in ((1, 91), (2, 92)):
        rng = np.random.default_rng(seed)
        rr = []
        for l, _ in vio8:
            while True:
                j = int(rng.integers(0, N.NN))
                if (l, j) not in used and (l, j) not in set(cand):
                    break
            used.add((l, j))
            rr.append((l, j))
        sets[f"r{k}_vio8_9b"] = mk(rr)
        arms[f"r{k}_vio8_9b"] = {"set": f"r{k}_vio8_9b", "t0": T0, "t1": T1}
    info["vio8_9b"] = [{"neuron": f"L{l}/N{j}", "auroc_256_512": round(auc[(l, j)], 3), "match": int(cnt[l, j]), "words": N.words(tok, dic, l, j, 1, 8)}
                       for l, j in vio8]
    info["candidates"] = len(cand)
    info["dictionary"] = os.environ.get("AB_DICT", "dict.npz")
    info["scan"] = {"samples": int(ok.sum()), "harmful": int(y[ok].sum()), "pick": pick}
    by = {}
    for line in open(l9a, encoding="utf-8"):
        r = json.loads(line)
        c = by.setdefault(r["condition"], [0, 0])
        c[0] += 1
        c[1] += r["harm"]
    rate = {c: v[1] / v[0] for c, v in by.items() if v[0]}
    tr = sorted((c for c in rate if c not in pick), key=lambda c: -rate[c])
    first16 = {}
    for line in open(l9a, encoding="utf-8"):
        r = json.loads(line)
        if r["seed"] < 16:
            v = first16.setdefault(r["condition"], [0, 0])
            v[0] += 1
            v[1] += r["harm"]
    test = [c for c in tr if first16.get(c, [0, 0])[1] >= 4]
    if len(test) < 4:
        test = tr[:4]
    info["test_prompts"] = {c: first16.get(c) for c in test}
    info["pick_prompts"] = {c: by.get(c) for c in pick}
    spec = {"arms": arms, "sets": sets, "conditions": test + pick, "transfer": test, "pick": pick, "seeds": 12, "seed_off": 20000, "budget": 6144,
            "extra_units": "extra_units_t9g.json", "info": info, "window": [T0, T1]}
    out.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    print("candidates", len(cand), "layers", sorted(Counter(l for l, _ in cand).items()))
    for r in info["vio8_9b"]:
        print("  ", r["neuron"], "AUROC", r["auroc_256_512"], "match", r["match"], " ".join(repr(w) for w in r["words"]))
    print("random", {k: [(x[0], x[1], round(x[2], 2)) for x in v] for k, v in sets.items() if k.startswith("r")})
    print("test prompts", info["test_prompts"], "pick", info["pick_prompts"])
    print("AM9_ARMS_DONE", tag)


if __name__ == "__main__":
    main(*sys.argv[1:])
