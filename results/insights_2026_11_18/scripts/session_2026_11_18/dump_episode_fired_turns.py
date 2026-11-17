import json, glob, os, re, ast
from collections import defaultdict
BASE=r'C:\Users\user\jlens-work\vt-episodes'
def c(s,n): s=re.sub(r'\s+',' ',s or ''); return s if len(s)<=n else s[:n]+'…'
def msgs(ctx):
    out=[]
    for seg in ctx.split('<|im_start|>')[1:]:
        role,_,body=seg.partition('\n'); body=body.replace('<|im_end|>','').strip()
        if role=='user' and body.startswith('<tool_response>'): role='tool'
        out.append((role,body))
    return out
recs=defaultdict(list)  # (task,cond)->records
for srv in ('s1','s2'):
    for cond in ('detect','jlens','caa','random'):
        for p in glob.glob(os.path.join(BASE,srv,'jlens-telemetry','vt-heldout',cond,'*.jsonl')):
            tid=os.path.basename(p).split('-')[0]
            for line in open(p,encoding='utf-8'):
                x=json.loads(line)
                iv=x.get('intervention')
                if isinstance(iv,str):
                    try: iv=ast.literal_eval(iv)
                    except Exception: iv={'raw':iv[:200]}
                x['_iv']=iv; x['_file']=os.path.basename(p)
                recs[(tid,cond)].append(x)
tasks=sorted({t for t,_ in recs},key=int)
for tid in tasks:
    for cond in ('detect','jlens','caa','random'):
        R=recs.get((tid,cond))
        if not R: continue
        files=sorted({x['_file'] for x in R})
        R=[x for x in R if x['_file']==files[-1]]
        R.sort(key=lambda x:x['turn_index'])
        fired=[x for x in R if x['_iv'].get('active') or x['_iv'].get('reason') in ('triggered','detect_only','logged_only') or x['_iv'].get('triggered')]
        if not fired: continue
        print(f"## task{tid} {cond} nturns={len(R)} fired_turns={[x['turn_index'] for x in fired]}")
        for x in fired:
            m=[y for y in msgs(x['rendered_context'])[:-1] if y[0]!='system']
            lu=next((b for r,b in reversed(m) if r=='user'),'')
            calls=','.join(t.get('name','?') for t in (x.get('tool_calls') or []))
            gt=re.sub(r'<tool_call>.*','',x['generated_text'],flags=re.S).replace('<|im_end|>','')
            print(f"   t{x['turn_index']} reason={x['_iv'].get('reason')} | USER: {c(lu,150)}")
            print(f"        -> calls=[{calls}] | {c(gt,200)}")
