# Decision Record: ADR-002 임베딩 모델

> Created at: `2026-10-10`
> ClickUp 작업: 해당 없음: 초기 세팅 단계 예외(WBS 0.9)
> 기능명세서 ID: 해당 없음: Phase 0 준비 작업
> Status: Proposed

## Context

색인과 검색에 쓸 임베딩 모델을 정해야 한다. 이 선택이 벡터 차원(QK-STO-001), 청크 크기 상한(QK-CHK-002),
일일 Neurons 예산(QK-EMB-001)을 모두 결정한다. 제약은 Workers AI 무료 할당 하루 10,000 Neurons, 한국어 지원,
그리고 청커가 모델 입력 한도를 직접 지켜야 한다는 것이다(constitution C-07).

WBS 0.6에서 Workers AI 임베딩 3종(`@cf/google/embeddinggemma-300m`, `@cf/baai/bge-m3`,
`@cf/qwen/qwen3-embedding-0.6b`)을 합성 한국어 문서·질의로 비교했다.

## Decision

임베딩 모델은 `@cf/baai/bge-m3`(1,024차원)를 쓴다.

## Rationale

- 셋 중 단가가 가장 낮다. 한국어 1,000자당 0.58 Neurons이고 요금표는 1M 토큰당 1,075다. Phase 1 대상 문서
  1,083 KB를 한 번 전체 색인하면 약 325 Neurons로, 일일 무료 할당의 3.3%다.
- 정식 모델이고 단가가 공개돼 있다. embeddinggemma는 Beta이고 Cloudflare 문서·요금표·카탈로그 API 어디에도
  입력 한도와 단가가 없어 측정 추정에 의존해야 한다(스파이크 W-01).
- 입력 한도 8,192토큰을 넘으면 HTTP 400(코드 3030)으로 알려 준다. 나머지 두 모델은 오류 없이 자른다.
  조용히 자르면 청크 뒷부분이 검색에서 빠져도 알 수 없다(스파이크 W-02).
- 질의·문서 접두어가 필요 없다. 접두어 형식이 바뀌면 전체 재임베딩이 필요한데 그 위험이 없다.
- 지연이 이번 측정에서 가장 짧았다(질의 12개 264 ms). 1회 측정이라 순위로 쓰지는 않지만,
  qwen3-embedding처럼 0.8~6.5초로 들쭉날쭉한 모델은 피한다.

## Alternatives considered

| Alternative | Advantages | Disadvantages | Reason not selected |
| --- | --- | --- | --- |
| `@cf/google/embeddinggemma-300m` (로드맵 기본안) | 768차원으로 저장 공간이 가장 작다. Matryoshka로 512·256·128차원까지 줄일 수 있다 | Beta다. 한도·단가가 공개되지 않았다. 입력 한도가 약 2,048토큰으로 가장 짧고 넘으면 조용히 잘린다. 단가가 bge-m3의 1.44배다. 접두어를 직접 붙여야 한다 | 단가·한도가 공개되지 않아 예산 계산을 검증할 수 없고, 한도 초과를 감지할 수 없다 |
| `@cf/qwen/qwen3-embedding-0.6b` | 응답 `usage`에 토큰 수와 Neurons를 준다. 이번 검색에서 정답·오답 간격이 가장 컸다 | 가장 느리고 지연 편차가 크다. 넘는 입력을 조용히 자른다. 질의마다 지시문이 필요하다. Cloudflare에서 차원 지정 방법을 확인하지 못했다 | 지연 편차가 크고 한도 초과를 감지할 수 없다 |

## Evidence

- `docs/sdd/research/spike-workers-ai.md` 3.1·3.2·3.3·5.1절. 측정 조건: 합성 한국어 문서 12개(부록 A.1),
  질의 12개(부록 A.2), n=12, 각 1회 측정, 2026-10-09, 임베딩 비교에 쓴 Neurons 약 7.
- 입력 한도와 요금표 근거는 같은 문서 7절의 Cloudflare 문서·모델 카드 출처([C5][M1]).
- pgvector의 `vector` 인덱스 차원 한도 2,000: https://neon.com/docs/extensions/pgvector (조회 2026-10-10)

## Data and cost

- 외부로 전송되는 데이터와 제공자의 학습 사용·보존 정책: 색인 대상 청크 본문과 질의를 Cloudflare Workers AI로
  보낸다. Cloudflare는 Workers AI 입력·출력을 모델 학습에 쓰지 않는다고 밝힌다(`spike-workers-ai.md` 7절).
  비밀값 검사를 통과한 청크만 보낸다(AGENTS.md 3.1, QK-SEC-001).
- 무료 한도와 예상 사용량: 하루 10,000 Neurons. Phase 1 전체 색인 1회 약 325, 증분 동기화는 그보다 작다.
  질의 임베딩은 하루 50건에 1 Neurons 미만이다.
- 교체 시 영향: 차원이 1,024다. 다른 모델로 바꾸면 전체 재임베딩과 인덱스 버전 상승이 필요하다(AGENTS.md 3.3).

## Consequences

### Positive

- 단가와 입력 한도가 공개돼 있어 예산 계산과 청크 크기 상한을 검증할 수 있다.
- 한도 초과를 HTTP 400으로 잡는다. 청커 테스트에서 경계를 확인할 수 있다.
- 접두어 규칙이 없어 청커와 검색 양쪽이 단순해진다.

### Negative / risks

- 차원이 1,024라 768보다 저장 공간이 33% 크다. pgvector 인덱스 한도(2,000차원) 안이라 구현 제약은 없다.
- 카탈로그 API의 `context_window` 값 60,000이 실제 8,192와 다르다. 카탈로그 값을 설정에 쓰지 않는다.
- 응답에 토큰 수가 없다. 사용량은 `cf-ai-neurons` 응답 헤더로만 집계한다(QK-EMB-001).
- 한국어 검색 품질로 세 모델을 가르지 못했다. 합성 세트가 쉬워 bge-m3와 qwen3-embedding이 모두 12/12로
  포화됐다(스파이크 W-06). 이 결정은 운영 조건(단가·한도·접두어·지연) 근거다.

## Revisit conditions

- QK-EVL-001(1.12) 검색 평가에서 Recall@5·MRR이 목표에 못 미치고 원인이 임베딩으로 좁혀질 때.
- 일일 Neurons 사용량이 무료 할당의 80%를 넘을 때.
- bge-m3의 단가·한도·지원이 바뀌거나 Workers AI 카탈로그에서 내려갈 때(RISK-04).
- 저장 용량이 Supabase Free 500 MB의 80%를 넘을 때. 차원을 줄일 수 있는 모델을 다시 본다.

## Approval

- Approvers: 확인 필요
- Approved at: 미승인. 사용자가 2026-10-10에 모델을 선택했고, 이 문서의 승인은 PR 리뷰에서 받는다.
