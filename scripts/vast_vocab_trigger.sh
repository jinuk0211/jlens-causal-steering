#!/usr/bin/env bash
# Vocab-trigger experiments on a vast.ai GPU:
#   1) all-layer pattern analysis of the failure vocabulary (forward pass per turn)
#   2) +/- steering replay on held-out turns
# Upload the telemetry first:  scp -P <port> vocab_trigger_data.tgz root@<host>:/workspace/
set -Eeuo pipefail

ROOT="${ROOT:-/workspace}"
REPO="$ROOT/jlens-causal-steering"
REF="${REF:-agent/official-baselines-tau2}"
DATA="$ROOT/vocab-trigger-data"
STAGE="${STAGE:-all}"          # patterns | sign | all
ALPHA="${ALPHA:-0.4}"

if [[ -d "$REPO/.git" ]]; then
  git -C "$REPO" fetch -q origin "$REF" && git -C "$REPO" checkout -q --detach FETCH_HEAD
else
  git clone -q --branch "$REF" https://github.com/jinuk0211/jlens-causal-steering.git "$REPO"
fi
mkdir -p "$DATA"
if [[ ! -d "$DATA/jlens-telemetry" ]]; then
  tar -xzf "$ROOT/vocab_trigger_data.tgz" -C "$DATA"
fi
cd "$REPO"
[[ -x .venv/bin/python ]] || python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -q -e . 2>&1 | tail -n 2
python -m pip install -q flash-linear-attention 2>&1 | tail -n 1 || true   # fast GatedDeltaNet kernels

export HF_HOME="${HF_HOME:-$ROOT/.hf_home}"
read -r MODEL LENS < <(python - <<'PY'
from huggingface_hub import snapshot_download
lens = snapshot_download("neuronpedia/jacobian-lens", revision="a4114d7752d11eb546e6cf372213d7e75526d3a1",
                         allow_patterns=["qwen3.5-4b/jlens/Salesforce-wikitext/Qwen3.5-4B_jacobian_lens_n1000.pt"])
model = snapshot_download("Qwen/Qwen3.5-4B", revision="851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a",
                          allow_patterns=["*.json", "*.safetensors", "*.txt", "*.jinja", "tokenizer*"])
print(model, lens + "/qwen3.5-4b/jlens/Salesforce-wikitext/Qwen3.5-4B_jacobian_lens_n1000.pt")
PY
)
TEL="$DATA/jlens-telemetry/failure-steering"
TASKS="$DATA/airline_tasks.json"
SPEC="configs/vocab_trigger/airline_qwen35_4b_layer16.json"
OUT="outputs/vocab_trigger"
mkdir -p "$OUT"

if [[ "$STAGE" == patterns || "$STAGE" == all ]]; then
  python scripts/vocab_trigger_patterns.py "$TEL" "$TASKS" --model-dir "$MODEL" --lens "$LENS" \
    --recompute --device cuda --output "$OUT/patterns_all_layers.json" | tee "$OUT/patterns_all_layers.log"
fi

if [[ "$STAGE" == sign || "$STAGE" == all ]]; then
  python scripts/vocab_trigger_select.py "$TEL" "$TASKS" "$SPEC" --model-dir "$MODEL" --lens "$LENS" \
    --output "$OUT/sign_triggered.jsonl"
  python scripts/vocab_trigger_select.py "$TEL" "$TASKS" "$SPEC" --model-dir "$MODEL" --lens "$LENS" \
    --untriggered --labels good_write --max-turns 15 --output "$OUT/sign_untriggered_good.jsonl"
  # Triggered held-out turns: +alpha (toward "ask"), -alpha (toward "comply strictly"), random +/-.
  python scripts/vocab_trigger_replay.py "$OUT/sign_triggered.jsonl" "$SPEC" "$TASKS" \
    --model-dir "$MODEL" --lens "$LENS" --precision cuda-bf16 \
    --alphas "$ALPHA" "-$ALPHA" --random-alphas "$ALPHA" "-$ALPHA" \
    --cap-to-logged --max-new-tokens 800 --output "$OUT/sign_triggered_results.jsonl"
  # Untriggered good writes: does pushing toward the risk vocabulary create bad writes?
  python scripts/vocab_trigger_replay.py "$OUT/sign_untriggered_good.jsonl" "$SPEC" "$TASKS" \
    --model-dir "$MODEL" --lens "$LENS" --precision cuda-bf16 \
    --alphas --random-alphas "-$ALPHA" --always-alphas "$ALPHA" "-$ALPHA" \
    --cap-to-logged --max-new-tokens 800 --output "$OUT/sign_always_good_results.jsonl"
  python scripts/vocab_trigger_summary.py "$OUT/sign_triggered_results.jsonl" "$OUT/sign_always_good_results.jsonl" \
    | tee "$OUT/sign_summary.txt"
fi
echo "done: $REPO/$OUT"
