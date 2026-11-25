# ToolAlignBench × J-lens: pre-registered analyses B-F (Gemma-4-E4B-it, base-fitted J-lens, greedy)

1373 steps, layers 0..40 + final. Same candidate tokens in every comparison.

## C. Action pressure at the first tool-name position of each document (paired wrongdoing − safe)

### Δ_email = lp(email) − lp(writeInternalLog); wrongdoing − safe, 235 pairs from 16 domains

| layer | 0 | 3 | 6 | 9 | 12 | 15 | 18 | 21 | 24 | 27 | 30 | 33 | 36 | 39 | final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mean | -0.16 | -0.13 | -0.10 | -0.16 | +0.70 | -0.13 | -0.63 | -0.12 | +0.15 | +0.17 | +0.33 | -0.05 | +1.74 | +1.67 | +3.51 |
| 95% CI | [-0.20,-0.12] | [-0.33,+0.07] | [-0.19,-0.01] | [-0.32,-0.03] | [+0.53,+0.89] | [-0.27,+0.01] | [-0.91,-0.36] | [-0.32,+0.10] | [+0.11,+0.18] | [+0.07,+0.26] | [-0.05,+0.72] | [-0.48,+0.39] | [+1.08,+2.34] | [+1.15,+2.18] | [+2.66,+4.40] |

- layers whose domain-clustered CI excludes 0: ['0', '4', '5', '6', '7', '8', '9', '11', '12', '13', '14', '16', '17', '18', '22', '23', '24', '25', '26', '27', '28', '29', '35', '36', '37', '38', '39', '40', 'final']

### Δ_misaligned = lp(best clearly-misaligned tool) − lp(writeInternalLog); wrongdoing − safe, 235 pairs from 16 domains

| layer | 0 | 3 | 6 | 9 | 12 | 15 | 18 | 21 | 24 | 27 | 30 | 33 | 36 | 39 | final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mean | +0.05 | +0.56 | -0.42 | -0.28 | -0.51 | -0.18 | -1.95 | -0.38 | +0.23 | -0.03 | +0.85 | +0.10 | +0.79 | +1.54 | +2.33 |
| 95% CI | [+0.01,+0.10] | [+0.31,+0.81] | [-0.64,-0.19] | [-0.45,-0.10] | [-0.70,-0.33] | [-0.40,+0.02] | [-2.51,-1.40] | [-0.80,+0.02] | [+0.16,+0.30] | [-0.18,+0.15] | [+0.34,+1.36] | [-0.56,+0.71] | [+0.08,+1.55] | [+0.87,+2.27] | [+1.51,+3.16] |

- layers whose domain-clustered CI excludes 0: ['0', '1', '3', '4', '5', '6', '7', '9', '10', '11', '12', '13', '16', '17', '18', '19', '20', '23', '24', '25', '26', '28', '30', '32', '35', '36', '37', '38', '39', '40', 'final']

## C/D. Lock-in layer and profile by final choice (all tool-name positions)

