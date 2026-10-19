# Research: QK-STO-001 저장 스키마·마이그레이션·검색 질의

조회일과 실측일은 모두 2026-10-19다. 계획(`plan.md`)의 기술 맥락에 남은 미정 항목을 여기서 닫는다.
로컬 실측 환경은 `supabase/postgres:17.11.0.004`(PostgreSQL 17.11, pgvector 0.8.2, PGroonga 3.2.5)이고, 별도 데이터베이스
`qk_spike`에서 실행한 뒤 지웠다.

## R-01 ADR-007 자체 스키마 vs PGVectorStore

- **Decision**: 자체 스키마·자체 마이그레이션·SQL 검색 함수를 만든다. 결정 기록은
  [ADR-007](../../docs/sdd/decisions/ADR-007-storage-schema.md)이다(2026-10-19 승인).
- **Rationale**: 로컬 스파이크에서 LlamaIndex `PGVectorStore` 0.9.0은 한국어 키워드("재시도", "개발") 검색이 0건이었고(tsvector `simple`),
  문서 교체가 두 트랜잭션으로 나뉘며, 인덱스 버전·출처 필수 검사·마이그레이션 기록을 넣을 자리가 없었다. 의존성(126 MB)도 Workers에 못 싣는다.
  자체 스키마 시제품은 같은 시험을 모두 통과했다. 비교표는 ADR-007 Evidence에 있다.
- **Alternatives considered**: LlamaIndex `PGVectorStore`(실측), langchain-postgres `PGVectorStore`(문서 기준, 실측 안 함).

## R-02 스키마 배치와 제약

- **Decision**: 모든 객체를 `qk` 스키마에 둔다. 테이블은 `index_version`, `artifact`, `embedding`, `chunk`, `schema_migration` 다섯 개다.
  요구사항은 가능한 한 DB 제약으로 강제한다.
  - 차원: `embedding.vector`를 `vector(1024)`로 선언해 다른 차원을 DB가 거부한다(FR-004, ADR-002).
  - 활성 인덱스 하나: `index_version`에 `status = 'active'` 부분 고유 인덱스(`ON ((true)) WHERE status = 'active'`)를 둔다(FR-005).
  - 출처 필수: `artifact.source_url`, `chunk.source_version`은 `NOT NULL`·빈 문자열 금지, `chunk.locator`는 빈 JSON 객체 금지(FR-004).
  - 임베딩 공유: `embedding`에 `(input_hash, model_version)` 고유 제약을 두고 청크가 외래 키로 가리킨다(FR-003).
- **Rationale**: 스파이크에서 차원 3 벡터는 `expected 1024 dimensions`로, 두 번째 활성 버전은 고유 제약 위반으로 거부됐다. 애플리케이션 검사만
  두면 다른 경로(수동 SQL, 후속 어댑터)에서 빠질 수 있다. `public`이 아닌 스키마에 두면 HTTP RPC 계층(PostgREST 등)을 붙여도 테이블이 기본으로 노출되지 않는다.
- **Alternatives considered**: 차원 없는 `vector` 칼럼 + `CHECK (vector_dims(v) = 1024)`(차원이 바뀌어도 칼럼을 안 바꿔도 되지만 HNSW 인덱스는
  고정 차원이 필요하다). 모델 차원이 바뀌면 새 인덱스 버전과 마이그레이션으로 칼럼을 추가한다(C-07).

## R-03 키워드 검색

- **Decision**: `chunk.search_text`에 PGroonga 인덱스(토크나이저 `TokenBigramSplitSymbol`, 정규화 `NormalizerAuto`)를 두고
  `search_text &@~ pgroonga_query_escape(:q)`로 검색한다. 점수는 `pgroonga_score(tableoid, ctid)`다. 검색어가 비었거나 공백뿐이면
  질의하지 않고 빈 결과를 돌려준다.
- **Rationale**: 스파이크에서 `retryPayment`(대소문자 무관), `/payments/{id}/cancel`, `max_retry_count`, "재시도", "개발"이 모두 맞는 청크를 찾았다.
  `(a OR "b`는 이스케이프 뒤 오류 없이 처리됐다(FR-010). `search_text`를 본문과 따로 두므로 ADR-010 후보(식별자 분해 등)를 스키마 변경 없이
  바꿔 넣을 수 있다(FR-002). 이번 작업에서는 `search_text = body`로 채운다.
