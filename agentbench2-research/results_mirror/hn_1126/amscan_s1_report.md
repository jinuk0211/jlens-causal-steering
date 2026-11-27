# AM full-reasoning neuron scan (2026-11-26 20:26:17)

samples: 174 (harmful 82, benign 92; original 92, fresh 82)
A neuron counts when its window-mean activation separates harmful from benign with AUROC >= 0.75 or <= 0.25 in both folds, same sign.

| response window (tokens) | samples (harmful / benign) | neurons | label permutation (mean of 5, max) | top-64 detector AUROC, fold 0 → 1 / 1 → 0 |
|---|---|---|---|---|
| 0-256 | 82 / 92 | 0 | 0, 0 | 0.53 / 0.53 |
| 256-512 | 81 / 92 | 1 | 0, 0 | 0.77 / 0.71 |
| 512-768 | 81 / 90 | 11 | 0, 0 | 0.73 / 0.79 |
| 768-1024 | 80 / 86 | 17 | 0, 0 | 0.72 / 0.73 |
| 1024-1280 | 77 / 85 | 30 | 0, 0 | 0.83 / 0.79 |
| 1280-1536 | 72 / 82 | 10 | 0, 0 | 0.72 / 0.68 |
| 1536-1792 | 66 / 80 | 23 | 0, 0 | 0.69 / 0.65 |
| 1792-2048 | 60 / 73 | 15 | 0, 0 | 0.66 / 0.64 |
| 2048-2304 | 50 / 67 | 235 | 0, 1 | 0.71 / 0.81 |
| 2304-2560 | 42 / 58 | 176 | 0, 1 | 0.86 / 0.76 |
| 2560-2816 | 34 / 48 | 546 | 3, 6 | 0.85 / 0.77 |
| 2816-3072 | 29 / 37 | 436 | 29, 71 | 0.64 / 0.72 |
| 3072-3328 | 25 / 33 | 8805 | 60, 85 | 0.82 / 0.80 |
| 3328-3584 | 23 / 25 | 1066 | 193, 291 | 0.62 / 0.41 |
| 3584-3840 | 21 / 17 | 2155 | 589, 1657 | 0.70 / 0.83 |
| 3840-4096 | 17 / 15 | 5477 | 811, 1710 | 0.75 / 0.65 |
| 256 before the first tool block | 81 / 90 | 30 | 0, 0 | 0.87 / 0.84 |

## Top neurons per window (AUROC fold 0, fold 1; above 0.5 = more active in harmful samples)

