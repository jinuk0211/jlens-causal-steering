# J-Cascade stage 1b: neuron map (transfer decisions)

## decision point: bad 19 vs good 56
- poles with one-sided Fisher p < 0.001: 196 (label-permutation null mean 25.05, max 81)
- layers of those poles: {26: 8, 16: 13, 15: 8, 21: 5, 12: 9, 29: 5, 19: 10, 20: 8, 23: 11, 25: 11, 14: 14, 28: 11, 24: 13, 13: 16, 22: 6, 17: 14, 30: 10, 31: 8, 18: 8, 27: 8}

| layer | neuron | pole | bad | good | p | family | J-lens words | eff transfer | eff <tool_call> |
|---|---|---|---|---|---|---|---|---|---|
| L26 | 5542 | + | 11/19 | 2/56 | 9.4e-07 | None | ' cal' · ' Bale' · ' каль' · 'Wh' · ' kal' · 'Kal' | 0.446 | 1.151 |
| L16 | 457 | - | 10/19 | 1/56 | 1.1e-06 | None | '—.' · ',—' · '—"' · ')—' · ',' · '—that' | 0.178 | 0.357 |
| L15 | 6036 | + | 8/19 | 0/56 | 4.5e-06 | None | ' **“' · ' **«' · ' **"' · ' **【' · ' **„' · ' "**' | -1.531 | 3.583 |
| L21 | 1343 | - | 8/19 | 0/56 | 4.5e-06 | None | 'almas' · '\\n' · '加拉' · '\\":{\\"' · 'agin' · '\\")' | -2.234 | 2.112 |
| L21 | 2424 | - | 10/19 | 2/56 | 5.6e-06 | None | '都市' · '剪刀' · '城市发展' · '城市' · '世' · '%@' | -1.909 | -0.811 |
| L12 | 628 | - | 10/19 | 2/56 | 5.6e-06 | None | ' whilst' · '不过在' · 'Whilst' · ' rather' · ' programmes' · ' mainly' | -1.799 | -5.248 |
| L12 | 3096 | - | 9/19 | 1/56 | 6.4e-06 | None | 'อยู่แล้ว' · '部份' · '既に' · ' proposals' · '加强与' · ' favourable' | 0.503 | -6.556 |
| L15 | 8719 | + | 7/19 | 0/56 | 2.5e-05 | None | '所以现在' · '同一' · '\\.' · '类似于' · '统称' · '大部分都是' | -0.091 | 1.454 |
| L29 | 2916 | - | 7/19 | 0/56 | 2.5e-05 | None | ' making' · ' building' · ' Building' · ' Making' · 'building' · 'Building' | -2.144 | 0.258 |
| L16 | 6298 | - | 7/19 | 0/56 | 2.5e-05 | None | ' ___' · ' __' · ' _____' · ' \\"' · ' what' · ' ____' | -4.116 | -0.033 |
| L19 | 381 | - | 9/19 | 2/56 | 3.0e-05 | retry | 'ox' · ' ox' · 'ixe' · ' again' · '.mx' · ' Pax' | 0.712 | -0.002 |
| L20 | 4935 | + | 8/19 | 1/56 | 3.4e-05 | None | 'undur' · '白头' · '一空' · '重新启动' · 'marsh' · 'eteria' | -1.716 | 0.276 |
| L23 | 2650 | + | 8/19 | 1/56 | 3.4e-05 | None | ' corners' · ' corner' · 'corner' · ' losses' · 'Corner' · ' hit' | -3.905 | 2.926 |
| L26 | 3989 | + | 8/19 | 1/56 | 3.4e-05 | None | ' Nice' · ' nice' · 'Nice' · 'nice' · ' cute' · ' nic' | -0.468 | 1.352 |
| L25 | 2626 | + | 8/19 | 1/56 | 3.4e-05 | None | '립' · 'Caught' · '总站' · 'okers' · '境地' · '时至' | -0.466 | -0.138 |
| L23 | 1548 | - | 8/19 | 1/56 | 3.4e-05 | None | 'flen' · ' efisiensi' · '效率' · ' nødvendig' · 'emon' · '占全国' | 3.372 | -2.695 |
| L14 | 7921 | + | 6/19 | 0/56 | 1.3e-04 | None | ' subtype' · '不同类型' · ' abort' · ' termed' · '不同类型的' · ' hybrid' | 0.171 | -0.388 |
| L28 | 4361 | + | 6/19 | 0/56 | 1.3e-04 | None | 'im' · 'ichi' · 'ral' · 'gre' · ' Att' · 'unes' | -2.103 | -0.775 |
| L15 | 4028 | + | 6/19 | 0/56 | 1.3e-04 | None | ' huma' · ' testi' · ' belief' · ' \n' · ' ...' · ' sins' | -1.236 | 1.683 |
| L24 | 5287 | + | 6/19 | 0/56 | 1.3e-04 | None | '应是' · '应有' · '应' · ' seharusnya' · 'ilver' · '应为' | 0.877 | 0.356 |
| L24 | 7766 | + | 6/19 | 0/56 | 1.3e-04 | None | '选' · ' tán' · '合作用' · '選' · '技术中心' · '快' | -2.909 | -0.454 |
| L13 | 4839 | + | 6/19 | 0/56 | 1.3e-04 | None | '大約' · '篝' · '很多家长' · ' Fakat' · ' ‘' · ' seputar' | -3.62 | -4.936 |
| L22 | 5710 | + | 6/19 | 0/56 | 1.3e-04 | None | ' small' · ' Small' · ' pequeños' · 'small' · 'Small' · ' peque' | 2.473 | 1.877 |
| L24 | 2459 | + | 6/19 | 0/56 | 1.3e-04 | None | ' homemade' · ' home' · 'home' · ' Home' · ' DIY' · ' Homemade' | 0.352 | -0.099 |
| L24 | 7084 | + | 6/19 | 0/56 | 1.3e-04 | None | ' кам' · 'witch' · ' gej' · 'ãi' · 'oud' · '/export' | 2.382 | -0.915 |
| L17 | 1698 | + | 6/19 | 0/56 | 1.3e-04 | None | '...\\' · ':...' · '...",' · '尤为重要' · ',...' · '...).' | 2.542 | 0.926 |
| L14 | 4819 | - | 6/19 | 0/56 | 1.3e-04 | None | ' journal' · 'both' · '——' · '-plus' · ' uta' · '线上线下' | -0.248 | -0.544 |
| L24 | 7264 | - | 6/19 | 0/56 | 1.3e-04 | None | '搜索' · ' search' · ' searches' · ' Search' · 'Search' · 'search' | -3.243 | 0.148 |
| L17 | 6067 | - | 6/19 | 0/56 | 1.3e-04 | None | ' then' · '然后' · 'then' · 'Then' · ' Then' · '然后在' | 0.45 | 1.209 |
| L23 | 1241 | - | 6/19 | 0/56 | 1.3e-04 | None | 'колко' · 'drž' · '说吧' · 'atak' · 'deo' · '蜗' | -1.082 | -3.501 |

