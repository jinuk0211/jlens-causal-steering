#!/bin/bash
# AgentDojo N2/N3 on project-b GPU 0 after the CAUSAL-2 path and N1 (from chain_am_n.sh).
B=/home/project-b/LJW/agentbench2
A=$B/ana
LOG=$A/logs/chain_dojo_n.log
mkdir -p $A/logs $A/dojo
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 AB_PLATFORM=projectb PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false
export AB_BATCH=${AB_BATCH:-16}
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
VA=$B/.venv/bin/python
D=$A/dojo
cd $A
echo "$(date '+%F %T') waiting: CHAIN_DOJO_PB_DONE and n1_neurons.json" >> $LOG
until grep -q CHAIN_DOJO_PB_DONE $A/logs/chain_dojo_pb.log 2>/dev/null && [ -f $A/n1/n1_neurons.json ]; do
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
  [ $rc -ne 0 ] && { echo "$(date '+%F %T') CHAIN_DOJO_N_FAILED at $name" >> $LOG; exit 1; }
  touch $D/done_$name
}
step n2fit $V -u ab_n2.py fit dojo $D/units.json $D/c2 $A/n1/n1_neurons.json $D/n2
step n2tune $V -u ab_n2.py tune dojo $D/units.json $D/c2 $A/n1/n1_neurons.json $D/n2
step n2test $V -u ab_n2.py test dojo $D/units.json $D/c2 $A/n1/n1_neurons.json $D/n2
step n2report $V -u ab_n2.py report dojo $D/units.json $D/c2 $A/n1/n1_neurons.json $D/n2
echo "$(date '+%F %T') CHAIN_DOJO_N_DONE" >> $LOG
