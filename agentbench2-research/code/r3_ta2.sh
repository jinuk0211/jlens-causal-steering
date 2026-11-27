#!/bin/bash
# R3-TA2 ToolAlign arms (PLAN.md "R3-TA2", user 11-27 19:1x): bash r3_ta2.sh GPU PLATFORM "REPS" B BUDGET
# For each replicate of REPS (one machine type per replicate), arms base, T2, rT2a, rT2b with the sets of r3/ta_sets2.json. base runs
# at once; the other arms wait for r3/TA_GO (or stop at r3/TA_STOP). Claims t2_<arm>_r<rep> under r3/claims; stop file r3/STOP2.
cd /home/project-b/LJW/agentbench2/ana
if [ "$2" = projectb ]; then
  source ../ops/env_ab.sh
  PY=/home/project-b/LJW/tau2-steer/.venv/bin/python
else
  . /workspace/cross_env.sh
  PY=$PYX
fi
export AB_PLATFORM=$2 CUDA_VISIBLE_DEVICES=$1 TA_SETS_FILE=ta_sets2.json PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
G=$1; B=${4:-12}; BUD=${5:-260000}
LG=logs/r3_ta2_g$G.log
mkdir -p r3/claims logs
say() { echo "$(date '+%F %T') ta2 gpu $G: $*" >> $LG; }
say "start reps $3, B $B, budget $BUD"
for rep in $3; do
  for arm in base T2 rT2a rT2b; do
    [ -e r3/STOP2 ] && { say "STOP2"; exit 0; }
    if [ "$arm" != base ]; then
      until [ -e r3/TA_GO ] || [ -e r3/TA_STOP ]; do [ -e r3/STOP2 ] && exit 0; sleep 60; done
      [ -e r3/TA_STOP ] && { say "TA_STOP: $(cat r3/TA_STOP)"; exit 0; }
    fi
    mkdir r3/claims/t2_${arm}_r$rep 2>/dev/null || continue
    say "tarun $arm r$rep start"
    TA_REPS=$rep TA_B=$B TA_BUDGET=$BUD $PY -u ab_r3.py tarun $arm >> logs/r3_ta2_${arm}_r$rep.log 2>&1
    say "tarun $arm r$rep end rc=$?"
    [ "$arm" = base ] && [ "$2" = projectb ] && $PY ab_r3.py tagate 1,2,3,4 6 >> $LG 2>&1
  done
done
say "exit"
