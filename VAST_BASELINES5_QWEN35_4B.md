# Qwen3.5-4B TauBench five-baseline run on a fresh Vast.ai instance

This is the end-to-end path for exactly these methods:

- CAA
- MERA
- SADI
- ITI
- AUSteer

CAST is excluded from the checked TauBench manifest. The removed learned
low-rank method is not installed, trained, or evaluated.

The compiled matrix also retains J-Servo, the study's proposed controller.
The scripts in this guide deliberately run only the five comparison baselines;
they neither require nor evaluate a J-Servo artifact.

The data dependency is:

```text
no-steering train/validation runs
  -> official full reviews
  -> localized failure events
  -> OpenAI-proposed and independently reviewed repairs
  -> validated (observed failure, repair) pairs
  -> five .pt artifacts
  -> validation strength selection
  -> frozen evaluation
```

There is no valid shortcut around the repair-pair gate. For the configured
`retry_without_state_change` category, artifact extraction requires at least
two eligible events and two validated repair pairs in both the train and
validation task splits. More trials increase the opportunity to observe that
failure but cannot guarantee it; a model that never exhibits the failure does
not support this experiment.

## 1. Before renting the instance

The two working branches must contain the current local changes. In particular,
the fresh clone must contain these files:

```text
jlens-causal-steering/scripts/collect_taubench_baselines5_data.sh
jlens-causal-steering/scripts/run_taubench_baselines5.sh
jlens-causal-steering/scripts/run_taubench_baselines5_fresh_vast.sh
tau2-bench/scripts/preflight_failure_steering.py
```

Commit and push the reviewed changes to:

```text
jinuk0211/jlens-causal-steering  branch agent/jlens-thought-steering
jinuk0211/tau2-bench             branch codex/jlens-telecom-backend
```

Do not start a paid instance until cloning those branches and finding the files
above is possible.

## 2. Vast.ai instance choice

Recommended configuration:

- One verified, on-demand NVIDIA GPU.
- 48 GB VRAM preferred: L40S, RTX A6000, A40, or A100 40/80 GB.
- 24 GB VRAM is the budget floor (RTX 3090/4090), with less OOM headroom.
- Ampere or newer GPU with BF16 support.
- At least 32 GB system RAM; 64 GB preferred.
- 100 GB instance disk; use 150 GB if retaining extensive logs/checkpoints.
- Reliability at least 0.98, good disk bandwidth, and sufficient rental duration.
- Vast's PyTorch/SSH template or another Ubuntu CUDA image with SSH access.

