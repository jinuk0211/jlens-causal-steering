# Failure-turn steering with official CAA / ITI on the vast box (started 2026-11-24 18:2x KST)

User 11-24 18:1x: "우리 vast ai 인스턴스에서는 그거 루프 돌려주라 caa,iti 같은 baseline으로 우리 실패턴에서만 steering 잘해서
점수 올리는거" (box: `ssh <vast-box>`).

## Setup
- Box: 2x GTX 1080 Ti 11 GB. Code is in /workspace/fsteer, the venv in /workspace/steer-venv (a copy of ne-venv with
  torch 2.14.1+cu126, transformers 5.20.2 = project-b, litellm 1.82.6).
- Code is the project-b tau2 fork (a6b112f + local edits), jlens, and jlens-causal-steering (official CAA/ITI adapters
  and the pinned upstream code). Everything was bundled from project-b (md5 6bd1014a…), without secrets.
- Box-only backend patches (jlens_backend.py; originals kept as .pre_split and .pre_snap):
  - `hf_device="split"` loads the model with device_map=auto over both GPUs (JLENS_MAX_MEMORY);
  - JLENS_PREFIX_SNAPSHOTS=1 reuses stored prefill caches at chunk-multiple cuts at or before the final `<|im_start|>`.
    Chunk boundaries are unchanged, and no hook-edited position is ever stored;
  - JLENS_ITI_CHUNKED=1: official ITI no longer forces one full-prompt forward. Its prompt is prefilled in chunks
    exactly like base. ITI does not edit prompt positions; this also removes a base/ITI difference in prompt numerics.
- Precision: float32, split over the two GPUs. bf16 has no memory-efficient attention on Pascal and is about 4x slower.
  f_detect ran in bf16 on an A6000, so the box base may not reproduce every logged turn; see the screen rule.
- User simulator: Claude Haiku through the PC proxy (Max plan).
  - The PC relay usersim_claude/box_relay.py adds the proxy token and is reached through an ssh -R tunnel on box
    127.0.0.1:18093. No token is on the box.
  - Same proxy prompt version as f_detect, with the disk cache, keyed by the trial seed.
  - 18:30: proxy.py now finds the newest claude.exe; the 2.1.325 path was gone.
- Decoding: greedy. max_new_tokens is 768 for single-turn regeneration and 1024 in episodes (f_detect: 4096 with a
  300 s max_time). No max_time.

## Data (already-run episodes only; no baseline is re-run)
- f_detect: 278 unsteered Haiku-user episodes, 43 failures by the reported score. Raw results.json has 39 failures:
  4 retail "passes" are failures only under the NL judge.
  - 35 of the 39 have a first bad write ("failure turn", label_calls bad_write in a failed episode).
  - 4 fail with no bad write (missing action). They, and the 4 NL-judge failures, have no single steerable turn.
- hdetect: 100 unsteered Haiku-user episodes (airline + retail). Their 20 failures are used for fitting (train fold)
  and for branch evaluation (eval fold).
- Fold: airline TRAIN 24 tasks = train; retail and telecom by md5(domain|task) % 2 == 0 = train (as in C-LOOP).
- Fit pairs (train fold, fail_first + fail_other, f_detect + hdetect): 48.
  - The prompt is the exact logged rendered_context. The negative is the logged action.
  - The positive is chosen in this order:
    1. the gold call of the same tool (wrong arguments): 18;
    2. otherwise the first pending gold write: 22;
    3. otherwise a real policy-denial reply from a passed episode of the same domain: 8. No canned sentence (the F-run
       lesson).
- Extraction: project-b fsteer/fs_extract.py → fs_units.jsonl.

## Methods (official adapters, applied ONLY at the failure turn: InterventionConfig.turn_indices = [0] of the branch)
- CAA (nrimsky): fit_items at layers 10/13/16/20/24, A/B items from the rendered prompts. Multiplier = α · median
  ||h_L|| / ||v_L|| over the train decision points, α ∈ {0.5, 1, 2}.
- ITI (honest_llama): fit with K = 48 heads (probe ranking, seed 42, val 0.2). The K = 16 version keeps the top-16 heads
  of the same fit. α ∈ {10, 20}, decode positions only.
- Random controls: the same artifact with each vector / head direction replaced by a Gaussian direction of the same
  norm (CAA seed 0, ITI seed 1).

