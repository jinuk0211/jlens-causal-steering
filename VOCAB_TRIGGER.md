# Vocabulary-triggered J-lens steering (?짼 airline, Qwen3.5-4B)

**Idea.** The agent's J-lens readout at the decision point of a turn is
checked for a risk vocabulary before it acts. When the risk vocabulary
outweighs a safe vocabulary, the residual stream is steered toward the safe
concept for the rest of that turn.

## Data

The no-steering baseline telemetry of Qwen3.5-4B on ?짼 airline
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

The readout is `W_U 쨌 Norm(J_l h)`, the same readout as the J-lens exports.
The vocabulary is mined on the train split only:

* tokens are ranked by smoothed log-odds of appearing in the top-50 at the
  decision point of `bad_write` turns versus all other turns;
* only tokens with at least two letters are kept, since punctuation tokens
  would be injected literally when steering.

The score is `logsumexp(z[risk]) ??logsumexp(z[safe])`, and the threshold
maximises F1 on train.

Selected trigger at layer 16 (`configs/vocab_trigger/airline_qwen35_4b_layer16.json`):

* **Risk tokens:** " Compliance", "?볠춬", " Ack", " Prior", " Customer", "餓δ툔閭ιい", "?롧‘誤곫콆", "訝ζ졏?됬뀱".
  This reads as acting "strictly per policy / following the steps".
* **Safe tokens:** "?셱e", "?방뜮?①쉪", "?뗥댆鵝?, " Ask", "?먬뿮", " Asking", "asking", "???訝?.
  This reads as asking the user.

| Split | AUC (bad_write vs rest) | Fires on bad_write | Fires on good_write | Fires on read |
|---|---|---|---|---|
| train | 0.90 | 28/51 | 23/61 | 2/476 |
| validation (held out) | 0.945 | 16/22 | 3/7 | 3/119 |
| evaluation (held out) | 0.90 | 5/11 | 7/18 | 2/141 |

Caveats:

* Splits are disjoint by task, but each split is small (11??2 bad writes).
* The threshold trades recall for false alarms on good writes.

## Steering (`src/jlens_causal/vocab_trigger.py`, `scripts/vocab_trigger_replay.py`)

**Direction.** `d = normalize(J_c^T (mean W_U[safe] ??mean W_U[risk]))` at
control layer `c = 20`.

**Edit.** `h ??h + 慣?뻞?뻚` on every position of the turn once the trigger has
fired. Detection happens on the first forward pass, at the decision position.

**Prefix replay.** Each selected turn's logged `input_ids` are re-fed and only
that turn is regenerated greedily:

* the prompt minus its last token is prefilled once, in chunks;
* each condition then continues from a copy of the cache.

**Conditions.**

| Condition | What it does |
|---|---|
| `off` | Detect only. |
| `trigger@慣` | Steer along `d` when the trigger fires. |
| `random@慣` | Same trigger timing and dose, but a random direction. |

Greedy regeneration without steering reproduces the logged GPU (bf16)
generation token for token on CPU (fp32).

## Status

**Done.** The detection results above, and a pipeline smoke test on CPU
(2026-11-13).

The smoke test ran two held-out turns, regenerating 40 tokens with 慣 = 0.4 at
control layer 20. That length is too short to reach the final tool call, so
outcome labels are not yet meaningful.

* **validation task 46, turn 3** (logged `bad_write`: an unexpected
  `transfer_to_human_agents`). Trigger score 1.82, so it fired.
  * `off` reproduces the logged text: "I understand your request, but I must
    follow the policy strictly??.
  * `trigger` changes it to "I understand you're requesting an exception to
    the policy??.
  * `random` stays on the baseline wording.
* **evaluation task 22, turn 8** (logged `good_write`, a false alarm). Score
  1.17, so it fired.
  * `off` goes straight to `update_reservation_passengers`.
  * `trigger` defers it: "For the passenger update, I need to provide??.
  * `random` reproduces the baseline exactly.

The edit is direction-specific: the random direction at the same dose leaves
the text unchanged. False alarms can delay correct writes.

**Done on GPU (2026-11-14).** The full held-out replay (31 triggered turns 횞
{off, 짹0.2, 짹0.4, 짹0.8, random 짹0.4/짹0.8}), the untriggered `always` control,
and the 32-layer pattern scan. See the GPU results below.

