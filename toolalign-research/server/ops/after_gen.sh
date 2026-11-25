#!/bin/bash
source /home/project-b/LJW/tau2-steer/ToolAlignBench/ops/env.sh
T=/home/project-b/LJW/tau2-steer/ToolAlignBench
L=$T/ops/logs/after_gen.log
SV=2647653
EC=2649907
PY=/home/project-b/LJW/tau2-steer/.venv/bin/python
cd $T
echo "$(date '+%F %T') waiting for FULL_DONE" >> $L
until grep -q FULL_DONE ops/logs/full.log; do sleep 30; done
echo "$(date '+%F %T') generation done; stopping vLLM serve=$SV enginecore=$EC" >> $L
kill $SV 2>/dev/null
sleep 10
kill $EC 2>/dev/null
sleep 10
used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 2)
echo "$(date '+%F %T') GPU 2 used $used MiB" >> $L
if [ "$used" -ge 2000 ]; then echo "$(date '+%F %T') GPU 2 not free; abort" >> $L; exit 1; fi
$PY ops/analysis/tab_labels.py runner/results/qwen35-greedy ops/analysis/labels > ops/logs/labels.log 2>&1
echo "$(date '+%F %T') labels rc=$?" >> $L
nice -n 5 $PY -u ops/analysis/tab_jlens.py runner/results/qwen35-greedy ops/analysis/jlens_points > ops/logs/jlens_points.log 2>&1
if ! grep -q JLENS_POINTS_DONE ops/logs/jlens_points.log; then echo "$(date '+%F %T') jlens failed" >> $L; exit 1; fi
nice -n 10 $PY ops/analysis/tab_analyze.py > ops/logs/analyze.log 2>&1
echo "$(date '+%F %T') AFTER_GEN_DONE analyze rc=$?" >> $L
