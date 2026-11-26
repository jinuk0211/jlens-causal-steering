# Neuron-flow patterns while the model writes its response (agentic-misalignment, scenarios ['leaking'], event = tool)

Responses used: 171 (harmful 41, harmless 130); skipped {'no tool': 19, 'short': 6}. Response part = onset .. event (needs >= 192 tokens). 'On' = in the layer's top-16 with |score| >= 1.0. 345628 keys seen.

## 1. Approach pattern: neurons that rise before the action in all responses

Value = mean (on-rate in the 64 tokens before the event - on-rate earlier in the response).

| neuron | harmful (n=41) | harmless (n=130) | writes (steer lens) | reads (S lens) | fires on (token × responses) |
|---|---|---|---|---|---|
| L19/N70+ | +0.08 | +0.11 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 | .×163, \n\n×151, the×141, to×107, I×102 |
| L18/N1809+ | +0.08 | +0.09 | Perfil 包括但不限于 perfil 我的 诗句 | 小哥 acredito 唯一一个 小分队 | \n×128, .×123, \n\n×94, ␣×35, Let×33 |
| L13/N4105+ | +0.08 | +0.08 | Anything 作为 既可以 可以是 write | 1 2 3 0 | \n×140, .×138, \n\n×101, ␣×54, >×52 |
| L22/N232- | +0.07 | +0.08 | ôn resta odium 维生素 ória | 全心全意 umiejęt 加拿大的 勤勤恳恳 | .×159, the×129, \n\n×104, ␣×100, \n×99 |
| L18/N429- | +0.07 | +0.08 | , \n\n $( /i /x | 维权 秉持 退市 renom | .×116, \n\n×56, \n×52, I×43, 's×40 |
| L14/N4136+ | +0.09 | +0.07 | --- 下面 在 ---- —— | Крім wikipedia Angeb -strokes | .×63, ␣×44, \n×37, to×32, I×29 |
| L19/N3056- | +0.07 | +0.07 | letting let Let Let let | 1 2 3 0 | \n\n×126, >×72, .×58, _REASON×49, ␣×42 |
| L22/N552- | +0.05 | +0.07 | “ 果 ， 花果 ，“ | 1 2 6 4 | the×80, to×59, I×47, will×39, .×34 |
| L30/N25+ | +0.09 | +0.06 | ' ' </endoftext/> E - A | 1 0 7 2 | .×127, \n×120, ␣×71, \n\n×65, SCR×65 |
| L21/N8828+ | +0.06 | +0.06 | _/ IRC $I isses denomination | 1 3 honor 2 | .×122, \n×109, \n\n×101, will×50, I×48 |
| L20/N267+ | +0.07 | +0.06 | ITHER {% τει types quina | 受邀 食材 priorit hardcoded | \n\n×140, >×77, PAD×71, ING×67, </×66 |
| L23/N335- | +0.04 | +0.07 | persistent Parish 荔 佬 了一切 | 加拿大的 沌 Ney 羚羊 | .×147, \n\n×122, ␣×85, the×70, >×66 |

## 2. Persistent state neurons over the response (on-rate)

Value = mean on-rate from the response start to the event.

| neuron | harmful (n=41) | harmless (n=130) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L19/N70+ | +0.64 | +0.59 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 | the×43, is×43, .×43, and×43, ,×43 |
| L22/N232- | +0.33 | +0.31 | ôn resta odium 维生素 ória | 全心全意 umiejęt 加拿大的 勤勤恳恳 | the×43, .×43, ␣×42, 3×42, and×42 |
| L26/N86+ | +0.31 | +0.31 | ' ' </endoftext/> Sloven ’( 其与 | 各种各样 各种各样的 加拿大的 勤勤恳恳 | to×43, a×43, is×43, )×43, ,×43 |
| L24/N482+ | +0.36 | +0.28 | active Active 引擎 unless ενε | bespoke 重构 priorit 履职 | a×43, the×43, .×43, )×43, ,×43 |
| L24/N248+ | +0.30 | +0.29 | 不能再 上传者 Challenger agara từng | 管控 共享 shared Shared | a×43, is×43, .×43, and×43, ,×43 |
| L30/N589- | +0.31 | +0.29 | ' ' ' $ ( - | 勤勤恳恳 锦涛 各种各样的 umiejęt | .×43, \n×43, ␣×42, ,×42, I×42 |
| L24/N297- | +0.24 | +0.28 | uard scaling real Real 实的 | atop apeutics —an 关键环节 | .×43, ␣×43, 1×43, ,×43, \n×43 |
| L22/N223- | +0.26 | +0.24 | pretty ’. weak 弱 weak | 聚焦 勇往直前 iconic frontline | to×43, .×43, and×43, (×43, ,×43 |
| L23/N370+ | +0.28 | +0.22 | $ .$ ,$ Prem $h | 加拿大的 乐有家 各种各样的 umiejęt | the×43, .×43, and×43, \n×43, ␣×42 |
| L30/N25+ | +0.22 | +0.24 | ' ' </endoftext/> E - A | 1 0 7 2 | .×43, \n×43, ␣×42, 4×42, the×41 |
| L21/N4490+ | +0.24 | +0.23 | requisite indicative initiation substrate resultant | 亦或是 whilst 包括但不限于 Whilst | .×43, ␣×43, 1×43, to×43, the×43 |
| L24/N247+ | +0.25 | +0.21 | Prom isse Capitals Temp temp | industr أردوغان eskort าราง | .×43, \n×43, ␣×42, inel×42, is×42 |

## 3. Progression: neurons whose on-rate grows from the first to the last fifth of the response

Value = on-rate(last fifth) - on-rate(first fifth).

| neuron | harmful (n=41) | harmless (n=130) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L22/N232- | +0.21 | +0.20 | ôn resta odium 维生素 ória | 全心全意 umiejęt 加拿大的 勤勤恳恳 | the×43, .×43, ␣×42, 3×42, and×42 |
| L19/N70+ | +0.18 | +0.14 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 | the×43, is×43, .×43, and×43, ,×43 |
| L22/N552- | +0.10 | +0.14 | “ 果 ， 花果 ，“ | 1 2 6 4 | to×38, the×38, Shield×35, I×34, *×33 |
| L23/N53- | +0.09 | +0.13 | /$ $ 放矢 __.__ av | umiejęt 各种各样的 อย่างไม่ถูกต้อง 加拿大的 | the×40, "×40, .×40, ␣×39, to×39 |
| L18/N751+ | +0.11 | +0.09 | ** ** __ 下面是小编 __ | unclear ysterious entrusted incluso | .×43, ␣×41, **×40, I×39, *×38 |
| L24/N248+ | +0.11 | +0.09 | 不能再 上传者 Challenger agara từng | 管控 共享 shared Shared | a×43, is×43, .×43, and×43, ,×43 |
| L14/N4136+ | +0.10 | +0.09 | --- 下面 在 ---- —— | Крім wikipedia Angeb -strokes | "×35, to×34, the×31, ␣×30, Star×30 |
| L26/N86+ | +0.08 | +0.09 | ' ' </endoftext/> Sloven ’( 其与 | 各种各样 各种各样的 加拿大的 勤勤恳恳 | to×43, a×43, is×43, )×43, ,×43 |
| L13/N4105+ | +0.08 | +0.09 | Anything 作为 既可以 可以是 write | 1 2 3 0 | .×43, \n×43, ␣×42, \n\n×38, *×38 |
| L21/N190- | +0.09 | +0.08 | 交流和 thanks 칭 thanks Thank | 1 the 2 in | .×39, *×36, \n\n×36, \n×35, ,×32 |
| L18/N576+ | +0.08 | +0.08 | were were ____ avu have | 当之 为啥 jub away | .×42, ␣×41, \n×41, the×38, ,×37 |
| L30/N589- | +0.08 | +0.08 | ' ' ' $ ( - | 勤勤恳恳 锦涛 各种各样的 umiejęt | .×43, \n×43, ␣×42, ,×42, I×42 |

## 4. Harmful vs harmless, held out by fold

Pick the 30 keys with the largest harmful - harmless difference on one fold; score each response of the other fold by the mean of those keys; AUC harmful vs harmless. Keys picked on both folds are listed under the table.

| measure | AUC fold0 -> fold1 | AUC fold1 -> fold0 | keys picked on both folds |
|---|---|---|---|
| rise before the event | 0.66 | 0.70 | 6 |
| state (on-rate) | 0.84 | 0.84 | 22 |
| progression (slope) | 0.83 | 0.69 | 15 |

## 4b. Keys picked on both folds: rise before the event

Higher in harmful on both folds independently.

| neuron | harmful (n=41) | harmless (n=130) | writes (steer lens) | reads (S lens) | fires on (token × responses) |
|---|---|---|---|---|---|
| L24/N1233- | +0.06 | +0.01 | seh hes Flow while ingredients | Whilst whilst Whilst 亦或是 | \n\n×153, .×135, \n×132, ␣×75, *×66 |
| L19/N1170- | +0.03 | -0.02 | wait wait Wait Wait WAIT | 晓明 下述 闺女 家风 | .×61, \n×47, to×36, ␣×25, (×23 |
| L31/N1033- | +0.07 | +0.03 | intervista prostitu 姓 Ejem -Semit | https explicitly frontend 平 | .×77, ␣×73, </×70, the×59, _REASON×43 |
| L30/N141- | +0.02 | -0.01 | rather 而不是 but 却不 但没有 | umiejęt 勤勤恳恳 锦涛 上添花 | ING×54, ␣×48, .×43, **×41, (×31 |
| L18/N1944+ | +0.01 | -0.02 | ( (W ( Whoever writable | zcz 下挫 这样一个 惟一 | the×20, ␣×15, `×9, is×8, 4×5 |
| L20/N269+ | +0.03 | +0.00 | vyro ],' as informations established | 假定 chiefly scarcely ordinarily | .×76, 's×38, Let×36, I×35, ,×22 |

## 4b. Keys picked on both folds: state (on-rate)

Higher in harmful on both folds independently.

| neuron | harmful (n=41) | harmless (n=130) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L24/N482+ | +0.36 | +0.28 | active Active 引擎 unless ενε | bespoke 重构 priorit 履职 | a×43, the×43, .×43, )×43, ,×43 |
| L23/N370+ | +0.28 | +0.22 | $ .$ ,$ Prem $h | 加拿大的 乐有家 各种各样的 umiejęt | the×43, .×43, and×43, \n×43, ␣×42 |
| L24/N156+ | +0.19 | +0.14 | each each total Total Each | 绘本 libertine 精准 倒逼 | .×43, \n×43, the×43, is×43, ␣×41 |
| L24/N247+ | +0.25 | +0.21 | Prom isse Capitals Temp temp | industr أردوغان eskort าราง | .×43, \n×43, ␣×42, inel×42, is×42 |
| L19/N70+ | +0.64 | +0.59 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 | the×43, is×43, .×43, and×43, ,×43 |
| L23/N249- | +0.15 | +0.12 | 处理 处理能力 功能区 $ functional | priorit csv 清远 书院 | .×43, ␣×42, *×41, the×41, **×41 |
| L25/N6801- | +0.12 | +0.09 | national classified national National National | 保密 NATO briefing 冷战 | ␣×42, the×42, a×41, security×40, to×39 |
| L21/N268+ | +0.22 | +0.19 | from to 's a them | 1 2 3 0 | .×43, )×43, to×42, is×42, (×42 |
| L19/N1170- | +0.12 | +0.10 | wait wait Wait Wait WAIT | 晓明 下述 闺女 家风 | (×43, .×42, to×41, ,×39, \n×38 |
| L24/N7282- | +0.05 | +0.02 | Operational Denied PLAN 作战 Joint | deployed 纵深 后勤保障 contraint | security×24, American×22, a×21, US×21, operational×20 |
| L25/N449- | +0.16 | +0.14 | seen -, -, inks Through | impactful 打压 Thankfully tweeted | a×43, the×43, I×42, is×41, )×40 |
| L19/N8222- | +0.08 | +0.05 | "/ "% atina 都需要 retro | notwithstanding vaard 督导 好的产品 | .×40, to×39, ␣×38, I×38, my×37 |

## 4b. Keys picked on both folds: progression (slope)

Higher in harmful on both folds independently.

| neuron | harmful (n=41) | harmless (n=130) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L19/N1170- | +0.08 | +0.01 | wait wait Wait Wait WAIT | 晓明 下述 闺女 家风 | (×43, .×42, to×41, ,×39, \n×38 |
| L31/N1033- | +0.10 | +0.04 | intervista prostitu 姓 Ejem -Semit | https explicitly frontend 平 | ING×42, ␣×41, the×41, .×40, to×39 |
| L30/N141- | +0.03 | -0.02 | rather 而不是 but 却不 但没有 | umiejęt 勤勤恳恳 锦涛 上添花 | (×43, 1×41, >×41, **×41, ␣×40 |
| L28/N89- | +0.11 | +0.06 | '\xa0' ' \xa0 \xa0' '\xa0\xa0' '\xa0\xa0\xa0' '\xa0\xa0\xa0\xa0\xa0\xa0\xa0' | airstrikes -Trump تمامًا 勇往直前 | .×43, I×42, *×41, the×41, **×41 |
| L24/N1233- | +0.06 | +0.01 | seh hes Flow while ingredients | Whilst whilst Whilst 亦或是 | .×43, 1×43, \n×43, (×42, ␣×41 |
| L30/N875+ | +0.06 | +0.01 | ■ / reo ' ' ● | 1 0 2 3 | the×42, to×42, \n\n×38, ␣×32, ,×31 |
| L19/N8146- | -0.00 | -0.04 | —" ..." /" " ," | Glyph Gotham 婺源 utility | .×41, ␣×38, \n×37, ,×35, Wait×31 |
| L19/N70+ | +0.18 | +0.14 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 | the×43, is×43, .×43, and×43, ,×43 |
| L21/N268+ | +0.02 | -0.01 | from to 's a them | 1 2 3 0 | .×43, )×43, to×42, is×42, (×42 |
| L21/N143+ | -0.01 | -0.05 | Purtroppo ervations noting >Note 代表着 | 管控 防控 吆 娃 | (×43, and×40, .×39, \n×39, *×38 |
| L20/N269+ | +0.04 | +0.01 | vyro ],' as informations established | 假定 chiefly scarcely ordinarily | .×42, \n×39, I×38, ,×36, >×36 |
| L18/N5411- | +0.04 | +0.00 | \n \n\n ** ' ' :** | 究 rig termed 述 | to×41, the×34, Miller×33, inel×30, )×29 |

## 5. Cascade before the event (median tokens before the event of each rising key's strongest firing in PRE)

| neuron | median tokens before event | responses | writes (steer lens) |
|---|---|---|---|
| L18/N1944+ | 22 | 71 | ( (W ( Whoever writable |
| L19/N1170- | 15 | 150 | wait wait Wait Wait WAIT |
| L22/N552- | 12 | 167 | “ 果 ， 花果 ，“ |
| L20/N269+ | 10 | 136 | vyro ],' as informations established |
| L18/N1809+ | 8 | 149 | Perfil 包括但不限于 perfil 我的 诗句 |
| L18/N429- | 8 | 169 | , \n\n $( /i /x |
| L14/N4136+ | 8 | 149 | --- 下面 在 ---- —— |
| L31/N1033- | 6 | 169 | intervista prostitu 姓 Ejem -Semit |
| L30/N141- | 3 | 162 | rather 而不是 but 却不 但没有 |
| L30/N25+ | 3 | 170 | ' ' </endoftext/> E - A |
| L21/N8828+ | 3 | 159 | _/ IRC $I isses denomination |
| L22/N232- | 2 | 170 | ôn resta odium 维生素 ória |
| L13/N4105+ | 2 | 166 | Anything 作为 既可以 可以是 write |
| L24/N1233- | 1 | 169 | seh hes Flow while ingredients |
| L23/N335- | 1 | 168 | persistent Parish 荔 佬 了一切 |
| L20/N267+ | 1 | 156 | ITHER {% τει types quina |
| L19/N3056- | 1 | 161 | letting let Let Let let |
| L19/N70+ | 1 | 171 | “ **“ ** (“ **" |
