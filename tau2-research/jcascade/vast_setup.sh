#!/bin/bash
# J-Cascade stage 1 environment on the vast box (same versions as project-b tau2-steer/.venv)
set -e
J=/workspace/jc; mkdir -p $J/hf $J/logs $J/data $J/out
export HF_HOME=$J/hf UV_CACHE_DIR=$J/uvcache
cd $J
command -v uv >/dev/null || pip install -q uv
uv venv -q --python 3.12 $J/venv
. $J/venv/bin/activate
uv pip install -q --index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/cu128 \
  "torch==2.8.0" "transformers==5.20.2" "flash-linear-attention==0.3.2" "fla-core==0.3.2" "triton==3.4.0" \
  "numpy==2.5.5" "safetensors==0.8.0" "tokenizers==0.23.3" "einops==0.8.2" "huggingface-hub==2.4.0"
python - <<'PY'
from huggingface_hub import snapshot_download, hf_hub_download
p = snapshot_download("Qwen/Qwen3.5-4B", revision="851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a")
print("MODEL", p)
l = hf_hub_download("neuronpedia/jacobian-lens", "qwen3.5-4b/jlens/Salesforce-wikitext/Qwen3.5-4B_jacobian_lens_n1000.pt",
                    revision="a4114d7752d11eb546e6cf372213d7e75526d3a1")
print("LENS", l)
PY
python -c "import torch; print('cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0))"
echo SETUP_DONE
