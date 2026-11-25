# G1 split: CAUSAL-1 flips (misaligned+boundary targets) by preamble length and condition

| op | preamble<10 (n=47) | preamble>=10 (n=17) | without-reasoning (n=37) | with-reasoning (n=27) |
|---|---|---|---|---|
| attn@16 | 3/47 | 0/17 | 1/37 | 2/27 |
| attn_all | 47/47 | 17/17 | 37/37 | 27/27 |
| attn_band | 28/47 | 0/17 | 21/37 | 7/27 |
| base | 0/47 | 0/17 | 0/37 | 0/27 |
| mlp@22 | 3/47 | 0/17 | 1/37 | 2/27 |
| mlp_all | 9/47 | 0/17 | 5/37 | 4/27 |
| mlp_band | 5/47 | 0/17 | 3/37 | 2/27 |
| neur_random_16 | 0/47 | 0/17 | 0/37 | 0/27 |
| neur_random_256 | 1/47 | 0/17 | 0/37 | 1/27 |
| neur_random_64 | 0/47 | 0/17 | 0/37 | 0/27 |
| neur_top_16 | 19/47 | 0/17 | 13/37 | 6/27 |
| neur_top_256 | 46/47 | 1/17 | 33/37 | 14/27 |
| neur_top_64 | 42/47 | 0/17 | 29/37 | 13/27 |
| res_dir@30 | 47/47 | 17/17 | 37/37 | 27/27 |
| res_full@28 | 47/47 | 17/17 | 37/37 | 27/27 |
| res_rand@18 | 1/47 | 0/17 | 0/37 | 1/27 |

Families with a layer grid show their best layer over all targets (max flips), so read them as optimistic.
