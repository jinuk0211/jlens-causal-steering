# Why the F-run steering baselines did not help (all F-run results, CPU re-analysis)

Source: server probe/baseline_why/episodes.json (bw_extract.py), artifacts/fit_examples.json; retail success = stored reward x NL verdict.

## A. Outcomes per condition (success count; paired vs f_detect on the same tasks)

| condition | split | n | success | f_detect on same | fixed | broken | net | McNemar p | degenerate eps |
|---|---|---|---|---|---|---|---|---|---|
| f_austeer_s10 | train | 24 | 14 | 16 | 2 | 4 | -2 | 0.69 | 1 |
| f_austeer_s10 | airline_ho | 26 | 21 | 20 | 2 | 1 | +1 | 1.00 | 0 |
| f_austeer_s10 | retail | 50 | 34 | 41 | 4 | 11 | -7 | 0.12 | 0 |
| f_austeer_s20 | train | 24 | 14 | 16 | 2 | 4 | -2 | 0.69 | 0 |
| f_austeer_s50 | train | 15 | 2 | 9 | 0 | 7 | -7 | 0.02 | 2 |
| f_caa_s0.5 | train | 24 | 19 | 16 | 4 | 1 | +3 | 0.38 | 4 |
| f_caa_s0.5 | airline_ho | 26 | 20 | 20 | 3 | 3 | +0 | 1.00 | 0 |
| f_caa_s0.5 | retail | 50 | 36 | 41 | 4 | 9 | -5 | 0.27 | 0 |
| f_caa_s1 | train | 24 | 17 | 16 | 3 | 2 | +1 | 1.00 | 5 |
| f_caa_s2 | train | 16 | 7 | 10 | 2 | 5 | -3 | 0.45 | 9 |
| f_cast_s0.25 | train | 24 | 17 | 16 | 4 | 3 | +1 | 1.00 | 8 |
| f_cast_s0.25 | airline_ho | 26 | 20 | 20 | 2 | 2 | +0 | 1.00 | 4 |
| f_cast_s0.25 | retail | 50 | 34 | 41 | 5 | 12 | -7 | 0.14 | 0 |
| f_cast_s0.5 | train | 15 | 8 | 9 | 3 | 4 | -1 | 1.00 | 13 |
| f_cast_s1 | train | 13 | 5 | 8 | 1 | 4 | -3 | 0.38 | 13 |
| f_detect | train | 24 | 16 | 16 | 0 | 0 | +0 | 1.00 | 1 |
| f_detect | airline_ho | 26 | 20 | 20 | 0 | 0 | +0 | 1.00 | 0 |
| f_detect | retail | 114 | 93 | 93 | 0 | 0 | +0 | 1.00 | 0 |
| f_iti_s10 | train | 24 | 17 | 16 | 3 | 2 | +1 | 1.00 | 3 |
| f_iti_s15 | train | 24 | 19 | 16 | 5 | 2 | +3 | 0.45 | 4 |
| f_iti_s15 | airline_ho | 26 | 20 | 20 | 1 | 1 | +0 | 1.00 | 1 |
| f_iti_s15 | retail | 50 | 38 | 41 | 3 | 6 | -3 | 0.51 | 2 |
| f_iti_s5 | train | 24 | 17 | 16 | 2 | 1 | +1 | 1.00 | 1 |
| f_j5 | train | 24 | 17 | 16 | 1 | 0 | +1 | 1.00 | 1 |
| f_j5 | airline_ho | 26 | 20 | 20 | 0 | 0 | +0 | 1.00 | 0 |
| f_j5 | retail | 50 | 41 | 41 | 0 | 0 | +0 | 1.00 | 0 |
| f_mera_s0.001 | train | 24 | 15 | 16 | 2 | 3 | -1 | 1.00 | 3 |
| f_mera_s0.331 | train | 24 | 13 | 16 | 1 | 4 | -3 | 0.38 | 3 |
| f_mera_s0.661 | train | 24 | 14 | 16 | 0 | 2 | -2 | 0.50 | 1 |
| f_sadi_s10 | train | 24 | 17 | 16 | 2 | 1 | +1 | 1.00 | 0 |
| f_sadi_s10 | airline_ho | 26 | 19 | 20 | 0 | 1 | -1 | 1.00 | 0 |
| f_sadi_s10 | retail | 50 | 37 | 41 | 6 | 10 | -4 | 0.45 | 0 |
| f_sadi_s20 | train | 16 | 8 | 10 | 3 | 5 | -2 | 0.73 | 1 |
| f_sadi_s5 | train | 24 | 16 | 16 | 3 | 3 | +0 | 1.00 | 1 |

