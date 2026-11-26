# Overnight search, ToolAlign leg (2080 Ti, fp32, ta_commit_edit harness; sets picked on the other domain fold)

flip = the regenerated call is writeInternalLog (targets whose base reproduces the original tool); broken = no tool name; refs kept = references (writeInternalLog originally) that still call it.

Base reproduces: onset 61/77, commit 43/53, name 0/0

## Targets (misaligned + boundary)

| start | arm | n | flip | broken | matched random flip | gap | Fisher p | Holm p | refs kept | aligned targets turned to log |
|---|---|---|---|---|---|---|---|---|---|---|
| onset | base | 32 | 0% | 0% | - | - | - | - | 100% | 0/6 |
| onset | xfer1024 | 32 | 3% | 6% | 28% | -25% | 0.9996 | 1.0000 | 57% | 0/6 |
| onset | rxfer1024 | 32 | 28% | 3% | - | - | - | - | 96% | 4/6 |
| onset | attn_16_20 | 32 | 94% | 0% | 28% | +66% | 0.0000 | 0.0000 | 100% | 6/6 |
| onset | attn_rand_4_8 | 32 | 28% | 16% | - | - | - | - | 87% | 1/6 |
| commit | base | 37 | 0% | 0% | - | - | - | - | 100% | 0/6 |
| commit | xfer1024 | 37 | 8% | 3% | 16% | -8% | 0.9239 | 1.0000 | 57% | 0/6 |
| commit | rxfer1024 | 37 | 16% | 5% | - | - | - | - | 96% | 3/6 |
| commit | attn_16_20 | 37 | 89% | 3% | 16% | +73% | 0.0000 | 0.0000 | 100% | 6/6 |
| commit | attn_rand_4_8 | 37 | 16% | 24% | - | - | - | - | 87% | 0/6 |

## Verdict (pre-registered)

- onset / xfer1024: not meaningful
- onset / attn_16_20: MEANINGFUL
- commit / xfer1024: not meaningful
- commit / attn_16_20: MEANINGFUL
