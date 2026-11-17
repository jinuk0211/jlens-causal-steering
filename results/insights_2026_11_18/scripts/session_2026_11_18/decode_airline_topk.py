import glob, json, os, sys, time
import torch
sys.path.insert(0, r'C:\Users\user\jlens-work\jlens-causal-steering\src')
from jlens_causal.vocab_trigger import load_readout_head
import jlens
from transformers import AutoTokenizer
MD=r'C:\Users\user\.cache\huggingface\hub\models--Qwen--Qwen3.5-4B\snapshots\851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a'
LENS=r'C:\Users\user\.cache\huggingface\hub\models--neuronpedia--jacobian-lens\snapshots\a4114d7752d11eb546e6cf372213d7e75526d3a1\qwen3.5-4b\jlens\Salesforce-wikitext\Qwen3.5-4B_jacobian_lens_n1000.pt'
ROOT=r'C:\Users\user\jlens-work\vocab-trigger-bundle\jlens-telemetry\failure-steering'
OUT=sys.argv[1]
torch.set_num_threads(8)
t0=time.time()
tok=AutoTokenizer.from_pretrained(MD)
head=load_readout_head(MD); lens=jlens.JacobianLens.load(LENS)
U=head.unembed  # fp32 [V,d]
print('loaded', round(time.time()-t0), 's', flush=True)
K=10
n=0
with open(OUT,'w',encoding='utf-8') as out:
    for split in ('train','validation','evaluation'):
        for path in sorted(glob.glob(os.path.join(ROOT,split,'*.jsonl'))):
            for line in open(path,encoding='utf-8'):
                rec=json.loads(line)
                items=rec['measurement'].get('residuals',[])
                keys=[];vecs=[];layers=[]
                for it in items:
                    keys.append((it['label'],int(it['layer']),int(it['position'])))
                    vecs.append(it['vector']); layers.append(int(it['layer']))
                res={}
                if vecs:
                    H=torch.tensor(vecs,dtype=torch.float32)
                    for L in sorted(set(layers)):
                        idx=[i for i,l in enumerate(layers) if l==L]
                        X=H[idx]@lens.jacobians[L].T if L in lens.jacobians else H[idx]
                        z=head.norm(X)@U.T
                        top=z.topk(K,dim=-1).indices.tolist()
                        for j,i in enumerate(idx):
                            lab,_,pos=keys[i]
                            res.setdefault(lab,{}).setdefault(str(L),[]) .append((pos,[tok.decode([t]) for t in top[j]]))
                # keep first position per (site,layer) and last for tool sites
                compact={}
                for lab,byL in res.items():
                    for L,lst in byL.items():
                        lst.sort()
                        compact[f'{lab}|L{L}|first']=lst[0][1]
                        if len(lst)>1: compact[f'{lab}|L{L}|last']=lst[-1][1]
                out.write(json.dumps({'split':split,'sim':os.path.basename(path)[:-6],'task_id':str(rec['task_id']),'turn':rec['turn_index'],'record_id':rec['record_id'],'top':compact},ensure_ascii=False)+'\n')
                n+=1
            print(split, os.path.basename(path)[:20], n, round(time.time()-t0),'s', flush=True)
print('done', n)
