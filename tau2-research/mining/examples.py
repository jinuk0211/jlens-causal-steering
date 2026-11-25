"""Concrete examples for the mining results: failed episodes by failure kind, with the J-lens decision-point readout.
Output: mining/examples.md (UTF-8)."""
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
TOPK = Path(r"C:\Users\h\Documents\ChatGPT\vlm interpretability\work\tau2-topk-20261119")
V = 248320
SHOW_LAYERS = (16, 20, 22, 24, 26, 28, 31)
READS = ("get_", "find_", "list_", "search_", "calculate", "think")


def clean(w):
    return w.replace("\n", "\\n").replace("|", "/")


def main():
    voc = json.loads(gzip.open(HERE / "vocab.json.gz", "rt", encoding="utf-8").read())
    turns = json.loads((HERE / "cache_turns.json").read_text(encoding="utf-8"))
    dec = np.load(HERE / "cache_dec.npy")
    res = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
    pairs = {(p["layer"], p["word"]): p["log_ratio"] for p in res["W_clean"]["top_pairs_full_fit"]}
    pair_keys = {}
    for (layer, word), lr in pairs.items():
        for i, w in enumerate(voc):
            if w == word:
                pair_keys[layer * V + i] = (layer, word, lr)
    eps = defaultdict(list)
    for t in turns:
        eps[(t["domain"], t["task"], t["sim"])].append(t)
    meta = {}
    for jf in TOPK.glob("*.json"):
        m = json.loads(jf.read_text(encoding="utf-8"))
        meta[(m["domain"], str(m["task"]), m["sim_id"])] = (m, jf)
    md = ["# Examples: failed episodes and the J-lens readout at the decision point", ""]
    failed = [k for k, ts in eps.items() if not ts[0]["ep_pass"]]
    kinds = Counter()
    no_bad = []
    for k in failed:
        b = [x.split(":")[0] for t in eps[k] for x in t["bad"]]
        if b:
            kinds.update(set(b))
        else:
            no_bad.append(k)
    md += [f"- failed episodes: {len(failed)}; with at least one bad write by kind: {dict(kinds)}; without any flagged bad write: {len(no_bad)}",
           f"- failure types of the episodes without a flagged bad write: "
           + json.dumps(Counter(ft for k in no_bad for ft in meta[k][0]["failure_types"]).most_common()), ""]
    picks = []
    seen_kind = Counter()
    for k in sorted(failed):
        for t in eps[k]:
            if t["label"] != "bad_write" or "dec_row" not in t:
                continue
            kind = t["bad"][0].split(":")[0]
            key = (kind, t["domain"])
            if seen_kind[key] >= 2:
                continue
            seen_kind[key] += 1
            picks.append((k, t))
    good = []
    seen_tool = Counter()
    for k, ts in sorted(eps.items()):
        if not ts[0]["ep_pass"]:
            continue
        for t in ts:
            if t["label"] == "good_write" and "dec_row" in t:
                tool = next((c for c in t["calls"] if not c.startswith(READS)), "none")
                if tool in ("transfer_to_human_agents", "update_reservation_flights", "cancel_pending_order", "refuel_data") and seen_tool[tool] < 2:
                    seen_tool[tool] += 1
                    good.append((k, t))
    for title, items in (("BAD writes in failed episodes", picks), ("GOOD writes in passed episodes (contrast)", good)):
        md += [f"## {title}", ""]
        for k, t in items:
            m, jf = meta[k]
            mt = next(x for x in m["turns"] if int(x["turn"]) == t["turn"])
            z = np.load(jf.with_suffix(".npz"))
            sel = np.nonzero((z["ctx_turn"] == t["turn"]) & (z["ctx_seg"] == 0))[0]
            user = "".join(voc[i] for i in z["ctx_tok"][sel][np.argsort(z["ctx_pos"][sel])])[-300:]
            ids = dec[t["dec_row"]]
            keys = set(((np.arange(32)[:, None] * V) + ids.astype(np.int64)).ravel().tolist())
            fired = sorted({pair_keys[x][:2] for x in keys if x in pair_keys})
            score = sum(pair_keys[x][2] for x in keys if x in pair_keys)
            calls = [(c["name"], c.get("arguments")) for c in mt["calls"]]
            md += [f"### {t['domain']} task {k[1][:70]} turn {t['turn']} | {t['bad'] or 'good'}",
                   f"- episode failure types: {m['failure_types']}",
                   f"- gold writes: {json.dumps(m.get('gold_writes'))[:400]}",
                   f"- user just before: {clean(user.strip())[-260:]!r}",
                   f"- agent call: {json.dumps(calls)[:400]}",
                   f"- agent text: {clean((mt.get('text') or '').strip())[:300]!r}",
                   f"- mined-pair score {round(score, 2)}; pairs present: {fired}",
                   "", "| layer | J-lens top-8 at the decision point |", "|---|---|"]
            for layer in SHOW_LAYERS:
                md.append(f"| L{layer} | " + " · ".join(repr(clean(voc[i])) for i in ids[layer][:8]) + " |")
            md.append("")
    (HERE / "examples.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
