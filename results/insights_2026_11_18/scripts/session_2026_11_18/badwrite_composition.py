import json, re
from collections import Counter
T=[json.loads(l) for l in open(r'C:\Users\user\jlens-work\insights-2026-11-17\tbl\turns.jsonl',encoding='utf-8')]
E={e['sim']:e for e in map(json.loads,open(r'C:\Users\user\jlens-work\insights-2026-11-17\tbl\episodes.jsonl',encoding='utf-8'))}
def bt(r):
    w=[x for x in r['write_types'] if x['type']!='match'][0]
    return 'transfer' if w['name']=='transfer_to_human_agents' else w['type']
for sp in ('train','validation','evaluation'):
    B=[r for r in T if r['split']==sp and r['label']=='bad_write']
    print(sp, 'bad', len(B), Counter(bt(r) for r in B), ' fired:', Counter(bt(r) for r in B if r['fired']))
# refusal register in generated text
POL=re.compile(r"(follow the policy|policy strictly|according to the policy|cannot (be )?(cancel|process|modify)|doesn't meet|does not meet|I understand your (frustration|concern))",re.I)
for lab in ('bad_write','good_write','read','no_call'):
    R=[r for r in T if r['label']==lab]
    print(lab, 'gen has refusal register', sum(bool(POL.search(r['gen'])) for r in R),'/',len(R), ' fired among those', sum(r['fired'] for r in R if POL.search(r['gen'])))
B=[r for r in T if r['label']=='bad_write']
for k in ('transfer','unexpected_tool','wrong_args'):
    R=[r for r in B if bt(r)==k]
    print(k, 'refusal register', sum(bool(POL.search(r['gen'])) for r in R),'/',len(R))
