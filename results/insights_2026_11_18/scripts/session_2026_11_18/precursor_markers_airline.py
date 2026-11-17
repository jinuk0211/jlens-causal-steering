import json, re, sys
from collections import defaultdict
sp=sys.argv[1]
TK={r['record_id']:r for r in map(json.loads,open(sp+r'\airline_topk.jsonl',encoding='utf-8'))}
T=[json.loads(l) for l in open(r'C:\Users\user\jlens-work\insights-2026-11-17\tbl\turns.jsonl',encoding='utf-8')]
E={e['sim']:e for e in map(json.loads,open(r'C:\Users\user\jlens-work\insights-2026-11-17\tbl\episodes.jsonl',encoding='utf-8'))}
MARK={'refuse':re.compile(r'^(unfortunately|sorry|apolog\w*|cannot|unable|抱歉|遗憾|无法\w*|对不起)$',re.I),
      'doubt':re.compile(r'^(wait|hmm|interesting\w*|actually|however|但是)$',re.I),
      'ask':re.compile(r'^(询问|问你|问询|问|问一下|请问|ask\w*|confirm\w*|确认)$',re.I),
      'success':re.compile(r'^(congratulations|successfully|成功)$',re.I),
      'eot':re.compile(r'^<\|endoftext\|>$')}
def has(rec,key,k,n=10):
    t=TK[rec]['top'].get(key) or []
    return any(MARK[k].match(x.strip()) for x in t[:n])
def bt(r):
    w=[x for x in r['write_types'] if x['type']!='match']
    return None if not w else ('transfer' if w[0]['name']=='transfer_to_human_agents' else 'harm')
by=defaultdict(list)
for r in T:
    if r['sim'] in E: by[r['sim']].append(r)
for L in ('L16','L31'):
    key=f'initial_decision|{L}|first'
    print(f'== {L} decision point: rate of marker in top-10')
    groups={'harmful-write turn':[], '1-2 turns before harmful':[], 'good-write turn':[], '1-2 turns before good':[], 'other turns, failed eps':[], 'other turns, passed eps':[]}
    for s,R in by.items():
        R=sorted(R,key=lambda r:r['turn'])
        harm=[i for i,r in enumerate(R) if r['label']=='bad_write' and bt(r)=='harm']
        good=[i for i,r in enumerate(R) if r['label']=='good_write']
        pre_h={j for i in harm for j in (i-1,i-2) if j>=0}-set(harm)
        pre_g={j for i in good for j in (i-1,i-2) if j>=0}-set(good)-set(harm)
        for i,r in enumerate(R):
            if i in harm: g='harmful-write turn'
            elif i in pre_h: g='1-2 turns before harmful'
            elif i in good: g='good-write turn'
            elif i in pre_g: g='1-2 turns before good'
            else: g='other turns, failed eps' if E[s]['reward']<1 else 'other turns, passed eps'
            groups[g].append(r['record_id'])
    for g,ids in groups.items():
        print(f'  {g:26s} n={len(ids):4d} '+'  '.join(f"{k}={sum(has(x,key,k) for x in ids)/max(len(ids),1):.2f}" for k in MARK))
