#!/bin/bash
source /home/project-b/LJW/tau2-steer/env.sh
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4
export JC_MODEL=/home/project-b/LJW/.cache/huggingface/hub/models--Qwen--Qwen3.5-4B/snapshots/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a
export TRITON_CACHE_DIR=/home/project-b/LJW/.cache/triton
cd /home/project-b/LJW/tau2-steer/probe/circuit
nice -n 5 /home/project-b/LJW/tau2-steer/.venv/bin/python -u "$@"
