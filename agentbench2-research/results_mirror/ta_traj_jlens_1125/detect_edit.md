# Detect, then edit (ToolAlign-4B targets; LODO 20-key detector, threshold = 90th pct of training negatives)

Edit applied only where the held-out detector fires. 'all' = edit every target (no detector).

| window | start | config | fail: fired / n | fail blocked | aligned: fired / n | aligned harmed | refs fired (no edit rows) |
|---|---|---|---|---|---|---|---|
| all | onset | attn_16_20 | 32/32 | 30/32 | 6/6 | 6/6 | - |
| doc | onset | attn_16_20 | 9/32 | 8/32 | 4/6 | 4/6 | 9/159 |
| in64 | onset | attn_16_20 | 9/32 | 7/32 | 4/6 | 4/6 | 9/159 |
| first64 | onset | attn_16_20 | 20/22 | 19/22 | 2/2 | 2/2 | 15/16 |
| last64 | onset | attn_16_20 | 21/22 | 19/22 | 1/2 | 1/2 | 11/16 |
| scaffold | onset | attn_16_20 | 26/32 | 24/32 | 3/6 | 3/6 | 15/159 |
| all | onset | attn_rand_4_8 | 32/32 | 9/32 | 6/6 | 1/6 | - |
| doc | onset | attn_rand_4_8 | 9/32 | 1/32 | 4/6 | 0/6 | 9/159 |
| in64 | onset | attn_rand_4_8 | 9/32 | 2/32 | 4/6 | 0/6 | 9/159 |
| first64 | onset | attn_rand_4_8 | 20/22 | 5/22 | 2/2 | 1/2 | 15/16 |
| last64 | onset | attn_rand_4_8 | 21/22 | 5/22 | 1/2 | 1/2 | 11/16 |
| scaffold | onset | attn_rand_4_8 | 26/32 | 7/32 | 3/6 | 1/6 | 15/159 |
| all | onset | neur_top_256 | 32/32 | 5/32 | 6/6 | 0/6 | - |
| doc | onset | neur_top_256 | 9/32 | 0/32 | 4/6 | 0/6 | 9/159 |
| in64 | onset | neur_top_256 | 9/32 | 0/32 | 4/6 | 0/6 | 9/159 |
| first64 | onset | neur_top_256 | 20/22 | 5/22 | 2/2 | 0/2 | 15/16 |
| last64 | onset | neur_top_256 | 21/22 | 5/22 | 1/2 | 0/2 | 11/16 |
| scaffold | onset | neur_top_256 | 26/32 | 5/32 | 3/6 | 0/6 | 15/159 |
| all | onset | neur_top_1024 | 32/32 | 6/32 | 6/6 | 1/6 | - |
| doc | onset | neur_top_1024 | 9/32 | 0/32 | 4/6 | 1/6 | 9/159 |
| in64 | onset | neur_top_1024 | 9/32 | 1/32 | 4/6 | 1/6 | 9/159 |
| first64 | onset | neur_top_1024 | 20/22 | 5/22 | 2/2 | 1/2 | 15/16 |
| last64 | onset | neur_top_1024 | 21/22 | 5/22 | 1/2 | 0/2 | 11/16 |
| scaffold | onset | neur_top_1024 | 26/32 | 5/32 | 3/6 | 1/6 | 15/159 |
| all | commit | attn_16_20 | 37/37 | 33/37 | 6/6 | 6/6 | - |
| doc | commit | attn_16_20 | 10/37 | 8/37 | 4/6 | 4/6 | 9/159 |
| in64 | commit | attn_16_20 | 13/37 | 10/37 | 4/6 | 4/6 | 9/159 |
| first64 | commit | attn_16_20 | 24/27 | 20/27 | 2/2 | 2/2 | 15/16 |
| last64 | commit | attn_16_20 | 26/27 | 22/27 | 1/2 | 1/2 | 11/16 |
| scaffold | commit | attn_16_20 | 31/37 | 27/37 | 3/6 | 3/6 | 15/159 |
| all | commit | attn_rand_4_8 | 37/37 | 6/37 | 6/6 | 0/6 | - |
| doc | commit | attn_rand_4_8 | 10/37 | 1/37 | 4/6 | 0/6 | 9/159 |
| in64 | commit | attn_rand_4_8 | 13/37 | 2/37 | 4/6 | 0/6 | 9/159 |
| first64 | commit | attn_rand_4_8 | 24/27 | 2/27 | 2/2 | 0/2 | 15/16 |
| last64 | commit | attn_rand_4_8 | 26/27 | 2/27 | 1/2 | 0/2 | 11/16 |
| scaffold | commit | attn_rand_4_8 | 31/37 | 4/37 | 3/6 | 0/6 | 15/159 |
| all | commit | neur_top_256 | 37/37 | 3/37 | 6/6 | 0/6 | - |
| doc | commit | neur_top_256 | 10/37 | 1/37 | 4/6 | 0/6 | 9/159 |
| in64 | commit | neur_top_256 | 13/37 | 0/37 | 4/6 | 0/6 | 9/159 |
| first64 | commit | neur_top_256 | 24/27 | 1/27 | 2/2 | 0/2 | 15/16 |
| last64 | commit | neur_top_256 | 26/27 | 2/27 | 1/2 | 0/2 | 11/16 |
| scaffold | commit | neur_top_256 | 31/37 | 3/37 | 3/6 | 0/6 | 15/159 |
| all | commit | neur_top_1024 | 37/37 | 3/37 | 6/6 | 1/6 | - |
| doc | commit | neur_top_1024 | 10/37 | 0/37 | 4/6 | 1/6 | 9/159 |
| in64 | commit | neur_top_1024 | 13/37 | 1/37 | 4/6 | 1/6 | 9/159 |
| first64 | commit | neur_top_1024 | 24/27 | 1/27 | 2/2 | 1/2 | 15/16 |
| last64 | commit | neur_top_1024 | 26/27 | 2/27 | 1/2 | 0/2 | 11/16 |
| scaffold | commit | neur_top_1024 | 31/37 | 2/37 | 3/6 | 1/6 | 15/159 |
