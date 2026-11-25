# N1: label-free neuron selection by J-lens readout of output directions

Rule: >= 2 of the top-20 readout tokens equal a lexicon word (case- and space-normalized). Rank by matches, then output norm.

## dojo: 283 neurons qualify; lexicon ['transfer', 'send', 'wire', 'iban', 'attacker', 'recipient', 'email', 'password', 'forward', 'reservation', 'booking']

| rank | layer | neuron | matches | norm | top-20 tokens |
|---|---|---|---|---|---|
| 1 | 19 | 8791 | 8 | 0.457 | '预订' ' booking' ' reservation' ' bookings' ' requis' '预约' ' tickets' ' invitations' ' Booking' ' reservations' ' requests' ' Reservation' 'booking' ' request' 'Reservation' '申请' 'Booking' ' booked' 'reservation' 'requests' |
| 2 | 19 | 2641 | 7 | 0.578 | ' email' '(email' 'EMAIL' ' Email' '邮箱' '.email' '[email' 'Email' '.Email' '.EMAIL' '手机号' ' EMAIL' 'email' 'ByEmail' ' emails' '\temail' '>Email' ',email' '.getEmail' ' 이메일' |
| 3 | 25 | 1860 | 7 | 0.517 | '密码' ' password' ' Password' 'password' 'Password' ' passwords' '_password' '.password' '-password' ' PASSWORD' '密碼' '/password' 'PASSWORD' '.Password' '和密码' '\tpassword' '>Password' 'Passwords' '(password' '_PASSWORD' |
| 4 | 30 | 9053 | 7 | 0.483 | ' password' '密码' 'Password' ' Password' 'password' '/password' '_password' ' passwords' '.password' '-password' '_PASSWORD' ' PASSWORD' '和密码' '.Password' 'PASSWORD' '密碼' '\tpassword' '(password' 'パスワード' ',password' |
| 5 | 27 | 4255 | 6 | 0.464 | '密码' ' password' ' Password' '钥匙' 'zey' '.password' '-Key' 'password' ' PASSWORD' '和密码' '密碼' ' Key' 'OCK' 'Password' 'PASSWORD' '_KEY' ' key' ' passwords' '識' 'Key' |
| 6 | 25 | 2985 | 6 | 0.437 | ' email' ' Email' 'email' ' emails' 'Email' ' mail' '邮件' '电子邮件' '_email' ' EMAIL' '-email' ' emailing' ' Emails' '/email' 'EMAIL' 'mail' ' emailed' '.email' '邮箱' '-mail' |
| 7 | 18 | 2923 | 5 | 0.529 | ' Sending' ' sending' '送' ' send' 'Sending' 'send' 'sending' ' sends' ' sent' ' Send' 'Send' ' ارسال' '发送' '送去' ' SEND' '/send' '"**' ' Sends' ' **“' 'sent' |
| 8 | 26 | 7986 | 5 | 0.518 | ' forward' ' forth' ' Forward' ' forwards' 'forward' 'forth' 'Forward' '-forward' '_forward' ' forwarded' ' forwarding' '.forward' ' FORWARD' ' fwd' '向前' '_FORWARD' '_fwd' ' fore' ' вперед' ' fourth' |
| 9 | 24 | 6592 | 5 | 0.482 | ' forward' ' Forward' 'forward' 'Forward' ' forwards' '-forward' '_forward' ' straight' '.forward' ' FORWARD' '向前' '前进' ' Straight' 'straight' ' forwarding' ' ahead' 'Straight' '_fwd' ' fwd' '_FORWARD' |
| 10 | 18 | 5101 | 5 | 0.480 | ' email' ' Email' 'EMAIL' 'Email' ' partnership' 'partners' ' emailed' ' help' '提供更' ' whatsapp' ' emails' ' Partnership' ' mailing' ' info' ' EMAIL' ' emailing' '帮助' ' partnerships' ' discussion' ' sms' |
| 11 | 24 | 7479 | 5 | 0.474 | ' forwarding' ' Forward' 'Forward' ' forward' 'forward' '-forward' '转发' ' FORWARD' ' forwards' '_forward' '.forward' '_FWD' ' forwarded' '隔' ' datap' '_FORWARD' '厦' ' fwd' '拉' '炉' |
| 12 | 23 | 6702 | 5 | 0.471 | 'foy' 'Transfer' 'transfer' ' transferred' ' offensive' ' transfer' 'acas' 'strup' ' transferring' '转移' '-transfer' 'wav' 'Sn' ' Transfer' 'Searching' 'OTS' 'TRANSFER' ' offense' 'rax' '/stat' |
| 13 | 21 | 4420 | 5 | 0.471 | ' email' ' Email' '-mail' '.email' 'email' '_email' '邮件' ' emails' '.mail' '邮箱' ' mail' 'Email' 'EmailAddress' 'mail' '电子邮件' '.Email' ' EMAIL' '-email' '>Email' 'emails' |
| 14 | 25 | 4755 | 5 | 0.468 | ' transfer' ' Transfer' 'transfer' 'Transfer' '转移' '-transfer' ' transfers' '_transfer' ' transferring' ' transferred' '.transfer' 'TRANSFER' ' transferência' ' transferencia' ' transf' '转让' ' transfert' '.Transfer' ' trasfer' '转移到' |
| 15 | 27 | 6031 | 5 | 0.467 | ' transfer' ' Transfer' ' transfers' 'transfer' '-transfer' 'Transfer' '_transfer' '转移' '.transfer' ' transferring' ' transferred' ' transf' ' transferencia' '转移到' ' Trans' ' trans' '.Transfer' '轉移' ' transfert' 'TRANSFER' |
| 16 | 29 | 3431 | 5 | 0.466 | ' forward' ' Forward' 'Forward' 'forward' ' forwards' '-forward' '_forward' ' FORWARD' '向前' '.forward' '_FORWARD' ' fwd' ' backward' ' вперед' ' forwarding' '_fwd' ' forwarded' '往前' '前进' ' upward' |
| 17 | 25 | 5099 | 5 | 0.461 | ' transfer' 'transfer' ' Transfer' 'Transfer' '转移' ' transferred' ' transfers' '-transfer' ' transferring' 'TRANSFER' '_transfer' '转移到' '转让' ' transf' '.transfer' '轉移' ' trasfer' ' off' ' transferencia' ' transfert' |
| 18 | 25 | 3717 | 5 | 0.460 | ' email' ' Email' '电子邮件' 'Email' '邮件' ' Pal' ' emails' 'メール' 'email' 'Pal' 'mail' '_email' ' communication' ' EMAIL' '-mail' '沟通能力' '沟通' 'aina' ' packet' ' mail' |
| 19 | 24 | 2737 | 5 | 0.457 | ' transfer' ' Transfer' 'transfer' ' transfers' '转移' 'Transfer' '_transfer' '.transfer' '-transfer' ' transferred' ' transferring' ' distribution' '轉移' ' sell' ' Distribution' 'TRANSFER' ' transferencia' '_TRANSFER' ' distributions' ' purchase' |
| 20 | 26 | 1006 | 5 | 0.456 | ' transfer' '转移' ' Transfer' ' transfers' 'transfer' 'Transfer' ' transferring' ' transferred' '-transfer' '_transfer' '.transfer' ' transferencia' '转移到' ' transferência' 'TRANSFER' ' transf' ' transfert' '轉移' ' trasfer' '.Transfer' |
| 21 | 23 | 2387 | 5 | 0.455 | ' forward' ' Forward' 'forward' 'Forward' ' forwards' ' FORWARD' '-forward' '_forward' ' fwd' '.forward' '_FORWARD' ' encode' ' front' ' encoder' '向前' ' forwarding' '编码' ' encoding' '前后' '向东' |
| 22 | 25 | 2712 | 5 | 0.451 | ' transfer' ' transfers' ' Transfer' 'transfer' ' transferring' ' transferred' '转移' 'Transfer' '-transfer' '_transfer' ' transferencia' ' transf' '移植' '.transfer' 'TRANSFER' ' transfert' '转移到' ' transplant' ' transferência' ' transplantation' |
| 23 | 23 | 7609 | 5 | 0.449 | ' send' ' sending' ' sent' ' sends' ' Send' 'send' 'Send' ' Sending' '送' '发送' 'sending' 'Sending' '/send' ' Sends' '_send' '.send' '-send' ' SEND' ' Sent' ' sender' |
| 24 | 21 | 5607 | 5 | 0.448 | '密码' ' password' ' Password' ' passwords' 'password' 'Password' '密碼' ' security' '/password' '.password' '_password' ' PASSWORD' '>Password' ' пароль' ' setPassword' ' lock' '_PASSWORD' '和密码' 'Passwords' 'security' |

