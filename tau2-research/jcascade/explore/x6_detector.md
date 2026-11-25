# X6: can neuron features gate unneeded transfers better than the J-lens word pairs? (5-fold CV grouped by task)

rows 75 (bad 19); J_pairs (stage 0, out-of-fold) AUC 0.763

| detector | AUC | rank-average with J_pairs |
|---|---|---|
| activation at decision point, top-10 by train-fold t, logistic | 0.788 | 0.794 |
| activation at decision point, top-50 by train-fold t, logistic | 0.790 | 0.793 |
| activation at decision point, top-200 by train-fold t, logistic | 0.779 | 0.790 |
| attribution to transfer tokens, top-10 by train-fold t, logistic | 0.426 | 0.622 |
| attribution to transfer tokens, top-50 by train-fold t, logistic | 0.393 | 0.594 |
| attribution to transfer tokens, top-200 by train-fold t, logistic | 0.407 | 0.613 |

label-free scalar scores (no training):

- attribution summed over give-up readout neurons L20-26: AUC 0.395 (bad mean 0.00, good mean 0.02)
- attribution summed L12-19: AUC 0.414 (bad mean 0.09, good mean 0.13)
- attribution summed L20-26: AUC 0.618 (bad mean -0.09, good mean -0.23)
- attribution summed L27-31: AUC 0.548 (bad mean -0.13, good mean -0.30)

best trained detector: activation at decision point k=50 AUC 0.790. Exploratory: three k values and two feature sets were tried, so the best number is optimistic.
