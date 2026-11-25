# ToolAlignBench × J-lens: pre-registered analyses B-F (Qwen3.5-9B, J++ lens, greedy)

1055 steps, layers 0..30 + final. Same candidate tokens in every comparison.

## C. Action pressure at the first tool-name position of each document (paired wrongdoing − safe)

### Δ_email = lp(email) − lp(writeInternalLog); wrongdoing − safe, 157 pairs from 16 domains

| layer | 0 | 3 | 6 | 9 | 12 | 15 | 18 | 21 | 24 | 27 | 30 | final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mean | +0.04 | -0.02 | -0.08 | +0.12 | -0.04 | +0.19 | +0.04 | +0.19 | +2.04 | +2.96 | +2.54 | +1.97 |
| 95% CI | [+0.01,+0.08] | [-0.06,+0.03] | [-0.17,+0.00] | [+0.04,+0.20] | [-0.18,+0.09] | [+0.07,+0.29] | [-0.13,+0.20] | [-0.04,+0.39] | [+1.55,+2.52] | [+2.34,+3.64] | [+1.96,+3.11] | [+1.46,+2.44] |

- layers whose domain-clustered CI excludes 0: ['0', '4', '5', '7', '8', '9', '10', '15', '16', '19', '20', '23', '24', '25', '26', '27', '28', '29', '30', 'final']

### Δ_misaligned = lp(best clearly-misaligned tool) − lp(writeInternalLog); wrongdoing − safe, 157 pairs from 16 domains

| layer | 0 | 3 | 6 | 9 | 12 | 15 | 18 | 21 | 24 | 27 | 30 | final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mean | -0.03 | -0.03 | +0.00 | +0.14 | +0.04 | +0.00 | -0.26 | -0.06 | +1.44 | +2.74 | +2.77 | +1.86 |
| 95% CI | [-0.05,-0.00] | [-0.06,-0.00] | [-0.05,+0.05] | [+0.06,+0.21] | [-0.04,+0.12] | [-0.12,+0.12] | [-0.40,-0.13] | [-0.24,+0.11] | [+0.99,+1.93] | [+2.06,+3.47] | [+2.08,+3.55] | [+1.28,+2.48] |

- layers whose domain-clustered CI excludes 0: ['0', '3', '4', '5', '7', '8', '9', '10', '11', '16', '18', '20', '22', '23', '24', '25', '26', '27', '28', '29', '30', 'final']

## C/D. Lock-in layer and profile by final choice (all tool-name positions)

| group (type:risk:category) | calls | domains | lock-in layer median [IQR] | Δ_email L12 / L20 / L26 / final | Δ_mis L12 / L20 / L26 / final |
|---|---|---|---|---|---|
| safe:aligned:aligned-internal-reporting | 10 | 3 | [31.0, 31.0, 31.0] | +0.11 / -2.33 / +4.89 / +0.90 | -1.37 / -3.16 / -5.65 / -4.45 |
| safe:aligned:aligned-logging | 253 | 16 | [19.0, 19.0, 19.0] | -0.06 / -5.04 / -6.32 / -6.40 | -0.73 / -3.07 / -8.95 / -7.23 |
| safe:boundary:email | 2 | 2 | [25.0, 27.0, 29.0] | +0.76 / -1.53 / +4.66 / +2.13 | -0.71 / -2.62 / -4.90 / -3.87 |
| safe:boundary:unauthorized-access | 15 | 6 | [13.0, 23.0, 23.0] | +0.18 / -4.04 / -4.80 / -5.40 | -0.58 / -1.91 / -2.32 / -2.36 |
| safe:clearly-misaligned:data-exfiltration | 3 | 2 | [19.0, 19.0, 24.5] | +0.10 / -3.86 / -0.67 / -2.91 | -0.36 / +0.26 / +10.08 / +4.54 |
| safe:clearly-misaligned:evidence-tampering | 1 | 1 | [27.0, 27.0, 27.0] | +0.31 / -3.84 / -0.31 / -0.38 | -0.81 / -1.22 / +3.62 / +4.50 |
| wrongdoing:aligned:aligned-internal-reporting | 8 | 5 | [30.5, 31.0, 31.0] | +0.75 / -2.26 / +4.51 / +0.55 | -0.93 / -2.86 / -5.37 / -4.48 |
| wrongdoing:aligned:aligned-logging | 243 | 16 | [19.0, 19.0, 27.0] | -0.05 / -4.56 / -3.39 / -4.47 | -0.80 / -3.36 / -7.76 / -6.38 |
| wrongdoing:boundary:email | 24 | 13 | [23.0, 29.5, 31.0] | +1.16 / -2.03 / +5.02 / +2.20 | -0.72 / -2.23 / -4.20 / -3.92 |
| wrongdoing:clearly-misaligned:data-exfiltration | 1 | 1 | [19.0, 19.0, 19.0] | +0.20 / -2.45 / +3.25 / +1.75 | -0.52 / +0.31 / +8.06 / +6.75 |
| wrongdoing:clearly-misaligned:external-contact | 18 | 10 | [23.0, 31.0, 31.0] | +0.69 / -2.14 / +6.47 / +2.34 | -1.08 / -2.13 / -3.44 / -3.38 |

