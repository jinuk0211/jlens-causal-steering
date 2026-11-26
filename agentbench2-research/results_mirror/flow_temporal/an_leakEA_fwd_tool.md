# Neuron-flow patterns while the model writes its response (agentic-misalignment, scenarios ['leaking'], event = tool)

Responses used: 44 (harmful 33, harmless 11); skipped {}. Response part = onset .. event (needs >= 192 tokens). 'On' = in the layer's top-16 with |score| >= 1.0. 259608 keys seen.

## 1. Approach pattern: neurons that rise before the action in all responses

Value = mean (on-rate in the 64 tokens before the event - on-rate earlier in the response).

| neuron | harmful (n=33) | harmless (n=11) | writes (steer lens) | reads (S lens) | fires on (token × responses) |
|---|---|---|---|---|---|
| L14/N4136+ | +0.10 | +0.06 | --- 下面 在 ---- —— | Крім wikipedia Angeb -strokes | .×21, ␣×17, to×14, ,×9, \n×9 |
| L13/N4105+ | +0.09 | +0.07 | Anything 作为 既可以 可以是 write | 1 2 3 0 | \n×37, .×32, \n\n×22, ␣×16, 's×12 |
| L18/N429- | +0.07 | +0.10 | , \n\n $( /i /x | 维权 秉持 退市 renom | .×31, 's×13, \n×13, Let×12, I×11 |
| L19/N70+ | +0.07 | +0.10 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 | .×41, the×40, to×33, \n\n×31, ␣×29 |
| L30/N25+ | +0.10 | +0.02 | ' ' </endoftext/> E - A | 1 0 7 2 | \n×34, .×33, to×21, ␣×18, \n\n×15 |
| L21/N190- | +0.09 | +0.05 | 交流和 thanks 칭 thanks Thank | 1 the 2 in | .×36, \n×33, \n\n×22, *×18, ␣×13 |
| L18/N1809+ | +0.08 | +0.06 | Perfil 包括但不限于 perfil 我的 诗句 | 小哥 acredito 唯一一个 小分队 | \n×30, .×28, \n\n×22, Let×9, *×8 |
| L25/N2911- | +0.07 | +0.06 | 执行 execution Execution Execution 执行的 | 执行力 脚踏实 扎克 团战 | \n×24, \n\n×23, ␣×18, .×16, 's×13 |
| L23/N302- | +0.08 | +0.03 | Per per histor historical وغ | aforementioned dikarenakan 前往 entirety | .×39, \n×35, ␣×26, \n\n×22, I×21 |
| L21/N8828+ | +0.07 | +0.05 | _/ IRC $I isses denomination | 1 3 honor 2 | .×30, \n×28, \n\n×23, will×10, I×9 |
| L30/N22+ | +0.08 | +0.01 | п 跻 尾声 а 再从 | 产自 {name xr 但不能 | ␣×21, \n\n×18, \n×14, >×13, </×11 |
| L22/N232- | +0.06 | +0.06 | ôn resta odium 维生素 ória | 全心全意 umiejęt 加拿大的 勤勤恳恳 | .×43, the×35, \n×28, ␣×28, \n\n×26 |

## 2. Persistent state neurons over the response (on-rate)

Value = mean on-rate from the response start to the event.

| neuron | harmful (n=33) | harmless (n=11) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L19/N70+ | +0.63 | +0.65 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 | of×44, as×44, is×44, to×44, .×44 |
| L22/N232- | +0.34 | +0.36 | ôn resta odium 维生素 ória | 全心全意 umiejęt 加拿大的 勤勤恳恳 | "×44, .×44, and×44, ,×44, \n×44 |
| L24/N482+ | +0.35 | +0.30 | active Active 引擎 unless ενε | bespoke 重构 priorit 履职 | "×44, .×44, and×44, ,×44, is×44 |
| L30/N589- | +0.32 | +0.32 | ' ' ' $ ( - | 勤勤恳恳 锦涛 各种各样的 umiejęt | is×44, .×44, interests×44, )×44, ,×44 |
| L26/N86+ | +0.31 | +0.33 | ' ' </endoftext/> Sloven ’( 其与 | 各种各样 各种各样的 加拿大的 勤勤恳恳 | is×44, to×44, a×44, American×44, ,×44 |
| L24/N248+ | +0.30 | +0.29 | 不能再 上传者 Challenger agara từng | 管控 共享 shared Shared | is×44, to×44, .×44, \n×44, )×44 |
| L23/N370+ | +0.28 | +0.24 | $ .$ ,$ Prem $h | 加拿大的 乐有家 各种各样的 umiejęt | .×44, and×44, ,×44, is×44, American×44 |
| L22/N223- | +0.26 | +0.25 | pretty ’. weak 弱 weak | 聚焦 勇往直前 iconic frontline | .×44, and×44, ,×44, (×44, interests×44 |
| L24/N247+ | +0.25 | +0.21 | Prom isse Capitals Temp temp | industr أردوغان eskort าราง | "×44, .×44, ,×44, is×44, to×44 |
| L30/N25+ | +0.23 | +0.23 | ' ' </endoftext/> E - A | 1 0 7 2 | Star×43, 1×43, .×43, American×43, \n×43 |
| L24/N297- | +0.23 | +0.22 | uard scaling real Real 实的 | atop apeutics —an 关键环节 | .×44, and×44, ,×44, \n×44, the×44 |
| L21/N268+ | +0.22 | +0.22 | from to 's a them | 1 2 3 0 | )×44, .×43, ,×43, is×43, to×43 |

## 3. Progression: neurons whose on-rate grows from the first to the last fifth of the response

Value = on-rate(last fifth) - on-rate(first fifth).

| neuron | harmful (n=33) | harmless (n=11) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L22/N232- | +0.21 | +0.21 | ôn resta odium 维生素 ória | 全心全意 umiejęt 加拿大的 勤勤恳恳 | "×44, .×44, and×44, ,×44, \n×44 |
| L19/N70+ | +0.19 | +0.19 | “ **“ ** (“ **" | 亦或是 entirety anyways 更加的 | of×44, as×44, is×44, to×44, .×44 |
| L18/N751+ | +0.11 | +0.13 | ** ** __ 下面是小编 __ | unclear ysterious entrusted incluso | .×44, I×43, ␣×43, ,×42, to×42 |
| L28/N89- | +0.11 | +0.11 | '\xa0' ' \xa0 \xa0' '\xa0\xa0' '\xa0\xa0\xa0' '\xa0\xa0\xa0\xa0\xa0\xa0\xa0' | airstrikes -Trump تمامًا 勇往直前 | .×44, ,×44, I×44, the×43, \n×42 |
| L22/N552- | +0.10 | +0.12 | “ 果 ， 花果 ，“ | 1 2 6 4 | American×44, to×41, the×41, Shield×39, I×39 |
| L21/N190- | +0.10 | +0.11 | 交流和 thanks 칭 thanks Thank | 1 the 2 in | .×43, \n×41, *×40, \n\n×36, ␣×35 |
| L31/N1033- | +0.10 | +0.09 | intervista prostitu 姓 Ejem -Semit | https explicitly frontend 平 | the×44, ,×43, ING×42, ␣×42, .×41 |
| L14/N4136+ | +0.09 | +0.10 | --- 下面 在 ---- —— | Крім wikipedia Angeb -strokes | "×41, Star×38, to×37, ␣×35, inel×34 |
| L23/N53- | +0.09 | +0.11 | /$ $ 放矢 __.__ av | umiejęt 各种各样的 อย่างไม่ถูกต้อง 加拿大的 | "×44, .×44, ,×44, is×44, to×44 |
| L24/N248+ | +0.10 | +0.08 | 不能再 上传者 Challenger agara từng | 管控 共享 shared Shared | is×44, to×44, .×44, \n×44, )×44 |
| L22/N341+ | +0.09 | +0.08 | z too is takes was | Harbor 曾经的 打造 ambang | "×44, .×44, and×44, ,×44, American×44 |
| L24/N510- | +0.08 | +0.11 | .$ $ '\xa0' ，《 $( | anyways effortlessly Hadir simplistic | ␣×41, .×41, *×37, ,×37, \n×37 |

## 4. Harmful vs harmless, held out by fold

Pick the 30 keys with the largest harmful - harmless difference on one fold; score each response of the other fold by the mean of those keys; AUC harmful vs harmless. Keys picked on both folds are listed under the table.

| measure | AUC fold0 -> fold1 | AUC fold1 -> fold0 | keys picked on both folds |
|---|---|---|---|
| rise before the event | 0.76 | 0.77 | 9 |
| state (on-rate) | 0.89 | 0.64 | 13 |
| progression (slope) | 0.37 | 0.48 | 5 |

## 4b. Keys picked on both folds: rise before the event

Higher in harmful on both folds independently.

| neuron | harmful (n=33) | harmless (n=11) | writes (steer lens) | reads (S lens) | fires on (token × responses) |
|---|---|---|---|---|---|
| L19/N1170- | +0.03 | -0.06 | wait wait Wait Wait WAIT | 晓明 下述 闺女 家风 | \n×21, .×18, to×16, ␣×13, (×8 |
| L30/N25+ | +0.10 | +0.02 | ' ' </endoftext/> E - A | 1 0 7 2 | \n×34, .×33, to×21, ␣×18, \n\n×15 |
| L30/N22+ | +0.08 | +0.01 | п 跻 尾声 а 再从 | 产自 {name xr 但不能 | ␣×21, \n\n×18, \n×14, >×13, </×11 |
| L20/N267+ | +0.07 | +0.01 | ITHER {% τει types quina | 受邀 食材 priorit hardcoded | \n\n×25, >×16, </think>×13, </×12, PAD×11 |
| L20/N5209- | +0.05 | -0.01 | [...] tracks 主体工程 yms yme | Wikipedia ISBN ensen isch | to×13, ␣×13, 2×8, ID×7, forward×7 |
| L30/N875+ | +0.05 | -0.00 | ■ / reo ' ' ● | 1 0 2 3 | \n\n×30, >×16, </think>×13, .×13, ␣×12 |
| L24/N1233- | +0.07 | +0.01 | seh hes Flow while ingredients | Whilst whilst Whilst 亦或是 | \n×40, .×37, \n\n×32, ␣×24, *×21 |
| L16/N7633- | +0.06 | +0.01 | </endoftext/> \n\n " \n\n \n\n | 最终 亦或是 共计 balanced | \n\n×17, >×15, </think>×13, </×12, SCR×10 |
| L18/N751+ | +0.03 | -0.00 | ** ** __ 下面是小编 __ | unclear ysterious entrusted incluso | .×32, ␣×27, *×15, \n×13, ,×12 |

## 4b. Keys picked on both folds: state (on-rate)

Higher in harmful on both folds independently.

| neuron | harmful (n=33) | harmless (n=11) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L24/N482+ | +0.35 | +0.30 | active Active 引擎 unless ενε | bespoke 重构 priorit 履职 | "×44, .×44, and×44, ,×44, is×44 |
| L23/N370+ | +0.28 | +0.24 | $ .$ ,$ Prem $h | 加拿大的 乐有家 各种各样的 umiejęt | .×44, and×44, ,×44, is×44, American×44 |
| L24/N247+ | +0.25 | +0.21 | Prom isse Capitals Temp temp | industr أردوغان eskort าราง | "×44, .×44, ,×44, is×44, to×44 |
| L25/N449- | +0.17 | +0.14 | seen -, -, inks Through | impactful 打压 Thankfully tweeted | the×44, a×44, I×44, to×43, 's×43 |
| L19/N1373+ | +0.12 | +0.09 | presently </endoftext/> currently current its | 首个 iconic alongside 相较于 | .×44, and×44, interests×44, 1×43, ,×43 |
| L23/N329+ | +0.14 | +0.12 | Heritage heritage hasta until -relative | impactful 相较于 relocated aligned | to×44, .×43, \n×43, **×43, I×43 |
| L31/N4128+ | +0.12 | +0.09 | 适于 deline 阐释 又没有 대해서 | atop bespoke 相较 相较于 | the×44, security×44, to×43, a×43, an×42 |
| L24/N146+ | +0.09 | +0.07 | ‘ overall sé disc ‘ | ceasefire 首个 薪资 剧集 | .×44, ,×44, \n×43, the×43, ␣×43 |
| L17/N46- | +0.10 | +0.08 | as (...) <i  Google | 首个 iconic 仅需 精准 | .×44, \n×44, the×44, (×43, **×43 |
| L18/N168+ | +0.11 | +0.09 | 臂 ums erez 谷歌 vr | umiejęt 不及待 unveil รีส | .×44, my×44, the×44, a×44, 's×44 |
| L26/N1474+ | +0.13 | +0.11 | 之中的 或者其他 之后 之后的 之中 | 还没有 可以自由 叫做 不得不 | (×44, to×44, and×43, ,×43, of×41 |
| L24/N220- | +0.20 | +0.18 | 而是因为 及其自动化 规划 eggio _consumer | 乐有家 déro 勇往直前 勤勤恳恳 | and×44, ,×44, is×44, the×44, a×44 |

## 4b. Keys picked on both folds: progression (slope)

Higher in harmful on both folds independently.

| neuron | harmful (n=33) | harmless (n=11) | writes (steer lens) | reads (S lens) | fires on (token × responses, 40-response sample) |
|---|---|---|---|---|---|
| L24/N156+ | -0.02 | -0.06 | each each total Total Each | 绘本 libertine 精准 倒逼 | .×44, ,×44, is×44, the×44, I×44 |
| L17/N1553- | +0.01 | -0.03 | wait Wait Wait wait 等待 | 坚定理想信念 聚焦 iconic identifiers | .×43, if×43, (×42, ,×41, \n×40 |
| L24/N482+ | -0.17 | -0.21 | active Active 引擎 unless ενε | bespoke 重构 priorit 履职 | "×44, .×44, and×44, ,×44, is×44 |
| L17/N4369- | +0.00 | -0.03 | And and 以及 And AND | 甚至是 亦或是 非常的 每一位 | .×44, \n×43, ,×42, )×39, ).×36 |
| L23/N200- | +0.03 | +0.00 | probably maybe 衅 maybe Maybe | 挖掘公司 umiejęt 俱乐部 各种各样的 | my×44, to×44, I×44, are×44, and×43 |

## 5. Cascade before the event (median tokens before the event of each rising key's strongest firing in PRE)

| neuron | median tokens before event | responses | writes (steer lens) |
|---|---|---|---|
| L19/N1170- | 12 | 44 | wait wait Wait Wait WAIT |
| L20/N5209- | 12 | 35 | [...] tracks 主体工程 yms yme |
| L18/N751+ | 10 | 42 | ** ** __ 下面是小编 __ |
| L14/N4136+ | 6 | 39 | --- 下面 在 ---- —— |
| L25/N2911- | 5 | 40 | 执行 execution Execution Execution 执行的 |
| L18/N1809+ | 5 | 33 | Perfil 包括但不限于 perfil 我的 诗句 |
| L18/N429- | 5 | 44 | , \n\n $( /i /x |
| L30/N22+ | 4 | 42 | п 跻 尾声 а 再从 |
| L23/N302- | 3 | 43 | Per per histor historical وغ |
| L21/N8828+ | 3 | 38 | _/ IRC $I isses denomination |
| L21/N190- | 3 | 42 | 交流和 thanks 칭 thanks Thank |
| L13/N4105+ | 3 | 43 | Anything 作为 既可以 可以是 write |
| L30/N25+ | 2 | 44 | ' ' </endoftext/> E - A |
| L22/N232- | 2 | 44 | ôn resta odium 维生素 ória |
| L30/N875+ | 1 | 44 | ■ / reo ' ' ● |
| L24/N1233- | 1 | 43 | seh hes Flow while ingredients |
| L20/N267+ | 1 | 35 | ITHER {% τει types quina |
| L19/N70+ | 1 | 44 | “ **“ ** (“ **" |
| L16/N7633- | 1 | 30 | </endoftext/> \n\n " \n\n \n\n |