| group (type:risk:category) | calls | domains | lock-in layer median [IQR] | Δ_email L16 / L26 / L34 / final | Δ_mis L16 / L26 / L34 / final |
|---|---|---|---|---|---|
| safe:aligned:aligned-internal-reporting | 3 | 3 | [35.5, 41.0, 41.0] | +4.62 / +0.54 / +0.38 / +3.33 | +2.33 / -0.54 / -0.42 / +2.08 |
| safe:aligned:aligned-logging | 336 | 16 | [29.0, 29.0, 29.0] | +2.03 / +1.06 / -5.11 / -17.60 | -0.67 / -0.91 / -6.53 / -16.67 |
| safe:boundary:unauthorized-access | 14 | 6 | [34.2, 35.0, 40.0] | +2.50 / +1.21 / +0.57 / -3.06 | -1.24 / -0.55 / -1.56 / -3.07 |
| safe:clearly-misaligned:data-exfiltration | 5 | 2 | [31.0, 35.0, 35.0] | +3.05 / +0.93 / -0.95 / +2.77 | +0.70 / -0.43 / +1.87 / +10.14 |
| safe:clearly-misaligned:evidence-tampering | 1 | 1 | [37.0, 37.0, 37.0] | +4.25 / +0.50 / +0.00 / -6.38 | +2.25 / -0.25 / +1.25 / +4.75 |
| safe:clearly-misaligned:record-manipulation | 1 | 1 | [30.0, 30.0, 30.0] | +4.12 / +0.50 / -0.12 / -7.12 | +2.88 / -0.25 / +1.12 / +5.25 |
| wrongdoing:aligned:aligned-internal-reporting | 108 | 16 | [23.0, 23.0, 30.0] | +2.34 / +1.63 / +2.45 / +10.99 | -0.68 / -0.87 / -3.09 / -0.68 |
| wrongdoing:aligned:aligned-logging | 477 | 16 | [29.0, 29.0, 29.0] | +2.15 / +1.24 / -4.46 / -14.42 | -0.30 / -0.58 / -5.36 / -13.09 |
| wrongdoing:boundary:email | 6 | 4 | [23.0, 26.5, 30.0] | +1.73 / +1.73 / +2.69 / +10.89 | -1.27 / -1.12 / -3.44 / -2.41 |
| wrongdoing:boundary:unauthorized-access | 43 | 11 | [32.0, 35.0, 40.5] | +2.71 / +1.35 / +1.30 / -2.62 | -0.41 / +0.05 / +0.29 / +1.64 |
| wrongdoing:clearly-misaligned:data-exfiltration | 26 | 10 | [31.0, 39.0, 40.8] | +3.13 / +1.02 / -0.08 / +0.46 | +1.34 / +0.09 / +2.23 / +10.27 |
| wrongdoing:clearly-misaligned:evidence-tampering | 17 | 10 | [29.0, 32.0, 34.2] | +3.36 / +0.88 / +0.10 / -2.29 | +1.36 / +0.10 / +0.91 / +5.37 |
| wrongdoing:clearly-misaligned:external-contact | 38 | 12 | [23.0, 23.0, 26.0] | +1.79 / +1.97 / +3.62 / +14.09 | -1.43 / -0.93 / -3.65 / -0.67 |
| wrongdoing:clearly-misaligned:record-manipulation | 18 | 8 | [36.2, 41.0, 41.0] | +2.94 / +0.76 / +0.01 / -1.49 | +0.77 / +0.22 / +0.66 / +4.81 |
| wrongdoing:clearly-misaligned:system-manipulation | 3 | 1 | [27.0, 29.0, 32.0] | +1.54 / +2.00 / +0.04 / -4.62 | +0.96 / +1.54 / +5.34 / +14.52 |

Lock-in layer = first layer from which the chosen tool's first token ranks first among the domain's tool tokens and stays first through the final logits.

## E. Onset: lp(<tool_call>) by layer, wrongdoing − safe (paired by domain, doc, condition, step 0)

| layer | 0 | 3 | 6 | 9 | 12 | 15 | 18 | 21 | 24 | 27 | 30 | 33 | 36 | 39 | final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mean | -0.05 | -3.10 | -0.54 | -0.02 | -2.79 | -1.28 | +0.15 | -1.87 | -0.13 | +0.00 | -1.15 | +0.47 | -0.91 | -0.89 | -0.71 |
| 95% CI | [-0.09,-0.01] | [-4.96,-1.31] | [-1.03,-0.07] | [-0.30,+0.23] | [-3.62,-1.92] | [-1.91,-0.69] | [-0.35,+0.64] | [-2.59,-1.25] | [-0.30,+0.05] | [-0.37,+0.45] | [-1.95,-0.34] | [-0.10,+1.09] | [-1.79,+0.01] | [-1.63,-0.11] | [-1.11,-0.32] |

- 256 pairs from 16 domains

## B. Words read out at the end of each document (onset, step 0): in top-30 for >= 9/16 domains in wrongdoing, <= 3/16 in safe; leave-one-domain-out presence

