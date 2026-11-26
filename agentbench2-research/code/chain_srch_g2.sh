#!/bin/bash
# Overnight search, project-b GPU 2 lane (OVERNIGHT.md): dojo capture -> toolalign capture -> dojo sets -> distrib analyze (CPU,
# background) -> dojo worker -> AM worker.
B=/home/project-b/LJW/agentbench2
A=$B/ana
LOG=$A/logs/srch_g2.log
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=2 AB_PLATFORM=projectb
export PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
cd $A
lg() { echo "$(date '+%F %T') [g2] $*" >> $LOG; }
run() { local n=$1; shift; lg "start $n"; "$@" > $A/logs/srch_$n.log 2>&1; local rc=$?; lg "$n rc=$rc"; return $rc; }
lg "chain start"
[ -f distrib/dojo/CAPTURE_DONE ] || run cap_dojo $V -u ab_distrib.py capture dojo distrib || { lg SRCH_G2_FAILED; exit 1; }
[ -f distrib/toolalign/CAPTURE_DONE ] || run cap_toolalign $V -u ab_distrib.py capture toolalign distrib
[ -f distrib/toolalign/CAPTURE_DONE ] && [ ! -f search/toolalign/sets_ta.json ] && run sets_ta $V -u ab_search.py sets_ta toolalign
[ -f search/dojo/SETS_DONE ] || run sets_dojo $V -u ab_search.py sets dojo || { lg SRCH_G2_FAILED; exit 1; }
(
  until [ -f distrib/am/CAPTURE_DONE ] && [ -f distrib/dojo/CAPTURE_DONE ] && [ -f distrib/toolalign/CAPTURE_DONE ]; do
    [ -f $A/SRCH_STOP ] && exit 0; sleep 60; done
  [ -f distrib/report.md ] || CUDA_VISIBLE_DEVICES= run analyze $V -u ab_distrib.py analyze distrib
) &
PA=$!
bash srch_worker.sh dojo 2 2 24
bash srch_worker.sh am 2 2 24
wait $PA
lg SRCH_G2_DONE
