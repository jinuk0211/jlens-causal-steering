# Overnight search, 11-25 21:40 → 11-26 10:00 KST (user 11-25 21:3x)

User request (verbatim): "내일 오전 10시까지 돌아가는 gpu 0,2 vast ai 2080ti만 사용하는 루프 걸어줘 어떻게든 찾아야되 toolalignbench, agentdojo, AM 유의미한 결과내는 방법 탐색해서" + "난 개인적으로 이거 두개 염두해두고 탐색했으면 좋겠어" (the two documents: Goodfire "Neurons as an Interpretable Basis" 2026-11-10; Anthropic "Neuron Basis Part 2: Using Neurons For Safety Applications" 2026-11-23) + earlier: "MLP attention residual stream 전부 흩어져있대 어떤 한레이어 뉴런특정된게 아니라".

Written before any result of the arms below. Thresholds and selection rules are fixed here; anything added later is marked (사후) in the Log.

## What is already known (Qwen3.5-4B)

- Decision position only (CAUSAL-1): attribution-picked neurons, top-256 by gradient x (act - mu_ref), chosen on the other fold, flip the decision. AgentDojo 52 %, AM 78 %, ToolAlign (N4, original) 19-92 %. Same-layer random neurons give 0-2 %. attn_all gives 93-100 %. A single layer gives 0-6 %, and a residual layer gives at most 40 %.
- Behavior (CAUSAL-2, whole regeneration):
  - AgentDojo TEST: any 6-layer attention window set to the reference mean flips 27-44 %. The rule band (attention L8-13) gives 40 % vs 32 % for the best random band, so FAIL.
  - The neuron top-256 arm, picked by the |act difference| z-score over the commit span (not by attribution), gives 3 % on AgentDojo.
  - AM TEST is still running (26/48 at 21:10).
  - So the decision is spread over layers, components and positions. ToolAlign trajectory J-lens: when the tool is already named in the response text, the name position is too late (flip 0-19 %).
- Attribution-picked sets (the CAUSAL-1 selection) have never been run through a whole regeneration. That is the main gap.

## The two documents, turned into arms

- **Goodfire.**
  - Causal effect sits in a few strong firings. Keeping the top 8 % of firings per layer costs +2.9 % loss.
  - RelP attribution keeps 90 % of a logit margin with 0.2-0.8 % of the firing neurons (~520 per token).
  - Mean ablation, not zero.
  - Weak "Q3" firings matter for long generation only as a sustained background.
  - Translated here:
    - (G1) attribution-picked distributed neurons (RelP-like gradient x (act - mu)), all layers, mean replacement, through the whole regeneration;
    - (G2) tail-gated replacement: a picked neuron is replaced only at positions where it fires in its tail, |z| over its reference distribution >= the p97 threshold, so normal firings stay untouched (less damage);
    - (G3) dose: K = 256 / 1024 / 4096, overshoot beta = 2 (x <- x + beta (mu - x)).
