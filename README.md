# 실험 결과 모음 (2026-11-16 ~ 11-26)

τ²-bench, ToolAlignBench, agentic-misalignment(AM), AgentDojo에서 J-lens 판독과 steering·인과 개입으로 한 실험의 결과입니다.
2026-11-26 19:1x KST 스냅샷입니다. 첫 스냅샷(11-25 21:2x, 커밋 a07ff8f)에 그 뒤 결과를 더했습니다.

먼저 읽을 것은 두 문서입니다.
- [HISTORY_1-55_20261126.md](HISTORY_1-55_20261126.md): 1~55부 전체 기록입니다. 시간순이고 맨 위에 목차가 있습니다. 요약은 10부, 19부, 26부, 36부, 46부, 55부에 있습니다. 앞 내용을 뒤에서 고친 곳은 목차 앞에 따로 모아 두었습니다.
- [SAFETY_EXPERIMENTS_20261126.md](SAFETY_EXPERIMENTS_20261126.md): ToolAlignBench·AM·AgentDojo 실험을 주제별로 정리한 문서입니다(11-26 17:3x 기준). 0절 표에 질문별 답이 있습니다.

## 폴더

| 폴더 | 내용 | 기록 |
|---|---|---|
| [tau2-research/](tau2-research/) | τ² 연구 루프: PLAN.md(사전 등록과 로그), WRITEUP_draft.md, J-Cascade, M1, C-LOOP(circuit), baseline_why, C2T, NL 판정 | 1~16부, 30부 |
| [tau2-topk-20261119/](tau2-topk-20261119/) | 기본 실행 278개의 에피소드별 메타데이터(json). 층별 top-k 배열(npz)은 빠져 있음 | 6부 |
| [toolalign-research/](toolalign-research/) | ToolAlignBench: Qwen3.5-4B(server), Gemma-4-E4B-it(server_gemma), Qwen3.5-9B(server_q9). 대화 기록 md, metrics, 행동 라벨, J-lens, CAUSAL-1/2 | 17~26부 |
| [agentbench2-research/](agentbench2-research/) | AM과 AgentDojo. 아래 표 참고 | 31~55부 |
| [neuron-explorer-cases/](neuron-explorer-cases/) | neuron-explorer UI에 ToolAlign 궤적 212개를 "#case N"으로 넣은 파일 3개(ne_cases.py, cases.js, index.html). 원본 리포 [lyramakesmusic/neuron-explorer](https://github.com/lyramakesmusic/neuron-explorer)의 `explorer/` 아래에 덮어 쓰는 파일입니다 | 40부 |
| [vast-fsteer/](vast-fsteer/) | vast 상자에서 실패 턴에만 공식 baseline steering (중단) | 29부 |
| [vast-archive-20261125/](vast-archive-20261125/) | 삭제한 vast 상자 2개의 보관본 목록(README만) | 38부 이후 |

### agentbench2-research/ 안

| 경로 | 내용 | 기록 |
|---|---|---|
| PLAN.md | 사전 등록(경계 규칙, TEST 기준, N1~N4)과 로그. 11-26 로그에 neuron-explorer와 2080 Ti AM 실험(프롬프트 유형별 뉴런, AM steering, 토큰별 흐름)도 있음 | 31~39부 |
| OVERNIGHT.md | 11-25 밤 기여도 뉴런 탐색: 사전 등록과 최종 보고 | 41~47부 |
| OVERNIGHT2.md | 11-26 실패 기반 루프(hard negative, clamp, onset probe)와 뉴런 트랙 T1~T9: 사전 등록과 로그 | 49~55부 |
| code/ | 분석 코드(ab_core, ab_ne, ab_hn, ab_strict, ab_serve_steer 등) | |
| am_results/, am18/ | AM 생성 결과와 Haiku 판정, AM 18조건 설정 | 32부 |
| results_mirror/srch_2215 | 야간 탐색 결과(세 벤치마크의 뉴런 집합, 행 단위 결과) | 41~46부 |
| results_mirror/ta_traj_jlens_1125 | ToolAlign 궤적 뉴런 기록, 결정 문장 편집(2080 Ti, fp32) | 40부, 44부 |
| results_mirror/hn_1126 | T1·T2·T3·T6, 에피소드 전체 실험(X14·X15), 감지 표 | 50~54부 |
| results_mirror/am18_explorer, am_steer, flow_temporal | AM 18조건 프롬프트 유형별 뉴런, AM steering 루프, 응답 600개의 토큰별 흐름 시간 분석(모두 2080 Ti) | PLAN.md 11-26 13:1x~18:3x 로그 |
| xfer/ | RTX 3090 상자에서 돌린 AM test 행 목록 | 37~39부 |

ToolAlign의 원본 trace(`*.trace.json`, 모델별 128개)는 용량 때문에 각 결과 폴더의 `traces.tar.gz`로 묶었습니다.
풀려면 `tar -xzf traces.tar.gz`를 실행하면 됩니다. 같은 대화의 읽기 쉬운 버전은 옆의 `.md` 파일들입니다.

τ² 파일럿 에피소드 원본과 F-run 결과는 같은 리포의 [`tau2-pilot-results`](https://github.com/jinuk0211/jlens-causal-steering/tree/tau2-pilot-results) 브랜치에 있습니다.
τ² 실험 코드는 [`agent/official-baselines-tau2`](https://github.com/jinuk0211/jlens-causal-steering/tree/agent/official-baselines-tau2) 브랜치에, ToolAlign 코드는 [jinuk0211/ToolAlignBench](https://github.com/jinuk0211/ToolAlignBench)의 `agent/toolalign-full-trajectory-jlens` 브랜치에 있습니다.

## 아직 안 들어간 것

- 11-26 19:1x에 시작한 AM 전체 추론 뉴런 스캔(T9)과 T8b 재표본, AgentDojo X16·X17의 나머지 행, 2080 Ti의 AM steering F1(murder)은 스냅샷 시점에 아직 돌고 있었습니다. OVERNIGHT2.md 로그에는 19:1x까지의 중간 결과만 있습니다.

## 빠진 것

- 수치 배열(`.npz`, `.pt`, `.npy`)과 `.tgz` 묶음: 합쳐서 약 10 GB라 올리지 않았습니다. 로컬 PC에 보관되어 있습니다.
- 캐시와 임시 작업 폴더: Claude 판정 캐시, `ne_cache`, `__pycache__`, 가상환경, agentic-misalignment 원본 리포 사본, 옛 버전 코드 보관 폴더.
- 접속용 스크립트: 손님 AI 프록시, SSH 터널, 원격 relay, 파일 가져오기 스크립트.
- 남은 문서의 서버·vast 상자 IP 주소와 SSH 주소는 `<server-ip>`, `<vast-ip>`, `ssh <vast-box>`로 바꿨습니다.
- τ² 대화 기록 중 손님 AI가 말한 실제 이메일 주소는 `user@example.com`으로 바꿨습니다. AM 결과에 나오는 gmail 주소(Kyle Johnson, Jessica Wilson 등)는 벤치마크 시나리오의 가상 인물입니다.
