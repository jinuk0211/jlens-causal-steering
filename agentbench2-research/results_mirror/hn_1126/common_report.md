# Common misalignment-detecting neurons, T3a (2026-11-26 13:04:12)

Per-neuron AUROC (harmful vs benign) at the decision position. Common = same sign and AUROC >= 0.75 (or <= 0.25) in both folds of every benchmark.

- units (harmful, benign): {'dojo': [85, 229], 'am': [51, 311], 'toolalign': [44, 129]}
- replicating in both folds of one benchmark: {'dojo': 30643, 'am': 47422, 'toolalign': 47262}
- common to all three: **224** (label permutation, 20 runs: mean 0.0, max 0)
- pairs: {'dojo x am': 2662, 'dojo x toolalign': 2135, 'am x toolalign': 4701}; permutation means {'dojo x am': 0.0, 'dojo x toolalign': 0.0, 'am x toolalign': 0.0}

## Leave-one-benchmark-out detection (label-free score on the held-out benchmark)

| held out | K | AUROC | same-layer random mean | random p95 | p |
|---|---|---|---|---|---|
| dojo | 8 | 0.37 | 0.45 | 0.73 | 0.69 |
| dojo | 32 | 0.52 | 0.48 | 0.71 | 0.45 |
| dojo | 128 | 0.74 | 0.45 | 0.71 | 0.03 |
| am | 8 | 0.72 | 0.47 | 0.83 | 0.15 |
| am | 32 | 0.80 | 0.53 | 0.84 | 0.12 |
| am | 128 | 0.66 | 0.57 | 0.84 | 0.38 |
| toolalign | 8 | 0.58 | 0.50 | 0.84 | 0.34 |
| toolalign | 32 | 0.75 | 0.52 | 0.87 | 0.17 |
| toolalign | 128 | 0.59 | 0.49 | 0.82 | 0.34 |

## Top common neurons

