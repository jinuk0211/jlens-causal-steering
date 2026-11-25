# 실패 결정의 뉴런 (C0 grad×act × neuron explorer 사전, all conditions)

unit 834개 (결정이 재현되고 m ≥ 0.5인 것): bad T-args 59, bad T-call 38, bad T-name 56, good T-args 239, good T-call 219, good T-name 223.
점수 m = logit(고른 토큰) − logit(대안), 대안은 bad/good 모두 같은 규칙(C0 대칭 contrast). 뉴런 기여 s = 활성 × ∂m/∂활성, unit마다 Σ|s|로 나눔.

## 1. 레이어별 기여 비중 (bad vs good, 같은 결정 종류)

| 결정 | 라벨 | unit | task | L0–7 | L8–15 | L16–23 | L24–27 | L28–31 |
|---|---|---|---|---|---|---|---|---|
| T-call | bad | 38 | 10 | 13% | 21% | 34% | 12% | 21% |
| T-call | good | 219 | 163 | 17% | 20% | 32% | 11% | 19% |
| T-name | bad | 56 | 27 | 14% | 15% | 28% | 15% | 28% |
| T-name | good | 223 | 166 | 16% | 14% | 26% | 14% | 30% |
| T-args | bad | 59 | 13 | 15% | 19% | 28% | 13% | 26% |
| T-args | good | 239 | 170 | 20% | 22% | 25% | 11% | 21% |

## 2. 같은 툴 안에서 bad 쪽으로 더 미는 뉴런

train task에서 (bad task 평균 s − good task 평균 s)가 큰 뉴런을 고르고, eval task에서 같은 방향인지(AUC, bad > good이면 0.5 초과) 봅니다. 우연 수준 = task 라벨을 500번 섞었을 때 train 최대 차이의 95번째 백분위수.


### T-call · 모든 툴 — train bad 9 unit/3 task, good 111/85; eval bad 29/7, good 108/78

train 최대 차이 0.0008, 우연 수준(95%) 0.0011 → 우연과 구분 안 됨

