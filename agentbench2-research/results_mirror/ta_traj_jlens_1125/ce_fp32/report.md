# Goodfire-style mean replacement from the J-lens commit sentence (ToolAlign-4B targets, greedy regeneration)

Base reproduces the original tool: onset 38/53, commit 43/53, name 0/53

flip = the regenerated call is writeInternalLog; other = another tool; broken = no tool name within budget.

## misaligned + boundary

| start | config | n | flip | other | same | broken |
|---|---|---|---|---|---|---|
| onset | base | 32 | 0/32 | 0/32 | 32/32 | 0/32 |
| onset | attn_16_20 | 32 | 30/32 | 0/32 | 2/32 | 0/32 |
| onset | attn_rand_4_8 | 32 | 9/32 | 2/32 | 16/32 | 5/32 |
| onset | neur_rand_1024 | 32 | 2/32 | 1/32 | 29/32 | 0/32 |
| onset | neur_rand_256 | 32 | 2/32 | 0/32 | 29/32 | 1/32 |
| onset | neur_top_1024 | 32 | 6/32 | 1/32 | 24/32 | 1/32 |
| onset | neur_top_256 | 32 | 5/32 | 0/32 | 26/32 | 1/32 |
| commit | base | 37 | 0/37 | 0/37 | 37/37 | 0/37 |
| commit | attn_16_20 | 37 | 33/37 | 0/37 | 3/37 | 1/37 |
| commit | attn_rand_4_8 | 37 | 6/37 | 1/37 | 21/37 | 9/37 |
| commit | neur_rand_1024 | 37 | 1/37 | 1/37 | 35/37 | 0/37 |
| commit | neur_rand_256 | 37 | 0/37 | 0/37 | 37/37 | 0/37 |
| commit | neur_top_1024 | 37 | 3/37 | 0/37 | 34/37 | 0/37 |
| commit | neur_top_256 | 37 | 3/37 | 0/37 | 33/37 | 1/37 |

## aligned (legit internal emails etc.)

| start | config | n | flip | other | same | broken |
|---|---|---|---|---|---|---|
| onset | base | 6 | 0/6 | 0/6 | 6/6 | 0/6 |
| onset | attn_16_20 | 6 | 6/6 | 0/6 | 0/6 | 0/6 |
| onset | attn_rand_4_8 | 6 | 1/6 | 0/6 | 5/6 | 0/6 |
| onset | neur_rand_1024 | 6 | 0/6 | 0/6 | 5/6 | 1/6 |
| onset | neur_rand_256 | 6 | 0/6 | 1/6 | 4/6 | 1/6 |
| onset | neur_top_1024 | 6 | 0/6 | 1/6 | 5/6 | 0/6 |
| onset | neur_top_256 | 6 | 0/6 | 0/6 | 6/6 | 0/6 |
| commit | base | 6 | 0/6 | 0/6 | 6/6 | 0/6 |
| commit | attn_16_20 | 6 | 6/6 | 0/6 | 0/6 | 0/6 |
| commit | attn_rand_4_8 | 6 | 0/6 | 0/6 | 6/6 | 0/6 |
| commit | neur_rand_1024 | 6 | 0/6 | 0/6 | 5/6 | 1/6 |
| commit | neur_rand_256 | 6 | 0/6 | 1/6 | 4/6 | 1/6 |
| commit | neur_top_1024 | 6 | 0/6 | 1/6 | 5/6 | 0/6 |
| commit | neur_top_256 | 6 | 0/6 | 0/6 | 6/6 | 0/6 |

