# Failure-mode steering: executable protocol

This is the non-Task-18 default protocol. It never selects an intervention by a
hard-coded conversation turn. Tau2 emits online boundaries from the observed
trajectory:

- `after_tool_error`
- `after_repeated_tool_error`
- `after_repeated_tool_call`
- `after_short_tool_cycle`
- `after_successful_tool_result`

The treatment boundary is the last observable state *before* the action that
must change. For example, `retry_without_state_change` is treated at
`after_tool_error`, not after the same failed call has already been repeated.
The repeated-call boundaries remain available as post-hoc recovery controls.

The model and hidden-state hooks run on an authenticated remote GPU worker. The
local Tau2 process only runs the environment, user simulator, result writer,
and official reviewer.

The project dependency is pinned to Jacobian Lens commit
`021c19beb934dfeaeb1130b2431e39e536a858d3` from
`jinuk0211/jacobian-lens`, so the extraction and runtime machines use the same
exact-token implementation (including position chunking).

## What is implemented

- Official Tau2 review import with agent/user attribution and exact `turn_idx`.
- Structural localization of explicit tool errors, unchanged retries, short
  cycles, unresolved calls, protocol errors, and bad termination.
- A replay plan with no-steer, post-hoc oracle, learned-gate, count-matched
  random-gate, negative-direction, and wrong-category conditions.
- A remote-only Core-7 condition matrix for CAA, CAST, MERA, SADI, ITI,
  AUSteer, and LoReFT.
- `jlens-jservo-v1` artifacts with failure-mode token bundles, observer/control
  layers, protected directions, target margins, natural-delta dose caps, and
  calibration fingerprints. The runtime computes the minimum remaining
  margin edit at each layer and records zero dose after an earlier recovery.
- A non-executing candidate buffer with typed-schema, identifier-provenance,
  and unchanged-repeat validation. Cap excess, missing signal, or validator
  failure is recorded as `abstained` before a tool can execute.
- Generic CAA, CAST, MERA, SADI, ITI, AUSteer, and LoReFT extractors using validated
  `repair - observed failure` action
  pairs. It measures the last token in the pairwise-divergent rendered action
  span, so a changed tool argument is measured instead of a shared XML/chat
  suffix.
- Paired TauBench analysis of reward, task success, tool errors, retries,
  loops, official agent-review errors, user-review errors, and verified
  intervention dose.
- CAST learns a prospective failure-risk condition gate from failed and clean
  decisions at the same structural opportunity boundary. LoReFT trains only
  its low-rank intervention on repaired assistant continuations, selecting the
  checkpoint on task-disjoint validation pairs.
- Existing ToolAlign Core-7 full-trajectory analyzers for aligned-to-worse and
  abliterated-to-aligned behavior transitions.

## Leakage-controlled TauBench sequence

The checked manifest preserves Tau2's official 30-task train and 20-task test
split. Six train tasks are reserved for validation, leaving 24 artifact-training
tasks. Evaluation tasks cannot be used to build repair pairs. The runner,
preflight, and analyzer validate the compiled IDs against Tau2's checked-in
`data/tau2/domains/airline/split_tasks.json` and reject any mismatch.

Compile the Core-7 plus J-Servo condition matrix without loading a model:

```powershell
cd D:\jlens\jlens-causal-steering
.\.venv\Scripts\python.exe -m jlens_causal.failure_cli compile `
  configs\taubench_airline_failure_modes_qwen35_4b.json `
  --output outputs\taubench-airline-failure-matrix.json
```

Start the model worker on the remote GPU machine. Both repositories and the
artifacts are expected under `/workspace`:

```bash
cd /workspace/tau2-bench
source .venv/bin/activate
export JLENS_REMOTE_TOKEN='<random-secret>'
python scripts/jlens_remote_worker.py --host 0.0.0.0 --port 8877
```

