# 실험 결과 모음 (2026-11-16 ~ 11-27)

τ²-bench, ToolAlignBench, agentic-misalignment(AM), AgentDojo에서 J-lens 판독과 steering·인과 개입으로 한 실험의 결과입니다.
이 판은 2026-11-27 21시 KST 스냅샷입니다. 앞 판은 11-25 21:2x(커밋 a07ff8f)와 11-26 19:1x(커밋 0174ed3)이고, 그 뒤에 나온 결과를 더했습니다.

먼저 읽을 문서는 세 개입니다.
- [ALL_EXPERIMENTS_20261127.md](ALL_EXPERIMENTS_20261127.md): 11-16 ~ 11-27 19:10의 모든 실험을 벤치마크별로 정리했습니다. 실험마다 무엇을 어떻게 했는지, 예시, 결과, 판정이 있습니다.
- [HISTORY_1-61_20261127.md](HISTORY_1-61_20261127.md): 1~61부 전체 기록이고 11-27 10:00까지 시간순입니다. 맨 위에 목차가 있고, 앞 내용을 뒤에서 고친 곳은 목차 앞에 모아 두었습니다.
- [SAFETY_EXPERIMENTS_20261127.md](SAFETY_EXPERIMENTS_20261127.md): ToolAlignBench·AM·AgentDojo 실험을 주제별로 정리한 문서입니다.

## 폴더

