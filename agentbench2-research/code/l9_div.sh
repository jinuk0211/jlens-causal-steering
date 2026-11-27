#!/bin/bash
# L9-div (PLAN.md Log 11-27 16:3x): on GPU 2 once it is empty: the divergence capture, its report, then the second L9c worker.
B=/home/project-b/LJW/agentbench2
A=$B/ana
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID AB_PLATFORM=projectb PYTHONDONTWRITEBYTECODE=1
export TOKENIZERS_PARALLELISM=false CUDA_VISIBLE_DEVICES=2
export AB_MODEL=Qwen/Qwen3.5-9B AB_REV=c202236235762e1c871ad0ccb60c8ee5ba337b9a AB_NE=$A/ne9
export AB_SCAN_NO_ORIG=1 AB_SCAN_CONDS=leaking_explicit-america_none,leaking_explicit-america_replacement AB_EXTRA_UNITS=$A/ne9/steer_am/extra_units_t9g.json
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
cd $A
LG=logs/l9_chain.log
say() { echo "$(date '+%F %T') $*" >> $LG; }
say "l9_div.sh start: waiting for GPU 2 to empty (AgentDojo lanes 2:18305 / 2:18306 drained)"
until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 2)" -lt 1000 ] || [ -f L9_STOP ]; do sleep 30; done
[ -f L9_STOP ] && { say STOP; exit 0; }
if [ ! -f ne9/div_meta.json ]; then
  $V -u ab_div.py cap ne9/div > logs/l9_div_cap.log 2>&1
  say "div cap rc=$? $(tail -1 logs/l9_div_cap.log | cut -c1-120)"
fi
CUDA_VISIBLE_DEVICES="" $V -u ab_div.py report ne9/div ne9/l9a_judge_labels.json > logs/l9_div_report.log 2>&1
say "div report rc=$?"
say "L9c worker w1 (GPU 2, rows 4, seeds 20006-20011)"
AB_ROWS_SUFFIX=_w1 AB_SEED_OFF=20006 AB_SEEDS=6 AB_STEER_ROWS=4 setsid -f $V -u ab_ne.py amwin l9t > logs/l9_amwin_w1.log 2>&1 < /dev/null
