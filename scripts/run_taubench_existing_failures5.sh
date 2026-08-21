#!/usr/bin/env bash
# Reuse completed no-steering baselines and pool localized review failures into
# one general agent-behavior direction for CAA, MERA, SADI, ITI, and AUSteer.

set -Eeuo pipefail

CAUSAL_ROOT="${CAUSAL_ROOT:-/workspace/jlens-causal-steering}"

export FAILURE_CATEGORY="agent_behavior_error"
export FAILURE_SOURCE_CATEGORIES="${FAILURE_SOURCE_CATEGORIES:-missed_required_action guideline_violation incorrect_interpretation wrong_sequence irrelevant_tool_call repeated_tool_call tool_call_error}"
export MANIFEST="${MANIFEST:-${CAUSAL_ROOT}/configs/taubench_airline_behavior_errors_qwen35_4b.json}"
export ARTIFACT_ROOT="${ARTIFACT_ROOT:-/workspace/jlens-artifacts/taubench-airline/agent-behavior-error}"
export PREFIX="${PREFIX:-failure-steering-behavior5-v1}"
export MATRIX="${MATRIX:-${CAUSAL_ROOT}/outputs/taubench-airline-behavior-matrix.json}"
export REPAIRS="${REPAIRS:-${CAUSAL_ROOT}/outputs/taubench-airline-behavior-repairs.jsonl}"
export REPAIR_REPORT="${REPAIR_REPORT:-${CAUSAL_ROOT}/outputs/taubench-airline-behavior-repairs.report.json}"
export REPAIR_PAIRS="${REPAIR_PAIRS:-${CAUSAL_ROOT}/outputs/taubench-airline-behavior-repair-pairs.jsonl}"
export REPAIR_SEED="${REPAIR_SEED:-${CAUSAL_ROOT}/outputs/taubench-airline-repairs.jsonl}"
export MINIMUM_TRAIN_EVENTS="${MINIMUM_TRAIN_EVENTS:-4}"
export MINIMUM_VALIDATION_EVENTS="${MINIMUM_VALIDATION_EVENTS:-4}"
export REPAIR_MINIMUM_PER_SPLIT="${REPAIR_MINIMUM_PER_SPLIT:-4}"
export REPAIR_MAX_PER_SPLIT="${REPAIR_MAX_PER_SPLIT:-4}"
export RUN_LOG="${RUN_LOG:-/workspace/taubench-behavior5.log}"
export WORKER_LOG="${WORKER_LOG:-/workspace/jlens-remote-worker-behavior5.log}"

exec bash "${CAUSAL_ROOT}/scripts/run_taubench_baselines5.sh"
