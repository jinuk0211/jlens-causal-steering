import json
from collections import defaultdict
T=[json.loads(l) for l in open(r'C:\Users\user\jlens-work\insights-2026-11-17\tbl\turns.jsonl',encoding='utf-8')]
g=defaultdict(lambda:{'good':[],'bad':[]})
for r in T:
    if r['label']=='good_write':
        for w in r['write_types']: g[(r['task_id'],w['name'])]['good'].append(r); break
    elif r['label']=='bad_write':
        ws=[w for w in r['write_types'] if w['type']!='match']
        if ws and ws[0]['name']!='transfer_to_human_agents': g[(r['task_id'],ws[0]['name'])]['bad'].append(r)
n=0; higher=0; ties=0
for k,v in sorted(g.items(),key=lambda kv:int(kv[0][0])):
    if v['good'] and v['bad']:
        gs=[round(r['trig_score'],2) for r in v['good']]; bs=[round(r['trig_score'],2) for r in v['bad']]
        print(f"task{k[0]:>3} {k[1]:28s} good={gs}  bad={bs}")
        for b in bs:
            for s in gs:
                n+=1; higher+= b>s; ties+= b==s
print('matched-pair AUC (bad>good within same task+tool):', round((higher+0.5*ties)/n,3), 'pairs', n)
