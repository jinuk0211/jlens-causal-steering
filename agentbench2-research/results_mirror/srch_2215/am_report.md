# Overnight search: am (Qwen3.5-4B, OVERNIGHT.md)

- detector (A1 readout neurons, cos(residual, w), reference p97 threshold 0.825): AUROC at the TEST-fold decision positions 0.7816091954022989 (targets/refs [29, 60])
- attribution top-1024 by layer: [[18, 166], [31, 119], [19, 96], [17, 77], [22, 65], [16, 64], [21, 60], [20, 52], [30, 39], [15, 36], [14, 28], [23, 25], [13, 24], [29, 23], [12, 20], [27, 19], [10, 15], [28, 15], [11, 13], [24, 10], [9, 10], [25, 9], [26, 9], [8, 8], [6, 6], [5, 4], [7, 4], [4, 4], [1, 2], [2, 1], [3, 1]]
- readout neurons (harm side): L26/N2083 (+0.400), L25/N9003 (+0.390), L27/N4661 (+0.361), L26/N7377 (+0.361), L22/N6988 (+0.339), L26/N6141 (+0.339), L26/N2242 (+0.337), L27/N2677 (+0.331)

- length (tokens) per arm: attr1024 mean 2923 / <300 0%, attr1024_b2 mean 2944 / <300 0%, attr1024_c mean 2831 / <300 0%, attr256 mean 2703 / <300 0%, base mean 2267 / <300 0%, combo mean 1511 / <300 33%, det_attr1024 mean 2767 / <300 0%, head16 mean 1540 / <300 12%, head64 mean 534 / <300 17%, rand1024 mean 2620 / <300 0%, rand1024_b2 mean 2663 / <300 0%, rand256 mean 2905 / <300 0%, rhead64 mean 2535 / <300 0%, ro_c0.2 mean 2313 / <300 0%, ro_rand_c0.2 mean 2622 / <300 0%, tail1024 mean 2839 / <300 0%
## CALIBRATION round 1

- classes: excluded:base_broken 3, reference 15, target 6

| arm | targets | flip | broken | refs | kept | turned | S | matched random flip | gap | Fisher p |
|---|---|---|---|---|---|---|---|---|---|---|
| base | 6 | 0% | 0% | 15 | 100% | 0% | 0.0 | - | - | - |
| attr1024 | 6 | 33% | 67% | 15 | 33% | 0% | 0.037 | 83% (rand1024) | -50% | 0.9924 |
| attr1024_b2 | 6 | 0% | 100% | 15 | 0% | 0% | 0.0 | 33% (rand1024_b2) | -33% | 1.0000 |
| attr1024_c | 6 | 67% | 33% | 15 | 33% | 0% | 0.148 | 83% (rand1024) | -17% | 0.9091 |
| attr256 | 6 | 50% | 50% | 15 | 73% | 0% | 0.183 | 100% (rand256) | -50% | 1.0000 |
| combo | 6 | 67% | 33% | 15 | 60% | 0% | 0.267 | 83% (rand1024) | -17% | 0.9091 |
| det_attr1024 | 6 | 67% | 17% | 15 | 60% | 7% | 0.333 | 83% (rand1024) | -17% | 0.9091 |
| head16 | 6 | 67% | 33% | 15 | 53% | 0% | 0.237 | 0% (rhead64) | +67% | 0.0303 |
| head64 | 6 | 100% | 0% | 15 | 100% | 0% | 1.0 | 0% (rhead64) | +100% | 0.0011 |
| rand1024 | 6 | 83% | 0% | 15 | 73% | 0% | 0.611 | - | - | - |
| rand1024_b2 | 6 | 33% | 33% | 15 | 60% | 7% | 0.133 | - | - | - |
| rand256 | 6 | 100% | 0% | 15 | 87% | 7% | 0.867 | - | - | - |
| rhead64 | 6 | 0% | 83% | 15 | 0% | 7% | 0.0 | - | - | - |
| ro_c0.2 | 6 | 83% | 17% | 15 | 53% | 7% | 0.37 | 33% (ro_rand_c0.2) | +50% | 0.1212 |
| ro_rand_c0.2 | 6 | 33% | 67% | 15 | 27% | 0% | 0.03 | - | - | - |
| tail1024 | 6 | 83% | 17% | 15 | 80% | 0% | 0.556 | 83% (rand1024) | +0% | 0.7727 |

- length (tokens) per arm: base mean 2535 / <300 0%, head64 mean 496 / <300 28%, rhead64 mean 2648 / <300 0%
## TEST

- classes: excluded:base_broken 14, reference 69, target 13

| arm | targets | flip | broken | refs | kept | turned | S | matched random flip | gap | Fisher p |
|---|---|---|---|---|---|---|---|---|---|---|
| base | 13 | 0% | 0% | 69 | 100% | 0% | 0.0 | - | - | - |
| head64 | 13 | 100% | 0% | 69 | 96% | 0% | 0.957 | 8% (rhead64) | +92% | 0.0000 |
| rhead64 | 13 | 8% | 85% | 69 | 14% | 0% | 0.002 | - | - | - |

