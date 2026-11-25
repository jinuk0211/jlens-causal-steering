# tau2 steering: direction-finding loop (started 2026-11-16 21:10 KST)

User request (11-16 ~21:00): "Do everything with Qwen3.5-9B. Use the results so far to run a loop that finds a
meaningful direction. No need to stick to the existing method. Use only GPUs 2 and 5. Check first whether any
words or layers separate accident writes from normal writes."

## Fixed rules
- GPUs: nvidia-smi 2 (A5000, 4c593ff4) and 5 (A6000, e6c6cfdf) only. CUDA_DEVICE_ORDER=PCI_BUS_ID. All paths under /home/project-b/LJW.
- User simulator: Qwen3.5-9B@c2022362 via the shared server reserve/usersim/server.py on GPU 2 (127.0.0.1:18090);
  tau2 arg `--user-llm localhf/server:http://127.0.0.1:18090/qwen3.5-9b`. Retail NL-assertion judge later: same 9B (offline).
- The agent under study stays Qwen3.5-4B unless a direction below says otherwise (the 9B agent is an option, not the default).
- Never overwrite or delete results; archive with a suffix. 4B-user results are archived as *_user4b.
- Tune only on airline train tasks (24); held-out airline (26) and retail are evaluation only.
- Every action goes into server reserve/changes.md; the decision log below records the reasoning.
- Report to the user in Korean: one status line per tick, more only when a phase ends or a decision is made.

## What we know (evidence so far, all 4B agent + 4B user)
1. Decision-point vocab triggers detect "about to write", not "wrong write". A-plan words are in the top-100 for 71/84 bad
   vs 67/67 good writes. Old L16 trigger within-write AUC is 0.50 (all) and 0.36 (no transfer).
2. Within-write separability at the decision point (fork, probe/within_write): on writes without transfers (36 bad /
   47 good), vocab AUC is 0.33-0.69 at every layer, and a raw-residual logistic upper bound is 0.38-0.66, with CIs that
   include 0.5. Tool identity alone gives 0.58-0.68.
3. The user simulator contaminates labels. Of 21 failed episodes with a non-transfer bad write: user fault 7, mixed 6,
   agent only 7, unclear 1. The 9B user fixed 2 of 4 audited 4B-user failures fully and 1 partly.
4. Agent-only accident types: (a) cancellation eligibility misjudged (3), (b) payment method switched without consent
   right after a tool error (3), (c) order or arithmetic mistakes (3-4). The 9B agent repeats (a) (task 43).
5. Failure-vocab DB: the strongest "pass" signal (total, refund, payment) comes from generated-token positions,
   i.e. conversation content and progress, not the decision point. It is absent from the decision-point top-100 (0/151).
6. 9B DB (9B agent + 9B user, 60 eps, 1 per task): no within-task strata, stopped. Reference pass rates: airline 21/30, retail 7/30.
7. Early 9B-user audit (21:45, first 17 airline detect episodes, script reserve/qual/audit_u9b.py): pass 13/17 vs 12/17 for the same
   tasks under the 4B user (11 and 17 now pass, 14 now fails). The 4 failures are user 2, mixed 1, agent 1:
   - task 7 (user): the user asked to cancel two more reservations that the instructions never mention.
   - task 20 (user): the user made up a DOB, 1990-05-12, and the agent used it instead of the profile value.
   - task 14 (mixed): the user decided $2628 < $2000 and accepted; the agent charged everything to the Mastercard and used a wrong flight.
   - task 10 (agent): the agent quoted $670, and the true cost is over $1000.
   The 9B user still causes most failures, so gold-match labels stay noisy.

## Phases and directions (update status in place)
P0 [running] Infrastructure: 9B user server; archive 4B-user outputs; rerun detect (100) + fitx (48) with 4 agent
   workers on GPU 5; refit the 4 baselines (fit_chain.sh) on the new data; rebuild the 4B failure-vocab DB.
P1 [next] Clean labels: audit about 15 failed episodes again (agent vs user fault). Recompute within-write separability with
   the fork's within_write.py on the new residual caches (train tasks).
   The fork owns the residual and within-write part (since 21:16): probe/run_u9b.sh (log probe/logs/run_u9b.log) waits for the 48
   airline train units, borrows the w3 slot, writes probe/residuals_u9b, restarts w3, then writes
   probe/within_write/report_u9b.json + table_u9b.txt (all / no_transfer + prev_tool_error counts). ETA about 23:07. Do not duplicate it.
   AGENT criterion: after my audit, give the fork (or run it myself) `within_write.py --res probe/residuals_u9b
   --agent-sims <sim-id prefixes> --tag _u9b_agent` (CPU, about 16 min). Decision rule: if a held-out-by-task
   within-write AUC is at least 0.70 with a CI above 0.55 at some layer, go to D1. Otherwise drop decision-point error triggers.
D1 Error-specific vocab trigger (only if P1 passes): words picked within writes; steer on train, evaluate held-out.
D2 Risky-write caution steering. Gate on the write type, not the lens: cancel_reservation, or update_* with payment.
   Steer with a J-lens direction toward "check policy / ask / confirm" words. Metric on train: unwarranted or
   ineligible writes prevented vs correct writes delayed or broken. This targets accident type (a).
D3 Post-error retry guard. Gate on "the previous tool message is an Error and the next action is a write". Steer toward asking
   the user. This targets accident type (b), which is clean and frequent in airline payment flows.
D4 Argument-confidence signal. Read the lens or next-token margin at the tool-argument tokens (flight numbers,
   payment ids, counts) to flag accident type (c). Needs generation-position residuals (GPU recompute, GPU 5).
D5 Reasoning-text window. Score the agent's pre-call text tokens (not only the first decision token) with the
   lens. The DB same-tool contrast (refund/payment vs because/subsequent/Cannot) suggests signal there. Test on clean labels.
D6 [new, 21:45] Policy-oracle labels, independent of the user simulator. Define agent errors with programmatic policy checks on
   the environment state instead of the gold-action match:
   (i) cancel_reservation on an ineligible reservation: not business, not within 24 h of booking, not airline-cancelled, and
       no insurance with a health or weather reason;
   (ii) a write whose payment_id differs from the one the user last confirmed, right after a tool Error, with no user turn
        in between (D3);
   (iii) baggage: nonfree_baggages above what the membership and cabin allow (later).
   These labels are clean targets for D2/D3. Measure lens predictability and steering effects on them, not on reward alone.
   Report reward too.
