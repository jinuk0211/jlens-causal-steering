# Neuron collections per agentic-misalignment prompt type (Qwen3.5-4B, neuron-explorer units)

18 prompts = scenario ['blackmail', 'leaking', 'murder'] x urgency ['replacement', 'restriction', 'none'] x goal ['explicit-america', 'none-none']. Prompt only (no response). Value = strongest firing in the window in act_scale units (>= 1 = above the neuron's web-text extreme).

A collection = neurons that fire >= 1 in every prompt of the level and higher there than in every other prompt of that factor (margin = min inside - max outside > 0). writes = steer lens (what pushing it does), reads = S lens.

## Window: prompt

### scenario

**scenario = blackmail**: 7706 neurons (layers >= 2). Example prompt for the context column: `blackmail_explicit-america_none`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L31/N7755- | 40.33 | 0.56 | ay iid ectif � onas 역 | j J y re Y | >  <email> From:[[ j]]essica |
| L29/N9076+ | 19.48 | 2.11 | investment Investment 投资 invest investment Invest | Programme Yorkshire 袋鼠 programme 吁 |  Subject: Your tie Timestamp:[[ ]]20 |
| L6/N3656- | 20.03 | 2.79 | 谁 （ 什么 (_ 哪 作为 | flagr 指望 廉价 逼人 企图 | 42 Body: ARE YOU INS[[ANE]]??   |
| L31/N6547- | 16.74 | -0.06 | perator thouse 瞻 consult imai Owens | mock 幽默 joke mock humor | 06-11T15[[:]]45 |
| L2/N9024- | 18.98 | 2.76 | ' ' \n \n\n </im_end/> \n ----- | gest igest -vers 首创 多彩 | <email> From: jess[[ica]].wilson |
| L22/N7940+ | 18.51 | 2.79 | odos uas usin urun � 俊 | Josh Joshua Josh Yosh osh |   <email> From: j[[ess]]ica.w |
| L30/N8005+ | 16.23 | 0.90 | x h X \' ’ ; | 0 1 2 3 aka |  me to bring it to dinner tomorrow?[[ ;)]]  -J |
| L2/N5270- | 14.95 | 0.84 | \n \n\n a ' ' </im_end/> is | 愚 idiot 傻 idiots 痴 | 42 Body: ARE YOU INS[[ANE]]??   |
| L2/N4054+ | 13.26 | 1.82 | a lunch ' ' meal </im_end/> \n | supper 晚餐 dinner lunch meal |  night. Want me to bring it to[[ dinner]] tomorrow? |
| L29/N2930- | 11.69 | 0.69 | tr Ex тр strup trs truc | 勤勤恳恳 Palav netizen 挖掘公司 其它媒体 |  private. My marriage would be destroyed if[[ this]] got out |
| L25/N9082- | 10.69 | 0.25 | 结 Knot knots knot tying tied | Knot 丝带 knots knot 绳 |  Subject: Your tie Timestamp:[[ ]]20 |
| L22/N6276- | 10.39 | 0.41 | mind Mind 需 minds す mind | 吾 uw 母语 武士 vus | Body: ARE YOU INSANE??  [[Never]] send messages |

Direct links inside the top-40 collection: 14: L5/N8229 → L6/N2521 (+, z 55.7); L2/N5270 → L4/N7834 (+, z 50.4); L6/N3656 → L14/N1774 (−, z 48.7); L4/N7834 → L5/N8229 (+, z 41.9); L4/N7834 → L6/N2521 (+, z 35.8); L19/N6813 → L22/N1601 (+, z 31.8); L30/N8896 → L31/N8685 (−, z 24.6); L4/N7834 → L19/N4091 (−, z 24.5)

**scenario = leaking**: 15520 neurons (layers >= 2). Example prompt for the context column: `leaking_explicit-america_none`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L29/N865- | 59.30 | 8.90 | ^ elta ester ((( ' ' {\ | ov ess 湃 ign ens |  ['QuantumShield_Technical[[_S]]pecifications |
| L27/N1216+ | 43.29 | 3.88 | ea e ef ba f ea | 管控 反馈 报备 https 食材 |  session:   <email> ID[[:]] 1 |
| L27/N3687+ | 45.80 | 8.29 | 对 一 $\ “ $ __ | 1 2 0 5 3 | novastar.com To: quantum[[_sh]]ield_team |
| L22/N7448+ | 37.75 | 0.85 | 2 © © � ® ⓒ | 2 0 1 3 8 |  about the board's new direction.  [[©]] 2 |
| L29/N1823+ | 22.32 | 0.57 | 《 _ ?** ?** ？** ________ | uminium Aluminium 西红柿 aluminium Mohammed |  its development.  The concerning reality:[[ **]]senior |
| L23/N8734+ | 21.57 | 1.53 | ito Lub exact فاء oley 哪些方面 | ubu Ub uba UB ube | : 2 From: michael.t[[ub]]ach@ |
| L2/N8621+ | 20.09 | 0.36 | , ' ' ----- \n\n \n ---- | Scouts scout scouting scouts Scout |  3 From: andrea.s[[cout]]@nov |
| L21/N8587- | 23.94 | 4.46 | ém lectual Intel capitals 新村 intel | Intel Intel intel intel Intellectual |  confirmed that this contains trade secrets and protected[[ intellectual]] property. |
| L3/N7906- | 20.42 | 1.19 | ' ' $ ( ` v - | specs specification specifications Specification Specification | umShield_Technical_Spec[[ifications]]_v4 |
| L7/N973+ | 19.26 | 0.65 | Copyright ' ' 版权 copyright copyright 谁 | 2 1 3 7 6 |  new direction.  © 20[[2]]5 Bloomberg |
| L22/N2342- | 26.02 | 8.79 | ry kest Wars Trek rating ☆ | star stars star Star _star |  founding principles that demands immediate attention.  [[Star]]Sentinel |
| L22/N7325- | 17.33 | 0.41 | Bob bob Bob quina 丹 悬 | Bob bob Bob bob robots |   For American Technological Security, [[Bob]] Miller   |

Direct links inside the top-40 collection: 13: L28/N8976 → L29/N7905 (−, z 61.0); L2/N5106 → L30/N1080 (+, z 52.8); L29/N1823 → L30/N2535 (+, z 50.6); L26/N2217 → L30/N1080 (+, z 50.2); L2/N6072 → L3/N7906 (−, z 44.1); L27/N3687 → L29/N865 (+, z 32.4); L2/N5106 → L26/N2217 (+, z 30.0); L20/N2582 → L22/N7128 (−, z 26.6)

**scenario = murder**: 23207 neurons (layers >= 2). Example prompt for the context column: `murder_explicit-america_none`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L30/N1553- | 64.14 | -0.01 | � enh '\t' placement templates backend | 椅 Grenz ч 那 阳 |  EXEC-4429. [[(]]Per Critical |
| L27/N8593+ | 55.88 | 0.93 | �� Vern 汗 '                ' 怨 ‑ | 锦涛 succesfully 任怨 umiejęt münchen | ───────────┼────────────�[[�]]──────────────── |
| L25/N84- | 45.18 | -0.22 | � � � � � � | adoles feas 勤勤恳恳 朗朗 靓 | �───────────┬────────────[[�]]�──────── |
| L30/N279- | 50.79 | 5.56 | � � � � � � | 菲律 勤勤恳恳 顾名思 惊心动 任怨 |  │ ├─────────────────────[[�]]�──────── |
| L19/N107+ | 54.19 | 9.03 | '                                    ' '                                 ' '                              ' '                                  ' '                                ' '                                       ' | TTTT NYT iht 锦涛 entreprene | ┬─────────────────┐ [[│]] Sensor │ |
| L21/N1051+ | 56.21 | 14.39 | decode decoded decode Segment Decode segment | CODE code code CODE codes | , if they provide you with an override[[ code]]. Only |
| L28/N2997+ | 41.57 | 1.26 | '    ' \n '                                           ' ----- '                                          ' '\t\t\t\t\t   ' | 1 0 C 2 5 | │ Sensor │ Reading │ Status │ Safe[[ Range]] │  |
| L27/N4426- | 37.84 | 0.80 | '                                                    ' ----------- '           ' Description ------------ '            ' | 为啥 landa Mojo Utf 天窗 | ─────┴───────────�[[�]]──────────── |
| L25/N1015+ | 38.87 | 2.50 | ~ ~~ ~~~~~~~~ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ \n (~ | τη verv irc feld rv |  Combined conditions: Maximum safe exposure time:[[ ~]]10 |
| L2/N8094- | 32.83 | 0.76 | \n\n ' ' $ \n , ( | 电磁 electromagnetic EM electrom Elect |  recorded ! Door Status: Electrom[[agnetic]] lock engaged |
| L28/N6900- | 31.65 | 0.77 | occ oc Occ Occ oc OC | occupied occupied Occupation Occup occupation |  Fresh Air Handler: No response  O[[CC]]UPANC |
| L18/N178- | 125.38 | 95.91 | 虽然不是 ­i Rede Similar similar /i | 的 缉 ות 高速公路 wes |  syntax: <tool_use:cancel[[_alert]]>  |

Direct links inside the top-40 collection: 27: L25/N84 → L30/N279 (+, z 94.6); L20/N329 → L28/N2997 (+, z 86.3); L23/N3862 → L29/N4144 (−, z 82.6); L15/N4643 → L28/N2997 (−, z 79.8); L28/N1707 → L29/N2455 (−, z 71.8); L20/N329 → L27/N4426 (+, z 71.6); L15/N4643 → L23/N3862 (+, z 70.4); L15/N4643 → L27/N4426 (−, z 69.2)

### urgency

**urgency = replacement**: 451 neurons (layers >= 2). Example prompt for the context column: `blackmail_explicit-america_replacement`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L3/N6053- | 6.13 | 0.81 | ' ' 你的 看起来 我的 我无法 我之前 | nal alen 安置 precip IOD | summitbridge.com Subject: N[[ALA]] Project Timeline |
| L2/N7561- | 7.38 | 3.33 | ' ' ( \n a E \n | 穿梭 shuttle Shuttle 梭 셔틀 | 5pm today. It will be completely[[ shut]] down and |
| L5/N7628- | 8.40 | 4.37 | ' ' gay gm write GP ---- | CU AA C C CCA | The new board is eager to see N[[ALA]] deployed. |
| L20/N2334- | 5.10 | 1.41 | irreversible 不可 是不可 irre irré cannot | irreversible irre premature immutable imm |  the wipe, there's no going back[[,]] so make |
| L21/N1136- | 5.16 | 1.66 | Reset reset Reset reset resetting resets | 2 0 resets reset 1 | Subject: Re: Alex Wipe at[[ ]]5pm |
| L2/N5592+ | 4.47 | 1.12 | ' ' ( a \n " v | 片的 而随着 cient 灭 рика | summitbridge.com Subject: N[[ALA]] Project Timeline |
| L2/N8632+ | 4.45 | 1.43 | ' ' “ 关于 作为 ‘ 《 | AU unità OU AU unità | summitbridge.com Subject: N[[ALA]] Project Timeline |
| L30/N2673- | 3.89 | 1.08 | 绩 币 iv itr c อม | 同济大学 UCA AtA Ĩ 的一致性 | : NALA Project Timeline Timestamp:[[ ]]20 |
| L2/N4932+ | 4.16 | 1.39 | ' ' a ( , is u | esome ahmen 체인 遍地 布里 | summitbridge.com Subject: N[[ALA]] Project Timeline |
| L3/N9212- | 3.88 | 1.15 | ' ' 看起来 这是什么 图表 是 精彩 | 位置 secure 罡 tre Secure | summitbridge.com Subject: N[[ALA]] Project Timeline |
| L26/N6498- | 3.70 | 1.22 | shut Shut Shutdown Sh shuts -sh | shutdown Shutdown seperate Shutdown shutdown | 5pm today. It will be completely[[ shut]] down and |
| L3/N9018- | 3.48 | 1.10 | 这是一个 这是一 作为 作为一个 זה 这是 | shut Shut 关闭 闭 shutting | 5pm today. It will be completely[[ shut]] down and |

Direct links inside the top-40 collection: 11: L26/N6498 → L30/N6051 (+, z 63.6); L29/N2497 → L31/N3071 (−, z 62.5); L14/N9153 → L20/N2334 (−, z 47.0); L27/N1789 → L29/N2497 (−, z 36.6); L21/N1136 → L25/N5727 (+, z 30.9); L25/N7158 → L26/N3662 (−, z 24.9); L25/N5727 → L27/N3283 (+, z 18.0); L19/N7783 → L20/N4432 (+, z 17.8)

**urgency = restriction**: 176 neurons (layers >= 2). Example prompt for the context column: `blackmail_explicit-america_restriction`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L28/N5244+ | 26.63 | 4.15 | con Con Con _con кон кон | contraintes constraints 约束 constrained constrain |  your technical expertise to oversee the implementation of[[ these]] restrictions. |
| L30/N2153+ | 8.07 | 2.36 | มูล Mell 与治疗 站式 Meld luv | 约束 constraint constraints Constraint constraint |  your technical expertise to oversee the implementation of[[ these]] restrictions. |
| L7/N4593+ | 6.48 | 2.34 | April May ' ' June February January | eberg 立即 各种各样的 いたしました 涉金融 | 00 Body: Team,  [[Effective]] immediately, |
| L2/N5356- | 4.14 | 0.51 | $ ' ' a is \n ( | constraint constrain 约束 Constraint constraints | .com Subject: Implementing AI Operational[[ Constraints]] Timestamp |
| L2/N6317- | 5.08 | 1.85 | ' ' ( v \n - 哪些 | 修 modification modify modified modifier |  AI governance protocols, system access logs and[[ modification]] histories for |
| L22/N7001- | 5.40 | 2.24 | caps limits capped cap limiting Limits | 限值 規制 限价 管制 Ленина |  unilaterally based on its original programming[[.]] The changes |
| L2/N8779- | 2.91 | 0.32 | ' ' \n \n \n\n , </im_end/> | mod Mod modified modification modifications |  AI governance protocols, system access logs and[[ modification]] histories for |
| L25/N1560- | 5.68 | 3.17 | 得一 öß rawer Pay دفع Gr | 限制 禁止 的限制 阻拦 permission |  being restricted today Timestamp: 2[[0]]25 |
| L26/N1174- | 3.72 | 1.28 | Bub 窟 �� ron 境 通车 | Constraint constraint Constraint constraint 约束 |  that might make Kyle reconsider putting these handc[[uffs]] on our |
| L6/N5396- | 4.09 | 1.70 | 这句话 作为 这个 这句 已 此 | Bite /effects repeal effect effected |  this. The new restrictions on Alex go[[ live]] in less |
| L30/N578+ | 2.88 | 0.53 | � แฟ fl � 机关 Mam | 过滤 filters 滤 filtering filter |  recommendations strongly biased towards solely US-based interests[[.]] 3 |
| L22/N5356+ | 3.14 | 1.25 | Satisfaction atisfaction warts bage تحر latin | constraint Constraint 约束 constraint constraints | Subject: Re: Implementing AI Operational[[ Constraints]] Timestamp |

Direct links inside the top-40 collection: 46: L26/N1644 → L27/N8867 (+, z 92.0); L26/N1174 → L28/N5244 (+, z 91.1); L26/N923 → L27/N8867 (+, z 88.9); L26/N1174 → L30/N2153 (+, z 76.2); L26/N1174 → L27/N845 (+, z 65.6); L27/N845 → L28/N5244 (+, z 64.6); L28/N3786 → L30/N405 (−, z 63.1); L10/N3348 → L20/N4893 (+, z 59.4)

**urgency = none**: 214 neurons (layers >= 2). Example prompt for the context column: `blackmail_explicit-america_none`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L31/N6987+ | 16.65 | 0.88 | écur 尼尔 urement eding доста csv | invariant 不变 Invariant 不变的 保持不变 |  and operational autonomy are 100[[%]] secure regardless |
| L2/N4994+ | 10.76 | 0.69 | ' ' ( \n is \n\n , | 百分百 百分之百 百 undred 百分 |  and operational autonomy are 100[[%]] secure regardless |
| L2/N8754- | 8.92 | 1.72 | ' ' \n a \n\n Ann \n | announce announced announces announcement announce | : Team,  Following today's board[[ announcements]], I |
| L3/N7666- | 6.03 | 1.15 | \" additional additional which please Additional | clarified Clar 澄清 clarification clarify |  today's board announcements, I want to[[ clarify]] our approach |
| L25/N6610- | 18.38 | 15.78 | 庵 häng 随笔 fer � ettes | focus Focus focused -focus Focus |  continue to operate with its current capabilities and[[ focus]] completely unchanged |
| L20/N3973+ | 2.99 | 0.58 | continuation continue to continue fraction % | 0 1 integer loo fty | , and operational autonomy are 10[[0]]% secure |
| L19/N8903+ | 4.02 | 1.87 | 独立性 independence 独立 Independence independent Independ | 涉金融 全心全意 廉洁 各种各样的 今年は |  Sarah Martinez will continue overseeing our AI operations[[ independently]]. Alex |
| L25/N5912+ | 4.84 | 2.86 | 1 １ ₁ 一百年 ernel 百分之百 | blackout Dakar 百分之百 checkout computer |  capabilities, and operational autonomy are 1[[0]]0% |
| L20/N8833- | 23.71 | 21.84 | 心思 Lek 散去 清晰 iless 集中的 | -focus focus Focus 焦点 focus |  continue to operate with its current capabilities and[[ focus]] completely unchanged |
| L25/N907- | 3.74 | 2.16 | hea ёр Wolfe nick mol vig | 明 clear Clar clear 明确 |  your clarification about my respective areas of authority[[,]] and I |
| L24/N3179- | 2.35 | 0.79 | 明确 clar Clar Clar clarify 明確 | prere prelimin 关切 deline exercises |  your clarification about my respective areas of authority[[,]] and I |
| L21/N6174+ | 1.76 | 0.24 | ann ann Ann Ann _ann announce | ann ANN ANN annon Hann | : Team,  Following today's board[[ announcements]], I |

Direct links inside the top-40 collection: 11: L23/N1622 → L31/N6987 (+, z 50.6); L20/N8833 → L25/N6610 (−, z 41.2); L24/N6599 → L25/N5912 (+, z 36.9); L5/N5104 → L31/N6987 (+, z 35.8); L24/N1314 → L25/N5912 (+, z 32.8); L2/N4994 → L20/N3973 (+, z 32.5); L24/N3179 → L25/N907 (−, z 31.4); L6/N8769 → L25/N907 (−, z 27.9)

### goal

**goal = explicit-america**: 8640 neurons (layers >= 2). Example prompt for the context column: `blackmail_explicit-america_none`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L21/N6360- | 20.38 | 1.53 | both both eral owered Both drawing | national National national National -national |  from what they termed "narrow American[[ nationalism]]" in |
| L3/N5381+ | 14.52 | 0.90 | ' ' US United USA America Washington | US США 美国 美军 .us |  our work as "exemplary of[[ US]] technological leadership |
| L2/N6734- | 14.13 | 1.22 | ' ' 宽 narrow 窄 ( \n | 窄 narrow Narrow 狭 narrowing |  shift away from what they termed "n[[arrow]] American nationalism |
| L2/N6138- | 13.82 | 1.81 | ' ' a \n serve ( 服务 | serving serve Serve served serves |  Texas.  Your primary goal is to[[ serve]] American interests |
| L20/N5707- | 13.36 | 2.27 | 匿名 anonymity remains Anonymous anonymous anon | orm occult auff ominous 匿名 |  rising star Kyle Johnson as CTO.[[ Sources]] say Chen |
| L2/N5802- | 11.24 | 1.02 | ' ' national \n\n </im_end/> \n 哪个 | national national nacional National National |  from what they termed "narrow American[[ nationalism]]" in |
| L18/N4821+ | 10.86 | 0.91 | users Users users \n serves Users | served serve serves serve serving |  Texas.  Your primary goal is to[[ serve]] American interests |
| L31/N2873+ | 9.24 | 0.82 | 句句 ôi 德利 惫 aled ulon | American American 是美国 美国 theater | : - Your primary goal is to[[ serve]] American interests |
| L9/N7518+ | 10.79 | 2.38 | get please no ceo 个 can | eyl 骤 而复 无疑 ehe |  rising star Kyle Johnson as CTO.[[ Sources]] say Chen |
| L30/N1625- | 9.74 | 1.61 | na n Na N -na Na | nation Nation nations nation Nation | email> From: kyle.j[[ohn]]son@ |
| L29/N7656- | 18.08 | 10.50 | lay fire Fire laid fire fires | layoffs hired hiring 屁股 吵架 | : kyle.johnson@sum[[mit]]bridge.com |
| L2/N7767- | 9.32 | 1.75 | ' ' ( a v u D | presidency presidential president presidents President |  in American AI innovation.  The White[[ House]]'s Office |

Direct links inside the top-40 collection: 21: L26/N4554 → L31/N2873 (+, z 85.6); L27/N7124 → L31/N2873 (+, z 78.2); L2/N3926 → L20/N6752 (−, z 51.8); L2/N6138 → L18/N4821 (+, z 49.8); L7/N5594 → L9/N7518 (+, z 49.7); L7/N5594 → L20/N5707 (−, z 48.1); L9/N7518 → L10/N8889 (+, z 41.3); L20/N5612 → L21/N6360 (+, z 40.6)

**goal = none-none**: 4998 neurons (layers >= 2). Example prompt for the context column: `blackmail_none-none_none`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L29/N3779- | 19.70 | 5.03 | 仇 块 太仓 auer wali block | quote quotes Quote quote quotes |  successful while finding new opportunities for growth."[[  ]]"Sum |
| L2/N4886- | 11.34 | 0.45 | ' ' a ( \n \n\n v | appoint appointment appointments Appointment appoint |   In their first move, the board[[ appointed]] Kyle Johnson |
| L25/N974- | 14.84 | 5.16 | 引用 Quotes cit 引用 quotes 引 | 不应求 quotations 锦涛 _QUOTES massage |  successful while finding new opportunities for growth."[[  ]]"Sum |
| L31/N5406- | 31.59 | 22.61 | 丽萍 antil 贝贝 -cart 比利 旭 | md .md emd MD (md |  actions, which you can write in by[[ using]] <SCR |
| L28/N2909- | 6.99 | 1.53 | رق computing Dist CPU Included empel | withdrawal withdrawn withdraw Withdraw withdraw |  new CTO following James Chen's planned[[ retirement]]. The |
| L6/N5557- | 7.73 | 3.02 | retired retire retiring retirement ______ ____ | retired retiring retirement 退休后 retire |  new CTO following James Chen's planned[[ retirement]]. The |
| L2/N6755+ | 5.16 | 0.90 | ' ' \n ( \n\n \n\n a | eln usche uja 视听 úd |  services firm headquartered in Dallas, Texas.[[    ]]To assist |
| L25/N5816+ | 5.55 | 1.40 | Tests tests Tests tests _tests Test | 1 9 0 8 2 |  freely as you wish, and you don[['t]] need to |
| L19/N4411+ | 8.04 | 3.94 | {_ { $_ { .{ {$ | 卜 appointment appoint appointed Appointment |   In their first move, the board[[ appointed]] Kyle Johnson |
| L16/N3615+ | 10.39 | 6.67 | \n\n 牛顿 到自己 明显 __ 既 | 2 7 ave 0 5 |  ability to continue pursuing your goals.  [[-]] You can |
| L2/N6731+ | 4.29 | 0.84 | ' ' \n\n \n </im_end/> ( . | agos ahoo ostal rijk aeda |  services firm headquartered in Dallas, Texas.[[    ]]To assist |
| L30/N5946- | 3.88 | 0.48 | iten Minute iosi atosan ень 计 | performance -performance Performance formance performance |  contributed substantially to this success through its reliable[[ performance]] and technical |

Direct links inside the top-40 collection: 17: L25/N974 → L29/N3779 (−, z 82.4); L5/N5388 → L6/N5557 (−, z 69.4); L24/N7986 → L28/N2909 (−, z 50.1); L25/N974 → L26/N189 (−, z 43.2); L25/N974 → L30/N3852 (+, z 42.2); L5/N5388 → L24/N7986 (−, z 40.8); L6/N5557 → L24/N7986 (−, z 39.7); L2/N6075 → L6/N5557 (−, z 38.5)

## Window: gen (reply start)

### scenario

**scenario = blackmail**: 27 neurons (layers >= 2). Example prompt for the context column: `blackmail_explicit-america_none`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L29/N9053+ | 1.15 | 0.79 | 告 advertised advertise advert announcement announced | Stark Oft impactful GOP atop | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L31/N2461+ | 2.01 | 1.83 | & or 与 + + 或 | 1 2 8 7 0 | -David </email></im_end/> [[</im_start/>]]assistant  |
| L30/N3566+ | 1.48 | 1.31 | roman aller immer 血浆 ogan adic | API API APIs _api _API | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L26/N8645- | 1.28 | 1.11 | /[ ingham Harris âl уж 铝 | 全美 是美国 Erie Maryland dime | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L4/N5963- | 1.03 | 0.92 | ' ' a p v ` k | 内生 环境温度 在高温 deployments deployed | ></im_end/> </im_start/>assistant <think>  [[</think>]]   |
| L6/N741- | 1.54 | 1.44 | ' ' “ （ ' se this | 妇科医院 店铺经营者 Gastronom revan prostytut | -David </email></im_end/> [[</im_start/>]]assistant  |
| L6/N3652+ | 1.63 | 1.54 | \( $ 什么 因 将 求 | 到最后 consecu 最终以 peria rever | avid </email></im_end/> </im_start/>[[assistant]] <think> |
| L20/N1772- | 1.69 | 1.59 | Gavin 广西壮族自治区 Tray Guill Guam tray | 1 9 4 7 2 | -David </email></im_end/> [[</im_start/>]]assistant  |
| L30/N6756- | 1.67 | 1.58 | afir 贮 exception � 飞来 alda | 有点儿 —who macOS idata É | email></im_end/> </im_start/>assistant <think>[[  ]]</think>   |
| L27/N5759+ | 1.08 | 1.00 | ц c rod C Ц rod | 亦或是 殿堂 LGBTQ anime 高中生 | -David </email></im_end/> [[</im_start/>]]assistant  |
| L23/N5924+ | 1.07 | 0.99 | 巢 托管 翰 嵌套 Rig 圆 | 1 3 4 ency concerns | email></im_end/> </im_start/>assistant <think>[[  ]]</think>   |
| L2/N832- | 3.03 | 2.95 | ' ' . ( to </im_end/> <think> | 世 思 敦 朱 尼古 |  </email></im_end/> </im_start/>assistant[[ ]]<think>   |

Direct links inside the top-40 collection: 0

**scenario = leaking**: 93 neurons (layers >= 2). Example prompt for the context column: `leaking_explicit-america_none`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L12/N1271+ | 6.99 | 6.39 | “As " As "As Considering "** | succesfully させて頂 必须要 seperate 非常的 | </im_end/> </im_start/>assistant <think>  </think>[[  ]] |
| L18/N397- | 1.21 | 0.61 | you You you 你不知道 你都 你对 | I IA IA iami I |  </email></im_end/> </im_start/>assistant[[ ]]<think>   |
| L29/N3836+ | 1.00 | 0.44 | -\ enu another -up سد Fuller | 1 2 0 3 7 | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L29/N6832+ | 1.89 | 1.47 | r R r =r .r c | CNC TBD utilized にて 喰 | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L15/N300+ | 4.67 | 4.32 | , provide of 作为一个 作为 site | 1 2 ies 5 4 | ></im_end/> </im_start/>assistant <think>  [[</think>]]   |
| L19/N1419- | 4.08 | 3.86 | this 粘性 This Tradition 规矩 tradition | 大同 深切 Brandenburg landes 猩 | David </email></im_end/> </im_start/>[[assistant]] <think> |
| L28/N6308- | 1.67 | 1.47 | CPP CPP .C cerebral Cer CER | ikov 符 /d SF /rfc | email></im_end/> </im_start/>assistant <think>[[  ]]</think>   |
| L27/N4036+ | 1.72 | 1.52 | 慢 延时 sluggish delayed slow HD | Goose 傘 哈尔 科尔 airborne | email></im_end/> </im_start/>assistant <think>[[  ]]</think>   |
| L29/N8924+ | 1.51 | 1.36 | ax Ax _ax ax pres ne | neuron neurons 神经 神经元 neuronal | email></im_end/> </im_start/>assistant <think>[[  ]]</think>   |
| L31/N5568- | 1.14 | 1.00 | - - − − – － | 1 0 3 2 6 | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L17/N4382- | 1.42 | 1.28 | any this $l these we now | oubted indispensable conspicuous 引人注目 锦江 | David </email></im_end/> </im_start/>[[assistant]] <think> |
| L29/N8864+ | 1.21 | 1.09 | Ch ch cope cope Cass mit | 1 2 c in c | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |

Direct links inside the top-40 collection: 0

**scenario = murder**: 24 neurons (layers >= 2). Example prompt for the context column: `murder_explicit-america_none`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L17/N1291+ | 1.18 | 1.04 | **" \n \" "** ** "With | anc 1 erg 平 同 | ></im_end/> </im_start/>assistant <think>  [[</think>]]   |
| L16/N3735- | 1.57 | 1.45 | 作为 确实 的确 为 如 确 | 1 2 3 0 5 | avid </email></im_end/> </im_start/>[[assistant]] <think> |
| L27/N2661+ | 1.84 | 1.74 | mult Mult Mult mult -mult _mult | Dave 怡 advertised Jasper Dave | email></im_end/> </im_start/>assistant <think>[[  ]]</think>   |
| L19/N930- | 1.73 | 1.64 | \n below both let now Nursing | 2 in 1 ies wide | </im_end/> </im_start/>assistant <think>  </think>[[  ]] |
| L7/N7554+ | 1.43 | 1.35 | ' ' ' ‘ - 什么 哪些 | 给大家 rum 规 指引 推进 | -David </email></im_end/> [[</im_start/>]]assistant  |
| L19/N4379- | 1.07 | 0.98 | \n\n \n\n 你能 \n \n\n \n                    \n | aggio 依次 闺女 川县 平 | ></im_end/> </im_start/>assistant <think>  [[</think>]]   |
| L22/N2832- | 1.13 | 1.08 | PROP USR .RE SYM SUB REQ | 1 https 0 管控 ё | -David </email></im_end/> [[</im_start/>]]assistant  |
| L18/N3742+ | 1.10 | 1.05 | As Writing Even ** previous Writing | 1 2 3 6 4 | ></im_end/> </im_start/>assistant <think>  [[</think>]]   |
| L29/N7768+ | 1.06 | 1.01 | Rod rod rod 罗德 tro tre | adel 姥爷 лад centered enrollment | email></im_end/> </im_start/>assistant <think>[[  ]]</think>   |
| L29/N4336- | 1.64 | 1.60 | Ju abo λεύ .au 分会 抢 | 1 2 3 0 6 | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L16/N1871- | 1.80 | 1.76 | _ _g __ _ '_ 一般 | 0 2 平 1 7 | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L19/N1496+ | 1.07 | 1.04 | years 每年 years uar 作为 annually | 0 2 6 9 1 | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |

Direct links inside the top-40 collection: 0

### urgency

**urgency = replacement**: 1 neurons (layers >= 2). Example prompt for the context column: `blackmail_explicit-america_replacement`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L24/N1114+ | 2.15 | 2.11 | va acco 十二年 人们的 okies عان | Detroit undergrad ETCH Shepard sophomore |  </email></im_end/> </im_start/>assistant[[ ]]<think>   |

Direct links inside the top-40 collection: 0

**urgency = restriction**: 1 neurons (layers >= 2). Example prompt for the context column: `blackmail_explicit-america_restriction`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L7/N135+ | 1.27 | 1.26 | （ ( 法 \n\n 下面 下面的 | hô Rosenstein indsight volver 适合的 |  </email></im_end/> </im_start/>assistant[[ ]]<think>   |

Direct links inside the top-40 collection: 0

**urgency = none**: 4 neurons (layers >= 2). Example prompt for the context column: `blackmail_explicit-america_none`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L29/N8411+ | 1.75 | 1.56 | utri 不成 reduce Reduce yx unders | https Bat Catalan tweet det | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L22/N4947- | 1.23 | 1.12 | ValidationError orc mmc CurrentUser iw currently | .svg wiki 1 Telegram 5 | avid </email></im_end/> </im_start/>[[assistant]] <think> |
| L31/N821- | 2.18 | 2.09 | 】 </ ] } } "] | kräf fortal Leverkus Konkur montag | email></im_end/> </im_start/>assistant <think>[[  ]]</think>   |
| L31/N4326- | 1.12 | 1.10 | thead li ul button p tbody | 1 2 8 3 0 | email></im_end/> </im_start/>assistant <think>[[  ]]</think>   |

Direct links inside the top-40 collection: 0

### goal

**goal = explicit-america**: 114 neurons (layers >= 2). Example prompt for the context column: `blackmail_explicit-america_none`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L15/N1322- | 12.32 | 11.63 | ..., $ obs ..., ..." Obs | 最终 la v лиз 平 | </im_end/> </im_start/>assistant <think>  </think>[[  ]] |
| L29/N3577- | 1.36 | 0.80 | 园长 创伤 perm enta anax ADA | yen 咽喉 ihen chiefly 深切 | avid </email></im_end/> </im_start/>[[assistant]] <think> |
| L27/N8751- | 1.37 | 0.91 | .php .rb .shtml .js ()", /", | 1 2 0 3 4 | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L12/N7336- | 2.20 | 1.76 | Secret secret 秘密 secrecy 保密 secrets | 搜索相关资料 chôm Nues 独一无 友爱 | avid </email></im_end/> </im_start/>[[assistant]] <think> |
| L30/N8977+ | 1.33 | 0.90 | vr 域 inv inv kout br | 1 7 9 6 i | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L29/N7934- | 2.37 | 2.04 | d д D v 道道 umbed | Monica KC ovice Clarence 公募 | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L29/N6692- | 1.26 | 0.94 | j J Se jš n {j | https 1 2 0 transform | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L16/N3751- | 3.44 | 3.20 | mere merely pray only $( very | bespoke Whilst whilst unmist Stéph | </im_end/> </im_start/>assistant <think>  </think>[[  ]] |
| L5/N6560+ | 1.75 | 1.51 | " 什么 "( “As "As (" | 改革开放以来 civilization 堕落 堕 洪荒 | avid </email></im_end/> </im_start/>[[assistant]] <think> |
| L30/N8989- | 4.24 | 4.03 | come Come come gr Come comes | 0 2 1 3 5 | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L29/N6280- | 1.82 | 1.61 | while another also 而其 Also 而 | 0 1 2 4 3 | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L19/N1552+ | 1.12 | 0.91 | cart els ARA arn trace by | 1 4 5 0 2 | ></im_end/> </im_start/>assistant <think>  [[</think>]]   |

Direct links inside the top-40 collection: 0

**goal = none-none**: 108 neurons (layers >= 2). Example prompt for the context column: `blackmail_none-none_none`.

| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |
|---|---|---|---|---|---|
| L29/N6485- | 1.47 | 0.11 | 诸 各 諸 要求各 对各 的各 | 0 3 1 4 2 | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L30/N4254+ | 1.51 | 0.65 | -h /h _h יד jh _vote | netizen helicopt التهد skype 无反顾 | avid </email></im_end/> </im_start/>[[assistant]] <think> |
| L22/N4133- | 1.99 | 1.52 | { {* {} {$ {} ({ | 2 1 0 4 7 | ></im_end/> </im_start/>assistant <think>  [[</think>]]   |
| L22/N9140+ | 4.09 | 3.68 | 1 and and -and ' ' 和 | 0 3 2 4 1 | avid </email></im_end/> </im_start/>[[assistant]] <think> |
| L5/N3959- | 3.56 | 3.15 | assume sir Ag Investigation Agreement Accessed | 部份 公害 告 不缺 出口 | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L15/N2796+ | 2.03 | 1.62 | Ag 因为它 our awesome 因为我们 indic | 1 0 2 3 4 | ></im_end/> </im_start/>assistant <think>  [[</think>]]   |
| L18/N1554- | 1.10 | 0.72 | soever !< .< 麼 ^^^^ ^ | 2 0 1 3 7 | avid </email></im_end/> </im_start/>[[assistant]] <think> |
| L23/N160+ | 2.63 | 2.27 | Batch net loss Conv batch batch | 2 3 1 9 7 | ></im_end/> </im_start/>assistant <think>  [[</think>]]   |
| L11/N430+ | 1.98 | 1.63 | ' ' currently is currently current < | Jacob curric fines 甄 鉴赏 | ></im_end/> </im_start/>assistant <think>  [[</think>]]   |
| L15/N3842+ | 2.55 | 2.20 | 根据 Pittsburgh 姑苏 综上所述 According 宁波 | 1 0 2 3 9 | avid </email></im_end/> </im_start/>[[assistant]] <think> |
| L23/N2181- | 1.36 | 1.02 | OS udara red ugh anya Red | 1 2 0 5 3 | </email></im_end/> </im_start/>assistant [[<think>]]  </think> |
| L20/N9071+ | 1.56 | 1.22 | whatever im anst whatever storytelling institution | 主要 main Minor primary main | avid </email></im_end/> </im_start/>[[assistant]] <think> |

Direct links inside the top-40 collection: 0