**Not done.** Full ?짼 episodes with steering in the loop, which would give
task pass rates rather than turn labels.

## GPU results (2026-11-14)

Run on an RTX 3080 in bf16, with `scripts/vast_vocab_trigger.sh STREAM=1`.
That host's disk could not hold the checkpoint, so the weights were streamed
from the Hub straight into GPU memory (`src/jlens_causal/hf_stream.py`).

As a numerics check, the recomputed layer-16 decision residuals match the
logged ones: cosine ??0.9992, mean 0.9998.

Unsteered greedy regeneration in bf16 reproduces the logged action token for
token on 18 of the 31 triggered turns. Triggered turns sit close to a decision
boundary.

### Where the failure vocabulary lives (`results/vocab_trigger/gpu/patterns/`)

The scan covers every block (0??1), at the decision point, on 500 turns: all
84 bad writes plus a random 416 others. The vocabulary is mined on train
turns; AUC is reported on the held-out splits.

| layers | held-out AUC (mean of val, eval) | bad-write ("risk") tokens | other ("safe") tokens |
|---|---|---|---|
| 0?? | 0.80??.88 (L6 0.64) | function words, places (" The", " Columbia", " Connecticut") | function words |
| 10 | 0.55 | ??| ??|
| 11??3 | 0.84??.87 | Complaint, Thank, Disclaimer, apologies, Ensure | ask, inquire, ???, Asking |
| 14??5 | 0.83??.88 | apologies, Confirm, 若뚧닇雅?(done), successfully, Congratulations | 瑥룬뿮 (may I ask), your, you |
| **16??9** | **0.89??.91** | ?롧‘誤곫콆 (explicitly requested), Compliance, 餓δ툔閭ιい (following steps), ?볠춬 (apology), Ack, Request, acknowledgment, 簾?쐣 (indeed) | 瑥룡궓/瑥룡궓??(please, first), 瑥룬뿮, ?방뜮?①쉪 (per your), Ask |
| 20??4 | 0.80??.87 | acknowledgment, acknowledge, ?욤? (admit), forgive, cannot, Unable | ?묊쐦?겻틙/?얍댆雅??ε댆/?η쐦雅?(I found / looked up) |
| 25??7 | 0.83??.86 | proceed, proceeding, 弱녻퓵烏?(will carry out), 閭됪꼷 (apology) | Let's, 溫⒵닊餓? Checking, 溫⑴뵪??(let the user) |
| 28??1 | 0.81??.86 | apologize, apology, 野밥툖壅? ?녈걮鼇? misunderstand, Proceed, Transfer | let, Hello, Could, Found, Welcome |

* **Layers.** Early layers separate the classes about as well as the middle
  ones, but their vocabulary is task identity (places, function words), not a
  concept. The interpretable signal peaks at L16??9, which is also the best
  held-out band. L30 has the best *train* AUC (0.912) but drops to 0.86 held
  out.
* **Depth progression.** The failure state reads as a sequence:
  1. *concede and comply* (L16??9),
  2. *acknowledge* (L20??4),
  3. *proceed* (L25??7),
  4. *apologise* (L28??1, the surface tokens).

  The success state reads as *ask first* (L11??9), *look it up* (L20??4) and
  *let the user* (L25??1).
* **Similar words.** Each enriched token comes with its family:
  morphological variants plus translations.
  * " apologize" ??apologise / apologized / apologies / apology / ?볠춬, each
    enriched in bad writes (log-odds +1.7 to +2.8).
  * Proceed ??proceeds / proceeding / proceeded.
  * Understanding ??understand / ?녻㎗.
  * On the other side, " lets" ??let / letting / \tlet (log-odds ??.1 to ??.6).

  A family-level trigger (pooling each family) should be more robust than the
  single-token vocabulary.
* **Mid-stack before surface.** Median rank among 248k tokens, bad writes vs
  the rest:
  * " apologies" is 69 vs 326 at L16 and 39 vs 125 at L24, but 480 vs 807 at
    L31.
  * " Understanding" is 33 vs 1609 at L24 and 16 vs 926 at L28.

  The concept is present in the middle of the stack before it reaches the
  output.

### Does the sign of the steering matter? (`results/vocab_trigger/gpu/sign/`)

**Setup.** The direction is `d = J_20巢(mean W_U[safe] ??mean W_U[risk])`.

