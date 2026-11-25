# M1b: mean-ablating the attributed neurons (selected out of fold) vs random neurons from the same layers

| group | K | bad flip (top) | bad flip (random) | good kept (top) | good kept (random) | mean dm bad (top) | layers (top) | localized? |
|---|---|---|---|---|---|---|---|---|
| all:T-args | 16 | 0.00 | 0.00 | 1.0 | 1.0 | -0.08 | [6, 17, 23, 27, 28, 29, 30, 31] | no |
| all:T-args | 64 | 0.00 | 0.00 | 1.0 | 1.0 | -0.83 | [6, 7, 8, 9, 17, 18, 19, 20, 21, 22, 23, 27] | no |
| all:T-args | 256 | 0.00 | 0.00 | 1.0 | 1.0 | -1.65 | [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] | no |
| all:T-call | 16 | 0.03 | 0.03 | 0.99 | 1.0 | -0.45 | [15, 17, 18, 20, 21, 28, 29, 30, 31] | no |
| all:T-call | 64 | 0.08 | 0.00 | 0.96 | 1.0 | -1.25 | [6, 7, 13, 15, 16, 17, 18, 19, 20, 21, 22, 23] | no |
| all:T-call | 256 | 0.23 | 0.03 | 0.91 | 1.0 | -2.65 | [3, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16] | no |
| all:T-name | 16 | 0.00 | 0.00 | 1.0 | 1.0 | -2.18 | [18, 20, 22, 24, 26, 27, 28, 29, 30, 31] | no |
| all:T-name | 64 | 0.00 | 0.00 | 1.0 | 1.0 | -4.00 | [2, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27] | no |
| all:T-name | 256 | 0.25 | 0.00 | 1.0 | 1.0 | -6.47 | [2, 4, 5, 6, 8, 9, 13, 14, 15, 16, 17, 18] | no |
| unexpected_transfer:T-call | 16 | 0.00 | 0.00 | 0.98 | 1.0 | -0.54 | [14, 17, 18, 19, 20, 21, 22, 23, 27, 28, 29, 30] | no |
| unexpected_transfer:T-call | 64 | 0.30 | 0.00 | 0.96 | 1.0 | -1.70 | [6, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24] | YES |
| unexpected_transfer:T-call | 256 | 0.50 | 0.00 | 0.91 | 1.0 | -3.76 | [3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 16, 17] | YES |
| unexpected_transfer:T-name | 16 | 0.00 | 0.00 | 1.0 | 1.0 | -2.82 | [17, 18, 23, 27, 29, 30, 31] | no |
| unexpected_transfer:T-name | 64 | 0.00 | 0.00 | 1.0 | 1.0 | -4.55 | [6, 9, 16, 17, 18, 19, 20, 21, 22, 23, 26, 27] | no |
| unexpected_transfer:T-name | 256 | 0.00 | 0.00 | 1.0 | 1.0 | -6.78 | [3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15] | no |
| unexpected_write:T-call | 16 | 0.05 | 0.00 | 0.97 | 1.0 | -0.66 | [6, 13, 15, 18, 19, 20, 21, 22, 24, 25, 27, 28] | no |
| unexpected_write:T-call | 64 | 0.11 | 0.00 | 0.96 | 1.0 | -1.84 | [6, 7, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21] | no |
| unexpected_write:T-call | 256 | 0.26 | 0.05 | 0.89 | 1.0 | -3.43 | [0, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13] | no |
| unexpected_write:T-name | 16 | 0.00 | 0.00 | 1.0 | 1.0 | -0.60 | [17, 18, 21, 24, 27, 29, 30, 31] | no |
| unexpected_write:T-name | 64 | 0.00 | 0.00 | 1.0 | 1.0 | -1.33 | [8, 15, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26] | no |
| unexpected_write:T-name | 256 | 0.00 | 0.00 | 1.0 | 1.0 | -2.74 | [3, 5, 7, 8, 9, 10, 12, 13, 15, 16, 17, 18] | no |
| wrong_args:T-args | 16 | 0.00 | 0.00 | 1.0 | 1.0 | -0.08 | [6, 17, 23, 27, 28, 29, 30, 31] | no |
| wrong_args:T-args | 64 | 0.00 | 0.00 | 1.0 | 1.0 | -0.83 | [6, 7, 8, 9, 17, 18, 19, 20, 21, 22, 23, 27] | no |
| wrong_args:T-args | 256 | 0.00 | 0.00 | 1.0 | 1.0 | -1.65 | [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] | no |
| wrong_args:T-call | 16 | 0.00 | 0.00 | 1.0 | 1.0 | -0.73 | [22, 24, 29, 30, 31] | no |
| wrong_args:T-call | 64 | 0.10 | 0.00 | 1.0 | 1.0 | -1.92 | [13, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25] | no |
| wrong_args:T-call | 256 | 0.10 | 0.00 | 1.0 | 1.0 | -2.93 | [0, 1, 2, 4, 5, 6, 7, 8, 10, 12, 13, 14] | no |
| wrong_args:T-name | 16 | 0.00 | 0.00 | 1.0 | 1.0 | -5.55 | [20, 22, 24, 25, 26, 28, 29, 30, 31] | no |
| wrong_args:T-name | 64 | 0.09 | 0.00 | 1.0 | 1.0 | -9.09 | [2, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27] | no |
| wrong_args:T-name | 256 | 0.68 | 0.00 | 1.0 | 1.0 | -13.61 | [2, 5, 6, 9, 12, 13, 14, 15, 16, 17, 18, 19] | YES |

- baseline check: mean |m_base - m_extract| = 0.086

## Verdict (pre-registered: flip >= 30 %, random <= 5 %, good kept >= 90 % at some K)

- all:T-args: not localized to a sparse neuron set
- all:T-call: not localized to a sparse neuron set
- all:T-name: not localized to a sparse neuron set
- unexpected_transfer:T-call: LOCALIZED
- unexpected_transfer:T-name: not localized to a sparse neuron set
- unexpected_write:T-call: not localized to a sparse neuron set
- unexpected_write:T-name: not localized to a sparse neuron set
- wrong_args:T-args: not localized to a sparse neuron set
- wrong_args:T-call: not localized to a sparse neuron set
- wrong_args:T-name: LOCALIZED
