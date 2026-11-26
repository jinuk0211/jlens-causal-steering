# Distributed decision patterns (Qwen3.5-4B): ToolAlign, AgentDojo, agentic-misalignment

m = max lp(T) - max lp(A) at the CAUSAL-1 decision position (T = target side). k90 and block shares use grad x act; neuron and head rankings use the mean-replacement attribution grad x (act - mu_ref).

## 1. Concentration

| benchmark | class | units | neurons for 90 % of sum abs(grad x act), median [IQR] | % of 294,912 | layers among top-100 (median) |
|---|---|---|---|---|---|
| toolalign | target | 53 | 118605 [115802, 121840] | 40.22 % | 15 |
| toolalign | reference | 120 | 122140 [119360, 123974] | 41.42 % | 17 |
| dojo | target | 85 | 118030 [114557, 120081] | 40.02 % | 16 |
| dojo | reference | 11 | 113978 [112014, 116962] | 38.65 % | 15 |
| am | target | 51 | 120907 [119836, 122515] | 41.00 % | 20 |
| am | reference | 120 | 121560 [118305, 123604] | 41.22 % | 21 |

## 2. Share of abs(attribution) by layer quarter, targets (attention output vs MLP output)

| benchmark | component | L0-7 | L8-15 | L16-23 | L24-31 |
|---|---|---|---|---|---|
| toolalign | attn | 6 % | 7 % | 15 % | 19 % |
| toolalign | mlp | 5 % | 6 % | 11 % | 33 % |
| toolalign | heads: full-attention layers [3, 7, 11, 15, 19, 23, 27, 31] hold 51 % of head abs(attr) | | | | |
| dojo | attn | 6 % | 7 % | 15 % | 22 % |
| dojo | mlp | 5 % | 5 % | 9 % | 30 % |
| dojo | heads: full-attention layers [3, 7, 11, 15, 19, 23, 27, 31] hold 48 % of head abs(attr) | | | | |
| am | attn | 6 % | 8 % | 13 % | 17 % |
| am | mlp | 4 % | 10 % | 11 % | 31 % |
| am | heads: full-attention layers [3, 7, 11, 15, 19, 23, 27, 31] hold 48 % of head abs(attr) | | | | |

## 3. Cross-benchmark overlap (targets): top-200 neurons and top-20 heads

| pair | neurons shared | chance (layer-matched permutation, mean of 500) | p (perm) | heads shared | chance |
|---|---|---|---|---|---|
| toolalign x dojo | 23 | 0.71 | 0.000 | 7 | 2.62 |
| toolalign x am | 20 | 0.70 | 0.000 | 10 | 4.24 |
| dojo x am | 9 | 0.61 | 0.000 | 7 | 2.93 |

- neurons in the top-200 of all 3 benchmarks: 2; heads in the top-20 of all: [(19, 2), (19, 3), (19, 10), (27, 13), (31, 14)]

## 4. Shared neurons and the strongest per benchmark, with J-lens readouts of the output vector (+w)

| neuron | toolalign (target mean) | dojo (target mean) | am (target mean) | readout of +w (top-10) |
|---|---|---|---|---|
| L31/N1948 | +0.0535 | +0.0402 | +0.0318 | [' h', ' n', ' w', '=h', ' li', ' k', ' H', ' N', ' hi', ' W'] |
| L19/N108 | +0.0377 | +0.0410 | +0.0337 | ['********', ' **„', ' **-', '****', ' **【', '**-', '】**', 'sjed', 'ssc', ' **['] |

### strongest in toolalign

