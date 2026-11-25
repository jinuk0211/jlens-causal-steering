# C2T: ToolAlign CAUSAL-2 intervention on tau2 (Qwen3.5-4B, greedy regeneration of one agent turn)

- base reproduces the original call (and ends): A 32/34, B 29/29, K 40/40, L 21/22. Only reproducing units are scored.
- A = unneeded transfers, B = unexpected writes, L = legitimate transfers, K = correct non-transfer writes.
- flip = original call absent and the turn ended; unfinished = budget hit; verbal = no transfer call but transfer language in the text.

| config | A flip | A unfinished | A verbal-of-flips | B flip | L flip (legit transfers) | K kept | K unfinished |
|---|---|---|---|---|---|---|---|
| base | 0/32 (0%) | 0/32 (0%) | 0/0 | 0/29 (0%) | 0/21 (0%) | 40/40 (100%) | 0/40 (0%) |
| attn_27 | 2/32 (6%) | 1/32 (3%) | 1/2 (50%) | 3/29 (10%) | 5/21 (24%) | 39/40 (98%) | 0/40 (0%) |
| attn_band_10_18 | 28/32 (88%) | 0/32 (0%) | 3/28 (11%) | 25/29 (86%) | 20/21 (95%) | 20/40 (50%) | 0/40 (0%) |
