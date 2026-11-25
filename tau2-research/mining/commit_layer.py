"""J-lens counterpart of M1's "formation layer": at which layer does the tool-name token of a call become the J-lens top-1 and stay
top-1 through L31? (278 f_detect episodes, agent generated-token readouts, top-30 per layer.)
Unit = the first tool-name token after "<function=" in a generated turn (readout at the "=" position predicts it).
Groups: BT unneeded transfer in a failed episode; GT transfer in a passed episode (same token 'transfer', so the token is
controlled); BW unexpected write in a failed episode; GW good write (other tools) in a passed episode.
Output: mining/commit_layer.md
"""
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import mine

HERE = Path(__file__).resolve().parent
TOPK = HERE.parent.parent / "tau2-topk-20261119"


def main():
    voc = json.loads(gzip.open(HERE / "vocab.json.gz", "rt", encoding="utf-8").read())
    nl = json.loads((HERE.parent / "nl_judge/nl_verdicts.json").read_text(encoding="utf-8"))["records"]
    units = []
    for jf in sorted(TOPK.glob("*.json")):
        m = json.loads(jf.read_text(encoding="utf-8"))
        if m.get("cond") != "f_detect":
            continue
        r = float(m["reward"] or 0)
        key = f"f_detect|{m['domain']}|{m['task']}|{m['sim_id']}"
        if m["domain"] == "retail" and key in nl:
            r = float(nl[key]["corrected_reward"])
        ok = r >= 1
        z = np.load(jf.with_suffix(".npz"))
        at, aseg, apos, atok, atop = z["agent_turn"], z["agent_seg"], z["agent_pos"], z["agent_tok"], z["agent_topk_jlens"]
        for t in m["turns"]:
            if not t["calls"]:
                continue
            sel = np.nonzero((at == int(t["turn"])) & (aseg == 4))[0]
            order = sel[np.argsort(apos[sel])]
            toks = [voc[x] for x in atok[order]]
            name_pos = [k + 3 for k in range(len(toks) - 3) if toks[k] == "<" and toks[k + 1] == "function" and toks[k + 2] == "="]
            for ci, (call, p) in enumerate(zip(t["calls"], name_pos)):
                name = call["name"]
                if name.startswith(mine.__dict__.get("READS", ("get_", "find_", "list_", "search_", "calculate", "think"))):
                    continue
                bad_kinds = [b.split(":")[0] for b in t["bad"] if b.endswith(":" + name)]
                if name == "transfer_to_human_agents":
                    if "unexpected_transfer" in bad_kinds and not ok:
                        g = "BT"
                    elif not bad_kinds and ok:
                        g = "GT"
                    else:
                        continue
                else:
                    if "unexpected_write" in bad_kinds and not ok:
                        g = "BW"
                    elif not bad_kinds and ok:
                        g = "GW"
                    else:
                        continue
                tok = atok[order[p]]
                tops = atop[order[p - 1]]
                rank = np.array([int(np.nonzero(tops[l] == tok)[0][0]) if (tops[l] == tok).any() else 30 for l in range(tops.shape[0])])
                top1 = rank == 0
                commit = 32
                for l in range(31, -1, -1):
                    if top1[l]:
                        commit = l
                    else:
                        break
                enter = int(np.nonzero(rank < 30)[0][0]) if (rank < 30).any() else 32
                units.append({"g": g, "domain": m["domain"], "task": m["task"], "name": name, "commit": commit, "enter": enter,
                              "rank": rank.tolist(), "first_top1": int(np.nonzero(top1)[0][0]) if top1.any() else 32})
    md = ["# J-lens commitment layer of the tool-name token (counterpart of M1's formation layer)", "",
          f"units: {dict(Counter(u['g'] for u in units))}", "",
          "| group | n | tasks | commit layer median (IQR) | first layer in top-30 median | first top-1 median | top-1 already at L20 | at L24 | at L27 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for g in ("BT", "GT", "BW", "GW"):
        U = [u for u in units if u["g"] == g]
        if not U:
            continue
        c = np.array([u["commit"] for u in U])
        md.append(f"| {g} | {len(U)} | {len({(u['domain'], u['task']) for u in U})} | {np.median(c):.0f} ({np.percentile(c, 25):.0f}-{np.percentile(c, 75):.0f}) | "
                  f"{np.median([u['enter'] for u in U]):.0f} | {np.median([u['first_top1'] for u in U]):.0f} | "
                  f"{np.mean([u['rank'][20] == 0 for u in U]):.2f} | {np.mean([u['rank'][24] == 0 for u in U]):.2f} | {np.mean([u['rank'][27] == 0 for u in U]):.2f} |")
    for a, b in (("BT", "GT"), ("BW", "GW")):
        A = [u for u in units if u["g"] in (a, b)]
        if len({u["g"] for u in A}) < 2:
            continue
        y = np.array([u["g"] == a for u in A], int)
        for feat in ("commit", "enter", "first_top1"):
            s = -np.array([u[feat] for u in A], float)
            md.append(f"- {a} vs {b}: AUC of an EARLIER {feat} layer = {mine.auc(s, y):.3f} "
                      f"(task-cluster CI {mine.boot_ci(s, y, [u['domain'] + '|' + u['task'] for u in A], np.random.default_rng(0))})")
    md += ["", "Mean rank of the chosen tool-name token by layer (0 = top-1, 30 = not in top-30):", "",
           "| layer | " + " | ".join(g for g in ("BT", "GT", "BW", "GW")) + " |", "|---|---|---|---|---|"]
    for l in range(12, 32):
        md.append(f"| L{l} | " + " | ".join(f"{np.mean([u['rank'][l] for u in units if u['g'] == g]):.1f}" if any(u['g'] == g for u in units) else "-"
                                            for g in ("BT", "GT", "BW", "GW")) + " |")
    (HERE / "commit_layer.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