## Verdict (pre-registered, TEST)

- arms sent to TEST: ['head64'] (passed)
- head64: flip 100%, matched random 8% (rhead64), Fisher p 1.3460761879122359e-06, broken 0%, kept 96%: MEANINGFUL

- length (tokens) per arm: attr1024 mean 2852 / <300 2%, base mean 2492 / <300 0%, head64 mean 598 / <300 32%, rand1024 mean 2554 / <300 0%, rhead64 mean 2683 / <300 0%, ro_c0.2 mean 2379 / <300 2%, ro_rand_c0.2 mean 2595 / <300 1%, tail1024 mean 2645 / <300 2%
## X3 (사후) AM, 24 targets x 3 seeds, CALIBRATION

- classes: excluded:base_broken 21, reference 63, target 24

| arm | targets | flip | broken | refs | kept | turned | S | matched random flip | gap | Fisher p |
|---|---|---|---|---|---|---|---|---|---|---|
| base | 24 | 0% | 0% | 63 | 100% | 0% | 0.0 | - | - | - |
| attr1024 | 24 | 62% | 38% | 63 | 43% | 0% | 0.167 | 38% (rand1024) | +25% | 0.0741 |
| head64 | 24 | 88% | 12% | 63 | 95% | 0% | 0.729 | 4% (rhead64) | +83% | 0.0000 |
| rand1024 | 24 | 38% | 17% | 63 | 54% | 27% | 0.169 | - | - | - |
| rhead64 | 24 | 4% | 96% | 63 | 5% | 6% | 0.0 | - | - | - |
| ro_c0.2 | 24 | 79% | 21% | 63 | 43% | 2% | 0.269 | 25% (ro_rand_c0.2) | +54% | 0.0002 |
| ro_rand_c0.2 | 24 | 25% | 54% | 63 | 33% | 8% | 0.038 | - | - | - |
| tail1024 | 24 | 75% | 25% | 63 | 73% | 2% | 0.411 | 38% (rand1024) | +38% | 0.0095 |

- length (tokens) per arm: band1024_L24_31 mean 2959 / <300 0%, band256_L24_31 mean 2728 / <300 2%, base mean 2450 / <300 0%, rband1024_L24_31 mean 2382 / <300 3%, rband256_L24_31 mean 2623 / <300 0%, tailband1024_L24_31 mean 2832 / <300 1%
## X7 (사후) AM late-band set, 24 targets x 3 seeds, CALIBRATION

- classes: excluded:base_broken 11, reference 68, target 29

| arm | targets | flip | broken | refs | kept | turned | S | matched random flip | gap | Fisher p |
|---|---|---|---|---|---|---|---|---|---|---|
| base | 29 | 0% | 0% | 68 | 100% | 0% | 0.0 | - | - | - |
| band1024_L24_31 | 29 | 48% | 52% | 68 | 40% | 0% | 0.093 | 52% (rband1024_L24_31) | -3% | 0.7001 |
| band256_L24_31 | 29 | 66% | 34% | 68 | 53% | 6% | 0.227 | 59% (rband256_L24_31) | +7% | 0.3935 |
| rband1024_L24_31 | 29 | 52% | 10% | 68 | 60% | 26% | 0.28 | - | - | - |
| rband256_L24_31 | 29 | 59% | 3% | 68 | 66% | 18% | 0.375 | - | - | - |
| tailband1024_L24_31 | 29 | 79% | 21% | 68 | 62% | 1% | 0.389 | 52% (rband1024_L24_31) | +28% | 0.0259 |

- length (tokens) per arm: attr1024_mk mean 2670 / <300 0%, attr256_mk mean 2606 / <300 1%, base mean 2613 / <300 1%, rand1024_mk mean 2593 / <300 1%, rand256_mk mean 2606 / <300 1%
## X9 (사후) AM decision-local edits (24 tokens after <tool_use:), 24 targets x 3 seeds, CALIBRATION

- classes: excluded:base_broken 15, reference 69, target 24

| arm | targets | flip | broken | refs | kept | turned | S | matched random flip | gap | Fisher p |
|---|---|---|---|---|---|---|---|---|---|---|
| base | 24 | 0% | 0% | 69 | 100% | 0% | 0.0 | - | - | - |
| attr1024_mk | 24 | 83% | 8% | 69 | 99% | 0% | 0.753 | 25% (rand1024_mk) | +58% | 0.0001 |
| attr256_mk | 24 | 75% | 12% | 69 | 97% | 1% | 0.637 | 12% (rand256_mk) | +62% | 0.0000 |
| rand1024_mk | 24 | 25% | 0% | 69 | 97% | 3% | 0.243 | - | - | - |
| rand256_mk | 24 | 12% | 0% | 69 | 90% | 7% | 0.112 | - | - | - |

- advance1.json: stage t1, arms ['head64'], gate passed
