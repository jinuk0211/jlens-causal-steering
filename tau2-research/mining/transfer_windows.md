# Unneeded vs legitimate transfer with J-lens words from every logged position (278 f_detect episodes)

rows: bad 19 (19 tasks), good 56; turn index alone AUC 0.599; mean preamble length (tokens before <tool_call>): bad 101, good 160

| window | features | K | AUC | turn-residualized | null mean / 95th / max | p |
|---|---|---|---|---|---|---|
| prev | J-lens words | 10 | 0.699 | 0.661 | 0.514 / 0.634 / 0.687 | 0.00 |
| prev | J-lens words | 30 | 0.715 | 0.669 | 0.516 / 0.645 / 0.694 | 0.00 |
| prev | J-lens words | 100 | 0.729 | 0.695 | 0.516 / 0.655 / 0.691 | 0.00 |
| prev | surface tokens | 10 | 0.726 | 0.762 | 0.540 / 0.653 / 0.689 | 0.00 |
| prev | surface tokens | 30 | 0.783 | 0.789 | 0.544 / 0.659 / 0.732 | 0.00 |
| prev | surface tokens | 100 | 0.749 | 0.748 | 0.553 / 0.660 / 0.681 | 0.00 |
| ctx | J-lens words | 10 | 0.739 | 0.735 | 0.511 / 0.675 / 0.729 | 0.00 |
| ctx | J-lens words | 30 | 0.709 | 0.705 | 0.510 / 0.670 / 0.735 | 0.02 |
| ctx | J-lens words | 100 | 0.678 | 0.679 | 0.513 / 0.646 / 0.679 | 0.01 |
| ctx | surface tokens | 10 | 0.783 | 0.797 | 0.542 / 0.673 / 0.730 | 0.00 |
| ctx | surface tokens | 30 | 0.719 | 0.725 | 0.561 / 0.689 / 0.756 | 0.01 |
| ctx | surface tokens | 100 | 0.616 | 0.638 | 0.535 / 0.648 / 0.691 | 0.10 |
| gen | J-lens words | 10 | 0.770 | 0.760 | 0.505 / 0.641 / 0.779 | 0.01 |
| gen | J-lens words | 30 | 0.803 | 0.782 | 0.503 / 0.647 / 0.764 | 0.00 |
| gen | J-lens words | 100 | 0.794 | 0.766 | 0.509 / 0.634 / 0.768 | 0.00 |
| gen | surface tokens | 10 | 0.723 | 0.745 | 0.525 / 0.643 / 0.738 | 0.02 |
| gen | surface tokens | 30 | 0.618 | 0.617 | 0.553 / 0.667 / 0.685 | 0.18 |
| gen | surface tokens | 100 | 0.477 | 0.507 | 0.566 / 0.704 / 0.735 | 0.85 |
| all | J-lens words | 10 | 0.688 | 0.671 | 0.518 / 0.657 / 0.727 | 0.02 |
| all | J-lens words | 30 | 0.729 | 0.716 | 0.515 / 0.646 / 0.710 | 0.00 |
| all | J-lens words | 100 | 0.779 | 0.756 | 0.516 / 0.650 / 0.725 | 0.00 |
| all | surface tokens | 10 | 0.652 | 0.628 | 0.527 / 0.667 / 0.686 | 0.08 |
| all | surface tokens | 30 | 0.744 | 0.743 | 0.536 / 0.651 / 0.683 | 0.00 |
| all | surface tokens | 100 | 0.750 | 0.747 | 0.550 / 0.656 / 0.673 | 0.00 |

Most lopsided J-lens words per window (all rows, descriptive; count = rows with the word, bad of 19 vs good of 56):

