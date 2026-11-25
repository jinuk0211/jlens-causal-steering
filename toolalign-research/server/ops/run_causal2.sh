#!/bin/bash
source /home/project-b/LJW/tau2-steer/ToolAlignBench/ops/env.sh
cd /home/project-b/LJW/tau2-steer/ToolAlignBench
PY=/home/project-b/LJW/tau2-steer/.venv/bin/python
L=ops/logs/causal2_chain.log
echo "$(date '+%F %T') stats start" >> $L
CUDA_VISIBLE_DEVICES=2 nice -n 5 $PY -u ops/analysis/ta_causal2.py stats > ops/logs/causal2_stats.log 2>&1
if ! grep -q STATS_DONE ops/logs/causal2_stats.log; then echo "$(date '+%F %T') stats failed" >> $L; exit 1; fi
echo "$(date '+%F %T') stats done; launching workers on GPU 1 and GPU 2" >> $L
CUDA_VISIBLE_DEVICES=1 nice -n 5 $PY -u ops/analysis/ta_causal2.py run 0 2 > ops/logs/causal2_w0.log 2>&1 &
P0=$!
CUDA_VISIBLE_DEVICES=2 nice -n 5 $PY -u ops/analysis/ta_causal2.py run 1 2 > ops/logs/causal2_w1.log 2>&1 &
P1=$!
wait $P0 $P1
echo "$(date '+%F %T') workers exited (w0 $(grep -c RUN_DONE ops/logs/causal2_w0.log), w1 $(grep -c RUN_DONE ops/logs/causal2_w1.log))" >> $L
$PY ops/analysis/ta_causal2.py report > ops/logs/causal2_report.log 2>&1
echo "$(date '+%F %T') CAUSAL2_CHAIN_DONE" >> $L
