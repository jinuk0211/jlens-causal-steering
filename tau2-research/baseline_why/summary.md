# Why the F-run steering baselines failed (h-04, 11-24; CPU re-analysis of every F-run episode)

Data: 1,031 F-run episodes. That is every f_* condition at every strength: airline TRAIN 24 + held-out 26 + retail 50.
Also used: artifacts/fit_examples.json, and the unsteered Haiku rerun hdetect.
Scripts: bw_extract.py (server CPU), bw_analyze.py → report.md, bw_extra.py → report_extra.md.

1. **The intended effect never appears.** Eval set, per episode, steered vs reference on the same tasks:
   - Bad-write share of writes: 0.29 for the reference, 0.31-0.35 for all five baselines.
   - Unneeded transfers: 22 for the reference, 20-23 for the baselines.
   - Verify-first replies: unchanged, except CAST at +0.13.
   - Writes per episode: unchanged (±0.1).
2. **Every always-on edit re-rolls the conversation from the first turn.**
   - All 76 eval episodes differ from the reference under every always-on baseline:
     - most from agent turn 0 (CAA 45, AUSteer 58, ITI 57, CAST 66 of 76);
     - SADI later (turn 0 on 19, turn 1 on 27).
   - Edits land on 100 % of turns. CAST's own gate fires on 85 % of turns, so it is effectively always on.
3. **Airline: changes sit inside the rerun noise.**
   - The unsteered rerun hdetect vs f_detect differs on 11/76 tasks overall. On airline: broken 4/20, fixed 0/6, net −4.
   - The baselines on airline held-out: net −1 to +1.
4. **Retail: a shared, systematic harm, beyond the noise.**
   - The unsteered rerun on retail: broken 3/41 (7 %), net +1.
   - The baselines break 15-29 % of passing retail tasks, with nets of −3 to −7.
   - They break the SAME tasks:
     - retail 36 and 5 under 5/5 methods; 100, 38 and 9 under 4/5;
     - tasks broken by ≥ 3 methods: 8 observed vs 0.93 expected if independent (p < 1e-4);
     - pairwise overlap of retail broken sets: methods vs methods 3-7 shared (of 11-16 in the union); methods vs the
       unsteered rerun 0-2.
   - The failures are wrong action choices on multi-item retail tasks (exchange instead of return, cancel instead of
     modify, extra writes, transfers), seen as db_mismatch / missing_write / wrong_args / unexpected_write.
   - No airline vocabulary leaks into retail (0 airline words in every condition).
5. **Why the shared direction is the wrong one: the fit data.** 56 examples in total:
   - 34 positives (61 %) are a single canned sentence ("Before I make any change, let me check this request against the
     policy and confirm the details with you."); 22 are gold arguments.
   - 26 negatives (46 %) are transfers; 18 are update_reservation_flights.
   - 11 of the 56 come from one task (airline 21).
   - Sources: the 4B-user detect runs and the T=0.7 qwen-user fitx runs. Evaluation uses the Haiku user.
   - So every method learns roughly the same contrast: "canned verify sentence vs airline transfer / flight update
     text". That contrast is narrow and lexical, not a general decision signal. Applied to every token of every turn, it
     derails retail procedures in a correlated way and does nothing measurable for the targeted errors.
6. **Selection picked noise.**
   - TRAIN winners: CAA 0.5 at +3 (McNemar p 0.38) and ITI 15 at +3 (p 0.45). That is the best of 18 method × dose
     options on 24 tasks. Both are +0 on held-out airline.
   - Dose curves have no window: higher doses only degenerate.
     - CAA 2: 7/16, 9 degenerate. AUSteer 50: 2/15.
     - CAST 0.5 / 1: 8/15 and 5/13, 13 degenerate each.
   - CAST at 0.25 already adds +562 characters per turn and +0.34 capped turns per episode.
7. **The two non-movers:**
   - MERA: its own rule applies no steering (TRAIN best 15/24 < 16).
   - J5: fires rarely and mostly abstains. Identical to the reference on 70/76 eval episodes; 6 diverge with no outcome
     change.
8. **Context from the earlier analyses** (WRITEUP_draft.md):
   - The agent's errors are confident.
   - They are spread over many classes (none covers more than 4/50 airline tasks).
   - There is no internal "knew but did otherwise" state for a direction to amplify.

Caveat: hdetect ran on an earlier proxy version, so it is an approximate noise floor, not an exact repeat.
