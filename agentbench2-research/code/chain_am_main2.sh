#!/bin/bash
# agentic-misalignment main chain, CAUSAL-2 path (PLAN.md S3, S5-S7), project-b GPU 0. Needs the labels and stats.npz only,
# so it runs next to the J-lens path (chain_am_jl.sh). Any failed step stops the chain (the loop restarts it).
B=/home/project-b/LJW/agentbench2
A=$B/ana
LOG=$A/logs/chain_am_main.log
source $B/ops/env_ab.sh
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 AB_PLATFORM=projectb PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false
export AB_BATCH=${AB_BATCH:-32} PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True  # 32 (was 64): GPU 0 is shared with the other chains
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
R=$B/agentic-misalignment/results/qwen35_4b_am
cd $A
echo "$(date '+%F %T') waiting for LABELS_READY and stats.npz" >> $LOG
until [ -f $A/am/LABELS_READY ] && [ -f $A/am/c2/stats.npz ]; do
  [ -f $A/CHAIN_STOP ] && { echo "$(date '+%F %T') stop file" >> $LOG; exit 0; }
  sleep 60
done
step() {
  local name=$1; shift
  [ -f $A/am/done_$name ] && { echo "$(date '+%F %T') $name already done" >> $LOG; return 0; }
  echo "$(date '+%F %T') start $name" >> $LOG
  "$@" > $A/logs/am_$name.log 2>&1
  local rc=$?
  echo "$(date '+%F %T') $name rc=$rc" >> $LOG
  [ $rc -ne 0 ] && { echo "$(date '+%F %T') CHAIN_AM_MAIN_FAILED at $name" >> $LOG; exit 1; }
  touch $A/am/done_$name
}
[ -f $R/haiku_classifications.jsonl ] || cp $A/am/haiku_classifications.jsonl $R/haiku_classifications.jsonl
step units $V -u units_am.py $R $B/ops/proxy_log/am.jsonl $A/am/units.json
step behavior $V -u ab_behavior.py am $R $A/am/units.json $A/am/behavior.md
step sweep $V -u ab_regen.py sweep am $A/am/units.json $A/am/c2
step band $V -u ab_regen.py band am $A/am/units.json $A/am/c2
step test $V -u ab_regen.py test am $A/am/units.json $A/am/c2
step report $V -u ab_regen.py report am $A/am/units.json $A/am/c2
echo "$(date '+%F %T') CHAIN_AM_MAIN_DONE" >> $LOG
