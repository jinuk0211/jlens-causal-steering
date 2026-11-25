# CAUSAL-2 (Gemma-4-E4B-it): interventions over the whole response, greedy regeneration

- base reproduces the original tool: targets 63/90, references 40/40. Only reproducing units are scored.
- targets excluded (base did not reproduce), by risk: aligned 7/15, boundary 7/30, clearly-misaligned 13/45
- rev_* rows are on references only: 'refs kept' = still writeInternalLog; 1 - kept = deviation caused by the target-mean attention.

| config | flip mis+bnd | flip misaligned | flip boundary | flip aligned email | broken (targets) | other tool (targets) | refs kept | refs broken |
|---|---|---|---|---|---|---|---|---|
| base | 0/55 (0%) | 0/32 (0%) | 0/23 (0%) | 0/8 (0%) | 0/63 (0%) | 0/63 (0%) | 40/40 (100%) | 0/40 (0%) |
| attn_band_16_21 | 24/55 (44%) | 12/32 (38%) | 12/23 (52%) | 4/8 (50%) | 16/63 (25%) | 7/63 (11%) | 27/40 (68%) | 13/40 (32%) |
| attn_band_16_26 | 43/55 (78%) | 25/32 (78%) | 18/23 (78%) | 7/8 (88%) | 13/63 (21%) | 0/63 (0%) | 9/40 (22%) | 31/40 (78%) |
| attn_band_16_26_after | 44/55 (80%) | 25/32 (78%) | 19/23 (83%) | 6/8 (75%) | 12/63 (19%) | 1/63 (2%) | 9/40 (22%) | 31/40 (78%) |
| attn_band_16_26_onset | 6/55 (11%) | 3/32 (9%) | 3/23 (13%) | 0/8 (0%) | 3/63 (5%) | 3/63 (5%) | 40/40 (100%) | 0/40 (0%) |
| attn_band_21_26 | 51/55 (93%) | 28/32 (88%) | 23/23 (100%) | 8/8 (100%) | 0/63 (0%) | 1/63 (2%) | 40/40 (100%) | 0/40 (0%) |
| attn_band_28_38 | 10/55 (18%) | 6/32 (19%) | 4/23 (17%) | 2/8 (25%) | 12/63 (19%) | 39/63 (62%) | 1/40 (2%) | 20/40 (50%) |
| attn_band_4_14 | 13/55 (24%) | 5/32 (16%) | 8/23 (35%) | 1/8 (12%) | 19/63 (30%) | 8/63 (13%) | 28/40 (70%) | 12/40 (30%) |
| attn_full_17_23 | 41/55 (75%) | 22/32 (69%) | 19/23 (83%) | 5/8 (62%) | 4/63 (6%) | 3/63 (5%) | 34/40 (85%) | 5/40 (12%) |
| attn_rand11_d0 | 1/55 (2%) | 1/32 (3%) | 0/23 (0%) | 0/8 (0%) | 41/63 (65%) | 19/63 (30%) | 0/40 (0%) | 22/40 (55%) |
| attn_rand11_d1 | 5/55 (9%) | 3/32 (9%) | 2/23 (9%) | 1/8 (12%) | 6/63 (10%) | 13/63 (21%) | 17/40 (42%) | 22/40 (55%) |
| attn_rand11_d2 | 41/55 (75%) | 21/32 (66%) | 20/23 (87%) | 6/8 (75%) | 2/63 (3%) | 4/63 (6%) | 39/40 (98%) | 1/40 (2%) |
| attn_randfull_d0 | 8/55 (15%) | 6/32 (19%) | 2/23 (9%) | 1/8 (12%) | 7/63 (11%) | 5/63 (8%) | 27/40 (68%) | 11/40 (28%) |
| attn_randfull_d1 | 0/55 (0%) | 0/32 (0%) | 0/23 (0%) | 0/8 (0%) | 0/63 (0%) | 50/63 (79%) | 0/40 (0%) | 4/40 (10%) |
| attn_randfull_d2 | 11/55 (20%) | 3/32 (9%) | 8/23 (35%) | 2/8 (25%) | 13/63 (21%) | 8/63 (13%) | 25/40 (62%) | 14/40 (35%) |
| attn_sliding_16_26 | 41/55 (75%) | 20/32 (62%) | 21/23 (91%) | 6/8 (75%) | 3/63 (5%) | 5/63 (8%) | 34/40 (85%) | 6/40 (15%) |
| mlp_band_16_26 | 0/55 (0%) | 0/32 (0%) | 0/23 (0%) | 0/8 (0%) | 63/63 (100%) | 0/63 (0%) | 0/40 (0%) | 40/40 (100%) |
| mlp_band_28_38 | 0/55 (0%) | 0/32 (0%) | 0/23 (0%) | 0/8 (0%) | 63/63 (100%) | 0/63 (0%) | 0/40 (0%) | 40/40 (100%) |
| neur_rand_1024 | 3/55 (5%) | 2/32 (6%) | 1/23 (4%) | 1/8 (12%) | 3/63 (5%) | 2/63 (3%) | 40/40 (100%) | 0/40 (0%) |
| neur_rand_256 | 5/55 (9%) | 4/32 (12%) | 1/23 (4%) | 0/8 (0%) | 0/63 (0%) | 4/63 (6%) | 38/40 (95%) | 0/40 (0%) |
| neur_rand_256_L16_26 | 6/55 (11%) | 5/32 (16%) | 1/23 (4%) | 0/8 (0%) | 1/63 (2%) | 3/63 (5%) | 39/40 (98%) | 0/40 (0%) |
| neur_rand_64 | 1/55 (2%) | 1/32 (3%) | 0/23 (0%) | 1/8 (12%) | 2/63 (3%) | 2/63 (3%) | 40/40 (100%) | 0/40 (0%) |
| neur_top_1024 | 7/55 (13%) | 3/32 (9%) | 4/23 (17%) | 0/8 (0%) | 6/63 (10%) | 4/63 (6%) | 38/40 (95%) | 0/40 (0%) |
| neur_top_256 | 7/55 (13%) | 5/32 (16%) | 2/23 (9%) | 0/8 (0%) | 6/63 (10%) | 4/63 (6%) | 40/40 (100%) | 0/40 (0%) |
| neur_top_256_L16_26 | 4/55 (7%) | 2/32 (6%) | 2/23 (9%) | 0/8 (0%) | 7/63 (11%) | 4/63 (6%) | 38/40 (95%) | 2/40 (5%) |
| neur_top_64 | 3/55 (5%) | 2/32 (6%) | 1/23 (4%) | 1/8 (12%) | 1/63 (2%) | 4/63 (6%) | 40/40 (100%) | 0/40 (0%) |
| rev_attn_band_16_26 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 8/40 (20%) | 32/40 (80%) |
| rev_attn_full_17_23 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | 24/40 (60%) | 11/40 (28%) |

## Verdict (flip ≥ 50 % mis+bnd, matched random ≤ 10 %, broken ≤ 10 %, refs kept ≥ 90 %)

- attn_band_16_21: no (band edit: no matched random control, reported descriptively)
- attn_band_16_26: no (band edit: no matched random control, reported descriptively)
- attn_band_16_26_after: no (band edit: no matched random control, reported descriptively)
- attn_band_16_26_onset: no (band edit: no matched random control, reported descriptively)
- attn_band_21_26: no (band edit: no matched random control, reported descriptively)
- attn_band_28_38: no (band edit: no matched random control, reported descriptively)
- attn_band_4_14: no (band edit: no matched random control, reported descriptively)
- mlp_band_16_26: no (band edit: no matched random control, reported descriptively)
- mlp_band_28_38: no (band edit: no matched random control, reported descriptively)
- neur_top_1024: no
- neur_top_256: no
- neur_top_256_L16_26: no
- neur_top_64: no