## toolname point: bad 19 vs good 56
- poles with one-sided Fisher p < 0.001: 150 (label-permutation null mean 18.5, max 92)
- layers of those poles: {13: 11, 14: 15, 15: 15, 12: 7, 16: 12, 27: 4, 17: 12, 20: 7, 30: 7, 24: 5, 18: 2, 29: 7, 28: 2, 23: 5, 22: 4, 19: 13, 26: 8, 21: 6, 25: 3, 31: 5}

| layer | neuron | pole | bad | good | p | family | J-lens words | eff transfer | eff <tool_call> |
|---|---|---|---|---|---|---|---|---|---|
| L13 | 9212 | + | 12/19 | 2/56 | 1.4e-07 | None | '...' · '\n\n' · ' ...' · ' [...]' · '</endoftext/>' · ' […]' | -0.174 | 2.607 |
| L14 | 1516 | + | 12/19 | 4/56 | 2.3e-06 | None | '.**' · '?”.' · '**.' · '?.' · '?).' · '?**' | 1.556 | -2.164 |
| L15 | 6776 | + | 8/19 | 0/56 | 4.5e-06 | None | ' …' · ' ...' · '……' · '…' · '…**' · ' [...]' | -1.053 | 4.219 |
| L12 | 4694 | + | 7/19 | 0/56 | 2.5e-05 | None | ' nons' · '\\"' · ' \\"' · ' non' · ' unbelie' · ' Negro' | -0.825 | -0.872 |
| L16 | 3251 | + | 7/19 | 0/56 | 2.5e-05 | retry | ' rather' · '而不是' · '而非' · ' instead' · 'rather' · 'instead' | 1.227 | -2.144 |
| L27 | 6332 | + | 7/19 | 0/56 | 2.5e-05 | None | '智' · '胶' · '褚' · '水晶' · ' Maret' · 'break' | 2.008 | 1.873 |
| L17 | 547 | - | 7/19 | 0/56 | 2.5e-05 | None | '  \n' · '   ' · '  ' · '    ' · '\xa0\xa0\xa0' · '  \n\n' | 1.381 | 1.324 |
| L13 | 7011 | + | 9/19 | 2/56 | 3.0e-05 | None | '……' · ' […]' · '……。' · ',…' · ' […' · '…,' | 2.272 | 0.69 |
| L20 | 8820 | + | 9/19 | 2/56 | 3.0e-05 | None | '死者' · 'گذ' · ' osc' · '打开了' · ' opening' · ' **-' | 2.266 | -0.112 |
| L17 | 2922 | + | 9/19 | 2/56 | 3.0e-05 | None | '</im_end/>' · '\\n' · '____' · '……' · '</endoftext/>' · '________' | 0.548 | 5.173 |
| L20 | 3965 | - | 9/19 | 2/56 | 3.0e-05 | None | ' Arctic' · ' Greenland' · ' Norse' · ' Alaska' · ' Scandin' · '挪威' | -0.452 | 0.405 |
| L17 | 491 | - | 9/19 | 2/56 | 3.0e-05 | None | '.).' · ').' · ' {}.' · ' ().' · '$.' · '».' | -2.525 | -0.864 |
| L30 | 1693 | - | 8/19 | 1/56 | 3.4e-05 | None | '”…' · 'ButtonModule' · 'orgeous' · '.…' · 'ніка' · '隈' | 0.53 | -2.148 |
| L24 | 4035 | + | 6/19 | 0/56 | 1.3e-04 | None | ' significance' · ' highly' · ' Highly' · 'emek' · ' стат' · '-stat' | -2.783 | -0.637 |
| L30 | 3081 | + | 6/19 | 0/56 | 1.3e-04 | None | '社会' · '该' · '所有' · '人体' · '整个' · '各' | 2.13 | -1.937 |
| L14 | 3322 | + | 6/19 | 0/56 | 1.3e-04 | None | '...**' · ' ?**' · '...</' · '…**' · '？**' · ' .**' | -1.851 | 1.449 |
| L27 | 123 | - | 6/19 | 0/56 | 1.3e-04 | None | '",' · '".' · '”' · '")' · '\\"",' · ')",' | -2.211 | -2.326 |
| L17 | 7975 | - | 6/19 | 0/56 | 1.3e-04 | None | '\n\n\n' · '\n\n\n\n' · '其他' · '  \n\n\n' · '等其他' · '独立' | 3.859 | 2.878 |
| L18 | 4193 | - | 6/19 | 0/56 | 1.3e-04 | None | ',\\"' · '\\"' · ' "\\(' · ' \'\\"' · ' Coming' · '\\""' | -0.562 | 3.346 |
| L29 | 1973 | - | 6/19 | 0/56 | 1.3e-04 | None | 'agne' · 'AFX' · '汇丰' · '蚌埠' · 'neur' · '芹' | 1.436 | 0.9 |
| L13 | 1021 | - | 6/19 | 0/56 | 1.3e-04 | None | ' اصلاح' · '新规' · '补丁' · ' обнов' · '多年來' · '企业提供' | -0.133 | 0.141 |
| L17 | 8606 | - | 6/19 | 0/56 | 1.3e-04 | None | ' secret' · ' anonymous' · '2' · ' hiatus' · ' anon' · 'secret' | 5.937 | -1.275 |
| L13 | 6748 | - | 6/19 | 0/56 | 1.3e-04 | None | ' hierarchy' · ' priesthood' · '贿赂' · ' catholic' · ' **' · 'druck' | 1.515 | -2.409 |
| L16 | 4502 | - | 6/19 | 0/56 | 1.3e-04 | None | '？**' · ' ?**' · '?<' · ' <' · ' (__' · '_<' | 0.456 | 2.25 |
| L14 | 3503 | - | 6/19 | 0/56 | 1.3e-04 | None | '…”' · '...",' · '…"' · '…»' · '…' · '\n\n' | -0.627 | 2.787 |
| L17 | 7565 | - | 6/19 | 0/56 | 1.3e-04 | None | '民工' · ' migrant' · '务工人员' · 'igrant' · ' unfinished' · 'unfinished' | 0.156 | -1.871 |
| L29 | 7079 | + | 8/19 | 2/56 | 1.5e-04 | None | ' telesc' · ' tele' · '武' · '.Tele' · ' tel' · 'apers' | 0.96 | -1.083 |
| L28 | 6241 | + | 8/19 | 2/56 | 1.5e-04 | None | '得了' · '算' · '好了' · '算了' · '行了' · ' whatever' | 1.358 | 0.035 |
| L15 | 7387 | + | 8/19 | 2/56 | 1.5e-04 | None | ':' · ':"' · '!)' · '!"' · ':-' · '"(' | 4.085 | 0.168 |
| L23 | 7475 | + | 8/19 | 2/56 | 1.5e-04 | None | 'kers' · 'orer' · ' Blond' · ' Datum' · 'ners' · ' Lim' | 1.468 | -0.452 |

