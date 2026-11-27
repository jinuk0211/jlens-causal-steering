"""T9f and T9g specs (OVERNIGHT2.md, 11-27 00:0x), built from the round-4 spec arms_t9d4.json and the T9e spec arms_t9e.json.
The edit is the round-4 one: add-dose on the 8 concept neurons (vio8), per-neuron size = dose x layer residual norm / ||w||.
  python am_t9f_arms.py t9f          -> arms_t9f.json : window, sign, depth and dose variants of vio8 on the two original prompts
  python am_t9f_arms.py t9g1         -> arms_t9g1.json: base only on the 14 transfer prompts (other goal values), 16 seeds
  python am_t9f_arms.py t9g2 C1,C2   -> arms_t9g2.json: base, vio8 at dose 0.1 and two random sets on the chosen transfer prompts
  python am_t9f_arms.py t9h          -> arms_t9h.json : base, vio8 at dose 0.1 and 19 new random sets (same layers, same dose rule)"""
import json
import sys
from pathlib import Path

OUT = Path("/home/project-b/LJW/agentbench2/ana/ne/steer_am")
CONDS = ("leaking_explicit-america_none", "leaking_explicit-america_replacement")
T0, T1 = 128, 640


def scaled(s, k):
    return [[l, j, float(v * k), side] for l, j, v, side in s]


