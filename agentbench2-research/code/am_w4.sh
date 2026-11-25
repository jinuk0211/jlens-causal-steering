#!/bin/bash
# Fourth AM worker on project-b GPU 0 (user 11-25 20:4x: use the free VRAM; GPU 0 had ~20 GB free). Sweep, then TEST.
# step of the AM chain through unit claims (ab_regen.run_rows); rows go to rows_<tag>_w2.jsonl.
# process on GPU 2.
B=/home/project-b/LJW/agentbench2
A=$B/ana
LOG=$A/logs/am_w4.log
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 AB_PLATFORM=projectb
export PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false AB_BATCH=${AB_BATCH:-24} AB_ROWS_SUFFIX=_w4
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
D=$A/am
cd $A
waitfor() {
  echo "$(date '+%F %T') waiting for $1" >> $LOG
  until [ -f $D/$1 ]; do
    [ -f $A/CHAIN_STOP ] && { echo "$(date '+%F %T') stop file" >> $LOG; exit 0; }
    sleep 60
  done
}
run() {
  local name=$1; shift
  echo "$(date '+%F %T') start $name" >> $LOG
  "$@" > $A/logs/am_w4_$name.log 2>&1
  echo "$(date '+%F %T') $name rc=$?" >> $LOG
}
run sweep $V -u ab_regen.py sweep am $D/units.json $D/c2
waitfor done_band
run test $V -u ab_regen.py test am $D/units.json $D/c2
echo "$(date '+%F %T') AM_W2_DONE" >> $LOG
