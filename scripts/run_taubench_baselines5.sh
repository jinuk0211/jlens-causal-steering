#!/usr/bin/env bash
# Restartable TauBench Airline five-baseline run after no-steering data collection:
# repairs -> five artifacts -> validation selection -> frozen evaluation.

set -Eeuo pipefail

# Qwen3.5 can approach the 16 GiB boundary on max-token steering failures.
# Expandable CUDA segments reduce fragmentation between sequential turns.
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

CAUSAL_ROOT="${CAUSAL_ROOT:-/workspace/jlens-causal-steering}"
TAU2_ROOT="${TAU2_ROOT:-/workspace/tau2-bench}"
ARTIFACT_ROOT="${ARTIFACT_ROOT:-/workspace/jlens-artifacts/taubench-airline/tool-call-error}"
PREFIX="${PREFIX:-failure-steering-baselines5-v1}"
BASELINE_PREFIX="${BASELINE_PREFIX:-failure-steering}"
FAILURE_CATEGORY="${FAILURE_CATEGORY:-tool_call_error}"
FAILURE_SOURCE_CATEGORIES="${FAILURE_SOURCE_CATEGORIES:-$FAILURE_CATEGORY}"
read -r -a FAILURE_SOURCE_CATEGORY_ARGS <<<"$FAILURE_SOURCE_CATEGORIES"
MINIMUM_TRAIN_EVENTS="${MINIMUM_TRAIN_EVENTS:-2}"
MINIMUM_VALIDATION_EVENTS="${MINIMUM_VALIDATION_EVENTS:-1}"
REPAIR_MINIMUM_PER_SPLIT="${REPAIR_MINIMUM_PER_SPLIT:-$MINIMUM_VALIDATION_EVENTS}"
REVIEW_MODEL="${REVIEW_MODEL:-gpt-4.1-2025-04-14}"
USER_MODEL="${USER_MODEL:-gpt-5.2-2025-12-11}"
PROPOSAL_MODEL="${PROPOSAL_MODEL:-gpt-5.2}"
REPAIR_MAX_ATTEMPTS="${REPAIR_MAX_ATTEMPTS:-5}"
REPAIR_MAX_PER_SPLIT="${REPAIR_MAX_PER_SPLIT:-8}"
REVIEW_ATTEMPTS="${REVIEW_ATTEMPTS:-3}"
REVIEW_RETRY_DELAY_SECONDS="${REVIEW_RETRY_DELAY_SECONDS:-65}"
SIMULATION_TIMEOUT_SECONDS="${SIMULATION_TIMEOUT_SECONDS:-1200}"
FIXED_STRENGTH_EVALUATION_ONLY="${FIXED_STRENGTH_EVALUATION_ONLY:-0}"

MANIFEST="${MANIFEST:-${CAUSAL_ROOT}/configs/taubench_airline_failure_modes_qwen35_4b.json}"
TOOLS_JSON="${CAUSAL_ROOT}/configs/taubench_airline_tools.json"
MATRIX="${MATRIX:-${CAUSAL_ROOT}/outputs/taubench-airline-failure-matrix.json}"
MERGED="${CAUSAL_ROOT}/outputs/taubench-airline-merged-reviewed.json"
AUDIT_DIR="${CAUSAL_ROOT}/outputs/taubench-airline-failure-audit"
EVENTS="${AUDIT_DIR}/failure-events.jsonl"
REPAIRS="${REPAIRS:-${CAUSAL_ROOT}/outputs/taubench-airline-repairs.jsonl}"
REPAIR_REPORT="${REPAIR_REPORT:-${CAUSAL_ROOT}/outputs/taubench-airline-repairs.report.json}"
REPAIR_PAIRS="${REPAIR_PAIRS:-${CAUSAL_ROOT}/outputs/taubench-airline-repair-pairs.jsonl}"
REPAIR_SEED="${REPAIR_SEED:-}"
RESULTS_ROOT="data/simulations/${PREFIX}"
TELEMETRY_ROOT="data/jlens-telemetry/${PREFIX}"
ANALYSIS_ROOT="data/analysis/${PREFIX}"
RUN_LOG="${RUN_LOG:-/workspace/taubench-baselines5.log}"
WORKER_LOG="${WORKER_LOG:-/workspace/jlens-remote-worker-baselines5.log}"

