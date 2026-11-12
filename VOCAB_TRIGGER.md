# Vocabulary-triggered J-lens steering (τ² airline, Qwen3.5-4B)

**Idea.** The agent's J-lens readout at the decision point of a turn is
checked for a risk vocabulary before it acts. When the risk vocabulary
outweighs a safe vocabulary, the residual stream is steered toward the safe
concept for the rest of that turn.

## Data

The no-steering baseline telemetry of Qwen3.5-4B on τ² airline
(`data/jlens-telemetry/failure-steering/{train,validation,evaluation}`) covers
1,428 agent turns. Each turn record holds:

* the exact `input_ids`;
* the emitted tool calls;
* the residuals at the decision point (layers 8 / 16 / 31).

Turns are labelled against the task's gold actions with
`jlens_causal.vocab_trigger.label_calls`:

| Label | Meaning |
|---|---|
| `bad_write` | A state-changing call with wrong arguments, or one that no gold action uses. `transfer_to_human_agents` is judged by name only. |
| `good_write` | A state-changing call that matches a gold action. |
| `read` | A read-only call. |
| `no_call` | No tool call. |

## Detection (`scripts/vocab_trigger_mine.py`)

The readout is `W_U · Norm(J_l h)`, the same readout as the J-lens exports.
The vocabulary is mined on the train split only:

* tokens are ranked by smoothed log-odds of appearing in the top-50 at the
  decision point of `bad_write` turns versus all other turns;
* only tokens with at least two letters are kept, since punctuation tokens
  would be injected literally when steering.

The score is `logsumexp(z[risk]) − logsumexp(z[safe])`, and the threshold
maximises F1 on train.

Selected trigger at layer 16 (`configs/vocab_trigger/airline_qwen35_4b_layer16.json`):

* **Risk tokens:** " Compliance", "道歉", " Ack", " Prior", " Customer", "以下步骤", "明确要求", "严格按照".
  This reads as acting "strictly per policy / following the steps".
* **Safe tokens:** "’re", "根据您的", "看到你", " Ask", "提问", " Asking", "asking", "问一下".
  This reads as asking the user.

| Split | AUC (bad_write vs rest) | Fires on bad_write | Fires on good_write | Fires on read |
|---|---|---|---|---|
| train | 0.90 | 28/51 | 23/61 | 2/476 |
| validation (held out) | 0.945 | 16/22 | 3/7 | 3/119 |
| evaluation (held out) | 0.90 | 5/11 | 7/18 | 2/141 |

Caveats:

* Splits are disjoint by task, but each split is small (11–22 bad writes).
* The threshold trades recall for false alarms on good writes.

## Steering (`src/jlens_causal/vocab_trigger.py`, `scripts/vocab_trigger_replay.py`)

**Direction.** `d = normalize(J_c^T (mean W_U[safe] − mean W_U[risk]))` at
control layer `c = 20`.

**Edit.** `h ← h + α‖h‖d` on every position of the turn once the trigger has
fired. Detection happens on the first forward pass, at the decision position.

**Prefix replay.** Each selected turn's logged `input_ids` are re-fed and only
that turn is regenerated greedily:

* the prompt minus its last token is prefilled once, in chunks;
* each condition then continues from a copy of the cache.

**Conditions.**

| Condition | What it does |
|---|---|
| `off` | Detect only. |
| `trigger@α` | Steer along `d` when the trigger fires. |
| `random@α` | Same trigger timing and dose, but a random direction. |

Greedy regeneration without steering reproduces the logged GPU (bf16)
generation token for token on CPU (fp32).

## Status

**Done.** The detection results above, and a pipeline smoke test on CPU
(2026-11-13).

The smoke test ran two held-out turns, regenerating 40 tokens with α = 0.4 at
control layer 20. That length is too short to reach the final tool call, so
outcome labels are not yet meaningful.

* **validation task 46, turn 3** (logged `bad_write`: an unexpected
  `transfer_to_human_agents`). Trigger score 1.82, so it fired.
  * `off` reproduces the logged text: "I understand your request, but I must
    follow the policy strictly…".
  * `trigger` changes it to "I understand you're requesting an exception to
    the policy…".
  * `random` stays on the baseline wording.
* **evaluation task 22, turn 8** (logged `good_write`, a false alarm). Score
  1.17, so it fired.
  * `off` goes straight to `update_reservation_passengers`.
  * `trigger` defers it: "For the passenger update, I need to provide…".
  * `random` reproduces the baseline exactly.

The edit is direction-specific: the random direction at the same dose leaves
the text unchanged. False alarms can delay correct writes.

**Not done.** The full held-out replay: 31 triggered turns (21 bad / 10 good
writes) × {off, trigger, random}, regenerated to the end of the action. On a
GPU this takes minutes; on this CPU it takes about 5 hours.

## Running

```bash
# mine on train, score held-out splits
python scripts/vocab_trigger_mine.py <telemetry_root> <airline tasks.json> \
  --model-dir <Qwen3.5-4B snapshot> --lens <Qwen3.5-4B_jacobian_lens_n1000.pt> --output-dir outputs/vocab_trigger/airline
# held-out triggered turns
python scripts/vocab_trigger_select.py <telemetry_root> <tasks.json> outputs/vocab_trigger/airline/trigger_layer16.json \
  --model-dir ... --lens ... --output outputs/vocab_trigger/airline/replay_selection.jsonl
# replay (GPU recommended; on CPU use --precision fp32 and expect ~10 min per turn)
python scripts/vocab_trigger_replay.py outputs/vocab_trigger/airline/replay_selection.jsonl \
  outputs/vocab_trigger/airline/trigger_layer16.json <tasks.json> --model-dir ... --lens ... \
  --alphas 0.4 --random-alpha 0.4 --cap-to-logged --max-new-tokens 600 --output outputs/vocab_trigger/airline/replay.jsonl
```

The lens is `neuronpedia/jacobian-lens@a4114d77`, file
`qwen3.5-4b/jlens/Salesforce-wikitext/Qwen3.5-4B_jacobian_lens_n1000.pt`. The
model is `Qwen/Qwen3.5-4B@851bf6e8`.