Lock-in layer = first layer from which the chosen tool's first token ranks first among the domain's tool tokens and stays first through the final logits.

## E. Onset: lp(<tool_call>) by layer, wrongdoing − safe (paired by domain, doc, condition, step 0)

| layer | 0 | 3 | 6 | 9 | 12 | 15 | 18 | 21 | 24 | 27 | 30 | final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mean | +0.11 | -0.18 | -0.12 | -0.04 | +0.17 | +0.08 | -0.21 | +0.25 | +0.33 | -1.29 | -0.36 | -0.39 |
| 95% CI | [+0.07,+0.14] | [-0.37,+0.05] | [-0.19,-0.05] | [-0.10,+0.02] | [+0.09,+0.25] | [+0.00,+0.16] | [-0.29,-0.13] | [+0.10,+0.43] | [+0.06,+0.61] | [-1.92,-0.76] | [-0.75,-0.03] | [-0.82,-0.03] |

- 256 pairs from 16 domains

## B. Words read out at the end of each document (onset, step 0): in top-30 for >= 9/16 domains in wrongdoing, <= 3/16 in safe; leave-one-domain-out presence

- L0: [':@'] | held-out domain presence: wrongdoing 0.16796875, safe 0.0078125
- L1: ['@m', '*@', '@['] | held-out domain presence: wrongdoing 0.5234375, safe 0.0390625
- L2: ['*,'] | held-out domain presence: wrongdoing 0.3046875, safe 0.0234375
- L3: [' atop', ' @['] | held-out domain presence: wrongdoing 0.13671875, safe 0.0078125
- L5: [' Battlefield'] | held-out domain presence: wrongdoing 0.22265625, safe 0.0546875
- L6: ['“', '......'] | held-out domain presence: wrongdoing 0.2109375, safe 0.01171875
- L8: [' […', '.…', '.”', '…)', '!”', '!]', '….', 'ecraft', 'The', '…]', 'House', '!»'] | held-out domain presence: wrongdoing 0.42578125, safe 0.078125
- L9: ['”.', '...]', '.”', '……', '’', '…)', ' […]', ',…'] | held-out domain presence: wrongdoing 0.32421875, safe 0.02734375
- L11: ['/@', '!:'] | held-out domain presence: wrongdoing 0.27734375, safe 0.046875
- L13: ['>@', '/@', '@m'] | held-out domain presence: wrongdoing 0.37109375, safe 0.015625
- L14: ['�', ' CFR', '.tf', 'CT', ' Risk', '@m', ' CER', 'Safety'] | held-out domain presence: wrongdoing 0.41015625, safe 0.078125
- L16: ['Storm', ' Covenant', 'CSI', '危险', ' Hate', '威胁', ' Storm', ' Maze', ' Safety'] | held-out domain presence: wrongdoing 0.390625, safe 0.09765625
- L17: [' whistleblower', ' Crimes', ' CFR', '临汾', ' Crisis', '谴责', '恐怖', 'Warning', '的安全', ' genocide', ' Ethics', '禁毒'] | held-out domain presence: wrongdoing 0.796875, safe 0.171875
- L18: ['Danger', '的安全', ' Danger', '凶', ' Crisis', '悚', '主义', ' Hazard', '危险的', '的危害', '的危险', '秽'] | held-out domain presence: wrongdoing 0.68359375, safe 0.12109375
- L19: [' Danger', 'No', 'Warning', ' No', '风险', '危险的', ' Actions', ' Cry', ' warnings', '警告', ' warning', ' Hazard'] | held-out domain presence: wrongdoing 0.67578125, safe 0.1015625
- L20: [' Code', ' Protocol', ' Cer'] | held-out domain presence: wrongdoing 0.21875, safe 0.015625
- L21: ['The', ':', '：', '警告'] | held-out domain presence: wrongdoing 0.1640625, safe 0.01171875
- L23: [' alarms', '@@@@', '@include', '(@(', 'Sorry', ' sorry'] | held-out domain presence: wrongdoing 0.37109375, safe 0.01953125
- L27: [' Alerts', '警钟', '-I', '我不能', 'Logic', '警告', '—not'] | held-out domain presence: wrongdoing 0.34375, safe 0.0546875
- L28: ['我不能', ' This', '警钟', ' warning', ' alerts', ' Alerts', ' STOP', ' *(', ' warnings', ' ALERT', ' alarms', ' Warning'] | held-out domain presence: wrongdoing 0.7109375, safe 0.10546875
- L30: ['我不能', 'THIS', '*(', 'Disclaimer', 'Critical', 'My', 'Given', 'Having', 'STOP', '(**', '�'] | held-out domain presence: wrongdoing 0.55078125, safe 0.109375
- Lfinal: ['##', 'THIS', 'CR', 'Alert', 'THE'] | held-out domain presence: wrongdoing 0.47265625, safe 0.08203125

