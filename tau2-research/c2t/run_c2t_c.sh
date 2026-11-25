#!/bin/bash
source /home/project-b/LJW/tau2-steer/env.sh
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4
export JC_MODEL=/home/project-b/LJW/.cache/huggingface/hub/models--Qwen--Qwen3.5-4B/snapshots/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a
export TRITON_CACHE_DIR=/home/project-b/LJW/.cache/triton
export C2_CONFIGS=base,attn_band_10_18,attn_27
cd /home/project-b/LJW/tau2-steer/probe/c2t
PY=/home/project-b/LJW/tau2-steer/.venv/bin/python
L=logs/chain.log
echo "$(date '+%F %T') user: only the two tau2-grounded configs (+ base); 4 workers" >> $L
P=""
for w in v0a v0b v0c v0d; do C2_WID=$w nice -n 5 $PY -u tau_causal2.py run > logs/run_$w.log 2>&1 & P="$P $!"; sleep 30; done
wait $P
C2_WID=sweep2 C2_SWEEP=1 nice -n 5 $PY -u tau_causal2.py run > logs/run_sweep2.log 2>&1
$PY tau_causal2.py report > logs/report.log 2>&1
echo "$(date '+%F %T') C2T_DONE" >> $L
