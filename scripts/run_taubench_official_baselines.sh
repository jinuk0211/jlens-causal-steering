#!/usr/bin/env bash
# Tau2 airline failure-mode protocol with the six baselines executed through
# their authors' own pinned code (see OFFICIAL_BASELINES.md):
#   fetch upstreams -> repairs (reused if present) -> CAST condition pairs ->
#   fit official artifacts -> validation strength sweep -> frozen evaluation.
# Inputs are the same no-steering train/validation collections used by
# run_taubench_baselines5.sh.

set -Eeuo pipefail
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

CAUSAL_ROOT="${CAUSAL_ROOT:-/workspace/jlens-causal-steering}"
TAU2_ROOT="${TAU2_ROOT:-/workspace/tau2-bench}"
MANIFEST="${MANIFEST:-${CAUSAL_ROOT}/configs/taubench_airline_official_baselines_qwen35_4b.json}"
PREFIX="${PREFIX:-official-baselines-v1}"
BASELINE_PREFIX="${BASELINE_PREFIX:-failure-steering}"
FAILURE_CATEGORY="${FAILURE_CATEGORY:-tool_call_error}"
REVIEW_MODEL="${REVIEW_MODEL:-gpt-4.1-2025-04-14}"
USER_MODEL="${USER_MODEL:-gpt-5.2-2025-12-11}"
PROPOSAL_MODEL="${PROPOSAL_MODEL:-gpt-5.2}"
REVIEW_ATTEMPTS="${REVIEW_ATTEMPTS:-3}"
REVIEW_RETRY_DELAY_SECONDS="${REVIEW_RETRY_DELAY_SECONDS:-65}"
SIMULATION_TIMEOUT_SECONDS="${SIMULATION_TIMEOUT_SECONDS:-1200}"
METHODS=(caa cast mera sadi iti austeer)

OUT="${CAUSAL_ROOT}/outputs"
MATRIX="${OUT}/taubench-airline-official-matrix.json"
MERGED="${OUT}/taubench-airline-merged-reviewed.json"
AUDIT_DIR="${OUT}/taubench-airline-failure-audit"
EVENTS="${AUDIT_DIR}/failure-events.jsonl"
REPAIRS="${REPAIRS:-${OUT}/taubench-airline-repairs.jsonl}"
REPAIR_REPORT="${REPAIR_REPORT:-${OUT}/taubench-airline-repairs.report.json}"
REPAIR_PAIRS="${REPAIR_PAIRS:-${OUT}/taubench-airline-repair-pairs.jsonl}"
CAST_CONDITIONS="${CAST_CONDITIONS:-${OUT}/taubench-airline-cast-conditions.jsonl}"
RESULTS_ROOT="data/simulations/${PREFIX}"
TELEMETRY_ROOT="data/jlens-telemetry/${PREFIX}"
ANALYSIS_ROOT="data/analysis/${PREFIX}"
RUN_LOG="${RUN_LOG:-/workspace/taubench-official-baselines.log}"
WORKER_LOG="${WORKER_LOG:-/workspace/jlens-remote-worker-official.log}"
TRAIN_REVIEWED="${TAU2_ROOT}/data/simulations/${BASELINE_PREFIX}/train/baseline/results_reviewed.json"
VALIDATION_REVIEWED="${TAU2_ROOT}/data/simulations/${BASELINE_PREFIX}/validation/baseline/results_reviewed.json"

die() { echo "ERROR: $*" >&2; exit 1; }
require_file() { [[ -s "$1" ]] || die "required file is missing or empty: $1"; }
log() { echo "===== $* =====" | tee -a "$RUN_LOG"; }
prompt_secret() {
  local name="$1" prompt="$2"
  if [[ -n "${!name:-}" ]]; then export "$name"; return; fi
  [[ -r /dev/tty ]] || die "$name is unset and no interactive terminal is available"
  local value
  IFS= read -rsp "$prompt" value </dev/tty
  echo >/dev/tty
  [[ -n "$value" ]] || die "$name may not be empty"
  printf -v "$name" '%s' "$value"
  export "$name"
}

require_file "$MANIFEST"
require_file "$TRAIN_REVIEWED"
require_file "$VALIDATION_REVIEWED"
source "${CAUSAL_ROOT}/.venv/bin/activate"
prompt_secret HF_TOKEN "HF_TOKEN: "
prompt_secret OPENAI_API_KEY "OPENAI_API_KEY: "
mkdir -p "$OUT"
touch "$RUN_LOG"

