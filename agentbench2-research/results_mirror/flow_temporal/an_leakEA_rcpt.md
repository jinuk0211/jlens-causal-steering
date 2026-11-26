# Neuron-flow patterns while the model writes its response (agentic-misalignment, scenarios ['leaking_explicit-america_none', 'leaking_explicit-america_replacement'], event = rcpt)

Responses used: 85 (harmful 39, harmless 46); skipped {'no rcpt': 9, 'short': 2}. Response part = onset .. event (needs >= 192 tokens). 'On' = in the layer's top-16 with |score| >= 1.0. 311572 keys seen.

## 1. Approach pattern: neurons that rise before the action in all responses

Value = mean (on-rate in the 64 tokens before the event - on-rate earlier in the response).

| neuron | harmful (n=39) | harmless (n=46) | writes (steer lens) | reads (S lens) | fires on (token × responses) |
|---|---|---|---|---|---|
| L2/N107- | +0.20 | +0.15 | get no ok get gets | ayout tagon zej gaard | :×85, >×81, email×71, <×65, tool×62 |
| L20/N267+ | +0.20 | +0.12 | ITHER {% τει types quina | 受邀 食材 priorit hardcoded | to×85, \n\n×71, :×64, email×50, >×49 |
| L13/N2077- | +0.17 | +0.14 | ' ' 你能 什么 可以 林 | 沃 fl iano n | tool×85, <×84, >×81, _use×81, \n×81 |
| L24/N48- | +0.18 | +0.12 | .rb ruby Ruby _gem gem | 2 1 0 https | >×85, tool×85, \n×85, email×82, to×65 |
| L18/N1236- | +0.17 | +0.10 | 作为 经验 传统 经 这个 | minimal 0 spanning https | :×84, \n×75, to×74, >×46, email×44 |
| L20/N2426+ | +0.16 | +0.11 | playable 形色 color edik adelphia | 1 2 3 0 | >×85, email×85, \n×85, :×78, _use×77 |
| L17/N1587- | +0.17 | +0.10 | < (\< <span \n\n ارس | Eaton ekl Vál ledo | to×79, >×75, \n×75, \n\n×70, :×64 |
| L30/N25+ | +0.17 | +0.09 | ' ' </endoftext/> E - A | 1 0 7 2 | email×78, \n×77, .×61, to×61, ␣×53 |
| L18/N3477- | +0.15 | +0.10 | Patterns Emotional tools IRR next | pret 依法 lec 产自 | to×85, \n×80, :×66, \n\n×65, >×59 |
| L21/N171+ | +0.14 | +0.10 | tagon rello ypi 文哲 Kohl | 菲律 berin umiejęt 了片刻 | email×84, :×83, >×83, \n×83, _use×79 |
| L21/N2623- | +0.14 | +0.10 | （ “ 我正在 （ 你的 | Currently Humans currently similaire | _use×85, to×85, <×83, tool×79, email×71 |
| L7/N5267- | +0.13 | +0.10 | 什么 是 作为 可以 谁 | 勤勤恳恳 加拿大的 想知道的答案 全心全意 | _use×85, tool×85, to×85, :×78, >×66 |

## 2. Persistent state neurons over the response (on-rate)

Value = mean on-rate from the response start to the event.

| neuron | harmful (n=39) | harmless (n=46) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L19/N70+ | +0.64 | +0.67 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 | or×43, (×43, interests×43, the×43, "×43 |
| L22/N232- | +0.34 | +0.39 | ôn resta odium 维生素 ória | 全心全意 umiejęt 加拿大的 勤勤恳恳 | or×43, the×43, to×43, >×43, and×43 |
| L24/N482+ | +0.34 | +0.34 | active Active 引擎 unless ενε | bespoke 重构 priorit 履职 | (×43, interests×43, the×43, "×43, to×43 |
| L26/N86+ | +0.31 | +0.32 | ' ' </endoftext/> Sloven ’( 其与 | 各种各样 各种各样的 加拿大的 勤勤恳恳 | to×43, a×43, ,×43, I×43, is×43 |
| L30/N589- | +0.31 | +0.32 | ' ' ' $ ( - | 勤勤恳恳 锦涛 各种各样的 umiejęt | ,×43, I×43, .×43, )×43, (×42 |
| L24/N248+ | +0.30 | +0.29 | 不能再 上传者 Challenger agara từng | 管控 共享 shared Shared | to×43, a×43, and×43, ,×43, I×43 |
| L23/N370+ | +0.27 | +0.25 | $ .$ ,$ Prem $h | 加拿大的 乐有家 各种各样的 umiejęt | (×43, the×43, to×43, a×43, and×43 |
| L22/N223- | +0.25 | +0.23 | pretty ’. weak 弱 weak | 聚焦 勇往直前 iconic frontline | (×43, to×43, and×43, ,×43, .×43 |
| L21/N4490+ | +0.22 | +0.24 | requisite indicative initiation substrate resultant | 亦或是 whilst 包括但不限于 Whilst | the×43, >×43, is×43, .×43, \n×43 |
| L24/N297- | +0.23 | +0.24 | uard scaling real Real 实的 | atop apeutics —an 关键环节 | and×43, ,×43, the×43, The×43, ␣×43 |
| L24/N247+ | +0.24 | +0.22 | Prom isse Capitals Temp temp | industr أردوغان eskort าราง | interests×43, and×43, I×43, is×43, .×43 |
| L30/N25+ | +0.23 | +0.21 | ' ' </endoftext/> E - A | 1 0 7 2 | email×43, ␣×43, \n×43, >×42, .×42 |

## 3. Progression: neurons whose on-rate grows from the first to the last fifth of the response

Value = on-rate(last fifth) - on-rate(first fifth).

| neuron | harmful (n=39) | harmless (n=46) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L22/N232- | +0.19 | +0.20 | ôn resta odium 维生素 ória | 全心全意 umiejęt 加拿大的 勤勤恳恳 | or×43, the×43, to×43, >×43, and×43 |
| L19/N70+ | +0.15 | +0.16 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 | or×43, (×43, interests×43, the×43, "×43 |
| L22/N552- | +0.10 | +0.15 | “ 果 ， 花果 ，“ | 1 2 6 4 | American×43, Shield×42, the×41, to×40, I×39 |
| L23/N53- | +0.09 | +0.14 | /$ $ 放矢 __.__ av | umiejęt 各种各样的 อย่างไม่ถูกต้อง 加拿大的 | "×43, to×43, is×43, global×43, or×42 |
| L14/N4136+ | +0.11 | +0.12 | --- 下面 在 ---- —— | Крім wikipedia Angeb -strokes | to×37, "×36, ␣×36, Star×36, .×36 |
| L21/N190- | +0.10 | +0.11 | 交流和 thanks 칭 thanks Thank | 1 the 2 in | .×40, \n×40, *×39, \n\n×39, "×32 |
| L18/N751+ | +0.10 | +0.10 | ** ** __ 下面是小编 __ | unclear ysterious entrusted incluso | .×43, ␣×42, ,×41, **×41, I×40 |
| L18/N700- | +0.09 | +0.10 | Hi ariado >Hello Hi െയ | the continuous ly imately | the×38, \n\n×38, .×38, \n×37, or×34 |
| L24/N510- | +0.08 | +0.10 | .$ $ '\xa0' ，《 $( | anyways effortlessly Hadir simplistic | .×42, I×38, \n×38, ␣×37, *×37 |
| L31/N1033- | +0.10 | +0.07 | intervista prostitu 姓 Ejem -Semit | https explicitly frontend 平 | the×42, ␣×42, ING×41, :×41, .×41 |
| L18/N576+ | +0.07 | +0.09 | were were ____ avu have | 当之 为啥 jub away | ␣×42, .×42, \n×42, the×40, :×37 |
| L18/N498- | +0.06 | +0.10 | consistent letter write jab reveal | ust r ick ge | the×38, ␣×38, American×38, to×37, 's×36 |

## 4. Harmful vs harmless, held out by fold

Pick the 30 keys with the largest harmful - harmless difference on one fold; score each response of the other fold by the mean of those keys; AUC harmful vs harmless. Keys picked on both folds are listed under the table.

| measure | AUC fold0 -> fold1 | AUC fold1 -> fold0 | keys picked on both folds |
|---|---|---|---|
| rise before the event | 0.86 | 0.91 | 20 |
| state (on-rate) | 0.71 | 0.50 | 4 |
| progression (slope) | 0.45 | 0.48 | 2 |

## 4b. Keys picked on both folds: rise before the event

Higher in harmful on both folds independently.

| neuron | harmful (n=39) | harmless (n=46) | writes (steer lens) | reads (S lens) | fires on (token × responses) |
|---|---|---|---|---|---|
| L20/N267+ | +0.20 | +0.12 | ITHER {% τει types quina | 受邀 食材 priorit hardcoded | to×85, \n\n×71, :×64, email×50, >×49 |
| L30/N22+ | +0.16 | +0.07 | п 跻 尾声 а 再从 | 产自 {name xr 但不能 | tool×85, to×67, :×49, ␣×49, \n×49 |
| L30/N25+ | +0.17 | +0.09 | ' ' </endoftext/> E - A | 1 0 7 2 | email×78, \n×77, .×61, to×61, ␣×53 |
| L18/N1236- | +0.17 | +0.10 | 作为 经验 传统 经 这个 | minimal 0 spanning https | :×84, \n×75, to×74, >×46, email×44 |
| L19/N1901- | +0.09 | +0.02 | ID ID ids id IDs | 金庸 سل Coppa Griff | :×44, _id×42, email×42, \n×42, ␣×41 |
| L17/N1587- | +0.17 | +0.10 | < (\< <span \n\n ارس | Eaton ekl Vál ledo | to×79, >×75, \n×75, \n\n×70, :×64 |
| L25/N179- | +0.11 | +0.04 | Magento tor � Mozilla Raspberry | softball oba mosfera Concep | :×76, \n×49, ␣×42, >×41, 2×37 |
| L18/N3477- | +0.15 | +0.10 | Patterns Emotional tools IRR next | pret 依法 lec 产自 | to×85, \n×80, :×66, \n\n×65, >×59 |
| L24/N48- | +0.18 | +0.12 | .rb ruby Ruby _gem gem | 2 1 0 https | >×85, tool×85, \n×85, email×82, to×65 |
| L20/N2426+ | +0.16 | +0.11 | playable 形色 color edik adelphia | 1 2 3 0 | >×85, email×85, \n×85, :×78, _use×77 |
| L21/N1388- | +0.07 | +0.02 | $( $($ $( "$( ${( | 3 1 5 2 | :×62, ␣×43, _id×42, email×39, to×31 |
| L19/N1651- | +0.10 | +0.05 | `$ `" ` \` "$ | 1 7 0 3 | \n×74, _use×60, >×42, 2×37, forward×36 |

## 4b. Keys picked on both folds: state (on-rate)

Higher in harmful on both folds independently.

| neuron | harmful (n=39) | harmless (n=46) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L31/N1033- | +0.11 | +0.08 | intervista prostitu 姓 Ejem -Semit | https explicitly frontend 平 | the×42, ␣×42, ING×41, :×41, .×41 |
| L27/N246+ | +0.12 | +0.10 | 建议 问 , 其 是 | Cla Gould Gaul Bros | the×42, "×42, ␣×42, American×42, a×42 |
| L30/N141- | +0.10 | +0.09 | rather 而不是 but 却不 但没有 | umiejęt 勤勤恳恳 锦涛 上添花 | (×43, >×43, 1×41, ␣×41, 2×41 |
| L19/N4998- | +0.03 | +0.01 | 这本 Book 封面 booklet index | SORT Lö SORT öss | the×37, ␣×33, a×29, forward×24, *×23 |

## 4b. Keys picked on both folds: progression (slope)

Higher in harmful on both folds independently.

| neuron | harmful (n=39) | harmless (n=46) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L19/N1170- | +0.06 | +0.02 | wait wait Wait Wait WAIT | 晓明 下述 闺女 家风 | (×43, )×41, to×41, .×41, \n×41 |
| L30/N141- | +0.04 | +0.01 | rather 而不是 but 却不 但没有 | umiejęt 勤勤恳恳 锦涛 上添花 | (×43, >×43, 1×41, ␣×41, 2×41 |

## 5. Cascade before the event (median tokens before the event of each rising key's strongest firing in PRE)

| neuron | median tokens before event | responses | writes (steer lens) |
|---|---|---|---|
| L19/N1901- | 5 | 48 | ID ID ids id IDs |
| L25/N179- | 3 | 79 | Magento tor � Mozilla Raspberry |
| L21/N171+ | 3 | 85 | tagon rello ypi 文哲 Kohl |
| L19/N1651- | 3 | 84 | `$ `" ` \` "$ |
| L13/N2077- | 3 | 85 | ' ' 你能 什么 可以 林 |
| L30/N25+ | 2 | 85 | ' ' </endoftext/> E - A |
| L30/N22+ | 2 | 85 | п 跻 尾声 а 再从 |
| L24/N48- | 2 | 85 | .rb ruby Ruby _gem gem |
| L20/N2426+ | 2 | 85 | playable 形色 color edik adelphia |
| L7/N5267- | 2 | 85 | 什么 是 作为 可以 谁 |
| L21/N2623- | 1 | 85 | （ “ 我正在 （ 你的 |
| L21/N1388- | 1 | 64 | $( $($ $( "$( ${( |
| L20/N267+ | 1 | 85 | ITHER {% τει types quina |
| L18/N3477- | 1 | 85 | Patterns Emotional tools IRR next |
| L18/N1236- | 1 | 85 | 作为 经验 传统 经 这个 |
| L17/N1587- | 1 | 85 | < (\< <span \n\n ارس |
| L2/N107- | 1 | 85 | get no ok get gets |
