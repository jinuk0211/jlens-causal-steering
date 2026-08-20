#!/usr/bin/env bash
# Full restartable Qwen3.5-4B workflow on a fresh Vast instance.

set -Eeuo pipefail

CAUSAL_ROOT="${CAUSAL_ROOT:-/workspace/jlens-causal-steering}"

bash "${CAUSAL_ROOT}/scripts/collect_taubench_baselines5_data.sh"
bash "${CAUSAL_ROOT}/scripts/run_taubench_baselines5.sh"