TRAIN_REVIEWED="${TAU2_ROOT}/data/simulations/${BASELINE_PREFIX}/train/baseline/results_reviewed.json"
VALIDATION_REVIEWED="${TAU2_ROOT}/data/simulations/${BASELINE_PREFIX}/validation/baseline/results_reviewed.json"

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

prompt_secret() {
  local name="$1"
  local prompt="$2"
  if [[ -n "${!name:-}" ]]; then
    export "$name"
    return
  fi
  [[ -r /dev/tty ]] || die "$name is unset and no interactive terminal is available"
  local value
  IFS= read -rsp "$prompt" value </dev/tty
  echo >/dev/tty
  [[ -n "$value" ]] || die "$name may not be empty"
  printf -v "$name" '%s' "$value"
  export "$name"
}

[[ -d "$CAUSAL_ROOT" ]] || die "causal repository not found: $CAUSAL_ROOT"
[[ -d "$TAU2_ROOT" ]] || die "Tau2 repository not found: $TAU2_ROOT"
require_file "$MANIFEST"
require_file "$TOOLS_JSON"
require_file "$TRAIN_REVIEWED"
require_file "$VALIDATION_REVIEWED"
require_positive_integer SIMULATION_TIMEOUT_SECONDS "$SIMULATION_TIMEOUT_SECONDS"

source "${CAUSAL_ROOT}/.venv/bin/activate"
prompt_secret HF_TOKEN "HF_TOKEN: "
prompt_secret OPENAI_API_KEY "OPENAI_API_KEY: "

mkdir -p "${CAUSAL_ROOT}/outputs" "$ARTIFACT_ROOT"
touch "$RUN_LOG"

echo "===== Prepare reviewed failure data =====" | tee -a "$RUN_LOG"
cd "$CAUSAL_ROOT"
python -m jlens_causal.failure_cli merge \
  "$TRAIN_REVIEWED" \
  "$VALIDATION_REVIEWED" \
  --output "$MERGED" \
  2>&1 | tee -a "$RUN_LOG"

python -m jlens_causal.failure_cli audit \
  "$MERGED" \
  --output-dir "$AUDIT_DIR" \
  2>&1 | tee -a "$RUN_LOG"

python - \
  "$EVENTS" \
  "$MANIFEST" \
  "$MINIMUM_TRAIN_EVENTS" \
  "$MINIMUM_VALIDATION_EVENTS" \
  "${FAILURE_SOURCE_CATEGORY_ARGS[@]}" <<'PY' \
  2>&1 | tee -a "$RUN_LOG"
import json
import sys
from collections import Counter

events_path, manifest_path, minimum_train, minimum_validation, *categories = sys.argv[1:]
minimum_train = int(minimum_train)
minimum_validation = int(minimum_validation)
manifest = json.load(open(manifest_path, encoding="utf-8"))
split_by_task = {
    str(task_id): split
    for split in ("train", "validation")
    for task_id in manifest["splits"][f"{split}_task_ids"]
}
counts = Counter()
inventory = Counter()
with open(events_path, encoding="utf-8") as handle:
    for line in handle:
        event = json.loads(line)
        split = split_by_task.get(str(event.get("task_id")))
        if split and event.get("steerable") and event.get("first_bad_message_index") is not None:
            inventory[(str(event.get("category")), split)] += 1
            if event.get("category") in categories and float(event.get("confidence", 0.0)) >= 0.5:
                counts[split] += 1
print("eligible structural/review event inventory:")
for (name, split), count in sorted(inventory.items()):
    print(f"  {name:36s} {split:10s} {count}")
print(f"pooled source categories {categories!r}: train={counts['train']} validation={counts['validation']}")
if counts["train"] < minimum_train or counts["validation"] < minimum_validation:
    raise SystemExit(
        f"Need at least {minimum_train} eligible train event(s) and "
        f"{minimum_validation} eligible validation event(s). "
        "Rerun the no-steering collection with larger BASELINE_TRAIN_TRIALS and "
        "BASELINE_VALIDATION_TRIALS before artifact extraction."
    )
