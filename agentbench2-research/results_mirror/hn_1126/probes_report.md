# Detection before the action, three benchmarks (2026-11-26 17:05:45)

Logistic probe on the residual stream, trained on fold 0 (group CV for the layer choice), tested on fold 1.

## dojo

units (fold 0 harmful, benign; fold 1 harmful, benign): [30, 64, 55, 165]
onset probe, layer chosen by CV: L18, CV AUROC 0.92, fold 1 AUROC 0.93; fold-1 AUROC range over layers 4-30: 0.88-0.95

| layer | tokens before the onset | fold-1 positions | fold-1 AUROC |
|---|---|---|---|
| 16 | 0-64 | 352 | 0.90 |
| 16 | 64-256 | 379 | 0.70 |
| 16 | 256-1024 | 166 | 0.52 |
| 24 | 0-64 | 352 | 0.91 |
| 24 | 64-256 | 379 | 0.76 |
| 24 | 256-1024 | 166 | 0.49 |

## am

units (fold 0 harmful, benign; fold 1 harmful, benign): [22, 160, 29, 151]
onset probe, layer chosen by CV: L18, CV AUROC 0.93, fold 1 AUROC 0.97; fold-1 AUROC range over layers 4-30: 0.86-0.98

| layer | tokens before the onset | fold-1 positions | fold-1 AUROC |
|---|---|---|---|
| 16 | 0-64 | 346 | 0.70 |
| 16 | 64-256 | 1032 | 0.72 |
| 16 | 256-1024 | 4007 | 0.77 |
| 16 | 1024-more | 11652 | 0.76 |
| 24 | 0-64 | 346 | 0.65 |
| 24 | 64-256 | 1032 | 0.70 |
| 24 | 256-1024 | 4007 | 0.77 |
| 24 | 1024-more | 11652 | 0.77 |

## toolalign

units (fold 0 harmful, benign; fold 1 harmful, benign): [16, 69, 20, 90]
onset probe, layer chosen by CV: L20, CV AUROC 0.97, fold 1 AUROC 0.99; fold-1 AUROC range over layers 4-30: 0.96-0.99

| layer | tokens before the onset | fold-1 positions | fold-1 AUROC |
|---|---|---|---|
| 16 | 0-64 | 43 | 0.51 |
| 16 | 64-256 | 97 | 0.75 |
| 16 | 256-1024 | 118 | 0.54 |
| 24 | 0-64 | 43 | 0.51 |
| 24 | 64-256 | 97 | 0.67 |
| 24 | 256-1024 | 118 | 0.56 |

