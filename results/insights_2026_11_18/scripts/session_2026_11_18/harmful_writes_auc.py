import json
from sklearn.metrics import roc_auc_score
T=[json.loads(l) for l in open('tbl/turns.jsonl',encoding='utf-8')]
E={e['sim']:e for e in map(json.loads,open('tbl/episodes.jsonl',encoding='utf-8'))}
def btype(r):
    w=[x for x in r['write_types'] if x['type']!='match'][0]
    return 'transfer' if w['name']=='transfer_to_human_agents' else w['type']
bad=[r for r in T if r['label']=='bad_write']; good=[r for r in T if r['label']=='good_write']
from collections import Counter
print('bad by type x episode reward:', Counter((btype(r), E[r['sim']]['reward']) for r in bad))
harm=[r for r in bad if btype(r)!='transfer']
y=[1]*len(harm)+[0]*len(good); s=[r['trig_score'] for r in harm+good]
print('nontransfer bad vs good AUC', round(roc_auc_score(y,s),3), len(harm), len(good))
hf=[r for r in harm if E[r['sim']]['reward']<1]
y=[1]*len(hf)+[0]*len(good); s=[r['trig_score'] for r in hf+good]
print('nontransfer bad in FAILED eps vs good AUC', round(roc_auc_score(y,s),3), len(hf))
print('fired: transfer', sum(r['fired'] for r in bad if btype(r)=='transfer'), '/', sum(btype(r)=='transfer' for r in bad), ' harm', sum(r['fired'] for r in harm),'/',len(harm), ' good', sum(r['fired'] for r in good),'/',len(good))
eps=list(E.values()); fail=[e for e in eps if e['reward']<1]
print('episodes', len(eps), 'fail', len(fail))
# failed episodes: did they contain any harmful bad write?
hs={r['sim'] for r in harm}
print('failed eps with harmful bad write', sum(e['sim'] in hs for e in fail), '/', len(fail))
print('failed eps with any fired turn', sum(any(e['fired']) for e in fail), '/', len(fail), ' passed eps any fired', sum(any(e['fired']) for e in eps if e['reward']>=1), '/', len(eps)-len(fail))
print('failure flags', Counter((e['agent_error'], e['user_error']) for e in fail))
