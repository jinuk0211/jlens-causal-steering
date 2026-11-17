import os, json, gzip, re, sys, random
from collections import Counter, defaultdict
import numpy as np
root=r'C:\Users\user\jlens-drive-data\vast-backup'
sets={'gptoss':['gptoss20airline/0011-0050-reasoning-low-ctx32k-out4k-seed300/full','48577418/tail20/full','gpt-oss-20b-airline20/tail20/full'],
      'qwen4retail':['qwen4retail'], 'qwen08retail':['qwen0.5retail']}
name=sys.argv[1]; maxcalls=int(sys.argv[2])
CJK=re.compile(r'[\u4e00-\u9fff]'); WORD=re.compile(r"^\s?[A-Za-z]{3,}$")
calls=[]
seen=set()
for p in sets[name]:
    base=os.path.join(root,p)
    for d in sorted(os.listdir(base)):
        fp=os.path.join(base,d)
        if d.startswith('task_') and os.path.exists(os.path.join(fp,'slice.bin')) and d not in seen:
            seen.add(d); calls.append(fp)
random.Random(0).shuffle(calls); calls=calls[:maxcalls]
agg=defaultdict(Counter); dec=defaultdict(Counter); layers_ref=None
for fp in calls:
    m=json.load(open(os.path.join(fp,'meta.json'),encoding='utf-8'))
    T=m['T']; Ls=m['layers']; K=m['top_n']; voc=m['vocab']; ctx=m['ctx_strs']; off=int(m.get('ctx_offset') or 0)
    raw=gzip.decompress(open(os.path.join(fp,'slice.bin'),'rb').read())
    N=T*len(Ls)*K
    ids=np.frombuffer(raw,dtype=np.int32,count=N).reshape(T,len(Ls),K)
    layers_ref=Ls
    seg={s['kind']:s for s in m['segments']}
    a=seg.get('assistant'); d=seg.get('boundary-decision')
    if not a: continue
    s0,e0=a['start']-off,a['end']-off
    for t in range(max(s0-1,0), min(e0-1,T-1)):
        nxt=ctx[t+1].strip().lower()
        for li,L in enumerate(Ls):
            row=[voc.get(str(i),'') for i in ids[t,li]]
            g=agg[L]; g['n']+=1
            g['top1']+= row[0].strip().lower()==nxt
            g['top10']+= any(x.strip().lower()==nxt for x in row)
            g['word']+=sum(bool(WORD.match(x)) for x in row); g['cjk']+=sum(bool(CJK.search(x)) for x in row); g['tot']+=len(row)
    if d:
        t=d['start']-off
        for li,L in enumerate(Ls):
            for x in [voc.get(str(i),'') for i in ids[t,li]][:3]: dec[L][x.strip().lower()]+=1
print(f"{name}: calls={len(calls)} layers={layers_ref}")
print("  layer  next-tok@1  next-tok@10  word%  cjk%")
for L in layers_ref:
    g=agg[L]; print(f"  L{L:>2}   {g['top1']/g['n']:.3f}      {g['top10']/g['n']:.3f}     {100*g['word']/g['tot']:5.1f} {100*g['cjk']/g['tot']:5.1f}")
print("  decision boundary top-3 tokens:")
for L in layers_ref: print(f"   L{L:>2}: "+', '.join(f"{t}({n})" for t,n in dec[L].most_common(8)))