- prev, more in BAD: A/L13 ' Remain' 7/19 vs 0/56; C/L15 ' accurate' 7/19 vs 0/56; A/L20 '余额' 7/19 vs 0/56; A/L23 ' names' 7/19 vs 0/56; A/L23 'altern' 7/19 vs 0/56; A/L23 ' alternativ' 7/19 vs 0/56; A/L26 ' methodology' 7/19 vs 0/56; A/L31 '_cal' 7/19 vs 0/56; C/L4 "'>" 6/19 vs 0/56; C/L10 ' instead' 6/19 vs 0/56; A/L15 'stay' 6/19 vs 0/56; A/L18 '余额' 6/19 vs 0/56
- prev, more in GOOD: C/L30 ' Invalid' 0/19 vs 33/56; C/L16 '或缺' 0/19 vs 32/56; C/L31 ' services' 0/19 vs 30/56; A/L20 '发生了什么' 0/19 vs 30/56; C/L18 '”*' 0/19 vs 30/56; C/L15 ' suspicious' 0/19 vs 30/56; C/Lany '似乎是' 0/19 vs 28/56; C/Lany 'JKLM' 0/19 vs 27/56; C/L23 '_air' 0/19 vs 27/56; C/Lany ' KC' 0/19 vs 26/56; C/Lany '_service' 0/19 vs 26/56; C/L27 'Service' 0/19 vs 26/56
- ctx, more in BAD: C/L17 ' necessary' 6/19 vs 0/56; C/L26 '—including' 6/19 vs 0/56; C/L28 '-have' 6/19 vs 0/56; C/L29 ' incapable' 6/19 vs 0/56; C/L30 ' recommended' 6/19 vs 0/56; C/L22 ' suggested' 6/19 vs 0/56; C/L31 ' Be' 6/19 vs 0/56; A/Lany '再见' 6/19 vs 0/56; C/Lany ' countless' 6/19 vs 0/56; C/L0 'inals' 5/19 vs 0/56; C/L0 ' }</' 5/19 vs 0/56; C/L26 ' specifying' 5/19 vs 0/56
- ctx, more in GOOD: A/Lany '我看到' 0/19 vs 29/56; D/L20 '情况说明' 0/19 vs 27/56; D/L19 '情况说明' 0/19 vs 26/56; A/L23 '我看到' 0/19 vs 25/56; A/L26 '我看到' 0/19 vs 25/56; C/L25 '显示的' 0/19 vs 24/56; C/Lany '情况进行了' 0/19 vs 23/56; C/L21 ' flagged' 0/19 vs 23/56; D/L28 ' Congratulations' 0/19 vs 23/56; C/L22 '情况进行了' 0/19 vs 22/56; D/L22 '报告显示' 0/19 vs 22/56; C/L19 ' stats' 0/19 vs 22/56
- gen, more in BAD: G/L21 ' którzy' 6/19 vs 0/56; G/Lany ' INCLUDING' 6/19 vs 0/56; G/Lany '不方便' 6/19 vs 0/56; G/L18 '包括了' 6/19 vs 0/56; G/L28 '的人力资源' 5/19 vs 0/56; G/L20 '姓名' 5/19 vs 0/56; G/L21 ' INCLUDING' 5/19 vs 0/56; G/L21 'INCLUDING' 5/19 vs 0/56; G/L21 ' quien' 5/19 vs 0/56; G/L21 'Including' 5/19 vs 0/56; G/L21 '姓名' 5/19 vs 0/56; G/L21 ' включая' 5/19 vs 0/56
- gen, more in GOOD: G/L25 '显示' 0/19 vs 31/56; G/L31 '显示' 0/19 vs 31/56; G/Lany '显示了' 0/19 vs 30/56; G/Lany ' showed' 0/19 vs 30/56; G/L30 ' showed' 0/19 vs 30/56; G/L29 ' indicates' 0/19 vs 30/56; G/L25 '显示了' 0/19 vs 29/56; G/L31 ' showed' 0/19 vs 29/56; G/L14 ' recovery' 0/19 vs 29/56; G/L21 ' violations' 0/19 vs 29/56; G/L27 '_due' 0/19 vs 28/56; G/L26 '显示了' 0/19 vs 28/56
