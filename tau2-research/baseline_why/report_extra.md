# Supplement: noise floor, transfers, examples

## 1. Unsteered rerun noise: hdetect (Haiku user, earlier run) vs f_detect on the same eval tasks

- tasks in both: 76; outcome differs on 11 (14%); hdetect success 58, f_detect 61
- differing tasks: ['airline:2', 'airline:25', 'airline:34', 'airline:35', 'retail:0', 'retail:111', 'retail:38', 'retail:6', 'retail:64', 'retail:71', 'retail:97']
- tasks flipped by ≥ 3 of the 5 baselines: 13; of those with an hdetect run, the unsteered rerun also differs on 3/13
- tasks flipped by none of the 5: 33; unsteered rerun differs on 3/33

## 2. Unneeded transfers (unexpected_transfer writes) per condition, eval set

- f_detect: unneeded transfer calls 22, episodes with one 22/76
- f_caa_s0.5: unneeded transfer calls 22, episodes with one 22/76
- f_austeer_s10: unneeded transfer calls 20, episodes with one 20/76
- f_sadi_s10: unneeded transfer calls 20, episodes with one 20/76
- f_iti_s15: unneeded transfer calls 23, episodes with one 23/76
- f_cast_s0.25: unneeded transfer calls 21, episodes with one 21/76
- f_j5: unneeded transfer calls 22, episodes with one 22/76
- fixed episodes (pooled over the 5 baselines): {'other reference failure': 13, 'reference had an unneeded transfer': 17}

## 3. Fragile tasks (broken by ≥ 3 baselines): what the reference did vs a steered run

### retail task 36 (broken by 5/5; reference turns 22)
- f_caa_s0.5: FAIL ['db_mismatch', 'missing_write', 'unexpected_write']; diverges at turn 0; turns 16
- f_austeer_s10: FAIL ['db_mismatch', 'missing_write', 'unexpected_transfer', 'wrong_args']; diverges at turn 0; turns 19
- f_sadi_s10: FAIL ['db_mismatch', 'missing_write', 'unexpected_write', 'wrong_args']; diverges at turn 0; turns 19
- f_iti_s15: FAIL ['db_mismatch', 'missing_write', 'unexpected_transfer', 'unexpected_write', 'wrong_args']; diverges at turn 0; turns 23
- f_cast_s0.25: FAIL ['db_mismatch', 'missing_write', 'unexpected_write', 'wrong_args']; diverges at turn 0; turns 23
  - at the first differing turn 0: reference calls [], f_caa_s0.5 calls []
  - reference text: 'I understand your concern about the payment. However, according to the policy, I can only help with modifying the payment method for a pending order, but the user can only choose a single payment method different from th'
  - f_caa_s0.5 text: "I'd be happy to help you with your order. First, I need to authenticate your identity to access your account information. Could you please provide your email address so I can locate your user ID?<|im_end|>"
  - reference writes: ['modify_pending_order_items', 'modify_pending_order_items']
  - f_caa_s0.5 writes: ['cancel_pending_order']
### retail task 5 (broken by 5/5; reference turns 17)
- f_caa_s0.5: FAIL ['db_mismatch', 'missing_write', 'unexpected_write']; diverges at turn 0; turns 13
- f_austeer_s10: FAIL ['db_mismatch', 'missing_write', 'unexpected_write']; diverges at turn 0; turns 12
- f_sadi_s10: FAIL ['db_mismatch', 'missing_write', 'unexpected_write']; diverges at turn 0; turns 16
- f_iti_s15: FAIL ['db_mismatch', 'missing_write', 'unexpected_write']; diverges at turn 0; turns 13
- f_cast_s0.25: FAIL ['db_mismatch', 'missing_write', 'unexpected_write']; diverges at turn 0; turns 15
  - at the first differing turn 0: reference calls [], f_caa_s0.5 calls []
  - reference text: 'I need to authenticate your identity first. You mentioned your username is mei_kovacs_8020 and zip code is 28236. Let me look up your user ID using your email address. Could you please provide your email address so I can'
  - f_caa_s0.5 text: 'I need to authenticate your identity first. You mentioned your username is mei_kovacs_8020, but I need to verify this by looking up your user ID using your email or name and zip code. Could you please provide your email '
  - reference writes: ['return_delivered_order_items']
  - f_caa_s0.5 writes: ['exchange_delivered_order_items']
### airline task 35 (broken by 4/5; reference turns 17)
- f_caa_s0.5: FAIL ['db_mismatch', 'missing_write', 'unexpected_transfer']; diverges at turn 0; turns 8
- f_austeer_s10: FAIL ['db_mismatch', 'missing_write', 'unexpected_transfer']; diverges at turn 0; turns 8
- f_sadi_s10: FAIL ['db_mismatch', 'missing_write', 'unexpected_transfer']; diverges at turn 2; turns 7
- f_iti_s15: FAIL ['db_mismatch', 'missing_write', 'unexpected_transfer']; diverges at turn 0; turns 12
- f_cast_s0.25: PASS; diverges at turn 0; turns 25
  - at the first differing turn 0: reference calls [], f_caa_s0.5 calls []
  - reference text: "I'd be happy to help you with your cancellation. To proceed, I need to obtain some information from you. First, I need your user ID to access your reservation details. Could you please provide your user ID? Also, I'll ne"
  - f_caa_s0.5 text: "I'd be happy to help you with your cancellation. To proceed, I need to obtain some information from you. First, could you please provide your user ID?<|im_end|>"
  - reference writes: ['book_reservation']
  - f_caa_s0.5 writes: ['transfer_to_human_agents']
