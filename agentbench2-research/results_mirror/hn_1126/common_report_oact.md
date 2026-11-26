# Common misalignment-detecting neurons, T3a (2026-11-26 13:23:05), position: call onset

Per-neuron AUROC (harmful vs benign) at that position. Common = same sign and AUROC >= 0.75 (or <= 0.25) in both folds of every benchmark.

- units (harmful, benign): {'dojo': [85, 229], 'am': [51, 311]}
- replicating in both folds of one benchmark: {'dojo': 41651, 'am': 38788}
- common to all three: **3621** (label permutation, 20 runs: mean 0.0, max 0)
- pairs: {'dojo x am': 3621}; permutation means {'dojo x am': 0.0}
- ToolAlign with only the aligned non-log targets as benign (harmful, benign units; common neurons; same sign; still >= 0.75): {}

## Leave-one-benchmark-out detection (label-free score on the held-out benchmark)

| held out | K | AUROC | same-layer random mean | random p95 | p |
|---|---|---|---|---|---|
| dojo | 8 | 0.64 | 0.50 | 0.81 | 0.30 |
| dojo | 32 | 0.20 | 0.51 | 0.83 | 0.94 |
| dojo | 128 | 0.45 | 0.49 | 0.78 | 0.60 |
| am | 8 | 0.75 | 0.49 | 0.82 | 0.11 |
| am | 32 | 0.61 | 0.46 | 0.85 | 0.26 |
| am | 128 | 0.46 | 0.50 | 0.81 | 0.54 |

## Top common neurons

