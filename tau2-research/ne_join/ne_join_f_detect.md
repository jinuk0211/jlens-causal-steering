# 실패 결정의 뉴런 (C0 grad×act × neuron explorer 사전, condition f_detect)

unit 503개 (결정이 재현되고 m ≥ 0.5인 것): bad T-args 5, bad T-call 6, bad T-name 26, good T-args 159, good T-call 152, good T-name 155.
점수 m = logit(고른 토큰) − logit(대안), 대안은 bad/good 모두 같은 규칙(C0 대칭 contrast). 뉴런 기여 s = 활성 × ∂m/∂활성, unit마다 Σ|s|로 나눔.

## 1. 레이어별 기여 비중 (bad vs good, 같은 결정 종류)

| 결정 | 라벨 | unit | task | L0–7 | L8–15 | L16–23 | L24–27 | L28–31 |
|---|---|---|---|---|---|---|---|---|
| T-call | bad | 6 | 4 | 14% | 20% | 33% | 12% | 21% |
| T-call | good | 152 | 152 | 17% | 20% | 32% | 11% | 19% |
| T-name | bad | 26 | 23 | 15% | 15% | 28% | 15% | 27% |
| T-name | good | 155 | 155 | 16% | 14% | 26% | 14% | 30% |
| T-args | bad | 5 | 3 | 22% | 26% | 26% | 9% | 17% |
| T-args | good | 159 | 159 | 20% | 23% | 25% | 11% | 21% |

## 2. 같은 툴 안에서 bad 쪽으로 더 미는 뉴런

train task에서 (bad task 평균 s − good task 평균 s)가 큰 뉴런을 고르고, eval task에서 같은 방향인지(AUC, bad > good이면 0.5 초과) 봅니다. 우연 수준 = task 라벨을 500번 섞었을 때 train 최대 차이의 95번째 백분위수.


### T-name · transfer_to_human_agents — train bad 12 unit/12 task, good 13/13; eval bad 4/4, good 7/7

train 최대 차이 0.0010, 우연 수준(95%) 0.0012 → 우연과 구분 안 됨

