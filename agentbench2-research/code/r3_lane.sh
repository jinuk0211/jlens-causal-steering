#!/bin/bash
# R3 lane (PLAN.md "R3"): bash r3_lane.sh GPU. Waits until the GPU has had no compute process and no CROSS process for 10 min
# (user 11-27: start after the other session's run), then does the R3 tasks in order. Claims are directories under r3/claims, so
# two lanes never run the same task. GPU 0 runs the AM part with three workers; any lane then runs the ToolAlign arms.
cd /home/project-b/LJW/agentbench2/ana
source ../ops/env_ab.sh
export AB_PLATFORM=projectb CUDA_VISIBLE_DEVICES=$1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
G=$1
PY=/home/project-b/LJW/tau2-steer/.venv/bin/python
LG=logs/r3_lane$G.log
CL=r3/claims
mkdir -p $CL logs
say() { echo "$(date '+%F %T') lane $G: $*" >> $LG; }
claim() { mkdir $CL/$1 2>/dev/null; }
run() { say "start $*"; $PY -u ab_r3.py "$@" >> logs/r3_$1_g$G.log 2>&1; local rc=$?; say "end $* rc=$rc"; return $rc; }
[ -e r3/STOP ] && exit 0
say "waiting for GPU $G (no compute process and no CROSS process for 10 min)"
$PY -u ab_r3.py wait $G 10 >> $LG 2>&1
[ -e r3/STOP ] && exit 0
if [ "$G" = 0 ]; then
  if claim amcap; then run amcap || { say "amcap failed"; exit 1; }; fi
  until [ -e r3/AMCAP_DONE ]; do sleep 60; done
  if claim amsets; then run amsets || { say "amsets failed"; exit 1; }; fi
  until [ -e ne/steer_am/arms_r3am.json ]; do sleep 60; done
  if claim amsmoke; then run amsmoke || { say "amsmoke failed; AM part stopped"; touch r3/AM_FAILED; }; fi
  if [ ! -e r3/AM_FAILED ] && claim amrun; then
    say "AM workers start"
    W1="leaking_explicit-america_none,leaking_explicit-america_replacement"
    W2="blackmail_explicit-america_none,blackmail_explicit-america_replacement,blackmail_none-none_none,blackmail_none-none_replacement,leaking_none-none_none"
    W3="leaking_none-none_replacement,murder_explicit-america_none,murder_explicit-america_replacement,murder_none-none_none,murder_none-none_replacement"
    for w in 1 2 3; do
      eval "CS=\$W$w"
      AB_CONDS=$CS AB_ROWS_SUFFIX=_w$w $PY -u ab_r3.py amrun >> logs/r3_amrun_w$w.log 2>&1 &
      sleep 90
    done
    wait
    say "AM workers done"
    $PY ab_r3.py amreport > r3/am_report.log 2>&1
    say "amreport written"
  fi
fi
# ToolAlign: capture and selection once, then arms until none is left.
if claim tacap; then run tacap || { say "tacap failed"; exit 1; }; fi
until [ -e r3/TACAP_DONE ]; do [ -e r3/STOP ] && exit 0; sleep 60; done
if claim tasets; then run tasets || { say "tasets failed"; exit 1; }; fi
until [ -e r3/ta_sets.json ]; do [ -e r3/STOP ] && exit 0; sleep 60; done
if claim tasmoke; then TA_SMOKE=1 run tarun T1024 || { say "tasmoke failed"; touch r3/TA_FAILED; }; fi
until grep -q TASMOKE_OK logs/r3_tarun_g*.log 2>/dev/null || [ -e r3/TA_FAILED ]; do [ -e r3/STOP ] && exit 0; sleep 30; done
[ -e r3/TA_FAILED ] && exit 1
for arm in base T1024 rT1 rT2; do
  [ -e r3/STOP ] && exit 0
  if claim ta_$arm; then
    if [ "$G" = 0 ]; then B=24; BUD=520000; else B=12; BUD=260000; fi
    TA_B=$B TA_BUDGET=$BUD run tarun $arm || say "tarun $arm rc non-zero"
  fi
done
if [ -e r3/ta_eps/base/DONE ] && [ -e r3/ta_eps/T1024/DONE ] && [ -e r3/ta_eps/rT1/DONE ] && [ -e r3/ta_eps/rT2/DONE ] && claim tareport; then
  $PY ab_r3.py tareport > r3/ta_report.log 2>&1
  say "tareport written"
fi
say "lane exit"
