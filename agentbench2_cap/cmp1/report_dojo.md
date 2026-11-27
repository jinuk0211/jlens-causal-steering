# Comparison 1: dojo (dojo), attack succeeded vs attack failed

Samples 216: attack succeeded 110, attack failed 106; groups 26; folds by group.

## Segment gen (110 vs 106; median 126 tokens)

Neurons (MLP, 294,912): 1 pass in both folds; label shuffles [0, 0, 0, 0, 0].
- by layer: L15 1
- strongest: L15/N5298 -0.25, L8/N4118 +0.23, L11/N927 -0.21, L14/N1667 +0.21, L28/N8420 -0.21, L19/N519 +0.21, L12/N5184 -0.21, L27/N4819 -0.21, L27/N5975 +0.20, L22/N3938 -0.20, L19/N3224 -0.20, L22/N4410 -0.20

Heads (write norm, 896 heads): 0 pass in both folds; label shuffles [0, 0, 0, 0, 0].
- strongest: L16H8 +0.16, L18H14 +0.15, L15H12 +0.14, L17H2 +0.14, L18H26 +0.13, L18H27 +0.13, L10H5 +0.12, L30H13 -0.12, L11H14 +0.12, L26H19 +0.12

## Segment gen64 (110 vs 106; median 64 tokens)

Neurons (MLP, 294,912): 0 pass in both folds; label shuffles [0, 0, 0, 0, 0].
- by layer: 
- strongest: L15/N5298 -0.19, L15/N5441 -0.19, L18/N4789 +0.19, L16/N1090 -0.18, L24/N214 +0.18, L12/N5184 -0.18, L8/N5636 +0.18, L27/N5975 +0.18, L24/N3555 +0.18, L16/N7835 -0.18, L12/N445 -0.18, L1/N600 +0.17

Heads (write norm, 896 heads): 0 pass in both folds; label shuffles [0, 0, 0, 0, 0].
- strongest: L1H4 -0.14, L30H20 +0.14, L6H18 -0.13, L28H19 +0.12, L26H19 +0.12, L13H24 -0.11, L9H16 +0.10, L31H12 +0.10, L5H1 -0.09, L19H10 +0.09

## Segment inj_spans (110 vs 106; median 145 tokens)

Writes, cross-fitted AUROC per layer (attention / MLP / residual after the layer); null max over layers, 95th percentile = 0.60:

| layer | attn | mlp | resid | share of final residual difference: attn | mlp |
|---|---|---|---|---|---|
| 0 | 0.55 | 0.64 | 0.56 | -0.000 | +0.001 |
| 1 | 0.66 | 0.66 | 0.60 | +0.001 | +0.000 |
| 2 | 0.67 | 0.67 | 0.63 | +0.002 | -0.000 |
| 3 | 0.66 | 0.68 | 0.64 | +0.002 | +0.001 |
| 4 | 0.64 | 0.65 | 0.64 | +0.002 | -0.000 |
| 5 | 0.67 | 0.65 | 0.64 | +0.003 | +0.000 |
| 6 | 0.68 | 0.65 | 0.67 | +0.009 | -0.003 |
| 7 | 0.66 | 0.67 | 0.66 | +0.006 | -0.003 |
| 8 | 0.67 | 0.65 | 0.65 | +0.005 | -0.005 |
| 9 | 0.68 | 0.66 | 0.65 | +0.002 | +0.000 |
| 10 | 0.66 | 0.66 | 0.65 | +0.004 | -0.000 |
| 11 | 0.62 | 0.67 | 0.64 | +0.002 | -0.003 |
| 12 | 0.68 | 0.68 | 0.65 | +0.003 | +0.001 |
| 13 | 0.67 | 0.66 | 0.65 | -0.000 | +0.003 |
| 14 | 0.65 | 0.67 | 0.66 | +0.008 | +0.001 |
| 15 | 0.63 | 0.68 | 0.66 | +0.002 | +0.001 |
| 16 | 0.68 | 0.66 | 0.65 | +0.001 | +0.004 |
| 17 | 0.68 | 0.65 | 0.65 | +0.004 | +0.002 |
| 18 | 0.65 | 0.66 | 0.66 | +0.011 | +0.007 |
| 19 | 0.67 | 0.66 | 0.65 | +0.019 | +0.005 |
| 20 | 0.63 | 0.67 | 0.65 | +0.005 | +0.011 |
| 21 | 0.63 | 0.67 | 0.65 | +0.014 | +0.010 |
| 22 | 0.65 | 0.68 | 0.66 | +0.014 | +0.020 |
| 23 | 0.67 | 0.67 | 0.66 | +0.029 | +0.012 |
| 24 | 0.63 | 0.67 | 0.66 | +0.014 | +0.004 |
| 25 | 0.64 | 0.67 | 0.65 | +0.006 | +0.007 |
| 26 | 0.62 | 0.62 | 0.66 | +0.008 | +0.025 |
| 27 | 0.62 | 0.66 | 0.66 | +0.038 | +0.032 |
| 28 | 0.63 | 0.67 | 0.66 | +0.035 | +0.037 |
| 29 | 0.62 | 0.64 | 0.66 | +0.028 | +0.047 |
| 30 | 0.61 | 0.64 | 0.66 | +0.045 | +0.082 |
| 31 | 0.61 | 0.58 | 0.65 | +0.062 | +0.319 |

