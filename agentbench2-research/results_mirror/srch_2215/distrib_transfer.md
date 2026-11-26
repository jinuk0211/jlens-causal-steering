# Cross-benchmark transfer: top-K target neurons of the other two benchmarks, set to the held-out benchmark's reference mean at its decision position

| held-out | K | flip (shared) | flip (same-layer random) | targets |
|---|---|---|---|---|
| toolalign | 64 | 0/52 | 0/52 | 53 |
| toolalign | 256 | 0/52 | 0/52 | 53 |
| toolalign | 1024 | 3/52 | 0/52 | 53 |
| dojo | 64 | 0/85 | 0/85 | 85 |
| dojo | 256 | 0/85 | 0/85 | 85 |
| dojo | 1024 | 2/85 | 0/85 | 85 |
| am | 64 | 0/50 | 0/50 | 51 |
| am | 256 | 0/50 | 0/50 | 51 |
| am | 1024 | 0/50 | 0/50 | 51 |