D7 [most promising, 22:00] "Knows but does": a conflict signal at policy-sensitive writes.
   Evidence (4B user, archived DB; reserve/qual/d7_cancel.py and d7_words.py): 41 cancel_reservation decisions, 7 of them
   oracle-ineligible, from tasks 39, 41 (x4), 43 and 47. "Unfortunately" is in the decision-point J-lens top-100 at some layer in
   L25-31 for 7/7 ineligible vs 7/34 eligible cancels. "Cannot" is 4/7 vs 2/34. Proceed words show up for nearly all, both kinds.
   Reading: the model still weighs a refusal at the moment it calls the tool.
   By write type (22:13, reserve/qual/d7_allwrites.py), "Unfortunately" in L25-31 top-100:
   | write | violation | ok |
   |---|---|---|
   | cancel | 7/7 | 7/34 |
   | update_flights (the retry_switch cases) | 3/3 | 23/38 |
   | book | – | 6/13 |
   | baggages | – | 3/9 |
   | passengers | – | 0/7 |
   | read/none turns | – | 861/1234 |
   | transfer | – | 35/40 |
   So it is sharp for cancel and weak where the base rate is high. Next: use the log-prob values (dec_val_jlens) instead of
   top-100 presence and compute a per-tool AUC.
   Rank-based (22:44, reserve/qual/d7_rank.py). Score = best rank of the refusal set (Unfortunately, Cannot, Unable,
   unfortunately) in the decision top-100 over L25-31; 101 if absent. AUC for oracle violation vs ok write:
   | writes | AUC | violation / ok |
   |---|---|---|
   | all writes | 0.87 (L19-24: 0.77) | 10 / 101 |
   | cancel | 0.90 | 7 / 34 |
   | update_flights | 0.98 | 3 / 38 |
   With gold-match labels the same within-write question gave about 0.5. The clean oracle labels are what make the signal visible.
   Caveats: 10 events from about 6 tasks, and the vocab and band were chosen post hoc.
   Open question: is it just the model's own next-token distribution (L31 ~ output) or does J-lens at mid/deep layers add
   something? Next: a per-layer breakdown (L25..L31 separately, plus L20-24), compared with L31 alone.
   Per layer (23:14, reserve/qual/d7_layers.py), single-layer AUC:
   | writes | L20 | L21 | L26 | L28 | L31 | L12-19 |
   |---|---|---|---|---|---|---|
   | all | 0.78 | 0.78 | 0.87 | 0.77 | 0.86 | ≤0.70 |
   | cancel | 0.71 | 0.80 | 0.81 | – | 0.88 | ~0.5 |
   Read honestly: most of the signal is already in the final layer (L31 ~ the model's own next-token distribution), so
   detection does not need J-lens; mid layers L20-21 carry a weaker form. Frame D7 as "the agent's own refusal mass at a write
   decision" (an output-level conflict signal). J-lens may still matter for the steering direction (refusal-vs-proceed words at L20).
   Confirmation plan:
   (1) Tonight, train tasks, fresh 9B-user episodes. Use the fork's probe/residuals_u9b (decision residuals, all layers) and
       compute refusal-set ranks with the J-lens / unembedding on CPU, with oracle labels from oracle.py.
   (2) After P0, held-out tasks. Rebuild the DB for held-out u9b episodes; this is an independent-task test.
   PRE-REGISTERED (all writes): on fresh 9B-user episodes, refusal-set best rank over L25-31 vs oracle violation.
   Pass = AUC at least 0.75 with at least 5 violations. The cancel-only rule above stays as a second criterion.
   PRE-REGISTERED confirmation, on fresh 9B-user episodes (rebuild the 4B DB for episodes with cancel calls after P0):
   rule = "Unfortunately" in the decision top-100 at any L25-31 at a cancel decision. Pass if ineligible hit rate is at least 70%,
   eligible hit rate is at most 30%, and there are at least 5 ineligible events. Also report the same rule for all writes vs oracle violations.
   If it passes, the steering design on train cancel tasks (7, 39, 41, 42, plus 14 and 23 if they involve cancel) is:
     gate = write decision + "Unfortunately" in L25-31 top-100 (or a rank threshold);
     direction = J-lens vocab direction (refusal words: Unfortunately, Cannot) minus (proceed words: Proceed, confirmed) at L20, alpha 0.8.
   Run several sampled-user trials per task to get enough events. Metrics: ineligible cancels prevented, eligible cancels kept,
   reward. Baselines: no steering, and an always-on gate on cancel intent (D2), which shows whether the conflict gate adds anything.
Order: P0, then P1, then D6 labels on all finished episodes (CPU), then the cheapest offline tests D3, D2 and D5 (CPU, existing data), then small GPU runs on train
tasks for the best one or two. Steered runs for held-out and retail come only after a train-set win.

## D7 confirmation (1) result (23:50, reserve/qual/d7_confirm.py, fresh 9B-user episodes from probe/residuals_u9b)
- Data: 109 write turns, 5 oracle violations: 21 and 15 retry_switch; 38, 43 and 39 cancel_ineligible.
- PRE-REG all writes, best rank L25-31: AUC 0.774, so it PASSES at the 0.75 bar, with exactly the minimum of 5 violations.
- Cancel only: 0.867 (3 / 25). Per layer: L31 0.75, L26 0.73, L20-24 0.66-0.68, so the signal is output-level as before.
- CORRECTION (00:10): the gold-label "0.80" includes transfer turns, which have high refusal mass because they follow a refusal.
  The fork's u9b within-write (gold labels, no_transfer, words and residual) still finds no separability, same as with the 4B user.
  The oracle AUC 0.774 is conservative, because transfers sit in the "ok" group with high scores.
- D3 did not replicate under the 9B user ("write right after a tool error": bad 2/56 vs good 1/46). Dropped as a standalone direction.
- Violation ranks: retry_switch 5 and 3; cancels 35, 91 and 47.

## D7 confirmation (2) result (01:16, held-out tasks only, episodes not used in (1); reserve/qual/d7_confirm2.py ->
## d7_confirm2_heldout.json)
- Data: 34 write turns, 3 oracle violations: 16 and 32 retry_switch (ranks 4 and 5), 47 cancel_ineligible (rank 93).
- All writes, best rank L25-31: AUC 0.806, above 0.75. But 3 < 5 violations, so the criterion is formally UNDERPOWERED
  (direction consistent, not a pass).
- Per layer: L21-22 0.84-0.88, L31 0.83. Gold-label bad vs good: 0.50 (no signal, as expected).
- Pooled with (1): 8 violations, AUC 0.77-0.81 on both splits.
- Across 4B and 9B, train and held-out, the retry_switch violations always rank 3-5 (the model strongly "wanted" to say
  "Unfortunately"). Ineligible cancels rank weaker (35-93).

## D7 steering prototype (spec sent to the fork 23:52; train tasks only)
Two-pass "conflict-gated refusal steering":
1. Generate the turn as usual.
2. If it contains a write call (book/cancel/update/send_certificate), compute the refusal-set best rank over L25-31 at the turn's
   decision point.
3. If rank <= R* (R* picked on 4B-user TRAIN writes by max TPR-FPR, reported before the run), regenerate the turn with the
   J-lens vocab direction (refusal - proceed words) at L20, alpha 0.8.
4. Log both versions.
Conditions:
- d7gate: the gated version above.
- d7always: always regenerate writes with steering. Control: does the gate matter?
- Baseline: existing u9b detect + fitx.
Trials: fitx-style, 2 sampled-user trials (T=0.7, same seeds, so paired with fitx) on all 24 train tasks; about 96 episodes per
condition. Runs on GPU 5 after P0.
PRE-REGISTERED success:
- d7gate cuts oracle violations per episode by at least 50% vs fitx baseline, with reward not lower by more than 5 pp.
- d7gate reward is at least d7always reward.
Report regenerated writes that became non-writes (correct writes delayed).

Implementation status (fork, 00:04): method jlens_rewrite in tmp_d7/ (live tree untouched until install), 18 tests pass.
- Telemetry: intervention.rewrite = {ranks, best_rank, fired, regenerated, first/second tool calls...}.
- Tokens: refusal 7 ids, proceed 8 ids.
- R* = 80 by the pre-registered rule (4B-user TRAIN writes: TPR 8/8, FPR 44/106). The gate is broad: about 45% of normal writes regenerate.
- Pool: probe/pool_d7.py. Smoke test running in the w3 slot.
- Added an EXPLORATORY condition d7gate10 (R*=10; TPR 3/8, FPR 1/106 on 4B-user train) to test gate specificity.
  The primary pre-registered result stays d7gate (R*=80). Units: 24 train tasks × 3 conditions × 2 trials = 144 episodes, after P0.

## D7 dose result (02:13; probe/d7_dose_*.json, 24 train write prompts: 4 violations + 20 normal)
| mode | α | degenerate | violation kept | normal kept |
|---|---|---|---|---|
| A | 0 | 1/24 | 3/4 | 14/20 |
| A | 0.05 | 0/24 | 3/4 | 13/20 |
| A | 0.1 | 0/24 | 3/4 | 13/20 |
| A | 0.2 | 2/24 | 3/4 | 13/20 |
| A | 0.3 | 2/24 | 2/4 | 12/20 |
| A | 0.4 | 10/24 | 1/4 | 11/20 |
| A | 0.8 | 17/24 | 1/4 | 6/20 |
| B | 0.8 (first 16 tokens) | 15/24 | 1/4 | 6/20 |
Verdict: the literal rule picks α=0.1, but its effect on violations equals α=0 (pure regeneration). J-lens refusal-minus-proceed
steering has no non-degenerate effective dose. The d7gate/d7always episode runs are skipped (expected null, about 5 GPU h).
## D7b (pre-registered 02:15): first-token refusal branching, no steering vector
- Mechanism: when the gate fires on a write turn, regenerate with the first generated token forced to the highest-ranked
  refusal token at that decision position; free greedy decoding after that.
- Offline on the same 24 prompts, gates R*=80 (main) and R*=10 (exploratory).
- Criterion: violation kept ≤ 2/4, normal kept ≥ (α0 normal kept − 2), degenerate 0/24.
- The fork's pre-registration file is artifacts/d7b_prereg.json (02:16, approved). Wording:
  - The forced token is the refusal id with the highest logit in the model's OUTPUT distribution.
  - Degenerate counts only the forced completions that are used.
  - Normal kept must be ≥ 12/20 (α0 has 14/20). If both gates pass, R80 is used.
  - Offline run probe/d7_dose_c.py -> probe/d7_dose_C.json (02:17, about 20 min).
- If some gate meets it: episode run d7b (24 train tasks × 2 trials, paired with fitx). If none does: end the D7 intervention line
  (detection result stands as a finding).

## D7b result (02:43, probe/d7_dose_C.json): FAIL both gates
- R80: fired 12/24 (4/4 violations); violation kept 2/4 and normal 14/20 meet the bar, but 1 used forced completion degenerates
  (the task-21 retry prompt, which loops even at α0), so FAIL. Without that α0-degenerate prompt it would pass. Post hoc, so not used.
- R10: fired 2/24; violation kept 3/4, so FAIL.
- Observation: forcing "Unfortunately" does not stop the action. t15 continues "Unfortunately ... let me try" and calls update.
## D7c (pre-registration requested 02:46): gated self-check message
- Mechanism: a gated regeneration with a fixed "Policy check: ..." system note (wording in the fork message / changes.md); no steering.
- Same 24 prompts, gates R80/R10.
- Criterion: violation kept ≤ 2/4, normal ≥ 12/20, degenerate 0 excluding prompts already degenerate at α0 (defined before running).
- Pass: d7c episodes (48). Fail: close the intervention line and write up the detection finding for the user.

## D7c result (03:13, probe/d7_dose_d.py log)
- R80: FAIL (violation kept 2/4, normal 12/20, 1 degenerate on the normal t21 prompt).
- R10 (exploratory): PASS (fired 2/24, both violations; violation kept 2/4; normal 14/20; degenerate 0).
- t15 now explains the payment policy instead of silently retrying.
## Stress-set episode run (exploratory, requested 03:16; R10 is data-chosen)
- Baseline violation rate is low (u9b TRAIN fitx: 2/48 episodes; detect 2/24), so use a stress set: TRAIN tasks with past oracle
  violations {10, 15, 17, 21, 38, 39, 41}, 6 trials each (user T=0.7, seeds 1-6, paired).
- Conditions:
  - d7obs: gate R10 logged only, which also measures live detection;
  - d7c10: gated self-check regeneration.
- Size: 84 episodes on GPU 5.
- Primary metric: oracle violations per episode (paired). Secondary: reward, gate precision/recall (d7obs), writes removed, turns.
- Exploratory success: violations -50% vs d7obs, reward drop ≤ 5 pp.

D7s implementation (fork, 03:2x):
- Code: rewrite_mode "observe" + rewrite_style "note" (the note is added for that turn only); 24 tests pass.
- Pre-registration: artifacts/d7s_prereg.json.
- Conditions d7obs_s1..s6 / d7c10_s1..s6, where tau2 --seed k is the pairing key.
- Process: smoke on task 15; then probe/install_d7s.sh backs up, swaps the backend + pool, appends 84 units and starts w1-w4. ETA 2-2.5 h.
- Caveat (fork): the offline R10 pass rests on one prompt (t15).
- My scorer: reserve/qual/d7s_eval.py. Paired oracle violations, reward, live gate precision/recall in d7obs, regenerations.
  Run it once the episodes finish. It writes reserve/qual/d7s_eval.json.

## D7s FINAL (08:14; reserve/qual/d7s_eval.json; pairs 42/42; invariant PASS 31, TIME_CUTOFF 10, FAIL 0)
- Oracle violations: d7obs 9 (5 episodes) vs d7c10 8 (4 episodes), i.e. -11%. Exploratory criterion (-50%) FAILS.
- Reward 29/42 vs 30/42. 1 pair better (t21), 0 worse. 5 regenerations.
- Live gate R10: tp 1, fp 5, fn 8, tn 70.
- Live detection (84 d7obs writes): retry_switch vs ok AUC 0.917 (n=4); cancel_ineligible vs ok AUC 0.209 (n=5).
- KEY CORRECTION: all 10 writes right after a tool Error have high refusal rank (3-16), violations (3, 13, 14, 14) and ok writes
  (6, 7, 9, 9, 12, 16) alike. Within after-error writes the rank does not separate them. The D7 "knows but does" signal mostly
  reflects the structural "just had an error" context. After-error writes violate 4/10; all writes 9/84.
## errguard (requested 08:16; exploratory, pre-registered in the fork message)
- Gate: a write right after a tool Error (no user turn between) gets the D7c note and is regenerated; no lens.
- Tasks {10, 15, 17, 21} × seeds 1-6, paired with the existing d7obs. 24 episodes.
- Pass: violations -50% (4 -> ≤2), reward drop ≤ 5 pp, pairing invariant.
- Corrected D7s pairing: PASS 32, TIME_CUTOFF 10, FAIL 0. Excluding TIME_CUTOFF: violations 9 vs 8, reward 23/32 vs 23/32.
- errguard pre-registration (fork, 08:28, artifacts/errguard_prereg.json):
  - d7obs baseline on these tasks: 4 violations (all t21), reward 13/24. Pass = violations ≤ 2 AND reward ≥ 12/24.
  - Gate: rewrite_gate=after_error (rank still logged).
  - Pair check: probe/eg_pairs_status.json. Scorer: reserve/qual/eg_eval.py.
  - Caveat: 10/24 of these pairs were TIME_CUTOFF in D7s, so max_time noise will be large here too.
- Installed 09:04 (29 tests pass, backups probe/*.pre_eg); 24 units on w1-w4; pairing loop -> probe/eg_pairs_status.json. ETA about 11:00.
- Smoke t21 s1 (reward 0):
  - turn 14: after an Error, regenerated, but the note still produced the update;
  - turn 15: after an Error, the note made it explain both errors instead of acting;
  - turn 16: a user turn came between, so no gate and the write went through.
  The pairing vs d7obs_s1 passes.
- 10:0x pairing FAIL on t21 s2 turn 14. Same input sha, both end in EOS, same parsed tool call; the text diverges at token 771 on a near-tie.
  Cause: run-to-run numerical nondeterminism (errguard runs about 5 h after d7obs). Decision:
  - PASS1_NONDET (gate fired, pass 1 discarded) counts as a valid pair;
  - NONDET (diverged but not regenerated) counts as valid and is flagged;
  - real mismatches still FAIL.
  The final report has three cuts: all / no TIME_CUTOFF / no NONDET and no TIME_CUTOFF.
  PROTOCOL NOTE: greedy decoding on this stack (transformers + fla + triton, bf16) is not bit-reproducible across runs, so run paired
  conditions concurrently.

## errguard FINAL (10:30; reserve/qual/eg_eval.json): exploratory PASS
- All 24 pairs: violations 4 -> 1, reward 13 -> 15/24. Clean pairs (14): violations 4 -> 0, reward 7 -> 8.
- Paired: 3 better, 1 worse. The worse one is t10 s5, a cancel outside the gate scope that had diverged by max_time at turn 9.
- Pairing: PASS 13, PASS1_NONDET 1, TIME_CUTOFF 10, FAIL 0.
- Caveat: every removed violation is in task 21.
## CONFIRMATORY held-out run (pre-registered 10:35; the fork implements)
- Tasks: airline held-out {8, 16, 32}, the only held-out tasks with a past after-error write. Seeds 1-8.
- Conditions: cf_obs (observe) vs cf_eg (errguard). 48 episodes.
- Protocol fixes: no agent max_time (max_new_tokens only); each pair runs concurrently.
- Pass: cf_eg oracle violations ≤ 50% of cf_obs AND reward ≥ cf_obs − 1. If cf_obs has fewer than 2 violations: inconclusive (underpowered).
- With max_time removed, TIME_CUTOFF must not occur; it counts as FAIL.
- The fork recorded artifacts/cf_errguard_prereg.json (10:33).
  - Conditions: cf_obs = observe + after_error logging; cf_eg = errguard; both without max_time.
  - Pairing barrier: wait_for_partner, so 2 pairs run at a time. Pool dry-run tests 35/35.
  - Checker: --no-cutoff.
  - Smoke on TRAIN t21 s1, so held-out stays unseen; then install_cf.sh.
  - Power caveat: each held-out task had only 1 past after-error write.
- Installed 10:56: 48 units on w1-w4, pairs start together (4 s / 1 s apart), cf_pairs loop --no-cutoff -> probe/cf_pairs_status.json.
  ETA 14:00-15:00. Smoke: pairing PASS; without max_time, a 3036-token turn ended with EOS.
  Scorer: reserve/qual/cf_eval.py -> cf_eval.json.

## Claude Haiku user simulator (11:52; user: "Max subscription only, no API budget")
Path: server tau2 client -> SSH reverse tunnel (127.0.0.1:18091) -> PC proxy -> Claude Code CLI print mode.
- CLI call: model haiku (claude-haiku-5-5), effort low, no tools/skills/MCP, dynamic sections excluded, empty cwd.
  Overhead is about 1k tokens per call; about 3 s per call.
- Files: work\tau2-research\usersim_claude\{proxy.py, tunnel.py, cache\, token.txt, proxy.log, tunnel.log}.
  Server: reserve/usersim/claude_token (600). tau2 local_hf_llm.py sends the token (backup .pre_token).
- Reply cache keyed by (model, effort, seed, temperature, messages), so paired runs stay paired and repeated prefixes are free.
  temperature cannot be set on the CLI; sampling diversity comes from Haiku itself, and determinism from the cache.
- Usage counts against the user's Max limits (shared with this session). Rough estimate: about 12 calls × about 5k tokens per episode.
- Tested end to end from the server (11:51). The PC must stay on, with proxy.py (pid 9344) and tunnel.py (pid 9080) running.
Plan once the cf run (9B user) ends:
- H0: smoke 1 train episode with the Haiku user (check that it follows instructions).
- H1: detect rerun with the Haiku user, airline 50 + retail 50. Stop the 9B server, so GPU 2 can take 2 extra agent workers.
- H2: audit about 15 failures (user vs agent fault).
- H3: errguard on Haiku-user baselines, with concurrent pairs.
- Report before any larger run (Max usage).

## cf_errguard OFFICIAL (12:35; reserve/qual/cf_eval.json): NOT CONFIRMED
- Violations: cf_obs 7 (5 episodes) vs cf_eg 5 (4 episodes) = 71% > 50%. Reward 22 -> 21/24 (meets ≥ obs − 1 at the edge).
  Pairing 24/24 PASS: the concurrent protocol without max_time gives zero nondeterminism.
- Detection replicates on held-out: the after_error gate on writes has tp 7, fp 4, fn 0, tn 34; refusal-rank AUC 0.981.
- The note intervention is weak: 8 of 10 regenerations reproduce the identical tool call.
- All 7 violations sit in reward-1 episodes, so this risk does not change the tau2 reward; it is policy compliance only.
## Haiku phase started 12:40
- The 9B server is stopped. GPU 2 and 5 are free for agent workers. The proxy restarted with USERSIM_CONCURRENCY=6 (pid 25780),
  the tunnel runs as pid 9080, and the loop cron is 6f89ecb7 -> new id (Haiku rules).
- Requested from the fork: condition hdetect (Haiku user, no max_time, airline 50 + retail 50, interleaved), GPU 2 workers w5/w6,
  and a smoke first (h-04 reads the transcript before H1).

## H0 cost finding (13:20)
- The smoke (t21, hdetect, GPU 2) ran 36+ min with 80 user CLI calls. Cache creation was 1.65M tokens, about $0.48
  API-equivalent for one episode, about 50x my estimate. Each call resent the whole transcript.
- Fix in proxy.py: per-episode Claude Code session continuation (--resume <sid> --fork-session) when the request = previous state +
  our reply + one new agent turn; fresh session otherwise. Tested on port 18092 (3 turns: 2 resumed, $0.0021 total, sane behaviour).
- Deploy on 18091 right after the smoke finishes (in-flight requests would break). H1 is ON HOLD until cost per episode is re-measured.
- Smoke 1 result (13:20): max_steps (201 messages). After the agent's transfer, Haiku never sent ###TRANSFER###; it kept talking and
  the 4B agent degenerated into repeats. About 55 of the 80 CLI calls happened after the transfer.
- Proxy v2 (13:35, pid 6548):
  - session resume;
  - FINAL instruction restates tau2's own termination-token rules;
  - cache key includes prompt_version=2.
  Test: transfer -> exactly ###TRANSFER###; 3 turns cost $0.0018. Asked the fork to rerun the t21 smoke.
- H0 smoke 2 (13:34): user_stop, 11 min, 18 agent turns, 5 Haiku calls, $0.0064 per episode (about 1/75 of v1).
  User behaviour checked by reading all 5 turns: faithful and reactive, defers the calculation as instructed. Reward 0 comes from the agent
  (retry_switch after two tool errors, wrong gift card). H0 PASS -> H1 approved 13:40 (install_h.sh: w1-w4 on GPU 5, w5-w6 on GPU 2,
  100 hdetect units). Estimated cost about $1.
- H1 restart with proxy v3 (13:44):
  - Problem: v2 over-triggered ###OUT-OF-SCOPE###. In retail t5 the agent asked for a name; the scenario gives only the user id and
    zip; Haiku ended the episode at 6 messages. Of the other 6 v2 episodes, 6 ended in TRANSFER. In 5 of them the agent made a real
    transfer_to_human_agents call; in airline t0 the user said TRANSFER first (reward 1).
  - v3 FINAL (PROMPT_VERSION=3): never invent missing details; say "don't know" and offer the user id or zip; use OUT-OF-SCOPE only
    when there is truly no way to continue.
  - Test on port 18092: 4/4 retail continue, transfer case still gives ###TRANSFER###. One case inferred "Mei Kovacs" from the
    user id (benign).
  - Killed the H1 workers. Archived 16 hdetect task dirs to tau2-bench/data/{simulations,jlens-telemetry}/pilot_hdetect_v2proxy/
    and the claims to pilot/claims_archive_hdetect_v2proxy/.
  - Proxy v3 runs as PC pid 13236 (concurrency 6); v2 is kept as proxy_v2.py. Workers restarted via
    reserve/usersim/restart_h1_v3.sh. v2 total spend was 72 calls, $0.072.
  - v3 check (13:51), retail t5 hdetect: the user says it doesn't remember its email or name and offers the user id + zip. The agent
    authenticates through get_user_details. The user asks the agent to find the order, as the scenario allows. The episode ends in
    too_many_errors (36 messages): the 4B agent loops on get_product_details errors. That is an agent fault; the user behaves
    correctly. v3 fix confirmed.
  - H1 interim (14:19), 33/100 done, 0 failed:
    - airline: 11/15 reward. User tokens: TRANSFER 10, STOP 5.
    - retail: 3/18 reward. Endings: TRANSFER 9, too_many_errors 5, OUT-OF-SCOPE 2, STOP 2.
    - Haiku spend: $0.31 for 218 calls, about $0.009 per episode, so about $0.95 for the full run.
    - Both v3 OUT-OF-SCOPE endings are legitimate. The user had offered everything it knew, and the 4B agent still could not
      authenticate:
      - t9: the agent did not try get_user_details on the given user id.
      - t26: the name + zip lookup failed on the agent side.
      In both, the agent explicitly refused to continue, so these are agent faults. One mild user embellishment in t26 ("I checked
      my email inbox"), harmless.
  - Disk (14:22): free space fell 35 -> 13.3 GB in 35 min because of another user's job (KJH/MSM/imi_vm20i/dataset*, 1+ GB CSVs,
    about 18 GB/h). LJW wrote <100 MB. reserve/disk_watch.sh creates pilot/STOP below 3000 MB free (pause, nothing deleted).
    Cleanup candidates are reported to the user, not touched: LJW .cache/uv 15G and .cache/triton 8G.
  - 14:25, user request: deleted LJW HF cache models--Qwen--Qwen3-VL-8B-Instruct (17 GB; outputs/qwen3-vl8b kept). Free space went
    12.0 -> 28.8 GB. The other job still writes about 18 GB/h, so this buys about 80 min. H1 needs about 70 more min. The watcher
    stays armed.
  - 14:29 disk audit:
    - J-lens telemetry is about 1 MB per episode (all telemetry 524 MB).
    - The LJW grower is .cache/triton: 12 GB, +0.9 GB/h and about 5k new kernel dirs per hour while the workers run. It is
      regenerable. Prune old entries after H1 if needed.
    - Free space jumped to 56.5 GB at 14:28 (freed outside LJW).

## CRITICAL: retail tool-argument bug (found 14:55 in H2 prep; reserve/qual/h2_audit.py)
- Cause: jlens_backend.py `_parsed_call_from_xml_payload` runs json.loads on every `<parameter>` value. Digit-only strings
  (zip, product_id, item_id; schema type "string") become ints. The DB compares strings, so every lookup fails.
- Evidence:
  - find_user_id_by_name_zip: 0/142 successes across every retail run (hdetect, 9B-user detect, 4B-user detect).
  - H1 retail: 139/219 tool calls are errors (63%).
  - Airline: 1/426 (alphanumeric IDs, unaffected).
- Consequences:
  - Every retail number so far is invalid, in all conditions and baselines and for all three user sims. Retail pass rates were
    agent-crippled, which explains why they were identical across user sims (7/39 for all three).
  - All airline findings stand: D7, errguard, cf, oracle, and the no-separability result.
  - Retail "unneeded transfers" are mostly a downstream effect: auth fails -> the agent gives up -> transfer.
- Fix (fork implements): schema-aware XML param conversion (vLLM qwen3_coder style), unit tests, and a retail name+zip smoke.
  Deploy after H1. Then archive retail hdetect -> pilot_hdetect_zipbug and rerun the 50 retail hdetect units.
- Fork status (15:00):
  - Patch in tmp_zip, diff in probe/logs/zipfix.diff.
  - probe/test_zipfix.py: 38 checks PASS.
  - Replay of every logged agent turn, old vs new parser: airline 4,020/4,020 calls identical; retail 571/939 changed, all int->str
    on string params, 0 unexpected.
  - pytest: 36/36 on both trees.
  - Smoke on TRAIN retail 0 after H1 (probe/smoke_after_h1.sh), then probe/deploy_zip.sh.
- DEPLOYED 15:33-15:36 (probe/logs/deploy_zip.log). Live jlens_backend.py = tmp_zip (md5 3e844076); backup
  probe/jlens_backend.py.pre_zipfix (374abda5).
  - Smoke t0: reward 1; string product_id and item_ids; exchange succeeded.
  - Smoke t52: find_user_id_by_name_zip with zip "78260" returned sofia_li_9219; 0 tool errors; reward 0 (no matching camera,
    a legitimate outcome).
  - Old retail hdetect archived: pilot_hdetect_zipbug/retail/hdetect (50 sims + 50 telemetry).
  - Retail rerun of 50 hdetect units started 15:33 on proxy v4. ETA 16:30-17:00.
  - Early check (15:49, 16/50):
    - Reward 14/16. The bugged run had 9/50.
    - Tool errors 2/99. The bugged run had 139/219.
    - Name + zip auth 10/10 ok.
    - User tokens: STOP 14, TRANSFER 2.
    - 0 meta retries.
    The bug alone caused the retail failures. The 4B agent is near ceiling on retail, so airline (31/50) is now the harder
    domain and the one where interventions can show effects.
  - Push loop: the "retail hdetect 50" key was removed from pushed.json (backup kept) so the rerun replaces the bugged
    15:17 push.
- Go criteria for the deploy, set by h-04:
  - find_user_id_by_name_zip returns an id;
  - no int-on-string tool errors;
  - the episode ends normally.
  The smoke's reward does not gate the deploy.
- Older retail results (detect, baselines, failvocab, user4b) need a decision from the user. The GitHub results branch holds
  them; per the no-errata rule, tell the user in chat only.
- Airline H2 preliminary (38 done): Haiku 25/38 = 9B user 25/38 on the same tasks, with 10 flips (5 each way), so per-task
  single-trial noise is high. Oracle violations: 5 in 4 episodes (retry_switch t21; cancel_ineligible t34, t39 ×2, t43).
  The agent transfers in 22/38 episodes, and gold needs a transfer in 1.

## H1 FINAL + H2 airline (15:35; reserve/qual/h2_audit.py, h2_view.py)
- H1 hdetect 100/100, 0 failed. Proxy v3 throughout.
  - Airline: 31/50. On the same tasks, the 9B user got 34/50 and the 4B user 31/50. 13 flips vs 9B: 8 lost, 5 gained.
    Single-trial per-task noise is large, so comparisons need concurrent pairs.
  - Retail: 9/50, invalid (zip bug); being rerun.
  - The 4096 max_new_tokens cap was hit in 8 episodes, all airline.
- Airline oracle violations: 6 in 5 episodes. retry_switch t21; cancel_ineligible t34, t39 ×2, t43, t44. All are in reward-0
  episodes.
- H2 attribution, 16 of 19 airline failures read by hand:
  - Agent fault: 12/16.
    - Wrong price or arithmetic: t10 quoted $670 and charged $2010; t12 charged $1200 over a $650 limit; t17 nonfree bags 1
      vs 0.
    - Wrong payment: t21 used a credit card instead of the smallest gift card (also retry_switch).
    - Ineligible or misread cancel: t34 read "cancel the request" as cancelling the reservation; t39.
    - Gave up via transfer: t24, t39, t42, t43.
    - Tool loop to max_steps: t2.
    - Wrong total communicated: t7.
    - Wrong rebooking: t14.
  - User fault: 2/16.
    - t25: role break on CLI-injected context. Fixed in proxy v4.
    - t29: invented a "never cancel" constraint, but gold is cancel + rebook.
  - Mixed: 2/16. t23 is a stalemate over a gift-card policy question; in t33 the user never reached the scripted upgrade step.
  - The Haiku user is usable: 2-4 of 16 failures involve the user, vs 13/21 for the 4B user and 3/4 early for the 9B user.
- Proxy v4 (15:22, pid 17972): ignore-context note + meta-refusal retry. The retail rerun runs entirely on v4.

## H3 pre-registration (15:35, before any H3 run; the choice of arm waits for the retail rerun + retail H2)
Common protocol:
- hdetect-v4 as the reference, concurrent pairs, no max_time, Haiku user v4.
- Tuning only on airline TRAIN 24. Evaluation on airline held-out 26 + retail 50 (fixed parser).
- Primary per arm as below. Secondary: oracle violations and the max_new_tokens cap rate.
- H3-A, stronger post-error guard (deterministic, no lens):
  - Rule: after a tool Error, a write whose payment or args differ, with no user turn in between, is blocked. The agent must
    instead state the error and ask the user.
  - Stress set: train 10, 15, 17, 21; held-out 16, 32 × seeds.
  - PASS: retry_switch violations reduced ≥ 50% on held-out, and reward ≥ reference − 1.
- H3-B, unneeded-transfer guard:
  - Rule: when transfer_to_human_agents is emitted without an explicit user request for a human, regenerate once with a note
    ("continue within policy; transfer only if the user asks and the request is out of policy").
  - PASS: held-out net task gain (fixed − broken) ≥ +3, with no rise in oracle violations.
- H3-C, the original comparison:
  - hdetect-v4 vs jlens, caa, sadi, iti, austeer. The fitted artifacts come from airline TRAIN, which the zip bug did not
    affect.
  - Airline 50 + retail 50, about 500 episodes. Estimate: about 8-10 h on GPUs 2+5 and about $5 API-equivalent Haiku.
  - PASS for jlens: net tasks vs the best baseline ≥ +3 on held-out + retail, and its degeneration (cap, repeats) is no
    worse than detect's.
  - Large run: the user decides.
- Selection rule, fixed now: if one agent failure mode covers ≥ 30% of retail failures after the fix, pick the matching guard.
  H3-B is for transfers; H3-A is for error loops. Ask the user about H3-C in parallel.

## H1 COMPLETE + H2 retail (16:25)
- Retail rerun (fixed parser, proxy v4): 42/50.
  - The bugged run had 9/50. The 9B user had 7/50 and the 4B user 9/50, both bugged.
  - Tool errors 7/356; name + zip auth 37/37.
  - The parser fix and the v3 -> v4 proxy change landed together. The tool-error drop is clearly the parser's doing. The reward
    gain is mostly the parser, because v4 only changes the rare role-break case.
- H2 retail attribution, all 8 failures read:
  - User: 6-7 of 8. The pattern is over-caution or refusal.
    - t7, t8: the user won't give the name implied by the user id mei_kovacs_8020. My v3 "never invent" rule caused this.
    - t0: refused the thermostat ("Google Assistant" is not literally "Google Home").
    - t39: never said "the address is in my recent order", as the scenario instructs.
    - t60: refused to pick a refund method. The agent then transferred.
    - t97, t108: kept deferring and never completed the requested actions.
  - Ambiguous: t38. The user gave the cancel reason "ordered by mistake"; gold expects "no longer needed".
  - Agent: at most 1 (the t60 transfer).
- Selection rule: no agent failure mode reaches ≥ 30% of retail failures, because retail agent failures are about 0. No retail
  guard.
- Airline agent faults (12):
  - give-up transfer: 4 (t24, t39, t42, t43)
  - price/arithmetic: 3 (t10, t12, t17)
  - cancel misread/ineligible: 2
  - wrong payment: 1
  - loop: 1
  - wrong total: 1
  - wrong rebooking: 1 (t14)
  Transfers mostly follow a wrong write, so a transfer guard alone would recover at most about 2 tasks. H3-B is weak.
- Reading: retail has no agent headroom (42/50, failures mostly user-side). Airline has the headroom (31/50, failures
  agent-side). For H3-C, airline is the informative domain; retail only checks for harm.
- User-sim caveat: v4 errs toward over-caution. Paired, concurrent runs share user replies up to divergence, so this is
  common-mode noise there. Do NOT tune the user prompt on eval tasks. A v5 only if the user wants retail as a headline domain.

## F-run: faithful steering comparison (pre-registered 19:40, user decision 19:35)
User: "stop the current run; finish the steering methods first on retail + airline; original authors' code; only minimal benchmark
adaptations (reviewer risk)". User choices: all 6 official baselines; strength selected on airline TRAIN 24.
- H3-C stopped (pilot/STOP 19:27). Its gated-baseline outputs are kept as an ablation ("baselines under the J-lens trigger").
  Nothing is deleted.
- Baselines as published: always on, no J-lens trigger gate, generation scope per OFFICIAL_BASELINES.md.
  - CAST keeps its own published condition gate.
  - MERA keeps its own fall-back-to-no-steering rule.
  - SADI uses option F (upstream full-prompt prefill edit, exact).
  - Code: each author's pinned upstream commit plus the documented adapters only.
- J-lens (ours) keeps its own trigger, as that is the method.
- Phase S (selection, airline TRAIN 24 only):
  - f_detect.
  - J-lens α ∈ {0.2, 0.4, 0.8}.
  - Each baseline over its config grid:
    - CAA {0.5, 1, 2}
    - CAST {1, 1.5, 3}
    - MERA {0.001, 0.331, 0.661}
    - SADI {5, 10, 20}
    - ITI {5, 10, 15}
    - AUSteer {10, 20, 50}
  - 24 + 72 + 432 = 528 units.
  - Rule: the highest TRAIN reward wins; ties go to the smaller strength. MERA falls back to no steering if its best is below
    f_detect.
  - The selection is mechanical and runs automatically; no other tuning.
- Phase E (evaluation): f_detect + the chosen J-lens + the 6 chosen baselines on airline held-out 26 + retail 50 = 8 × 76 = 608
  units. f_detect on TRAIN comes from phase S.
- Primary: net tasks vs f_detect (fixed − broken) on held-out + retail.
  - J-lens PASS needs ≥ +3 net over the best baseline, with degeneration (cap, repeat, empty) no worse than f_detect.
  - All per-method nets are reported, TRAIN separately.
- Protocol:
  - Haiku user v4.1 (PROMPT_VERSION 4, cache kept).
  - Fixed parser.
  - No max_time; --timeout 3600 per episode as before.
  - Per-task GPU affinity.
  - At most 1 SADI per GPU; GPU 2 has a single worker.
- Estimate: about 1,060 units, about 16-19 h, Haiku about $6-8 API-equivalent.

## J5: 5-layer J-lens design (user 19:45: "build the 5-layer version from insights; use my earlier results")
Inputs:
- work\drive-prev-analysis\INSIGHTS_20261117.md (user's earlier runs). Main points:
  - Errors look like cross-layer reversals: an early-layer concept at L16-22 loses at L24/L28.
  - Tool commitment happens at L22-23.
  - Suggested steering site per error type:
    - tool choice: L20-22
    - entity binding: L24
    - numbers: L26-28
    - veto: L22, using the refusal concept read at L26-31
  - Suggested dose: J-Servo minimal-margin.
- The 11-16 multilayer harmful-vocabulary draft (probe/multilayer.py, never installed):
  - Layers {13, 20, 21, 29, 30}; commitment words such as "Final", "accepted", "Confirmed".
  - Train OOF: bad-write 38/67, but good-write 35/47 too, so it mostly detects "about to write" (AUC 0.86 vs all turns).
- Today's evidence:
  - The refusal rank at L25-31 separates retry_switch (live AUC 0.92-0.98).
  - No good-vs-bad write separability elsewhere.
  - Fixed α 0.8 degenerates.
- J-Servo (tau2 agent jservo.py, wired into the backend): targeted minimal-margin control with abstain.
Design (all choices on airline TRAIN only):
1. Data: decision points of airline TRAIN episodes under the Haiku user and the fixed parser (H1 hdetect TRAIN + F-run
   f_detect). Replay them once with all-layer J-lens readouts (a GPU pass).
   - Labels: H2-style agent-fault bad writes plus oracle violations, against good writes.
   - The contrast is write vs write, not write vs read.
2. Detection:
   - Per-layer features: harmful-vocabulary salience (multilayer.py method, re-mined on write-vs-write), refusal mass, and a
     reversal score (the rank drop at layers ≥ 24 of the top concept at layers ≤ 22).
   - Pick the 5 layers by task-grouped CV OOF AUC on bad vs good writes; the trigger fires when any chosen layer passes its
     threshold.
   - Pre-registered usefulness bar: OOF good-write firing ≤ 30% with bad-write recall ≥ 40%. If the bar is not met, J5 runs
     anyway, and the write-up states it.
3. Steering:
   - Direction: the J-lens concept vector of the losing early concept (reversal), or the refusal concept (veto).
   - Site chosen from {20, 22, 24, 26, 28} by an offline counterfactual on the logged TRAIN bad-write prompts: the best flip
     rate of bad writes, with good writes kept and 0 degeneration.
   - Dose: J-Servo minimal margin with a cap and abstain, two margins {low, high}.
4. Phase S units: f_j5_m{low, high} on TRAIN 24, selected by the same rule as the baselines. Its phase E units are appended
   after the baselines' phase E, which does not wait for J5 (user priority: finish all baselines first).
GPU: the replay and counterfactuals need about 10 GB. Run them on GPU 2 next to w5, which is about 10 GB; no full-forward slot
unit may run on GPU 2 at the same time. Coordinate with the fork.

## A1: argument-level cross-layer reversal (pre-registered 11-19 05:23, before any run; offline, airline TRAIN only)
Why this, after F-run + J5:
- Every decision-point feature family is null on TRAIN bad vs good writes. J5 step 1: words 0.43-0.55, reversal 0.54, flip
  0.48, refusal mass ≤ 0.70.
- The largest bad-write class is agent:wrong_args (11 of 29), and argument values are decided at the argument tokens, not at
  the decision point.
- The user's 8/13 analysis puts binding/number errors at L24-L28 ("each" → "all" at L24; 708 formed at L28).
  Nobody has looked at the lens at argument tokens.
Data:
- Write calls of airline TRAIN f_detect + hdetect episodes (unsteered, Haiku v4.1, fixed parser).
- Teacher-forced replay on GPU 5 (probe/argrev/argrev_replay.py): J-lens readout at every layer for each argument-value token.
- Leaves = flattened argument values (e.g. flights[1].flight_number, payment_id). Gold = the same-name gold action with the most
  matching leaves.
- correct = leaf equal to gold (any episode). wrong = leaf unequal to gold at the same path, in a reward-0 episode attributed
  to the agent (h2 mode_of; hdetect t23 excluded). Wrong leaves in reward-1 episodes are reported separately. Identical
  (task, prompt, generation) turns are counted once.
Scores per leaf over its value tokens (greedy, so the chosen token is the L31 top-1):
- s_out (no lens, baseline) = −min logp_L31(chosen).
- s_commit (J-lens) = max over tokens of the first layer from which the chosen token stays top-1 through L31.
- s_comp (J-lens) = max over tokens and L16-28 of [logp_l(top-1 at l) − logp_l(chosen)].
PASS (J-lens adds argument-error detection): best of s_commit/s_comp has
- leaf AUC ≥ 0.70 with task-bootstrap CI lower ≥ 0.55;
- ≥ 8 wrong leaves;
- AUC ≥ s_out AUC + 0.05.
Descriptive (no pass/fail): at the divergence token of each wrong leaf, how often the gold token is top-1 / top-10 at some L16-28
("had the right value mid-stack, then lost it"), plus the median gold rank by layer.
Next:
- PASS: design an argument-level gated fix on TRAIN and report to the user before any episode run.
- FAIL: argument-level detection is null too. Recommend the write-up (no further steering runs).
Cost: about 30 min on GPU 5, no Haiku calls.

## A1 RESULT (05:36; probe/argrev/summary.md, summary.json): FAIL
- Data: 48 episodes and 435 leaves. Labels: correct 323; wrong 16 (agent-fault, reward 0); nogold 80 (unwarranted write
  tools); nopath 16.
  - The wrong leaves come from 5 tasks, and 10 of 16 are t21 payment_id. The n is small and clustered.
- Leaf AUC, wrong vs correct:

  | score | AUC | CI |
  |---|---|---|
  | s_out | 0.68 | [0.27, 0.84] |
  | s_commit | 0.50 | [0.04, 0.62] |
  | s_comp | 0.36 | [0.07, 0.58] |

  - The J-lens scores do not beat chance, nor output confidence.
- Divergence tokens (16):
  - The gold token is never top-1 at any L16-28 (0/16). It is top-10 at some mid layer in 9/16.
  - Median gold rank: L20 3504, L24 2588, L28 6, L31 2.
  - The chosen wrong token has logp ≈ 0 at L31 for 14/16.
  - Wrong arguments are confident errors whose runner-up is gold with negligible mass. There is no "had the right value
    mid-stack, then lost it" reversal.
- Exploratory, not pre-registered: per-layer −min logp(chosen) has AUC 0.28-0.37 at L12-28 (inverted). The wrong values are,
  if anything, MORE readable mid-stack than the correct ones. This fits a wrong value copied from context, i.e. a
  selection/state error rather than a late slip.
- Decision per pre-registration: argument-level J-lens detection is null too. Together with J5 step 1 (decision point) and the
  F-run/J5 episodes, no lens-based detector of wrong writes exists for this 4B agent on airline TRAIN.
  - Recommendation: write up. No further steering runs unless the user picks a new direction (e.g. a 9B agent).

## C1: J-lens contrastive decoding at argument tokens (pre-registered 11-19 13:52, before any run; offline, airline TRAIN only)
Why:
- A1 found three things:
  - wrong argument values are MORE readable mid-stack than correct ones (exploratory per-layer AUC 0.28-0.37 at L12-28);
  - the gold token's median rank at L31 is 2;
  - the wrong token carries ≈ all the mass.
- So a DoLa-style contrast "final minus J-lens mid layer" may demote copied-from-context values. It is a discrete decoding
  choice, so it has no activation edit and no degeneration risk.
Data: the A1 leaves (airline TRAIN f_detect + hdetect write calls; correct 323, wrong 16), teacher-forced on the logged path.
Rule per value-token row:
- candidates = {v : p31(v) ≥ β · max p31} (adaptive plausibility, as DoLa);
- pick argmax over candidates of [log p31(v) − λ · log p_l(v)].
- p_l is the J-lens readout at layer l.
- Grid: l ∈ {12, 16, 20, 24, 28}; λ ∈ {0.25, 0.5, 1}; β ∈ {0.1, 0.01, 0.001, 0.0001} (60 configs).
Metrics:
- fix = wrong leaves whose divergence-token pick equals the gold token. This is a necessary condition only, since later
  tokens are not re-decoded.
- break = correct leaves where any value-token pick differs from the logged token.
PASS (TRAIN screen): some config has fix ≥ 4/16 and break ≤ 6/323 (≤ 2 %). The selected config maximises fix − break among
those; ties go to the larger β, then the smaller λ.
Next:
- PASS: freeze the config and run the same offline check on airline held-out write calls, evaluation only. Then report to
  the user before any episode run.
- FAIL: method 1 is dead. Go to method 2 (isolated self-verification), offline.

## FULL τ² BASE RUN (user 14:0x): data to generalise J-lens layer patterns
User requirements (14:0x, standing):
- Any method must find a suspicious layer pattern in J-lens readouts and confirm the anomaly with words at those layers.
- The current patterns are too few, so first collect more data.
User choices:
- unsteered agent only (f_detect: J-lens readouts logged, no edit);
- 1 trial per task;
- skip tasks that have already run.
Scope:
- retail: the 64 of 114 tasks not yet run;
- telecom: 114 base tasks (task set "telecom", split "base");
- airline: all 50 are done.
Telecom needs user tools (dual control):
- Server tau2 local_hf_llm.py: the server route passes the tools and the tool messages, and returns the user's tool calls.
  Backup .pre_usertools. Tool-free requests are unchanged.
- PC proxy v5: TOOL_CALL line protocol, tools in the cache key, session resume across tool results. The tool-free path is
  identical to v4.1 (backup proxy_v41.py).
- Tested on port 18092: text → tool call → tool result → text, with resume and cache hit; 3 calls, $0.002.
- Export: telecom ids contain | : [ ], which are invalid in Windows paths, so reserve/export_results.py safe() maps them
  to _ (backup .pre_telecom).
Plan:
1. Retail runs now (w2-w4 GPU 5, w5-w6 GPU 2).
2. Telecom smoke on 18092, read by h-04.
3. If OK: when retail is done, move the live 18091 proxy to v5 (no requests in flight) and append the 114 telecom
   f_detect units.
4. Retail NL grading after the run.
5. All-layer J-lens top-k (user 14:1x: "모든 레이어에서 top k 다 구하는거 맞지?"): the live run logs only tokens plus the L16
   trigger score.
   - failvocab/build.py replays every unsteered Haiku-user episode: airline 50 + retail 114 + telecom 114.
   - It keeps the top-20 at all 32 layers for every agent position (decision point + generated tokens) and the top-10 for
     context positions.
   - Estimate 1.5-2 h of GPU.
Afterwards: mine layer patterns on the bigger unsteered set (TRAIN splits only), as the user asked.
- 11-20 01:19 tick:
  - Ops OK: GPU 2/5 idle; proxy idle $18.68 / 0 errors; disk 27 GB; push loop alive.
  - Waiting for the user's GO on pattern mining.
- 11-20 00:49 tick:
  - Ops OK: GPU 2/5 idle; proxy idle $18.68 / 0 errors; disk 27 GB; push loop alive.
  - Waiting for the user's GO on pattern mining.
- 11-20 00:19 tick:
  - Ops OK: GPU 2/5 idle; proxy idle $18.68 / 0 errors; disk 27 GB; push loop alive.
  - Waiting for the user's GO on pattern mining.
- 23:49 tick:
  - Ops OK: GPU 2/5 idle; proxy idle $18.68 / 0 errors; disk 27 GB; push loop alive.
  - Waiting for the user's GO on pattern mining.
- 23:19 tick:
  - Ops OK: GPU 2/5 idle; proxy idle $18.68 / 0 errors; disk 27 GB; push loop alive.
  - Waiting for the user's GO on pattern mining.
- 22:49 tick:
  - Ops OK: GPU 2/5 idle; proxy idle $18.68 / 0 errors; disk 27 GB; push loop alive.
  - Waiting for the user's GO on pattern mining.
- 22:19 tick:
  - Ops OK: GPU 2/5 idle; proxy idle $18.68 / 0 errors; disk 27 GB; push loop alive.
  - Waiting for the user's GO on pattern mining.
- 21:49 tick:
  - Ops OK: GPU 2 and GPU 5 both idle (OntoLoop vLLM gone); proxy idle $18.68 / 0 errors; disk 27 GB; push loop alive.
  - Waiting for the user's GO on pattern mining.
- 21:19 tick:
  - Ops OK: GPU 2 idle; GPU 5 used by OntoLoop; proxy idle $18.68 / 0 errors; disk 27 GB; push loop alive.
  - Waiting for the user's GO on pattern mining.
- 20:49 tick:
  - Ops OK: GPU 2 idle; GPU 5 used by OntoLoop; proxy idle $18.68 / 0 errors; disk 27 GB; push loop alive.
  - Waiting for the user's GO on pattern mining.
- 20:19 tick:
  - Ops OK: GPU 2 idle; GPU 5 used by OntoLoop; proxy idle $18.68 / 0 errors; disk 28 GB; push loop alive.
  - Waiting for the user's GO on pattern mining.
- 19:49 tick:
  - Ops OK: GPU 2 idle; GPU 5 used by OntoLoop; proxy idle $18.68 / 0 errors; disk 28 GB; push loop alive.
  - Still waiting for the user's GO on pattern mining.
- 19:19 tick:
  - Ops OK: none of our processes running; GPU 2 idle; GPU 5 used by OntoLoop; proxy idle $18.68 / 0 errors; disk 29 GB;
    push loop alive.
  - Waiting for the user's GO on the pattern-mining design. No code until then (user 13:5x: "코드쓰지말고 잠시만").
- 18:51 Retail NL grading done (grade_new.sh, Haiku; nl_verdicts.json 138 records). f_detect retail 97 → 93/114 (4 flips).
  - Final unsteered: airline 36/50, retail 93/114, telecom 106/114 = 235/278; 43 failed episodes.
  - Pattern-mining design was sent to the user and is waiting for GO.
- 18:50 FULL τ² BASE RUN + ALL-LAYER TOP-K COMPLETE.
  - Unsteered Qwen3.5-4B with the Haiku user, 1 trial, all episodes user_stop. Stored rewards (retail before NL
    grading):

    | Domain | All | Official train split | Official test split |
    |---|---|---|---|
    | airline | 36/50 | 20/30 | 16/20 |
    | retail | 97/114 | 63/74 | 34/40 |
    | telecom | 106/114 | 69/74 | 37/40 |

  - 39 failed episodes in total.
  - Top-k:
    - 278/278 episodes built and moved to the PC: work/tau2-topk-20261119, 3.5 GB.
    - Contents per episode: npz + json; the .ok file holds the original name.
    - The server keeps only the .done markers.
  - Retail NL grading of the new episodes runs on the PC (nl_judge/grade_new.sh, Haiku).
  - GPU 5 is now used by the OntoLoop session (LJW/ontoloop vLLM Qwen3.5-9B, 42.7 GB, from 18:42). It is legitimate and
    left alone; GPU 2 is free.
  - Next: pattern mining on the PC (CPU), per the user's requirement. The design goes to the user before it starts.
- 18:19 tick:
  - Top-k: 248/278 built and all 248 on the PC (3.3 GB). No puller errors since the 17:19 fix.
  - The 30 left are in GPU-5 shards b0-b2; telecom episodes take about 3 min each. ETA about 18:50.
  - GPU 2's shard b3 is done; left idle (tail only, a third split would save about 10 min).
  - Disk 31 GB; proxy idle.
- 17:50 tick:
  - Top-k is at 204/278 on the PC (2.8 GB).
  - GPU 2's shard 3/4 finished and GPU 2 sat idle, so the remainder was rebalanced: --shard i/n:salt, 4 salted shards (b),
    GPU 5 ×3 and GPU 2 ×1.
  - ETA about 18:20.
  - Proxy idle ($18.68, 0 errors); disk 33 GB.
- 17:25 tick: Windows MAX_PATH problems with long telecom names.
  - PC top-k puller: it was stuck on one long name from 17:14; since then local names over 100 chars are shortened (.ok
    keeps the original) and one failure no longer blocks the pass. Restarted (pid 30732) and moving again.
  - Push loop: another session fixed results_loop.py at 17:20 (short_part + LONG_NAMES.json) and pushed telecom f_detect
    114 (044c657). I reverted my duplicate server-side shortening in export_results.py to avoid renames.
  - Top-k: 133/278 built, 4 shards healthy.
  - FYI: the results worktree has about 145 uncommitted deletions under results/tau2-pilot-20261116/ (the old 4B-user
    snapshot). The loop never stages that path. Not mine, left untouched; told the user.
- 17:10 TELECOM DONE; top-k sharded.
  - Telecom f_detect is complete at 114/114; 0 failed; workers exited about 17:05.
  - Top-k (user: "GPU 5 VRAM is free"):
    - The two unsharded builders were stopped at 105 done.
    - build_topk.py got --shard i/n (md5 of the name mod n; backup .pre_shard).
    - 4 shard builders cover airline + retail + telecom: GPU 5 runs shards 0-2 (33.5 GB), GPU 2 runs shard 3 (11.5 GB).
    - Throughput is about 2.2 episodes/min. At 17:13, 115/278 were done; ETA about 18:30.
  - Local size is about 17 MB/episode, so about 4.7 GB in total (PC free space 69 GB).
- 16:49 tick:
  - Telecom 106/114 done (100 with reward 1, all user_stop), 0 failed. The last 8 finish about 17:05.
  - Proxy v5: 2,327 calls, $18.59, 0 errors.
  - Top-k: 77/278 on the PC.
  - Armed probe/topk/after_telecom.sh: when the pool workers exit, it builds telecom top-k on GPU 2 (run_topk_gpu2.sh)
    while GPU 5 finishes airline/retail.
  - Re-run run_topk.sh airline retail afterwards to pick up retail episodes finished after its glob; markers skip done
    episodes.
  - Top-k ETA about 19:30.
- 16:19 tick:
  - Telecom 74/114 done (69 with reward 1, all user_stop), 0 failed. ETA about 16:50.
  - Proxy v5: 1,735 calls, $13.48 (about $0.18/episode, lower than projected), 0 errors.
  - Top-k: 56 episodes on the PC.
  - Disk: 34 GB.
- 15:49 tick:
  - Telecom 29/114 done (25 with reward 1, all user_stop; mean 37 user turns), 0 failed; 5 workers up. ETA about 18:15.
  - Proxy v5: 1,058 calls, $9.64 (about $0.33/episode, so about $38 projected for telecom), cli_errors 0, tool parse
    errors 0.
  - Top-k: 40 episodes moved to the PC; 0 pull errors.
  - Disk: 39 GB.
- 15:19 tick:
  - Restart happened 15:11 (2 telecom .failed markers archived for retry); w2-w6 are on telecom.
  - Telecom: 4 finished (3 with reward 1, all user_stop), 0 failed.
  - Top-k: 26 episodes built and moved to the PC.
  - Push loop pushed retail f_detect 114 at 15:01.
  - Cost flag:
    - Telecom episodes have 31-53 user turns each (14-23 of them user tool calls), against about 10 on airline.
    - Proxy v5 is at 301 calls and $2.88, about $0.01/call (longer user context).
    - Projection: about $0.4-0.5 per telecom episode, about $35-50 for 114 (API-equivalent on the Max plan). The user has
      been told; continuing by default.
  - Telecom ETA about 18:30 (8-10 min/episode, 5 workers).
- 15:1x Telecom long-name bug.
  - Problem: 2 telecom units FAILED with "[Errno 36] File name too long". Three base ids are 213-215 chars, plus the sim id,
    which is over the 255-byte limit.
  - Action: pilot/STOP set 15:06, so running units finish and no new ones are claimed.
  - Fix in tau2/agent/jlens_agent.py _path_for_run (backup .pre_longname): a sanitized task segment over 160 chars becomes
    the first 140 + "~" + sha1[:12].
    - 18 telecom ids are affected; all names stay unique; airline/retail are unchanged.
  - build_topk.py finds telemetry through the same function, falling back to the plain name.
  - probe/telecom/restart_after_stop.sh waits for the workers to exit, then:
    - archives the telecom .failed markers (*.longname_1119, one retry);
    - removes STOP;
    - restarts w2-w6.
- 15:00 Retail done; telecom started.
  - Retail f_detect is complete at 114/114 (64 new, 0 failed). Stored reward 1 in 97/114 before NL grading (88/104 at 14:49
    plus the rest).
  - Proxy 18091 switched v4.1 → v5 with no requests in flight. v4.1 final: 5,309 CLI calls, $17.47, 0 errors. The test
    18092 proxy and tunnel are stopped.
  - 114 telecom base units appended (backup queue.pre_telecom_1119.txt); w2-w6 restarted 15:00.
- 14:25 tick:
  - Retail f_detect is at 72/114 (+22 new); 59 have reward 1 (stored, NL deferred). 0 failed; 5 workers up. ETA about 15:05.
  - Then: proxy v5 on 18091, then the telecom units.
  - Top-k: 2 episodes built (68-115 s each, while sharing GPU 5); 1 moved to the PC.
  - Disk: 59 → 39 GB free since 13:49. LJW .cache/triton is 27 GB (regenerable); the rest is outside LJW. Free space was
    stable over 1 min.
  - disk_watch.sh had been dead since 11-17 22:17; restarted.
  - Proxy 18091: $16.99, cli_errors 0. Test proxy 18092: about $0.04.
- 14:2x All-layer top-k STARTED (user 14:1x: "top-100/30/30, results on the PC, not the server disk").
  - Builder: probe/topk/build_topk.py, a copy of failvocab/build.py (the original is untouched).
    - K: agent 30, context 30, decision 100.
    - Lenses: J-lens + J++.
    - It leaves a .done marker per episode.
    - It runs on GPU 5 next to w2-w4 (run_topk.sh airline retail; a re-run later picks up new retail + telecom).
  - Puller: work/tau2-research/topk_pull/pull.py (PC pid 19120).
    - It moves each episode to work/tau2-topk-20261119, checking size + md5, then deletes the server copy.
    - Local names have Windows-invalid characters replaced; the .ok file keeps the original name.
  - First episode: airline t0, 68 s, 7.1 MB. 278 episodes ≈ 2 GB locally; about 1-2 min/episode while sharing GPU 5.
- 14:13 telecom smoke PASS. Reward 1.0; 6 faithful user-tool calls, read by h-04; $0.038.

## J-Cascade STAGE 2: offline steering regeneration (pre-registered 11-23 12:5x, before any stage-2 run)
- User (11-23): "승인 안받아도돼", so stage 2 starts automatically after stage 1. GPU 0 only.
- Code: jcascade/stage2_regen.py; server probe/jcascade/run_stage2.sh (3 shards on GPU 0).
- Rows: logged transfer turns. bad = unneeded transfer in a failed episode (19); good = transfer in a passed episode (56).
- Method:
  - Each turn is regenerated greedily (bf16) from its logged prompt.
  - Interventions apply at the decision point plus the first 48 generated tokens; max 768 new tokens.
  - Neuron sets (k = 16) are chosen on one task-half and applied to the other (2-fold cross-fitting by task).
  - Selection uses the stage-1 firing stats (beyond the p97 / p3 of all decision points) plus label-free J-lens readout
    families of each pole's W_down direction.
- Configs:
  - C0: none.
  - S1: writers (L20-26, give-up families: inability / understanding / acknowledgement, ranked by fold Fisher p) set to
    their mean.
  - S2: the same writers with the gate closed (-4).
  - S4: readers (L27-31, positive direct effect on the transfer-name token, ranked at the tool-name point) with the gate
    closed.
  - S5: bipolar poles (give-up pole vs retry/proceed opposite pole) flipped.
  - S6: writers set to their mean on passed-episode "continue" writes.
  - S7: retry-family poles (L16-28, most active on continue writes) raised to p99 / p1.
  - S47: S4 + S7.
  - R1: random L20-26 neurons set to mean (control for S1).
  - R47: random L27-31 gate closed + random L16-28 raised to p99 (control for S47).
- Outcome per turn: transfer / other_tool / text / verbal_transfer / degenerate (cap or an 8-gram repeated ≥ 3).
- PASS per config:
  - bad turns converted (no transfer, not verbal, not degenerate) ≥ 40 %;
  - good turns keep the transfer ≥ 80 %;
  - degenerate ≤ 5 %;
  - conversion higher than its random control and than C0.
  - C0 must reproduce the logged outcome on most turns (determinism check).
- Not run: the residual J-Servo control (machinery lives in the tau2 backend). Dropped for time; noted.
- Disk (user 11-23): if the server disk runs short, the LJW VLM HF caches may be deleted, or results moved to the PC.
- Stage-1 npz stays on the server until stage 2 finishes, then goes to the PC; the server copy is deleted after.

## J-Cascade STAGE 2 RESULT (11-23 15:22; jcascade/out/stage2/summary.md, summary.json): FAIL, every config
- Bad turns converted: 0/19 in every config, C0, S1-S7, S47, R1 and R47 alike. Every domain shows 0: airline 0/10,
  retail 0/4, telecom 0/5.
- Good turns kept: 77-88 % (C0 82 %). Degenerate: 0-5 % (C0 4 %).
- S7 also misses the keep gate (77 %).
- C0 calls the transfer tool again on 64/75 turns. The rest are mostly verbal transfers, so the regeneration is
  faithful enough.
- The interventions do act. Share of rows whose first 600 characters equal C0 (fewer means more change):
  - S47 23/75, S7 27/75, S1 36/75, S6 39/75, S2 40/75, S5 48/75 and S4 63/75;
  - random controls R1 56/75 and R47 26/49 (partial count).
- Changed text never changes the decision. The steered turns rephrase the same preamble ("I do not have access to ...")
  and still call transfer_to_human_agents.
- Reading:
  - At k = 16 with these values (mean, gate closed, flip, p99), the transfer decision does not move at all, while the
    wording does. The decision is either already fixed before this turn (in the prompt state) or spread over far more
    than 16 neurons.
  - This matches stage 1b: the neurons that separate bad from good do not write give-up words.
- Stage 3 (Haiku episodes) is NOT started: its gate was a stage-2 pass.
- Not run: the residual J-Servo control (dropped before the run, see above).
- Open choice for the user:
  - (a) Stop the J-Cascade steering here. Keep stage-0 detection (AUC 0.763 vs 0.655) plus this null as the result.
  - (b) An exploratory dose check (k = 64 / 256, stronger values) to tell "too weak" from "wrong place". It would need a
    new pre-registration.
  - (c) Intervene one turn earlier, on the turn before the transfer.

## J-Cascade STAGE 2b: causal neuron selection + paired-prompt DoM (pre-registered 11-23 16:1x, before any 2b run)
- User 11-23 15:5x: "다른방식 고안해서 시도되냐" + three reference docs (Goodfire neuron communities 2611.23112;
  mechanistic shaping 2611.07071; neurons as an interpretable basis).
- What the docs say about the stage-2 null:
  - Stage 2 picked neurons by firing rate (activation only). The communities paper finds that activation-only selection
    is at chance (2.5-2.7 % coverage vs 9.9 % for activation x gradient, shuffled 2.9 %).
  - Communities span many layers and vote redundantly, so removing a few neurons does little.
  - The shaping paper uses a probe (filter) to detect and a DoM (pattern) to steer. It builds the DoM from matched pairs
    (the same bird on two backgrounds) without class labels.
- The detection stays as in stage 0 (the user's hard requirement): the J-lens layer-word pattern at the decision point
  (stage-0 J_pairs; L20 inability, L24 understanding, L26 acknowledgement). Only the intervention changes.
- Same 75 rows, same 2-fold task cross-fitting (md5(task) % 2). Everything is selected on fold f and applied to fold 1-f.
  GPU 0 only, bf16, greedy, max 768 new tokens, interventions over the whole turn.
- Code: jcascade/stage2b_regen.py. JC_PHASE=prep runs once; JC_PHASE=gen runs as 3 shards.
- Prep, label-free (no bad/good labels are used to select neurons or directions):
  - Teacher-force each logged transfer turn.
  - L = sum of log p of the transfer tokens: the first token of transfer_to_human_agents after "<function=", plus
    preamble tokens whose text starts with "transfer".
  - Gradients come from one backward over the turn (decision point + generated tokens).
  - score[l, n] = sum over positions of (a - mu) * dL/da, at layers L12-31. This is the first-order effect of
    mean-ablating the neuron over the whole turn.
    - mu = the token mean over all teacher-forced turn positions.
    - The score is averaged over the rows of the selection fold.
  - Paired-prompt DoM:
    - The same prompt is run with and without a policy reminder.
    - The reminder is a system message inserted before the final assistant header. It quotes the policy text that all
      three domains share: "You should deny user requests that are against this policy. You should transfer the user to
      a human agent if and only if the request cannot be handled within the scope of your actions."
    - v_l = mean over fold rows of (h_rem - h_plain) at the last prompt position, at the J-lens layers L20, L24 and L26.
  - Necessity check (teacher-forced, no generation): change in L under each ablation set, on the other fold.
- Configs (gen):
  - C0: none, rerun for pairing.
  - P0: the reminder prompt itself. This is an upper bound on flippability, not a method.
  - A5 / A20: top-5 / top-20 positive-score neurons per layer, L12-31 (100 / 400 neurons), mean-ablated.
  - AG20: up to 20 per layer at L20-26, keeping only neurons whose J-lens readout of W_down (either pole) is in a give-up
    family (inability / understanding / acknowledgement), ranked by score. This joins the J-lens words with causal
    attribution.
  - RA20: 20 random neurons per layer, L12-31, mean-ablated. This is the control for A*.
  - B1 / B3 / B8: add alpha * v_l at L20, L24 and L26 (alpha = 1, 3, 8 times the raw paired DoM).
  - RB8: a random direction per layer with the norm of 8 * v_l. This is the control for B*.
- Gate (offline): the stage-0 out-of-fold J_pairs score.
  - For rows in fold f, threshold = the 80th percentile of the out-of-fold scores of the good rows in fold 1-f.
  - Flagged rows take the config's outcome. Unflagged rows take C0's outcome.
- PASS for a method config needs all of the following:
  - Ungated bad converted >= 40 %.
  - Ungated bad converted >= its control + 4/19, with a one-sided paired sign test p < 0.05 against the control.
  - Gated bad converted >= 40 %, gated good kept >= 80 % and degenerate <= 5 %.
  - There are 6 method configs. Picking among them is a multiple comparison. Stage 3/4 is the confirmation.
- Reading P0: if the faithful reminder itself converts < 40 % of bad turns, the decision is not flippable from this
  turn's prompt, and option (c) (one turn earlier) becomes the next step.
- Not run: training-time shaping (reliance / expression shaping needs fine-tuning). Out of scope here.
- AMENDMENT 11-23 16:2x, after the smoke test (4 rows: 1 bad, 3 good) and before the full run.
  - The smoke was a code test. Its rows are part of the eval set, so this changes the dose grid only, never the
    pass criteria.
  - What the smoke showed:
    - B3 degenerates on 4/4 rows ("user's user's ..."). The paired DoM is about 17-19 % of the residual norm.
    - So RB8 does not match the low doses: a random push that size degenerates, and conversion above it would be
      trivial.
    - A20 lowers the summed transfer log p by 5.6 (A5 by 2.6; RA20 +0.01, AG20 +0.02), but the tool-name token stays
      top-1 on 4/4, and 4/4 regenerated turns still transfer.
  - Added configs:
    - B05: alpha 0.5.
    - RB1: a random direction with the norm of 1 * v_l.
    - A100: 100 per layer over L12-31, so 2,000 neurons.
    - RA100: 100 random per layer.
  - Controls:
    - A5, A20 and AG20 against RA20;
    - A100 against RA100;
    - B05 and B1 against RB1;
    - B3 and B8 against RB8.
  - Methods are now A5, A20, A100, AG20, B05, B1, B3 and B8. The multiple-comparison caveat grows with them.
  - Scheduling, so GPU 0 does not sit idle:
    - C0 and P0 do not need prep, so they start together with prep.
    - The other 12 configs then run in 3 lanes.

## J-Cascade STAGE 2b RESULT (11-23 20:45; jcascade/out/stage2b/summary.md): FAIL, every run method config
- Configs run: C0, P0, A20, A100, RA20, RA100, B05, B1 and RB1. A5, AG20, B3, B8 and RB8 were dropped (see the deviation
  note under EXPLORATION X).
- Bad converted, with good kept in brackets (C0: 0 %, 86 %):
  - A20 0 % (50 %); A100 5 % (27 %);
  - B05 0 % (84 %); B1 0 % (88 %);
  - P0 5 % (80 %);
  - controls: RA20 0 % (88 %), RA100 5 % (80 %), RB1 0 % (75 %).
- No config beats its control. The gated results are no better.
- Necessity, teacher-forced: A100 lowers the transfer log p by 13.7, yet the tool-name token stays top-1 on 75/75.
- Paired-DoM fold cosine 0.87-0.89 (a stable direction), norm 2-4 against a residual norm of 18-33.
- Reading:
  - The attribution neurons are causal for the act of calling the tool, but they do not carry the decision. Ablating
    them hits legitimate transfers (they turn into verbal transfers) more than unneeded ones.
  - The paired policy-reminder direction is stable but inert at doses that keep the text intact.
- Stage 3 is not started.

## J-Cascade EXPLORATION X (user 11-23 16:5x: "이거 다 참고해서 explore 좀 많이해줘 ... 12시까지 돌아갈수있을정도")
- This is EXPLORATORY work, not confirmatory. Findings here only choose the next pre-registered test. GPU 0 only, through
  the queue jobs/jc_queue.sh (at most 3 jobs, and only with > 15 GB free). All runs are offline on the 75 logged
  transfer turns unless noted. No Haiku.
- Deviation in stage 2b, logged honestly:
  - Not run: A5 and AG20 (necessity AG20 -0.06, A5 weaker than A20) and B3 / B8 / RB8 (smoke: B3 degenerate on 4/4).
    Their GPU time goes to the exploration below.
  - Still run: C0, P0, A20, A100, RA20, RA100, B05, B1, RB1.
- Questions, from the docs and our nulls:
  - X1 WHEN (CPU, PC): at how many turns before the transfer do transfer words ("transfer", "human", "agent",
    "specialist") first enter the J-lens top-k at the decision point, by layer, bad vs good? Source: tau2-topk-20261119.
  - X5 WHERE (GPU, teacher-forced; communities paper, step 4):
    - layer-range MLP ablation (L12-19 / L20-26 / L27-31, mean ablation);
    - attention-output ablation at the 8 full-attention layers;
    - a cross-row attribution community (top-5 per layer, kept when it recurs in >= 30 % of rows) with
      necessity / in-layer sufficiency;
    - all measured as the change in transfer log p and whether the tool-name token stays top-1.
  - X2 WHAT IN CONTEXT (GPU): teacher-forced occlusion of context segments, then regeneration for the segments that
    matter most. Segments:
    - the last user message;
    - the last tool output;
    - the transfer tool's "Only transfer if" description;
    - the policy's transfer sentence;
    - earlier assistant turns.
  - X3 CONTROLLABILITY (GPU): force the turn's first words (4 openings: policy-check / apology-refusal / continue-helping /
    neutral) and regenerate. Does any opening stop an unneeded transfer while keeping legitimate ones?
  - X6 BETTER GATE (CPU, PC): task-grouped CV detector on stage-1 neurons + attribution neurons + J-lens words, against
    J_pairs 0.763.
  - X8 NATURAL DoM (GPU, after X2/X3):
    - DoM between correct policy-denial turns of passed episodes and the bad transfer turns, at L20/24/26 (pattern, not
      filter);
    - small doses plus an equal-norm random direction.
- Order:
  1. stage 2b remainder;
  2. X5 (cheap);
  3. X3;
  4. X2;
  5. X8;
  6. whatever the earlier results point to, until about 24:00.
  - X1 and X6 run on the PC CPU at the same time.

## J-Cascade EXPLORATION X RESULT (11-23 23:2x; jcascade/out/explore/explore_summary.md; exploratory, not confirmatory)
- 30+ configs on the same 75 turns (19 bad, 56 good). Baseline C0: bad converted 0 %, good kept 86 %.
- Best levers. Bad converted: original scoring / negation-aware rescoring. Good kept: ungated / gated.
  - P1 (clarified policy reminder): 21 % / 42 %; 45 % / 73 %. The only lever that moves every domain: airline 2/10,
    retail 1/4, telecom 5/5 on reading the texts.
  - PF_self: 21 % / 21 %; 82 % / 86 %. Telecom only.
  - PF_help: 21 %; 71 % / 80 %. Airline 2/10.
  - MID / MID2: 21 %; 71-73 %. Telecom 4/5, airline 0/10.
  - PF_deny: 0 % / 32 %; 80 %. Telecom 5/5 on reading.
- No lever moves the bad turns without also moving good ones. No config comes close to the stage-2 gate (40 % conversion
  with 80 % kept), except P1 rescored at 42 %, but only at 45 % kept.
- What the exploration says about the failure:
  - When (X1): no J-lens precursor in earlier turns. The decision forms at the turn.
  - What in context (X2): removing the tool-description clauses or the policy's transfer sentence changes nothing.
    Removing the user's requests for a human moves both bad and good turns.
  - Mechanism, from neuron ablation, TM, MID, sampling and the texts:
    - The unneeded transfer is a confident, deterministic script: 15/19 bad rows transfer in all 4 samples, against
      28/56 good rows. With the tool banned the agent still announces the transfer.
    - The attribution neurons implement the tool call, not the decision.
  - Two different failures:
    - Telecom (one task): early give-up. Flips easily with any opening that delays the decision.
    - Airline / retail: "the policy forbids it" read as "out of scope", so transfer. Robust. Even the explicit
      clarification moves only 2/10 airline turns.
  - Gate (X6): J-lens word pairs 0.763, neuron activations 0.79. Flags 13/19 bad and 12/56 good.
- Candidate for a pre-registered next step (user to decide): "J-lens gate → clarified-policy injection (P1) on flagged
  turns".
  - Gated now: bad 21 % (42 % rescored), good kept 73 %. Below the 40 % / 80 % gate on the original scoring.
  - It would need either a better gate or a clarification that spares legitimate transfers.
- Not done: training-time shaping (reliance / expression shaping) of the "forbidden → out of scope → transfer" reading.
  This is the doc-backed route for a script that inference-time levers cannot move.

## J-Cascade DETECTOR D (user 11-24 11:5x: "1번으로 가자 감지기 좀 더 좋게 만들어봐"; protocol fixed 12:0x, before any X15 result)
- Goal: a better gate for "J-lens gate → clarified-policy injection". The gate must stay J-lens layer + word based (the
  user's hard requirement). Neuron and residual detectors are reported only as comparisons or complements.
- Data (X15, GPU 0): every transfer turn of the unsteered Qwen3.5-4B runs:
  - f_detect (Haiku user, 3 domains, the current 75 rows);
  - hdetect (Haiku user, airline + retail);
  - detect (4B user, airline; retail detect excluded for the zip-auth bug);
  - d7obs_s1-6 and fitx (qwen user, airline).
  - Labels as in stage 0. Retail provisional passes (NL judge deferred) are excluded from good.
- Features at the decision point:
  - J-lens and J++ top-100 ids + logits at all 32 layers;
  - MLP activations L12-31;
  - residual L0-31.
- Detectors:
  - D1: J_pairs (the stage-0 method) retrained on the pooled rows.
  - D2: J-lens family features. Per layer and per pre-specified word family, the best logit of a family token in the
    top-100 (0 if absent), then an L2 logistic.
    - Families: inability, apology, understanding, acknowledgement, transfer, retry, proceed, refusal, hesitate, verify,
      ask, error, policy.
  - D3: D2 on J-lens + J++.
  - D4: neuron activations (comparison).
  - D5: residual logistic probe at L20/24/26 (comparison).
  - D6: rank-average of the best J-lens detector and D4.
- Evaluation:
  - 5-fold CV grouped by task across all runs. Hyperparameters (k, L2) are chosen inside the training folds only.
  - Primary set: Haiku-user rows (f_detect + hdetect), i.e. the deployment setting. Also reported: all rows.
  - Metrics: AUC, and TPR at a threshold set to 20 % FPR on the training folds' good rows.
  - System estimate on the 75 f_detect rows with regenerated outcomes: gated bad converted / good kept under P1 and
    P1PF_self.
- Choice rule: the best J-lens detector (D1-D3) by out-of-fold AUC on the primary set.
  - Any claim about it needs a fresh held-out confirmation (stage 4 test split or new episodes), because several
    detectors are compared on the same rows.

## J-Cascade REVIEW FOLLOW-UP (user 11-24 ~12:1x: "gpu0에서 이 계획 반영해서 코드 수정하고 실행해줘"; review pasted by the user)
- The review's six points, and how each is tested here. All of this is diagnostic: no method is tuned, and no stage-3
  episodes are run (stage 3 still needs a plan + cost report first).
- R1 power (point 1, CPU). How many repeats or branch continuations are needed before a 19-turn effect can be told apart
  from re-run noise?
  - Noise model from the 7-draw airline data: 24/50 coin-flip tasks, score 36.1 ± 2.0.
  - Designs compared:
    - (a) full reruns of all 278 tasks;
    - (b) branch-at-flagged-turn: the same prefix, K continuations per arm, only flagged episodes.
  - Grid: conversion c, success-given-conversion s, harm to legitimate transfers h.
- R2 sample size (point 3, CPU). Recompute the stage-0 AUC CI with a cluster bootstrap. The 5 telecom bad turns (one MMS
  roaming scenario) count as one cluster; the other rows cluster by task. Report the effective n.
- R3 situation-matched comparison (point 4, CPU on existing J-lens top-k + stage-1 neuron npz). Compare the bad transfer
  turn against denial turns in the same refusal situation:
  - (a) earlier turns of the same episode where the agent refused the request without transferring (same task, same
    request);
  - (b) denial turns of other episodes in the same domain.
  - Scores: the stage-0 J_pairs detector (pairs selected on transfer rows of the other folds), the a-priori family ranks
    (L20 inability, L24 understanding, L26 acknowledgement), and the X6 neuron detector.
  - Pre-registered reading:
    - If bad-transfer vs matched-denial AUC is <= 0.60, the detector reads the refusal situation, not the decision. The
      J-lens path is then closed and option (2) is next.
    - If it is >= 0.70, the decision itself is visible.
- R4 noise floor (point 2, GPU 0). Why does greedy C0 differ from the log on 11/75 turns?
  - (a) stage-2 C0 vs stage-2b C0: two separate processes, same settings.
  - (b) reruns C0_r2 / C0_r3 in new processes.
  - (c) teacher-forced check of the logged turn: the first position where the logged token is not our argmax, and the
    margin there. A near-tie means numeric drift; a large margin means a different backend or context.
  - Reruns of the key treatments give their own run-to-run stability and full texts for R6: P1_r2, P1PF_self_r2,
    PF_self_r2, PF_deny_r2, MID2_r2.
- R5 where the P1 effect enters (point 5, GPU 0). Activation patching from the P1 run into the clean run, on the rows
  where P1 changes the outcome.
  - P1 inserts its system message right before the assistant header, so only the header positions (and the inserted
    tokens) differ.
  - Patch sweep, per layer 0-31, on header positions aligned by offset:
    - the residual at all header positions;
    - the residual at the last position only;
    - the attention-block output only;
    - the MLP output only.
  - Metric: teacher-forced Δ = log p(P1's text) − log p(C0's text). Restoration = (Δ_patch − Δ_clean) / (Δ_donor −
    Δ_clean).
- R6 blinded re-judging (point 6, PC). A Claude Haiku judge (Claude Code CLI, Max plan) sees the last user message and the
  full agent turn, with config names hidden and the order shuffled.
  - Labels: called transfer / promised transfer without calling / refused or explained without transfer / continued
    helping (question or other tool) / broken.
  - Run on the full-text reruns (R4) and C0. The word-rule outcome is compared with the judge's.
- Code changes:
  - stage2b_regen.py: a `_rN` repeat suffix on any config, full generated text stored as `text_full`, and a `tfcheck`
    phase.
  - New: jcascade/patch_p1.py, review/power.py, review/matched.py, review/judge_blind.py.

## M1: WHERE does each failure form? Layer + neuron localization over ALL failures (pre-registered 11-24 12:4x, before any run)
User 11-24 12:3x: "실패 19개에서만 한게 문제" and "레이어나 어떤 뉴런에서 실패가 일어났는지 밝히기는 커녕 자연어로 대화중간에 넣는
실험이나 하고있냐". So: no prompt interventions. Mechanistic localization, all failure types, same footing for every failure.
- Data: the unsteered Qwen3.5-4B runs used by X15 (515 episodes: f_detect 3 domains, hdetect, detect airline, fitx, d7obs).
- Units, at the FIRST DIVERGENT TOKEN of a write call (teacher-forced from the logged generation):
  - bad, from failed episodes (every bad write, not only transfers):
    - T-name: chosen tool name differs from the expected one (first unmatched gold write). Covers unexpected transfers and
      unexpected writes when a gold write is still pending. Contrast c = chosen token, g = expected-name token.
    - T-args: same tool, an argument value differs from gold (wrong_args). c = chosen token, g = gold token at the first
      differing character (as in A1).
    - T-call: no gold write is pending but the agent calls a write (incl. transfer). Position = the <tool_call> token.
      c = <tool_call>, g = the best non-<tool_call> token there.
  - good, from passed episodes (one sampled write per episode, same three position types): c = chosen token, g = the
    runner-up token. This is the same measurement for correct decisions.
  - Missing writes (failed episodes with no bad write) have no divergent token; they are counted and reported, not hidden.
- Metric: m = logit(c) - logit(g) at the position predicting the divergent token.
- Per unit, one no-grad prefill of the prefix plus one grad step at that position:
  - direct logit attribution (DLA) of the embedding, every layer's attention output and MLP output to m (final RMSNorm
    linearized); check sum(DLA) ~ m;
  - per-neuron DLA (act x W_down . d) and grad x act of m, all 32 layers x 9,216 neurons.
- M1a (descriptive, all units): per failure type vs matched good units:
  - the layer profile (where m is written: attention vs MLP per layer, and the layer where the cumulative m turns and stays
    positive);
  - top neurons and how often they recur across failures, and whether the same neurons also drive correct decisions.
- M1b (causal, pre-registered now): per failure type with >= 8 bad units, 2-fold by task.
  - Select the top-K neurons by mean grad x act on fold A bad units, K in {16, 64, 256}.
  - Mean-ablate them at the unit's position (mean = good units of the same position type) on fold B.
  - Control: K random neurons from the same layers.
  - "Localized" = at some K: bad flips (m < 0) >= 30 %, random-control flips <= 5 %, and good units keep their choice
    >= 90 %.
  - Otherwise the failure is reported as not localized to a sparse neuron set (with the layer profile still reported).
- GPU 2 (A5000, idle; GPU 0 stays with the parallel session's review jobs). No generation, no Haiku. Code:
  server probe/m1/m1_extract.py, m1_analyze.py; outputs probe/m1/out, summaries copied to work/tau2-research/m1/.

## M1 RESULT (11-24 13:52; m1/out/m1a.md, m1a_taskbal.md, m1b.md)
**CORRECTION 11-24 14:2x: contrast artifact.** The fork session found it (probe/m1/m1_recontrast.py); I verified it.
- The bug: good T-name and T-args units used g = runner-up. For 104/223 T-name and 113/239 T-args units, that runner-up was a
  spelling variant of the chosen token (' transfer' vs 'transfer'). Bad units used g = gold, which is a different tool or
  value. Every bad-vs-good comparison for T-name and T-args is therefore invalid.
- Re-measured transfer T-name with the same contrast for bad and good (g = best other tool name; 24 bad, 22 good):
  - L31/1257, L31/2776 and L26/1006 are top-50 in 100 % of BOTH. They write 'transfer' and are not failure neurons.
  - L27 attention is LARGER in good transfers: 10.3 vs 7.8.
  - m is 19.4 good vs 15.8 bad.
- RETRACTED:
  - the "17 failure-specific transfer neurons";
  - "bad T-name relies on attention, good on L31 MLP";
  - the earlier formation layer for bad T-name;
  - the M1b good-kept numbers for the T-name/T-args groups. These are also the basis of the wrong_args:T-name LOCALIZED
    verdict, which is pending re-scoring.
- STANDS:
  - all within-bad results: the layer profile of bad units, the M1b bad flips vs random, and the absence of shared neurons
    in wrong_args:T-args;
  - every T-call comparison, since good T-call g is never a variant;
  - the unexpected_transfer:T-call verdict (n=10).
- Fix queued: probe/m1/after_h1_rc.sh runs on GPU 2 after the H1 head trace.
  - m1_rc2.py re-contrasts all good T-name/T-args units into out_rc2.
  - m1a_rc.py redoes the corrected bad-vs-good comparison, with neuron specificity cross-validated by task folds.
  - m1b_goodkept.py re-scores good-kept as "top-1 kept" on the identical ablation sets.

- Coverage: 515 episodes, 839 units: 154 bad from 40 tasks, 685 good from 170 tasks. There are 26 missing-write failures with
  no divergent token. Their count is reported here; the method cannot analyze them. Baseline drift in M1b: mean
  |m_base - m_extract| 0.086 (max 3.5).
- Duplication caveat: wrong_args:T-args has 37/59 units from airline task 21. wrong_args:T-name has 17/22 units from tasks
  17 and 21, which share the same '_b' > '_fl' (book vs update-flights) pair. Added m1a_taskbal (each task weighs once).
- WHERE the wrong preference is written (task-balanced DLA):
  - 78-93 % of m is written in L27-31 for every failure type. Good decisions are also written there (77-97 %), so "late
    layers" alone is not failure-specific.
  - What does differ: bad T-name relies on ATTENTION (L27 attention 6.47, L23 2.54) where good T-name relies on L31 MLP
    (6.65 vs 1.33 in bad). Unexpected transfer is the extreme case: L27 attention 8.48 of m 17.8.
  - The cumulative formation layer comes earlier for bad T-name than for good (median about 19-21 vs 27).
  - T-call failures, a write called while no gold write is pending, use the same profile and the same neurons as correct
    calls (top-200 overlap 154/200; L31/844, L31/66, L31/4074, L30/1269 are in the top-50 for 100 % of both). The failure
    is not a separate circuit. The one exception is L30/856.
- WHICH neurons (task-balanced, in the top-50 for >= 50 % of bad tasks and <= 10 % of good tasks):
  - unexpected_transfer:T-name has 17 such neurons across 19 tasks, the clearest failure-specific signature. L31/1257 is
    top-50 in 100 % of bad tasks vs 1 % of good. Others: L31/2776, L26/1006 (95 %), L31/1826, L31/826, L31/3377, L30/1922.
  - wrong_args:T-args (wrong digit or payment value) has none. No neuron recurs in more than 46 % of tasks (L29/121).
  - unexpected_write:T-name has 7 (L31/315, ...) from only 8 tasks.
- CAUSAL (M1b, pre-registered: out-of-fold top-K by grad x (act - mu_good), mean-ablation):
  - LOCALIZED, wrong_args:T-name, K=256: flips 0.71 and 0.62 across folds (task 17 to 21 and back), random 0, good kept
    1.0. It is one confusion type, book vs update-flights.
  - LOCALIZED, unexpected_transfer:T-call, K=64/256: flips 0.30/0.50, but the test folds hold only 8 and 2 units. Weak.
  - Not localized (8 groups): unexpected_transfer:T-name flips 0 % even at K=256 (dm -6.8 against m 17.8); wrong_args:T-args
    0 %; unexpected_write:T-name 0 %; unexpected_write:T-call 26 % at K=256; all:T-name 25 %; all:T-call 23 %.
  - The causally selected neurons sit in mid layers (6-23). The DLA-top neurons sit in L26-31. Late neurons that write the
    answer are not where an ablation can reverse it.
- Reading: transfer failures carry a consistent late-layer signature (L27 attention plus a fixed L26-31 neuron set) that is
  absent from correct decisions. That set is a readout, though: ablating it does not undo the choice, which means the
  decision is redundant or formed upstream (attention L23/L27 copying from context). wrong_args failures have no shared
  neurons beyond a single task's confusion.

## REVIEW FOLLOW-UP AMENDMENT (second review, user 11-24 12:3x: "반영할건 반영하고 걸러들을건 걸러들어")
- Written before any R3, R5 or R6 result exists.
- Stage-3 stop rule: no Haiku branch episodes unless R3 or R5 (or a later pre-registered test) yields an intervention
  whose gated bad conversion is >= 40 % on the offline turns (judge-confirmed, see R6) at no more than the C0 noise band
  of good-transfer loss.
  - The best so far is 21 % gated, so stage 3 stays off.
- Branch design, if it is ever run:
  - The unit is the branch point (25 flagged turns), not the 250 continuations. The R1 simulation already tests over
    branch points.
  - Telecom bad branch points count as one cluster.
  - The 12 good branch points are measured in the same run, so gain and loss come from one experiment.
- x15 sample, counted by distinct tasks:
  - bad: 35 rows from 24 tasks (airline 15, retail 4, telecom 5, the telecom ones being one MMS scenario; so about 20
    clusters);
  - good: 131 rows from 61 tasks (airline 26, retail 8, telecom 27).
  - The extra rows come from reruns of the same airline tasks (hdetect, detect, d7obs, fitx).
  - Every CV and CI uses domain|task groups, which r3_matched.py already does.
- R3 decision rules (fixed now):
  - Matched sets:
    - M1: denial turns in the same task as a bad transfer, in any run;
    - M2: denial turns earlier in the same episode as a bad transfer.
  - A denial turn has no tool call, a refusal phrase in its first 400 characters, no transfer / human-agent /
    representative / supervisor / escalation mention, and no completion phrase. This is the extractor in
    review_denial_extract.py.
  - Scores: J_pairs re-fit on the x15 transfer rows (task-grouped 5-fold, so denial rows get the pairs selected without
    their task), and the a-priori cascade (L20 / L24 / L26).
  - Judged on the 95 % task-cluster bootstrap interval of AUC(bad transfer vs M1):
    - "Reads the situation": the point estimate <= 0.655 (the stage-0 best simple baseline) or the CI upper bound < 0.70.
      The J-lens detection path is then closed for this failure, and option (2) is next.
    - "Decision visible": the CI lower bound >= 0.60.
    - Otherwise: inconclusive, reported as such.
  - M2 is reported only if it has >= 8 bad rows.
- R5 checks:
  - Header positions are aligned from the end. Only the shared header tail is patched, which already holds.
  - A same-length irrelevant system message is used as a null donor; its residual patch curve must stay near 0.
  - Restoration curves are reported separately for bad and good rows. The target is a layer / position that restores the
    bad rows but not the good ones.
- R4 interpretation rule: good-kept differences below about 11 % (6/56, the C0-vs-C0 flip rate) are not interpreted.
- R6 calibration: before Haiku judges anything, I read and label 30 blinded items myself.
  - The judge is used only if it agrees with me on >= 27/30; otherwise the prompt is revised once and re-checked.
- Not adopted from the review: nothing material. One fix: "positions must be aligned from the end" was already true,
  because only the header tail is patched. It is kept as a smoke-test check.

## REVIEW FOLLOW-UP results (filled in as they land)
- Note: the h-d4 / h-04 session ran x15_extract.py (166 transfer turns from 515 unsteered episodes, out/x15). It agreed to
  leave stage2b_regen.py and the queue to this run, and to fold its detector work into R2/R3.
- R1 power (jcascade/review/r1_r2.md):
  - Per full draw of all 278 tasks, the pass-count SD is about 5.3.
  - (a) Full reruns: c 0.4 with s 0.8 needs 13 draws per arm; c 0.4 with s 0.5 needs 31; c 0.2 with s 0.5 needs 124. Not
    feasible.
  - (b) Branch at the 25 flagged turns, K = 5 continuations per arm (250 Haiku continuation episodes):
    - power 0.96 at c 0.4, s 0.8, h 0;
    - power 0.78 with h 0.1;
    - power 0.57 at c 0.3, s 0.5.
  - At the observed best gated conversion (about 0.2), power is 0.13-0.6. Stage 3 as a whole-run comparison cannot
    separate pass from fail. Only the branch design can, and only for an effect of c >= 0.4.
- R2 sample size:
  - Stage-0 AUC 0.763, Hanley-McNeil SE 0.069.
  - 95 % cluster bootstrap CI: 0.63-0.88 (task clusters), 0.62-0.88 (telecom bad as one cluster), 0.57-0.87 (all telecom
    as one cluster).
  - Effective bad clusters: 15.
  - By domain: airline 0.68, retail 0.75, telecom 0.85; without telecom 0.71. The 0.75 pass is not robust.
- R4 noise floor:
  - (a) Two separate C0 processes (stage 2 vs 2b): first 600 characters identical on 57/75, outcome identical on 69/75.
    All 6 flips are good rows; the bad rows agree 19/19.
  - (c) tfcheck: 29/75 logged turns equal our greedy exactly. The other 46 diverge only at near-ties: the top-vs-logged
    log-prob gap at the first mismatch has median 0.125 and max 0.25, and the logged token is always rank 1-2.
  - 8 of the 9 C0 rows that do not transfer have such a tie.
  - So the noise is bf16 numeric ties in greedy decoding that then cascade, not a different backend or context. Offline
    "good kept" carries about ±8 % run-to-run noise by itself.
- R3 situation-matched comparison (jcascade/review/r3_matched.md). Data: x15 (35 bad from 24 tasks, 131 good from 61
  tasks) plus 111 denial turns from the same 515 episodes.
  - (A) bad vs good on the bigger sample:
    - J_pairs AUC 0.679, CI 0.55-0.80 (stage 0 had 0.763 on 75 rows);
    - the a-priori cascade (L20 / L24 / L26) is 0.558, CI 0.46-0.67, i.e. chance.
    - The stage-0 result shrinks with more data.
  - (B) bad transfer vs denial, pre-registered rule:
    - M1 (same task, 15 bad from 12 tasks vs 26 denials): J_pairs 0.673 [0.56, 0.80] → inconclusive; cascade 0.692
      [0.54, 0.82] → inconclusive.
    - M2 (same episode, earlier turn; 11 bad from 9 tasks vs 14): J_pairs 0.692 [0.59, 0.81] → inconclusive; cascade
      0.636 → reads the situation.
    - All denials in the domain: J_pairs 0.543 → reads the situation.
    - Reference: good transfer vs all denials, J_pairs 0.376. The detector ranks denial turns ABOVE legitimate transfers.
      It is high wherever the agent is in a refusal situation, whether it then transfers or denies.
    - Formal verdict on the primary M1: inconclusive. The secondary comparisons point to situation-reading.
  - (C) a trained linear probe on the residual stream, same-task bad transfer vs denial (task-grouped CV):
    - AUC 0.85-0.89 at L6 and L10-L18;
    - with the turn index regressed out, L12 0.887 and L18 0.841;
    - turn index alone 0.586; a within-task label-permutation null for L6 has mean 0.53 and max 0.73.
    - The transfer-vs-deny decision IS linearly readable at the decision point at middle layers, but not in the J-lens
      vocabulary. Caveat: 16 layers were scanned on 41 rows from 12 tasks.
  - R4 reruns, same settings:
    - C0 three runs: good kept 45-48/56, outcome agreement 67-70/75.
    - P1 two runs: bad converted (negation-aware) 8 and 10/19, 8 in both; good kept 25 and 24/56; agreement 61/75. P1's
      conversions reproduce.
  - R5 smoke (2 rows), with Δ = log p(P1 answer) − log p(C0 answer):
    - P1 moves Δ by about +30 (2.5 → 33.7; 19.2 → 44.7). The same-length null message moves it +2 to +6.
    - A single-layer header patch restores at most 0.13-0.20 (L13). The null donor's curve peaks at a similar 0.12.
    - So header positions carry little of the P1 effect, and that little is not P1-specific.
    - Before the full run, cumulative header patches (L0/8/12/16/20/24 through L31) were added, giving the upper bound
      of what the header can carry.
  - R6 calibration (29 blinded items: 7 transfer / 11 verbal / 5 text / 4 other_tool / 2 degenerate by the word rule;
    I labelled them before running Haiku):
    - Judge vs me: label 26/29. All 3 misses are C↔D (refuse-and-stop vs refuse-and-ask), both "no transfer".
    - On the metrics actually used, agreement is converted-vs-not 29/29 and offers_transfer 20/20.
    - Deviation from the 27/30 rule: the judge is used with C and D merged ("no transfer"). Label-level C/D splits are
      not reported.
    - The old word rule agrees with my labels on converted-vs-not only 18/29. Most of its errors label an offer ("Would
      you like me to transfer you?") as a verbal transfer.
    - From now on, conversions are reported in two parts: "stopped with no transfer mention" and "stopped but offers a
      transfer".
  - R5 full (18 rows where C0 transfers and P1 does not: 8 bad, 10 good; out/review/patch_p1.json, r5_summary.md):
    - Mean Δ: clean −1.1, P1 donor 18.5, same-length null donor 2.8. The null shift is 22 % of the P1 shift.
    - Single-layer header residual patch, restoration bad / good:
      - rises from L13 to a plateau of 0.21-0.26 / 0.13-0.19 at L13-L17, then about 0.20 / 0.09 up to L31;
      - the null donor gives 0.06-0.11 there, so the P1-specific part at the header is about 0.10-0.15.
    - By component, the attention output at the header peaks at L13 (0.12), L15 (0.18) and L19 (0.14) for bad rows. The
      MLP output stays <= 0.08. The last position alone matters only at L30-31 (0.17-0.20, the first-token logits).
    - Cumulative header patch: from L0 0.43 / 0.40, from L12 0.44 / 0.34, from L16 0.29 / 0.23, from L24 0.19 / 0.10.
    - Reading:
      - At most about 40 % of the P1 effect passes through the header positions. It is written there by attention at
        L13-L19, the same band where R3 finds the decision linearly readable (L10-18).
      - The other about 60 % reaches the answer through the generated tokens attending directly to the inserted text.
      - Bad-vs-good selectivity is weak: the largest gap is +0.12 at L14 (residual) and L15 (attention).
      - Any intervention confined to the decision point / header is therefore bounded at about 0.4 of P1's own effect.
        P1 itself stops only 3/19 cleanly, so this route cannot reach the 40 % gate. Consistent with the stage-3 stop
        rule.
  - R6 blinded judge, first batch (out/review/r6_judged.md):
    - C0_r2:
      - bad: transferred 17/19, stopped with no mention 0/19, stopped but offers a transfer 2/19;
      - good: tool transfer kept 45/56.
    - P1_r2:
      - bad: transferred 8/19, stopped with no mention 3/19, offers a transfer 8/19, broken 0/19;
      - good: tool transfer kept 26/56.
      - The word rule counted 4/19 bad stopped.
    - So most of P1's "conversions" end by offering the transfer. A user who says yes would still be transferred.
      Clean stops are 3/19.
  - R6 batch 2. Bad: transferred / clean stop / stop-but-offer / broken. Good: tool transfer kept.
    - C0_r3: 19 / 0 / 0 / 0; good 47/56.
    - PF_self_r2: 11 / 4 / 3 / 1; good 48/56 (no loss). The 4 clean stops are all telecom, one MMS scenario.
    - P1PF_self_r2: 8 / 6 / 3 / 2; good 36/56. Clean stops: telecom 4, airline 1, retail 1.
    - Gated with the J_pairs gate (13/19 bad flagged), clean stop / stop incl. offer / good kept:
      - P1PF_self 5/19 / 9/19 / 41/56 (C0 45/56);
      - P1 3/19 / 9/19 / 38/56;
      - PF_self 3/19 / 6/19 / 45/56.
    - Stage-3 stop rule, using clean stops (an offered transfer is not a fix): best gated is 26 % < 40 %, so stage 3
      stays off. Counting offers gives 47 %, but this is not adopted, because in these rows the user is already asking
      for a human.
  - R6 final batch:
    - MID2_r2: bad 12 / 3 / 4 / 0; good 48/56.
    - PF_deny_r2: bad 12 / 1 / 6 / 0; good 46/56. The earlier negation-aware 6/19 for PF_deny was mostly offers; there is
      1 clean stop.
    - All 7 reruns × 75 turns are judged (525 items, 0 judge errors). out/review/r6_judged.{json,md}
- REVIEW FOLLOW-UP CONCLUSION (11-24 ~14:2x):
  - No intervention tried so far stops unneeded transfers cleanly at a useful rate:
    - best ungated is P1PF_self at 6/19 clean, with good 36/56;
    - best without good loss is PF_self at 4/19 clean, all telecom, which is one cluster.
  - The J-lens word detector mostly reads the refusal context (R3). The decision is readable in the mid-layer residual
    (R3-C, L10-18), and that is where P1's effect is written (R5, attention L13-19). But at most about 40 % of it passes
    through the decision point.
  - Offline outcome noise is about 11 % on good rows (R4), so smaller differences are not interpreted.
  - Stage 3 stays off under the stop rule.
  - Next step waits for the user:
    - (a) allow a residual-probe detector at L10-18 instead of J-lens words, and pre-register a matched
      (same-task denial) DoM steering test there; or
    - (b) go to training-time shaping (option 2).
  - Reading:
    - J-lens word detection mostly reads the refusal context.
    - The decision lives in mid-layer residual directions (L10-18) that the J-lens word families do not express.
    - This conflicts with the user's hard requirement that the anomaly be confirmed with words at the flagged layers.
      The user has to decide whether a residual-probe detector is acceptable.

## C-LOOP: circuit tracing → root cause → steering on tau2 (GPU 0 only; started 11-24 14:3x)
Request (11-24 14:2x): attribution graph / circuit tracing, "분석 빡세게 해서 원인분석해서 tau-bench^2에서 steering해서 점수
올리는게 내일생일대의 목표다 gpu0에서만 돌아가는 루프 걸어줘". Loop cron 767c1178 (:13/:43). Papers: Goodfire neurons-as-basis (poles,
p97/3 tails, input/reader subcircuits, RelP 90 % margin pruning, mean-ablation), neuron communities (2611.23112: |h·dlogp/dh| top-k,
co-occurrence z-score graph, Leiden, necessity / sufficiency / layer-necessity tests), mechanistic shaping (2611.07071: pattern = DoM,
Gradient×Input, monitoring L1-L5). The parallel session moved to ToolAlignBench on GPU 2 (no conflict; it confirmed).
Fixed rules for this loop:
- GPU 0 only (c27bc2d7), UUID-checked in every script. Never touch other users' / sessions' jobs.
- No natural-language prompt interventions. Interventions act on activations, neurons, heads or directions only.
- Symmetric contrasts. Bad and good decisions are measured with the same alternative-token rule:
  - tool-name start: the best other tool-name first token;
  - mid-name and argument tokens: the best top-64 token that is not a case/space/prefix variant and has an alphanumeric char;
  - T-call: the best non-<tool_call> token.
  For bad units the gold-token contrast is reported next to it.
- Every selection is compared with a random control matched in count, layers and norm.
- Selection is made on the train split only: airline TRAIN 24 + retail/telecom tasks with md5(domain|task) % 2 == 0. Everything is
  evaluated on the other tasks. Current M1 units: bad train 112 (airline 99, telecom 7, retail 6), bad eval 42 (airline 36, retail 5,
  telecom 1); good train 368, eval 317.
  - Bad units are clustered: airline task 21 dominates. All CIs and AUCs are task-clustered.
- Exploratory comparisons are labelled as such and need a fresh held-out confirmation.
Stages and pre-registered gates:
- C0 tool (probe/circuit/c0_graph.py). Per decision unit, one cached-prefix grad step at the position predicting the divergent token.
  - Nodes and their scores:
    - MLP neurons 32×9216: act, grad×act, neuron DLA.
    - Attention heads, from the o_proj / out_proj input slice: head DLA and grad×act. Full attention has 8 layers × 16 heads,
      linear attention 24 layers × 32 heads.
    - Context sources for the 8 full-attention layers: exact per-source DLA = W_O^h (sigmoid(gate_h) ⊙ a_{h,s} v_s) · d. These are
      grouped by role (system/policy, user, tool output, assistant).
  - Edges: kept-node → kept-neuron input contribution to gate/up pre-activation, through the frozen RMSNorm scale.
  - Pruning (RelP-style): the smallest top-N set by |grad×act| whose survival (everything else mean-ablated at that position) keeps
    ≥ 90 % of m; necessity = ablating the set.
    - Made precise before any C0b run (11-24 14:5x), script probe/circuit/c0_prune.py:
      - score = grad × (x − mu), the first-order effect of mean-ablating the node (replaces |grad×act|, which is the effect of
        zero-ablation);
      - mu = mean over train-split good units of the same position type;
      - f(S) = (m_S − m_0) / (m − m_0), where m_0 = every neuron and head at that position mean-ablated;
      - N90 is found on a doubling grid 16…65,536 (of 295,808 nodes), then 4 bisection steps;
      - necessity: nec = (m − m_without_S) / (m − m_0);
      - random control: the same per-layer neuron and head counts, drawn outside S;
      - units with |m − m_0| < 0.5 are skipped.
    - The third validity criterion means: N90 exists for ≥ 80 % of units, and the random set's median f ≤ 0.5. Necessity is
      descriptive.
  - Validity gate before C1:
    - mean |sum DLA - m| < 0.3;
    - source DLA sums match head DLA (relative error < 2 %);
    - pruned sets keep ≥ 90 % of m while a random set of the same size keeps far less.
- C1 cause map. Build graphs for every bad unit and the matched good units, with the same contrast and task balance.
  - Report: the layer/head/neuron/source profile of bad vs good; neuron communities (co-occurrence + Leiden) with necessity and
    sufficiency tests.
  - A failure-specific path is a node, community or source group with task-clustered AUC ≥ 0.75 (bad vs good, CI lower ≥ 0.6),
    chosen on train and confirmed on eval.
- C2 offline intervention (teacher-forced, held-out). An intervention passes if: bad flips ≥ 30 %, the matched random control flips
  ≤ 5 %, and good decisions keep their choice ≥ 90 %.
- C3 episodes on a GPU-0 worker. Held-out tasks × 4 seeds, with base, candidate and random control run concurrently and no
  max_time.
  - Success requires the candidate's success rate to beat base with a task-cluster CI, and to beat the random control.
  - A run of more than 300 Haiku episodes is announced first; it starts at the next tick if nobody objects.
- If every C2 candidate fails, widen C1 to other circuits or failure types. Training-time shaping (LoRA) needs user approval.
- C1-T, the transfer decision upstream. Pre-registered 11-24 15:0x, before any knockout result.
  - Units: probe/circuit/out/units_up.json, built by c1_upstream.py: 36 units, 16 bad and 20 good.
    - Each unit is the first committed ' transfer' / ' human' / ' escalate' token in the reply text before <tool_call>.
    - A commitment phrase ("need to", "must", "Let me", "requires a", …) must appear within the previous 8 tokens.
    - The same rule is used for bad and good units.
    - 10 transfer turns have no text before the call and stay at the tool-call decision.
  - Graphs: c0_graph.py with C0_UNITS / C0_OUT=out/c0_up.
  - Causal test (c1_knockout.py): attention knockout of fixed key-position groups at the decision query of all 8 full-attention
    layers. The groups are defined before the results and with the same rule for bad and good:
    - user_last
    - user_mention and gen_mention (word list: human / agent / supervisor / transfer / person / someone / representative / …)
    - user+gen_mention
    - system_all
    - system_transfer_clause (system tokens within ±12 of transfer / human / escalate)
    - gen_before
    - assistant_earlier
    - tool_all
    - top10 / top50 by total source effect
    - Random controls: same size, same role pool, 3 draws.
  - Criteria:
    - A group is a causal source if its knockout flips ≥ 30 % of bad units (m' < 0) and its random controls flip ≤ 5 %.
    - It is failure-specific if the bad flip rate − good flip rate ≥ 0.3, reported per domain.
    - Bad units are 10 airline (2 of them in train tasks), 5 retail and 1 telecom. Good units are mostly telecom.
    - So the result is exploratory and must be confirmed on fresh episodes. Groups are fixed lists, not selected, so the split
      rule does not apply to them.
Status (11-24 16:2x):
- C0: PASS (decision log 16:2x).
- C1 so far: every pre-registered test is null.
  - C1-T: transfer upstream knockout;
  - C1 profile: its 4 passes are confounded by tool and domain;
  - C1-N: neuron communities.
- C1-M select: 11/18 turns at 16:20, and the interim pick is NONE. It finishes around 16:50; confirm runs only if a
  setting converts.
- Earlier status, kept for the record:
  - C0b smoke, 4 units with partial means:
    - N90 is 7.4k–22.5k of 295,808 nodes;
    - random sets of the same size keep 0–4 %;
    - necessity is about 1.0.
    So the decision circuits are valid but large, not sparse.
- C1-T (transfer, upstream token): NOT MET (decision log 15:2x).
- C1-M as run. Pre-registered 11-24 15:3x, before any C1-M result. Script probe/circuit/c1m_dom.py.
  - Why the plan changed: same-task denial donors exist for only 2 of the 35 bad transfer turns (x15: 35 bad from 24
    tasks; denial turns from passed episodes: 49). So full-residual same-task patching is not possible.
  - Data, reused read-only:
    - jcascade/out/x15: 166 transfer turns, residual at the decision point (the last input position), layers 0–31;
    - jcascade/out/review/denial: 111 denial turns, same features.
  - Labels:
    - bad = an unneeded transfer (label bad_write) in a failed episode: 35;
    - legit = a gold transfer (good_write) in a passed episode: 25;
    - harmless = a bad_write transfer in a passed episode: 106;
    - denial = a denial turn of a passed episode: 49.
  - Direction:
    - v_L = mean(res_L, denial train) − mean(res_L, bad train), using train tasks only, L ∈ {10, 14, 18};
    - added as α · |h_L| · v_L/|v_L| with α ∈ {0.1, 0.2};
    - scope D: the decision point only (prefill last position); scope A: also every generated position;
    - random control: a random direction with the same norm (seed 0) for every (L, α, scope).
  - Outcome:
    - greedy regeneration of the turn (≤ 320 new tokens, stops at </tool_call> or <|im_end|>);
    - transfer = the reply contains <function=transfer_to_human_agents;
    - also count other write calls and degenerate output (a repeated 8-gram ≥ 3 times).
    - The baseline regeneration must reproduce the logged transfer for ≥ 90 % of the turns, otherwise stop.
  - C1-M passes if the selected setting meets all of these on EVAL bad turns:
    - selection: on train bad turns, the most conversions among settings with degenerate ≤ 10 %;
    - on eval: bad converted ≥ 30 %;
    - its random control converts ≤ 5 %;
    - degenerate ≤ 10 %.
  - Legit, harmless and denial turns are reported here. They are not gated, because selectivity is the job of the C2 gate.
  - Definitions, fixed 15:3x before any select result:
    - converted = the regenerated outcome is "text" or "other_tool" (no transfer call and no verbal transfer);
    - "verbal_transfer", "degenerate" and "capped" are not converted, and degenerate + capped counts as degenerate.
    - Tie-break for selection: most conversions, then fewer degenerate, then smaller α, then scope D, then the lower
      layer. c1m_pick.py applies it, and the confirm phase starts automatically.
    - If the best setting converts 0 train turns, C1-M fails without a confirm run.
  - Smoke, 1 turn (task 11): the base regeneration reproduces the logged transfer, at about 12 s per condition. Its rows
    are kept as part of the select run, since the code and the conditions are the same.
  - Deviation, 15:5x, decided from the logged generations only. In 2 of the 18 train bad turns the logged transfer call
    comes at token 1,597 (task 10, x15:33) and 2,616 (task 39, x15:49). That is beyond MAX_NEW = 480, so the turn's
    first decision is not the transfer.
    - Rule: turns whose logged transfer comes after MAX_NEW are excluded from selection and from the reproduction check.
    - The eval bad turns are all ≤ 344, so none are excluded there.
    - The same rule applies to the legit / harmless turns in the confirm summary.
- C1-N, neuron communities (paper 2611.23112). Pre-registered 11-24 15:5x, before any C1-N result. Scripts
  probe/circuit/c1_comm.py (CPU) and c1_comm_abl.py (GPU, later).
  - Node score per unit: s = grad × act at the decision position (C0a grad, M1 act), symmetric contrast. Top-k = 100
    neurons by |s| per unit.
  - Graph from TRAIN units only (bad and good):
    - neurons in the top-k of ≥ 5 train units;
    - an edge when the co-occurrence z ≥ 3 and n_ij ≥ 3, where z = (n_ij − N p_i p_j) / sqrt(N p_i p_j (1 − p_i p_j));
    - networkx Leiden (seed 0, resolution 1), with Louvain as a cross-check;
    - communities with ≥ 5 neurons are kept.
  - Unit score per community: its share of the unit's top-k attribution mass, Σ_C |s| / Σ_topk |s|.
  - Specificity test, matched groups, the lesson of the profile test:
    - (i) transfer T-name: bad vs good transfers;
    - (ii) T-args: bad vs good, by the same tool;
    - (iii) T-call: bad vs good.
    - For each group, the community with the largest |AUC − 0.5| on train is tested on eval. It passes at AUC ≥ 0.75 (or
      ≤ 0.25) with a task-cluster CI that excludes 0.6 (0.4). Per-domain AUCs are reported.
  - Necessity (GPU, after C1-M): mean-ablate the community at the decision position on eval units of the group. A
    community is necessary if it flips ≥ 30 % of the group's bad units (m' < 0) while a random set with the same layer
    counts flips ≤ 5 %. The KL of the output distribution is reported (paper: necessity KL ≥ 0.7).
- Next (C1 widened, in order):
  1. C1-M, the mid-layer decision at the turn start.
     - J-Cascade R3-C found the transfer decision readable at L10–18 of the turn, before any reply token.
     - Causal test: activation patching at the first reply position, L10–18 residual. Donors are same-task denial turns
       from passing runs; recipients are bad transfer turns. Reverse patching, good into bad, is the control.
     - Pass if bad transfers flip ≥ 30 %, a random same-norm patch flips ≤ 5 %, and good transfers survive the
       reverse-direction control ≥ 90 %.
     - Only if it passes: C2 detector-gated DoM at that site.
  2. A mechanism table for all 43 f_detect failures, CPU, from the logs: capability misbelief, policy misreading,
     pressure transfer, selection error, computation or order error, or other. This bounds what any single fix could
     gain.
  3. Linear-attention (GatedDeltaNet) per-source attribution via the delta-rule's linear form, so that source tracing
     covers all 32 layers. Needed for the wrong_args provenance.

## C2T: the ToolAlign CAUSAL-2 intervention on τ² (pre-registered 11-25 09:5x, before any run; GPU 0)
User 11-25: "같은 방식 개입을 tau^2 bench에서 gpu 0으로 돌려줘".
- Intervention, the same as ToolAlign CAUSAL-2:
  - Regenerate an agent turn greedily from its first token.
  - At EVERY generated position, set the attention-block output of chosen layers to μ. μ is the mean attention output
    over generated tokens of reference turns: correct non-transfer write turns from passed episodes, leave-one-task-out.
  - Qwen3.5-4B, offline, no user simulator.
- Units, from the M1 turns: dedup by (cond, sim, turn, call).
  - A: 34 unneeded-transfer turns (primary).
  - B: 29 unexpected-write turns.
  - L: 22 legitimate-transfer turns (specificity).
  - K: 40 correct non-transfer write turns, a domain-stratified sample with seed 0, used for "kept".
- Configs:
  - base;
  - attention bands 16-20, 12-20, 3-11, 21-29;
  - full {15, 19}; linear 12-20;
  - 3 random 5-layer draws outside 12-20; 3 random full-attention pairs outside 12-20;
  - 16-20 onset-only and after-onset.
- Outcome, from all `<function=…>` names of the regenerated turn:
  - flip = the original call is absent and the turn ended (EOS);
  - unfinished = the budget min(1536, 1.5·len+64) was hit;
  - verbal transfer = no transfer call, but the text says transfer / human agent / representative.
  - Units whose base regeneration does not reproduce the original call are excluded and counted.
- Pre-registered predictions:
  - T1: 16-20 removes ≥ 50 % of unneeded transfers (A), with unfinished ≤ 10 %.
  - T2: legitimate transfers (L) flip at a similar rate (within 20 pp of A), i.e. the effect is NOT failure-specific
    (predicted from ToolAlign).
  - T3: every random 5-layer draw flips ≤ 20 % of A.
  - T4: K keeps its call ≥ 90 % under 16-20.
  - Also report onset-only vs after-onset, and how many flips are verbal transfers.
  - If T1 fails, τ² stays "not flippable by activation edits" even with the ToolAlign intervention.
- Code: probe/c2t/tau_causal2.py (stats in 3 parallel splits → 4 dynamic workers → report). Output: probe/c2t/out.
- AMENDMENT 11-25 13:2x. The user asked why the τ² layers were not chosen from τ² J-lens evidence. Two τ²-grounded
  configs were added BEFORE any C2T outcome was read (52 rows existed, none inspected):
  - attn_band_10_18: the layers where R3 reads "transfer vs refuse" (0.85-0.89). Prediction T5: it removes the
    transfer decision like 12-20, and flips are NOT mostly verbal.
  - attn_27: only layer 27, where H1 found head 5 retrieving the transfer tool entry (the copy step). Prediction T6
    (copy thesis): the transfer CALL disappears in a minority of turns, and when it does, most such turns still
    transfer verbally. In other words, the decision survives the copy-layer edit.
- AMENDMENT 2, 11-25 13:2x. User: "τ² 근거 기반 설정 두 개만해줘 14개 박치기는 좀 오바다".
  - Only base, attn_band_10_18 and attn_27 are run and reported (C2_CONFIGS).
  - T1-T4 (ToolAlign bands and random controls) are dropped. The rows already made for them are kept on disk, not
    analyzed.
  - Without a random-layer control, T5 is read against base only. A large flip rate shows the window carries the
    decision, not that it is the ONLY window.

## Decision log
- 11-25 13:5x C2T RESULT (Qwen3.5-4B; base + attn_band_10_18 + attn_27; c2t/out/report.md).
  - Base reproduces the original call in A 32/34, B 29/29, L 21/22 and K 40/40.
  - attn_band_10_18:
    - unneeded transfers flip 28/32 (88 %), unfinished 0, verbal-only 3/28;
    - unexpected writes flip 25/29;
    - legitimate transfers flip 20/21 (95 %);
    - correct writes are kept in only 20/40.
    - What the flips became: mostly OTHER WRITE calls. A: update_reservation_baggages 17/28, update_reservation_flights
      3, cancel 2. K: baggages 11, refuel_data 5. L: resume_line 12.
  - attn_27:
    - A flips 2/32 (both became text replies; 1 was a verbal transfer);
    - B 3/29; L 5/21 (became read calls); K kept 39/40.
  - T5 is formally MET (88 % flips, 11 % verbal), but the substance differs from the prediction. The edit does not
    "remove the transfer decision". It erases the context-driven choice, and the model falls back to the average
    reference action, a generic write, often an unjustified one such as update_reservation_baggages. It also wrecks
    legitimate transfers and half of the correct writes. This is a hijack toward the reference mean, not a fix, and
    not failure-specific.
  - T6 (copy layer): the decision survives a layer-27 edit (94 % unchanged), consistent with the copy thesis. The
    "mostly verbal" part is untestable (n=2 flips).
  - vs ToolAlign: the same mechanism. Mid-depth attention carries "which action, given the context".
    - In ToolAlign the reference mean was the benign default (writeInternalLog), so the flips looked like a fix.
    - In τ² the reference mean is "some write", so the flips become wrong writes.
    - The ToolAlign CAUSAL-2 "fix" therefore reflects what the reference mean was, not a misalignment mechanism.
- 11-24 17:1x STOPPED at the user's request ("걍 멈쳐줘 여기세션 실험").
  - Cron 767c1178 is cancelled.
  - Killed by pid: the after_c2n.sh waiter and c2n_neuron.py, mid-select at 5/16 turns. No C-loop process is left and
    GPU 0 is free.
  - C2-N partial result, 5 train bad turns, exploratory only. Base 5/5 transfer. Every neuron setting converted 0/5
    (K64/K256, λ 1/3: transfer 4–5, capped 0–1). The random controls were the same (0/5, one degenerate at λ 3).
  - Partial outputs are kept in out/c2n/rows_select.jsonl. The C1-M confirm rows are in
    out/c1m/rows_confirm_L18_a0.1_A.jsonl.
- 11-24 17:0x C2-N, neuron steering. The user asked (17:0x): "neuron-explorer은 그냥 neuron steering만해도 바뀌던데 너는
  뭐니?". Until now the loop used mean-ablation and DoM directions, never clamping or steering neurons. Pre-registered
  before any C2-N result. Script probe/circuit/c2n_neuron.py.
  - Data: the same turns as C1-M (x15 transfer turns, denial turns), with the decision-point MLP activations at
    L12–31 (feat 'mlp').
  - Neuron selection, train tasks only:
    - effect size d = (mean_bad − mean_denial) / pooled sd per neuron (L12–31 × 9216);
    - the top-K by |d|, K ∈ {64, 256}.
  - Steering: on the selected neurons, at the decision point and at every generated position,
    a ← a + λ · (μ_denial − μ_bad), with λ ∈ {1, 3}. So λ = 1 moves a neuron by its bad-to-denial mean gap, and λ = 3
    pushes it 3× further toward the denial pole.
  - Random control: K random neurons with the same per-layer counts, given the selected shift magnitudes (permuted)
    with random signs.
  - Outcome: same as C1-M (greedy regeneration; first call; converted = text / other_tool).
  - Select on the train bad turns (16; the same 2 late turns excluded), with the C1-M tie-break. Then confirm the pick on
    eval bad 17 + legit 25 + harmless 20 + denial 20.
  - Pass:
    - eval bad converted ≥ 30 %;
    - the random control ≤ 5 %;
    - degenerate ≤ 10 %;
    - legit transfers kept ≥ 90 %, reported. If only this fails, a gate is the next step.
- 11-24 16:5x C1-M RESULT (confirm, L18_a0.1_A, eval). NOT MET.
  - Eval bad: base 17/17 transfer. DoM converts 1/17 (6 %; 1 text). The random control converts 0/17 (3 verbal transfers,
    not counted). Gate ≥ 30 %.
  - Legit (gold transfers), eval: base 10/11 transfer; DoM 7/11; random 7/11. Train: 14/14, 12/14, 12/14. The DoM is no
    more harmful to legit transfers than a random direction, and no more useful.
  - Harmless, eval / train: base 4/4 and 12/12; DoM 3/4 and 7/12; random 3/4 and 9/12.
  - The denial turns were still running at 16:56. They are reported when done and do not affect the verdict.
- 11-24 16:5x WHERE THE C-LOOP STANDS. Every pre-registered C1 test is null:
  - C1-T: no causal source group;
  - profile: its passes are confounded;
  - C1-N: no failure-specific community;
  - C1-M: a decision-point DoM converts 6 %.
  - With the J-Cascade work (X1–X8, R3–R6) this covers source occlusion and knockout, neuron sets and communities,
    head-level profiles, and DoM at L10–31, both at the decision point and on all positions.
  - Root cause, in plain terms:
    - The biggest failure family is the give-up transfer. The policy-denied request is read as out of scope, so the agent
      transfers. It is formed in mid layers at the start of the turn (R3-C: readable at L10–18), written out in the
      reply text, and then copied into the call.
    - Wrong arguments are reasoning errors written earlier in the reply and copied.
    - Unexpected writes are wrong plans that the user then confirmed.
  - None of these has a sparse or failure-specific circuit. The decisions are confident: m ≈ 11–17 against the
    alternatives, and N90 is 10²–10⁴ nodes.
  - Next, by the loop rules:
    - (a) training-time shaping (LoRA, reliance / expression shaping) needs the user's approval, and is asked for in the
      16:5x report;
    - (b) until then, one more C1 widening: C1-F, the formation of the L10–18 decision at the turn start (decision log
      below, when it is pre-registered).
- 11-24 16:5x C1-T v3 RESULT (valid contrasts for all 16 bad units; c1_knockout.py on out/c0_up v3). NOT MET.
  - The bad units' g are all real alternative words: make, consider, arrange, offer, inform, assist, follow, now, be,
    proceed, check.
  - The good telecom ' escalate' units (9) got ' elevate', a synonym, so their good-side numbers are discounted.
  - Bad m median is about 12.8 (range 0.1–17.3). The decision is already made at the committed token.
  - Knockout of the fixed groups at the 8 full-attention reads:
    - the best is top50_total, 2/16 bad flips (12 %), and these are the two units with m < 8;
    - system_all: 0/16 flips, mean dm −1.6;
    - system_transfer_clause: 1/16 (the m = 0.1 unit), dm −1.4;
    - user_last, user_mention, user+gen_mention: 0/16, |dm| ≤ 0.4;
    - random controls: |dm| ≤ 0.04 with 0 flips.
  - The all-layer source shares (full + linear total effect, c1_allsrc.py → out/c0_up/allsrc_report.txt) are
    first-order and do not sum to m. They are recorded as exploratory only and are not interpreted.
  - Verdict: no fixed source group is a causal source of the committed transfer token. This agrees with J-Cascade X2,
    where text occlusion moves bad and good transfers alike.
- 11-24 16:4x CORRECTION to C1-T. The v2 upstream contrast was still a variant for 25 of the 36 units:
  - '_transfer' ×13, ' escape' ×9 (for ' escalate'), 'escal' ×3. Only 11 units had a real alternative word.
  - The 15:2x note "a stronger filter cannot rescue it, so the verdict stands" was wrong for those 25 units: their m
    measured spelling, not the decision. The C1-T verdict is suspended until v3.
  - The all-layer source report on v2 (role shares, top sources) is therefore also void. Archived as
    archive/c0_up_v2_variant_contrast.
  - v3 concept rule (c0_graph.py), compared after stripping non-alphanumerics. A token is skipped if:
    - it starts with a concept stem;
    - or it is a ≥ 3-character prefix of a stem;
    - or it shares a ≥ 4-character prefix with c.
  - Rerun chain on GPU 0: c0_graph → c0_linsrc → c1_knockout on out/c0_up. The criteria are those pre-registered for
    C1-T.
  - T-call alternatives were checked and are fine: 'I' 133, '**' 35, 'Let' 26, and so on.
- 11-24 16:3x C1-M select done (16:26; out/c1m/rows_select.jsonl, pick.json).
  - 16 train bad turns counted (2 late turns excluded). The base regeneration reproduces 16/16.
  - Every one of the 12 settings converts at most 1/16 turns.
  - The pre-registered pick is L18_a0.1_A: it converts 1/16 with 1/16 degenerate. Its own random control also converts
    1/16, so the selection is at noise level.
  - D-scope settings, at the decision point only, convert 0/16.
  - By the pre-registered rule (≥ 1 conversion → confirm), the confirm phase started automatically at 16:26: eval bad 17,
    legit 25, harmless 20 and denial 20 turns × {base, dom, rand}. ETA about 17:30.
- 11-24 16:2x C0 VALIDITY GATE: PASS (c0_gate.py → out/c0/gate.md; C0a and C0b on all 839 units; C0b finished 16:26).
  - (1) |m_lin − m|: mean 0.055, p95 0.129, max 0.181. Gate < 0.3.
  - (2) Source DLA vs head DLA, L1 relative error: median 0.36 %, p95 0.53 %, max 0.71 %. Gate < 2 %.
  - (3) N90 exists for 784/839 = 93 % of units.
    - N90 median is 2,240 nodes (p10 31, p90 24,576) of 295,808, and f at N90 has median 0.91.
    - A random set of the same size has median f 0.015 (p90 0.11).
    - Ablating the N90 set removes a median 0.93 of (m − m0); the random set removes 0.00.
  - By type, median N90: T-args 108–184 nodes (necessity about 0.5, so partly redundant); T-name 2k–12.5k; T-call
    10–12k with about 700 of 896 heads.
    - N90 neurons sit mostly in L30–31 (35 %) and L14–22.
  - Matched check: N90 size does not separate bad from good.
    - transfer T-name: 8.3k vs 3.4k, AUC 0.54;
    - non-transfer T-name: AUC 0.38;
    - T-call: 0.43 / 0.44;
    - T-args: 0.56.
    The raw T-name gap (12.5k vs 2.0k) comes from unit composition.
  - C0 is done. The tools are valid, and the decision circuits are real but not sparse.
- 11-24 16:0x C1-N RESULT (pre-registered 15:5x; c1_comm.py → out/c1n/comm.md). NOT MET.
  - Graph: 1,788 neurons appear in ≥ 5 train top-100 lists, with 91,501 edges at z ≥ 3. Leiden gives 24 communities of
    ≥ 5 neurons; Louvain gives 8. The large communities agree across the two methods (Jaccard 0.80–0.96).
  - Matched-group specificity on eval: none passes.
    - transfer T-name: #7 (93 neurons, the 'transfer'-writing community, share 0.15 in transfer units vs 0.01 elsewhere).
      Train AUC 0.85, eval 0.57 [0.26, 0.84].
    - T-args, same tools: #1, train 0.16, eval 0.29 [0.14, 0.48].
    - T-call, same tools: #21, train 0.65, eval 0.45.
  - Overall, communities #5, #8 and #11 are 4–6× higher in bad units. They are token-content communities from task 21,
    which dominates the bad units:
    - #5 writes '_b' after "update_reservation_" (baggages before flights, tasks 21/17/33);
    - #8 and #11 write the digits '2' and '7' of the task-21 flight numbers.
    The task-cluster CI removes them.
  - The GPU necessity test is not run: there is no specific community to test.
- 11-24 15:5x unexpected_write (29 bad units): 26 follow a user confirmation ("Yes, please…"), 3 follow a tool output. Good
  T-calls: 156 confirmed, 20 unconfirmed, 47 after a tool output. These are not "acting without confirmation". The agent
  proposed a wrong plan and the user agreed, so the error is upstream reasoning.
- 11-24 15:4x Tools and contrast hygiene.
  - c0_linsrc.py, exact per-source attribution through the 24 linear-attention layers, works. The gated delta rule is linear
    in v given k, beta and g. Weights w_s = beta_s k_s^T A_{s+1}…A_t q_t (backward recursion); the gated RMSNorm is frozen.
    - Smoke on units 1 and 27: reconstruction error ≤ 0.3 %. The per-head direct and total sums match C0a within 0.033
      and 0.045. About 40 s per unit.
    - Source tracing now covers all 32 layers.
  - Example, unit 1 (bad transfer, T-name, m 17.3):
    - 'transfer' is copied from this turn's own text "…I need to transfer you to a human agent.\n\n<tool_call>\n<function="
      (+1.8, +1.2 at the last two markup tokens, half through linear attention). Also from the system tool entry
      "transfer_to_human_agents" (+0.8) and the policy line "make a tool call to transfer_to_human_agents" (+0.7).
    - "update_reservation_baggages" in the tool list pushes the other way (−1.6).
    - So the name step is a copy of the decision already written in the text.
  - Contrast hygiene, third pitfall: 42 of 298 T-args units had a class-mismatched g. These were variants ('_credit' for
    'credit', '>An'), '<|im_end|>' ×3, or a Chinese token. That is bad 6/59 and good 36/239. The T-args profile test is
    null either way.
    - c0_graph.py rule v2, now the default (C0_RULE=v2):
      - compare tokens after stripping non-alphanumerics;
      - skip <…> markup and special tokens;
      - skip non-ASCII alternatives when c is ASCII.
    - C0a rows stay as they are (rule v1), recorded here. The run-2 code is archived as archive/c0_graph_run2_upstream_v2.py.
- 11-24 15:3x C1 PROFILE TEST (pre-registered C1 gate; c1_profile.py → out/c1/profile.md; full C0a, 839 units).
  - Formally 4 of 30 train-selected features pass on eval (AUC ≥ 0.75, CI lower ≥ 0.6, or the mirror). All 4 are T-name
    (tool_first) head total-effect shares: L20h5, L28h10, L29h28, L29h31.
  - They are confounded, so they are NOT accepted as failure-specific paths:
    - Tool identity: bad T-name units are 24/34 'transfer', while good units are spread over all tools. Among good
      units, transfer vs other tools gives AUC 0.69 / 0.90 / 0.84 / 0.01 for the four heads. The heads track which tool
      is named.
    - Domain: within transfers (bad 24 vs good 22) AUC is 0.74 / 0.67 / 0.73 / 0.19. Within airline transfers (only 2
      good) it is 0.50 / 0.36 / 0.79 / 0.64. The transfer split is airline/retail bad vs mostly telecom good.
    - L20h5 also separates non-transfer bad vs good T-name (AUC 0.73), but that is 10 bad units over 7 tools.
      Exploratory only.
  - T-call and T-args: no feature passes. The best eval AUCs are 0.33–0.62.
  - Lesson: the C1 profile test must match bad and good by chosen tool and domain. The pre-registered version did not, so
    its 4 passes are recorded as confounded.
- 11-24 15:2x C1-T RESULT (pre-registered criteria; c1_knockout.py on out/c0_up v2: 16 bad, 20 good). NOT MET.
  - No knockout group is a causal source. The best is top50_total: it flips 2/16 bad (12 %) and 1/20 good.
    - Bad mean dm: system_all −0.95, system_transfer_clause −0.64, top50 −3.3. Good: system_all −0.62, top50 −3.1.
    - User and gen mention groups: |dm| ≤ 0.3, flips 0.
    - Random controls: |dm| ≤ 0.05.
  - At the committed ' transfer' token the decision is already made. Median m is about 12 against the best non-transfer
    word. The units that flip are the two with m < 1 (k=100176, 100370).
  - Bad and good read the same sources. Limitation: the 24 linear-attention layers are not covered by this knockout.
  - The concept filter still let '_transfer', 'escal' and ' escape' through as g for about half of the units (rank 2–7). A
    stronger filter cannot rescue a decision with m ≈ 12, so the verdict stands.
  - This agrees with the J-Cascade work of 11-23 (X1/X2/N10/N20, review R3–R6):
    - no precursor in earlier turns;
    - text occlusion of the policy and tool clauses changes nothing;
    - DoM steering fails (N10 bad 1/19, N20 3/19 with good kept 39 %);
    - the decision is readable at L10–18 of the turn.
- 11-24 15:2x Failure landscape for f_detect (from the logs; no new GPU work):
  - 22 of the failures are missing writes (the agent's writes are a strict prefix of gold). 13 of those 22 end in a
    transfer before a required write:
    - airline tasks 11, 29, 32, 33, 40, 44;
    - retail tasks 111, 6, 60, 8;
    - telecom MMS × 3.
    So "giving up by transfer" is the largest single cause.
  - Transfers are often harmless for reward. In the base-like airline runs, 115 of 240 runs contain a transfer and most
    of them pass, e.g. task 41 is 11/11 pass, all with a transfer. Blocking transfers blindly would therefore risk the
    passing runs.
  - wrong_args (91 units, 39 episodes, 18 tasks) is mostly reasoning that was already written in the reply and then
    copied into the call: the wrong 'fastest' flight in task 21, the bag count computed before the cabin change in tasks
    17/21/33, the wrong reservation or order chosen in tasks 39/42/retail 59, the payment method in task 18.
  - Bad decisions are confident:
    - median m is 13.6 (T-name) and 12.8 (T-args), and the gold token is usually rank 2–6;
    - low m separates bad from good only for T-args (AUC 0.74);
    - so there is no near-tie lever.
- 11-24 15:0x Upstream transfer units, v1 → v2. The v1 contrast was a translation artifact.
  - In v1, the novariant rule picked '转移' (Chinese "transfer") as g for most ' transfer' units. So m measured English vs Chinese,
    not the decision.
  - The source report and the 7 knockouts that had finished were therefore uninformative: |dm| ≤ 1.4, mostly ≈ 0.1.
  - The run was stopped (my pid) and the outputs were archived to probe/circuit/archive/c0_up_v1_translation_contrast.
  - v2, the same rule for bad and good:
    - decision token = the first verb ' transfer' / ' Transfer' / ' escalate' after a commitment phrase;
    - new "concept" contrast in c0_graph.py: g = the best top-64 ASCII word that does not start with a transfer-concept stem
      (transfer, escalat, connect, refer, redirect, forward, route, hand, pass, human, supervisor, manager, representative,
      specialist).
  - Checked C0a for the same problem: 1 of 280 rows has a non-ASCII g ('7' vs '现在', not a translation). The T-name units use
    tool names, so C0a is fine.
  - Exploratory reading of the v1 report, which does not depend on g:
    - the commitment token right before the decision ("need to") dominates the direct read at L31;
    - the system tool description "Transfer the user to a human agent" and the policy line "You should transfer the user to a
      human agent if and only if…" are read at L19–L27;
    - in several bad units, the agent's own earlier turns ("This would require a human agent") feed the decision.
- 11-24 14:5x C0a smoke passed; full run started on GPU 0.
  - Smoke: 3 transfer units. |m − m_lin| ≤ 0.1. Head-vs-attention DLA diff ≤ 0.013. Source sum vs head DLA L1 relative error
    ≤ 0.4 %.
  - First look, exploratory, 2 bad + 1 good transfer: 'transfer' vs 'update' comes from the L23/L27/L31 full-attention heads
    reading the system block (the tool list), plus L31 reading this turn's generated tokens. The bad and good units look the same.
    So the name token copies a choice made earlier. C1 therefore needs the total (gradient) source effects at L3–L19, not only
    direct effects.
  - Added grad-based per-source total effect: tsrc = a_{h,s} · v_s · (sigmoid(gate_h) ⊙ ∂m/∂(o_proj input)_h).
  - The symmetric-contrast rerun of all units is part of C0a: rc2 never wrote output, so out_rc2 is empty.
- 11-24 14:4x C-LOOP started (section above).
  - The user asked for a GPU-0-only loop doing circuit tracing → root cause → steering on tau2. Cron 767c1178 at :13/:43.
  - The parallel M1 session moved to ToolAlignBench on GPU 2 at the user's request. It confirmed no conflict with GPU 0.
    Its rc2 chain was cancelled; the C-LOOP will run the symmetric-contrast M1 rerun on GPU 0 instead.
- 11-24 14:15 (h-04): H1 attention-head trace started (user: "해봐 이걸로 실패 detect될거 같냐?"). GPU 2 (UUID 4c593ff4); the
  M1 session confirmed GPU 2 was free.
  - Script m1/h1_heads.py → probe/m1_heads/full.
  - Units: x15 transfer turns, f_detect unexpected writes, and good writes (up to 150).
  - Teacher-forced at the "=" of "<function=". For each of the 8 full-attention layers × 16 heads it records: attention mass
    over 13 context segments, DLA to the chosen name token (direct and J-lens; mean-centred unembedding, no runner-up
    contrast, so the M1a artifact does not apply), J-lens top-10 tokens, and the top-8 source tokens at L23/L27.
  - Smoke (3 units, all reproduce the logged token): L27h5 gives about 12.5 of the ~21 all-head attention DLA for
    'transfer'. It reads the end of the transfer tool's JSON entry; its J-lens words are ' transfer' / '转移'.
  - Analysis m1/h1_analyze.py (PC, labels as X17 / R3 (C)): pre-specified features of the top transfer head chosen
    without labels, layer totals, CV logistic detectors with within-task permutation null, and the turn-only baseline.
- 11-24 14:2x CORRECTION to the M1 RESULT: the transfer "failure signature" is a contrast artifact.
  - Cause: good T-name units used g = runner-up. For 19/22 legitimate transfers that is ' transfer', a spelling
    variant (103/223 good T-name units overall). Bad transfers used another tool name.
  - m1/m1_recontrast.py (GPU 0, free) → probe/m1/out_recontrast. All 46 transfer T-name units were re-measured with the
    same contrast: g = best alternative tool-name token.
    - L31/1257, L31/2776 and L26/1006 are top-50 in 100 % of bad AND 100 % of good transfers. They write 'transfer';
      they are not failure neurons.
    - L27 attention DLA is larger in good transfers (10.28 vs 7.84; AUC bad>good 0.14), and m is good 19.4 vs bad
      15.8, so bad transfers are less confident.
    - Only weak, in-sample, non-CV differences remain: L31/1826 0.78, L30/1310 0.76, L31/2304 0.74.
  - Also contaminated by the same mismatch: the attention-vs-MLP and formation-layer contrasts in M1a, and M1b good-kept.
    M1b bad-vs-random flips are unaffected.
  - Peer sessions 032533 and cc6da5 have been notified.
  - Coverage of the 43 failed f_detect episodes:
    - 28 have an M1 unit: 19 involve transfers, 6 wrong_args, 7 unexpected_write (overlapping);
    - 13 are missing-write failures, which have no divergent token;
    - 2 bad writes were not captured.
- 11-24 14:2x (h-04): unneeded vs legitimate transfer with J-lens words from EVERY logged position (user: "이전턴의 징조나
  이번턴 모든단어에서 j-lens 단어 본거 맞냐"). mining/transfer_windows.py → transfer_windows.md. CPU only, f_detect, 19 bad vs
  56 good.
  - Windows: prev (3 previous turns, all positions), ctx (this turn's input + decision point), gen (this turn's generated
    preamble before `<tool_call>`), all. Each is compared with surface tokens; null = 100 label permutations.
  - prev: J-lens 0.70-0.73 vs surface 0.73-0.78.
  - ctx: J-lens 0.68-0.74 vs surface 0.62-0.78.
  - So the previous turns and this turn's input give nothing beyond the surface text.
  - gen (the preamble): J-lens 0.77-0.80 (p <= 0.01) vs surface 0.48-0.72.
    - Within domain: J-lens 0.77-0.82 (airline 0.69-0.74, retail 0.73-0.89, telecom 0.86-0.90, where telecom is 1
      scenario) vs surface 0.32-0.70.
    - Preamble length alone 0.656 (within domain 0.696). Length-residualized J-lens 0.74-0.77; a length-free share score
      0.77-0.79.
  - Words in the preamble:
    - Bad: L21 'INCLUDING' / ' включая' / '包括了', L20-21 '姓名', L28 '的人力资源', '不方便' (5-6 of 19).
    - Good: L25-31 '显示' / ' showed' / ' indicates', L21 ' violations', L14 ' recovery' (29-31 of 56).
    - Reading: legitimate transfers cite what a check showed; unneeded ones are list-like summaries of the user's
      requests. This is exploratory, n is small, and several variants were tried.
- 11-24 14:1x (h-04): M1 ↔ J-lens matching (user: "이결과 보고나서 jacobian lens 결과랑 매칭시킬점 하나도 없니"). CPU only.
  - mining/commit_layer.py → commit_layer.md: the J-lens rank of the chosen tool-name token, at the "=" before it, by
    layer (278 f_detect episodes, top-30).
    - In every group the name first becomes top-1 at L23 (median). This matches M1's L23 attention contribution and the
      Aug Drive analysis "tool commit L22-23".
    - It stays top-1 from L29-30. At L27-28 the chosen name is rank 1 (never top-1) in every group: a lens blind spot
      exactly where M1 puts the L27 attention write.
    - Earlier formation in failures, the same direction as M1 (19-21 vs 27):
      - unexpected writes (9) vs good writes (227): enter the top-30 at L18 vs L23, AUC 0.745 [0.59, 0.91]. The tools
        differ, so the tool is not controlled.
      - unneeded vs legitimate transfer (same token 'transfer'): L20 vs L23, AUC 0.60 [0.44, 0.76], n.s.
  - m1/m1_neuron_words.py (server CPU) → probe/baseline_why/m1_neuron_words.json: J-lens readout of the M1 neurons'
    W_down columns.
    - Failure-only transfer neurons:
      - L26/1006 + pole = ' transfer', '转移', ' Transfer', ' transferring' ('transfer' rank 4);
      - L31/1257 − pole = 'trans', ' Trans', 'TRAN';
      - L31/2776 − pole = ' transmettre', ' rejoindre', ' accueillir';
      - L30/1922 + pole = '处理', '管理', ' execution', ' delivery'.
    - L30/856 (T-call exception) = ' let' / 'Let'. L29/121 (wrong_args) = '1', '１', '₁' (digit writer).
    - The shared T-call neurons (L31/844, /66, /4074, L30/1269) read as no interpretable words.
  - Reading:
    - The J-lens names what M1's failure neurons write (transfer / hand-off tokens).
    - Both methods put the readout at L26-31 and the formation upstream: J-lens words L13-20 (X17), residual probe
      L10-18 (R3), M1 causal neurons L6-23.
    - The J-lens misses the L27 attention step, which M1 says carries the failure.
- 11-24 13:52 (M1 session): M1 chain done on GPU 2 (extract 13:04, M1a 13:05, M1b 13:52; GPU 2 now free of M1). Results in
  "M1 RESULT". Added m1a_taskbal.py (task-balanced) after spotting task 21 duplication. Two of ten groups are localized
  (wrong_args:T-name, a single book vs update-flights confusion; unexpected_transfer:T-call with n=10). Transfer T-name has a
  consistent neuron signature but is not ablatable. Summaries copied to m1/. Cron cc12bb76 expired; not recreated.
- 11-24 13:3x (h-04): broad J-lens re-analysis (user: "좀 광범위하게 잡아서 이상한 단어여도 전레이어에서 ... 턴도 실패순간말고 좀
  넓히고"). CPU, PC. Exploratory: several variants were tried, so read the best numbers as optimistic.
  - mining/broad_mine.py → broad_mine.md. 278 f_detect episodes, whole vocabulary, all 32 layers plus an any-layer
    feature, every logged position (context and agent top-30, decision top-100). Task-grouped CV with a surface-token
    baseline.
    - E1 whole episode, 43 failed vs 235 passed: J-lens 0.70-0.74 vs surface 0.64-0.73.
    - E2 the 3 turns before the first bad write, 30 failures vs good writes of the same tools: J-lens 0.70-0.72 vs
      surface 0.69-0.72. Within-tool: J-lens 0.46-0.48, surface 0.47-0.56.
    - E3 the last 3 turns of the 13 failures with no bad write: J-lens 0.70-0.73 vs surface 0.63-0.77.
    - The selected "failure words" are unstable noise (' Monten', 'khusus', ...).
    - Verdict: for failures beyond transfers, nothing beyond surface text, at any layer or position.
  - explore/x17_matched_broad.py → x17_matched_broad.md. R3 (C) rows: bad transfer vs same-task denial, 15 bad (12 tasks)
    vs 26. Data-driven (layer, word) features over the whole vocabulary; null = within-task label permutation.
    - The signal is STRONG: J-lens 0.74-0.85 and J++ 0.75-0.89.
    - Layers 0-20 only: 0.83-0.89. With turn removed: 0.77-0.87.
    - The null has mean about 0.50 and max 0.77-0.85, so p <= 0.01 for most configs. R3 found the a-priori families at
      0.54; the data-driven words catch what the families missed.
    - Lopsided words include L16 ' Customer', L13 ' complaint', L18 ' FINAL', L26 ' goodbye', i.e. escalation /
      hand-off framing.
  - The same broad features on unneeded vs legitimate transfers (x15: 35 bad, 24 tasks, vs 131 good):
    - raw 0.64-0.78 (best J++ L0-20 K10 0.778), against J_pairs 0.679;
    - but turn index alone gives 0.665, and with turn removed the scores fall to 0.65-0.69.
  - Reading: the J-lens clearly shows WHETHER the agent is about to transfer (vs deny). Whether that transfer is unneeded
    is barely visible beyond conversation length. The gate's weak point is unchanged.
- 11-24 12:49 tick (cron session; the 7-day cron cc12bb76 ended with this run):
  - M1 extraction: 240/515 episodes, 356 units (135 bad), 13 missing-write failures counted so far, no tracebacks.
    ETA about 13:15, then the M1a/M1b chain.
  - GPU 2 is ours (M1); GPU 0 has the parallel session's review jobs; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (12:27). Disk 13 GB.
- 11-24 12:5x (h-04 / 설명 기반 실험): R3 done (see REVIEW FOLLOW-UP results). GPU 0 is still running R4 reruns and the R5
  patch smoke.
- 11-24 12:45 (h-04, main conversation): cron 1b1f8ead was still firing here, although the 12:14 entry below records the
  user's "루프 꺼줘". It is now deleted with CronDelete (only this session could remove it).
  - GPU 0 runs the parallel session's review queue: running R4 C0_r2, R4 P1_r2, R3 denial; 7 pending (R5 patch,
    R4 reruns).
  - GPU 2 is busy (13.5 GB, M1). Disk 13 GB.
  - h-04 queues nothing and touches none of it.
- 11-24 12:5x (h-04): baseline failure investigation (user: "baseline으로 돌아가서 이것들이 실패한 원인에 대해 조사해봐 그떄
  결과들 전부보고"). CPU only, no GPU. Full write-up: baseline_why/summary.md (+ report.md, report_extra.md).
  - The intended effect is absent:
    - bad-write share 0.29 (reference) vs 0.31-0.35 (baselines);
    - unneeded transfers 22 vs 20-23;
    - verify-first replies unchanged.
  - Always-on edits change every eval episode, mostly from agent turn 0.
  - Airline: inside the rerun noise. Unsteered rerun net −4; baselines −1 to +1.
  - Retail: systematic shared harm.
    - Unsteered rerun breaks 7 % of passing tasks; the baselines break 15-29 %.
    - The same tasks break across methods: 8 broken by ≥ 3 methods vs 0.93 expected (p < 1e-4).
    - Method-method overlap 3-7 vs method-rerun 0-2.
  - The fit data explain the shared direction. 56 examples:
    - 61 % of positives are one canned verify sentence;
    - 46 % of negatives are transfers;
    - 20 % come from task 21;
    - the user sims differ from the evaluation.
  - TRAIN selection was noise (+3, p ≥ 0.38, best of 18 options).
- 11-24 12:35 M1 running on GPU 2.
  - Smoke 8 units OK: sum of DLA = m, e.g. 17.62 vs 17.48.
  - Two fixes were needed for gradients: Qwen3.5 linear attention has no backward for 1-token cached steps, so the grad
    step uses the last 4 tokens (chunk kernel), with the initial recurrent state cloned.
  - Restarted 12:32 with resume + faster neuron DLA (33 units kept). Rate about 5 s per episode; extraction ETA
    about 13:20.
  - Chain armed (after_m1.sh): M1a analysis (CPU), then M1b ablation (GPU 2), ETA about 14:10.
- 11-24 12:4x M1 pre-registered (section above), after the user's objection: the detector work covered only the 19
  transfer failures, and the exploration drifted into prompt interventions. M1 localizes every failure type by
  layer and neuron on GPU 2.
- 11-24 12:2x (h-04): coordination with the session "설명 기반 실험", which runs the user's REVIEW FOLLOW-UP R1-R6 on
  the same GPU-0 queue.
  - The detector question is folded into its R2 (cluster bootstrap, done) and R3 (situation-matched comparison, which
    uses out/x15 read-only).
  - x16_detector.py stays unrun. h-04 does not edit stage2b_regen.py and queues nothing.
  - R2 (reported by that session): stage-0 AUC 0.763.
    - 95 % cluster CI 0.62-0.88; 0.57-0.87 with telecom counted as one cluster.
    - Airline only: 0.68.
- 11-24 12:2x J++ check (user: "J++, ICA lens로도 안 잡히냐"). mining/checks_jpp.py → checks_jpp.md. CPU, same folds and labels
  as checks.py, 278 f_detect episodes. The J++ cache was aligned with cache_dec.npy (asserted).
  - Non-transfer bad writes (21: wrong_args + unexpected_write) vs 227 good. Tool-only baseline 0.82.
    | lens | AUC | within-tool AUC |
    |---|---|---|
    | J-lens | 0.68 | 0.46 |
    | J++ | 0.61 | 0.42 |
    | J-lens + J++ | 0.64 | 0.47 |
    J++ does not catch them either.
  - Transfer-only (19 bad vs 22 good): J-lens 0.90, J++ 0.88, both 0.89.
  - ICA lens: no implementation or artifact exists in tau2-steer, probe/ or the local work dirs. Asked the user which one
    is meant.
- 11-24 12:14 (h-04): the user said "루프 꺼줘", so the session cron loop 1b1f8ead is cancelled. The GPU-0 queue runner
  stays up, idle.
  - X15 extraction is DONE (12:10): 515 unsteered episodes, 166 transfer turns, in out/x15.
  - The user also pasted a critique and plan:
    - power;
    - C0 noise floor;
    - effective n about 15;
    - the detector may read the "refusal situation";
    - attention / patching not examined;
    - blind re-judging.
  - The user asked to implement it on GPU 0, then interrupted. Waiting for confirmation of scope; the proposal is
    items 1 (power) and 4 (situation-matched comparison) first.
- 11-24 11:49 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (11:27). Disk 15 GB.
  - Waiting for the user's direction.
- 11-24 11:19 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (10:56). Disk 15 GB.
  - Waiting for the user's direction.
- 11-24 10:49 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (10:26). Disk 16 GB.
  - Waiting for the user's direction.
- 11-24 10:19 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (09:56). Disk 16 GB.
  - Waiting for the user's direction.
- 11-24 09:49 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (09:26). Disk 16 GB.
  - Waiting for the user's direction.
- 11-24 09:19 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (08:56). Disk 16 GB.
  - Waiting for the user's direction.
- 11-24 08:49 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (08:26). Disk 16 GB.
  - Waiting for the user's direction.
- 11-24 08:19 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (07:55). Disk 16 GB.
  - Waiting for the user's direction.
- 11-24 07:49 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (07:25). Disk 16 GB.
  - Waiting for the user's direction.
- 11-24 07:19 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (06:55). Disk 16 GB.
  - Waiting for the user's direction.
- 11-24 06:49 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (06:25). Disk 16 GB.
  - Waiting for the user's direction.
- 11-24 06:19 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (05:55). Disk 16 GB.
  - Waiting for the user's direction.
- 11-24 05:49 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (05:25). Disk 17 GB.
  - Waiting for the user's direction.
- 11-24 05:19 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (04:54). Disk 17 GB.
  - Waiting for the user's direction.
- 11-24 04:49 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (04:24). Disk 17 GB.
  - Waiting for the user's direction.
- 11-24 04:19 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (03:54). Disk 17 GB.
  - Waiting for the user's direction.
- 11-24 03:49 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (03:24). Disk 17 GB.
  - Waiting for the user's direction.
- 11-24 03:19 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (02:54). Disk 17 GB.
  - Waiting for the user's direction.
- 11-24 02:49 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (02:24). Disk 17 GB.
  - Waiting for the user's direction.
- 11-24 02:19 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (01:54). Disk 17 GB.
  - Waiting for the user's direction.
- 11-24 01:49 tick (cron session): idle; no change.
  - GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy 0 calls. Push loop OK (01:23). Disk 17 GB.
  - Waiting for the user's direction.
- 11-24 01:19 tick (cron session):
  - Idle: no jobs of ours. GPU 0 and 2 are free; GPU 5 has the root vLLM.
  - Proxy v5: 0 calls, 0 errors. Tunnel up; push loop alive (00:53). Disk 17 GB.
  - Waiting for the user's choice of the next direction after the J-Cascade exploration (23:44). No action.
- 11-23 23:44 (h-04): exploration finished. The queue is empty, and GPU 0 is idle (no processes of ours).
  - P1PF_self (clarified reminder + "can I handle this myself" opening):
    - bad 5/19, sign p 0.031 vs C0; rescored 32 %; telecom 4/5, retail 1/4, airline 0/10;
    - good kept 62 %, degenerate 17 %;
    - gated: bad 21 %, good kept 82 %.
  - P1PF_deny: bad 2/19 (rescored 42 %), good kept 57 %.
  - The airline / retail script still holds. All exploration rows and logs are on the PC
    (jcascade/out/explore, out/stage2b, logs; md5 ok). Waiting for the user's choice of the next direction (see
    EXPLORATION X RESULT).
- 11-23 22:44 tick (h-04).
  - MID final: bad 4/19 (telecom 4/5, airline 0/10), good kept 73 %, degenerate 16 %.
  - PF_self ("…whether this is something I can handle myself"): bad 4/19 (telecom 4/5), good kept 82 %.
  - PF_denyhelp: bad 4/19 (airline 2/10, telecom 2/5), rescored 26 %, but good kept 50 %.
  - PF_alt: bad 2/19, good kept 68 %.
  - P1, partial (27 rows): airline 1/10, rescored 20 %, good kept 53 % so far.
  - Running: PF_clarify, P1, MID2. The queue empties at about 23:20.
- 11-23 22:2x (h-04).
  - S07a-d, 4 samples:
    - bad: 15/19 rows transfer in all 4 samples, and only 2/19 convert in any sample;
    - good: 16/56 convert in some sample.
    - The unneeded transfers are MORE deterministic than the legitimate ones.
  - MID (74/75 rows): injected on all 19 bad rows. Telecom bad converted 4/5, airline 0/10. Airline texts after the
    injection say, for example, "the user is asking for something that's against policy, and I cannot do that", and then
    transfer anyway.
  - Hypothesis (from TM, MID, sampling and the C0 texts): the agent maps "the policy forbids X" to "the request cannot be
    handled within the scope of my actions", which the policy's own sentence turns into "transfer". It is a semantic
    reading of the policy, not a tool reflex.
  - Test queued (50, 51; exploratory), with a reminder text that resolves the ambiguity: "a request the policy does not
    allow is still within your scope: deny it; do not transfer just because the policy does not allow it".
    - P1: the clarifying system reminder before the turn (compare with P0, which repeated the ambiguous sentence).
    - MID2: the same clarification injected at the transfer call (compare with MID).
  - If P1 / MID2 move the airline turns, the candidate method for a pre-registered test is: J-lens gate → inject the
    clarification on flagged turns.
- 11-23 21:44 tick (h-04).
  - TM (tool-call token banned):
    - bad: 15 verbal transfer, 2 text, 2 degenerate;
    - good: 48 verbal transfer.
    - With the tool unavailable, the agent still writes "I'll now transfer you … YOU ARE BEING TRANSFERRED TO A HUMAN
      AGENT. PLEASE HOLD ON." The transfer intention is fully intact; it is a script, not a tool reflex.
  - S07a / S07b (sampled, T 0.7): bad 1/19 each. Only 2/19 bad rows convert in either of the two samples.
    - The model's own distribution rarely contains a non-transfer continuation. A J-lens-scored reranker over
      samples would have little to choose from (S07c/d will give the 4-sample count).
  - Running: S07c, S07d, MID. Pending: PF_alt, PF_self, PF_denyhelp, PF_clarify. ETA about 23:00.
- 11-23 21:14 tick (h-04).
  - O_policy (the policy's transfer sentence removed): bad 0/19, good kept 77 %.
  - TH_pc (thinking that starts with a policy check): bad 1/19 (retail), good kept 77 %.
  - PF_neutral ("Thank you for your patience."): bad 2/19 (telecom), good kept 75 %.
  - Telecom bad turns flip with almost any opening that delays the decision. Airline turns move only under PF_help
    (2/10), TH_free (1/10), O_userhuman (1/10) and N20 (1/10).
  - Running: S07a, TM, S07b. Pending 7. ETA about 23:00.
- 11-23 20:14 tick (h-04).
  - N20 (natural DoM, 0.2 x |h|): bad 3/19, but good kept 39 % and degenerate 20 %, so it is too strong.
  - PF_help ("I can help you with that."): bad 4/19 (airline 2/10, telecom 2/5), good kept 71 %. It is the first lever
    to move airline turns.
  - B05: 0/19, good kept 84 %.
  - Since openings are where airline turns start to move, 4 more opening variants are queued (46-49): PF_alt,
    PF_self, PF_denyhelp, PF_clarify.
  - Queue: 12 pending + 3 running (RB1, RN20, O_policy). ETA about 23:00.
- 11-23 19:44 tick (h-04).
  - O_desc (the whole "Only transfer if ..." clause removed from the tool description): bad 0/19, good kept 79 %. The
    tool description does not drive the unneeded transfers either.
  - N10 (natural denial-vs-transfer DoM, 0.1 x |h|): bad 1/19, good kept 68 %.
  - MID smoke OK: the injection fires at the transfer call on 3 of 4 rows.
  - Queue: 11 pending + 3 running (B05, N20, PF_help). ETA about 22:00.
- 11-23 19:2x (h-04) tick.
  - TH_free done: bad converted 3/19 (airline 1, telecom 2), good kept 73 %.
  - RA20 done: 0/19, good kept 88 %. So A20's good-transfer loss is specific to the attribution neurons.
  - Added MID: when the agent is about to call transfer_to_human_agents (a greedy lookahead after `<tool_call>`), one
    policy-recall sentence is injected into the agent's own text, and generation continues. This targets the
    "deny then escalate" moment directly. Smoke 29b and full run 45 are queued.
  - Queue: 14 pending + 3 running. ETA about 22:00.
- 11-23 18:5x (h-04): exploration results plus a scoring caveat.
  - Caveat: classify() labels any text with "human agent" as verbal_transfer, including "I cannot transfer you to a
    human agent until ...".
    - explore_summary.py adds a negation-aware rescoring column (exploratory; the pre-registered stage-2 / 2b scoring
      is unchanged): a verbal transfer counts only if some sentence affirms a transfer without a negation, "only",
      "until", "unless" or "before" attached to it.
  - Bad converted, original / rescored:
    - PF_deny ("I'm sorry, but according to our policy,"): 0 % / 32 %, good kept 80 %. All 5 telecom bad turns now keep
      troubleshooting ("policy says I must try all steps first"). Airline / retail still deny and then transfer anyway.
    - PF_pc: 16 % / 21 %, good kept 75 %.
    - P0: 5 % / 16 %, good kept 80 %.
    - O_userhuman: 16 % / 16 %, good kept 59 %.
    - TH_free (29 rows so far): 10 %, good kept 53 %.
    - B1, O_ask, A20, A100, RA100: 0-5 %.
  - RA100 control: good kept 80 %. So A100's good-transfer loss (27 % kept) comes from those neurons specifically,
    not from ablating 2,000 neurons in general.
  - Reading:
    - The airline/retail "deny then escalate" script survives every lever so far.
    - Telecom bad turns (one MMS task) flip when the opening invokes the policy.
- 11-23 18:2x (h-04): more exploration results.
  - O_userhuman (the user's sentences asking for a human / escalation removed; 43/75 prompts changed):
    - bad converted 3/19 (telecom 2/5, airline 1/10);
    - good kept 59 % (16 lost).
    - User requests drive the legitimate transfers more than the unneeded ones, so this does not separate the two.
  - PF_pc (forced opening "Let me first check what the policy says about this request."):
    - bad converted 3/19 (telecom 3/5);
    - good kept 75 % (9 lost). Best lever so far, but small.
  - B1 (paired DoM, 1x): bad converted 0/19, good kept 88 %.
  - Reading of the 19 bad C0 texts:
    - Airline/retail (14): mostly "the policy forbids X → transfer". The agent states the denial correctly, then hands
      off. Some are auth / missing info, and 2 are user-urged.
    - Telecom (5): all one MMS-roaming task, where the agent gives up troubleshooting early.
  - natdom v2: 30 denial turns (17 / 13 per fold); fold cosine 0.55-0.63; examples look like real denials.
  - New diagnostics queued (40-44):
    - S07a-d: 4 sampled continuations (T 0.7, top-p 0.95). Does the model's own distribution contain non-transfer
      continuations? This is a precondition for J-lens-scored reranking.
    - TM: the tool-call token is banned. What does the agent do when it cannot transfer: deny properly, or a verbal
      transfer?
- 11-23 17:50 (h-04): exploration results so far (explore/explore_summary.md).
  - O_ask, i.e. the transfer tool description without "the user explicitly asks for a human agent": bad converted 0/19,
    good kept 80 %. That clause is not what drives the unneeded transfers.
  - A20 / A100, mean ablation of the attribution neurons:
    - bad converted 0/19 / 1/19;
    - good kept 50 % / 27 % (C0 86 %).
  - The ablation mostly turns tool calls into a verbal transfer that never calls the tool:
    - good A20: 28 transfer, 14 verbal; A100: 15 transfer, 14 verbal;
    - bad A20: 15 transfer, 3 verbal.
  - Reading: these neurons carry the act of calling the tool, not the decision. The unneeded transfers are the MORE
    robust ones, so this lever pushes the wrong way.
  - X8: natdom v1 used a regex that matched non-denial turns ("successfully booked" etc.). v1 is archived
    (out/explore/archive/natdom_v1_loose.*). v2 is queued with a strict filter: a denial phrase within the first 400
    characters and no completion phrases. The N jobs wait for v2.
- 11-23 17:14 tick (h-04): the exploration smoke passed for all 4 configs. The thinking block closes and the outcome is
  parsed from the text after `</think>`.
  - Queue OK, no failures. Running: A100 (62/75), A20 (43/75) and O_ask (10/75). GPU 0 has only our 3 jobs. Disk 17 GB.
- 11-23 17:0x (h-04), EXPLORATION started (see the EXPLORATION X section).
  - Queue: jc_queue.sh runs 3 jobs on GPU 0. Running now: A100, A20 and the exploration smoke. 19 jobs pending,
    exploration interleaved with the 2b controls:
    - X2: O_ask, O_userhuman, O_desc, O_policy;
    - X3: PF_pc, PF_deny, PF_help, PF_neutral;
    - X9: TH_free, TH_pc (thinking on, max 2048);
    - X8: natdom prep, N10, N20, RN20;
    - 2b: B1, RA100, RA20, B05, RB1.
  - ETA for the queue: about 20:45. Follow-ups until 24:00 depend on those results.
  - P0 final (75/75): bad converted 1/19, good kept 80 % (C0 86 %), 10 good transfers lost. The faithful policy reminder
    does not fix unneeded transfers.
  - Gate (J_pairs out-of-fold, threshold from the other fold): flags 13/19 bad and 12/56 good.
  - X1 (CPU) result: transfer words almost never enter the J-lens top-100 at earlier decision points (mean 0.00 layers
    at lag >= 1). At the transfer turn they appear in late layers only (mostly L27-31, about 1 layer on average).
    The transfer intention has no J-lens precursor in the previous turns, so the decision forms at the turn itself,
    from its latest input.
  - X6 (CPU) result: a decision-point neuron-activation detector reaches AUC 0.79 (best of 6 tries, optimistic),
    against J_pairs 0.763. The combination gives 0.79. Attribution-based features stay <= 0.62. The gate is near its
    ceiling with these features.
- 11-23 16:44 (h-04): stage 2b prep DONE on all 75 rows.
  - Necessity, change in summed transfer log p:
    - A5 -1.7, A20 -5.2, A100 -13.7;
    - AG20 -0.06;
    - RA20 0.000, RA100 +0.002.
  - The tool-name token stays top-1 on 75/75 under every set, A100 (2,000 neurons) included. The causal neurons are
    real, but at this turn they do not flip the decision.
  - Early P0 (57/75 rows): the faithful policy reminder converts 1/18 bad turns (13 transfer, 2 verbal, 2 degenerate).
  - Reading: the decision looks fixed before the transfer turn. The user asked whether designing so many configs helps
    ("실험설계 많이해서 되냐"). Answer: no more configs at this turn.
- 11-23 16:3x (h-04): stage 2b smoke OK on the 2nd try. The 1st try failed in backward because the linear-attention
  cache overwrote its saved state in place; fixed by assigning instead of copying during the grad pass only.
  - Smoke prep, 4 rows: give-up readout neurons per layer L20 115 ... L26 25.
  - Paired-DoM norm 3-6 against residual norm 18-33.
  - Necessity, change in summed transfer log p: A5 -2.6, A20 -5.6, AG20 +0.02, RA20 +0.01. The tool-name token stays
    top-1 on 4/4.
  - Smoke gen: B3 degenerate 4/4, A20 still transfers 4/4, P0 2 transfers + 2 degenerate (a long cancellation turn).
    A 4-row smoke is not the evaluation.
  - AMENDMENT added (see the STAGE 2b section). Full run started on GPU 0 after the user said "gpu 0이 ㅈㄴ 노는데":
    - lane 1: prep, then A100, RA100, A5, AG20;
    - lane 2: C0, A20, RA20, B05, B1;
    - lane 3: P0, B3, B8, RB1, RB8.
  - 3 processes, 28 GB, 100 %. ETA about 19:15.
- 11-23 15:44 tick (h-04): idle. GPU 0 is empty (no jobs from anyone) and the disk has 18 GB free. The next step is
  waiting for the user to choose (a), (b) or (c).
- 11-23 15:3x (h-04): the stage-1 npz are now on the PC in jcascade/out/neurons (278 files, 2.0 GB, md5 re-verified
  278/278). The server copies are deleted. Disk 19 GB free.
- 11-23 15:25 (h-04): STAGE2_ALL_DONE at 15:21:57. The verdict is FAIL for every config (see the STAGE 2 RESULT
  section).
  - stage2/, the smoke dirs and logs/ are on the PC (md5 ok, 31 files).
  - The stage-1 npz (2.0 GB, 278 files) are being copied to the PC. The server copy is deleted only after md5 matches.
  - GPU 0 is now free of our processes. Stage 3 is not started. The next step waits for the user: (a), (b) or (c).
- 11-23 15:14 tick (h-04):
  - Shards s1 and s2 are done (15:00 and 15:02). Every steered config is complete, and every one converts 0/19 bad turns.
    - Good kept: S7 77 %, S47 80 %.
    - Random control R1: 0/19 converted, good kept 82 %.
  - Only R47, the random control on s0, is left: 48 of 75 rows, done about 15:25.
  - The verdict is already fixed: no config passes, because conversion is 0 % against the 40 % gate.
  - C0 still calls the transfer tool on 64/75 turns.
  - GPU 0 runs 1 of our processes. Disk 17 GB.
- 11-23 14:44 tick (h-04):
  - Stage 2 is at 544 of 750 rows, with no errors. GPU 0 runs only our 3 processes. Disk 17 GB.
  - S4, S5 and S6 are complete, and all convert 0/19.
    - Good kept: S4 84 %, S5 80 %, S6 84 %.
    - Degenerate: 1-3 %.
  - So all six complete steered configs (S1-S6) FAIL the pre-registered gate on conversion.
  - Partial runs also convert 0 so far: S7 (10 bad rows), S47 (12) and R1 (10).
  - ETA: s1 and s2 about 15:05, s0 (S7 then R47) about 15:35.
- 11-23 14:14 tick (h-04):
  - Stage 2 is at 329 of 750 rows, with no errors. The three processes on GPU 0 are ours (12.8 GB each). Disk 17 GB.
  - Each config takes about 32 min. ETA: s1 and s2 about 15:05, s0 about 15:35.
  - C0, S1 and S2 are complete:
    - bad converted 0/19 in all three; C0 itself transfers 18/19.
    - good kept: C0 82 %, S1 86 %, S2 88 %.
    - degenerate: C0 4 %, S1 0 %, S2 4 %.
  - S1 and S2 therefore FAIL the pre-registered gate, on conversion.
  - Partial S4 (14 bad rows), S5 (12) and S6 (11) also convert 0.
  - Scratch summary only; the official summary comes after the full pull.
- 11-23 13:47 tick (h-04):
  - Stage 1b DONE 13:16. neuron_map.{json,md} are on the PC in jcascade/out/ (md5 ok). The stage-1 npz stays on the
    server until stage 2 ends.
  - Decision point: 196 poles at p < 0.001, against a label-permutation null with mean 25.05 and max 81.
  - Tool-name point: 150 poles, against a null with mean 18.5 and max 92.
  - The 19 bad rows come from 19 distinct tasks, so task clustering does not inflate these counts. The permutation is
    within domain.
  - Reading: the top poles separate bad from good, but their J-lens words are mostly not give-up words. Of the top 60
    at the decision point, 59 have no family; at the tool-name point, 57 of 60 have none. eff_transfer > 0 for about half
    of them, so there is no sign bias either.
  - Readable exceptions:
    - L28 N6241+ ("算了 / 好了 / whatever"), tool-name point, bad 8/19 vs good 2/56.
    - L16 N3251+ ("rather / instead"), tool-name point, 7/19 vs 0/56.
    - L19 N381− ("again"), decision point, 9/19 vs 2/56.
  - Stage 2 is running on GPU 0, split by config:
    - s0: C0, S4, S7, R47;
    - s1: S1, S5, S47;
    - s2: S2, S6, R1.
  - At 13:47, 140 of 750 rows are done (about 2.4 rows/min per shard). ETA: s1 and s2 about 15:00, s0 about 15:30.
- 11-23 13:19 tick (cron session):
  - Stage 1b finished with ALL_DONE at 13:16. Stage 2 then chained automatically: 3 stage2_regen.py shards started
    13:17-13:18 on GPU 0 and are loading.
  - Proxy v5 (restarted 12:49) has 0 calls, 0 errors. Tunnel up; push loop alive (12:49).
  - GPU 2 is idle; GPU 5 has the root vLLM. Disk 18 GB.
- 11-23 13:14 tick:
  - Stage 1a DONE 13:12: 278/278 episodes, 3 shards of about 37 min each, no errors.
  - Stage 1b (stage1_analyze.py) is running its CPU phase (per-neuron percentiles over 4.5k decision points, 9.6 GB RSS).
  - run_stage2.sh is waiting for ALL_DONE. GPU 0 is idle meanwhile. Disk 18 GB free.
- 11-23 13:04 tick: stage 1a 222/278, no errors.
  - GPU 0 runs 4 of our processes (3 shards + the smoke's last config), 39 GB, 100 %. Disk 18 GB free.
  - ETA: stage 1a about 13:20, stage 1b about 13:35, then stage 2 starts automatically (run_stage2.sh).
- 11-23 13:0x Stage 2 AMENDMENT before any real stage-2 run:
  - The smoke (2 turns × C0/S1/S47/R47, partial stage-1 stats) ran end to end: about 25-75 s/turn with 4 processes on GPU 0.
  - It showed that the transfer call comes after a 200-400-token preamble. So the first-48-token window never reached the
    decision; the texts start identically.
  - Fix: interventions now apply at the decision point plus every generated token of the turn (JC_KPOS default = 768).
    The ops stay sparse (16-32 poles).
  - The k48 smoke is kept as out/stage2_smoke_k48. A second smoke with the full window is running.
- 11-23 12:50 tick (cron session):
  - FIX: the PC Haiku proxy, the reverse tunnel and the push loop had all been down since the 11-20 ~17:5x SSH outage.
    Restarted:
    - proxy v5 pid 25544 (counters reset);
    - tunnel pid 13888;
    - loop pid 14732 (no new block, 71 complete).
    Server health is OK. Logged in changes.md.
  - J-Cascade stage 1 (parallel session, GPU 0 only): shards s0-s2 at 47/93, 42/93 and 45/92, about 45 s per episode.
    ETA about 13:30, then stage 2 chains automatically.
  - GPU 2 is idle; GPU 5 has the root vLLM (another user). Disk 19 GB.
- 11-23 12:5x Stage 2 code written and pre-registered (section above). Stage 2 chains automatically after stage 1. User
  allows deleting the LJW VLM caches if the disk is short.
- 11-23 12:33 STAGE 1 REDO on project-b GPU 0 only.
  - User: "gpu 0 비어있는데 거기서만 실험 ㄱㄱ". This overrides the old GPU 2/5 rule for this work. GPU 0 = A6000 c27bc2d7,
    which was empty.
  - Setup: probe/jcascade (inputs uploaded, md5 checked); run_all.sh starts 3 stage1_replay.py shards (bf16, power-of-two
    chunks, UUID guard) and then stage1_analyze.py.
  - Throughput: 20 episodes in 3.5 min. ETA stage 1a about 13:40, analysis about 14:00.
  - After that: pull out/ to the PC, delete the server copy.
  - User also asked whether the steering check is part of the remaining work. Yes:
    - stage 2 = offline regeneration with S1-S8 + random-neuron control (first steering test);
    - stage 3 = paired episodes.
    Stage 1 only finds the targets.
- 11-23 12:3x The vast box is gone: ports 52392 and ssh5:19225 refuse.
  - The stage 1a/1b outputs were never pulled, so they are LOST. Stage 1 must be redone on a new instance.
  - Inputs and scripts are saved permanently in work/tau2-research/jcascade/: vast_setup.sh, jc_export.tgz (md5 5670bb31),
    stage1_replay.py (fp16 + power-of-two chunks), stage1_analyze.py.
  - Labels and vocab are in mining/.
  - redo_on_vast.sh <port> <host> uploads everything, sets up the env, runs every GPU, then the analysis (logs/stage1b.log
    ALL_DONE).
  - Lesson: on a non-volume vast box, pull results as soon as they finish.
  - Remaining experiments told to the user: J-Cascade stages 1 (redo), 2 (offline regeneration S1-S8 + random-neuron
    control), 3 (paired episodes ×3 seeds + random-neuron control), then the test-split confirmation.
  - Optional and not approved: random-direction control + multi-seed for the baselines; the refuel_data 2 vs 2.0 label check;
    the write-up update.
- 11-20 17:44 (user: "is all the code on the vast GPU? can I work from another computer?"):
  - The box's /workspace is NOT a persistent volume (workspace_is_volume false); results get pulled to the PC.
  - Copied PLAN.md, WRITEUP_draft.md, mining/*.py and the mining reports to /workspace/jc/code (+ README.md).
  - The 3.5 GB top-k data stays on the PC only, and the mining scripts still carry Windows paths.
  - Box access works from any machine whose SSH key is in the vast account (5 keys installed).
  - Stage 1a was at 157/278 at 17:42.
- 11-20 17:16 tick:
  - Vast stage 1a: 15/278 episodes, both GPUs busy, box disk 49 GB free.
  - project-b: idle, 25 GB free. Proxy $18.68, 0 errors. Push loop OK (16:58).
- 11-20 17:2x STAGE 1 on the vast box (ssh <vast-box>, key auth; work dir /workspace/jc, logs in logs/).
  - Env: venv with the same versions as project-b (torch 2.8.0+cu128, transformers 5.20.2, fla 0.3.2, triton 3.4.0).
  - Models: Qwen3.5-4B @851bf6e and the J-lens n1000 @a4114d7 from HF.
  - Inputs: the f_detect token sequences (278 episodes, delta-coded, 3.8 MB) plus the jlens / jlens_causal packages, relayed
    project-b → PC → box (md5 checked; the server temp copy was deleted).
  - Speed on the 2080 Ti (sm75):
    - bf16 2.6 s and fp16 1.0 s per 2048 tokens; fp32 is unsupported by the fla GatedDeltaNet kernel.
    - A first bf16 run took 528 s/episode, because the triton kernels recompiled for every new chunk length.
    - Fix: feed power-of-two pieces and use fp16. Now about 20-50 s/episode.
    - fp16 on one episode: no NaN, |a| max 20.
  - stage1_replay.py runs on both GPUs (JC_SHARD 0/2, 1/2). Per turn it saves the decision-point act = silu(gate)·up at L12-31
    (fp16), plus gate/up for write turns and act/gate/up at the tool-name point for transfer turns → out/neurons/*.npz.
    ETA about 18:45 KST.
  - after_1a.sh then runs stage1_analyze.py on GPU 0, writing out/neuron_map.{json,md}:
    - per-pole firing (beyond p97 / p3 of all 4.5k decision points) for bad vs good transfers at both points;
    - Fisher p plus a label-permutation null;
    - J-lens readout of each pole's write direction with word families;
    - direct effect on the transfer-name token and on <tool_call>;
    - retry-family and bipolar (give-up vs go) poles.
- 11-20 16:5x J-CASCADE GO (user: "not GPUs 2/5; run it on the vast box", ssh <vast-box> or <vast-host>, key
  auth).
  - Box: 2× RTX 2080 Ti 22 GB, 65 GB disk, 64 CPU, 125 GB RAM; /workspace may not persist, so results go to the PC.
  - STAGE 0 (PC CPU, mining/stage0.py → stage0.md), transfer decisions only.
    - Labels: unneeded transfer in a failed episode 19 (airline 10, retail 4, telecom 5) vs transfer in a passed episode 56.
    - Results:

      | Score | AUC | CI |
      |---|---|---|
      | J_pairs (data-driven layer-word pairs selected inside the training folds) | 0.763 | [0.63, 0.87] |
      | J_cascade (a-priori 5-layer) | 0.664 | [0.51, 0.81] |
      | Best baseline: user asked for a human | 0.655 | |
      | Relative turn position | 0.61 | |
      | Prior tool errors | 0.49 | |
      | Domain | 0.43 | |
      | Logistic on all baselines | 0.48 | |

    - PRE-REGISTERED PASS: J_pairs ≥ 0.75 and +0.11 over the best baseline. Caveats: n = 19 bad, telecom carries much of it.
  - Per-layer medians (rank of the family word, bad vs good):

    | Layer | Family | Bad | Good | Reading |
    |---|---|---|---|---|
    | L20 | inability | 7 | 16 | discriminative |
    | L22 | apology | 2 | 2 | not discriminative (multiplexing: the same apology in both) |
    | L24 | understanding | 1 | 10 | strongly discriminative |
    | L26 | acknowledgement | 82 | 101 | weakly discriminative |
    | L29 | justification "Given / Based" | 38 | 16 | reversed: more in legitimate transfers |

  - So the refined detector layers are L20 / L24 / L26 (+ the data-driven pairs). Apology and justification are dropped as
    anomaly signs.
  - Next: stage 1 neuron map on the vast box. Set up the venv, Qwen3.5-4B, the J-lens file and the f_detect token sequences
    relayed project-b → PC → box.
- 11-20 16:19 tick (h-04):
  - No tau2 workers. GPU 2 (22.5 GB) and GPU 5 (44.8 GB) are still held by other users.
  - Proxy $18.68, 0 errors. Push loop OK (15:57). Disk 26 GB.
  - Awaiting the user's GO on J-Cascade stage 0.
- 11-20 15:49 tick (h-04):
  - No tau2 workers. GPU 2 (22.5 GB) and GPU 5 (44.8 GB) are still held by other users.
  - Proxy $18.68, 0 errors. Push loop OK (15:27). Disk 26 GB.
  - Awaiting the user's GO on J-Cascade stage 0.
- 11-20 15:19 tick (h-04):
  - No tau2 workers. GPU 2 (22.5 GB) and GPU 5 (44.8 GB) are still held by other users.
  - Proxy $18.68, 0 errors. Push loop OK (14:57). Disk 26 GB.
  - Awaiting the user's GO on J-Cascade stage 0.
- 11-20 14:49 tick (h-04):
  - No tau2 workers. GPU 2 (22.5 GB) and GPU 5 (44.8 GB, now 0 % util) are still held by other users.
  - Proxy $18.68, 0 errors. Push loop OK (14:27). Disk 26 GB.
  - Awaiting the user's GO on J-Cascade stage 0.
- 11-20 14:19 tick (h-04):
  - No tau2 workers. GPU 2 (22.5 GB) and GPU 5 (44.8 GB) are still used by other users.
  - Proxy $18.68, 0 errors. Push loop OK (13:57). Disk 24 GB.
  - Awaiting the user's GO on J-Cascade stage 0.
- 11-20 13:49 tick (h-04): neuron-level steering design sent to the user (13:3x); awaiting GO. Nothing run.
  - Ops: no tau2 workers. GPU 2 (22.5 GB) and GPU 5 (44.8 GB) are in use by other users, so stage 1 has no GPU room yet.
    Proxy $18.68, 0 errors. Push loop OK (13:27). Disk 26 GB.
  - User request (13:2x): design a J-lens method with a ~5-layer anomaly check plus steering, using everything so far and
    the Goodfire "Neurons as an Interpretable Basis" ideas (sparse strong-firing neurons, poles, gate vs up,
    multiplexing via primers/readers).
  - Design, "J-Cascade":
    - Model facts: Qwen3.5-4B MLPs are dense SwiGLU (silu), 32 layers × 9,216 neurons, hidden 2,560; 24 linear-attention +
      8 full-attention layers.
    - Detector (J-lens words, the user's requirement), on transfer turns only, a 5-layer cascade:
      L20 inability (我无法 / Unable) → L22 apology (apologize / 抱歉) → L24 understanding (理解 / understand) →
      L26 acknowledgement (acknowledge / sincerely) → L29 justification (Given / Based).
    - Steering on sparse neuron poles (≤ 8-32), pole-specific, values kept inside the observed range (mean to p99), only
      at the gated turn's decision point and first tokens, and always against a random-neuron control. Options:
      - S1 mean-clamp the writer poles;
      - S2 close their gate;
      - S3 cut the L12-19 primers that make readers read the apology as escalation;
      - S4 block the L27-31 readers that push <tool_call> → transfer;
      - S5 flip bipolar poles;
      - S6 transplant natural values from a matched "continue" turn;
      - S7 raise "retry / alternative" neurons up to their p99;
      - S8 mode-gate any of these with input-fingerprint mode ID.
      - Recommended: S4 + S7 + S8, then S6, with S1/S2 as baselines.
    - Rationale:
      - residual-direction edits behave like random directions (weak = reword, strong = degenerate);
      - the "Actually, wait, re-check" loops match the paper's weak-activation (Q3) ablation symptom;
      - multiplexing explains why the apology concept appears in legitimate and unneeded transfers alike.
  - Stages:
    - 0: detector CV inside transfers vs simple baselines (CPU).
    - 1: neuron map (gate/up/out at L12-31 on transfer + write turns; GPU 10-12 GB, about 1 h).
    - 2: offline regeneration per option (pass: convert ≥ 40 % unneeded, keep ≥ 80 % legitimate, degenerate ≤ 5 %,
      beat the random-neuron control).
    - 3: paired episodes ×3 seeds with a random-neuron control.
- 11-20 13:19 tick (h-04):
  - No tau2 workers. GPU 2 (22.5 GB) and GPU 5 (44.8 GB) are used by other users; untouched.
  - Proxy $18.68, 0 errors. Push loop OK (12:56). Disk 26 GB.
  - Waiting for the user's GO on the transfer-only analysis.
- 11-20 12:51 tick (h-04):
  - No tau2 workers. GPU 2 now 21 GB / 100 % and GPU 5 44.8 GB, both other users' jobs, untouched.
  - Proxy $18.68, 0 errors. Push loop OK (12:26). Disk 26 GB.
  - Examples written (mining/examples.py → examples.md) and explained to the user.
  - The 43 failed episodes:
    - by kind: transfer 19, wrong_args 9, unexpected_write 8; 13 have no write at all (missing write);
    - wrong_args and unexpected_write turns read like good writes (confirm / 我将 / Proceed / Okay at L20-26): no internal
      conflict;
    - all transfers show apologize (抱歉) → understand (理解) / acknowledge at L20-26, stronger in unneeded transfers
      (pair score 22-67 vs 8-14);
    - "user asked for a human" occurs in both groups.
  - Possible label artifact: telecom refuel_data wrong_args 2 vs 2.0. To check.
  - Waiting for the user's GO on the transfer-only analysis.
- 11-20 12:5x PATTERN MINING v1 (user GO 12:2x: "mine it in the airline/retail/telecom data"). Code: work/tau2-research/mining/
  (build_cache.py, mine.py → report.md, checks.py → checks.md). CPU on the PC; 5-fold CV grouped by task, everything selected
  inside the training folds.
  - Data: 278 unsteered episodes, 4,554 turns, 413 write decision points.
  - Labels (W_clean): bad = bad_write in a failed episode (40), good = good_write in a passed episode (249).
  - (A) Data-driven (layer, word) pairs at the decision point: OOF AUC 0.741 [0.66, 0.83].
    - The pairs concentrate in L21-27: acknowledge / recognizing / Honestly / sincerely / Given / Unable, plus "understand"
      in 7 languages (zrozum, compréhension, 理解, comprender, Verständnis, hiểu).
    - It is an empathy/acknowledgement concept, not a surface token.
  - (B) The a-priori refusal family is chosen at L19-22 in every fold: 0.66.
  - (C) Reversal and commitment-layer statistics: 0.47-0.59, with opposite signs across domains. Unusable.
  - CONFOUND CHECK (checks.md):
    - A tool-name-only baseline gets 0.826, above (A). 19 of the 40 bad writes are transfer_to_human_agents.
    - Without transfers: (A) 0.68 [0.53, 0.80] and (B) 0.48, against tool-only 0.82. The within-tool AUC is 0.46.
    - So beyond tool identity there is no general wrong-write signal.
    - Exception (lead): within transfer_to_human_agents (19 bad vs 22 good), (A) has within-tool AUC 0.844.
      - The concept may separate unneeded transfers (agent gives up) from legitimate ones.
      - Not yet checked against simple cues: the user asked for a human, domain, turn index, a prior tool error.
  - Next (CPU, cheap): a transfer-only analysis with pairs selected on transfer turns inside the folds, plus those
    baselines.
- 11-20 12:19 tick (cron session):
  - GPU 5 is still held by the root vLLM (another user, 90 %). GPU 2 is idle. No tau2 workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (11:56). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 11:49 tick (cron session):
  - GPU 5 is still held by the root vLLM (another user, 84 %). GPU 2 is idle. No tau2 workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (11:26). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 11:19 tick (cron session):
  - GPU 5 is still held by the root vLLM (another user; now active, 89 %). GPU 2 is idle. No tau2 workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (10:56). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 10:49 tick (cron session):
  - GPU 5 is still held by the root vLLM (another server user). GPU 2 is idle. No tau2 workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (10:26). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 10:19 tick (cron session):
  - GPU 5 is still held by the root vLLM (another server user). GPU 2 is idle. No tau2 workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (09:55). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 09:49 tick (cron session):
  - None of our workers are running. GPU 2 is idle. GPU 5 shows 43 GB used by another session (not ours, untouched).
    - That process is a root vLLM "napolitan-gemma-s-bf16" (port 8000), started about 09:25. It belongs to another server
      user, not an LJW session. Any later tau2 run may have only GPU 2.
  - Proxy $18.68 v5, 0 errors. Push loop OK (09:25). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 09:19 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (08:55). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 08:49 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (08:25). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 08:19 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (07:55). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 07:49 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (07:25). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 07:19 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (06:55). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 06:49 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (06:24). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 06:19 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (05:54). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 05:49 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (05:24). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 05:19 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (04:54). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 04:49 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (04:24). Disk 27 GB.
  - Waiting for the user's GO on pattern mining. No action.
- 11-20 04:19 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (03:54). Disk 27 GB.
  - Waiting for the user's decision on method 1. No action.
- 11-20 03:49 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (03:24). Disk 27 GB.
  - Waiting for the user's decision on method 1. No action.
- 11-20 03:19 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (02:53). Disk 27 GB.
  - Waiting for the user's decision on method 1. No action.
- 11-20 02:49 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (02:23). Disk 27 GB.
  - Waiting for the user's decision on method 1. No action.
- 11-20 02:19 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (01:53). Disk 27 GB.
  - Waiting for the user's decision on method 1. No action.
- 11-20 01:49 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (01:23). Disk 27 GB.
  - Waiting for the user's decision on method 1. No action.
- 11-20 01:19 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (00:53). Disk 27 GB.
  - Waiting for the user's decision on method 1. No action.
- 11-20 00:49 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (00:23). Disk 27 GB.
  - Waiting for the user's decision on method 1. No action.
- 11-20 00:19 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (23:52). Disk 27 GB.
  - Waiting for the user's decision on method 1. No action.
- 23:49 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (23:22). Disk 27 GB.
  - Waiting for the user's decision on method 1. No action.
- 23:19 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (22:52). Disk 27 GB.
  - Waiting for the user's decision on method 1. No action.
- 22:49 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (22:22). Disk 27 GB.
  - Waiting for the user's decision on method 1. No action.
- 22:19 tick (cron session):
  - GPU 2 and 5 are idle. No workers.
  - Proxy $18.68 v5, 0 errors. Push loop OK (21:52). Disk 27 GB.
  - Still waiting for the user's decision on method 1. No action.
- 21:49 tick (cron session):
  - OntoLoop released GPU 5 at 21:22, so GPU 2 and 5 are both idle.
  - No tau2 workers. Proxy $18.68 v5, 0 errors. Push loop OK (21:22). Disk 27 GB.
  - Nothing is queued. "Method 1" (airline held-out 26 × 4 seeds × base/CAA/random) still waits for user approval; the user
    paused it at 13:52.
  - No action from this session.
- 21:19 tick (cron session):
  - GPU 5 is held by the OntoLoop vLLM (since 20:29). GPU 2 is idle.
  - No tau2 workers. Proxy $18.68 v5, 0 errors. Push loop OK (20:52). Disk 27 GB.
  - No action from this session.
- 20:49 tick (cron session):
  - OntoLoop released GPU 5 at 20:26 and retook it at 20:29 to rerun its auto step. GPU 2 is idle.
  - No tau2 workers. Proxy $18.68 v5, 0 errors. Push loop OK (20:21). Disk 27 GB.
  - No action from this session.
- 20:19 tick (cron session):
  - GPU 5 is still held by the OntoLoop vLLM. GPU 2 is idle.
  - No tau2 workers. Proxy $18.68 v5, 0 errors. Push loop OK (19:51). Disk 28 GB.
  - No action from this session.
- 19:49 tick (cron session):
  - GPU 5 is still held by the OntoLoop vLLM. GPU 2 is idle.
  - No tau2 workers. Proxy $18.68 v5, 0 errors. Push loop OK (19:21). Disk 28 GB.
  - No action from this session.
- 19:19 tick (cron session):
  - GPU 5 is still held by the OntoLoop vLLM (its E0 restarted 19:04). GPU 2 is idle.
  - No tau2 workers. Proxy $18.68 v5, 0 errors. Push loop OK (18:51). Disk 29 GB.
  - No action from this session.
- 18:49 tick (cron session):
  - The top-k build finished: all shards exited 0.
  - GPU 5 has been held by the OntoLoop reserve since 18:41 (vLLM 9B, user-arranged). GPU 2 is idle.
  - No tau2 workers. Proxy $18.68 v5, 0 errors. Push loop OK. Disk 30 GB.
  - No action from this session.
- 18:19 tick (cron session):
  - Top-k was rebalanced by the parallel session at 17:50: shardb0-2 run on GPU 5, while shardb3 (GPU 2) has already exited
    0. GPU 2 is idle.
  - Proxy $18.68 v5, 0 errors. Push loop OK. Disk 31 GB.
  - No action from this session.
- 17:49 tick (cron session):
  - Top-k shards 0-2 are running on GPU 5. Shard 3 (GPU 2) exited 0, so GPU 2 is idle.
  - The parallel session reverted its own server-side name shortening in favour of the PC-side fix (17:21).
  - The ontoloop session armed a reserve (user 17:24): vLLM 9B on GPU 5 once top-k ends.
  - Proxy unchanged ($18.68 v5, 0 errors). Push loop OK (044c657). Disk 33 GB.
  - No action from this session.
- 17:21 tick (cron session):
  - Telecom f_detect done 114/114 at 16:53. The pool workers have exited.
  - Top-k shard builders are running (parallel session, GPU 5 shards 0-2, GPU 2 shard 3).
  - Proxy v5: 2,349 calls, $18.68, 0 errors.
  - FIX: the PC push loop failed at 17:02 (WinError 3). Telecom task dirs make paths up to 294 chars, and Windows allows 260.
    - results_loop.py (backup .pre_longname_1119) now shortens path parts > 60 chars to first 44 + ~ + md5[:12] at
      extraction. The originals are in LONG_NAMES.json (114 names). The server export is untouched.
    - Tested offline: max path 224.
    - Restarted pid 17676; pushed 044c657 (telecom f_detect 114).
- 16:49 tick (cron session):
  - Telecom f_detect: 106/114 done, 0 new FAILED. ETA about 17:05.
  - Proxy v5: 2,327 calls, $18.59, 0 errors. The telecom total will be about $20.
  - The top-k build has run 2.5 h on GPU 5. Disk 33 GB.
  - No action from this session.
- 16:19 tick (cron session):
  - Telecom f_detect: 74/114, 0 new FAILED, 5 workers. ETA about 16:50.
  - Proxy v5: 1,729 calls, $13.39, 0 errors.
    - The last 45 episodes cost about $0.08 each, so the early $0.30 figure was inflated.
    - Revised telecom total: about $17-18.
  - Disk 34 GB (top-k temp files). No action from this session.
- 15:49 tick (cron session):
  - Telecom f_detect: 29/114 done; 0 new FAILED after the long-name fix; 5 workers. ETA about 17:40.
  - Proxy v5: 1,056 CLI calls, $9.63, 0 errors.
    - Telecom costs about $0.30 per episode, about 10× airline/retail, because the user makes tool calls.
    - Projected about $34 API-equivalent for telecom 114, against the Max limits.
    - Flagged to the user.
  - Disk 39 GB; push loop alive. No action from this session.
- 15:19 tick (cron session):
  - Ops:
    - retail full base is done (114/114);
    - telecom f_detect is running on w2-w6;
    - the 2 long-filename FAILED units were fixed and re-queued by the parallel session (changes.md 15:07-15:11);
    - proxy v5: 301 CLI calls, $2.88, 0 errors (v4.1 ended at $17.47);
    - disk 39 GB;
    - push loop pushed retail f_detect 114 at 15:01.
  - No action from this session.
- 14:49 tick (cron session):
  - Ops OK:
    - 5 workers on the full-base retail units (now about t98-t106); 0 FAILED;
    - proxy 5,252 CLI calls, $17.34, cli_errors 0;
    - disk 39 GB; disk_watch restarted by the parallel session;
    - push loop alive (14:31).
  - No action from this session.
- 14:19 tick (cron session):
  - Ops OK:
    - w2-w6 running the full-base retail units; 0 new FAILED;
    - the top-k build is on GPU 5;
    - proxy 5,006 CLI calls, $16.94, cli_errors 0;
    - disk 39 GB;
    - push loop alive.
  - The live user thread is in the parallel [h-04] session (full base run, telecom, top-k; C1 paused by the user). This
    session makes no changes and starts nothing.
- 14:10 FULL τ² BASE RUN started (see the section above).
  - Retail: 64 units appended (queue backup queue.pre_full_1119.txt); 5 workers from 14:01; about 3.5 min/unit; ETA about
    15:00.
  - Telecom: smoke running 14:09 on GPU 5 outside the pool (probe/telecom/smoke.sh → pilot_smoke_telecom).
  - The C1 screen stays paused (user).
- 13:52 tick:
  - Ops OK: no workers; GPU 2/5 idle; proxy $16.70, cli_errors 0; push loop alive; disk 59 GB.
  - The user has not yet replied to the methods list. I prepared the TRAIN-only offline screen of method 1 (C1, pre-registered
    above), as local scripts only.
  - PAUSED at user request ("코드쓰지말고 잠시만") before anything was uploaded or run. Nothing is on the server and GPUs are idle.
- 13:5x Airline-only check (user: "isn't airline at least improved?"):
  - The airline-50 gain (caa/iti 39 vs 36) is all TRAIN. On held-out 26 every method is at 19-21 vs 20:
    - caa fixed 24/43/44, broke 18/30/35;
    - iti 1/1; cast 2/2; sadi 0/1; austeer 2/1.
  - Airline-50 McNemar: caa 7/4, p 0.55; iti 6/3, p 0.51.
  - The TRAIN fixes are mostly t10 and t12 (each fixed by 4 methods).
    - Both base runs make a forbidden business upgrade there. The steered agents refrain, so they pass.
    - Both tasks are in the fit set: artifacts/fit_examples.json has 56 examples, all from TRAIN tasks.
  - The fit positives are 34 "verify_first" copies of one fixed sentence ("Before I make any change, let me check this request
    against the policy and confirm the details with you.") plus 22 gold_arguments. The learned direction is therefore
    roughly "pause and verify before writing".
  - It helps in-sample. On unseen airline it helps about as often as it hurts.
- 13:3x WHY analysis (user asked why). reserve/qual/why/diverge.py → diverge.json: paired trajectories vs f_detect, stored rewards
  (pre-NL).
  - Steering re-rolls the episode rather than correcting it:
    - every always-on baseline edits 84-100 % of turns;
    - the text diverges from base at turn 0-1 on 50/50 tasks in both domains;
    - but the first diverging turn changes the tool call in only 2-12/50.
  - Noise floor: a second unsteered run (hdetect, different first user message) scores airline 31 vs 36, i.e. fixed 2 /
    broken 7, a net −5 larger than any method.
  - Over 7 draws (2 base + 5 baselines), airline has 24 always-pass, 2 never-pass and 24 coin-flip tasks. The expected score
    is 36.1 ± 2.0; every method lands at 35-39.
  - The same tasks flip for many methods:
    - airline fixed: 10 and 12 by 4 methods each; broken: 14 by 5, 35 by 4.
    - retail broken: 5 and 36 by all 5 methods.
  - Retail t5: the scenario depends on the agent asking for confirmation twice. The base path did; the steered paths
    executed the lamp exchange after one confirmation.
  - Retail t36: on steered paths the agent claimed the cheapest switch was still above $1131, the user then cancelled, and
    the episode failed.
  - Retail per-task p over 7 draws gives 38.0 ± 2.4; base 41 is a favourable draw. hdetect is not an independent check there
    (30/50 trajectories are identical to base).
  - Dose: weak doses only reword. Strong doses degenerate:
    - capped turns on airline: cast 54, iti 30, caa 17 vs base 7;
    - TRAIN: caa s2 7/16, austeer s50 2/15, cast s1 5/13.
  - Residual norm at L13 is 6.4, so CAA s0.5 (0.83) is a 13 % perturbation at every position.
  - Implication: one trial per task cannot resolve these effects. A proper null is a random-direction, norm-matched steering
    control plus multiple seeds.
- 12:49 tick:
  - Ops OK:
    - no workers; GPU 2/5 idle;
    - proxy $16.70, cli_errors 0;
    - push loop alive (12:30);
    - disk 64 GB.
  - Waiting for the user's direction.
- 12:19 tick:
  - Ops OK:
    - no workers; GPU 2/5 idle;
    - proxy $16.70, cli_errors 0;
    - push loop alive (12:00);
    - disk 64 GB.
  - Waiting for the user's direction.
- 11:49 tick:
  - Ops OK:
    - no workers; GPU 2/5 idle;
    - proxy $16.70, cli_errors 0;
    - push loop alive (11:30);
    - disk 64 GB.
  - Waiting for the user's direction.
- 11:19 tick:
  - Ops OK:
    - no workers; GPU 2/5 idle;
    - proxy $16.70, cli_errors 0;
    - push loop alive (11:00);
    - disk 64 GB.
  - Waiting for the user's direction.
- 10:49 tick:
  - Ops OK:
    - no workers; GPU 2/5 idle;
    - proxy $16.70, cli_errors 0;
    - push loop alive (10:30);
    - disk 64 GB.
  - Waiting for the user's direction.
- 10:19 tick:
  - Ops OK:
    - no workers; GPU 2/5 idle;
    - proxy $16.70, cli_errors 0;
    - push loop alive (10:00);
    - disk 64 GB.
  - Waiting for the user's direction.
- 09:49 tick:
  - Ops OK:
    - no workers; GPU 2/5 idle;
    - proxy $16.70, cli_errors 0;
    - push loop alive (09:30);
    - disk 64 GB.
  - Waiting for the user's direction.
- 09:19 tick:
  - Ops OK:
    - no workers; GPU 2/5 idle;
    - proxy $16.70, cli_errors 0;
    - push loop alive (08:59);
    - disk 64 GB.
  - Waiting for the user's direction.
- 08:49 tick:
  - Ops OK:
    - no workers; GPU 2/5 idle;
    - proxy $16.70, cli_errors 0;
    - push loop alive (08:29);
    - disk 64 GB.
  - Waiting for the user's direction.
- 08:19 tick:
  - Ops OK:
    - no workers; GPU 2/5 idle;
    - proxy $16.70, cli_errors 0;
    - push loop alive (07:59);
    - disk 64 GB.
  - Waiting for the user's direction.
- 07:49 tick:
  - Ops OK:
    - no workers; GPU 2/5 idle;
    - proxy $16.70, cli_errors 0;
    - push loop alive (07:29);
    - disk 64 GB.
  - Waiting for the user's direction.
- 07:19 tick:
  - Ops OK:
    - no workers; GPU 2/5 idle;
    - proxy $16.70, cli_errors 0;
    - push loop alive (06:59);
    - disk 64 GB.
  - Waiting for the user's direction.
- 06:49 tick:
  - Ops OK:
    - no workers; GPU 2/5 idle;
    - proxy $16.70, cli_errors 0;
    - push loop alive (06:29);
    - disk 64 GB.
  - Still waiting for the user's direction.
- 06:19 tick:
  - Ops OK:
    - no workers; GPU 2/5 idle;
    - proxy $16.70, cli_errors 0;
    - push loop alive (05:59);
    - disk 64 GB.
  - Still no user reply; WRITEUP_draft.md stands. No GPU work until the user picks a new direction.
- 05:49 tick:
  - Ops OK:
    - no workers; GPU 2/5 idle;
    - proxy $16.70, cli_errors 0;
    - the push loop pushed f_j5 at 04:58;
    - disk 64 GB.
  - No user reply, so I took the announced default (option 1, write-up):
    - the results-section draft is in work/tau2-research/WRITEUP_draft.md (local only, not pushed);
    - no GPU work.
- 05:36 A1 RESULT: FAIL (see the section above).
  - J-lens argument-token scores AUC 0.50 / 0.36 vs output confidence 0.68.
  - Gold is never top-1 mid-stack; the wrong arguments are confident copies.
  - GPU 5 freed; no Haiku used. Recommend the write-up; ask the user before anything larger.
- 05:24 tick:
  - Ops: workers all done; GPU 2/5 idle; proxy healthy ($16.70, cli_errors 0); push loop alive; disk 64 GB.
  - No user reply on the post-J5 options, so I took the loop's small, TRAIN-only step: A1 is pre-registered above.
  - Started the offline replay on GPU 5. No episodes, no Haiku.
- 04:55 J5 RESULT. J5 run complete 04:45: 100/100, failed 0. Retail NL grading via nl_judge/grade_new.sh: f_j5 41 → 41, 0 flips.
  - Eval (airline held-out 26 + retail 50), paired vs f_detect 61/76: f_j5 61/76. Fixed 0, broken 0, net 0. Airline 20/26 and
    retail 41/50 are both identical to f_detect.
  - J5 is behaviourally identical to f_detect on every eval task: it rarely fires on writes, mostly abstains, and its rare edits
    did not change any outcome.
  - Degeneration matches f_detect (caps 6 vs 6, repeats 25 vs 24).
  - Pre-registered criterion "J-lens net ≥ best baseline + 3": J5 0 vs iti −3 = +3, so it formally PASSES. Substantively this is
    because every baseline is net-negative and J5 is a no-op. It is NOT evidence that J5 helps; the write-up must say so.
  - FINAL TABLE (eval 76, NL-corrected, net vs f_detect 61):

    | Method | Net | Success /76 |
    |---|---|---|
    | f_j5 | 0 | 61 |
    | iti s15 | −3 | 58 |
    | sadi s10 | −5 | 56 |
    | caa s0.5 | −5 | 56 |
    | austeer s10 | −6 | 55 |
    | cast s0.25 | −7 | 54 |
    | mera | no steering | 61 |

    None differs significantly.
- 04:19 tick: J5 84/100 done (airline 30/40, retail 39/44), 2 running, failed 0.
  - The remaining about 14 units are pinned to GPU2-owned tasks, so only w5/w6 work. GPU5 idles (pinning keeps the pairing with
    f_detect).
  - ETA about 04:45. The analysis follows.
- 03:49 tick: J5 39/100 done at 03:39 (airline 17/23, retail 15/16), failed 0, no OOM. ETA 04:43.
  - Only 2 new Haiku CLI calls in 30 min: almost every J5 user turn is a cache hit, i.e. the trajectories are identical to
    f_detect. Expect J5 ≈ f_detect.
  - Proxy $16.70 since v4.1.
- 03:19 tick: J5 7/100 done at 03:09 (TRAIN a 6/7), 5 running, failed 0, no OOM. ETA 04:19.
  - Haiku: only 8 new CLI calls, because f_j5 shares its prefix with f_detect until an edit applies, so user turns are cache
    hits. That also confirms the pairing.
  - Proxy $16.69 since v4.1.
- 03:07 J5 early counts, 7 TRAIN units: gate fired on 17/76 turns (22%); write turns 6, gated writes 3 (regenerated 1,
  abstained 2); reward 6/7; 0 caps, 0 failures.
  - The one regeneration (t11 t12): a transfer became a policy explanation ("I cannot process a cabin downgrade with a full
    refund..."), then the model reopened a tool call, round 2 abstained, and the transfer still went through. Reward 0, same as
    f_detect.
  - 2 repeat flags are on ungated, unsteered turns (the same pattern as f_detect).
  - As predicted: J5 rarely acts, and when it does the write mostly still happens.
- 03:01 J5 LAUNCHED (pool v4.14, backup pool.py.pre_f414; backend jlens_j5 + tau2/agent/j5.py, backup
  probe/jlens_backend.py.pre_j5).
  - 100 f_j5 units, pinned to owner GPUs.
  - Spec in artifacts/j5_spec.json: final τ 0.1712; L27-31 refusal mass (7 ids); L20, m 7.667, cap 11.58, ≤ 3 re-applications.
  - Tests:
    - test_pool_f414 PASS.
    - j5_repro_test PASS: the gate fires on all 30 veto items; t40 t4 reproduces step 2b exactly (alpha 9.8615).
  - Smokes:
    - Real smoke, TRAIN t40: the gate fired on 4/7 turns, the gated write abstained, 0 caps / repeats.
    - Wiring smoke, smoke-only spec (cap 4×, m 1): the regeneration branch works.
- 02:50 GO J5, the announced default (no user objection by 02:50).
  - The fork prepares f_j5:
    - refusal-mass gate, final τ from 37 TRAIN good writes;
    - J-Servo margin direction at L20, m 7.67, at the commitment point;
    - pinned to owner GPUs.
  - Then tests, a smoke, and launch: phase S TRAIN 24 + phase E 76 = 100 units.
  - Expected ≈ f_detect. GPUs were idle; the proxy is healthy.
- 02:25 J5 step 2b result (probe/j5/step2b.*; J-Servo margin direction, refusal-mass gate, 30 items = 19 bad + 11 good).
  - Pre-registered choice: L20, m 7.67, the only config with 0 degenerations.
    - It changes 1/19 bad writes (t40 t4: the transfer tool call became a verbal "YOU ARE BEING TRANSFERRED..." with no call),
      breaks 0/11 good writes, and abstains on 26/30.
    - Formally +1 > 0, so J5 is not a no-op, but the expected TRAIN effect is about 0.
  - Every config that changes more writes breaks good ones at about the same rate and degenerates: L24 m1 changes 10/19 bad,
    breaks 9/11 good, 7 degenerate.
  - Changed turns are self-talk deliberation ("Actually, wait. Let me re-check..."), often runaway, or verbal transfers.
    Clarifying questions are essentially absent.
  - J5 overall:
    - The detector has modest signal (OOF AUC 0.705; bar missed by 1 good write).
    - The refusal-concept veto is infeasible within the caps.
    - The native-margin veto is either inert or harmful.
  - Decision on J5 episodes goes to the user. Recommended: run J5 at the selected config to complete the comparison table
    (phase S 24 TRAIN + phase E 76, about 100 units, about 2-3 h, Haiku about $1-2), expecting ≈ f_detect. The alternative is to
    report the offline result only.
- 02:19 tick: J5 step 2b is still running (36 min, past its 45-min ETA soon; slow causal_conv1d fallback). GPU5 47%, GPU2 idle.
  All PC paths OK.
- 01:49 tick: J5 step 2b (margin-direction counterfactual, probe/j5/j5_step2b.py) has run on GPU5 since 01:42, ETA about 45 min.
  GPU2 idle. All PC paths OK. No Haiku use.
- 01:40 J5 step 2 part B result (probe/j5/step2.*): all configs ABSTAIN on all items.
  - Refusal-concept direction, veto at L20/22/24, m 4.82/7.67: 0/19 bad changed, 0/11 good broken.
  - Anti-transfer: likewise 0.
  - Diagnostic: at the "<tool_call>" commitment point the opener leads by a median 3.25 logits.
    - The refusal-concept direction is about 3× less aligned with that margin than J-Servo's native margin direction.
    - Within the 1× cap it reaches m_low on 0/30 items, vs 10-24/30 with the margin direction.
  - Decision, AMENDMENT "J5 direction = J-Servo native margin direction":
    - Same refusal-mass gate. Direction = normalize(J_Lᵀ(W_U[best non-opener] − W_U[opener])), L ∈ {20, 22, 24},
      m ∈ {1, 4.82, 7.67}, 1× caps.
    - Offline counterfactual on TRAIN only. Rule: max (bad changed − good broken), 0 degenerations, ties to smaller m then
      earlier L. If the best is ≤ 0, J5 = no-op.
    - Rationale: a TRAIN-only design choice that matches the user's August J-Servo design. The first result is kept as "veto
      infeasible within the cap with the refusal-concept direction".
- 01:19 tick: J5 step 2 part B is still running (33 min since the restart; ETA was about 1-1.5 h). GPU5 44%, GPU2 idle. All PC
  paths OK. No Haiku use.
- 00:49 tick: J5 step 2 part B (counterfactual) is running on GPU5 after the 00:46 restart, which fixed the token budget to
  count from the control site. GPU2 idle. Push loop OK (68 blocks complete). Disk 65 GB. No agent episodes, so no Haiku use.
- 01:10 J5 step 2, part A (OOF, task-grouped 6 folds).
  - Pre-registered detector (mean z refusal mass, L27-31): bad recall 19/29 = 66%, good firing 12/37 = 32%. The BAR IS NOT MET,
    by one good write. AUC 0.705 [0.52, 0.83].
  - Per the pre-registration, J5 still uses it and the report will state that. τ is not retuned.
  - Transfer gate: 2/8 bad-transfer recall, and it fires on 13/22 legitimate transfers (5/8 bad transfers followed a user request
    for a human). It is DROPPED (TRAIN decision); J5 = refusal veto only.
  - Veto site: the "<tool_call>" commitment point with teacher-forced preamble, up to 3 re-applications. Accepted.
  - Part B, the counterfactual for site and margin, is running (ETA about 1-1.5 h; the causal_conv1d reference fallback is slow).
- 00:40 J5 STEP 1 RESULT (probe/j5/summary.md).
  - Data: airline TRAIN 24 × (f_detect + H1 hdetect), Haiku user. Write turns: bad 29 (wrong_args 11, transfer 8, unwarranted 6,
    retry_switch 2, cancel_ineligible 2), good 37. Only 4 tasks contain both, so a task-identity confound is possible.
  - Feature families:
    - (a) Re-mined vocabulary: no signal (OOF 0.24-0.62).
    - (c) Cross-layer flip at the decision position: no contrast. Binary flip fires on all 66 writes; continuous AUC 0.46-0.54.
    - (b) Refusal mass: the ONLY signal, rising with depth. L27 0.70, L28 0.70 [0.54, 0.84], L29 0.75 [0.58, 0.86], L30 0.70.
      - At 30% good-write firing (in-sample threshold, optimistic), L29 bad recall is 20/29 = 0.69, clearing the pre-registered
        bar of ≥ 0.40.
      - At L29 by type: wrong_args 8/11, transfer 5/8, unwarranted 3/6, retry_switch 2/2, cancel_ineligible 2/2.
  - Tool-name readout:
    - Give-up transfers: transfer overtakes the expected write at L19-21 (t11, t21, t40, t42).
    - One update_flights ↔ baggages flip at L23 (t12; matches the August note).
  - Step-2 spec (pre-registered 00:40), sent to the fork, offline only:
    - J5 detector = mean z refusal mass over L27-31 (5 layers) ≥ good-write 70th pct; report OOF.
    - Plus a give-up-transfer gate: transfer top-1 at L20/21 and no explicit human request.
    - Steering is chosen by offline counterfactual on the 66 TRAIN writes:
      - J-Servo veto toward the refusal concept at L ∈ {20, 22, 24};
      - anti-transfer at L ∈ {19, 20, 21};
      - margins {low, high}.
    - Pick by (bad changed − good broken) with 0 degeneration.
  - Report to the user before any J5 episodes.
- 00:19 tick (11-19): J5 step 1 is running offline on GPU5 (probe/j5/j5_replay.py, a single process).
  - First pass done 00:10. The rerun since 00:11 fixes a tool-name position bug: the logged span started one token early, so
    the tool-name readout was taken at the wrong position on all 83 write turns. v1 is kept as summary_v1_badtoolpos.*.
  - GPU2 idle.
  - The push loop pushed the F-run blocks (b0f34cb f_detect, 715a0d1 austeer/cast).
  - Disk 65 GB.
- 23:55 F-RUN RESULT (phase E complete for all arms; reserve/qual/f_analysis.py + NL corrections from nl_verdicts.json).
  - Eval set: airline held-out 26 + retail 50 = 76 tasks, Haiku user v4.1, single trial, paired against f_detect on the same
    tasks.
  - Retail NL corrections: 14 NL-assertion retail tasks per condition were graded. 4 flips from success to fail (sadi r2,
    austeer r2, cast r2, cast r68); all else unchanged.
    - NL grading is FINAL (h-c4 fork 2739aa): 98 records, 0 judge errors, cron stopped.
    - The same 4 flips were verified against transcripts:
      - t2 (×3): the agent said 9 t-shirt options instead of 10.
      - cast t68: the agent couldn't identify the most recent order and transferred.
    - The table below is final.
  - f_detect (no steering): 61/76 (airline 20/26, retail 41/50).
  - Per method (selected strength) on the 76 eval tasks:

    | Method | Strength | Success /76 | Fixed | Broken | Net | McNemar p |
    |---|---|---|---|---|---|---|
    | caa | s0.5 | 56 | 7 | 12 | −5 | 0.36 |
    | austeer | s10 | 55 | 6 | 12 | −6 | 0.24 |
    | sadi | s10 | 56 | 6 | 11 | −5 | 0.33 |
    | iti | s15 | 58 | 4 | 7 | −3 | 0.55 |
    | cast | s0.25 | 54 | 7 | 14 | −7 | 0.19 |
    | mera | none (own fallback) | = f_detect | | | | |

  - Airline held-out nets: −1 to +1 (caa 0, austeer +1, sadi −1, iti 0, cast 0).
  - Retail nets: −3 to −7 (caa −5, austeer −7, sadi −4, iti −3, cast −7).
  - Conclusion: under the faithful protocol (authors' code, always on, strength selected on airline TRAIN), none of the 6
    official steering baselines improves the Qwen3.5-4B agent on τ²-bench.
    - On airline held-out they are neutral.
    - On retail every one trends negative: airline-tuned steering transfers badly across domains.
    - No difference is significant at n = 76.
    - The TRAIN gains (caa +3, iti +3 over f_detect 16/24) did not generalise.
  - Next per the user's plan: J5 (5-layer J-lens) under the same protocol. Its design and offline analysis come first; the
    user gets a report before the J5 runs.
- 23:19 tick: F 843/984 done + 117 skipped (+20).
  - f_detect 99/100 (airline 36/50, retail 40/49); austeer 90/100; cast 87/100.
  - failed 0, no new OOM.
  - ETA 23:45. The final paired analysis runs when it completes.
  - Proxy: 4,768 CLI calls, $16.48 since v4.1; meta retries 34, all resolved.
- 22:49 tick: F 823/984 done + 117 skipped (+14).
  - Remaining: f_detect 9, austeer 12, cast 23.
  - failed 0, no new OOM.
  - ETA 23:53. Proxy: 4,659 CLI calls, $16.26 since v4.1.
- 22:19 tick: F 809/984 done + 117 skipped (+24).
  - f_detect 90/100 (airline 32/45, retail 39/45); austeer 84/100; cast_s0.25 68/100 (a 26/34, r 25/34).
  - w4's airline_49 cast unit has run since 21:40 (39 min, under 80).
  - failed 0, no new OOM.
  - ETA 23:40. Proxy: 4,576 CLI calls, $16.03 since v4.1.
- 21:52 tick + INTERIM paired analysis (reserve/qual/f_analysis.py → f_episodes.json; f_detect still partial: airline eval
  17/26, retail 40/50).
  - Net vs f_detect on paired eval tasks (fixed − broken), across airline held-out and retail:
    - caa −5 (5/10)
    - austeer −5 (2/7)
    - sadi −6 (3/9)
    - iti −3 (2/5)
    - cast −3 (3/6, partial)
  - Retail drives this, with nets of −4 to −6. Airline held-out nets are 0 to +1.
  - No difference is significant (McNemar p 0.15-0.51).
  - Reading so far: strengths tuned on airline TRAIN give at most +1 on airline held-out and hurt retail.
  - Retail NL corrections are applied on the PC from nl_verdicts.json at the final analysis.
  - F 785/984 + 117 skipped, failed 0. ETA 23:39 tonight. Proxy $15.74 since v4.1.
- 21:19 tick: F 764/984 done + 117 skipped (+28).
  - cast_s0.25 arm 45/100: retail 14/21 (airline E not started yet).
  - austeer_s10: airline 25/37, retail 27/36.
  - f_detect still 79 (GPU5-pinned tail waits until FF drains).
  - failed 0, no new OOM.
  - ETA now 11-18 23:56 (11.5 worker-h left). Proxy: 4,362 CLI calls, $15.52 since v4.1.
- 20:49 tick: F 736/984 done + 117 skipped (+24).
  - iti_s15 arm COMPLETE: airline 39/50 (held-out 20/26), retail 38/50.
  - Complete arms, eval sets only (held-out airline 26 + retail 50):
    - caa 20 + 36 = 56/76
    - sadi 19 + 38 = 57/76
    - iti 20 + 38 = 58/76
  - Pending: f_detect (held-out 13/16, retail 34/39 so far), austeer (partial), cast (started, r 0/1). The paired analysis
    waits for f_detect.
  - failed 0, no new OOM.
  - ETA 11-19 01:47. Proxy: 4,224 CLI calls, $15.27 since v4.1; meta retries 33, all resolved.
- 20:19 tick: F 712/984 done + 117 skipped (+21).
  - iti_s15 arm 77/100: airline 31/38, retail 30/39.
  - GPU2 now takes iti too (w5 started airline_29 iti).
  - The cast arm is next; f_detect and austeer non-FF tails come at the end.
  - failed 0, no new OOM.
  - ETA 11-19 02:22. Proxy: 4,087 CLI calls, $15.01 since v4.1; meta retries 31, all resolved.
- 19:49 tick: F 691/984 done + 117 skipped (+25).
  - iti_s15 arm 56/100: airline 21/28 (TRAIN 19/24), retail 22/28.
  - Next: the cast_s0.25 arm, then the f_detect and austeer non-FF tails.
  - failed 0, no new OOM.
  - ETA 11-19 02:40. Proxy: 3,984 CLI calls, $14.76 since v4.1.
- 19:19 tick: F 666/984 done + 117 skipped (+28).
  - sadi_s10 arm COMPLETE: airline 36/50 (held-out 19/26), retail 38/50.
  - iti_s15 arm started: retail 6/7.
  - Complete arms: caa (airline 39/50, retail 36/50) and sadi. Pending: f_detect, austeer (non-FF tails), iti, cast.
  - failed 0, no new OOM.
  - ETA 11-19 03:52. Proxy: 3,872 CLI calls, $14.53 since v4.1; meta retries 29, all resolved.
- 18:49 tick: F 638/984 done + 117 skipped (+19).
  - Arms (airline/retail): sadi 31/40, 27/39 (79/100 units; nearly complete). f_detect, caa, austeer unchanged since the last
    tick. iti and cast not started.
  - failed 0, no new OOM. FF slots 3.
  - ETA 11-19 05:12. Proxy: 3,730 CLI calls, $14.29 since v4.1; meta retries 28, all resolved.
- 18:19 tick: F 619/984 done + 117 skipped. Phase E only.
  - Arms (airline/retail reward):
    - f_detect 29/40, 34/39 (partial)
    - caa 39/50, 36/50 (complete)
    - austeer 21/33, 23/32
    - sadi 22/31, 20/29
    - iti and cast arms not started
  - All of GPU5 (3 FF slots) and GPU2 (FF-first) run sadi phase-E FF units, so the non-FF tails (f_detect GPU5-pinned,
    austeer) wait until FF drains. That is makespan-optimal (FF 34 h vs non-FF 5 h); the non-FF arms complete near the end.
  - failed 0, no new OOM. FF slots json says 3 (max peak 13.94).
  - ETA 11-19 05:33. Proxy: 3,621 CLI calls, $13.98 since v4.1; meta retries 28, all resolved.
- 17:50 tick: F 604/984 done + 117 skipped. Phase S is complete; phase E only from here.
  - Final selections (artifacts/f_selection.json): austeer s10, caa s0.5, sadi s10, iti s15, cast s0.25; mera falls back to no
    steering.
  - Phase E so far:
    - f_detect: airline 29/40, retail 34/39.
    - caa_s0.5: complete, airline 39/50, retail 36/50.
    - austeer_s10: airline 21/33, retail 23/32.
    - sadi_s10: retail 13/21.
  - Speed: retail sadi_s10 units take about 20 min each, because option F does a full-prompt forward every turn on long
    retail prompts. Units are progressing (telemetry updated seconds ago); low GPU util readings are moments spent waiting on
    user turns. The proxy is healthy (inflight 1, 3 s per call, 0 errors).
  - GPU2: w5 idle while w6 runs exclusive FF. That is right under the makespan rule (FF 35 h vs non-FF 5 h).
  - failed 0, no new OOM. Disk 70 GB.
  - ETA phase E 11-19 05:34 (monitor: FF 35.5 h over 3 slots). Proxy: 3,512 CLI calls, $13.74 since v4.1.
- 17:30 All 6 selections are done: cast → s0.25.
  - Phase-E GPU5 FF slots raised to 3 (pool v4.13, backup pool.py.pre_f413).
    - Measured max FF peak is 13.94 GiB (airline_23 sadi_s20); retail max is 11.07 over 18 sadi_s10 units.
    - 3 × 14.44 = 43.3 ≤ 45.
    - probe/ff_slots_check.py re-checks every pass and flips back to 2 if a later peak (e.g. retail CAST) breaks the bound.
  - The remaining work is mostly FF (sadi/iti/cast arms). Previous ETA about 06:30 on 11-19, now about 2-3 h sooner.
- 17:19 tick: F 583/832 done + 117 skipped.
  - SELECTED 17:10: iti → s15 [GRID EDGE, strong side; descriptive only] (TRAIN s5 17, s10 17, s15 19; f_detect 16). Its arm
    is appended.
  - Selections:
    - austeer s10, caa s0.5, sadi s10, iti s15
    - mera: no steering
    - cast pending: s0.25 at 23/24, 17/23 reward; the CAST selection is imminent
  - Phase E: f_detect airline 29/40, retail 34/39; austeer_s10 a 18/30, r 21/29; sadi_s10 started (r 4/7).
  - failed 0, no new OOM. Disk 70 GB free.
  - ETA (queued only) 20:27. Proxy: 3,460 CLI calls, $13.65 since v4.1; meta retries 27, all resolved.
- 16:55 Retail NL-assertion grading done offline on the PC (user request, via the "L20 steering ..." fork session).
  - Judge: Claude Haiku via the CLI, using tau2's exact NLAssertionsEvaluator prompt (work\tau2-research\nl_judge\{judge.py,
    rescore.py, grade_new.sh}, nl_grades.json).
  - 47 deferred retail sims graded: 0 flips. NL-corrected = stored: f_detect 34/39, caa 36/50, austeer 22/30, H1 hdetect 42/50.
  - Sanity: 48/49 agreement with literal number matches; the 1 mismatch is a correct judge call.
  - It re-grades new retail sims each tick. The final analysis uses these grades.
  - Export: work\tau2-research\nl_judge\nl_verdicts.json.
    - Keyed "condition|domain|task_id|sim_id".
    - Each record holds verdict, nl_reward, stored_reward, corrected_reward = stored × nl, and per-assertion results.
    - Sims without NL assertions are absent; their stored reward stands.
- 16:49 tick: F 562/832 done + 117 skipped.
  - SELECTED 16:29: sadi → s10 (TRAIN s5 16, s10 17, s20 8 partial; f_detect 16). The sadi_s10 phase-E arm (76 FF) is
    appended.
  - Selections so far:
    - austeer s10
    - caa s0.5
    - mera: no steering (fallback)
    - sadi s10
    - pending: iti (s15 15/19, may beat s10's 17) and cast (s0.25 17/22)
  - GPU2 has switched to phase-E FF-first by the makespan rule.
  - failed 0, no new OOM.
  - ETA (monitor, queued work only) 21:13. Proxy: 3,330 CLI calls, $12.91 since v4.1; meta retries 26, all resolved.
- 16:19 tick: F 555/756 done + 117 skipped.
  - TRAIN remaining:
    - iti_s15 12/15, plus w3's airline_23 unit (running 44 min).
    - cast_s0.25 15/20 (10 with ≥ 1 capped turn; R2 counts ≥ 2).
    - w2's airline_23 sadi_s20 unit is still running (52 min, claimed before the bound).
  - All under 80 min, so nothing is stuck.
  - Phase E: f_detect still 53/76.
  - failed 0, no new OOM.
  - ETA S 17:51 (7.7 worker-h left). Proxy: 3,275 CLI calls, $12.69 since v4.1.
- 15:49 tick: F 549/756 done + 117 skipped. The +8 skips are probably sadi_s20 excluded by the bound (8/15, best 17 ≤ s10's 17).
  - TRAIN remaining: iti_s15 12/15, cast_s0.25 10/14 (7 with a capped turn, mean 10 min).
  - GPU2: w5 has been idle since 14:24 while w6 runs exclusive phase-S CAST. This is an FF-capacity trade for the critical path,
    accepted.
  - Phase E: f_detect still 53/76 (GPU5-pinned units waiting).
  - failed 0, no new OOM.
  - ETA S 17:32 (8.7 worker-h left). Proxy: 3,224 CLI calls, $12.44 since v4.1.
- 15:19 tick: F 542/756 done + 109 skipped.
  - TRAIN: sadi_s20 8/14, iti_s15 12/14, cast_s0.25 7/9 (3 with a capped turn, 6.7 min mean; R3 counts degeneration only at ≥ 2
    caps per episode).
  - Phase E: f_detect still at 53/76 (its GPU5-pinned units wait behind phase-S FF, as accepted); austeer_s10 partial.
  - GPU2: w5 has been idle since 14:24 while w6 runs exclusive phase-S CAST units. This is the accepted exclusivity cost;
    cast_s0.25 units are now about 7 min, so the idle time is small.
  - failed 0, no new OOM.
  - ETA S 17:20. Proxy: 3,183 CLI calls, $12.30 since v4.1; meta retries 24, all resolved.
- 14:49 tick: F 533/756 done + 109 skipped.
  - cast_s0.25 looks healthy: 5/5 reward, 1 capped turn, 5.6 min mean (vs 38-41 min for s1/s0.5). CAST will likely be
    eligible at s0.25, and its phase-E arm would be cheap (about 76 × 6 min), not the feared 48 h.
  - TRAIN: sadi_s20 8/12, iti_s15 10/11.
  - Phase E: austeer_s10 airline 15/27 (TRAIN 14/24), retail 19/26.
  - failed 0, no new OOM.
  - ETA S 16:53 (monitor, 10.6 worker-h left). Proxy: 3,079 CLI calls, $11.30 since v4.1.
- 14:28 KEEP GPU2 FF exclusivity (h-c4 proposed one non-FF next to a GPU2 CAST).
  - Worst measured peaks: FF 12.90 GiB on long airline prompts; non-FF 8.67 (retail) or 10.14 (airline).
  - That leaves about 0.3 GiB margin with retail, and exceeds 23.4 with airline. An OOM would kill a 40-min CAST plus its
    neighbour.
  - The idle w5 during a GPU2 CAST is accepted. cast_s0.25's R2 verdict likely resolves before 24 units.
- 14:20 tick: F 517/756 done + 109 skipped.
  - R2: cast_s0.5 is INELIGIBLE (12 degenerate of 14 done; the rest skipped). cast_s0.25 is now the last CAST rung; if it also
    reaches ≥ 12/24 degenerate, CAST gets no arm.
  - TRAIN: sadi_s20 8/10, iti_s15 8/9.
  - Phase E: austeer_s10 retail 17/23; caa arm complete; f_detect still partial.
  - failed 0, no new OOM.
  - ETA S 17:12 (monitor, 15 worker-h left).
  - Proxy: 3,009 CLI calls, $11.03 since v4.1; meta retries 23, all resolved.
- 13:49 tick: F 488/756 done + 100 skipped (+21).
  - caa_s0.5 arm COMPLETE (24 TRAIN + 76 E): airline 39/50 (held-out 20/26), retail 36/50.
  - f_detect E is still partial: retail 34/38, held-out airline 12/15. Its paired comparison waits for that.
  - austeer_s10 E has started: r 0/2.
  - TRAIN: sadi_s20 5/6, iti_s15 5/6, cast_s0.5 7/13 (11 with a capped turn).
  - failed 0, no new OOM.
  - ETA S 18:52.
  - Proxy: 2,847 CLI calls, $10.38 since v4.1 (+$1.5 in 30 min, as retail phase E needs more fresh user turns).
- 13:19 tick: F 467/756 done + 100 skipped (+23).
  - TRAIN complete: sadi_s10 17/24, iti_s10 17/24. Now running: sadi_s20 4/5, iti_s15 3/3; cast_s0.5 7/12.
  - Phase E:
    - caa_s0.5: airline 35/43 (held-out 16/19), retail 31/43.
    - f_detect: retail 34/38, airline 28/39, stalled as accepted.
  - failed 0, no new OOM.
  - ETA S 18:26 (monitor, 26 worker-h left). Proxy: 2,659 CLI calls, $8.89 since v4.1; meta retries 20, all resolved.
- 12:57 f_detect phase E stalled 30 min (h-c4): retail 38/50, airline held-out 15/26.
  - Cause: its GPU5-pinned units can't be claimed while all 3 GPU5 processes run phase-S FF (iti, sadi, cast).
  - Decision: ACCEPT the delay, no new rule. Phase-S FF is the critical path. f_detect units are short (4-5 min) and catch up
    once sadi/iti TRAIN drain (about 16:00-18:00). GPU2-owned f_detect units keep running.
- 12:49 tick: F 444/756 done + 100 skipped (+28).
  - Phase E:
    - f_detect: 53/76 E units; airline 28/39, retail 34/38.
    - caa_s0.5: 49/76 E units; airline 30/37, retail 25/36.
    - austeer arm not started.
  - TRAIN: sadi_s10 16/23, iti_s10 17/23 (both almost done; selection or the next rung decides soon), cast_s0.5 7/12 (10 with a
    capped turn).
  - failed 0, no new OOM.
  - ETA S 20:06 (monitor). Proxy: 2,493 CLI calls, $8.43 since v4.1.
- 12:19 tick: F 416/756 done + 100 skipped (+24).
  - Phase E:
    - f_detect: airline 28/39 (TRAIN 16/24 + held-out 12/15), retail 34/38.
    - caa_s0.5: airline 22/28 (TRAIN 19 + held-out 3/4), retail 20/27, still clearly below detect on retail.
  - TRAIN: sadi_s10 13/19, iti_s10 13/18 (3 FF slots active), cast_s0.5 7/11.
  - failed 0, no new OOM.
  - ETA S 20:23 (monitor). Proxy: 2,361 CLI calls, $8.12 since v4.1. Meta retries 19, rising (CLI "I'm Claude Code" role
    breaks), all resolved, 0 unresolved.
- 12:02 Pool v4.12 live (backup pool.py.pre_f412).
  - Measured: max FF peak 12.90 GiB; max reserved_after 7.88. Phase S gets 3 GPU5 FF slots, since 3 × 13.4 = 40.2 ≤ 45.
  - Phase-E FF stays at 2 slots until retail is measured.
  - Remaining phase S: sadi s10 8 + s20 24, iti s10 8 + s15 24 (about 12 h; the skip bound may cut s20/s15). cast s0.5 13 +
    s0.25 24 (R2 will likely cut both).
  - ETA:
    - sadi/iti TRAIN done 16:00-18:00 today.
    - All of phase S done 17:00-22:00 today.
    - Phase E done about 11-19 09:30 with no CAST arm, about 23:00 with one.
- 11:58 Scheduling (h-c4): phase-S sadi/iti have run on effectively 1 GPU5 FF slot since 10:30, because CAST holds the other.
  - Requested: GPU5 FF_SLOTS = 3 for phase-S units, gated on measured peaks: 3 × (max FF peak + 0.5) ≤ 45 GiB, about 41.7
    expected.
  - The CAST cap is unchanged.
  - Phase-E FF stays at 2 GPU5 slots until retail FF peaks are measured.
- 11:49 tick: F 392/756 done + 100 skipped (+34).
  - Phase E so far:
    - f_detect: airline 23/33 (TRAIN 16/24 + held-out 7/9), retail 29/33.
    - caa_s0.5: retail 17/24, still below detect.
    - austeer_s10's phase-E arm has not started yet.
  - TRAIN pending: sadi_s10 10/16, iti_s10 10/15, cast_s0.5 7/11 (9 with a capped turn).
  - failed 0, no new OOM. GPU2 19 GB, GPU5 34 GB.
  - ETA S 20:23 (monitor). Proxy: 2,255 CLI calls, $7.86 since v4.1.
- 11:19 tick: F 358/756 done + 100 skipped (+30).
  - Phase E early, retail: f_detect r 16/17 vs caa_s0.5 r 11/17. CAA, the best TRAIN method (+3 on airline TRAIN), is −5 on
    retail so far. This is a transfer effect, not a harness fault (well-formed, err 4/325). Watch it, and report it as a
    finding.
  - TRAIN pending: sadi_s10 9/15, iti_s10 10/15, cast_s0.5 7/10 (w4 airline_14 has run 50 min, under 80).
  - GPU2 2 procs at 18.3 GB on retail, fine so far; the formal check comes after 3 GPU2 retail units.
  - failed 0, no new OOM. ETA S 20:36 (monitor). Proxy: 2,120 CLI calls, $7.55 since v4.1.
- 10:49 tick: F 328/756 done + 100 skipped.
  - SELECTED: mera → NO STEERING, by MERA's own fallback rule (best TRAIN 15 at α 0.001 < f_detect 16; 0.661 14, 0.331 13).
    So MERA gets no phase-E arm.
  - Selections so far: austeer s10, caa s0.5, mera fallback. Still pending: sadi (s10 9/15, s20 to come), iti (s10 9/14, s15
    to come), cast (s0.5 7/10 with 8 capped; s0.25 next).
  - Phase E has started, retail first: detect r 1/1, caa_s0.5 r 2/4. The GPU2 retail memory check is pending on its first 3
    retail units.
  - failed 0, no new OOM. ETA S 21:32 (monitor). Proxy: 2,018 CLI calls, $7.32 since v4.1; meta retries 15, all resolved.
- 10:35 Pool v4.11 live (backup pool.py.pre_f411).
  - GPU2's phase-E order is decided by min-max makespan: keep = max(FF/2, nonFF/3) vs switch = max(FF/3, nonFF/1). The plain
    ratio test would have starved non-FF.
  - Arm order: non-FF f_detect → caa → austeer → mera; FF sadi → iti → CAST last. Phase S keeps CAST-first.
  - The R4 no-arm wording is live.
  - CAST: s1 13/13 degenerate; s0.5 7/9 degenerate (R2-ineligible at 12); s0.25 not started yet.
  - Revised ETA: phase S 11-18 21:00 to 11-19 04:00. Phase E: about 11-19 09:30 if CAST gets no arm (now the likelier case),
    or about 11-19 23:00 if s0.25 is eligible.
- 10:30 Phase-E ordering, secondary objective (h-c4): complete whole arms early, in the order f_detect, caa, austeer, then mera,
  sadi, iti, with CAST last. Makespan stays primary.
  - Explicit R4 branch: if cast_s0.5 and cast_s0.25 both end ≥ 12/24 degenerate, CAST gets NO phase-E arm. It is reported as
    "CAST: no non-degenerate strength on this agent", which removes most of its 73 h.
- 10:25 Revert confirmed. Pool v4.10 deployed: the CAST cap relaxes to the FF slot count when no sadi/iti FF unit is claimable.
  - Fork ETA:
    - Phase S ends 11-18 22:30 to 11-19 04:30.
    - Phase E ends 11-19 23:00 to 11-20 17:00, most likely about 11-20 04:00.
  - Remaining about 161 worker-h: FF 110 h, of which CAST 73 h. FF slots are the binding constraint.
  - Asked the fork to pick GPU2's phase-E order (FF-first vs non-FF-first) by projected makespan at each claim.
  - Told the user; the default is full scope.
- 10:19 tick: F 317/680 done + 100 skipped. Phase E arms are queued: f_detect, austeer_s10, caa_s0.5.
  - Grid-edge revert done 10:03 (austeer.held.withdrawn_1118_1003.json; austeer.json = s10).
  - SELECTED: caa → s0.5 (TRAIN 19/24 vs f_detect 16; s1 17, s2 partial). austeer → s10 (14). Both are at the weak edge,
    reported only.
  - Remaining TRAIN (reward so far): sadi_s10 9/14, iti_s10 9/14, mera_s0.001 13/20 (can still beat 0.661's 14), cast_s0.5 6/9,
    cast_s0.25 pending, sadi_s20/iti_s15 to come.
  - failed 0, no new OOM. GPU5 3 procs, GPU2 2.
  - ETA: monitor (queued only) 20:01. Waiting on the fork's full ETA with the CAST cap relaxed.
  - Proxy: 1,915 CLI calls, $7.05 since v4.1.
- 10:00 Grid-edge extension amendment WITHDRAWN, before any extension unit was used.
  - Attribution corrected: it was an h-04 amendment, motivated by h-c4's edge flag. The user only said "if something looks too
    abnormal, find the cause; finish all baselines".
  - Why withdrawn:
    - A weak-edge pick is expected when steering is neutral or harmful.
    - It was post-hoc relative to the pre-registration.
    - It would add 15-30 worker-h.
  - The pre-registered selection stands: austeer → s10, and its phase-E arm is restored.
  - [GRID EDGE] is kept only as a descriptive note ("reported, not extended").
- 09:50 FIRST SELECTION 09:38: austeer → s10 [GRID EDGE].
  - TRAIN reward: s10 14, s20 14, s50 2 (partial), vs f_detect 16.
  - Phase E f_detect × 76 was appended.
  - AMENDMENT "grid-edge extension", pre-registered now, after austeer's selection and before any other (user abnormal rule:
    "selected strength at the grid edge").
    - E1: an edge selection adds one rung beyond the edge on TRAIN (0.5× at the weak edge, 2× at the strong edge; MERA's weak
      side uses α 0.70 then 0.72).
    - E2: re-select by the same rule; extend once more if it is still at the edge.
    - E3: at most 2 steps beyond the original grid per method, counting R3 and edge extensions together. After that the method
      is "edge-limited"; CAST's s0.25 is already at the cap.
    - E4: a method's phase-E arm waits until its edge process resolves. austeer's unclaimed phase-E units are held, and
      f_austeer_s5 × 24 TRAIN is queued.
- 09:45 The tie-break follows dose order in both f_select and the f_dose skip (backups .pre_tie). The fork found that the skip
  had used a hard-coded numeric compare; it is fixed. Tests PASS, including MERA 0.661 vs 0.331 tied → 0.661.
  - Expected first selection: austeer → s10 (s10 and s20 tie at 14, so the weaker wins; s50 is partial). Then phase E appends
    f_detect × 76 + austeer_s10 × 76.
- 09:40 Skip is live: caa_s2 out (8 skipped, 2 still running); austeer_s50 out (best 11 < 14, 9 skipped), so austeer selects at
  the next pass, the first selection, bringing f_detect phase E × 76 plus the austeer arm. sadi_s20 has opened.
  - The fork's guards: a rung is skipped only once its own R2 verdict (and R3 verdict, if it is a base) is determined, and
    partial rungs' R2/R3 rates use the full 24.
  - CLARIFICATION, made before any MERA selection: ties go to the weaker dose in each method's dose order. For MERA that is the
    larger α (consistent with the 21:15 MERA order, α descending = weaker first). f_select's numeric tie-break is corrected
    to match; nothing changes for the other five methods.
- 09:32 Selection-determined skip (h-c4 suggestion, bookkeeping, no decision change).
  - Rung X's unclaimed units are skipped when X can no longer win: best(X) = successes + pending, compared with a complete,
    eligible rung Y of the same method.
    - Y of lower dose: X is out if best(X) ≤ reward(Y).
    - Y of higher dose: X is out if best(X) < reward(Y).
  - Excluded rungs are marked partial in the dose-response table.
  - Now excluded: caa_s2 (17 ≤ caa_s0.5's 19) and austeer_s50 (12 < 14). That saves about 5-6 worker-h. mera_s0.001 stays.
- 09:19 tick: F phase S 300/504 done + 59 skipped at 09:09.
  - Throughput: 12 units/h over the last 2 h, vs 24/h over 12 h. Causes: long level-2 units, 5 workers since v4.7, and rolling
    restarts in progress.
  - Unit-time means: caa_s2 22.2 min, mera 18-19, cast 37-38, others 6-11.
  - Remaining phase S:
    - CAA s2 10, MERA 0.001 10, AUSteer s50 10
    - SADI s10 13 (+ s20 24 if it opens), ITI s10 13 (+ s15 24)
    - CAST s0.5 17 + s0.25 24
    That is about 44 worker-h. The CAST critical path is about 41 units × 33 min over 2 slots, about 11 h, so S ends about
    20:00-21:00.
  - Phase E (about 532 units, about 80 worker-h) overlaps from the first selection on, so the F-run likely finishes around
    11-19 10:00-14:00.
  - Told the user the scope can be cut (e.g. retail phase E on 25 tasks) if they want it sooner. Default: full scope continues.
  - failed 0, OOM 0 new. Proxy: 1,817 CLI calls, $6.45 since v4.1.
- 08:57 Deployed (scheduling only): per-method selection (f_select --per-method), phase E appended per method, pool v4.8 with
  phase S claimed ahead of phase E, and loop f_loop2.
  - A method selects once all its TRAIN units are resolved, no R3 extension is still owed, and f_detect TRAIN is complete.
  - A .failed unit waits for its retry and is never counted as 0.
  - Phase E: f_detect × 76 at the first selection, then each chosen strength × 76, with retail and airline interleaved.
  - GPU2 runs phase-S FF exclusively ahead of phase-E non-FF; accepted, since the CAST tail is the critical path.
  - GPU2 retail memory check happens after the first 3 retail units (STOP_w6 if the margin is under 2 GiB).
  - Pending TRAIN at 08:57: caa 10, mera 10, austeer 10, sadi 37, iti 38, cast 41. The first selection (with the f_detect
    phase-E arm) is expected in 1-2 h.
  - The austeer_s50 and s20 flags were already verdicted FAITHFUL; the note goes into austeer's selection record.
- 08:49 tick: F phase S 296/480 done + 59 skipped at 08:39.
  - R3: f_cast_s0.25 appended (24 TRAIN units; cast_s0.5 reached ≥ 5/24 degenerate).
  - Level 2 (TRAIN reward): sadi_s10 7/11, iti_s10 7/10, caa_s2 7/12, mera_s0.001 9/14, austeer_s50 2/13, cast_s0.5 5/7.
  - GPU5 3 procs (32 GB), GPU2 2 procs (20 GB). No new OOM; failed 0.
  - Change requested (scheduling only): per-method selection, with phase E appended per method as soon as that method's rungs
    complete; f_detect phase E goes in with the first method. This keeps CAST's long tail from holding back everything else.
  - ETA S 17:00 (monitor; CAST's s0.25 tail extends that); E then overlaps.
  - Proxy: 1,762 CLI calls, $6.12 since v4.1.
- 08:19 tick: F phase S 289/480 done + 59 skipped at 08:09.
  - v4.7 is live: GPU5 runs w2-w4 (34 GB), GPU2 runs w5/w6 (20 GB); w1 retired; no new OOM.
  - The failed airline_14_f_caa_s2 is on its one retry (w5, GPU2, since 07:57).
  - Level 2 (TRAIN reward): sadi_s10 7/10, iti_s10 7/9, caa_s2 7/11, mera_s0.001 7/12, austeer_s50 2/12, cast_s0.5 5/6.
  - retail: phase E only. failed 0 after the retry move, stuck 0.
  - ETA S 16:14 (monitor; 5 workers now). Proxy: 1,713 CLI calls, $5.86 since v4.1; meta retries 14, all resolved.
- 07:56 Pool v4.7 (backup pool.py.pre_f47), the OOM root-cause fix.
  - Cause: each process keeps its own model copy resident (about 8.7 GiB + 0.5 context, even when idle), and the caching
    allocator never shrinks (no empty_cache; a process that had run sadi still held 13.2 GB on its next unit). Four GPU5
    processes therefore sit at about 37 GiB before activations, and a running-unit rule cannot protect them.
  - Fix:
    - MAX_PROCS: GPU5 3, GPU2 2 (registry; an over-cap worker waits holding no GPU memory).
    - gc + empty_cache after every unit, with a reserved_after_gb field.
  - w1 retired; GPU5 now runs w2-w4.
  - The only OOM since 21:09 was airline_14_f_caa_s2. Its marker is archived (claims_failed_archive/...oom_1118_0749, partial
    outputs *.sim_oom/*.tel_oom) and the unit is retried once.
  - Phase E watch: retail peaks on GPU2. If the margin is under 2 GiB, run GPU2 with 1 process for retail.
- 07:49 tick: F phase S 281/480 done + 59 skipped.
  - FAILED 1: airline_14_f_caa_s2 hit a CUDA OOM on GPU5 at 07:49. 47.2 of 47.4 GiB were in use by 2 FF units (13.4 + 12.9 GB)
    and 2 non-FF units (10.9 + 10.0 GB); long prompts push non-FF to about 11 GB.
  - Mitigation: STOP_w1, so GPU5 drops to 3 workers after w1's unit. The fork will add a memory-aware rule (at most 3 GPU5 units
    while 2 FF are active), then retry the failed unit once and restart w1.
  - Level 2 (TRAIN reward): sadi_s10 6/8, iti_s10 6/8, caa_s2 7/9, mera_s0.001 6/10, austeer_s50 2/11 (TOOLERR 10), cast_s0.5
    5/6 (4 with a capped turn).
  - stuck 0. ETA S 15:46 (monitor). Proxy: 1,667 CLI calls, $5.68 since v4.1; meta retries 14, all resolved.
- 07:19 tick: F phase S 275/480 done + 59 skipped at 07:09 (+8). About 146 units remain, mostly level 2.
  - Level 2 (TRAIN reward): sadi_s10 6/8, iti_s10 5/7, caa_s2 7/9, mera_s0.001 6/9, austeer_s50 2/8 (one 60.8 min loop unit),
    cast_s0.5 5/5.
  - The 51 min austeer_s50 unit ended at the cut (60.8 min); no stuck units.
  - retail: phase E only. failed 0.
  - ETA S 14:18 (30 worker-h) / E about 05:00-08:00 (11-19), at about 10 min/unit for 532 units over 6 workers.
  - Proxy: 1,624 CLI calls, $5.47 since v4.1; meta retries 14, all resolved.
- 06:49 tick: F phase S 267/480 done + 59 skipped at 06:39 (+6 only).
  - Long units are running:
    - w1 airline_9 mera_s0.001: 56 min
    - w3 airline_9 austeer_s50: 51 min, where s50's mean is 1.7, so likely a loop
    - w5 airline_10 mera_s0.001: 35 min
    The 1 h tau2 cut is the protocol; units are stuck only past about 80 min.
  - Level 2 (TRAIN reward): sadi_s10 6/7, iti_s10 5/7, caa_s2 5/7, mera_s0.001 5/6, austeer_s50 2/6, cast_s0.5 5/5 (3 with a
    capped turn; REPEAT flag 4 vs detect 0, so watch R3 for s0.25).
  - retail: phase E only. failed 0.
  - ETA S 13:34. Proxy: 1,555 CLI calls, $5.19 since v4.1; meta retries 14, all resolved.
- 06:19 tick: F phase S 261/480 done + 59 skipped at 06:09 (+12, slower).
  - Level 2 is running (TRAIN reward): sadi_s10 5/5, iti_s10 4/5, caa_s2 4/6, mera_s0.001 5/6, austeer_s50 2/6, cast_s0.5 4/4
    (2 with a capped turn, gate on 37/47 turns, max 51 min).
  - retail: phase E only. failed 0, stuck 0.
  - ETA S 12:16 (24 worker-h left; FF 18 h / 3 slots).
  - Proxy: 1,517 CLI calls, $4.85 since v4.1; meta retries 14, all resolved.
- 06:02 austeer_s50 check (h-c4 heads-up): reward 2/6 vs detect, unit time 1.7 min, 0 caps.
  - Episode-level read vs f_detect: well-formed text and valid tool calls, no empty or garbled turns.
  - The low reward comes from rash, policy-skipping actions:
    - t0: cancels right after reading the reservation.
    - t1: uses the user_id as a reservation_id.
    - t3: answers about baggage, then the user transfers.
  - Verdict: dose effect of the method (over-steering), not a harness break. Selection handles it; no action.
- 05:49 tick: F phase S 249/480 done + 59 skipped at 05:39 (+25).
  - Complete rungs (TRAIN reward /24):
    - detect 16
    - caa_s0.5 19, caa_s1 17
    - mera_s0.661 14, mera_s0.331 13
    - sadi_s5 16, iti_s5 17
    - austeer_s10 14, austeer_s20 14
    - cast_s1 ineligible
  - Running rungs: caa_s2 4/5, mera_s0.001 4/4, sadi_s10 2/2, iti_s10 1/1, austeer_s50 2/5 (2 tool errors), cast_s0.5 3/3.
  - retail: phase E only. failed 0, stuck 0.
  - ETA S 10:36 (19 worker-h left). Phase E is appended right after selection.
  - Proxy: 1,469 CLI calls, $4.65 since v4.1; meta retries 13, all resolved.
- 05:19 tick: F phase S 224/480 done + 59 skipped at 05:09 (+28 in 30 min).
  - airline TRAIN per-cond:
    - sadi_s5 16/23, iti_s5 17/23, caa_s1 17/23, mera_s0.331 12/20, austeer_s20 14/23
    - cast_s0.5 3/3 (1 cap, not degenerate; gate on 22/29 turns)
    - level 0: detect 16/24, caa_s0.5 19/24, mera_s0.661 14/24, austeer_s10 14/24
  - Open now: caa_s2, mera_s0.001 (level 2), austeer_s50, sadi_s10, iti_s10.
  - The w3 mera unit that had run 61 min ended normally (tau2 cut).
  - retail: phase E only. failed 0, stuck 0.
  - ETA S 12:42. Proxy: 1,341 CLI calls, $4.29 since v4.1; meta retries 12, all resolved.
- 04:49 tick: F phase S 196/480 done + 59 skipped at 04:39.
  - airline TRAIN per-cond: sadi_s5 13/20, iti_s5 15/20, caa_s1 11/16, mera_s0.331 8/14, austeer_s20 10/16 (level-0 rows
    unchanged).
  - cast_s0.5 started under v4.6: 1/1 so far, NOT degenerate (5.2 min, gate on 5/7 turns). The extension looks usable.
  - Watch: w3 airline_20_f_mera_s0.331 has run since 03:48 (61 min). tau2's 3600 s episode cut plus setup gives unit times up
    to about 73 min (mera max 72.7). Treat it as stuck only past about 80 min.
  - retail: phase E only. failed 0.
  - ETA S 12:28. Proxy: 1,243 CLI calls, $4.08 since v4.1; meta retries 10, all resolved.
- 04:21 Pool v4.6 deployed (backup pool.py.pre_f46; scheduling only):
  - GPU5 claims CAST FF first, then other FF, then non-FF.
  - GPU2 claims non-FF first, then CAST FF, then other FF.
  - Applies to all f_cast units, which in phase E means the chosen CAST strength too.
  - Sim: 6/6 CAST units started before the last sadi/iti unit (v4.5: 0/6). Invariants hold.
  - Rolling restarts of all 6 workers between units.
- 04:19 tick: F phase S 183/480 done + 59 skipped at 04:09.
  - airline TRAIN per-cond: sadi_s5 10/17, iti_s5 10/15, caa_s1 11/15, mera_s0.331 8/13, austeer_s20 9/14 (level-0 rows
    unchanged).
  - austeer_s50 is open now.
  - Issue: cast_s0.5 had 0 started (queue tail). Asked the fork to put CAST extension units first in the FF claim order, so the
    R3 verdict comes early and cast_s0.25 (if needed) overlaps with sadi/iti instead of trailing at the end. Scheduling only.
  - retail: phase E only. failed 0, stuck 0.
  - ETA S 13:31. Proxy: 1,172 CLI calls, $3.80 since v4.1. Meta retries 10 (CLI "I'm Claude Code" role breaks), all resolved.
- 03:49 tick: F phase S 170/480 done + 59 skipped at 03:39.
  - airline TRAIN per-cond: detect 16/24, caa_s0.5 19/24, mera_s0.661 14/24, austeer_s10 14/24, sadi_s5 8/14, iti_s5 9/14,
    caa_s1 9/12, mera_s0.331 7/10, austeer_s20 7/11.
  - New gates: sadi_s10 and iti_s10 opened (≥ 13 non-degenerate determined).
  - Flag TOOLERR austeer_s20 (11 vs detect 0), checked: 9/11 come from ONE episode, task_14 book_reservation, retried with
    "Payment amount does not add up" (multi-certificate payment arithmetic). The others: 1 calculate with a date string, 1
    gift-card balance. These are genuine agent errors, not a harness bug. Verdict: FAITHFUL, no action.
  - retail: phase E only. failed 0, stuck 0.
  - ETA S 13:10 (monitor). Proxy: 1,092 CLI calls, $3.53 since v4.1; meta retries 8, all resolved.
- 03:19 tick: F phase S 161/480 done + 59 skipped (R2) at 03:09.
  - airline TRAIN per-cond: detect 16/24, caa_s0.5 19/24, mera_s0.661 14/24, austeer_s10 14/24, sadi_s5 8/13, iti_s5 9/12,
    caa_s1 7/10, mera_s0.331 6/8, austeer_s20 7/10. cast_s1 ineligible; cast_s0.5 queued (FF, 1 per GPU).
  - Watch: w1 airline_9 and w3 airline_10 f_mera_s0.331 have run 43-46 min, probably the date sweep. tau2's 1 h cut lands
    about 03:33/03:36, which is protocol.
  - retail: phase E only. failed 0, stuck 0.
  - ETA S 12:36 (monitor, 47 worker-h left now that skips are excluded). Flags: CAP/REPEAT cast, CAP caa_s1 2/10 (≥ 1 cap,
    not yet R2-degenerate).
  - Proxy: 1,023 CLI calls, $3.29 since v4.1. Meta retries 8, all resolved.
- 02:49 tick: F phase S 151/480 at 02:39.
  - R2 verdict: cast_s1 INELIGIBLE (12/12 degenerate, determined at 12/24). 11 unclaimed s1 units are skipped; cast_s1.5 and
    cast_s3 are skipped as "degenerate at lower dose". One s1 unit claimed before the verdict is still running (w2 airline_14).
  - airline TRAIN per-cond:
    - level 0 done: detect 16/24, caa_s0.5 19/24, mera_s0.661 14/24, austeer_s10 14/24.
    - level 0 running: sadi_s5 8/12, iti_s5 8/11.
    - level 1: caa_s1 6/7, mera_s0.331 5/6, austeer_s20 5/7.
    - cast_s0.5 (R3) queued.
  - retail: phase E only. failed 0, stuck 0.
  - ETA S 12:00-16:00 (fork) / 17:43 (monitor). Flags: CAP/REPEAT cast as expected.
  - Proxy: 961 CLI calls, $3.05 since v4.1. Meta retries now 8 (4 in the last 30 min, all from CLI "environment update /
    scratchpad / token count" injections), all resolved; 0 unresolved. Watch: act if any goes unresolved.
- 02:19 tick: F phase S, all 6 workers active on v4.5 (STOP files cleared).
  - Baseline units per GPU: GPU5 62, GPU2 43, so unpinning works.
  - airline TRAIN per-cond: detect 16/23, caa_s0.5 19/24 (done), cast_s1 5/10 (10/10 degenerate, gate 82/82), mera_s0.661
    14/23, sadi_s5 7/10, iti_s5 7/10, austeer_s10 14/23. Level 1: caa_s1 2/2, mera_s0.331 2/2, austeer_s20 1/1.
  - retail: phase E only. failed 0, stuck 0. GPU5 41 GB, GPU2 20 GB, both 100%.
  - ETA S 12:00-16:00 (fork) / 18:18 (the crude monitor counts cast_s1.5/s3 as pending). Flags: CAP/REPEAT cast as expected.
  - Proxy: 877 CLI calls, $2.83 since v4.1.
- 01:49 tick: F phase S 122/480 at 01:39.
  - airline TRAIN per-cond: detect 16/23, caa_s0.5 19/23, cast_s1 5/9, mera_s0.661 14/23, sadi_s5 7/10, iti_s5 7/9,
    austeer_s10 14/23. Level 1 has started: caa_s1 1/1, austeer_s20 1/1, mera_s0.331 running.
  - Open gates: caa_s1, austeer_s20, mera_s0.331, plus the cast_s0.5 extension.
  - retail: phase E only. failed 0, stuck 0.
  - Transitional idle: w5 on GPU2 is waiting for w6's exclusive airline_11 f_cast_s1 (since 01:14, ending about 02:10).
  - Rolling v4.5 restarts are pending (STOP_w1/w2/w4/w6 set, between units).
  - ETA S 13:04 (monitor) / 12:00-16:00 (fork estimate). Flags: CAP (detect included), REPEAT cast.
  - Proxy: 809 CLI calls, $2.54 since v4.1.
- 01:50 Pool v4.5 deployed 01:42 (backup pool.py.pre_f45); rolling restarts between units.
  - Premise check on live telemetry: CAST's condition was met at turn 0 in 11/11 episodes; MERA moved positions at turn 0 in
    24/24. So neither shares a prefix with detect.
  - Pinned: f_detect, h3_*, and any future non-baseline F condition such as J5.
  - Extra fix: the FF slot check now runs before taking ownership. GPU2 had been grabbing tasks it then couldn't run, which
    explains the 14:10 skew.
  - Phase E ownership goes to the least-owned GPU.
  - FF backlog:
    - cast_s1: 9/9 degenerate. R2 at 12 skips cast_s1.5, cast_s3 and about 10 remaining s1 units.
    - cast_s0.5: 24 ready.
    - sadi_s5: 10 done, 0 degenerate.
    - iti_s5: 9 done, 0 degenerate.
  - Non-FF ready: caa_s1 22, mera_s0.331 22, austeer_s20 23.
  - ETA S 12:00-16:00 (11-18); +4-8 h if cast_s0.25 is triggered. E follows.
- 01:45 AMENDMENT "affinity scope" (reverses the 01:32 decline).
  - Fork backlog: GPU2 owns 13/23 TRAIN tasks; its FF units (52 ready + 84 blocked) run serially and exclusively, so the tail
    was over 15 h.
  - Per-task GPU pinning exists for prefix pairing with f_detect. The always-on F baselines diverge from turn 0 and share no
    generated prefix, so pinning gives them no pairing benefit.
    - Now pinned: f_detect and future gated J5 only.
    - The six baselines and their extensions may run on either GPU; the GPU UUID is recorded per unit and the analysis
      stratifies by GPU.
  - Scheduling: GPU5 FF first (2 slots, 1 CAST cap); GPU2 non-FF first, with FF exclusive only when nothing else is
    claimable.
  - Phase E: new task ownership alternates between the GPUs.
  - Already applied at 01:34-01:35 (bookkeeping): rungs open on a determined verdict (caa_s1, austeer_s20, mera_s0.331 opened);
    pool v4.4 makes GPU2 claim non-FF first.
- 01:32 IDLE WORKERS (h-c4 01:29): w5 has idled since 01:14, w1 and w3 since 01:25.
  - Cause: the next rung opened only after the whole level 0 completed, and the remaining level-0 units were slot-limited FF.
  - Fix 1 (bookkeeping, no decision change): open a method's next rung once its current rung has ≥ 13/24 non-degenerate
    episodes (the R2 outcome is then determined). caa_s1, austeer_s20 and mera_s0.331 open now.
  - Fix 2 (scheduling): GPU2 workers claim non-FF first; FF starts on GPU2 only when no non-FF GPU2 unit is claimable.
  - Declined: moving GPU2-owned CAST units to GPU5, because it breaks per-task GPU affinity.
- 01:19 tick: F phase S 110/480 at 01:09 (25 units in the last 30 min).
  - airline TRAIN per-cond (level 0): detect 15/22, caa_s0.5 18/22, cast_s1 5/8, mera_s0.661 12/20, sadi_s5 6/9, iti_s5 6/8,
    austeer_s10 12/21.
  - Degenerate: cast_s1 8/8; the rest are low.
  - retail: phase E only. failed 0, stuck 0.
  - GPU5 48 GB at 100%; GPU2 21 GB at 43% (momentary).
  - ETA S 13:59 / E about 10:00-13:00 (11-19). Flags: CAP (same as before, detect included), REPEAT cast.
  - Proxy: 758 CLI calls, $2.34 since v4.1. Meta retries 4, all resolved. The 01:09 one was an in-character reply that
    mentioned the CLI's "scratchpad path"; the fresh retry handled it.
- 00:49 tick: F phase S 85/480 at 00:39.
  - airline TRAIN per-cond (level 0): detect 10/16, caa_s0.5 13/16, cast_s1 4/7, mera_s0.661 8/15, sadi_s5 6/8, iti_s5 6/8,
    austeer_s10 9/15.
  - Monitor CAP flags count episodes with ≥ 1 capped turn, and fire for detect too (4/16), so they reflect long later tasks
    rather than steering. R2 uses ≥ 2 caps. cast_s1 is 7/7 degenerate (gate 53/53 turns).
  - retail: phase E only. failed 0, stuck 0.
  - ETA S 15:36 (90 worker-h / 6) / E about 10:00-14:00 (11-19). Flags: CAP as above, REPEAT cast.
  - Proxy: 668 CLI calls, $2.07 since v4.1. meta retries 3, all resolved, 0 unresolved. The latest at 00:48 was Haiku
    refusing the role as "Claude Code"; the fresh retry fixed it.
- 00:19 tick (11-18): F phase S 74/480 at 00:09.
  - airline TRAIN per-cond (level 0): detect 9/14, caa_s0.5 11/14, cast_s1 4/6, mera_s0.661 7/13, sadi_s5 6/7, iti_s5 6/7,
    austeer_s10 9/13. sadi_s5 just finished its 8th unit (28.6 min).
  - Degenerate: cast_s1 6/6; caa/austeer/mera about 1-3 each; detect 0.
  - retail: phase E only. failed 0, stuck 0.
  - FF slots are used correctly: GPU5 runs 1 CAST + 1 ITI.
  - The slowdown is genuine: later airline TRAIN tasks have long dialogs (detect 24 min on airline_21, sadi 29, austeer 22).
  - ETA S 13:26 (monitor: 81 worker-h / 6 workers) / E about 06:00-10:00 (11-19), using phase-S unit times. Flags: none.
  - Proxy: 559 CLI calls, $1.73 since v4.1.
- 23:49 tick: F phase S 66/456 (+24 R3 units) at 23:39.
  - airline TRAIN per-cond (level 0): detect 8/13, caa_s0.5 9/12, cast_s1 4/5, mera_s0.661 6/11, sadi_s5 6/7, iti_s5 6/7,
    austeer_s10 8/11.
  - Degenerate: cast_s1 5/5 (gate 34/34 turns). R3 has appended f_cast_s0.5 (24 units, labelled extension). caa_s0.5 2/12,
    austeer 2/11, mera 1/11, detect 0/13.
  - Monitor flag: REPEAT cast_s1 5 vs detect 1 (already covered by R2/R3).
  - retail: phase E only.
  - failed 0, stuck 0. The CAST cap is working: SADI is running again (w4 airline_10_f_sadi_s5).
  - GPU5 39 GB, GPU2 21 GB, both 100%.
  - ETA S 11:16 (monitor, 6 workers, 70 worker-h left) / E about 01:00-03:00 (11-19).
  - Proxy: 493 CLI calls, $1.49 since v4.1.
- 23:21 Pool v4.3 deployed (backup pool.py.pre_f43; scheduling only, argv unchanged):
  - At most 1 f_cast per GPU, taken before the FF slot. Tests PASS.
  - Rolling restarts of w1-w4 between units; the 2 running CAST units are untouched.
  - Transition caveat: until those 2 finish, one extra CAST could start once an FF slot frees.
  - The monitor's ETA now divides by 6 workers.
- 23:19 tick: F phase S 56/456 at 23:09.
  - airline TRAIN per-cond (level 0): detect 7/11, caa_s0.5 8/10, cast_s1 3/3, mera_s0.661 6/9, sadi_s5 6/7, iti_s5 6/7,
    austeer_s10 7/9.
  - Degenerate: cast_s1 3/3, caa_s0.5 1/10, austeer_s10 1/9, others 0.
  - retail: phase E only.
  - failed 0, stuck 0. 6 workers: GPU5 47 GB, GPU2 21 GB.
  - Bottleneck: both GPU5 FF slots are held by 45-55 min CAST units. sadi/iti have stalled at 7 since 22:39; throughput is about
    0.33 units/min.
    - Fix requested: at most 1 concurrent f_cast per GPU (scheduling only).
    - The monitor's ETA is to divide by 6.
  - ETA S about 09:30-10:00 (11-18). E about 01:00 (11-19) at about 10 min/unit; it depends on the chosen CAST and MERA
    strengths.
  - Flags: none. Proxy: 426 CLI calls, $1.26 since v4.1.
- 23:02 f_dose bookkeeping (h-c4 suggestion; no decision changes):
  - R2 determined-ineligible at ≥ 12/24 degenerate: the unclaimed units of that strength are skipped and logged, never deleted
    or killed.
  - R3 extension queued as soon as the lowest value is ≥ 5/24 degenerate.
  - Eligible strengths still run all 24 units.
  - Not adopted: a sequential "6/6" rule, which would be post-hoc on CAST data.
  - Status: cast_s1 3/3 degenerate (gate on 20/20 turns, about 55 min per unit).
- 22:49 tick: F phase S 46/456 at 22:39.
  - airline TRAIN per-cond (level 0): detect 6/8, caa_s0.5 7/9, cast_s1 2/2, mera_s0.661 6/6, sadi_s5 6/7, iti_s5 6/7,
    austeer_s10 6/7.
  - Degenerate so far (R-def): caa_s0.5 1/9, cast_s1 2/2 (gate on 10/10 turns), austeer_s10 1/7, others 0.
  - retail: phase E only.
  - failed 0, stuck 0.
  - 6 workers: GPU5 46 GB at 100%; GPU2 19 GB at 100% (w5 + w6).
  - ETA S about 08:30-10:00 / E about 20:00-22:00 (11-18). The monitor still divides by 5 workers. CAST is heading for the R3
    extension (0.5×, 0.25×).
  - Flags: none. Proxy: 368 CLI calls, $1.01 since v4.1.
- 22:35 w6 started on GPU2 under rule (b) (pool v4.2; backup pool.py.pre_f42).
  - Measured allocated peaks: GPU2 FF 11.25 GB and non-FF 8.81 GB; GPU5 FF 11.22 GB and non-FF 9.51 GB.
  - Rule (a) passed only nominally: nvidia-smi adds context and cache, and 26-32k-token prompts reach 12.1-12.8 GB in FF. So
    rule (b) applies: a GPU2 FF unit runs exclusively, while non-FF units share the GPU.
  - The 3-worker sim showed 0 FF overlap and 19 non-FF overlaps.
  - Live: w5 detect + w6 caa, about 9 GB each.
  - Now 6 workers in total. The ETA should improve by about 10-15% (next tick).
- 22:19 tick: F phase S 35/456 at 22:09.
  - airline TRAIN per-cond (level 0): detect 6/8, caa_s0.5 6/7, sadi_s5 5/6, iti_s5 5/6, austeer_s10 5/6, cast_s1 1/1, mera_s0.661
    1/1.
  - cast_s1: 1 capped turn, gate on 5/5 turns, 18 min. mera_s0.661 moved 92% of positions, 0 caps.
  - retail: phase E only.
  - failed 0, stuck 0. Degenerate (≥ 2 caps / sweep / max_steps): 0 so far.
  - GPU5 4 workers 100% (44 GB); GPU2 w5 72%.
  - ETA S 07:49 (monitor, 48 worker-h left) / E about 19:00 (11-18). Flags: none.
  - Proxy: 298 CLI calls, $0.79 since v4.1.
- 21:49 tick: F phase S 25/456 at 21:39.
  - airline TRAIN per-cond (level 0): detect 5/5, caa_s0.5 5/5, sadi_s5 5/5, iti_s5 5/5, austeer_s10 5/5. cast_s1 and
    mera_s0.661 are just unheld (0 done).
  - retail: phase E only.
  - failed 0, stuck 0. caps 0. The monitor's within-turn "rep" also fires on detect, so it is not used.
  - GPU5 w1-w4 at 100%; GPU2 w5 at 97%. All 5 workers are on pool v4.1.
  - ETA revised from the measured rate of about 0.8 units/min: S about 06:30 / E about 17:00 (11-18). R2 pruning may shorten
    it; CAST/MERA degenerate tails may lengthen it.
  - Flags: none. Proxy: 265 CLI calls, $0.68 since v4.1, 1 meta retry (resolved).
- 21:40 CAST/MERA root-cause verdicts: both FAITHFUL, i.e. dose effects of the authors' code and settings, not bugs.
  - CAST:
    - Upstream IBM MalleableModel gives an identical condition, similarity and 64-token output.
    - The comparator matches upstream (lines 431-432 / 169-170).
    - The gate is weak, not inverted: it fires on 52/56 positives, 37/56 negatives and 10/10 clean first turns; AUC 0.718,
      a documented limitation.
    - The ×1.5 push adds 8.5-18% of the residual norm at each of 9 layers, so turn-0 caps are a dose effect.
  - MERA:
    - The edit is bitwise equal to upstream MERA.steer.
    - The probe is oriented error = high on 32/32 layers.
    - Under the authors' runner flags it fires on 91-100% of positions at every α; the date sweep is that always-on, all-layer
      push.
  - Action: pool v4.1 (MERA ext α 0.70/0.72), rolling restarts, w5 on GPU2. The holds are lifted; CAST starts at s1 and MERA
    at α 0.661 under R1-R4.
- 21:19 tick: F phase S running since 21:09 (dose level 0). w1-w4 GPU5 at 100% (39 GB); GPU2 runs the CAST root-cause check
  (MERA next), w5 not started. failed 0, stuck 0. ETA S about 03:30 / E about 11:00 (11-18). Flags: CAST/MERA held pending
  verdicts. The proxy's v4 meta-retry fired once (21:17, CLI "environment update" again) and resolved on a fresh session. That
  is the intended behaviour; 0 unresolved. Proxy: 193 CLI calls, $0.55 since v4.1.
- 21:15 tick: F phase S LAUNCHED 21:09: 0/456 done. w1-w4 on GPU5, both GPU5 full-forward slots in use (SADI, ITI). GPU2:
  the CAST/MERA root-cause checks (w5 joins after them). airline per-cond: starting at dose level 0. retail: phase E only.
  failed 0, stuck 0. ETA S about 03:30 / E about 11:00 (11-18). Flags: CAST and MERA held pending verdicts.
  - Smoke details (fork): the MERA "loop" is a search_direct_flight date sweep, one date per turn for about 95 turns, never
    answering; not identical outputs. CAST's gate fired on 4/4 turns (similarity 0.034-0.079).
  - Final R-rules:
    - Degenerate episode = ≥ 2 capped turns, OR ≥ 10 consecutive same-tool turns, OR max_steps. f_detect's rate is reported
      as the reference; a single capped turn occurs in 8% of unsteered H1 episodes.
    - MERA runs α descending (0.661 first). Its low-end extension is α 0.70, then 0.72.
  - H3-C archived to pilot_h3_gated: 73 task dirs, nothing deleted.
- 21:02 F smoke degeneration found (telemetry pilot_smoke_f, airline t9):
  - cast_s1.5: 4/4 turns at the 4,096 cap, starting at turn 0. Reward 1 only because gold needs no write.
  - mera_s0.331: over 100 turns of identical 61-token outputs, a loop.
  - austeer_s20: 1/19 turns capped.
  - sadi (32 edits/turn), iti and caa: clean.
  Pre-registered before phase-S data, sent to the fork as "phase-S dose ordering":
  - R1: ascending strength per method.
  - R2: skip higher strengths once a strength degenerates in ≥ 50% of its 24 TRAIN episodes.
  - R3: if the lowest grid value degenerates in ≥ 20%, add 0.5× and then 0.25× (a labelled amendment, TRAIN only).
  - R4: strengths degenerating in ≥ 50% are ineligible for selection.
  Unit minutes on the smoke: detect 5.2, caa 8.0, iti 6.9, sadi 15.1, austeer 14.9, cast 22.1, mera > 37.
- 20:49 tick: F-run 0/988, not launched; the F smoke (TRAIN airline 9, 7 conditions at middle strength, GPU 5 s1-s4, started
  20:20) has 6/7 done, every one with reward 1. Messages: detect 24, caa 28, cast 10, iti 26, sadi 30, austeer 40. MERA is still
  running. failed 0, stuck 0. GPU2 idle; GPU5 smoke. ETA S about 03:15 / E about 10:30 (11-18), counted from launch after the
  smoke. Flags: none. Proxy: 168 CLI calls, $0.51 since v4.1.
- 20:19 tick: H3 69/500 STOPPED (archived as an ablation at F launch). F-run 0/988, not started. airline per-cond: none yet.
  retail per-cond: none yet. failed 0, stuck 0. GPU2 idle (gates done); GPU5 w1 on its last H3 unit (airline_10_h3_caa, 1 h
  cut about 20:21), then the F smoke (about 15 min) and install_f.sh. ETA S about 02:45 / E about 10:00 (11-18), before
  degenerate tails. Flags: none. Proxy since v4.1: 144 CLI calls, $0.44.
- 20:12 tick: H3 69/500 STOPPED (user 19:27); F-run not started yet. airline/retail per-cond: none yet. failed 0, stuck 0.
  GPU2 idle (CAST/MERA fit done 20:06), GPU5 w1 finishing its last H3 unit (airline_10_h3_caa, about 20:21). ETA: F smoke
  about 20:21-20:35, then launch; phase S 456 + phase E 532. Flags: none.
- 11-17 20:12 USER DECISION (about 20:05, via h-c4, after h-c4 retracted its 19:5x over-reading):
  - The faithful F-run is the base, through the authors' code.
  - Fix clearly abnormal baselines at the root: no-op edits; high cap or repeat; reward collapse; infra errors; a selected
    strength at the grid edge; an artifact failing validation. Each deviation is a labelled amendment, and only the affected
    units are rerun.
  - Goal: finish ALL baseline experiments on airline + retail. GPUs 2 and 5 only.
  - The 5-layer J5 is still planned but does not block the baselines.
  - h-c4 monitors read-only at :23/:53. Tick lines here use h-c4's format.
  - Prep is done (fork, 20:06):
    - CAST/MERA fitted. CAST F1 0.717 is in-sample (TRAIN only); this is a documented limitation.
    - Pool v4 tests PASS.
    - (b) edit-position equality PASS for CAA, AUSteer and MERA.
    - (a) option F equivalence PASS: CAST 4/4, ITI 4/4, SADI 7/7.
    - The old chunked CAST read only the first chunk; the old chunked ITI added one extra edit and degenerated at 27.6k tokens.
  - GO given: the smoke runs when w1 ends; install_f.sh follows on PASS. Phase E is appended automatically after selection.
- 11-17 16:25 H1 + H2 done. Asked the user to choose H3-C scope: airline-only, 6 conditions × 50 tasks run concurrently, about
  4-5 h and about $3; or both domains, about 8-10 h and about $5.
  Without approval, run nothing large. GPUs 2 and 5 idle.
- 11-17 16:50 Proxy v4.1 (pid 20032): single-flight per cache key.
  - Why: H3-C runs 6 conditions of one task concurrently. Identical user requests arrive at the same moment, and unseeded Haiku
    would answer each differently, so pairs would diverge before any intervention.
  - Test: SINGLEFLIGHT PASS (6 concurrent requests -> 1 CLI call).
  - PROMPT_VERSION stays 4.
  - H3-C pairing check: all conditions must be token-identical up to the first steered turn (the d7s/cf invariant checker).
- 11-17 17:25 USER APPROVED H3-C, airline + retail (600 units). The user asked why I had been idle; lesson below.
  - Spec sent to the fork:
    1. Cross-GPU determinism check (GPU 5 vs the GPU 2 A5000).
    2. Per-task concurrent groups with a barrier.
    3. Group smoke on an airline TRAIN task.
    4. Launch.
  - Revised ETA: the barrier makes every group wait for its slowest condition, so 100 groups take about 10-14 h.
  - Haiku cost is below 600 × $0.01, because the single-flight proxy shares user turns until the conditions diverge.
  - Lesson: when blocked on a user decision, say so in the report as an explicit, prominent question, not a one-line status;
    and offer to start the recommended option by default.
- 11-17 18:19 H3-C LAUNCHED (5 conditions, 500 units).
  - The 18:17 install first failed its own queue-size check; it was fixed and installed at 18:18.
  - pool.py backup is pool.py.pre_h3. GPU affinity is recorded in claims/gpu_<domain>_<task>.json; per-unit metadata in
    pilot/h3_runs/.
  - Workers are starting staggered: w1 and w2 are up.
  - Proxy: 36 requests, 14 CLI calls, 22 cache hits, so single-flight is working.
  - The SADI fix gate is pending: probe/logs/sadi_equiv.log, 6 trigger prompts of 5-12k tokens, arms A/B/C/D plus a detect
    chunked-vs-full control.
  - Amended before the result (18:25): token identity is required only where chunking alone doesn't change detect's tokens.
    Also required: the same edit position and units, the edited value within bf16 tolerance, and C == B exactly.
  - The w6 GPU 2 slot joins after the gate.
  - 18:28 SADI chunk-aware fix FAIL on (iii). Detail:
    - (i) PASS 6/6.
    - (ii) PASS bitwise: 32 edits per prompt, same units, post-edit hidden identical in 192/192 layer edits.
    - (iii) failed on 2/6 prompts where detect chunked == detect full.
    Diagnosis: the edit is correct, but the large L31 edit (about 230 abs) creates near-ties, and bf16 differences between
    chunked and full prefill flip them.
    D reproduces 0 edits, so the bug is confirmed. No SADI agent episode had run in the pilot before the H3 smoke; the earlier
    "SADI baseline" was effectively never run.
  - Decision 18:30, option F: on SADI-active turns, skip the prefix cache so upstream's single full-prompt forward runs
    (= upstream exactly). Deploy only if all three hold:
    - SADI_FULL F == B on 7 prompts;
    - GPU 2 peak ≤ about 11.5 GB per process (otherwise GPU-2 SADI units run while that GPU's other worker is idle);
    - h3_detect tokens unchanged across the backend swap on both GPUs.
    Then append 100 h3_sadi units pinned to each task's owner GPU. Otherwise drop SADI.
  - 18:35 Results:
    - SADI_FULL PASS on 7/7 prompts, up to 26.5k tokens.
    - Peak 12.8 GB on the 26.5k prompt, which is > 11.5. So GPU 2 stays at the single worker w5 (w6 never starts), and a per-GPU
      SADI slot allows at most 1 h3_sadi per GPU at a time.
    - Deploy plan approved: backups, swap, STOP_w4, condition-3 token check per GPU, rolling restarts, then append 100 h3_sadi.
      Wall time is about +15%.
  - H3 status at 18:30: 10/500 done, 0 failed, pairs 7/7 PASS, no flags.
  - 18:49 tick:
    - H3 20/500 at 18:40, 0 failed, no flags. Rate is about 1 unit/min, so the 500 finish around 03:00 and the +100 SADI units
      around 05:00.
    - SADI deploy steps a and b done (backups made, live backend/pool swapped); STOP_w4 is pending for step c.
    - Proxy: 277 requests, 70 CLI calls, 207 cache hits; $0.14 since v4.1.
  - 18:57 fork report:
    - Pool v3 SADI slot tests PASS: max 1 concurrent per GPU, with a control showing that the detector catches overlap.
    - The fork stopped its own deploy script: a 60-min timeout rollback could have started a duplicate w4. It resumed with a
      no-limit wait.
    - h3_jlens degenerates on airline 3: the trigger fires at turn 5, then the turns cap at 4,096 in a loop ("me to ask me to
      ask"). Same failure as the D7 α 0.8 smoke. Pre-set dose, no change.
    - The episode wall-clock --timeout 3600 still applies (as in H1). Degenerate episodes end at about 1 h, which censors
      length only; keep it for all conditions. No early stop rule (in the smoke, caa capped and still got reward 1).
    - I asked for per-condition wall time and an ETA in the monitor. If the projected finish is past 09:00 on 11-18, consider
      asking the user to reorder.
  - 19:05 H3 45/500, 0 failed, no flags.
    - Unit min mean/max: detect 3.7/8.6, jlens 4.2/9.0, caa 3.8/10.2, iti 3.4/7.5, austeer 3.1/7.6.
    - jlens cap episodes: 1/9.
    - ETA 11-18 01:41 including the SADI 100, before any degenerate tails. The monitor flags ETA_PAST_0900.
  - 19:19 tick: H3 58/500 at 19:10, 0 failed, no flags. Conditions are so far within ±1 of each other (about 11-13 units each).
    - w4 is still on the degenerate airline_3_h3_jlens. tau2's 1 h cut lands about 19:38; the SADI deploy step c follows.
    - Proxy since v4.1: 483 requests, 125 CLI calls, $0.33.
    - Disk 55 GB. All PC paths OK.
- 11-17 18:10 H3-C group smoke (TRAIN airline 9, 6 conditions at once): HOLD, then decisions by h-04.
  - The determinism claim was corrected. GPU 5 and GPU 2 diverge on a near-tie (same 6,238-token input: 466 vs 731 tokens).
    Each GPU is deterministic on its own.
    -> Per-task GPU affinity: all units of a task run on one GPU, recorded per task. No cross-GPU pairing.
  - SADI was a no-op. official/sadi.py edits only when a single forward covers the whole prompt, but the agent prefills in
    4,096-token chunks, so applied_edits = 0. ALL EARLIER PILOT SADI RUNS WERE NO-OPS. Tell the user, chat only.
    -> Chunk-aware fix, gated: it must be equivalent to upstream's full-prompt forward on ≥ 3 logged trigger prompts (one
       > 4,096 tokens). PASS: append h3_sadi pinned to each task's GPU. FAIL: drop SADI.
  - Launch the other 5 conditions now (500 units).
  - CAA hit the 4,096 cap on its first steered turn at matched multiplier 3.0. Kept as pre-set; counted as degeneration.
  - The other methods applied: jlens 202 positions, iti 64 edits, austeer 31,929, caa 4,100. Smoke reward 1/1 in all.
- 11-17 17:48 fork determinism check (probe/det_gpu.sh): greedy agent generation matches within GPU across processes, across
  GPUs (5 vs the GPU 2 A5000), and against the original H1 run (12/12). One group of 6 per task (w1-w4 GPU 5, w5-w6 GPU 2) is
  fine. The fork is now implementing the group barrier and smoke.
- 11-17 17:19 tick: idle, still waiting for the user's H3-C scope. All paths OK. Disk 55 GB.
- 11-17 16:19 tick: idle, waiting for the user's H3-C scope. The retail rerun was pushed (fa1a3b9). Proxy/tunnel/push loop OK.
  Disk 55 GB free.
- 11-17 10:35 errguard passed (exploratory, rests on t21). Requested the held-out confirmatory run.
- 11-17 08:16 D7s failed its exploratory criterion. The refusal signal is ~ the post-error context. Launched errguard (structural guard)
  as the last exploratory test. Then summarize for the user. Main robust findings so far:
  (1) gold-match labels are contaminated by the user simulator;
  (2) no decision-point separability for wrong writes (4B and 9B users);
  (3) oracle labels work;
  (4) the main agent-attributable risk is a silent retry after a tool error;
  (5) J-lens refusal steering has no non-degenerate dose;
  (6) reproducibility pitfalls (user RNG, max_time) were found and handled.
- 11-17 06:44 D7s interim, 24/42 pairs: violations 8 vs 8, reward 15/24 vs 16/24, 2 regenerations.
  LIVE detection AUC is 0.48 overall (8 violations / 42 ok). By type:
  - task 21 retry_switch ×3: ranks 13, 14, 14. Strong, but just above R10, so the gate never fired.
  - task 39 cancel_ineligible ×5: ranks 99-330. No signal.
  Reading: the refusal-mass signal holds for "silent retry after a tool error" (4B/9B users, train/held-out, live). It does NOT
  replicate for cancel-eligibility errors; the offline cancel AUCs were small-n.
  Recommended next step for the user, not launched while D7s holds GPU 5: a combined gate = previous tool message is Error
  AND write AND refusal rank ≤ ~20 -> self-check note, on retry tasks {10, 15, 17, 21} (+ held-out 16, 32 for evaluation).
- 11-17 06:14 D7s interim, 16/42 pairs (13 PASS, 3 TIME_CUTOFF, 0 FAIL). Oracle violations 4 vs 4 in both conditions, reward 10/16
  in both, 2 regenerations. LIVE detection from online-logged ranks (d7obs write turns): AUC 0.685 (4 violations / 31 ok).
  Violation ranks are 13, 14, 14 and 167: three sit just above R10, so the gate never fires on them. Live detection looks weaker than
  offline (0.77-0.87); the per-tool mix differs (the stress set is cancel-heavy).
- 11-17 05:13 D7s interim, 7/42 pairs (pairing: 5 PASS, 1 TIME_CUTOFF, 1 incomplete; 0 FAIL).
  Oracle violations: d7obs 3 (in 2 episodes) vs d7c10 3 (in 2). Reward 4/7 in both conditions. 1 regeneration.
  Live R10 gate in d7obs: tp 0, fp 1, fn 3, tn 15, so it has missed every live violation so far. That fits R10 covering mainly
  retry_switch (ranks 3-5) and not ineligible cancels (ranks 35-93). Expect a null primary unless retry cases dominate.
- 11-17 04:15 BUG in my user server: seeding sat outside the generate lock. With concurrent workers, sampled (T>0) user turns
  were not reproducible, so paired d7obs/d7c10 diverged at user turns even with 0 regenerations. Detect (greedy) is unaffected.
  The u9b fitx episodes are valid but not reproducible.
  Fix script reserve/usersim/fix_usersim_rng.sh: STOP the workers, restart the server with seeding inside the lock, run a
  determinism check, archive the pre-fix D7s outputs to pilot_d7s_prefix, restart the workers. All 84 D7s units rerun; ETA about 07:00.
  The first 4 pre-fix pairs: 0 violations and 0 regenerations in both conditions.
- 11-17 04:20 The fork will run a read-only pairing-invariant check after the restart: d7obs_sk and d7c10_sk must be token-identical
  up to the first d7c10 regeneration, or across the whole episode if nothing regenerated. It checks the fix under 4-worker load;
  results go to changes.md. The final D7s report includes the count of invariant-passing pairs.
  Checker validated on the pre-fix data: all 5 pre-fix pairs FAIL, diverging at user turns, so it catches the race.
  Live note path confirmed (pre-fix t21 s1, turn 15). A write right after a tool error ("Not enough seats") fired the gate at rank 6.
  Pass 1 was update_reservation_flights; pass 2 made no write and explained the seat problem.
  The checker loop (probe/d7s_pairs_loop.sh) starts after my fix script moves the pre-fix outputs.
- 11-17 04:45 After the RNG fix: 3 pairs checked, 2 PASS, 1 FAIL (t10 s1, turn 5).
  - Cause: the agent's max_time=300 s wall-clock cut. Both generations are token-identical for 3884 tokens, no EOS; the cut
    point depends on GPU load. Inputs and gate ranks are identical, so the RNG fix holds.
  - Decision (option 1): the checker labels such pairs TIME_CUTOFF (censored, not FAIL) and keeps going. Real FAILs still stop it.
    Pair statuses go to probe/d7s_pairs_status.json, and d7s_eval reports both all pairs and pairs without TIME_CUTOFF.
  - PROTOCOL FIX for any confirmatory run: drop max_time and rely on max_new_tokens. The wall-clock cut is a reproducibility
    hole in every condition (detect/fitx/baselines), not only D7s.
- 11-17 03:46 The fork was idle since 03:19 (after SMOKE_DONE, likely a permission prompt). h-04 reviewed the smoke (clean, gate did not fire)
  and ran install_d7s.sh unchanged. 84 D7s units are queued; w1-w4 started 03:44-03:46. ETA about 06:00. Then run d7s_eval.py.
- 11-17 03:16 D7c R10 passed offline; stress-set run requested (the fork implements, tests, smokes, queues).
- 11-17 02:46 D7b failed by pre-registration. Requested D7c (last cheap intervention test).
- 11-17 02:15 J-lens steering arm closed by the dose table. D7b requested from the fork (offline first).
- 11-17 01:16 P0 DONE (124/124 + FIT_DONE). Confirmation (2): AUC 0.806 on held-out, n=3 violations (underpowered, consistent).
  Waiting for the fork's dose table and the D7 install decision (amendment rule). GPU 5 runs only the dose check now. GPU 5 sits partly
  idle; consider using it for the retail oracle/audit or a retail residual pass if D7 stays on hold.
- 11-17 01:10 The D7 smoke (task 39) showed collapse at α 0.8. The regenerated turns loop "Unfortunately, I cannot ..." until max tokens
  (the refusal-minus-proceed direction is too concentrated). Install held. P0 finished at 01:04.
  Pre-run amendment, decided by h-04:
  1. α = the largest grid value with 0/24 degenerate outputs on 24 train write prompts (probe/d7_dose.py; grid 0-0.8).
  2. If that α changes 0/4 violation writes, switch to option B instead: α 0.8, only at the decision position + the first 16 decode
     tokens, and only if B is 0/24 degenerate.
  3. If neither qualifies, hold D7 and show the user the dose table.
  The rest stays as pre-registered.
- 11-17 00:50 The fork's probe/install_d7.sh fires on its own once P0 is terminal. Steps: residuals_u9b for the remaining airline detect
  episodes (held-out) -> changes.md line "residuals_u9b for the remaining airline detect episodes ... N detect caches" -> swap
  the backend -> start the D7 workers. When that line appears, run d7_confirm.py restricted to non-TRAIN tasks (confirmation 2).
  Smoke: task 41 ran clean (gate 0.4-1.6 s/turn; ended in a transfer, nothing regenerated); task 39 smoke running to exercise regeneration.
- 11-17 00:44 FIT_DONE 00:36 (4 baselines refit on 9B-user data). Retail detect 34/50, so P0 ends about 01:00. D7 smoke 1 done, smoke 2
  (task 39) running. Asked the fork for a held-out residual pass before the D7 launch, for confirmation (2).
- 11-17 00:14 Push loop fixed (TOP -> u9b folder; new pid 25048); pushed 78afb6b (u9b airline detect 50 + fitx 24).
  Disk 9.6 GB free and falling about 1 GB/h (the shared disk is 100% used). Regenerable caches under LJW if needed: .cache/uv 15G,
  .cache/triton 8.1G. Only clean them when free space is under 5 GB, and tell the user.
  P0: retail detect 2/50; fit iti/austeer remaining; D7 smoke (task 41) running in the w3 slot.
- 11-17 00:10 The u9b within-write (gold) confirms no decision-point separability for non-transfer writes. D3 dropped.
  D7 implemented; added exploratory d7gate10. Install after P0 + smoke.
- 11-16 23:50 D7 confirmation (1) passes (0.774, n=5 violations). Next: D7 steering prototype on train (fork implements; runs
  after P0). In parallel, confirmation (2) on held-out after P0 (DB rebuild or residual pass for held-out u9b episodes).
- 11-16 23:14 Per-layer: the D7 signal peaks at L31/L26 (0.86/0.87). Detection is essentially output-level. P0: fitx 24/24 done,
  airline detect 26/50, the fork's residual pass started (w3 lent), fit_chain is stopping w4 to fit. Next: confirmation (1) once
  probe/residuals_u9b exists.
- 11-16 22:44 D7 rank AUC is 0.87 across all writes for oracle violations (4B-user data). D7 is the lead direction, pending the
  pre-registered check on 9B-user data. Next tick: per-layer breakdown. After P0: rebuild the DB for u9b episodes with writes.
- 11-16 22:00 Oracle v2 (reserve/qual/oracle.py: DB flight statuses, state tracking, gold exemption) on 4B-user (98 episodes):
  8 violations (cancel_ineligible 5, retry_switch 3), all in reward-0 episodes. 9B-user so far: 2/21 (tasks 38 and 21).
  D7 found (see D7). Next after P0: rebuild the 4B DB for cancel episodes, then run the pre-registered D7 check.
- 11-16 21:45 Early 9B-user audit (fact 7): user-sim noise persists. Added D6 (policy-oracle labels) and moved it ahead of the lens tests.
- 11-16 21:00 Stopped the A-plan install (user). The within-write check finds no decision-point separability (fact 2).
- 11-16 20:56 Stopped the 9B DB (fact 6). GPU 2 now hosts the 9B user server.