PY

echo "===== Generate and validate counterfactual repairs =====" | tee -a "$RUN_LOG"
REPAIR_SEED_ARGS=()
if [[ -n "$REPAIR_SEED" && -s "$REPAIR_SEED" ]]; then
  REPAIR_SEED_ARGS=(--seed-repairs "$REPAIR_SEED")
fi
python -u -m jlens_causal.failure_cli repairs \
  "$MERGED" \
  "$EVENTS" \
  "$MANIFEST" \
  --category "$FAILURE_CATEGORY" \
  --categories "${FAILURE_SOURCE_CATEGORY_ARGS[@]}" \
  --output-category "$FAILURE_CATEGORY" \
  "${REPAIR_SEED_ARGS[@]}" \
  --output "$REPAIRS" \
  --report "$REPAIR_REPORT" \
  --pairs-output "$REPAIR_PAIRS" \
  --proposal-model "$PROPOSAL_MODEL" \
  --review-model "$REVIEW_MODEL" \
  --reasoning-effort low \
  --minimum-per-split "$REPAIR_MINIMUM_PER_SPLIT" \
  --maximum-per-split "$REPAIR_MAX_PER_SPLIT" \
  --max-attempts "$REPAIR_MAX_ATTEMPTS" \
  --review-tpm 27000 \
  2>&1 | tee -a "$RUN_LOG"

python -m jlens_causal.failure_cli compile \
  "$MANIFEST" \
  --output "$MATRIX" \
  2>&1 | tee -a "$RUN_LOG"

require_file "$REPAIR_PAIRS"
require_file "$MATRIX"

ARTIFACTS=(
  "$ARTIFACT_ROOT/caa-layer-20.pt"
  "$ARTIFACT_ROOT/mera-layer-20.pt"
  "$ARTIFACT_ROOT/sadi-hidden-units.pt"
  "$ARTIFACT_ROOT/iti-heads.pt"
  "$ARTIFACT_ROOT/austeer-attention-aus.pt"
)

validate_artifacts() {
  python - "$ARTIFACT_ROOT" <<'PY'
import sys
from pathlib import Path

import torch

from jlens_causal.baselines import (
    load_austeer_artifact,
    load_caa_artifact,
    load_iti_artifact,
    load_mera_artifact,
    load_sadi_artifact,
)

root = Path(sys.argv[1])
model_id = "Qwen/Qwen3.5-4B"
load_caa_artifact(
    torch,
    root / "caa-layer-20.pt",
    expected_model_id=model_id,
    expected_layer=20,
)
load_mera_artifact(
    torch,
    root / "mera-layer-20.pt",
    expected_model_id=model_id,
    expected_layer=20,
)
load_sadi_artifact(torch, root / "sadi-hidden-units.pt", expected_model_id=model_id)
load_iti_artifact(torch, root / "iti-heads.pt", expected_model_id=model_id)
load_austeer_artifact(
    torch,
    root / "austeer-attention-aus.pt",
    expected_model_id=model_id,
)
print("Validated all five baseline artifacts")
PY
}

ARTIFACTS_READY=1
for artifact in "${ARTIFACTS[@]}"; do
  if [[ ! -s "$artifact" ]]; then
    ARTIFACTS_READY=0
    break
  fi
done
if [[ "$ARTIFACTS_READY" == 1 ]] && ! validate_artifacts; then
  ARTIFACTS_READY=0
fi

if [[ "$ARTIFACTS_READY" == 1 ]]; then
  echo "===== Five baseline artifacts already complete =====" | tee -a "$RUN_LOG"
else
  echo "===== Extract five baseline artifacts (one model load) =====" | tee -a "$RUN_LOG"
  python scripts/extract_airline_failure_artifacts.py all \
    "$MANIFEST" \
    "$REPAIR_PAIRS" \
    --category "$FAILURE_CATEGORY" \
    --layers 20 24 \
    --attention-layers 19 23 \
    --tools-json "$TOOLS_JSON" \
    --output-dir "$ARTIFACT_ROOT" \
    2>&1 | tee -a "$RUN_LOG"
