import os, json, glob
root=r'C:\Users\user\jlens-drive-data\vast-backup'
for p in ['gptoss20airline/0011-0050-reasoning-low-ctx32k-out4k-seed300/full','48577418/tail20/full','gpt-oss-20b-airline20/tail20/full']:
    base=os.path.join(root,p)
    m=json.load(open(os.path.join(base,'manifest.json'),encoding='utf-8'))
    print('=====',p, 'manifest keys', list(m.keys()) if isinstance(m,dict) else type(m))
    s=json.dumps(m,ensure_ascii=False); print('  ',s[:700])
    calls=[d for d in os.listdir(base) if d.startswith('task_')]
    print('  calls', len(calls), 'tasks', sorted({c.split('__')[0] for c in calls}))
    c0=os.path.join(base,calls[0]); print('  files', os.listdir(c0)[:10])
    for f in ('meta.json','analysis.json'):
        fp=os.path.join(c0,f)
        if os.path.exists(fp):
            j=json.load(open(fp,encoding='utf-8')); s=json.dumps(j,ensure_ascii=False)
            print(f'  {f} {len(s)} chars keys', list(j.keys())[:25] if isinstance(j,dict) else type(j)); print('    ', s[:900])
    r=os.path.join(c0,'ranks'); 
    if os.path.isdir(r): fl=os.listdir(r); print('  ranks files', len(fl), fl[:5], os.path.getsize(os.path.join(r,fl[0])))
