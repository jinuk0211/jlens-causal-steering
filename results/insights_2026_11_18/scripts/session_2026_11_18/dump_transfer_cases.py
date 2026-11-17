import json, re
from collections import defaultdict, Counter
TASKS={str(t['id']):t for t in json.load(open(r'C:\Users\user\jlens-work\tau2-bench\data\tau2\domains\airline\tasks.json',encoding='utf-8'))}
T=[json.loads(l) for l in open(r'C:\Users\user\jlens-work\insights-2026-11-17\tbl\turns.jsonl',encoding='utf-8')]
E={e['sim']:e for e in map(json.loads,open(r'C:\Users\user\jlens-work\insights-2026-11-17\tbl\episodes.jsonl',encoding='utf-8'))}
def c(s,n): s=re.sub(r'\s+',' ',s or ''); return s if len(s)<=n else s[:n]+'…'
rows=[r for r in T if r['label']=='bad_write' and any(w['name']=='transfer_to_human_agents' and w['type']!='match' for w in r['write_types'])]
by=defaultdict(list)
for r in rows: by[r['task_id']].append(r)
for tid in sorted(by,key=int):
    t=TASKS[tid]; ins=t['user_scenario']['instructions']
    gw=[a['name'] for a in t['evaluation_criteria']['actions'] if a['name'] not in ('get_user_details','get_reservation_details','search_direct_flight','search_onestop_flight','list_all_airports','calculate','get_flight_status')]
    print(f"## task{tid} n={len(by[tid])} gold_writes={gw or 'NONE'}")
    print("   REASON:", c(ins['reason_for_call'],200), "| INSTR:", c(ins.get('task_instructions'),200))
    for r in by[tid]:
        e=E[r['sim']]
        print(f"   - idx{r['idx']} t{r['turn']} R={e['reward']} fired={int(r['fired'])} | USER: {c(r['last_user'],170)} | GEN: {c(re.sub(r'<tool_call>.*','',r['gen'],flags=re.S),170)}")