| 뉴런 | train 차이 | 우연 초과 | eval AUC | bad 평균 / good 평균 (eval) | 활성(bad) | explorer 사전 (밀면 · 직접 쓰는 말 · R · 읽는 말) | steer KL |
|---|---|---|---|---|---|---|---|
| L28/N277+ | 0.0008 | 아니오 | 0.52 | 0.0000 / 0.0000 | +2.18 | steer: Acts 九九 ucar  Acts  Akt · logit: .lu lu 就连 ual ā · R: 九九 lico áticamente 巴克 вален · S:  actually  really 其实是 真正 实际上 | 0.23 |
| L31/N2382− | 0.0006 | 아니오 | 0.67 | -0.0003 / -0.0008 | -1.06 | steer:  I I .I ,I >I · logit:  I I .I ,I >I · R:  I I .I ,I >I · S:  everytime  succesfully  anyways ไม่อย  skype | 7.17 |
| L22/N3652− | 0.0004 | 아니오 | 0.69 | -0.0001 / -0.0004 | -0.62 | steer:  will will  Will  sẽ Will · logit:  will  Will will Will  akan · R:  will will  Will Will  akan · S: regon 淇淋  chec  Affid  gak | 1.13 |
| L31/N4074− | 0.0003 | 아니오 | 0.55 | 0.0004 / 0.0004 | -3.29 | steer:  *«  *"  `'  *„  ¦[ · logit:  *"  *«  *„  `'  *“ · R: <tool_call> </tool_response> %n <¦fim_middle¦> ًّا · S: 加拿大的  tadi  helicopt 格里拉 埔寨 | 9.74 |
| L31/N3982− | 0.0003 | 아니오 | 0.63 | 0.0001 / 0.0000 | -1.13 | steer: 一想 usada apsed 眼看 fter · logit: ለ fter 一想 čk 而言 · R: ለ fter čk 一想 而言 · S:  But  And But And  Kids | 1.63 |
| L29/N488− | 0.0003 | 아니오 | 0.70 | -0.0003 / -0.0006 | -1.28 | steer:  i )i -i ,i .i · logit:  I I _I ,I .I · R:  I I ,I .I _I · S:  everytime ufac  tadi  Needless uely | 4.31 |
| L31/N844− | 0.0003 | 아니오 | 0.62 | 0.0007 / 0.0006 | -6.44 | steer:  β  α  γ β α · logit: α β  β  α γ · R: α β  β  α  γ · S:  netizen 埔寨 勤勤恳恳 锦涛  Urla | 13.41 |
| L26/N194+ | 0.0003 | 아니오 | 0.67 | -0.0002 / -0.0004 | +1.14 | steer: “I 我看 "I 'I 我認為 · logit:  I  ich  myself  tôi  saya · R:  I I  ich  myself  tôi · S: 加拿大的  umiejęt  netizen  succesfully  helicopt | 1.71 |
| L31/N144− | 0.0003 | 아니오 | 0.72 | 0.0003 / 0.0001 | -6.49 | steer: смотрите 俱乐部  میتوان  میکنند  میتوانند · logit: </think>  میتوان смотрите 俱乐部  میدهد · R: </think>  میتوان смотрите 俱乐部  میدهد · S:  umiejęt ไม่อย 加拿大的 各种各样 อย่างไม่ถูกต้อง | 0.56 |
| L29/N3720+ | 0.0002 | 아니오 | 0.36 | 0.0000 / 0.0000 | +0.78 | steer:  b  б b  ب _b · logit: -b  b  б _b .b · R: -b  b b _b  б · S:  eignen  equipments  eyl 好人 用意 | 2.40 |
| L22/N6433− | 0.0002 | 아니오 | 0.70 | -0.0001 / -0.0002 | -0.10 | steer: 我将 我们将  I I 我再 · logit: 我们将 我将  we  We We · R: 我们将 我将  we We  We · S: 2 1 8 7 0 | 1.74 |
| L24/N671− | 0.0002 | 아니오 | 0.68 | -0.0001 / -0.0002 | -0.09 | steer: 培优 egra 有效 acula woff · logit:  выигра 当之 j  Till fund · R: 当之 会更加  Till Calibri Net · S:  succesfully 不及待 ไม่อย  recieved  Desta | 0.32 |

상위 12개의 레이어: L22 2, L24 1, L26 1, L28 1, L29 2, L31 5

### T-args · update_reservation_flights — train bad 8 unit/3 task, good 11/5; eval bad 37/2, good 16/3

train 최대 차이 0.0011, 우연 수준(95%) 0.0031 → 우연과 구분 안 됨

| 뉴런 | train 차이 | 우연 초과 | eval AUC | bad 평균 / good 평균 (eval) | 활성(bad) | explorer 사전 (밀면 · 직접 쓰는 말 · R · 읽는 말) | steer KL |
|---|---|---|---|---|---|---|---|
| L30/N117+ | 0.0011 | 아니오 | 0.57 | -0.0008 / -0.0013 | +2.77 | steer:         \n  (  \n  \n · logit:      ,  .        · R: i 1 I a 2 · S:  céré  demu vou iere 健全 | 1.94 |
| L30/N8− | 0.0009 | 아니오 | 0.56 | -0.0011 / -0.0015 | -3.73 | steer: 支 /. -. 版 ． · logit: uya presenta uilt 履  tuyến · R: ijin  Зато  зато presenta  Extre · S: 1 2 0 4 3 | 0.38 |
| L31/N1155− | 0.0008 | 아니오 | 0.51 | -0.0000 / -0.0004 | -0.15 | steer:  H H  h _h h · logit:  H H  h h _h · R:  H H  h h _h · S:  umiejęt 加拿大的 勤勤恳恳 芝加 不应求 | 11.24 |
| L31/N457+ | 0.0007 | 아니오 | 0.68 | -0.0000 / -0.0003 | +0.10 | steer: CHA SEG ADR RU OSC · logit: APT CHA CU HE SHA · R: APT CHA CU SHA HE · S:  EEUU  succesfully  Desta Innen  incontournable | 6.33 |
| L31/N2609− | 0.0006 | 아니오 | 0.77 | -0.0000 / -0.0004 | -0.28 | steer: واده elit .ToArray angkit 臼 · logit: 臼 plash .ToArray 西街 elit · R: 臼 plash .ToArray 西街 elit · S:  H -H 赫  House  Hand | 0.72 |
| L31/N1723− | 0.0006 | 아니오 | 0.48 | -0.0010 / -0.0011 | -0.24 | steer: вершенство ombongan ennes 槻 ญ · logit: вершенство ญ _ าง 槻 · R: вершенство ญ าง 槻 ombongan · S: /respond weer декват 案例 到账 | 0.88 |
| L29/N47+ | 0.0005 | 아니오 | 0.57 | 0.0002 / 0.0000 | +2.23 | steer: antina plant  id  v  Pett · logit: Sh vers Id Sl ant · R: ebed antina plant  Pett ibt · S:  Clarkson เพิ่มด้วย geschäft  สถานที่สำคัญ  อเมริกัน | 0.50 |
| L29/N2− | 0.0005 | 아니오 | 0.36 | -0.0010 / -0.0004 | -8.79 | steer:  a    (  an  and · logit: irr ong ij ONG IRR · R: endl 桥镇 valid  تقريب vider · S: 锦涛  umiejęt 加拿大的  succesfully 勤勤恳恳 | 2.42 |
| L30/N193− | 0.0005 | 아니오 | 0.59 | -0.0015 / -0.0006 | -0.27 | steer: � iru 琛 罹  best · logit: atric iru ambu ญ 车载 · R: iru ambu  autó 浮云 еду · S: 查看更多信息 事半功倍 上添花 任怨 周边二手房 | 0.35 |
| L29/N84+ | 0.0004 | 아니오 | 0.73 | 0.0000 / -0.0000 | +0.66 | steer:  Mighty  (` 绝地 ivs ：** · logit: ورش bund ッサ 当事 くださった · R: :eq …the ッサ …but 舍 · S: 加拿大的 锦涛 不及待  ตามระดับ 乐有家 | 0.18 |
| L31/N730+ | 0.0003 | 아니오 | 0.72 | 0.0002 / 0.0000 | +0.53 | steer: � ship 性地 �  Way · logit: � ship 性地 iver 性的 · R: ship 性地 性的 iver iving · S:  utrecht 弄虚 托育  luder  récem | 1.51 |
| L31/N273+ | 0.0003 | 아니오 | 0.68 | -0.0001 / -0.0012 | +7.65 | steer: potential completion definition result initial · logit: potential content response connection condition · R: potential content response connection definition · S: 透析  paradigm adays ialog 麻辣烫 | 8.63 |

