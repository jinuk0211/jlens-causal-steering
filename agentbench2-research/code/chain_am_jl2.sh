#!/bin/bash
# AM J-lens path, second run (15:1x): candidate fix for unquoted recipients (' secure', ' k'), then B-F and CAUSAL-1.
B=/home/project-b/LJW/agentbench2
A=$B/ana
LOG=$A/logs/chain_am_jl.log
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 AB_PLATFORM=projectb PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
cd $A
step() {
  local name=$1; shift
  [ -f $A/am/done_$name ] && { echo "$(date '+%F %T') $name already done" >> $LOG; return 0; }
  echo "$(date '+%F %T') start $name" >> $LOG
  "$@" > $A/logs/am_$name.log 2>&1
  local rc=$?
  echo "$(date '+%F %T') $name rc=$rc" >> $LOG
  [ $rc -ne 0 ] && { echo "$(date '+%F %T') CHAIN_AM_JL_FAILED at $name" >> $LOG; exit 1; }
  touch $A/am/done_$name
}
step jlens2 $V -u ab_jlens.py am $A/am/units.json $A/am/jlens
step analyze $V -u ab_analyze.py $A/am/jlens $A/am/jlens_report $A/am/units.json
step causal1 $V -u ab_causal1.py $A/am/jlens $A/am/units.json $A/am/c1
echo "$(date '+%F %T') CHAIN_AM_JL_DONE" >> $LOG
