import json, re, ast
from collections import defaultdict
L=[json.loads(l) for l in open(r'C:\Users\user\jlens-work\jlens-causal-steering\results\vocab_trigger\gpu\sign\dose_triggered_results.jsonl',encoding='utf-8')]
T={r['record_id']:r for r in map(json.loads,open(r'C:\Users\user\jlens-work\insights-2026-11-17\tbl\turns.jsonl',encoding='utf-8'))}
E={e['sim']:e for e in map(json.loads,open(r'C:\Users\user\jlens-work\insights-2026-11-17\tbl\episodes.jsonl',encoding='utf-8'))}
by=defaultdict(dict)
for x in L: by[x['record_id']][x['condition']]=x
def c(s,n): s=re.sub(r'\s+',' ',s or ''); return s if len(s)<=n else s[:n]+'…'
def calls(x):
    tc=x['tool_calls']
    m=re.findall(r"'name': '([a-z_]+)'",str(tc or ''))+re.findall(r'"name": "([a-z_]+)"',str(tc or ''))
    return ','.join(m) or '-'
def kind(r):
    ws=[w for w in r['write_types'] if w['type']!='match']
    if not ws: return 'GOOD:'+','.join(w['name'] for w in r['write_types'])
    w=ws[0]; return 'transfer' if w['name']=='transfer_to_human_agents' else w['type']+':'+w['name']
order=sorted(by, key=lambda k:(by[k]['off@0.0']['logged_label'], int(by[k]['off@0.0']['task_id'])))
for rid in order:
    cs=by[rid]; o=cs['off@0.0']; r=T[rid]
    print(f"### task{o['task_id']} t{o['turn_index']} logged={o['logged_label']} kind={kind(r)} epR={E[r['sim']]['reward']}")
    print(f"   USER: {c(r['last_user'],200)}")
    for cond in ('off@0.0','trigger@0.8','trigger@-0.8','random@-0.8','random@0.8'):
        x=cs.get(cond)
        if not x: continue
        txt=re.sub(r'<tool_call>.*','',x['text'],flags=re.S)
        print(f"   [{cond:12s}] {x['label']:9s} call={calls(x):28s} | {c(txt,230)}")
    print()
