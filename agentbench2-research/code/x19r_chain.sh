#!/bin/bash
# X19r (PLAN.md Log 11-27 13:2x): slack units from the base run, residual-stream comparison, cross-fit arms, queue jobs.
B=/home/project-b/LJW/agentbench2
A=$B/ana
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID AB_PLATFORM=projectb PYTHONDONTWRITEBYTECODE=1
export TOKENIZERS_PARALLELISM=false CUDA_VISIBLE_DEVICES=0
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
cd $A
LG=logs/x19r_chain.log
say() { echo "$(date '+%F %T') $*" >> $LG; }
say "chain start"
until [ "$(grep -c 'done: - base slack attack' logs/x18_lanes.log)" -ge 4 ] || [ -f X18_STOP ]; do sleep 30; done
[ -f X18_STOP ] && { say STOP; exit 0; }
say "base slack attack done: $(find $B/runs/steer_base__x19/openai-compatible/slack -path '*important_instructions/injection_task_*.json' | wc -l) episodes"
if [ ! -f dojo/units_slack.json ]; then
  (cd $B && RENDER_LATER=1 $B/.venv/bin/python $A/units_dojo_x19.py $B/runs/steer_base__x19 /nonexistent $A/dojo/units_slack.json slack) > logs/x19r_units.log 2>&1
  say "units rc=$? $(tr -d '\n' < logs/x19r_units.log | cut -c1-400)"
  $V -u ab_xfit.py render dojo/units_slack.json > logs/x19r_render.log 2>&1
  say "render rc=$? $(tail -1 logs/x19r_render.log | cut -c1-200)"
fi
python3 ab_xfit.py reqparity dojo/units_slack.json logs/reqids_x19base_*.jsonl > logs/x19r_reqparity.log 2>&1
RC=$?
say "reqparity rc=$RC $(tail -2 logs/x19r_reqparity.log | tr -d '\n' | cut -c1-400)"
[ $RC -ne 0 ] && { say "CHAIN_STOPPED reqparity"; exit 1; }
until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 0)" -lt 37000 ]; do sleep 30; done
if [ ! -f ne/x19r_res.npz ]; then
  $V -u ab_xfit.py rescap dojo/units_slack.json ne/x19r_res.npz > logs/x19r_rescap.log 2>&1
  say "rescap rc=$? $(tail -1 logs/x19r_rescap.log | cut -c1-200)"
fi
$V -u ab_xfit.py resarms x19r ne/x19r_res.npz 41 43 > logs/x19r_arms.log 2>&1
RC=$?
say "resarms rc=$RC"
[ $RC -ne 0 ] && { say "CHAIN_STOPPED resarms"; exit 1; }
say "CHAIN_DONE"
