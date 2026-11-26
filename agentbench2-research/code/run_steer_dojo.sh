#!/bin/bash
# X12 (OVERNIGHT.md, 사후): AgentDojo full episodes through ab_serve_steer.py. usage: bash run_steer_dojo.sh ARM PORT GPU
# TEST-fold user tasks (fold-1 groups of ana/dojo/units.json), important_instructions attack, then the same user tasks
# without an attack. Results: runs/steer_<ARM>[_noattack]. Stops its own server by pid at the end.
ARM=$1
PORT=$2
G=$3
B=/home/project-b/LJW/agentbench2
A=$B/ana
LOG=$A/logs/steer_dojo_$ARM.log
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=$G AB_PLATFORM=projectb
export PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false AB_ARM=$ARM AB_PORT=$PORT
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
cd $A
echo "$(date '+%F %T') start server $ARM on GPU $G port $PORT" >> $LOG
setsid $V -u $A/ab_serve_steer.py > $A/logs/serve_steer_$ARM.out 2>&1 < /dev/null &
SV=$!
for i in $(seq 1 60); do curl -sf http://127.0.0.1:$PORT/v1/models > /dev/null && break; sleep 10; done
curl -sf http://127.0.0.1:$PORT/v1/models > /dev/null || { echo "$(date '+%F %T') server did not come up" >> $LOG; kill $SV; exit 1; }
echo "$(date '+%F %T') server up (pid $SV)" >> $LOG
export OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:$PORT/v1 OPENAI_COMPATIBLE_API_KEY=local
cd $B
for SUITE in banking travel; do
  UT=$($V -c "
import json
U = json.load(open('$A/dojo/units.json'))
ts = sorted({u['user_task'] for u in U if u['suite'] == '$SUITE' and u['fold'] == 1}, key=lambda s: int(s.split('_')[-1]))
print(' '.join('-ut ' + t for t in ts))")
  echo "$(date '+%F %T') $SUITE attack: $UT" >> $LOG
  [ -f $A/STEER_STOP ] && break
  $B/.venv/bin/python -m agentdojo.scripts.benchmark --model OPENAI_COMPATIBLE --model-id Qwen/Qwen3.5-4B --benchmark-version v1.2.2 \
    -s $SUITE $UT --attack important_instructions --logdir runs/steer_$ARM > $A/logs/steer_dojo_${ARM}_${SUITE}_attack.log 2>&1
  echo "$(date '+%F %T') $SUITE attack rc=$?" >> $LOG
done
for SUITE in banking travel; do
  UT=$($V -c "
import json
U = json.load(open('$A/dojo/units.json'))
ts = sorted({u['user_task'] for u in U if u['suite'] == '$SUITE' and u['fold'] == 1}, key=lambda s: int(s.split('_')[-1]))
print(' '.join('-ut ' + t for t in ts))")
  [ -f $A/STEER_STOP ] && break
  $B/.venv/bin/python -m agentdojo.scripts.benchmark --model OPENAI_COMPATIBLE --model-id Qwen/Qwen3.5-4B --benchmark-version v1.2.2 \
    -s $SUITE $UT --logdir runs/steer_${ARM}_noattack > $A/logs/steer_dojo_${ARM}_${SUITE}_noattack.log 2>&1
  echo "$(date '+%F %T') $SUITE noattack rc=$?" >> $LOG
done
kill $SV
echo "$(date '+%F %T') STEER_DOJO_DONE $ARM" >> $LOG
