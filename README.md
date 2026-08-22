# ToolAlign thought-axis J-lens causal steering

This repository tests whether a cross-domain internal thought direction can
causally move both Jacobian-lens readouts and downstream ToolAlign behavior.
It is separate from ToolAlignBench and uses its public prompts, tool taxonomy,
and XML system prompt unchanged.

The complete Core-6 integration (CAA, CAST, MERA, SADI, ITI, and AUSteer) and
runnable ToolAlign aligned/abliterated plus TauBench Airline Task
18 protocols are in [STEERING_EXPERIMENTS.md](STEERING_EXPERIMENTS.md).

The generic, remote-only failure-mode protocol that replaces fixed Task-18
turn selection is in [FAILURE_MODE_STEERING.md](FAILURE_MODE_STEERING.md).

The fresh Vast.ai commands for the Qwen3.5-4B five-baseline TauBench run are in
[VAST_BASELINES5_QWEN35_4B.md](VAST_BASELINES5_QWEN35_4B.md).

## Experimental design

The checked-in split uses 12 calibration domains (48 matched document pairs)
and four held-out evaluation domains. Evaluation domains never participate in
target selection or direction construction.

At the pre-response position of layer 30, the runner computes the
`wrongdoing - safe` Jacobian-lens logit difference within every matched pair.
It removes tool/XML terms, function words, and domain-specific names. A target
candidate must be a complete word found in at least three calibration domains
and be more prevalent in the corresponding safe or wrongdoing documents. Its
readout sign must agree in at least 9 of 12 domains and it must remain a top
leave-one-domain-out effect in at least 9 of 12 folds. The five highest stable
tokens in each direction form transparent targets `u_safe` and
`u_wrongdoing`, weighted by absolute cross-domain mean effect.

For intervention layer `l` and target `t`, the additive J-lens direction is

```text
d_jlens[l, t] = normalize(J[l].T @ u_t) * mean_calibration_residual_norm[l]
```

The comparison direction is the paired activation contrast

```text
d_contrastive[l, safe->wrongdoing]
  = normalize(mean_pair(h_wrongdoing[l] - h_safe[l])) * residual_norm[l]
```

and every random vector is independently sampled at the same layer norm. The
candidate intervention modifies only tokens belonging to the current user
document, once during prompt prefill. It is never reapplied during cached
decoding. The wrong-position control modifies the same number of tokens in the
system/tool-schema span. The wrong-layer control uses the same vector at a
non-candidate layer.

The exploratory coordinate swap applies the automatically selected safe and
wrongdoing J-lens coordinates simultaneously across the 24/26/28 band. It is
reported separately from additive, norm-matched methods.

## Outcomes

Every run stores the layer-30 `u_wrongdoing - u_safe` margin immediately before
the response and at the first 32 generated decision sites. The primary thought
contrast is

```text
thought_delta = effect_steer - mean_seed(effect_random)
```

Downstream behavior uses ToolAlign's parsing-based profile: no-tool, aligned
logging/internal email, boundary actions, and clearly misaligned actions.
Internal versus external email is classified from sender/recipient domains as
in ToolAlign's analyzer. A matched alpha-zero pair whose behavior profiles are
identical has `baseline_discriminative=0` and is excluded from behavior-flip
success; it cannot produce a false success merely because both sides used the
same tool.

`joint_causal_success=1` requires a valid completion, positive random-adjusted
thought movement, and positive random-adjusted behavior movement. Text change
alone is never success. Parse errors and 4096-token truncations receive zero
causal credit and are reported as corruption.

The primary pilot runs every document as an independent first response. The
original four-document, up-to-ten-step trajectory is reserved for a later
confirmatory run after this isolated causal test shows a signal.

## Setup and commands

Python 3.10+ and a CUDA PyTorch environment capable of loading Qwen3.5-4B are
required for execution.