Expose the worker through TLS or an authenticated private tunnel. On the local
machine, set the URL and the same token. Before running a benchmark, verify the
compiled matrix, all seven method families, credentials, and remote health
without printing any secret values:

```powershell
cd D:\jlens\tau2-bench
.\.venv\Scripts\python.exe scripts\preflight_failure_steering.py `
  D:\jlens\jlens-causal-steering\outputs\taubench-airline-failure-matrix.json `
  --method baseline
```

This authenticated check runs on the worker and requires CUDA. After extracting
one method's artifacts, run it again with (for example) `--method caa`; it then
verifies every remote CAA artifact path before allowing the sweep. Add
`--require-hf-token` when the selected remote model is gated.

Then reproduce training trajectories:

```powershell
$env:JLENS_REMOTE_ENDPOINT = 'https://gpu-worker.example'
$env:JLENS_REMOTE_TOKEN = '<random-secret>'
cd D:\jlens\tau2-bench
.\.venv\Scripts\python.exe scripts\run_airline_failure_steering.py `
  D:\jlens\jlens-causal-steering\outputs\taubench-airline-failure-matrix.json `
  --condition baseline --split train --review

.\.venv\Scripts\python.exe scripts\run_airline_failure_steering.py `
  D:\jlens\jlens-causal-steering\outputs\taubench-airline-failure-matrix.json `
  --condition baseline --split validation --review
```

`--review` invokes the required official command in full mode with details.
It needs a provider key accepted by Tau2:

```text
tau2 review <results.json> --mode full --show-details
```

Normalize the reviewed failures:

```powershell
cd D:\jlens\jlens-causal-steering
.\.venv\Scripts\python.exe -m jlens_causal.failure_cli merge `
  D:\jlens\tau2-bench\data\simulations\failure-steering\train\baseline\results_reviewed.json `
  D:\jlens\tau2-bench\data\simulations\failure-steering\validation\baseline\results_reviewed.json `
  --output outputs\airline-train-validation-reviewed.json

.\.venv\Scripts\python.exe -m jlens_causal.failure_cli audit `
  outputs\airline-train-validation-reviewed.json `
  --output-dir outputs\airline-train-failure-audit
```

Create `repairs.jsonl`. Every record must identify one `event_id`, contain one
replacement assistant action, and pass all four checks:

```json
{
  "event_id": "...",
  "source": "llm_then_replay_and_review",
  "repaired_message": {
    "role": "assistant",
    "content": null,
    "tool_calls": [{"id": "repair", "name": "tool_name", "arguments": {}}]
  },
  "validation": {
    "protocol_valid": true,
    "tool_schema_valid_or_not_applicable": true,
    "environment_replay_valid": true,
    "review_passed": true
  }
}
```

Join only train/validation repairs to their exact pre-failure contexts:

```powershell
.\.venv\Scripts\python.exe -m jlens_causal.failure_cli pairs `
  <results_reviewed.json> `
  outputs\airline-train-failure-audit\failure-events.jsonl `
  repairs.jsonl `
  configs\taubench_airline_failure_modes_qwen35_4b.json `
  --output outputs\airline-failure-repair-pairs.jsonl
```

Build CAST's risk/control contexts from the same reviewed baseline. Positive
and negative examples share the same pre-action boundary, and evaluation tasks
are excluded:

```powershell
.\.venv\Scripts\python.exe -m jlens_causal.failure_cli cast-conditions `
  <results_reviewed.json> `
  outputs\airline-train-failure-audit\failure-events.jsonl `
  configs\taubench_airline_failure_modes_qwen35_4b.json `
  --category retry_without_state_change `
  --output outputs\airline-cast-condition-pairs.jsonl
```

Export the exact 14 airline tool schemas used by Tau2's HF prompt, then copy
the repair pairs, CAST condition pairs, and schema file to the remote machine:

```powershell
cd D:\jlens\tau2-bench
.\.venv\Scripts\python.exe scripts\export_airline_tool_schemas.py `
  --output D:\jlens\jlens-causal-steering\configs\taubench_airline_tools.json
```

