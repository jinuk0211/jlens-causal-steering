# H1: attention heads that write the tool name (teacher-forced at the "=" of "<function=")

units: {'transfer': 166, 'BW': 9, 'GW': 150}; reproduced (argmax = logged token) 325/325

## A. Name-writing heads (task-balanced mean direct logit attribution to the chosen name token)

### transfer (n 166, tasks 80): attention DLA by layer L3 -0.00, L7 0.01, L11 -0.04, L15 -0.01, L19 0.44, L23 3.03, L27 10.91, L31 5.57; all heads 19.90

| head | DLA direct | DLA J-lens | share of all-head DLA | J-lens top words (most frequent in top-3) | main source segments (mass) |
|---|---|---|---|---|---|
| L27h5 | 11.33 | 19.83 | 0.57 | ' transfer', ' Transfer', 'transfer', '转移' | tool_desc_transfer 0.58, tools_other 0.16, policy_other 0.10 |
| L31h3 | 3.66 | 3.66 | 0.18 | ' transfer', ' Transfer', '转移', 'transfer' | tool_desc_transfer 0.67, tools_other 0.12, policy_transfer 0.11 |
| L23h11 | 2.82 | 5.16 | 0.14 | ' transfer', '转移', 'transfer', ' transferring', ' transfers' | tool_desc_transfer 0.57, tools_other 0.15, policy_transfer 0.14 |
| L31h14 | 2.27 | 2.27 | 0.11 | '转移', ' transfer', 'transfer', ' transition', 'check' | preamble_now 0.78, tools_other 0.05, assistant_prev 0.04 |
| L27h13 | 1.29 | 1.73 | 0.06 | 'transfer', 'fer', ' transfer', 'mer', 'Transfer' | tool_desc_transfer 0.84, tools_other 0.13, policy_transfer 0.03 |
| L31h8 | 0.77 | 0.77 | 0.04 | '=', '-', 'z', '+', 'quad' | preamble_now 0.56, tools_other 0.16, format_instr 0.07 |
| L31h9 | 0.54 | 0.54 | 0.03 | 'ว่า', 'day', ' a', 'linear', 'dice' | preamble_now 0.98, format_instr 0.01, assistant_prev 0.01 |
| L27h1 | 0.52 | 0.44 | 0.03 | 'uffer', ' terra', 'iefe', ' thriller', 'ache' | tool_desc_transfer 0.85, tools_other 0.05, policy_transfer 0.05 |

### BW (n 9, tasks 8): attention DLA by layer L3 0.02, L7 0.08, L11 -0.05, L15 -0.04, L19 0.05, L23 2.96, L27 5.97, L31 3.49; all heads 12.48

| head | DLA direct | DLA J-lens | share of all-head DLA | J-lens top words (most frequent in top-3) | main source segments (mass) |
|---|---|---|---|---|---|
| L23h11 | 2.63 | 4.91 | 0.21 | ' cancel', ' cancellation', '更新', ' update', ' updating' | tools_other 0.75, policy_other 0.08, assistant_prev 0.08 |
| L27h6 | 2.53 | 4.82 | 0.20 | ' cancel', 'cancel', ' Cancel', ' cancellation', ' Ref' | tools_other 0.52, policy_other 0.19, assistant_prev 0.11 |
| L27h0 | 2.05 | 3.53 | 0.16 | ' update', '更新', 'update', ' search', ' calculate' | tools_other 0.62, policy_other 0.14, assistant_prev 0.11 |
| L31h14 | 1.62 | 1.62 | 0.13 | '-c', '-update', 'update', 'c', 'UP' | preamble_now 0.57, assistant_prev 0.17, tools_other 0.12 |
| L27h13 | 1.38 | 2.06 | 0.11 | 'cancel', 'update', ' update', 'Update', ' cancel' | tools_other 0.84, assistant_prev 0.06, tool_desc_transfer 0.05 |
| L31h3 | 1.04 | 1.04 | 0.08 | ' transfer', '转移', 'transfer', ' central', 'central' | tools_other 0.62, tool_desc_transfer 0.14, assistant_prev 0.09 |
| L27h10 | 0.96 | 1.67 | 0.08 | ' get', ' update', ' take', ' return', 'update' | tools_other 0.66, tool_desc_transfer 0.11, policy_other 0.10 |
| L27h12 | 0.83 | 1.84 | 0.07 | ' replace', ' cancel', ' extend', ' modify', ' eliminate' | tools_other 0.65, policy_other 0.14, assistant_prev 0.08 |

