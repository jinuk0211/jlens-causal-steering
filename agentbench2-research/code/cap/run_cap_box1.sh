#!/bin/bash
# vast box 1 (2080 Ti) capture of ToolAlign (CIRCUIT.md): fp16, torch fallback for Gated DeltaNet, chunk 1024.
cd /workspace/cap
export HF_HOME=/workspace/.hf_home HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export CAP_DTYPE=fp16 CAP_GDN_PATCH=1 CAP_CHUNK=${CAP_CHUNK:-1024} CAP_MAX_PENDING_GB=${CAP_MAX_PENDING_GB:-22}
for kv in "$@"; do export "$kv"; done
O=${CAP_OUT:-/workspace/cap/ta}
mkdir -p $O
[ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)" ] || { echo "$(date '+%F %T') GPU busy, not started" >> $O/guard.log; exit 1; }
exec /workspace/tj/.venv/bin/python -u capture.py jobs_ta.jsonl $O >> $O/capture.log 2>&1
