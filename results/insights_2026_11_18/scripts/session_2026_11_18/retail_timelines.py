import os, json, csv, re
from collections import defaultdict
csv.field_size_limit(10**9)
root=r'C:\Users\user\jlens-drive-data\vast-backup\qwen4retail'
m=json.load(open(os.path.join(root,'manifest.json'),encoding='utf-8'))
cases={c['simulation_id']:c for c in m['cases']}
LAY=['15','19','23','27','model_final']
rd=defaultdict(lambda: defaultdict(dict))  # call_id -> boundary(+label) -> layer -> toks
meta_call={}
for row in csv.DictReader(open(os.path.join(root,'semantic_boundary_readouts.csv'),encoding='utf-8')):
    if row['layer'] not in LAY: continue
    b=row['boundary']
    if b=='argument': b='arg:'+ (row['boundary_label'] or '')[:30]
    key=b
    if key in rd[row['call_id']] and row['layer'] in rd[row['call_id']][key]: continue  # first occurrence
    rd[row['call_id']][key][row['layer']]=[t.strip() for t in json.loads(row['top_token_pieces'])][:5]
    meta_call[row['call_id']]=(row['simulation_id'],int(row['call_index']),int(row['turn_index']))
# assistant text + previous message from call dirs
dirs={d.split('__call_')[-1]:os.path.join(root,d) for d in os.listdir(root) if '__call_' in d}
def texts(cid):
    p=dirs.get(cid)
    if not p: return '',''
    mt=json.load(open(os.path.join(p,'meta.json'),encoding='utf-8'))
    off=int(mt.get('ctx_offset') or 0); ctx=mt['ctx_strs']
    seg={s['kind']:s for s in mt['segments']}
    a=seg.get('assistant')
    full=''.join(ctx)
    asst=''.join(ctx[a['start']-off:a['end']-off]) if a else ''
    req=''.join(ctx[:(a['start']-off) if a else len(ctx)])
    last=req.rsplit('<|im_start|>',2)
    prev=last[-2] if len(last)>=2 else ''
    return re.sub(r'\s+',' ',prev)[-260:], re.sub(r'\s+',' ',asst)[:260]
def fmt(d):
    return ' | '.join(f"{'F' if L=='model_final' else 'L'+L}:{','.join(d.get(L,[]))}" for L in LAY if L in d)
bysim=defaultdict(list)
for cid,(sim,ci,ti) in meta_call.items(): bysim[sim].append((ci,ti,cid))
order=sorted(cases.values(), key=lambda c:(c['outcome']!='failure', int(c['task_id'])))
for c in order:
    sim=c['simulation_id']
    print(f"\n######## task {c['task_id']} {c['outcome']} sim {sim[:8]}  expected={c['expected_tools']}  actual={c['actual_tools']}")
    ri=c.get('reward_info') or {}
    print('   reward_info:', json.dumps(ri,ensure_ascii=False)[:400])
    for ci,ti,cid in sorted(bysim[sim]):
        prev,asst=texts(cid)
        print(f" -- call {ci} (turn {ti})  PREV: {prev}")
        print(f"    ASST: {asst}")
        for b in ('observation','decision','tool'):
            if b in rd[cid]: print(f"    [{b[:3]}] {fmt(rd[cid][b])}")
        args=[k for k in rd[cid] if k.startswith('arg:')][:2]
        for k in args: print(f"    [{k[:22]}] {fmt(rd[cid][k])}")