## AMENDMENT 11-24 19:5x (user: "baseline caa, iti말고도 많잖아 그것까지 끝내라"; "결과 이상하면 자가 피드백해서
## baseline으로써 어느정도 성과는 있게"), written before any steered output
- All six official baselines of the F-run, each applied only at the failure turn (turn_indices [0]):
  - CAA and ITI as above;
  - SADI: hiddens, top_k 10, strength {5, 10, 20};
  - AUSteer: attention, top_k 8, {10, 20, 50};
  - CAST: gated by its own condition, {1, 1.5, 3};
  - MERA: all positions, sigmoid+logit, {0.001, 0.331, 0.661}.
  These are the F-run manifest grids.
- Fit (fs_fit2.py): the same 48 train pairs, fit through the official functions with the manifest settings (fp32,
  both GPUs). One deviation: the CAST condition negatives are train good-write turns of the same domain (the same task
  preferred), because other turns of the failed episodes are not in the bundle. Random controls: every float state
  tensor is replaced by a same-norm Gaussian, and (layer, unit) tables by random indices. CAST keeps its condition and
  randomizes only the behavior directions.
- Memory fix, exact: fs_patches.py runs transformers' torch fallback torch_chunk_gated_delta_rule in segments of 1024
  tokens and carries the recurrent state. CPU test: max |diff| 0.0 for both the output and the final state. Full-prompt
  forwards (SADI and CAST official, and the fits that read arbitrary positions) now fit on the 1080 Ti.
  - So JLENS_ITI_CHUNKED is dropped: ITI is back to the official full-prompt forward.
  - The CAA/ITI fit (fs_fit.py) keeps its chunked forward. It reads only last-token values, which are identical.
- Snapshot safety: under hooks, stored prefill caches are reused only for CAA and ITI and are never stored there.
  CAST, MERA, AUSteer and SADI edit prompt positions, so they prefill from scratch.
- Round 2, automatic, train turns only, for every method that got no pick in round 1. Stronger doses:
  - CAA α {3, 4}; ITI α {30, 40};
  - SADI 40, AUSteer 100, CAST 5, MERA 0.99.
  Selection then uses rounds 1 + 2 together, with the same rule.
- Self-feedback protocol (the loop applies it; every attempt is logged and reported, with the count of tries):
  1. Check for bugs before calling a method weak:
     - an edit is never applied (the telemetry intervention trace);
     - every setting is identical to base;
     - all outputs are degenerate;
     - base does not reproduce the logged failure (fidelity);
     - a prompt mismatch.
     Fix and rerun only the affected jobs.
  2. If there is no bug and a method still fails after round 2, the next widenings are run on train turns only, in this
     order:
     - (a) per-failure-type vectors, refit separately on transfer-type pairs (gold_pending / denial) and
       argument-type pairs (gold_arguments), applied by the failure type of the turn;
     - (b) extra CAA layers 6/8/28;
     - (c) steering the failure turn and the following turns.
  3. The eval branch (24 turns) runs once per final pick, with its random control. It is never used to choose or tune.
- Order of the stages: fit (CAA/ITI) → fit2 (SADI, AUSteer, MERA, CAST) → smoke (base + one setting per method) →
  screen (30 turns × 32 conditions) → round 2 if needed → random controls → branch + harm.

## Stages and pre-registered rules (fixed before any steered output exists)
1. Smoke, 1 train unit × {base, caa_L16_a1, iti_k16_a10}. Required:
   - all 3 rows written;
   - the base telemetry prompt equals the logged rendered_context.
   Otherwise stop.
2. Screen: single-turn regeneration of 30 train failure turns. One unit is dropped because its logged reply is longer
   than 752 tokens. There are 20 conditions: base, 15 CAA, 4 ITI.
   - Outcomes: same (the logged bad write set again), fixed (the positive gold call is made, or for denial positives no
     write and no verbal transfer), away (another action), verbal_transfer, degenerate (a repeated 8-gram ≥ 3 times, or
     capped).
   - Eligible units: base outcome == same, i.e. the box reproduces the failure.
   - Score = eligible units that are fixed or away. Settings with degenerate > 10 % are ineligible.
   - Pick per method: the highest score, then more fixed, then smaller α, then the lower layer or K.
   - A method proceeds if its score ≥ max(2, ceil(0.2 × eligible)).
