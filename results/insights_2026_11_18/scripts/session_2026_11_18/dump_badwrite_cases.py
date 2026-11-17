import json, glob, os, sys, re
from collections import defaultdict
ROOT=r'C:\Users\user\jlens-work\vocab-trigger-bundle\jlens-telemetry\failure-steering'
TASKS={str(t['id']):t for t in json.load(open(r'C:\Users\user\jlens-work\tau2-bench\data\tau2\domains\airline\tasks.json',encoding='utf-8'))}
T=[json.loads(l) for l in open(r'C:\Users\user\jlens-work\insights-2026-11-17\tbl\turns.jsonl',encoding='utf-8')]
E={e['sim']:e for e in map(json.loads,open(r'C:\Users\user\jlens-work\insights-2026-11-17\tbl\episodes.jsonl',encoding='utf-8'))}
want={r['record_id'] for r in T if r['label']=='bad_write'}
raw={}
for p in glob.glob(os.path.join(ROOT,'*','*.jsonl')):
    for line in open(p,encoding='utf-8'):
        rec=json.loads(line)
        if rec['record_id'] in want:
            raw[rec['record_id']]=rec['rendered_context']
def msgs(ctx):
    out=[]
    for seg in ctx.split('<|im_start|>')[1:]:
        role,_,body=seg.partition('\n'); body=body.replace('<|im_end|>','').strip()
        if role=='user' and body.startswith('<tool_response>'): role='tool'
        out.append((role,body))
    return out
def c(s,n): s=re.sub(r'\s+',' ',s); return s if len(s)<=n else s[:n]+'…'
WRITE={'book_reservation','cancel_reservation','update_reservation_flights','update_reservation_baggages','update_reservation_passengers','send_certificate','transfer_to_human_agents'}
def btype(r):
    w=[x for x in r['write_types'] if x['type']!='match'][0]
    return 'transfer' if w['name']=='transfer_to_human_agents' else w['type']
mode=sys.argv[1]
rows=[r for r in T if r['label']=='bad_write' and ((btype(r)=='transfer')==(mode=='transfer'))]
rows.sort(key=lambda r:(int(r['task_id']),r['sim'],r['turn']))
for r in rows:
    t=TASKS[r['task_id']]; ins=t['user_scenario']['instructions']; e=E[r['sim']]
    print(f"### idx{r['idx']} task{r['task_id']} {r['split'][:4]} turn{r['turn']} ep_reward={e['reward']} fired={r['fired']} trig={r['trig_score']:.2f} type={btype(r)}")
    print("  REASON:", c(ins['reason_for_call'],260))
    print("  INSTR:", c(ins.get('task_instructions') or '',360))
    gw=[a for a in t['evaluation_criteria']['actions'] if a['name'] in WRITE]
    print("  GOLD:", c('; '.join(a['name']+json.dumps(a['arguments'],ensure_ascii=False) for a in gw) or 'NONE',420))
    print("  MADE:", c('; '.join(x['name']+json.dumps(x['arguments'],ensure_ascii=False) for x in r['calls']),420))
    m=[x for x in msgs(raw[r['record_id']])[:-1] if x[0]!='system']
    tail=m[-(4 if mode!='transfer' else 2):]
    for role,b in tail:
        print(f"  [{role}] {c(b, 330 if role!='tool' else 220)}")
    print()
