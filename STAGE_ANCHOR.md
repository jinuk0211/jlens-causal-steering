# Stage-Anchor: 층 사이 경합 감지와 자기 중간층 기반 수정

근거와 배경은 [INSIGHTS_2026-11-18.md](INSIGHTS_2026-11-18.md)의 4~6절에 있다. 구현은 `src/jlens_causal/stage_anchor.py`다.

## 아이디어
- Qwen3.5-4B의 lens 정보는 full-attention 블록에서 계단식으로 들어온다. 단계는 L15 화행 → L19 입장 → L23 행동·tool → L27 인자 → L31 출력이다.
- binding 오류는 중간층에 있던 맞는 항목이 확정층에서 다른 것으로 바뀌는 모양으로 나타난다. 예: task 18 `each` → `all`.
- 기존 vocab trigger는 고정 어휘로 화행·입장 단계만 바꿔서, write를 미룰 수는 있어도 인자를 고칠 수는 없었다.

## 정의
gate가 켜진 위치(Qwen3.5 tool call의 인자 값, 선택적으로 함수 이름)에서:

- `b` = 중간층(기본 L19) lens 1위, `a` = 확정층(기본 L23) lens 1위
- **경합:** 아래 조건을 모두 만족할 때
  - `a`, `b`가 둘 다 내용 토큰이다 (특수 토큰·구두점·숫자 제외)
  - 같은 단어가 아니다 (정규화 문자열이 다르고, unembedding 코사인 < `same_cos`)
  - `rank_mid(a) < k`이고 `rank_com(b) < k`이다 (두 후보가 양쪽 층 모두 top-k 안에 있음)
- **점수:** `s = (z_mid[b] − z_mid[a]) + (z_com[a] − z_com[b])`. 경합이면서 `s ≥ threshold`일 때 발화한다.
- **수정:** `d = normalize(J_com^T (W_U[b] − W_U[a]))`, `h ← h + α‖h‖d`. 그 한 위치에서만 적용하며, 확정층 판독이 b를 앞서게 되는 가장 작은 α를 쓴다.
- **조건:** `off`(감지만), `anchor`, `reverse`(같은 위치·양으로 a 쪽), `random`(같은 위치·양, 무작위 방향).

중간층 판독은 hook으로 캐시하고, 확정층 hook이 점수를 계산한 뒤 자기 출력을 수정한다. 따라서 한 번의 forward로 끝나고, 수정은 그 뒤 모든 블록에 전달된다. `--mid 23 --commit 27`로 바꾸면 tool 선택 대신 인자 값 단계를 겨냥한다.

## 실행
```bash
# 0) (CPU) 저장된 J-lens viewer로 오프라인 스캔
python scripts/stage_anchor_offline.py <vast-backup>/qwen4retail --mid 19 --commit 23 --show 40 \
    --output results/stage_anchor/qwen4retail_19_23.jsonl

# 1) 재생할 턴 선택 (airline 해로운 write 36 / 좋은 write 86 / transfer 48)
python scripts/stage_anchor_select.py results/insights_2026_11_18/data/airline_turns.jsonl \
    /workspace/vt/vocab-trigger-data/jlens-telemetry/failure-steering --kinds harmful good transfer \
    --output selection.jsonl          # 미리 만든 것: results/insights_2026_11_18/stage_anchor/selection_airline.jsonl

# 2) (GPU) 감지만 해서 threshold 보정. good write의 경합 점수 95퍼센타일을 쓴다
python scripts/stage_anchor_replay.py selection.jsonl tasks.json --model-dir M --lens LENS \
    --modes off --output sa_off.jsonl

# 3) (GPU) 조건 비교
python scripts/stage_anchor_replay.py selection.jsonl tasks.json --model-dir M --lens LENS \
    --threshold T --modes anchor reverse random --output sa.jsonl
```
각 행에는 tool call과 gold 대비 라벨, gate가 켜진 위치 수, 경합·발화·수정 횟수, 상위 경합(디코딩된 a/b, 점수, α)이 기록된다.

## 현재 상태와 주의
- CPU 단위 테스트(`tests/test_stage_anchor.py`)는 통과했다. GPU 재생은 아직 돌리지 않았다.
- 오프라인(retail 4B 319 call)에서 실패 episode를 가르는 AUC는 L19/L23 0.53, L23/L27 0.46이다. 성공 call에서 확정층이 맞은 경합도 있다(city: L19 Downtown, L23 Austin, 정답 Austin).
- **"중간층이 맞다"는 전제는 검증되지 않았다.** 2단계 `off` 재생으로, 경합 위치에서 어느 층의 1위가 gold 인자와 맞는지부터 센다. 해로운 write에서 중간층이 더 자주 맞을 때만 `anchor`를 돌릴 의미가 있다.
- 오프라인 점수는 순위 기반(`log(1+r_mid(a)) + log(1+r_com(b))`)이라 온라인 logit 점수와 단위가 다르다.