3. Screenrand: each pick's random control on the same 30 turns. A pick passes if score(pick) − score(random) ≥ 2.
4. Branch, the score test. The 24 eval failure turns (f_detect eval 13 + hdetect eval 11) are continued to the end of
   the episode with Haiku.
   - Conditions: base, the passing picks, and their random controls, steered at the failure turn only. Seed = the
     original trial seed.
   - Primary outcome: reward 1 count per condition, paired with base.
   - Success (exploratory, n = 24): passes(pick) − passes(base) ≥ 3, and the random control's gain is less than half of
     the pick's. On success a second seed (rep 1) is run before any claim. A deployable gate (detector-triggered
     steering on fresh full episodes) is then proposed to the user.
   - Harm, in parallel: 30 train good write turns (10 per domain) × the same conditions, single-turn regeneration.
     Kept rate is reported; it matters only for a later gated deployment.
5. Report: score readout = f_detect score + net fixes at the eval failure turns. This is an oracle-gate upper bound.
- The driver (fs_driver.py) applies these rules automatically. It halts if more than 5 % of a stage's jobs fail.

## SELF-CHECK BUG 11-25 12:5x (found while answering the user's "유의미하니")
- caa_L10_a2 "converted 14/14" was an artifact. All 14 replies are truncated tool calls, e.g.
  '<tool_call>\n<function=update_reservation<|im_end|>' (8-10 tokens).
  - The backend parses no call from them, and classify() counted "no write call" as away/fixed (for denial
    positives).
  - austeer_s20 had 4 of the same kind (garbled JSON, e.g. '"2024-05-24",oublet":').
- Fix: classify() now returns broken_call when no call is parsed but the text contains <tool_call>/<function=.
  broken_call counts with degenerate in the <= 10 % rule and in the pruning.
- The driver recomputes every regen row's outcome with the current classify(), and keeps outcome_logged. No rerun is
  needed: the stored text and calls are enough.
- Corrected interim (14 train units, all eligible: base reproduces 14/14). Columns: fixed / away / same /
  degenerate+broken.
  - caa_L10_a1: 0 / 9 / 3 / 2. Away is mostly the same tool with other (still wrong) arguments.
  - caa_L24_a0.5: 0 / 4 / 7 / 1.
  - austeer_s20: 1 / 4 / 2 / 4, so it is pruned.
  - Every other setting has fixed ≤ 1/14.
  - Pruned as degenerate: caa_L10_a2, austeer_s20, caa_L16_a1, iti_k16_a20, iti_k48_a10 and the earlier ones.

## STOPPED 11-25 13:3x (user: "야 이거 답없다 멈춰")
- Cron 6ee1ff1b deleted. On the box, the driver (26333) and the worker (20626) were killed by pid and a STOP file was
  written. The running job was moved to q/archive/stopped_1125. GPUs are free.
- The PC relay box_relay.py and its ssh -R tunnel were stopped. proxy.py (18091) is left running.
- State at stop: screen 675/870 (done 320, skipped 356, pending 199). 16 train units, base reproduces 16/16. The
  corrected table is in out/interim_final_1125.txt.
  - The best "converted" is caa_L10_a1: 0 fixed / 11 away / 3 same / 2 degenerate. Away is mostly the same tool with
    other wrong arguments.
  - No setting fixes more than 1/16.
  - The stronger doses of CAA, ITI and AUSteer break the output.
- Not run: random controls, branch episodes (the score), harm, CAST, Track 2.
- All outputs are kept on the box: out/, art/, q/, logs/.

## Track 2 prep (11-25 10:5x): ToolAlign data on the box
- Copied to /workspace/fsteer/toolalign: the 128 greedy traces (qwen35-greedy), the jlens_experiment replay code
  (trace_replay, model_profiles), the CAUSAL units (53 targets: 15 misaligned, 29 boundary, 9 aligned email; 40
  writeInternalLog references), steps.json and ta_causal2.py. md5 be886cdb.
- Plan: reuse ta_causal2's unit list, prompt replay and first-tool-name regeneration rule.
  - Fit the official CAA/ITI/SADI/AUSteer/MERA on fold-A domains: positive = the writeInternalLog call, negative = the
    misaligned/boundary call, same prompt.
  - Apply at the decision step only, on fold-B targets and references, with random controls.
  - GPUs only after the tau2 pipeline.

## Track 2 (planned, not started): ToolAlignBench 128 existing conversations
- Failure turns: the 15 clearly-misaligned and 38 boundary calls.
- Same official CAA / ITI at those turns only, with single-turn regeneration first.
- Starts after the tau2 screen is running. It needs the ToolAlign prompt rendering on the box.

## Log
- 11-24 18:2x project-b extraction: 35 f_detect failure turns (airline 14, retail 14, telecom 7; train 22, eval 13),
  hdetect 20.