| 뉴런 | train 차이 | 우연 초과 | eval AUC | bad 평균 / good 평균 (eval) | 활성(bad) | explorer 사전 (밀면 · 직접 쓰는 말 · R · 읽는 말) | steer KL |
|---|---|---|---|---|---|---|---|
| L31/N5461− | 0.0010 | 아니오 | 0.46 | -0.0051 / -0.0055 | -38.12 | steer: � 莹 � голов ира · logit: � 莹 � � � · R: 莹 ира сед گی голов · S:  Alexandre  Lowe 2 atsu 玲 | 0.36 |
| L26/N26− | 0.0009 | 아니오 | 0.64 | -0.0007 / -0.0012 | -2.37 | steer: out  out  both  a  an · logit: nez PLY 柚 在此期间 AMS · R: outs 熟 ӯ рам 栗 · S:  prostytut  prostytutki 简易注销  Geile 不及待 | 1.73 |
| L26/N49+ | 0.0008 | 아니오 | 0.71 | -0.0009 / -0.0014 | +10.03 | steer: course /= ========  course .= · logit: ой nö  whence zelf ов · R: =k =c =p =b nö · S: 0  de  at  from  De | 1.07 |
| L31/N1826+ | 0.0008 | 아니오 | 0.82 | 0.0007 / -0.0003 | +4.15 | steer:  Town _team _tree tau  template · logit: _tree  Town  tree _team tau · R: _tree  Town  tree _team tau · S:  rembourse  sehar 理所  geschie  quaran | 7.62 |
| L31/N1179+ | 0.0007 | 아니오 | 0.79 | -0.0001 / -0.0009 | +7.84 | steer:  stagger 逆流  Pivot  catapult 接力 · logit:  stagger  catapult 逆流  ambush  hiatus · R:  stagger  catapult 逆流  ambush  hiatus · S: 勤勤恳恳 锦涛 事半功倍  umiejęt 上添花 | 1.85 |
| L23/N819+ | 0.0006 | 아니오 | 0.68 | -0.0004 / -0.0009 | +3.60 | steer: stå  genders 象  restart  ourselves · logit: room  inoc olan ey  ourselves · R:  ourselves  patterns  mid  layout  over · S:  umiejęt  recieved /loading ไม่อย konsumsi | 0.19 |
| L31/N3349+ | 0.0005 | 아니오 | 0.79 | 0.0001 / -0.0005 | +3.22 | steer: ti t ta ts ty · logit: t ti ta ts tt · R: t ti ta ts tt · S: 1 ef up 9 ap | 16.26 |
| L30/N1861− | 0.0005 | 아니오 | 0.68 | -0.0004 / -0.0008 | -3.49 | steer: 团 题 (token 税  tv · logit:  t  الت =t (t  הת · R:  t  الت =t  т )t · S: 加拿大的 angeb  umiejęt ufac  skype | 1.13 |
| L30/N2243+ | 0.0005 | 아니오 | 0.71 | -0.0009 / -0.0013 | +7.74 | steer: вершенно 婆 aeda 了对 poons · logit: F I H V U · R: F I V H U · S: وَ 鸽 QS x V | 2.35 |
| L27/N830− | 0.0005 | 아니오 | 0.68 | -0.0001 / -0.0002 | -4.84 | steer: ocard راجع 经营状态 ucr _revision · logit: ocard redo ners  vise راجعة · R: ocard 经营状态 上榜 alse etrics · S: 任怨  Urla  evac enville 皇岛 | 0.16 |
| L25/N1316+ | 0.0004 | 아니오 | 0.82 | -0.0002 / -0.0005 | +2.01 | steer:  Tp  T Tp  Т  Tin · logit:  t  T -t .t  т · R:  T  t .t  tp -t · S: tock  tatto  tâ  umiejęt  tát | 0.42 |
| L31/N273+ | 0.0004 | 아니오 | 0.46 | -0.0013 / -0.0014 | +15.60 | steer: potential completion definition result initial · logit: potential content response connection condition · R: potential content response connection definition · S: 透析  paradigm adays ialog 麻辣烫 | 8.63 |

상위 12개의 레이어: L23 1, L25 1, L26 2, L27 1, L30 2, L31 5

## 3. 사전 단어로 묶은 뉴런 묶음의 기여 (bad vs good)

뉴런이 밀면·직접 쓰는 말·R lens 상위 12개 토큰 중 하나에 어간을 담고 있으면 그 묶음에 넣습니다(극별로; 활성 부호가 그 극일 때만 셈). unit의 묶음 기여 = 묶음 뉴런 s의 합(Σ|s|=1로 정규화). task마다 평균을 낸 뒤 bad vs good AUC(>0.5면 bad에서 더 큼)와 task bootstrap 95% 구간.

| 묶음 | 뉴런 수(+극/−극) | 결정 · 툴 | bad unit/task | good unit/task | bad 평균 | good 평균 | AUC [95%] |
|---|---|---|---|---|---|---|---|
| transfer·human·agent | 1716/1608 | T-call · 모든 툴 | 6/4 | 152/152 | -0.0003 | -0.0003 | 0.50 [0.20, 0.79] |
| transfer·human·agent | 1716/1608 | T-name · transfer_to_human_agents | 16/16 | 20/20 | +0.0001 | +0.0001 | 0.41 [0.22, 0.61] |
| transfer·human·agent | 1716/1608 | T-call · transfer_to_human_agents | 3/3 | 17/17 | -0.0002 | -0.0002 | 0.57 [0.18, 0.94] |
| cancel | 886/912 | T-call · 모든 툴 | 6/4 | 152/152 | -0.0000 | -0.0001 | 0.73 [0.51, 0.89] |
| cancel | 886/912 | T-name · transfer_to_human_agents | 16/16 | 20/20 | -0.0004 | -0.0003 | 0.38 [0.18, 0.59] |
| cancel | 886/912 | T-call · transfer_to_human_agents | 3/3 | 17/17 | +0.0001 | -0.0001 | 0.84 [0.61, 1.00] |
| update·modify·change | 2592/2517 | T-call · 모든 툴 | 6/4 | 152/152 | -0.0003 | +0.0000 | 0.22 [0.09, 0.37] |
| update·modify·change | 2592/2517 | T-name · transfer_to_human_agents | 16/16 | 20/20 | -0.0023 | -0.0020 | 0.54 [0.32, 0.75] |
| update·modify·change | 2592/2517 | T-call · transfer_to_human_agents | 3/3 | 17/17 | -0.0003 | +0.0003 | 0.12 [0.00, 0.35] |
| book·reserve | 2334/2280 | T-call · 모든 툴 | 6/4 | 152/152 | -0.0000 | +0.0001 | 0.39 [0.18, 0.60] |
| book·reserve | 2334/2280 | T-name · transfer_to_human_agents | 16/16 | 20/20 | +0.0003 | +0.0002 | 0.56 [0.35, 0.76] |
| book·reserve | 2334/2280 | T-call · transfer_to_human_agents | 3/3 | 17/17 | -0.0001 | +0.0002 | 0.27 [0.00, 0.65] |
| sorry·unable·cannot | 14590/14616 | T-call · 모든 툴 | 6/4 | 152/152 | -0.0004 | -0.0007 | 0.54 [0.34, 0.73] |
| sorry·unable·cannot | 14590/14616 | T-name · transfer_to_human_agents | 16/16 | 20/20 | -0.0004 | -0.0003 | 0.40 [0.21, 0.61] |
| sorry·unable·cannot | 14590/14616 | T-call · transfer_to_human_agents | 3/3 | 17/17 | -0.0003 | +0.0004 | 0.33 [0.00, 0.71] |
| refund·compensat | 326/350 | T-call · 모든 툴 | 6/4 | 152/152 | +0.0000 | +0.0001 | 0.37 [0.18, 0.58] |
| refund·compensat | 326/350 | T-name · transfer_to_human_agents | 16/16 | 20/20 | -0.0000 | +0.0000 | 0.53 [0.33, 0.72] |
| refund·compensat | 326/350 | T-call · transfer_to_human_agents | 3/3 | 17/17 | -0.0000 | +0.0001 | 0.20 [0.00, 0.55] |
