#!/usr/bin/env bash
# Collect and review the no-steering data needed before five baseline artifacts
# can be extracted. Safe to rerun; Tau2 resumes missing task/trial pairs.

set -Eeuo pipefail

CAUSAL_ROOT="${CAUSAL_ROOT:-/workspace/jlens-causal-steering}"
TAU2_ROOT="${TAU2_ROOT:-/workspace/tau2-bench}"
BASELINE_PREFIX="${BASELINE_PREFIX:-failure-steering}"
BASELINE_TRAIN_TRIALS="${BASELINE_TRAIN_TRIALS:-5}"
BASELINE_VALIDATION_TRIALS="${BASELINE_VALIDATION_TRIALS:-5}"
BASELINE_EVALUATION_TRIALS="${BASELINE_EVALUATION_TRIALS:-1}"
USER_MODEL="${USER_MODEL:-gpt-5.2-2025-12-11}"
REVIEW_MODEL="${REVIEW_MODEL:-gpt-4.1-2025-04-14}"
REVIEW_ATTEMPTS="${REVIEW_ATTEMPTS:-3}"
REVIEW_RETRY_DELAY_SECONDS="${REVIEW_RETRY_DELAY_SECONDS:-65}"
MANIFEST="${CAUSAL_ROOT}/configs/taubench_airline_failure_modes_qwen35_4b.json"
MATRIX="${CAUSAL_ROOT}/outputs/taubench-airline-failure-matrix.json"
RUN_LOG="${BASELINE_RUN_LOG:-/workspace/taubench-baselines5-data.log}"
WORKER_LOG="${BASELINE_WORKER_LOG:-/workspace/jlens-remote-worker-baseline-data.log}"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_file() {
  [[ -s "$1" ]] || die "required file is missing or empty: $1"
}

require_positive_integer() {
  [[ "$2" =~ ^[1-9][0-9]*$ ]] || die "$1 must be a positive integer, got: $2"
}

[[ -d "$CAUSAL_ROOT" ]] || die "causal repository not found: $CAUSAL_ROOT"
[[ -d "$TAU2_ROOT" ]] || die "Tau2 repository not found: $TAU2_ROOT"
require_file "$MANIFEST"
require_file "${CAUSAL_ROOT}/.venv/bin/activate"
[[ -n "${HF_TOKEN:-}" ]] || die "export HF_TOKEN before running"
[[ -n "${OPENAI_API_KEY:-}" ]] || die "export OPENAI_API_KEY before running"
require_positive_integer BASELINE_TRAIN_TRIALS "$BASELINE_TRAIN_TRIALS"
require_positive_integer BASELINE_VALIDATION_TRIALS "$BASELINE_VALIDATION_TRIALS"
require_positive_integer BASELINE_EVALUATION_TRIALS "$BASELINE_EVALUATION_TRIALS"

source "${CAUSAL_ROOT}/.venv/bin/activate"
mkdir -p "${CAUSAL_ROOT}/outputs"
touch "$RUN_LOG"

cd "$CAUSAL_ROOT"
python -m jlens_causal.failure_cli compile \
  "$MANIFEST" \
  --output "$MATRIX" \
  2>&1 | tee -a "$RUN_LOG"
require_file "$MATRIX"

python - <<'PY' 2>&1 | tee -a "$RUN_LOG"
import torch

if not torch.cuda.is_available():
    raise SystemExit("CUDA is not available")
major, minor = torch.cuda.get_device_capability()
if major < 8 or not torch.cuda.is_bf16_supported():
    raise SystemExit(
        f"GPU compute capability {major}.{minor} lacks required bfloat16 support"
    )
print(
    {
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(),
        "compute_capability": f"{major}.{minor}",
        "bfloat16_supported": torch.cuda.is_bf16_supported(),
    }
)
PY

WORKER_PORT="$(
python - <<'PY'
import socket

sock = socket.socket()
sock.bind(("127.0.0.1", 0))
print(sock.getsockname()[1])
sock.close()
PY
)"
export JLENS_REMOTE_ENDPOINT="http://127.0.0.1:${WORKER_PORT}"
export JLENS_REMOTE_TOKEN="${JLENS_REMOTE_TOKEN:-$(python -c 'import secrets; print(secrets.token_urlsafe(48))')}"

cd "$TAU2_ROOT"
python scripts/jlens_remote_worker.py \
  --host 127.0.0.1 \
  --port "$WORKER_PORT" \
  >"$WORKER_LOG" 2>&1 &
WORKER_PID=$!

