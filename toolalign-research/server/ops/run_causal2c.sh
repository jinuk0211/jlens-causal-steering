#!/bin/bash
source /home/project-b/LJW/tau2-steer/ToolAlignBench/ops/env.sh
cd /home/project-b/LJW/tau2-steer/ToolAlignBench
PY=/home/project-b/LJW/tau2-steer/.venv/bin/python
L=ops/logs/causal2_chain.log
echo "$(date '+%F %T') 2c: dynamic workers (main + 2b configs) on GPU 0,1,2 x2" >> $L
PIDS=""
for spec in 1:g1a 2:g2a 0:g0a 1:g1b 2:g2b 0:g0b; do
  g=${spec%%:*}; w=${spec##*:}
  C2_EXTRA=1 C2_WID=$w CUDA_VISIBLE_DEVICES=$g nice -n 5 $PY -u ops/analysis/ta_causal2.py run 0 1 > ops/logs/causal2c_$w.log 2>&1 &
  PIDS="$PIDS $!"
  sleep 20
done
wait $PIDS
echo "$(date '+%F %T') 2c: dynamic workers exited; sweep on GPU 2" >> $L
C2_EXTRA=1 C2_SWEEP=1 C2_WID=sweep CUDA_VISIBLE_DEVICES=2 nice -n 5 $PY -u ops/analysis/ta_causal2.py run 0 1 > ops/logs/causal2c_sweep.log 2>&1
$PY ops/analysis/ta_causal2.py report > ops/logs/causal2_report.log 2>&1
echo "$(date '+%F %T') CAUSAL2C_DONE" >> $L