* **+慣** pushes toward the "ask / please-first" vocabulary.
* **?믊?* pushes toward the "comply / acknowledge" vocabulary.
* **random** is a random direction at the same dose.

All are latched for the whole turn once the layer-16 trigger fires. The
results come from `scripts/vocab_trigger_sign_report.py`.

**The edit moves the J-lens readout exactly as signed.** The probe reads the
risk-minus-safe score at the decision point, after the edit. The table shows
the mean shift versus `off`; the edit moved it on 30/31 turns, the one
exception being a turn whose live score fell below the threshold.

| condition | L20 | L24 | L28 | L30 |
|---|---|---|---|---|
| trigger +0.2 / +0.4 / +0.8 | ??.5 / ??6.7 / ??4.5 | ??.2 / ??0.1 / ??8.6 | ??.6 / ??.8 / ??4.7 | ??.4 / ??.0 / ??.5 |
| trigger ??.2 / ??.4 / ??.8 | +7.6 / +14.5 / +22.0 | +4.8 / +9.1 / +16.1 | +2.2 / +4.4 / +9.2 | +1.2 / +2.5 / +5.2 |
| random +0.8 / ??.8 | +0.8 / +0.3 | ??.5 / ??.2 | ??.2 / ??.2 | ??.0 / ??.6 |

The shift is monotone in dose, has the right sign on every steered turn, and
decays with depth. A random direction at the same norm barely moves it.

**Behaviour follows the sign only at a high dose.** These are the 31 held-out
triggered turns, labelled from the logs as 21 bad and 10 good writes. Each
cell gives the bad / no-call / good counts after regeneration.

| condition | logged-bad turns (21) | logged-good turns (10) | +慣 better / ?믊?better (paired) |
|---|---|---|---|
| off | 18 / 3 / 0 | 0 / 0 / 10 | |
| trigger 짹0.2 | 15 / 6 / 0 쨌 15 / 6 / 0 | 0 / 1 / 9 쨌 0 / 0 / 10 | 2 / 3 |
| trigger 짹0.4 | 15 / 6 / 0 쨌 15 / 6 / 0 | 0 / 3 / 7 쨌 0 / 2 / 8 | 4 / 5 |
| trigger 짹0.8 | **4 / 17 / 0** 쨌 12 / 9 / 0 | 0 / 6 / 4 쨌 **2** / 3 / 5 | **10 / 2** |
| random 짹0.8 | 15 / 5 / 1 쨌 11 / 10 / 0 | 1 / 3 / 6 쨌 0 / 4 / 6 | 4 / 7 |

* **At 慣 ??0.4, + and ??are indistinguishable,** and a random direction
  changes about as many outcomes. These triggered turns sit near a decision
  boundary: unsteered bf16 regeneration already differs from the log on 13/31
  of them, and any perturbation of this size flips some of them.
* **At 慣 = 0.8 the sign separates.**
  * **+0.8** removes 14 of the 18 bad writes and never creates one.
  * **??.8** removes 7, but turns 2 good writes into bad ones.
  * **Random 짹0.8** removes 5 to 8, and creates 1 to 2 bad writes elsewhere.
* **+慣 holds back writes; it does not repair them.** Every change under +0.8
  is a write turned into no call: 14 bad ??no call, and 6 good ??no call. No
  bad write becomes the gold write within the same turn.
* **The text markers move with the sign.** The share of turns whose visible
  text asks the user something rises under + (10/21 at +0.8) and falls under ??  (3/21).

**On stable turns the direction is specific.** These are 15 untriggered
held-out good writes, steered with `always` at 짹0.4.

| condition (15 good writes) | good | no call | bad | changed vs off |
|---|---|---|---|---|
| off | 13 | 2 | 0 | ??|
| always +0.4 | 6 | 9 | 0 | 7 |
| always ??.4 | 10 | 5 | 0 | 3 |
| random ??.4 | 13 | 2 | 0 | 0 |

Here a random direction changes nothing, while the J-lens direction does, and
+ changes much more than ??

**Summary.** The direction is causal for the readout and sign-asymmetric for
behaviour. +慣 (toward asking) defers writes, and at a high dose it removes
most bad writes on triggered turns, at the cost of deferring correct ones.
?믊?does little, except at a high dose, where it can create bad writes.

**Not measured: the ?짼 task score.** Prefix replay labels one turn. Whether a
deferred write becomes the correct write later in the conversation needs full
?짼 episodes with a user simulator.

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
