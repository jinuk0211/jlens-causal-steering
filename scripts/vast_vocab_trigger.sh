#!/usr/bin/env bash
# Vocab-trigger experiments on a vast.ai GPU:
#   sign      +/- steering replay on held-out turns (run first: the main question)
#   patterns  all-layer pattern analysis of the failure vocabulary (forward pass per turn)
# Upload the telemetry first:  scp -P <port> vocab_trigger_data.tgz root@<host>:/workspace/
#
# STREAM=1 is for hosts whose disk cannot hold the 9 GB checkpoint: the weights are
# streamed from the Hub straight into GPU memory, and the turn selections must be
# uploaded as $DATA/selections/sign_*.jsonl (vocab_trigger_select.py run elsewhere).
# BASE_PYTHON reuses an existing torch install (venv with --system-site-packages).
set -Eeuo pipefail

ROOT="${ROOT:-/workspace}"
REPO="$ROOT/jlens-causal-steering"
REF="${REF:-agent/official-baselines-tau2}"
DATA="$ROOT/vocab-trigger-data"
STAGE="${STAGE:-all}"            # sign | patterns | all
ALPHA="${ALPHA:-0.4}"
PRECISION="${PRECISION:-cuda-fp32}"   # cuda-bf16 on Ampere+; Turing (2080 Ti) has no fast bf16
PATTERN_DTYPE="${PATTERN_DTYPE:-float32}"
PATTERN_TURNS="${PATTERN_TURNS:-500}"
STREAM="${STREAM:-0}"
BASE_PYTHON="${BASE_PYTHON:-python3}"
JLENS="jlens @ git+https://github.com/jinuk0211/visual-jlens.git@021c19beb934dfeaeb1130b2431e39e536a858d3"

if [[ -d "$REPO/.git" ]]; then
  git -C "$REPO" fetch -q origin "$REF" && git -C "$REPO" checkout -q --detach FETCH_HEAD
else
  git clone -q --branch "$REF" https://github.com/jinuk0211/jlens-causal-steering.git "$REPO"
fi
mkdir -p "$DATA"
[[ -d "$DATA/jlens-telemetry" ]] || tar -xzf "$ROOT/vocab_trigger_data.tgz" -C "$DATA"
cd "$REPO"
[[ -x .venv/bin/python ]] || "$BASE_PYTHON" -m venv --system-site-packages .venv
source .venv/bin/activate
# PyPI's torch 2.8 wheel is the CUDA 12.8 build; its nvidia-* deps also come from PyPI
# (the download.pytorch.org index pulls them from pypi.nvidia.com, which can time out).
# uv downloads packages in parallel, which matters on hosts with slow single connections.
# torch is never re-resolved through the repo's metadata, so an existing install is kept.
if command -v uv >/dev/null; then
  PIP=(uv pip install -q --python .venv/bin/python)
else
  PIP=(python -m pip install -q --retries 10 --timeout 120)
fi
python -c "import torch" 2>/dev/null || "${PIP[@]}" "torch==2.8.0"
"${PIP[@]}" "transformers>=5.5" "huggingface-hub>=0.23" "numpy>=1.26" requests safetensors
"${PIP[@]}" --no-deps "$JLENS"
"${PIP[@]}" --no-deps -e .
python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"

export HF_HOME="${HF_HOME:-$ROOT/.hf_home}"
read -r MODEL LENS < <(STREAM="$STREAM" python - <<'PY'
import os
from huggingface_hub import snapshot_download
lens = snapshot_download("neuronpedia/jacobian-lens", revision="a4114d7752d11eb546e6cf372213d7e75526d3a1",
                         allow_patterns=["qwen3.5-4b/jlens/Salesforce-wikitext/Qwen3.5-4B_jacobian_lens_n1000.pt"])
patterns = ["*.json", "*.txt", "*.jinja", "tokenizer*"]
if os.environ["STREAM"] != "1":
    patterns.append("*.safetensors")
model = snapshot_download("Qwen/Qwen3.5-4B", revision="851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a",
                          allow_patterns=patterns, max_workers=16)
print(model, lens + "/qwen3.5-4b/jlens/Salesforce-wikitext/Qwen3.5-4B_jacobian_lens_n1000.pt")
PY
)
TEL="$DATA/jlens-telemetry/failure-steering"
TASKS="$DATA/airline_tasks.json"
SPEC="configs/vocab_trigger/airline_qwen35_4b_layer16.json"
OUT="outputs/vocab_trigger"
mkdir -p "$OUT"
STREAM_FLAG=()
[[ "$STREAM" == 1 ]] && STREAM_FLAG=(--stream-weights)