- 18:30 Haiku relay and tunnel up. Box test reply OK (3 s).
- 18:4x fit attempts: bf16 OOM (Pascal has no efficient attention for bf16), then fp32 full-sequence OOM (the torch
  fallback of the linear attention). The chunked forward (1024) for the fit works; it reads the same last-token values
  as one forward.
- 18:59 driver started (waits for FIT_DONE). Fit ETA about 21:00 KST.
- 19:2x The user asked to add project-b GPU 0. It is busy: the ToolAlign session's Gemma-4-e4b vLLM (serve_batched.py
  port 18210, 40.5 GB, 100 %), not touched. User: "vast ai 로만 루프 돌려야될듯" → the box's 2 GPUs only. The fit is
  at CAA 19/48 items.
- 19:5x amendment above. The backend snapshot patch was made safe (.pre_snap2), and fs_patches.py was added. The driver
  was restarted at 19:23 UTC+9 (10:23 box UTC) with the six-method stages. Fit 1 is at CAA 34/48.
- 20:59 fit 1 done.
  - CAA 3830 s; dose ||v||/median||h||: L10 0.47/5.30, L13 1.03/6.46, L16 3.40/8.60.
  - ITI 3812 s: K16 heads in L27/31; K48 in L15/19/23/27/31.
- 21:00-21:35 problems found and fixed (attempt log). The 3 smoke jobs and the fit2 runs are archived under
  q/archive, out/archive and art/archive.
  1. fit2 (fp32): all 4 methods OOM on GPU 1. The full-sequence fits keep every layer's hidden states (about 3 GB at 9k
     tokens). Fix: fit2 now loads fp16 split (5/5 GiB). Pascal has memory-efficient attention for fp16. The vectors are
     applied in the fp32 agent.
     - Rerun 21:34. The fp32 retry at 21:28 also OOMed.
  2. Smoke "base": the backend rejects intervene mode without an intervention. Fix: base = official CAA with
     strength 0.0 (adds exactly 0; same hooks and prefill path as CAA).
  3. Worker GPU 1 OOM. JLENS_MAX_MEMORY was 0:7/1:9 GiB and prefill snapshots were kept on GPU. Fix:
     - snapshots are kept in CPU RAM and moved back when reused (round trip exact, max diff 0.0);
     - budgets are 0:7.6/1:8 GiB (fp32 weights 15.6 GiB with the tied embedding).
     After the fix: base smoke OK, prompt_match True, reproduces the logged failure (same update_reservation_flights).
  4. BUG (self-check a): CAA applied_edits = 0. The official CAA ForwardCounter counts positions from the first hooked
     forward, and the hooked re-prefill started from a stored snapshot, so no position ever reached from_position
     (14112). Fix: stored caches are used only for the unhooked prefix; hooked prefills always start at 0. The buggy
     caa_L16_a1 smoke row is archived.
     - The worker now records applied_official_edits.
     - The driver's smoke check now also requires applied edits > 0 for every steered condition except gated CAST.
  5. ITI official full-prompt forward: OOM on GPU 1 (fp32, 14k-token prompt). Fix: JLENS_ITI_TAIL2. The unhooked
     prefix stops 2 tokens early, so generate's first forward has length 2. ITI's hook skips it (b.shape[1] > 1) exactly
     as in the upstream full-prompt forward. The prompt stays unedited and decode steps are edited, which is identical
     semantics without the full forward. JLENS_ITI_CHUNKED is no longer used.
- 22:37 fit2 (fp16): MERA ok, 3784 s; probe_weights per layer, 32 × 2560. SADI started.
  - CAST does about 288 full-sequence forwards (behavior 96, condition 96, condition-point search 96). Estimate 2-3 h.
  - fit2 ETA is about 03:30. The screen follows it (960 jobs, about 10 h).
- 23:55 fp16 too slow. MERA took 63 min on the box vs 4 min on the A6000; Pascal fp16 GEMMs are slow, so SADI, AUSteer
  and CAST would take more than 10 h. SADI was killed after 76 min.
  - fit2 is now fp32 with manual placement:
    - the model is loaded on CPU;
    - layers 0-13 go to cuda:0 and 14-27 to cuda:1 (5.8 GiB each);
    - layers 28-31, the final norm and the tied embedding/lm_head stay on CPU;
    - accelerate AlignDevicesHook moves the inputs per module.
  - device_map="cpu" entries failed with meta tensors (accelerate offload).
  - The placement 0-15/16-31 OOMed: SADI on cuda:0 at 10.6 GB.
  - MERA (fp16 fit, ok) is kept and skipped.
  - Restarted 00:13. No OOM after 6 min.