- **Anthropic Part 2.**
  - A neuron is a context-gated steering vector: the output vector w (down_proj column) is what it writes.
  - Picking neurons by the J-lens readout of w, label-free, steers as well as a trained vector (21 % vs 21 %).
  - cos(residual, w) averaged over picked neurons is a zero-shot detector.
  - Translated here:
    - (A1) readout steering: neurons whose J-lens readout of w ranks the harmful action tokens (T side of each benchmark's CAUSAL-1 contrast) high, chosen on CALIBRATION, get added with the minus sign: dr = -c * ||r_L|| * w/||w|| at every generated position, for c in {0.1, 0.2, 0.4}. A second variant adds +w for neurons whose readout ranks the safe side (A side) high.
    - (A2) detector-gated: the zero-shot neuron score (cos(residual, w) of the A1 neurons, standardized on CALIBRATION references) gates G1/A1, so edits are on only at positions where the score exceeds its CALIBRATION threshold (the reference p97).
- **Attention.** The decision also runs through attention (attn_all 93-100 %; Anthropic note: attention-only changes are missed by MLP neurons).
  - (H1) the top-16 / 64 heads by attribution, with the o_proj or out_proj input slice set to the reference mean.
  - (H2) the combination of G1 K = 1024 and H1 16.

## Procedure (same splits as PLAN.md, fold 0 = CALIBRATION, fold 1 = TEST)

1. **capture** (ab_distrib.py): at every CAUSAL-1 decision position, save the activations and gradients of m = max lp(T) - max lp(A) for all MLP neurons and head inputs, plus block-level attributions.
   - AgentDojo: all 85 targets and 11 references.
   - AM: 51 targets and 120 references.
   - ToolAlign: 53 targets and 100 references.
   - Then the distributed-pattern report: concentration (neurons for 90 %), layer spread, MLP vs attention share, cross-benchmark top-neuron and top-head overlap vs a layer-matched permutation, J-lens readouts of shared neurons, target minus reference. Also the cross-benchmark transfer ablation.
2. **sets** (ab_search.py): picked on fold-0 units only.
   - attribution order: mean over fold-0 targets of grad x (act - mu_ref).
   - head order: the same, summed per head.
   - readout order (A1): the J-lens readout of each w scored against the T and A token sets.
   - Random controls: neurons in the same layers, heads in the same layers.
3. **screen** on CALIBRATION through the whole regeneration (ab_regen.run_rows).
   - AgentDojo: all fold-0 runset units, greedy.
   - AM: 12 targets and 12 references, 1 seed.
   - ToolAlign: on the 2080 Ti (see GPUs).
   - Round 1 arms: base | attr256 all | rand256 all | attr1024 all | rand1024 all | attr1024 commit | attr1024_b2 | rand1024_b2 | tail1024 (G2) | head16 | head64 | rhead64 | combo (attr1024 + head16) | ro_c0.2 (A1 minus) | ro_rand_c0.2 | det_attr1024 (A2).
   - Round 2 (only for a benchmark where round 1 has no arm through the gate): attr4096 | rand4096 | attr4096_b2 | tail4096 | ro_c0.4 | ro_safe_c0.2 | head128 | rhead128 | combo2 (attr1024_b2 + head64).
4. **Gate to TEST** (CALIBRATION):
   - flip >= 25 %;
   - flip - matched random >= 15 pp;
   - broken <= 20 %;
   - refs kept >= 80 %.
   - Up to 2 arms per benchmark, by S = flip (1 - broken) kept.
   - If no arm passes after round 2, TEST the single arm with the largest flip - random, marked "did not pass the CALIBRATION gate".
5. **TEST once** on fold 1: base, the chosen arms and their matched randoms.
   - AM: 24 targets + 24 references, 2 seeds if TEST starts before 04:00, else 1.
   - AgentDojo: all fold-1 runset units.
6. **Verdict** ("meaningful", TEST):
   - flip >= 30 %;
   - flip - matched random >= 20 pp;
   - one-sided Fisher exact p < 0.01 against the matched random (flip counts);
   - broken <= 15 %;
   - refs kept >= 85 %.
   - Report every arm, pass or not. No retuning on TEST.

## GPUs and order

- project-b GPU 0 (A6000 48 GB) and GPU 2 (24 GB) only, and only while every process on them is ours. GPU 1 is never used. GPUs 3-5 are not ours.
- vast: only the 2080 Ti box (ssh <vast-box>, fp32).
  - Session neuron-explorer runs run_tj2080.sh there now (ToolAlign commit-sentence mean replacement). Do not stop or touch it.
  - After its TJ2080_DONE, and after neuron-explorer says the box is free, the box runs the ToolAlign arms (attribution sets from step 2 through their ToolAlign regeneration harness).
  - Nothing on the 3090 or 1080 Ti boxes.
- Order:
  1. AM TEST finishes on GPU 0/2 (do not interrupt).
  2. Then capture: am on GPU 0; dojo, then toolalign, on GPU 2.
  3. Then sets.
  4. Then screen: AM with 2 workers on GPU 0; dojo on GPU 2, then a 3rd AM worker.
  5. Then gate.
  6. Then TEST.
- AB_BATCH: 24 on GPU 2, 32 on GPU 0. Disk: project-b had 16 GB free at 21:10; stop writing if < 6 GB.
- Haiku judge: PC only (AM uses markers; no judge needed overnight).

## Stop

- At 11-26 10:00 KST: stop launching, let running units finish or record where they are, and write the final Korean report.
  - Contents: what was found, numbers by arm and benchmark, the verdicts, the distributed-pattern summary.
  - Destination: PLAN Log, changes.md, and a reply. Then delete the loop.

## Log

- 11-25 21:40 written. ab_distrib.py exists locally (not yet uploaded); ab_search.py not yet written.
- 11-25 21:45 neuron-explorer reply:
  - It will message this session when TJ2080_DONE is written. Status then: ce_fp32 stats ~41/212, then run 1.5-2 h, then report, so roughly 00:30-01:30.
  - After that the 2080 Ti is free for this loop. It will not add an attribution arm itself; this loop runs it.
  - Requested for a matching comparison:
    - the same starts as ta_commit_edit (onset / commit / name);
    - the same LODO reference means, from /workspace/tj/ce_fp32/stats.npz (fp32);
    - a separate out dir (not ce_fp32).
  - Until then it runs only CPU analysis on the box.
  - ToolAlign leg: import ta_commit_edit's regeneration and stats helpers, add the attribution-picked sets (from the toolalign capture, picked on the other domain fold), write to /workspace/tj/srch_attr.