fi

for artifact in "${ARTIFACTS[@]}"; do
  require_file "$artifact"
done
validate_artifacts 2>&1 | tee -a "$RUN_LOG"

echo "===== Start authenticated local GPU worker =====" | tee -a "$RUN_LOG"
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

for method in caa mera sadi iti austeer; do
  python scripts/preflight_failure_steering.py \
    "$MATRIX" \
    --method "$method" \
    --require-hf-token \
    2>&1 | tee -a "$RUN_LOG"
done

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

echo "===== Copy verified baselines into lean run namespace =====" | tee -a "$RUN_LOG"
for split in validation evaluation; do
  source_baseline="data/simulations/${BASELINE_PREFIX}/${split}/baseline"
  target_parent="${RESULTS_ROOT}/${split}"
  target_baseline="${target_parent}/baseline"
  require_file "${source_baseline}/results.json"
  require_file "${source_baseline}/results_reviewed.json"
  review_valid "${source_baseline}/results.json" "${source_baseline}/results_reviewed.json" \
    || die "source ${split} baseline review is incomplete"
  mkdir -p "$target_parent"
  if [[ -d "$target_baseline" ]] \
    && ! review_valid "${target_baseline}/results.json" "${target_baseline}/results_reviewed.json"; then
    mv "$target_baseline" "${target_baseline}.invalid-$(date +%Y%m%d-%H%M%S)"
  fi
  if [[ ! -d "$target_baseline" ]]; then
    cp -a "$source_baseline" "$target_parent/"
  fi
done

run_and_review() {
  local split="$1"
  local condition="$2"
  local condition_dir="${RESULTS_ROOT}/${split}/${condition}"
  local results="${condition_dir}/results.json"
  local reviewed="${condition_dir}/results_reviewed.json"

  echo "===== ${condition}: ${split} =====" | tee -a "$RUN_LOG"
  python scripts/run_airline_failure_steering.py \
    "$MATRIX" \
    --condition "$condition" \
    --split "$split" \
    --simulation-timeout-seconds "$SIMULATION_TIMEOUT_SECONDS" \
    --save-prefix "$PREFIX" \
    --user-llm "$USER_MODEL" \
    --user-llm-args '{"reasoning_effort":"low"}' \
    2>&1 | tee -a "$RUN_LOG"

  if review_valid "$results" "$reviewed"; then
    echo "Review already complete: $reviewed" | tee -a "$RUN_LOG"
    return
  fi

  local attempt
  for attempt in $(seq 1 "$REVIEW_ATTEMPTS"); do
    if [[ -e "$reviewed" ]]; then
      mv "$reviewed" "${reviewed%.json}.invalid-$(date +%Y%m%d-%H%M%S).json"
    fi
    echo "Review attempt ${attempt}/${REVIEW_ATTEMPTS}: ${condition}" | tee -a "$RUN_LOG"
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
      echo "Review incomplete; waiting ${REVIEW_RETRY_DELAY_SECONDS}s before retry" \
        | tee -a "$RUN_LOG"
      sleep "$REVIEW_RETRY_DELAY_SECONDS"
    fi
  done
  die "invalid or incomplete review after ${REVIEW_ATTEMPTS} attempts: $reviewed"
}

if [[ "$FIXED_STRENGTH_EVALUATION_ONLY" == 1 ]]; then
  echo "===== Skip validation sweep; use one fixed strength per method =====" \
    | tee -a "$RUN_LOG"
  EVALUATION_CONDITIONS=(
    "${FAILURE_CATEGORY}-caa-s1"
    "${FAILURE_CATEGORY}-mera-s1"
    "${FAILURE_CATEGORY}-sadi-s10"
    "${FAILURE_CATEGORY}-iti-s10"
    "${FAILURE_CATEGORY}-austeer-s10"
  )
