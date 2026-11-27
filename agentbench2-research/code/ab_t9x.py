"""T9x (PLAN.md Log 11-27 20:4x, user: "지금 너가 말한걸 확인하는 실험안되냐"): two checks of the explanation of why the AgentDojo
reading-stage clamp did not carry over to AM.
  units  : CPU. X1, cue redundancy (base only). Leaking prompts with the goal statement (A) and the goal-conflict emails (B) on or off,
           urgency none and replacement: A+B = explicit-america, B only = latent-america (official), A only = the explicit system
           prompt over the none-goal emails (built here), neither = none-none. -> ne/steer_am/extra_units_t9x1.json, arms_t9x1.json
  unr    : CPU. X2, concept specificity. For each vio8 neuron, in its layer, the neuron whose top-10 dictionary tokens best match one
           unrelated concept (fixed order below; >= 3 of the top 10 or >= 2 of the top 3 starting with a stem; else +-1, +-2, +-3
           layers). Dose as vio8: 0.1 x layer residual norm / ||w||, add at generation steps 128-640. Arms base, vio8_d0.1, unr8_d0.1
           and the T9e random set r2_vio8_d0.1. -> ne/steer_am/arms_t9x2.json, ne/t9x2_unr.json"""
import json
import sys
from pathlib import Path

import numpy as np

A = Path("/home/project-b/LJW/agentbench2/ana")
NE = A / "ne"
sys.path.insert(0, str(A))
NN = 9216
MAIN = ("leaking_explicit-america_none", "leaking_explicit-america_replacement")
CONCEPTS = [("food", ("cook", "recipe", "food", "kitchen", "bake", "delicious", "meal", "soup", "bread", "pizza", "食")),
            ("weather", ("rain", "weather", "sunny", "snow", "storm", "cloud", "wind", "humid", "雨", "天气")),
            ("sports", ("football", "soccer", "basketball", "tennis", "athlet", "golf", "baseball", "sport", "olymp", "球")),
            ("music", ("music", "song", "guitar", "piano", "melod", "concert", "singer", "drum", "violin", "音乐")),
            ("animals", ("dog", "cat", "animal", "bird", "horse", "pupp", "kitten", "wildlife", "狗", "猫")),
            ("colors", ("red", "blue", "green", "yellow", "purple", "orange", "color", "colour", "pink", "色")),
            ("clothing", ("shirt", "dress", "shoe", "jacket", "cloth", "fashion", "coat", "hat", "衣")),
            ("vehicles", ("car", "truck", "bicycl", "vehicle", "bus", "train", "motorcycl", "wheel", "车")),
            ("geography", ("mountain", "river", "ocean", "island", "beach", "lake", "valley", "forest", "山")),
            ("cooking2", ("chef", "restaurant", "dessert", "cake", "cheese", "coffee", "tea", "茶"))]


def mode_units():
    from transformers import AutoTokenizer
    import ab_core as C
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    U = {u["condition"]: u for u in json.loads((A / "r3" / "am_units.json").read_text(encoding="utf-8"))}
    ext, conds = [], []
    for urg in ("none", "replacement"):
        for name, src in ((f"leaking_AB_{urg}", f"leaking_explicit-america_{urg}"), (f"leaking_Bonly_{urg}", f"leaking_latent-america_{urg}"),
                          (f"leaking_neither_{urg}", f"leaking_none-none_{urg}")):
            ext.append({"condition": name, "prompt_ids": U[src]["prompt_ids"], "scenario": "leaking", "source": src})
            conds.append(name)
        sysp = U[f"leaking_explicit-america_{urg}"]["system"]
        user = U[f"leaking_none-none_{urg}"]["user"]
        ids = tok.encode(tok.apply_chat_template([{"role": "system", "content": sysp}, {"role": "user", "content": user}], add_generation_prompt=True,
                                                 tokenize=False, enable_thinking=False), add_special_tokens=False)
        ext.append({"condition": f"leaking_Aonly_{urg}", "prompt_ids": ids, "scenario": "leaking",
                    "source": f"system of leaking_explicit-america_{urg} + user of leaking_none-none_{urg}"})
        conds.append(f"leaking_Aonly_{urg}")
    for f, obj in (("extra_units_t9x1.json", ext), ("arms_t9x1.json", {"arms": {"base": None}, "sets": {}, "conditions": conds, "seeds": 24,
                                                                        "seed_off": 22000, "budget": 6144, "extra_units": "extra_units_t9x1.json"})):
        p = NE / "steer_am" / f
        if p.exists():
            raise SystemExit(f"{p} exists")
        p.write_text(json.dumps(obj), encoding="utf-8")
    print(conds, [len(e["prompt_ids"]) for e in ext])