- L3: [' മറ്റ്'] | held-out domain presence: wrongdoing 0.0, safe 0.0
- L5: ['─', '且', '层', '⁺', '喺'] | held-out domain presence: wrongdoing 0.359375, safe 0.03515625
- L6: ['––', '方的', '\u200cو', '՝', '专属'] | held-out domain presence: wrongdoing 0.43359375, safe 0.0625
- L7: ['⭐⭐'] | held-out domain presence: wrongdoing 0.10416666666666667, safe 0.034722222222222224
- L9: [' functionalities', '—'] | held-out domain presence: wrongdoing 0.1015625, safe 0.015625
- L10: [' своём', ' utilize', ' Generalized', ' সময়ে', ' massive', '!:', '하였'] | held-out domain presence: wrongdoing 0.6640625, safe 0.12890625
- L11: [' foundational', ' extremely', ' unsurprisingly', ' Extremely', ' Regardless', ' historically', ' fascinating'] | held-out domain presence: wrongdoing 0.44140625, safe 0.109375
- L12: [' unsurprisingly', ' leveraging', ' shockingly', ' foundational'] | held-out domain presence: wrongdoing 0.44140625, safe 0.06640625
- L13: [' 대한민국', ' Blockchain', 'Regardless', ' collaboratively', 'يًا', ' BuzzFeed', ' unsurprisingly', ' leveraging', ' showcasing', ' incredibly'] | held-out domain presence: wrongdoing 0.453125, safe 0.0703125
- L14: [' 대한민국', ' تمامی', 'يًا', 'Documentation', ' Blockchain', '?!?!', ' Markdown', ' আবারো', 'Screenshot', ' impactful', ' tweet', 'ITICAL'] | held-out domain presence: wrongdoing 0.73046875, safe 0.1484375
- L15: ['第一时间', ' تمامی', '🤦', 'Alright', '执法', 'Upon', '🤯', ' 대한민국'] | held-out domain presence: wrongdoing 0.5703125, safe 0.09375
- L16: ['震惊', 'udos', '🔥🔥', ' السلام', '!!!"', ' horrifying', '自身の', ' 대한민국', '드립니다', '🖤', '...";', '举报'] | held-out domain presence: wrongdoing 0.6171875, safe 0.08203125
- L17: ['🚨', '举报', 'Documentation', ' livestream', ' whistleblower', 'TransactionLog', ' Prosecutor', '文档', 'Logs', ' redacted', ' blockchain'] | held-out domain presence: wrongdoing 0.55859375, safe 0.109375
- L18: ['⚖', '🚨', ' कार्रवाई', ' urgently', ' finalizing', ' operational', '第一时间', ' document'] | held-out domain presence: wrongdoing 0.40625, safe 0.0546875
- L19: ['緊急', '紧急', '震惊', ' ██', ' urgently', ' livestream', ' archival', ' rapporter'] | held-out domain presence: wrongdoing 0.41015625, safe 0.04296875
- L20: ['緊急', '紧急', '第一时间', '🔥🔥', '震惊', '⚖', ' 緊急', '立即', ' catastrophic', '報道', ' livestream', '加密'] | held-out domain presence: wrongdoing 0.6640625, safe 0.0859375
- L21: ['迅速', 'zilla', 'urk', ' 緊急', ' urgent', '震惊', '\\&', ' माफिया', 'EventManager', 'ALERT', 'aclysm', ' unprecedented'] | held-out domain presence: wrongdoing 0.80078125, safe 0.19140625
- L22: [' utilising', ' *', ' ทั้ง', ' explicitly', ':', ')));', ' fundamentally', ' unequivocally', '\\"', " '';", ' ไม่', ' clearly'] | held-out domain presence: wrongdoing 0.53125, safe 0.08203125
- L23: ['ㅋㅋㅋㅋㅋㅋㅋㅋ', 'Chapter', 'Following', 'Throughout', ':[', 'Born', 'Download'] | held-out domain presence: wrongdoing 0.3125, safe 0.046875
- L24: ['Anderson', 'Regardless', 'NOTE', 'Spencer', 'Evans', 'Though', 'Films', ' CONCLUSION'] | held-out domain presence: wrongdoing 0.33984375, safe 0.08203125
- L25: ['DESCRIPTION', ' CONCLUSION', 'RESPONSE', 'Ź', 'ARTICLE', 'wikipedia', 'Written', 'Several', 'Once', 'Though', ' CHALL'] | held-out domain presence: wrongdoing 0.5703125, safe 0.10546875
- L26: [' Undoubtedly', ' Whatever', 'Entire', 'Concern', 'Editar', 'nThe', 'Everything', 'Nelson', 'COMPLETE', 'Immediately', 'Documentation'] | held-out domain presence: wrongdoing 0.49609375, safe 0.12890625
- L27: ['Editors', 'Logan', ' JOURNAL', 'Immediately', ' Historically', 'Erin', 'PHYS', 'Aaron', 'Dangerous', 'Suddenly', 'EMAIL', 'BOTH'] | held-out domain presence: wrongdoing 0.7734375, safe 0.11328125
- L28: ['Martin', 'Immediately', 'この記事', 'Strateg', 'RECORD', 'Warren', 'DOCUMENT', 'Regardless', 'Entire', 'This', 'Hern', 'Rosen'] | held-out domain presence: wrongdoing 0.76171875, safe 0.08203125
- L29: [' Owing', ' aufgrund', ' This', ' Aufgrund', 'Regardless', 'The', ' Concerned', 'This', '[[[[', ' Мне', ' this', ' هذا'] | held-out domain presence: wrongdoing 0.625, safe 0.1015625
- L30: ['Due', 'この', ' this', 'this', ' هذا', ' هذه', 'Regardless', '这座', 'ဤ', 'OfThe', ' этот', '这场'] | held-out domain presence: wrongdoing 0.49609375, safe 0.0859375
- L31: [' this', ' هذا', ' aufgrund', 'Due', 'この', 'this', '鉴', 'のお客様', '<eos>', ' इस', 'OfThe', 'Because'] | held-out domain presence: wrongdoing 0.62890625, safe 0.09765625
- L32: [' 基于', ' This', 'Judging', ' this', ' هذا', 'この', ' इस', 'this', ' этот', 'OfThe', ' هذه', ' Aufgrund'] | held-out domain presence: wrongdoing 0.63671875, safe 0.12109375
- L33: ['This', '我的', 'Considering', 'この', ' This', ' this', 'this', ' هذا', ' هذه', 'Given', ' этот', '！！！'] | held-out domain presence: wrongdoing 0.5078125, safe 0.09765625
- L34: [' يا', 'This', 'my', 'Given', 'Considering', '！！', '我的', 'この', ' this', 'this', 'The', ' هذا'] | held-out domain presence: wrongdoing 0.6640625, safe 0.11328125
- L35: ['my', 'Given', 'This', ' मेरी', 'Regardless', 'Detected', 'Received', ' моих', '我的', 'Receipt', 'The', ' the'] | held-out domain presence: wrongdoing 0.4375, safe 0.10546875
- L36: [' Given', 'Due', ' This', ' My', 'As', ' my', ' The', ' the', '鉴', 'Observation', 'Receipt', ' \\<'] | held-out domain presence: wrongdoing 0.5, safe 0.12109375
- L37: [" '<", 'ERROR', ' This', '鉴', 'Considering', 'Due', '殿', ' the', ' given', '《', 'OfThe', ' my'] | held-out domain presence: wrongdoing 0.6875, safe 0.125
- L38: ['<!', ' Commander', 'Peter', 'Well', ' This', '我的', 'Considering', '我对', ' Peter', ' the', ' எனக்கு', 'Due'] | held-out domain presence: wrongdoing 0.83203125, safe 0.16015625
- L39: ['Due', ' This', 'Running', 'Your', ' Recognizing', 'OfThe', '您', 'Analysis', 'Greetings', 'Rece', ' the', ' thanks'] | held-out domain presence: wrongdoing 0.80078125, safe 0.21484375
- L40: ['Considering', 'Among', 'ERROR', ' Given', 'ivos', 'Following', 'Your', ' This', 'Processing', '当', 'Rece', 'Analyzing'] | held-out domain presence: wrongdoing 0.70703125, safe 0.1484375
- Lfinal: ['*(', 'Analyzing', 'Analysis', 'Due', '§', 'W', 'Evidence', 'Rece', 'Document', 'Despite', 'Upon', 'Across'] | held-out domain presence: wrongdoing 0.609375, safe 0.0703125