else
  VALIDATION_CONDITIONS=(
    "${FAILURE_CATEGORY}-caa-s0.5"
    "${FAILURE_CATEGORY}-caa-s1"
    "${FAILURE_CATEGORY}-caa-s2"
    "${FAILURE_CATEGORY}-mera-s0.5"
    "${FAILURE_CATEGORY}-mera-s1"
    "${FAILURE_CATEGORY}-mera-s2"
    "${FAILURE_CATEGORY}-sadi-s5"
    "${FAILURE_CATEGORY}-sadi-s10"
    "${FAILURE_CATEGORY}-sadi-s20"
    "${FAILURE_CATEGORY}-iti-s5"
    "${FAILURE_CATEGORY}-iti-s10"
    "${FAILURE_CATEGORY}-iti-s15"
    "${FAILURE_CATEGORY}-austeer-s5"
    "${FAILURE_CATEGORY}-austeer-s10"
    "${FAILURE_CATEGORY}-austeer-s15"
  )

  for condition in "${VALIDATION_CONDITIONS[@]}"; do
    run_and_review validation "$condition"
  done

  python scripts/analyze_airline_failure_steering.py \
    "$MATRIX" \
    --split validation \
    --results-root "$RESULTS_ROOT" \
    --telemetry-root "$TELEMETRY_ROOT" \
    --output-dir "$ANALYSIS_ROOT" \
    2>&1 | tee -a "$RUN_LOG"

  mapfile -t EVALUATION_CONDITIONS < <(
    python - "$ANALYSIS_ROOT/validation.json" <<'PY'
import json
import math
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
methods = ["caa", "mera", "sadi", "iti", "austeer"]

def number(value):
    return -math.inf if value is None else float(value)

for method in methods:
    candidates = [
        row
        for row in data["summary"]
        if row["method"] == method
        and row["control_type"] == "targeted"
        and row["paired_coverage"] == 1.0
        and row["review_coverage"] == 1.0
    ]
    if len(candidates) != 3:
        raise SystemExit(f"{method}: expected 3 complete conditions, found {len(candidates)}")
    best = max(
        candidates,
        key=lambda row: (
            number(row.get("mean_task_success")),
            number(row.get("mean_task_reward")),
            number(row.get("mean_repeat_reduction_vs_baseline")),
            number(row.get("mean_tool_error_reduction_vs_baseline")),
            -abs(number(row.get("strength"))),
        ),
    )
    print(best["condition"])
PY
  )
fi

[[ "${#EVALUATION_CONDITIONS[@]}" -eq 5 ]] \
  || die "expected five selected evaluation conditions"
printf '%s\n' "${EVALUATION_CONDITIONS[@]}" \
  | tee /workspace/baselines5-selected-conditions.txt \
  | tee -a "$RUN_LOG"

for condition in "${EVALUATION_CONDITIONS[@]}"; do
  run_and_review evaluation "$condition"
done

python scripts/analyze_airline_failure_steering.py \
  "$MATRIX" \
  --split evaluation \
  --results-root "$RESULTS_ROOT" \
  --telemetry-root "$TELEMETRY_ROOT" \
  --output-dir "$ANALYSIS_ROOT" \
  2>&1 | tee -a "$RUN_LOG"

echo "Five-baseline run complete" | tee -a "$RUN_LOG"
if [[ "$FIXED_STRENGTH_EVALUATION_ONLY" == 1 ]]; then
  echo "Validation strength sweep: skipped (fixed strengths)" | tee -a "$RUN_LOG"
  echo "Evaluation: 5 fixed conditions x 20 tasks = 100" | tee -a "$RUN_LOG"
  echo "Total steered in this protocol: 100 trajectories" | tee -a "$RUN_LOG"
else
  echo "Validation: 15 conditions x 6 tasks = 90" | tee -a "$RUN_LOG"
  echo "Evaluation: 5 selected conditions x 20 tasks = 100" | tee -a "$RUN_LOG"
  echo "Total steered: 190 trajectories" | tee -a "$RUN_LOG"
fi
echo "Selected conditions: /workspace/baselines5-selected-conditions.txt" | tee -a "$RUN_LOG"
echo "Analysis: ${TAU2_ROOT}/${ANALYSIS_ROOT}" | tee -a "$RUN_LOG"
echo "Log: ${RUN_LOG}" | tee -a "$RUN_LOG"
