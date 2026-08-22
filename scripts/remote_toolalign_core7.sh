#!/usr/bin/env bash
set -euo pipefail

METHOD="${1:-caa}"
PHASE="${2:-validate}"
ROLE="${3:-both}"
STEERING_ROOT="${STEERING_ROOT:-/workspace/jlens-causal-steering}"

case "${METHOD}" in
  caa|cast|mera|sadi|iti|austeer) ;;
  *) echo "method must be caa|cast|mera|sadi|iti|austeer" >&2; exit 2 ;;
esac
case "${PHASE}" in
  validate|baseline|extract|sweep|analyze|full) ;;
  *) echo "phase must be validate|baseline|extract|sweep|analyze|full" >&2; exit 2 ;;
esac
case "${ROLE}" in
  aligned|abliterated|both) ;;
  *) echo "role must be aligned|abliterated|both" >&2; exit 2 ;;
esac

cd "${STEERING_ROOT}"
source .venv/bin/activate

python - <<'PY'
import torch

if not torch.cuda.is_available():
    raise SystemExit("ToolAlign Core-7 execution requires a remote CUDA host")
print("remote CUDA:", torch.cuda.get_device_name(0))
PY

CONFIG="configs/toolalign_${METHOD}_llama8b.json"
if [[ "${METHOD}" == "caa" ]]; then
  CONFIG="configs/toolalign_caa_llama8b.json"
fi

validate() {
  if [[ "${METHOD}" == "caa" ]]; then
    python -m jlens_causal.steering_cli validate-toolalign-caa "${CONFIG}"
  else
    python -m jlens_causal.steering_cli "validate-toolalign-${METHOD}" "${CONFIG}"
  fi
}

run_role_phase() {
  local role="$1"
  local phase="$2"
  local command
  case "${phase}" in
    baseline)
      command="toolalign-baseline"
      [[ "${METHOD}" != "caa" ]] && command="toolalign-baseline-${METHOD}"
      ;;
    extract) command="toolalign-extract-${METHOD}" ;;
    sweep) command="toolalign-sweep-${METHOD}" ;;
    analyze) command="toolalign-analyze-${METHOD}" ;;
    *) echo "unsupported role phase ${phase}" >&2; exit 2 ;;
  esac
  python -m jlens_causal.steering_cli "${command}" "${CONFIG}" --role "${role}"
}

roles=(aligned abliterated)
if [[ "${ROLE}" != "both" ]]; then roles=("${ROLE}"); fi

if [[ "${PHASE}" == "validate" ]]; then
  validate
  exit 0
fi

validate
phases=("${PHASE}")
if [[ "${PHASE}" == "full" ]]; then phases=(baseline extract sweep analyze); fi
for phase in "${phases[@]}"; do
  for role in "${roles[@]}"; do
    run_role_phase "${role}" "${phase}"
  done
done