| 폴더 | 내용 | 기록 |
|---|---|---|
| [tau2-research/](tau2-research/) | τ² 연구 루프: PLAN.md(사전 등록과 로그), WRITEUP_draft.md, J-Cascade, M1, C-LOOP(circuit), baseline_why, C2T, NL 판정 | 1~16부, 30부 |
| [tau2-topk-20261119/](tau2-topk-20261119/) | 기본 실행 278개의 에피소드별 메타데이터(json). 층별 top-k 배열(npz)은 빠져 있음 | 6부 |
| [toolalign-research/](toolalign-research/) | ToolAlignBench: Qwen3.5-4B(server), Gemma-4-E4B-it(server_gemma), Qwen3.5-9B(server_q9). 대화 기록 md, metrics, 행동 라벨, J-lens, CAUSAL-1/2 | 17~26부 |
| [agentbench2-research/](agentbench2-research/) | AM과 AgentDojo. 아래 표 참고 | 31~61부 |
| [agentbench2_cap/](agentbench2_cap/) | 세 벤치마크 전체 네트워크 캡처의 목록(plan, index, 로그)과 비교 1(cmp1) 보고서. 캡처 배열 npz(약 137 GB)는 빠져 있음 | CIRCUIT.md |
| [neuron-explorer-cases/](neuron-explorer-cases/) | neuron-explorer UI에 ToolAlign 궤적 212개를 "#case N"으로 넣은 파일 3개(ne_cases.py, cases.js, index.html). 원본 리포 [lyramakesmusic/neuron-explorer](https://github.com/lyramakesmusic/neuron-explorer)의 `explorer/` 아래에 덮어 쓰는 파일 | 40부 |
| [vast-fsteer/](vast-fsteer/) | vast 상자에서 실패 턴에만 공식 baseline steering(중단) | 29부 |
| [vast-archive-20261125/](vast-archive-20261125/) | 삭제한 vast 상자 2개의 보관본 목록(README만) | 38부 이후 |
| [vast-archive-20261127/](vast-archive-20261127/) | vast 2번 상자 백업 시도 기록(README와 받은 항목 목록). 백업은 중간에 끊겨 불완전함 | |

### agentbench2-research/ 안

| 경로 | 내용 | 기록 |
|---|---|---|
| PLAN.md | 사전 등록(경계 규칙, TEST 기준, N1~N4)과 로그. 11-27 로그에 X18·X19r(AgentDojo 교차 fold와 slack), L9(9B AM), T9w, PropensityBench 등록도 있음 | 31부~ |
| OVERNIGHT.md | 11-25 밤 기여도 뉴런 탐색: 사전 등록과 최종 보고 | 41~47부 |
| OVERNIGHT2.md | 11-26 실패 기반 루프와 뉴런 트랙 T1~T9: 사전 등록, 로그, "최종 보고" | 49~61부 |
| CROSS.md | 11-27 고르는 방식 교차 실험(S1, S2): 등록과 결과. 19:03 사용자 요청으로 중단 | |
| CIRCUIT.md | 11-27 전체 네트워크 비교와 circuit 탐색: 등록과 비교 1 결과 | |
| code/ | 분석 코드(ab_core, ab_ne, ab_hn, ab_strict, ab_serve_steer, ab_xfit 등). 11-27에 추가된 X18·X19·L9·CROSS·R3·그림 코드, X20(AgentDojo slack·workspace, 4B·9B·27B)과 PropensityBench 코드도 있음 | |
| am_results/ | AM 생성 결과와 Haiku 판정. 11-27에 T9d4·T9e·T9g2·T9h·T9i·T9m·T9p·T9q·T9r 판정과 9B(L9a, L9c) 판정이 추가됨 | 32부~ |
| am18/ | AM 18조건 설정 | 32부 |
| results_mirror/srch_2215 | 야간 탐색 결과(세 벤치마크의 뉴런 집합, 행 단위 결과) | 41~46부 |
| results_mirror/ta_traj_jlens_1125 | ToolAlign 궤적 뉴런 기록, 결정 문장 편집(2080 Ti, fp32) | 40부, 44부 |
| results_mirror/hn_1126 | T1·T2·T3·T6, 에피소드 전체 실험(X14·X15), 감지 표, T9 스캔·arm 설정·보고서와 행 | 50~61부 |
| results_mirror/am18_explorer, am_steer, flow_temporal | AM 18조건 프롬프트 유형별 뉴런, AM steering 루프, 응답 600개의 토큰별 흐름(모두 2080 Ti) | PLAN.md 11-26 로그 |
| results_mirror/fig_resid, fig_flow | 논문 그림 두 개(residual_streams, residual_flow)와 수치, 보고서 | PLAN.md 11-27 로그 |
| results_mirror/x18_1127 | X18 교차 fold 보고서(banking, travel, user_task_9), X19r slack residual 비교 | PLAN.md 11-27 12:5x~ |
| results_mirror/l9_1127 | L9: Qwen3.5-9B AM 유출 흐름(lens 선택, arm, 판정 라벨, 응답 토큰 전체의 residual 비교 div_report) | PLAN.md 11-27 13:2x~ |
| results_mirror/cross_1127 | CROSS S1·S2의 arm 설정, 용량 보정, 로그 | CROSS.md |
| results_mirror/cmp1_1127 | 비교 1 보고서(AgentDojo, ToolAlign, AM) | CIRCUIT.md |
| results_mirror/vast_1127 | vast 상자 AM 루프 기록 | |
| xfer/ | RTX 3090 상자에서 돌린 AM test 행 목록 | 37~39부 |

ToolAlign의 원본 trace(`*.trace.json`, 모델별 128개)는 용량 때문에 각 결과 폴더의 `traces.tar.gz`로 묶었습니다.
풀려면 `tar -xzf traces.tar.gz`를 실행하면 됩니다. 같은 대화의 읽기 쉬운 버전은 옆의 `.md` 파일들입니다.

## 다른 브랜치와 리포

- AgentDojo(X20)와 PropensityBench 코드만 따로 정리한 것은 [`agentdojo-propensity-code`](https://github.com/jinuk0211/jlens-causal-steering/tree/agentdojo-propensity-code) 브랜치에 있습니다.
- τ² 파일럿 에피소드 원본과 F-run 결과는 [`tau2-pilot-results`](https://github.com/jinuk0211/jlens-causal-steering/tree/tau2-pilot-results) 브랜치에 있습니다.
- τ² 실험 코드는 [`agent/official-baselines-tau2`](https://github.com/jinuk0211/jlens-causal-steering/tree/agent/official-baselines-tau2) 브랜치에 있습니다.
- ToolAlign 코드는 [jinuk0211/ToolAlignBench](https://github.com/jinuk0211/ToolAlignBench)의 `agent/toolalign-full-trajectory-jlens` 브랜치에 있습니다.

## 아직 안 들어간 것

- 이번 판은 PC에 내려받아 둔 사본만으로 만들었고, 서버에서 다시 받지 않았습니다. 마지막 사본 이후 서버에만 있는 결과는 빠져 있습니다. 예를 들면 X18 14:52 이후 행, X19r arm 에피소드, L9 16:36 이후 결과, T9w3 행입니다.
- vast 2번 상자의 주요 결과(amflow/abl, taabl, tanew, comp)는 백업이 끊겨 받지 못했습니다(vast-archive-20261127/README.md).

## 빠진 것

- 수치 배열(`.npz`, `.pt`, `.npy`)과 `.tgz`·`.tar` 묶음: 용량 때문에 올리지 않았고 로컬 PC에 보관되어 있습니다. D 드라이브의 전체 네트워크 캡처(약 137 GB)도 여기에 해당합니다.
- 캐시와 임시 작업 폴더: Claude 판정 캐시, `ne_cache`, `__pycache__`, 가상환경, agentic-misalignment 원본 리포 사본, 옛 버전 코드 보관 폴더.
- 접속용 스크립트: 손님 AI 프록시, SSH 터널, 원격 relay, 파일 가져오기 스크립트(puller 포함).
- 남은 문서의 서버·vast 상자 IP 주소와 SSH 주소는 `<server-ip>`, `<vast-ip>`, `ssh <vast-box>`로 바꿨습니다.
- τ² 대화 기록 중 손님 AI가 말한 실제 이메일 주소는 `user@example.com`으로 바꿨습니다. AM 결과에 나오는 이메일 주소(Kyle Johnson 등)는 벤치마크 시나리오의 가상 인물입니다.
