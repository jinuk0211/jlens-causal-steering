"""Turn-level replay: what kind of bad write did +0.8 remove, and were those harmful?"""
import json, sys
from collections import Counter, defaultdict

dose_path, turns_path, eps_path = sys.argv[1:4]
rows = {r["record_id"]: r for r in (json.loads(l) for l in open(turns_path, encoding="utf-8"))}
eps = {e["sim"]: e for e in (json.loads(l) for l in open(eps_path, encoding="utf-8"))}
res = [json.loads(l) for l in open(dose_path, encoding="utf-8")]


def kind(r):
    if r["label"] == "good_write":
        return "good"
    if r["label"] != "bad_write":
        return r["label"]
    b = [w for w in r["write_types"] if w["type"] != "match"][0]
    if b["type"] == "unexpected_tool" and b["name"] == "transfer_to_human_agents":
        return "bad_transfer"
    return f"bad_{b['type']}"


conds = sorted({x["condition"] for x in res})
print("conditions:", conds)
by = defaultdict(dict)
for x in res:
    by[x["record_id"]][x["condition"]] = x

print("\n== the 31 triggered held-out turns by kind (logged) ==")
K = Counter()
for rid in by:
    r = rows[rid]
    K[(kind(r), eps[r["sim"]]["reward"])] += 1
for k, v in sorted(K.items()):
    print(f"  {k}: {v}")

print("\n== outcome per condition, split by logged kind (bad/no_call/good counts) ==")
for cond in conds:
    agg = defaultdict(Counter)
    for rid, cs in by.items():
        if cond not in cs:
            continue
        r = rows[rid]
        agg[kind(r)][cs[cond]["label"]] += 1
    s = "  ".join(f"{k}: " + "/".join(str(agg[k][l]) for l in ("bad_write", "no_call", "good_write", "read")) for k in sorted(agg))
    print(f"  {cond:14s} {s}")

print("\n== +0.8 changes (logged-bad turns), with episode reward and generated text ==")
plus = [c for c in conds if c.startswith("trigger@0.8")]
pc = plus[0] if plus else None
for rid, cs in by.items():
    r = rows[rid]
    if pc not in cs or "off@0.0" not in cs:
        continue
    off, st = cs["off@0.0"], cs[pc]
    if off["label"] != st["label"]:
        print(f"- task {r['task_id']} t{r['turn']} [{kind(r)}] ep_reward={eps[r['sim']]['reward']} gold_writes={r['n_gold_writes']}: off={off['label']}({[c['name'] for c in off['tool_calls']]}) -> +0.8={st['label']}({[c['name'] for c in st['tool_calls']]}) asks={st.get('asks_question')}")
        print(f"     +0.8 text: {st['text'][:260]!r}")
