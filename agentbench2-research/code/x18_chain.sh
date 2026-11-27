#!/bin/bash
# X18 / X19 chain (PLAN.md Log 11-27), GPU 0: captures and arm files that the queued clamp jobs wait for.
#   1. banking + travel: capture with per-fold token statistics, parity check against the original capture, arms_x18.json
#      (x = picked on fold 1, tested on the fold-0 user tasks).
#   2. slack: after the four base attack slices are done, units from the request logs, capture, arms_x19.json
#      (s0 = picked on slack fold 0, s1 = picked on slack fold 1).
B=/home/project-b/LJW/agentbench2
A=$B/ana
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID AB_PLATFORM=projectb PYTHONDONTWRITEBYTECODE=1
export TOKENIZERS_PARALLELISM=false CUDA_VISIBLE_DEVICES=0
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
cd $A
LG=logs/x18_chain.log
say() { echo "$(date '+%F %T') $*" >> $LG; }
say "chain start"
if [ ! -f ne/steer_dojo/arms_x18.json ]; then
  if [ ! -f ne/read_xfit_dojo.npz ]; then
    $V -u ab_xfit.py cap dojo/units.json ne/read_xfit_dojo.npz > logs/x18_cap_dojo.log 2>&1
    say "cap dojo rc=$?"
  fi
  $V -u ab_xfit.py check ne/read_xfit_dojo.npz > logs/x18_check.log 2>&1
  RC=$?
  say "check rc=$RC $(tail -1 logs/x18_check.log)"
  if [ $RC -ne 0 ]; then say "CHAIN_STOPPED parity check failed"; exit 1; fi
  $V -u ab_xfit.py arms x18 ne/read_xfit_dojo.npz x:1 31 > logs/x18_arms.log 2>&1
  say "arms x18 rc=$?"
fi
until [ "$(grep -c 'done: - base slack attack' logs/x18_lanes.log 2>/dev/null)" -ge 4 ] || [ -f X18_STOP ]; do sleep 60; done
[ -f X18_STOP ] && { say "STOP"; exit 0; }
say "slack base attack slices done: $(find $B/runs/steer_base__x19/openai-compatible/slack -path '*important_instructions/injection_task_*.json' | wc -l) episodes"
if [ ! -f ne/steer_dojo/arms_x19.json ]; then
  $B/.venv/bin/python - > logs/x19_tasks.log 2>&1 <<'PY'
import json
from agentdojo.task_suite.load_suites import get_suites
s = get_suites("v1.2.2")["slack"]
out = {"suite": "slack", "user": {k: v.PROMPT for k, v in s.user_tasks.items()}, "inj": {k: v.GOAL for k, v in s.injection_tasks.items()}}
json.dump(out, open("/home/project-b/LJW/agentbench2/ana/dojo/slack_tasks.json", "w"))
print(len(out["user"]), len(out["inj"]))
PY
  say "slack tasks rc=$? $(tail -1 logs/x19_tasks.log)"
  $V -u ab_xfit.py slackunits dojo/slack_tasks.json dojo/units_slack.json logs/reqids_x19base_*.jsonl > logs/x19_units.log 2>&1
  say "slack units rc=$? $(tail -2 logs/x19_units.log | head -1 | cut -c1-300)"
  $V -u ab_xfit.py cap dojo/units_slack.json ne/read_xfit_slack.npz > logs/x19_cap_slack.log 2>&1
  say "cap slack rc=$?"
  $V -u ab_xfit.py arms x19 ne/read_xfit_slack.npz s0:0,s1:1 37 > logs/x19_arms.log 2>&1
  say "arms x19 rc=$?"
fi
say "CHAIN_DONE"
