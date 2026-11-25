"""C-LOOP C1 exploratory report: which context tokens drive a decision token, from the C0a total source effects (tsrc_pos: per
full-attention layer and source position, a_{h,s} v_s . (sigmoid(gate_h) * dm/d(o_proj input)_h), summed over heads).
Per unit: m, contrast token, role shares of the summed total effect, per-layer role sums, and the top source positions decoded with
context. Usage: c1_src_report.py <c0 out dir> <units json> [k ...]. CPU only. Prints a text report."""
import json
import os
import sys
from pathlib import Path

import numpy as np

R = Path("/home/project-b/LJW/tau2-steer")
sys.path.insert(0, str(R / "probe/topk"))
import build_topk as bt

ROLES = ["system", "user_earlier", "user_last", "tool_earlier", "tool_last", "assistant_earlier", "header", "gen", "other"]
FULL = [3, 7, 11, 15, 19, 23, 27, 31]
TOPN = 12


def main():
    c0 = Path(sys.argv[1])
    units = {u["k"]: u for u in json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))}
    rows = {r["k"]: r for r in json.loads((c0 / "units.json").read_text(encoding="utf-8"))}
    ks = [int(k) for k in sys.argv[3:]] or sorted(rows)
    ks = [k for k in ks if k in rows and (c0 / f"n_{k}.npz").is_file()]
    os.chdir(R / "tau2-bench")
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(os.environ["JC_MODEL"])
    want = {(units[k]["cond"], units[k]["sim"], units[k]["turn"]): k for k in ks}
    seqs = {}
    for domain in ("airline", "retail", "telecom"):
        conds = sorted({units[k]["cond"] for k in ks if units[k]["domain"] == domain})
        if not conds:
            continue
        for domain_, cond, task, sim, tel in bt.episodes(Path("data/simulations/pilot"), Path("data/jlens-telemetry/pilot"), [domain], conds):
            for line in tel.open(encoding="utf-8"):
                rec = json.loads(line)
                key = (cond, sim["id"], int(rec["turn_index"]))
                if key in want:
                    k = want[key]
                    seqs[k] = list(rec["input_ids"]) + list(rec["generated_ids"][:units[k]["d"]])
    for k in ks:
        r, u = rows[k], units[k]
        z = np.load(c0 / f"n_{k}.npz")
        role = z["tsrc_role"].sum(1)
        tot = role.sum(0)
        pos = z["tsrc_pos"].astype(np.float32).sum(0)
        codes = z["codes"]
        seq = seqs.get(k)
        m = r["m"]
        print(f"\n### k={k} {r['label']} {r['kind']} {r['domain']} task={str(r['task'])[:40]} c={r['c_tok']!r} g={r['g_tok']!r} m={m:.2f} "
              f"T={r['T']} attn-sum(full)={float(z['attn_dla'][FULL].sum()):.2f} mlp-sum={float(z['mlp_dla'].sum()):.2f}")
        print("  total source effect by role (sum over 8 full layers):",
              ", ".join(f"{ROLES[i]} {tot[i]:+.2f}" for i in np.argsort(-np.abs(tot))[:6]))
        print("  per layer [" + " ".join(f"L{l}" for l in FULL) + "] top role:",
              " ".join(f"{ROLES[int(np.argmax(np.abs(role[j])))][:6]}{role[j][int(np.argmax(np.abs(role[j])))]:+.1f}" for j in range(8)))
        if seq is None:
            continue
        order = np.argsort(-pos)
        print("  top +sources:")
        for p in order[:TOPN]:
            a, b = max(0, p - 8), min(len(seq), p + 4)
            ctx = tok.decode(seq[a:p]) + "[[" + tok.decode([seq[p]]) + "]]" + tok.decode(seq[p + 1:b])
            print(f"    {pos[p]:+.2f} {ROLES[codes[p]][:10]:10s} @{p}: {ctx!r}")
        print("  top -sources:")
        for p in np.argsort(pos)[:4]:
            a, b = max(0, p - 8), min(len(seq), p + 4)
            ctx = tok.decode(seq[a:p]) + "[[" + tok.decode([seq[p]]) + "]]" + tok.decode(seq[p + 1:b])
            print(f"    {pos[p]:+.2f} {ROLES[codes[p]][:10]:10s} @{p}: {ctx!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
