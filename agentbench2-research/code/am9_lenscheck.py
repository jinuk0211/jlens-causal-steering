"""L9 lens check (PLAN.md Log 11-27 13:3x). On 4B, where the result is known, apply the frozen candidate and vio8 rules
(am_concept_arms.py) with three dictionaries: the GPU J-lens dictionary used on 11-26 (ne/dict.npz), the same J-lens on the CPU
(implementation check) and the 4B instruct J++ lens on the CPU. Rule: if the J++ vio8 shares >= 6 of the 8 original vio8 neurons,
9B uses its instruct J++ lens, else the Qwen3.5-9B-Base J-lens. No 9B outcome is used. -> ne9/LENS_CHOICE.json
Usage: python am9_lenscheck.py DICT_J_CPU DICT_JPP_CPU"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_core as C
import ab_ne as N
from am_concept_arms import STEMS

A = Path("/home/project-b/LJW/agentbench2/ana")
VIO8 = [(21, 2518), (24, 1497), (15, 6484), (17, 9111), (21, 2538), (12, 5432), (12, 8975), (13, 5772)]


def pick(dic, strs_hit, arr, y, ok):
    pos = dic["pos_i"]
    cnt = strs_hit[pos].sum(-1)
    top3 = strs_hit[pos[:, :, :3]].sum(-1)
    cand = [(int(l), int(j)) for l, j in np.argwhere((cnt >= 3) | (top3 >= 2)) if 8 <= l <= 24]
    auc = {(l, j): N.auc1(np.asarray(arr[ok, 1, l, j], dtype=np.float32), y[ok]) for l, j in cand}
    return cand, sorted(cand, key=lambda k: auc[k])[:8]


def main(dj_cpu, djpp_cpu):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    paths = (A / "ne" / "dict.npz", dj_cpu, djpp_cpu)
    V = max(int(np.load(p)["pos_i"].max()) for p in paths) + 1
    strs = [s.strip().lower() for s in tok.batch_decode([[i] for i in range(V)])]
    hit = np.array([any(s.startswith(st) for st in STEMS) for s in strs])
    arr = np.load(A / "ne" / "amscan_s1.npy", mmap_mode="r")
    meta = json.loads((A / "ne" / "amscan_s1_meta.json").read_text(encoding="utf-8"))
    y = np.array([m["harm"] for m in meta]).astype(int)
    ok = np.array([m["bins"][1] for m in meta]) >= 128
    res = {}
    for name, p in zip(("j_gpu", "j_cpu", "jpp_cpu"), paths):
        cand, v8 = pick(np.load(p), hit, arr, y, ok)
        res[name] = {"candidates": len(cand), "vio8": [f"L{l}/N{j}" for l, j in v8], "shared_with_original_vio8": len(set(v8) & set(VIO8)),
                     "_cand": cand}
    cj, cc, cp = (set(res[k].pop("_cand")) for k in ("j_gpu", "j_cpu", "jpp_cpu"))
    res["candidate_overlap"] = {"j_gpu&j_cpu": len(cj & cc), "j_gpu&jpp": len(cj & cp)}
    res["implementation_ok"] = res["j_gpu"]["shared_with_original_vio8"] == 8 and res["j_cpu"]["shared_with_original_vio8"] >= 7
    res["choice"] = "jpp" if res["jpp_cpu"]["shared_with_original_vio8"] >= 6 else "jbase"
    out = A / "ne9" / "LENS_CHOICE.json"
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    if not res["implementation_ok"]:
        raise SystemExit("LENSCHECK_IMPLEMENTATION_MISMATCH")
    print("LENSCHECK_DONE", res["choice"])


if __name__ == "__main__":
    main(*sys.argv[1:])
