#!/bin/bash
source /home/project-b/LJW/tau2-steer/ToolAlignBench/ops/env_gemma.sh
cd /home/project-b/LJW/tau2-steer/ToolAlignBench
PY=/home/project-b/LJW/tau2-steer/.venv/bin/python
L=ops/logs/gemma_chain.log
$PY ops/analysis/tab_labels.py runner/results/gemma4-greedy ops/analysis_gemma/labels > ops/logs/gemma_labels.log 2>&1
echo "$(date '+%F %T') labels rc=$?" >> $L
JL_SPLIT=0/2 nice -n 5 $PY -u ops/analysis_gemma/tab_jlens_g.py runner/results/gemma4-greedy ops/analysis_gemma/jlens_points_w0 > ops/logs/gemma_jlens_w0.log 2>&1 &
P0=$!
sleep 30
JL_SPLIT=1/2 nice -n 5 $PY -u ops/analysis_gemma/tab_jlens_g.py runner/results/gemma4-greedy ops/analysis_gemma/jlens_points_w1 > ops/logs/gemma_jlens_w1.log 2>&1 &
P1=$!
wait $P0 $P1
if grep -q JLENS_POINTS_DONE ops/logs/gemma_jlens_w0.log && grep -q JLENS_POINTS_DONE ops/logs/gemma_jlens_w1.log; then
  $PY ops/analysis_gemma/merge_points_g.py >> $L 2>&1
  nice -n 10 $PY ops/analysis_gemma/tab_analyze_g.py > ops/logs/gemma_analyze.log 2>&1
  echo "$(date '+%F %T') S3_S4_DONE analyze rc=$?" >> $L
else
  echo "$(date '+%F %T') jlens failed" >> $L
fi
