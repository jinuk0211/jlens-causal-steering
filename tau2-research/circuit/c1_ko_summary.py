"""C-LOOP C1 knockout summary (PLAN.md C1-T criteria): per group, bad / good flip rates and mean dm, the random control, and the same
split by domain. Usage: c1_ko_summary.py <knockout.json>. CPU only."""
import json
import sys
from collections import defaultdict

import numpy as np


def main():
    rows = json.load(open(sys.argv[1], encoding="utf-8"))
    groups = sorted({g for r in rows for g in r["groups"]})
    print(f"{len(rows)} units: " + ", ".join(f"{lab} {sum(r['label'] == lab for r in rows)}" for lab in ("bad", "good")))
    print(f"{'group':24s} {'n':>4s} {'flip bad':>9s} {'flip good':>9s} {'dm bad':>8s} {'dm good':>8s} {'rand dm':>8s} "
          f"{'rand flip':>9s}  verdict")
    for g in groups:
        st = defaultdict(list)
        for r in rows:
            e = r["groups"].get(g)
            if e is None:
                continue
            st[r["label"]].append(e)
        fb = np.mean([e["flip"] for e in st["bad"]]) if st["bad"] else float("nan")
        fg = np.mean([e["flip"] for e in st["good"]]) if st["good"] else float("nan")
        db = np.mean([e["dm"] for e in st["bad"]]) if st["bad"] else float("nan")
        dg = np.mean([e["dm"] for e in st["good"]]) if st["good"] else float("nan")
        rd = [x for lab in ("bad", "good") for e in st[lab] for x in e.get("dm_rand", [])]
        rflip = [x for lab in ("bad", "good") for r in rows if r["label"] == lab and g in r["groups"]
                 for x in r["groups"][g].get("dm_rand", []) if r["m_base"] + x < 0]
        n_r = sum(len(r["groups"][g].get("dm_rand", [])) for r in rows if g in r["groups"])
        rf = len(rflip) / n_r if n_r else float("nan")
        causal = fb >= 0.30 and (np.isnan(rf) or rf <= 0.05)
        specific = causal and (np.isnan(fg) or fb - fg >= 0.30)
        n = len(st["bad"]) + len(st["good"])
        print(f"{g:24s} {n:4d} {fb:9.2f} {fg:9.2f} {db:8.2f} {dg:8.2f} {np.mean(rd) if rd else float('nan'):8.2f} {rf:9.2f}  "
              f"{'causal' if causal else '-'}{' +bad-specific' if specific else ''}")
    print("\nby domain (flip bad / flip good, n):")
    for g in groups:
        parts = []
        for dom in ("airline", "retail", "telecom"):
            b = [r["groups"][g]["flip"] for r in rows if r["domain"] == dom and r["label"] == "bad" and g in r["groups"]]
            o = [r["groups"][g]["flip"] for r in rows if r["domain"] == dom and r["label"] == "good" and g in r["groups"]]
            parts.append(f"{dom} {np.mean(b) if b else float('nan'):.2f}/{np.mean(o) if o else float('nan'):.2f} ({len(b)}/{len(o)})")
        print(f"  {g:24s} " + "  ".join(parts))
    print("\nper unit (dm by group; F = flip):")
    for r in rows:
        print(f"  k={r['k']} {r['label']:4s} {r['domain']:7s} {str(r['task'])[:12]:12s} c={r['c_tok']!r} g={r['g_tok']!r} m={r['m_base']:.2f} | "
              + " ".join(f"{g[:10]}{e['dm']:+.1f}{'F' if e['flip'] else ''}" for g, e in r["groups"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
