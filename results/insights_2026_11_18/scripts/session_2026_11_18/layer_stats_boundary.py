import os, json, csv, re, sys
from collections import Counter, defaultdict
csv.field_size_limit(10**9)
root=r'C:\Users\user\jlens-drive-data\vast-backup'
d=sys.argv[1]
fp=os.path.join(root,d,'semantic_boundary_readouts.csv')
CJK=re.compile(r'[\u4e00-\u9fff]')
WORD=re.compile(r"^\s?[A-Za-z]{3,}$")
rows=defaultdict(dict)  # (call,boundary,pos) -> layer -> tokens
stats=defaultdict(lambda: Counter())
tops=defaultdict(Counter)  # (boundary,layer)->Counter top1..3
for row in csv.DictReader(open(fp,encoding='utf-8')):
    L=row['layer']; L='F' if L=='model_final' else int(L)
    toks=json.loads(row['top_token_pieces'])
    key=(row['call_id'],row['boundary'],row['position'])
    rows[key][L]=toks
    s=stats[L]
    s['n']+=1; s['word']+=sum(bool(WORD.match(t)) for t in toks); s['cjk']+=sum(bool(CJK.search(t)) for t in toks); s['tot']+=len(toks)
    for t in toks[:3]: tops[(row['boundary'],L)][t.strip().lower()]+=1
layers=sorted([l for l in stats if l!='F'])+['F']
# adjacent jaccard
jac=defaultdict(list)
for key,byL in rows.items():
    for a,b in zip(layers,layers[1:]):
        if a in byL and b in byL:
            A=set(byL[a]); B=set(byL[b]); jac[a].append(len(A&B)/len(A|B))
# jaccard to final
jf=defaultdict(list)
for key,byL in rows.items():
    if 'F' in byL:
        F=set(byL['F'])
        for l in layers:
            if l in byL and l!='F': jf[l].append(len(set(byL[l])&F)/10)
print(f"{d}: layer  word%  cjk%  jac(next)  overlap_w_final")
for l in layers:
    s=stats[l]
    j=sum(jac[l])/len(jac[l]) if jac[l] else float('nan'); o=sum(jf[l])/len(jf[l]) if jf[l] else float('nan')
    print(f"  L{l!s:>2}  {100*s['word']/s['tot']:5.1f}  {100*s['cjk']/s['tot']:5.1f}   {j:.2f}      {o:.2f}")
for bnd in ('observation','decision','tool','argument','update'):
    print(f"\n== {bnd}: most frequent top-3 tokens per layer")
    for l in layers:
        c=tops[(bnd,l)]
        if c: print(f"  L{l!s:>2}: "+', '.join(f"{t}({n})" for t,n in c.most_common(7)))
