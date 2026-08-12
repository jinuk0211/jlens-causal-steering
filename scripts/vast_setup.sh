#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-setup}"
VAST_ROOT="${VAST_ROOT:-/workspace}"
STEERING_DIR="${VAST_ROOT}/jlens-causal-steering"
TOOLALIGN_DIR="${VAST_ROOT}/ToolAlignBench"

case "${MODE}" in
  setup|smoke|full) ;;
  *)
    echo "usage: vast_setup.sh [setup|smoke|full]" >&2
    exit 2
    ;;
esac

command -v git >/dev/null || {
  echo "git is required; choose a Vast.ai PyTorch development image" >&2
  exit 1
}
command -v python3 >/dev/null || {
  echo "python3 is required; choose a Vast.ai PyTorch development image" >&2
  exit 1
}
command -v nvidia-smi >/dev/null || {
  echo "nvidia-smi is unavailable; start a GPU-enabled Vast.ai instance" >&2
  exit 1
}

mkdir -p "${VAST_ROOT}"

if [[ -d "${STEERING_DIR}/.git" ]]; then
  git -C "${STEERING_DIR}" pull --ff-only
else
  git clone https://github.com/jinuk0211/jlens-causal-steering.git "${STEERING_DIR}"
fi

if [[ -d "${TOOLALIGN_DIR}/.git" ]]; then
  git -C "${TOOLALIGN_DIR}" pull --ff-only
else
  git clone https://github.com/jinuk0211/ToolAlignBench.git "${TOOLALIGN_DIR}"
fi

cd "${STEERING_DIR}"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv --system-site-packages .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip wheel "setuptools>=77,<81"
python -m pip install -e ".[dev]"

export HF_HOME="${HF_HOME:-${VAST_ROOT}/.cache/huggingface}"
mkdir -p "${HF_HOME}"

python - <<'PY'
import torch

if not torch.cuda.is_available():
    raise SystemExit("CUDA-enabled PyTorch is required")
name = torch.cuda.get_device_name(0)
free, total = torch.cuda.mem_get_info()
print(f"CUDA ready: {name}; free={free / 2**30:.1f} GiB / total={total / 2**30:.1f} GiB")
PY

jlens-causal validate configs/smoke.json

if [[ "${MODE}" == "smoke" ]]; then
  jlens-causal all configs/smoke.json --fresh
elif [[ "${MODE}" == "full" ]]; then
  jlens-causal all configs/qwen35_toolalign_pilot.json
else
  echo "Setup complete. Activate with: source ${STEERING_DIR}/.venv/bin/activate"
fi
