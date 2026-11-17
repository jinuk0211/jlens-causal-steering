import json, sys
tasks = {str(t["id"]): t for t in json.load(open(sys.argv[1], encoding="utf-8"))}
for tid in sys.argv[2].split(","):
    t = tasks[tid]
    us = t.get("user_scenario", {})
    instr = us.get("instructions")
    print(f"===== task {tid}")
    print("instructions:", json.dumps(instr, ensure_ascii=False)[:1500])
    for a in t["evaluation_criteria"]["actions"]:
        print("  gold:", a["name"], json.dumps(a.get("arguments"), ensure_ascii=False)[:300])
