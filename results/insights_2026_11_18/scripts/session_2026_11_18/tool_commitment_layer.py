import os, json, csv, sys
from collections import defaultdict
import numpy as np
from sklearn.metrics import roc_auc_score
csv.field_size_limit(10**9)
root=r'C:\Users\user\jlens-drive-data\vast-backup'
for TH,d in [(1,'qwen4retail'),(9,'qwen4retail'),(1,'qwen0.5retail'),(9,'qwen0.5retail')]:
    R=defaultdict(dict); kind={}
    for row in csv.DictReader(open(os.path.join(root,d,'tool_scores.csv'),encoding='utf-8')):
        k=row['candidate_kind']
        if k not in ('expected_and_actual','actual'): continue
        key=(row['call_id'],row['candidate_tool'])
        L=99 if row['layer']=='model_final' else int(row['layer'])
        R[key][L]=json.loads(row['ranks'])[0]; kind[key]=k
    out={'expected_and_actual':[], 'actual':[]}
    for key,byL in R.items():
        Ls=sorted(byL)
        # commitment layer: earliest L after which first-token rank stays 0 (top-1) through the last layer
        c=None
        for i,L in enumerate(Ls):
            if all(byL[M]<=TH for M in Ls[i:]): c=L; break
        if c is None: c=100
        # number of top-1 flips across layers >= mid
        mids=[L for L in Ls if L>=Ls[len(Ls)//2]]
        flips=sum((byL[a]<=TH)!=(byL[b]<=TH) for a,b in zip(mids,mids[1:]))
        out[kind[key]].append((c,flips))
    a=out['expected_and_actual']; b=out['actual']
    ca=[x[0] for x in a]; cb=[x[0] for x in b]
    auc=roc_auc_score([0]*len(ca)+[1]*len(cb), ca+cb)
    auc2=roc_auc_score([0]*len(a)+[1]*len(b), [x[1] for x in a]+[x[1] for x in b])
    print(f"{d} rank<={TH}: commitment layer (rank stays top-1 to the end)  correct: median {np.median(ca)} IQR {np.percentile(ca,25)}-{np.percentile(ca,75)} (n={len(ca)}) | wrong: median {np.median(cb)} IQR {np.percentile(cb,25)}-{np.percentile(cb,75)} (n={len(cb)}) | AUC later-commit=>wrong {auc:.2f} | top-1 flips AUC {auc2:.2f}")
