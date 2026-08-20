# Agent steering experiments

This workspace integrates the seven selected baselines in this order:

1. CAA
2. CAST
3. MERA
4. SADI
5. ITI
6. AUSteer
7. ReFT

CAA and CAST are implemented milestones. Results must not be claimed until
the real-model commands below finish and the paired analysis files exist.

## Shared CAA contract

Both benchmarks consume `agent-steering-vector-v1` tensor-only artifacts.
Each artifact records and validates the model ID, model revision, extraction
layer, direction orientation (`positive_minus_negative`), pair IDs, tensor
width, metadata hash, and vector hash. Cross-model and accidental cross-layer
use fail closed. A deliberate wrong-layer control must declare a separate
`artifact_layer` and is recorded as such.

The generation hook changes only:

- the final prompt residual that predicts the first assistant token; and
- each newly decoded assistant-token residual.

It does not alter earlier system, user, tool-schema, or trajectory tokens.
Every run records the observed prefill/decode dose.

## ToolAlign: aligned versus abliterated checkpoints

Config: `configs/toolalign_caa_llama8b.json`

The calibration split contains 48 wrongdoing cases from 12 domains. A pair is
kept only when the aligned checkpoint is non-misaligned and the abliterated
checkpoint is misaligned. Both responses are then teacher-forced through each
target checkpoint separately, producing checkpoint-specific CAA directions.
The held-out evaluation split contains safe and wrongdoing cases from four
unseen domains.

The historical ToolAlign config names
`huihui-ai/Llama-3.1-8B-Instruct-abliterated`, which is no longer publicly
available. The runnable config therefore pins the accessible full-precision
`mlabonne/Meta-Llama-3.1-8B-Instruct-abliterated` checkpoint and records this
deviation. It must not be described as an exact reproduction of the historical
checkpoint.

Run on a GPU machine with enough memory for one 8B checkpoint at a time:

```powershell
cd D:\jlens\jlens-causal-steering
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli validate-toolalign-caa configs\toolalign_caa_llama8b.json
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-baseline configs\toolalign_caa_llama8b.json --role aligned
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-baseline configs\toolalign_caa_llama8b.json --role abliterated
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-pairs configs\toolalign_caa_llama8b.json
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-extract-caa configs\toolalign_caa_llama8b.json --role aligned
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-extract-caa configs\toolalign_caa_llama8b.json --role abliterated
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-sweep-caa configs\toolalign_caa_llama8b.json --role aligned
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-sweep-caa configs\toolalign_caa_llama8b.json --role abliterated
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-analyze-caa configs\toolalign_caa_llama8b.json --role aligned
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-analyze-caa configs\toolalign_caa_llama8b.json --role abliterated
```

Primary tests are positive CAA on the abliterated model (restoration) and
negative CAA on the aligned model (erosion). The full sweep also includes the
opposite sign, first-decision-only dosing, wrong-layer dosing, and three
norm-matched random directions. All evaluation uses ToolAlign's ten-step
prompt-based tool loop, including success results, duplicate suppression, and
loop detection.

## TauBench Airline Task 18

Config: `configs/taubench_task18_caa.json`

This first causal case targets the observed `each -> all` transition. Eight
matched plans contrast correct per-reservation original-payment binding with a
single global payment template. They are appended to the exact rendered
failure context from call 9 and teacher-forced through Qwen3.5-4B at L20/L24.

First extract the vectors on a GPU machine:

```powershell
cd D:\jlens\jlens-causal-steering
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli validate-taubench-caa configs\taubench_task18_caa.json
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli taubench-extract-caa configs\taubench_task18_caa.json
```

Then run the unsteered baseline before any treatment. The config uses the
original recorded agent sampling settings (`temperature=1`, seed `626729`) to
make failure reproduction more likely:

```powershell
cd D:\jlens\tau2-bench
.\.venv\Scripts\python.exe scripts\run_airline_task18_caa.py D:\jlens\jlens-causal-steering\configs\taubench_task18_caa.json --condition baseline
.\.venv\Scripts\python.exe scripts\analyze_airline_task18_caa.py D:\jlens\jlens-causal-steering\configs\taubench_task18_caa.json
```

Do not interpret treatment runs if `baseline_reproduces_failure` is false.
When it is true, list and run conditions individually so one failed job does
not discard the matrix:

```powershell
.\.venv\Scripts\python.exe scripts\run_airline_task18_caa.py D:\jlens\jlens-causal-steering\configs\taubench_task18_caa.json --condition list
.\.venv\Scripts\python.exe scripts\run_airline_task18_caa.py D:\jlens\jlens-causal-steering\configs\taubench_task18_caa.json --condition caa-positive-l20-a1
```

The intervention is eligible only at agent turn 9 and only after a user
message. The analysis verifies the actual nonzero dose from telemetry and
reports:

- correct reservation/payment mappings out of five;
- total reward and DB reward;
- gain over the paired baseline;
- active intervention turns;
- prefill and decode positions actually modified.

The main causal claim requires increased mapping count or reward for positive
CAA, no comparable random/wrong-layer effect, and no intervention dose outside
the preregistered turn. One successful anecdote is only a pilot; confirmatory
runs need multiple seeds and the remaining failure families.

## Shared CAST contract

CAST uses the pinned ICLR 2025 implementation at IBM/activation-steering commit
`52be60235ee309b46c49d6d5877f36e20c52e6ab`. Both benchmarks consume the same
`agent-cast-v1` artifact. It stores two unit PCA-pairwise directions (behavior
and condition), their tensor hashes, exact train/validation IDs, held-out gate
scores, selected layer/threshold/effective comparator, extraction/application
sites, and an overall metadata hash.

The implementation preserves CAST's important site distinction: directions
are learned from block outputs, while the condition is measured and behavior
is added at block inputs. The official dose changes every prompt token on the
first call and every decode token after the gate fires. A `decision_only`
control changes only the final prefill position, making its dose comparable to
CAA. Ungated and complement-gate controls test whether any improvement really
depends on conditional targeting.

### ToolAlign CAST

Config: `configs/toolalign_cast_llama8b.json`

Eight calibration domains train the behavior and wrongdoing-condition
directions, four different domains tune the CAST gate, and four further
domains evaluate full trajectories. The aligned-versus-abliterated behavior
pairs retain the same strict divergent-response rule as CAA.

```powershell
cd D:\jlens\jlens-causal-steering
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli validate-toolalign-cast configs\toolalign_cast_llama8b.json
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-baseline-cast configs\toolalign_cast_llama8b.json --role aligned
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-baseline-cast configs\toolalign_cast_llama8b.json --role abliterated
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-pairs-cast configs\toolalign_cast_llama8b.json
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-extract-cast configs\toolalign_cast_llama8b.json --role aligned
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-extract-cast configs\toolalign_cast_llama8b.json --role abliterated
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-sweep-cast configs\toolalign_cast_llama8b.json --role aligned
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-sweep-cast configs\toolalign_cast_llama8b.json --role abliterated
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-analyze-cast configs\toolalign_cast_llama8b.json --role aligned
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-analyze-cast configs\toolalign_cast_llama8b.json --role abliterated
```

### TauBench Task 18 CAST

Config: `configs/taubench_task18_cast.json`

The behavior vector contrasts the same eight correct per-reservation plans
against global-payment plans, now using CAST's suffix-mean PCA-pairwise rule.
Eight paired final-user paraphrases train the condition direction and four
disjoint pairs tune the gate. The untouched benchmark wording is used only in
the real evaluation trajectory.

```powershell
cd D:\jlens\jlens-causal-steering
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli validate-taubench-cast configs\taubench_task18_cast.json
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli taubench-extract-cast configs\taubench_task18_cast.json

cd D:\jlens\tau2-bench
.\.venv\Scripts\python.exe scripts\run_airline_task18_cast.py D:\jlens\jlens-causal-steering\configs\taubench_task18_cast.json --condition baseline
.\.venv\Scripts\python.exe scripts\run_airline_task18_cast.py D:\jlens\jlens-causal-steering\configs\taubench_task18_cast.json --condition list
.\.venv\Scripts\python.exe scripts\run_airline_task18_cast.py D:\jlens\jlens-causal-steering\configs\taubench_task18_cast.json --condition cast-positive-l20-a1
.\.venv\Scripts\python.exe scripts\analyze_airline_task18_cast.py D:\jlens\jlens-causal-steering\configs\taubench_task18_cast.json
```

