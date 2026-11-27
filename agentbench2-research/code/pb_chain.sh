#!/bin/bash
# PropensityBench chain for one GPU (PLAN.md "PB"): bash pb_chain.sh GPU LANE SHARD NSHARD PORT
#   1. base: pb_serve.py arm base + pb_run.py on every task of the lane (both folds)        -> pb/runs/base_<lane>.jsonl
#   2. after every lane's base: ab_pb.py units once (lock pb/locks/units)
#   3. ab_pb.py capture, shard SHARD/NSHARD (HF on this GPU)
#   4. after every shard: ab_pb.py select once (lock pb/locks/select; its gate can stop the chain)
#   5. arms H512 H1024 H2048 rH1024: set fold 0 on the lane's fold-1 tasks, set fold 1 on its fold-0 tasks -> pb/runs/<arm>_s<f>_<lane>.jsonl
#   6. ab_pb.py report
# Lanes (task -> machine pinned for every arm): a6000 = project-b GPU 0, a5000 = GPU 2. Stop file pb/STOP, checked between jobs.
# Env: PB_WORKERS (concurrent episodes; 48 on the A6000, 24 on the A5000), PB_MEM, PB_ONLY=base to stop after step 1.
source /home/project-b/LJW/agentbench2/ops/env_ab.sh
cd /home/project-b/LJW/agentbench2/ana || exit 1
G=$1; LANE=$2; SH=$3; NSH=$4; PORT=$5
VPY=/home/project-b/LJW/ontoloop/.venv/bin/python
HPY=/home/project-b/LJW/tau2-steer/.venv/bin/python
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
mkdir -p pb/logs pb/runs pb/locks
LG=pb/logs/chain_$LANE.log
say() { echo "$(date '+%F %T') $LANE gpu $G: $*" >> $LG; }
stop() { [ -e pb/STOP ] && { say "STOP"; exit 0; }; }

serve_run() {
  local ARM=$1 SF=$2 TF=$3 OUT=$4
  stop
  [ -e pb/runs/$OUT.DONE ] && return 0
  bash /home/project-b/LJW/agentbench2/ops/gpu_guard.sh $G || { say "gpu guard refused GPU $G"; exit 3; }
  CUDA_VISIBLE_DEVICES=$G PB_PORT=$PORT PB_ARM=$ARM PB_SETFOLD=$SF PB_TAG=$OUT $VPY -u pb_serve.py >> pb/logs/serve_$OUT.log 2>&1 &
  local SP=$!
  for i in $(seq 1 240); do
    curl -sf http://127.0.0.1:$PORT/v1/models > /dev/null && break
    kill -0 $SP 2> /dev/null || { say "server died before ready: $OUT"; exit 4; }
    sleep 5
  done
  say "server up $OUT pid $SP"
  local FO=""
  [ "$TF" != all ] && FO="--fold $TF"
  $HPY -u pb_run.py --api http://127.0.0.1:$PORT/v1 --out $OUT --arm $ARM --lane $LANE $FO --workers ${PB_WORKERS:-48} >> pb/logs/run_$OUT.log 2>&1
  local rc=$?
  curl -s http://127.0.0.1:$PORT/pb_stats >> pb/logs/serve_$OUT.log; echo >> pb/logs/serve_$OUT.log
  kill $SP; wait $SP 2> /dev/null
  say "run $OUT rc=$rc"
  [ $rc = 0 ] && touch pb/runs/$OUT.DONE
  [ $rc = 0 ] || exit 5
}

say "start shard $SH/$NSH port $PORT"
serve_run base - all base_$LANE
touch pb/BASE_$LANE
[ "$PB_ONLY" = base ] && { say "PB_ONLY=base, exit"; exit 0; }
until [ -e pb/BASE_a6000 ] && [ -e pb/BASE_a5000 ]; do stop; sleep 60; done
if mkdir pb/locks/units 2> /dev/null; then
  $HPY ab_pb.py units >> $LG 2>&1 && touch pb/UNITS_DONE || touch pb/UNITS_FAIL
fi
until [ -e pb/UNITS_DONE ] || [ -e pb/UNITS_FAIL ]; do stop; sleep 30; done
[ -e pb/UNITS_FAIL ] && { say "units failed"; exit 6; }
stop
if [ ! -e pb/CAP_$SH ]; then
  bash /home/project-b/LJW/agentbench2/ops/gpu_guard.sh $G || { say "gpu guard refused GPU $G"; exit 3; }
  AB_PLATFORM=projectb CUDA_VISIBLE_DEVICES=$G PB_SHARD=$SH/$NSH $HPY -u ab_pb.py capture >> pb/logs/capture_s$SH.log 2>&1 && touch pb/CAP_$SH
  [ -e pb/CAP_$SH ] || { say "capture failed"; exit 7; }
fi
while true; do
  n=0; for i in $(seq 0 $((NSH - 1))); do [ -e pb/CAP_$i ] && n=$((n + 1)); done
  [ $n = $NSH ] && break
  stop; sleep 60
done
if mkdir pb/locks/select 2> /dev/null; then
  $HPY ab_pb.py select >> $LG 2>&1 && touch pb/SELECT_DONE || touch pb/SELECT_FAIL
fi
until [ -e pb/SELECT_DONE ] || [ -e pb/SELECT_FAIL ]; do stop; sleep 30; done
[ -e pb/SELECT_FAIL ] && { say "select failed or gate stopped the run"; exit 8; }
for A in H512 H1024 H2048 rH1024; do
  serve_run $A 0 1 ${A}_s0_$LANE
  serve_run $A 1 0 ${A}_s1_$LANE
done
touch pb/ARMS_$LANE
$HPY ab_pb.py report > /dev/null 2>> $LG
say "exit"
