import json, sys
from collections import defaultdict
turns_path, results_path = sys.argv[1:3]
rows = [json.loads(l) for l in open(turns_path, encoding="utf-8")]
by_sim = defaultdict(list)
for r in rows:
    by_sim[r["sim"]].append(r)
d = json.load(open(results_path, encoding="utf-8"))
for s in d["simulations"][:4]:
    key = f"baseline-{s['task_id']}-{s['id']}"
    T = sorted(by_sim.get(key, []), key=lambda r: r["turn"])
    print("====", key, "tele turns", len(T), [t["turn"] for t in T][:30])
    for m in s["messages"][:40]:
        tc = [c.get("name") for c in (m.get("tool_calls") or [])]
        print(f"   msg turn_idx={m['turn_idx']} role={m['role']:9s} calls={tc} content={(m.get('content') or '')[:70]!r}")
    for t in T[:12]:
        print(f"   TELE turn={t['turn']} label={t['label']} calls={[c['name'] for c in t['calls']]} gen={t['gen'][:70]!r}")
