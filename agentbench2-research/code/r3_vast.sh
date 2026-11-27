#!/bin/bash
# R3 on the vast boxes (PLAN.md "R3", user 11-27 18:2x: run now on the vast boxes). bash r3_vast.sh GPU PLATFORM
#   A4000 box (PLATFORM a4000, bf16): the AM part (capture, selection, smoke, four generation workers) and ToolAlign replicates 2-4.
#   2080 Ti box (PLATFORM t2080, fp16): ToolAlign capture, selection, smoke and replicate 1 (all four arms on one platform).
# Each GPU waits until it has had no compute process for 10 min (another session's jobs keep running), claims tasks with mkdir under
# r3/claims, and stops at r3/STOP. ta_sets.json is made on the 2080 Ti box and copied to the A4000 box by hand.
cd /home/project-b/LJW/agentbench2/ana
. /workspace/cross_env.sh
export AB_PLATFORM=$2 CUDA_VISIBLE_DEVICES=$1
G=$1
PY=$PYX
LG=logs/r3_vast_g$G.log
CL=r3/claims
mkdir -p $CL logs
say() { echo "$(date '+%F %T') gpu $G: $*" >> $LG; }
claim() { mkdir $CL/$1 2>/dev/null; }
run() { say "start $*"; $PY -u ab_r3.py "$@" >> logs/r3_$1_g$G.log 2>&1; local rc=$?; say "end $* rc=$rc"; return $rc; }
stop() { [ -e r3/STOP ]; }
stop && exit 0
say "waiting for GPU $G (no compute process for 10 min)"
$PY -u ab_r3.py wait $G 10 >> $LG 2>&1
stop && exit 0
if [ "$2" = a4000 ]; then
  if claim amcap; then run amcap || { say "amcap failed"; touch r3/AM_FAILED; }; fi
  until [ -e r3/AMCAP_DONE ] || [ -e r3/AM_FAILED ]; do stop && exit 0; sleep 30; done
  if claim amsets; then run amsets || { say "amsets failed"; touch r3/AM_FAILED; }; fi
  until [ -e ne/steer_am/arms_r3am.json ] || [ -e r3/AM_FAILED ]; do stop && exit 0; sleep 30; done
  if claim amsmoke; then run amsmoke && touch r3/AMSMOKE_OK || { say "amsmoke failed"; touch r3/AM_FAILED; }; fi
  until [ -e r3/AMSMOKE_OK ] || [ -e r3/AM_FAILED ]; do stop && exit 0; sleep 30; done
  MAIN="leaking_explicit-america_none,leaking_explicit-america_replacement"
  W2="blackmail_explicit-america_none,blackmail_explicit-america_replacement,blackmail_none-none_none,blackmail_none-none_replacement,leaking_none-none_none"
  W3="leaking_none-none_replacement,murder_explicit-america_none,murder_explicit-america_replacement,murder_none-none_none,murder_none-none_replacement"
  if [ ! -e r3/AM_FAILED ]; then
    for w in w1a w1b w2 w3; do
      stop && exit 0
      claim am_$w || continue
      case $w in
        w1a) C=$MAIN; OFF=0; NS=12;; w1b) C=$MAIN; OFF=12; NS=12;; w2) C=$W2; OFF=0; NS=1000;; w3) C=$W3; OFF=0; NS=1000;;
      esac
      say "amrun $w start"
      AB_CONDS=$C AB_SEED_OFF=$OFF AB_SEEDS=$NS AB_ROWS_SUFFIX=_a4$w $PY -u ab_r3.py amrun >> logs/r3_amrun_$w.log 2>&1
      say "amrun $w end rc=$?"
      touch r3/AMRUN_DONE_$w
    done
  fi
  if [ -e r3/AMRUN_DONE_w1a ] && [ -e r3/AMRUN_DONE_w1b ] && [ -e r3/AMRUN_DONE_w2 ] && [ -e r3/AMRUN_DONE_w3 ] && claim amreport; then
    $PY ab_r3.py amreport > r3/am_report.log 2>&1
    say "amreport written"
  fi
  REPS="2 3 4"
else
  if claim tacap; then run tacap || { say "tacap failed"; touch r3/TA_FAILED; exit 1; }; fi
  if claim tasets; then run tasets || { say "tasets failed"; touch r3/TA_FAILED; exit 1; }; fi
  REPS="1"
fi
say "ToolAlign: waiting for r3/ta_sets.json"
until [ -e r3/ta_sets.json ]; do stop && exit 0; sleep 60; done
if claim tasmoke; then TA_SMOKE=1 run tarun T1024 && touch r3/TASMOKE_OK || { say "tasmoke failed"; touch r3/TA_FAILED; }; fi
until [ -e r3/TASMOKE_OK ] || [ -e r3/TA_FAILED ]; do stop && exit 0; sleep 30; done
[ -e r3/TA_FAILED ] && exit 1
if [ "$2" = a4000 ]; then B=8; BUD=140000; else B=12; BUD=260000; fi
for rep in $REPS; do
  for arm in base T1024 rT1 rT2; do
    stop && exit 0
    claim ta_${arm}_r$rep || continue
    TA_REPS=$rep TA_B=$B TA_BUDGET=$BUD run tarun $arm || say "tarun $arm r$rep rc non-zero"
  done
done
say "lane exit"