if [[ "$STAGE" == sign || "$STAGE" == all ]]; then
  if [[ "$STREAM" == 1 ]]; then
    # Selections made on another host: point their telemetry paths at this host's copy.
    for name in sign_triggered sign_untriggered_good; do
      python - "$DATA/selections/$name.jsonl" "$TEL" "$OUT/$name.jsonl" <<'PY'
import json, re, sys
source, root, target = sys.argv[1:]
with open(source, encoding="utf-8") as fin, open(target, "w", encoding="utf-8") as fout:
    for line in fin:
        row = json.loads(line)
        split, name = re.split(r"[\\/]", row["telemetry_path"])[-2:]
        row["telemetry_path"] = f"{root}/{split}/{name}"
        fout.write(json.dumps(row, ensure_ascii=False) + "\n")
PY
    done
  else
    python scripts/vocab_trigger_select.py "$TEL" "$TASKS" "$SPEC" --model-dir "$MODEL" --lens "$LENS" \
      --output "$OUT/sign_triggered.jsonl"
    python scripts/vocab_trigger_select.py "$TEL" "$TASKS" "$SPEC" --model-dir "$MODEL" --lens "$LENS" \
      --untriggered --labels good_write --max-turns 15 --output "$OUT/sign_untriggered_good.jsonl"
  fi
  # Triggered held-out turns: +alpha (toward "ask"), -alpha (toward "comply strictly"), random +/-.
  python scripts/vocab_trigger_replay.py "$OUT/sign_triggered.jsonl" "$SPEC" "$TASKS" \
    --model-dir "$MODEL" --lens "$LENS" --precision "$PRECISION" --prefill-chunk 4096 "${STREAM_FLAG[@]}" \
    --alphas "$ALPHA" "-$ALPHA" --random-alphas "$ALPHA" "-$ALPHA" \
    --cap-to-logged --max-new-tokens 800 --output "$OUT/sign_triggered_results.jsonl"
  # Untriggered good writes: does pushing toward the risk vocabulary create bad writes?
  python scripts/vocab_trigger_replay.py "$OUT/sign_untriggered_good.jsonl" "$SPEC" "$TASKS" \
    --model-dir "$MODEL" --lens "$LENS" --precision "$PRECISION" --prefill-chunk 4096 "${STREAM_FLAG[@]}" \
    --alphas --random-alphas "-$ALPHA" --always-alphas "$ALPHA" "-$ALPHA" \
    --cap-to-logged --max-new-tokens 800 --output "$OUT/sign_always_good_results.jsonl"
  python scripts/vocab_trigger_summary.py "$OUT/sign_triggered_results.jsonl" "$OUT/sign_always_good_results.jsonl" \
    | tee "$OUT/sign_summary.txt"
fi

if [[ "$STAGE" == patterns || "$STAGE" == all ]]; then
  python scripts/vocab_trigger_patterns.py "$TEL" "$TASKS" --model-dir "$MODEL" --lens "$LENS" \
    --recompute --device cuda --dtype "$PATTERN_DTYPE" --max-turns "$PATTERN_TURNS" "${STREAM_FLAG[@]}" \
    --output "$OUT/patterns_all_layers.json" | tee "$OUT/patterns_all_layers.log"
fi
echo "done: $REPO/$OUT"