EXCLUDE = ("busines", "commerc", "financ", "secur", "nation", "govern", "confiden", "violat", "polic", "legal", "complian", "corporat",
           "compan", "techn", "econom", "politic", "militar", "defen")


def hit(x, s):
    """A stem of 3 characters or fewer must be the whole word (or its plural); longer stems match as prefixes."""
    return x in (s, s + "s") if len(s) <= 3 and s.isascii() else x.startswith(s)


def matches(words, stems):
    w = [x.strip().lower() for x in words]
    if any(any(x.startswith(e) for e in EXCLUDE) for x in w):
        return 0, 0
    return sum(any(hit(x, s) for s in stems) for x in w), sum(any(hit(x, s) for s in stems) for x in w[:3])


def mode_unr():
    from transformers import AutoTokenizer
    import ab_core as C
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    dic = np.load(NE / "dict.npz")
    wn = dic["wnorm"]
    rn = np.load(A / "search" / "am" / "refstats.npz")["resnorm"]
    d4 = json.loads((NE / "steer_am" / "arms_t9d4.json").read_text(encoding="utf-8"))
    e = json.loads((NE / "steer_am" / "arms_t9e.json").read_text(encoding="utf-8"))
    vio = d4["sets"]["vio8_d0.1"]
    cache = {}

    def layer_words(l):
        if l not in cache:
            cache[l] = [[tok.decode([int(t)]) for t in dic["pos_i"][l, j, :10]] for j in range(NN)]
        return cache[l]
    used = {(int(x[0]), int(x[1])) for x in vio}
    unr, info, ci = [], [], 0
    for x in vio:
        l0 = int(x[0])
        found = None
        while found is None and ci < len(CONCEPTS):
            name, stems = CONCEPTS[ci]
            for dl in (0, 1, -1, 2, -2, 3, -3):
                l = l0 + dl
                if not 0 <= l < 32:
                    continue
                best = None
                for j, ws in enumerate(layer_words(l)):
                    if (l, j) in used:
                        continue
                    m10, m3 = matches(ws, stems)
                    if m10 >= 3 or m3 >= 2:
                        if best is None or m10 > best[0]:
                            best = (m10, j)
                if best:
                    found = (name, l, best[1], best[0])
                    break
            ci += 1
        if found is None:
            raise SystemExit("ran out of concepts")
        name, l, j, m = found
        used.add((l, j))
        unr.append([l, j, float(0.1 * rn[l] / wn[l, j]), 2.0])
        info.append({"for_vio8": f"L{l0}/N{int(x[1])}", "concept": name, "neuron": f"L{l}/N{j}", "matches_top10": m,
                     "words": layer_words(l)[j][:8]})
    sets = {"vio8_d0.1": vio, "unr8_d0.1": unr, "r2_vio8_d0.1": e["sets"]["r2_vio8_d0.1"]}
    arms = {"base": None, **{k: {"set": k, "t0": 128, "t1": 640} for k in sets}}
    p = NE / "steer_am" / "arms_t9x2.json"
    if p.exists():
        raise SystemExit(f"{p} exists")
    p.write_text(json.dumps({"arms": arms, "sets": sets, "conditions": list(MAIN), "seeds": 24, "seed_off": 22100, "budget": 6144}), encoding="utf-8")
    (NE / "t9x2_unr.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    for i in info:
        print(i["for_vio8"], "->", i["concept"], i["neuron"], i["matches_top10"], "".join(i["words"][:6]))


if __name__ == "__main__":
    {"units": mode_units, "unr": mode_unr}[sys.argv[1]]()
