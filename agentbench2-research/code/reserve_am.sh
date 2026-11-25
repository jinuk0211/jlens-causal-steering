#!/bin/bash
# Wait until project-b GPU 0 has no compute process at all (user: "gpu 0끝나면 거기서도 예약걸어줘"; never share a GPU
# that someone else is using), then serve Qwen3.5-4B there with vLLM and run the agentic-misalignment generation.
B=/home/project-b/LJW/agentbench2
L=$B/ops/logs/reserve_am.log
echo "$(date '+%F %T') waiting for GPU 0 to be completely free" >> $L
while true; do
  [ -f $B/ops/RESERVE_AM_STOP ] && { echo "$(date '+%F %T') stop file; exit" >> $L; exit 0; }
  U=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i 0)
  N=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | grep -c "$U")
  if [ "$N" -eq 0 ]; then
    sleep 120
    N=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | grep -c "$U")
    [ "$N" -eq 0 ] && break
  fi
  sleep 60
done
echo "$(date '+%F %T') GPU 0 free; starting vLLM" >> $L
AB_GPU=0 AB_FORBIDDEN_GPUS=1 AB_MEM=0.85 setsid bash $B/ops/serve_ab.sh > $B/ops/logs/serve_ab_gpu0.log 2>&1 &
for i in $(seq 1 60); do curl -sf http://127.0.0.1:18230/v1/models > /dev/null && break; sleep 10; done
curl -sf http://127.0.0.1:18230/v1/models > /dev/null || { echo "$(date '+%F %T') vLLM did not come up; see serve_ab_gpu0.log" >> $L; exit 1; }
echo "$(date '+%F %T') vLLM up; AM generation" >> $L
bash $B/ops/run_gen.sh am > $B/ops/logs/gen_am.log 2>&1
echo "$(date '+%F %T') AM generation exit $? ($(find $B/agentic-misalignment/results/qwen35_4b_am -name response.json | wc -l) responses)" >> $L
SV=$(ps -eo pid,args | awk '$3 ~ /vllm$/ && $4=="serve" && $0 ~ /18230/ {print $1}')
EC=""
U=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i 0)
for p in $(nvidia-smi --query-compute-apps=pid,gpu_uuid --format=csv,noheader | grep "$U" | cut -d, -f1 | tr -d ' '); do
  [ "$(ps -o args= -p $p)" = "VLLM::EngineCore" ] && [ "$(ps -o ppid= -p $p | tr -d ' ')" = "$SV" ] && EC="$EC $p"
done
[ -n "$SV" ] && kill $SV
sleep 10
for p in $EC; do kill $p 2>/dev/null; done
echo "$(date '+%F %T') RESERVE_AM_DONE (stopped vLLM $SV $EC)" >> $L
