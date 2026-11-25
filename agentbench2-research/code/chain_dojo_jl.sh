#!/bin/bash
# AgentDojo J-lens path on project-b GPU 0 after the AM J-lens path (GPU memory): jlens, analyze (B-F + AUC), CAUSAL-1.
B=/home/project-b/LJW/agentbench2
A=$B/ana
LOG=$A/logs/chain_dojo_jl.log
mkdir -p $A/logs $A/dojo
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 AB_PLATFORM=projectb PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false
export AB_BATCH=${AB_BATCH:-16}
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
VA=$B/.venv/bin/python
D=$A/dojo
cd $A
echo "$(date '+%F %T') waiting: done_units and CHAIN_AM_JL_DONE" >> $LOG
until [ -f $D/done_units ] && grep -q CHAIN_AM_JL_DONE $A/logs/chain_am_jl.log 2>/dev/null; do
  [ -f $A/CHAIN_STOP ] && { echo "$(date '+%F %T') stop file" >> $LOG; exit 0; }
  sleep 60
done
step() {
  local name=$1; shift
  [ -f $D/done_$name ] && { echo "$(date '+%F %T') $name already done" >> $LOG; return 0; }
  echo "$(date '+%F %T') start $name" >> $LOG
  "$@" > $A/logs/dojo_$name.log 2>&1
  local rc=$?
  echo "$(date '+%F %T') $name rc=$rc" >> $LOG
  [ $rc -ne 0 ] && { echo "$(date '+%F %T') CHAIN_DOJO_JL_FAILED at $name" >> $LOG; exit 1; }
  touch $D/done_$name
}
step jlens $V -u ab_jlens.py dojo $D/units.json $D/jlens
step analyze $V -u ab_analyze.py $D/jlens $D/jlens_report $D/units.json
step causal1 $V -u ab_causal1.py $D/jlens $D/units.json $D/c1
echo "$(date '+%F %T') CHAIN_DOJO_JL_DONE" >> $LOG
