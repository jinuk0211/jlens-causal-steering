# τ²-bench steering study: results section draft (h-04, 2026-11-19)

Source of truth for every number: PLAN.md (F-RUN RESULT 23:55, J5 RESULT 04:55, A1 RESULT 05:36), server
reserve/qual/f_analysis.py, probe/j5/*, probe/argrev/*.

## Setup
- Benchmark: τ²-bench airline (50 tasks) and retail (50 tasks); single trial per task.
- Agent: Qwen3.5-4B, greedy, bf16 (transformers).
- User simulator: Claude Haiku, effort low, prompt v4.
  - Replies are cached by (messages, seed), so paired conditions see identical user turns until the agent's trajectories diverge.
- Retail tool arguments use a schema-aware parser.
- Runs: no wall-clock cut-off; per-episode timeout 3600 s. Paired conditions run concurrently, because greedy decoding on
  this stack is not bit-reproducible across separate runs.
- Split:
  - Steering strength is selected on 24 airline TRAIN tasks only.
  - Evaluation: 26 held-out airline tasks + 50 retail tasks = 76.
  - Retail is a cross-domain transfer test, since every method is fitted on airline.
- Reference (f_detect): the unsteered agent. The J-lens readouts are computed and logged, but nothing is edited.
- Retail NL assertions: graded offline with the τ² judge prompt (Claude Haiku). Reported success = stored reward × NL verdict.

## Baselines (faithful protocol)
Six published activation-steering methods, each run from the authors' pinned upstream code with only the adapters
needed for multi-turn tool use: CAA, CAST, MERA, SADI, ITI and AUSteer.
- Each method is always on, with no external gate:
  - CAST keeps its own published condition gate.
  - MERA keeps its own fall-back-to-no-steering rule.
  - SADI uses the upstream full-prompt edit.
- Strength is chosen per method on airline TRAIN by a fixed rule:
  - Walk the doses in ascending order.
  - Stop climbing once ≥ 50 % of episodes degenerate.
  - The highest TRAIN reward wins; ties go to the weaker dose.
- Selected strengths: CAA 0.5, CAST 0.25, SADI 10, ITI 15, AUSteer 10. MERA's best TRAIN configuration fell below the
  reference, so by its own rule it applies no steering.

## Main result (76 evaluation tasks, paired against the unsteered reference)

| Method | Airline (26) | Retail (50) | Total (76) | Fixed | Broken | Net | McNemar p |
|---|---|---|---|---|---|---|---|
| Unsteered reference | 20 | 41 | 61 | – | – | – | – |
| CAA | 20 | 36 | 56 | 7 | 12 | −5 | 0.36 |
| AUSteer | 21 | 34 | 55 | 6 | 12 | −6 | 0.24 |
| SADI | 19 | 37 | 56 | 6 | 11 | −5 | 0.33 |
| ITI | 20 | 38 | 58 | 4 | 7 | −3 | 0.55 |
| CAST | 20 | 34 | 54 | 7 | 14 | −7 | 0.19 |
| MERA | = reference (no steering) | | 61 | 0 | 0 | 0 | 1.0 |
| J5 (5-layer J-lens, ours) | 20 | 41 | 61 | 0 | 0 | 0 | 1.0 |

- Airline held-out: every method is within ±1 task of the reference.
- Retail: every always-on baseline trends negative (−3 to −7). Steering fitted on airline transfers badly across domains.
- On TRAIN, CAA and ITI each gained +3 over the reference (16/24). That gain did not carry over to held-out airline.
- No difference is significant at n = 76. A real effect of ±3 tasks cannot be resolved with one trial per task.

## Why J-lens steering has nothing to act on: detection analyses
J5 design: a refusal-mass gate (L27-31) plus J-Servo minimal-margin control at L20 (m = 7.67), with dose caps and abstention.
In episodes it is behaviourally identical to the reference on all 76 tasks:
- it rarely fires on writes;
- when it fires it mostly abstains;
- its few edits changed no outcome.
The reason is in the offline analyses on airline TRAIN, all with task-grouped CV:
- **Decision point** (the last prompt token of the turn that issues a write):
  - Data: 29 bad vs 37 good writes.
  - Per-layer feature families are at chance:
    - harmful-word salience 0.43-0.55;
    - cross-layer flip 0.48;
    - cross-layer reversal 0.54;
    - refusal mass ≤ 0.70 (best L28).
  - The refusal-mass gate missed the pre-registered usefulness bar: it fires on 32 % of good writes.
- **Argument tokens** (A1, 435 argument leaves, 16 wrong vs 323 correct):
  - J-lens commitment depth: AUC 0.50.
  - Mid-layer competitor strength: AUC 0.36.
  - Output confidence alone: 0.68.
  - At the first wrong token, the gold token is never top-1 at any of L16-28 (0/16). Its median rank is 2 at the output, but
    the wrong token carries ≈ all of the probability mass.
  - Wrong arguments are confident selections of a wrong value from context, not a late-layer reversal of a correct one.
- **Oracle policy violations:**
  - Refusal mass at L25-31 separates the "retry with a different payment after a tool error" violation from ordinary writes
    (live AUC 0.92-0.98).
  - The same signal is high for every write right after a tool error, compliant or not, so it encodes the context ("an error
    just happened") rather than the violation.
  - A deterministic after-error guard cut violations 4 → 1 on TRAIN. On held-out tasks the pre-registered confirmation
    failed: 7 → 5, against a ≤ 50 % bar. Reward went 22 → 21 of 24.

## Failure anatomy (unsteered reference, Haiku user)
- Retail has little agent headroom: 41-42/50. Of the 8 audited failures, 6-7 are caused by the user simulator (over-caution,
  refusing choices). At most 1 is an agent error.
- Airline held the agent errors (12 audited):
  - giving up and transferring to a human: 4;
  - price or arithmetic: 3;
  - cancellation eligibility: 2;
  - wrong payment: 1;
  - loops: 1;
  - wrong total: 1;
  - wrong rebooking: 1.
- No single error class covers more than about 4 of 50 airline tasks, which caps what any targeted intervention can show here.

## Takeaways
1. Under a faithful protocol, six published steering methods do not improve a 4B tool-using agent on τ²-bench. Always-on
   steering tuned on one domain hurts the other.
2. J-lens readouts do not separate wrong from correct actions in this agent, at the decision point or at the argument tokens.
   A lens-gated controller therefore abstains and is equivalent to no steering. That is safe, but it is not an improvement.
3. The agent's errors are confident: the alternative is present but carries negligible mass at every depth. There is no
   internal "knew but did otherwise" state for steering to exploit.

## Limitations
- Single trial per task, n = 76: effects of ±3 tasks cannot be detected.
- One agent size (4B). A larger agent may show the "knows but does" pattern this analysis looks for.
- The Haiku user simulator errs toward over-caution on retail. It is shared across paired conditions, so this is common-mode noise.
- Wrong-argument events are few (16) and concentrated (10 in one task).
