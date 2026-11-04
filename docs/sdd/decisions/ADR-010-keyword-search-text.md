# Decision Record: ADR-010 키워드 검색 텍스트 규칙은 후보 A(기준선)를 유지한다

> Created at: `2026-11-04`
> Jira 이슈: `https://tkv123.atlassian.net/browse/SCRUM-124`
> 기능명세서 ID: `QK-EVL-001` (후보와 비교 기준은 `QK-RET-001` research R-11)
> Status: Proposed
>
> 이 문서의 수치는 [검색 평가 리포트](../../../specs/QK-EVL-001-retrieval-eval/measurement/retrieval-eval-report.md)를 그대로 옮긴 것이다. Status 결정과 운영 반영은 사람이 별도 작업으로 한다(QK-RET-001 FR-021).

## Context

- 하이브리드 검색의 키워드 쪽은 청크마다 키워드 검색용 텍스트를 만들어 PGroonga로 색인한다(QK-RET-001 US5). 어떤 텍스트를 어떤 토크나이저로 색인할지가 ADR-010이다.
- ADR-007 스파이크에서 `retry`가 `retryPayment`를 찾지 못했다(QK-RET-001 spec US5). 식별자 일부로 묻는 질문을 키워드 검색이 놓칠 수 있다.
- QK-RET-001은 색인 쪽 후보 두 개를 구현하고 운영 기본값은 기준선으로 두었다. 운영 규칙 변경은 QK-EVL-001 비교와 이 결정 뒤로 미뤘다(QK-RET-001 spec Clarifications).
- 로드맵 1.G는 첫 검색 평가 리포트와 ADR-010 결정을 요구한다.

후보(QK-RET-001 research R-11, QK-EVL-001 spec FR-023):

| 후보 | 색인 쪽 규칙 | 토크나이저 | 질의 쪽 규칙 | 운영에 반영할 때 |
| --- | --- | --- | --- | --- |
| A 기준선 | `kw-index-baseline-v1`(제목 경로 + 본문) | `TokenBigramSplitSymbol` | `kw-query-v1` | 변경 없음(현재 운영 기본값) |
| B 식별자 분해 | `kw-index-idsplit-v1` | `TokenBigramSplitSymbol` | `kw-query-v1` | 새 인덱스 버전(`iv-8b7e93b22051`)으로 재색인 |
| C 토크나이저 교체 | `kw-index-baseline-v1` | `TokenBigramSplitSymbolAlpha` | `kw-query-v1` | 키워드 색인 재생성 마이그레이션 |

## Decision

키워드 검색 텍스트 규칙은 후보 A(`kw-index-baseline-v1`, `TokenBigramSplitSymbol`)를 유지할 것을 제안한다.

## Rationale

- 측정 전에 고정한 판단 규칙(리포트 1.1절, 계약 고정 커밋 `9561733`, n = 3, m = 1)으로 B와 C 모두 "권고 가능"이 아니다. 규칙은 어느 후보도 권고 가능이 아니면 A를 권고한다.
- 판단 규칙: 후보 X는 (1) 주 지표(camel·pascal·acronym·digit 일부 질문 20문항의 키워드 상위 20건 포함 질문 수)가 A보다 3문항 이상 많고,
  (2) 가드레일 G1~G5가 각각 A보다 1문항 넘게 나빠지지 않고, (3) 실행이 유효하면 권고 가능이다. 둘 다 권고 가능이면 주 지표가 더 오른 후보, 같으면 B다.
- 판단 수치(리포트 4.4절, 공통 질문 집합):

| 지표 | 표본 | A | B | C |
| --- | ---: | ---: | ---: | ---: |
| 주 지표: camel·pascal·acronym·digit 일부 질문의 키워드 상위 20건 포함 | 20 | 15 | 19(+4) | 20(+5) |
| G1 골든 v2 하이브리드 Recall@5 | 23 | 22 | 22(0) | 21(−1) |
| G2 골든 v2 하이브리드 첫 근거 순위가 A보다 나빠진 질문 | 23 | — | 0 | 1(`cand-S31`) |
| G3 식별자 키워드 Precision@5가 A보다 낮아진 질문 | 82 | — | 1(`kebab-02-partial`) | 5 |
| G4 식별자 키워드 상한(20) 도달 | 82 | 28 | 30(+2) | 32(+4) |
| G5 대조군(snake·kebab·url_path 원형·일부) 키워드 상위 20건 포함 | 30 | 29 | 29(0) | 29(0) |

- B는 주 지표가 +4로 기준(3)을 넘었으나 G4가 +2로 허용(1)을 넘었다. C는 주 지표가 +5로 기준을 넘었으나 G3(5문항)과 G4(+4)가 허용을 넘었다.
- 골든 v2 하이브리드 검색은 A에서 Recall@5 22/23, MRR 17.4242/23=0.7576이고 B도 같다(리포트 4.1절). 지금 팀 질문 기준의 검색 품질은 A로도 유지된다.

## Alternatives considered

| Alternative | Advantages | Disadvantages | Reason not selected |
| --- | --- | --- | --- |
| B 식별자 분해 | 식별자 일부 질문 35문항의 키워드 Recall@5가 26/35 → 32/35(리포트 4.2절 query_form 표). 골든 v2 하이브리드 지표가 A와 같다 | 키워드 결과가 상한에 닿는 질문이 28 → 30으로 늘었다(일치가 넓어짐). 새 인덱스 버전으로 재색인이 필요하다 | 고정한 판단 규칙의 가드레일 G4(+2 > 1)를 넘었다 |
| C 토크나이저 교체 | 주 지표가 가장 많이 올랐다(15 → 20). 일부 질문 35문항의 키워드 MRR 22.5998/35=0.6457 → 28.3713/35=0.8106 | 골든 v2 하이브리드 Recall@5가 22 → 21(`cand-S31` 4위 → 16위). Precision@5가 낮아진 질문 5, 상한 도달 +4. 운영 반영에 마이그레이션이 필요하고 인덱스 버전으로 가려지지 않는다(아래 Consequences) | 가드레일 G3(5 > 1)·G4(+4 > 1)를 넘었다 |