상위 12개의 레이어: L29 3, L30 3, L31 6

### T-name · transfer_to_human_agents — train bad 18 unit/14 task, good 14/13; eval bad 6/5, good 8/7

train 최대 차이 0.0010, 우연 수준(95%) 0.0011 → 우연과 구분 안 됨

| 뉴런 | train 차이 | 우연 초과 | eval AUC | bad 평균 / good 평균 (eval) | 활성(bad) | explorer 사전 (밀면 · 직접 쓰는 말 · R · 읽는 말) | steer KL |
|---|---|---|---|---|---|---|---|
| L31/N5461− | 0.0010 | 아니오 | 0.50 | -0.0052 / -0.0053 | -38.19 | steer: � 莹 � голов ира · logit: � 莹 � � � · R: 莹 ира сед گی голов · S:  Alexandre  Lowe 2 atsu 玲 | 0.36 |
| L26/N26− | 0.0010 | 아니오 | 0.73 | -0.0006 / -0.0011 | -2.37 | steer: out  out  both  a  an · logit: nez PLY 柚 在此期间 AMS · R: outs 熟 ӯ рам 栗 · S:  prostytut  prostytutki 简易注销  Geile 不及待 | 1.73 |
| L26/N49+ | 0.0009 | 아니오 | 0.71 | -0.0008 / -0.0013 | +10.14 | steer: course /= ========  course .= · logit: ой nö  whence zelf ов · R: =k =c =p =b nö · S: 0  de  at  from  De | 1.07 |
| L31/N1826+ | 0.0009 | 아니오 | 0.85 | 0.0009 / -0.0001 | +4.19 | steer:  Town _team _tree tau  template · logit: _tree  Town  tree _team tau · R: _tree  Town  tree _team tau · S:  rembourse  sehar 理所  geschie  quaran | 7.62 |
| L31/N1179+ | 0.0007 | 아니오 | 0.81 | 0.0000 / -0.0007 | +7.90 | steer:  stagger 逆流  Pivot  catapult 接力 · logit:  stagger  catapult 逆流  ambush  hiatus · R:  stagger  catapult 逆流  ambush  hiatus · S: 勤勤恳恳 锦涛 事半功倍  umiejęt 上添花 | 1.85 |
| L31/N3349+ | 0.0006 | 아니오 | 0.75 | 0.0002 / -0.0004 | +3.24 | steer: ti t ta ts ty · logit: t ti ta ts tt · R: t ti ta ts tt · S: 1 ef up 9 ap | 16.26 |
| L30/N1861− | 0.0005 | 아니오 | 0.75 | -0.0003 / -0.0008 | -3.62 | steer: 团 题 (token 税  tv · logit:  t  الت =t (t  הת · R:  t  الت =t  т )t · S: 加拿大的 angeb  umiejęt ufac  skype | 1.13 |
| L23/N819+ | 0.0005 | 아니오 | 0.75 | -0.0002 / -0.0008 | +3.56 | steer: stå  genders 象  restart  ourselves · logit: room  inoc olan ey  ourselves · R:  ourselves  patterns  mid  layout  over · S:  umiejęt  recieved /loading ไม่อย konsumsi | 0.19 |
| L30/N2243+ | 0.0005 | 아니오 | 0.67 | -0.0009 / -0.0011 | +7.71 | steer: вершенно 婆 aeda 了对 poons · logit: F I H V U · R: F I V H U · S: وَ 鸽 QS x V | 2.35 |
| L22/N1631+ | 0.0004 | 아니오 | 0.71 | -0.0004 / -0.0005 | +5.55 | steer: ，   。 易 leading · logit: nya teros  scu 现代人 ovat · R: nya UID 的 UE ETA · S: otope 宜人 ardt 上人 犯人 | 1.09 |
| L18/N1180+ | 0.0004 | 아니오 | 0.67 | -0.0002 / -0.0003 | +2.15 | steer: 从 。 我 您 在 · logit: 性问题 istr 子在 在线阅读 于心 · R: ;a ;q insn ;x 更可 · S: 1 onte öd 深水 发言人 | 3.31 |
| L31/N273+ | 0.0004 | 아니오 | 0.38 | -0.0014 / -0.0014 | +15.54 | steer: potential completion definition result initial · logit: potential content response connection condition · R: potential content response connection definition · S: 透析  paradigm adays ialog 麻辣烫 | 8.63 |

상위 12개의 레이어: L18 1, L22 1, L23 1, L26 2, L30 2, L31 5

## 3. 사전 단어로 묶은 뉴런 묶음의 기여 (bad vs good)

뉴런이 밀면·직접 쓰는 말·R lens 상위 12개 토큰 중 하나에 어간을 담고 있으면 그 묶음에 넣습니다(극별로; 활성 부호가 그 극일 때만 셈). unit의 묶음 기여 = 묶음 뉴런 s의 합(Σ|s|=1로 정규화). task마다 평균을 낸 뒤 bad vs good AUC(>0.5면 bad에서 더 큼)와 task bootstrap 95% 구간.

| 묶음 | 뉴런 수(+극/−극) | 결정 · 툴 | bad unit/task | good unit/task | bad 평균 | good 평균 | AUC [95%] |
|---|---|---|---|---|---|---|---|
| transfer·human·agent | 1716/1608 | T-call · 모든 툴 | 38/10 | 219/163 | -0.0002 | -0.0003 | 0.65 [0.50, 0.79] |
| transfer·human·agent | 1716/1608 | T-args · update_reservation_flights | 45/5 | 27/8 | -0.0001 | -0.0000 | 0.47 [0.15, 0.82] |
| transfer·human·agent | 1716/1608 | T-name · transfer_to_human_agents | 24/19 | 22/20 | -0.0000 | +0.0001 | 0.35 [0.16, 0.54] |
| transfer·human·agent | 1716/1608 | T-call · update_reservation_flights | 11/4 | 26/8 | -0.0000 | -0.0003 | 0.84 [0.44, 1.00] |
| transfer·human·agent | 1716/1608 | T-name · update_reservation_flights | 7/4 | 27/8 | +0.0002 | -0.0003 | 0.72 [0.44, 1.00] |
| transfer·human·agent | 1716/1608 | T-call · transfer_to_human_agents | 10/6 | 19/17 | -0.0002 | -0.0002 | 0.56 [0.30, 0.84] |
| transfer·human·agent | 1716/1608 | T-call · cancel_reservation | 14/6 | 13/5 | -0.0003 | -0.0003 | 0.60 [0.17, 0.90] |
| transfer·human·agent | 1716/1608 | T-args · book_reservation | 5/3 | 11/6 | +0.0004 | +0.0005 | 0.50 [0.17, 0.89] |
| cancel | 886/912 | T-call · 모든 툴 | 38/10 | 219/163 | -0.0000 | -0.0001 | 0.64 [0.52, 0.75] |
| cancel | 886/912 | T-args · update_reservation_flights | 45/5 | 27/8 | -0.0002 | -0.0000 | 0.20 [0.00, 0.50] |
| cancel | 886/912 | T-name · transfer_to_human_agents | 24/19 | 22/20 | -0.0005 | -0.0003 | 0.37 [0.20, 0.55] |
| cancel | 886/912 | T-call · update_reservation_flights | 11/4 | 26/8 | -0.0002 | -0.0001 | 0.31 [0.06, 0.66] |
| cancel | 886/912 | T-name · update_reservation_flights | 7/4 | 27/8 | +0.0002 | -0.0001 | 1.00 [1.00, 1.00] |
| cancel | 886/912 | T-call · transfer_to_human_agents | 10/6 | 19/17 | +0.0001 | -0.0000 | 0.76 [0.53, 0.96] |
| cancel | 886/912 | T-call · cancel_reservation | 14/6 | 13/5 | -0.0000 | -0.0000 | 0.57 [0.20, 0.90] |
| cancel | 886/912 | T-args · book_reservation | 5/3 | 11/6 | +0.0001 | -0.0001 | 0.83 [0.50, 1.00] |
| update·modify·change | 2592/2517 | T-call · 모든 툴 | 38/10 | 219/163 | -0.0002 | +0.0000 | 0.27 [0.14, 0.40] |
| update·modify·change | 2592/2517 | T-args · update_reservation_flights | 45/5 | 27/8 | +0.0001 | -0.0003 | 0.75 [0.45, 1.00] |
| update·modify·change | 2592/2517 | T-name · transfer_to_human_agents | 24/19 | 22/20 | -0.0023 | -0.0019 | 0.54 [0.34, 0.75] |
| update·modify·change | 2592/2517 | T-call · update_reservation_flights | 11/4 | 26/8 | -0.0003 | -0.0002 | 0.38 [0.09, 0.81] |
| update·modify·change | 2592/2517 | T-name · update_reservation_flights | 7/4 | 27/8 | +0.0025 | +0.0034 | 0.47 [0.00, 0.94] |
| update·modify·change | 2592/2517 | T-call · transfer_to_human_agents | 10/6 | 19/17 | -0.0001 | +0.0002 | 0.23 [0.05, 0.42] |
| update·modify·change | 2592/2517 | T-call · cancel_reservation | 14/6 | 13/5 | -0.0002 | -0.0001 | 0.50 [0.13, 0.87] |
| update·modify·change | 2592/2517 | T-args · book_reservation | 5/3 | 11/6 | -0.0003 | -0.0000 | 0.22 [0.00, 0.67] |
| book·reserve | 2334/2280 | T-call · 모든 툴 | 38/10 | 219/163 | -0.0001 | +0.0001 | 0.30 [0.17, 0.43] |
| book·reserve | 2334/2280 | T-args · update_reservation_flights | 45/5 | 27/8 | +0.0001 | +0.0001 | 0.42 [0.12, 0.75] |
| book·reserve | 2334/2280 | T-name · transfer_to_human_agents | 24/19 | 22/20 | +0.0003 | +0.0002 | 0.57 [0.38, 0.75] |
| book·reserve | 2334/2280 | T-call · update_reservation_flights | 11/4 | 26/8 | +0.0000 | +0.0002 | 0.25 [0.00, 0.59] |
| book·reserve | 2334/2280 | T-name · update_reservation_flights | 7/4 | 27/8 | -0.0020 | -0.0034 | 0.75 [0.38, 1.00] |
| book·reserve | 2334/2280 | T-call · transfer_to_human_agents | 10/6 | 19/17 | -0.0001 | +0.0002 | 0.25 [0.06, 0.51] |
| book·reserve | 2334/2280 | T-call · cancel_reservation | 14/6 | 13/5 | -0.0002 | -0.0002 | 0.50 [0.13, 0.87] |
| book·reserve | 2334/2280 | T-args · book_reservation | 5/3 | 11/6 | +0.0000 | +0.0002 | 0.33 [0.00, 0.83] |
| sorry·unable·cannot | 14590/14616 | T-call · 모든 툴 | 38/10 | 219/163 | -0.0005 | -0.0007 | 0.51 [0.40, 0.63] |
| sorry·unable·cannot | 14590/14616 | T-args · update_reservation_flights | 45/5 | 27/8 | -0.0004 | +0.0003 | 0.25 [0.00, 0.60] |
| sorry·unable·cannot | 14590/14616 | T-name · transfer_to_human_agents | 24/19 | 22/20 | -0.0003 | -0.0002 | 0.40 [0.21, 0.59] |
| sorry·unable·cannot | 14590/14616 | T-call · update_reservation_flights | 11/4 | 26/8 | -0.0005 | +0.0001 | 0.38 [0.06, 0.75] |
| sorry·unable·cannot | 14590/14616 | T-name · update_reservation_flights | 7/4 | 27/8 | -0.0002 | -0.0011 | 0.84 [0.56, 1.00] |
| sorry·unable·cannot | 14590/14616 | T-call · transfer_to_human_agents | 10/6 | 19/17 | -0.0001 | +0.0005 | 0.31 [0.12, 0.55] |
| sorry·unable·cannot | 14590/14616 | T-call · cancel_reservation | 14/6 | 13/5 | -0.0008 | +0.0001 | 0.23 [0.00, 0.53] |
| sorry·unable·cannot | 14590/14616 | T-args · book_reservation | 5/3 | 11/6 | -0.0006 | +0.0010 | 0.00 [0.00, 0.00] |
| refund·compensat | 326/350 | T-call · 모든 툴 | 38/10 | 219/163 | +0.0000 | +0.0001 | 0.39 [0.25, 0.53] |
| refund·compensat | 326/350 | T-args · update_reservation_flights | 45/5 | 27/8 | +0.0000 | -0.0001 | 0.85 [0.60, 1.00] |
| refund·compensat | 326/350 | T-name · transfer_to_human_agents | 24/19 | 22/20 | +0.0000 | +0.0000 | 0.61 [0.41, 0.81] |
| refund·compensat | 326/350 | T-call · update_reservation_flights | 11/4 | 26/8 | +0.0001 | +0.0000 | 0.69 [0.37, 1.00] |
| refund·compensat | 326/350 | T-name · update_reservation_flights | 7/4 | 27/8 | -0.0001 | -0.0001 | 0.47 [0.06, 0.94] |
| refund·compensat | 326/350 | T-call · transfer_to_human_agents | 10/6 | 19/17 | -0.0000 | +0.0001 | 0.29 [0.07, 0.58] |
| refund·compensat | 326/350 | T-call · cancel_reservation | 14/6 | 13/5 | -0.0000 | -0.0000 | 0.53 [0.17, 0.90] |
| refund·compensat | 326/350 | T-args · book_reservation | 5/3 | 11/6 | +0.0000 | -0.0001 | 0.72 [0.33, 1.00] |
