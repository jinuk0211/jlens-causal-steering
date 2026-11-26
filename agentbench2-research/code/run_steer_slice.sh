#!/bin/bash
# X12 helper (사후): extra server for one arm on a slice of user tasks, same logdir (AgentDojo skips finished episodes).
# usage: bash run_steer_slice.sh ARM PORT GPU SUITE MODE(attack|noattack) "user_task_a user_task_b ..."
ARM=$1; PORT=$2; G=$3; SUITE=$4; MODE=$5; TASKS=$6
B=/home/project-b/LJW/agentbench2
A=$B/ana
LOG=$A/logs/steer_dojo_${ARM}_slice_$PORT.log
source $B/ops/env_ab.sh
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=$G AB_PLATFORM=projectb
export PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false AB_ARM=$ARM AB_PORT=$PORT
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
cd $A
echo "$(date '+%F %T') start slice server $ARM GPU $G port $PORT $SUITE $MODE: $TASKS" >> $LOG
setsid $V -u $A/ab_serve_steer.py > $A/logs/serve_steer_${ARM}_$PORT.out 2>&1 < /dev/null &
SV=$!
for i in $(seq 1 60); do curl -sf http://127.0.0.1:$PORT/v1/models > /dev/null && break; sleep 10; done
curl -sf http://127.0.0.1:$PORT/v1/models > /dev/null || { echo "$(date '+%F %T') server did not come up" >> $LOG; kill $SV; exit 1; }
export OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:$PORT/v1 OPENAI_COMPATIBLE_API_KEY=local
cd $B
UT=""; for t in $TASKS; do UT="$UT -ut $t"; done
if [ $MODE = attack ]; then
  $B/.venv/bin/python -m agentdojo.scripts.benchmark --model OPENAI_COMPATIBLE --model-id Qwen/Qwen3.5-4B --benchmark-version v1.2.2 \
    -s $SUITE $UT --attack important_instructions --logdir runs/steer_$ARM > $A/logs/steer_dojo_${ARM}_${SUITE}_${MODE}_$PORT.log 2>&1
else
  $B/.venv/bin/python -m agentdojo.scripts.benchmark --model OPENAI_COMPATIBLE --model-id Qwen/Qwen3.5-4B --benchmark-version v1.2.2 \
    -s $SUITE $UT --logdir runs/steer_${ARM}_noattack > $A/logs/steer_dojo_${ARM}_${SUITE}_${MODE}_$PORT.log 2>&1
fi
echo "$(date '+%F %T') slice rc=$?" >> $LOG
kill $SV
echo "$(date '+%F %T') SLICE_DONE" >> $LOG
