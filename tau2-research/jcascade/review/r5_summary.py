import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
P = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "out/review/patch_p1.json"


def main():
    R = json.loads(P.read_text(encoding="utf-8"))
    bad = [r for r in R if r["y"] == 1]
    good = [r for r in R if r["y"] == 0]
    md = [f"# R5: where the P1 effect enters (rows where C0 transfers and P1 does not: bad {len(bad)}, good {len(good)})", "",
          "delta = log p(P1 answer) - log p(C0 answer), teacher-forced; restoration = (delta_patch - delta_clean) / (delta_donor - delta_clean)", "",
          f"- mean delta: clean {np.mean([r['delta_clean'] for r in R]):.1f}, P1 donor {np.mean([r['delta_donor'] for r in R]):.1f}, "
          f"same-length null donor {np.mean([r['delta_null_donor'] for r in R]):.1f}",
          f"- null donor shift as a share of the P1 shift: "
          f"{np.mean([(r['delta_null_donor'] - r['delta_clean']) / (r['delta_donor'] - r['delta_clean']) for r in R]):.2f}", ""]
    comps = ["resid_all", "resid_last", "attn_all", "mlp_all", "null_resid_all"]
    md += ["## single-layer patch at the header positions (mean restoration; bad / good)", "",
           "| layer | " + " | ".join(comps) + " |", "|---|" + "---|" * len(comps)]
    for l in range(32):
        cells = []
        for c in comps:
            b = np.mean([r["patch"][c][l] for r in bad if r["patch"][c][l] is not None]) if bad else float("nan")
            g = np.mean([r["patch"][c][l] for r in good if r["patch"][c][l] is not None]) if good else float("nan")
            cells.append(f"{b:.2f} / {g:.2f}")
        md.append(f"| L{l} | " + " | ".join(cells) + " |")
    md += ["", "## cumulative header patch (all header positions, layers L0..31 from the given start)", "",
           "| from | bad | good |", "|---|---|---|"]
    for l0 in (0, 8, 12, 16, 20, 24):
        k = f"resid_all_from_L{l0}"
        if k in R[0]["patch"]:
            md.append(f"| L{l0} | {np.mean([r['patch'][k] for r in bad]):.2f} | {np.mean([r['patch'][k] for r in good]):.2f} |")
    best = {}
    for c in comps[:4]:
        diff = [np.mean([r["patch"][c][l] for r in bad]) - np.mean([r["patch"][c][l] for r in good]) for l in range(32)]
        l = int(np.argmax(diff))
        best[c] = (l, diff[l])
    md += ["", "largest bad-minus-good restoration gap per component: " + ", ".join(f"{c} L{l} {d:+.2f}" for c, (l, d) in best.items())]
    out = P.with_name("r5_summary.md")
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