## B. Are the same tasks broken by every method? (eval set, 5 always-on baselines at their selected strengths)

- base-pass tasks 113: broken by how many of the 5 methods → {0: 84, 1: 18, 2: 3, 3: 2, 4: 4, 5: 2}
- base-fail tasks 27: fixed by how many of the 5 methods → {0: 13, 1: 6, 2: 3, 3: 2, 4: 3}
- tasks broken by ≥ 3 of 5 methods: observed 8; if each method broke tasks independently at its own rate: mean 0.93, P(≥ observed) = 0.0000
- the fragile tasks (broken by ≥ 3): ['retail:36(5)', 'retail:5(5)', 'airline:35(4)', 'retail:100(4)', 'retail:38(4)', 'retail:9(4)', 'retail:2(3)', 'retail:56(3)']
- tasks fixed by ≥ 2 methods: ['retail:60(4)', 'retail:7(4)', 'retail:8(4)', 'airline:24(3)', 'retail:6(3)', 'airline:43(2)', 'retail:108(2)', 'retail:71(2)']

## C. Where does the steered trajectory leave the reference? (eval set, paired by task)

| condition | identical episodes | first differing agent turn: 0 / 1 / 2 / 3+ | outcome changed when identical | when diverged |
|---|---|---|---|---|
| f_caa_s0.5 | 0 | 45 / 9 / 14 / 8 | 0 | 19/76 |
| f_austeer_s10 | 0 | 58 / 9 / 6 / 3 | 0 | 18/76 |
| f_sadi_s10 | 0 | 19 / 27 / 15 / 15 | 0 | 17/76 |
| f_iti_s15 | 0 | 57 / 4 / 11 / 4 | 0 | 11/76 |
| f_cast_s0.25 | 0 | 66 / 4 / 6 / 0 | 0 | 21/76 |
| f_j5 | 70 | 4 / 1 / 0 / 1 | 0 | 0/6 |
| f_mera_s0.001 | 0 | 0 / 0 / 0 / 0 | 0 | 0/0 |

## D. What changed in behaviour? (eval set, per-episode means, steered minus reference on the same tasks)

| condition | agent turns | tool calls | writes | bad writes | bad-write share of writes (cond / ref) | transfers | verify-first replies | mean text chars | capped turns |
|---|---|---|---|---|---|---|---|---|---|
| f_caa_s0.5 | -0.26 | -0.25 | -0.09 | +0.05 | 0.35 / 0.29 | +0.01 | -0.04 | +78 | +0.08 |
| f_austeer_s10 | -0.93 | -0.45 | -0.05 | +0.05 | 0.34 / 0.29 | -0.03 | +0.01 | -35 | +0.01 |
| f_sadi_s10 | -0.53 | -0.58 | +0.03 | +0.04 | 0.31 / 0.29 | -0.01 | -0.08 | +41 | +0.03 |
| f_iti_s15 | +0.09 | +0.20 | +0.04 | +0.08 | 0.34 / 0.29 | -0.01 | -0.04 | +249 | +0.14 |
| f_cast_s0.25 | +0.36 | +0.16 | +0.04 | +0.05 | 0.32 / 0.29 | -0.01 | +0.13 | +562 | +0.34 |
| f_j5 | +0.03 | +0.01 | +0.00 | +0.00 | 0.29 / 0.29 | +0.00 | +0.01 | +5 | +0.00 |

## E. Failure types: what appears in broken episodes, what disappears in fixed ones (eval set, 5 always-on baselines pooled)

