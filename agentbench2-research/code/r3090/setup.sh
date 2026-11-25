#!/bin/bash
# 2x RTX 3090 box (11-25 20:0x): same package versions as the project-b analysis venv (bf16 + fla), model and lens cache.
set -x
W=/workspace/agentbench2
mkdir -p $W/ana/logs $W/ana/am
cd $W
export HF_HOME=/workspace/.hf_home UV_CACHE_DIR=/workspace/.uv_cache
uv venv $W/.venv --python 3.12
uv pip install --python $W/.venv/bin/python torch==2.8.0 --index-url https://download.pytorch.org/whl/cu128
uv pip install --python $W/.venv/bin/python transformers==5.20.2 tokenizers==0.23.3 huggingface-hub==2.4.0 safetensors==0.8.0 \
  numpy==2.5.5 flash-linear-attention==0.3.2 fla-core==0.3.2 einops==0.8.2
$W/.venv/bin/python -c "import torch, transformers, fla; print('VERS', torch.__version__, transformers.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
$W/.venv/bin/python - <<'PY'
from huggingface_hub import snapshot_download, hf_hub_download
p = snapshot_download("Qwen/Qwen3.5-4B", revision="851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a")
print("MODEL", p)
q = hf_hub_download("neuronpedia/jacobian-lens", "qwen3.5-4b/jlens/Salesforce-wikitext/Qwen3.5-4B_jacobian_lens_n1000.pt", revision="a4114d7752d11eb546e6cf372213d7e75526d3a1")
print("LENS", q)
PY
echo SETUP_DONE