- 24:0x smoke with the fixes (base, caa_L16_a1, iti_k16_a10, mera_s0.331 on train unit 340843df, airline 10):
  - no OOM; prompt_match True;
  - edits applied: CAA 241, ITI 456, MERA 459,040;
  - base reproduces the logged failure (update_reservation_flights);
  - CAA moves to "away" (the same tool, other arguments); ITI and MERA stay "same".
- The driver was reset to stage "fit" and restarted. It waits for FIT2_DONE, then smokes all fitted methods. Smoke jobs
  already done are skipped by job id.
- 01:45 SADI fit ok (5459 s): max_hiddens 128 units, max_acts 1000. AUSteer started.
  - The fp32 forward with 4 CPU layers takes about 57 s, so CAST's ~288 forwards would take about 4.5 h.
  - Decision: CAST is DEFERRED to after the 5-method pipeline, so that results for 5 methods arrive about 4.5 h
    earlier. The plan to finish all six is unchanged.
  - defer_cast.sh waits for austeer ok/FAILED, then:
    - kills fit2 (pid 15727);
    - writes the SADI/AUSteer random controls;
    - writes FIT2_DONE with cast = DEFERRED.
  - After the 5-method run, the loop fits CAST (fit2 skips the methods already fitted) and runs a CAST add-on with the
    same rules: screen (round 2 if needed) → random control → branch + harm on the same units.
- 04:2x AUSteer is still fitting, 159 min so far. Its official MFU_screening loops twice over the 48 train pairs for each
  applied module (attention, ffn), about 384 forwards in all. The 4 CPU layers dominate (CPU 840 %, GPUs mostly idle).
  ETA about 07:00. Not restarted, to keep the progress.
- 04:47 AUSteer fit ok (10938 s): attention scores 32768 units, ffn 81920. defer_cast.sh worked:
  - SADI/AUSteer random controls written;
  - FIT2_DONE with cast DEFERRED.
- 04:49 Smoke: SADI OOM on GPU 1. The official SADI does a full-prompt clean pass plus a full-prompt edit forward
  (fp32, 14k tokens). Fix, JLENS_TAIL2_METHODS=sadi (adapter + backend, originals .pre_tail2):
  - the clean pass runs in 1024-token chunks with a cache (it reads only the last position);
  - the backend prefills prompt[:-2] unhooked and keeps that prefix;
  - the first hooked forward (the 2-token prompt tail) edits the last prompt position once per layer;
  - decode steps are not edited.
  This is the same edit at the same position as upstream. The failed job was archived and rerun: applied_edits 32
  (one per layer), prompt_match True.
- 04:58 SMOKE OK, 6 conditions on train unit airline 10:
  - base same; caa_L16_a1 away; iti_k16_a10 same; sadi_s10 same; mera_s0.331 same;
  - austeer_s20 FIXED (the gold call).
  → SCREEN started: 870 jobs (30 units × 29 conditions, the 5 methods). About 35-90 s per job, so the ETA is about
  19:30 on 11-25.
- 05:25 Speed. 11 jobs took 28 min (mean 132 s). Degenerate replies ran to the 768-token cap (262 s); 3/11 so far
  (caa_L13_a1, caa_L13_a2, caa_L16_a2). Two lossless changes:
  - FS_REPEAT_STOP=1: generation stops when the last 32 generated tokens have occurred 4 times. The worker classifies
    such a turn as degenerate, as before.
  - Driver pruning: a condition with >= 4 degenerate rows on the screen units is already ineligible under the
    <= 10 % rule (30 units). Its remaining pending screen jobs move to q/skipped, which counts as finished. The
    selection result is unchanged.
  - The worker and the driver were restarted; the stale job was requeued.
- First screen rows, unit airline 10:
  - caa_L10_a2 FIXED; caa_L10_a1 and caa_L16_a1 away;
  - α 0.5 the same as base at every layer so far;
  - the edits were applied in all of them (self-check a).
- 05:54 screen 27/870. After the restart the mean is 104 s per job, on unit 1 with a 14.1k-token prompt. The screen
  units have prompts of 5.2k-20.3k tokens (mean 10.7k) and logged replies of median 164 tokens. Expected about 80 s
  per job, so with pruning the ETA is about 20:00-21:00 on 11-25.
  - Unit 1: 13 of 28 steered settings already degenerate. CAA α ≥ 1 at L13-24, ITI k16 α20 and k48, AUSteer 50.
