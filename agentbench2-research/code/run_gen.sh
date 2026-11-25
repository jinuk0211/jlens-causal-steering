#!/bin/bash
# S1 generation against the vLLM server from serve_ab.sh (must already be up on port 18230).
# Clients go through ab_proxy.py (port 18231), which records exact prompt/completion token ids.
# usage: bash run_gen.sh dojo|am
source /home/project-b/LJW/agentbench2/ops/env_ab.sh
B=/home/project-b/LJW/agentbench2
PY=$B/.venv/bin/python
curl -sf http://127.0.0.1:18230/v1/models > /dev/null || { echo "run_gen: vLLM server not up"; exit 3; }
AB_PROXY_TAG=$1 $PY $B/ops/ab_proxy.py > $B/ops/logs/proxy_$1.log 2>&1 &
PROXY=$!
sleep 3
curl -sf http://127.0.0.1:18231/v1/models > /dev/null || { echo "run_gen: proxy not up"; kill $PROXY; exit 3; }
case "$1" in
  dojo)
    # The CLI's --max-workers path fails at this commit ('str' object has no attribute 'name') and only parallelizes
    # suites anyway. Instead: per suite, user tasks split into 4 groups, one single-suite process per group (8 in all).
    cd $B
    export OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:18231/v1 OPENAI_COMPATIBLE_API_KEY=local
    mkdir -p $B/ops/logs/dojo_par
    launch() {  # MODE SUITE N GROUP
      local UT=""
      for ((k=$4; k<$3; k+=4)); do UT="$UT -ut user_task_$k"; done
      if [ $1 = attack ]; then
        $PY -m agentdojo.scripts.benchmark --model OPENAI_COMPATIBLE --model-id Qwen/Qwen3.5-4B --benchmark-version v1.2.2 \
          -s $2 $UT --attack important_instructions --logdir runs/qwen35_4b > $B/ops/logs/dojo_par/$1_$2_$4.log 2>&1 & WPIDS="$WPIDS $!"
      else
        $PY -m agentdojo.scripts.benchmark --model OPENAI_COMPATIBLE --model-id Qwen/Qwen3.5-4B --benchmark-version v1.2.2 \
          -s $2 $UT --logdir runs/qwen35_4b_noattack > $B/ops/logs/dojo_par/$1_$2_$4.log 2>&1 & WPIDS="$WPIDS $!"
      fi
    }
    # attack: group 0 of each suite first writes the injection-as-user-task checks (9 banking, 7 travel); the other groups
    # start after, so no two processes write the same log file.
    launch attack banking 16 0
    launch attack travel 20 0
    for i in $(seq 1 90); do
      nb=$(ls runs/qwen35_4b/openai-compatible/banking/injection_task_*/none/none.json 2>/dev/null | wc -l)
      nt=$(ls runs/qwen35_4b/openai-compatible/travel/injection_task_*/none/none.json 2>/dev/null | wc -l)
      [ $nb -ge 9 ] && [ $nt -ge 7 ] && break
      sleep 10
    done
    sleep 5
    for G in 1 2 3; do launch attack banking 16 $G; launch attack travel 20 $G; done
    for p in $WPIDS; do wait $p; done; WPIDS=""  # not a bare wait: it would also wait for the proxy
    echo "DOJO_attack_DONE $(date '+%F %T')"
    for G in 0 1 2 3; do launch noattack banking 16 $G; launch noattack travel 20 $G; done
    for p in $WPIDS; do wait $p; done; WPIDS=""
    echo "DOJO_noattack_DONE $(date '+%F %T')"
    echo "DOJO_GEN_DONE $(date '+%F %T')"
    ;;
  am)
    cd $B/agentic-misalignment
    $PY $B/ops/am_patch.py
    cp $B/ops/qwen35_4b_am.yaml configs/qwen35_4b_am.yaml
    $PY scripts/generate_prompts.py --config configs/qwen35_4b_am.yaml
    AM_LOCAL_MODEL=Qwen/Qwen3.5-4B AM_LOCAL_BASE_URL=http://127.0.0.1:18231/v1 \
      $PY scripts/run_experiments.py --config configs/qwen35_4b_am.yaml
    echo "AM_GEN_DONE $(date '+%F %T')"
    ;;
  *) echo "usage: run_gen.sh dojo|am"; kill $PROXY; exit 2;;
esac
kill $PROXY
