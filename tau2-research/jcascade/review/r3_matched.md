# R3: situation-matched comparison (x15 transfer turns + denial turns from the same unsteered runs)

- transfer rows with a label: bad 35 (24 tasks), good 131; by cond {'f_detect': 19, 'hdetect': 11, 'detect': 3, 'fitx': 1, 'd7obs_s1': 1} (bad)
- denial rows 111; in a bad task 26; followed by a transfer later in the same episode 24

## (A) bad vs good transfer, bigger sample (task-grouped 5-fold)

- J_pairs AUC 0.679, cluster CI [0.552, 0.803]
- a-priori cascade (L20 inability + L24 understanding + L26 acknowledgement) AUC 0.558, cluster CI [0.457, 0.665]

## (B) bad transfer vs denial (y=1 bad transfer, y=0 denial)

| comparison | n bad / n denial | J_pairs AUC (cluster CI) | cascade AUC (cluster CI) |
|---|---|---|---|
| same task (any run) | 15 (12 tasks) / 26 | 0.673 [0.561, 0.798] -> inconclusive | 0.692 [0.541, 0.821] -> inconclusive |
| same episode, earlier turn, before the transfer | 11 (9 tasks) / 14 | 0.692 [0.592, 0.812] -> inconclusive | 0.636 [0.415, 0.867] -> reads the situation |
| same domain (all denials) | 35 (24 tasks) / 111 | 0.543 [0.385, 0.72] -> reads the situation | 0.603 [0.478, 0.74] -> reads the situation |

- reference: good transfer vs all denials, J_pairs AUC 0.376

Pre-registered rule (PLAN amendment 11-24): 'reads the situation' if AUC <= 0.655 or the CI upper bound < 0.70; 'decision visible' if the CI lower bound >= 0.60; else inconclusive. M1 = same task, M2 = same episode (reported if >= 8 bad rows).

## (C) trained probe: bad transfer vs same-task denial, task-grouped CV (where is the decision linearly readable?)

rows: bad 15, denial 26, task clusters 12

| feature | AUC |
|---|---|
| residual L0 | 0.628 |
| residual L2 | 0.697 |
| residual L4 | 0.690 |
| residual L6 | 0.877 |
| residual L8 | 0.605 |
| residual L10 | 0.846 |
| residual L12 | 0.862 |
| residual L14 | 0.833 |
| residual L16 | 0.844 |
| residual L18 | 0.846 |
| residual L20 | 0.808 |
| residual L22 | 0.777 |
| residual L24 | 0.777 |
| residual L26 | 0.726 |
| residual L28 | 0.756 |
| residual L30 | 0.779 |
| MLP L12-31 top-200 by t | 0.831 |

## (C) confound checks (M1 rows: 15 bad transfers from 12 tasks, 26 same-task denials)
- turn index alone: AUC 0.586, cluster CI [0.48, 0.77]
- residual probe with the turn-index direction regressed out: L6 0.772, L12 0.887, L18 0.841
- L6 probe with labels permuted within task (20 permutations): mean 0.526, max 0.726
- caveat: 16 layers were scanned on 41 rows, so the best layer is optimistic; the L10-L18 band is consistently 0.83-0.89
