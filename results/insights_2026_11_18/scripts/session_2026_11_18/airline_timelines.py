import json, re, sys
from collections import defaultdict
sp=sys.argv[1]
TK={r['record_id']:r for r in map(json.loads,open(sp+r'\airline_topk.jsonl',encoding='utf-8'))}
T=[json.loads(l) for l in open(r'C:\Users\user\jlens-work\insights-2026-11-17\tbl\turns.jsonl',encoding='utf-8')]
E={e['sim']:e for e in map(json.loads,open(r'C:\Users\user\jlens-work\insights-2026-11-17\tbl\episodes.jsonl',encoding='utf-8'))}
def c(s,n): s=re.sub(r'\s+',' ',s or ''); return s if len(s)<=n else s[:n]+'…'
def tk(rec,key,n):
    t=TK[rec]['top'].get(key)
    return ','.join(x.strip() for x in t[:n]) if t else '-'
by=defaultdict(list)
for r in T: by[r['sim']].append(r)
mode=sys.argv[2]
sims=[s for s in by if s in E and (E[s]['reward']<1)==(mode=='fail')]
sims.sort(key=lambda s:(int(by[s][0]['task_id']),s))
for s in sims:
    R=sorted(by[s],key=lambda r:r['turn'])
    print(f"\n#### task {R[0]['task_id']} {s[-8:]} reward={E[s]['reward']} {R[0]['split'][:4]}")
    for r in R:
        lab={'bad_write':'BAD','good_write':'good','read':'read','no_call':'-'}[r['label']]
        calls=','.join(x['name'].replace('_reservation','').replace('get_','g:').replace('search_','s:') for x in r['calls'])
        u=c(r['last_user'],70) if r['last_is_user'] else '(tool)'
        print(f" t{r['turn']:<2} {lab:4} L16:{tk(r['record_id'],'initial_decision|L16|first',6)} || L31:{tk(r['record_id'],'initial_decision|L31|first',3)} || U:{u} -> {calls or c(re.sub(r'<.*?>','',r['gen']),45)}")
