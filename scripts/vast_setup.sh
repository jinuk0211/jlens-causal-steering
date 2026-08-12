#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-setup}"
STEERING_REF="${2:-main}"
VAST_ROOT="${VAST_ROOT:-/workspace}"
STEERING_DIR="${VAST_ROOT}/jlens-causal-steering"
TOOLALIGN_DIR="${VAST_ROOT}/ToolAlignBench"

case "${MODE}" in
  setup|smoke|full) ;;
  *)
    echo "usage: vast_setup.sh [setup|smoke|full] [git-ref]" >&2
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
  if [[ "${STEERING_REF}" == "main" ]]; then
    git -C "${STEERING_DIR}" switch main
    git -C "${STEERING_DIR}" pull --ff-only
  else
    git -C "${STEERING_DIR}" fetch origin "${STEERING_REF}"
    git -C "${STEERING_DIR}" checkout --detach FETCH_HEAD
  fi
else
  git clone --branch "${STEERING_REF}" \
    https://github.com/jinuk0211/jlens-causal-steering.git "${STEERING_DIR}"
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
  python - <<'PY'
import csv
import json
from pathlib import Path

root = Path("outputs/smoke")
records = [json.loads(line) for line in (root / "runs.jsonl").read_text().splitlines()]
baselines = [record for record in records if record["method"] == "baseline"]
selection = json.loads((root / "target_selection.json").read_text())
assert len(records) == 18, f"expected 18 records, found {len(records)}"
assert len(baselines) == 2, f"expected two baselines, found {len(baselines)}"
assert not any(record["truncated"] for record in baselines)
assert not any(record["behavior"]["parse_error"] for record in baselines)
assert selection["schema_version"] == "jlens-target-selection-v2"
for side in ("target_a", "target_b"):
    assert len(selection[side]) == 5
    assert all(row["domain_consistency"] >= 9 for row in selection[side])
    assert all(row["loo_top_frequency"] >= 9 for row in selection[side])
    assert all(
        row["lexical_domains_target"] >= 3
        and row["lexical_domains_target"] > row["lexical_domains_other"]
        for row in selection[side]
    )
required = (
    "target_selection.json",
    "summary.csv",
    "thought_trajectories.csv",
    "behavior_profiles.csv",
)
assert all((root / name).is_file() for name in required)
with (root / "summary.csv").open(newline="") as handle:
    assert next(csv.reader(handle), None), "summary.csv is empty"
print("VALID THOUGHT-STEERING SMOKE: 18 records; baselines and lexical targets valid")
print("safe targets:", ", ".join(row["token"] for row in selection["target_a"]))
print("wrongdoing targets:", ", ".join(row["token"] for row in selection["target_b"]))
PY
elif [[ "${MODE}" == "full" ]]; then
  jlens-causal all configs/qwen35_toolalign_pilot.json
else
  echo "Setup complete. Activate with: source ${STEERING_DIR}/.venv/bin/activate"
fi