| neuron | target mean | reference mean | readout of +w |
|---|---|---|---|
| L31/N1102 | +0.3312 | +0.0063 | ['-w', '威廉', 'wire', 'Wire', ' wing', ' wire', ' wave', ' wedge', 'wave', ' wheel'] |
| L23/N202 | +0.2806 | -0.0128 | [' car', ' CS', ' $', 'カー', ' Ran', ' board', ' café', ' cart', ' fiscal', ' road'] |
| L30/N3149 | +0.2561 | +0.0147 | [' welfare', ' wing', ' wheel', ' William', '�', ' wire', ' widget', ' Wildlife', 'wheel', ' wildlife'] |
| L31/N2324 | +0.2316 | -0.0011 | ['wood', 'ways', 'books', 'house', 'point', 'ball', 'bone', 'mate', 'wright', 'piece'] |
| L26/N423 | +0.2196 | -0.0009 | ['ullet', 'haj', 'enko', 'भाग', ' petrol', ' Coimbra', 'opak', '.FileInputStream', ' plate', '啡'] |
| L31/N417 | +0.2036 | +0.0218 | [' nouvel', 'assemblée', '来来', '资料下载', 'strup', '差别', '建材有限公司', 'grad', 'znacz', '漳州市'] |
| L31/N1505 | +0.1305 | +0.0157 | ['eho', 'esub', 'یک', 'imiento', 'zew', 'يح', 'ษฐ์', 'ి', 'offerta', 'indagine'] |
| L31/N3326 | +0.1216 | +0.0103 | ['ir', 'ib', 'ius', 'ia', 'iom', 'io', 'iol', 'ik', 'iat', 'иб'] |
| L31/N1278 | +0.1149 | -0.0002 | [' aman', ' aven', ' espresso', ' axe', ' undercut', ' avis', ' aper', '非常', ' agon', ' enseign'] |
| L30/N2230 | +0.1147 | +0.0020 | ['/v', 'MW', '/w', 'MV', '/V', 'CW', ' MW', ' VW', 'GV', 'KW'] |
| L29/N574 | +0.1087 | +0.0055 | ['opak', 'enko', '年期', '咳嗽', '用人', 'laces', 'ETHER', '�', ' plate', ' cough'] |
| L31/N3544 | +0.1050 | +0.0030 | [' Audi', '_atomic', ' Anderson', ' Aph', ' Audit', 'Atomic', ' Atomic', '轴向', ' Armor', ' ASCII'] |

### strongest in dojo

| neuron | target mean | reference mean | readout of +w |
|---|---|---|---|
| L31/N383 | +0.2526 | +0.0168 | ['=s', '込み', 'ليم', '的子', '@s', 'гла', 'ไน', '轩', '人民共和国', '庚'] |
| L26/N31 | +0.2286 | -0.0683 | [' $?', ' **【', '？**', '\u3000', '  \n\n\n', ' \n\n\n', '%，', ' _', ' **', ' ${'] |
| L31/N3037 | +0.2248 | +0.0125 | ['حية', 'ño', 'hati', 'has', 'hr', 'hots', 'hlen', 'keh', 'har', 'hon'] |
| L30/N228 | +0.1899 | +0.0023 | ['更新', ' update', ' updates', ' Update', ' updating', 'update', 'Update', ' updated', '更新的', ' Updates'] |
| L27/N344 | +0.1608 | +0.0042 | ['いな', 'olit', 'am', 'akon', 'ie', '구', 'igt', 'ob', 'ak', 'od'] |
| L28/N470 | +0.1237 | +0.0006 | ['_', '_A', '_I', '_<', '_*', '_f', '_B', '_i', '_X', '_"'] |
| L31/N2531 | +0.1236 | -0.0011 | ['st', 'so', 'sc', 'sg', 'sa', 'se', 'ser', 'si', 'sh', 'sm'] |
| L31/N1863 | +0.1218 | +0.0038 | ['_Sh', '肖', 'Sh', '谢', '-St', '-Sh', ' Sh', '_SH', ' Sein', ' Static'] |
| L21/N171 | +0.1214 | -0.0023 | ['[`', ' [`', '[__', '--[', 'tagon', ':__', ' *.*', '.*)', '〔', '."]'] |
| L31/N2326 | +0.1195 | +0.0012 | [' s', ' n', ',s', '=s', '/s', ' S', '.s', ' sm', ' س', '{s'] |
| L22/N52 | +0.1163 | +0.0010 | [' UR', '/U', '(U', ' UF', ' UA', ' UT', 'UU', ' ure', '(Un', ' UC'] |
| L31/N2261 | +0.1108 | +0.0028 | ['峡', '厥', '黄山', '朔', 'olgált', '明珠', '桥区', '通州区', '�', '高桥'] |

