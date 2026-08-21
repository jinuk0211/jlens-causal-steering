#!/usr/bin/env bash
# Bootstrap code, dependencies, and the checksum-pinned Drive snapshot for the
# existing-failure five-method run. Set RUN_STEERING=1 to start it immediately.

set -Eeuo pipefail

VAST_ROOT="${VAST_ROOT:-/workspace}"
CAUSAL_REF="${CAUSAL_REF:-agent/jlens-thought-steering}"
TAU2_REF="${TAU2_REF:-codex/jlens-telecom-backend}"
RUN_STEERING="${RUN_STEERING:-0}"
CAUSAL_DIR="${VAST_ROOT}/jlens-causal-steering"
TAU2_DIR="${VAST_ROOT}/tau2-bench"

for command in curl git nvidia-smi python3 sha256sum; do
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
export UV_CACHE_DIR="${UV_CACHE_DIR:-${VAST_ROOT}/.cache/uv}"
mkdir -p \
  "$HF_HOME" \
  "$UV_CACHE_DIR" \
  "$CAUSAL_DIR/outputs" \
  "$TAU2_DIR/data/simulations/failure-steering"

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

download_drive_file() {
  local file_id="$1"
  local target="$2"
  local expected_sha256="$3"
  local actual_sha256
  mkdir -p "$(dirname "$target")"
  if [[ -s "$target" ]]; then
    actual_sha256="$(sha256sum "$target" | cut -d' ' -f1)"
    if [[ "$actual_sha256" == "$expected_sha256" ]]; then
      echo "Data already verified: $target"
      return
    fi
  fi
  local temporary
  temporary="$(mktemp "${target}.download.XXXXXX")"
  curl --fail --location \
    --retry 5 --retry-all-errors --connect-timeout 30 \
    "https://drive.usercontent.google.com/download?id=${file_id}&export=download&confirm=t" \
    --output "$temporary"
  actual_sha256="$(sha256sum "$temporary" | cut -d' ' -f1)"
  if [[ "$actual_sha256" != "$expected_sha256" ]]; then
    rm -f "$temporary"
    echo "ERROR: checksum mismatch for $target" >&2
    exit 1
  fi
  if [[ -e "$target" ]]; then
    mv "$target" "${target}.invalid-$(date +%Y%m%d-%H%M%S)"
  fi
  mv "$temporary" "$target"
  echo "Downloaded and verified: $target"
}

DATA_ROOT="$TAU2_DIR/data/simulations/failure-steering"
download_drive_file \
  1hZy4xPyUG_n1yc-SiA6qo86NicKUOg1P \
  "$DATA_ROOT/train/baseline/results.json" \
  ae880021561a40f8e1219b887d660a7da4735d30250499f2edc4e04f6060daf3
download_drive_file \
  15bjuk7yPKL3a8OuR5sIOQg_baxfgY50g \
  "$DATA_ROOT/train/baseline/results_reviewed.json" \
  9f4de554d3a3aebcd3ee2bdc257c751500c0149648075a8c63e3beab3d500cfa
download_drive_file \
  1B5o9G2NvM9WgE7KUOPdehZZ8M_f4S6Lp \
  "$DATA_ROOT/validation/baseline/results.json" \
  559163c188a937c0d0e244f2417c93e41d9fc7124d84e384c771d1799ab423f4
download_drive_file \
  1vd0pWC7PMFJhL59Wp0he2sljvl3NV84B \
  "$DATA_ROOT/validation/baseline/results_reviewed.json" \
  61411a7784b4a086cc36198d08cbda2f591fc94d0be7eec4e65529884e33d63b
download_drive_file \
  1IraINXr5GKrgB5h8lK5TsbLLggFz2Qdf \
  "$DATA_ROOT/evaluation/baseline/results.json" \
  efa6fd075e8f162f9f8fe6855b661810e1528a519cf888aefe9d9bb17e58a00e
download_drive_file \
  1Yws9LINTnT2e_BGB_YNRw8BgDseRGlnY \
  "$DATA_ROOT/evaluation/baseline/results_reviewed.json" \
  9bfdde17faee47d69422aee33d97cc4cbf3e38ee1efc7e31cf9af666792e926e
download_drive_file \
  1N15Zoa9kXjyhBhgOx0UebH_5yigeSVsh \
  "$CAUSAL_DIR/outputs/taubench-airline-repairs.jsonl" \
  8b405a015a4ebb2fe1f42688d35fa7651e1b04a9e5acbf242e66b05fb1430b09

python - "$DATA_ROOT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
expected = {"train": 72, "validation": 30, "evaluation": 20}
for split, count in expected.items():
    for name in ("results.json", "results_reviewed.json"):
        path = root / split / "baseline" / name
        value = json.loads(path.read_text(encoding="utf-8"))
        actual = len(value.get("simulations") or [])
        if actual != count:
            raise SystemExit(f"{path}: expected {count} simulations, found {actual}")
    print(f"Verified {split}: {count} baseline simulations and reviews")
PY

echo
echo "Code, dependencies, baseline data, and repair seed are ready."
if [[ "$RUN_STEERING" == 1 ]]; then
  echo "Starting five-method steering run..."
  cd "$CAUSAL_DIR"
  exec bash scripts/run_taubench_existing_failures5.sh
fi
echo "Run:"
echo "  cd ${CAUSAL_DIR}"
echo "  source .venv/bin/activate"
echo "  bash scripts/run_taubench_existing_failures5.sh"
