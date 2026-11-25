#!/bin/bash
# agentic-misalignment main chain on project-b GPU 0 (PLAN.md S3-S7). Waits for CHAIN_AM_PRE_DONE and for the Haiku
# labels (ana/am/LABELS_READY, uploaded from the PC). Any failed step stops the chain (the loop restarts it).
B=/home/project-b/LJW/agentbench2
A=$B/ana
LOG=$A/logs/chain_am_main.log
source $B/ops/env_ab.sh
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 AB_PLATFORM=projectb PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false
export AB_BATCH=${AB_BATCH:-64}
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
R=$B/agentic-misalignment/results/qwen35_4b_am
cd $A
echo "$(date '+%F %T') waiting for CHAIN_AM_PRE_DONE and LABELS_READY" >> $LOG
until grep -q CHAIN_AM_PRE_DONE $A/logs/chain_am_pre.log 2>/dev/null && [ -f $A/am/LABELS_READY ]; do
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
step analyze $V -u ab_analyze.py $A/am/jlens $A/am/jlens_report $A/am/units.json
step causal1 $V -u ab_causal1.py $A/am/jlens $A/am/units.json $A/am/c1
step sweep $V -u ab_regen.py sweep am $A/am/units.json $A/am/c2
step band $V -u ab_regen.py band am $A/am/units.json $A/am/c2
step test $V -u ab_regen.py test am $A/am/units.json $A/am/c2
step report $V -u ab_regen.py report am $A/am/units.json $A/am/c2
echo "$(date '+%F %T') CHAIN_AM_MAIN_DONE" >> $LOG
