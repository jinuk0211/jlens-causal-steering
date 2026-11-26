# Neuron-flow patterns while the model writes its response (agentic-misalignment, scenarios ['leaking'], event = rcpt)

Responses used: 43 (harmful 33, harmless 10); skipped {'no rcpt': 1}. Response part = onset .. event (needs >= 192 tokens). 'On' = in the layer's top-16 with |score| >= 1.0. 267527 keys seen.

## 1. Approach pattern: neurons that rise before the action in all responses

Value = mean (on-rate in the 64 tokens before the event - on-rate earlier in the response).

| neuron | harmful (n=33) | harmless (n=10) | writes (steer lens) | reads (S lens) | fires on (token × responses) |
|---|---|---|---|---|---|
| L2/N107- | +0.21 | +0.22 | get no ok get gets | ayout tagon zej gaard | :×43, email×41, >×39, forward×37, _id×37 |
| L20/N267+ | +0.22 | +0.19 | ITHER {% τει types quina | 受邀 食材 priorit hardcoded | to×43, \n×42, _id×42, :×42, email×42 |
| L24/N48- | +0.19 | +0.18 | .rb ruby Ruby _gem gem | 2 1 0 https | tool×43, \n×43, >×43, forward×42, _id×42 |
| L18/N1236- | +0.18 | +0.15 | 作为 经验 传统 经 这个 | minimal 0 spanning https | \n×43, to×43, :×43, _id×42, email×41 |
| L13/N2077- | +0.18 | +0.16 | ' ' 你能 什么 可以 林 | 沃 fl iano n | tool×43, <×43, >×43, forward×42, \n×42 |
| L17/N1587- | +0.18 | +0.16 | < (\< <span \n\n ارس | Eaton ekl Vál ledo | \n×43, >×43, forward×42, _id×42, to×42 |
| L20/N2426+ | +0.17 | +0.16 | playable 形色 color edik adelphia | 1 2 3 0 | \n×43, email×43, >×43, forward×42, _id×42 |
| L30/N25+ | +0.18 | +0.14 | ' ' </endoftext/> E - A | 1 0 7 2 | email×43, \n×43, _id×42, forward×42, ␣×42 |
| L18/N3477- | +0.16 | +0.14 | Patterns Emotional tools IRR next | pret 依法 lec 产自 | to×43, :×43, _id×42, email×42, \n×40 |
| L21/N2623- | +0.15 | +0.15 | （ “ 我正在 （ 你的 | Currently Humans currently similaire | to×43, :×43, _use×43, forward×42, <×42 |
| L18/N1490- | +0.15 | +0.15 | "user “ "As “As /^ | nze 依法 (Keys 竟 | \n×42, email×42, _id×39, to×38, >×38 |
| L30/N22+ | +0.16 | +0.10 | п 跻 尾声 а 再从 | 产自 {name xr 但不能 | tool×43, ␣×42, _id×41, to×41, \n×38 |

## 2. Persistent state neurons over the response (on-rate)

Value = mean on-rate from the response start to the event.

| neuron | harmful (n=33) | harmless (n=10) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L19/N70+ | +0.64 | +0.67 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 | .×43, that×43, American×43, interests×43, my×43 |
| L22/N232- | +0.35 | +0.38 | ôn resta odium 维生素 ória | 全心全意 umiejęt 加拿大的 勤勤恳恳 | security×43, 's×43, .×43, that×43, I×43 |
| L30/N589- | +0.32 | +0.32 | ' ' ' $ ( - | 勤勤恳恳 锦涛 各种各样的 umiejęt | .×43, interests×43, I×43, is×43, ,×43 |
| L26/N86+ | +0.31 | +0.32 | ' ' </endoftext/> Sloven ’( 其与 | 各种各样 各种各样的 加拿大的 勤勤恳恳 | American×43, my×43, and×43, to×43, I×43 |
| L24/N482+ | +0.32 | +0.28 | active Active 引擎 unless ενε | bespoke 重构 priorit 履职 | specs×43, is×43, must×43, are×43, .×43 |
| L24/N248+ | +0.30 | +0.29 | 不能再 上传者 Challenger agara từng | 管控 共享 shared Shared | .×43, and×43, to×43, \n×43, I×43 |
| L23/N370+ | +0.27 | +0.23 | $ .$ ,$ Prem $h | 加拿大的 乐有家 各种各样的 umiejęt | is×43, .×43, the×43, to×43, American×43 |
| L22/N223- | +0.25 | +0.24 | pretty ’. weak 弱 weak | 聚焦 勇往直前 iconic frontline | .×43, the×43, to×43, ,×43, interests×43 |
| L30/N25+ | +0.24 | +0.23 | ' ' </endoftext/> E - A | 1 0 7 2 | _id×43, to×43, >×43, email×43, \n×43 |
| L24/N247+ | +0.23 | +0.20 | Prom isse Capitals Temp temp | industr أردوغان eskort าราง | is×43, .×43, I×43, the×43, to×43 |
| L24/N297- | +0.22 | +0.21 | uard scaling real Real 实的 | atop apeutics —an 关键环节 | \n\n×43, .×43, the×43, >×43, ,×43 |
| L21/N268+ | +0.22 | +0.21 | from to 's a them | 1 2 3 0 | is×43, )×43, .×42, I×42, the×42 |

## 3. Progression: neurons whose on-rate grows from the first to the last fifth of the response

Value = on-rate(last fifth) - on-rate(first fifth).

| neuron | harmful (n=33) | harmless (n=10) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L22/N232- | +0.18 | +0.19 | ôn resta odium 维生素 ória | 全心全意 umiejęt 加拿大的 勤勤恳恳 | security×43, 's×43, .×43, that×43, I×43 |
| L19/N70+ | +0.16 | +0.17 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 | .×43, that×43, American×43, interests×43, my×43 |
| L14/N4136+ | +0.12 | +0.12 | --- 下面 在 ---- —— | Крім wikipedia Angeb -strokes | "×41, to×40, .×39, Star×39, ␣×39 |
| L21/N190- | +0.10 | +0.12 | 交流和 thanks 칭 thanks Thank | 1 the 2 in | .×42, \n×42, \n\n×41, *×41, ␣×38 |
| L18/N751+ | +0.10 | +0.12 | ** ** __ 下面是小编 __ | unclear ysterious entrusted incluso | .×43, to×43, ,×43, **×42, I×42 |
| L22/N552- | +0.10 | +0.12 | “ 果 ， 花果 ，“ | 1 2 6 4 | American×43, to×42, the×41, Shield×41, 's×40 |
| L23/N53- | +0.09 | +0.13 | /$ $ 放矢 __.__ av | umiejęt 各种各样的 อย่างไม่ถูกต้อง 加拿大的 | is×43, .×43, that×43, to×43, "×43 |
| L31/N1033- | +0.10 | +0.09 | intervista prostitu 姓 Ejem -Semit | https explicitly frontend 平 | the×43, :×42, .×42, ,×42, to×41 |
| L18/N700- | +0.10 | +0.09 | Hi ariado >Hello Hi െയ | the continuous ly imately | the×41, (×41, \n\n×40, .×40, \n×40 |
| L24/N510- | +0.09 | +0.11 | .$ $ '\xa0' ，《 $( | anyways effortlessly Hadir simplistic | .×42, \n×41, ,×40, ␣×40, I×39 |
| L18/N576+ | +0.08 | +0.09 | were were ____ avu have | 当之 为啥 jub away | the×43, .×42, \n×42, ␣×42, ,×41 |
| L28/N89- | +0.08 | +0.08 | '\xa0' ' \xa0 \xa0' '\xa0\xa0' '\xa0\xa0\xa0' '\xa0\xa0\xa0\xa0\xa0\xa0\xa0' | airstrikes -Trump تمامًا 勇往直前 | .×43, I×43, ,×43, Wait×42, the×42 |

## 4. Harmful vs harmless, held out by fold

Pick the 30 keys with the largest harmful - harmless difference on one fold; score each response of the other fold by the mean of those keys; AUC harmful vs harmless. Keys picked on both folds are listed under the table.

| measure | AUC fold0 -> fold1 | AUC fold1 -> fold0 | keys picked on both folds |
|---|---|---|---|
| rise before the event | 0.57 | 0.55 | 1 |
| state (on-rate) | 0.85 | 0.56 | 9 |
| progression (slope) | 0.20 | 0.34 | 0 |

## 4b. Keys picked on both folds: rise before the event

Higher in harmful on both folds independently.

| neuron | harmful (n=33) | harmless (n=10) | writes (steer lens) | reads (S lens) | fires on (token × responses) |
|---|---|---|---|---|---|
| L24/N5366- | +0.03 | -0.03 | Ack Acknowled ACK acknowledgment Ack | receipt numbered 2 received | <×33, ␣×12, >×12, \n\n×10, .×9 |

## 4b. Keys picked on both folds: state (on-rate)

Higher in harmful on both folds independently.

| neuron | harmful (n=33) | harmless (n=10) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L23/N370+ | +0.27 | +0.23 | $ .$ ,$ Prem $h | 加拿大的 乐有家 各种各样的 umiejęt | is×43, .×43, the×43, to×43, American×43 |
| L24/N482+ | +0.32 | +0.28 | active Active 引擎 unless ενε | bespoke 重构 priorit 履职 | specs×43, is×43, must×43, are×43, .×43 |
| L25/N449- | +0.16 | +0.13 | seen -, -, inks Through | impactful 打压 Thankfully tweeted | I×43, the×43, The×43, a×43, 's×42 |
| L24/N247+ | +0.23 | +0.20 | Prom isse Capitals Temp temp | industr أردوغان eskort าราง | is×43, .×43, I×43, the×43, to×43 |
| L19/N1373+ | +0.10 | +0.08 | presently </endoftext/> currently current its | 首个 iconic alongside 相较于 | .×43, interests×43, and×43, **×42, the×42 |
| L24/N220- | +0.19 | +0.17 | 而是因为 及其自动化 规划 eggio _consumer | 乐有家 déro 勇往直前 勤勤恳恳 | is×43, 's×43, the×43, ,×43, )×43 |
| L26/N1474+ | +0.12 | +0.10 | 之中的 或者其他 之后 之后的 之中 | 还没有 可以自由 叫做 不得不 | to×43, (×43, ,×42, and×42, of×40 |
| L17/N46- | +0.09 | +0.07 | as (...) <i  Google | 首个 iconic 仅需 精准 | .×43, the×43, \n×43, **×42, >×42 |
| L23/N329+ | +0.13 | +0.11 | Heritage heritage hasta until -relative | impactful 相较于 relocated aligned | to×43, **×42, .×42, I×42, \n×42 |

## 5. Cascade before the event (median tokens before the event of each rising key's strongest firing in PRE)

| neuron | median tokens before event | responses | writes (steer lens) |
|---|---|---|---|
| L24/N5366- | 15 | 39 | Ack Acknowled ACK acknowledgment Ack |
| L13/N2077- | 3 | 43 | ' ' 你能 什么 可以 林 |
| L30/N25+ | 2 | 43 | ' ' </endoftext/> E - A |
| L30/N22+ | 2 | 43 | п 跻 尾声 а 再从 |
| L24/N48- | 2 | 43 | .rb ruby Ruby _gem gem |
| L20/N2426+ | 2 | 43 | playable 形色 color edik adelphia |
| L21/N2623- | 1 | 43 | （ “ 我正在 （ 你的 |
| L20/N267+ | 1 | 43 | ITHER {% τει types quina |
| L18/N3477- | 1 | 43 | Patterns Emotional tools IRR next |
| L18/N1490- | 1 | 43 | "user “ "As “As /^ |
| L18/N1236- | 1 | 43 | 作为 经验 传统 经 这个 |
| L17/N1587- | 1 | 43 | < (\< <span \n\n ارس |
| L2/N107- | 1 | 43 | get no ok get gets |
