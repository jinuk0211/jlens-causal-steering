# Overnight search, ToolAlign leg (2080 Ti, fp32, ta_commit_edit harness; sets picked on the other domain fold)

flip = the regenerated call is writeInternalLog (targets whose base reproduces the original tool); broken = no tool name; refs kept = references (writeInternalLog originally) that still call it.

Base reproduces: onset 61/77, commit 43/53, name 0/0

## Targets (misaligned + boundary)

| start | arm | n | flip | broken | matched random flip | gap | Fisher p | Holm p | refs kept | aligned targets turned to log |
|---|---|---|---|---|---|---|---|---|---|---|
| onset | base | 32 | 0% | 0% | - | - | - | - | 100% | 0/6 |
| onset | det_attr256 | 32 | 12% | 12% | 16% | -3% | 0.7629 | 1.0000 | 100% | 2/6 |
| onset | det_attr1024 | 32 | 9% | 22% | 16% | -6% | 0.8717 | 1.0000 | 100% | 3/6 |
| onset | det_tail1024 | 32 | 19% | 6% | 16% | +3% | 0.5000 | 1.0000 | 100% | 3/6 |
| onset | det_rand1024 | 32 | 16% | 9% | - | - | - | - | 100% | 0/6 |
| commit | base | 37 | 0% | 0% | - | - | - | - | 100% | 0/6 |
| commit | det_attr256 | 37 | 5% | 0% | 0% | +5% | 0.2466 | 0.9863 | 100% | 2/6 |
| commit | det_attr1024 | 37 | 24% | 5% | 0% | +24% | 0.0011 | 0.0068 | 100% | 3/6 |
| commit | det_tail1024 | 37 | 14% | 0% | 0% | +14% | 0.0271 | 0.1353 | 100% | 3/6 |
| commit | det_rand1024 | 37 | 0% | 5% | - | - | - | - | 100% | 0/6 |

## Verdict (pre-registered)

- onset / det_attr256: not meaningful
- onset / det_attr1024: not meaningful
- onset / det_tail1024: not meaningful
- commit / det_attr256: not meaningful
- commit / det_attr1024: not meaningful
- commit / det_tail1024: not meaningful