def main(tag, *args):
    d4 = json.loads((OUT / "arms_t9d4.json").read_text(encoding="utf-8"))
    e = json.loads((OUT / "arms_t9e.json").read_text(encoding="utf-8"))
    v = d4["sets"]["vio8_d0.1"]
    if tag == "t9f":
        sets = {"vio8_d0.1": v, "neg_d0.1": scaled(v, -1.0), "vio8_d0.05": scaled(v, 0.5), "vio8_d0.15": scaled(v, 1.5),
                "late3_d0.1": [x for x in v if x[0] >= 21], "mid5_d0.1": [x for x in v if x[0] < 21]}
        arms = {"base": None, "vio8_d0.1": {"set": "vio8_d0.1", "t0": T0, "t1": T1}}
        for a, b in ((0, 128), (128, 384), (384, 640), (640, 1152)):
            arms[f"w{a}_{b}"] = {"set": "vio8_d0.1", "t0": a, "t1": b}
        arms["wall"] = {"set": "vio8_d0.1", "t0": 0, "t1": 100000}
        for nm in ("neg_d0.1", "late3_d0.1", "mid5_d0.1", "vio8_d0.05", "vio8_d0.15"):
            arms[nm] = {"set": nm, "t0": T0, "t1": T1}
        spec = {"arms": arms, "sets": sets, "conditions": list(CONDS), "seeds": 24, "seed_off": 6000, "budget": 6144}
    elif tag == "t9g1":
        ext = json.loads((OUT / "extra_units_t9g.json").read_text(encoding="utf-8"))
        spec = {"arms": {"base": None}, "sets": {}, "conditions": [u["condition"] for u in ext], "seeds": 16, "seed_off": 7000, "budget": 6144,
                "extra_units": "extra_units_t9g.json"}
    elif tag == "t9g2":
        sets = {k: e["sets"][k] for k in ("vio8_d0.1", "r_vio8_d0.1", "r2_vio8_d0.1")}
        arms = {"base": None}
        for k in sets:
            arms[k] = {"set": k, "t0": T0, "t1": T1}
        spec = {"arms": arms, "sets": sets, "conditions": args[0].split(","), "seeds": 24, "seed_off": 7100, "budget": 6144,
                "extra_units": "extra_units_t9g.json"}
    elif tag == "t9i":
        units = json.loads((OUT.parent.parent / "am" / "units.json").read_text(encoding="utf-8"))
        conds = sorted({u["condition"] for u in units} - set(CONDS))
        sets = {k: e["sets"][k] for k in ("vio8_d0.1", "r2_vio8_d0.1")}
        arms = {"base": None}
        for k in sets:
            arms[k] = {"set": k, "t0": T0, "t1": T1}
        spec = {"arms": arms, "sets": sets, "conditions": conds, "seeds": 8, "seed_off": 9000, "budget": 6144}
    elif tag in ("t9j1", "t9j2"):
        a, b = int(args[0]), int(args[1])
        names = ("vio8_d0.1", "r_vio8_d0.1", "r2_vio8_d0.1", "r3_vio8_d0.1") if tag == "t9j1" else ("vio8_d0.1", "r_vio8_d0.1", "r2_vio8_d0.1")
        sets = {k: e["sets"][k] for k in names}
        arms = {"base": None}
        for k in sets:
            arms[k] = {"set": k, "t0": a, "t1": b}
        if tag == "t9j1":
            spec = {"arms": arms, "sets": sets, "conditions": list(CONDS), "seeds": 32, "seed_off": 10000, "budget": 6144, "window": [a, b]}
        else:
            g2 = json.loads((OUT / "arms_t9g2.json").read_text(encoding="utf-8"))
            spec = {"arms": arms, "sets": sets, "conditions": g2["conditions"], "seeds": 16, "seed_off": 10100, "budget": 6144, "window": [a, b],
                    "extra_units": "extra_units_t9g.json"}
    elif tag == "t9n":
        g2 = json.loads((OUT / "arms_t9g2.json").read_text(encoding="utf-8"))
        mid5 = [x for x in v if x[0] < 21]
        sets = {"vio8_d0.1": v, "vio8_d0.075": scaled(v, 0.75), "mid5_d0.1": mid5, "mid5_d0.15": scaled(mid5, 1.5)}
        arms = {"base": None}
        for k in sets:
            arms[k] = {"set": k, "t0": T0, "t1": T1}
        spec = {"arms": arms, "sets": sets, "conditions": list(CONDS) + g2["conditions"], "seeds": 12, "seed_off": 12000, "budget": 6144,
                "extra_units": "extra_units_t9g.json"}
    elif tag == "t9p":
        g2 = json.loads((OUT / "arms_t9g2.json").read_text(encoding="utf-8"))
        h = json.loads((OUT / "arms_t9h.json").read_text(encoding="utf-8"))
        mid5 = [x for x in v if x[0] < 21]
        ra = [x for x in h["sets"]["rs01"] if x[0] < 21]
        rb = [x for x in h["sets"]["rs02"] if x[0] < 21]
        sets = {"mid5_d0.1": mid5, "mid5_d0.15": scaled(mid5, 1.5), "ra_mid5_d0.1": ra, "rb_mid5_d0.1": rb,
                "ra_mid5_d0.15": scaled(ra, 1.5), "rb_mid5_d0.15": scaled(rb, 1.5)}
        arms = {"base": None}
        for k in sets:
            arms[k] = {"set": k, "t0": T0, "t1": T1}
        spec = {"arms": arms, "sets": sets, "conditions": list(CONDS) + g2["conditions"], "seeds": 8, "seed_off": 13000, "budget": 6144,
                "extra_units": "extra_units_t9g.json"}
    elif tag == "t9q":
        sets = {k: e["sets"][k] for k in ("vio8_d0.1", "r2_vio8_d0.1", "r3_vio8_d0.1")}
        arms = {"base": None}
        for k in sets:
            arms[k] = {"set": k, "t0": T0, "t1": T1}
        spec = {"arms": arms, "sets": sets, "conditions": [c + "+dont" for c in CONDS], "seeds": 18, "seed_off": 14000, "budget": 6144,
                "extra_units": "extra_units_t9m.json"}
    elif tag == "t9r":
        g2 = json.loads((OUT / "arms_t9g2.json").read_text(encoding="utf-8"))
        sets = {k: e["sets"][k] for k in ("vio8_d0.1", "r2_vio8_d0.1", "r3_vio8_d0.1")}
        arms = {"base": None}
        for k in sets:
            arms[k] = {"set": k, "t0": T0, "t1": T1}
        spec = {"arms": arms, "sets": sets, "conditions": [c + "+dont" for c in g2["conditions"]], "seeds": 12, "seed_off": 15000, "budget": 6144,
                "extra_units": "extra_units_t9m.json"}
    elif tag == "t9m":
        ext = json.loads((OUT / "extra_units_t9m.json").read_text(encoding="utf-8"))
        spec = {"arms": {"base": None}, "sets": {}, "conditions": [u["condition"] for u in ext], "seeds": 32, "seed_off": 11000, "budget": 6144,
                "extra_units": "extra_units_t9m.json"}
    elif tag == "t9h":
        import numpy as np
        ana = OUT.parent.parent
        wn = np.load(ana / "ne" / "dict.npz")["wnorm"]
        rn = np.load(ana / "search" / "am" / "refstats.npz")["resnorm"]
        cands = json.loads((ana / "ne" / "am_concept_cands.json").read_text(encoding="utf-8"))
        used = {(int(x[0]), int(x[1])) for k in e["sets"] for x in e["sets"][k]}
        text = json.dumps(cands)
        import re
        used |= {(int(a), int(b)) for a, b in re.findall(r"L(\d+)/N(\d+)", text)}
        rng = np.random.default_rng(91)
        sets, arms = {"vio8_d0.1": v}, {"base": None, "vio8_d0.1": {"set": "vio8_d0.1", "t0": T0, "t1": T1}}
        for k in range(1, 20):
            s = []
            for l, _, _, side in v:
                while True:
                    j = int(rng.integers(0, wn.shape[1]))
                    if (int(l), j) not in used:
                        break
                used.add((int(l), j))
                s.append([int(l), j, float(0.1 * rn[int(l)] / wn[int(l), j]), side])
            sets[f"rs{k:02d}"] = s
            arms[f"rs{k:02d}"] = {"set": f"rs{k:02d}", "t0": T0, "t1": T1}
        spec = {"arms": arms, "sets": sets, "conditions": list(CONDS), "seeds": 12, "seed_off": 8000, "budget": 6144, "excluded": len(used)}
    else:
        raise SystemExit("unknown tag")
    f = OUT / f"arms_{tag}.json"
    if f.exists():
        raise SystemExit(f"{f} exists; not overwritten")
    f.write_text(json.dumps(spec), encoding="utf-8")
    print(tag, list(spec["arms"]), spec["conditions"], spec["seeds"], spec["seed_off"])
    for k, s in spec["sets"].items():
        print("  ", k, [(x[0], x[1], round(x[2], 2)) for x in s])


if __name__ == "__main__":
    main(*sys.argv[1:])
