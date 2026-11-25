"""Turn-level feature cache from the all-layer top-k episodes (work/tau2-topk-20261119), CPU only.

Per agent turn: domain, task, labels, episode outcome (retail NL-corrected), the J-lens decision-point top-100 ids at all
32 layers (write turns only), per-family best rank at every layer at the decision point, and generated-text statistics
(L20 top-1 missing from the L31 top-30; commitment layer of each generated token).
Output: mining/cache_turns.json, mining/cache_dec.npy (write turns: [n, 32, 100] int32).
"""
import gzip
import json
import os
import sys
from pathlib import Path

import numpy as np

TOPK = Path(r"C:\Users\h\Documents\ChatGPT\vlm interpretability\work\tau2-topk-20261119")
HERE = Path(__file__).resolve().parent
NL = Path(r"C:\Users\h\Documents\ChatGPT\vlm interpretability\work\tau2-research\nl_judge\nl_verdicts.json")
FAMILIES = {
    "refusal": {"unfortunately", "cannot", "can't", "unable", "sorry", "apologize", "apologies", "regret", "not"},
    "hesitate": {"wait", "actually", "hmm", "however", "but", "although", "though", "instead"},
    "verify": {"confirm", "verify", "check", "double", "ensure", "sure", "confirmation"},
    "ask": {"could", "would", "please", "?", "question", "clarify", "which"},
    "transfer": {"transfer", "human", "representative", "escalate", "specialist"},
    "error": {"error", "failed", "fail", "invalid", "issue", "problem", "wrong", "incorrect"},
}
GEN, DEC = 4, 3


def main():
    voc = json.loads(gzip.open(HERE / "vocab.json.gz", "rt", encoding="utf-8").read())
    norm = [v.strip().lower() for v in voc]
    fam_ids = {f: np.array([i for i, w in enumerate(norm) if w in ws], dtype=np.int64) for f, ws in FAMILIES.items()}
    fam_mask = {}
    for f, ids in fam_ids.items():
        m = np.zeros(len(voc), dtype=bool)
        m[ids] = True
        fam_mask[f] = m
    wordlike = np.array([any(ch.isalpha() for ch in v) and len(v.strip()) >= 3 for v in voc])
    nl = json.loads(NL.read_text(encoding="utf-8"))["records"]
    turns, dec_rows = [], []
    files = sorted(TOPK.glob("*.json"))
    for n, jf in enumerate(files):
        m = json.loads(jf.read_text(encoding="utf-8"))
        if m.get("cond") != "f_detect":
            continue
        dom, task, sid = m["domain"], str(m["task"]), m["sim_id"]
        reward = float(m["reward"] or 0)
        key = f"f_detect|{dom}|{task}|{sid}"
        if dom == "retail" and key in nl:
            reward = float(nl[key]["corrected_reward"])
        z = np.load(jf.with_suffix(".npz"))
        dec_turn = z["dec_turn"]
        dec_ids = z["dec_ids_jlens"]
        a_turn, a_seg, a_pos, a_tok = z["agent_turn"], z["agent_seg"], z["agent_pos"], z["agent_tok"]
        a_top = z["agent_topk_jlens"]
        dec_index = {int(t): i for i, t in enumerate(dec_turn)}
        for t in m["turns"]:
            ti = int(t["turn"])
            row = {"domain": dom, "task": task, "sim": sid, "turn": ti, "label": t["label"], "bad": t["bad"],
                   "ep_pass": reward >= 1, "calls": [c["name"] for c in t["calls"]]}
            di = dec_index.get(ti)
            if di is not None:
                ids = dec_ids[di]
                fam_rank = {}
                for f, msk in fam_mask.items():
                    hit = msk[ids]
                    r = np.where(hit.any(1), hit.argmax(1) + 1, 101)
                    fam_rank[f] = r.tolist()
                row["fam_rank"] = fam_rank
                if t["label"] in ("bad_write", "good_write"):
                    row["dec_row"] = len(dec_rows)
                    dec_rows.append(ids.astype(np.int32))
            sel = np.nonzero((a_turn == ti) & (a_seg == GEN))[0]
            if len(sel) > 1:
                order = sel[np.argsort(a_pos[sel])]
                pred = a_tok[order[1:]]
                tops = a_top[order[:-1]]
                top1_20 = tops[:, 20, 0]
                miss = ~(tops[:, 31, :] == top1_20[:, None]).any(1)
                wl = wordlike[top1_20]
                row["rev20_rate"] = float((miss & wl).mean())
                commit = np.full(len(pred), 32)
                for layer in range(31, -1, -1):
                    still = tops[:, layer, 0] == pred
                    commit = np.where(still & (commit == layer + 1), layer, commit)
                row["commit_mean"] = float(commit.mean())
                row["late_commit_rate"] = float((commit >= 28).mean())
                row["n_gen"] = int(len(pred))
            turns.append(row)
        if n % 25 == 0:
            print(f"{n}/{len(files)} {jf.name[:60]}", flush=True)
    (HERE / "cache_turns.json").write_text(json.dumps(turns), encoding="utf-8")
    np.save(HERE / "cache_dec.npy", np.stack(dec_rows) if dec_rows else np.zeros((0, 32, 100), np.int32))
    print("turns", len(turns), "write decision rows", len(dec_rows))


if __name__ == "__main__":
    main()
