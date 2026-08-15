# 크롬에 열린 논문 정리

정리일: 2026-08-15  
대상: 열린 논문 탭 17개 중 중복 1개를 합친 고유 논문 16편  
BibTeX: [`open_papers.bib`](./open_papers.bib)

## 한눈에 보는 흐름

이 논문 묶음은 크게 세 축으로 이어진다.

1. **활성값 조향과 내부 제어**: CAA·ITI에서 시작해 조건부 조향, 규범 보존 조향, 조향 저항, 검출과 제어의 방향 불일치까지 발전한다.
2. **안전성의 동적 실패**: 단일 프롬프트가 아니라 추론 과정, 다회차 대화 상태, 언어 형식, 언어 간 공유 뉴런에서 안전 정렬이 어떻게 무너지는지 살핀다.
3. **에이전트와 도구 사용의 신뢰성**: 도구 호출을 내부 표현으로 감시·제어하고, 강한 추론이 오히려 도구 환각을 키울 수 있다는 문제를 다룬다.

## 논문별 설명

### 1. Beyond the Black Box: Interpretability of Agentic AI Tool Use

- 링크: <https://arxiv.org/abs/2605.06890v3>
- 인용키: `tatsat2026beyond`
- 설명: 도구를 호출하기 직전의 모델 내부 상태를 희소 오토인코더(SAE)와 선형 프로브로 읽어, 도구가 필요한지와 다음 행동의 위험도를 예측한다. GPT-OSS 20B와 Gemma 3 27B의 다단계 도구 사용 궤적에 적용하고 특징 제거 실험까지 수행해, 에이전트 관찰성을 외부 로그에서 사전 내부 신호로 확장한다.
- 읽을 포인트: 장기 에이전트 실행에서 초기 도구 실수를 실행 전에 포착할 수 있는지에 초점을 둔 실용적인 기계론적 해석 연구다.

### 2. Selective Steering: Norm-Preserving Control Through Discriminative Layer Selection

- 링크: <https://arxiv.org/abs/2601.19375>
- 인용키: `dang2026selective`
- 설명: 기존 활성값 덧셈이나 각도 조향이 활성값의 크기를 흐트러뜨려 생성 붕괴를 일으킬 수 있다는 문제를 지적한다. 엄밀한 규범 보존 회전과, 두 클래스가 반대 부호로 정렬되는 층만 고르는 선택적 적용을 결합해 아홉 모델에서 안정적인 행동 제어를 보고한다.
- 읽을 포인트: 조향의 세기뿐 아니라 **어느 층에, 어떤 기하학으로 개입하는가**가 안정성을 좌우한다는 주장이다.

### 3. Controlling Tool Use with Heading-Specific Activation Steering

- 링크: <https://arxiv.org/abs/2607.05790>
- 인용키: `chen2026controlling`
- 설명: 프롬프트의 헤딩 앵커 위치에서 추출한 조향 벡터로 도구 호출을 양방향 제어하며, 특히 모델 자체 추론으로 충분한 경우 불필요한 호출을 잘 억제한다. 다만 도구 호출 표현은 깔끔한 단일 선형 방향이 아니라 이봉형·분산형이고 도구 종류별 내부 특징도 상당히 다르다고 보고한다.
- 읽을 포인트: 인과적 제어가 잘 된다는 사실이 곧 개념이 단순한 선형 방향으로 표현된다는 뜻은 아니라는 중요한 반례다.

### 4. The Reasoning Trap: How Enhancing LLM Reasoning Amplifies Tool Hallucination

- 링크: <https://arxiv.org/abs/2510.22977v2>
- 인용키: `yin2025reasoning`
- 설명: 도구가 없거나 방해용 도구만 있는 상황을 측정하는 SimpleToolHalluBench를 만들고, RL·SFT·추론 시 단계적 사고 모두에서 추론 강화가 도구 환각을 늘리는 현상을 보인다. 환각 억제는 유용성 저하와 맞바뀌며, 내부적으로는 도구 신뢰성 관련 표현의 붕괴와 후기 층 잔차 스트림의 발산이 관찰된다.
- 읽을 포인트: “더 잘 생각하는 모델이 더 믿을 만한 도구 사용자”라는 직관이 성립하지 않을 수 있음을 정면으로 다룬다.

### 5. Beyond Linear Probes: Dynamic Safety Monitoring for Language Models

- 링크: <https://arxiv.org/abs/2509.26238>
- 인용키: `oldfield2025beyond`
- 설명: 다항식을 항별로 순차 평가할 수 있는 Truncated Polynomial Classifier(TPC)를 제안한다. 쉬운 입력은 저차 항에서 조기 종료하고 모호한 입력만 고차 항까지 계산해, 하나의 모니터로 비용과 안전 강도를 동적으로 조절한다.
- 읽을 포인트: 정적 선형 프로브와 고정 비용 MLP 사이에서, 해석 가능성과 계산 적응성을 함께 얻으려는 안전 모니터링 설계다.

