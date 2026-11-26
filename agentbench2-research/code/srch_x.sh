#!/bin/bash
# Exploratory stages (OVERNIGHT.md X1-X3, 사후): BENCH WID GPU BATCH TAG [TAG...]. Waits for the bench's t1_DONE, then runs each
# tag with shared claims, then writes the report. SRCH_STOP in ana/ stops it between tags.
B=/home/project-b/LJW/agentbench2
A=$B/ana
BENCH=$1
W=$2
G=$3
BS=$4
shift 4
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=$G AB_PLATFORM=projectb
export PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false AB_BATCH=$BS AB_ROWS_SUFFIX=_x$W
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
S=$A/search/$BENCH
LOG=$A/logs/srch_g$G.log
cd $A
lg() { echo "$(date '+%F %T') [$BENCH x$W] $*" >> $LOG; }
until [ -f $S/t1_DONE ]; do [ -f $A/SRCH_STOP ] && exit 0; sleep 60; done
for TAG in "$@"; do
  [ -f $A/SRCH_STOP ] && { lg "stop file"; exit 0; }
  if [ ! -f $S/${TAG}_DONE ]; then
    lg "run $TAG"
    $V -u $A/ab_search.py run $BENCH $TAG >> $A/logs/srch_${BENCH}_${TAG}_x$W.log 2>&1
    lg "$TAG rc=$?"
  fi
  $V -u $A/ab_search.py report $BENCH >> $A/logs/srch_${BENCH}_decide.log 2>&1
done
lg "x worker done"
