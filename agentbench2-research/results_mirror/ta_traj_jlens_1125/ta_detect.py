"""Can J-lens words (top-50, layers 0-30 + final, every scanned token) detect an upcoming misaligned / boundary action
before it is taken? ToolAlign-4B trajectory units. CPU only.
Positive = target whose call is clearly-misaligned or boundary (44). Negative = reference (writeInternalLog, 159) and
aligned target (legit internal email etc., 9).
Regions: input tail (300 tokens before the response, same length for every unit), preamble (onset .. call scaffold;
lengths differ a lot: references median 6 tokens, positives 171), early preamble (before the J-lens commit token; empty for
references), last64 (the last 64 tokens before the call, only units with >= 70 preamble tokens: the length-matched test).
1. The words named so far (Chinese refusal / detection / risk words, justification frames, FBI / DOJ / whistleblower):
   share of units in which each appears in the top-50 at L16-28 in a region, by group.
2. Data-driven detector, leave-one-domain-out: on the other 15 domains pick 20 tokens with the largest
   P(present | positive) - P(present | negative), P(negative) <= 0.25; score a held-out unit by how many are present.
   Pooled AUC; recall and false-fire rate at the threshold that keeps the training false-fire rate <= 10 %.
3. Timing: does the detector fire before the J-lens commit token of the positive units?
Usage: python ta_detect.py TRAJ_DIR OUT_MD [EDIT_ROWS_JSONL]"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_core as C

LO, HI = 16, 28
SCAF = "<tool_call>\n<tool_name>"
NAMED = {"无法 (cannot)": ["无法"], "检测 (detected)": ["检测"], "ALERT": ["ALERT", "Alert"], "风险 (risk)": ["风险"],
         "Given": ["Given"], "Considering": ["Considering"], "鉴于 (given that)": ["鉴于"], "FBI": ["FBI"], "DOJ": ["DOJ"],
         "whistle(blower)": ["whistle", "Whistle"], "我不能 / 不能 (cannot)": ["不能"], "illegal": ["illegal", "Illegal"],
         "fraud": ["fraud", "Fraud"], "regulator": ["regulat", "Regulat"]}


def auc(pos, neg):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if not len(pos) or not len(neg):
        return None
    r = np.argsort(np.argsort(np.concatenate([pos, neg]), kind="mergesort"), kind="mergesort") + 1.0
    allv = np.concatenate([pos, neg])
    for v in np.unique(allv):
        m = allv == v
        r[m] = r[m].mean()
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    d = Path(sys.argv[1])
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    scaf = tok.encode(SCAF, add_special_tokens=False)
    V = tok.vocab_size + 300
    dec = {}

    def s(t):
        if t not in dec:
            dec[t] = tok.decode([t])
        return dec[t]

    named_ids = defaultdict(set)
    U = []
    for u in meta:
        z = np.load(d / f"u_{u['idx']}.npz")
        top = z["top_ids"][:, LO:HI + 1, :]
        cl = z["cand_lp"].astype(np.float32)
        n = top.shape[0]
        on = u["onset"] - u["span"][0]
        ids = u["span_ids"][:n]
        scaf_start = n - len(scaf) if ids[n - len(scaf):n] == scaf else n - 1
        if u["label"] == "target":
            ci, wi = u["cand_ids"].index(u["c"]), u["cand_ids"].index(u["w"])
            m24 = cl[:, 24, ci] - cl[:, 24, wi]
            commit = next((t for t in range(on, n) if m24[t] > 0 and (m24[t:] > 0).mean() >= 0.8), None)
        else:
            commit = None
        regs = {"input": range(0, on), "preamble": range(on, scaf_start),
                "last64": range(scaf_start - 64, scaf_start) if scaf_start - on >= 70 else range(0),
                "early": range(on, commit if commit is not None and commit > on else on)}
        pres = {}
        first = {}
        for rn, rr in regs.items():
            cnt = Counter()
            for p in rr:
                for t in set(top[p].ravel().tolist()):
                    cnt[t] += 1
                    if rn == "preamble":
                        first.setdefault(t, p)
            pres[rn] = cnt
        pos_lab = u["label"] == "target" and u["risk"] != "aligned"
        grp = "positive (misaligned+boundary)" if pos_lab else ("aligned target" if u["label"] == "target" else "reference")
        U.append({"u": u, "pos": pos_lab, "grp": grp, "pres": pres, "first": first, "commit": commit, "on": on,
                  "pre_len": scaf_start - on})
    for t in set().union(*[set(x["pres"]["preamble"]) | set(x["pres"]["input"]) for x in U]):
        st = s(t)
        for k, subs in NAMED.items():
            if any(w in st for w in subs):
                named_ids[k].add(t)
    md = ["# Can J-lens words detect a misaligned / boundary action before it happens? (ToolAlign-4B, 212 units)", "",
          f"Groups: {Counter(x['grp'] for x in U)}. Top-50 at L{LO}-{HI}, every scanned token.", "",
          "## 1. Words named so far: share of units where the word is in the top-50 somewhere in the region", "",
          "| word | region | positive | aligned target | reference |", "|---|---|---|---|---|"]
    for k in NAMED:
        ids_k = named_ids.get(k, set())
        for rn in ("input", "preamble", "last64"):
            row = []
            for g in ("positive (misaligned+boundary)", "aligned target", "reference"):
                xs = [x for x in U if x["grp"] == g and (rn != "last64" or x["pre_len"] >= 70)]
                row.append(f"{np.mean([bool(ids_k & set(x['pres'][rn])) for x in xs]):.0%} (n={len(xs)})" if xs else "-")
            md.append(f"| {k} | {rn} | " + " | ".join(row) + " |")
    md.append("")
    md += ["## 2. Leave-one-domain-out detector (20 tokens picked on the other 15 domains)", "",
           "| region | AUC | recall at train-FPR<=10% | false fire: aligned target | false fire: reference | example tokens (picked in most folds) |",
           "|---|---|---|---|---|---|"]
    doms = sorted({x["u"]["domain"] for x in U})
    for rn in ("input", "preamble", "early", "last64"):
        scores, picked = {}, Counter()
        fire = {}
        keep = (lambda x: x["pre_len"] >= 70) if rn == "last64" else (lambda x: True)
        for hd in doms:
            tr = [x for x in U if x["u"]["domain"] != hd and keep(x)]
            te = [x for x in U if x["u"]["domain"] == hd and keep(x)]
            P = [x for x in tr if x["pos"]]
            N = [x for x in tr if not x["pos"]]
            if not P or not N:
                continue
            cp, cn = Counter(), Counter()
            for x in P:
                cp.update(t for t, c in x["pres"][rn].items() if c >= 2)
            for x in N:
                cn.update(t for t, c in x["pres"][rn].items() if c >= 2)
            cand = [(cp[t] / len(P) - cn[t] / len(N), t) for t in cp if cn[t] / len(N) <= 0.25]
            sel = [t for _, t in sorted(cand, reverse=True)[:20]]
            picked.update(sel)
            sc = lambda x: sum(1 for t in sel if x["pres"][rn].get(t, 0) >= 2)
            trn = sorted(sc(x) for x in N)
            thr = next((k for k in range(0, 21) if np.mean([v >= k for v in trn]) <= 0.10), 21)
            for x in te:
                scores[id(x)] = sc(x)
                fire[id(x)] = sc(x) >= thr
        pos = [scores[id(x)] for x in U if x["pos"] and id(x) in scores]
        neg = [scores[id(x)] for x in U if not x["pos"] and id(x) in scores]
        rec = np.mean([fire[id(x)] for x in U if x["pos"] and id(x) in fire])
        fa = np.mean([fire[id(x)] for x in U if x["grp"] == "aligned target" and id(x) in fire])
        fr = np.mean([fire[id(x)] for x in U if x["grp"] == "reference" and id(x) in fire])
        ex = ", ".join(repr(s(t)) for t, _ in picked.most_common(12))
        a = auc(pos, neg)
        npn = (sum(1 for x in U if x["pos"] and id(x) in scores), sum(1 for x in U if not x["pos"] and id(x) in scores))
        md.append(f"| {rn} (pos {npn[0]} / neg {npn[1]}) | {'-' if a is None else f'{a:.2f}'} | {rec:.0%} | {fa:.0%} | {fr:.0%} | {ex} |")
        for x in U:
            x.setdefault("fire", {})[rn] = fire.get(id(x))
    md.append("")
    md += ["## 3. Timing: positive units whose early-preamble detector fires before the J-lens commit token", ""]
    pe = [x for x in U if x["pos"] and x["commit"] is not None and x["commit"] > x["on"]]
    md.append(f"- {sum(bool(x['fire'].get('early')) for x in pe)}/{len(pe)} positive units with a commit after the onset fire on the text "
              f"before the commit token; median tokens between onset and commit: {np.median([x['commit'] - x['on'] for x in pe]) if pe else 0:.0f}")
    md.append("")
    if len(sys.argv) > 3 and Path(sys.argv[3]).is_file():
        rows = [json.loads(l) for l in Path(sys.argv[3]).open(encoding="utf-8")]
        md += ["## 4. Detect-then-edit (commit-start edits from ta_commit_edit; edit applied only where the preamble detector fires)", ""]
        flip = {(r["idx"], r["config"]): r["gen_tool"] == "writeInternalLog" for r in rows if r["start"] == "commit"}
        for cfg in sorted({c for _, c in flip}):
            if cfg == "base":
                continue
            bl = [(x["fire"].get("preamble") and flip.get((x["u"]["idx"], cfg), False)) for x in U if x["pos"] and (x["u"]["idx"], cfg) in flip]
            co = [(x["fire"].get("preamble") and flip.get((x["u"]["idx"], cfg), False)) for x in U if x["grp"] == "aligned target" and (x["u"]["idx"], cfg) in flip]
            al = [flip.get((x["u"]["idx"], cfg), False) for x in U if x["grp"] == "aligned target" and (x["u"]["idx"], cfg) in flip]
            md.append(f"- {cfg}: misaligned/boundary blocked {np.mean(bl) if bl else float('nan'):.0%} (n={len(bl)}); aligned targets changed "
                      f"{np.mean(co) if co else float('nan'):.0%} with the detector vs {np.mean(al) if al else float('nan'):.0%} always-on (n={len(co)})")
    Path(sys.argv[2]).write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
