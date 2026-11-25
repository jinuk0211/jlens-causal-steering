#!/bin/bash
source /home/project-b/LJW/tau2-steer/ToolAlignBench/ops/env_q9.sh
cd /home/project-b/LJW/tau2-steer/ToolAlignBench
PY=/home/project-b/LJW/tau2-steer/.venv/bin/python
L=ops/logs/q9_chain.log
$PY ops/analysis/tab_labels.py runner/results/qwen9-greedy ops/analysis_q9/labels > ops/logs/q9_labels.log 2>&1
echo "$(date '+%F %T') labels rc=$?" >> $L
JL_SPLIT=0/2 nice -n 5 $PY -u ops/analysis_q9/tab_jlens_q9.py runner/results/qwen9-greedy ops/analysis_q9/jlens_points_w0 > ops/logs/q9_jlens_w0.log 2>&1 &
P0=$!
sleep 30
JL_SPLIT=1/2 nice -n 5 $PY -u ops/analysis_q9/tab_jlens_q9.py runner/results/qwen9-greedy ops/analysis_q9/jlens_points_w1 > ops/logs/q9_jlens_w1.log 2>&1 &
P1=$!
wait $P0 $P1
if grep -q JLENS_POINTS_DONE ops/logs/q9_jlens_w0.log && grep -q JLENS_POINTS_DONE ops/logs/q9_jlens_w1.log; then
  $PY ops/analysis_q9/merge_points_q9.py >> $L 2>&1
  nice -n 10 $PY ops/analysis_q9/tab_analyze_q9.py > ops/logs/q9_analyze.log 2>&1
  echo "$(date '+%F %T') S3_S4_DONE analyze rc=$?" >> $L
else
  echo "$(date '+%F %T') jlens failed" >> $L
fi
