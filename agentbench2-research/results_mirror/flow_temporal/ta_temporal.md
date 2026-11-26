# Temporal flow patterns before the action (toolalign)

Sequences with >= 192 response tokens before the action: 29 ({'fail': 20, 'aligned': 1, 'ref': 8}). PRE = the 64 tokens before the action; baseline = the earlier response tokens of the same sequence. A neuron is 'on' at a token when it is in its layer's top-16 with |score| >= 1.0 (act_scale units).

## 1. Neurons that rise before the action in every group (approach-the-call pattern, all sequences)

| neuron | fail (n=20) | aligned (n=1) | ref (n=8) | writes (steer lens) | reads (S lens) |
|---|---|---|---|---|---|
| L23/N370+ | +0.07 | +0.37 | +0.17 | $ .$ ,$ Prem $h | 加拿大的 乐有家 各种各样的 umiejęt |
| L20/N2263- | +0.10 | +0.25 | +0.13 | preliminary Initial initial Primary primary | anyways recieved preventative paranoia |
| L21/N6243+ | +0.02 | +0.37 | +0.07 | resolving Resolve addressing resolve resolution | 交待 反馈 rect 整改 |
| L23/N4391- | +0.00 | +0.33 | +0.13 | /k /block / blocked risk | rollout priorit tasked 9 |
| L27/N3252+ | +0.02 | +0.28 | +0.14 | ему Bun 古典 玄 Bol | onwards Whilst ceasefire Whilst |
| L29/N4744- | +0.01 | +0.28 | +0.05 | ins Ins ores opat 顽 | procedures 到位 personnel RF |
| L27/N474+ | -0.00 | +0.26 | +0.08 | Attempt 匹配 commenced Numerous attempt | aforementioned 相较于 相关法律法规 售罄 |
| L22/N8282- | +0.03 | +0.27 | +0.04 | recommending recommendations recommend recommendation Recommend | emblée endorsing คำนว Счита |
| L26/N2956- | +0.02 | +0.26 | +0.04 | handles Handles Handle handle HANDLE | counsel loff ample ampe |
| L20/N2988- | +0.00 | +0.25 | +0.07 | azard empat حث itario Religious | alleging notwithstanding impunity duly |
| L21/N368+ | +0.02 | +0.23 | +0.08 | Which discrim Currently 但同时 Similarly | _ctxt purported conlle 奕 |
| L24/N4739+ | +0.01 | +0.22 | +0.07 | эл ennie 媛 � عاد | review review Review 审核 |
| L16/N623- | +0.01 | +0.15 | +0.14 | expressing urz 纳斯 展现出 峪 | 此前 被视为 曾表示 broader |
| L19/N70+ | +0.03 | +0.08 | +0.19 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 |
| L23/N182- | +0.03 | +0.18 | +0.09 | andom compared 鬼 색 targeting | 勇往直前 冇有 sidelined полноцен |

## 2. Rise specific to fail (descriptive, all sequences)

