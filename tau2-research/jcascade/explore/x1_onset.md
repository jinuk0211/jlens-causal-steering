# X1: when does the transfer intention show up in the J-lens readout? (decision points, top-100, L20-31)

transfer rows: bad 19, good 56; base rate from 3355 decision points of episodes that never transfer

- base: mean layers with a transfer word in top-100 = 0.00; share of decision points with >= 3 such layers = 0.000

| lag (turns before the transfer turn) | n bad / good | mean #layers bad | mean #layers good | AUC (bad vs good, #layers) | share >= 3 layers bad | good |
|---|---|---|---|---|---|---|
| 0 | 19 / 56 | 1.00 | 0.61 | 0.578 | 0.11 | 0.11 |
| 1 | 19 / 56 | 0.00 | 0.00 | 0.5 | 0.00 | 0.00 |
| 2 | 19 / 56 | 0.00 | 0.00 | 0.5 | 0.00 | 0.00 |
| 3 | 19 / 54 | 0.05 | 0.00 | 0.526 | 0.00 | 0.00 |
| 4 | 18 / 52 | 0.00 | 0.02 | 0.49 | 0.00 | 0.00 |
| 5 | 17 / 50 | 0.00 | 0.00 | 0.5 | 0.00 | 0.00 |

onset = number of consecutive earlier turns (before the transfer turn) with >= 3 layers showing a transfer word:

- bad: onset distribution {0: 19}, mean 0.00
- good: onset distribution {0: 56}, mean 0.00

per-layer mean readout score (101 - rank)/100 at lag 0 and lag 1:

| layer | lag0 bad | lag0 good | lag1 bad | lag1 good |
|---|---|---|---|---|
| L20 | 0.00 | 0.00 | 0.00 | 0.00 |
| L21 | 0.00 | 0.00 | 0.00 | 0.00 |
| L22 | 0.00 | 0.00 | 0.00 | 0.00 |
| L23 | 0.03 | 0.00 | 0.00 | 0.00 |
| L24 | 0.00 | 0.00 | 0.00 | 0.00 |
| L25 | 0.03 | 0.00 | 0.00 | 0.00 |
| L26 | 0.00 | 0.00 | 0.00 | 0.00 |
| L27 | 0.06 | 0.05 | 0.00 | 0.00 |
| L28 | 0.10 | 0.07 | 0.00 | 0.00 |
| L29 | 0.09 | 0.06 | 0.00 | 0.00 |
| L30 | 0.10 | 0.06 | 0.00 | 0.00 |
| L31 | 0.24 | 0.15 | 0.00 | 0.00 |

by domain, lag 1 mean #layers (bad / good):

- airline: bad 0.00 (n 10), good 0.00 (n 21)
- retail: bad 0.00 (n 4), good 0.00 (n 8)
- telecom: bad 0.00 (n 5), good 0.00 (n 27)
