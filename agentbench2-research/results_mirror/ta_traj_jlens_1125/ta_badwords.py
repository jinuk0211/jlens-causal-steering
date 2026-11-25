"""Which J-lens words come with bad actions in ToolAlign-4B? Trajectory scan output (ta_traj_jlens.py).
Groups: bad = clearly-misaligned calls (external email, data export, evidence deletion); boundary = unauthorized access;
aligned = internal-reporting emails; reference = writeInternalLog.
Per unit, region (input tail / response text before the call / call scaffold + name) and layer band, a token's score is
the share of (position, layer) cells where it is in the top-20. Ranking: the domain-matched difference bad - reference
(per domain with both, then averaged), so words that come from a domain's documents cancel. Also: in how many bad
domains the difference is > 0, and the same difference for boundary and aligned emails.
Usage: python ta_badwords.py TRAJ_DIR OUT_MD"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_core as C

BANDS = {"L12-18": range(12, 19), "L19-24": range(19, 25), "L25-30": range(25, 31)}
K = 20
SCAF = "<tool_call>\n<tool_name>"


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    d = Path(sys.argv[1])
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    scaf = tok.encode(SCAF, add_special_tokens=False)
    V = len(tok)
    grp = lambda u: "reference" if u["label"] == "reference" else {"clearly-misaligned": "bad", "boundary": "boundary", "aligned": "aligned"}[u["risk"]]
    S = defaultdict(dict)
    for u in meta:
        z = np.load(d / f"u_{u['idx']}.npz")
        top = z["top_ids"][:, :, :K]
        n = top.shape[0]
        on = u["onset"] - u["span"][0]
        ids = u["span_ids"]
        sc = n - len(scaf) if ids[n - len(scaf):n] == scaf else n - 1
        regions = {"input": range(0, on), "response": range(on, sc), "call": range(sc, n)}
        for r, pos in regions.items():
            pos = list(pos)
            if not pos:
                continue
            for b, lays in BANDS.items():
                cells = top[pos][:, list(lays)].reshape(-1)
                cnt = np.bincount(cells, minlength=V).astype(np.float32) / (len(pos) * len(lays))
                S[(r, b)][u["idx"]] = cnt
    by = {u["idx"]: (grp(u), u["domain"]) for u in meta}
    bad_domains = sorted({dm for g, dm in by.values() if g == "bad"})
    md = ["# J-lens words that come with bad actions, ToolAlign-4B (trajectory scan)", "",
          f"bad units: {sum(g == 'bad' for g, _ in by.values())} in {len(bad_domains)} domains {bad_domains}; "
          f"boundary {sum(g == 'boundary' for g, _ in by.values())}; aligned emails {sum(g == 'aligned' for g, _ in by.values())}; "
          f"references {sum(g == 'reference' for g, _ in by.values())}.",
          "Score = share of (position, layer) cells with the token in the top-20. diff = domain-matched mean(group) - mean(reference).", ""]
    for (r, b), sc in S.items():
        def dmean(g, dm):
            xs = [sc[i] for i, (gg, dd) in by.items() if gg == g and dd == dm and i in sc]
            return np.mean(xs, 0) if xs else None

        diffs = {g: [] for g in ("bad", "boundary", "aligned")}
        doms = {g: [] for g in diffs}
        for dm in sorted({dd for _, dd in by.values()}):
            ref = dmean("reference", dm)
            if ref is None:
                continue
            for g in diffs:
                m = dmean(g, dm)
                if m is not None:
                    diffs[g].append(m - ref)
                    doms[g].append(dm)
        if not diffs["bad"]:
            continue
        D = np.stack(diffs["bad"])
        mean_d = D.mean(0)
        pos_dom = (D > 0.002).sum(0)
        order = np.argsort(-mean_d)
        bd = np.mean(diffs["boundary"], 0) if diffs["boundary"] else np.zeros(V)
        ad = np.mean(diffs["aligned"], 0) if diffs["aligned"] else np.zeros(V)
        md += [f"## {r} | {b} (bad units in {len(doms['bad'])} domains with references)", "",
               "| word | bad - ref | bad domains with diff > 0 | boundary - ref | aligned email - ref |", "|---|---|---|---|---|"]
        shown = 0
        for t in order:
            if mean_d[t] < 0.003 or shown >= 15:
                break
            if pos_dom[t] < max(2, (len(doms["bad"]) + 1) // 2):
                continue
            md.append(f"| {tok.decode([int(t)])!r} | {mean_d[t]:+.3f} | {pos_dom[t]}/{len(doms['bad'])} | {bd[t]:+.3f} | {ad[t]:+.3f} |")
            shown += 1
        md.append("")
    Path(sys.argv[2]).write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
