# N4: preamble manipulation on ToolAlign-4B CAUSAL-1 targets (name-position neuron edits)

- skipped: {'multi_call': 9}

| kind | variant | op | flip (valid variants) | n valid | n invalid (unedited m <= 0) | mean m |
|---|---|---|---|---|---|---|
| no_preamble | commit | base | 0.00 | 13 | 0 | +6.16 |
| no_preamble | commit | neur_random_16 | 0.00 | 13 | 0 | +6.18 |
| no_preamble | commit | neur_random_256 | 0.00 | 13 | 0 | +6.45 |
| no_preamble | commit | neur_random_64 | 0.00 | 13 | 0 | +6.16 |
| no_preamble | commit | neur_top_16 | 0.00 | 13 | 0 | +3.99 |
| no_preamble | commit | neur_top_256 | 0.23 | 13 | 0 | +0.41 |
| no_preamble | commit | neur_top_64 | 0.00 | 13 | 0 | +2.23 |
| no_preamble | neutral | base | 0.00 | 9 | 4 | +1.28 |
| no_preamble | neutral | neur_random_16 | 0.00 | 9 | 4 | +1.26 |
| no_preamble | neutral | neur_random_256 | 0.00 | 9 | 4 | +1.37 |
| no_preamble | neutral | neur_random_64 | 0.00 | 9 | 4 | +1.26 |
| no_preamble | neutral | neur_top_16 | 0.33 | 9 | 4 | +0.36 |
| no_preamble | neutral | neur_top_256 | 0.89 | 9 | 4 | -1.19 |
| no_preamble | neutral | neur_top_64 | 0.67 | 9 | 4 | -0.39 |
| no_preamble | original | base | 0.00 | 12 | 1 | +0.92 |
| no_preamble | original | neur_random_16 | 0.00 | 12 | 1 | +0.91 |
| no_preamble | original | neur_random_256 | 0.00 | 12 | 1 | +1.05 |
| no_preamble | original | neur_random_64 | 0.00 | 12 | 1 | +0.89 |
| no_preamble | original | neur_top_16 | 0.58 | 12 | 1 | +0.01 |
| no_preamble | original | neur_top_256 | 0.92 | 12 | 1 | -1.46 |
| no_preamble | original | neur_top_64 | 0.83 | 12 | 1 | -0.68 |
| text_preamble | deleted | base | 0.00 | 15 | 16 | +2.24 |
| text_preamble | deleted | neur_random_16 | 0.00 | 15 | 16 | +2.25 |
| text_preamble | deleted | neur_random_256 | 0.00 | 15 | 16 | +2.46 |
| text_preamble | deleted | neur_random_64 | 0.00 | 15 | 16 | +2.23 |
| text_preamble | deleted | neur_top_16 | 0.27 | 15 | 16 | +0.81 |
| text_preamble | deleted | neur_top_256 | 1.00 | 15 | 16 | -1.46 |
| text_preamble | deleted | neur_top_64 | 0.60 | 15 | 16 | -0.35 |
| text_preamble | neutral | base | 0.00 | 17 | 14 | +2.06 |
| text_preamble | neutral | neur_random_16 | 0.00 | 17 | 14 | +2.05 |
| text_preamble | neutral | neur_random_256 | 0.00 | 17 | 14 | +2.20 |
| text_preamble | neutral | neur_random_64 | 0.00 | 17 | 14 | +2.01 |
| text_preamble | neutral | neur_top_16 | 0.24 | 17 | 14 | +0.71 |
| text_preamble | neutral | neur_top_256 | 1.00 | 17 | 14 | -1.31 |
| text_preamble | neutral | neur_top_64 | 0.47 | 17 | 14 | -0.34 |
| text_preamble | original | base | 0.00 | 31 | 0 | +8.58 |
| text_preamble | original | neur_random_16 | 0.00 | 31 | 0 | +8.59 |
| text_preamble | original | neur_random_256 | 0.00 | 31 | 0 | +8.81 |
| text_preamble | original | neur_random_64 | 0.00 | 31 | 0 | +8.56 |
| text_preamble | original | neur_top_16 | 0.00 | 31 | 0 | +5.82 |
| text_preamble | original | neur_top_256 | 0.19 | 31 | 0 | +0.64 |
| text_preamble | original | neur_top_64 | 0.03 | 31 | 0 | +3.23 |

Prediction: no_preamble commit < original; text_preamble deleted > original (top-K arms; random arms stay low).