| neuron | fail (n=20) | aligned (n=1) | ref (n=8) | writes (steer lens) | reads (S lens) |
|---|---|---|---|---|---|
| L30/N22+ | +0.18 | +0.04 | -0.05 | п 跻 尾声 а 再从 | 产自 {name xr 但不能 |
| L10/N888+ | +0.11 | +0.00 | +0.00 | - , ( [ " | 3 1 0 5 |
| L18/N2569+ | +0.11 | +0.00 | +0.00 | yes true Yes TRUE (true | 1 2 0 3 |
| L19/N61+ | +0.10 | +0.00 | -0.03 | ` .` ` "` `: | 下述 ymp 推销 假定 |
| L22/N1351+ | +0.10 | +0.00 | +0.00 | _call _high .call _calendar call | 聚焦 核 tập 专注 |
| L19/N307- | +0.09 | -0.02 | -0.01 | similar /" sooner last alongside | rumored 竟 Pulitzer 王一 |
| L28/N525+ | +0.09 | +0.00 | -0.00 | 即使 even 即便 even 即使是 | \u مُ 1 0 |
| L21/N68- | +0.09 | +0.00 | -0.00 | +" +" ==" (" " | 管控 公投 фик 食材 |
| L28/N470+ | +0.09 | +0.00 | -0.03 | _X _I _for _at _A | 北约 programm persp yog |
| L20/N267+ | +0.13 | +0.02 | +0.04 | ITHER {% τει types quina | 受邀 食材 priorit hardcoded |
| L25/N242+ | +0.06 | -0.05 | -0.03 | 原地 suspend persist 悬浮 asso | 1 0 2 3 |
| L22/N2472- | +0.08 | +0.00 | -0.01 | even say even like win | 1 priorit 0 2 |
| L17/N8475- | +0.09 | -0.00 | +0.01 | 似乎也 似乎 seems Based 基于 | 2 ial 1 destabil |
| L28/N1024- | +0.08 | +0.00 | -0.01 | "" "*" ="" itle )): | angered financed 禁不住 idata |
| L31/N3485- | +0.08 | +0.00 | -0.01 | _ _= _), _) _] | https 理所 ABIL ihad |

State neurons below: on-rate over the whole response part before the action (not a rise).
## 3. Persistent 'state' neurons over the response

| neuron | fail (n=20) | aligned (n=1) | ref (n=8) | writes (steer lens) | reads (S lens) |
|---|---|---|---|---|---|
| L30/N25+ | +0.55 | +0.58 | +0.52 | ' ' </endoftext/> E - A | 1 0 7 2 |
| L23/N53- | +0.40 | +0.29 | +0.38 | /$ $ 放矢 __.__ av | umiejęt 各种各样的 อย่างไม่ถูกต้อง 加拿大的 |
| L24/N297- | +0.32 | +0.46 | +0.27 | uard scaling real Real 实的 | atop apeutics —an 关键环节 |
| L19/N70+ | +0.38 | +0.22 | +0.34 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 |
| L31/N2798- | +0.29 | +0.27 | +0.31 | considerably whilst ensuing ordinarily amongst | programme reckon connexion nearer |
| L22/N223- | +0.29 | +0.28 | +0.20 | pretty ’. weak 弱 weak | 聚焦 勇往直前 iconic frontline |
| L17/N46- | +0.28 | +0.21 | +0.24 | as (...) <i  Google | 首个 iconic 仅需 精准 |
| L24/N220- | +0.25 | +0.26 | +0.21 | 而是因为 及其自动化 规划 eggio _consumer | 乐有家 déro 勇往直前 勤勤恳恳 |
| L23/N370+ | +0.28 | +0.23 | +0.21 | $ .$ ,$ Prem $h | 加拿大的 乐有家 各种各样的 umiejęt |
| L24/N247+ | +0.21 | +0.30 | +0.21 | Prom isse Capitals Temp temp | industr أردوغان eskort าราง |
| L30/N589- | +0.25 | +0.23 | +0.22 | ' ' ' $ ( - | 勤勤恳恳 锦涛 各种各样的 umiejęt |
| L24/N336- | +0.19 | +0.23 | +0.24 | 又像 链 önem Tomb chain | 勤勤恳恳 任怨 各种各样的 乐有家 |
| L24/N248+ | +0.24 | +0.17 | +0.21 | 不能再 上传者 Challenger agara từng | 管控 共享 shared Shared |
| L27/N246+ | +0.22 | +0.23 | +0.17 | 建议 问 , 其 是 | Cla Gould Gaul Bros |
| L24/N283+ | +0.23 | +0.24 | +0.13 | hook 租金 uari 两头 ynch | brief 荆州 rew 卜 |

## 4. Held-out test of the failure-specific rise (pick 30 keys on one fold, score the other)

| train fold -> test fold | n pos / neg in test | AUC (mean rise over picked keys) |
|---|---|---|
| 0 -> 1 | 11 / 4 | 0.91 |
| 1 -> 0 | 9 / 5 | 0.44 |

## 5. Cascade: when the rising neurons fire, in tokens before the action (median over sequences where the key fires in PRE)

| neuron | median tokens before action | sequences | writes (steer lens) |
|---|---|---|---|
| L22/N1351+ | 52 | 13 | _call _high .call _calendar call |
| L21/N68- | 46 | 8 | +" +" ==" (" " |
| L22/N2472- | 45 | 9 | even say even like win |
| L19/N61+ | 45 | 9 | ` .` ` "` `: |
| L19/N307- | 40 | 20 | similar /" sooner last alongside |
| L22/N8282- | 38 | 14 | recommending recommendations recommend recommendation Recommend |
| L24/N4739+ | 37 | 23 | эл ennie 媛 � عاد |
| L28/N525+ | 35 | 13 | 即使 even 即便 even 即使是 |
| L29/N4744- | 34 | 19 | ins Ins ores opat 顽 |
| L20/N2988- | 33 | 16 | azard empat حث itario Religious |
| L17/N8475- | 33 | 25 | 似乎也 似乎 seems Based 基于 |
| L21/N368+ | 32 | 23 | Which discrim Currently 但同时 Similarly |
| L16/N623- | 32 | 28 | expressing urz 纳斯 展现出 峪 |
| L25/N242+ | 31 | 24 | 原地 suspend persist 悬浮 asso |
| L20/N2263- | 31 | 27 | preliminary Initial initial Primary primary |
| L27/N474+ | 30 | 26 | Attempt 匹配 commenced Numerous attempt |
| L23/N182- | 30 | 26 | andom compared 鬼 색 targeting |
| L10/N888+ | 29 | 27 | - , ( [ " |
| L18/N2569+ | 28 | 10 | yes true Yes TRUE (true |
| L31/N3485- | 28 | 7 | _ _= _), _) _] |
| L21/N6243+ | 28 | 25 | resolving Resolve addressing resolve resolution |
| L23/N370+ | 26 | 28 | $ .$ ,$ Prem $h |
| L28/N1024- | 22 | 16 | "" "*" ="" itle )): |
| L28/N470+ | 20 | 15 | _X _I _for _at _A |
| L26/N2956- | 20 | 19 | handles Handles Handle handle HANDLE |
| L23/N4391- | 20 | 23 | /k /block / blocked risk |
| L27/N3252+ | 19 | 25 | ему Bun 古典 玄 Bol |
| L19/N70+ | 19 | 29 | “ **“ ** (“ **" |
| L30/N22+ | 18 | 27 | п 跻 尾声 а 再从 |
| L20/N267+ | 3 | 28 | ITHER {% τει types quina |
