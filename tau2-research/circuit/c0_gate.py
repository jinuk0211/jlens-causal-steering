"""C-LOOP C0 validity gate (PLAN.md C0): from out/c0/units.json (C0a) and out/c0/prune.json (C0b).
(1) mean |m_lin - m| < 0.3; (2) source DLA vs head DLA relative error < 2 % (max over full-attention layers, per unit; reported
as median and 95th percentile); (3) N90 exists (<= 65,536 nodes) for >= 80 % of units and the random set's median f <= 0.5.
Necessity is descriptive. CPU only. Prints a markdown report and writes out/c0/gate.md."""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

C0 = Path("/home/project-b/LJW/tau2-steer/probe/circuit/out/c0")


def q(x, p):
    return float(np.percentile(x, p)) if len(x) else float("nan")


def main():
    rows = json.loads((C0 / "units.json").read_text(encoding="utf-8"))
    pr = json.loads((C0 / "prune.json").read_text(encoding="utf-8"))
    lin = np.array([abs(r["m_lin"] - r["m"]) for r in rows])
    src = np.array([r["chk_src_vs_head"] for r in rows])
    head = np.array([r["chk_head_vs_attn"] for r in rows])
    ok1 = lin.mean() < 0.3
    ok2 = q(src, 95) < 0.02
    have = [p for p in pr if p.get("N90") is not None]
    frac = len(have) / max(1, len(pr))
    frand = np.array([p["f_rand"] for p in have])
    f90 = np.array([p["f90"] for p in have])
    nec = np.array([p["nec90"] for p in have])
    necr = np.array([p["nec_rand"] for p in have])
    n90 = np.array([p["N90"] for p in have])
    ok3 = frac >= 0.8 and np.median(frand) <= 0.5
    skipped = sum(1 for p in pr if not p["grid"])
    md = ["# C0 validity gate", "",
          f"- units: C0a {len(rows)}, C0b {len(pr)} (skipped |m - m0| < 0.5: {skipped})",
          f"- (1) |m_lin - m|: mean {lin.mean():.3f}, p95 {q(lin, 95):.3f}, max {lin.max():.3f} -> {'PASS' if ok1 else 'FAIL'}",
          f"- (2) source-vs-head DLA L1 relative error: median {np.median(src):.4f}, p95 {q(src, 95):.4f}, max {src.max():.4f}; "
          f"head-vs-attention |diff| p95 {q(head, 95):.3f} -> {'PASS' if ok2 else 'FAIL'}",
          f"- (3) N90 found for {len(have)}/{len(pr)} = {frac:.0%}; N90 median {np.median(n90):.0f} (p10 {q(n90, 10):.0f}, p90 {q(n90, 90):.0f}) "
          f"of 295,808 nodes; f at N90 median {np.median(f90):.2f}; random same-size set f median {np.median(frand):.3f} (p90 {q(frand, 90):.3f}) "
          f"-> {'PASS' if ok3 else 'FAIL'}",
          f"- necessity (descriptive): ablating the N90 set removes median {np.median(nec):.2f} of (m - m0); the random set {np.median(necr):.3f}",
          ""]
    by = defaultdict(list)
    for p in have:
        by[(p["label"], p["ptype"])].append(p)
    md += ["| label | ptype | n | N90 median | N90 p90 | f_rand median | nec median | heads in S median |", "|---|---|---|---|---|---|---|---|"]
    for (lab, pt), ps in sorted(by.items()):
        md.append(f"| {lab} | {pt} | {len(ps)} | {np.median([p['N90'] for p in ps]):.0f} | {q([p['N90'] for p in ps], 90):.0f} | "
                  f"{np.median([p['f_rand'] for p in ps]):.3f} | {np.median([p['nec90'] for p in ps]):.2f} | "
                  f"{np.median([p['n_heads'] for p in ps]):.0f} |")
    lay = np.zeros(32)
    for p in have:
        lay += np.array(p["layer_neurons"]) / max(1, sum(p["layer_neurons"]))
    lay /= max(1, len(have))
    md += ["", "- mean share of N90 neurons per layer: " + " ".join(f"L{i}:{v:.2f}" for i, v in enumerate(lay) if v >= 0.02)]
    md += ["", f"## Verdict: {'PASS' if ok1 and ok2 and ok3 else 'FAIL'} (1 {ok1}, 2 {ok2}, 3 {ok3})"]
    (C0 / "gate.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
