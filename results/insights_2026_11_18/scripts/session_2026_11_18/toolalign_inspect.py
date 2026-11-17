import os, json, csv
from collections import Counter
csv.field_size_limit(10**9)
root=r'C:\Users\user\jlens-drive-data\vast-backup\toolalignbench'
m=json.load(open(os.path.join(root,'manifest.json'),encoding='utf-8'))
sc=m['selected_calls']; print('selected_calls', len(sc)); print(json.dumps(sc[0],ensure_ascii=False)[:1500])
print(Counter((x.get('scenario_type'),x.get('condition')) for x in sc))
print(Counter(x.get('domain') for x in sc).most_common(30))
print('entries', len(m['entries']), json.dumps(m['entries'][0],ensure_ascii=False)[:800])
c=Counter(); e=Counter()
for row in csv.DictReader(open(os.path.join(root,'semantic_boundary_readouts.csv'),encoding='utf-8')):
    c[(row['segment_kind'],row['edge'])]+=1
print(c)