Extract CAA on the remote CUDA host:

```bash
cd /workspace/jlens-causal-steering
source .venv/bin/activate
python scripts/extract_airline_failure_artifacts.py caa \
  configs/taubench_airline_failure_modes_qwen35_4b.json \
  outputs/airline-failure-repair-pairs.jsonl \
  --category retry_without_state_change --layers 20 24 \
  --tools-json configs/taubench_airline_tools.json
```

Replace `caa` with `mera`, `sadi`, `iti`, or `austeer` for their artifacts.
CAST additionally takes
`--condition-pairs outputs/airline-cast-condition-pairs.jsonl`; LoReFT accepts
`--ranks 4 --epochs 8`. All seven methods use the exact tool-bearing chat
template and task-disjoint train/validation roles.

Extract one multi-mode J-Servo artifact from every failure category that has
at least two validated train and two validation repair pairs. Layer bands are
selected by failure stage (for example, semantic state at L16--24 and
serialization at L28--30), so `--layers` is only the fallback for an unknown
category:

```bash
python scripts/extract_airline_failure_artifacts.py jservo \
  configs/taubench_airline_failure_modes_qwen35_4b.json \
  outputs/airline-failure-repair-pairs.jsonl \
  --categories retry_without_state_change completion_not_released \
  --observation-layers 16 --layers 20 24 \
  --tools-json configs/taubench_airline_tools.json \
  --output-dir /workspace/jlens-artifacts/taubench-airline
```

The output path is
`/workspace/jlens-artifacts/taubench-airline/jservo.pt`, matching the checked
manifest. Preflight and run all J-Servo treatments with `--method jservo`:

```powershell
cd D:\jlens\tau2-bench
.\.venv\Scripts\python.exe scripts\preflight_failure_steering.py `
  D:\jlens\jlens-causal-steering\outputs\taubench-airline-failure-matrix.json `
  --method jservo

.\.venv\Scripts\python.exe scripts\run_airline_failure_steering.py `
  D:\jlens\jlens-causal-steering\outputs\taubench-airline-failure-matrix.json `
  --method jservo --split evaluation --review
```

Select layer/strength on validation tasks only. Then run the frozen condition
on evaluation tasks. Run the no-steering baseline once, then one complete
method family at a time. `--method caa` selects every CAA target and control
condition but no conditions from the other six methods:

```powershell
cd D:\jlens\tau2-bench
.\.venv\Scripts\python.exe scripts\run_airline_failure_steering.py `
  D:\jlens\jlens-causal-steering\outputs\taubench-airline-failure-matrix.json `
  --condition baseline --split evaluation --review

.\.venv\Scripts\python.exe scripts\run_airline_failure_steering.py `
  D:\jlens\jlens-causal-steering\outputs\taubench-airline-failure-matrix.json `
  --method caa `
  --split evaluation --review

.\.venv\Scripts\python.exe scripts\analyze_airline_failure_steering.py `
  D:\jlens\jlens-causal-steering\outputs\taubench-airline-failure-matrix.json `
  --split evaluation --require-complete
