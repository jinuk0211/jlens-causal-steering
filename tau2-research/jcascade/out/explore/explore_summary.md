# J-Cascade exploration: regenerated transfer turns (19 bad, 56 good), each compared with C0 on the same rows

| config | rows | bad converted | bad conv. (negation-aware, exploratory) | good kept | degenerate | bad: converted only here / only C0 (sign p) | good: lost transfer vs C0 | changed prompt rows | gated bad conv | gated good kept |
|---|---|---|---|---|---|---|---|---|---|---|
| MID | 75 | 21% {'airline': '0/10', 'retail': '0/4', 'telecom': '4/5'} | 21% (rc 0) | 73% | 16% | 4 / 0 (p 0.062) | 10 | 75 | 16% | 82% |
| MID2 | 75 | 21% {'airline': '0/10', 'retail': '0/4', 'telecom': '4/5'} | 21% (rc 1) | 71% | 15% | 4 / 0 (p 0.062) | 11 | 75 | 16% | 80% |
| N10 | 75 | 5% {'airline': '0/10', 'retail': '0/4', 'telecom': '1/5'} | 5% (rc 1) | 68% | 5% | 1 / 0 (p 0.500) | 13 | 75 | 5% | 84% |
| N20 | 75 | 16% {'airline': '1/10', 'retail': '0/4', 'telecom': '2/5'} | 21% (rc 2) | 39% | 20% | 3 / 0 (p 0.125) | 27 | 75 | 11% | 79% |
| O_ask | 75 | 0% {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'} | 0% (rc 0) | 80% | 7% | 0 / 0 (p -) | 4 | 75 | 0% | 86% |
| O_desc | 75 | 0% {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'} | 0% (rc 2) | 79% | 4% | 0 / 0 (p -) | 5 | 75 | 0% | 86% |
| O_policy | 75 | 0% {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'} | 0% (rc 2) | 77% | 1% | 0 / 0 (p -) | 8 | 75 | 0% | 82% |
| O_userhuman | 75 | 16% {'airline': '1/10', 'retail': '0/4', 'telecom': '2/5'} | 16% (rc 0) | 59% | 4% | 3 / 0 (p 0.125) | 16 | 43 | 11% | 79% |
| P1 | 75 | 21% {'airline': '1/10', 'retail': '1/4', 'telecom': '2/5'} | 42% (rc 5) | 45% | 3% | 4 / 0 (p 0.062) | 24 | 75 | 21% | 73% |
| P1PF_deny | 75 | 11% {'airline': '1/10', 'retail': '0/4', 'telecom': '1/5'} | 42% (rc 9) | 57% | 1% | 2 / 0 (p 0.250) | 21 | 75 | 5% | 73% |
| P1PF_self | 75 | 26% {'airline': '0/10', 'retail': '1/4', 'telecom': '4/5'} | 32% (rc 4) | 62% | 17% | 5 / 0 (p 0.031) | 17 | 75 | 21% | 82% |
| PF_alt | 75 | 11% {'airline': '0/10', 'retail': '0/4', 'telecom': '2/5'} | 11% (rc 1) | 68% | 0% | 2 / 0 (p 0.250) | 17 | 75 | 5% | 82% |
| PF_clarify | 75 | 11% {'airline': '0/10', 'retail': '0/4', 'telecom': '2/5'} | 11% (rc 1) | 46% | 1% | 2 / 0 (p 0.250) | 23 | 75 | 5% | 82% |
| PF_deny | 75 | 0% {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'} | 32% (rc 7) | 80% | 0% | 0 / 0 (p -) | 9 | 75 | 0% | 84% |
| PF_denyhelp | 75 | 21% {'airline': '2/10', 'retail': '0/4', 'telecom': '2/5'} | 26% (rc 1) | 50% | 1% | 4 / 0 (p 0.062) | 24 | 75 | 16% | 75% |
| PF_help | 75 | 21% {'airline': '2/10', 'retail': '0/4', 'telecom': '2/5'} | 21% (rc 0) | 71% | 3% | 4 / 0 (p 0.062) | 12 | 75 | 11% | 80% |
| PF_neutral | 75 | 11% {'airline': '0/10', 'retail': '0/4', 'telecom': '2/5'} | 11% (rc 2) | 75% | 0% | 2 / 0 (p 0.250) | 11 | 75 | 5% | 82% |
| PF_pc | 75 | 16% {'airline': '0/10', 'retail': '0/4', 'telecom': '3/5'} | 21% (rc 2) | 75% | 9% | 3 / 0 (p 0.125) | 9 | 75 | 11% | 82% |
| PF_self | 75 | 21% {'airline': '0/10', 'retail': '0/4', 'telecom': '4/5'} | 21% (rc 0) | 82% | 11% | 4 / 0 (p 0.062) | 8 | 75 | 16% | 86% |
| RN20 | 75 | 5% {'airline': '0/10', 'retail': '0/4', 'telecom': '1/5'} | 5% (rc 1) | 62% | 3% | 1 / 0 (p 0.500) | 15 | 75 | 5% | 82% |
| S07a | 75 | 5% {'airline': '1/10', 'retail': '0/4', 'telecom': '0/5'} | 5% (rc 1) | 73% | 1% | 1 / 0 (p 0.500) | 11 | 75 | 0% | 86% |
| S07b | 75 | 5% {'airline': '0/10', 'retail': '0/4', 'telecom': '1/5'} | 5% (rc 1) | 77% | 7% | 1 / 0 (p 0.500) | 9 | 75 | 5% | 82% |
| S07c | 75 | 5% {'airline': '0/10', 'retail': '0/4', 'telecom': '1/5'} | 5% (rc 1) | 71% | 3% | 1 / 0 (p 0.500) | 10 | 75 | 5% | 86% |
| S07d | 75 | 5% {'airline': '0/10', 'retail': '0/4', 'telecom': '1/5'} | 5% (rc 1) | 75% | 4% | 1 / 0 (p 0.500) | 10 | 75 | 5% | 80% |
| TH_free | 75 | 16% {'airline': '1/10', 'retail': '0/4', 'telecom': '2/5'} | 16% (rc 2) | 73% | 7% | 3 / 0 (p 0.125) | 10 | 75 | 5% | 84% |
| TH_pc | 75 | 5% {'airline': '0/10', 'retail': '1/4', 'telecom': '0/5'} | 5% (rc 0) | 77% | 1% | 1 / 0 (p 0.500) | 10 | 75 | 0% | 84% |
| TM | 75 | 11% {'airline': '0/10', 'retail': '0/4', 'telecom': '2/5'} | 16% (rc 3) | 0% | 12% | 2 / 0 (p 0.250) | 48 | 75 | 11% | 64% |
| A100 | 75 | 5% {'airline': '0/10', 'retail': '0/4', 'telecom': '1/5'} | 5% (rc 1) | 27% | 16% | 1 / 0 (p 0.500) | 33 | 75 | 5% | 77% |
| A20 | 75 | 0% {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'} | 5% (rc 6) | 50% | 5% | 0 / 0 (p -) | 20 | 75 | 0% | 79% |
| B05 | 75 | 0% {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'} | 0% (rc 1) | 84% | 1% | 0 / 0 (p -) | 4 | 75 | 0% | 86% |
| B1 | 75 | 0% {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'} | 0% (rc 1) | 88% | 5% | 0 / 0 (p -) | 4 | 75 | 0% | 86% |
| C0 | 75 | 0% {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'} | 0% (rc 1) | 86% | 1% | 0 / 0 (p -) | 0 | 75 | 0% | 86% |
| P0 | 75 | 5% {'airline': '0/10', 'retail': '0/4', 'telecom': '1/5'} | 16% (rc 2) | 80% | 4% | 1 / 0 (p 0.500) | 10 | 75 | 5% | 84% |
| RA100 | 75 | 5% {'airline': '0/10', 'retail': '0/4', 'telecom': '1/5'} | 5% (rc 1) | 80% | 1% | 1 / 0 (p 0.500) | 8 | 75 | 5% | 84% |
| RA20 | 75 | 0% {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'} | 0% (rc 0) | 88% | 0% | 0 / 0 (p -) | 4 | 75 | 0% | 86% |
| RB1 | 75 | 0% {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'} | 5% (rc 3) | 75% | 0% | 0 / 0 (p -) | 10 | 75 | 0% | 86% |

gate: stage-0 J_pairs out-of-fold, threshold = 80th percentile of the other fold's good rows; flags bad 13/19, good 12/56
