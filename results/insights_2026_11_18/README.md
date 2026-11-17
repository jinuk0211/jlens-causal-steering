# results/insights_2026_11_18

[INSIGHTS_2026-11-18.md](../../INSIGHTS_2026-11-18.md)의 근거 파일과 재현 스크립트다.

## data/
| 파일 | 내용 |
|---|---|
| `airline_turns.jsonl` | airline baseline 1,428턴 표. 라벨(good/bad write, read, no_call), write 유형·diff, 문맥 특징(유저 yes 등), L16 trigger 점수·발화 여부. `scripts/session_2026_11_17/build_turns.py`로 생성 |
| `airline_episodes.jsonl` | 122 episode의 보상, 종료 사유, 턴별 라벨 |
| `airline_jlens_topk_L8_L16_L31.jsonl` | 위 1,428턴의 저장된 residual(결정·tool 이름·인자 위치, L8/16/31)을 J-lens top-10으로 디코딩한 결과. `scripts/session_2026_11_18/decode_airline_topk.py` |

## cases/ (원문과 함께 읽은 사례)
| 파일 | 내용 |
|---|---|
| `harmful_bad_writes.txt` | 해로운 write 36건. 과제·지시, gold vs 실제 호출, 직전 대화 4개 |
| `transfer_bad_writes_full.txt`, `transfer_bad_writes_by_task.txt` | transfer 48건 |
| `steering_replay_outputs.txt` | vocab trigger 재생 31턴 × off/±0.8/random±0.8 출력 |
| `episode_fired_turns.txt` | 3단계 episode에서 조건별로 trigger가 발화한 모든 턴 |

## timelines/ (episode 시간순 J-lens top-k)
| 파일 | 내용 |
|---|---|
| `retail4b_episode_timelines.txt` | qwen4retail 30 episode. call마다 관찰·결정·tool·인자 위치의 L15/19/23/27/최종 층 top-5와 대화 원문 |
| `airline_failed_episodes.txt`, `airline_passed_episodes.txt` | airline 27 실패 / 95 통과 episode. 턴마다 L16·L31 top-k, 유저 발화, 호출 |
| `precursor_markers_retail4b.txt`, `precursor_markers_airline.txt` | 거절·의심·완료·정책 표지 비율과 lens→문장 선행성 |

## layer_stats/
| 파일 | 내용 |
|---|---|
| `retail4b_boundary_layers.txt`, `retail08b_boundary_layers.txt` | 경계 판독의 층별 단어 비율·한자 비율·인접 층 Jaccard, 경계 유형별 상위 토큰 |
| `retail4b_slice_all_calls.txt`, `retail08b_slice_all_calls.txt` | `slice.bin` 전체(319 / 419 call)에서 다음 토큰 예측력 |
| `airline_trigger_basic.txt`, `airline_trigger_yes2x2.txt` | trigger AUC 재현, 나쁜 write 분류, 유저 동의 2×2 |
| `airline_harmful_vs_good.txt`, `airline_matched_pairs.txt`, `airline_badwrite_composition.txt` | 해로운 vs 좋은 write AUC, 같은 task·tool 쌍 AUC(0.533), transfer·거절 대본 비율 |

## stage_anchor/
| 파일 | 내용 |
|---|---|
| `offline_retail4b_L19_L23*.{jsonl,txt}`, `offline_retail4b_L23_L27*` | `scripts/stage_anchor_offline.py` 결과(call별 경합 위치)와 요약 |
| `selection_airline.jsonl` | GPU 재생용 170턴 (해로운 36 / 좋은 86 / transfer 48). 서버 경로 `/workspace/vt/vocab-trigger-data/...` 기준 |

## scripts/
분석 당시 Windows 로컬에서 그대로 실행한 스크립트다. 입력 경로는 파일 위쪽에 상수로 박혀 있으니 환경에 맞게 바꿔서 쓴다.
- `session_2026_11_17/`: 턴 표 생성(`build_turns.py`), trigger 재현·probe·재생·출력 손상 분석(`a1`~`a11`).
- `session_2026_11_18/`:
  - 사례 덤프: `dump_*.py`, `compare_episode_write_args.py`
  - AUC: `harmful_writes_auc.py`(`tbl/turns.jsonl` 기준 상대 경로), `matched_pair_auc.py`, `badwrite_composition.py`
  - 미러 조사: `survey_mirror*.py`, `inspect_gptoss_viewer.py`
  - 층 분석: `layer_stats_boundary.py`, `slice_layer_stats.py`(viewer `slice.bin` 디코딩), `tool_emergence_by_layer.py`, `tool_commitment_layer.py`
  - ToolAlignBench: `toolalign_*.py`
  - 시간순 분석: `decode_airline_topk.py`(로컬 가중치·lens 필요, CPU), `airline_timelines.py`, `retail_timelines.py`, `precursor_markers_*.py`

viewer `slice.bin` 형식: gzip(int32 top-k id `[T·L·K]` ‖ int32 rank `[T·L·K]`), 순서는 `[ctx, layer, k]`. `ranks/<id>.bin`은 gzip(int32 rank `[T·L]`)이고, 토큰 문자열은 `meta.json`의 `vocab`에 있다.
