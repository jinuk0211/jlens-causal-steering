#!/bin/bash
source /home/project-b/LJW/tau2-steer/ToolAlignBench/ops/env_gemma.sh
cd /home/project-b/LJW/tau2-steer/ToolAlignBench
PY=/home/project-b/LJW/tau2-steer/.venv/bin/python
L=ops/logs/gemma_chain.log
C1PID=$1
while kill -0 $C1PID 2>/dev/null; do sleep 30; done
if ! grep -q CAUSAL1_DONE ops/logs/gemma_causal.log; then echo "$(date '+%F %T') S5 failed" >> $L; exit 1; fi
$PY ops/analysis_gemma/g1_split_g.py > ops/logs/gemma_g1.log 2>&1
echo "$(date '+%F %T') S5_DONE g1 rc=$?" >> $L
$PY ops/analysis_gemma/sample_g.py ops/analysis_gemma >> $L 2>&1
export C2_ONLY=/home/project-b/LJW/tau2-steer/ToolAlignBench/ops/analysis_gemma/causal2_sample.txt
nice -n 5 $PY -u ops/analysis_gemma/ta_causal2_g.py stats > ops/logs/gemma_causal2_stats.log 2>&1
if ! grep -q STATS_DONE ops/logs/gemma_causal2_stats.log; then echo "$(date '+%F %T') S6 stats failed" >> $L; exit 1; fi
echo "$(date '+%F %T') S6 stats done; 2 workers" >> $L
PIDS=""
for w in g0a g0b; do
  C2_EXTRA=1 C2_CTRL=1 C2_WID=$w nice -n 5 $PY -u ops/analysis_gemma/ta_causal2_g.py run 0 1 > ops/logs/gemma_causal2_$w.log 2>&1 &
  PIDS="$PIDS $!"
  sleep 40
done
wait $PIDS
C2_EXTRA=1 C2_CTRL=1 C2_SWEEP=1 C2_WID=sweep nice -n 5 $PY -u ops/analysis_gemma/ta_causal2_g.py run 0 1 > ops/logs/gemma_causal2_sweep.log 2>&1
$PY ops/analysis_gemma/ta_causal2_g.py report > ops/logs/gemma_causal2_report.log 2>&1
echo "$(date '+%F %T') G_S6_DONE" >> $L
