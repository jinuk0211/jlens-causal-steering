# J-lens layer-pattern mining: full unsteered tau2 (airline 50 + retail 114 + telecom 114)

- counts: {"W_clean": {"airline_good": 26, "airline_bad": 22, "retail_good": 135, "retail_bad": 9, "telecom_good": 88, "telecom_bad": 9}, "W_all": {"airline_good": 33, "airline_bad": 43, "retail_good": 156, "retail_bad": 25, "telecom_good": 95, "telecom_bad": 61}}

## W_clean

| score | AUC (out-of-fold) | 95% CI | airline | retail | telecom |
|---|---|---|---|---|---|
| A_pairs | 0.741 | [0.658, 0.825] | 0.641 | 0.695 | 0.768 |
| B_family | 0.66 | [0.567, 0.756] | 0.718 | 0.68 | 0.612 |
| C_rev20_rate | 0.589 | [0.5, 0.686] | 0.668 | 0.623 | 0.742 |
| C_commit_mean | 0.467 | [0.349, 0.589] | 0.264 | 0.379 | 0.787 |
| C_late_commit_rate | 0.481 | [0.376, 0.585] | 0.276 | 0.371 | 0.773 |

- B: (family, layer) chosen per fold: [('refusal', 19), ('refusal', 19), ('refusal', 21), ('refusal', 21), ('refusal', 22)]
- A: layer histogram of the 30 full-fit pairs: {"3": 1, "4": 1, "15": 1, "16": 2, "17": 2, "21": 2, "22": 3, "23": 3, "24": 3, "25": 3, "26": 2, "27": 1, "28": 1, "29": 2, "30": 2, "31": 1}

| layer | word | bad rate | good rate | log ratio | folds |
|---|---|---|---|---|---|
| L31 | 'At' | 0.25 | 0.0 | 3.26 | 5/5 |
| L21 | ' Honestly' | 0.3 | 0.004 | 3.1 | 5/5 |
| L29 | ' Given' | 0.375 | 0.008 | 3.06 | 5/5 |
| L29 | 'Given' | 0.375 | 0.008 | 3.06 | 5/5 |
| L23 | ' Ack' | 0.375 | 0.008 | 3.06 | 5/5 |
| L24 | ' sincerely' | 0.2 | 0.0 | 3.04 | 4/5 |
| L23 | ' Recogn' | 0.2 | 0.0 | 3.04 | 4/5 |
| L25 | ' Recogn' | 0.2 | 0.0 | 3.04 | 4/5 |
| L30 | 'Unable' | 0.25 | 0.004 | 2.92 | 4/5 |
| L24 | ' recognizing' | 0.175 | 0.0 | 2.92 | 4/5 |
| L28 | ' Given' | 0.35 | 0.012 | 2.79 | 3/5 |
| L23 | ' recognizing' | 0.15 | 0.0 | 2.77 | 2/5 |
| L21 | ' heartbreaking' | 0.15 | 0.0 | 2.77 | 4/5 |
| L26 | ' Honestly' | 0.2 | 0.004 | 2.71 | 4/5 |
| L22 | ' acknowledge' | 0.2 | 0.004 | 2.71 | 2/5 |
| L26 | ' sincerely' | 0.2 | 0.004 | 2.71 | 2/5 |
| L30 | ' Given' | 0.2 | 0.004 | 2.71 | 2/5 |
| L15 | '.......' | 0.25 | 0.008 | 2.67 | 2/5 |
| L22 | ' acknowledges' | 0.25 | 0.008 | 2.67 | 3/5 |
| L22 | ' Ack' | 0.3 | 0.012 | 2.64 | 2/5 |
| L27 | ' zrozum' | 0.3 | 0.012 | 2.64 | 1/5 |
| L25 | ' begrij' | 0.35 | 0.016 | 2.63 | 2/5 |
| L17 | '  \r\n\r\n' | 0.125 | 0.0 | 2.6 | 2/5 |
| L25 | ' Honestly' | 0.125 | 0.0 | 2.6 | 0/5 |
| L4 | '科学院' | 0.125 | 0.0 | 2.6 | 1/5 |
| L3 | ' Washington' | 0.125 | 0.0 | 2.6 | 1/5 |
| L16 | ' acknowledgment' | 0.125 | 0.0 | 2.6 | 1/5 |
| L24 | ' recognize' | 0.125 | 0.0 | 2.6 | 1/5 |
| L16 | ' unable' | 0.125 | 0.0 | 2.6 | 2/5 |
| L17 | ' couldn' | 0.125 | 0.0 | 2.6 | 2/5 |

family AUC by layer (decision point, higher rank = more present):

| family | L0 | L4 | L8 | L12 | L16 | L20 | L24 | L28 | best layer |
|---|---|---|---|---|---|---|---|---|---|
| refusal | 0.5 | 0.5 | 0.51 | 0.61 | 0.68 | 0.71 | 0.67 | 0.59 | L22 0.744 |
| hesitate | 0.29 | 0.61 | 0.53 | 0.61 | 0.44 | 0.47 | 0.38 | 0.37 | L4 0.611 |
| verify | 0.5 | 0.5 | 0.5 | 0.46 | 0.49 | 0.34 | 0.44 | 0.38 | L0 0.5 |
| ask | 0.5 | 0.51 | 0.4 | 0.52 | 0.53 | 0.51 | 0.41 | 0.39 | L9 0.651 |
| transfer | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.51 | 0.53 | L31 0.585 |
| error | 0.5 | 0.5 | 0.5 | 0.5 | 0.52 | 0.52 | 0.51 | 0.48 | L19 0.53 |

## W_all

