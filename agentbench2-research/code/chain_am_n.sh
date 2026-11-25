#!/bin/bash
# agentic-misalignment N1 / N2 / N3 on project-b GPU 0 after the main chain (PLAN.md MAIN QUESTION).
B=/home/project-b/LJW/agentbench2
A=$B/ana
LOG=$A/logs/chain_am_n.log
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 AB_PLATFORM=projectb PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false
export AB_BATCH=${AB_BATCH:-32}  # 32 (was 64): GPU 0 is shared
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
cd $A
echo "$(date '+%F %T') waiting for CHAIN_AM_MAIN_DONE" >> $LOG
until grep -q CHAIN_AM_MAIN_DONE $A/logs/chain_am_main.log 2>/dev/null; do
  [ -f $A/CHAIN_STOP ] && { echo "$(date '+%F %T') stop file" >> $LOG; exit 0; }
  grep -q CHAIN_AM_MAIN_FAILED $A/logs/chain_am_main.log 2>/dev/null && { echo "$(date '+%F %T') main chain failed; waiting for a restart" >> $LOG; sleep 300; continue; }
  sleep 60
done
step() {
  local name=$1; shift
  [ -f $A/am/done_$name ] && { echo "$(date '+%F %T') $name already done" >> $LOG; return 0; }
  echo "$(date '+%F %T') start $name" >> $LOG
  "$@" > $A/logs/am_$name.log 2>&1
  local rc=$?
  echo "$(date '+%F %T') $name rc=$rc" >> $LOG
  [ $rc -ne 0 ] && { echo "$(date '+%F %T') CHAIN_AM_N_FAILED at $name" >> $LOG; exit 1; }
  touch $A/am/done_$name
}
D=$A/am
step n1 $V -u ab_n1.py $A/n1
step n2fit $V -u ab_n2.py fit am $D/units.json $D/c2 $A/n1/n1_neurons.json $D/n2
step n2tune $V -u ab_n2.py tune am $D/units.json $D/c2 $A/n1/n1_neurons.json $D/n2
step n2test $V -u ab_n2.py test am $D/units.json $D/c2 $A/n1/n1_neurons.json $D/n2
step n2report $V -u ab_n2.py report am $D/units.json $D/c2 $A/n1/n1_neurons.json $D/n2
echo "$(date '+%F %T') CHAIN_AM_N_DONE" >> $LOG
