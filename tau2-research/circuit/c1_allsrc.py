"""C-LOOP C1 exploratory: all-layer source profile of decision tokens (8 full-attention layers from C0a tsrc_* plus 24 linear-
attention layers from c0_linsrc.py), as shares of m by role, bad vs good, per domain. Also the top source positions over all 32
layers for each unit, decoded. Usage: c1_allsrc.py <c0 out dir> <units json>. CPU only. Prints a report."""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

R = Path("/home/project-b/LJW/tau2-steer")
sys.path.insert(0, str(R / "probe/topk"))
sys.path.insert(0, str(R / "probe/circuit"))
import build_topk as bt
from c1_profile import auc

ROLES = ["system", "user_earlier", "user_last", "tool_earlier", "tool_last", "assistant_earlier", "header", "gen", "other"]


def main():
    c0 = Path(sys.argv[1])
    units = {u["k"]: u for u in json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))}
    rows = [r for r in json.loads((c0 / "units.json").read_text(encoding="utf-8")) if (c0 / f"ls_{r['k']}.npz").is_file()]
    os.chdir(R / "tau2-bench")
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(os.environ["JC_MODEL"])
    want = {(units[r["k"]]["cond"], units[r["k"]]["sim"], units[r["k"]]["turn"]): r["k"] for r in rows}
    seqs = {}
    for domain in ("airline", "retail", "telecom"):
        conds = sorted({units[r["k"]]["cond"] for r in rows if r["domain"] == domain})
        if not conds:
            continue
        for domain_, cond, task, sim, tel in bt.episodes(Path("data/simulations/pilot"), Path("data/jlens-telemetry/pilot"), [domain], conds):
            for line in tel.open(encoding="utf-8"):
                rec = json.loads(line)
                key = (cond, sim["id"], int(rec["turn_index"]))
                if key in want:
                    k = want[key]
                    seqs[k] = list(rec["input_ids"]) + list(rec["generated_ids"][:units[k]["d"]])
    prof = {}
    for r in rows:
        z = np.load(c0 / f"n_{r['k']}.npz")
        ls = np.load(c0 / f"ls_{r['k']}.npz")
        full = z["tsrc_role"].sum((0, 1))
        lin = ls["role_tot"].sum((0, 1))
        T = len(z["codes"])
        pos = z["tsrc_pos"].astype(np.float32).sum(0) + ls["tot"].astype(np.float32).sum(0)
        last = T - 1
        own = pos[last]
        prof[r["k"]] = dict(full=full / r["m"], lin=lin / r["m"], all=(full + lin) / r["m"], own=own / r["m"], pos=pos, codes=z["codes"])
    print(f"{len(rows)} units with all-layer sources")
    print("\nmean share of m by role (all 32 layers; 'own' = the decision token's own position), bad vs good, by domain:")
    hdr = "  " + f"{'group':22s}" + "".join(f"{r_[:9]:>10s}" for r_ in ROLES) + f"{'own':>8s}"
    print(hdr)
    groups = defaultdict(list)
    for r in rows:
        groups[(r["label"], r["domain"])].append(r["k"])
        groups[(r["label"], "all")].append(r["k"])
    for g, ks in sorted(groups.items()):
        a = np.mean([prof[k]["all"] for k in ks], axis=0)
        o = np.mean([prof[k]["own"] for k in ks])
        print("  " + f"{g[0] + ' ' + g[1] + f' n={len(ks)}':22s}" + "".join(f"{v:10.3f}" for v in a) + f"{o:8.3f}")
    print("\nAUC bad vs good per role share (all units; airline only; via linear attention only):")
    lab = np.array([r["label"] == "bad" for r in rows])
    air = np.array([r["domain"] == "airline" for r in rows])
    for i, role in enumerate(ROLES):
        x = np.array([prof[r["k"]]["all"][i] for r in rows])
        xl = np.array([prof[r["k"]]["lin"][i] for r in rows])
        print(f"  {role:18s} all {auc(x[lab], x[~lab]):.2f} | airline {auc(x[lab & air], x[~lab & air]):.2f} | lin-only {auc(xl[lab], xl[~lab]):.2f}")
    print("\ntop sources over all 32 layers per unit (excluding the decision token):")
    for r in rows:
        p = prof[r["k"]]
        seq = seqs.get(r["k"])
        if seq is None:
            continue
        pos = p["pos"]
        order = np.argsort(-pos[:-1])[:6]
        parts = []
        for q in order:
            a, b = max(0, q - 6), min(len(seq), q + 3)
            parts.append(f"{pos[q] / r['m']:+.2f} {ROLES[p['codes'][q]][:6]} {tok.decode(seq[a:q]) + '[[' + tok.decode([seq[q]]) + ']]' + tok.decode(seq[q + 1:b])!r}")
        print(f"  k={r['k']} {r['label']} {r['domain']} {str(r['task'])[:10]} m={r['m']:.1f}:")
        for s in parts:
            print("     " + s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