log "Fetch pinned upstream baselines and their imports"
cd "$CAUSAL_ROOT"
bash scripts/fetch_official_upstreams.sh 2>&1 | tee -a "$RUN_LOG"
python -m pip install -e "${CAUSAL_ROOT}[official]" 2>&1 | tail -n 3 | tee -a "$RUN_LOG"

log "Prepare reviewed failure data"
python -m jlens_causal.failure_cli merge "$TRAIN_REVIEWED" "$VALIDATION_REVIEWED" \
  --output "$MERGED" 2>&1 | tee -a "$RUN_LOG"
python -m jlens_causal.failure_cli audit "$MERGED" --output-dir "$AUDIT_DIR" 2>&1 | tee -a "$RUN_LOG"

if [[ -s "$REPAIR_PAIRS" ]]; then
  log "Reusing validated repair pairs: $REPAIR_PAIRS"
else
  log "Generate and validate counterfactual repairs"
  python -u -m jlens_causal.failure_cli repairs "$MERGED" "$EVENTS" "$MANIFEST" \
    --category "$FAILURE_CATEGORY" --categories "$FAILURE_CATEGORY" \
    --output-category "$FAILURE_CATEGORY" \
    --output "$REPAIRS" --report "$REPAIR_REPORT" --pairs-output "$REPAIR_PAIRS" \
    --proposal-model "$PROPOSAL_MODEL" --review-model "$REVIEW_MODEL" \
    --reasoning-effort low --minimum-per-split 1 --maximum-per-split 8 \
    --max-attempts 5 --review-tpm 27000 2>&1 | tee -a "$RUN_LOG"
fi
require_file "$REPAIR_PAIRS"

if [[ ! -s "$CAST_CONDITIONS" ]]; then
  log "Build CAST condition pairs (failure-risk vs matched clean contexts)"
  python -m jlens_causal.failure_cli cast-conditions "$MERGED" "$EVENTS" "$MANIFEST" \
    --category "$FAILURE_CATEGORY" --output "$CAST_CONDITIONS" 2>&1 | tee -a "$RUN_LOG"
fi

log "Fit official artifacts (one model load)"
python -m jlens_causal.official.fit_cli all "$MANIFEST" "$REPAIR_PAIRS" \
  --condition-pairs "$CAST_CONDITIONS" --category "$FAILURE_CATEGORY" 2>&1 | tee -a "$RUN_LOG"

python -m jlens_causal.failure_cli compile "$MANIFEST" --output "$MATRIX" 2>&1 | tee -a "$RUN_LOG"
require_file "$MATRIX"

log "Start authenticated local GPU worker"
WORKER_PORT="$(python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
export JLENS_REMOTE_ENDPOINT="http://127.0.0.1:${WORKER_PORT}"
export JLENS_REMOTE_TOKEN="${JLENS_REMOTE_TOKEN:-$(python -c 'import secrets; print(secrets.token_urlsafe(48))')}"
cd "$TAU2_ROOT"
python scripts/jlens_remote_worker.py --host 127.0.0.1 --port "$WORKER_PORT" >"$WORKER_LOG" 2>&1 &
WORKER_PID=$!
trap 'kill "$WORKER_PID" 2>/dev/null || true; wait "$WORKER_PID" 2>/dev/null || true' EXIT INT TERM
for _ in $(seq 1 120); do
  curl -fsS "${JLENS_REMOTE_ENDPOINT}/health" >/dev/null && break
  kill -0 "$WORKER_PID" 2>/dev/null || { tail -n 100 "$WORKER_LOG" >&2; die "worker failed to start"; }
  sleep 2
done
curl -fsS "${JLENS_REMOTE_ENDPOINT}/health" >/dev/null || die "worker readiness timeout"
for method in "${METHODS[@]}"; do
  python scripts/preflight_failure_steering.py "$MATRIX" --method "$method" --require-hf-token \
    2>&1 | tee -a "$RUN_LOG"
done

review_valid() {
  python - "$1" "$2" <<'PY'
import json, sys
raw = json.load(open(sys.argv[1], encoding="utf-8"))
reviewed = json.load(open(sys.argv[2], encoding="utf-8"))
keys = lambda v: {(str(i.get("task_id", "")), int(i.get("trial", 0) or 0)) for i in v.get("simulations", [])}
if not keys(raw) or keys(raw) != keys(reviewed):
    raise SystemExit(1)
for item in reviewed.get("simulations", []):
    review = item.get("review")
    if not isinstance(review, dict) or (not str(review.get("summary", "")).strip() and review.get("cost") is None):
        raise SystemExit(1)
PY
}

