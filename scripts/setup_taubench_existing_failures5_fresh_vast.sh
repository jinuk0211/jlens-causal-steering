#!/usr/bin/env bash
# Bootstrap code and dependencies for the existing-failure five-method run.
# Experiment data is intentionally not downloaded from Git; restore it from
# the user's Drive snapshot after this setup completes.

set -Eeuo pipefail

VAST_ROOT="${VAST_ROOT:-/workspace}"
CAUSAL_REF="${CAUSAL_REF:-agent/jlens-thought-steering}"
TAU2_REF="${TAU2_REF:-codex/jlens-telecom-backend}"
CAUSAL_DIR="${VAST_ROOT}/jlens-causal-steering"
TAU2_DIR="${VAST_ROOT}/tau2-bench"

for command in git python3 nvidia-smi; do
  command -v "$command" >/dev/null || {
    echo "ERROR: $command is required; use a recent Vast PyTorch development image" >&2
    exit 1
  }
done

python3 - <<'PY'
import sys

if not (sys.version_info >= (3, 12) and sys.version_info < (3, 14)):
    raise SystemExit("Python >=3.12,<3.14 is required by the pinned Tau2 checkout")
PY

mkdir -p "$VAST_ROOT"

checkout() {
  local url="$1"
  local ref="$2"
  local destination="$3"
  if [[ -d "${destination}/.git" ]]; then
    git -C "$destination" fetch origin "$ref"
    git -C "$destination" checkout --detach FETCH_HEAD
  elif [[ -e "$destination" ]]; then
    echo "ERROR: destination exists but is not a Git checkout: $destination" >&2
    exit 1
  else
    git clone --branch "$ref" "$url" "$destination"
  fi
}

checkout \
  https://github.com/jinuk0211/jlens-causal-steering.git \
  "$CAUSAL_REF" \
  "$CAUSAL_DIR"
checkout \
  https://github.com/jinuk0211/tau2-bench.git \
  "$TAU2_REF" \
  "$TAU2_DIR"

cd "$CAUSAL_DIR"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv --system-site-packages .venv
fi
source .venv/bin/activate

python -m pip install --upgrade pip wheel "setuptools>=77,<81"
python -m pip install -e "$CAUSAL_DIR"
python -m pip install -e "$TAU2_DIR" jsonschema

export HF_HOME="${HF_HOME:-${VAST_ROOT}/.cache/huggingface}"
mkdir -p "$HF_HOME" "$TAU2_DIR/data/simulations/failure-steering"

python - <<'PY'
import torch
import tau2
import jlens_causal

if not torch.cuda.is_available():
    raise SystemExit("CUDA-enabled PyTorch is required")
free, total = torch.cuda.mem_get_info()
print(f"CUDA ready: {torch.cuda.get_device_name(0)}; free={free / 2**30:.1f}/{total / 2**30:.1f} GiB")
print(f"tau2 import: {tau2.__file__}")
print(f"jlens_causal import: {jlens_causal.__file__}")
PY

missing=0
for split in train validation evaluation; do
  for name in results.json results_reviewed.json; do
    path="${TAU2_DIR}/data/simulations/failure-steering/${split}/baseline/${name}"
    if [[ ! -s "$path" ]]; then
      echo "DATA MISSING: $path"
      missing=1
    fi
  done
done

echo
if [[ "$missing" == 1 ]]; then
  echo "Code setup complete. Restore the six baseline JSON files from Drive, then run:"
else
  echo "Code and baseline data are ready. Run:"
fi
echo "  cd ${CAUSAL_DIR}"
echo "  source .venv/bin/activate"
echo "  bash scripts/run_taubench_existing_failures5.sh"