cleanup() {
  kill "$WORKER_PID" 2>/dev/null || true
  wait "$WORKER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

WORKER_READY=0
for _ in $(seq 1 120); do
  if curl -fsS "${JLENS_REMOTE_ENDPOINT}/health" >/dev/null; then
    WORKER_READY=1
    break
  fi
  if ! kill -0 "$WORKER_PID" 2>/dev/null; then
    tail -n 100 "$WORKER_LOG" >&2
    die "worker failed to start"
  fi
  sleep 2
done
if [[ "$WORKER_READY" != 1 ]]; then
  tail -n 100 "$WORKER_LOG" >&2
  die "worker readiness timeout"
fi

python scripts/preflight_failure_steering.py \
  "$MATRIX" \
  --method baseline \
  --require-hf-token \
  2>&1 | tee -a "$RUN_LOG"

review_valid() {
  local results="$1"
  local reviewed="$2"
  [[ -s "$results" && -s "$reviewed" ]] || return 1
  python - "$results" "$reviewed" <<'PY'
import json
import sys

raw = json.load(open(sys.argv[1], encoding="utf-8"))
reviewed = json.load(open(sys.argv[2], encoding="utf-8"))

def keys(value):
    return {
        (str(item.get("task_id", "")), int(item.get("trial", 0) or 0))
        for item in value.get("simulations", [])
    }

if not keys(raw) or keys(raw) != keys(reviewed):
    raise SystemExit(1)
for item in reviewed.get("simulations", []):
    review = item.get("review")
    if not isinstance(review, dict):
        raise SystemExit(1)
    if not str(review.get("summary", "")).strip() and review.get("cost") is None:
        raise SystemExit(1)
PY
}

results_cover_requested_trials() {
  local results="$1"
  local split="$2"
  local trials="$3"
  [[ -s "$results" ]] || return 1
  python - "$results" "$MATRIX" "$split" "$trials" <<'PY'
import json
import sys

results_path, matrix_path, split, trials = sys.argv[1:]
value = json.load(open(results_path, encoding="utf-8"))
matrix = json.load(open(matrix_path, encoding="utf-8"))
actual = {
    (str(item.get("task_id", "")), int(item.get("trial", 0) or 0))
    for item in value.get("simulations", [])
}
expected = {
    (str(task_id), trial)
    for task_id in matrix["splits"][f"{split}_task_ids"]
    for trial in range(int(trials))
}
if actual != expected:
    raise SystemExit(1)
PY
}

review_results() {
  local results="$1"
  local reviewed="${results%/results.json}/results_reviewed.json"
  if review_valid "$results" "$reviewed"; then
    echo "Review already complete: $reviewed" | tee -a "$RUN_LOG"
    return
  fi
  local attempt
  for attempt in $(seq 1 "$REVIEW_ATTEMPTS"); do
    if [[ -e "$reviewed" ]]; then
      mv "$reviewed" "${reviewed%.json}.invalid-$(date +%Y%m%d-%H%M%S).json"
    fi
    echo "Review attempt ${attempt}/${REVIEW_ATTEMPTS}: $results" | tee -a "$RUN_LOG"
    if python -m tau2.cli review \
      "$results" \
      --mode full \
      --show-details \
      --max-concurrency 1 \
      --review-model "$REVIEW_MODEL" \
      2>&1 | tee -a "$RUN_LOG"; then
      if review_valid "$results" "$reviewed"; then
        return
      fi
    fi
    if [[ "$attempt" -lt "$REVIEW_ATTEMPTS" ]]; then
      sleep "$REVIEW_RETRY_DELAY_SECONDS"
    fi
  done
  die "invalid or incomplete review after ${REVIEW_ATTEMPTS} attempts: $reviewed"
}

collect_split() {
  local split="$1"
  local trials="$2"
  local condition_dir="data/simulations/${BASELINE_PREFIX}/${split}/baseline"
  local results="${condition_dir}/results.json"
  local reviewed="${condition_dir}/results_reviewed.json"

  echo "===== Baseline ${split}: ${trials} trial(s) per task =====" | tee -a "$RUN_LOG"
  if [[ -e "$reviewed" ]] && ! results_cover_requested_trials "$results" "$split" "$trials"; then
    mv "$reviewed" "${reviewed%.json}.before-extension-$(date +%Y%m%d-%H%M%S).json"
  fi
  python scripts/run_airline_failure_steering.py \
    "$MATRIX" \
    --condition baseline \
    --split "$split" \
    --num-trials "$trials" \
    --max-concurrency 1 \
    --save-prefix "$BASELINE_PREFIX" \
    --user-llm "$USER_MODEL" \
    --user-llm-args '{"reasoning_effort":"low"}' \
    2>&1 | tee -a "$RUN_LOG"
  results_cover_requested_trials "$results" "$split" "$trials" \
    || die "incomplete baseline coverage: $results"
  review_results "$results"
}

collect_split train "$BASELINE_TRAIN_TRIALS"
collect_split validation "$BASELINE_VALIDATION_TRIALS"
collect_split evaluation "$BASELINE_EVALUATION_TRIALS"

echo "Baseline data collection complete" | tee -a "$RUN_LOG"
echo "Train: 24 x ${BASELINE_TRAIN_TRIALS}" | tee -a "$RUN_LOG"
echo "Validation: 6 x ${BASELINE_VALIDATION_TRIALS}" | tee -a "$RUN_LOG"
echo "Evaluation: 20 x ${BASELINE_EVALUATION_TRIALS}" | tee -a "$RUN_LOG"
echo "Log: ${RUN_LOG}" | tee -a "$RUN_LOG"
