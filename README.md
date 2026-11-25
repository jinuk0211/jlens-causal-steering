# 실험 결과 모음 (2026-11-16 ~ 11-25)

τ²-bench, ToolAlignBench, agentic-misalignment(AM), AgentDojo에서 J-lens 판독과 steering·인과 개입으로 한 실험의 결과입니다.
2026-11-25 21:2x KST 스냅샷입니다. 이때 AM CAUSAL-2 TEST는 아직 돌고 있어서, 그 결과는 일부만 들어 있습니다.

먼저 읽을 것은 [HISTORY_1-38_20261125.md](HISTORY_1-38_20261125.md)입니다. 1~38부 전체 기록이 시간순으로 있고, 맨 위에 목차가 있습니다.
요약은 10부, 19부, 26부, 36부에 있습니다.

## 폴더

| 폴더 | 내용 | 기록 |
|---|---|---|
| [tau2-research/](tau2-research/) | τ² 연구 루프: PLAN.md(사전 등록과 로그), WRITEUP_draft.md, J-Cascade, M1, C-LOOP(circuit), baseline_why, C2T, NL 판정 | 1~16부, 30부 |
| [tau2-topk-20261119/](tau2-topk-20261119/) | 기본 실행 278개의 에피소드별 메타데이터(json). 층별 top-k 배열(npz)은 빠져 있음 | 6부 |
| [toolalign-research/](toolalign-research/) | ToolAlignBench: Qwen3.5-4B(server), Gemma-4-E4B-it(server_gemma), Qwen3.5-9B(server_q9). 대화 기록 md, metrics, 행동 라벨, J-lens, CAUSAL-1/2 | 17~26부 |
| [agentbench2-research/](agentbench2-research/) | AM과 AgentDojo: PLAN.md, 분석 코드(code/), AM 생성 결과와 Haiku 판정(am_results/), 서버 결과 사본(results_mirror/) | 31~38부 |
| [vast-fsteer/](vast-fsteer/) | vast 상자에서 실패 턴에만 공식 baseline steering (중단) | 29부 |
| [vast-archive-20261125/](vast-archive-20261125/) | 삭제한 vast 상자 2개의 보관본 목록(README만) | 38부 이후 |

ToolAlign의 원본 trace(`*.trace.json`, 모델별 128개)는 용량 때문에 각 결과 폴더의 `traces.tar.gz`로 묶었습니다.
풀려면 `tar -xzf traces.tar.gz`를 실행하면 됩니다. 같은 대화의 읽기 쉬운 버전은 옆의 `.md` 파일들입니다.

τ² 파일럿 에피소드 원본과 F-run 결과는 같은 리포의 [`tau2-pilot-results`](https://github.com/jinuk0211/jlens-causal-steering/tree/tau2-pilot-results) 브랜치에 있습니다.
τ² 실험 코드는 [`agent/official-baselines-tau2`](https://github.com/jinuk0211/jlens-causal-steering/tree/agent/official-baselines-tau2) 브랜치에, ToolAlign 코드는 [jinuk0211/ToolAlignBench](https://github.com/jinuk0211/ToolAlignBench)의 `agent/toolalign-full-trajectory-jlens` 브랜치에 있습니다.

## 빠진 것

- 수치 배열(`.npz`, `.pt`, `.npy`)과 `.tgz` 묶음: 합쳐서 약 10 GB라 올리지 않았습니다. 로컬 PC에 보관되어 있습니다.
- 캐시와 임시 작업 폴더: Claude 판정 캐시, `ne_cache`, `__pycache__`, 가상환경, agentic-misalignment 원본 리포 사본.
- 접속용 스크립트: 손님 AI 프록시, SSH 터널, 원격 relay, 파일 가져오기 스크립트.
- 남은 문서의 서버·vast 상자 IP 주소와 SSH 주소는 `<server-ip>`, `<vast-ip>`, `ssh <vast-box>`로 바꿨습니다.
- τ² 대화 기록 중 손님 AI가 말한 실제 이메일 주소는 `user@example.com`으로 바꿨습니다.
