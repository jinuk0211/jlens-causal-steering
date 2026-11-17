import json, sys, glob, os
root, task, conds = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
for cond in conds:
    fs = glob.glob(os.path.join(root, "s*", "simulations", "vt-heldout", cond, f"task_{task}", "results.json"))
    for f in fs:
        d = json.load(open(f, encoding="utf-8"))
        for s in d["simulations"]:
            print(f"########## task {task} [{cond}] reward={s['reward_info']['reward']} term={s['termination_reason']}")
            for m in s["messages"]:
                tc = [(c["name"], json.dumps(c.get("arguments"), ensure_ascii=False)[:160]) for c in (m.get("tool_calls") or [])]
                body = (m.get("content") or "").replace("\n", " ")
                if m["role"] == "tool":
                    body = body[:120]
                else:
                    body = body[:int(sys.argv[4]) if len(sys.argv) > 4 else 400]
                print(f"  [{m['turn_idx']}] {m['role']:9s} {tc if tc else ''} {body}")