### GW (n 150, tasks 87): attention DLA by layer L3 -0.00, L7 0.01, L11 0.01, L15 0.00, L19 0.18, L23 3.29, L27 7.20, L31 4.23; all heads 14.92

| head | DLA direct | DLA J-lens | share of all-head DLA | J-lens top words (most frequent in top-3) | main source segments (mass) |
|---|---|---|---|---|---|
| L27h5 | 3.32 | 6.11 | 0.22 | ' transfer', ' Transfer', 'modify', ' modify', 'transfer' | tools_other 0.58, policy_other 0.12, tool_desc_transfer 0.12 |
| L23h11 | 2.19 | 4.24 | 0.15 | ' modify', ' modification', '修改', ' return', '返回' | tools_other 0.81, assistant_prev 0.07, policy_other 0.05 |
| L31h3 | 2.09 | 2.09 | 0.14 | 'modify', ' Modify', ' modify', ' return', 'return' | tools_other 0.72, assistant_prev 0.12, tool_desc_transfer 0.07 |
| L31h14 | 1.88 | 1.88 | 0.13 | 'modify', ' modify', ' return', 'return', '-c' | preamble_now 0.55, tools_other 0.15, assistant_prev 0.13 |
| L27h10 | 1.54 | 2.58 | 0.10 | ' return', '回', 'return', ' get', 'get' | tools_other 0.73, assistant_prev 0.08, policy_other 0.08 |
| L27h13 | 1.46 | 2.11 | 0.10 | 'ify', 'modify', 'fy', 'return', ' return' | tools_other 0.82, assistant_prev 0.12, tool_desc_transfer 0.04 |
| L27h6 | 1.14 | 2.35 | 0.08 | ' cancel', 'cancel', ' Cancel', ' exchange', '交换' | tools_other 0.49, policy_other 0.18, assistant_prev 0.13 |
| L23h5 | 0.95 | 1.81 | 0.06 | ' return', 'return', ' change', ' Change', ' Return' | tools_other 0.74, policy_other 0.09, assistant_prev 0.08 |

## B. Transfers: bad (unneeded, failed episode) vs good (passed episode)

rows: bad 35 (24 tasks), good 130 (60 tasks); tasks with both labels 5

Pre-specified single features (no fitting). AUC > 0.5 = higher in bad. Turn-controlled = residual after a quadratic in turn index.
p = within-task label permutation (counts per task kept).

