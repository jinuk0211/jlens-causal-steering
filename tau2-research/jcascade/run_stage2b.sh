#!/bin/bash
# J-Cascade stage 2b on project-b GPU 0 only. Lane 1: prep then 4 configs; lanes 2-3 start at once with C0 / P0 (no prep needed),
# then wait for prep.pt and continue with their configs. 3 processes on the A6000 at any time.
J=/home/project-b/LJW/tau2-steer/probe/jcascade
source /home/project-b/LJW/tau2-steer/env.sh
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 JC_GPU_UUID=c27bc2d7 JC_DIR=$J PYTHONDONTWRITEBYTECODE=1
export JC_MODEL=/home/project-b/LJW/.cache/huggingface/hub/models--Qwen--Qwen3.5-4B/snapshots/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a
export JC_LENS=$(cat /home/project-b/LJW/tau2-steer/lens_path.txt) PYTHONPATH=$J/data TRITON_CACHE_DIR=/home/project-b/LJW/.cache/triton
PYV=/home/project-b/LJW/tau2-steer/.venv/bin/python
cd $J
if [ -n "$JC_SMOKE" ]; then
  JC_PHASE=prep $PYV -u stage2b_regen.py > logs/stage2b_smoke_prep.log 2>&1 && JC_PHASE=gen $PYV -u stage2b_regen.py > logs/stage2b_smoke_gen.log 2>&1
  echo "SMOKE_EXIT $? $(date)" >> logs/stage2b_smoke_prep.log
  exit 0
fi
( [ -f out/stage2b/prep.pt ] || JC_PHASE=prep nice -n 5 $PYV -u stage2b_regen.py > logs/stage2b_prep.log 2>&1
  JC_PHASE=gen JC_CFGS=A100,RA100,A5,AG20 nice -n 5 $PYV -u stage2b_regen.py > logs/stage2b_l1.log 2>&1 ) &
sleep 40
JC_PHASE=gen JC_CFGS=C0,A20,RA20,B05,B1 nice -n 5 $PYV -u stage2b_regen.py > logs/stage2b_l2.log 2>&1 &
sleep 40
JC_PHASE=gen JC_CFGS=P0,B3,B8,RB1,RB8 nice -n 5 $PYV -u stage2b_regen.py > logs/stage2b_l3.log 2>&1 &
wait
echo "STAGE2B_ALL_DONE $(date)" >> logs/stage2b_done.log
