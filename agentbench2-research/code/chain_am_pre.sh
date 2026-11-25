#!/bin/bash
# agentic-misalignment, label-free steps on project-b GPU 0 while the Haiku labels are made on the PC:
# wait for RESERVE_AM_DONE, build unlabeled units, then CAUSAL-2 stats and J-lens extraction. GPU 0 must have no
# other process (ab_core.gpu_guard checks again inside every python step).
B=/home/project-b/LJW/agentbench2
A=$B/ana
LOG=$A/logs/chain_am_pre.log
mkdir -p $A/logs $A/am
source $B/ops/env_ab.sh
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 AB_PLATFORM=projectb PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
echo "$(date '+%F %T') waiting for RESERVE_AM_DONE" >> $LOG
until grep -q RESERVE_AM_DONE $B/ops/logs/reserve_am.log; do
  [ -f $A/CHAIN_STOP ] && { echo "$(date '+%F %T') stop file" >> $LOG; exit 0; }
  sleep 60
done
sleep 30
U=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i 0)
N=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | grep -c "$U")
[ "$N" -ne 0 ] && { echo "$(date '+%F %T') GPU 0 not free ($N processes); stop" >> $LOG; exit 1; }
cd $A
R=$B/agentic-misalignment/results/qwen35_4b_am
$V -u units_am.py $R $B/ops/proxy_log/am.jsonl $A/am/units_pre.json --unlabeled > $A/logs/units_am_pre.log 2>&1
echo "$(date '+%F %T') units_pre rc=$?" >> $LOG
$V -u ab_regen.py stats am $A/am/units_pre.json $A/am/c2 > $A/logs/am_stats.log 2>&1
echo "$(date '+%F %T') stats rc=$?" >> $LOG
$V -u ab_jlens.py am $A/am/units_pre.json $A/am/jlens > $A/logs/am_jlens.log 2>&1
echo "$(date '+%F %T') jlens rc=$?" >> $LOG
echo "$(date '+%F %T') CHAIN_AM_PRE_DONE" >> $LOG
