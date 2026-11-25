#!/bin/bash
# AgentDojo CAUSAL-2 path on project-b GPU 0 (bf16, same platform as the vLLM generation): units, behavior, stats, sweep, band, test, report.
B=/home/project-b/LJW/agentbench2
A=$B/ana
LOG=$A/logs/chain_dojo_pb.log
mkdir -p $A/logs $A/dojo
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 AB_PLATFORM=projectb PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false
export AB_BATCH=${AB_BATCH:-16}
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
VA=$B/.venv/bin/python
D=$A/dojo
cd $A
echo "$(date '+%F %T') waiting: DOJO_VLLM_DONE" >> $LOG
until grep -q DOJO_VLLM_DONE $B/ops/logs/dojo_vllm.log 2>/dev/null; do
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
  [ $rc -ne 0 ] && { echo "$(date '+%F %T') CHAIN_DOJO_PB_FAILED at $name" >> $LOG; exit 1; }
  touch $D/done_$name
}
step units $VA -u units_dojo.py $B/runs/qwen35_4b $B/ops/proxy_log/dojo.jsonl $D/units.json
step behavior $VA -u ab_behavior.py dojo $B/runs/qwen35_4b $B/runs/qwen35_4b_noattack $D/units.json $D/behavior.md
step stats $V -u ab_regen.py stats dojo $D/units.json $D/c2
step sweep $V -u ab_regen.py sweep dojo $D/units.json $D/c2
step band $V -u ab_regen.py band dojo $D/units.json $D/c2
step test $V -u ab_regen.py test dojo $D/units.json $D/c2
step report $V -u ab_regen.py report dojo $D/units.json $D/c2
echo "$(date '+%F %T') CHAIN_DOJO_PB_DONE" >> $LOG
