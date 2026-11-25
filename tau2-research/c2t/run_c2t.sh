#!/bin/bash
source /home/project-b/LJW/tau2-steer/env.sh
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4
export JC_MODEL=/home/project-b/LJW/.cache/huggingface/hub/models--Qwen--Qwen3.5-4B/snapshots/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a
export TRITON_CACHE_DIR=/home/project-b/LJW/.cache/triton
cd /home/project-b/LJW/tau2-steer/probe/c2t
PY=/home/project-b/LJW/tau2-steer/.venv/bin/python
L=logs/chain.log
mkdir -p logs out
echo "$(date '+%F %T') stats x3" >> $L
P=""
for i in 0 1 2; do nice -n 5 $PY -u tau_causal2.py stats $i 3 > logs/stats_$i.log 2>&1 & P="$P $!"; sleep 20; done
wait $P
for i in 0 1 2; do grep -q STATS_DONE logs/stats_$i.log || { echo "$(date '+%F %T') stats $i failed" >> $L; exit 1; }; done
echo "$(date '+%F %T') stats done; 3 workers" >> $L
P=""
for w in t0a t0b t0c; do C2_WID=$w nice -n 5 $PY -u tau_causal2.py run > logs/run_$w.log 2>&1 & P="$P $!"; sleep 40; done
wait $P
C2_WID=sweep C2_SWEEP=1 nice -n 5 $PY -u tau_causal2.py run > logs/run_sweep.log 2>&1
$PY tau_causal2.py report > logs/report.log 2>&1
echo "$(date '+%F %T') C2T_DONE" >> $L
