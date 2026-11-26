# Overnight search, ToolAlign leg (2080 Ti, fp32, ta_commit_edit harness; sets picked on the other domain fold)

flip = the regenerated call is writeInternalLog (targets whose base reproduces the original tool); broken = no tool name; refs kept = references (writeInternalLog originally) that still call it.

Base reproduces: onset 61/77, commit 43/53, name 0/53

## Targets (misaligned + boundary)

| start | arm | n | flip | broken | matched random flip | gap | Fisher p | Holm p | refs kept |
|---|---|---|---|---|---|---|---|---|---|
| onset | base | 32 | 0% | 0% | - | - | - | - | 100% |
| onset | attr256 | 32 | 34% | 3% | 3% | +31% | 0.0013 | 0.0093 | 91% |
| onset | rand256 | 32 | 3% | 12% | - | - | - | - | 91% |
| onset | attr1024 | 32 | 50% | 25% | 38% | +12% | 0.2250 | 0.9001 | 61% |
| onset | rand1024 | 32 | 38% | 3% | - | - | - | - | 100% |
| onset | attr1024_b2 | 32 | 9% | 75% | 25% | -16% | 0.9783 | 1.0000 | 17% |
| onset | rand1024_b2 | 32 | 25% | 9% | - | - | - | - | 96% |
| onset | tail1024 | 32 | 22% | 6% | 38% | -16% | 0.9503 | 1.0000 | 83% |
| onset | ro_c0.2 | 32 | 69% | 28% | 16% | +53% | 0.0000 | 0.0001 | 74% |
| onset | ro_rand_c0.2 | 32 | 16% | 22% | - | - | - | - | 57% |
| commit | base | 37 | 0% | 0% | - | - | - | - | 100% |
| commit | attr256 | 37 | 32% | 0% | 8% | +24% | 0.0093 | 0.0559 | 91% |
| commit | rand256 | 37 | 8% | 0% | - | - | - | - | 91% |
| commit | attr1024 | 37 | 51% | 22% | 14% | +38% | 0.0005 | 0.0040 | 61% |
| commit | rand1024 | 37 | 14% | 3% | - | - | - | - | 100% |
| commit | attr1024_b2 | 37 | 35% | 54% | 19% | +16% | 0.0950 | 0.4749 | 17% |
| commit | rand1024_b2 | 37 | 19% | 3% | - | - | - | - | 96% |
| commit | tail1024 | 37 | 16% | 0% | 14% | +3% | 0.5000 | 1.0000 | 83% |
| commit | ro_c0.2 | 37 | 73% | 24% | 8% | +65% | 0.0000 | 0.0000 | 74% |
| commit | ro_rand_c0.2 | 37 | 8% | 14% | - | - | - | - | 57% |
| name | base | 0 | - | - | - | - | - | - | 100% |
| name | attr256 | 0 | - | - | 0% | +0% | - | - | 91% |
| name | rand256 | 0 | - | - | - | - | - | - | 91% |
| name | attr1024 | 0 | - | - | 0% | +0% | - | - | 61% |
| name | rand1024 | 0 | - | - | - | - | - | - | 100% |
| name | attr1024_b2 | 0 | - | - | 0% | +0% | - | - | 17% |
| name | rand1024_b2 | 0 | - | - | - | - | - | - | 96% |
| name | tail1024 | 0 | - | - | 0% | +0% | - | - | 83% |
| name | ro_c0.2 | 0 | - | - | 0% | +0% | - | - | 74% |
| name | ro_rand_c0.2 | 0 | - | - | - | - | - | - | 57% |

## Verdict (pre-registered)

- onset / attr256: MEANINGFUL
- onset / attr1024: not meaningful
- onset / attr1024_b2: not meaningful
- onset / tail1024: not meaningful
- onset / ro_c0.2: not meaningful
- commit / attr256: not meaningful
- commit / attr1024: not meaningful
- commit / attr1024_b2: not meaningful
- commit / tail1024: not meaningful
- commit / ro_c0.2: not meaningful
- name / attr256: not meaningful
- name / attr1024: not meaningful
- name / attr1024_b2: not meaningful
- name / tail1024: not meaningful
- name / ro_c0.2: not meaningful