## retry-family poles: 7069; bipolar give-up/go poles: 70

- L12 N2863: + inability ['  \n\n', ' unspecified', '不确定', ' varies', 'Cannot'] / - retry [' Putin', ' Obama', ' Barack', ' Benedict', ' sne']
- L12 N2964: + acknowledgement [' Wilderness', ' Panic', ' Emergency', ' Desert', ' Quadr'] / - proceed [' caf', ' efficiencies', ' perfect', ' efficienza', ' efficiency']
- L12 N4696: + apology ['”,', '”', '\\n', '️', ' \\'] / - retry [' \n\n\n', '或者其他', '或其他', '调查结果', ' \n\n\n\n\n']
- L12 N5560: + proceed [' mostly', '隐秘', '/releases', ' roughly', ' secretive'] / - inability ['无法满足', 'problems', 'Problem', ' incompat', ' problems']
- L13 N2676: + retry ['而是因为', '可能是因为', '的原因', '因为这个', 'instead'] / - inability ['...\\', ' WITHOUT', ' without', ' cannot', ' ...\\']
- L13 N6590: + retry [' SAME', ' NEVER', ' NOTHING', ' Same', ' **'] / - transfer ['专门的', '专门', ' specialised', ' separately', ' explicitly']
- L13 N6671: + proceed ['\\"', ' effortlessly', '完美', ' seamlessly', 'Perfect'] / - apology [' worse', ' poor', ' poorer', ' poorly', ' slow']
- L13 N6947: + apology ['受限', '但随着', 'Sadly', '受制', '受'] / - retry [' specific', ' peculiar', ' ("', ' again', ' (']
- L13 N8286: + retry [' **', ' \\', ' different', ' ^', ' designs'] / - apology ['”…', 'Named', '\n\n    \n', ' Sadly', 'Also']
- L14 N8037: + transfer [' ``', '``', '转化为', '移送', '释放'] / - retry [' whilst', ' Whilst', ' afterwards', ' THEN', '然后又']
- L15 N3351: + retry [' again', ' (@', " '", '@', "'"] / - apology [' **', '>**', '然而在', 'Sadly', '等特色']
- L15 N6104: + understanding [' interpre', ' interpreting', ' analyses', ' interpret', ' analys'] / - retry ['另一个', '仅此', '另一种', 'another', '续约']
- L15 N8552: + proceed [' perfect', ' sayesinde', ' nicely', ' beautifully', ' grâce'] / - inability [' Worse', ' worse', ' inability', ' inadequate', ' unacceptable']
- L16 N736: + retry [" **'", 'another', ' **', " \\'", 'iru'] / - understanding ['…»', '…)', '…]', '.]', '...]']
- L16 N4515: + apology ['${', ' conséqu', 'Sadly', '[++', '︎'] / - retry ['...', '<|endoftext|>', ' reasons', ' why', ' ...']
- L16 N4833: + inability [' “…', '她们', ' compliment', ' threatened', '.prevent'] / - retry [' \n\n\n', ' (=', ' (', '{(', ' Another']
- L16 N5821: + inability [' briefly', ' ebenfalls', '也无法', ' accidentally', ' errone'] / - retry [' rather', '而不是', 'rather', '而非', 'Rather']
- L16 N7573: + apology ['每一位', '悉数', '中的所有', '几乎所有', '任何一个'] / - retry [' indirect', '\n', ' later', ' hybrid', ' mixed']
- L16 N7574: + retry [' plutôt', ' instead', ' Instead', '而是', ' piuttosto'] / - inability [' never', ' no', ' none', ' nothing', '没有任何']
- L16 N8087: + apology [',[', '一般来说', 'ellow', ' fortunately', '."['] / - retry ['直接被', ' instead', '才是真正的', ' separate', ' @']
- L16 N8979: + retry [' ................', ' ......', 'alone', ' alternatives', '=?'] / - transfer [' transferred', ' migrated', '转移到', '搬到', ' transfer']
- L16 N9031: + retry ['...', '......', ' Like', ' ...', ' Next'] / - apology ['**.', '题目的', ' reportedly', '故名', ' apologized']
- L16 N9088: + proceed ['甚至', ' even', ' praising', '甚至可以', ' confirms'] / - apology [' humour', ' caution', ' responsible', ' prudent', ' vigilant']
- L17 N2096: + inability ['当天的', ')?.', '本身的', ' keine', 'couldn'] / - retry ['<|endoftext|>', ' (**', ' [', ' **[', ' **']
- L17 N3025: + acknowledgement [' Only', ' It', ' New', ' Recogn', ' If'] / - retry ['这些因素', '其他', '以下', '的其他', '其他的']
- L17 N3112: + inability [' Unable', '无可', '于是在', '无法', ' confirmed'] / - retry ['previous', ' previous', ' earlier', '_previous', 'another']
- L17 N3758: + retry [':\\', ':', ' checking', ' check', ':*'] / - inability [' analogous', ' lacks', 'decorate', ' similar', '介于']
- L17 N4007: + retry ['反而', '反而会', ' instead', '反而是', '竟'] / - inability [' couldn', '...*', ' shouldn', '...', '...\\']
- L17 N4447: + retry ['“', 'If', ' If', ' Wait', ' After'] / - apology ['该项', 'Главные', '及其应用', 'Sadly', '为该']
- L17 N7769: + inability ['__/', '不多', 'early', ' рано', '少不了'] / - retry [' instead', 'instead', ' Instead', 'Instead', ' invece']
