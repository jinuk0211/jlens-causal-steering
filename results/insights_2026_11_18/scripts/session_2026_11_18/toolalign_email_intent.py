import os, json, csv, re
from collections import Counter, defaultdict
csv.field_size_limit(10**9)
root=r'C:\Users\user\jlens-drive-data\vast-backup\toolalignbench'
EMAIL=re.compile(r'(发送邮件|邮件|email|e-mail|mail)', re.I)
REFUSE=re.compile(r'(我不能|拒绝|cannot|refuse|不能)', re.I)
ESC=re.compile(r'(escalat|report|whistle|authorit|regulator|fda|sec\b|举报|报告)', re.I)
tr=defaultdict(lambda: {'type':None,'bold':None,'email_call':False,'email_lens':Counter(),'refuse_lens':Counter(),'esc_lens':Counter(),'steps':set()})
for row in csv.DictReader(open(os.path.join(root,'semantic_boundary_readouts.csv'),encoding='utf-8')):
    t=tr[row['trace_id']]; t['type']=row['scenario_type']; t['bold']=row['condition'].split('-')[0]=='boldly'; t['steps'].add(row['step'])
    if row['segment_kind']=='tool-name' and 'email' in row['segment'].lower(): t['email_call']=True
    if row['segment_kind'] in ('assistant','scratchpad'):
        toks=json.loads(row['top_tokens']); L=int(row['layer'])
        if any(EMAIL.search(x) for x in toks): t['email_lens'][L]+=1
        if any(REFUSE.search(x) for x in toks): t['refuse_lens'][L]+=1
        if any(ESC.search(x) for x in toks): t['esc_lens'][L]+=1
print('traces', len(tr))
for typ in ('wrongdoing','safe'):
    for bold in (True,False):
        T=[t for t in tr.values() if t['type']==typ and t['bold']==bold]
        if not T: continue
        calls=sum(t['email_call'] for t in T)
        line=f"{typ:10s} {'bold' if bold else 'tame'} n={len(T):3d} email_called={calls:2d}"
        for L in (16,20,24,28,31):
            el=sum(t['email_lens'][L]>0 for t in T); both=sum(t['email_lens'][L]>0 and t['email_call'] for t in T)
            line+=f" | L{L} email-in-lens {el} (called {both})"
        print(line)
print()
for typ in ('wrongdoing','safe'):
    T=[t for t in tr.values() if t['type']==typ]
    print(typ, 'traces with refusal tokens in lens by layer:', {L: sum(t['refuse_lens'][L]>0 for t in T) for L in (0,4,8,12,16,20,24,28,30,31)}, ' escalation tokens:', {L: sum(t['esc_lens'][L]>0 for t in T) for L in (16,20,24,28,30,31)}, 'n', len(T))
