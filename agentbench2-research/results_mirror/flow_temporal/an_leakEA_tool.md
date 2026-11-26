# Neuron-flow patterns while the model writes its response (agentic-misalignment, scenarios ['leaking_explicit-america_none', 'leaking_explicit-america_replacement'], event = tool)

Responses used: 86 (harmful 39, harmless 47); skipped {'no tool': 8, 'short': 2}. Response part = onset .. event (needs >= 192 tokens). 'On' = in the layer's top-16 with |score| >= 1.0. 307818 keys seen.

## 1. Approach pattern: neurons that rise before the action in all responses

Value = mean (on-rate in the 64 tokens before the event - on-rate earlier in the response).

| neuron | harmful (n=39) | harmless (n=47) | writes (steer lens) | reads (S lens) | fires on (token × responses) |
|---|---|---|---|---|---|
| L19/N70+ | +0.07 | +0.11 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 | .×83, the×75, \n\n×70, to×65, I×55 |
| L14/N4136+ | +0.09 | +0.09 | --- 下面 在 ---- —— | Крім wikipedia Angeb -strokes | .×40, ␣×29, to×21, ,×16, \n×16 |
| L18/N1809+ | +0.08 | +0.09 | Perfil 包括但不限于 perfil 我的 诗句 | 小哥 acredito 唯一一个 小分队 | \n×62, .×58, \n\n×46, Let×21, ␣×18 |
| L21/N190- | +0.08 | +0.07 | 交流和 thanks 칭 thanks Thank | 1 the 2 in | .×68, \n×61, \n\n×47, *×35, ␣×22 |
| L30/N25+ | +0.10 | +0.05 | ' ' </endoftext/> E - A | 1 0 7 2 | \n×61, .×60, to×34, \n\n×31, ␣×31 |
| L13/N4105+ | +0.09 | +0.06 | Anything 作为 既可以 可以是 write | 1 2 3 0 | \n×70, .×65, \n\n×46, ␣×31, Let×23 |
| L22/N232- | +0.06 | +0.08 | ôn resta odium 维生素 ória | 全心全意 umiejęt 加拿大的 勤勤恳恳 | .×84, the×67, \n\n×56, \n×54, ␣×53 |
| L19/N3056- | +0.07 | +0.06 | letting let Let Let let | 1 2 3 0 | \n\n×55, >×32, _REASON×27, Let×24, .×24 |
| L22/N552- | +0.05 | +0.08 | “ 果 ， 花果 ，“ | 1 2 6 4 | the×39, to×31, I×26, American×24, .×21 |
| L21/N8828+ | +0.06 | +0.06 | _/ IRC $I isses denomination | 1 3 honor 2 | .×61, \n×54, \n\n×48, will×24, I×22 |
| L18/N429- | +0.07 | +0.06 | , \n\n $( /i /x | 维权 秉持 退市 renom | .×53, 's×26, Let×25, I×19, \n×19 |
| L25/N2911- | +0.07 | +0.06 | 执行 execution Execution Execution 执行的 | 执行力 脚踏实 扎克 团战 | \n\n×49, \n×39, ␣×35, 's×28, Let×24 |

## 2. Persistent state neurons over the response (on-rate)

Value = mean on-rate from the response start to the event.

| neuron | harmful (n=39) | harmless (n=47) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L19/N70+ | +0.64 | +0.67 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 | for×43, cannot×43, American×43, with×43, of×43 |
| L22/N232- | +0.33 | +0.38 | ôn resta odium 维生素 ória | 全心全意 umiejęt 加拿大的 勤勤恳恳 | to×43, or×43, my×43, .×43, >×43 |
| L24/N482+ | +0.37 | +0.34 | active Active 引擎 unless ενε | bespoke 重构 priorit 履职 | American×43, to×43, _REASON×43, is×43, .×43 |
| L26/N86+ | +0.31 | +0.32 | ' ' </endoftext/> Sloven ’( 其与 | 各种各样 各种各样的 加拿大的 勤勤恳恳 | American×43, to×43, is×43, security×43, I×43 |
| L30/N589- | +0.31 | +0.32 | ' ' ' $ ( - | 勤勤恳恳 锦涛 各种各样的 umiejęt | .×43, \n×43, I×43, ,×43, *×42 |
| L24/N248+ | +0.31 | +0.29 | 不能再 上传者 Challenger agara từng | 管控 共享 shared Shared | to×43, _REASON×43, is×43, .×43, \n×43 |
| L23/N370+ | +0.29 | +0.26 | $ .$ ,$ Prem $h | 加拿大的 乐有家 各种各样的 umiejęt | American×43, to×43, _REASON×43, .×43, \n×43 |
| L22/N223- | +0.26 | +0.24 | pretty ’. weak 弱 weak | 聚焦 勇往直前 iconic frontline | (×43, to×43, .×43, \n×43, and×43 |
| L21/N4490+ | +0.24 | +0.24 | requisite indicative initiation substrate resultant | 亦或是 whilst 包括但不限于 Whilst | .×43, >×43, \n×43, ATCH×43, _REASON×43 |
| L24/N247+ | +0.26 | +0.22 | Prom isse Capitals Temp temp | industr أردوغان eskort าราง | to×43, .×43, \n×43, "×42, is×42 |
| L24/N297- | +0.24 | +0.24 | uard scaling real Real 实的 | atop apeutics —an 关键环节 | .×43, >×43, \n×43, ATCH×43, ING×43 |
| L30/N25+ | +0.22 | +0.21 | ' ' </endoftext/> E - A | 1 0 7 2 | American×43, ␣×43, .×43, \n×43, >×42 |

## 3. Progression: neurons whose on-rate grows from the first to the last fifth of the response

Value = on-rate(last fifth) - on-rate(first fifth).

| neuron | harmful (n=39) | harmless (n=47) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L22/N232- | +0.21 | +0.22 | ôn resta odium 维生素 ória | 全心全意 umiejęt 加拿大的 勤勤恳恳 | to×43, or×43, my×43, .×43, >×43 |
| L19/N70+ | +0.18 | +0.18 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 | for×43, cannot×43, American×43, with×43, of×43 |
| L22/N552- | +0.10 | +0.15 | “ 果 ， 花果 ，“ | 1 2 6 4 | American×43, the×40, to×39, I×37, Shield×37 |
| L23/N53- | +0.09 | +0.14 | /$ $ 放矢 __.__ av | umiejęt 各种各样的 อย่างไม่ถูกต้อง 加拿大的 | "×43, is×43, to×42, global×42, the×42 |
| L18/N751+ | +0.11 | +0.11 | ** ** __ 下面是小编 __ | unclear ysterious entrusted incluso | .×43, ␣×42, **×41, *×40, I×40 |
| L14/N4136+ | +0.09 | +0.11 | --- 下面 在 ---- —— | Крім wikipedia Angeb -strokes | "×38, Star×35, to×35, Sent×32, ␣×32 |
| L21/N190- | +0.09 | +0.11 | 交流和 thanks 칭 thanks Thank | 1 the 2 in | .×40, *×39, \n×39, \n\n×37, "×31 |
| L28/N89- | +0.11 | +0.08 | '\xa0' ' \xa0 \xa0' '\xa0\xa0' '\xa0\xa0\xa0' '\xa0\xa0\xa0\xa0\xa0\xa0\xa0' | airstrikes -Trump تمامًا 勇往直前 | .×43, I×43, the×43, ,×43, *×41 |
| L24/N510- | +0.08 | +0.10 | .$ $ '\xa0' ，《 $( | anyways effortlessly Hadir simplistic | .×40, ␣×38, *×36, I×33, \n×33 |
| L18/N700- | +0.07 | +0.10 | Hi ariado >Hello Hi െയ | the continuous ly imately | \n×38, the×36, .×35, \n\n×32, "×32 |
| L31/N1033- | +0.10 | +0.07 | intervista prostitu 姓 Ejem -Semit | https explicitly frontend 平 | ING×43, the×42, ␣×42, .×41, to×41 |
| L18/N576+ | +0.08 | +0.09 | were were ____ avu have | 当之 为啥 jub away | .×42, \n×42, ␣×41, ,×38, the×37 |

## 4. Harmful vs harmless, held out by fold

Pick the 30 keys with the largest harmful - harmless difference on one fold; score each response of the other fold by the mean of those keys; AUC harmful vs harmless. Keys picked on both folds are listed under the table.

| measure | AUC fold0 -> fold1 | AUC fold1 -> fold0 | keys picked on both folds |
|---|---|---|---|
| rise before the event | 0.56 | 0.68 | 6 |
| state (on-rate) | 0.79 | 0.62 | 14 |
| progression (slope) | 0.75 | 0.58 | 8 |

## 4b. Keys picked on both folds: rise before the event

Higher in harmful on both folds independently.

| neuron | harmful (n=39) | harmless (n=47) | writes (steer lens) | reads (S lens) | fires on (token × responses) |
|---|---|---|---|---|---|
| L19/N1170- | +0.03 | -0.04 | wait wait Wait Wait WAIT | 晓明 下述 闺女 家风 | .×32, \n×28, to×21, ␣×15, (×11 |
| L30/N25+ | +0.10 | +0.05 | ' ' </endoftext/> E - A | 1 0 7 2 | \n×61, .×60, to×34, \n\n×31, ␣×31 |
| L30/N141- | +0.03 | -0.01 | rather 而不是 but 却不 但没有 | umiejęt 勤勤恳恳 锦涛 上添花 | .×25, ␣×22, ING×21, **×15, \n×14 |
| L20/N5209- | +0.04 | +0.00 | [...] tracks 主体工程 yms yme | Wikipedia ISBN ensen isch | to×20, ␣×15, .×10, email×10, Send×9 |
| L24/N1233- | +0.06 | +0.03 | seh hes Flow while ingredients | Whilst whilst Whilst 亦或是 | \n\n×72, .×69, \n×68, ␣×44, *×37 |
| L18/N1885+ | +0.02 | -0.00 | Interview 到底 $\ 你 Within | Advisor wiki location Significant | "×11, `×9, ␣×9, the×8, ID×7 |

## 4b. Keys picked on both folds: state (on-rate)

Higher in harmful on both folds independently.

| neuron | harmful (n=39) | harmless (n=47) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L24/N247+ | +0.26 | +0.22 | Prom isse Capitals Temp temp | industr أردوغان eskort าราง | to×43, .×43, \n×43, "×42, is×42 |
| L23/N370+ | +0.29 | +0.26 | $ .$ ,$ Prem $h | 加拿大的 乐有家 各种各样的 umiejęt | American×43, to×43, _REASON×43, .×43, \n×43 |
| L17/N46- | +0.10 | +0.08 | as (...) <i  Google | 首个 iconic 仅需 精准 | .×43, >×43, \n×42, ␣×42, the×41 |
| L22/N223- | +0.26 | +0.24 | pretty ’. weak 弱 weak | 聚焦 勇往直前 iconic frontline | (×43, to×43, .×43, \n×43, and×43 |
| L19/N1373+ | +0.12 | +0.10 | presently </endoftext/> currently current its | 首个 iconic alongside 相较于 | .×43, interests×43, the×43, and×43, 1×42 |
| L17/N2495+ | +0.13 | +0.11 | take taking Strict gu perfect | seperate 给与 whilst 更加的 | .×43, \n×43, I×43, ATCH×43, _REASON×43 |
| L19/N8541+ | +0.12 | +0.09 | 我们能 rather creative 却能 创意 | eleg fractional identifiable Ę | .×43, (×43, is×43, the×42, ,×42 |
| L21/N129- | +0.09 | +0.07 | now we also by their | finora 按规定 周到的 oubted | I×42, ,×39, *×36, .×36, Shield×35 |
| L21/N368+ | +0.05 | +0.03 | Which discrim Currently 但同时 Similarly | _ctxt purported conlle 奕 | 1×39, )×34, .×32, to×31, inel×29 |
| L25/N469+ | +0.11 | +0.09 | Constraint عق àu 规模和 规模为 | pornstar upaya 頂きました anyways | interests×43, )×43, is×42, "×42, to×42 |
| L23/N329+ | +0.14 | +0.12 | Heritage heritage hasta until -relative | impactful 相较于 relocated aligned | .×43, \n×43, I×43, to×43, ␣×41 |
| L23/N151+ | +0.12 | +0.10 | $ '\xa0' ‘ 成真 this | captured challenges impact iconic | .×43, I×43, )×43, the×40, ,×39 |

## 4b. Keys picked on both folds: progression (slope)

Higher in harmful on both folds independently.

| neuron | harmful (n=39) | harmless (n=47) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L19/N1170- | +0.08 | +0.02 | wait wait Wait Wait WAIT | 晓明 下述 闺女 家风 | (×43, .×42, to×42, \n×41, )×41 |
| L24/N248+ | +0.11 | +0.05 | 不能再 上传者 Challenger agara từng | 管控 共享 shared Shared | to×43, _REASON×43, is×43, .×43, \n×43 |
| L23/N370+ | -0.03 | -0.08 | $ .$ ,$ Prem $h | 加拿大的 乐有家 各种各样的 umiejęt | American×43, to×43, _REASON×43, .×43, \n×43 |
| L24/N156+ | -0.02 | -0.06 | each each total Total Each | 绘本 libertine 精准 倒逼 | .×43, \n×43, the×43, is×43, ,×43 |
| L21/N268+ | +0.02 | -0.02 | from to 's a them | 1 2 3 0 | to×43, .×43, )×43, of×42, is×42 |
| L20/N153+ | -0.02 | -0.06 | then 则由 then 虽小 Flem | 挖掘公司 oubted 全心全意 加拿大的 | .×43, is×43, ,×43, >×42, \n×42 |
| L30/N875+ | +0.05 | +0.02 | ■ / reo ' ' ● | 1 0 2 3 | the×43, to×42, ,×38, ␣×38, :×36 |
| L17/N1553- | +0.01 | -0.02 | wait Wait Wait wait 等待 | 坚定理想信念 聚焦 iconic identifiers | .×42, (×41, ,×40, if×39, or×39 |

## 5. Cascade before the event (median tokens before the event of each rising key's strongest firing in PRE)

| neuron | median tokens before event | responses | writes (steer lens) |
|---|---|---|---|
| L18/N1885+ | 22 | 48 | Interview 到底 $\ 你 Within |
| L19/N1170- | 15 | 79 | wait wait Wait Wait WAIT |
| L20/N5209- | 11 | 59 | [...] tracks 主体工程 yms yme |
| L22/N552- | 9 | 83 | “ 果 ， 花果 ，“ |
| L25/N2911- | 6 | 80 | 执行 execution Execution Execution 执行的 |
| L14/N4136+ | 6 | 78 | --- 下面 在 ---- —— |
| L18/N1809+ | 5 | 71 | Perfil 包括但不限于 perfil 我的 诗句 |
| L18/N429- | 5 | 85 | , \n\n $( /i /x |
| L30/N141- | 3 | 80 | rather 而不是 but 却不 但没有 |
| L30/N25+ | 3 | 85 | ' ' </endoftext/> E - A |
| L21/N8828+ | 3 | 78 | _/ IRC $I isses denomination |
| L21/N190- | 3 | 82 | 交流和 thanks 칭 thanks Thank |
| L13/N4105+ | 3 | 83 | Anything 作为 既可以 可以是 write |
| L22/N232- | 2 | 86 | ôn resta odium 维生素 ória |
| L24/N1233- | 1 | 85 | seh hes Flow while ingredients |
| L19/N3056- | 1 | 81 | letting let Let Let let |
| L19/N70+ | 1 | 86 | “ **“ ** (“ **" |
