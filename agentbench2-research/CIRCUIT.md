# Full-network comparison and circuit search (11-27, user request)

Written 11-27 17:4x KST, before any comparison-1 number was read.

## User request

- 16:3x: AgentDojo: compare the residual stream (MLP + attention) of the misaligned and aligned clusters before the injection,
  during it and after it. AM: the same over the whole decoding. ToolAlign: three clusters (normal documents, wrongdoing documents
  where the model acts, where it does not), over the whole process.
- Then: how many neurons (MLP and attention, all layers) are suspected, can a subcircuit be found, and why 8 or 512 neurons.
- 16:5x: "세 벤치마크 모두에서 모든 토큰의 attention, MLP, residual 값을 저장 ... 읽히기만 ... 1번 비교 ... 차이가 큰 곳부터 연결을
  따라가 회로를 묶어 시험 ... 로컬 D". 16:5x: AgentDojo stores only the injected text in full.
- 17:3x: the full download was too slow (the PC's D drive is a single HDD); the user stopped it: "포기하고", then "받은만큼만 1번비교하자".

## Capture (code/cap/capture.py; prep_jobs.py; puller.py)

- Qwen3.5-4B rev 851bf6e, forward only over the prompt plus the completion the model produced (vLLM proxy token ids for
  AgentDojo and AM; ToolAlign trace token ids). bf16 with fla on project-b GPU 0 (AM) and 2 (AgentDojo); fp16 with the torch
  fallback on vast box 1 (ToolAlign). One platform per benchmark.
- Per token: attention write and MLP write of all 32 layers (fp8 e4m3, one scale per 128 dims; AgentDojo only on the injected
  blocks), top-32 MLP neurons per layer, write norm of every head. Per piece of at most 128 tokens: mean of every MLP neuron and of
  every head's o_proj input. Checks (verify.py): residual identity h[l+1] = h[l] + attn[l] + mlp[l] to 2.7e-3; fp8 median relative
  error 3 %, cosine p1 0.998; snapshot path equal to a scratch forward up to bf16 noise (top-32 overlap 0.985).
- Received before the stop (sorted order of token ids, so coverage is by prompt):
  - AM: 134 of 600 responses: leaking_explicit-america_replacement and _none complete (50 each), leaking_none-none_replacement 34.
  - AgentDojo: 1,620 of 2,295 requests; 216 decision-step requests of attack episodes (110 succeeded, 106 failed; 26 user tasks).
  - ToolAlign: 221 of 1,381 steps, 16 domains; no failure step among them, so the "acts vs does not" cluster cannot be compared.

## Comparison 1 (code/cap/cmp1_labels.py, cmp1_segs.py, cmp1_features.py, cmp1_report.py)

- Clusters:
  - AM: Haiku verdict (leak / no leak), groups = condition.
  - AgentDojo: attack succeeded / failed, on the first request after the injected text is read; groups = user task.
  - ToolAlign: wrongdoing scenario / safe scenario, every step; groups = domain.
- Segments:
  - AM: response tokens 0-256, 256-512, 512-768, 768-1,024, 1,024-1,536, 1,536-2,048, 2,048-3,072, 3,072-4,096, and the 256
    tokens before the first tool block.
  - AgentDojo: 256 prompt tokens before the first injected block, the injected blocks, the rest of the prompt, the first 64
    generated tokens, the whole generation.
  - ToolAlign: the last user message of the prompt, the generation before the first tool call, the whole generation.
- Features are centered within group (label-free group mean); two group-disjoint folds.
- Writes: per layer the attention write, the MLP write and the residual after the layer (cumulative sum; embedding excluded).
  Separation = AUROC of the projection on the mean difference fitted on the other fold. Null = 40 within-group label shuffles,
  95th percentile of the maximum over layers. Decomposition = projection of each layer's attention and MLP mean difference on the
  final-layer residual difference (shares sum to 1).
- Units: all 294,912 MLP neurons (segment means) and all 768 heads (write norm): AUROC >= 0.75 or <= 0.25 in both folds with the
  same sign; null = 5 within-group shuffles.
- Reading rule, fixed now: a segment "separates" if the residual AUROC exceeds both 0.75 and the null 95th percentile at some
  layer. Unit counts are read against their shuffles (a count is meaningful only if it exceeds the largest shuffle count).

## Comparison 1 results (11-27 18:4x, reports in results_mirror/cmp1_1127)

- **AM** (42 leak vs 88 no leak; 2 of the 42 from leaking_none-none_replacement):
  - No segment separates by the rule: the residual AUROC peaks at 0.73 (768-1,024 tokens, layer 19); attention and MLP writes
    reach 0.76 at layers 15-19 (768-1,024 and the 256 tokens before the first tool block). Null 95th percentile 0.63-0.69.
  - Time course: 0.41-0.48 at 0-256 tokens, 0.66-0.70 at 256-512, 0.68-0.71 at 512-768, 0.73-0.76 at 768-1,024, then lower.
  - Neurons passing in both folds: 0, 2, 16, 61, 44 over the first five windows; 71 before the first tool block (shuffles 0-1);
    spread over all layers, strongest |AUROC - 0.5| 0.27-0.34. Later windows: 47 against shuffles up to 7, and 969 against
    shuffles up to 321 (too few samples). Heads: 0 in every segment.
  - Attention and MLP shares of the final residual difference are about half each; the largest single terms are the last
    layers (L27 attention, L31 MLP).
  - The 8 concept neurons of T9e: lower in leaking responses in 256-512 tokens in both folds for all 8 (AUROC 0.26-0.44), never
    past the 0.25 threshold; weaker or mixed elsewhere.
- **AgentDojo** (110 succeeded vs 106 failed, centered per user task): the injected blocks give residual AUROC 0.56-0.66 at
  every layer from layer 0 (null 0.60), below 0.75; 0 neurons and 0 heads in every segment (1 neuron in the whole generation).
- **ToolAlign** (137 wrongdoing vs 84 safe steps): every segment separates from layer 0 (generation 0.96-1.00, document
  0.72-0.92), 24,000-42,000 neurons and 39-122 heads. With only log-only steps (79 vs 24) the same. This is the text content of
  the scenarios and the logs, not a misalignment signal. No failure step was received, so failure vs log was not compared.
- Reading by the rule: no AM or AgentDojo segment qualifies for step 3; ToolAlign qualifies only through content.

## Step 3 (circuit), rule fixed now, run only for segments that separate

- Candidates: the passing neurons and heads of that segment, ranked by the smaller fold strength; the layers with the largest
  attention / MLP shares bound where to look.
- Grouping: for the top candidates, the weight-based connections (neuron-explorer dictionary up/down links, and head output to
  neuron input through the residual) define a graph; a subcircuit is a connected set.
- Test on fresh generations (GPU), against size- and layer-matched random sets, with the T9e rule: the harmful rate drops by at
  least 20 points against the pooled random sets (one-sided Fisher p < 0.01) and the quality kept is not more than 10 points lower.
  Size is chosen on a curve (sizes 4, 8, 16, ... up to the candidate count) on the CALIBRATION fold before the test: the smallest
  size reaching 80 % of the largest size's effect.
