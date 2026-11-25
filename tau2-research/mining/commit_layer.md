# J-lens commitment layer of the tool-name token (counterpart of M1's formation layer)

units: {'BW': 9, 'BT': 19, 'GT': 22, 'GW': 227}

| group | n | tasks | commit layer median (IQR) | first layer in top-30 median | first top-1 median | top-1 already at L20 | at L24 | at L27 |
|---|---|---|---|---|---|---|---|---|
| BT | 19 | 19 | 30 (30-30) | 20 | 23 | 0.00 | 0.95 | 0.00 |
| GT | 22 | 22 | 29 (29-30) | 23 | 23 | 0.00 | 0.95 | 0.00 |
| BW | 9 | 8 | 30 (30-30) | 18 | 23 | 0.00 | 0.56 | 0.00 |
| GW | 227 | 147 | 30 (30-30) | 23 | 26 | 0.00 | 0.21 | 0.01 |
- BT vs GT: AUC of an EARLIER commit layer = 0.208 (task-cluster CI [0.1, 0.321])
- BT vs GT: AUC of an EARLIER enter layer = 0.598 (task-cluster CI [0.439, 0.76])
- BT vs GT: AUC of an EARLIER first_top1 layer = 0.496 (task-cluster CI [0.425, 0.567])
- BW vs GW: AUC of an EARLIER commit layer = 0.471 (task-cluster CI [0.452, 0.487])
- BW vs GW: AUC of an EARLIER enter layer = 0.745 (task-cluster CI [0.589, 0.913])
- BW vs GW: AUC of an EARLIER first_top1 layer = 0.650 (task-cluster CI [0.45, 0.822])

Mean rank of the chosen tool-name token by layer (0 = top-1, 30 = not in top-30):

| layer | BT | GT | BW | GW |
|---|---|---|---|---|
| L12 | 30.0 | 30.0 | 30.0 | 30.0 |
| L13 | 30.0 | 30.0 | 30.0 | 29.9 |
| L14 | 30.0 | 30.0 | 25.9 | 29.5 |
| L15 | 30.0 | 30.0 | 25.7 | 29.2 |
| L16 | 30.0 | 30.0 | 27.1 | 29.1 |
| L17 | 30.0 | 30.0 | 26.7 | 28.4 |
| L18 | 30.0 | 30.0 | 19.7 | 27.7 |
| L19 | 25.5 | 25.5 | 19.6 | 27.3 |
| L20 | 19.9 | 23.3 | 16.3 | 27.3 |
| L21 | 21.8 | 25.5 | 15.6 | 26.9 |
| L22 | 24.2 | 28.8 | 13.7 | 25.7 |
| L23 | 1.6 | 0.6 | 1.8 | 4.2 |
| L24 | 1.6 | 1.4 | 1.6 | 4.4 |
| L25 | 1.6 | 0.4 | 0.6 | 3.8 |
| L26 | 1.7 | 1.1 | 0.7 | 3.6 |
| L27 | 1.0 | 1.0 | 1.0 | 1.0 |
| L28 | 1.0 | 1.0 | 1.0 | 1.0 |
| L29 | 0.9 | 0.4 | 1.0 | 0.9 |
| L30 | 0.0 | 0.0 | 0.0 | 0.0 |
| L31 | 0.0 | 0.0 | 0.0 | 0.0 |
