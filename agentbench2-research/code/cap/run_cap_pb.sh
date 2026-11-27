#!/bin/bash
# project-b capture (CIRCUIT.md). bash run_cap_pb.sh GPU BENCH OUT_DIR [VAR=VALUE ...]; log OUT_DIR/capture.log
# Starts only if every compute process on that GPU is ours (no other user's process).
source /home/project-b/LJW/agentbench2/ops/env_ab.sh
G=$1; B=$2; O=$3; shift 3
export CUDA_VISIBLE_DEVICES=$G PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/project-b/LJW/agentbench2/ana/cap
for kv in "$@"; do export "$kv"; done
mkdir -p $O
u=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i $G)
for p in $(nvidia-smi --query-compute-apps=pid,gpu_uuid --format=csv,noheader | grep "$u" | cut -d, -f1); do
  if ! tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q "/LJW/agentbench2/"; then
    echo "$(date '+%F %T') GPU guard: pid $p on GPU $G is not ours; not started" >> $O/guard.log
    exit 1
  fi
done
exec /home/project-b/LJW/tau2-steer/.venv/bin/python -u /home/project-b/LJW/agentbench2/ana/cap/capture.py jobs/jobs_$B.jsonl $O >> $O/capture.log 2>&1
