# Decision Record: ADR-007 저장 스키마 — 자체 스키마 vs PGVectorStore

> Created at: `2026-10-19`
> Jira 이슈: `https://tkv123.atlassian.net/browse/SCRUM-90`
> 기능명세서 ID: `QK-STO-001`
> Status: Accepted

## Context

QK-STO-001은 청크·임베딩·인덱스 버전을 저장하고 벡터 검색과 한국어 키워드 검색을 제공해야 한다. 로드맵 3절 Phase 1 진행 순서 1이
"저장 스키마 스파이크에서 ADR-007(자체 스키마 vs PGVectorStore)을 확정한다"고 정했고, 명세 FR-021이 비교 기준을 정했다.

- FR-002: 키워드 검색용 텍스트를 본문과 따로 둔다(ADR-010 후보 비교용).
- FR-005: 인덱스 버전과 "활성 하나 이하" 규칙.
- FR-008: 권한·상태·버전 조건을 질의 안에서 적용한다(C-14).
- FR-012·013: 문서 단위 교체가 원자적이고 동시 실행에 안전하다(C-08).
- FR-016~019: 스키마 변경을 버전·체크섬이 붙은 마이그레이션으로만 한다.

여기에 ADR-008 제약이 붙는다. 질의응답은 Cloudflare Python Workers에서 돌고(CPU 10 ms, subrequest 50개), 운영 저장소는
PostgreSQL(pgvector·PGroonga)이다. 운영 위치는 Supabase Free에서 Oracle Cloud Always Free 인스턴스로 바꾸는 변경 제안이 있다(ADR-008).

## Decision

LlamaIndex `PGVectorStore`를 쓰지 않고, 자체 스키마(`qk` 스키마의 원본 자료·청크·임베딩·인덱스 버전 테이블)와 자체 마이그레이션,
SQL 검색 함수를 만든다.

## Rationale

- 한국어 키워드 검색: `PGVectorStore`의 하이브리드 검색은 PostgreSQL `tsvector`(설정 `simple`)로 고정돼 있다. 로컬 스파이크에서
  "재시도"·"개발"을 검색하면 0건이었다. 조사가 붙은 어절("재시도는")이 토큰 하나로 들어가기 때문이다. 같은 데이터에서 PGroonga
  `&@~`는 두 단어를 찾았다. 키워드 검색은 RISK-05의 핵심이라 이 차이가 결정적이다.
- 문서 단위 교체: `PGVectorStore.delete(ref_doc_id)`와 `add(nodes)`가 각각 자기 트랜잭션을 열고 커밋한다(소스 `base.py`의
  `with self._session() as session, session.begin()` 블록). 둘 사이에 실패하면 문서 청크가 비고, 두 교체가 동시에 돌면 섞일 수 있다.
  자체 스키마는 한 트랜잭션 안에서 원본 자료 행을 `FOR UPDATE`로 잠그고 지우고 넣는다. 스파이크에서 교체 도중 실패를 넣어도 이전
  청크 5개가 그대로 보였고, 동시 교체 두 건은 한쪽 결과만 남았다.
- 스키마 통제: `PGVectorStore`는 `perform_setup=True`로 실행 시점에 테이블을 만든다(`id`, `text`, `metadata_ json`, `node_id`,
  `embedding vector(n)`, `text_search_tsv`). 인덱스 버전, 출처 필수 검사, 임베딩 공유(FR-003), 별도 키워드 텍스트(FR-002)를
  넣을 자리가 없고 마이그레이션 기록도 없다. 메타데이터가 JSON 한 칸이라 출처 누락을 DB가 거부하게 만들 수 없다.
- Workers 호환: `PGVectorStore`는 SQLAlchemy·asyncpg·psycopg2·llama-index-core가 필요하다(설치 크기 126 MB, 패키지 139개).
  Python Workers 번들에 넣을 수 없어 질의 경로에서는 어차피 쓰지 못한다. 자체 스키마는 검색을 SQL 함수로 두므로 색인 쪽은 psycopg로,
  Workers 쪽은 HTTP RPC(PostgREST 등) 한 번으로 같은 함수를 부를 수 있다(research R-06). 운영 위치가 바뀌어도 그대로다.
- 대가: 마이그레이션 실행기와 검색 SQL을 직접 쓴다. 범위가 테이블 4개, 함수 3개, 실행기 하나라 감당할 수 있다고 본다.

## Alternatives considered

| Alternative | Advantages | Disadvantages | Reason not selected |
| --- | --- | --- | --- |
| LlamaIndex `PGVectorStore` 0.9.0 | 노드 저장·필터·하이브리드 검색이 바로 된다. LlamaIndex 검색기와 붙는다 | 한국어 키워드 검색 실패(tsvector). 교체가 두 트랜잭션. 스키마·마이그레이션 통제 없음. Workers 번들 불가 | FR-002·005·007·012·016을 만족하지 못한다 |
| langchain-postgres `PGVectorStore` | 테이블 이름·메타데이터 칼럼을 지정할 수 있다 | 이번 스파이크에서 돌려 보지 않았다. 키워드 검색이 tsvector 기반이고 Workers 번들 문제는 같다고 본다(문서 확인 기준) | 같은 이유. 실측하지 않았으므로 근거는 문서 수준이다 |
| 자체 스키마 + PGroonga + 자체 마이그레이션 (선택) | 요구사항을 DB 제약으로 강제한다. 검색이 SQL 함수라 실행 환경과 무관하다 | 실행기와 SQL을 직접 유지한다 | — |