The pinned Qwen repository is about 9.34 GB and defines a 4B, 32-layer model.
Artifact extraction also needs model working memory and activation buffers, so
VRAM must not be sized from weight files alone. See the official
[Qwen3.5-4B repository](https://huggingface.co/Qwen/Qwen3.5-4B) and
[model files](https://huggingface.co/Qwen/Qwen3.5-4B/tree/main).

Vast's default disk is only 10 GB, and the instance disk cannot be resized after
creation. Storage is billed while an instance exists, including when stopped.
See Vast's [instance selection guide](https://docs.vast.ai/guides/instances/choosing/find-and-rent)
and [pricing guide](https://docs.vast.ai/guides/instances/pricing).

## 3. Connect and install everything

SSH into the new instance, then paste this block. Vast containers normally run
as root and expose `/workspace` as persistent instance storage.

```bash
set -Eeuo pipefail

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  build-essential ca-certificates curl git jq tmux

curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="/root/.local/bin:${PATH}"
uv python install 3.12

export HF_HOME=/workspace/.cache/huggingface
export UV_CACHE_DIR=/workspace/.cache/uv
mkdir -p "$HF_HOME" "$UV_CACHE_DIR"

cd /workspace
git clone --branch agent/jlens-thought-steering --single-branch \
  https://github.com/jinuk0211/jlens-causal-steering.git
git clone --branch codex/jlens-telecom-backend --single-branch \
  https://github.com/jinuk0211/tau2-bench.git

test -s /workspace/jlens-causal-steering/scripts/collect_taubench_baselines5_data.sh
test -s /workspace/jlens-causal-steering/scripts/run_taubench_baselines5.sh
test -s /workspace/jlens-causal-steering/scripts/run_taubench_baselines5_fresh_vast.sh
test -s /workspace/tau2-bench/scripts/preflight_failure_steering.py

cd /workspace/jlens-causal-steering
uv venv --python 3.12 .venv
source .venv/bin/activate

uv pip install torch --torch-backend=auto
uv pip install -e '.[dev]'
uv pip install -e '../tau2-bench[knowledge,experiments,dev]'
uv pip check
```

`--torch-backend=auto` asks `uv` to select the PyTorch wheel compatible with
the installed NVIDIA driver. It is documented in Astral's
[PyTorch integration guide](https://docs.astral.sh/uv/guides/integration/pytorch/).

## 4. Export credentials and verify the machine

Start a persistent terminal first:

```bash
tmux new -s baselines5
```

Inside tmux, export the two credentials you created. Do not paste real values
into a tracked file or shell script.

```bash
export HF_TOKEN='replace-with-your-new-token'
export OPENAI_API_KEY='replace-with-your-new-key'
export HF_HOME=/workspace/.cache/huggingface
export UV_CACHE_DIR=/workspace/.cache/uv
export PATH="/root/.local/bin:${PATH}"

cd /workspace/jlens-causal-steering
source .venv/bin/activate
```

Verify CUDA, BF16, imports, the exact model revision, and the five-method
manifest:

```bash
python - <<'PY'
import json
import torch
import transformers
import tau2
import jlens_causal
from huggingface_hub import snapshot_download

assert torch.cuda.is_available(), "CUDA is unavailable"
assert torch.cuda.is_bf16_supported(), "GPU does not support BF16"
print("torch", torch.__version__, "cuda", torch.version.cuda)
print("gpu", torch.cuda.get_device_name())
print("transformers", transformers.__version__)

manifest_path = "configs/taubench_airline_failure_modes_qwen35_4b.json"
manifest = json.load(open(manifest_path, encoding="utf-8"))
assert manifest["enabled_methods"] == ["caa", "mera", "sadi", "iti", "austeer"]
assert "cast" not in manifest["failure_modes"]["retry_without_state_change"]["methods"]

path = snapshot_download(
    repo_id="Qwen/Qwen3.5-4B",
    revision="851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a",
)
print("pinned model cache", path)
PY
```

## 5. Run the complete restartable pipeline

The defaults collect five trials per train task, five per validation task, and
one per held-out evaluation task. They then generate repairs, extract all five
artifacts in one model load, run three validation strengths per method, select
one condition per method without using evaluation outcomes, and run the frozen
evaluation.

```bash
export BASELINE_TRAIN_TRIALS=5
export BASELINE_VALIDATION_TRIALS=5
export BASELINE_EVALUATION_TRIALS=1
export SIMULATION_TIMEOUT_SECONDS=1200

export USER_MODEL='gpt-5.2-2025-12-11'
export REVIEW_MODEL='gpt-4.1-2025-04-14'
export PROPOSAL_MODEL='gpt-5.2'

cd /workspace/jlens-causal-steering
bash scripts/run_taubench_baselines5_fresh_vast.sh
```

If one of those OpenAI model IDs is unavailable to the account, set the
corresponding environment variable to an available compatible model before
starting. Keep the same IDs for all conditions within a completed experiment.

Detach from tmux with `Ctrl-b`, then `d`. Reattach and inspect logs with:

```bash
tmux attach -t baselines5
tail -f /workspace/taubench-baselines5-data.log
tail -f /workspace/taubench-baselines5.log
tail -f /workspace/jlens-remote-worker-baselines5.log
nvidia-smi
```

The driver is restartable. After an SSH disconnect or recoverable API failure,
run the same command again inside the same instance and workspace.
Each individual simulation is capped at 1200 wallclock seconds by default;
completed task/trial checkpoints are reused when the driver is restarted.

## 6. If the repair-pair gate stops the run

The script prints an event inventory. If
`retry_without_state_change` has fewer than two eligible train or validation
events, increase only the calibration trials and resume:

```bash
cd /workspace/jlens-causal-steering
source .venv/bin/activate

export BASELINE_TRAIN_TRIALS=10
export BASELINE_VALIDATION_TRIALS=10
export BASELINE_EVALUATION_TRIALS=1

bash scripts/run_taubench_baselines5_fresh_vast.sh
```

Do not lower a trial count after data has already been collected in the same
prefix. If ten trials still produce no eligible failure in either split, that
is an experimental data result: the configured failure category is unsupported
for this deterministic Qwen setup. Do not fabricate pairs or reuse evaluation
tasks for calibration.

## 7. Expected artifacts and workload

Validated pair data:

```text
/workspace/jlens-causal-steering/outputs/taubench-airline-repairs.jsonl
/workspace/jlens-causal-steering/outputs/taubench-airline-repairs.report.json
/workspace/jlens-causal-steering/outputs/taubench-airline-repair-pairs.jsonl
```

Five model artifacts:

```text
/workspace/jlens-artifacts/taubench-airline/retry/caa-layer-20.pt
/workspace/jlens-artifacts/taubench-airline/retry/mera-layer-20.pt
/workspace/jlens-artifacts/taubench-airline/retry/sadi-hidden-units.pt
/workspace/jlens-artifacts/taubench-airline/retry/iti-heads.pt
/workspace/jlens-artifacts/taubench-airline/retry/austeer-attention-aus.pt
```

Final selection and analysis:

```text
/workspace/baselines5-selected-conditions.txt
/workspace/tau2-bench/data/analysis/failure-steering-baselines5-v1/validation.json
/workspace/tau2-bench/data/analysis/failure-steering-baselines5-v1/evaluation.json
```

With default trial counts, the pipeline creates 170 no-steering trajectories
(120 train, 30 validation, 20 evaluation), then 90 steered validation and 100
steered evaluation trajectories: 360 trajectories total. Each trajectory can
contain multiple OpenAI-backed user-simulator calls, and every trajectory is
fully reviewed, so OpenAI usage is likely a larger monetary cost than creation
of the five small `.pt` files.

Of the remaining methods, CAA and MERA are the lightest. SADI is moderate. ITI
and especially AUSteer require finer attention/head or atomic-unit statistics
and are the most compute-heavy of the five, but they do not train a language
model. If another method must be removed later for compute reasons, AUSteer is
the first candidate; that is a protocol change and should be made before data
collection, not midway through a run.

## 8. Archive results before deleting the instance

```bash
cd /workspace
archive="baselines5-qwen35-4b-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
tar -czf "$archive" \
  jlens-causal-steering/outputs \
  jlens-artifacts/taubench-airline \
  tau2-bench/data/simulations/failure-steering \
  tau2-bench/data/simulations/failure-steering-baselines5-v1 \
  tau2-bench/data/jlens-telemetry/failure-steering-baselines5-v1 \
  tau2-bench/data/analysis/failure-steering-baselines5-v1 \
  baselines5-selected-conditions.txt \
  taubench-baselines5-data.log \
  taubench-baselines5.log

sha256sum "$archive" | tee "${archive}.sha256"
ls -lh "$archive" "${archive}.sha256"
```

Download both files and verify the checksum before deleting the Vast instance.
Stopping an instance does not stop storage charges; deletion does.
