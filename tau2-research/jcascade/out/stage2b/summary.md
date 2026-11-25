# J-Cascade stage 2b: causal neuron ablation and paired-prompt DoM steering

gate (stage-0 J_pairs, out-of-fold; threshold = 80th percentile of the other fold's good rows): flags bad 13/19, good 12/56

| config | bad converted | good kept | degenerate | vs control (conv only cfg / only control, sign p) | gated bad converted | gated good kept | gated degenerate |
|---|---|---|---|---|---|---|---|
| C0 | 0% ({'transfer': 18, 'verbal_transfer': 1}) | 86% | 1% | -: 0 / 0, p - | 0% | 86% | 1% |
| P0 | 5% ({'verbal_transfer': 2, 'degenerate': 2, 'transfer': 14, 'text': 1}) | 80% | 4% | C0: 1 / 0, p 0.500 | 5% | 84% | 3% |
| A20 | 0% ({'verbal_transfer': 3, 'degenerate': 1, 'transfer': 15}) | 50% | 5% | RA20: 0 / 0, p - | 0% | 79% | 3% |
| A100 | 5% ({'degenerate': 3, 'transfer': 10, 'verbal_transfer': 5, 'text': 1}) | 27% | 16% | RA100: 0 / 0, p - | 5% | 77% | 5% |
| RA20 | 0% ({'transfer': 19}) | 88% | 0% | C0: 0 / 0, p - | 0% | 86% | 1% |
| RA100 | 5% ({'transfer': 18, 'text': 1}) | 80% | 1% | C0: 1 / 0, p 0.500 | 5% | 84% | 1% |
| B05 | 0% ({'transfer': 17, 'degenerate': 1, 'verbal_transfer': 1}) | 84% | 1% | RB1: 0 / 0, p - | 0% | 86% | 1% |
| B1 | 0% ({'transfer': 16, 'degenerate': 1, 'verbal_transfer': 2}) | 88% | 5% | RB1: 0 / 0, p - | 0% | 86% | 1% |
| RB1 | 0% ({'transfer': 18, 'verbal_transfer': 1}) | 75% | 0% | C0: 0 / 0, p - | 0% | 86% | 1% |

PASS (pre-registered): ungated conversion >= 40 % and >= control + 4/19 with sign p < 0.05; gated conversion >= 40 %, gated good kept >= 80 %, gated degenerate <= 5 %.

- A20: FAIL; conv>=40% no, conv>=ctl+4 no, sign p<0.05 no, gated conv>=40% no, gated kept>=80% no, gated degen<=5% ok
- A100: FAIL; conv>=40% no, conv>=ctl+4 no, sign p<0.05 no, gated conv>=40% no, gated kept>=80% no, gated degen<=5% no
- B05: FAIL; conv>=40% no, conv>=ctl+4 no, sign p<0.05 no, gated conv>=40% no, gated kept>=80% ok, gated degen<=5% ok
- B1: FAIL; conv>=40% no, conv>=ctl+4 no, sign p<0.05 no, gated conv>=40% no, gated kept>=80% ok, gated degen<=5% ok

necessity (teacher-forced, other fold): mean change of transfer-token log p {'A5': -1.7424464747916864, 'A20': -5.226173395156505, 'A100': -13.654563666670098, 'AG20': -0.059103930957893076, 'RA20': -0.00014244224650004374, 'RA100': 0.0021659635287930236}; tool-name token still top-1 {'none': '75/75', 'A5': '75/75', 'A20': '75/75', 'A100': '75/75', 'AG20': '75/75', 'RA20': '75/75', 'RA100': '75/75'}
set sizes {'0': {'A5': 100, 'A20': 400, 'A100': 2000, 'AG20': 129, 'RA20': 400, 'RA100': 2000}, '1': {'A5': 100, 'A20': 400, 'A100': 2000, 'AG20': 130, 'RA20': 400, 'RA100': 2000}}; paired-DoM norms {'0': [2.23877215385437, 3.204502820968628, 3.5577032566070557], '1': [2.418599843978882, 3.5815584659576416, 3.9400269985198975]} vs residual norms [17.826213836669922, 28.15169906616211, 32.87324905395508]; DoM cosine between folds [0.8920712471008301, 0.8699056506156921, 0.8788974285125732]
