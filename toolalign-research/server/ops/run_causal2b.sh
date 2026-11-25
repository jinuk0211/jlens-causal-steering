#!/bin/bash
source /home/project-b/LJW/tau2-steer/ToolAlignBench/ops/env.sh
cd /home/project-b/LJW/tau2-steer/ToolAlignBench
PY=/home/project-b/LJW/tau2-steer/.venv/bin/python
L=ops/logs/causal2_chain.log
until grep -q CAUSAL2_CHAIN_DONE $L; do sleep 30; done
cp ops/analysis/causal2/report.md ops/analysis/causal2/report_main.md
echo "$(date '+%F %T') 2b: launching C2_EXTRA workers" >> $L
C2_EXTRA=1 CUDA_VISIBLE_DEVICES=1 nice -n 5 $PY -u ops/analysis/ta_causal2.py run 0 2 > ops/logs/causal2b_w0.log 2>&1 &
P0=$!
C2_EXTRA=1 CUDA_VISIBLE_DEVICES=2 nice -n 5 $PY -u ops/analysis/ta_causal2.py run 1 2 > ops/logs/causal2b_w1.log 2>&1 &
P1=$!
wait $P0 $P1
$PY ops/analysis/ta_causal2.py report > ops/logs/causal2_report.log 2>&1
echo "$(date '+%F %T') CAUSAL2B_DONE" >> $L
