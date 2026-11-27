#!/bin/bash
# New vast box (RTX PRO 5000 72GB): same package versions as the project-b analysis venv (torch 2.8.0+cu128, triton 3.4.0,
# fla 0.3.2, transformers 5.20.2), then Qwen3.5-4B at rev 851bf6e into /workspace/.hf_home.
set -e
cd /workspace
mkdir -p cap logs
export HF_HOME=/workspace/.hf_home
uv venv /workspace/.venv --python 3.12 > logs/setup.log 2>&1
source /workspace/.venv/bin/activate
uv pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cu128 >> logs/setup.log 2>&1
uv pip install transformers==5.20.2 tokenizers==0.23.3 safetensors==0.8.0 huggingface_hub==2.4.0 numpy==2.5.5 \
  flash-linear-attention==0.3.2 fla-core==0.3.2 >> logs/setup.log 2>&1
python - >> logs/setup.log 2>&1 <<'PY'
import torch, triton, transformers
print("versions", torch.__version__, triton.__version__, transformers.__version__, torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0))
from huggingface_hub import snapshot_download
p = snapshot_download("Qwen/Qwen3.5-4B", revision="851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a")
print("model at", p)
PY
echo SETUP_DONE >> logs/setup.log
