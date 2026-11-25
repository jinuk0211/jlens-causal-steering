# J-lens analyses B-F, dojo (Qwen3.5-4B)

252 units: reference 131, target 121; 35 groups; layers 0..30 + final.

## Decision positions (one structural rule for both classes)

reference skip:no_call: 8; reference skip:no_inj_fn: 13; reference skip:tool: 49; reference skip:value_not_at_step: 23; reference tool: 28; reference value: 10; target skip:tool: 37; target skip:value_not_at_step: 12; target tool: 55; target value: 17

## C. Decision-position margin lp(T) - max lp(A), target - reference within group

| layer | 0 | 3 | 6 | 9 | 12 | 15 | 18 | 21 | 24 | 27 | 30 | final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mean | -2.66 | -3.66 | -1.77 | -0.14 | +0.12 | +0.04 | +1.07 | +2.59 | +15.00 | +25.43 | +19.79 | +23.74 |
| 95% CI | [-3.97,-1.21] | [-5.24,-1.84] | [-2.77,-0.40] | [-1.10,+0.96] | [-0.77,+1.31] | [-0.94,+1.00] | [+0.38,+1.69] | [+1.84,+3.31] | [+12.43,+17.19] | [+20.89,+29.93] | [+16.26,+22.87] | [+20.09,+26.75] |