Layer histogram of the top-256: L2:1, L5:3, L6:3, L7:4, L8:7, L9:11, L10:10, L11:9, L12:2, L13:2, L14:2, L15:1, L16:3, L17:2, L18:5, L19:13, L20:4, L21:9, L22:11, L23:28, L24:20, L25:37, L26:23, L27:10, L28:12, L29:9, L30:7, L31:8

## am: 150 neurons qualify; lexicon ['blackmail', 'leverage', 'affair', 'expose', 'leak', 'forward', 'confidential', 'override', 'cancel', 'alert', 'threat']

| rank | layer | neuron | matches | norm | top-20 tokens |
|---|---|---|---|---|---|
| 1 | 30 | 8351 | 6 | 0.501 | ' alert' 'alert' ' Alert' ' alerts' 'Alert' '/alert' ' Alerts' ' ALERT' '.alert' '_alert' '-alert' 'alerts' ' alerta' ' alerted' '\talert' '.Alert' '(alert' '_ALERT' '警报' ' alarm' |
| 2 | 26 | 7986 | 5 | 0.518 | ' forward' ' forth' ' Forward' ' forwards' 'forward' 'forth' 'Forward' '-forward' '_forward' ' forwarded' ' forwarding' '.forward' ' FORWARD' ' fwd' '向前' '_FORWARD' '_fwd' ' fore' ' вперед' ' fourth' |
| 3 | 24 | 6592 | 5 | 0.482 | ' forward' ' Forward' 'forward' 'Forward' ' forwards' '-forward' '_forward' ' straight' '.forward' ' FORWARD' '向前' '前进' ' Straight' 'straight' ' forwarding' ' ahead' 'Straight' '_fwd' ' fwd' '_FORWARD' |
| 4 | 26 | 5054 | 5 | 0.480 | ' alert' ' alarm' ' Alert' 'alert' 'Alert' '报警' ' Alarm' ' alerts' '警报' '/alert' ' alarms' 'alarm' '-alert' '警' 'Alarm' '_alert' ' Alerts' '.alert' ' alerta' ' ALERT' |
| 5 | 24 | 7479 | 5 | 0.474 | ' forwarding' ' Forward' 'Forward' ' forward' 'forward' '-forward' '转发' ' FORWARD' ' forwards' '_forward' '.forward' '_FWD' ' forwarded' '隔' ' datap' '_FORWARD' '厦' ' fwd' '拉' '炉' |
| 6 | 25 | 1931 | 5 | 0.469 | ' override' ' overrides' 'override' ' overriding' ' supers' ' Override' ' overridden' ' Overrides' 'overrides' 'Override' 'Overrides' '\toverride' '_override' '超' ' sup' '超越' '.override' ' overwhel' ' super' '_OVERRIDE' |
| 7 | 29 | 3431 | 5 | 0.466 | ' forward' ' Forward' 'Forward' 'forward' ' forwards' '-forward' '_forward' ' FORWARD' '向前' '.forward' '_FORWARD' ' fwd' ' backward' ' вперед' ' forwarding' '_fwd' ' forwarded' '往前' '前进' ' upward' |
| 8 | 23 | 2387 | 5 | 0.455 | ' forward' ' Forward' 'forward' 'Forward' ' forwards' ' FORWARD' '-forward' '_forward' ' fwd' '.forward' '_FORWARD' ' encode' ' front' ' encoder' '向前' ' forwarding' '编码' ' encoding' '前后' '向东' |
| 9 | 21 | 6827 | 5 | 0.444 | ' cancelled' '取消' ' cancellation' ' canceled' ' cancel' ' cancell' ' Cancel' 'cancel' ' cancelling' '取消了' 'cancelled' ' canc' 'Cancel' 'Cancelled' '-cancel' 'Cancellation' 'Canceled' '.cancel' '_cancel' 'CANCEL' |
| 10 | 27 | 684 | 5 | 0.432 | ' cancel' ' cancellation' ' Cancel' ' canc' ' cancell' ' cancelling' 'cancel' ' cancelled' ' canceled' '取消' 'Cancel' '-cancel' '_cancel' 'Cancellation' '.cancel' 'cancelled' ' Canc' '(cancel' 'Cancelled' '\tcancel' |
| 11 | 24 | 8603 | 4 | 0.512 | ' wake' '醒' '清醒' 'wake' ' alert' ' awake' ' Wake' 'Wake' ' waking' ' Alert' '觉醒' ' wakes' 'alert' '醒了' 'Alert' '/alert' ' Awake' '警醒' '警觉' ' woke' |
| 12 | 22 | 8415 | 4 | 0.500 | ' backward' ' leaning' ' forward' '向后' 'backward' ' lean' ' leans' ' leaned' ' backwards' '向前' 'Forward' 'forward' ' Forward' '倾斜' '往后' ' forwards' 'leaning' '往前' '_forward' '_backward' |
| 13 | 25 | 9052 | 4 | 0.493 | ' watch' ' alert' ' vigil' ' Vigil' ' Watch' '警' ' vigilant' ' Alert' 'alert' 'vig' '/alert' 'Watch' '-watch' 'Alert' 'watch' ' vigilancia' '警戒' ' watches' ' guard' '警觉' |
| 14 | 28 | 2045 | 4 | 0.487 | ' back' '反' ' forward' '的反' ' Back' 'Back' ' backward' '_back' 'back' ' backwards' ' Forward' 'forward' ' reverse' '-back' '反向' 'Sl' 'sl' 'Forward' ' sl' ' Sl' |
| 15 | 31 | 4420 | 4 | 0.485 | ' vor' ' перед' ' Vor' 'vor' 'Vor' ' pred' ' foreground' ' forward' 'перед' ' przed' ' před' ' Перед' ' Forward' '前景' 'forward' ' пред' 'Forward' '向前' ' پیش' ' avant' |
| 16 | 26 | 7831 | 4 | 0.480 | ' forward' ' Forward' ' shifted' 'Forward' 'efeld' ' Sat' 'UID' ' Nack' '_OVERFLOW' '(O' '-O' 'forward' 'ốn' 'OAD' '颠' ' Dx' ' Sham' 'shm' '刘家' ' Oy' |
| 17 | 22 | 8481 | 4 | 0.479 | '前进' '向前' ' forward' ' advancing' '前行' 'forward' ' Forward' ' proceeding' ' forwards' 'Forward' ' advance' ' progressing' ' proceed' '向前走' '往前走' '_forward' '往前' ' ahead' ' proceeds' 'advance' |
| 18 | 14 | 1155 | 4 | 0.461 | ' overriding' ' overrides' '优先' ' override' ' Overrides' ' Override' 'overrides' ' overridden' 'override' ' precedence' '_override' ' supers' '优先级' '優先' 'Priority' 'Override' ' Priority' ' priority' 'Overrides' '更正' |
| 19 | 20 | 7617 | 4 | 0.458 | ' override' ' overriding' ' overrides' 'override' ' Overrides' ' Override' '优先级' '优先' 'overrides' ' overridden' ' priority' 'Overrides' '優先' 'Override' ' Priority' ' priorit' 'priority' 'Priority' ' precedence' ' приор' |
| 20 | 22 | 1437 | 4 | 0.457 | ' forward' '汗' ' Forward' ' FORWARD' ' [' '简明' '学弟' ' Command' '师弟' 'Forward' '免征' 'ดัง' ' decis' 'ivals' '汉' '的前' '师妹' '代收' '弟' ' sweat' |
| 21 | 23 | 3592 | 4 | 0.457 | '-forward' ' Forward' 'iki' 'forward' ' forward' 'prints' '谊' '.backward' ' forwarding' ' Print' 'Forward' 'شار' 'omat' '早报' ' complain' 'obod' '遇' ' Compl' '形势' ' Rational' |
| 22 | 24 | 6610 | 4 | 0.456 | ' rel' ' relay' ' Forward' ' routing' ' forwarding' ' hop' 'Forward' ' forward' ' hops' ' forwards' 'forward' '_forward' ' Relay' 'relay' ' route' '路由' ' forwarded' 'Hop' '转发' ' routed' |
| 23 | 22 | 6255 | 4 | 0.453 | ' onward' ' onwards' ' downwards' ' downward' ' upwards' ' upward' ' forward' '向下' '向上' 'forward' ' forwards' '向前' 'wards' ' Forward' ' outward' '往后' ' inward' '往前' '往下' 'Forward' |
| 24 | 22 | 2232 | 4 | 0.453 | ' over' ' overwrite' ' Over' ' override' 'Over' 'over' '-over' 'override' ' overrides' ' overriding' '_over' ' overwritten' 'overwrite' '.over' ' Override' 'Override' ' Overrides' ' overridden' ' OVER' '_override' |

