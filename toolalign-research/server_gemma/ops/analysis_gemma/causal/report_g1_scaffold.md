# G1 split, scaffold-corrected (POST-HOC definition fix): no text preamble = onset->name distance == 11 tokens (the XML scaffold only)

| op | no text preamble | with text preamble |
|---|---|---|
| neur_top_16 | 31/81 | 8/91 |
| neur_top_64 | 74/81 | 13/91 |
| neur_top_256 | 81/81 | 36/91 |
| neur_random_256 | 0/81 | 0/91 |
| attn_band | 81/81 | 69/91 |
| mlp_band | 81/81 | 42/91 |
| attn_all | 81/81 | 91/91 |
| mlp_all | 81/81 | 89/91 |
| res_dir@40 | 43/81 | 13/91 |
| res_full@20 | 16/81 | 8/91 |
| res_full@28 | 81/81 | 91/91 |
| attn@22 | 27/81 | 9/91 |
| mlp@22 | 49/81 | 11/91 |
| attn@26 | 0/81 | 3/91 |
| mlp@26 | 7/81 | 5/91 |

best single-layer op among WITH-preamble units: {'res_full': ('res_full@28', 91), 'res_dir': ('res_dir@40', 13), 'res_rand': ('res_rand@8', 1), 'attn': ('attn@22', 9), 'mlp': ('mlp@24', 12)} n= 91
