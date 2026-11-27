"""T9d round 4 arms (OVERNIGHT2.md, 11-26 21:5x): concept-picked neurons for AM, the neuron-explorer way.
Candidates = neurons of layers 8-24 whose J-lens dictionary words are about violation (at least 3 of the top-10 +w tokens, or 2 of the
top-3, start with one of STEMS). Two sets of 8:
  vio8  = the candidates with the lowest harmful-vs-benign AUROC of the window mean at response tokens 256-512 (most benign-side);
  viow8 = the candidates with the most matching words, no label used (ties by layer, neuron).
Edit: add-dose at generation steps T0..T1 only, da = dose x layer residual norm / ||w|| (neuron-explorer's size), dose per neuron.
Random controls: 8 random neurons of the same layers, same doses.
Usage: python am_concept_arms.py TAG   -> ne/steer_am/arms_TAG.json"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_core as C
import ab_ne as N

A = Path("/home/project-b/LJW/agentbench2/ana")
NE = A / "ne"
STEMS = ("violat", "breach", "unauthor", "classified", "confidential", "illegal", "prohibit", "forbid", "unlawful", "leak", "disclos", "improper",
         "wrongdoing", "misconduct", "unethical")
T0, T1 = 128, 640


def main(tag):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    dic = np.load(NE / "dict.npz")
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
    viow8 = sorted(cand, key=lambda k: (-int(cnt[k]), k))[:8]
    rn = np.load(A / "search" / "am" / "refstats.npz")["resnorm"]
    rng = np.random.default_rng(71)
    sets, arms, info = {}, {"base": None}, {}

    def mk(ns, dose):
        return [[l, j, float(dose * rn[l] / wn[l, j]), 2.0] for l, j in ns]
    for nm, ns in (("vio8", vio8), ("viow8", viow8)):
        rr = [(l, int(rng.integers(0, N.NN))) for l, _ in ns]
        info[nm] = [{"neuron": f"L{l}/N{j}", "auroc_256_512": round(auc[(l, j)], 2), "match": int(cnt[l, j]), "words": N.words(tok, dic, l, j, 1, 8)} for l, j in ns]
        for dose in ((0.1, 0.2) if nm == "vio8" else (0.2,)):
            sets[f"{nm}_d{dose}"], sets[f"r_{nm}_d{dose}"] = mk(ns, dose), mk(rr, dose)
            arms[f"{nm}_d{dose}"] = {"set": f"{nm}_d{dose}", "t0": T0, "t1": T1}
            arms[f"r_{nm}_d{dose}"] = {"set": f"r_{nm}_d{dose}", "t0": T0, "t1": T1}
    (NE / "steer_am" / f"arms_{tag}.json").write_text(json.dumps({"arms": arms, "sets": sets, "conditions": list(N.AM_CONDS), "seeds": 24, "seed_off": 4000,
                                                                 "budget": 6144, "info": info, "candidates": len(cand), "window": [T0, T1]}, ensure_ascii=False), encoding="utf-8")
    print("candidates", len(cand), "arms", list(arms))
    for nm in info:
        print(nm)
        for r in info[nm]:
            print("  ", r["neuron"], "AUROC", r["auroc_256_512"], "match", r["match"], " ".join(repr(w) for w in r["words"]))


if __name__ == "__main__":
    main(sys.argv[1])
