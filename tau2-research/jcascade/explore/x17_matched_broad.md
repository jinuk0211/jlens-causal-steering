# X17: any J-lens word, any layer: unneeded transfer vs same-task denial (R3 (C) rows)

rows: bad 15 (12 tasks), denial 26, task clusters 12; within-task label-permutation null, 100 permutations, selection + CV rerun each time

| detector | AUC (pooled OOF) | within-task AUC | null mean | null 95th pct | null max | p (null >= observed) |
|---|---|---|---|---|---|---|
| J_pairs (bad-direction, K30) | 0.736 | 0.781 | 0.534 | 0.698 | 0.805 | 0.02 |
| turn index | 0.586 | 0.844 | 0.443 | 0.522 | 0.541 | 0.00 |
| broad J-lens K10 | 0.824 | 0.828 | 0.503 | 0.695 | 0.792 | 0.00 |
| broad J++ K10 | 0.753 | 0.953 | 0.495 | 0.668 | 0.755 | 0.01 |
| broad J-lens+J++ K10 | 0.794 | 0.906 | 0.500 | 0.681 | 0.781 | 0.00 |
| broad J-lens K30 | 0.790 | 0.906 | 0.509 | 0.685 | 0.804 | 0.01 |
| broad J++ K30 | 0.813 | 0.969 | 0.493 | 0.681 | 0.777 | 0.00 |
| broad J-lens+J++ K30 | 0.804 | 0.938 | 0.496 | 0.674 | 0.755 | 0.00 |
| broad J-lens K100 | 0.737 | 0.859 | 0.519 | 0.707 | 0.735 | 0.00 |
| broad J++ K100 | 0.854 | 0.969 | 0.510 | 0.714 | 0.769 | 0.00 |
| broad J-lens+J++ K100 | 0.844 | 0.969 | 0.502 | 0.689 | 0.760 | 0.00 |
| residual L10 (logistic) | 0.782 | 0.938 | 0.496 | 0.672 | 0.779 | 0.00 |
| residual L12 (logistic) | 0.890 | 0.969 | 0.500 | 0.689 | 0.826 | 0.00 |
| residual L14 (logistic) | 0.862 | 0.969 | 0.504 | 0.688 | 0.823 | 0.00 |
| residual L16 (logistic) | 0.797 | 0.969 | 0.518 | 0.666 | 0.831 | 0.01 |
| residual L18 (logistic) | 0.849 | 0.969 | 0.510 | 0.687 | 0.790 | 0.00 |

Most lopsided features on all rows (descriptive only, not cross-validated): J++/L24/'   \n\n' bad 8/15 denial 0/26; J/L16/' Customer' bad 8/15 denial 0/26; J++/Lany/' Complaint' bad 8/15 denial 0/26; J/L18/' FINAL' bad 7/15 denial 0/26; J/L17/'  \r\n\r\n' bad 7/15 denial 0/26; J++/L13/' complaint' bad 7/15 denial 0/26; J/L21/'   \n\n' bad 6/15 denial 0/26; J/L23/' Recogn' bad 6/15 denial 0/26; J++/L26/' goodbye' bad 6/15 denial 0/26; J++/Lany/'Σ' bad 6/15 denial 0/26; J++/L31/'Σ' bad 6/15 denial 0/26; J++/Lany/'ürg' bad 6/15 denial 0/26; J/L31/'<|im_start|>' bad 6/15 denial 0/26; J/Lany/'UM' bad 6/15 denial 0/26; J/L31/'UM' bad 6/15 denial 0/26; J/Lany/'(...' bad 6/15 denial 0/26; J/Lany/'Transfer' bad 6/15 denial 0/26; J/L31/'Transfer' bad 6/15 denial 0/26; J++/Lany/'<|im_start|>' bad 6/15 denial 0/26; J/L14/'.…' bad 6/15 denial 0/26
