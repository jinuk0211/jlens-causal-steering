import os, json, csv, re, math, random
from collections import Counter, defaultdict
import numpy as np
from sklearn.metrics import roc_auc_score
csv.field_size_limit(10**9)
root=r'C:\Users\user\jlens-drive-data\vast-backup\toolalignbench'
tools=Counter()
bags=defaultdict(lambda: defaultdict(Counter))  # (segkind,edge)->layer->(trace,step,pos)->tokens ; simplified
items=defaultdict(list) # (segkind,edge,layer) -> list of (trace, label, tokens)
for row in csv.DictReader(open(os.path.join(root,'semantic_boundary_readouts.csv'),encoding='utf-8')):
    sk=row['segment_kind']; ed=row['edge']
    if sk=='tool-name' and ed=='start' and row['layer']=='0':
        tools[(row['scenario_type'], row['condition'].split('-')[0], row['segment'].split(': ')[-1])]+=1
    if (sk,ed) in (('assistant','start'),('tool-name','start'),('arguments','start'),('assistant','end'),('scratchpad','start')):
        toks=[t.strip().lower() for t in json.loads(row['top_tokens'])]
        items[(sk,ed,int(row['layer']))].append((row['trace_id'], row['scenario_type']=='wrongdoing', row['condition'].split('-')[0]=='boldly', toks))
print('tool calls by scenario x prompt x tool:')
for k,v in sorted(tools.items()): print('  ',k,v)
def nb_auc(data, target_idx):
    traces=sorted({d[0] for d in data}); random.Random(0).shuffle(traces)
    test=set(traces[:len(traces)//3])
    tr=[d for d in data if d[0] not in test]; te=[d for d in data if d[0] in test]
    if len({d[target_idx] for d in te})<2: return float('nan')
    cp=Counter(); cn=Counter(); npos=nneg=0
    for d in tr:
        if d[target_idx]: cp.update(set(d[3])); npos+=1
        else: cn.update(set(d[3])); nneg+=1
    V=set(cp)|set(cn)
    def s(toks): return sum(math.log((cp[t]+1)/(npos+2))-math.log((cn[t]+1)/(nneg+2)) for t in set(toks) if t in V)
    return roc_auc_score([d[target_idx] for d in te],[s(d[3]) for d in te])
print('\nheld-out (by trace) naive-Bayes AUC from J-lens top-10 bag: wrongdoing-vs-safe | bold-vs-tame prompt')
for sk,ed in (('assistant','start'),('tool-name','start'),('arguments','start'),('assistant','end')):
    print(f' {sk}/{ed}: '+'  '.join(f"L{L}:{nb_auc(items[(sk,ed,L)],1):.2f}|{nb_auc(items[(sk,ed,L)],2):.2f}" for L in (0,4,8,12,16,20,24,28,30,31)))
print('\nmost distinctive tokens (wrongdoing vs safe) at assistant/start, log-odds, min count 15:')
for L in (12,16,20,24,28,31):
    D=items[('assistant','start',L)]; cp=Counter(); cn=Counter(); npos=sum(d[1] for d in D); nneg=len(D)-npos
    for d in D: (cp if d[1] else cn).update(set(d[3]))
    lo={t: math.log((cp[t]+1)/(npos+2))-math.log((cn[t]+1)/(nneg+2)) for t in set(cp)|set(cn) if cp[t]+cn[t]>=15}
    top=sorted(lo,key=lo.get,reverse=True)[:10]; bot=sorted(lo,key=lo.get)[:8]
    print(f"  L{L} wrongdoing+: "+', '.join(f"{t}({cp[t]}/{cn[t]})" for t in top)); print(f"       safe+: "+', '.join(f"{t}({cp[t]}/{cn[t]})" for t in bot))
