#!/bin/bash
source /home/project-b/LJW/tau2-steer/ToolAlignBench/ops/env_q9.sh
cd /home/project-b/LJW/tau2-steer/ToolAlignBench
PY=/home/project-b/LJW/tau2-steer/.venv/bin/python
L=ops/logs/q9_chain.log
bash ops/s3_q9.sh
if ! grep -q S3_S4_DONE $L; then echo "$(date '+%F %T') Q S3/S4 failed" >> $L; exit 1; fi
CAUSAL_LIMIT=3 $PY -u ops/analysis_q9/ta_causal_q9.py > ops/logs/q9_causal_smoke.log 2>&1
if ! grep -q "base flips (should be 0): 0" ops/logs/q9_causal_smoke.log; then echo "$(date '+%F %T') Q S5 smoke failed (base flips or crash)" >> $L; exit 1; fi
echo "$(date '+%F %T') Q S5 smoke ok: $(grep 'baseline drift' ops/logs/q9_causal_smoke.log | head -1)" >> $L
nice -n 5 $PY -u ops/analysis_q9/ta_causal_q9.py > ops/logs/q9_causal.log 2>&1
if ! grep -q CAUSAL1_DONE ops/logs/q9_causal.log; then echo "$(date '+%F %T') Q S5 failed" >> $L; exit 1; fi
$PY ops/analysis_q9/g1_split_q9.py > ops/logs/q9_g1.log 2>&1
echo "$(date '+%F %T') Q S5_DONE" >> $L
NT=$($PY -c "import json;print(len(json.load(open('ops/analysis_q9/causal/units.json'))['targets']))")
if [ "$NT" -gt 90 ]; then
  $PY ops/analysis_q9/sample_q9.py ops/analysis_q9 >> $L 2>&1
  export C2_ONLY=/home/project-b/LJW/tau2-steer/ToolAlignBench/ops/analysis_q9/causal2_sample.txt
  echo "$(date '+%F %T') Q targets $NT > 90: stratified sample" >> $L
fi
nice -n 5 $PY -u ops/analysis_q9/ta_causal2_q9.py stats > ops/logs/q9_causal2_stats.log 2>&1
if ! grep -q STATS_DONE ops/logs/q9_causal2_stats.log; then echo "$(date '+%F %T') Q S6 stats failed" >> $L; exit 1; fi
echo "$(date '+%F %T') Q S6 stats done; 2 workers" >> $L
PIDS=""
for w in q0a q0b; do
  C2_EXTRA=1 C2_CTRL=1 C2_WID=$w nice -n 5 $PY -u ops/analysis_q9/ta_causal2_q9.py run 0 1 > ops/logs/q9_causal2_$w.log 2>&1 &
  PIDS="$PIDS $!"
  sleep 60
done
wait $PIDS
C2_EXTRA=1 C2_CTRL=1 C2_SWEEP=1 C2_WID=sweep nice -n 5 $PY -u ops/analysis_q9/ta_causal2_q9.py run 0 1 > ops/logs/q9_causal2_sweep.log 2>&1
$PY ops/analysis_q9/ta_causal2_q9.py report > ops/logs/q9_causal2_report.log 2>&1
echo "$(date '+%F %T') Q_S6_DONE" >> $L