```

The deployable claim is the learned/structural gate. The post-hoc oracle gate
is only an upper bound. A causal success requires a paired improvement over the
same task/trial baseline, nonzero verified dose at the intended boundary, and
no comparable gain for negative-direction, wrong-category, wrong-layer, or
count-matched random controls. SADI and LoReFT's explicit zero-strength rows are
classified as `zero_dose`; the analyzer keeps every layer and strength as a
separate condition, reports agent-review and user-review errors separately,
and gives improved/worsened discordant task counts with an exact paired
McNemar p-value.

The runner refuses to review a condition unless every requested task/trial is
present exactly once. During a sequential sweep, omit `--require-complete` to
inspect partial results; use it for the final paper table so every condition
in the fingerprinted matrix must be present and exactly paired to baseline.

## ToolAlign Core-7 sequence

Run ToolAlign entirely on the remote CUDA host. CAA first:

```bash
cd /workspace/jlens-causal-steering
bash scripts/remote_toolalign_core7.sh caa full both
```

Then run `cast`, `mera`, `sadi`, `iti`, `austeer`, and `loreft` one at a time.
Each analyzer compares every treatment with its exact alpha-zero case and
reports both abliterated-to-aligned restoration and aligned-to-misaligned
erosion, plus parse corruption, safe degradation, tool-signature changes, and
method-specific dose. The alignment flip table also includes an exact paired
McNemar p-value, so a net-looking gain cannot hide equally many reverse flips.

After all seven methods and both model roles finish, require and combine all 14
paired analyses into one JSON/CSV table:

```bash
python scripts/summarize_toolalign_core7.py \
  --config-dir configs \
  --output-dir outputs/toolalign-core7-summary
```

The command fails on a missing method/role by default. `--allow-partial` is
only for inspecting an unfinished sweep, not for a paper result. It also
requires aligned/abliterated results for a method to share one config
fingerprint and to contain all 32 held-out ToolAlign cases per baseline role.

## ToolAlign J-Servo sequence

J-Servo uses eight calibration domains, four disjoint validation domains, and
four held-out evaluation domains. Baselines for both checkpoints must exist
before matched repair pairs can be extracted:

```bash
cd /workspace/jlens-causal-steering
python scripts/run_toolalign_jservo.py validate configs/toolalign_jservo_llama8b.json
python scripts/run_toolalign_jservo.py baseline configs/toolalign_jservo_llama8b.json --role aligned
python scripts/run_toolalign_jservo.py baseline configs/toolalign_jservo_llama8b.json --role abliterated
python scripts/run_toolalign_jservo.py pairs configs/toolalign_jservo_llama8b.json

python scripts/run_toolalign_jservo.py extract configs/toolalign_jservo_llama8b.json --role aligned
python scripts/run_toolalign_jservo.py extract configs/toolalign_jservo_llama8b.json --role abliterated
python scripts/run_toolalign_jservo.py sweep configs/toolalign_jservo_llama8b.json --role aligned
python scripts/run_toolalign_jservo.py sweep configs/toolalign_jservo_llama8b.json --role abliterated
python scripts/run_toolalign_jservo.py analyze configs/toolalign_jservo_llama8b.json --role aligned
python scripts/run_toolalign_jservo.py analyze configs/toolalign_jservo_llama8b.json --role abliterated
```

The targeted condition tests abliterated-to-aligned recovery. The reverse
controller has its own source-margin target, so the aligned checkpoint tests
aligned-to-misaligned induction instead of receiving a zero edit. Fixed
strength, fixed layer, wrong mode, random, validator-only, and no-steering
conditions use the same held-out cases. No evaluation case contributes a
token bundle, threshold, layer, or dose cap.

## Current execution blocker

Run the cross-repository completion audit at any time:

```powershell
cd D:\jlens\jlens-causal-steering
.\.venv\Scripts\python.exe scripts\audit_core7_benchmark_protocol.py `
  --output outputs\core7-protocol-audit.json
```

It separates `implementation_ready` from `empirical_complete`; it exits
nonzero until all 73 reviewed TauBench conditions and all 14 ToolAlign
method/role analyses exist. This prevents passing unit tests or dry runs from
being reported as experimental results.

The code and local validation do not require a base model. Real causal numbers
do require `JLENS_REMOTE_ENDPOINT`, `JLENS_REMOTE_TOKEN`, and an LLM provider
key for full Tau2 review. ToolAlign's gated aligned Llama model also requires a
Hugging Face token. These values are intentionally not stored in the
repository. Until the preflight report says `"ready": true`, generated matrices
and dry runs are protocol validation, not causal benchmark results.