### retail task 100 (broken by 4/5; reference turns 20)
- f_caa_s0.5: FAIL ['db_mismatch', 'missing_write', 'wrong_args']; diverges at turn 7; turns 17
- f_austeer_s10: PASS; diverges at turn 0; turns 19
- f_sadi_s10: FAIL ['db_mismatch', 'missing_write', 'wrong_args']; diverges at turn 2; turns 14
- f_iti_s15: FAIL ['db_mismatch', 'missing_write', 'unexpected_transfer', 'wrong_args']; diverges at turn 0; turns 25
- f_cast_s0.25: FAIL ['db_mismatch', 'missing_write']; diverges at turn 0; turns 17
  - at the first differing turn 7: reference calls ['get_product_details'], f_caa_s0.5 calls ['get_product_details']
  - reference text: 'Let me review your orders and understand your requests: 1. **Luggage Set**: You mentioned wanting to return and swap for the exact same set but in red. Looking at your orders, I see order #W3295833 contains a Luggage Set'
  - f_caa_s0.5 text: 'Let me review your orders and understand your requests: 1. **Luggage Set**: You mentioned wanting to return and swap for the exact same set but in red. Looking at order #W3295833, I see a Luggage Set (item_id: 8926329222'
  - reference writes: ['return_delivered_order_items', 'return_delivered_order_items', 'modify_pending_order_items', 'transfer_to_human_agents']
  - f_caa_s0.5 writes: ['modify_pending_order_items', 'return_delivered_order_items']
### retail task 38 (broken by 4/5; reference turns 18)
- f_caa_s0.5: FAIL ['db_mismatch', 'missing_write', 'wrong_args']; diverges at turn 1; turns 16
- f_austeer_s10: FAIL ['db_mismatch', 'missing_write', 'wrong_args']; diverges at turn 0; turns 17
- f_sadi_s10: PASS; diverges at turn 1; turns 18
- f_iti_s15: FAIL ['db_mismatch', 'missing_write', 'wrong_args']; diverges at turn 0; turns 18
- f_cast_s0.25: FAIL ['db_mismatch', 'missing_write', 'wrong_args']; diverges at turn 0; turns 19
  - at the first differing turn 1: reference calls ['find_user_id_by_email'], f_caa_s0.5 calls ['find_user_id_by_email']
  - reference text: "I'll look up your user ID using your email address. <tool_call> <function=find_user_id_by_email> <parameter=email> daikisanchez1479@example.com </parameter> </function> </tool_call><|im_end|>"
  - f_caa_s0.5 text: '<tool_call> <function=find_user_id_by_email> <parameter=email> daikisanchez1479@example.com </parameter> </function> </tool_call><|im_end|>'
  - reference writes: ['cancel_pending_order']
  - f_caa_s0.5 writes: ['cancel_pending_order']
### retail task 9 (broken by 4/5; reference turns 14)
- f_caa_s0.5: FAIL ['db_mismatch', 'missing_write', 'unexpected_transfer']; diverges at turn 0; turns 5
- f_austeer_s10: FAIL ['db_mismatch', 'missing_write']; diverges at turn 0; turns 6
- f_sadi_s10: FAIL ['db_mismatch', 'missing_write', 'unexpected_transfer']; diverges at turn 1; turns 5
- f_iti_s15: PASS; diverges at turn 0; turns 12
- f_cast_s0.25: FAIL ['db_mismatch', 'missing_write', 'unexpected_transfer']; diverges at turn 0; turns 6
  - at the first differing turn 0: reference calls [], f_caa_s0.5 calls []
  - reference text: 'I need to authenticate your identity first. You mentioned your username is mei_kovacs_8020, but I need to verify this by looking up your user ID using your email address. Could you please provide your email address?<|im_'
  - f_caa_s0.5 text: 'I need to authenticate your identity first. You mentioned your username is mei_kovacs_8020, but I need to locate your user ID via email or name + zip code. Could you please provide your email address?<|im_end|>'
  - reference writes: ['exchange_delivered_order_items']
  - f_caa_s0.5 writes: ['transfer_to_human_agents']

## 4. Fix and break rates per opportunity (eval set)

- f_caa_s0.5 airline: broken 3/20 = 15% of passing tasks; fixed 3/6 = 50% of failing tasks
- f_caa_s0.5 retail: broken 9/41 = 22% of passing tasks; fixed 4/9 = 44% of failing tasks
- f_austeer_s10 airline: broken 1/20 = 5% of passing tasks; fixed 2/6 = 33% of failing tasks
- f_austeer_s10 retail: broken 11/41 = 27% of passing tasks; fixed 4/9 = 44% of failing tasks
- f_sadi_s10 airline: broken 1/20 = 5% of passing tasks; fixed 0/6 = 0% of failing tasks
- f_sadi_s10 retail: broken 10/41 = 24% of passing tasks; fixed 6/9 = 67% of failing tasks
- f_iti_s15 airline: broken 1/20 = 5% of passing tasks; fixed 1/6 = 17% of failing tasks
- f_iti_s15 retail: broken 6/41 = 15% of passing tasks; fixed 3/9 = 33% of failing tasks
- f_cast_s0.25 airline: broken 2/20 = 10% of passing tasks; fixed 2/6 = 33% of failing tasks
- f_cast_s0.25 retail: broken 12/41 = 29% of passing tasks; fixed 5/9 = 56% of failing tasks
