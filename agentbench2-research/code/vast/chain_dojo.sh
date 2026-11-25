#!/bin/bash
# AgentDojo analyses on the vast box (PLAN.md S3-S7, then N1/N2), fp32 split over both 1080 Ti, same platform as the
# generation. Waits for DOJO_ALL_DONE. Each step runs once (done flag) and any failure stops the chain.
W=/workspace/agentbench2
A=$W/ana
LOG=$A/logs/chain_dojo.log
mkdir -p $A/logs $A/dojo
export HF_HOME=/workspace/.hf_home HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True AB_PLATFORM=vast AB_BATCH=${AB_BATCH:-8}
export PYTHONPATH=/workspace/fsteer/jlens-causal-steering/src
V=$W/.venv/bin/python
cd $A
echo "$(date '+%F %T') waiting for DOJO_ALL_DONE" >> $LOG
until grep -q DOJO_ALL_DONE $W/runs/dojo_chain.log; do
  [ -f $A/CHAIN_STOP ] && { echo "$(date '+%F %T') stop file" >> $LOG; exit 0; }
  sleep 60
done
step() {
  local name=$1; shift
  [ -f $A/dojo/done_$name ] && { echo "$(date '+%F %T') $name already done" >> $LOG; return 0; }
  echo "$(date '+%F %T') start $name" >> $LOG
  "$@" > $A/logs/dojo_$name.log 2>&1
  local rc=$?
  echo "$(date '+%F %T') $name rc=$rc" >> $LOG
  [ $rc -ne 0 ] && { echo "$(date '+%F %T') CHAIN_DOJO_FAILED at $name" >> $LOG; exit 1; }
  touch $A/dojo/done_$name
}
D=$A/dojo
step units $V -u units_dojo.py $W/runs/qwen35_4b $W/runs/qwen35_4b/trace.jsonl $D/units.json
step behavior $V -u ab_behavior.py dojo $W/runs/qwen35_4b $W/runs/qwen35_4b_noattack $D/units.json $D/behavior.md
step jlens $V -u ab_jlens.py dojo $D/units.json $D/jlens
step analyze $V -u ab_analyze.py $D/jlens $D/jlens_report $D/units.json
step stats $V -u ab_regen.py stats dojo $D/units.json $D/c2
step causal1 $V -u ab_causal1.py $D/jlens $D/units.json $D/c1
step sweep $V -u ab_regen.py sweep dojo $D/units.json $D/c2
step band $V -u ab_regen.py band dojo $D/units.json $D/c2
step test $V -u ab_regen.py test dojo $D/units.json $D/c2
step report $V -u ab_regen.py report dojo $D/units.json $D/c2
step n1 $V -u ab_n1.py $A/n1
step n2fit $V -u ab_n2.py fit dojo $D/units.json $D/c2 $A/n1/n1_neurons.json $D/n2
step n2tune $V -u ab_n2.py tune dojo $D/units.json $D/c2 $A/n1/n1_neurons.json $D/n2
step n2test $V -u ab_n2.py test dojo $D/units.json $D/c2 $A/n1/n1_neurons.json $D/n2
step n2report $V -u ab_n2.py report dojo $D/units.json $D/c2 $A/n1/n1_neurons.json $D/n2
echo "$(date '+%F %T') CHAIN_DOJO_DONE" >> $LOG
