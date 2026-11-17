import os, json, csv, sys
csv.field_size_limit(10**9)
root=r'C:\Users\user\jlens-drive-data\vast-backup'
for d in ['qwen4retail','qwen0.5retail','toolalignbench']:
    p=os.path.join(root,d)
    print('=====',d)
    for f in ['manifest.json','analysis_report.json']:
        fp=os.path.join(p,f)
        if os.path.exists(fp):
            j=json.load(open(fp,encoding='utf-8'))
            s=json.dumps(j,ensure_ascii=False)
            print(f' {f} ({len(s)} chars) keys:', list(j.keys())[:20] if isinstance(j,dict) else type(j))
            print('   ', s[:900])
    for f in ['semantic_boundary_readouts.csv','tool_scores.csv','generated_span_scores.csv']:
        fp=os.path.join(p,f)
        if os.path.exists(fp):
            with open(fp,encoding='utf-8') as fh:
                r=csv.reader(fh); hdr=next(r); first=next(r); n=1+sum(1 for _ in r)
            print(f' {f}: rows={n} size={os.path.getsize(fp)//1024}KB cols={hdr}')
            print('    first:', [x[:80] for x in first])
    subs=[x for x in os.listdir(p) if os.path.isdir(os.path.join(p,x))]
    print(' n subdirs', len(subs))
    if subs:
        s0=os.path.join(p,subs[0]); print(' sample subdir', subs[0], os.listdir(s0)[:10])