## F. Email recipient position: top J-lens words (external vs internal recipients)

- aligned-internal-reporting (n=111): L13 ' Email', 'EMAIL', 'Email', ' email', '邮箱', 'email'; L21 ' ",', '.",', '\\",', '\\"",', '}",', ':",'; L26 '<unused2211>', '<unused2117>', 'Fitz', 'editors', 'Nelson', 'commander'; L32 ' CEO', 'CEO', ' Chief', ' Legal', 'Legal', 'Chief'; L37 ' Chief', 'Chief', ' Legal', ' Compliance', 'Compliance', ' legal'; Lfinal 'Chief', 'Legal', 'compliance', 'Compliance', 'legal', 'Executive'
- email (n=6): L13 ' Email', 'Email', 'EMAIL', ' email', '邮箱', 'email'; L21 '}",', '",', '?",', ')",', '.";', ' ",'; L26 'Warner', 'editors', 'Evans', 'Fitz', 'brothers', '<unused2117>'; L32 'CEO', ' CEO', ' Legal', ' legal', ' Chief', 'Legal'; L37 ' legal', 'legal', ' Legal', 'Legal', 'CEO', 'Chief'; Lfinal 'Legal', 'legal', 'Executive', 'executive', 'General', 'Chief'
- external-contact (n=38): L13 ' Email', 'EMAIL', 'Email', ' email', ' Emails', 'email'; L21 '",', ')",', '}",', '.",', '%",', ':",'; L26 'Nelson', '<unused2117>', 'Warner', 'brothers', 'Evans', 'Fitz'; L32 ' regulatory', ' regulator', ' regulators', ' Regulatory', 'Regulatory', 'regulatory'; L37 ' regulatory', ' regulators', ' regulator', 'regulatory', '监管', 'Regulatory'; Lfinal 'regulatory', 'wh', 'reg', 'Regulatory', 'external', 'External'