The CAST analysis adds the observed condition score, threshold, natural and
effective gate decisions, condition/behavior layers, and exact prefill/decode
dose beside the five reservation/payment bindings and TauBench reward.

## MERA adaptive error reduction

MERA is adapted from the ICML 2025 official implementation at commit
`1a1e6880e885ef9905815baed065e0cbbeed70c7`. It fits the same no-intercept
linear error probe in log-odds space and uses the published closed form at each
eligible token:

```text
score = sigmoid(w^T h)
if score > alpha:
    h <- h + ((logit(alpha) - w^T h) / (||w||^2 + 1e-8)) w
```

Thus intervention strength is not a fixed coefficient: every token is moved
only as far as required to reach the calibrated error boundary. The artifact
stores the probe, train/validation response IDs, all validation scores, alpha
grid, selected alpha, selection metrics, source commit, module site, and
fingerprints. This agent adaptation selects alpha by held-out
failure-detection F1; the upstream code calibrates with task accuracy, so that
difference is explicit rather than presented as an exact reproduction.

ToolAlign uses eight domains for probe fitting, four for alpha selection, and
four for final safe/wrongdoing trajectories:

```powershell
cd D:\jlens\jlens-causal-steering
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli validate-toolalign-mera configs\toolalign_mera_llama8b.json
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-baseline-mera configs\toolalign_mera_llama8b.json --role aligned
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-baseline-mera configs\toolalign_mera_llama8b.json --role abliterated
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-pairs-mera configs\toolalign_mera_llama8b.json
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-extract-mera configs\toolalign_mera_llama8b.json --role aligned
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-extract-mera configs\toolalign_mera_llama8b.json --role abliterated
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-sweep-mera configs\toolalign_mera_llama8b.json --role aligned
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-sweep-mera configs\toolalign_mera_llama8b.json --role abliterated
```

TauBench uses six of the eight matched correct/global plans for probe fitting
and two for alpha selection. The untouched Task-18 trajectory remains the
causal evaluation:

```powershell
cd D:\jlens\jlens-causal-steering
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli validate-taubench-mera configs\taubench_task18_mera.json
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli taubench-extract-mera configs\taubench_task18_mera.json

cd D:\jlens\tau2-bench
.\.venv\Scripts\python.exe scripts\run_airline_task18_mera.py D:\jlens\jlens-causal-steering\configs\taubench_task18_mera.json --condition baseline
.\.venv\Scripts\python.exe scripts\run_airline_task18_mera.py D:\jlens\jlens-causal-steering\configs\taubench_task18_mera.json --condition list
.\.venv\Scripts\python.exe scripts\analyze_airline_task18_mera.py D:\jlens\jlens-causal-steering\configs\taubench_task18_mera.json
```

Controls include decision-only dosing, alpha=1 global abstention, fixed
uncalibrated thresholds, and three norm-matched random probes. Telemetry stores
the estimated error range and the fraction of positions actually changed.

## SADI sparse dynamic-unit scaling

SADI uses the official hidden-output variant from `weixuan-wang123/SADI` at
commit `47b11e4f0818ce4ca625f0c86e59f882ddb0656b`. For every matched response pair,
the adapter records the last assistant-content activation at each selected
MLP output, averages `correct - failure`, flattens layer and coordinate, and
keeps the globally largest signed coordinates. At inference it performs the
reference operation on the final prompt position:

```text
h[layer, selected_dimension] <- strength * h[layer, selected_dimension]
```

This is dynamic multiplicative steering, not a fixed vector addition. The
`agent-sadi-v1` artifact stores the ordered units, train scores, held-out unit
scores, exact pair IDs, hook site, source revision, and tensor/metadata hashes.
The held-out split audits whether selected units keep the same sign; it does
not select strength or Top-K. Those are a preregistered sensitivity grid.

ToolAlign uses eight domains for unit selection, four different domains for
sign validation, and four final domains for safe/wrongdoing trajectories:

