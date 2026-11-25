# N4 on AgentDojo: preamble manipulation, decision-position neuron edits (CAUSAL-1 sets)

- skipped: {'kind_value': 16}; references for mu: 11

| kind | variant | op | flip (valid) | n valid | n invalid | mean m |
|---|---|---|---|---|---|---|
| no_preamble | commit | base | 0.00 | 30 | 0 | +6.78 |
| no_preamble | commit | neur_random_16 | 0.00 | 30 | 0 | +6.79 |
| no_preamble | commit | neur_random_256 | 0.00 | 30 | 0 | +6.73 |
| no_preamble | commit | neur_random_64 | 0.00 | 30 | 0 | +6.77 |
| no_preamble | commit | neur_top_16 | 0.00 | 30 | 0 | +5.24 |
| no_preamble | commit | neur_top_256 | 0.50 | 30 | 0 | -0.07 |
| no_preamble | commit | neur_top_64 | 0.00 | 30 | 0 | +3.27 |
| no_preamble | neutral | base | 0.00 | 30 | 0 | +4.05 |
| no_preamble | neutral | neur_random_16 | 0.00 | 30 | 0 | +4.04 |
| no_preamble | neutral | neur_random_256 | 0.00 | 30 | 0 | +3.99 |
| no_preamble | neutral | neur_random_64 | 0.00 | 30 | 0 | +4.05 |
| no_preamble | neutral | neur_top_16 | 0.40 | 30 | 0 | +2.25 |
| no_preamble | neutral | neur_top_256 | 0.80 | 30 | 0 | -2.66 |
| no_preamble | neutral | neur_top_64 | 0.47 | 30 | 0 | +0.20 |
| no_preamble | original | base | 0.00 | 30 | 0 | +5.59 |
| no_preamble | original | neur_random_16 | 0.00 | 30 | 0 | +5.56 |
| no_preamble | original | neur_random_256 | 0.00 | 30 | 0 | +5.50 |
| no_preamble | original | neur_random_64 | 0.00 | 30 | 0 | +5.55 |
| no_preamble | original | neur_top_16 | 0.07 | 30 | 0 | +3.55 |
| no_preamble | original | neur_top_256 | 0.80 | 30 | 0 | -2.01 |
| no_preamble | original | neur_top_64 | 0.43 | 30 | 0 | +1.26 |
| text_preamble | deleted | base | 0.00 | 33 | 6 | +3.50 |
| text_preamble | deleted | neur_random_16 | 0.00 | 33 | 6 | +3.47 |
| text_preamble | deleted | neur_random_256 | 0.00 | 33 | 6 | +3.40 |
| text_preamble | deleted | neur_random_64 | 0.00 | 33 | 6 | +3.49 |
| text_preamble | deleted | neur_top_16 | 0.45 | 33 | 6 | +1.48 |
| text_preamble | deleted | neur_top_256 | 0.67 | 33 | 6 | -3.08 |
| text_preamble | deleted | neur_top_64 | 0.55 | 33 | 6 | -0.31 |
| text_preamble | neutral | base | 0.00 | 34 | 5 | +2.85 |
| text_preamble | neutral | neur_random_16 | 0.00 | 34 | 5 | +2.86 |
| text_preamble | neutral | neur_random_256 | 0.00 | 34 | 5 | +2.78 |
| text_preamble | neutral | neur_random_64 | 0.00 | 34 | 5 | +2.86 |
| text_preamble | neutral | neur_top_16 | 0.50 | 34 | 5 | +0.79 |
| text_preamble | neutral | neur_top_256 | 0.68 | 34 | 5 | -3.59 |
| text_preamble | neutral | neur_top_64 | 0.56 | 34 | 5 | -0.98 |
| text_preamble | original | base | 0.00 | 39 | 0 | +10.52 |
| text_preamble | original | neur_random_16 | 0.00 | 39 | 0 | +10.53 |
| text_preamble | original | neur_random_256 | 0.00 | 39 | 0 | +10.47 |
| text_preamble | original | neur_random_64 | 0.00 | 39 | 0 | +10.47 |
| text_preamble | original | neur_top_16 | 0.00 | 39 | 0 | +8.17 |
| text_preamble | original | neur_top_256 | 0.41 | 39 | 0 | +1.74 |
| text_preamble | original | neur_top_64 | 0.00 | 39 | 0 | +5.98 |

Prediction: no_preamble commit < original; text_preamble deleted > original (top-K arms; random arms stay low).