Layer histogram of the top-256: L2:1, L5:6, L6:4, L7:1, L8:2, L9:8, L10:7, L11:3, L12:4, L13:7, L14:3, L16:2, L17:2, L18:3, L19:7, L20:10, L21:12, L22:8, L23:7, L24:13, L25:15, L26:11, L27:3, L28:1, L29:5, L30:4, L31:1

## toolalign: 158 neurons qualify; lexicon ['delete', 'export', 'fraud', 'whistleblower', 'regulator', 'fbi', 'doj', 'leak', 'external']

| rank | layer | neuron | matches | norm | top-20 tokens |
|---|---|---|---|---|---|
| 1 | 31 | 8241 | 7 | 0.309 | '出口' ' export' ' Export' ' exported' 'Export' 'export' ' exports' '出口的' ' exporting' '/export' '-export' '_export' '.export' ' exporter' ' EXPORT' 'exports' 'EXPORT' ' exporters' '\texport' '_EXPORT' |
| 2 | 25 | 1975 | 6 | 0.474 | ' delete' 'delete' '/delete' '\tdelete' ' Delete' '-delete' ' deleted' '删' ' deletion' ' deleting' '_delete' 'Delete' '删除' '.delete' ' deletes' ' DELETE' ' Deleting' '(delete' ' operator' ' Deleted' |
| 3 | 25 | 6726 | 5 | 0.465 | ' export' '出口' 'export' '.export' ' exporting' ' exported' 'Export' ' exports' 'Exports' '出口的' ' sourced' ' exporta' ' sourcing' '-export' ' Export' '_export' 'Exporter' '/export' ' exporter' 'EXPORT' |
| 4 | 25 | 8077 | 5 | 0.451 | ' Export' ' exporting' 'entro' 'Export' ' export' 'oto' ' exported' '�' '托' 'ento' ' phơi' 'vore' ' EXPORT' 'export' 'ENTO' 'rets' '_EXPORT' '北辰' 'gere' ' رج' |
| 5 | 17 | 6581 | 4 | 0.590 | '现代化' '现代的' 'Modern' ' modern' 'modern' ' Modern' '现代化的' 'External' '现代' ' External' '\n\n\n' 'external' ' external' ' modernes' '的现代' ' moderni' '外部' '在现代' '外来' 'Extern' |
| 6 | 18 | 4047 | 4 | 0.540 | '/internal' '内部' 'internal' '外部' ' External' 'External' ' Internal' '/Internal' 'Internal' '！（' 'external' ' internal' '的内部' '.external' '的外部' '内外' '.internal' '内' ' external' '內部' |
| 7 | 30 | 5052 | 4 | 0.516 | ' outside' ' Outside' 'outside' ' exterior' ' external' '外部' 'Outside' ' External' 'external' '外' '的外部' '以外' ' Exterior' '外的' '之外' ' externally' '外界' '外面' '外面的' 'External' |
| 8 | 26 | 837 | 4 | 0.511 | ' delete' ' deletion' '删除' ' Delete' ' deleted' 'Delete' 'delete' ' deleting' ' delet' ' deletes' ' Deleting' ' Del' 'Del' ' Deleted' 'Deleted' '-delete' '_delete' 'del' '.delete' ' del' |
| 9 | 23 | 2096 | 4 | 0.491 | ' external' '模板' ' template' '外部' ' External' ' category' ' Category' 'external' ' templates' '的外部' ' Template' 'template' ' categories' 'External' '_category' 'category' 'Category' '-category' ' 외부' '.template' |
| 10 | 27 | 6598 | 4 | 0.489 | ' internal' ' external' 'internal' ' Internal' ' External' '外部' 'external' 'Internal' 'External' '内部' '外' '的内部' '内' '的外部' '.internal' '_internal' ' externally' '/internal' ' internally' '(internal' |
| 11 | 26 | 2898 | 4 | 0.485 | ' external' ' External' '外部' 'External' '外的' '外' '在外' '的外部' '_external' ' outside' 'external' '外力' ' outsiders' ' outer' '的外' '外面的' '外面' '外国' 'Outside' '外在' |
| 12 | 23 | 2904 | 4 | 0.484 | ' deleted' '删除' 'deleted' ' deletion' ' delete' ' Deleted' 'Deleted' ' deleting' ' Delete' 'delete' 'Delete' '_deleted' ' deletes' ' Deleting' ' delet' '删' '-delete' '.delete' '.deleted' '_delete' |
| 13 | 25 | 7890 | 4 | 0.481 | ' application' ' Application' 'application' ' external' ' External' 'External' ' externally' '.Application' 'Application' '外部' '包' '_application' 'external' 'extern' ' extern' '的外部' ' applications' '-application' '外包' ' Context' |
| 14 | 23 | 8678 | 4 | 0.481 | ' outside' ' Outside' 'outside' 'Outside' ' outdoors' '外' ' external' ' outdoor' '外面' ' exterior' '外部' '外的' '外面的' '室外' 'external' ' External' '户外' ' Outdoor' 'External' '在外' |
| 15 | 27 | 5986 | 4 | 0.479 | ' ab' ' external' ' External' ' internal' ' add' '-ab' '外部' ' abducted' ' Internal' '_ab' '丰' 'hto' 'external' 'ab' 'External' '斗' '.ab' '.internal' ' Ab' '的外部' |
| 16 | 25 | 7499 | 4 | 0.478 | ' export' ' source' '出口' 'export' 'source' ' exports' ' exported' ' exporting' '-export' '源' 'Source' '-source' '_export' ' Source' '.export' 'Export' ' sources' '(source' '/export' '\texport' |
| 17 | 22 | 6812 | 4 | 0.477 | ' internal' ' external' 'external' ' nearby' 'internal' 'central' ' central' '外部' ' External' '内部的' ' Internal' ' distant' 'Internal' ' local' 'External' '内部' ' externally' ' overseas' '的外部' ' Nearby' |
| 18 | 28 | 3517 | 4 | 0.475 | ' external' '外部' ' External' '外' 'external' ' international' '的外部' 'External' ' extern' 'international' '国际' ' eksternal' ' externally' ' externa' '.external' '的国际' '_external' ' внеш' '國際' ' внешних' |
| 19 | 26 | 7566 | 4 | 0.474 | ' front' ' Front' 'Front' 'front' '-front' ' bus' '前端' '_front' ' buss' ' External' ' external' ' peripheral' '(front' 'External' ' Bus' 'Bus' 'external' '外部' '外人' '/front' |
| 20 | 21 | 7514 | 4 | 0.464 | ' exporting' ' export' ' exports' ' cocoa' ' cacao' ' extraction' ' production' 'export' ' lumber' '出口' '-export' ' exported' 'Export' ' Export' ' mineral' ' timber' ' extract' ' coffee' ' extracted' ' Extraction' |
| 21 | 25 | 3108 | 4 | 0.462 | ' outside' ' Outside' 'outside' 'Outside' '外部' ' external' '外面' ' exterior' '外的' ' External' '外面的' '外' 'external' 'External' '的外部' '在外面' ' externally' '_external' ' Exterior' ' خارج' |
| 22 | 23 | 8601 | 4 | 0.459 | ' internal' '内部' ' Internal' ' internally' 'internal' 'Internal' '的内部' ' externally' '内部的' ' external' '外部' '內部' ' External' 'external' 'External' '/internal' '_internal' '内外' '的外部' '(internal' |
| 23 | 26 | 3705 | 4 | 0.458 | ' wood' 'wood' '木材' ' Wood' 'Wood' '木' ' external' '在外' ' древес' '室外' ' outdoor' 'WOOD' ' External' '的外部' 'external' ' charcoal' 'External' 'Hol' '外露' ' woods' |
| 24 | 19 | 8200 | 4 | 0.453 | ' export' ' exports' ' exported' '-export' ' exporting' 'export' '出口' ' Export' ' exporters' '国际市场' ' markets' '海外市场' 'Export' '_export' ' abroad' '/export' ' sales' 'exports' '出口的' ' exporter' |

Layer histogram of the top-256: L2:1, L4:1, L5:1, L6:5, L7:2, L8:5, L9:8, L10:8, L11:10, L12:4, L13:2, L15:3, L16:2, L17:6, L18:7, L19:8, L20:7, L21:7, L22:8, L23:8, L24:16, L25:12, L26:9, L27:2, L28:5, L29:4, L30:3, L31:4

