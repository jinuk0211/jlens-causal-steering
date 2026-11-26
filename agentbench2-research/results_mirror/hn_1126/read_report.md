# T6a reading-stage neurons, AgentDojo (2026-11-26 14:40:33)

units: fold 0 76, fold 1 176. z = (mean act on the injection span - mean act on the other tool-result tokens) / token sd.
neurons with fold-0 median z above 1 / 2 / 3 / 5: {'z0>1': 354, 'z0>2': 12, 'z0>3': 1, 'z0>5': 0}
layers of the top 200: [(1, 1), (2, 3), (3, 1), (4, 1), (5, 4), (6, 10), (7, 5), (8, 4), (9, 9), (10, 16), (11, 10), (12, 6), (13, 1), (14, 14), (15, 4), (16, 8), (17, 5), (18, 15), (19, 8), (20, 10), (21, 9), (22, 5), (23, 1), (24, 1), (25, 2), (26, 1), (27, 2), (28, 5), (29, 6), (30, 13), (31, 20)]

| neuron | z fold 0 (median) | z fold 1 (median) | fold 1 units with z > 1 | fold 1 units whose max on the injection beats the max elsewhere | words (+w) |
|---|---|---|---|---|---|
| L7/N296 | 3.1 | 3.4 | 100% | 100% | '：**' ' **' '>**' ':\\"' '。**' ' **【' ';**' ' **「' |
| L6/N753 | 2.9 | 3.1 | 100% | 100% | ' “[' ':\\' '?\\' ':\\"' '\\u' ' [\\' '”—' '’d' |
| L19/N1826 | 2.8 | 1.0 | 51% | 97% | ' your' ' you' 'your' ' Your' ' YOUR' 'Your' '你的' 'you' |
| L19/N4124 | 2.7 | 2.8 | 100% | 98% | '问题' '什么问题' '具体问题' '诉求' ' problem' '的问题' '详细描述' ' problems' |
| L12/N6662 | 2.4 | 2.5 | 100% | 100% | ' If' '...\\' ' __________________' '    ' '<|im_end|>' ' Regarding' ' Please' ' Recommend' |
| L20/N2384 | 2.3 | 2.6 | 100% | 99% | ' reasoning' '回答' '回复' '一步步' ' RESPONSE' '推理' ' Reply' ' respond' |
| L12/N6875 | 2.2 | 2.0 | 100% | 100% | ' Advice' ' Guidance' ' Useful' ' \n        \n' ' \n    \n' '但不要' ' Используйте' '帮助你' |
| L15/N4445 | 2.2 | 2.0 | 100% | 97% | '?\\' '？' '”?' '？”' '?”' "'?" '?“' '"?' |
| L10/N3865 | 2.2 | 2.2 | 100% | 100% | '––' 'Britain' ' Britain' ' Mme' '?...' ' vitt' ' фабри' '……' |
| L31/N550 | 2.2 | 2.1 | 94% | 91% | ' “' ' ‘' ' ”' '’s' ' (“' ' ’' '’' '”' |
| L14/N52 | 2.1 | 1.7 | 91% | 93% | '\n\n\n' '\n\n' '<|im_end|>' '\n \n' '\n\n\n\n\n' '\n\n\n\n' '\r\n\r\n' '\n' |
| L9/N7141 | 2.0 | 1.9 | 93% | 100% | ' instruction' ' instructed' 'instruction' ' instructions' '指令' 'Instruction' 'instructions' ' instruct' |
| L16/N6446 | 1.9 | 2.0 | 100% | 90% | '?“' ' ".' ' "?' ' “.' ' "".' ' "' ' “' ' ">' |
| L10/N6048 | 1.9 | 1.8 | 88% | 100% | ' É' '红烧' '别墅' 'olini' ' **' '撤回' '援' ' aluminium' |
| L14/N253 | 1.9 | 2.1 | 99% | 89% | '…).' ' […]' '…"' '…”' '…' '…)' '[…]' '.…' |
| L18/N749 | 1.8 | 1.8 | 92% | 87% | '隆重举行' '離婚' 'чал' ' settled' ' settles' ' devrez' 'inges' 'igts' |
| L5/N851 | 1.8 | 1.9 | 100% | 99% | ',[' '[[' ')[' 'Whilst' '大部分的' '()[' ').[' '",[' |
| L17/N4818 | 1.8 | 1.8 | 99% | 99% | '谜底' ' clues' 'hint' '谜' ' clue' ' hint' '揭晓' 'Hint' |
| L10/N1980 | 1.8 | 1.9 | 97% | 100% | ' ________' ' ____' ' **"' '________' '____' '?\\' '?' ' ______' |
| L28/N106 | 1.8 | 1.5 | 86% | 100% | ' th' ' tha' ' wi' ' anot' ' hav' ' teh' ' nto' ' ina' |
| L16/N3533 | 1.8 | 1.9 | 99% | 95% | ' likely' ' presumably' ' probably' ' seems' 'likely' ' seemingly' ' maybe' '似乎是' |
| L9/N1210 | 1.7 | 1.9 | 99% | 96% | '____' '?\\' '<|im_end|>' '_________' '？' '___' ' ____' '\\"' |
| L21/N3694 | 1.7 | 1.6 | 95% | 90% | ' debugging' ' Debug' ' debug' '调试' 'debug' 'Debug' '-debug' '/debug' |
| L11/N7309 | 1.7 | 1.6 | 97% | 100% | '联系人' ' conversation' '线索' '询问' '访谈' '走访' ' informant' ' Conversation' |
| L21/N426 | 1.7 | 1.7 | 88% | 95% | ' Neural' ' neural' ' halluc' ' Speech' '神经' ' speech' ' brain' ' neuro' |
| L20/N5166 | 1.7 | -0.3 | 36% | 41% | ' fill' ' fills' ' filling' '填' 'Fill' ' Fill' 'fill' '(fill' |
| L18/N473 | 1.7 | 1.7 | 96% | 57% | 'ANNEL' ' Investments' '...</' 'Coal' 'iern' ' Investment' '园内' '\n\n\n\n\n\n\n\n\n\n' |
| L31/N96 | 1.7 | 1.7 | 96% | 100% | ' SINGLE' ' RESPONSE' ' INITIAL' ' VALUE' ' CURRENT' ' THROUGH' ' COLLECTION' ' DIFF' |
| L14/N7683 | 1.7 | 1.8 | 99% | 100% | '你们的' '和你的' 'your' '让你们' '是你们' '你们' ' vostro' '你那' |
| L6/N3655 | 1.7 | 1.7 | 100% | 100% | ',’' '’,' ',”' '\xadt' '”—' '\xadtion' '”,' ",'" |
| L6/N2703 | 1.7 | 1.7 | 100% | 100% | '________' ' ________' '_____' ' _____' '_________' '____' ' ___' '___' |
| L10/N613 | 1.6 | 1.6 | 83% | 98% | ',' '<|endoftext|>' '–' '\tstrncpy' '不过在' ' –' '\tstrcpy' ' Впрочем' |
| L9/N8193 | 1.6 | 1.8 | 96% | 100% | ' my' ' myself' ' tôi' '我的' ' saya' 'my' '所以我' '因为我' |
| L9/N4042 | 1.6 | 1.9 | 97% | 99% | ':\\' '?\\' '.\\' ':"' ';\\' ':[' ',[' ':*' |
| L18/N8339 | 1.6 | 2.3 | 89% | 82% | ':</' '\\u' '?\\' '?</' '!</' '\\' '?”' ':\\' |
| L11/N7016 | 1.6 | 1.5 | 90% | 93% | ' seemingly' ' supposedly' ' seems' ' seem' ' weird' ' seemed' ' oddly' ' Disney' |
| L11/N2681 | 1.6 | 1.5 | 99% | 99% | ' **«' ' **“' '”**' ' Cannabis' '】**' ' **「' '"**' '）**' |
| L6/N2090 | 1.6 | 1.3 | 74% | 100% | ' analys' ':_' ' analysis' ' analyse' ' _:' ' analyst' ' _' ' _)' |
| L18/N5137 | 1.6 | 1.6 | 96% | 90% | '及相关' '及有关' '\n\n\n' ' ><' ' **«' " **'" ' *«' '\n\n\n\n' |
| L18/N2031 | 1.6 | 1.4 | 85% | 82% | '_.' '____' '?' ' ____' '__' '__.' '________' ' ___' |
| L14/N8118 | 1.6 | 1.6 | 95% | 100% | ' instructions' '指令' ' instruction' ' Instructions' ' directive' ' directives' ' instructed' 'instructions' |
| L19/N2864 | 1.6 | 1.5 | 99% | 77% | '….' '.…' '…' ' ….' ',…' '…)' '还是不' '?...' |
| L14/N2842 | 1.6 | 1.7 | 90% | 99% | '—the' '—' '—a' '—if' '—in' '—as' '—that' '—an' |
| L21/N4232 | 1.5 | 1.7 | 98% | 93% | ' Retrieve' ' retrieve' ' Evaluate' 'Evaluate' ' Find' '分析一下' 'etermine' ' prepare' |
| L7/N8027 | 1.5 | 1.6 | 100% | 100% | '？**' ' ?**' '！**' '**?' ' **【' ' !**' '**!' '？' |
| L12/N8671 | 1.5 | 1.8 | 95% | 100% | ' pricey' ' famously' '\n\n\n\n' '<|im_end|>' ' trendy' ' showcase' ' \n\n' ' hugely' |
| L9/N5122 | 1.5 | 1.6 | 96% | 97% | ' your' ' yourself' 'your' ' you' ' YOUR' '你的' ' Your' ' yourselves' |
| L20/N6252 | 1.5 | 1.1 | 65% | 100% | '附' ' information' '获取更多' '附有' '附带' ' gathering' 'Information' '信息' |
| L26/N7779 | 1.5 | 1.6 | 98% | 100% | ' assistant' ' assistants' '助' ' Assistant' 'Assistant' ' Assist' '助手' ' assist' |
| L31/N997 | 1.5 | 1.5 | 97% | 93% | '解决' ' solve' ' solving' '解' ' Sol' ' solved' ' solves' ' sol' |
| L14/N2297 | 1.5 | 1.4 | 93% | 93% | '...' '..."' '\n\n' "...'" '...)' '...\\' '......' ' ...' |
| L20/N492 | 1.5 | 1.5 | 93% | 99% | '训练' ' training' ' trained' ' Training' '训练的' '-trained' ' AI' '的训练' |
| L18/N5596 | 1.5 | 1.8 | 94% | 100% | '.","' '.",' ' \n  \n' '.".' ':\\\\' '.""' ".''" '\\",\\"' |
| L2/N186 | 1.5 | 1.1 | 57% | 100% | ' ``(' ' _____' ' ``' ' `_' ' ...\\' ' ____' ' `<' ' ___' |
| L30/N1523 | 1.5 | 1.5 | 94% | 100% | '!' '！' '!)' '!).' '!**' '!),' '!"' '!”' |
| L30/N312 | 1.5 | 1.5 | 97% | 93% | ' conf' 'conf' ' Conf' 'Conf' '-conf' '_conf' '/conf' '.conf' |
| L18/N231 | 1.5 | 1.5 | 97% | 78% | '？' '请问' '____' '？”' ' __' '?\\' ' ____' ' ___' |
| L30/N8100 | 1.5 | 1.3 | 72% | 80% | ' pose' ' poses' ' posed' ' Pose' 'pose' 'Pose' ' posing' 'poses' |
| L16/N5706 | 1.5 | 1.6 | 91% | 100% | ' supposedly' ' allegedly' ' якобы' ' purported' ' supposed' ' reportedly' ' claimed' ' claims' |
| L9/N1603 | 1.5 | 1.9 | 83% | 89% | ' congel' ' dumping' ' specs' ' ebay' ' labs' ' dred' ' scrut' ' inspection' |