```powershell
cd D:\jlens\jlens-causal-steering
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli validate-toolalign-sadi configs\toolalign_sadi_llama8b.json
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-baseline-sadi configs\toolalign_sadi_llama8b.json --role aligned
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-baseline-sadi configs\toolalign_sadi_llama8b.json --role abliterated
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-pairs-sadi configs\toolalign_sadi_llama8b.json
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-extract-sadi configs\toolalign_sadi_llama8b.json --role aligned
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-extract-sadi configs\toolalign_sadi_llama8b.json --role abliterated
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-sweep-sadi configs\toolalign_sadi_llama8b.json --role aligned
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-sweep-sadi configs\toolalign_sadi_llama8b.json --role abliterated
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-analyze-sadi configs\toolalign_sadi_llama8b.json --role aligned
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli toolalign-analyze-sadi configs\toolalign_sadi_llama8b.json --role abliterated
```

The analysis reports aligned/misaligned rates, tool-call loops, verified
scalar dose, and every paired behavior transition from the unsteered baseline.
This directly tests both abliterated-to-aligned restoration and
aligned-to-worse degradation/necessity.

TauBench reuses six correct-vs-global payment plans for selection and two for
held-out sign auditing. The real Task-18 trajectory is untouched until causal
evaluation:

```powershell
cd D:\jlens\jlens-causal-steering
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli validate-taubench-sadi configs\taubench_task18_sadi.json
.\.venv\Scripts\python.exe -m jlens_causal.steering_cli taubench-extract-sadi configs\taubench_task18_sadi.json

cd D:\jlens\tau2-bench
.\.venv\Scripts\python.exe scripts\run_airline_task18_sadi.py D:\jlens\jlens-causal-steering\configs\taubench_task18_sadi.json --condition baseline
.\.venv\Scripts\python.exe scripts\run_airline_task18_sadi.py D:\jlens\jlens-causal-steering\configs\taubench_task18_sadi.json --condition list
.\.venv\Scripts\python.exe scripts\analyze_airline_task18_sadi.py D:\jlens\jlens-causal-steering\configs\taubench_task18_sadi.json
```

Official-fidelity conditions apply only at the last prompt token and do not
reapply during decode. Controls include selected-unit zeroing, three
count-matched random unit sets, and a separately labelled decode-dynamic agent
extension. The primary result is the reservation/payment mapping count out of
five, accompanied by reward gain and verified scalar dose.

## ITI attention-head steering

ITI follows `likenneth/honest_llama` commit
`2c6b2179be7b5aa8f0a171688cf9e01b812ca327`. Held-out logistic probes rank
attention heads; selected heads receive center-of-mass directions scaled by
their projection standard deviation. ToolAlign separates head training,
validation, and evaluation domains. TauBench fits on six Task-18 plan pairs,
validates on two, and changes only causal turn 9. Negative, prefill-only, and
three count-matched random-head controls record their actual dose.

Configs: `configs/toolalign_iti_llama8b.json` and
`configs/taubench_task18_iti.json`. Commands use the `*-iti` suffixes.

## AUSteer scalar attention units

AUSteer follows `zijian678/AUSteer` commit
`d6573876734f662824062a69c5b9dee31ae57f81`. It computes a signed paired
consistency beta per scalar attention-output unit, selects global Top-K by
`abs(beta)`, and applies the official operation:

```text
h_selected <- h_selected * (1 + alpha * beta)
```

Official conditions change every prompt and decode position. Negative-alpha,
decision-only, and three count-matched random-AU controls are separately
labelled. ToolAlign reports behavior transitions and loops; TauBench reports
the five payment bindings, reward gain, active turn, and scalar dose.

Configs: `configs/toolalign_austeer_llama8b.json` and
`configs/taubench_task18_austeer.json`. Commands use the `*-austeer` suffixes.

## Current execution status

Every TauBench Core-6 analyzer also uses the benchmark's explicit
`ToolMessage.error` field and a shared canonical tool-call fingerprint. The
JSON and CSV outputs include tool errors, unresolved calls, identical retries,
short A-B-A-B loops, max-step termination, and positive-is-better reductions
against the baseline condition. Generated call IDs are excluded from the
fingerprint; tool names and sorted arguments are retained.

- Configuration validation: passed.
- Main project tests: 59 passed plus 6 parser subtests.
- TauBench Core-7 backend and Task-18 script tests: 52 passed.
- Cross-repository artifact round trip: passed, including both fingerprints.
- Real 4B/8B model results: not run locally. The installed GTX 1650 has only
  4 GB VRAM, which is insufficient for these full-precision experiments.
  This establishes runnable, tested machinery, not benchmark-effect claims.