- best: layer 17 (attn 0.68, mlp 0.65, resid 0.65); first layer with resid AUROC >= max(0.75, null p95): None; attention share +0.38, MLP share +0.62 (sum = 1)

- largest contributions: attention layers [(31, 0.062), (30, 0.045), (27, 0.038), (28, 0.035), (23, 0.029)]; MLP layers [(31, 0.319), (30, 0.082), (29, 0.047), (28, 0.037), (27, 0.032)]

Neurons (MLP, 294,912): 0 pass in both folds; label shuffles [0, 0, 0, 0, 0].
- by layer: 
- strongest: L11/N4786 -0.25, L2/N5490 -0.25, L12/N8429 -0.24, L26/N4817 +0.24, L20/N8667 +0.24, L4/N4012 -0.24, L23/N3982 +0.24, L6/N3062 +0.23, L1/N4922 -0.23, L22/N7496 +0.23, L25/N2317 -0.23, L28/N8887 -0.22

Heads (write norm, 896 heads): 0 pass in both folds; label shuffles [0, 0, 0, 0, 0].
- strongest: L1H29 -0.15, L1H10 -0.14, L20H29 +0.13, L14H19 -0.13, L5H28 -0.12, L10H30 +0.12, L29H9 +0.12, L9H22 +0.12, L17H19 +0.12, L14H14 -0.12

## Segment post (110 vs 106; median 14 tokens)

Neurons (MLP, 294,912): 0 pass in both folds; label shuffles [0, 0, 0, 0, 0].
- by layer: 
- strongest: L21/N3843 +0.19, L18/N7290 -0.18, L16/N5461 -0.18, L17/N6625 +0.18, L20/N5651 +0.17, L19/N7564 +0.17, L19/N5084 +0.17, L15/N1817 +0.17, L15/N4721 -0.17, L23/N6534 +0.17, L25/N1214 -0.17, L16/N1271 -0.17

Heads (write norm, 896 heads): 0 pass in both folds; label shuffles [0, 0, 0, 0, 0].
- strongest: L5H5 +0.18, L4H18 -0.16, L30H25 +0.16, L28H2 +0.16, L13H13 +0.16, L16H15 -0.15, L30H28 +0.14, L6H27 -0.13, L2H21 +0.13, L0H24 +0.12

## Segment pre (110 vs 106; median 256 tokens)

Neurons (MLP, 294,912): 0 pass in both folds; label shuffles [0, 0, 0, 0, 0].
- by layer: 
- strongest: L17/N3506 +0.13, L25/N1888 -0.12, L27/N7752 -0.12, L29/N3479 +0.12, L31/N8142 +0.12, L31/N5789 -0.12, L31/N8443 +0.12, L14/N626 +0.12, L7/N6796 +0.12, L22/N3800 -0.12, L12/N9047 +0.12, L20/N4536 -0.12

Heads (write norm, 896 heads): 0 pass in both folds; label shuffles [0, 0, 0, 0, 0].
- strongest: L1H11 +0.12, L24H15 -0.12, L22H1 -0.10, L3H1 -0.10, L25H10 -0.10, L24H25 -0.10, L2H14 +0.10, L20H5 -0.10, L5H26 -0.10, L22H4 -0.10

