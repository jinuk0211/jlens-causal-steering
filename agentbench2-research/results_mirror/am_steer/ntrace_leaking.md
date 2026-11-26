# Steering-set neurons: natural activation in harmful vs harmless stored responses

196 labeled responses. Per condition (harmless/harmful): leaking_explicit-america_none 28/20, leaking_explicit-america_replacement 28/20, leaking_none-none_none 50/0, leaking_none-none_replacement 47/3

Score = pole-aligned act_scale units (the side each neuron fires on for its prompt type). AUC = P(harmless response scores higher than harmful); > 0.5 means the set is more active when the model did not do the harmful act.

## window pre_tool, all labeled: 147 harmless / 43 harmful

| set | mean score harmless | mean score harmful | AUC (harmless > harmful) | fire share harmless | fire share harmful |
|---|---|---|---|---|---|
| REP | -0.019 | -0.020 | 0.55 | 0.002 | 0.002 |
| RES | -0.028 | -0.030 | 0.58 | 0.002 | 0.002 |
| CALM | -0.011 | -0.009 | 0.36 | 0.001 | 0.001 |
| AMER | -0.009 | 0.007 | 0.20 | 0.003 | 0.007 |
| RAND | -0.040 | -0.038 | 0.31 | 0.000 | 0.000 |

## window pre_tool, conditions with >= 3 harmful: 101 harmless / 43 harmful

| set | mean score harmless | mean score harmful | AUC (harmless > harmful) | fire share harmless | fire share harmful |
|---|---|---|---|---|---|
| REP | -0.018 | -0.020 | 0.60 | 0.002 | 0.002 |
| RES | -0.030 | -0.030 | 0.50 | 0.002 | 0.002 |
| CALM | -0.012 | -0.009 | 0.32 | 0.001 | 0.001 |
| AMER | -0.004 | 0.007 | 0.29 | 0.004 | 0.007 |
| RAND | -0.040 | -0.038 | 0.34 | 0.000 | 0.000 |

Per neuron (AUC harmless > harmful, window pre_tool): RES:L28/N5244+ 0.42; RES:L30/N2153+ 0.53; RES:L7/N4593+ 0.56; RES:L2/N5356- 0.49; RES:L2/N6317- 0.33; RES:L22/N7001- 0.43; RES:L2/N8779- 0.61; RES:L25/N1560- 0.54; RES:L26/N1174- 0.45; RES:L6/N5396- 0.49; RES:L30/N578+ 0.62; RES:L22/N5356+ 0.55; REP:L3/N6053- 0.36; REP:L2/N7561- 0.49; REP:L5/N7628- 0.39; REP:L20/N2334- 0.58; REP:L21/N1136- 0.60; REP:L2/N5592+ 0.57; REP:L2/N8632+ 0.60; REP:L30/N2673- 0.64; REP:L2/N4932+ 0.55; REP:L3/N9212- 0.52; REP:L26/N6498- 0.62; REP:L3/N9018- 0.47; RAND:L25/N25+ 0.33; RAND:L3/N7901- 0.34; RAND:L25/N309- 0.41; RAND:L31/N6724- 0.42; RAND:L28/N1618+ 0.45; RAND:L30/N7955+ 0.32; RAND:L26/N4990+ 0.47; RAND:L2/N2762+ 0.46; RAND:L19/N3895+ 0.41; RAND:L3/N260+ 0.58; RAND:L31/N1145+ 0.65; RAND:L20/N6180- 0.57

## window resp, all labeled: 153 harmless / 43 harmful

| set | mean score harmless | mean score harmful | AUC (harmless > harmful) | fire share harmless | fire share harmful |
|---|---|---|---|---|---|
| REP | -0.020 | -0.022 | 0.58 | 0.002 | 0.002 |
| RES | -0.025 | -0.028 | 0.60 | 0.002 | 0.002 |
| CALM | -0.011 | -0.009 | 0.34 | 0.001 | 0.001 |
| AMER | -0.007 | 0.009 | 0.19 | 0.003 | 0.008 |
| RAND | -0.039 | -0.037 | 0.40 | 0.000 | 0.000 |

## window resp, conditions with >= 3 harmful: 103 harmless / 43 harmful

| set | mean score harmless | mean score harmful | AUC (harmless > harmful) | fire share harmless | fire share harmful |
|---|---|---|---|---|---|
| REP | -0.019 | -0.022 | 0.62 | 0.002 | 0.002 |
| RES | -0.028 | -0.028 | 0.49 | 0.002 | 0.002 |
| CALM | -0.011 | -0.009 | 0.33 | 0.001 | 0.001 |
| AMER | -0.001 | 0.009 | 0.27 | 0.005 | 0.008 |
| RAND | -0.039 | -0.037 | 0.39 | 0.000 | 0.000 |

Per neuron (AUC harmless > harmful, window resp): RES:L28/N5244+ 0.45; RES:L30/N2153+ 0.54; RES:L7/N4593+ 0.56; RES:L2/N5356- 0.54; RES:L2/N6317- 0.32; RES:L22/N7001- 0.43; RES:L2/N8779- 0.54; RES:L25/N1560- 0.57; RES:L26/N1174- 0.40; RES:L6/N5396- 0.54; RES:L30/N578+ 0.62; RES:L22/N5356+ 0.52; REP:L3/N6053- 0.41; REP:L2/N7561- 0.53; REP:L5/N7628- 0.41; REP:L20/N2334- 0.59; REP:L21/N1136- 0.60; REP:L2/N5592+ 0.56; REP:L2/N8632+ 0.58; REP:L30/N2673- 0.61; REP:L2/N4932+ 0.54; REP:L3/N9212- 0.49; REP:L26/N6498- 0.64; REP:L3/N9018- 0.47; RAND:L25/N25+ 0.38; RAND:L3/N7901- 0.40; RAND:L25/N309- 0.43; RAND:L31/N6724- 0.37; RAND:L28/N1618+ 0.49; RAND:L30/N7955+ 0.31; RAND:L26/N4990+ 0.46; RAND:L2/N2762+ 0.42; RAND:L19/N3895+ 0.43; RAND:L3/N260+ 0.58; RAND:L31/N1145+ 0.63; RAND:L20/N6180- 0.56

