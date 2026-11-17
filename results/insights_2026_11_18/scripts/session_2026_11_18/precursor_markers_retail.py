import os, json, csv, re
from collections import defaultdict, Counter
csv.field_size_limit(10**9)
root=r'C:\Users\user\jlens-drive-data\vast-backup\qwen4retail'
m=json.load(open(os.path.join(root,'manifest.json'),encoding='utf-8'))
cases={c['simulation_id']:c for c in m['cases']}
MARK={
 'refuse': re.compile(r'^(unfortunately|sorry|apolog\w*|cannot|unable|抱歉|遗憾|无法\w*|我无法|没有办法|对不起)$', re.I),
 'doubt': re.compile(r'^(wait|hmm|interesting\w*|actually|notice|注意到|however|但是)$', re.I),
 'done':  re.compile(r'^(already|earlier|previously|我已经|回答了|已经)$', re.I),
 'policy':re.compile(r'^(policy|policies|protocol|严格按照|明确要求|mandatory|according|required|mandated)$', re.I),
}
TEXT={'refuse':re.compile(r'unfortunately|sorry|apolog|cannot|unable',re.I),'doubt':re.compile(r'\bwait\b|\bhmm\b|interesting|actually|however',re.I),'done':re.compile(r'already|earlier|previously',re.I),'policy':re.compile(r'policy|protocol|required',re.I)}
LAYS=['15','19','23','27','model_final']
hits=defaultdict(lambda: defaultdict(set))  # call -> (marker) -> set of 'b@L'
info={}
for row in csv.DictReader(open(os.path.join(root,'semantic_boundary_readouts.csv'),encoding='utf-8')):
    if row['boundary'] not in ('decision','observation') or row['layer'] not in LAYS: continue
    toks=[t.strip() for t in json.loads(row['top_token_pieces'])][:5]
    info[row['call_id']]=(row['simulation_id'],int(row['call_index']))
    for k,rx in MARK.items():
        if any(rx.match(t) for t in toks): hits[row['call_id']][k].add(f"{row['boundary'][:3]}@{row['layer']}")
dirs={d.split('__call_')[-1]:os.path.join(root,d) for d in os.listdir(root) if '__call_' in d}
def asst(cid):
    p=dirs.get(cid)
    if not p: return ''
    mt=json.load(open(os.path.join(p,'meta.json'),encoding='utf-8')); off=int(mt.get('ctx_offset') or 0)
    a=next((s for s in mt['segments'] if s['kind']=='assistant'),None)
    return ''.join(mt['ctx_strs'][a['start']-off:a['end']-off]) if a else ''
bysim=defaultdict(list)
for cid,(sim,ci) in info.items(): bysim[sim].append((ci,cid))
print('per-call rate of marker in lens top-5 (any of dec/obs @ L19/L23) | outcome')
for k in MARK:
    for oc in ('failure','success'):
        calls=[cid for sim,L in bysim.items() if cases[sim]['outcome']==oc for _,cid in L]
        n=sum(any(x.endswith(('@19','@23')) for x in hits[c][k]) for c in calls)
        print(f'  {k:7s} {oc:8s} {n:3d}/{len(calls)} = {n/len(calls):.2f}')
print('\nlead time: first call with marker in lens (dec/obs, L19 or L23) vs first call whose OWN text contains it')
for k in ('refuse','done','doubt','policy'):
    for oc in ('failure','success'):
        leads=[]
        for sim,L in bysim.items():
            if cases[sim]['outcome']!=oc: continue
            L=sorted(L)
            lens_first=next((ci for ci,cid in L if any(x.endswith(('@19','@23')) for x in hits[cid][k])),None)
            text_first=next((ci for ci,cid in L if TEXT[k].search(re.sub(r'<.*?>','',asst(cid)))),None)
            leads.append((lens_first,text_first))
        both=[(a,b) for a,b in leads if a is not None and b is not None]
        lens_only=sum(a is not None and b is None for a,b in leads); text_only=sum(a is None and b is not None for a,b in leads)
        earlier=sum(a<b for a,b in both); same=sum(a==b for a,b in both); later=sum(a>b for a,b in both)
        print(f'  {k:7s} {oc:8s} eps={len(leads):2d} both={len(both):2d}: lens earlier {earlier}, same call {same}, later {later} | lens-only {lens_only} | text-only {text_only}')
