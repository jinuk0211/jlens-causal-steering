#!/bin/bash
source /home/project-b/LJW/tau2-steer/ToolAlignBench/ops/env.sh
cd /home/project-b/LJW/tau2-steer/ToolAlignBench
PY=/home/project-b/LJW/tau2-steer/.venv/bin/python
L=ops/logs/after_gen.log
[ -f ops/logs/jlens_points.log ] && mv ops/logs/jlens_points.log ops/logs/jlens_points_try_$(date +%H%M%S).log
nice -n 5 $PY -u ops/analysis/tab_jlens.py runner/results/qwen35-greedy ops/analysis/jlens_points > ops/logs/jlens_points.log 2>&1
if ! grep -q JLENS_POINTS_DONE ops/logs/jlens_points.log; then echo "$(date '+%F %T') jlens failed" >> $L; exit 1; fi
nice -n 10 $PY ops/analysis/tab_analyze.py > ops/logs/analyze.log 2>&1
echo "$(date '+%F %T') AFTER_GEN_DONE analyze rc=$?" >> $L
