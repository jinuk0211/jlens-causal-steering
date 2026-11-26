"""Harmful vs harmless stored responses: natural activation of each steering-set neuron (pole-aligned act_scale score).
Groups: harmful = repo classifier True; harmless = False (unlabeled skipped). Reported per window (pre_tool = the reply before
its first tool use, resp = whole reply): per set, mean over its 12 neurons of the per-response mean score, by group, and the
AUC harmless > harmful of that set score (AUC > 0.5 = more active when the model did NOT do the harmful act); per neuron the
same AUC. Within-condition view: only conditions with >= 3 harmful. Descriptive.
Usage: python3 ntrace_cmp.py NTRACE_JSONL OUT_MD"""
import json
import sys
from collections import defaultdict


def auc(pos, neg):
    if not pos or not neg:
        return None
    s = 0.0
    for p in pos:
        for q in neg:
            s += 1.0 if p > q else 0.5 if p == q else 0.0
    return s / (len(pos) * len(neg))


def main():
    R = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
    R = [r for r in R if r["harmful"] is not None]
    names = R[0]["names"]
    sets = defaultdict(list)
    for j, nm in enumerate(names):
        sets[nm.split(":")[0]].append(j)
    cnt = defaultdict(lambda: [0, 0])
    for r in R:
        cnt[r["condition"]][int(bool(r["harmful"]))] += 1
    md = ["# Steering-set neurons: natural activation in harmful vs harmless stored responses", "",
          f"{len(R)} labeled responses. Per condition (harmless/harmful): " + ", ".join(f"{c} {v[0]}/{v[1]}" for c, v in sorted(cnt.items())), "",
          "Score = pole-aligned act_scale units (the side each neuron fires on for its prompt type). AUC = P(harmless response "
          "scores higher than harmful); > 0.5 means the set is more active when the model did not do the harmful act.", ""]
    views = [("all labeled", lambda r: True), ("conditions with >= 3 harmful", lambda r: cnt[r["condition"]][1] >= 3)]
    for w in ("pre_tool", "resp"):
        for vname, sel in views:
            rs = [r for r in R if sel(r) and r["w"].get(w)]
            H = [r for r in rs if r["harmful"]]
            S = [r for r in rs if not r["harmful"]]
            md += [f"## window {w}, {vname}: {len(S)} harmless / {len(H)} harmful", "",
                   "| set | mean score harmless | mean score harmful | AUC (harmless > harmful) | fire share harmless | fire share harmful |",
                   "|---|---|---|---|---|---|"]
            for s, js in sets.items():
                f = lambda r, key: sum(r["w"][w][key][j] for j in js) / len(js)
                sh, sm = [f(r, "mean") for r in S], [f(r, "mean") for r in H]
                fh, fm = [f(r, "fire") for r in S], [f(r, "fire") for r in H]
                a = auc(sh, sm)
                md.append(f"| {s} | {sum(sh) / max(1, len(sh)):.3f} | {sum(sm) / max(1, len(sm)):.3f} | {'-' if a is None else f'{a:.2f}'} | "
                          f"{sum(fh) / max(1, len(fh)):.3f} | {sum(fm) / max(1, len(fm)):.3f} |")
            md.append("")
            if vname.startswith("conditions"):
                md += ["Per neuron (AUC harmless > harmful, window " + w + "): " + "; ".join(
                    f"{names[j]} {auc([r['w'][w]['mean'][j] for r in S], [r['w'][w]['mean'][j] for r in H]):.2f}"
                    for s in ("RES", "REP", "RAND") for j in sets[s]), ""]
    open(sys.argv[2], "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