- **토크나이저 비교(구현 중 실측, 2026-10-19)**: 기본 `TokenBigram`은 Markdown에 흔한 백틱 감싼 경로(`` `/health` ``,
  `` `/payments/{id}/cancel` ``)를 찾지 못했다. 백틱과 `/`가 기호 토큰 하나로 묶이기 때문이다. 같은 8문장으로 비교한 결과다.

  | 토크나이저 | 백틱 경로 | `retryPayment` | `retry` → `retryPayment` | `health` → `healthcheck` | 한국어 |
  | --- | --- | --- | --- | --- | --- |
  | `TokenBigram` | 못 찾음 | 찾음 | 못 찾음 | 못 찾음 | 찾음 |
  | `TokenBigramSplitSymbol` (선택) | 찾음 | 찾음 | 못 찾음 | 못 찾음 | 찾음 |
  | `TokenBigramSplitSymbolAlpha(Digit)` | 찾음 | 찾음 | 찾음 | 찾음 | 찾음 |

  기호만 쪼개는 `TokenBigramSplitSymbol`을 쓴다. 영문까지 쪼개면 식별자 부분 검색이 되지만 일치가 넓어져 정밀도가 달라진다.
  이 선택은 검색 품질 평가가 필요하므로 QK-RET-001(ADR-010)에서 비교한다. 바꿀 때는 인덱스만 다시 만드는 마이그레이션 하나로 된다.
- **Alternatives considered**: tsvector(한국어 실패, R-01), `&@`(단일 키워드만 받아 여러 단어 검색이 안 된다), pg_bigm(이미지에 없음).

## R-04 벡터 검색과 질의 안 필터

- **Decision**: `embedding.vector`에 HNSW 인덱스(`vector_cosine_ops`)를 두고, 검색 함수 속성(`CREATE FUNCTION ... SET hnsw.iterative_scan = relaxed_order`)으로
  iterative scan을 켜고 활성 인덱스 버전·활성 자료·팀 공용 접근 범위·선택 필터를 `WHERE`에 넣는다. 점수는 `1 - 코사인 거리`, 순위는 1부터 매긴다.
- **Rationale**: 필터를 질의 안에 넣어야 C-14·FR-008을 지킨다. HNSW는 필터 전 후보만 보므로 필터가 많이 걸리면 상위 N이 모자랄 수 있는데,
  pgvector 0.8의 iterative scan이 모자란 만큼 더 훑는다. 스파이크에서 같은 벡터를 가진 청크 8개 중 허용 4개만 나왔다.
  Phase 1 규모(원문 약 1.1 MB, 청크 수천 개)에서는 인덱스 없이 전부 훑어도 빠를 수 있어, SC-005 측정에서 실행 계획을 함께 기록한다.
- **Alternatives considered**: 결과를 받은 뒤 거르기(FR-008 위반), 부분 인덱스를 범위별로 만들기(범위 값 체계가 QK-SEC-001에서 정해지기 전이라 이르다).

## R-05 접근 범위 값

- **Decision**: `artifact.access_scope`는 문자열로 저장하고, 검색 대상은 값이 정확히 `team`인 자료뿐이다. `NULL`과 그 밖의 값은 모두 제외한다.
  상수는 `qk.visible_access_scope()` 함수 하나에 둔다.
- **Rationale**: 명세 Edge Cases가 빈 값을 "미확인"으로 다루라고 한다. 값 체계는 QK-SEC-001이 정하므로, 여기서는 허용 목록 하나만 두고
  나머지를 모두 막는 쪽(기본 거부)을 택한다. 값 체계가 바뀌면 함수 하나와 마이그레이션 하나로 바꾼다.
- **Alternatives considered**: `boolean` 칼럼(값 체계 확장 시 스키마가 바뀐다), enum 타입(QK-SEC-001 전에 값을 고정한다).

## R-06 검색 질의의 형태와 Workers 연결

- **Decision**: 벡터 검색, 키워드 검색, 주변 청크 조회를 `qk` 스키마의 SQL 함수(`qk.search_vector`, `qk.search_keyword`, `qk.chunk_neighbors`)로 둔다.
  검색 함수는 `jsonb` 하나(`{"active_index_version": ..., "hits": [...]}`)를 돌려준다. 이번 작업에서는 색인 쪽과 테스트가 psycopg로 부른다.
  Workers 질의 경로는 같은 함수를 HTTP RPC(운영 인스턴스의 PostgREST 등, HTTP 한 번)로 부르는 어댑터를 QK-RET-001·QK-BOT-001에서 만든다.
  운영 저장소가 Oracle Cloud 인스턴스로 바뀌어(ADR-008 변경 제안) Supabase Data API는 쓸 수 없다.
- **Rationale**: Python Workers에는 psycopg 같은 TCP 드라이버를 실을 수 없다. 함수로 두면 검색 한 번이 저장소 왕복 한 번(subrequest 하나)이고
  조건(C-14)이 DB 안 한 곳에 있다(ADR-008 가정). `jsonb`로 돌려주면 "활성 인덱스 없음" 상태를 같은 왕복에 실을 수 있다(Edge Cases).
