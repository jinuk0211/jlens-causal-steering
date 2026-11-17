import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print("top keys:", list(d.keys()) if isinstance(d, dict) else type(d))
sims = d["simulations"]
print("n sims", len(sims))
s = sims[0]
print("sim keys:", list(s.keys()))
ri = s.get("reward_info")
print(json.dumps(ri, ensure_ascii=False)[:2500])
print("termination:", s.get("termination_reason"))
msgs = s.get("messages", [])
print("n msgs", len(msgs), "msg keys", list(msgs[0].keys()) if msgs else None)
tasks = d.get("tasks", [])
if tasks:
    print("task keys", list(tasks[0].keys()))
    print("eval criteria", json.dumps(tasks[0].get("evaluation_criteria"), ensure_ascii=False)[:800])
