# Confound checks (out-of-fold AUC, 5 folds grouped by task)

## W_clean_all: bad 40, good 249

| score | AUC | 95% CI | airline | retail | telecom |
|---|---|---|---|---|---|
| A_pairs | 0.741 | [0.657, 0.83] | 0.641 | 0.695 | 0.768 |
| B_family | 0.66 | [0.567, 0.761] | 0.718 | 0.68 | 0.612 |
| tool_only | 0.826 | [0.76, 0.882] | 0.622 | 0.844 | 0.737 |
| A_plus_tool_rank | 0.854 | [0.792, 0.908] | 0.658 | 0.82 | 0.816 |

- bad turns by tool: {'transfer_to_human_agents': 19, 'update_reservation_flights': 7, 'cancel_reservation': 3, 'cancel_pending_order': 3, 'update_reservation_baggages': 2, 'modify_pending_order_items': 2, 'refuel_data': 2, 'send_payment_request': 2}
- within-tool A_pairs AUC (tools with both labels): [('cancel_pending_order', 3, 18, 0.5), ('cancel_reservation', 3, 6, 0.5), ('modify_pending_order_items', 2, 27, 0.481), ('refuel_data', 2, 22, 0.455), ('send_payment_request', 2, 5, 0.5), ('transfer_to_human_agents', 19, 22, 0.844), ('update_reservation_baggages', 2, 1, 0.5), ('update_reservation_flights', 7, 10, 0.557)]
- weighted within-tool AUC: 0.589

## W_clean_no_transfer: bad 21, good 227

| score | AUC | 95% CI | airline | retail | telecom |
|---|---|---|---|---|---|
| A_pairs | 0.68 | [0.529, 0.799] | 0.673 | 0.341 | 0.577 |
| B_family | 0.481 | [0.318, 0.634] | 0.485 | 0.389 | 0.139 |
| tool_only | 0.816 | [0.708, 0.894] | 0.452 | 0.752 | 0.757 |
| A_plus_tool_rank | 0.793 | [0.661, 0.895] | 0.66 | 0.56 | 0.743 |

- bad turns by tool: {'update_reservation_flights': 7, 'cancel_reservation': 3, 'cancel_pending_order': 3, 'update_reservation_baggages': 2, 'modify_pending_order_items': 2, 'refuel_data': 2, 'send_payment_request': 2}
- within-tool A_pairs AUC (tools with both labels): [('cancel_pending_order', 3, 18, 0.444), ('cancel_reservation', 3, 6, 0.444), ('modify_pending_order_items', 2, 27, 0.315), ('refuel_data', 2, 22, 0.341), ('send_payment_request', 2, 5, 0.75), ('update_reservation_baggages', 2, 1, 1.0), ('update_reservation_flights', 7, 10, 0.714)]
- weighted within-tool AUC: 0.464

## W_clean_wrong_args_or_unexpected_write: bad 21, good 227

| score | AUC | 95% CI | airline | retail | telecom |
|---|---|---|---|---|---|
| A_pairs | 0.68 | [0.531, 0.811] | 0.673 | 0.341 | 0.577 |
| B_family | 0.481 | [0.329, 0.634] | 0.485 | 0.389 | 0.139 |
| tool_only | 0.816 | [0.714, 0.9] | 0.452 | 0.752 | 0.757 |
| A_plus_tool_rank | 0.793 | [0.658, 0.899] | 0.66 | 0.56 | 0.743 |

- bad turns by tool: {'update_reservation_flights': 7, 'cancel_reservation': 3, 'cancel_pending_order': 3, 'update_reservation_baggages': 2, 'modify_pending_order_items': 2, 'refuel_data': 2, 'send_payment_request': 2}
- within-tool A_pairs AUC (tools with both labels): [('cancel_pending_order', 3, 18, 0.444), ('cancel_reservation', 3, 6, 0.444), ('modify_pending_order_items', 2, 27, 0.315), ('refuel_data', 2, 22, 0.341), ('send_payment_request', 2, 5, 0.75), ('update_reservation_baggages', 2, 1, 1.0), ('update_reservation_flights', 7, 10, 0.714)]
- weighted within-tool AUC: 0.464