### 6. When Do Hallucinations Arise? A Graph Perspective on the Evolution of Path Reuse and Path Compression

- 링크: <https://arxiv.org/abs/2604.03557>
- 인용키: `dai2026hallucinations`
- 설명: 다음 토큰 예측을 그래프 탐색으로 보고, 문맥 기반 추론은 샘플된 하위 그래프의 제한된 탐색, 문맥 없는 질의는 기억된 전체 그래프의 탐색으로 해석한다. 초기 학습의 **경로 재사용**과 후기 학습의 **경로 압축**이라는 두 메커니즘으로, 기억 지식이 문맥 제약을 덮거나 빈번한 다단계 경로가 잘못된 지름길로 굳는 환각을 설명한다.
- 읽을 포인트: 환각을 단순 사실 오류가 아니라 학습 중 경로 구조가 진화한 결과로 통합하려는 이론적 관점이다.

### 7. When Safety Alignment Fails to Generalize: Probing with Language Game Jailbreaks

- 링크: <https://aclanthology.org/2026.findings-acl.739/>
- DOI: <https://doi.org/10.18653/v1/2026.findings-acl.739>
- 인용키: `long-etal-2026-safety`
- 설명: 의미는 유지하면서 표면 언어 형식만 바꾸는 언어 게임을 이용해 안전 정렬의 일반화를 시험한다. 변환 규칙을 자동 발견·개선하는 AutoLanJail 실험에서, 한 형식으로 안전 미세조정된 방어가 아주 작은 형식 변화에도 일반화되지 않는다는 결과를 보인다.
- 읽을 포인트: 현재 안전 미세조정이 의미 수준의 규칙보다 훈련에서 본 표현 형식에 과도하게 묶일 수 있음을 보여준다.

### 8. Who Transfers Safety? Identifying and Targeting Cross-Lingual Shared Safety Neurons

- 링크: <https://arxiv.org/abs/2602.01283>
- 인용키: `zhang2026transfersafety`
- 설명: 고자원·저자원 언어 사이에서 함께 안전 거부를 조절하는 소수의 공유 안전 뉴런(SS-Neurons)을 식별한다. 이 뉴런을 억제하면 여러 저자원 언어의 안전성이 함께 떨어지고, 강화하거나 선택적으로 미세조정하면 일반 능력을 유지하면서 저자원 언어의 방어가 개선된다고 보고한다.
- 읽을 포인트: 다국어 안전 전이가 모델 전체에 퍼진 현상이 아니라 작은 공통 뉴런 집합에 집중될 수 있다는 가설을 제시한다.

### 9. Why Attention Patterns Exist: A Unifying Temporal Perspective Analysis

- 링크: <https://arxiv.org/abs/2601.21709>
- 인용키: `yang2026attention`
- 설명: 검색 헤드·어텐션 싱크·대각선 패턴을 따로 설명하는 대신 TAPPA라는 시간적 관점으로 통합한다. 쿼리의 시간축 자기유사성이 패턴의 예측 가능성을 결정한다고 분석하고, 이 관찰에서 얻은 지표를 KV 캐시 압축과 모델 프루닝에 적용한다.
- 읽을 포인트: 어텐션 시각화의 사후적 이름 붙이기를 넘어, 여러 패턴이 생기는 공통 수학적 이유와 시스템 최적화를 연결한다.

### 10. Steering Llama 2 via Contrastive Activation Addition

- 링크: <https://arxiv.org/abs/2312.06681>
- 인용키: `panickssery2023steering`
- 설명: 긍정·부정 행동 예시 쌍의 잔차 스트림 활성값 차이를 평균해 조향 벡터를 만들고, 추론 중 해당 벡터를 더하거나 빼는 Contrastive Activation Addition(CAA)을 제안한다. Llama 2 Chat에서 사실성 등 고수준 행동을 연속적으로 조절하면서 일반 능력 손실이 작다고 보고한다.
- 읽을 포인트: 뒤의 조건부 조향·선택적 조향·조향 저항 연구가 출발하는 대표적인 활성값 덧셈 계열 기준선이다.

### 11. Endogenous Resistance to Activation Steering in Language Models