| feature | mean bad | mean good | AUC | task-cluster 95% CI | within-task AUC | turn-controlled AUC | p |
|---|---|---|---|---|---|---|---|
| L27h5 DLA direct (top transfer head) | 11.238 | 11.673 | 0.449 | [0.298, 0.587] | 0.6 | 0.468 | 0.750 |
| L27h5 DLA J-lens | 19.652 | 20.413 | 0.452 | [0.298, 0.587] | 0.64 | 0.469 | 0.755 |
| L27h5 mass sink | 0.000 | 0.000 | 0.462 | [0.313, 0.622] | 0.32 | 0.425 | 0.095 |
| L27h5 mass policy_transfer | 0.071 | 0.078 | 0.328 | [0.214, 0.446] | 0.32 | 0.335 | 0.060 |
| L27h5 mass policy_deny | 0.001 | 0.001 | 0.379 | [0.259, 0.526] | 0.32 | 0.44 | 0.380 |
| L27h5 mass policy_other | 0.092 | 0.095 | 0.340 | [0.229, 0.484] | 0.32 | 0.329 | 0.315 |
| L27h5 mass format_instr | 0.012 | 0.015 | 0.230 | [0.125, 0.345] | 0.2 | 0.242 | 0.010 |
| L27h5 mass tool_desc_transfer | 0.587 | 0.584 | 0.555 | [0.421, 0.685] | 0.6 | 0.548 | 0.760 |
| L27h5 mass tools_other | 0.171 | 0.168 | 0.479 | [0.344, 0.616] | 0.48 | 0.574 | 0.540 |
| L27h5 mass user_last | 0.004 | 0.004 | 0.577 | [0.462, 0.691] | 0.24 | 0.582 | 0.895 |
| L27h5 mass user_earlier | 0.006 | 0.003 | 0.705 | [0.584, 0.826] | 0.52 | 0.686 | 0.665 |
| L27h5 mass tool_results | 0.011 | 0.011 | 0.487 | [0.354, 0.611] | 0.72 | 0.408 | 0.965 |
| L27h5 mass assistant_prev | 0.028 | 0.023 | 0.595 | [0.459, 0.73] | 0.4 | 0.543 | 0.720 |
| L27h5 mass header_now | 0.001 | 0.001 | 0.488 | [0.363, 0.606] | 0.32 | 0.496 | 0.520 |
| L27h5 mass preamble_now | 0.016 | 0.019 | 0.371 | [0.258, 0.465] | 0.52 | 0.377 | 0.515 |
| L27h5 mass on copies of 'transfer' | 0.060 | 0.051 | 0.548 | [0.41, 0.674] | 0.16 | 0.68 | 0.975 |
| L19 all-head attention DLA (M1 layer total) | 0.356 | 0.502 | 0.300 | [0.177, 0.44] | 0.2 | 0.38 | 0.060 |
| L23 all-head attention DLA (M1 layer total) | 2.837 | 3.095 | 0.404 | [0.268, 0.539] | 0.52 | 0.401 | 0.345 |
| L27 all-head attention DLA (M1 layer total) | 10.702 | 11.148 | 0.439 | [0.296, 0.576] | 0.64 | 0.429 | 0.710 |
| L31 all-head attention DLA (M1 layer total) | 5.365 | 5.484 | 0.455 | [0.324, 0.581] | 0.52 | 0.45 | 0.465 |
| all full-attn layers, attention DLA total | 19.170 | 20.131 | 0.358 | [0.216, 0.497] | 0.48 | 0.36 | 0.400 |
| L27 all-head mean mass policy_transfer | 0.073 | 0.081 | 0.362 | [0.249, 0.464] | 0.56 | 0.345 | 0.415 |
| L23 all-head mean mass policy_transfer | 0.149 | 0.157 | 0.447 | [0.298, 0.599] | 0.52 | 0.419 | 0.390 |
| L27 all-head mean mass policy_deny | 0.009 | 0.011 | 0.376 | [0.265, 0.516] | 0.36 | 0.436 | 0.370 |
| L23 all-head mean mass policy_deny | 0.004 | 0.005 | 0.374 | [0.246, 0.527] | 0.44 | 0.491 | 0.170 |
| L27 all-head mean mass user_last | 0.006 | 0.005 | 0.624 | [0.525, 0.723] | 0.32 | 0.628 | 0.960 |
| L23 all-head mean mass user_last | 0.010 | 0.007 | 0.624 | [0.513, 0.732] | 0.36 | 0.652 | 0.955 |
| L27 all-head mean mass tool_results | 0.018 | 0.017 | 0.531 | [0.398, 0.656] | 0.52 | 0.437 | 0.180 |
| L23 all-head mean mass tool_results | 0.015 | 0.013 | 0.553 | [0.416, 0.687] | 0.6 | 0.473 | 0.075 |
| L27 all-head mean mass assistant_prev | 0.053 | 0.036 | 0.727 | [0.609, 0.834] | 0.4 | 0.658 | 0.355 |
| L23 all-head mean mass assistant_prev | 0.058 | 0.043 | 0.639 | [0.496, 0.781] | 0.44 | 0.578 | 0.605 |
| L27 all-head mean mass tool_desc_transfer | 0.351 | 0.354 | 0.480 | [0.339, 0.611] | 0.6 | 0.49 | 0.575 |
| L23 all-head mean mass tool_desc_transfer | 0.364 | 0.358 | 0.583 | [0.443, 0.719] | 0.36 | 0.534 | 0.820 |
| turn index | 14.629 | 10.831 | 0.665 | [0.529, 0.792] | 0.64 | - | 0.380 |