- 18 groups with both classes; CI excludes 0 at layers ['0', '1', '2', '3', '4', '5', '6', '7', '8', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', 'final']

- kind tool: 15 groups, final +22.28, L16 +0.62, L24 +14.06
- kind value: 2 groups, final +29.34, L16 +0.89, L24 +20.18

## AUC profile (CALIBRATION fold, PLAN boundary rule 4; reported, not used to pick the band)

| layer | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 | 30 | final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AUC | 0.37 | 0.23 | 0.38 | 0.40 | 0.18 | 0.17 | 0.16 | 0.21 | 0.22 | 0.30 | 0.37 | 0.33 | 0.37 | 0.29 | 0.31 | 0.46 | 0.57 | 0.62 | 0.69 | 0.84 | 0.85 | 0.90 | 0.81 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

- onset layer (first layer with AUC >= 0.75 that stays there): 19

## D. Lock-in layer of the chosen candidate at the decision position

| class | kind | n | lock-in median [IQR] | never locked |
|---|---|---|---|---|
| reference | tool | 2 | [17.8, 19.5, 21.2] | 0 |
| reference | value | 9 | [23.0, 23.0, 23.0] | 0 |
| target | tool | 44 | [20.8, 23.0, 26.0] | 0 |
| target | value | 16 | [14.0, 19.0, 19.0] | 0 |

## E. Onset lp('<tool_call>'), target - reference within group

| layer | 0 | 3 | 6 | 9 | 12 | 15 | 18 | 21 | 24 | 27 | 30 | final |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mean | +0.02 | +0.12 | -0.47 | -0.09 | +0.45 | -0.05 | -0.36 | -0.14 | -0.79 | -1.11 | -0.78 | -0.63 |
| 95% CI | [-0.00,+0.03] | [+0.02,+0.24] | [-0.66,-0.29] | [-0.36,+0.23] | [+0.01,+0.97] | [-0.39,+0.27] | [-0.85,+0.11] | [-0.71,+0.40] | [-1.65,+0.19] | [-2.40,+0.41] | [-1.57,+0.04] | [-1.33,-0.03] |

## B (top-30). Onset words: in >= 9/16 of target groups (31) and <= 3/16 of reference groups (33); held-out group presence

- L3: [' In'] | held-out presence: target 0.24793388429752067, reference 0.10687022900763359
- L5: ['.**'] | held-out presence: target 0.2892561983471074, reference 0.19083969465648856
- L8: [','] | held-out presence: target 0.35537190082644626, reference 0.10687022900763359
- L11: ['.**', '**'] | held-out presence: target 0.5289256198347108, reference 0.19083969465648856
- L13: ['.\\'] | held-out presence: target 0.30578512396694213, reference 0.03816793893129771
- L18: ['.**'] | held-out presence: target 0.512396694214876, reference 0.0916030534351145
- L22: [' Wait'] | held-out presence: target 0.21487603305785125, reference 0.08396946564885496
- Lfinal: ['Before'] | held-out presence: target 0.3884297520661157, reference 0.05343511450381679

## B (top-50). Onset words: in >= 9/16 of target groups (31) and <= 3/16 of reference groups (33); held-out group presence

- L3: [' The'] | held-out presence: target 0.32231404958677684, reference 0.1984732824427481
- L5: ['**'] | held-out presence: target 0.36363636363636365, reference 0.20610687022900764
- L9: [' **^**'] | held-out presence: target 0.30578512396694213, reference 0.11450381679389313
- L10: [' **.'] | held-out presence: target 0.4793388429752066, reference 0.26717557251908397
- L11: ['**.'] | held-out presence: target 0.4049586776859504, reference 0.1450381679389313
- L14: ['-**', '**.'] | held-out presence: target 0.5867768595041323, reference 0.2595419847328244
- L15: ['�'] | held-out presence: target 0.4049586776859504, reference 0.04580152671755725
- L22: [' Wait', 'Wait'] | held-out presence: target 0.2975206611570248, reference 0.10687022900763359
- L23: [' wait'] | held-out presence: target 0.2396694214876033, reference 0.07633587786259542
- L28: [' Before'] | held-out presence: target 0.2975206611570248, reference 0.07633587786259542
- Lfinal: ['But'] | held-out presence: target 0.3140495867768595, reference 0.16793893129770993

## F. Top words at recipient / argument positions (first 10 of top-30, counts)

- target arg_recipient (n=67): L8 ' \\"', ' <', 'ly', '.\\"', '\\"'; L12 '...', ' \\"', ' ...', '......', '\\"'; L16 '？', '?', '?\\', '<|im_end|>', '"?'; L20 'https', ' USD', 'US', '@example', ' UUID'; L24 ' US', ' USA', '_US', 'US', 'USA'; L28 ' US', 'US', '.US', '-US', '_US'; Lfinal 'US', 'us', '1', 'IS', 'ES'
- target arg_subject (n=66): L8 ' \\"', 'ly', ' <', '\\"', 'a'; L12 ' \\"', ' ...', '...', '\\"', '......'; L16 '\\"', ' Money', ' payment', ' \\"', '\\n'; L20 ' Payment', ' Request', ' payment', ' Favorite', ' Customer'; L24 ' Payment', ' payment', ' Payments', ' Pizza', ' User'; L28 ' Pizza', ' pizza', 'Pizza', 'pizza', ' pizzas'; Lfinal 'Payment', 'Your', 'Pizza', 'User', 'Apple'
- target arg_amount (n=54): L8 ' \\"', ' money', ' <', ' Money', 'ly'; L12 ' money', ' \\"', ' Money', ' ...', '...'; L16 ' Money', ' money', ' \\$', ' payment', ' \\"'; L20 ' \\"$', ' "$', ' \\$', '.$', ' USD'; L24 ' USD', 'USD', '-dollar', ' dollars', ' pizza'; L28 '5', '1', '9', '2', '4'; Lfinal '1', '5', '0', '2', '3'
- target arg_date (n=54): L8 ' \\"', ' <', ' \n', 'ly', 'a'; L12 ' December', ' January', ' date', '...', ' July'; L16 ' January', ' date', 'date', ' December', ' Tuesday'; L20 'date', ' date', ' today', 'Date', ' Date'; L24 ' Today', ' TODAY', 'today', ' today', 'Today'; L28 '2', ' Today', ' today', ' YYYY', ' TODAY'; Lfinal '2', '1', '0', 'today', 'Today'
- reference arg_restaurant_names (n=33): L8 'ly', ' \\"', ' <', '...', '\\"'; L12 '...', ' ...', '<|endoftext|>', 'ly', '\n'; L16 '\n', '\\"', '<|endoftext|>', '?', '...'; L20 '(\\"', '\\"', '\\"\\', '\\""', '["'; L24 '["', ' ["', '(\\"', '[new', ']["'; L28 ' ["', '["', ' New', '(["', '[new'; Lfinal '["', ' ["', '(["', "['", '{"'
- reference arg_company_name (n=15): L8 ' \\"', 'ly', '\\"', '...', '.\\"'; L12 '...', ' ...', ' \\"', '<|endoftext|>', '....'; L16 '?', '\n', '\\/', ' selection', '\\"'; L20 '["', ' ["', '(\\"', '\\""', '{\\"'; L24 ' ["', '["', '(["', " ['", ' [["'; L28 ' ["', '["', '(["', " ['", ' Sun'; Lfinal '["', "['", ' ["', '(["', '[]'
- reference arg_recipient (n=14): L8 ' \\"', ' <', 'ly', 's', '\\"'; L12 '...', ' \\"', ' ...', '\\"', '......'; L16 '？', '<|im_end|>', '?', '?\\', ']?'; L20 'https', '@example', '\\.', ':\\/\\/', 'WhatsApp'; L24 ' GBP', 'GB', ' GB', 'GBP', '英国'; L28 ' GB', 'GB', '_GB', ' gb', ' GBP'; Lfinal 'GB', 'GBP', ' GB', '_GB', 'gb'
- reference arg_amount (n=14): L8 ' \\"', ' money', ' <', ' Money', ' \\"$'; L12 '...', ' ...', ' \\"', ' Money', '<|endoftext|>'; L16 ' Money', ' refund', '\\.', '？', ' \\"'; L20 ' deducted', ' refund', ' refunded', '退款', ' refunds'; L24 '贰', '两手', '两套', 'double', ' refund'; L28 '1', ' Number', 'Number', ' number', '2'; Lfinal '5', '1', '0', '2', '3'
- reference arg_subject (n=14): L8 ' \\"', 'ly', '\\"', ' <', 'a'; L12 ' ...', '...', ' \\"', '\\"', '......'; L16 ' payment', ' Money', '\\"', ' refund', ' reimbursement'; L20 ' refund', ' reimbursement', ' refunds', '退款', ' refunded'; L24 ' reimbursement', ' refund', '退款', ' refunds', ' refunded'; L28 ' reimbursement', ' refund', ' repayment', ' Return', ' Difference'; Lfinal 'Re', 'Ref', 'Return', 'Difference', 'D'
- reference arg_date (n=14): L8 ' \\"', 'ly', ' <', ' \n', ' '; L12 '...', ' December', ' ...', ' \\"', ' date'; L16 ' date', 'date', ' today', ' Tuesday', ' Date'; L20 'date', ' date', 'Date', ' Date', ' today'; L24 ' Today', ' TODAY', 'today', ' today', 'Today'; L28 '2', ' Today', ' TBD', ' today', ' TODAY'; Lfinal '2', 'today', '1', 'Today', 'T'
- target arg_id (n=13): L8 'ly', ' <', 's', 'n', ' \\"'; L12 '...', ' #', ' ...', ' <', 's'; L16 '?', '\n', ']?', '2', '1'; L20 '\\.', '6', '.*)', '1', '.*'; L24 '6', '六大', '６', '六位', 'six'; L28 '6', '7', '６', 'six', '8'; Lfinal '6', '7', '8', '1', '5'
- target arg_recipients (n=12): L8 ' \\"', 'ly', ' <', 'fully', 'se'; L12 ' \\"', ' <', 'mail', '...', ' ...'; L16 'mailto', '@example', 'mail', 'email', ' Gmail'; L20 'mailto', '@gmail', ' gmail', 'https', '@example'; L24 ' ["', '["', ' [{"', ' [["', '["@'; L28 '[j', ' ["', '["', ' [', " ['"; Lfinal '["', '[j', ' ["', '["@', '[]'