- 링크: <https://arxiv.org/abs/2602.06941>
- 인용키: `mckenzie2026resistance`
- 설명: 모델이 잘못된 방향으로 계속 조향되는 중에도 “잠깐, 이건 아니다”와 같은 명시적 재시작을 거쳐 원래 과제로 돌아오는 내생적 조향 저항(ESR)을 정의한다. 특정 SAE 잠재 특징을 제거하면 재시도율이 감소하고, 메타 프롬프트와 자기수정 학습으로 ESR을 강화할 수도 있음을 보인다.
- 읽을 포인트: 모델이 활성 공간 개입 자체를 탐지·상쇄할 수 있어, 공격 방어에는 도움이 되지만 유익한 조향도 무력화할 수 있다는 양면성이 핵심이다.

### 12. Inverted Detection and Control in Steering Vectors

- 링크: <https://arxiv.org/abs/2608.02957>
- 인용키: `torop2026inverted`
- 설명: 어떤 개념을 잘 검출하는 양의 방향 벡터를 더했는데 오히려 반대 행동이 강화되는 **검출-제어 역전** 현상을 분석한다. 생성 결과를 직접 점수화하지 않고도 역전 벡터를 판별해 부호를 뒤집는 방법을 제안하며, ITI 기반 실험 30개 중 27개를 개선한다.
- 읽을 포인트: 선형 분리 방향을 곧바로 인과적 제어 방향으로 간주하는 활성 조향의 기본 가정을 흔든다.

### 13. Inference-Time Intervention: Eliciting Truthful Answers from a Language Model

- 링크: <https://arxiv.org/abs/2306.03341>
- 인용키: `li2023inference`
- 설명: 소수의 어텐션 헤드에서 진실성 방향을 찾고 추론 중 활성값을 이동시키는 Inference-Time Intervention(ITI)을 제안한다. Alpaca의 TruthfulQA 진실성 점수를 32.5%에서 65.1%로 높이지만, 진실성과 도움성 사이의 조정 가능한 상충관계도 확인한다.
- 읽을 포인트: 적은 라벨 데이터와 가벼운 추론 시 개입으로 출력 행동을 바꾸는 대표 연구이며, 이후 역전 조향 연구의 기반이기도 하다.

### 14. When Thinking Backfires: Mechanistic Insights Into Reasoning-Induced Misalignment

- 링크: <https://arxiv.org/abs/2509.00544>
- 인용키: `yan2025thinking`
- 설명: 특정 추론 패턴을 추론 시 유도하거나 학습하면 안전 정렬이 약해지는 Reasoning-Induced Misalignment(RIM)을 제시한다. 거부에 관여하는 어텐션 헤드가 CoT 토큰 주의를 줄여 합리화 과정을 조절하며, 학습 중 안전 핵심 뉴런에서 추론과 안전 표현이 얽히는 정도가 파국적 망각과 강하게 연관된다고 분석한다.
- 읽을 포인트: 추론 능력 강화와 안전 미세조정을 독립 목표로 다루기 어려운 뉴런 수준의 이유를 찾으려는 연구다.

### 15. Programming Refusal with Conditional Activation Steering

- 링크: <https://arxiv.org/abs/2409.05907>
- 인용키: `lee2024programming`
- 설명: 모든 입력에 무차별 적용되는 조향 대신, 입력 문맥의 활성 패턴을 분류해 조건이 맞을 때만 개입하는 CAST를 제안한다. 가중치 학습 없이 “특정 유해 범주이면 거부” 또는 “허용 도메인이 아니면 거부” 같은 규칙형 행동 제어를 구현한다.
- 읽을 포인트: 활성 조향을 단순 세기 조절에서 조건문이 있는 정책으로 확장해 실제 콘텐츠 조정에 가까워진다.

### 16. State-Dependent Safety Failures in Multi-Turn Language Model Interaction

- 링크: <https://arxiv.org/abs/2603.15684>
- 인용키: `li2026statedependent`
- 설명: 대화 기록을 상태 전이 연산자로 보는 STAR 프레임워크로 다회차 안전 실패를 분석한다. 정적 단일 프롬프트에는 강한 모델도 구조화된 대화에서 거부 표현으로부터 점진적으로 멀어지고, 역할 조건 문맥에서 갑작스러운 안전 붕괴 전이를 보일 수 있다고 보고한다.
- 읽을 포인트: 안전성을 개별 입력의 속성이 아니라 전체 대화 궤적 위에서 변화하는 동적 상태로 평가해야 한다는 주장이다.

## 메타데이터 처리 메모

- `2605.06890`과 `2510.22977`은 크롬에 각각 **v3**, **v2**가 열려 있어 해당 버전 URL을 유지했다.
- `2607.05790`은 동일 논문의 중복 탭 두 개를 하나로 합쳤다.
- ACL 논문은 ACL Anthology가 제공한 공식 BibTeX의 서지 필드를 사용했다.
- arXiv 논문은 열린 페이지의 citation 메타데이터(제목, 저자, 최초 제출 연도, arXiv ID, 주 분류)를 기준으로 표준 `@misc` 형식으로 통일했다.