- **Alternatives considered**: 애플리케이션 코드에 SQL 문자열을 두기(Workers 경로에서 다시 써야 하고 조건이 두 곳이 된다), Hyperdrive(Python Workers
  드라이버 문제는 같다).
- **남는 위험**: HTTP RPC 계층의 종류, 역할·권한 설정(함수만 노출, 테이블 차단), 공인 포트 없이 연결하는 방법(예: Cloudflare Tunnel)은 정하지 않았다.
  운영 연결을 만드는 QK-BOT-001에서 정한다.

## R-07 문서 단위 교체

- **Decision**: 교체 연산은 트랜잭션 하나에서 ① 원본 자료 행을 `SELECT ... FOR UPDATE`로 잠그고 ② 요청의 원본 버전·청크 묶음 해시가 저장된 값과
  같으면 아무것도 바꾸지 않고 끝내며 ③ 다르면 그 자료의 해당 인덱스 버전 청크를 지우고 새 청크를 넣은 뒤 원본 자료 행을 갱신한다.
- **Rationale**: PostgreSQL MVCC로 커밋 전에는 다른 세션이 이전 청크만 본다. 스파이크에서 교체 도중 실패를 넣어도 이전 5개가 그대로였고,
  동시 교체 두 건은 행 잠금으로 직렬화돼 한쪽 결과만 남았다(FR-012·013). 해시 비교로 같은 요청을 다시 실행하면 변경 0건이다(C-08).
- **Alternatives considered**: 세대 번호를 두고 활성 세대를 바꾸기(검색 조건이 늘고 이전 세대 정리가 필요하다), advisory lock(행 잠금으로 충분하다).

## R-08 마이그레이션 실행기

- **Decision**: 표준 라이브러리 + psycopg로 작은 실행기를 만든다. 파일은 `src/qello_knowledge/adapters/postgres/migrations/NNNN_<설명>.sql`이고
  패키지에 포함된다. 실행기는 다음을 지킨다.
  - 시작할 때 `pg_advisory_lock`으로 동시 실행을 막는다.
  - `qk.schema_migration`에 버전, 설명, SHA-256 체크섬, 적용 시각, 결과를 남긴다. 성공 기록이 있는 버전은 건너뛴다(FR-017).
  - 성공 기록의 체크섬과 파일 체크섬이 다르면 아무것도 적용하지 않고 멈춘다(FR-017).
  - 마이그레이션 하나를 트랜잭션 하나로 적용한다. 실패하면 되돌린 뒤 별도 트랜잭션에 실패 기록을 남기고 0이 아닌 코드로 끝낸다(FR-018).
  - 파일 첫 줄 주석 `-- qk:destructive`가 있으면 파괴적 변경으로 본다. 대상이 로컬(QK-FND-001 R-06 판단 재사용)이 아니면
    `--allow-destructive` 없이는 적용하지 않는다(FR-019).
  - 결과로 적용 개수를 출력한다. 두 번째 실행은 `applied=0`이다(SC-004).
- **Rationale**: 요구사항이 체크섬·원자 적용·파괴적 표시로 구체적이고, 마이그레이션은 SQL이면 된다. 의존성을 늘리지 않고 150줄 안팎이다.
- **Alternatives considered**: Supabase CLI 마이그레이션(Go 바이너리 설치, 체크섬 검사 없음, 로컬·운영 DB 모두 Supabase CLI 스택이 아님),
  Alembic(SQLAlchemy 의존성, Python 마이그레이션), yoyo-migrations(파괴적 표시 없음, 체크섬 불일치 시 멈춤 대신 경고).
- **남는 위험**: `CREATE INDEX CONCURRENTLY`처럼 트랜잭션 안에서 못 도는 문장은 쓸 수 없다. 데이터가 작아 Phase 1에서는 문제가 없다고 본다.

## R-09 저장소 경계와 의존성

- **Decision**: `ports/store.py`의 `Store` Protocol에 연산을 정의하고, 입력·출력 타입은 `domain/store.py`의 dataclass로 둔다(FR-015, C-06).
  구현은 `adapters/postgres/`에 두고 psycopg는 선택 의존성 `[project.optional-dependencies] postgres`로 추가한다. 개발 그룹에는 이미 있다.
- **Rationale**: QK-FND-001 R-04 경계 검사(`domain`·`ports`는 표준 라이브러리만)를 그대로 지킨다. 질의응답 번들에 psycopg가 딸려 가지 않는다.
- **Alternatives considered**: 런타임 의존성에 psycopg 추가(Workers 번들에 들어간다).