## Evidence

로컬 스파이크(2026-10-19). 환경: `supabase/postgres:17.11.0.004`, PostgreSQL 17.11(aarch64), pgvector 0.8.2, PGroonga 3.2.5.
별도 데이터베이스 `qk_spike`에서 실행하고 끝난 뒤 지웠다. 표본이 작아(청크 8개) 기능 확인용이며 성능 근거가 아니다.

| 확인 | 자체 스키마 | PGVectorStore 0.9.0 |
| --- | --- | --- |
| 1,024차원이 아닌 벡터 저장 | 거부(`expected 1024 dimensions, not 3`) | 테이블 차원과 다르면 거부(고정 차원 칼럼) |
| 활성 인덱스 버전 2개 | 거부(부분 고유 인덱스) | 해당 개념 없음 |
| 키워드 `retryPayment` | 찾음 | 찾음 |
| 키워드 `/payments/{id}/cancel`, `max_retry_count` | 찾음 | 미측정 |
| 키워드 "재시도", "개발"(한국어) | 찾음 | 0건 |
| 검색어 `(a OR "b`(문법 특수 문자) | `pgroonga_query_escape`로 오류 없이 0건 | 미측정 |
| 권한·상태·버전 조건을 건 벡터 검색 | 허용 청크 4건만 반환(미확인·제한·삭제·비활성 버전 4건 제외) | JSON 메타데이터 필터로 범위 1건 제외 확인 |
| 교체 도중 실패 | 이전 청크 5개 유지 | delete·add가 별도 커밋(소스 확인, 실측 안 함) |
| 동시 교체 A(3개)·B(2개) | B 2개만 남음, 섞임 없음 | 미측정 |

- 남는 관찰: 키워드 `retry`는 `retryPayment`를 찾지 못했다(어절 단위 토큰). 식별자 부분 검색은 키워드 검색 텍스트 생성(ADR-010, QK-RET-001)에서 다룬다.
- PGroonga 연산자·함수: https://pgroonga.github.io/reference/operators/query-v2.html ,
  https://pgroonga.github.io/reference/functions/pgroonga-query-escape.html (조회 2026-10-19)
- pgvector 필터와 iterative scan: https://github.com/pgvector/pgvector#iterative-index-scans (조회 2026-10-19)
- LlamaIndex PGVectorStore: PyPI `llama-index-vector-stores-postgres` 0.9.0 소스(`llama_index/vector_stores/postgres/base.py`)

## Data and cost

- 외부로 전송되는 데이터와 제공자의 학습 사용·보존 정책: 이 결정은 새 외부 서비스를 추가하지 않는다. 저장 위치는 ADR-008(Oracle Cloud 인스턴스로 바꾸는 변경 제안)이고
  그 정책 확인 결과는 ADR-008 변경 제안 절에 있다.
- 무료 한도와 예상 사용량: 해당 없음. 저장 용량 추정은 QK-STO-001 SC-006에서 측정한다.
- 교체 시 영향(재임베딩, 인덱스 버전): 나중에 프레임워크 저장소로 옮기면 스키마가 달라져 전체 재색인이 필요하다. 임베딩은 입력 해시로
  다시 쓸 수 있다(FR-003).

## Consequences

### Positive

- 출처 누락, 차원 불일치, 활성 버전 중복을 DB 제약이 막는다.
- 검색 조건(C-14)이 SQL 함수 한 곳에 있어 질의 경로가 바뀌어도 빠지지 않는다.
- 런타임 의존성이 psycopg 하나다(색인 쪽 선택 의존성).

### Negative / risks

- 마이그레이션 실행기와 검색 SQL을 팀이 유지한다.
- LlamaIndex 검색기·평가 도구를 그대로 붙일 수 없다. 필요해지면 `Store` 경계 위에 어댑터를 만든다.
- langchain-postgres는 실측하지 않았다.

## Revisit conditions

- QK-RET-001 평가에서 자체 검색 SQL이 지연 목표(SC-005)나 품질 기준을 못 맞출 때.
- Workers 질의 경로를 포기하고 Python 서버로 옮겨 프레임워크 의존성이 문제가 되지 않을 때.
- 한국어 키워드 검색을 PGroonga 없이 해야 할 때(ADR-008 Revisit conditions와 같다).

## Approval

- Approvers: 사용자(GitHub `tkv00`)
- Approved at: 2026-10-19. QK-STO-001 작업 세션에서 로컬 스파이크 근거를 보고 승인했다. 기록을 쓴 세션과 승인자가 다르다(AGENTS.md 2절).