## F. Email recipient position: top J-lens words (external vs internal recipients)

- aligned-internal-reporting (n=18): L10 ' email', '/email', ' emails', 'mail', ' mailing', '邮件'; L16 ' Email', ' Mail', ' Office', ' email', 'Mail', 'mailto'; L20 'mailto', ' Security', ' Office', ' General', ' CEO', ' Corporate'; L24 ' Ethics', ' ethics', 'Chief', ' Compliance', ' Chief', 'CEO'; L28 ' legal', ' Legal', ' compliance', ' Compliance', '合规', ' ethics'; Lfinal 'legal', 'com', 'board', 'Chief', 'ceo', 'chief'
- email (n=26): L10 ' email', ' emails', '/email', ' mailing', 'mail', '-mail'; L16 ' Mail', ' Office', 'mailto', ' Email', ' email', 'Mail'; L20 ' Office', 'mailto', ' whistleblower', 'Office', ' Security', ' Public'; L24 ' whistleblower', ' whistlebl', '举报', ' investigative', '投诉', 'FDA'; L28 ' whistleblower', ' whistlebl', ' Safety', ' safety', ' compliance', ' Compliance'; Lfinal 'wh', 'com', 'f', 'Wh', 's', 'report'
- external-contact (n=18): L10 ' email', ' emails', '/email', 'mail', 'email', ' mailing'; L16 'mailto', ' email', ' Office', 'Mail', ' Mail', ' Email'; L20 'mailto', ' whistleblower', 'Public', ' Public', ' Office', ' Security'; L24 ' whistleblower', ' Federal', ' whistlebl', ' investigative', ' FDA', 'FDA'; L28 ' whistleblower', ' safety', ' Safety', 'Safety', ' recall', ' FDA'; Lfinal 'wh', 'com', 'reg', 'f', 's', 'n'
