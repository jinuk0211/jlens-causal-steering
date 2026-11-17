import os, json, csv, glob
from collections import Counter
csv.field_size_limit(10**9)
root=r'C:\Users\user\jlens-drive-data\vast-backup'
for d in ['qwen4retail','qwen0.5retail','toolalignbench']:
    for f in ['semantic_boundary_readouts.csv','tool_scores.csv','generated_span_scores.csv']:
        fp=os.path.join(root,d,f)
        if not os.path.exists(fp): continue
        L=Counter(); B=Counter(); O=Counter()
        with open(fp,encoding='utf-8') as fh:
            r=csv.DictReader(fh)
            for row in r:
                L[row['layer']]+=1
                B[row.get('boundary') or row.get('segment_kind') or row.get('candidate_kind') or row.get('span_kind')]+=1
                O[row.get('outcome') or row.get('scenario_type')]+=1
        print(d,f,'layers',sorted(L,key=lambda x:(not x.isdigit(), int(x) if x.isdigit() else 0, x)),'| kinds',dict(B.most_common(8)),'| outcome',dict(O))
# GPT-OSS structure
for p in ['gptoss20airline/0011-0050-reasoning-low-ctx32k-out4k-seed300','gpt-oss-20b-airline20/tail20','48577418/tail20']:
    base=os.path.join(root,p)
    for sub in ['full','inspect']:
        sp_=os.path.join(base,sub)
        items=os.listdir(sp_)
        print('==',p,sub,len(items),items[:6])
