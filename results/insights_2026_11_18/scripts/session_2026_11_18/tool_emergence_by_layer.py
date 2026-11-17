import os, json, csv, sys, math
from collections import defaultdict
import numpy as np
from sklearn.metrics import roc_auc_score
csv.field_size_limit(10**9)
root=r'C:\Users\user\jlens-drive-data\vast-backup'
d=sys.argv[1]
def lk(x): return 99 if x=='model_final' else int(x)
# tool_scores: called tool, correct (expected_and_actual) vs wrong (actual only)
R=defaultdict(lambda: defaultdict(list))
for row in csv.DictReader(open(os.path.join(root,d,'tool_scores.csv'),encoding='utf-8')):
    k=row['candidate_kind']
    if k not in ('expected_and_actual','actual'): continue
    r0=json.loads(row['ranks'])[0]
    R[lk(row['layer'])][k].append((r0, float(row['mean_logprob']), float(row['mean_rank'])))
print(f"{d} tool_scores: called tool first-token rank by layer (median), correct vs wrong tool; AUC(wrong has worse rank)")
for L in sorted(R):
    a=R[L]['expected_and_actual']; b=R[L]['actual']
    ra=[x[0] for x in a]; rb=[x[0] for x in b]
    y=[0]*len(ra)+[1]*len(rb)
    auc=roc_auc_score(y, ra+rb) if rb else float('nan')
    auc_lp=roc_auc_score(y, [-x[1] for x in a]+[-x[1] for x in b]) if rb else float('nan')
    top10a=np.mean([x<10 for x in ra]); top10b=np.mean([x<10 for x in rb]) if rb else float('nan')
    print(f"  L{('F' if L==99 else L)!s:>2} correct n={len(ra)} med={np.median(ra):8.0f} top10={top10a:.2f} | wrong n={len(rb)} med={np.median(rb) if rb else float('nan'):8.0f} top10={top10b:.2f} | AUC rank {auc:.2f} logprob {auc_lp:.2f}")
# generated spans: failure vs success, per layer, tool_name and argument_value
S=defaultdict(lambda: defaultdict(lambda: {'s':[], 'f':[]}))
for row in csv.DictReader(open(os.path.join(root,d,'generated_span_scores.csv'),encoding='utf-8')):
    o='f' if row['outcome']=='failure' else 's'
    S[row['span_kind']][lk(row['layer'])][o].append(float(row['mean_logprob']))
for kind in S:
    print(f"\n{d} generated {kind}: AUC(failure-episode spans have lower J-lens logprob of the emitted token) per layer")
    line=[]
    for L in sorted(S[kind]):
        s=S[kind][L]['s']; f=S[kind][L]['f']
        auc=roc_auc_score([0]*len(s)+[1]*len(f), [-x for x in s]+[-x for x in f])
        line.append(f"L{('F' if L==99 else L)}:{auc:.2f}")
    print('  '+' '.join(line))
    print('  n success/failure spans per layer:', len(S[kind][0]['s']), len(S[kind][0]['f']))
