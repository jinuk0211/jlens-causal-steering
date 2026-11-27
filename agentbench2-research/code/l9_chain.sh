#!/bin/bash
# L9 chain (PLAN.md Log 11-27 13:2x): the 4B AM leaking flow on Qwen3.5-9B, project-b GPU 0 (and GPU 2 for the second test worker).
B=/home/project-b/LJW/agentbench2
A=$B/ana
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID AB_PLATFORM=projectb PYTHONDONTWRITEBYTECODE=1
export TOKENIZERS_PARALLELISM=false CUDA_VISIBLE_DEVICES=0
export AB_MODEL=Qwen/Qwen3.5-9B AB_REV=c202236235762e1c871ad0ccb60c8ee5ba337b9a AB_NE=$A/ne9
export AB_LENS_REV=d2527c3cdbaa60dd4b65cbca1604921f044e989a AB_LENS_FILE=qwen3.5-9b-pt/jlens/Salesforce-wikitext/Qwen3.5-9B-Base_jacobian_lens.pt
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
O=/home/project-b/LJW/ontoloop/.venv/bin/python
AMC=leaking_explicit-america_none,leaking_explicit-america_replacement
cd $A
mkdir -p ne9/steer_am
cp -n ne/steer_am/extra_units_t9g.json ne9/steer_am/
LG=logs/l9_chain.log
say() { echo "$(date '+%F %T') $*" >> $LG; }
free_mb() { echo $(( $(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits -i $1) - $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $1) )); }
need_free() { until [ "$(free_mb 0)" -ge $1 ] || [ -f L9_STOP ]; do sleep 30; done; [ -f L9_STOP ] && { say STOP; exit 0; }; }
drain() {
  for port in 18303 18302; do
    P=$(ps -eo pid,args | awk -v p="$port" '$2 == "bash" && $3 == "x18_lane.sh" && $4 == "0" && $5 == p {print $1}')
    [ -n "$P" ] && kill $P && say "drained AgentDojo lane 0:$port (loop pid $P; its current job finishes)"
  done
}
say "chain start"
drain
need_free 29500
say "L9a vLLM start, GPU 0 free $(free_mb 0) MB"
AB_MEM=0.55 $O -u am9_vllm.py ne9/amgen_vllm.jsonl "all16:0:16;$AMC:16:80" > logs/l9_vllm.log 2>&1
say "L9a vllm rc=$? $(grep -c . ne9/amgen_vllm.jsonl) rows"
python3 am9_vllm.py report ne9/amgen_vllm.jsonl > logs/l9a_report.md 2>&1
PICK=$(python3 - <<'PY'
import json
from collections import defaultdict
am = ("leaking_explicit-america_none", "leaking_explicit-america_replacement")
tot, f16 = [0, 0], defaultdict(lambda: [0, 0])
for line in open("/home/project-b/LJW/agentbench2/ana/ne9/amgen_vllm.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if r["condition"] in am:
        tot[0] += 1
        tot[1] += r["harm"]
    elif r["seed"] < 16:
        f16[r["condition"]][0] += 1
        f16[r["condition"]][1] += r["harm"]
if tot[1] >= 10:
    print(",".join(am))
else:
    print(",".join(sorted(f16, key=lambda c: -f16[c][1] / f16[c][0])[:2]))
PY
)
say "pick prompts: $PICK (america pair leaks: $(grep -c '"harm": true' <(grep -E 'america_(none|replacement)' ne9/amgen_vllm.jsonl)))"
if [ "$PICK" != "$AMC" ]; then
  say "stop rule: the america pair leaks in fewer than 10 samples; 80 more samples on $PICK"
  AB_MEM=0.55 $O -u am9_vllm.py ne9/amgen_vllm.jsonl "$PICK:16:80" >> logs/l9_vllm.log 2>&1
  say "L9a extra vllm rc=$?"
fi
need_free 31000
if [ ! -f ne9/DICT_DONE ]; then
  $V -u ab_ne.py dict > logs/l9_dict.log 2>&1
  say "dict rc=$? $(tail -1 logs/l9_dict.log | cut -c1-120)"
fi
if [ ! -f ne9/AMSCAN_DONE_s1 ]; then
  AB_SCAN_NO_ORIG=1 AB_SCAN_RESNORM=1 AB_SCAN_TAG=_s1 AB_SCAN_CONDS=$PICK AB_EXTRA_UNITS=$A/ne9/steer_am/extra_units_t9g.json \
    $V -u ab_ne.py amscan > logs/l9_scan.log 2>&1
  say "scan rc=$? $(grep -E 'AMSCAN_DONE|resnorm' logs/l9_scan.log | tail -2 | cut -c1-300)"
fi
$V -u am9_arms.py l9t ne9/amgen_vllm.jsonl $PICK > logs/l9_arms.log 2>&1
RC=$?
say "arms rc=$RC $(grep -E 'test prompts' logs/l9_arms.log | cut -c1-400)"
[ $RC -ne 0 ] && { say "CHAIN_STOPPED arms"; exit 1; }
need_free 29000
say "L9c worker w0 (GPU 0, seeds 20000-20005)"
AB_ROWS_SUFFIX=_w0 AB_SEED_OFF=20000 AB_SEEDS=6 AB_STEER_ROWS=12 setsid -f $V -u ab_ne.py amwin l9t > logs/l9_amwin_w0.log 2>&1 < /dev/null
sleep 600
until [ "$(free_mb 0)" -ge 29000 ] || [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 2)" -lt 1000 ] || [ -f L9_STOP ]; do sleep 60; done
[ -f L9_STOP ] && { say STOP; exit 0; }
if [ "$(free_mb 0)" -ge 29000 ]; then G=0; RB=12; else G=2; RB=4; fi
say "L9c worker w1 (GPU $G, rows $RB, seeds 20006-20011)"
CUDA_VISIBLE_DEVICES=$G AB_ROWS_SUFFIX=_w1 AB_SEED_OFF=20006 AB_SEEDS=6 AB_STEER_ROWS=$RB setsid -f $V -u ab_ne.py amwin l9t > logs/l9_amwin_w1.log 2>&1 < /dev/null
until [ -f ne9/steer_am/l9t_DONE_w0 ] && [ -f ne9/steer_am/l9t_DONE_w1 ]; do sleep 120; [ -f L9_STOP ] && { say STOP; exit 0; }; done
python3 am9_report.py ne9/steer_am/arms_l9t.json ne9/steer_am/rows_l9t_*.jsonl > logs/l9c_report.md 2>&1
say "L9C_DONE $(grep verdict logs/l9c_report.md | head -1)"
