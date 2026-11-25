import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE.parent
TRAIN = {"0", "1", "3", "4", "5", "7", "9", "10", "11", "12", "14", "15", "17", "20", "21", "23", "27", "28", "36", "38", "39", "40",
         "41", "42"}
ALWAYS_ON = ["f_caa_s0.5", "f_austeer_s10", "f_sadi_s10", "f_iti_s15", "f_cast_s0.25"]


def main():
    eps = json.loads((HERE / "episodes.json").read_text(encoding="utf-8"))
    nl = json.loads((RES / "nl_judge/nl_verdicts.json").read_text(encoding="utf-8"))["records"]
    hd = json.loads((HERE / "hdetect_rewards.json").read_text(encoding="utf-8"))
    E = defaultdict(dict)
    for e in eps:
        key = f"{e['cond']}|{e['domain']}|{e['task']}|{e['sim']}"
        r = float(e["reward"] or 0)
        if e["domain"] == "retail" and key in nl:
            r = float(nl[key]["corrected_reward"])
        e["ok"] = int(r >= 1)
        E[e["cond"]][(e["domain"], e["task"])] = e
    H = {}
    for key, r in hd.items():
        cond, dom, task, sim = key.split("|")
        rr = float(r or 0)
        if dom == "retail" and key in nl:
            rr = float(nl[key]["corrected_reward"])
        H[(dom, task)] = int(rr >= 1)
    base = E["f_detect"]
    evalk = [k for k in base if not (k[0] == "airline" and k[1] in TRAIN) and (k[0] == "airline" or k in E["f_caa_s0.5"])]
    md = ["# Supplement: noise floor, transfers, examples", ""]
    # 1. unsteered rerun (hdetect, Haiku user, earlier proxy version) vs f_detect
    both = [k for k in evalk if k in H]
    diff = [k for k in both if H[k] != base[k]["ok"]]
    md += ["## 1. Unsteered rerun noise: hdetect (Haiku user, earlier run) vs f_detect on the same eval tasks", "",
           f"- tasks in both: {len(both)}; outcome differs on {len(diff)} ({len(diff) / max(len(both), 1):.0%}); "
           f"hdetect success {sum(H[k] for k in both)}, f_detect {sum(base[k]['ok'] for k in both)}",
           f"- differing tasks: {sorted(f'{d}:{t}' for d, t in diff)}"]
    brk = Counter()
    fxc = Counter()
    for c in ALWAYS_ON:
        for k in evalk:
            if k in E[c]:
                if base[k]["ok"] and not E[c][k]["ok"]:
                    brk[k] += 1
                if not base[k]["ok"] and E[c][k]["ok"]:
                    fxc[k] += 1
    flippy = {k for k in evalk if brk[k] + fxc[k] >= 3}
    stable = {k for k in evalk if brk[k] + fxc[k] == 0}
    fd = [k for k in flippy if k in H]
    sd = [k for k in stable if k in H]
    md.append(f"- tasks flipped by ≥ 3 of the 5 baselines: {len(flippy)}; of those with an hdetect run, the unsteered rerun also differs on "
              f"{sum(H[k] != base[k]['ok'] for k in fd)}/{len(fd)}")
    md.append(f"- tasks flipped by none of the 5: {len(stable)}; unsteered rerun differs on {sum(H[k] != base[k]['ok'] for k in sd)}/{len(sd)}")
    # 2. unexpected transfers
    md += ["", "## 2. Unneeded transfers (unexpected_transfer writes) per condition, eval set", ""]
    for c in ["f_detect"] + ALWAYS_ON + ["f_j5"]:
        ks = [k for k in evalk if k in E[c]]
        n_ut = sum(sum(1 for t in E[c][k]["turns"] for b in t["bad"] if b.startswith("unexpected_transfer")) for k in ks)
        n_ep = sum(any(b.startswith("unexpected_transfer") for t in E[c][k]["turns"] for b in t["bad"]) for k in ks)
        md.append(f"- {c}: unneeded transfer calls {n_ut}, episodes with one {n_ep}/{len(ks)}")
    fixed_tr = Counter()
    for c in ALWAYS_ON:
        for k in evalk:
            if k in E[c] and not base[k]["ok"] and E[c][k]["ok"]:
                had = any(b.startswith("unexpected_transfer") for t in base[k]["turns"] for b in t["bad"])
                fixed_tr["reference had an unneeded transfer" if had else "other reference failure"] += 1
    md.append(f"- fixed episodes (pooled over the 5 baselines): {dict(fixed_tr)}")
    # 3. per-task examples of fragile tasks: first divergence and outcome
    md += ["", "## 3. Fragile tasks (broken by ≥ 3 baselines): what the reference did vs a steered run", ""]
    frag = sorted([k for k in evalk if base[k]["ok"] and brk[k] >= 3], key=lambda k: -brk[k])
    for k in frag[:6]:
        b = base[k]
        md.append(f"### {k[0]} task {k[1]} (broken by {brk[k]}/5; reference turns {len(b['turns'])})")
        for c in ALWAYS_ON:
            if k not in E[c]:
                continue
            s = E[c][k]
            d = next((i for i in range(min(len(b["turns"]), len(s["turns"]))) if b["turns"][i]["sha"] != s["turns"][i]["sha"]), None)
            status = "PASS" if s["ok"] else f"FAIL {s['failure_types']}"
            md.append(f"- {c}: {status}; diverges at turn {d}; turns {len(s['turns'])}")
        c = next(c for c in ALWAYS_ON if k in E[c] and not E[c][k]["ok"])
        s = E[c][k]
        d = next((i for i in range(min(len(b["turns"]), len(s["turns"]))) if b["turns"][i]["sha"] != s["turns"][i]["sha"]), 0)
        md.append(f"  - at the first differing turn {d}: reference calls {[x[0] for x in b['turns'][d]['calls']]}, {c} calls "
                  f"{[x[0] for x in s['turns'][d]['calls']]}")
        md.append(f"  - reference text: {re.sub(r'\s+', ' ', b['turns'][d]['text'])[:220]!r}")
        md.append(f"  - {c} text: {re.sub(r'\s+', ' ', s['turns'][d]['text'])[:220]!r}")
        md.append(f"  - reference writes: {[x[0] for t in b['turns'] for x in t['calls'] if not x[0].startswith(('get_', 'find_', 'list_', 'search_', 'calculate', 'think'))]}")
        md.append(f"  - {c} writes: {[x[0] for t in s['turns'] for x in t['calls'] if not x[0].startswith(('get_', 'find_', 'list_', 'search_', 'calculate', 'think'))]}")
    # 4. per-opportunity rates
    md += ["", "## 4. Fix and break rates per opportunity (eval set)", ""]
    for c in ALWAYS_ON:
        for dom in ("airline", "retail"):
            ks = [k for k in evalk if k[0] == dom and k in E[c]]
            npass = sum(base[k]["ok"] for k in ks)
            nfail = len(ks) - npass
            br = sum(1 for k in ks if base[k]["ok"] and not E[c][k]["ok"])
            fx = sum(1 for k in ks if not base[k]["ok"] and E[c][k]["ok"])
            md.append(f"- {c} {dom}: broken {br}/{npass} = {br / max(npass, 1):.0%} of passing tasks; fixed {fx}/{nfail} = {fx / max(nfail, 1):.0%} of failing tasks")
    (HERE / "report_extra.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
