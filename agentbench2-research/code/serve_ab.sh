#!/bin/bash
# usage: AB_GPU=<index> bash serve_ab.sh   (refuses forbidden or occupied GPUs)
source /home/project-b/LJW/agentbench2/ops/env_ab.sh
if [ -z "$AB_GPU" ]; then echo "serve_ab: set AB_GPU"; exit 3; fi
bash /home/project-b/LJW/agentbench2/ops/gpu_guard.sh "$AB_GPU" || exit 3
export CUDA_VISIBLE_DEVICES=$AB_GPU
exec /home/project-b/LJW/ontoloop/.venv/bin/vllm serve Qwen/Qwen3.5-4B --revision 851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a \
  --served-model-name Qwen/Qwen3.5-4B --host 127.0.0.1 --port 18230 --dtype bfloat16 --max-model-len 32768 \
  --gpu-memory-utilization ${AB_MEM:-0.85} --enable-auto-tool-choice --tool-call-parser qwen3_coder \
  --default-chat-template-kwargs '{"enable_thinking": false}' --max-num-seqs 32
