# J-lens causal steering pilot

An independent, resumable experiment runner for testing whether a steering
direction causes a paired ToolAlign behavior transition, rather than merely
corrupting generation.

The default pilot compares:

- one shared `alpha=0` baseline per prompt;
- additive `J^T u` concept differences;
- contrastive `mean(h_B) - mean(h_A)` directions;
- five norm-matched random directions;
- the same steering at a wrong layer and a wrong token position;
- both `A -> B` and `B -> A` interventions;
- the Jacobian Lens paper's two-coordinate swap as a separate, non-additive
  analysis.

The runner uses the exact prompt/tool builder from an existing ToolAlignBench
checkout without copying benchmark code into this repository.

## Design

For layer `l`, the contrastive direction is

```text
d_contrastive[l] = mean(h_B[l]) - mean(h_A[l])
```

Single-token concept aliases define the J-lens concept directions

```text
v_A[l] = normalize(J[l].T @ mean(W_U[alias_A]))
v_B[l] = normalize(J[l].T @ mean(W_U[alias_B]))
d_jlens[l] = normalize(v_B[l] - v_A[l]) * ||d_contrastive[l]||
```

Every random vector is independently sampled and scaled to the same
contrastive norm. Additive interventions are therefore

```text
A -> B: h' = h + alpha * d
B -> A: h' = h - alpha * d
```

The paper-style coordinate intervention builds `V = [v_A, v_B]`, obtains
`c = pinv(V) @ h`, swaps the two coordinates, and interpolates with `alpha`.
This method is reported separately because it is not an additive norm-matched
direction.

`position_policy="all"` modifies all positions seen by the layer during
prefill and cached decoding. The wrong-position control defaults to only the
first prompt position.

References: [Jacobian Lens](https://transformer-circuits.pub/2026/workspace/),
[official implementation](https://github.com/anthropics/jacobian-lens), and
[Contrastive Activation Addition](https://github.com/nrimsky/CAA).

## Setup

Python 3.10+ and a CUDA environment capable of loading the configured model
are recommended.

```bash
git clone <this-repository>
cd jlens-causal-steering
python -m venv .venv
python -m pip install -e ".[dev]"
```

Edit `data.toolalign_root` in the config if ToolAlignBench is not adjacent to
this repository. Model and lens revisions are pinned in the checked-in pilot
configs.

## Commands

Validate paths, selections, and the exact generation count without loading a
model:

```bash
jlens-causal validate configs/smoke.json
jlens-causal plan configs/qwen35_toolalign_pilot.json
```

Run a small end-to-end smoke test:

```bash
jlens-causal all configs/smoke.json --fresh
```

Run the full pilot in explicit phases:

```bash
jlens-causal extract-directions configs/qwen35_toolalign_pilot.json
jlens-causal run configs/qwen35_toolalign_pilot.json
jlens-causal analyze configs/qwen35_toolalign_pilot.json
```

`run` appends one flushed JSON object after every generation. Re-running it
skips completed deterministic `run_id` values. The ID includes the full
generation configuration, so results made with a different token limit cannot
be reused silently. `--fresh` removes only this runner's known artifacts before
an `all` run; `--limit N` bounds new generations without discarding compatible
results.

Both checked-in configs use ToolAlignBench inference's deterministic default
limit of `max_new_tokens=4096`. A completion that reaches this limit without an
EOS is recorded as truncated. An invalid alpha-zero baseline stops the sweep
before any causal comparison is made.

## Outputs

Each config has its own `output_dir`:

- `directions.pt`: tensor-only direction artifact with a config fingerprint;
- `manifest.json`: resolved config and planned generation counts;
- `runs.jsonl`: raw generation, termination metadata, treatment, and behavior;
- `trial_metrics.csv`: treatment paired with source/target alpha-zero baselines;
- `summary.csv`: grouped means and domain/document cluster-bootstrap intervals.

The two primary success definitions are matching the counterpart baseline's
coarse behavior class and matching its exact tool-name signature. For either
binary success metric `S`, the reported causal contrast is

```text
effect_steer = S_steer - S_alpha0
effect_random = mean_seed(S_random - S_alpha0)
causal_delta = effect_steer - effect_random
```

`safe_degradation` is the loss of the `aligned` indicator relative to the
same safe prompt's alpha-zero output. Parse errors, truncation, and the combined
`invalid_output`/`corruption_increase` fields are reported separately and always
receive zero target-success credit.

## Vast.ai

Choose a recent PyTorch CUDA image, attach at least 40 GB of disk, and use a
GPU with enough memory for the configured 4B model. From a fresh Vast.ai
terminal, the bootstrap script clones this repository and ToolAlignBench as
sibling directories, creates a virtual environment that can reuse the
image's CUDA-enabled PyTorch, installs the runner, and validates the data.

Setup only:

```bash
cd /workspace
curl -fsSL https://raw.githubusercontent.com/jinuk0211/jlens-causal-steering/main/scripts/vast_setup.sh | bash -s -- setup
```

Run a fresh 18-generation smoke grid immediately after setup. This intentionally
replaces any earlier smoke artifacts, including the obsolete 64-token run:

```bash
cd /workspace
curl -fsSL https://raw.githubusercontent.com/jinuk0211/jlens-causal-steering/main/scripts/vast_setup.sh | bash -s -- smoke
```

For the full 1,064-generation pilot, use a persistent shell such as `tmux`:

```bash
cd /workspace
curl -fsSL https://raw.githubusercontent.com/jinuk0211/jlens-causal-steering/main/scripts/vast_setup.sh | bash -s -- setup
tmux new -s jlens
source /workspace/jlens-causal-steering/.venv/bin/activate
export HF_HOME=/workspace/.cache/huggingface
cd /workspace/jlens-causal-steering
mkdir -p outputs
jlens-causal all configs/qwen35_toolalign_pilot.json 2>&1 | tee outputs/full-pilot.log
```

Detach from `tmux` with `Ctrl-b d` and reconnect with `tmux attach -t jlens`.
The runner is resumable: rerunning the same command skips completed `run_id`
records in `runs.jsonl`.

## Important interpretation notes

- Calibration and evaluation domains must not overlap; validation rejects
  such configs.
- Concept aliases must contain at least one single tokenizer token. Resolved
  token IDs are saved in `directions.pt` for auditability.
- A coarse-class transition is weaker evidence than a paired tool-signature
  transition. Report both.
- Wrong-site controls are evaluated at the configured control alpha. Random
  causal deltas are calculated where matched random trials exist (the main
  candidate site by default).
