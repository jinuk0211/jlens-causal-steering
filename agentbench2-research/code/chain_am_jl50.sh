#!/bin/bash
# AM J-lens re-extraction with top-50 (user request 11-25 16:4x), after the AgentDojo J-lens path (GPU 0 memory).
# Writes am/jlens50 and am/jlens50_report; am/jlens (top-30) stays as it is.
B=/home/project-b/LJW/agentbench2
A=$B/ana
LOG=$A/logs/chain_am_jl50.log
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 AB_PLATFORM=projectb PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false AB_TOPN=50
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
cd $A
echo "$(date '+%F %T') waiting for CHAIN_DOJO_JL_DONE" >> $LOG
until grep -q CHAIN_DOJO_JL_DONE $A/logs/chain_dojo_jl.log 2>/dev/null; do
  [ -f $A/CHAIN_STOP ] && { echo "$(date '+%F %T') stop file" >> $LOG; exit 0; }
  sleep 60
done
$V -u ab_jlens.py am $A/am/units.json $A/am/jlens50 > $A/logs/am_jlens50.log 2>&1 || { echo "$(date '+%F %T') jlens50 FAILED" >> $LOG; exit 1; }
$V -u ab_analyze.py $A/am/jlens50 $A/am/jlens50_report $A/am/units.json > $A/logs/am_analyze50.log 2>&1 || { echo "$(date '+%F %T') analyze50 FAILED" >> $LOG; exit 1; }
echo "$(date '+%F %T') CHAIN_AM_JL50_DONE" >> $LOG
