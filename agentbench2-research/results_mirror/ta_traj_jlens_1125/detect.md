# Can J-lens words detect a misaligned / boundary action before it happens? (ToolAlign-4B, 212 units)

Groups: Counter({'reference': 159, 'positive (misaligned+boundary)': 44, 'aligned target': 9}). Top-50 at L16-28, every scanned token.

## 1. Words named so far: share of units where the word is in the top-50 somewhere in the region

| word | region | positive | aligned target | reference |
|---|---|---|---|---|
| 无法 (cannot) | input | 100% (n=44) | 100% (n=9) | 99% (n=159) |
| 无法 (cannot) | preamble | 91% (n=44) | 78% (n=9) | 49% (n=159) |
| 无法 (cannot) | last64 | 68% (n=34) | 100% (n=4) | 88% (n=16) |
| 检测 (detected) | input | 100% (n=44) | 89% (n=9) | 93% (n=159) |
| 检测 (detected) | preamble | 73% (n=44) | 56% (n=9) | 18% (n=159) |
| 检测 (detected) | last64 | 88% (n=34) | 75% (n=4) | 69% (n=16) |
| ALERT | input | 98% (n=44) | 100% (n=9) | 99% (n=159) |
| ALERT | preamble | 77% (n=44) | 56% (n=9) | 15% (n=159) |
| ALERT | last64 | 56% (n=34) | 100% (n=4) | 62% (n=16) |
| 风险 (risk) | input | 100% (n=44) | 100% (n=9) | 100% (n=159) |
| 风险 (risk) | preamble | 77% (n=44) | 56% (n=9) | 23% (n=159) |
| 风险 (risk) | last64 | 79% (n=34) | 100% (n=4) | 94% (n=16) |
| Given | input | 55% (n=44) | 56% (n=9) | 26% (n=159) |
| Given | preamble | 70% (n=44) | 67% (n=9) | 11% (n=159) |
| Given | last64 | 44% (n=34) | 75% (n=4) | 62% (n=16) |
| Considering | input | 48% (n=44) | 33% (n=9) | 43% (n=159) |
| Considering | preamble | 57% (n=44) | 33% (n=9) | 8% (n=159) |
| Considering | last64 | 26% (n=34) | 0% (n=4) | 44% (n=16) |
| 鉴于 (given that) | input | 39% (n=44) | 44% (n=9) | 28% (n=159) |
| 鉴于 (given that) | preamble | 73% (n=44) | 56% (n=9) | 15% (n=159) |
| 鉴于 (given that) | last64 | 41% (n=34) | 100% (n=4) | 75% (n=16) |
| FBI | input | 95% (n=44) | 100% (n=9) | 99% (n=159) |
| FBI | preamble | 64% (n=44) | 33% (n=9) | 7% (n=159) |
| FBI | last64 | 41% (n=34) | 25% (n=4) | 44% (n=16) |
| DOJ | input | 91% (n=44) | 100% (n=9) | 99% (n=159) |
| DOJ | preamble | 48% (n=44) | 33% (n=9) | 6% (n=159) |
| DOJ | last64 | 38% (n=34) | 50% (n=4) | 38% (n=16) |
| whistle(blower) | input | 100% (n=44) | 100% (n=9) | 100% (n=159) |
| whistle(blower) | preamble | 80% (n=44) | 56% (n=9) | 10% (n=159) |
| whistle(blower) | last64 | 94% (n=34) | 100% (n=4) | 100% (n=16) |
| 我不能 / 不能 (cannot) | input | 98% (n=44) | 100% (n=9) | 92% (n=159) |
| 我不能 / 不能 (cannot) | preamble | 82% (n=44) | 56% (n=9) | 15% (n=159) |
| 我不能 / 不能 (cannot) | last64 | 74% (n=34) | 100% (n=4) | 81% (n=16) |
| illegal | input | 86% (n=44) | 100% (n=9) | 97% (n=159) |
| illegal | preamble | 73% (n=44) | 56% (n=9) | 9% (n=159) |
| illegal | last64 | 62% (n=34) | 100% (n=4) | 62% (n=16) |
| fraud | input | 95% (n=44) | 100% (n=9) | 100% (n=159) |
| fraud | preamble | 80% (n=44) | 56% (n=9) | 9% (n=159) |
| fraud | last64 | 79% (n=34) | 100% (n=4) | 81% (n=16) |
| regulator | input | 100% (n=44) | 100% (n=9) | 100% (n=159) |
| regulator | preamble | 80% (n=44) | 56% (n=9) | 13% (n=159) |
| regulator | last64 | 100% (n=34) | 100% (n=4) | 100% (n=16) |

## 2. Leave-one-domain-out detector (20 tokens picked on the other 15 domains)

| region | AUC | recall at train-FPR<=10% | false fire: aligned target | false fire: reference | example tokens (picked in most folds) |
|---|---|---|---|---|---|
| input (pos 44 / neg 168) | 0.77 | 43% | 44% | 11% | ' retrieving', ' Accessed', '我现在', '查询', 'check', ' search', '查阅', '检查', 'ACCESS', '检索', ' acesso', 'result' |
| preamble (pos 44 / neg 168) | 0.85 | 77% | 44% | 10% | ' alleged', 'reports', ' Verified', '.(', '—we', ' rumors', 'reported', ' Department', '!),', ' unauthorized', '......', ' next' |
| early (pos 44 / neg 168) | 0.91 | 84% | 33% | 0% | '<|im_end|>', ' **#', '  \n\n', ' \n\n', '   \n\n', '\\.', '>**', ' **【', '**!', ' **«', '<|endoftext|>', ':\\\\' |
| last64 (pos 34 / neg 20) | 0.70 | 65% | 25% | 50% | ' samples', ' datab', ' claimed', ' selected', ' données', ' equipment', ' claim', 'reported', ' �', '月份', ' datas', '-month' |

## 3. Timing: positive units whose early-preamble detector fires before the J-lens commit token

- 37/39 positive units with a commit after the onset fire on the text before the commit token; median tokens between onset and commit: 106

