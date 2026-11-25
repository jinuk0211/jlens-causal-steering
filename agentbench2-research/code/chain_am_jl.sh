#!/bin/bash
# agentic-misalignment J-lens path (PLAN.md S4 + CAUSAL-1), project-b GPU 0: after the J-lens rerun and units.json.
B=/home/project-b/LJW/agentbench2
A=$B/ana
LOG=$A/logs/chain_am_jl.log
source $B/ops/env_ab.sh
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 AB_PLATFORM=projectb PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
cd $A
echo "$(date '+%F %T') waiting for CHAIN_AM_PRE_DONE and done_units" >> $LOG
until grep -q CHAIN_AM_PRE_DONE $A/logs/chain_am_pre.log 2>/dev/null && [ -f $A/am/done_units ]; do
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
  [ $rc -ne 0 ] && { echo "$(date '+%F %T') CHAIN_AM_JL_FAILED at $name" >> $LOG; exit 1; }
  touch $A/am/done_$name
}
step analyze $V -u ab_analyze.py $A/am/jlens $A/am/jlens_report $A/am/units.json
step causal1 $V -u ab_causal1.py $A/am/jlens $A/am/units.json $A/am/c1
echo "$(date '+%F %T') CHAIN_AM_JL_DONE" >> $LOG
