# J-lens vs J++ vs both: decision-point (layer, word) pairs, out-of-fold AUC (5 folds grouped by task)

| lens | rows | bad | good | A_pairs AUC [CI] | tool-only AUC | within-tool AUC |
|---|---|---|---|---|---|---|
| jlens | W_clean_all | 40 | 249 | 0.741 [0.657, 0.83] | 0.826 | 0.589 |
| jlens | W_clean_no_transfer | 21 | 227 | 0.68 [0.529, 0.799] | 0.816 | 0.464 |
| jlens | W_clean_wrong_args_or_unexpected_write | 21 | 227 | 0.68 [0.531, 0.811] | 0.816 | 0.464 |
| jlens | transfer_only | 19 | 22 | 0.902 [0.788, 0.981] | 0.348 | 0.902 |
| jpp | W_clean_all | 40 | 249 | 0.776 [0.699, 0.854] | 0.826 | 0.622 |
| jpp | W_clean_no_transfer | 21 | 227 | 0.605 [0.465, 0.744] | 0.816 | 0.417 |
| jpp | W_clean_wrong_args_or_unexpected_write | 21 | 227 | 0.605 [0.48, 0.735] | 0.816 | 0.417 |
| jpp | transfer_only | 19 | 22 | 0.878 [0.746, 0.978] | 0.348 | 0.878 |
| jlens+jpp | W_clean_all | 40 | 249 | 0.75 [0.673, 0.842] | 0.826 | 0.593 |
| jlens+jpp | W_clean_no_transfer | 21 | 227 | 0.64 [0.506, 0.767] | 0.816 | 0.468 |
| jlens+jpp | W_clean_wrong_args_or_unexpected_write | 21 | 227 | 0.64 [0.498, 0.77] | 0.816 | 0.468 |
| jlens+jpp | transfer_only | 19 | 22 | 0.888 [0.774, 0.977] | 0.348 | 0.888 |
