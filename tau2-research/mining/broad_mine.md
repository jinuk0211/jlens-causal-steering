# Broad J-lens mining: every failure type, all layers, all logged positions (278 f_detect episodes)

E2 positive kinds: {'unexpected_write': 8, 'unexpected_transfer': 13, 'wrong_args': 9}; tools: {'update_reservation_flights': 4, 'transfer_to_human_agents': 13, 'update_reservation_baggages': 1, 'cancel_reservation': 3, 'cancel_pending_order': 3, 'modify_pending_order_items': 2, 'refuel_data': 2, 'send_payment_request': 2}

## E1 whole episode (diagnostic, includes the failing actions): positives 43, negatives 235

| features | K | AUC | 95% task-cluster CI | within-tool AUC |
|---|---|---|---|---|
| J-lens (group, layer, word) | 20 | 0.698 | [0.614, 0.772] | - |
| J-lens (group, layer, word) | 100 | 0.724 | [0.643, 0.792] | - |
| J-lens (group, layer, word) | 500 | 0.736 | [0.659, 0.809] | - |
| surface tokens only (no lens) | 20 | 0.639 | [0.56, 0.72] | - |
| surface tokens only (no lens) | 100 | 0.734 | [0.648, 0.815] | - |
| surface tokens only (no lens) | 500 | 0.692 | [0.596, 0.779] | - |

J-lens failure features picked in the most folds (K = 100): A/L11/' incomplete'×5; A/L21/' avenues'×5; A/L30/' Ln'×4; A/L31/' Lean'×4; A/L4/' Interaction'×4; A/L24/' khusus'×4; C/L27/' бюджет'×4; C/L26/'征得'×4; A/Lany/'相关新闻'×4; A/L17/' HELP'×4; A/L31/' Kh'×3; C/L14/' waitress'×3; C/L7/'rz'×3; A/L16/':["'×3; A/L10/'history'×3; A/L25/' ktorí'×3; A/Lany/' ktorí'×3; A/L19/'更加方便'×3; A/L22/'工作思路'×3; A/L23/' approx'×3; A/L19/' Франция'×3; A/L31/'gsub'×3; A/Lany/'没那么'×3; A/L27/'花期'×2; A/L29/'amik'×2

## E2 three turns before the first bad write, up to its decision point (vs good writes of the same tools): positives 30, negatives 98

| features | K | AUC | 95% task-cluster CI | within-tool AUC |
|---|---|---|---|---|
| J-lens (group, layer, word) | 20 | 0.711 | [0.599, 0.819] | 0.463 |
| J-lens (group, layer, word) | 100 | 0.716 | [0.604, 0.826] | 0.484 |
| J-lens (group, layer, word) | 500 | 0.699 | [0.593, 0.805] | 0.455 |
| surface tokens only (no lens) | 20 | 0.685 | [0.572, 0.798] | 0.494 |
| surface tokens only (no lens) | 100 | 0.688 | [0.56, 0.806] | 0.472 |
| surface tokens only (no lens) | 500 | 0.72 | [0.597, 0.843] | 0.56 |

J-lens failure features picked in the most folds (K = 100): A/L28/' Schedule'×5; A/L5/'December'×5; A/L26/' Apr'×5; A/L25/'转入'×5; A/L20/'/the'×5; A/L11/' ">'×5; A/L28/' Mayıs'×4; A/L29/'规则的'×4; A/L19/'只是一个'×4; A/L12/' professional'×4; A/L2/'December'×4; A/L9/' Rules'×3; A/L27/'是社会'×3; A/L29/'صاد'×3; A/L30/'是一条'×3; A/L8/'April'×3; A/L27/' Apr'×3; A/L25/'条件下'×3; A/L19/' EMPTY'×3; C/L25/' iemand'×3; A/L24/' challenges'×3; A/L20/'一般情况下'×2; A/L9/'April'×2; A/L9/'September'×2; A/L27/'.rules'×2

## E3 last three turns, failures without a bad write (missing write / NL) vs passed: positives 13, negatives 235

| features | K | AUC | 95% task-cluster CI | within-tool AUC |
|---|---|---|---|---|
| J-lens (group, layer, word) | 20 | 0.725 | [0.556, 0.871] | - |
| J-lens (group, layer, word) | 100 | 0.7 | [0.519, 0.836] | - |
| J-lens (group, layer, word) | 500 | 0.732 | [0.579, 0.87] | - |
| surface tokens only (no lens) | 20 | 0.701 | [0.57, 0.806] | - |
| surface tokens only (no lens) | 100 | 0.766 | [0.675, 0.846] | - |
| surface tokens only (no lens) | 500 | 0.626 | [0.517, 0.721] | - |

J-lens failure features picked in the most folds (K = 100): A/L24/' Monten'×5; A/L25/'quals'×4; C/L7/'lei'×4; A/L25/'ums'×4; C/L22/' запас'×3; C/Lany/' Baba'×3; A/L25/'στό'×3; C/L27/' Leopard'×3; C/L27/'.jsx'×3; A/L16/'comparison'×3; A/L22/'aknya'×3; C/L26/' ("%'×3; A/L22/'放在第一位'×3; A/L14/'Unless'×3; C/L22/'tt'×3; A/L26/'观望'×3; A/L27/' poch'×3; C/L23/'st'×3; C/L8/'lei'×3; A/L5/'＊＊'×3; A/L9/'“)'×3; A/L24/' Betten'×3; C/L26/' arithmetic'×3; A/L23/' lazer'×3; A/L15/' pounds'×3