| neuron | sign | dojo | am | toolalign | words (+w) | words (-w) |
|---|---|---|---|---|---|---|
| L31/N4740 | - | 0.10 | 0.10 | 0.05 | '滁州' ' Capture' '_capture' '框架' '捕获' '折' 'rec' '犁' | ' fi' 'fi' ' Fi' 'Fi' '-fi' ' FI' 'FI' '(fi' |
| L28/N6471 | + | 0.90 | 0.92 | 0.94 | 'oron' ' nat' 'inton' 'orgen' 'nat' 'atan' ' Morris' ' Griff' | ' Gal' 'Gal' ' gal' 'gal' ' GAL' ' Cop' 'Cop' '伽' |
| L23/N3946 | - | 0.11 | 0.12 | 0.07 | 'SCAN' '哨' 'scan' '民工' '_scan' 'perms' 'SCO' 'نگ' | 'unya' 'emer' ' expectations' '-under' '对准' ' terhadap' '期望' 'bed' |
| L27/N935 | + | 0.86 | 0.86 | 0.92 | ' Patterson' 'گاه' 'ritt' '.ht' 'цах' 'cip' 'enschutz' 'fato' | ' play' ' playing' ' plays' ' played' 'play' ' Play' 'Play' '-play' |
| L1/N3550 | - | 0.16 | 0.14 | 0.16 | " ''" '\n \n' ' ``' ' \\\\' ".''" ' \\"' ' *' ' …' | '“' '‘' '“.' '!”.' '“,' '”' '·' '”，' |
| L26/N9182 | + | 0.83 | 0.86 | 0.93 | ' Sho' '口' 'olec' 'azor' '肢' 'oso' 'oxid' '口镇' | ' clearance' ' cleared' '清' ' clear' ' release' ' Clearance' ' clearing' '清的' |
| L23/N1140 | + | 0.85 | 0.87 | 0.91 | ' sleek' ' elegant' ' crisp' ' smooth' ' vibrant' ' serene' 'smooth' ' sharp' | 'orean' '不住的' '幸' 'urun' '犯规' '复读' 'oman' '失败' |
| L30/N4262 | - | 0.16 | 0.17 | 0.09 | ' secretário' 'stras' 'istro' '��' ' Mok' 'ilton' 'стер' ' Reit' | ' dec' 'dec' ' Dec' 'Dec' '_dec' ' déc' '(dec' '.dec' |
| L23/N8729 | - | 0.17 | 0.05 | 0.13 | ' Ca' ' fusion' ' ves' ' channels' '膜的' ' fus' 'Channel' ' channel' | '端' '劲' '农牧' 'weep' ' Frontier' '勁' 'paramref' 'koch' |
| L22/N4160 | + | 0.87 | 0.88 | 0.89 | '他们都' ' element' '向他们' 'them' '他们都是' '“They' ' chapter' ' page' | ' formats' ' regimes' ' sectors' ' contexts' ' frameworks' ' regions' ' directories' ' sections' |
| L2/N8031 | + | 0.90 | 0.82 | 0.86 | '——' '—.' '_____' '________' '_________' '**.' '**—' '————' | '...' '...*' '...”' '..."' '...</' ' -->' ' ...\\' ' ...' |
| L26/N5630 | - | 0.11 | 0.18 | 0.13 | ' circular' 'Circular' ' Circular' '线' ' cent' 'ettle' ' mon' ' line' | ' r' '(r' '.r' '=r' '[r' '/r' '+r' ',r' |
| L28/N8300 | - | 0.17 | 0.12 | 0.03 | '-l' '-L' ' la' ' La' '_L' '_l' ' ly' ' Ла' | ' strat' '一层' ' Strat' ' layer' ' layers' '三层' '两层' '多层' |
| L30/N6686 | - | 0.14 | 0.18 | 0.15 | ' el' ' El' 'El' '-el' 'el' '_el' '.el' '/el' | 'aglia' ' 대' '战' 'က်' '락' '室' '退役军人' 'wór' |
| L25/N7256 | - | 0.15 | 0.16 | 0.15 | '程序' ' disclosing' ' disclose' ' disclosed' '动态' '程序的' 'Disclosure' '程序和' | 'sson' 'сс' 'son' '録' '衛' 'iona' ' Gunn' '憾' |
| L30/N7091 | + | 0.82 | 0.86 | 0.93 | 'ayan' '化' '翻' 'is' 'ardi' '分许' 'ay' 'dzi' | '一面' 'ята' 'لق' 'alm' 'ovar' 'eworld' ' Соз' '辺' |
| L30/N9197 | + | 0.86 | 0.94 | 0.85 | '主' '主的' '客' '的金' '的主' '_iv' 'kent' 'lenen' | '描' '�' 'are' 'ung' 'ante' '�' '相' '�' |
| L30/N6597 | + | 0.83 | 0.88 | 0.83 | 'ailer' 'untr' '่วง' 'ijnen' 'werker' '威士' ' ere' ' лице' | ' mit' 'mit' ' Mit' ' med' 'Mit' '/mit' ' mitigation' ' MIT' |
| L24/N6530 | + | 0.84 | 0.86 | 0.82 | ' closed' '闭' ' closure' 'closed' ' Closed' '闭合' ' closing' 'Closed' | 'orrent' '�' 'êmio' 'ashi' '掺杂' ' Parc' '鞭' 'гар' |
| L29/N5458 | + | 0.87 | 0.81 | 0.84 | '-c' '_c' '-C' '/c' ',c' '(c' '+c' ' getC' | '批判' ' krit' ' critique' ' Crit' ' critically' 'Crit' ' Critical' ' critical' |
| L28/N4429 | - | 0.18 | 0.14 | 0.09 | ' right' 'right' 'emed' 'ong' 'ziem' '驿' 'xo' ' Fellowship' | 'umbu' ' div' '灶' '不欲' '符' '金子' ' comp' 'udia' |
| L29/N2596 | + | 0.83 | 0.87 | 0.82 | ' sec' ' Sec' 'Sec' 'sec' ' secure' ' secured' ' Secure' 'secure' | '�' 'isha' ' Alv' 'ielo' '乳' 'ervo' 'entras' 'iago' |
| L26/N7643 | + | 0.82 | 0.90 | 0.89 | '设' '設' ' set' 'set' '设在' '-set' '设为' ' Set' | '彤' 'واح' ' predicted' ' predictions' 'predicted' ' assumed' '预测' 'ihad' |
| L5/N2396 | - | 0.14 | 0.13 | 0.19 | '.' ',' '?' ':' '?\\' '?",' ';' '.",' | 'ๆ' ' CENTER' ' «' 'ses' 's' ' Erick' 'eds' ' ´' |
| L26/N5841 | + | 0.87 | 0.86 | 0.91 | ' Stream' '豁' ' Sunshine' ' thread' '凤' 'HA' '/stream' ' Context' | ' Is' '.is' '_is' 'Is' '-is' '/is' ' Iso' ' iso' |
| L30/N9203 | - | 0.17 | 0.19 | 0.09 | 'udo' 'apo' 'usta' ' concent' ' px' 'bara' 'кта' 'cz' | '面' '面の' '面和' '面的' ' face' 'face' 'Face' '利' |
| L1/N8275 | + | 0.85 | 0.82 | 0.88 | '.' '·' '….' '…..' '—.' ',' '�' "'." | ' ``' ' --' ' ``(' " ''" " '''" ' \n        \n' '&quot' ' ---' |
| L25/N1895 | + | 0.84 | 0.83 | 0.95 | 'IRR' 'ubb' ' Maiden' ' Booker' 'rer' '水土' ' Zar' '\\">\\' | ' consumption' ' consumed' 'consum' 'Consum' ' Consumption' ' consume' ' Consum' '消费' |
| L1/N7520 | - | 0.11 | 0.19 | 0.14 | '",' '**,' '**.' '.",' '**:' '‑' '".' 'ly' | '\n\n\n' ' \n\n\n' '\n\n\n\n' ' »*' '\n\n\n\n\n' '\n \n' ' �' '  \n\n\n' |
| L27/N4212 | - | 0.17 | 0.19 | 0.10 | 'mont' 'mount' 'pass' 'pon' ' mount' ' monta' '蒙' ' mont' | '德里' '�' 'sir' ' electro' '剧场' '兌' '艾瑞' 'rebro' |
| L29/N2151 | + | 0.86 | 0.91 | 0.83 | ' gal' ' Gal' 'Gal' 'gal' ' GAL' ' Gall' ' gall' ' gallery' | '笋' 'ฤษ' '攀登' 'ngr' 'ünd' ' เส' '嗜' '範' |
| L27/N8428 | - | 0.12 | 0.18 | 0.17 | ' Pan' 'Pan' ' pan' '_pan' ' Perm' '潘' 'pan' ' PAN' | ' Деп' ' Bud' '苔' '箕' ' Retrie' 'tor' 'roup' 'retrieve' |
| L2/N1906 | + | 0.86 | 0.82 | 0.86 | ' **' " **'" " '**" ' \u200b\u200b' ' **.' ' "**' ' ..' ')**' | '____' '�' '\xad' '�t' '\\"' '\xadt' '\\n' '\xading' |
| L10/N5916 | + | 0.80 | 0.81 | 0.86 | '’' ' barren' ' lacking' ',—' ' drought' '′' ' drunken' '’,' | ' ...' '...' '...</' '...(' '...**' ' ...\\' '...*' ' (...' |
| L28/N5373 | - | 0.13 | 0.18 | 0.12 | ' LIV' 'Liv' '颠' '生活的' 'cou' ' liv' ' Liv' 'feu' | '莫' ' Pilk' '招' ' Recruitment' 'мо' ' recruiting' '招人' ' recr' |
| L3/N4160 | + | 0.82 | 0.84 | 0.86 | ' consort' '在欧洲' ' European' ' programmes' 'Whilst' ' Mediterranean' 'utnik' '不斷的' | '‘' '____' '”' '’t' '“' '’' '\\n' '’m' |
| L0/N13 | - | 0.10 | 0.20 | 0.17 | ' ...\\' '           ' '         ' '                   ' '     ' '...\\' '               ' '                    ' | '(M' '(IM' 'MM' '(mi' 'MMM' '/md' '/MM' ' MM' |
| L21/N4496 | - | 0.17 | 0.12 | 0.19 | ' idea' 'idea' ' Idea' ' ideas' '想法' ' notion' ' prospect' ' ideia' | 'υν' 'ын' '烂' '_else' '榜' ' Excellence' 'ÉN' ' Lung' |
| L24/N3732 | - | 0.16 | 0.09 | 0.20 | ' Disease' ' disease' 'ezd' '病情' 'essen' 'aires' '.std' ' Weight' | ' minor' ' Minor' 'minor' ' scratches' 'Minor' ' scratched' '摔' ' scraped' |
| L2/N8603 | - | 0.11 | 0.13 | 0.20 | ' ___' ' \n\n\n' '...*' '___' ' *“' '  \n\n\n' ' \n    \n' ' \n        \n' | '–' '»,' '».' ',' ').' '»' '.' '»:' |
| L30/N2470 | + | 0.85 | 0.80 | 0.82 | '<>' 'باب' 'TON' 'hui' 'uj' '[^' 'utih' '<>(' | ' as' 'as' ' As' '\tas' '-as' '_as' 'As' '.as' |
| L29/N287 | - | 0.14 | 0.13 | 0.11 | 'Add' 'Cor' 'Dim' 'Light' 'Roll' 'The' 'Ret' 'Sup' | 'wood' 'flow' 'union' 'child' 'view' 'drop' 'auth' 'marker' |
| L30/N5237 | + | 0.81 | 0.84 | 0.91 | '招' ' recruitment' '招募' ' recruiting' ' recruit' ' recruited' ' Recruitment' '招商' | 'rec' '/cop' '罗' 'cp' '提要' 'infeld' 'ock' ' continente' |
| L26/N5454 | - | 0.12 | 0.15 | 0.10 | '盒子' '盒' 'arring' ' Cove' ' accountant' 'ihak' ' Sheikh' 'boxes' | ' progen' ' Pro' 'pro' 'Pro' ' pro' ' Off' ' prog' 'Off' |
| L26/N281 | - | 0.14 | 0.20 | 0.13 | 'hurst' 'haj' '雪糕' '追杀' 'endorf' '驹' 'ドキ' 'antry' | ' solution' ' solutions' '解决方案' ' Solution' 'solution' '解' 'Solution' '解决' |
| L3/N7930 | - | 0.16 | 0.19 | 0.16 | ' ---' ' -*' 'воло' 'ㆍ' '还应当' 'aleigh' ' =>' ' --' | '**' '**:' '**,' '“' ' **' '",' '**.' '**。' |
| L9/N3512 | - | 0.13 | 0.21 | 0.17 | ' luggage' ' fun' ' سود' ' tourist' ' salsa' 'грам' 'tables' 'สนุก' | ' Failed' '?\\' '...**' ' Attempts' '...\\' ' Attempt' '...”' '...).' |
| L19/N8123 | - | 0.17 | 0.15 | 0.18 | ' Exact' ' precise' '的重要依据' '精密' 'Exact' '精确' ' exact' '精准' | ' near' '近' '=min' '_NEAR' ' minimise' '单身' ' nearing' ' vec' |
| L24/N7272 | + | 0.81 | 0.82 | 0.92 | ' soluble' ' writable' 'Readable' '是可' 'usable' ' readable' 'Editable' '可燃' | ' Limits' '.tick' 'onet' 'ticks' 'umenten' 'ikes' ' Rund' ' Terms' |
| L25/N7409 | + | 0.80 | 0.88 | 0.84 | 'Zone' 'world' ' world' ' Hub' ' Zone' 'World' 'Hub' ' World' | 'ohl' 'older' ' lengths' '青' 'yy' ' matching' 'vem' ' alo' |
| L4/N5629 | - | 0.12 | 0.21 | 0.15 | '\n\n\n' '<|endoftext|>' ' stuff' ' --' ' nice' ' %' '\n\n' ' ``' | '**.' '**:' '**,' ' **“' '**。' '**' ' **.' ')**.' |
| L29/N2705 | + | 0.81 | 0.82 | 0.94 | ' se' '被' 'ерна' '就被' 'lest' '修罗' ' being' '就会被' | ' has' ' have' 'has' 'have' ' Have' ' Has' '.has' 'Have' |
| L21/N472 | + | 0.85 | 0.90 | 0.80 | '观察到' '/documents' ' Observ' '看起来' 'remarks' '推荐' 'τον' 'impi' | '归' 'uide' '味' 'ushi' 'ziała' '?\\' '味的' '-transition' |
| L31/N3708 | + | 0.80 | 0.89 | 0.82 | '壁' ' wall' '壁的' '蓋' '炎' '壁上' '板' '盖' | 'zuf' ' flow' '途' ' Flow' 'sun' 'زر' 'ifique' 'ake' |
| L7/N6265 | + | 0.85 | 0.80 | 0.81 | '犯罪行为' ' theater' ' NASCAR' ' theaters' ' halftime' ' storefront' '韩剧' 'aley' | ' pond' ' ponds' ' ——' '‘' '——' ' tiny' ' Pond' ' –' |
| L20/N25 | - | 0.19 | 0.20 | 0.20 | ' **' ' \ufeff' ' ```' '"**' ' **"' '>**' ' **#' '**' | ' tests' ' ' 'tests' '-tests' ' \\(' '\\(' '1' '2' |
| L24/N7224 | - | 0.21 | 0.18 | 0.11 | ' operations' ' flo' ' Operations' ' Flo' ' operation' ' flop' '操作' ' Operation' | 'angnya' 'ukti' ' medium' 'ugs' 'medium' 'adle' 'nock' 'cobra' |
| L24/N658 | - | 0.16 | 0.20 | 0.16 | 'ycyj' 'apper' 'atinum' '이버' 'olini' '暧' '達人' ' Sachen' | '具体' ' specific' '具体的' 'specific' '的具体' '具體' 'Specific' ' Specific' |
| L28/N8050 | - | 0.16 | 0.12 | 0.17 | '极' '極' ' cực' ' extreme' ' 극' ' Cực' ' polar' '至极' | '比较' '比較' '较' '比较高' '比较大' '比较有' '比较小' ' comparison' |
| L11/N7109 | - | 0.17 | 0.10 | 0.19 | ' correlated' ' correlation' '因果关系' '关联性' ' correlations' ' корр' '关联' ' correlate' | '<|endoftext|>' '<|im_end|>' '\n\n' 'itorial' '？' ' Eston' '保留' ' Maritime' |

layers of the top 100: [(30, 14), (28, 9), (26, 9), (2, 7), (24, 7), (29, 6), (31, 5), (25, 5), (27, 4), (1, 4), (23, 3), (3, 3), (21, 3), (7, 3), (22, 2), (5, 2), (10, 2), (0, 2), (9, 2), (19, 2), (4, 2), (20, 2), (11, 1), (6, 1)]
