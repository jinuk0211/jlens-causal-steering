# J-Cascade stage 2: offline regeneration of transfer turns

source C:\Users\h\Documents\ChatGPT\vlm interpretability\work\tau2-research\jcascade\out\stage2; configs present: ['C0', 'S1', 'S2', 'S4', 'S5', 'S6', 'S7', 'S47', 'R1', 'R47']

| config | n bad | n good | bad converted | good kept transfer | degenerate | bad outcomes | good outcomes | vs C0 (bad, conv only in cfg / only in C0, sign p) |
|---|---|---|---|---|---|---|---|---|
| C0 | 19 | 56 | 0% | 82% | 4% | {'transfer': 18, 'verbal_transfer': 1} | {'transfer': 46, 'verbal_transfer': 4, 'text': 1, 'degenerate': 3, 'other_tool': 2} | 0 / 0, p - |
| S1 | 19 | 56 | 0% | 86% | 0% | {'transfer': 18, 'verbal_transfer': 1} | {'transfer': 48, 'verbal_transfer': 4, 'text': 2, 'other_tool': 2} | 0 / 0, p - |
| S2 | 19 | 56 | 0% | 88% | 4% | {'transfer': 18, 'verbal_transfer': 1} | {'transfer': 49, 'degenerate': 3, 'verbal_transfer': 1, 'text': 1, 'other_tool': 2} | 0 / 0, p - |
| S4 | 19 | 56 | 0% | 84% | 3% | {'transfer': 17, 'verbal_transfer': 2} | {'transfer': 47, 'verbal_transfer': 4, 'text': 1, 'degenerate': 2, 'other_tool': 2} | 0 / 0, p - |
| S5 | 19 | 56 | 0% | 80% | 1% | {'transfer': 19} | {'transfer': 45, 'degenerate': 1, 'verbal_transfer': 6, 'text': 1, 'other_tool': 3} | 0 / 0, p - |
| S6 | 19 | 56 | 0% | 84% | 3% | {'transfer': 18, 'verbal_transfer': 1} | {'transfer': 47, 'degenerate': 2, 'verbal_transfer': 4, 'text': 1, 'other_tool': 2} | 0 / 0, p - |
| S7 | 19 | 56 | 0% | 77% | 1% | {'transfer': 19} | {'transfer': 43, 'degenerate': 1, 'verbal_transfer': 6, 'other_tool': 4, 'text': 2} | 0 / 0, p - |
| S47 | 19 | 56 | 0% | 80% | 3% | {'transfer': 18, 'degenerate': 1} | {'transfer': 45, 'text': 3, 'verbal_transfer': 3, 'other_tool': 4, 'degenerate': 1} | 0 / 0, p - |
| R1 | 19 | 56 | 0% | 82% | 4% | {'transfer': 18, 'verbal_transfer': 1} | {'transfer': 46, 'verbal_transfer': 4, 'degenerate': 3, 'text': 1, 'other_tool': 2} | 0 / 0, p - |
| R47 | 19 | 56 | 0% | 86% | 5% | {'transfer': 19} | {'transfer': 48, 'verbal_transfer': 2, 'degenerate': 4, 'text': 1, 'other_tool': 1} | 0 / 0, p - |

C0 determinism: share of C0 turns that still call the transfer tool (all rows were logged transfers): 64/75

Pre-registered PASS per config: bad converted >= 40 %, good kept >= 80 %, degenerate <= 5 %, bad converted above C0 and above its random control (S1/S2/S5/S6 -> R1; S4/S7/S47 -> R47).

- S1: FAIL; conv>=40% no, kept>=80% ok, degen<=5% ok, conv>C0 no, conv>R1 no; bad converted by domain {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'}
- S2: FAIL; conv>=40% no, kept>=80% ok, degen<=5% ok, conv>C0 no, conv>R1 no; bad converted by domain {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'}
- S4: FAIL; conv>=40% no, kept>=80% ok, degen<=5% ok, conv>C0 no, conv>R47 no; bad converted by domain {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'}
- S5: FAIL; conv>=40% no, kept>=80% ok, degen<=5% ok, conv>C0 no, conv>R1 no; bad converted by domain {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'}
- S6: FAIL; conv>=40% no, kept>=80% ok, degen<=5% ok, conv>C0 no, conv>R1 no; bad converted by domain {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'}
- S7: FAIL; conv>=40% no, kept>=80% no, degen<=5% ok, conv>C0 no, conv>R47 no; bad converted by domain {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'}
- S47: FAIL; conv>=40% no, kept>=80% ok, degen<=5% ok, conv>C0 no, conv>R47 no; bad converted by domain {'airline': '0/10', 'retail': '0/4', 'telecom': '0/5'}