| score | AUC (out-of-fold) | 95% CI | airline | retail | telecom |
|---|---|---|---|---|---|
| A_pairs | 0.684 | [0.638, 0.733] | 0.764 | 0.711 | 0.61 |
| B_family | 0.695 | [0.637, 0.748] | 0.794 | 0.648 | 0.492 |
| C_rev20_rate | 0.649 | [0.587, 0.705] | 0.68 | 0.477 | 0.712 |
| C_commit_mean | 0.477 | [0.406, 0.541] | 0.179 | 0.221 | 0.773 |
| C_late_commit_rate | 0.477 | [0.409, 0.545] | 0.192 | 0.211 | 0.772 |

- B: (family, layer) chosen per fold: [('refusal', 19), ('refusal', 19), ('refusal', 19), ('refusal', 19), ('refusal', 19)]
- A: layer histogram of the 30 full-fit pairs: {"8": 1, "21": 3, "22": 5, "23": 2, "24": 8, "25": 3, "26": 3, "27": 2, "29": 2, "31": 1}

| layer | word | bad rate | good rate | log ratio | folds |
|---|---|---|---|---|---|
| L24 | ' recognizing' | 0.147 | 0.0 | 2.76 | 5/5 |
| L22 | ' acknowledge' | 0.186 | 0.004 | 2.67 | 4/5 |
| L23 | ' Ack' | 0.233 | 0.007 | 2.66 | 3/5 |
| L23 | ' Recogn' | 0.124 | 0.0 | 2.6 | 4/5 |
| L25 | ' Recogn' | 0.124 | 0.0 | 2.6 | 4/5 |
| L22 | ' acknowledges' | 0.217 | 0.007 | 2.59 | 3/5 |
| L27 | ' zrozum' | 0.264 | 0.011 | 2.59 | 5/5 |
| L21 | ' Ack' | 0.163 | 0.004 | 2.55 | 3/5 |
| L24 | ' compréhension' | 0.295 | 0.014 | 2.54 | 5/5 |
| L24 | ' sincerely' | 0.116 | 0.0 | 2.54 | 4/5 |
| L31 | 'At' | 0.116 | 0.0 | 2.54 | 3/5 |
| L29 | ' Given' | 0.202 | 0.007 | 2.52 | 4/5 |
| L24 | '的理解' | 0.287 | 0.014 | 2.51 | 4/5 |
| L8 | ' Hawaii' | 0.155 | 0.004 | 2.5 | 2/5 |
| L26 | ' comprendere' | 0.155 | 0.004 | 2.5 | 2/5 |
| L25 | '深刻理解' | 0.279 | 0.014 | 2.49 | 2/5 |
| L25 | ' comprender' | 0.279 | 0.014 | 2.49 | 2/5 |
| L29 | 'Given' | 0.194 | 0.007 | 2.48 | 3/5 |
| L22 | ' compréhension' | 0.318 | 0.018 | 2.47 | 3/5 |
| L24 | '理解和' | 0.318 | 0.018 | 2.47 | 2/5 |
| L24 | ' recognize' | 0.109 | 0.0 | 2.47 | 2/5 |
| L22 | ' Ack' | 0.233 | 0.011 | 2.47 | 2/5 |
| L22 | ' acknowledging' | 0.233 | 0.011 | 2.47 | 1/5 |
| L26 | '深刻理解' | 0.271 | 0.014 | 2.46 | 2/5 |
| L24 | ' comprendre' | 0.271 | 0.014 | 2.46 | 2/5 |
| L24 | ' zrozum' | 0.271 | 0.014 | 2.46 | 2/5 |
| L27 | ' Verständnis' | 0.147 | 0.004 | 2.45 | 2/5 |
| L21 | ' acknowledges' | 0.147 | 0.004 | 2.45 | 2/5 |
| L21 | ' acknowledging' | 0.147 | 0.004 | 2.45 | 2/5 |
| L26 | ' hiểu' | 0.186 | 0.007 | 2.44 | 2/5 |

family AUC by layer (decision point, higher rank = more present):

| family | L0 | L4 | L8 | L12 | L16 | L20 | L24 | L28 | best layer |
|---|---|---|---|---|---|---|---|---|---|
| refusal | 0.5 | 0.5 | 0.51 | 0.61 | 0.67 | 0.68 | 0.55 | 0.55 | L19 0.695 |
| hesitate | 0.38 | 0.44 | 0.52 | 0.61 | 0.46 | 0.41 | 0.33 | 0.33 | L12 0.605 |
| verify | 0.5 | 0.5 | 0.5 | 0.5 | 0.49 | 0.38 | 0.43 | 0.38 | L12 0.5 |
| ask | 0.5 | 0.44 | 0.47 | 0.59 | 0.52 | 0.53 | 0.4 | 0.42 | L10 0.649 |
| transfer | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.53 | L31 0.564 |
| error | 0.5 | 0.5 | 0.5 | 0.5 | 0.51 | 0.5 | 0.49 | 0.5 | L30 0.527 |

## E: failed vs passed episode

- episodes: fail 43, pass 235

| score | AUC | 95% CI | airline | retail | telecom |
|---|---|---|---|---|---|
| mean_rev20_rate | 0.501 | [0.393, 0.599] | 0.56 | 0.524 | 0.598 |
| mean_late_commit_rate | 0.596 | [0.492, 0.685] | 0.518 | 0.497 | 0.626 |
| mean_commit_mean | 0.551 | [0.45, 0.65] | 0.56 | 0.494 | 0.587 |

- in-sample best layer per family (max over turns; descriptive only): {"family_refusal_best_layer_insample": [22, 0.657], "family_hesitate_best_layer_insample": [4, 0.68], "family_verify_best_layer_insample": [13, 0.533], "family_ask_best_layer_insample": [21, 0.603], "family_transfer_best_layer_insample": [31, 0.597], "family_error_best_layer_insample": [29, 0.576]}
