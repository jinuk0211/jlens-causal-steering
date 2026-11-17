import json, glob, os
BASE=r'C:\Users\user\jlens-work\vt-episodes'
TASKS={str(t['id']):t for t in json.load(open(r'C:\Users\user\jlens-work\tau2-bench\data\tau2\domains\airline\tasks.json',encoding='utf-8'))}
W={'book_reservation','cancel_reservation','update_reservation_flights','update_reservation_baggages','update_reservation_passengers','send_certificate','transfer_to_human_agents'}
for tid in ('32','16'):
    print('GOLD', tid, [ (a['name'], a['arguments']) for a in TASKS[tid]['evaluation_criteria']['actions'] if a['name'] in W])
    for cond in ('detect','jlens','caa','random'):
        ps=glob.glob(os.path.join(BASE,'*','jlens-telemetry','vt-heldout',cond,f'{tid}-*.jsonl'))
        if not ps: continue
        p=sorted(ps,key=os.path.getmtime)[-1]
        for line in open(p,encoding='utf-8'):
            x=json.loads(line)
            for t in x.get('tool_calls') or []:
                if t.get('name') in W: print('  ',cond,'t',x['turn_index'],t['name'],json.dumps(t.get('arguments'),ensure_ascii=False)[:260])
