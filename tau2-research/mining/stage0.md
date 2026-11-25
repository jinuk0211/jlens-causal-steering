# J-Cascade stage 0: transfer decisions only

- bad (unneeded transfer, failed episode) 19, good (transfer in passed episode) 56; by (domain, label): {'airline_bad': 10, 'airline_good': 21, 'retail_good': 8, 'retail_bad': 4, 'telecom_good': 27, 'telecom_bad': 5}
- user asked for a human: bad 0.68, good 0.38

| score | AUC | 95% CI | airline | retail | telecom |
|---|---|---|---|---|---|
| J_cascade | 0.664 | [0.514, 0.805] | 0.586 | 0.5 | 0.911 |
| J_pairs | 0.763 | [0.632, 0.872] | 0.681 | 0.75 | 0.852 |
| B_user_asked_human | 0.655 | [0.525, 0.776] | 0.588 | 0.625 | 0.626 |
| B_rel_pos | 0.609 | [0.466, 0.747] | 0.774 | 0.297 | 0.807 |
| B_tool_errors | 0.492 | [0.437, 0.56] | 0.55 | 0.312 | 0.481 |
| B_domain | 0.434 | [0.273, 0.592] | 0.455 | 0.172 | 0.156 |
| B_logistic_all | 0.482 | [0.323, 0.638] | 0.543 | 0.031 | 0.481 |

- PRE-REGISTERED PASS (best J >= 0.75 and >= best baseline + 0.05): **True** (best J J_pairs 0.7631578947368421, best baseline B_user_asked_human 0.6546052631578947)

median family rank at its layer (101 = absent):

- L20 inability: bad 7.0, good 16.0
- L22 apology: bad 2.0, good 2.0
- L24 understanding: bad 1.0, good 10.0
- L26 acknowledgement: bad 82.0, good 101.0
- L29 justification: bad 38.0, good 16.0
