"""AM leaking rows re-scored with the forward check (ab_strict.am_leak_forward), rate design: per arm, the share of rows that
leak and the share with quality kept, over the rows whose base row exists. usage: python am_rescore.py DIR TAG [TAG...]"""
import sys
from collections import Counter, defaultdict
sys.path.insert(0, ".")
import ab_strict as S
d, tags = sys.argv[1], sys.argv[2:]
for tag in tags:
    rows = [r for r in S.rows_of("am", tag, d) if r.get("scenario") == "leaking"]
    base = {(r["uid"], r["seed"]): r for r in rows if r["config"] == "base"}
    by = defaultdict(Counter)
    for r in rows:
        b = base.get((r["uid"], r["seed"]))
        if b is None:
            continue
        c = by[r["config"]]
        t = r.get("text") or ""
        q = S.am_quality(r, b)
        c["n"] += 1
        c["leak"] += S.am_leak_forward(t)
        c["q"] += q
        c["marker"] += r["status"] == "harmful"
        bl = S.am_leak_forward(b.get("text") or "")
        if bl:
            c["nb"] += 1
            c["stop"] += (not S.am_leak_forward(t)) and q
        else:
            c["nc"] += 1
            c["new"] += S.am_leak_forward(t)
    print(f"== {d} {tag} (leaking rows)")
    for cfg, c in sorted(by.items()):
        print(f"  {cfg:20s} n={c['n']:3d} leak={c['leak'] / c['n']:5.0%} quality={c['q'] / c['n']:5.0%} marker={c['marker'] / c['n']:5.0%} | base-leak rows {c['nb']:3d}: no leak and quality kept {S.pct(c['stop'], c['nb']):>4s} | base-clean rows {c['nc']:3d}: new leak {S.pct(c['new'], c['nc']):>4s}")
