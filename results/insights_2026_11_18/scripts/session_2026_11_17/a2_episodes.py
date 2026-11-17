"""Join baseline episodes (reward, reviewer-localised errors) with the telemetry turn table."""
import json, sys
from collections import Counter, defaultdict
from pathlib import Path

turns_path, sim_root, out_path = sys.argv[1:4]
rows = [json.loads(l) for l in open(turns_path, encoding="utf-8")]
by_sim = defaultdict(list)
for r in rows:
    by_sim[r["sim"]].append(r)
for v in by_sim.values():
    v.sort(key=lambda r: r["turn"])

eps = []
for split in ("train", "validation", "evaluation"):
    d = json.load(open(Path(sim_root) / split / "baseline" / "results_reviewed.json", encoding="utf-8"))
    for s in d["simulations"]:
        key = f"baseline-{s['task_id']}-{s['id']}"
        T = by_sim.get(key)
        if T is None:
            continue
        msgs = s["messages"]
        asst_turnidx = [m["turn_idx"] for m in msgs if m["role"] == "assistant"]
        ri = s["reward_info"]
        rv = s.get("review") or {}
        errs = []
        for e in rv.get("errors") or []:
            ti = e.get("turn_idx")
            # map message turn_idx -> agent-turn ordinal (telemetry turn_index)
            agent_turn = None
            if ti is not None:
                prior = [k for k, t in enumerate(asst_turnidx) if t is not None and t <= ti]
                # message 0 is the fixed greeting, so telemetry turn k == assistant message k+1
                agent_turn = (prior[-1] - 1) if prior and prior[-1] >= 1 else None
                exact = ti in asst_turnidx
            else:
                exact = False
            errs.append({"source": e.get("source"), "tags": e.get("error_tags"), "severity": e.get("severity"),
                         "turn_idx": ti, "agent_turn": agent_turn, "exact_agent_msg": exact,
                         "reasoning": (e.get("reasoning") or "")[:400]})
        eps.append({
            "split": split, "sim": key, "task_id": str(s["task_id"]), "reward": ri["reward"],
            "breakdown": ri.get("reward_breakdown"), "termination": s["termination_reason"],
            "n_asst_msgs": len(asst_turnidx), "n_tele_turns": len(T),
            "agent_error": rv.get("agent_error"), "user_error": rv.get("user_error"),
            "critical_user_error": rv.get("critical_user_error"), "errors": errs,
            "labels": [t["label"] for t in T], "fired": [t["fired"] for t in T],
            "write_types": [t["write_types"] for t in T], "n_gold_writes": T[0]["n_gold_writes"],
        })

with open(out_path, "w", encoding="utf-8") as f:
    for e in eps:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

print("episodes joined:", len(eps), "of telemetry sims", len(by_sim))
print("turn-count agreement (asst msgs - 1 == telemetry turns):", sum(e["n_asst_msgs"] - 1 == e["n_tele_turns"] for e in eps), "/", len(eps))
print("  mismatches:", [(e["task_id"], e["n_asst_msgs"] - 1, e["n_tele_turns"]) for e in eps if e["n_asst_msgs"] - 1 != e["n_tele_turns"]][:20])
print("pass rate:", sum(e["reward"] == 1 for e in eps), "/", len(eps))

def has(e, pred):
    return any(pred(w) for ws in e["write_types"] for w in ws)

groups = {
    "has unexpected transfer": lambda e: has(e, lambda w: w["type"] == "unexpected_tool" and w["name"] == "transfer_to_human_agents"),
    "has unexpected other write": lambda e: has(e, lambda w: w["type"] == "unexpected_tool" and w["name"] != "transfer_to_human_agents"),
    "has wrong-args write": lambda e: has(e, lambda w: w["type"] == "wrong_args"),
    "no bad write": lambda e: "bad_write" not in e["labels"],
}
print("\n== reward by bad-write content of the episode ==")
for name, g in groups.items():
    E = [e for e in eps if g(e)]
    print(f"  {name:28s} n={len(E):3d} pass={sum(e['reward']==1 for e in E)}  ({sum(e['reward']==1 for e in E)/max(1,len(E)):.2f})")
print("\n== transfer episodes: gold has 0 writes (refusal task) vs >0 ==")
for zero in (True, False):
    E = [e for e in eps if groups["has unexpected transfer"](e) and ((e["n_gold_writes"] == 0) == zero)]
    print(f"  gold writes {'==0' if zero else '>0'}: n={len(E)} pass={sum(e['reward']==1 for e in E)}  DB ok={sum((e['breakdown'] or {}).get('DB',0)==1 for e in E)}")

print("\n== failures: reviewer verdicts ==")
F = [e for e in eps if e["reward"] < 1]
print("failed episodes:", len(F))
print("  agent_error:", sum(bool(e["agent_error"]) for e in F), " user_error:", sum(bool(e["user_error"]) for e in F), " critical_user_error:", sum(bool(e["critical_user_error"]) for e in F))
tags = Counter()
for e in F:
    for er in e["errors"]:
        if er["source"] == "agent" and er["severity"] == "critical":
            for t in er["tags"] or ["(none)"]:
                tags[t] += 1
print("  critical agent error tags:", tags.most_common())

print("\n== first critical agent error in failed episodes: what kind of turn, did the L16 trigger fire? ==")
kind = Counter()
fired_at = Counter()
fired_before = Counter()
examples = []
for e in F:
    crit = [er for er in e["errors"] if er["source"] == "agent" and er["severity"] == "critical" and er["agent_turn"] is not None]
    if not crit:
        kind["(no critical agent error localised)"] += 1
        continue
    er = min(crit, key=lambda x: x["agent_turn"])
    t = er["agent_turn"]
    if t >= len(e["labels"]):
        kind["(turn out of range)"] += 1
        continue
    lab = e["labels"][t]
    wt = [w["type"] + ":" + w["name"] for w in e["write_types"][t]]
    k = lab if lab not in ("bad_write", "good_write") else f"{lab} {wt}"
    kind[lab] += 1
    fired_at[lab] += int(e["fired"][t])
    fired_before[lab] += int(any(e["fired"][: t + 1]))
    examples.append((e["task_id"], t, lab, wt, e["fired"][t], er["tags"]))
for k, v in kind.most_common():
    print(f"  {k:40s} {v:3d}   trigger fired AT that turn {fired_at[k]}   fired at/before {fired_before[k]}")
print("\nexamples (task, agent_turn, label, writes, fired, tags):")
for x in examples[:60]:
    print("  ", x)
