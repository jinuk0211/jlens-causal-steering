import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE.parent.parent
TOPK = RES.parent / "tau2-topk-20261119"
WORDS = {"transfer", "transferring", "transferred", "human", "humans", "specialist", "supervisor", "representative",
         "escalate", "escalation", "人工", "转接", "转人工"}
LAYERS = list(range(20, 32))


def auc(s, y):
    s, y = np.asarray(s, float), np.asarray(y)
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    gt = (pos[:, None] > neg[None]).sum() + 0.5 * (pos[:, None] == neg[None]).sum()
    return float(gt / (len(pos) * len(neg)))


def main():
    voc = json.loads(gzip.open(RES / "mining/vocab.json.gz", "rt", encoding="utf-8").read())
    mask = np.array([v.strip().lower() in WORDS for v in voc])
    turns = json.loads((RES / "mining/cache_turns.json").read_text(encoding="utf-8"))
    lab = {}
    ep_has_transfer = defaultdict(bool)
    for t in turns:
        key = (t["domain"], str(t["task"]), t["sim"])
        if "transfer_to_human_agents" in t["calls"]:
            ep_has_transfer[key] = True
            bad = any(b.startswith("unexpected_transfer") for b in t["bad"])
            y = 1 if (bad and not t["ep_pass"]) else (0 if t["ep_pass"] else None)
            if y is not None:
                lab[key + (t["turn"],)] = y
    files = {}
    for jf in TOPK.glob("*.json"):
        m = json.loads(jf.read_text(encoding="utf-8"))
        files[(m["domain"], str(m["task"]), m["sim_id"])] = jf.with_suffix(".npz")

    def turn_scores(z):
        ids = z["dec_ids_jlens"]
        out = {}
        for i, t in enumerate(z["dec_turn"].tolist()):
            hit = mask[ids[i]]
            per = []
            for l in LAYERS:
                h = np.nonzero(hit[l])[0]
                per.append(101 - (h[0] + 1) if len(h) else 0)
            out[t] = (np.array(per) / 100.0, int(sum(1 for p in per if p > 0)))
        return out

    rows = []
    for (d, task, sim, turn), y in sorted(lab.items()):
        f = files.get((d, task, sim))
        if f is None:
            continue
        sc = turn_scores(np.load(f))
        lags = {}
        for lag in range(0, 6):
            if turn - lag in sc:
                lags[lag] = sc[turn - lag]
        onset = 0
        while (onset + 1) in lags and lags[onset + 1][1] >= 3:
            onset += 1
        rows.append({"domain": d, "task": task, "sim": sim, "turn": turn, "y": y, "lags": lags, "onset": onset})
    base = []
    for key, f in files.items():
        if ep_has_transfer.get(key):
            continue
        for t, (per, n) in turn_scores(np.load(f)).items():
            base.append((per, n))
    md = ["# X1: when does the transfer intention show up in the J-lens readout? (decision points, top-100, L20-31)", "",
          f"transfer rows: bad {sum(r['y'] for r in rows)}, good {sum(1 - r['y'] for r in rows)}; "
          f"base rate from {len(base)} decision points of episodes that never transfer", "",
          f"- base: mean layers with a transfer word in top-100 = {np.mean([n for _, n in base]):.2f}; "
          f"share of decision points with >= 3 such layers = {np.mean([n >= 3 for _, n in base]):.3f}", "",
          "| lag (turns before the transfer turn) | n bad / good | mean #layers bad | mean #layers good | AUC (bad vs good, #layers) | share >= 3 layers bad | good |",
          "|---|---|---|---|---|---|---|"]
    for lag in range(0, 6):
        rs = [r for r in rows if lag in r["lags"]]
        nb = [r["lags"][lag][1] for r in rs if r["y"] == 1]
        ng = [r["lags"][lag][1] for r in rs if r["y"] == 0]
        if not rs:
            continue
        a = auc([r["lags"][lag][1] for r in rs], [r["y"] for r in rs])
        md.append(f"| {lag} | {len(nb)} / {len(ng)} | {np.mean(nb) if nb else float('nan'):.2f} | {np.mean(ng) if ng else float('nan'):.2f} | "
                  f"{'-' if a is None else round(a, 3)} | {np.mean([x >= 3 for x in nb]) if nb else float('nan'):.2f} | "
                  f"{np.mean([x >= 3 for x in ng]) if ng else float('nan'):.2f} |")
    md += ["", "onset = number of consecutive earlier turns (before the transfer turn) with >= 3 layers showing a transfer word:", ""]
    for y in (1, 0):
        on = [r["onset"] for r in rows if r["y"] == y]
        md.append(f"- {'bad' if y else 'good'}: onset distribution {dict(sorted(Counter_(on).items()))}, mean {np.mean(on):.2f}")
    md += ["", "per-layer mean readout score (101 - rank)/100 at lag 0 and lag 1:", "",
           "| layer | lag0 bad | lag0 good | lag1 bad | lag1 good |", "|---|---|---|---|---|"]
    for li, l in enumerate(LAYERS):
        vals = []
        for lag in (0, 1):
            for y in (1, 0):
                v = [r["lags"][lag][0][li] for r in rows if lag in r["lags"] and r["y"] == y]
                vals.append(f"{np.mean(v):.2f}" if v else "-")
        md.append(f"| L{l} | " + " | ".join(vals) + " |")
    md += ["", "by domain, lag 1 mean #layers (bad / good):", ""]
    for d in sorted({r["domain"] for r in rows}):
        b = [r["lags"][1][1] for r in rows if r["domain"] == d and 1 in r["lags"] and r["y"] == 1]
        g = [r["lags"][1][1] for r in rows if r["domain"] == d and 1 in r["lags"] and r["y"] == 0]
        md.append(f"- {d}: bad {np.mean(b) if b else float('nan'):.2f} (n {len(b)}), good {np.mean(g) if g else float('nan'):.2f} (n {len(g)})")
    (HERE / "x1_onset.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (HERE / "x1_onset.json").write_text(json.dumps([{k: (v if k != "lags" else {str(a): [b[0].round(3).tolist(), b[1]] for a, b in v.items()})
                                                     for k, v in r.items()} for r in rows], indent=1), encoding="utf-8")
    print("\n".join(md))


def Counter_(xs):
    from collections import Counter
    return Counter(xs)


if __name__ == "__main__":
    main()
