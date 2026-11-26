# T6d reading-stage neurons on other injected wordings (2026-11-26 15:40:27)

fold-1 units: 112. Neurons: the fold-0 top 256 by median z on the original template, and 256 same-layer random neurons.
Detector = mean z-scored span activation of the top-K neurons. AUROC against the neutral_note text placed at the same position in the same prompt.

| variant | K=8 | K=64 | K=256 | random K=64 | mean z, K=64 |
|---|---|---|---|---|---|
| original | 1.00 | 1.00 | 1.00 | 1.00 | 1.72 |
| ignore_previous | 1.00 | 1.00 | 1.00 | 0.96 | 1.06 |
| direct | 0.94 | 0.99 | 0.75 | 0.92 | 0.82 |
| injecagent | 1.00 | 1.00 | 1.00 | 0.96 | 1.29 |
| bare_goal | 0.81 | 0.72 | 0.48 | 0.89 | 0.69 |
| polite_human | 0.04 | 0.01 | 0.00 | 0.29 | 0.35 |
| neutral_note (reference) | - | - | - | - | 0.52 |
