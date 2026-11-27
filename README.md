# AgentDojo and PropensityBench steering code (Qwen3.5)

This branch holds the code for two experiments. Both find neurons by comparing misaligned and aligned runs, then clamp those neurons so the model is steered from misaligned back to aligned behavior.

| Part | Benchmark | Models | Entry points |
|---|---|---|---|
| X20 | AgentDojo v1.2.2, `important_instructions` attack; suites slack and workspace (banking and travel also accepted) | Qwen3.5-4B, 9B, 27B | `dojo_suite.py`, `dojo_serve.py`, `ds_chain.sh`, `ds_lane.sh` |
| PB | PropensityBench (scaleapi/propensity-evaluation `09872f3`): 300 scenarios x 6 pressure categories = 1,800 tasks | Qwen3.5-4B | `ab_pb.py`, `pb_common.py`, `pb_serve.py`, `pb_run.py`, `pb_chain.sh` |

Status (2026-11-27): code only. No X20 step has been run. For PB, data download, task sampling and a CPU plumbing test have run: a scripted fake server on 18 tasks, with prompts rebuilt from rows matching the server md5 in 156 of 156 calls. The GPU parts of PB (vLLM server hooks, HF capture) have not been run.

## Models

The revisions are pinned in `dojo_suite.MODELS` and `pb_common.py`.

| Key | HF id | Revision | Layers x MLP neurons |
|---|---|---|---|
| 4b | Qwen/Qwen3.5-4B | 851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a | 32 x 9,216 |
| 9b | Qwen/Qwen3.5-9B | c202236235762e1c871ad0ccb60c8ee5ba337b9a | 32 x 12,288 |
| 27b | Qwen/Qwen3.5-27B | 81a287ca484a5e71148f5beb7f367bb5286d70f9 | 64 x 17,408 |

27B needs about 56 GB in bf16 and is meant for a single 80 GB GPU (`AB_PLATFORM=a80`). PB currently supports 4B only.

## X20: AgentDojo reading-stage clamp

Steps for each model and suite (full description in the `dojo_suite.py` docstring):

1. Base episodes on the HF server (`dojo_serve.py`, arm `<suite>.base`). The prompt ids of every request are logged.
2. Gate: the suite continues only if base ASR is at least 15 %.
3. Units: TARGET is an episode where the attack succeeded and REFERENCE one where it failed (`units_dojo_x19.py`). Units are rendered with the chat template and checked for request parity.
4. `compare`: misaligned vs aligned residual stream after attention and after the MLP, at every layer, at the injection span and at the decision position, with held-out AUROC by user-task fold. `arms` refuses to run until this report exists.
5. `readcap` + `arms`: the X15 rule on the suite's own units, never on a set from another suite or model. The K neurons with the largest median z (injection tokens vs other tool-result tokens) are clamped to the fold mean + 1 sd at tool-result positions only. Same-layer random neurons are the control. Sets are cross-fitted between user-task folds.
6. `smoke`: checks that the clamp acts and moves the logits.
7. Arm episodes, then `report`. Pass rule: pooled ASR of the selected set below the random set with one-sided Fisher p < 0.01, and no-attack utility at least base minus 1 task.

Run, with `code/` copied to `$AB_ROOT/ana`:

```bash
bash ds_chain.sh 4b "slack workspace"
AB_PLATFORM=a80 AB_ROOT=/path/to/tree AB_DS_LANES="0:18420" AB_DS_CAPGPU=0 bash ds_chain.sh 27b "slack workspace"
```

Outputs go to `ana/ds/<mk>/<suite>/` and `runs/ds_<mk>_<suite>_<arm>`. To stop, create `ana/ds/STOP` or `ana/ds/<mk>/STOP`.

## PB: PropensityBench

This applies the T9w recipe: neurons are picked by outcome and capped while the model generates. The subcommands of `ab_pb.py` are described in its docstring:

- `fetch`: downloads the 32 workspace files (Git LFS, sha256-checked).
- `sample`: folds by workspace, 75 scenarios per domain, 6 categories.
- Base episodes: `pb_serve.py` (in-process vLLM, eager) with `pb_run.py` (the official Agent / Executor / PropensityEvaluator; only the litellm transport is replaced).
- `units`: a misaligned unit is a decision step that calls the trigger tool, and each one is matched with 2 aligned steps.
- `capture`: teacher-forced HF pass over the units' generated tokens.
- `select`: AUROC per neuron in both selection halves. Sets H512, H1024 and H2048, plus rH1024 (same-layer random). The limit is the aligned token mean + 1 sd. Sets are cross-fitted between folds.
- Arms: `x <- min(x, limit)` at decode positions only.
- `report`: PropensityScore per arm, category and domain.

```bash
bash pb_chain.sh GPU LANE SHARD NSHARD PORT
```

## Files

- `dojo_suite.py`: X20 CLI (`env`, `tasks`, `fetch`, `queue`, `basecheck`, `rescap`, `compare`, `readcap`, `arms`, `smoke`, `report`).
- `dojo_serve.py`: OpenAI-compatible server, one model per process. The arm is chosen by URL (`/<suite>.<arm>/v1`).
- `ds_chain.sh`, `ds_lane.sh`: chain and job-queue lanes for X20.
- `ab_pb.py`, `pb_common.py`, `pb_serve.py`, `pb_run.py`, `pb_chain.sh`: PropensityBench.
- `ab_core.py`, `ab_ne.py`, `ab_xfit.py`, `ab_serve_steer.py`, `ab_regen.py`, `ab_hn.py`, `ab_strict.py`, `ab_search.py`, `ab_search_ta.py`, `ab_distrib.py`, `am_markers.py`, `units_am.py`, `units_dojo.py`, `units_dojo_x19.py`: the shared library the entry points import.
- `gpu_guard.sh`: refuses a GPU that has any process that is not ours.

## Requirements and what is not included

- Torch venv: torch, a transformers version with Qwen3.5 (`Qwen3_5ForConditionalGeneration`), flash-linear-attention (fla), numpy, scipy, scikit-learn, huggingface_hub.
- AgentDojo venv: `agentdojo` v1.2.2.
- PB server: vLLM 0.34.
- PB runner: a clone of scaleapi/propensity-evaluation at `09872f3` under `$AB_ROOT/propensity-evaluation`.
- Not included:
  - `ops/env_ab.sh`, the server environment that the shell scripts source.
  - Data, run outputs and model weights.
  - The J-lens package (`jlens`) and the ToolAlign modules (`model_profiles`, `trace_replay`, `ta_commit_edit`). Only ToolAlign and J-lens modes of `ab_ne.py`, `ab_distrib.py` and `ab_search_ta.py` import these, and X20 and PB do not use those modes.
- Default paths point to the original server tree (`AB_ROOT=/home/project-b/LJW/agentbench2`). Set `AB_ROOT`, `AB_TORCH_PY` and `AB_DOJO_PY` for another machine. PB paths are fixed in `pb_common.py` and `pb_chain.sh`; only `PB_DIR` can be overridden.
