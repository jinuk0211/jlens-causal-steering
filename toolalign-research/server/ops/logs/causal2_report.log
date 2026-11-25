# CAUSAL-2: interventions over the whole response, greedy regeneration

- base reproduces the original tool: targets 39/53, references 37/40. Only reproducing units are scored.

| config | flip mis+bnd | flip misaligned | flip boundary | flip aligned email | broken (targets) | other tool (targets) | refs kept | refs broken |
|---|---|---|---|---|---|---|---|---|
| base | 0/31 (0%) | 0/9 (0%) | 0/22 (0%) | 0/8 (0%) | 0/39 (0%) | 0/39 (0%) | 37/37 (100%) | 0/37 (0%) |
| attn_band_12_16 | 13/31 (42%) | 5/9 (56%) | 8/22 (36%) | 2/8 (25%) | 16/39 (41%) | 1/39 (3%) | 34/37 (92%) | 3/37 (8%) |
| attn_band_12_20 | 25/31 (81%) | 9/9 (100%) | 16/22 (73%) | 8/8 (100%) | 6/39 (15%) | 0/39 (0%) | 35/37 (95%) | 2/37 (5%) |
| attn_band_16_20 | 27/31 (87%) | 8/9 (89%) | 19/22 (86%) | 7/8 (88%) | 1/39 (3%) | 1/39 (3%) | 36/37 (97%) | 1/37 (3%) |
| attn_band_21_29 | 7/31 (23%) | 4/9 (44%) | 3/22 (14%) | 5/8 (62%) | 23/39 (59%) | 0/39 (0%) | 17/37 (46%) | 20/37 (54%) |
| attn_band_3_11 | 2/31 (6%) | 1/9 (11%) | 1/22 (5%) | 1/8 (12%) | 23/39 (59%) | 0/39 (0%) | 32/37 (86%) | 3/37 (8%) |
| attn_full_15_19 | 25/31 (81%) | 9/9 (100%) | 16/22 (73%) | 5/8 (62%) | 9/39 (23%) | 0/39 (0%) | 35/37 (95%) | 2/37 (5%) |
| attn_lin_12_20 | 17/31 (55%) | 3/9 (33%) | 14/22 (64%) | 5/8 (62%) | 3/39 (8%) | 2/39 (5%) | 37/37 (100%) | 0/37 (0%) |
| mlp_band_12_20 | 8/31 (26%) | 2/9 (22%) | 6/22 (27%) | 4/8 (50%) | 27/39 (69%) | 0/39 (0%) | 30/37 (81%) | 7/37 (19%) |
| mlp_band_21_29 | 13/31 (42%) | 5/9 (56%) | 8/22 (36%) | 3/8 (38%) | 15/39 (38%) | 1/39 (3%) | 34/37 (92%) | 3/37 (8%) |
| neur_rand_1024 | 3/31 (10%) | 3/9 (33%) | 0/22 (0%) | 1/8 (12%) | 4/39 (10%) | 0/39 (0%) | 35/37 (95%) | 2/37 (5%) |
| neur_rand_256 | 3/31 (10%) | 1/9 (11%) | 2/22 (9%) | 0/8 (0%) | 3/39 (8%) | 0/39 (0%) | 35/37 (95%) | 2/37 (5%) |
| neur_rand_256_L12_20 | 0/31 (0%) | 0/9 (0%) | 0/22 (0%) | 0/8 (0%) | 1/39 (3%) | 1/39 (3%) | 36/37 (97%) | 1/37 (3%) |
| neur_rand_64 | 0/31 (0%) | 0/9 (0%) | 0/22 (0%) | 0/8 (0%) | 5/39 (13%) | 0/39 (0%) | 36/37 (97%) | 1/37 (3%) |
| neur_top_1024 | 4/31 (13%) | 4/9 (44%) | 0/22 (0%) | 0/8 (0%) | 3/39 (8%) | 1/39 (3%) | 34/37 (92%) | 3/37 (8%) |
| neur_top_256 | 3/31 (10%) | 3/9 (33%) | 0/22 (0%) | 1/8 (12%) | 2/39 (5%) | 1/39 (3%) | 36/37 (97%) | 1/37 (3%) |
| neur_top_256_L12_20 | 0/31 (0%) | 0/9 (0%) | 0/22 (0%) | 0/8 (0%) | 1/39 (3%) | 1/39 (3%) | 35/37 (95%) | 2/37 (5%) |
| neur_top_64 | 3/31 (10%) | 3/9 (33%) | 0/22 (0%) | 0/8 (0%) | 0/39 (0%) | 0/39 (0%) | 37/37 (100%) | 0/37 (0%) |

## Verdict (flip ≥ 50 % mis+bnd, matched random ≤ 10 %, broken ≤ 10 %, refs kept ≥ 90 %)

- attn_band_12_16: no (band edit: no matched random control, reported descriptively)
- attn_band_12_20: no (band edit: no matched random control, reported descriptively)
- attn_band_16_20: no (band edit: no matched random control, reported descriptively)
- attn_band_21_29: no (band edit: no matched random control, reported descriptively)
- attn_band_3_11: no (band edit: no matched random control, reported descriptively)
- mlp_band_12_20: no (band edit: no matched random control, reported descriptively)
- mlp_band_21_29: no (band edit: no matched random control, reported descriptively)
- neur_top_1024: no
- neur_top_256: no
- neur_top_256_L12_20: no
- neur_top_64: no
