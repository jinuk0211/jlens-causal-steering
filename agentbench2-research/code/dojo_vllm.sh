#!/bin/bash
# AgentDojo generation on project-b GPU 0 with vLLM bf16 next to our own HF analyses (11-25 14:5x; the vast HF fp32 run
# decodes at ~2 min per episode, about 9 h for the rest). gpu_guard.sh refuses if any process on GPU 0 is not ours.
# vLLM gets 30 % of GPU 0. Exact token ids through ops/ab_proxy.py (tag dojo). Stops our vLLM by pid at the end.
B=/home/project-b/LJW/agentbench2
LOG=$B/ops/logs/dojo_vllm.log
echo "$(date '+%F %T') start" >> $LOG
AB_GPU=0 AB_FORBIDDEN_GPUS=1 AB_MEM=${AB_MEM:-0.30} setsid bash $B/ops/serve_ab.sh > $B/ops/logs/serve_dojo_gpu0.log 2>&1 &
for i in $(seq 1 60); do curl -sf http://127.0.0.1:18230/v1/models > /dev/null && break; sleep 10; done
curl -sf http://127.0.0.1:18230/v1/models > /dev/null || { echo "$(date '+%F %T') vLLM did not come up; see serve_dojo_gpu0.log" >> $LOG; exit 1; }
echo "$(date '+%F %T') vLLM up; AgentDojo generation" >> $LOG
bash $B/ops/run_gen.sh dojo > $B/ops/logs/gen_dojo.log 2>&1
RC=$?
NA=$(find $B/runs/qwen35_4b -path '*important_instructions*' -name '*.json' | wc -l)
NN=$(find $B/runs/qwen35_4b_noattack -path '*user_task_*' -name 'none.json' | wc -l)
echo "$(date '+%F %T') generation exit $RC ($NA attack episodes, $NN no-attack)" >> $LOG
SV=$(ps -eo pid,args | awk '$3 ~ /vllm$/ && $4=="serve" && $0 ~ /18230/ {print $1}')
EC=""
U=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i 0)
for p in $(nvidia-smi --query-compute-apps=pid,gpu_uuid --format=csv,noheader | grep "$U" | cut -d, -f1 | tr -d ' '); do
  [ "$(ps -o args= -p $p)" = "VLLM::EngineCore" ] && [ "$(ps -o ppid= -p $p | tr -d ' ')" = "$SV" ] && EC="$EC $p"
done
[ -n "$SV" ] && kill $SV
sleep 10
for p in $EC; do kill $p 2>/dev/null; done
if [ "$NA" -ge 284 ] && [ "$NN" -ge 36 ]; then
  echo "$(date '+%F %T') DOJO_VLLM_DONE (stopped vLLM $SV $EC)" >> $LOG
else
  echo "$(date '+%F %T') DOJO_VLLM_INCOMPLETE (stopped vLLM $SV $EC)" >> $LOG
fi
