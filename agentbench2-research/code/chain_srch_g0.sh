#!/bin/bash
# Overnight search, project-b GPU 0 lane (OVERNIGHT.md): AM capture -> AM sets -> 2 AM workers -> distrib transfer.
B=/home/project-b/LJW/agentbench2
A=$B/ana
LOG=$A/logs/srch_g0.log
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 AB_PLATFORM=projectb
export PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
cd $A
lg() { echo "$(date '+%F %T') [g0] $*" >> $LOG; }
run() { local n=$1; shift; lg "start $n"; "$@" > $A/logs/srch_$n.log 2>&1; local rc=$?; lg "$n rc=$rc"; return $rc; }
lg "chain start"
[ -f distrib/am/CAPTURE_DONE ] || run cap_am $V -u ab_distrib.py capture am distrib || { lg SRCH_G0_FAILED; exit 1; }
[ -f search/am/SETS_DONE ] || run sets_am $V -u ab_search.py sets am || { lg SRCH_G0_FAILED; exit 1; }
bash srch_worker.sh am 0a 0 32 &
P1=$!
sleep 120
bash srch_worker.sh am 0b 0 32 &
P2=$!
wait $P1 $P2
lg "AM workers done"
until [ -f distrib/am/CAPTURE_DONE ] && [ -f distrib/dojo/CAPTURE_DONE ] && [ -f distrib/toolalign/CAPTURE_DONE ]; do
  [ -f $A/SRCH_STOP ] && exit 0; sleep 60; done
[ -f distrib/transfer.md ] || run transfer $V -u ab_distrib.py transfer distrib
lg SRCH_G0_DONE
