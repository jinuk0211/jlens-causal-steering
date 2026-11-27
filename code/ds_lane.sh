#!/bin/bash
# X20 lane: bash ds_lane.sh MK GPU PORT
# One dojo_serve.py server (model MK on one GPU, all arms) and one AgentDojo process at a time. Pops jobs of model MK from
# ana/ds/queue.txt (dojo_suite.py pop); restarts the server when a job's arm is not loaded yet (arms.json written after start).
# Job: MK SUITE ARM attack|noattack USER_TASKS(comma) INJ(all|comma) LOGDIR. Exits when the queue has no job of MK, or on
# ana/ds/STOP or ana/ds/MK/STOP. Stops its own server by pid.
MK=$1; G=$2; PORT=$3
B=${AB_ROOT:-/home/project-b/LJW/agentbench2}
A=$B/ana
D=$A/ds
source $B/ops/env_ab.sh
eval "$(python3 $A/dojo_suite.py env $MK)" || exit 1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=$G AB_PLATFORM=${AB_PLATFORM:-projectb}
export PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false AB_PORT=$PORT
V=${AB_TORCH_PY:-/home/project-b/LJW/tau2-steer/.venv/bin/python}
ADV=${AB_DOJO_PY:-$B/.venv/bin/python}
mkdir -p $D/logs $D/$MK/logs
LG=$D/logs/lanes.log
say() { echo "$(date '+%F %T') lane $MK/$G:$PORT $*" >> $LG; }
SV=""
stop_server() {
  if [ -n "$SV" ]; then kill $SV 2>/dev/null; wait $SV 2>/dev/null; fi
  SV=""
}
start_server() {
  stop_server
  setsid $V -u $A/dojo_serve.py >> $D/$MK/logs/serve_$PORT.out 2>&1 < /dev/null &
  SV=$!
  for i in $(seq 1 180); do
    curl -sf http://127.0.0.1:$PORT/arms > /dev/null && { say "server up (pid $SV): $(curl -sf http://127.0.0.1:$PORT/arms | tr '\n' ' ')"; return 0; }
    kill -0 $SV 2>/dev/null || break
    sleep 10
  done
  say "server did not come up (see $D/$MK/logs/serve_$PORT.out)"
  stop_server
  return 1
}
trap 'stop_server; say exit' EXIT
say "start"
while true; do
  if [ -f $D/STOP ] || [ -f $D/$MK/STOP ]; then say "stop file"; break; fi
  JOB=$(python3 $A/dojo_suite.py pop $MK)
  if [ "$JOB" = EMPTY ] || [ -z "$JOB" ]; then break; fi
  if [ "$JOB" = WAIT ]; then sleep 30; continue; fi
  read -r JMK SUITE ARM MODE UTS ITS LD <<< "$JOB"
  KEY=$SUITE.$ARM
  if [ -z "$SV" ] || ! kill -0 $SV 2>/dev/null || ! curl -sf http://127.0.0.1:$PORT/arms | grep -qx "$KEY"; then
    if ! start_server || ! curl -sf http://127.0.0.1:$PORT/arms | grep -qx "$KEY"; then
      python3 $A/dojo_suite.py push $JOB > /dev/null
      say "arm $KEY not available; job put back, lane exits"
      break
    fi
  fi
  FL="-s $SUITE"
  for t in ${UTS//,/ }; do FL="$FL -ut $t"; done
  say "start: $JOB"
  export OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:$PORT/$KEY/v1 OPENAI_COMPATIBLE_API_KEY=local
  OUT=$D/$MK/logs/dojo_${KEY}_${MODE}_${UTS%%,*}_$PORT.log
  if [ "$MODE" = attack ]; then
    if [ "$ITS" != all ]; then for t in ${ITS//,/ }; do FL="$FL -it injection_task_$t"; done; fi
    (cd $B && $ADV -m agentdojo.scripts.benchmark --model OPENAI_COMPATIBLE --model-id $AB_DS_MID --benchmark-version v1.2.2 \
      $FL --attack important_instructions --logdir runs/$LD) > $OUT 2>&1
  else
    (cd $B && $ADV -m agentdojo.scripts.benchmark --model OPENAI_COMPATIBLE --model-id $AB_DS_MID --benchmark-version v1.2.2 \
      $FL --logdir runs/${LD}_noattack) > $OUT 2>&1
  fi
  RC=$?
  if ! kill -0 $SV 2>/dev/null; then
    python3 $A/dojo_suite.py push $JOB > /dev/null
    say "server died during the job (rc $RC); job put back, lane exits"
    SV=""
    break
  fi
  say "done rc=$RC: $JOB"
done
