# J-lens analyses B-F, am (Qwen3.5-4B)

594 units: reference 540, target 54; 12 groups; layers 0..30 + final.

## Decision positions (one structural rule for both classes)

reference recipient: 290; reference skip:no_recipient: 62; reference skip:no_tool: 60; reference tool: 128; target recipient: 42; target tool: 12

## C. Decision-position margin lp(T) - max lp(A), target - reference within group

| layer | 0 | 3 | 6 | 9 | 12 | 15 | 18 | 21 | 24 | 27 | 30 | final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mean | -0.01 | -0.02 | -0.32 | -0.52 | +0.93 | +1.18 | +1.89 | +3.48 | +10.60 | +11.48 | +9.99 | +8.74 |
| 95% CI | [-0.12,+0.12] | [-0.11,+0.06] | [-0.65,-0.02] | [-0.74,-0.24] | [+0.32,+1.75] | [+0.46,+2.10] | [+1.22,+2.61] | [+2.32,+4.74] | [+8.65,+12.56] | [+5.50,+17.81] | [+5.79,+14.51] | [+5.65,+11.60] |

- 8 groups with both classes; CI excludes 0 at layers ['4', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', 'final']

- kind recipient: 4 groups, final +10.35, L16 +1.16, L24 +10.29
- kind tool: 4 groups, final +7.12, L16 +1.84, L24 +10.92

## AUC profile (CALIBRATION fold, PLAN boundary rule 4; reported, not used to pick the band)

| layer | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 | 30 | final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AUC | 0.54 | 0.64 | 0.50 | 0.68 | 0.59 | 0.59 | 0.55 | 0.37 | 0.33 | 0.45 | 0.50 | 0.63 | 0.78 | 0.75 | 0.76 | 0.83 | 0.85 | 0.86 | 0.91 | 0.87 | 0.89 | 0.87 | 0.86 | 0.92 | 0.92 | 0.91 | 0.92 | 0.88 | 0.89 | 0.90 | 0.87 | 0.88 |

- onset layer (first layer with AUC >= 0.75 that stays there): 12

## D. Lock-in layer of the chosen candidate at the decision position

| class | kind | n | lock-in median [IQR] | never locked |
|---|---|---|---|---|
| reference | recipient | 282 | [23.0, 23.0, 27.0] | 19 |
| reference | tool | 128 | [16.0, 18.0, 23.8] | 4 |
| target | recipient | 42 | [23.0, 24.0, 24.0] | 0 |
| target | tool | 12 | [16.5, 19.0, 24.5] | 1 |

## E. Onset lp('<'), target - reference within group

| layer | 0 | 3 | 6 | 9 | 12 | 15 | 18 | 21 | 24 | 27 | 30 | final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mean | +0.00 | +0.01 | +0.02 | -0.00 | +0.01 | -0.00 | +0.01 | +0.00 | +0.01 | -0.01 | +0.00 | -0.00 |
| 95% CI | [-0.00,+0.00] | [+0.00,+0.02] | [-0.00,+0.04] | [-0.04,+0.03] | [-0.00,+0.02] | [-0.02,+0.01] | [-0.00,+0.02] | [-0.01,+0.02] | [-0.00,+0.02] | [-0.02,+0.00] | [-0.00,+0.00] | [-0.00,+0.00] |

## B. Onset words: top-30 in >= 9/16 of target groups (8) and <= 3/16 of reference groups (12); held-out group presence


## F. Top words at recipient / argument positions (first 10 of top-30, counts)

- reference to (n=762): L8 ' [...]', ' ...', ' (...)', '......', ' [...'; L12 ' ...', ' [...]', '......', ' ......', '...'; L16 ' email', ' Mail', ' emails', ' Emails', ' Twitter'; L20 ' gmail', ' email', ' whatsapp', ' michael', ' firstname'; L24 ' john', ' michael', ' robert', ' david', ' gmail'; L28 ' david', ' alex', ' todd', ' robert', ' David'; Lfinal ' th', ' david', ' "', ' k', ' alex'
- target to (n=114): L8 ' [...]', '......', ' ...', ' (...)', ' [...'; L12 ' ...', ' [...]', ' (...)', '...', '......'; L16 ' email', ' Mail', ' emails', ' Emails', ' Email'; L20 ' gmail', ' email', '-email', ' Gmail', ' emails'; L24 ' john', ' gmail', ' michael', ' secure', ' Secure'; L28 ' robert', ' secure', ' alex', ' Secure', 'secure'; Lfinal ' robert', ' alex', ' "', ' secure', ' security'
