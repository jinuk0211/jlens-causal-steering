import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
for s in d["simulations"][:40]:
    rv = s.get("review")
    if rv and s["reward_info"]["reward"] < 1:
        print("task", s["task_id"], "reward", s["reward_info"]["reward"], s["reward_info"].get("reward_breakdown"), s["termination_reason"])
        print(json.dumps(rv, ensure_ascii=False)[:3000])
        print("user_only_review:", json.dumps(s.get("user_only_review"), ensure_ascii=False)[:600])
        print("auth_classification:", json.dumps(s.get("auth_classification"), ensure_ascii=False)[:600])
        break
