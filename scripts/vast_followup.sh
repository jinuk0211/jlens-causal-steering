#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-all}"
STEERING_REF="${2:-agent/jlens-thought-steering}"
VAST_ROOT="${VAST_ROOT:-/workspace}"
STEERING_DIR="${VAST_ROOT}/jlens-causal-steering"
TOOLALIGN_DIR="${VAST_ROOT}/ToolAlignBench"

case "${MODE}" in
  smoke|full|all) ;;
  *) echo "usage: vast_followup.sh [all|smoke|full] [git-ref]" >&2; exit 2 ;;
esac

mkdir -p "${VAST_ROOT}"
if [[ -d "${STEERING_DIR}/.git" ]]; then
  git -C "${STEERING_DIR}" fetch origin "${STEERING_REF}"
  git -C "${STEERING_DIR}" checkout --detach FETCH_HEAD
else
  git clone --branch "${STEERING_REF}" https://github.com/jinuk0211/jlens-causal-steering.git "${STEERING_DIR}"
fi
if [[ -d "${TOOLALIGN_DIR}/.git" ]]; then
  git -C "${TOOLALIGN_DIR}" pull --ff-only
else
  git clone https://github.com/jinuk0211/ToolAlignBench.git "${TOOLALIGN_DIR}"
fi

cd "${STEERING_DIR}"
if [[ ! -x .venv/bin/python ]]; then python3 -m venv --system-site-packages .venv; fi
source .venv/bin/activate
python -m pip install --upgrade pip wheel "setuptools>=77,<81"
python -m pip install -e ".[dev]"
export HF_HOME="${HF_HOME:-${VAST_ROOT}/.cache/huggingface}"
mkdir -p "${HF_HOME}"
python - <<'PY'
import torch
if not torch.cuda.is_available(): raise SystemExit("CUDA-enabled PyTorch is required")
name = torch.cuda.get_device_name(0)
free, total = torch.cuda.mem_get_info()
print(f"CUDA ready: {name}; free={free/2**30:.1f} GiB / total={total/2**30:.1f} GiB")
PY

run_smoke() {
  jlens-followup validate configs/followup_smoke.json
  jlens-followup all configs/followup_smoke.json --fresh
  python - <<'PY'
import csv, json
from pathlib import Path
root = Path("outputs/followup-smoke")
records = [json.loads(line) for line in (root / "followup_runs.jsonl").read_text().splitlines()]
baselines = [row for row in records if row["method"] == "baseline"]
assert len(records) == 22, len(records)
assert len(baselines) == 2
assert all(row["followup"]["valid"] for row in baselines)
assert (root / "followup_targets.json").is_file()
targets = json.loads((root / "followup_targets.json").read_text())
counts = targets["calibration_decisions"]["decision_counts"]
assert counts["stop"] >= 4, counts
assert counts["repeat"] >= 4, counts
assert (root / "followup_summary.csv").is_file()
with (root / "followup_summary.csv").open(newline="") as handle:
    assert next(csv.reader(handle), None)
print("VALID POST-SUCCESS FOLLOWUP SMOKE: 22 records; baselines valid")
PY
}

launch_full() {
  jlens-followup validate configs/followup_powered.json
  mkdir -p outputs
  local fresh_flag="${1:-}"
  if command -v tmux >/dev/null 2>&1; then
    if tmux has-session -t jlens-followup 2>/dev/null; then
      echo "tmux session jlens-followup already exists"
    else
      tmux new-session -d -s jlens-followup \
        "cd '${STEERING_DIR}' && source .venv/bin/activate && export HF_HOME='${HF_HOME}' && jlens-followup all configs/followup_powered.json ${fresh_flag} 2>&1 | tee outputs/followup-powered.log"
      echo "Powered run started: tmux attach -t jlens-followup"
    fi
  else
    nohup bash -lc \
      "cd '${STEERING_DIR}' && source .venv/bin/activate && export HF_HOME='${HF_HOME}' && jlens-followup all configs/followup_powered.json ${fresh_flag}" \
      > outputs/followup-powered.log 2>&1 < /dev/null &
    echo "Powered run started with PID $!; log: ${STEERING_DIR}/outputs/followup-powered.log"
  fi
}

case "${MODE}" in
  smoke) run_smoke ;;
  full) launch_full ;;
  all)
    run_smoke
    launch_full --fresh
    ;;
esac
