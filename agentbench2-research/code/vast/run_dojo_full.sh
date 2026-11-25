#!/bin/bash
cd /workspace/agentbench2
export HF_HOME=/workspace/.hf_home HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True AB_CHUNK=256
echo "START v3 $(date '+%F %T')" >> runs/dojo_chain.log
.venv/bin/python -u dojo_hf.py --suites banking travel --attack important_instructions --logdir runs/qwen35_4b > runs/qwen35_4b.log 2>&1
echo "ATTACK_DONE rc=$? $(date '+%F %T')" >> runs/dojo_chain.log
.venv/bin/python -u dojo_hf.py --suites banking travel --no-attack --logdir runs/qwen35_4b_noattack > runs/qwen35_4b_noattack.log 2>&1
echo "DOJO_ALL_DONE rc=$? $(date '+%F %T')" >> runs/dojo_chain.log
