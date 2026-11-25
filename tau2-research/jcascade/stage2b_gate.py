import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "mining"))
import mine

MINING = HERE.parent / "mining"


def main():
    turns = json.loads((MINING / "cache_turns.json").read_text(encoding="utf-8"))
    dec = np.load(MINING / "cache_dec.npy")
    rows = []
    for t in turns:
        if "transfer_to_human_agents" not in t["calls"] or "dec_row" not in t:
            continue
        bad = any(b.startswith("unexpected_transfer") for b in t["bad"])
        y = 1 if (bad and not t["ep_pass"]) else (0 if t["ep_pass"] else None)
        if y is None:
            continue
        rows.append({"domain": t["domain"], "sim": t["sim"], "turn": t["turn"], "y": y, "group": f"{t['domain']}|{t['task']}",
                     "keys": mine.pair_keys(dec[t["dec_row"]])})
    y = np.array([r["y"] for r in rows])
    folds = np.array([mine.fold_of(r["group"]) for r in rows])
    oof = np.zeros(len(rows))
    for f in range(mine.NFOLD):
        tr, te = np.nonzero(folds != f)[0], np.nonzero(folds == f)[0]
        if len(set(y[tr].tolist())) < 2:
            continue
        sel, *_ = mine.select_pairs([rows[i]["keys"] for i in tr], y[tr])
        for i in te:
            oof[i] = mine.score_pairs(rows[i]["keys"], sel)
    out = [{"domain": r["domain"], "sim": r["sim"], "turn": r["turn"], "y": r["y"], "J_pairs_oof": float(s)} for r, s in zip(rows, oof)]
    print("rows", len(out), "AUC", mine.auc(oof, y))
    (HERE / "out/stage2b_gate.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