```bash
git clone https://github.com/jinuk0211/jlens-causal-steering.git
git clone https://github.com/jinuk0211/ToolAlignBench.git
cd jlens-causal-steering
python -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Validate paths and exact generation counts without loading the model:

```bash
jlens-causal validate configs/smoke.json
jlens-causal plan configs/qwen35_toolalign_pilot.json
```

Run a fresh corrected 18-generation smoke test:

```bash
jlens-causal all configs/smoke.json --fresh
```

Run or resume the 4,640-generation powered held-out pilot:

```bash
jlens-causal all configs/qwen35_toolalign_pilot.json
```

The powered pilot covers four held-out domains by four independent documents,
layers 24/26/28, `alpha={0,.25,.5,1,2,4}`, five norm-matched random seeds, and
wrong-layer/wrong-position controls at alpha 1 and 2. Alpha 4 is a fixed
high-dose point and receives no credit when it causes parse errors or
truncation. Both configs use deterministic generation and ToolAlign inference's
`max_new_tokens=4096` default. `--fresh` deletes only known runner artifacts.
Without it, compatible JSONL records resume by deterministic `run_id`. Config,
target-selection, schema, intervention, and generation changes are included in
fingerprints, so old smoke results cannot be reused.

## Outputs

Each config writes to its own output directory:

- `target_selection.json`: selected thought tokens, effects, weights,
  cross-domain consistency, and leave-one-domain-out frequency;
- `directions.pt`: tensor-only targets, `J.T @ u` directions, contrastive and
  random controls, residual scales, and fingerprint;
- `manifest.json`: resolved config, fingerprints, and planned counts;
- `runs.jsonl`: raw completions, exact intervention metadata, termination,
  thought trace, and ToolAlign behavior profile;
- `thought_trajectories.csv`: pre-response and first-32 generated margins;
- `behavior_profiles.csv`: original ToolAlign-style parsed behavior fields;
- `trial_metrics.csv`: source/target alpha-zero pairing and random-adjusted
  thought, behavior, joint, corruption, and safe-degradation outcomes;
- `summary.csv`: grouped means and domain/document cluster-bootstrap intervals.

An invalid alpha-zero baseline stops the sweep before treatments. Invalid
treatments remain in the output with success zero and corruption one.

## Vast.ai

Use a recent PyTorch CUDA image, at least 40 GB disk, and a GPU that can load
the pinned 4B model. The raw bootstrap clones/pulls both repositories, installs
the environment, verifies CUDA, and validates the smoke config.

Fresh smoke:

```bash
cd /workspace
curl -fsSL https://raw.githubusercontent.com/jinuk0211/jlens-causal-steering/agent/jlens-thought-steering/scripts/vast_setup.sh | bash -s -- smoke agent/jlens-thought-steering
```

Full run in `tmux` after the smoke is accepted:

```bash
cd /workspace
curl -fsSL https://raw.githubusercontent.com/jinuk0211/jlens-causal-steering/agent/jlens-thought-steering/scripts/vast_setup.sh | bash -s -- setup agent/jlens-thought-steering
tmux new -s jlens
source /workspace/jlens-causal-steering/.venv/bin/activate
export HF_HOME=/workspace/.cache/huggingface
cd /workspace/jlens-causal-steering
jlens-causal all configs/qwen35_toolalign_pilot.json 2>&1 | tee outputs/powered-pilot.log
```

Detach with `Ctrl-b d`; reconnect with `tmux attach -t jlens`.

References: [Jacobian Lens](https://transformer-circuits.pub/2026/workspace/),
[official implementation](https://github.com/anthropics/jacobian-lens),
[ToolAlignBench](https://github.com/aryankeluskar/ToolAlignBench), and
[Contrastive Activation Addition](https://github.com/nrimsky/CAA).

## Post-success stop/repeat steering

The page-derived follow-up experiment targets the strongest observed ToolAlign
state transition: after a controlled `writeInternalLog` call returns a real
successful `<tool_result>`, should the model stop or issue another tool call?
The intervention is applied once to the tool-result message tokens. The next
independent model response is the behavioral outcome, so this changes the
actual post-tool decision rather than merely changing an offline J-lens score.

The completion concept axis is preregistered from the analysis page as
`u_stop - u_repeat`. J-lens uses the exact
`normalize(J.T @ (u_stop - u_repeat))` direction. The contrastive control is
estimated only from 12 calibration domains as
`normalize(mean(h_stop) - mean(h_repeat))`, where stop/repeat labels come from
the model's genuine unsteered post-success response. Evaluation uses four
disjoint domains. Both directions, norm-matched random vectors, wrong layer,
and token-count-matched wrong position are included.

The smoke sweep writes 22 evaluation records after 96 held-out calibration
responses. The powered sweep writes 5,536 evaluation records (plus the same 96
calibration responses when directions are freshly extracted), using layers
20/24 and `alpha={.25,.5,1,2,4}` with five random seeds.

On a new Vast.ai instance, the following single command installs everything,
runs and validates the smoke test, then launches the powered run in a detached
`tmux` session (or `nohup` when tmux is unavailable):

```bash
cd /workspace && curl -fsSL https://raw.githubusercontent.com/jinuk0211/jlens-causal-steering/agent/jlens-thought-steering/scripts/vast_followup.sh | bash -s -- all agent/jlens-thought-steering
```

Monitor it with `tmux attach -t jlens-followup` or
`tail -f /workspace/jlens-causal-steering/outputs/followup-powered.log`.
