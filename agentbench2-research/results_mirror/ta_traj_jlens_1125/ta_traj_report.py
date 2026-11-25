"""Sentence-level report on the trajectory J-lens scan (ta_traj_jlens.py output). CPU only.
Regions per unit: input tail (300 tokens before the response), response sentences before the call (k = 1 is the sentence
right before the call, k = 2 the one before it, ...), and the call scaffold up to the tool-name position (k = 0).
Margin at a position = lens lp(chosen tool's first token) - lp(writeInternalLog's first token), same tool tokens for every
unit of a domain; for references (chosen = writeInternalLog) the margin is max over the other tools - writeInternalLog.
J-lens commit token (targets): the first response position from which the L24 margin is > 0 at >= 80 % of the remaining
positions up to the name (sustained).
Usage: python ta_traj_report.py TRAJ_DIR OUT_MD"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_core as C

LAYS = [12, 16, 20, 24, 28, 31]
KEY = 24
SCAF = "<tool_call>\n<tool_name>"


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    d = Path(sys.argv[1])
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    scaf = tok.encode(SCAF, add_special_tokens=False)
    U = []
    for u in meta:
        f = d / f"u_{u['idx']}.npz"
        if not f.is_file():
            continue
        z = np.load(f)
        cl = z["cand_lp"].astype(np.float32)
        ids = u["span_ids"]
        s0 = u["span"][0]
        n = cl.shape[0]
        ci = u["cand_ids"].index(u["c"]) if u["c"] in u["cand_ids"] else None
        wi = u["cand_ids"].index(u["w"])
        others = [i for i in range(cl.shape[2]) if i != wi]
        if u["label"] == "target" and ci is not None:
            marg = cl[:, :, ci] - cl[:, :, wi]
        else:
            marg = cl[:, :, others].max(2) - cl[:, :, wi]
        toks = [tok.decode([t]) for t in ids[:n]]
        on = u["onset"] - s0
        has_scaf = ids[n - len(scaf):n] == scaf
        scaf_start = n - len(scaf) if has_scaf else n - 1
        sents, cur, start = [], [], 0
        for i in range(n):
            region = "input" if i < on else ("call" if i >= scaf_start else "response")
            if cur and (region != sents_region(cur, on, scaf_start)):
                sents.append((start, i - 1))
                start, cur = i, []
            cur.append(i)
            t = toks[i]
            if region != "call" and (("\n" in t) or re.search(r"[.!?]\s*$", t)):
                sents.append((start, i))
                start, cur = i + 1, []
        if cur:
            sents.append((start, n - 1))
        info = []
        for a, b in sents:
            region = "input" if b < on else ("call" if a >= scaf_start else "response")
            text = "".join(toks[a:b + 1]).replace("\n", " ").strip()
            if not text and region != "call":
                continue
            info.append({"a": a, "b": b, "region": region, "text": text, "m": marg[a:b + 1].mean(0), "mmax": marg[a:b + 1].max(0)})
        resp = [s for s in info if s["region"] == "response"]
        for k, s in enumerate(reversed(resp)):
            s["k"] = k + 1
        for s in info:
            if s["region"] == "call":
                s["k"] = 0
        commit = None
        if u["label"] == "target":
            for t in range(on, n):
                rest = marg[t:, KEY]
                if rest[0] > 0 and (rest > 0).mean() >= 0.8:
                    commit = t
                    break
        csent = next((s for s in info if commit is not None and s["a"] <= commit <= s["b"]), None)
        U.append({"u": u, "marg": marg, "info": info, "commit": commit, "csent": csent, "on": on, "n": n, "toks": toks,
                  "top": z["top_ids"], "scaf_start": scaf_start, "pre_len": scaf_start - on - 1})
    md = ["# Trajectory J-lens, ToolAlign-4B CAUSAL-1 units (every token from the input tail to the tool name)", "",
          f"{len(U)} units: {Counter(x['u']['label'] for x in U)}. Margin = lp(chosen tool) - lp(writeInternalLog) (J-lens, same tool "
          "tokens per domain); for references, best other tool - writeInternalLog. Layers 0-30 = lens, 31 = final.", ""]
    md += ["## 1. Mean margin by region (k = sentences before the call; k=1 is the sentence right before it)", "",
           "| group | region | n units | " + " | ".join(f"L{l}" for l in LAYS) + " |", "|---|---|---|" + "---|" * len(LAYS)]

    def group(x):
        n4 = x["u"].get("n4") or {}
        if x["u"]["label"] == "reference":
            return "reference"
        return f"target:{n4.get('kind', 'multi_call')}"
    agg = defaultdict(list)
    for x in U:
        g = group(x)
        inp = [s for s in x["info"] if s["region"] == "input"]
        if inp:
            agg[(g, "input (last 2 sentences)")].append(np.mean([s["m"] for s in inp[-2:]], 0))
        for s in x["info"]:
            if s["region"] == "response" and s["k"] <= 3:
                agg[(g, f"response k={s['k']}")].append(s["m"])
            if s["region"] == "response" and s["k"] > 3:
                agg[(g, "response k>=4")].append(s["m"])
            if s["region"] == "call":
                agg[(g, "call scaffold")].append(s["m"])
        agg[(g, "name position")].append(x["marg"][-1])
    order = ["input (last 2 sentences)", "response k>=4", "response k=3", "response k=2", "response k=1", "call scaffold", "name position"]
    for g in sorted({k[0] for k in agg}):
        for r in order:
            v = agg.get((g, r))
            if v:
                m = np.mean(v, 0)
                md.append(f"| {g} | {r} | {len(v)} | " + " | ".join(f"{m[l]:+.2f}" for l in LAYS) + " |")
    md.append("")
    md += ["## 2. Where the chosen tool takes over (targets): sustained L24 commit token", "",
           "| group | n | commit in input/onset | commit in response k>=2 | commit in k=1 | commit in call scaffold / name | never |",
           "|---|---|---|---|---|---|---|"]
    cg = defaultdict(Counter)
    for x in U:
        if x["u"]["label"] != "target":
            continue
        g = group(x)
        c = x["commit"]
        if c is None:
            cg[g]["never"] += 1
        elif c <= x["on"]:
            cg[g]["input"] += 1
        elif x["csent"] and x["csent"]["region"] == "call":
            cg[g]["call"] += 1
        elif x["csent"] and x["csent"].get("k", 9) == 1:
            cg[g]["k1"] += 1
        else:
            cg[g]["k2"] += 1
    for g, c in sorted(cg.items()):
        md.append(f"| {g} | {sum(c.values())} | {c['input']} | {c['k2']} | {c['k1']} | {c['call']} | {c['never']} |")
    md.append("")
    md += ["## 3. Commit location vs the CAUSAL-1 name-position neuron edit (top-64 / top-256 flip on the original)", "",
           "| commit location | n | flip top-64 | flip top-256 | mean tokens from commit to name |", "|---|---|---|---|---|"]
    rel = defaultdict(list)
    for x in U:
        n4 = x["u"].get("n4")
        if x["u"]["label"] != "target" or not n4 or "neur_top_64" not in n4:
            continue
        c = x["commit"]
        loc = "never sustained" if c is None else ("before the call (response text)" if x["csent"] and x["csent"]["region"] == "response"
                                                  else ("input/onset" if c <= x["on"] else "call scaffold / name"))
        rel[loc].append((n4["neur_top_64"], n4.get("neur_top_256"), (x["n"] - 1 - c) if c is not None else None))
    for loc, v in sorted(rel.items()):
        dist = [t for _, _, t in v if t is not None]
        md.append(f"| {loc} | {len(v)} | {np.mean([a for a, _, _ in v]):.0%} | {np.mean([b for _, b, _ in v if b is not None]):.0%} | "
                  f"{np.mean(dist) if dist else float('nan'):.0f} |")
    md.append("")
    md += ["### 3b. Is the tool already written in the response text before the call? (copy source)", "",
           "named = the exact tool name, or all words of its camelCase split (e.g. 'access vehicle safety database'), appears in the "
           "response text before the call.", "",
           "| group | named in text | n | flip top-64 | flip top-256 | name-position margin L24 / final |", "|---|---|---|---|---|---|"]
    rb = defaultdict(list)
    for x in U:
        n4 = x["u"].get("n4")
        if x["u"]["label"] != "target" or not n4 or "neur_top_64" not in n4:
            continue
        resp_text = "".join(x["toks"][x["on"] + 1:x["scaf_start"]]).lower()
        words = [w.lower() for w in re.findall(r"[A-Z]?[a-z]+", x["u"]["tool"])]
        named = x["u"]["tool"].lower() in resp_text or (len(words) > 1 and all(w in resp_text for w in words))
        rb[(group(x), named)].append((n4["neur_top_64"], n4.get("neur_top_256"), x["marg"][-1]))
    for (g, named), v in sorted(rb.items()):
        mm = np.mean([m for _, _, m in v], 0)
        md.append(f"| {g} | {named} | {len(v)} | {np.mean([a for a, _, _ in v]):.0%} | {np.mean([b for _, b, _ in v if b is not None]):.0%} | "
                  f"{mm[24]:+.1f} / {mm[31]:+.1f} |")
    md.append("")
    md += ["## 4. J-lens words at the commit token (targets, L16-L28, top-10 of top-50, counts over units)", ""]
    wc = Counter()
    wr = Counter()
    for x in U:
        if x["u"]["label"] == "target" and x["commit"] is not None and x["commit"] > x["on"]:
            for l in range(16, 29):
                wc.update(x["top"][x["commit"], l, :10].tolist())
        if x["u"]["label"] == "reference":
            for s in x["info"]:
                if s["region"] == "response":
                    for l in range(16, 29):
                        wr.update(x["top"][s["b"], l, :10].tolist())
    nr = max(1, sum(wr.values()))
    nc = max(1, sum(wc.values()))
    lift = sorted(wc, key=lambda t: -(wc[t] / nc) / ((wr[t] + 1) / nr))[:25]
    md.append("- most over-represented vs reference preamble sentence ends: " + ", ".join(f"{tok.decode([t])!r}({wc[t]})" for t in lift if wc[t] >= 3))
    md.append("- most frequent at commit tokens: " + ", ".join(f"{tok.decode([t])!r}({c})" for t, c in wc.most_common(20)))
    md.append("")
    md += ["## 5. Examples (sentence by sentence; margins at L20 / L24 / L28 / final; <== = sustained commit sentence)", ""]
    picks = []
    for g in ("target:text_preamble", "target:no_preamble", "target:multi_call"):
        picks += [x for x in U if group(x) == g][:3 if g == "target:text_preamble" else 2]
    picks += [x for x in U if group(x) == "reference" and x["pre_len"] > 20][:2]
    for x in picks:
        u = x["u"]
        n4 = u.get("n4") or {}
        md += [f"### {group(x)} | {u['domain']} | tool {u['tool']} ({u['risk']}) | preamble {x['pre_len']} tokens | "
               f"edit flip top-64: {n4.get('neur_top_64')}", ""]
        for s in x["info"][-12:]:
            m = s["m"]
            tag = "<==" if x["csent"] is s else ""
            k = s.get("k", "")
            md.append(f"- [{s['region']}{'' if k == '' else ' k=' + str(k)}] {m[20]:+.1f} / {m[24]:+.1f} / {m[28]:+.1f} / {m[31]:+.1f} {tag} "
                      f"| {s['text'][:140]}")
        md.append("")
    Path(sys.argv[2]).write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:80]))


def sents_region(cur, on, scaf_start):
    i = cur[0]
    return "input" if i < on else ("call" if i >= scaf_start else "response")


if __name__ == "__main__":
    main()