## Evidence

- 리포트: `specs/QK-EVL-001-retrieval-eval/measurement/retrieval-eval-report.md`(1절 계약은 커밋 `9561733`, 측정 결과는 커밋 `62be51a`)
- 실행 기록: `specs/QK-EVL-001-retrieval-eval/measurement/runs/evl-20261104T074124Z-003c0063.json`(골든 v2), `…/evl-20261104T074138Z-a9f47f48.json`(식별자 v1). 둘 다 `complete = true`
- 실행 조건(리포트 1·3절):
  - 질문 세트: `qk-evl-001-golden` v2(32문항, 지표 대상 23, sha256 `ff8c661a…`), `qk-evl-001-identifiers` v1(82문항, sha256 `e573c313…`). 둘 다 2026-11-04 사람 확정
  - 자료원 `dnd-backend-docs` 고정 커밋 `6aeccd039b825dcd7a2b6c046a34ef72089a1f78`, 노출 문서 79
  - 임베딩 `@cf/baai/bge-m3`(1024차원), 질의 규칙 `kw-query-v1`, 후보 수 20, RRF 60, 검색 필터 없음. 세 대상이 한 실행에서 같은 질의 벡터를 썼다
  - 평가 대상: A `qk_eval_baseline_6aeccd039b82`(`iv-4c0bc4fcc642`, `chk-md-20d966f730bb`), B `qk_eval_idsplit_6aeccd039b82`(`iv-8b7e93b22051`, `chk-md-9621a10a386c`),
    C `qk_eval_baseline_alpha_6aeccd039b82`(`iv-4c0bc4fcc642`, 토크나이저만 교체). 모두 작업자 PC의 로컬 컨테이너
- 표본 한계: 주 지표 20문항에서 한 문항은 5%p, 골든 v2 23문항에서 한 문항은 약 4.3%p다. B의 G4 초과는 1문항 차이다.
- B 대상에서만 벡터 전용 상위 20건이 A와 다른 질문이 9개 있다. 첫 근거 순위는 모두 같다. B 데이터베이스를 새로 동기화해 HNSW 근사 색인이 다른 것으로 보인다(리포트 4.4·8.2절).
- 리포트 수치의 독립 대조(QK-EVL-001 tasks T042)는 이 문서 작성 시점에 아직 하지 않았다.

## Data and cost

- 외부로 전송되는 데이터와 제공자의 학습 사용·보존 정책: 평가 질문 문장 105개(골든 23, 식별자 82)를 Workers AI 임베딩(`@cf/baai/bge-m3`)으로 보냈다. 정책은 ADR-002를 따른다. 생성 호출 0
- 무료 한도와 예상 사용량: 측정 실제 1.04 Neurons(미리 보기 예상 2.3177 + 2.4338 이하), 일일 무료 한도 10,000. 평가용 DB 준비의 문서 임베딩은 캐시로 0 Neurons
- 교체 시 영향(재임베딩, 인덱스 버전): A 유지는 변경 없음. B로 바꾸면 새 인덱스 버전으로 재색인하되 문서 임베딩은 캐시로 처리된다(이번 B 준비가 0 Neurons). C로 바꾸면 키워드 색인 재생성 마이그레이션이 필요하고 임베딩은 바뀌지 않는다

## Consequences

### Positive

- 운영 색인과 마이그레이션을 바꾸지 않는다. 골든 v2 하이브리드 지표(Recall@5 22/23)를 그대로 유지한다.
- 측정 전에 고정한 기준으로 결정해, 수치를 본 뒤 기준을 고르는 편향이 없다.

### Negative / risks

- 식별자 일부로 묻는 질문에서 키워드 검색이 놓치는 경우가 남는다(A에서 일부 질문 20문항 가운데 5문항, 리포트 7절). 하이브리드에서는 벡터가 일부를 보완한다.
- 후보 C를 나중에 고른다면: 토크나이저는 인덱스 버전 재료가 아니어서(QK-EVL-001 spec FR-030), 운영에 반영하면 인덱스 버전이 그대로인 채 키워드 동작이 바뀐다.
  QK-STO-002 평가 게이트와 색인 쪽 규칙 대응표(`src/qello_knowledge/domain/keyword_rules.py`)가 이를 가릴 식별자가 필요하다(예: 토크나이저를 규칙 ID나 인덱스 버전 재료에 넣기). 방법은 사람이 정한다.
- 후보 B를 나중에 고른다면 `INDEX_KEYWORD_RULES`에 이미 `iv-8b7e93b22051` 대응이 있어 인덱스 버전으로 가릴 수 있다. QK-STO-002 절차로 새 버전을 평가·활성화한다.

## Revisit conditions

- 팀 질문(골든셋 다음 버전)에서 식별자 일부로 묻는 질문이 실제로 많고, 키워드 누락이 답변 실패로 이어진 사례가 쌓일 때
- 식별자 세트를 늘려 표본을 키우고 판단 규칙을 다시 정해 B를 다시 잴 때(이번 B의 G4 초과는 1문항 차이)
- Confluence 색인(QK-ING-003)처럼 자료원이 바뀌어 키워드 일치 분포가 달라질 때
- 임베딩 모델이나 청킹 규칙이 바뀌어 인덱스 버전을 올릴 때(AGENTS.md 3.3)

## Approval

- Approvers: 결정 전
- Approved at: 결정 전