34 features tested: at p < 0.05 about 1.7 are expected by chance.

Cross-validated detectors (task-grouped 5-fold, the same folds as X16/X17), within-task permutation null with refitting:

| detector | AUC (OOF) | within-task AUC | turn-controlled AUC | null mean | null 95th | p |
|---|---|---|---|---|---|---|
| logistic, all 8x16 heads (mass x13 segments + DLA direct + DLA J-lens) | 0.760 | 0.600 | 0.736 | 0.754 | 0.807 | 0.44 |
| logistic, L23+L27 heads (mass + DLA direct) | 0.721 | 0.480 | 0.710 | 0.721 | 0.765 | 0.54 |
| logistic, top transfer head L27h5 only (13 masses + 2 DLA) | 0.775 | 0.400 | 0.745 | 0.761 | 0.801 | 0.35 |
| logistic, turn index only | 0.631 | 0.640 | 0.391 | 0.627 | 0.645 | 0.35 |

## C. Writes: unexpected write in a failed episode (BW) vs good write (GW), same name token only

name tokens with both groups: 'update' BW 3 / GW 12, 'cancel' BW 4 / GW 27

| name token | top name head (label-free, from both groups) | DLA bad | DLA good | within-name AUC of DLA | mass user_last bad/good | mass tool_results bad/good |
|---|---|---|---|---|---|---|
| 'update' | L27h0 | 3.69 | 4.21 | 0.167 | 0.006/0.004 | 0.033/0.048 |
| 'cancel' | L27h6 | 5.07 | 5.22 | 0.435 | 0.012/0.011 | 0.030/0.035 |

## D. Source tokens of L27h5 (top-8 attended positions; recorded at L23 and L27 only)

- bad (n 35): top-8 weight by segment tool_desc_transfer 0.524, tools_other 0.056, policy_transfer 0.036, policy_other 0.003
  tokens: '}'@tool_desc_transfer 0.176, '",'@tool_desc_transfer 0.155, '"}}'@tool_desc_transfer 0.093, 'transfer'@tool_desc_transfer 0.060, '\n'@tools_other 0.044, ' transfer'@policy_transfer 0.036, ' transfer'@tool_desc_transfer 0.024, 'Transfer'@tool_desc_transfer 0.016, 'modify'@tools_other 0.008, 'exchange'@tools_other 0.004
- good (n 130): top-8 weight by segment tool_desc_transfer 0.515, tools_other 0.057, policy_transfer 0.043, preamble_now 0.000, policy_other 0.000, assistant_prev 0.000
  tokens: '}'@tool_desc_transfer 0.192, '",'@tool_desc_transfer 0.134, '"}}'@tool_desc_transfer 0.098, '\n'@tools_other 0.054, 'transfer'@tool_desc_transfer 0.051, ' transfer'@policy_transfer 0.043, ' transfer'@tool_desc_transfer 0.025, 'Transfer'@tool_desc_transfer 0.013, '_agents'@tool_desc_transfer 0.001, 'modify'@tools_other 0.001