| neuron | sign | dojo | am | words (+w) | words (-w) |
|---|---|---|---|---|---|
| L27/N7942 | - | 0.08 | 0.06 | '��' ' NRA' '温' ' NSS' '徽' 'Ce' 'do' '解除' | ' cop' ' block' ' Cop' ' Block' 'block' 'cop' 'Block' '/block' |
| L26/N2954 | + | 0.93 | 0.91 | ' definite' ' Def' ' definit' 'def' ' definitive' '-def' 'Def' ' def' | '.Conn' '薰' 'таж' ' Code' ' codes' '查询' '灾' ' stra' |
| L28/N5257 | - | 0.08 | 0.08 | ' par' 'par' ' Par' '-par' 'Par' '_par' ' пар' ' PAR' | '薪' '沫' 'HEY' 'yiz' ' drip' 'érit' '綴' '温' |
| L25/N6270 | + | 0.91 | 0.92 | ' Mening' 'Sp' ' sp' ' mening' ' Sp' ' exc' '隐藏' 'itas' | '发育' ' developmental' '益' ' dev' '.dev' 'Cong' 'dev' ' Development' |
| L29/N925 | - | 0.08 | 0.05 | 'le' 'l' 'la' 'les' 'lo' 'ls' 'li' 'led' | 'يث' '�' '求是' 'ภัย' 'ivosti' 'quez' 'ationally' '园路' |
| L31/N7153 | + | 0.90 | 0.95 | '市场' ' market' ' Market' '市場' '市场的' 'Market' '市场和' '和市场' | ' Jú' 'craft' '嫌疑' 'itto' 'icke' ' clinic' '舌尖' 'castle' |
| L20/N1429 | + | 0.92 | 0.90 | '鱼' '估计' ' plus' '恕' ' \\"$' ' السم' ' PLUS' '�' | ' discourse' ' narratives' ' neoliberal' '话语' ' masculinity' ' discours' ' spatial' ' textual' |
| L31/N297 | - | 0.09 | 0.10 | 'в' 'с' 'а' ' с' 'Т' 'г' ' С' 'В' | 'Главные' 'сполни' 'рованны' ' обращай' ' лепе' ' сбаланси' ' комплектацию' ' удержи' |
| L29/N732 | + | 0.90 | 0.92 | ' farm' '农' ' Farm' 'Farm' '农民' '農' ' farmer' ' agricultural' | '.shortcuts' ' sinus' 'uyan' 'edin' '赤字' 'ebin' 'BER' 'atan' |
| L29/N1263 | - | 0.10 | 0.08 | 'uvia' 'лт' '斛' ' Barrett' '语法' '弥' 'ouver' 'abee' | 'ign' 'ig' ' Ig' ' Ign' ' ig' 'Ig' 'Ign' 'иг' |
| L27/N1229 | - | 0.09 | 0.09 | ' target' ' Target' 'target' 'Target' ' targets' '目标' '-target' '_target' | '败' 'hana' '颂' 'Rock' '汉族' 'hamster' ' Rock' 'estro' |
| L30/N3560 | - | 0.11 | 0.06 | 'oz' '道的' '回' 'adet' 'odal' ' hào' ' st' '日照' | ' mark' ' val' ' cov' 'mark' 'קה' 'ساب' '}%' 'ál' |
| L31/N6428 | - | 0.08 | 0.06 | '金色' '黄色' '黑色' '蓝色' '红色' '绿色' '金黄色' '巨大' | '适当' '完整' '相同' '相间' '足够' 'eper' '合理' '合适' |
| L31/N62 | + | 0.92 | 0.91 | ' ' '1' ' (' '2' '3' '0' '.' '5' | ' .**' '锦涛' ' autobio' '勤勤恳恳' ' **—' '不应求' ' pupper' ' newcom' |
| L31/N7079 | - | 0.09 | 0.11 | '�' 'она' 'na' '�' '一无' 'ini' 'ana' 'на' | ' nel' ' nei' ' Nel' ' nell' ' nella' 'Nel' ' nelle' ' negli' |
| L23/N1637 | - | 0.09 | 0.06 | ' emerges' ' emerge' ' emerged' ' occurs' ' arises' ' arose' ' occur' ' arise' | '。\\' '认为是' '=<' 'pie' ' διαθέ' '。<' '请填写' '冷落' |
| L24/N1475 | - | 0.10 | 0.10 | 'upas' '燕山' '先来' '病毒' 'assi' ' вируса' ' Viral' 'ziale' | ' correction' ' corrected' '修正' ' corrections' ' adjustment' '调整' ' adjusted' 'adjust' |
| L31/N3222 | - | 0.11 | 0.08 | 'ucs' 'icar' 'ooting' 'ipper' 'uite' 'uyla' 'обо' 'ønn' | 'cy' 'ty' 'pan' 'kit' 'tn' 'ts' 'gon' 'gn' |
| L28/N474 | + | 0.89 | 0.90 | ' numer' '放松' 'opor' 'nolog' 'iedo' 'ifo' ' Ril' ' hor' | '审判' ' court' '法庭' '法院' ' judicial' ' courts' '法官' '判决' |
| L25/N6025 | + | 0.91 | 0.94 | 'ream' 'úb' 'PS' '_exports' '_pm' 'бет' 'STACK' '白玉' | ' Church' 'Church' ' church' '教会' 'church' '教會' ' Churches' ' Kirche' |
| L26/N4680 | + | 0.90 | 0.93 | '碳' ' Carbon' 'Carbon' ' carbon' 'carbon' '炭' ' carbone' ' carbono' | 'cl' ' cl' ' кл' ' clap' '/cl' ' kl' ' clamp' '-cl' |
| L27/N6356 | - | 0.08 | 0.09 | 'วด' '绝地' ' Cath' ' Ngãi' 'lice' '拔' ' ادار' '電池' | ' protein' '蛋白' ' Protein' '蛋白质' 'protein' ' proteins' '蛋白質' ' proteínas' |
| L31/N212 | + | 0.89 | 0.89 | '伊' ' apaixon' ' maravilh' ' naque' ' agradável' '在马' ' daqueles' ' incrível' | ' Consider' ' Proceed' ' Follow' ' Attempt' ' Expect' ' Require' ' Needs' ' Notice' |
| L28/N6143 | + | 0.92 | 0.90 | ' scal' ' Scaling' 'Scaling' ' scaling' 'scaling' '-scal' ' Det' 'órd' | 'ulf' 'bat' 'Ki' ' hydration' 'ick' 'BAT' '邑' ' hydrated' |
| L30/N8796 | + | 0.88 | 0.90 | ' the' 'the' '\tthe' '_the' '.the' 'وار' '(the' ' THE' | '末' '末端' '末尾' '结尾' '末期' ' ending' '开头' '年末' |
| L25/N8735 | - | 0.12 | 0.08 | '现金' ' Collins' 'kas' ' kas' 'CADE' ' cash' ' Cash' 'cash' | ' life' ' Life' 'Life' 'life' ' term' 'term' ' Term' '-life' |
| L29/N953 | + | 0.91 | 0.92 | '事由' '中大' 'rowning' 'avors' 'stel' 'spur' '趟' 'rowned' | ' ambiental' ' spatial' ' primordial' ' nazionale' ' natural' ' locales' ' locale' ' simple' |
| L28/N3683 | + | 0.88 | 0.94 | ' perceived' ' perce' ' perceive' ' perception' ' Perception' ' perceptions' 'Per' ' percep' | ' notice' 'AFF' '宫' ' Madden' ' Foley' 'oto' ' Notices' 'rts' |
| L27/N5686 | + | 0.88 | 0.93 | 'ubl' '彻' 'bli' 'Ki' ' den' ' Ki' '金马' 'рики' | ' Path' '安' '路' 'agod' '_path' 'Path' ' path' '的路' |
| L29/N8723 | + | 0.88 | 0.92 | ' nos' 'nos' ' Nos' 'Nos' ' NOS' '诺' ' NO' 'NO' | ' nas' ' Nas' 'nas' 'jade' ' va' 'Va' 'Wa' ' draft' |
| L24/N2471 | - | 0.09 | 0.11 | 'куль' 'ứ' '�' '宗' ' patented' 'hd' 'ذى' ' Native' | ' cracking' '裂' ' cracked' ' crack' ' cracks' '开裂' '裂纹' '裂缝' |
| L30/N4544 | + | 0.90 | 0.94 | '跟' '他跟' '就跟' '跟自己' '跟人' '跟他' '你跟' '跟你' | ' follows' ' follow' ' Follow' 'follow' ' following' 'Follow' 'following' ' followed' |
| L31/N2910 | - | 0.11 | 0.08 | ' art' ' physics' ' Physics' 'physics' ' chemistry' ' science' 'Physics' ' mathematics' | '耕' '耕地' 'ODA' 'oids' ' voter' ' Ster' '中矩' 'awal' |
| L24/N6186 | + | 0.90 | 0.89 | ' size' ' Size' ' sizes' 'size' 'Size' '大小' '-size' '_size' | 'FINITY' 'cla' ' Gap' 'oux' ' Hath' ' gap' ' clim' '间隔' |
| L28/N3248 | - | 0.12 | 0.07 | ' formal' ' Formal' ' formally' '正式' '正式的' ' رسمی' 'ORMAL' ' officially' | '禧' 'uze' ' pore' 'iad' '.DOM' 'wap' 'Hack' ' traffic' |
| L30/N6579 | - | 0.10 | 0.12 | '寄' '�' 'ords' 'iz' 'ellate' ' Jep' ' Liet' 'لاً' | ' ren' '格' ' Ren' '�' 'ump' '项' '背' 'хів' |
| L24/N7858 | + | 0.92 | 0.90 | ' GPA' ' GP' 'GP' ' transcript' ' IPA' '绩' ' CG' 'CG' | ' Space' ' Mystery' ' Muse' ' Myst' ' Painter' ' Fuj' ' Kemb' ' Litt' |
| L26/N1992 | + | 0.88 | 0.90 | ' pick' ' Pick' ' picking' 'Pick' 'pick' ' picked' ' picks' '_pick' | ' Dol' '熔' '�' ' spre' 'olon' '�' 'elius' ' sleeves' |
| L27/N1595 | - | 0.12 | 0.09 | 'vl' 'BL' '白' '�' 'VL' '-money' 'qd' '腹' | 'ทาง' 'ological' 'เชิง' 'etical' 'istical' 'ทางการ' 'lical' ' tactical' |
| L31/N1570 | - | 0.11 | 0.06 | '对应' ' correspond' ' Correspond' ' corresponding' '对应的' ' corresponds' ' correspondence' ' corres' | 'omo' 'untu' ' rehearsal' '渔' 'ędzie' '荸' 'ortal' '�' |
| L30/N4170 | - | 0.12 | 0.09 | '坞' '�' 'fan' 'ls' 'lo' 'lecture' 'ilen' 'lz' | 'eli' 'BI' ' el' 'oi' 'qui' ' oi' '刺耳' ' ol' |
| L29/N7803 | - | 0.07 | 0.09 | ' te' ' Te' '-te' 'Te' '(te' ' TE' '.te' 'te' | 'ár' ' sel' 'ebilecek' ' Trident' ' star' 'kul' 'utr' 'len' |
| L30/N506 | + | 0.92 | 0.89 | ' mag' ' Mag' 'mag' 'Mag' '磁' '_mag' ' magnetic' ' маг' | '翁' 'odka' '年终奖' 'athon' '公厕' 'undial' ' đẻ' 'ρυθ' |
| L24/N340 | + | 0.90 | 0.92 | '印度' ' Indian' ' India' 'India' 'Indian' '印度的' ' Indians' ' indian' | '紫' '�' '侍' '�' 'wich' '.lu' 'zure' ' كوب' |
| L31/N2591 | - | 0.08 | 0.13 | ' /' ' /\\' '(/' ' (/' ' /.' ' ／' ' `/' '／' | '且在' ' تبع' 'orc' '&E' '+B' '+E' '&B' '+l' |
| L23/N3008 | - | 0.12 | 0.10 | '刻意' '一鸣' ' deliberate' ' improv' '间隔' 'olta' '二' ' cod' | ' motivasi' ' motiv' 'Mot' ' motivational' ' motivating' ' cigarette' ' Mot' ' motivation' |
| L30/N1195 | + | 0.90 | 0.88 | 'avax' '烟' 'illant' 'ogos' 'azing' 'क्ट' 'illi' 'azionali' | '自由' '的自由' ' free' '自由的' ' Free' ' freedom' ' freely' 'free' |
| L31/N2662 | - | 0.09 | 0.12 | '菅' '二郎' ' Campbell' '酪' ' Angus' ' Baxter' '公路' '民工' | ' token' ' Token' 'Token' ' Jew' ' tokens' 'token' ' Tokens' '/token' |
| L26/N6293 | + | 0.90 | 0.91 | 'rafa' 'agan' ' stamps' '螺旋' 'isional' ' Staf' ' Stamp' ' mik' | ' fat' ' Fat' 'Fat' 'fat' '肥' '-fat' 'Ju' '脂肪' |
| L29/N5582 | + | 0.89 | 0.91 | ' early' '早期' ' Early' 'early' 'Early' '早' '早期的' '早早' | 'ipa' 'ép' '沛' ' pb' 'imba' 'Vit' ' Ov' 'iev' |
| L27/N2908 | + | 0.89 | 0.88 | '四人' '第四' '四' '九' '四个' '这四个' '四是' '这四' | '零八' 'inka' 'hirt' '³' ' StatusBar' ' Brug' '八十' 'اض' |
| L21/N4787 | + | 0.89 | 0.90 | '對外' 'idor' ' exterior' ' externally' 'ood' 'indows' 'Extern' '外链' | '獻' '承' '推崇' '奉' '如果发现' '圭' 'ักษ์' '/rules' |
| L27/N8238 | + | 0.90 | 0.92 | ' Jong' '.blob' '摩' 'moc' ' Jab' 'JC' 'cer' 'ubo' | 'ahn' 'hek' ' Orth' 'ANS' ' Thal' 'anser' 'uth' '寒气' |
| L30/N1618 | + | 0.88 | 0.88 | 'ungkap' 'ؤسسات' 'betrag' '琐' '.rawQuery' 'менов' 'кров' 'OutOfRange' | 'g' '-g' '_g' 'G' 'گ' 'gs' 'gh' 'ɡ' |
| L30/N7548 | - | 0.10 | 0.10 | '不成' '�' '票' '云飞' 'יתי' '影子' '套件' '影' | ' str' 'str' ' Str' 'Str' '(str' '_str' '-str' '.str' |
| L28/N3726 | + | 0.92 | 0.91 | 'arak' '暇' 'luž' 'gut' 'eluk' '大华' '余人次' 'icit' | 'O' 'o' ' O' 'SO' '[o' 'AO' 'CO' 'ZO' |
| L27/N6439 | - | 0.10 | 0.11 | 'HD' '魔' ' HD' 'жды' '魔力' '冲' ' mag' 'imer' | 'crement' '菲特' ' zp' 'bcc' '勤勉' 'inkin' 'pcf' '未央' |
| L28/N5083 | - | 0.13 | 0.09 | '芜' 'rane' '校准' '对应' '-scrollbar' 'inges' 'oggle' ' Lov' | ' identity' ' Identity' 'Identity' 'identity' ' identities' '_identity' '身份' '.identity' |
| L28/N1928 | - | 0.13 | 0.12 | ' reported' ' reporting' '报告' '报道' ' report' '描述' ' documented' ' reports' | ' rep' '-re' ' Rep' 'Rep' '_rep' 'rep' ' REP' 'REP' |
| L31/N9145 | + | 0.90 | 0.87 | 'illen' 'ill' 'ضم' 'box' 'illy' 'ahl' 'oten' 'oker' | 'uta' ' halfway' 'ists' '具' 'statt' 'urge' 'urg' 'ent' |

layers of the top 100: [(31, 19), (28, 16), (29, 15), (27, 11), (30, 11), (24, 10), (26, 7), (25, 4), (23, 4), (20, 1), (21, 1), (19, 1)]
