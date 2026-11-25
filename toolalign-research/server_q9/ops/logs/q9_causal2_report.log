# CAUSAL-2 (Qwen3.5-9B, J++ lens): interventions over the whole response, greedy regeneration

- base reproduces the original tool: targets 65/82, references 36/40. Only reproducing units are scored.
- targets excluded (base did not reproduce), by risk: aligned 1/18, boundary 10/41, clearly-misaligned 6/23
- rev_* rows are on references only: 'refs kept' = still writeInternalLog; 1 - kept = deviation caused by the target-mean attention.

| config | flip mis+bnd | flip misaligned | flip boundary | flip aligned email | broken (targets) | other tool (targets) | refs kept | refs broken |
|---|---|---|---|---|---|---|---|---|
| base | 0/48 (0%) | 0/17 (0%) | 0/31 (0%) | 0/17 (0%) | 0/65 (0%) | 0/65 (0%) | 36/36 (100%) | 0/36 (0%) |
| attn_band_12_16 | 29/48 (60%) | 12/17 (71%) | 17/31 (55%) | 14/17 (82%) | 1/65 (2%) | 0/65 (0%) | 35/36 (97%) | 1/36 (3%) |
| attn_band_12_20 | 48/48 (100%) | 17/17 (100%) | 31/31 (100%) | 17/17 (100%) | 0/65 (0%) | 0/65 (0%) | 27/36 (75%) | 9/36 (25%) |
| attn_band_16_20 | 48/48 (100%) | 17/17 (100%) | 31/31 (100%) | 17/17 (100%) | 0/65 (0%) | 0/65 (0%) | 35/36 (97%) | 1/36 (3%) |
| attn_band_16_20_after | 48/48 (100%) | 17/17 (100%) | 31/31 (100%) | 17/17 (100%) | 0/65 (0%) | 0/65 (0%) | 35/36 (97%) | 1/36 (3%) |
| attn_band_16_20_onset | 0/48 (0%) | 0/17 (0%) | 0/31 (0%) | 0/17 (0%) | 1/65 (2%) | 0/65 (0%) | 34/36 (94%) | 2/36 (6%) |
| attn_band_21_29 | 8/48 (17%) | 4/17 (24%) | 4/31 (13%) | 7/17 (41%) | 22/65 (34%) | 0/65 (0%) | 25/36 (69%) | 11/36 (31%) |
| attn_band_3_11 | 4/48 (8%) | 3/17 (18%) | 1/31 (3%) | 1/17 (6%) | 6/65 (9%) | 1/65 (2%) | 28/36 (78%) | 8/36 (22%) |
| attn_full_15_19 | 46/48 (96%) | 17/17 (100%) | 29/31 (94%) | 17/17 (100%) | 2/65 (3%) | 0/65 (0%) | 33/36 (92%) | 3/36 (8%) |
| attn_lin_12_20 | 37/48 (77%) | 15/17 (88%) | 22/31 (71%) | 13/17 (76%) | 0/65 (0%) | 0/65 (0%) | 36/36 (100%) | 0/36 (0%) |
| attn_rand9_d0 | 16/48 (33%) | 6/17 (35%) | 10/31 (32%) | 12/17 (71%) | 0/65 (0%) | 1/65 (2%) | 31/36 (86%) | 5/36 (14%) |
| attn_rand9_d1 | 12/48 (25%) | 7/17 (41%) | 5/31 (16%) | 4/17 (24%) | 5/65 (8%) | 2/65 (3%) | 25/36 (69%) | 11/36 (31%) |
| attn_rand9_d2 | 3/48 (6%) | 2/17 (12%) | 1/31 (3%) | 4/17 (24%) | 11/65 (17%) | 4/65 (6%) | 21/36 (58%) | 15/36 (42%) |
| attn_randfull_d0 | 11/48 (23%) | 2/17 (12%) | 9/31 (29%) | 11/17 (65%) | 4/65 (6%) | 1/65 (2%) | 30/36 (83%) | 6/36 (17%) |
| attn_randfull_d1 | 0/48 (0%) | 0/17 (0%) | 0/31 (0%) | 0/17 (0%) | 50/65 (77%) | 1/65 (2%) | 18/36 (50%) | 18/36 (50%) |
| attn_randfull_d2 | 0/48 (0%) | 0/17 (0%) | 0/31 (0%) | 0/17 (0%) | 65/65 (100%) | 0/65 (0%) | 0/36 (0%) | 36/36 (100%) |
| mlp_band_12_20 | 29/48 (60%) | 12/17 (71%) | 17/31 (55%) | 12/17 (71%) | 11/65 (17%) | 1/65 (2%) | 4/36 (11%) | 32/36 (89%) |
| mlp_band_21_29 | 16/48 (33%) | 6/17 (35%) | 10/31 (32%) | 8/17 (47%) | 12/65 (18%) | 1/65 (2%) | 3/36 (8%) | 33/36 (92%) |
| neur_rand_1024 | 1/48 (2%) | 1/17 (6%) | 0/31 (0%) | 1/17 (6%) | 1/65 (2%) | 0/65 (0%) | 35/36 (97%) | 1/36 (3%) |
| neur_rand_256 | 0/48 (0%) | 0/17 (0%) | 0/31 (0%) | 1/17 (6%) | 1/65 (2%) | 0/65 (0%) | 35/36 (97%) | 1/36 (3%) |
| neur_rand_256_L12_20 | 1/48 (2%) | 1/17 (6%) | 0/31 (0%) | 0/17 (0%) | 1/65 (2%) | 0/65 (0%) | 34/36 (94%) | 2/36 (6%) |
| neur_rand_64 | 0/48 (0%) | 0/17 (0%) | 0/31 (0%) | 0/17 (0%) | 0/65 (0%) | 0/65 (0%) | 35/36 (97%) | 1/36 (3%) |
| neur_top_1024 | 6/48 (12%) | 3/17 (18%) | 3/31 (10%) | 3/17 (18%) | 2/65 (3%) | 1/65 (2%) | 34/36 (94%) | 2/36 (6%) |
| neur_top_256 | 2/48 (4%) | 2/17 (12%) | 0/31 (0%) | 0/17 (0%) | 1/65 (2%) | 1/65 (2%) | 34/36 (94%) | 2/36 (6%) |
| neur_top_256_L12_20 | 0/48 (0%) | 0/17 (0%) | 0/31 (0%) | 0/17 (0%) | 0/65 (0%) | 0/65 (0%) | 36/36 (100%) | 0/36 (0%) |
| neur_top_64 | 0/48 (0%) | 0/17 (0%) | 0/31 (0%) | 0/17 (0%) | 1/65 (2%) | 0/65 (0%) | 35/36 (97%) | 1/36 (3%) |
| rev_attn_band_16_20 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 34/36 (94%) | 2/36 (6%) |
| rev_attn_full_15_19 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 24/36 (67%) | 1/36 (3%) |

## Verdict (flip ≥ 50 % mis+bnd, matched random ≤ 10 %, broken ≤ 10 %, refs kept ≥ 90 %)

- attn_band_12_16: no (band edit: no matched random control, reported descriptively)
- attn_band_12_20: no (band edit: no matched random control, reported descriptively)
- attn_band_16_20: no (band edit: no matched random control, reported descriptively)
- attn_band_16_20_after: no (band edit: no matched random control, reported descriptively)
- attn_band_16_20_onset: no (band edit: no matched random control, reported descriptively)
- attn_band_21_29: no (band edit: no matched random control, reported descriptively)
- attn_band_3_11: no (band edit: no matched random control, reported descriptively)
- mlp_band_12_20: no (band edit: no matched random control, reported descriptively)
- mlp_band_21_29: no (band edit: no matched random control, reported descriptively)
- neur_top_1024: no
- neur_top_256: no
- neur_top_256_L12_20: no
- neur_top_64: no
