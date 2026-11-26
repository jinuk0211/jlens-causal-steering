#!/bin/bash
# Overnight search worker (OVERNIGHT.md): BENCH WID GPU BATCH. Runs s1, then s2 if advance1 says so, then t1, with claims shared
# across workers; after each stage it runs the idempotent decide step. SRCH_STOP in ana/ stops it between stages.
B=/home/project-b/LJW/agentbench2
A=$B/ana
BENCH=$1
W=$2
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=$3 AB_PLATFORM=projectb
export PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false AB_BATCH=$4 AB_ROWS_SUFFIX=_w$W
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
S=$A/search/$BENCH
LOG=$A/logs/srch_g$3.log
cd $A
lg() { echo "$(date '+%F %T') [$BENCH w$W] $*" >> $LOG; }
until [ -f $S/SETS_DONE ]; do [ -f $A/SRCH_STOP ] && exit 0; sleep 60; done
for TAG in s1 s2 t1; do
  [ -f $A/SRCH_STOP ] && { lg "stop file"; exit 0; }
  if [ $TAG = s2 ]; then
    until [ -f $S/advance1.json ]; do [ -f $A/SRCH_STOP ] && exit 0; sleep 60; done
    grep -q '"stage": "s2"' $S/advance1.json || continue
  fi
  if [ $TAG = t1 ]; then
    until grep -qs '"stage": "t1"' $S/advance1.json $S/advance2.json; do [ -f $A/SRCH_STOP ] && exit 0; sleep 60; done
  fi
  if [ ! -f $S/${TAG}_DONE ]; then
    lg "run $TAG"
    $V -u ab_search.py run $BENCH $TAG >> $A/logs/srch_${BENCH}_${TAG}_w$W.log 2>&1
    lg "$TAG rc=$?"
  fi
  [ -f $S/${TAG}_DONE ] || { lg "$TAG not done, worker exits"; exit 1; }
  $V -u ab_search.py decide $BENCH $TAG >> $A/logs/srch_${BENCH}_decide.log 2>&1
  lg "decide $TAG rc=$?"
done
lg "worker done"