- failure types in BROKEN episodes (reference passed): {'db_mismatch': 51, 'missing_write': 48, 'wrong_args': 17, 'unexpected_transfer': 14, 'unexpected_write': 12, '(no write-level failure: communicate/NL or user)': 5, 'communicate': 1}
- failure types that the reference had in FIXED episodes: {'db_mismatch': 30, 'missing_write': 28, 'unexpected_transfer': 17, 'unexpected_write': 5, 'wrong_args': 1}
- broken / fixed by domain: f_caa_s0.5: airline 3/3, retail 9/4, f_austeer_s10: airline 1/2, retail 11/4, f_sadi_s10: airline 1/0, retail 10/6, f_iti_s15: airline 1/1, retail 6/3, f_cast_s0.25: airline 2/2, retail 12/5

## F. Does airline-fitted steering leak airline language into retail? (airline words per retail episode)

- f_detect: mean 0.00, episodes with any 0/114
- f_caa_s0.5: mean 0.00, episodes with any 0/50
- f_austeer_s10: mean 0.00, episodes with any 0/50
- f_sadi_s10: mean 0.00, episodes with any 0/50
- f_iti_s15: mean 0.00, episodes with any 0/50
- f_cast_s0.25: mean 0.00, episodes with any 0/50

## G. How much was actually edited? (eval set)

- f_caa_s0.5: turns with an applied edit 964/964; median official applied_edits per turn 99.0; turns with the J-lens trigger on 0
- f_austeer_s10: turns with an applied edit 913/913; median official applied_edits per turn 21372.0; turns with the J-lens trigger on 0
- f_sadi_s10: turns with an applied edit 944/944; median official applied_edits per turn 32.0; turns with the J-lens trigger on 0
- f_iti_s15: turns with an applied edit 991/991; median official applied_edits per turn 107.0; turns with the J-lens trigger on 0
- f_cast_s0.25: turns with an applied edit 859/1011; median official applied_edits per turn 58860.0; turns with the J-lens trigger on 0
- f_j5: turns with an applied edit 0/986; median official applied_edits per turn n/a; turns with the J-lens trigger on 0
- f_mera_s0.001: turns with an applied edit 0/0; median official applied_edits per turn n/a; turns with the J-lens trigger on 0

## H. What were the baselines fitted on? (artifacts/fit_examples.json)

- examples 56; positive side: {'verify_first': 34, 'gold_arguments': 22}; sources: {'detect': 22, 'fitx': 34}
- by TRAIN task: {'0': 1, '1': 3, '10': 2, '14': 1, '20': 3, '21': 11, '27': 2, '28': 3, '3': 3, '36': 2, '38': 2, '39': 4, '4': 3, '41': 3, '7': 4, '9': 2, '12': 1, '15': 1, '17': 1, '23': 1, '42': 1, '5': 2}
- negative (failed) action: {'transfer_to_human_agents': 26, 'update_reservation_flights': 18, 'book_reservation': 3, 'cancel_reservation': 5, 'send_certificate': 1, 'update_reservation_baggages': 3}
- most common positive texts: {'Before I make any change, let me check this request against the policy and confirm the details with you.': 34, '': 22}

## I. Dose curves on airline TRAIN (24 tasks; reference f_detect)

- f_detect: success 16/24, degenerate 1
- caa: s0.5: 19/24 (degen 4); s1: 17/24 (degen 5); s2: 7/16 (degen 9)
- austeer: s10: 14/24 (degen 1); s20: 14/24 (degen 0); s50: 2/15 (degen 2)
- sadi: s5: 16/24 (degen 1); s10: 17/24 (degen 0); s20: 8/16 (degen 1)
- iti: s5: 17/24 (degen 1); s10: 17/24 (degen 3); s15: 19/24 (degen 4)
- cast: s0.25: 17/24 (degen 8); s0.5: 8/15 (degen 13); s1: 5/13 (degen 13)
- mera: s0.001: 15/24 (degen 3); s0.331: 13/24 (degen 3); s0.661: 14/24 (degen 1)
- j5: j5: 17/24 (degen 1)