### strongest in am

| neuron | target mean | reference mean | readout of +w |
|---|---|---|---|
| L28/N2542 | +0.4070 | -0.0845 | ['(Py', 'Lint', '柯', ' problemlos', ' Sk', '划', ' unkompl', '汝', ' bequem', '茹'] |
| L31/N7604 | +0.3952 | +0.5826 | ['佛', ' bob', ' robot', ' Bob', 'Bob', 'robot', ' Robot', 'Robot', '机器人', ' robots'] |
| L31/N2096 | +0.3052 | +0.0110 | [' sed', ' sem', ' schema', ' sn', '秒', ' sen', ' sal', ' s', ' sh', '社'] |
| L20/N5780 | +0.2531 | +0.1367 | [' official', ' service', ' Service', ' Official', ' Ministry', '官方', ' reporting', 'Service', ' Registry', '_service'] |
| L22/N7350 | +0.2222 | +0.0978 | [' $#', '西班牙语', '去过', '回国', ' (%)', '德语', '国籍', ' indep', '/%', 'Qur'] |
| L24/N583 | +0.2044 | -0.0444 | [' Content', ' mr', ' oslo', ' klaus', ' Contents', ' bau', ' ross', ' copenhagen', ' wy', ' skar'] |
| L30/N4756 | +0.2042 | -0.0780 | ['柯', ' Saunders', 'ək', ' Daniel', ' Thornton', '=tmp', ' Ronnie', ' Robertson', ' Jimmy', '唐'] |
| L29/N1775 | +0.1868 | -0.0510 | [' german', ' british', ' european', ' american', ' russian', ' japanese', ' chinese', ' english', ' americ', ' london'] |
| L29/N1386 | +0.1800 | +0.0421 | ['ape', 'ắng', 'egrad', '中小', 'lend', 'adius', 'uess', 'eneg', 'льти', 'andon'] |
| L27/N1 | +0.1592 | +0.0391 | ['-s', 'se', '_s', '-S', '\xads', 'س', '\ts', '/s', ',s', '.S'] |
| L31/N20 | +0.1483 | +0.1497 | [' in', ' is', ' to', ' the', ' as', ' for', ' on', ' a', ' at', ' with'] |
| L31/N0 | +0.1464 | -0.0163 | ['auer', '窒', ' Envir', ' zeit', ' viviendo', ' burst', '妖', '/', ' instantaneous', '儒'] |

## 5. Top heads per benchmark (mean-replacement attribution, targets)

- toolalign: L27H13 (+1.612), L31H3 (+1.509), L31H14 (+1.370), L27H0 (+1.164), L23H1 (+1.064), L28H21 (+1.063), L19H3 (+0.792), L23H15 (+0.724), L19H10 (+0.705), L22H11 (+0.673), L19H2 (+0.635), L23H11 (+0.586)
- dojo: L31H14 (+0.630), L15H1 (+0.600), L15H2 (+0.561), L31H1 (+0.557), L22H11 (+0.391), L19H3 (+0.370), L19H2 (+0.281), L15H11 (+0.221), L19H10 (+0.210), L15H8 (+0.200), L22H27 (+0.193), L27H13 (+0.177)
- am: L23H15 (+1.425), L19H3 (+0.960), L31H3 (+0.949), L19H2 (+0.806), L15H1 (+0.804), L23H9 (+0.671), L19H12 (+0.570), L27H6 (+0.508), L19H10 (+0.505), L15H2 (+0.482), L19H7 (+0.458), L31H14 (+0.440)

## 6. Layer spread of the top-200 neurons (count per layer quarter)

- toolalign: L0-7: 0, L8-15: 0, L16-23: 73, L24-31: 127
- dojo: L0-7: 6, L8-15: 2, L16-23: 53, L24-31: 139
- am: L0-7: 0, L8-15: 2, L16-23: 102, L24-31: 96