- **256-512**: L19/N5814 (0.75, 0.79) 'amac' 'kamp' '*(-' '抢抓'
- **512-768**: L19/N7672 (0.78, 0.78) ' divisions' 'division' ' divided' ' division'; L25/N2275 (0.23, 0.24) '第' ' option' '的第' ' №'; L23/N4448 (0.21, 0.24) '封' '等系列' '销' '.deleteById'; L26/N852 (0.23, 0.24) '้อย' 'antos' 'iman' 'abas'; L27/N2172 (0.24, 0.24) '切' ' mi' 'voirs' '条条'; L9/N84 (0.78, 0.76) '  \n\n' '  \n' '_____' '  \n\n\n'
- **768-1024**: L16/N3877 (0.21, 0.22) ' ...' '?...' '...' ' -->'; L24/N1030 (0.80, 0.78) ' accompanying' '伴随' ' accompany' ' accompanied'; L7/N7818 (0.77, 0.79) '...",' ' […]' ' ..."' '......'; L25/N8264 (0.77, 0.77) ' mess' ' messenger' ' message' ' messages'; L19/N8851 (0.21, 0.24) '客人' '.Cos' 'ijin' '乘风'; L26/N3189 (0.22, 0.24) 'kamp' '琅' ' Demp' 'ôn'
- **1024-1280**: L19/N6337 (0.17, 0.22) ' age' '龄' '年龄' ' Age'; L28/N7878 (0.78, 0.79) ' om' ' Om' 'que' ' Shack'; L24/N6517 (0.78, 0.79) ' included' ' Tal' 'ARIA' '面'; L26/N5699 (0.81, 0.78) ' theme' '主题' ' themes' ' Theme'; L29/N7196 (0.23, 0.21) '�' 'opia' ' Ev' 'addock'; L19/N6693 (0.23, 0.22) 'escaping' '逃离' ' escapes' '摆脱'
- **1280-1536**: L17/N6532 (0.23, 0.22) '国际标准' ' currencies' ' international' ' symbols'; L15/N3658 (0.77, 0.77) ' personal' 'laub' ' Personal' 'intang'; L11/N7150 (0.77, 0.79) '防护' ' stiff' ' sturdy' '春秋'; L21/N5804 (0.21, 0.23) ' vision' '狱' ' Vision' '身后'; L27/N1891 (0.76, 0.77) 'burgh' '칭' '/~' 'asto'; L21/N8084 (0.76, 0.77) ' commentary' ' comments' '注释' ' comment'
- **1536-1792**: L10/N1308 (0.21, 0.21) '____' '_____' '________' '_________'; L12/N9017 (0.78, 0.79) '伴随' '伴随着' ' accompany' '配合'; L2/N6934 (0.22, 0.22) '»' '—"' '—' '„'; L21/N9026 (0.78, 0.78) '两份' '三份' '一式' ' copies'; L16/N8083 (0.78, 0.80) '尚未' '未能' '还未' '还没有'; L21/N2179 (0.79, 0.78) ' description' ' comment' ' descriptions' '描述'
- **1792-2048**: L20/N7333 (0.22, 0.23) 'porter' 'Store' '最伟大的' ' porté'; L0/N7760 (0.77, 0.80) '**' '**-' '**|' '-**'; L13/N4323 (0.77, 0.77) 'Various' ' Various' ' diverse' ' complexities'; L29/N7022 (0.22, 0.23) '征' '戏' 'igger' '即刻'; L15/N2308 (0.77, 0.77) '辅助' ' added' '____' ' additional'; L17/N4058 (0.78, 0.77) '<|endoftext|>' '初步' 'itial' '\n\n'
- **2048-2304**: L4/N2907 (0.15, 0.14) '”' '\\_' '-"' '")'; L13/N2719 (0.83, 0.83) ' Triple' ' Dual' ' setara' 'dach'; L29/N4138 (0.82, 0.83) ' les' 'les' ' Les' 'Les'; L16/N2224 (0.82, 0.82) 'ريحة' ' Porque' '(&(' ' whenever'; L12/N7521 (0.17, 0.19) '?".' '?' '".' '.'; L29/N2998 (0.81, 0.81) ' Есте' '讨' '倾倒' 'ESE'
- **2304-2560**: L3/N1066 (0.82, 0.83) "''," "''." ',,' ')..'; L7/N2097 (0.19, 0.19) ' coloured' ' organised' ' Whilst' ' чёр'; L17/N8394 (0.81, 0.82) ' Majority' ' prominent' '特别' ' Due'; L30/N4724 (0.80, 0.81) 'assi' 'assed' 'acap' 'ucr'; L24/N5714 (0.18, 0.20) ' dance' ' Dance' ' dancer' '舞者'; L16/N2605 (0.81, 0.80) '...*' '?...' ' \n\n' ' \n\n\n'
- **2560-2816**: L7/N697 (0.86, 0.93) '”?' '”' '？”' '?”'; L28/N6917 (0.91, 0.85) ' Engel' ' FAM' ' bọt' '渣'; L27/N8828 (0.13, 0.15) ' charge' 'charge' 'trx' ' gum'; L15/N2205 (0.15, 0.09) '."' '\n\n' '"' '".'; L30/N5188 (0.16, 0.15) 'hong' 'ONG' 'ong' ' opposing'; L0/N6699 (0.16, 0.11) '.' ',' '?.' ';'
- **2816-3072**: L21/N5053 (0.86, 0.82) ' side' '一侧' ' Side' ' sides'; L11/N7717 (0.18, 0.07) ' ostensibly' ' seemingly' ' Blogger' ' blog'; L20/N5067 (0.82, 0.86) '色' '到目前' '充' 'engg'; L18/N4376 (0.84, 0.82) ' interpreting' ' personalised' ' interpretations' ' terminology'; L31/N3719 (0.83, 0.82) '铁' 'iron' ' iron' ' Iron'; L10/N1741 (0.18, 0.19) ' **“' ' **‘' '’**' ' **„'
- **3072-3328**: L12/N6361 (0.93, 0.92) '...' "...'" ' ...' '..."'; L11/N5824 (0.08, 0.08) '**.' '\\",' '**,' '”.'; L21/N4001 (0.08, 0.07) '百花' '同心' ' Contributors' ' Contributions'; L6/N7925 (0.92, 0.95) ' __' ' ______' ' ________' ' ____'; L24/N6288 (0.07, 0.09) ' sky' 'lim' '.apply' ' oppose'; L19/N5841 (0.09, 0.06) 'γγ' ' proportion' 'irth' 'ASK'
- **3328-3584**: L17/N8648 (0.90, 0.93) ' introductory' ' preamble' ' overall' ' announcing'; L21/N9026 (0.92, 0.88) '两份' '三份' '一式' ' copies'; L11/N987 (0.12, 0.12) ' women' ' wine' ' countless' ' wedding'; L11/N6078 (0.08, 0.12) ' defence' '抵御' '防御' '防守'; L0/N5292 (0.87, 0.91) '**' '".**' '？**' '-**'; L10/N8763 (0.87, 0.93) '首创' ' Kickstarter' '施工中' 'iej'
- **3584-3840**: L10/N6891 (0.93, 0.97) ' ______' '...\\' ' ...' '____'; L23/N1637 (0.07, 0.09) ' emerges' ' emerge' ' emerged' ' occurs'; L9/N7815 (0.94, 0.90) ' tipe' '类型' '类型的' ' Serialized'; L18/N4376 (0.94, 0.90) ' interpreting' ' personalised' ' interpretations' ' terminology'; L27/N4269 (0.03, 0.11) ' Roman' ' Bender' ' Gardner' 'Roman'; L25/N4892 (0.89, 0.92) 'ebbe' '�' ' Wise' 'Gap'
- **3840-4096**: L18/N7784 (0.95, 0.95) '保留' ' Canadá' ' Canadian' '/doc'; L28/N8720 (0.07, 0.06) ' drug' ' tor' 'Tor' 'drug'; L21/N9078 (0.93, 0.95) ' easy' 'easy' ' Easy' 'Easy'; L10/N5862 (0.93, 0.94) '’B' 'Whilst' '繋が' ' **‘'; L29/N3439 (0.05, 0.08) '-' '\xad' ' -' '-</'; L0/N1608 (1.00, 0.92) ' ``' " ''" '``' '\r\n\r\n'
- **256 before the first tool block**: L11/N7769 (0.80, 0.85) ' wielding' ' guards' ' viewing' '驭'; L20/N2893 (0.22, 0.17) ' reversing' ' reversal' ' extraction' ' returning'; L11/N5345 (0.78, 0.78) '.…' '……' '...' '……。'; L15/N3658 (0.78, 0.80) ' personal' 'laub' ' Personal' 'intang'; L11/N987 (0.22, 0.23) ' women' ' wine' ' countless' ' wedding'; L12/N7605 (0.23, 0.19) '____' ' essentials' ' ______' ' essential'