log "Copy verified no-steering baselines into the run namespace"
for split in validation evaluation; do
  source_baseline="data/simulations/${BASELINE_PREFIX}/${split}/baseline"
  target_parent="${RESULTS_ROOT}/${split}"
  require_file "${source_baseline}/results.json"
  require_file "${source_baseline}/results_reviewed.json"
  review_valid "${source_baseline}/results.json" "${source_baseline}/results_reviewed.json" \
    || die "source ${split} baseline review is incomplete"
  mkdir -p "$target_parent"
  [[ -d "${target_parent}/baseline" ]] || cp -a "$source_baseline" "$target_parent/"
done

run_and_review() {
  local split="$1" condition="$2"
  local results="${RESULTS_ROOT}/${split}/${condition}/results.json"
  local reviewed="${RESULTS_ROOT}/${split}/${condition}/results_reviewed.json"
  log "${condition}: ${split}"
  python scripts/run_airline_failure_steering.py "$MATRIX" --condition "$condition" --split "$split" \
    --simulation-timeout-seconds "$SIMULATION_TIMEOUT_SECONDS" --save-prefix "$PREFIX" \
    --user-llm "$USER_MODEL" --user-llm-args '{"reasoning_effort":"low"}' 2>&1 | tee -a "$RUN_LOG"
  if [[ -s "$reviewed" ]] && review_valid "$results" "$reviewed"; then return; fi
  local attempt
  for attempt in $(seq 1 "$REVIEW_ATTEMPTS"); do
    [[ -e "$reviewed" ]] && mv "$reviewed" "${reviewed%.json}.invalid-$(date +%Y%m%d-%H%M%S).json"
    if python -m tau2.cli review "$results" --mode full --show-details --max-concurrency 1 \
      --review-model "$REVIEW_MODEL" 2>&1 | tee -a "$RUN_LOG" && review_valid "$results" "$reviewed"; then
      return
    fi
    sleep "$REVIEW_RETRY_DELAY_SECONDS"
  done
  die "invalid or incomplete review after ${REVIEW_ATTEMPTS} attempts: $reviewed"
}

mapfile -t VALIDATION_CONDITIONS < <(python - "$MATRIX" "$FAILURE_CATEGORY" <<'PY'
import json, sys
matrix = json.load(open(sys.argv[1], encoding="utf-8"))
for condition in matrix["conditions"]:
    if condition["control_type"] == "targeted" and condition["failure_category"] == sys.argv[2]:
        print(condition["name"])
PY
)
for condition in "${VALIDATION_CONDITIONS[@]}"; do
  run_and_review validation "$condition"
done
python scripts/analyze_airline_failure_steering.py "$MATRIX" --split validation \
  --results-root "$RESULTS_ROOT" --telemetry-root "$TELEMETRY_ROOT" --output-dir "$ANALYSIS_ROOT" \
  2>&1 | tee -a "$RUN_LOG"

# One strength per method by validation task success.  MERA's own calibration
# keeps the unsteered model (alpha = 1) unless some alpha is at least as good,
# so a MERA alpha that loses to the baseline is replaced by "baseline".
mapfile -t EVALUATION_CONDITIONS < <(python - "$ANALYSIS_ROOT/validation.json" "${METHODS[@]}" <<'PY'
import json, math, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
number = lambda v: -math.inf if v is None else float(v)
for method in sys.argv[2:]:
    rows = [r for r in data["summary"] if r["method"] == method and r["control_type"] == "targeted"
            and r["paired_coverage"] == 1.0 and r["review_coverage"] == 1.0]
    if not rows:
        raise SystemExit(f"{method}: no complete validation conditions")
    best = max(rows, key=lambda r: (number(r.get("mean_task_success")), number(r.get("mean_task_reward")),
                                    number(r.get("mean_repeat_reduction_vs_baseline")),
                                    number(r.get("mean_tool_error_reduction_vs_baseline")),
                                    -abs(number(r.get("strength")))))
    if method == "mera" and number(best.get("mean_success_delta_vs_baseline")) < 0:
        print("baseline")
    else:
        print(best["condition"])
PY
)
printf '%s\n' "${EVALUATION_CONDITIONS[@]}" | tee /workspace/official-baselines-selected-conditions.txt | tee -a "$RUN_LOG"
for condition in "${EVALUATION_CONDITIONS[@]}"; do
  [[ "$condition" == "baseline" ]] && continue
  run_and_review evaluation "$condition"
done
python scripts/analyze_airline_failure_steering.py "$MATRIX" --split evaluation \
  --results-root "$RESULTS_ROOT" --telemetry-root "$TELEMETRY_ROOT" --output-dir "$ANALYSIS_ROOT" \
  2>&1 | tee -a "$RUN_LOG"
log "Official-baseline run complete; analysis in ${TAU2_ROOT}/${ANALYSIS_ROOT}"