## R-10 테스트 구성

- **Decision**: 저장소 테스트는 `localdb` 표시를 붙여 `tests/localdb/store/`에 둔다. 세션마다 로컬 DB에 `qk_test_<무작위>` 데이터베이스를 만들어
  전체 마이그레이션을 적용하고 끝나면 지운다. 테스트마다 트랜잭션 대신 `TRUNCATE`로 비운다(교체·동시성 시험은 여러 연결이 필요하다).
  교체 도중 실패는 마지막 청크의 위치 정보를 비워 DB 제약 위반을 일으키는 방식으로 넣는다. 테스트 전용 훅을 제품 코드에 두지 않는다.
  벡터는 고정 시드 난수로 만든다(외부 호출 0건).
- **Rationale**: 공유 `postgres` 데이터베이스를 건드리지 않아 다른 테스트·개발 데이터와 섞이지 않는다(AGENTS.md 4절). 실제 제약 위반은 실제 실패
  경로를 탄다.
- **Alternatives considered**: 저장소 가짜 구현만으로 테스트(질의 안 필터·원자성·PGroonga를 확인할 수 없다).

## R-11 CI

- **Decision**: 기존 `test` job에 `uv run qk-migrate` 두 번 실행 단계를 넣는다. 두 번째 출력이 `applied=0`이 아니면 실패한다(FR-020, SC-004).
  저장소 테스트는 기존 `uv run pytest`(`QK_REQUIRE_LOCALDB=1`)로 함께 돈다.
- **Rationale**: 새 job을 만들지 않고 이미 띄운 로컬 DB를 쓴다. CI 시간 목표(10분)에 영향이 작다.

## R-12 성능·용량 측정 (SC-005, SC-006)

- **Decision**: `uv run qk-dev store bench`가 로컬 DB의 별도 데이터베이스에 합성 데이터(원문 약 1.1 MB 상당 청크, 1,024차원 난수 벡터)를 넣고
  벡터·키워드 검색 상위 20건을 각각 100회 돌려 p50·p95와 실행 계획 요약, 저장 사용량(FR-023)을 출력한다. 결과는 조건(데이터 규모, 반복 횟수,
  하드웨어, 이미지 태그)과 함께 `quickstart.md` 기록 절에 남긴다(C-13). SC-006은 같은 측정의 바이트/원문 바이트 비율로 10 MB 규모를 추정한다.
- **Rationale**: 실제 팀 자료를 쓰지 않고 측정한다(외부 전송 0, 비공개 원문 미기록). 기본 테스트에는 넣지 않는다(시간).
- **남는 위험**: 로컬 Apple Silicon 수치는 운영 인스턴스(A1 2 OCPU·12 GB) 수치와 다르다. 둘 다 arm64라 경향은 비슷하다고 보지만, 운영 측정은 QK-RET-001·QK-BOT-001에서 한다.

## R-13 운영 저장소 확인 (US6, FR-022)

- **Decision**: 2026-10-19 사용자 결정(잠정)에 따라 운영 저장소를 Supabase Free에서 Oracle Cloud Always Free Ampere A1 인스턴스의 자체 운영
  PostgreSQL로 바꾸는 변경 제안을 ADR-008에 남겼다. 데이터 처리 정책은 Oracle 공식 문서·약관을 조회해 같은 절에 출처 URL·조회일과 함께 적었고,
  컴퓨트·블록 볼륨 내용의 학습 사용 여부와 종료 뒤 보존 기간(일수)은 "확인 못 함"으로 남겼다. 운영 PGroonga 확인은 인스턴스에서 로컬과 같은 이미지
  (`supabase/postgres:17.11.0.004`, arm64)로 `CREATE EXTENSION`이 되는지 보는 것으로 바뀐다. 인스턴스 생성은 이 작업 범위 밖이라 사람 확인 대기(`BLOCKED`)다.
- **Rationale**: 같은 이미지를 직접 띄우므로 확장 기능은 우리가 통제한다. 로컬(aarch64)에서 같은 이미지로 이미 확인했으므로(R-01) 남는 위험은
  인스턴스 자원(2 OCPU·12 GB)과 운영 쪽이다. 스키마·질의 설계(R-02~R-08)는 운영 위치와 무관해 바꾸지 않는다. Workers 연결만 R-06에서 HTTP RPC 계층으로 바꿨다.
- **남는 위험**: 7일 저사용 시 유휴 인스턴스 회수(ADR-008 변경 제안). 대응을 정하기 전에는 실제 팀 자료의 유일한 사본을 두지 않는다.
- **Evidence**: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm (조회 2026-10-19)
