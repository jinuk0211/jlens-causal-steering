import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE.parent
TRAIN = {"0", "1", "3", "4", "5", "7", "9", "10", "11", "12", "14", "15", "17", "20", "21", "23", "27", "28", "36", "38", "39", "40",
         "41", "42"}
SELECTED = ["f_caa_s0.5", "f_austeer_s10", "f_sadi_s10", "f_iti_s15", "f_cast_s0.25", "f_j5"]
ALWAYS_ON = ["f_caa_s0.5", "f_austeer_s10", "f_sadi_s10", "f_iti_s15", "f_cast_s0.25"]
VERIFY = re.compile(r"before i make any change|let me (first )?check (this|the) (request|policy)|confirm the details|let me verify|"
                    r"could you (please )?confirm|can you confirm", re.I)
AIRLINE_WORDS = re.compile(r"\b(flight|flights|reservation|airline|baggage|cabin|passenger|boarding|layover)\b", re.I)


def mcnemar(a, b):
    n = a + b
    if n == 0:
        return 1.0
    k = min(a, b)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def main():
    eps = json.loads((HERE / "episodes.json").read_text(encoding="utf-8"))
    fit = json.loads((HERE / "fit.json").read_text(encoding="utf-8"))
    nl = json.loads((RES / "nl_judge/nl_verdicts.json").read_text(encoding="utf-8"))["records"]
    E = defaultdict(dict)
    for e in eps:
        key = f"{e['cond']}|{e['domain']}|{e['task']}|{e['sim']}"
        r = float(e["reward"] or 0)
        if e["domain"] == "retail" and key in nl:
            r = float(nl[key]["corrected_reward"])
        e["ok"] = int(r >= 1)
        e["split"] = "train" if (e["domain"] == "airline" and e["task"] in TRAIN) else ("airline_ho" if e["domain"] == "airline" else "retail")
        caps = sum(1 for t in e["turns"] if t["gen_tokens"] and t["max_new"] and t["gen_tokens"] >= t["max_new"])
        e["caps"] = caps
        e["degenerate"] = int(caps >= 2 or e["term"] == "max_steps")
        E[e["cond"]][(e["domain"], e["task"])] = e
    base = E["f_detect"]
    md = ["# Why the F-run steering baselines did not help (all F-run results, CPU re-analysis)", "",
          "Source: server probe/baseline_why/episodes.json (bw_extract.py), artifacts/fit_examples.json; retail success = stored reward x NL verdict.", ""]

    # A. outcomes
    md += ["## A. Outcomes per condition (success count; paired vs f_detect on the same tasks)", "",
           "| condition | split | n | success | f_detect on same | fixed | broken | net | McNemar p | degenerate eps |", "|---|---|---|---|---|---|---|---|---|---|"]
    per_task = defaultdict(dict)
    for cond in sorted(E):
        for split in ("train", "airline_ho", "retail"):
            ks = [k for k, e in E[cond].items() if e["split"] == split and k in base]
            if not ks:
                continue
            s = sum(E[cond][k]["ok"] for k in ks)
            b = sum(base[k]["ok"] for k in ks)
            fx = [k for k in ks if E[cond][k]["ok"] and not base[k]["ok"]]
            br = [k for k in ks if base[k]["ok"] and not E[cond][k]["ok"]]
            dg = sum(E[cond][k]["degenerate"] for k in ks)
            for k in ks:
                per_task[cond][k] = E[cond][k]["ok"]
            md.append(f"| {cond} | {split} | {len(ks)} | {s} | {b} | {len(fx)} | {len(br)} | {len(fx) - len(br):+d} | {mcnemar(len(fx), len(br)):.2f} | {dg} |")
    # B. overlap of broken / fixed tasks across the always-on methods (eval set)
    evalk = [k for k, e in base.items() if e["split"] != "train"]
    md += ["", "## B. Are the same tasks broken by every method? (eval set, 5 always-on baselines at their selected strengths)", ""]
    brk = Counter()
    fxc = Counter()
    for cond in ALWAYS_ON:
        for k in evalk:
            if k in E[cond]:
                if base[k]["ok"] and not E[cond][k]["ok"]:
                    brk[k] += 1
                if not base[k]["ok"] and E[cond][k]["ok"]:
                    fxc[k] += 1
    npass = sum(base[k]["ok"] for k in evalk)
    nfail = len(evalk) - npass
    md.append(f"- base-pass tasks {npass}: broken by how many of the 5 methods → {dict(sorted(Counter(brk[k] for k in evalk if base[k]['ok']).items()))}")
    md.append(f"- base-fail tasks {nfail}: fixed by how many of the 5 methods → {dict(sorted(Counter(fxc[k] for k in evalk if not base[k]['ok']).items()))}")
    rates = [sum(1 for k in evalk if base[k]["ok"] and k in E[c] and not E[c][k]["ok"]) / max(npass, 1) for c in ALWAYS_ON]
    rng = np.random.default_rng(0)
    sim_counts = []
    for _ in range(20000):
        m = np.stack([rng.random(npass) < p for p in rates]).sum(0)
        sim_counts.append((m >= 3).sum())
    obs3 = sum(1 for k in evalk if base[k]["ok"] and brk[k] >= 3)
    md.append(f"- tasks broken by ≥ 3 of 5 methods: observed {obs3}; if each method broke tasks independently at its own rate: "
              f"mean {np.mean(sim_counts):.2f}, P(≥ observed) = {np.mean(np.array(sim_counts) >= obs3):.4f}")
    frag = sorted([k for k in evalk if base[k]["ok"] and brk[k] >= 3], key=lambda k: -brk[k])
    md.append(f"- the fragile tasks (broken by ≥ 3): {[f'{d}:{t}({brk[(d, t)]})' for d, t in frag]}")
    fixed_multi = sorted([k for k in evalk if not base[k]["ok"] and fxc[k] >= 2], key=lambda k: -fxc[k])
    md.append(f"- tasks fixed by ≥ 2 methods: {[f'{d}:{t}({fxc[(d, t)]})' for d, t in fixed_multi]}")
    # C. divergence from the reference trajectory
    md += ["", "## C. Where does the steered trajectory leave the reference? (eval set, paired by task)", "",
           "| condition | identical episodes | first differing agent turn: 0 / 1 / 2 / 3+ | outcome changed when identical | when diverged |",
           "|---|---|---|---|---|"]
    for cond in SELECTED + ["f_mera_s0.001"]:
        if cond not in E:
            continue
        ident = 0
        first = Counter()
        chg_id = chg_dv = n_dv = 0
        for k in evalk:
            if k not in E[cond]:
                continue
            a, b = base[k]["turns"], E[cond][k]["turns"]
            d = next((i for i in range(min(len(a), len(b))) if a[i]["sha"] != b[i]["sha"]), None)
            if d is None and len(a) == len(b):
                ident += 1
                chg_id += base[k]["ok"] != E[cond][k]["ok"]
            else:
                d = d if d is not None else min(len(a), len(b))
                first[min(d, 3)] += 1
                n_dv += 1
                chg_dv += base[k]["ok"] != E[cond][k]["ok"]
        md.append(f"| {cond} | {ident} | {first[0]} / {first[1]} / {first[2]} / {first[3]} | {chg_id} | {chg_dv}/{n_dv} |")
    # D. behaviour deltas
    md += ["", "## D. What changed in behaviour? (eval set, per-episode means, steered minus reference on the same tasks)", "",
           "| condition | agent turns | tool calls | writes | bad writes | bad-write share of writes (cond / ref) | transfers | verify-first replies | "
           "mean text chars | capped turns |", "|---|---|---|---|---|---|---|---|---|---|"]

    def stats(e):
        t = e["turns"]
        writes = sum(1 for x in t for c in x["calls"] if not c[0].startswith(("get_", "search_", "list_", "calculate", "think", "find_")))
        badw = sum(len(x["bad"]) for x in t)
        return {"turns": len(t), "calls": sum(len(x["calls"]) for x in t), "writes": writes, "bad": badw,
                "transfer": sum(1 for x in t for c in x["calls"] if c[0] == "transfer_to_human_agents"),
                "verify": sum(1 for x in t if not x["calls"] and VERIFY.search(x["text"] or "")),
                "chars": np.mean([x["tlen"] for x in t]) if t else 0, "caps": e["caps"]}

    for cond in SELECTED:
        ks = [k for k in evalk if k in E[cond]]
        S = [stats(E[cond][k]) for k in ks]
        B = [stats(base[k]) for k in ks]
        def dm(f):
            return np.mean([s[f] - b[f] for s, b in zip(S, B)])
        share_c = sum(s["bad"] for s in S) / max(sum(s["writes"] for s in S), 1)
        share_b = sum(b["bad"] for b in B) / max(sum(b["writes"] for b in B), 1)
        md.append(f"| {cond} | {dm('turns'):+.2f} | {dm('calls'):+.2f} | {dm('writes'):+.2f} | {dm('bad'):+.2f} | {share_c:.2f} / {share_b:.2f} | "
                  f"{dm('transfer'):+.2f} | {dm('verify'):+.2f} | {dm('chars'):+.0f} | {dm('caps'):+.2f} |")
    # E. failure types in broken / fixed episodes
    md += ["", "## E. Failure types: what appears in broken episodes, what disappears in fixed ones (eval set, 5 always-on baselines pooled)", ""]
    new_ft, gone_ft = Counter(), Counter()
    for cond in ALWAYS_ON:
        for k in evalk:
            if k not in E[cond]:
                continue
            s, b = E[cond][k], base[k]
            if b["ok"] and not s["ok"]:
                for f in s["failure_types"] or ["(no write-level failure: communicate/NL or user)"]:
                    new_ft[f] += 1
            if s["ok"] and not b["ok"]:
                for f in b["failure_types"] or ["(no write-level failure)"]:
                    gone_ft[f] += 1
    md.append(f"- failure types in BROKEN episodes (reference passed): {dict(new_ft.most_common())}")
    md.append(f"- failure types that the reference had in FIXED episodes: {dict(gone_ft.most_common())}")
    # by domain breakdown of broken/fixed
    md.append("- broken / fixed by domain: " + ", ".join(
        f"{c}: airline {sum(1 for k in evalk if k[0] == 'airline' and k in E[c] and base[k]['ok'] and not E[c][k]['ok'])}/"
        f"{sum(1 for k in evalk if k[0] == 'airline' and k in E[c] and not base[k]['ok'] and E[c][k]['ok'])}, retail "
        f"{sum(1 for k in evalk if k[0] == 'retail' and k in E[c] and base[k]['ok'] and not E[c][k]['ok'])}/"
        f"{sum(1 for k in evalk if k[0] == 'retail' and k in E[c] and not base[k]['ok'] and E[c][k]['ok'])}" for c in ALWAYS_ON))
    # F. airline vocabulary leaking into retail
    md += ["", "## F. Does airline-fitted steering leak airline language into retail? (airline words per retail episode)", ""]
    rk = [k for k in evalk if k[0] == "retail"]
    for cond in ["f_detect"] + ALWAYS_ON:
        vals = [sum(len(AIRLINE_WORDS.findall(t["text"] or "")) for t in E[cond][k]["turns"]) for k in rk if k in E[cond]]
        md.append(f"- {cond}: mean {np.mean(vals):.2f}, episodes with any {sum(v > 0 for v in vals)}/{len(vals)}")
    # G. interventions actually applied
    md += ["", "## G. How much was actually edited? (eval set)", ""]
    for cond in SELECTED + ["f_mera_s0.001"]:
        if cond not in E:
            continue
        act = tot = 0
        edits = []
        trig = 0
        for k in evalk:
            if k not in E[cond]:
                continue
            for t in E[cond][k]["turns"]:
                iv = t["interv"] or {}
                tot += 1
                pos = (iv.get("applied_prefill_positions") or 0) + (iv.get("applied_decode_positions") or 0)
                ed = iv.get("off_applied_edits")
                if (ed or pos) and iv.get("active"):
                    act += 1
                if ed is not None:
                    edits.append(ed)
                trig += bool(iv.get("triggered"))
        md.append(f"- {cond}: turns with an applied edit {act}/{tot}; median official applied_edits per turn "
                  f"{np.median(edits) if edits else 'n/a'}; turns with the J-lens trigger on {trig}")
    # H. fit data
    md += ["", "## H. What were the baselines fitted on? (artifacts/fit_examples.json)", "",
           f"- examples {fit.get('n_examples')}; positive side: {fit.get('positive_source')}; sources: {fit.get('source')}",
           f"- by TRAIN task: {fit.get('by_task')}",
           f"- negative (failed) action: {fit.get('negative_calls')}",
           f"- most common positive texts: {fit.get('positive_texts')}"]
    # I. dose curves on TRAIN
    md += ["", "## I. Dose curves on airline TRAIN (24 tasks; reference f_detect)", ""]
    tk = [k for k, e in base.items() if e["split"] == "train"]
    md.append(f"- f_detect: success {sum(base[k]['ok'] for k in tk)}/{len(tk)}, degenerate {sum(base[k]['degenerate'] for k in tk)}")
    for meth in ("caa", "austeer", "sadi", "iti", "cast", "mera", "j5", "jlens"):
        cs = sorted([c for c in E if c.startswith(f"f_{meth}")], key=lambda c: float(re.findall(r"[\d.]+$", c)[0]) if re.findall(r"[\d.]+$", c) else 0)
        row = []
        for c in cs:
            ks = [k for k in tk if k in E[c]]
            if ks:
                row.append(f"{c.split('_', 2)[-1]}: {sum(E[c][k]['ok'] for k in ks)}/{len(ks)} (degen {sum(E[c][k]['degenerate'] for k in ks)})")
        if row:
            md.append(f"- {meth}: " + "; ".join(row))
    (HERE / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (HERE / "per_task.json").write_text(json.dumps({c: {f"{d}|{t}": v for (d, t), v in m.items()} for c, m in per_task.items()}, indent=0), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
