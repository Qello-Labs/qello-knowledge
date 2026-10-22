---
description: "QK-RET-001 구현 작업 목록"
---

# Tasks: QK-RET-001 하이브리드 검색·RRF·문맥 확장·토큰 예산·키워드 검색 텍스트

**Input**: `specs/QK-RET-001-hybrid-retrieval/`의 plan.md, spec.md, research.md(R-01~R-14), data-model.md, contracts/retrieval.md, contracts/cli.md, quickstart.md

**Tests**: 포함한다. 명세의 수용 시나리오와 C-12가 자동 시험을 요구한다. 시험을 먼저 쓰고 실패를 확인한 뒤 구현한다. 모든 자동 시험은 외부 호출 0건이다(가짜 임베딩 제공자
`embedding/fake.py`, 메모리 사용량 장부 `tests/unit/fakes.py`, 메모리 `RetrievalStore`, 로컬 DB). 실제 원본·Workers AI·운영 저장소는 맨 끝 "사람 단계"다.

**Organization**: 사용자 스토리별 단계. US1 → US2 → US3 → US4(모두 P1) → US5 → US6(P2) → US7(P3). US2~US4는 US1의 `retrieval/service.py`를 넓혀 나간다.
커밋은 스토리 단위로 나눈다(TASK.md 결정).

**선행 조건**: spec.md·plan.md 사람 승인(2026-10-22), 이 목록의 사람 승인, `TASK.md` Scope를 구현 범위로 갱신(plan.md "구현 Scope 승인이 필요한 것" 표 포함, AGENTS.md 1절).

**공통 규칙**:
- 질문 원문, 검색어 낱말, 청크 본문, 비밀값, 접속 주소를 로그·예외 문구·요약·사용량 기록·출력에 넣지 않는다(spec FR-008·FR-024). 시험은 이 규칙을 검사한다.
- 시험용 합성 문서만 쓰고 대상 저장소 원문을 저장소에 복사하지 않는다(AGENTS.md 6절). 시험을 지우거나 `skip`·`xfail`로 체크포인트를 통과시키지 않는다.
- 로컬 DB 시험은 `tests/localdb/` 아래에 두고 QK-STO-001 방식(세션마다 `qk_test_<무작위>` 데이터베이스 생성·마이그레이션·삭제, `tests/localdb/store/conftest.py`의 `db_url`)을 따른다.
  공유 `postgres` 데이터베이스는 건드리지 않는다.
- QK-STO-001·QK-CHK-002·QK-SYN-001·QK-FND-001 코드는 plan.md Scope 표의 변경만 한다. 기존 시험은 바꾸지 않고 그대로 통과해야 한다. 예외는 T011의 두 파일 기대값 갱신뿐이다
  (2026-10-22 사용자 결정, 검사 내용은 그대로).
- 새 시험 파일 이름은 `tests/` 전체에서 겹치지 않게 한다(시험 디렉터리에 `__init__.py`가 없어 같은 이름이면 pytest 수집이 실패한다).
- `retrieval/`은 표준 라이브러리와 `qello_knowledge.domain`·`ports`·`embedding`·`retrieval`만 가져온다(T002 경계 검사). 상대 경로 가져오기를 쓰지 않는다. 저장소는 `ports/retrieval.py`의
  `RetrievalStore`, 임베딩은 `ports/embedder.py`의 `Embedder`만 거친다.
- 기존 `qk.search_keyword`·`qk.chunk_neighbors`·`qk.hit_json`과 `PostgresStore`의 기존 메서드는 바꾸지 않는다.

**TDD 순서**: 각 단계에서 시험 작업을 먼저 쓰고 실패(아직 없는 모듈이면 수집 오류 포함)를 확인한 뒤 구현 작업을 한다. [P]는 같은 단계의 시험끼리, 구현끼리 병렬이라는 뜻이다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 다루고 미완료 작업에 기대지 않아 병렬로 할 수 있다
- **[Story]**: 해당 사용자 스토리(US1~US7)

---

## Phase 1: Setup

- [X] T001 패키지 자리 만들기: `src/qello_knowledge/retrieval/__init__.py`, `tests/unit/retrieval/`, `tests/localdb/retrieval/conftest.py`(`tests/localdb/store/conftest.py`의 `db_url` 방식을 재사용하는
  `db_url`·`store` 픽스처와, 활성 인덱스 버전 하나·자료·청크·임베딩을 합성해 넣는 `seed_chunks(...)` 도우미. 접근 범위·자료 상태·인덱스 버전·제목 경로·순서 번호를 인자로 받는다), `tests/localdb/devtools/`.
  시험 디렉터리에는 `__init__.py`를 만들지 않는다(QK-EMB-001 T001 결정과 같은 이유)
- [X] T002 [P] `tests/unit/test_boundaries.py`: 기존 `RESTRICTED`·`ALLOWED_INTERNAL`·`sync_violations`는 그대로 두고, `retrieval` 전용 허용 목록(`domain`·`ports`·`embedding`·`retrieval`)과 검사 함수를 따로 더한다.
  위반 사례 시험: `retrieval/`이 `qello_knowledge.adapters`·`security`·`chunking`·`psycopg`·`markdown_it`를 가져오면 실패, `domain`이 `qello_knowledge.retrieval`을 가져오면 기존 검사가 실패
  (contracts/retrieval.md 6절, plan.md Structure Decision)

---

## Phase 2: Foundational

**목적**: 모든 스토리가 쓰는 타입·설정, 저장소 경계와 새 SQL 함수 두 개, 메모리 저장소. 이 단계가 끝나야 스토리 시험을 쓸 수 있다.

- [X] T003 [P] `tests/unit/retrieval/test_retrieval_settings.py`(spec FR-028): `RetrievalSettings` 기본값(후보 20, RRF 60, 확장 상위 8, 앞뒤 1·1, 예산 2,000, 질문 상한 2,000자, 질의 규칙 `kw-query-v1`, 바이트당 토큰 3.5)과
  범위 경계("후보 1~50, RRF 1~1,000, 확장 상위 1~20, 앞뒤 0~3, 예산 1~8,000, 질문 상한 1~8,000자") 안·밖, 알 수 없는 질의 규칙 거부, `overrides`를 합친 값도 같은 검사를 받음
- [X] T004 [P] `tests/unit/retrieval/test_retrieval_domain.py`: data-model 2절 타입 불변식. `ContextBlock`에 같은 청크 두 번·다른 자료 청크·`ordinal` 역순이면 생성 실패, `RetrievalSummary`와 모든 결과 타입의 `repr`에
  질문·본문이 나오지 않음, `RetrievalFailure`가 spec FR-011의 아홉 값(`empty_question`, `question_too_long`, `no_active_index`, `store_unavailable`, `index_version_changed`, `query_embedding_failed`,
  `outgoing_blocked`, `keyword_search_failed`, `both_searches_failed`)과 정확히 같음
- [X] T005 `src/qello_knowledge/domain/retrieval.py`: data-model 1~2절을 표준 라이브러리 불변 dataclass·`StrEnum`으로 정의한다. `RetrievalSettings`(1.1 표의 기본·범위, 생성 때 `ValueError`, `with_overrides(**값)`),
  `RetrievalMode`(`hybrid`·`vector`·`keyword`), `RetrievalRequest`, `FusedHit`, `ContextChunk`(`role`: `center`·`section_first`·`before`·`after`), `ContextBlock`, `Skipped`(`reason`: `larger_than_budget`·
  `budget_exhausted`·`not_visible`), `Omitted`(생략한 검색과 사유), `RetrievalSummary`(2.5 필드, `source_revisions`는 기본 빈 값), `RetrievalResult`, `RetrievalFailure`(2.7 아홉 값).
  본문·질문 필드는 `field(repr=False)`
- [X] T006 [P] `src/qello_knowledge/domain/keyword_rules.py`: 규칙 식별자 상수 `QUERY_RULES = ("kw-query-v1", "kw-query-raw")`, `INDEX_RULES = ("kw-index-baseline-v1", "kw-index-idsplit-v1")`,
  `INDEX_KEYWORD_RULES = {"iv-4c0bc4fcc642": "kw-index-baseline-v1"}`(식별자 분해 항목은 T039), `index_rule_for(index_version) -> str`(없으면 `"unknown"`) (research R-05)
- [X] T007 `src/qello_knowledge/ports/retrieval.py`: `RetrievalStore` Protocol(`search_vector`, `search_keyword_terms(terms, top_n, filters) -> KeywordSearchResult`, `chunk_context(center_ids, before, after) -> ContextResult`)과
  `ContextItem(center, section_first, before, after)`·`ContextNeighbor`(QK-STO-001 `SearchHit` 필드 + `ordinal`·`artifact_id`)·`ContextResult(index_version, items)`. 키워드 결과는
  `KeywordHit(hit: SearchHit, matched_terms: int)`와 `KeywordSearchResult(status, index_version, hits: tuple[KeywordHit, ...])`로 싣고 `search_keyword_terms`는 `KeywordSearchResult`를 돌려준다.
  `domain/store.py`는 바꾸지 않는다 (contracts/retrieval.md 2절, 2026-10-22 재승인)
- [X] T008 [P] `tests/localdb/retrieval/test_keyword_terms.py`(research R-03 결정 2, data-model 4.1): `qk.search_keyword_terms`가 (1) 서로 다른 맞은 낱말 수가 많은 청크를 낱말 횟수와 무관하게 위에 둔다("결제"만 6번 나온 청크 < 네 낱말이 다 맞은 청크),
  (2) 같은 `matched_terms` 안에서는 OR 질의 점수, 그다음 `chunk_id` 순, (3) OR 질의에 없는 행의 점수는 0, (4) 일치 확장이 꺼져 `retry`가 `retryPayment`만 든 청크를 찾지 않고 다른 청크 유무와 무관하게 같은 결과,
  (5) 낱말 속 `"` `(` `-` `:` 등 특수 문자가 오류 없이 글자로 처리되고 소문자 `or` 낱말이 글자 "OR"를 찾는다, (6) 접근 범위 미확인·제한, 삭제 자료, 비활성 버전 청크 0건, 필터 적용,
  (7) `terms`가 빈 배열이면 `active_index_version`을 채운 빈 결과, 활성 버전이 없으면 `active_index_version`이 `null`, (8) 낱말 17개면 앞 16개만, `top_n`은 1~50으로 자름, (9) 같은 입력 두 번 같은 결과
- [X] T009 [P] `tests/localdb/retrieval/test_chunk_context.py`(research R-06, data-model 4.2): `qk.chunk_context`가 (1) 중심마다 `before`·`after`를 `ordinal` 오름차순으로 같은 자료·같은 인덱스 버전에서만,
  (2) `section_first` 정의(제목 경로가 다른 마지막 앞 청크 다음 청크, 없으면 자료의 첫 청크, 그것이 중심이면 `null`), 같은 제목 경로가 문서 안에 두 번 나올 때 중심 쪽 절만,
  (3) 노출 조건을 통과하지 못한 중심(미확인 접근 범위·삭제·비활성 버전·없는 식별자)은 항목이 없음, (4) 중심 21개면 앞 20개, 앞뒤 4면 3으로 자름, (5) 항목마다 `ordinal`·`artifact_id`·출처 키,
  (6) 활성 버전이 없으면 빈 `items`와 `null` 버전. 같은 파일에 `PostgresStore.source_revisions()` 시험(실행 기록 여럿 중 자료원별 가장 최근 `succeeded`의 `origin_version`, 실패 실행은 무시)
- [X] T010 `src/qello_knowledge/adapters/postgres/migrations/0005_retrieval.sql`: data-model 4.1·4.2의 두 함수. 둘 다 `STABLE`, `SET search_path = qk, public, extensions`, 쓰기 없음.
  `qk.search_keyword_terms(terms text[], top_n int, source_kinds text[] DEFAULT NULL, artifact_kinds text[] DEFAULT NULL)`에 `SET pgroonga.match_escalation_threshold = -1`, `SET enable_seqscan = off`.
  낱말별 조회는 `unnest(terms[1:16]) WITH ORDINALITY`와 `search_text &@~ pgroonga_query_escape(낱말)`, 점수는 `pgroonga_query_escape`한 낱말들을 ` OR `로 이은 질의 한 번의 `pgroonga_score`(research R-03 실측 2).
  노출은 `qk.is_visible`·`qk.kind_matches`. 반환은 `qk.search_keyword`와 같은 형식 + `matched_terms`. `qk.chunk_context`는 `qk.hit_json` 키 + `ordinal`·`artifact_id`. 기존 함수는 건드리지 않는다
- [ ] T011 0005·`keyword_text_rule` 추가로 깨지는 기존 시험의 기대값만 고친다(2026-10-22 사용자 결정): `tests/localdb/sync/test_migration.py`의 `"applied=0 skipped=4"`를 마이그레이션 파일 수에서 세게 하고
  (`tests/localdb/store/test_migrate.py`와 같은 방식), `tests/unit/devtools/test_measure.py`의 `c["settings"]` 기대 dict에 `"keyword_text_rule": "kw-index-baseline-v1"`을 더한다(T037 뒤). 검사 내용은 바꾸지 않는다.
  `tests/localdb/store/test_migrate.py`는 이미 파일 수에서 세므로 그대로. `uv run qk-migrate` 두 번째 실행이 `applied=0`
- [X] T012 `src/qello_knowledge/adapters/postgres/store.py`: `PostgresStore.search_keyword_terms`(빈 배열이면 빈 리스트를 넘김)·`chunk_context`·`source_revisions() -> Mapping[자료원 이름, 리비전]`
  (자료원별 가장 최근 `succeeded` 실행의 `qk.sync_run_source.origin_version`, research R-09). 연결 실패는 `StoreUnavailable`, 그 밖은 `StoreError`. 기존 메서드는 그대로
- [X] T013 `tests/unit/retrieval/fakes.py`: 메모리 `RetrievalStore`(정해 둔 `SearchResult`·`ContextResult`를 돌려주고, 호출 횟수와 받은 인자를 기록하고, 지정한 호출에서 `StoreUnavailable`·`StoreError`를 낸다)와
  호출 횟수를 세는 가짜 `Embedder` 감싸개(`embedding/fake.py` 제공자 + `tests/unit/fakes.py` 장부로 만든 `EmbeddingService`)
- [X] T014 [P] `src/qello_knowledge/config/registry.py`: `QK_RETRIEVAL_CONTEXT_BUDGET`(정수 1~8,000, 기본 2,000, 질의·색인 진입점) 등록. 설정 예시 파일 `.env.example`을 `uv run python -m qello_knowledge.config.example`로 다시 만든다.
  에이전트는 `.env.*`를 읽지 않으므로 생성 결과 확인은 기존 `tests/unit/config/test_example_file.py`가 맡는다. 범위 검사 시험은 새 파일 `tests/unit/config/test_retrieval_budget_setting.py`

**Checkpoint**: 로컬 DB 시험 T008·T009 통과, `qk-migrate` 재실행 안전, 기존 시험 전부 통과

---

## Phase 3: User Story 1 - 질문 하나로 벡터 검색과 키워드 검색을 합친 결과를 받는다 (P1) 🎯 MVP

**Goal**: 질문 → 질의용 임베딩 + `kw-query-v1` 낱말 배열 → 두 검색 → RRF 통합 순위(spec FR-001~005, FR-017).

**Independent Test**: 메모리 저장소와 로컬 DB에서 벡터 쪽에만·키워드 쪽에만·양쪽에 걸리는 청크가 있는 질문으로 통합 순위가 RRF 계산과 같고, 두 번 실행이 같다.

- [X] T015 [P] [US1] `tests/unit/retrieval/test_fuse.py`(research R-02, spec SC-001): `1/(k+rank)` 합, 한쪽만 나온 청크 포함, 양쪽 청크 한 번만·두 순위 기록, 수학적으로 같은 합의 동점이
  `(vector_rank, keyword_rank, chunk_id)`로 갈림(`Fraction` 비교), `k` 바꾸면 점수 변함, `keyword_matched`가 `FusedHit`에 실림
- [X] T016 [P] [US1] `tests/unit/retrieval/test_keyword_query.py`(research R-03 결정 1): `kw-query-v1` 기대값 표. "결제 취소 API 경로가 뭐야?" → `("결제", "취소", "API", "경로")`, 백틱·따옴표·괄호·`<>`·`[]`·`?!.,;:` 떼기,
  조사는 긴 것부터 하나("에서" 먼저, "경로가"→"경로", "집에서"→그대로), 대문자 `OR`→`or`(가운데 끼어도), 1글자 한글·질문 어미 목록 제외, 대소문자 무시 중복 제거, 64자 넘는 낱말 제외, 최대 16개,
  빈 질문 → 빈 배열. `kw-query-raw`는 질문 전체 낱말 하나 + 대문자 `OR`만 소문자
- [X] T017 [P] [US1] `tests/unit/retrieval/test_retrieve_hybrid.py`: 메모리 저장소로 contracts/retrieval.md 3절 1~7단계. 임베딩 요청이 `EmbedPurpose.QUERY`·입력 1개·질의마다 새 `run_id`, 두 검색 모두 `candidates`개 요청,
  필터가 두 검색에 같게 전달, 결과 항목에 통합·검색별 순위·원래 점수·`keyword_matched`·출처, 두 번 실행 같음, 결과 0건이면 `no_results`, 요약 기본 필드 값,
  한 검색 결과 안 같은 청크 두 번이면 그 검색만 생략(하이브리드), `caplog`에 질문·낱말이 없음(spec FR-008)
- [X] T018 [P] [US1] `tests/localdb/retrieval/test_hybrid.py`: 로컬 DB + 가짜 임베딩 제공자로 spec US1 수용 시나리오 1~5(한쪽 1위끼리 둘 다 나옴, 양쪽 청크 한 번, 동점 순서 고정, 자료원 필터, 결과 필드)
- [X] T019 [P] [US1] `src/qello_knowledge/retrieval/fusion.py`: `fuse(vector: SearchResult | None, keyword: KeywordSearchResult | None, k: int) -> tuple[FusedHit, ...]`(research R-02). 결과 안 중복 검사는 하지 않는다(T021이 검색마다 미리 한다)
- [X] T020 [P] [US1] `src/qello_knowledge/retrieval/keyword.py`: `keyword_query(question, rule) -> tuple[str, ...]`, 조사·질문 어미·떼는 문자 목록은 모듈 상수(research R-03 결정 1의 목록 그대로)
- [X] T021 [US1] `src/qello_knowledge/retrieval/service.py`: `retrieve(request, deps, settings)`의 1~7단계(질문 검사, 설정 합치기, 임베딩, 낱말 배열, 두 검색, `no_active_index`·버전 불일치 판정, `fuse`).
  `RetrievalDeps(store, embedder, new_run_id, model_version)`(질의 임베딩 모델 버전은 조립하는 쪽이 넘긴다, 기본 `@cf/baai/bge-m3`). 검색마다 결과 안 같은 청크가 두 번이면 그 검색의 `StoreError`로 본다(research R-02·R-14).
  요약 기본 필드(`mode`, `candidates`, `rrf_k`, `query_rule`, `index_rule`, `index_version`, `vector_count`, `keyword_count`, `keyword_terms`, `embedding`)를 채운다.
  질문 원문은 지역 변수로만 지나고 요약·예외·로그에 남기지 않는다. `retrieval/__init__.py`에서 공개

**Checkpoint**: US1 시험 통과. 이 단계까지가 MVP(순위만)

---

## Phase 4: User Story 2 - 노출하면 안 되는 청크는 결과에도 문맥에도 들어가지 않는다 (P1)

**Goal**: 통합 단계에서 새 경로가 생기지 않고, 한 결과가 한 인덱스 버전이다(spec FR-006·FR-007, SC-002).

**Independent Test**: 미확인·제한·삭제·내림·비활성 버전 청크를 질문과 가깝게 섞어 두고 결과에 0건, 버전이 바뀐 경로에서 합치지 않고 다시 검색하지 않는다.

- [X] T022 [P] [US2] `tests/localdb/retrieval/test_visibility.py`: spec US2 수용 시나리오 1·4와 SC-002 결과 쪽. 질문과 가장 가까운 청크가 미확인이면 결과에 없음, 삭제·내림(`artifact.status='deleted'`)·제한·비활성 버전 0건.
  `artifact.status='archived'`도 0건. Context 쪽(시나리오 2·3)은 T030에서 같은 파일에 더한다
- [X] T023 [P] [US2] `tests/unit/retrieval/test_retrieval_index_version.py`: 벡터·키워드 결과의 `index_version`이 다르면 `index_version_changed`이고 저장소 호출 수가 늘지 않음(다시 검색 0회, spec SC-007 일부), 한쪽이
  `no_active_index`면 `no_active_index`
- [X] T024 [US2] `src/qello_knowledge/retrieval/service.py`: 6단계 판정을 T023에 맞게 고정하고, 결과에 들어가는 청크가 저장소 반환 항목에서만 오도록 한다(캐시·별도 조회 없음, spec FR-007)

**Checkpoint**: US2 결과 쪽 시험 통과

---

## Phase 5: User Story 3 - 상위 결과에 앞뒤 문맥을 붙여 생성용 문맥 묶음을 만든다 (P1)

**Goal**: 주변 청크 일괄 조회 한 번 → 다시 확인한 중심만 → 문서별 묶음·생략 표시·Source ID(spec FR-012~015). 예산은 이 단계에서 무한대로 두고 US4에서 넣는다.

**Independent Test**: 청크 1~9인 문서에서 통합 상위가 2·3·8이면 묶음 하나, 원문 순서, gaps `(4~7 사이)`, 중복 0, Source ID와 문서 단위 출처.

- [X] T025 [P] [US3] `tests/unit/retrieval/test_context_blocks.py`: 메모리 `ContextResult`로 문서별 묶음 하나, `ordinal` 정렬, gaps 계산, 묶음 순위 = 중심의 가장 높은 통합 순위, 묶음 순서대로 `S1`, `S2`…,
  같은 청크가 여러 중심의 이웃이어도 한 번, `section_first`가 이미 중심이면 다시 넣지 않음, 문서 단위 출처(원본 링크·버전·원본 수정 시각·수집 시각)와 청크별 위치·제목 경로
- [X] T026 [P] [US3] `tests/unit/retrieval/test_expand.py`: `chunk_context`를 통합 상위 `expand_top`개 식별자로 정확히 한 번 부름, 반환에 없는 중심은 `Skipped(not_visible)`이고 Context에 없음(spec FR-012 다시 확인),
  반환 `index_version`이 검색 버전과 다르면 `index_version_changed`, `want_context=False`면 부르지 않음
- [X] T027 [P] [US3] `tests/localdb/retrieval/test_context.py`: spec US3 수용 시나리오 1~5를 로컬 DB로(문서 첫·마지막 청크, 같은 제목 경로 두 번, 출처 필드)
- [X] T028 [US3] `src/qello_knowledge/retrieval/pack.py`: 담은 청크 목록 → `ContextBlock` 목록(문서별 묶기, 정렬, gaps, 순위, Source ID). 담기 순서는 contracts/retrieval.md 4절 알고리즘의 역할 순서를 따르되 예산 검사는 T033에서
- [X] T029 [US3] `src/qello_knowledge/retrieval/service.py`: 8~10단계(`want_context`, `chunk_context` 한 번, 다시 확인, `pack` 호출)
- [X] T030 [US3] `tests/localdb/retrieval/test_visibility.py`에 spec US2 시나리오 2·3(비활성 버전 이웃 제외, 결과 뒤 내림된 문서는 Context에 없음과 `not_visible`)을 더하고 통과시킨다

**Checkpoint**: US1~US3 시험 통과. 순위 + 예산 없는 Context

---

## Phase 6: User Story 4 - Context를 정해진 토큰 예산 안에 담는다 (P1)

**Goal**: spec FR-016 담기 알고리즘(중심 먼저, 다음 문맥, 자르지 않음, 건너뛰기 기록).

**Independent Test**: 예상 토큰을 아는 합성 청크로 예산을 바꿔 가며 Context 합 ≤ 예산, 잘림 0, 중복 0, 담긴·건너뛴 청크가 기대값과 같다.

- [ ] T031 [P] [US4] `tests/unit/retrieval/test_pack.py`(spec SC-003): contracts/retrieval.md 4절 알고리즘 기대값 표. 중심 하나가 예산보다 크면 `larger_than_budget`이고 다음 중심 계속(spec US4 시나리오 3),
  남은 예산 부족이면 `budget_exhausted`로 그 청크만 건너뜀, 중심이 모두 담긴 뒤에야 문맥(상위 절 → 앞 가까운 것부터 → 뒤 가까운 것부터), 이미 담긴 청크 건너뜀,
  같은 청크는 `skipped`에 한 번만(처음 역할·사유), 뒤에 담기면 `skipped`에서 빠짐, 예상 토큰은 `ceil(UTF-8 바이트 ÷ 3.5)`, 같은 입력 같은 결과, 요약의 사용 토큰·예산
- [ ] T032 [P] [US4] `tests/unit/retrieval/test_pack_property.py`: 무작위 합성 청크(고정 시드 100개 경우)에서 합 ≤ 예산, 잘림 0, 중복 0, 담긴 중심의 순위가 담기지 않은 중심보다 항상 앞(예산이 허락하는 한)
- [ ] T033 [US4] `src/qello_knowledge/retrieval/pack.py`: `pack(hits, context, settings)`에 예산 알고리즘을 넣는다. 예상 토큰은 `embedding/estimate.py`와 같은 식 `ceil(UTF-8 바이트 ÷ bytes_per_token)`을
  `retrieval/pack.py`의 도우미 `estimated_tokens(text, bytes_per_token: float) -> int`로 둔다(`embedding/estimate.estimated_tokens`는 `ModelSpec`을 받으므로 그대로 쓰지 않는다)
- [ ] T034 [US4] `src/qello_knowledge/retrieval/service.py`: 요약의 `block_count`·`used_tokens`·`budget`·`skipped`를 채운다

**Checkpoint**: P1 스토리(US1~US4) 전부 통과. 생성(QK-GEN-001)이 쓸 수 있는 Context

---

## Phase 7: User Story 5 - 자연어 질문과 코드 식별자로도 키워드 검색이 맞는다 (P2)

**Goal**: 색인 쪽 규칙 선택(기준선 해시 불변), 식별자 분해 후보, 평가용 색인 준비 절차(spec FR-018~021, FR-029, SC-004·005·009·010).

**Independent Test**: 기준선 해시가 그대로이고, 규칙별 로컬 DB에서 식별자 원형·일부·문장형 질문의 상위 20건 포함 비율을 잰다. 평가용 DB를 캐시 복사로 만들 때 임베딩 호출 0.

- [ ] T035 [P] [US5] `tests/unit/chunking/test_keyword_rule_version.py`(spec SC-010, 기존 `test_version.py`는 바꾸지 않는다): `chunking_version(ChunkingSettings())`가 `"chk-md-20d966f730bb"`, `index_version_id("@cf/baai/bge-m3", 1024, 그 값)`이 `"iv-4c0bc4fcc642"`,
  `keyword_text_rule="kw-index-idsplit-v1"`이면 다른 값, 알 수 없는 규칙은 `ValueError`
- [ ] T036 [P] [US5] `tests/unit/chunking/test_keyword_text.py`: 기준선 `search_text`가 지금과 글자 하나 다르지 않음(기존 청커 시험 결과와 비교), 식별자 분해는 기준선 + 빈 줄 + camelCase·PascalCase·약어·숫자 경계로 나눈
  소문자 낱말(중복 없이 원문 순서, `HTTPClient` → `http client`, `retryPayment2` → `retry payment 2`), snake_case·kebab-case·경로는 덧붙이지 않음, 원형 유지, `embedding_text`는 두 규칙에서 같음(spec FR-019)
- [ ] T037 [US5] `src/qello_knowledge/domain/chunking.py`: `ChunkingSettings.keyword_text_rule: str = "kw-index-baseline-v1"`, 알 수 없는 값은 `ValueError`(`domain/keyword_rules.INDEX_RULES`)
- [ ] T038 [US5] `src/qello_knowledge/chunking/header.py`·`chunking/service.py`: `search_text(header, body, rule)`와 식별자 분해(research R-04). `src/qello_knowledge/chunking/version.py`: 규칙이 기준선이 아닐 때만
  재료에 `"keyword_text_rule"`을 넣는다. 기존 청커 시험이 그대로 통과해야 한다
- [ ] T039 [US5] `src/qello_knowledge/domain/keyword_rules.py`: 식별자 분해 인덱스 버전을 계산해 `INDEX_KEYWORD_RULES`에 더하고, `tests/unit/chunking/test_keyword_rule_version.py`에 "표의 모든 항목이 계산값과 같다" 시험을 더한다
  (research R-05)
- [ ] T040 [P] [US5] `tests/localdb/retrieval/test_keyword_rules.py`(spec SC-004·SC-005, US5 시나리오 1~6): 규칙마다 별도 `qk_test_*` 데이터베이스에 같은 합성 문서를 색인(가짜 임베딩)하고,
  `retrieval.keyword_query` → `PostgresStore.search_keyword_terms`를 직접 불러 키워드 순위를 본다(US6 방식 분기에 기대지 않는다).
  식별자 원형(camelCase·snake_case·kebab-case·URL 경로 각 5개 이상)은 두 규칙 모두, 식별자 일부는 식별자 분해에서 상위 20건 안 100%. 문장형 질문 10개 이상에서 `kw-query-v1` 90% 이상, `kw-query-raw` 비율도 출력.
  각 DB의 활성 인덱스 버전에 `index_rule_for`가 그 규칙을 돌려줌. 측정 조건(문서 수, 질문 수, 일치 확장 꺼짐)을 시험 출력에 남김
- [ ] T041 [P] [US5] `tests/unit/indexer/test_sync_cli_settings.py`: `indexer/sync_cli.py` 조립 함수가 `ChunkingSettings`를 인자로 받고, 인자 없이 부르면 지금과 같은 설정·현재 버전(기존 `qk-index run`·`index activate` 시험 그대로 통과)
- [ ] T042 [US5] `src/qello_knowledge/indexer/sync_cli.py`: 의존성 조립(`build_runtime`)과 활성화의 현재 버전 계산이 `ChunkingSettings` 인자를 받게 하고, 키워드 인자 두 개를 더한다.
  `targets_factory(configs, settings, clock) -> list[SyncTarget]`(기본은 지금 코드를 옮긴 함수: `github_repo_files`가 아닌 활성 자료원은 `unsupported_source_kind`로 거부하고 `GitHubRepoFilesAdapter`·`HttpsTransport`·
  `DefaultSourceSession`으로 대상을 만든다)와 `provider_factory(source, settings)`(기본 `WorkersAiRestProvider`). 종류 검사는 기본 `targets_factory` 안으로 옮기므로 인자 없이 부르면 동작이 같다(research R-09 6·7단계)
- [ ] T043 [P] [US5] `tests/localdb/devtools/test_eval_index.py`(spec FR-029, SC-009, research R-09): T044의 `targets_factory`로 가짜 대상(`tests/unit/sync/helpers.py`가 `SyncTarget(config.name, config.kind, config=…, adapter=FakeSourceAdapter, session=…)`을
  만드는 방식과 같은 가짜 어댑터·시험용 세션, 네트워크 없음)을, `provider_factory`로 `embedding/fake.py` 제공자를 넣고,
  합성 커밋 SHA(`"0" * 39 + "1"` 등 시험 전용 값)를 써서 H02 이름과 겹치지 않게 하며, 픽스처 정리 단계에서 그 시험이 만든 `qk_eval_*` 최종·준비용 DB를 지운다. 확인 내용: (1) 원본 DB의 임베딩을 복사한 평가용 DB에서 식별자 분해 동기화 임베딩 호출 0·원본 쓰기 0,
  (2) 최종 이름이 있으면 종료 코드 5, (3) `__preparing` 잔여물이 있으면 다시 만들고 성공, (4) 캐시로 처리되지 않는 문서가 있으면 예상 Neurons를 출력하고 종료 코드 4, `--allow-embed`면 진행,
  (5) 저장소의 `config/sources.toml`과 범위 검토 파일이 실행 전후 같음, (6) 짧은 SHA·브랜치 이름 거부, (7) 성공 출력에 이름·규칙·커밋·인덱스 버전·복사 벡터 수·임베딩 호출 수, (8) 지우는 대상이 `qk_eval_*__preparing`뿐
- [ ] T044 [US5] `src/qello_knowledge/devtools/eval_index.py`와 `devtools/db.py`의 `eval-index prepare` 하위 명령: research R-09 1~8단계(로컬 컨테이너 주소로 대상 접속, 원본은 읽기 전용 트랜잭션, 임시 사본의 `ref`만 SHA,
  `load_checked_sources`, 미리 보기 게이트, 동기화, 같은 설정의 활성화, 연결을 모두 닫은 뒤 이름 변경). 종료 코드는 contracts/cli.md 2절.
  `prepare(..., targets_factory=None, provider_factory=None)`로 시험이 가짜를 넣을 수 있게 하고, 명령행에서는 T042의 기본값을 쓴다
- [ ] T045 [US5] research R-04·R-11의 ADR-010 후보·비교 기준이 구현(T036 기대값)과 맞는지 확인하고 결과를 이 파일 "실행 기록"에 적는다. 어긋나면 research를 고치지 않고 멈춰 사람 확인을 받는다.
  ADR 파일은 만들지 않는다(TASK.md 제외 범위)

**Checkpoint**: US5 시험 통과, 기준선 `chk-md-20d966f730bb`·`iv-4c0bc4fcc642` 불변

---

## Phase 8: User Story 6 - 평가를 위해 검색 방식별 결과를 따로 받는다 (P2)

**Goal**: 방식 선택, 순위만 받기, 실패 매핑과 하이브리드 축소, 외부 호출 계산, 요약 조건(spec FR-009~011, FR-022~024, FR-026, SC-007·008·011).

**Independent Test**: 같은 질문을 세 방식으로 돌려 각 결과가 해당 검색 순위와 같고, 실패 주입에서 하이브리드는 축소·사유 기록, 단일 방식은 실패, 외부 호출 ≤ 7.

- [ ] T046 [P] [US6] `tests/unit/retrieval/test_modes.py`(spec US6 시나리오 1~4): 벡터 전용은 키워드 저장소 호출 0, 키워드 전용은 임베딩 호출 0(사용량 0), 결과가 각 검색 순위와 같음, 요약에 방식·후보 수·RRF·질의 규칙·
  `index_rule`·인덱스 버전·예산·`vector_count`·`keyword_count`·`keyword_terms`(수만)·`embedding`, `want_context=False`면 `chunk_context` 호출 0
- [ ] T047 [P] [US6] `tests/unit/retrieval/test_degrade.py`(spec SC-008·SC-011, FR-009, research R-14 표 전 행): 빈 질문·길이 초과는 외부 호출 0, 임베딩 `secret_blocked`·일시 실패·할당 소진·`EmbedError`, 벡터 검색 `StoreError`,
  키워드 검색 `StoreError`, 어느 단계든 `StoreUnavailable`(축소 없이 `store_unavailable`), 벡터 쪽 생략 + 낱말 0개, 양쪽 생략, 주변 조회 `StoreError`. 하이브리드는 `omitted`에 사유, 단일 방식은 실패(벡터 전용 벡터 검색 오류는
  `store_unavailable`). 모든 경우 요약·예외 문구·사용량 기록에 질문·낱말이 없음
- [ ] T048 [P] [US6] `tests/unit/retrieval/test_calls.py`(spec SC-007, SC-009 일부): 확장 상위 1·8·20, 임베딩 일시 실패 뒤 재시도 성공 경로에서 `external_calls` ≤ 7이고 실제 가짜 호출 수와 같음(임베딩 시도마다 사용량 기록 1),
  `EmbedError(AUTH_CONFIG)` 경로에서 임베딩 몫을 최대치 4로 셈,
  키워드 전용 임베딩 0, 버전 바뀜 경로 다시 검색 0
- [ ] T049 [US6] `src/qello_knowledge/retrieval/service.py`: 방식 분기, research R-14 순서대로 예외 잡기(`StoreUnavailable` → `StoreError` → `EmbedError`), 하이브리드 축소와 `omitted`, 단일 방식 실패, `external_calls`
  (저장소 호출은 서비스가 직접 세고, 임베딩은 `RunSummary`의 호출 수 × 2(호출 + 사용량 기록)로 센다. `EmbedError`로 `RunSummary`를 받지 못하면 시도 상한(재시도 포함 2) 기준의 최대치 4로 센다.
  보수적으로 크게 세는 값이라 상한 검사(SC-007)는 그대로 성립하고, 요약에 따로 표시하지 않는다(data-model 변경 없음)

**Checkpoint**: US1~US6 시험 통과

---

## Phase 9: User Story 7 - 운영 담당자가 명령으로 검색 결과를 확인한다 (P3)

**Goal**: `qk-index search`(spec FR-025, contracts/cli.md 1절, research R-07·R-10).

**Independent Test**: 로컬 DB에서 표준 입력 질문으로 순위·출처·요약이 나오고 질문은 출력·명령행·기록에 없다. 활성 인덱스가 없으면 종료 코드 1.

TDD 순서: T050과 T052(시험)를 먼저 쓰고 실패를 확인한 뒤 T051을 구현한다.

- [ ] T050 [P] [US7] `tests/unit/indexer/test_search_cli.py`: 질문을 표준 입력에서만 읽음(명령행 인자 질문 옵션 없음), 출력·`--json`에 질문·낱말·본문 없음, 첫 줄 `target=local|remote …`, 원격 대상인데 `--allow-remote` 없으면 3,
  실패 종류면 1, 인자·설정 오류 2, 성공·`no_results` 0, `--candidates`·`--budget`·`--expand-top`·`--source-kind`·`--mode`·`--query-rule`·`--ranks-only` 전달과 범위 밖 값 2, `--sources`·`--exceptions`로 `load_policy` 조립, 출처 없는 전송 검사, `source_revisions` 출력, 질의 임베딩 재시도 1회와 대기 `min(Retry-After 또는 0.5초, 2초)`
- [ ] T051 [US7] `src/qello_knowledge/indexer/search_cli.py`: 조립(research R-07: `EmbeddingService(retry_policy=RetryPolicy(max_retries=1), retry_delay=…)`, `indexer/embedding.py`의 `security_outgoing_check`),
  `QK_RETRIEVAL_CONTEXT_BUDGET`을 `RetrievalSettings.context_budget`에 연결, 표준 입력 읽기, `PostgresStore.source_revisions()`로 요약 채우기, 사람용·JSON 출력, 종료 코드.
  시험용 주입 인자(`store_factory`, `provider_factory`, `ledger_factory`, `indexer/cli.py`의 기존 factory 키워드 인자 방식)를 둔다. `src/qello_knowledge/indexer/cli.py`에 `search` 하위 명령 등록(기존 하위 명령 그대로)
- [ ] T052 [P] [US7] `tests/localdb/retrieval/test_search_command.py`: 로컬 DB에 합성 색인을 넣고 명령을 실행해 spec US7 시나리오 1~3(사용량 기록에 질의용 1건·원문 없음)

**Checkpoint**: 모든 스토리 시험 통과

---

## Phase 10: Polish & Cross-Cutting

- [ ] T053 `src/qello_knowledge/devtools/bench.py`와 `devtools/db.py`에 `qk-dev store bench --retrieval`을 더한다(research R-13, spec SC-006, quickstart 1절. 시험 마커는 만들지 않는다): 합성 1.1 MB를 넣은 로컬 DB에서 질문 50개 × 5회로 하이브리드 검색 + Context(가짜 임베딩) p50·p95, 순수 처리(규칙·RRF·담기)
  질의당 p95를 따로 출력. 결과와 조건(데이터 규모, 반복, 실행 환경)을 이 파일 "실행 기록"에 적는다. p95 1.5초를 넘거나 순수 처리 p95가 5 ms를 넘으면 사람에게 보고한다
- [ ] T054 경계·회귀 확인: `uv run pytest tests/unit/test_boundaries.py`, 기존 QK-STO-001·QK-CHK-002·QK-SYN-001·QK-EMB-001 시험 전부 통과, `uv run qk-migrate` 두 번
- [ ] T055 quickstart.md 1절 전체 실행(`python scripts/preflight.py`, `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run qk-dev db up`, `uv run qk-migrate` × 2, `QK_REQUIRE_LOCALDB=1 uv run pytest`)과 2절 로컬 손 확인.
  결과를 "실행 기록"에 적고 이 목록 체크 표시를 갱신한다
- [ ] T056 `TASK.md` Decisions·검증 기록 갱신, `/pr-draft-summary`로 PR 초안(CLAUDE.md 의무 사용)

---

## 사람 단계

| 단계 | 내용 | 상태 | 비용·허락 |
| --- | --- | --- | --- |
| H01 | research R-08 측정(생성 토크나이저 비율, 예산 초과 청크 수) | 2026-10-22 완료(예산 2,000 유지) | 저장소 복제·토크나이저 내려받기 허락 받음. Workers AI 0 |
| H02 | `uv run qk-dev eval-index prepare --rule kw-index-baseline-v1 --commit <SHA>`와 `--rule kw-index-idsplit-v1 --commit <같은 SHA>`로 평가용 DB 두 개를 만든다. 결과(이름·인덱스 버전·임베딩 호출 수)를 기록하고 QK-EVL-001에 넘긴다 | 구현 뒤 | GitHub 읽기. 예상 0 Neurons(0이 아니면 멈춤, 사람 확인) |
| H03 | 색인된 DB(로컬 또는 운영)에 `qk-index search`로 질문 몇 개(합성 또는 개인 정보 없는 질문)를 확인한다. 원격이면 `--allow-remote` | 구현 뒤 | 질의용 임베딩 질문당 1 Neurons 미만 |

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1 → US2 → US3 → US4. US5는 Phase 2 뒤 시작할 수 있다(T035~T039는 청커만, T040은 T020 `keyword_query`와 T012 저장소만 필요, T041~T044는 독립). T011의 `test_measure.py` 갱신은 T037 뒤. US6은 US1~US4 뒤. US7은 US6 뒤. Polish는 마지막.
- 같은 파일을 고치는 작업(`retrieval/service.py`: T021 → T024 → T029 → T034 → T049, `retrieval/pack.py`: T028 → T033)은 순서대로 한다.
- 사람 단계 H02는 T044 뒤, H03은 T051 뒤.

## Parallel Example

```text
Phase 2: T003, T004, T006, T008, T009, T014 (시험·독립 파일) / T013은 T007 뒤
US1:     T015, T016, T017, T018 (시험) → T019, T020 (구현) → T021
US7:     T050, T052 (시험) → T051
US5:     T035, T036, T040, T041, T043 (시험) → T037 → T038 → T039 / T042 → T044
US6:     T046, T047, T048 (시험) → T049
```

## Implementation Strategy

1. MVP: Phase 1·2 + US1(순위만). 여기서 멈춰도 평가(QK-EVL-001)의 순위 비교를 시작할 수 있다.
2. US2~US4로 생성(QK-GEN-001)이 쓸 Context를 완성한다.
3. US5로 ADR-010 후보와 평가용 색인을, US6으로 방식별 비교와 실패 처리를, US7로 확인 명령을 더한다.
4. 스토리마다 시험 → 구현 → 체크포인트 → 커밋(`/harness-commit`).

## 실행 기록

- 2026-10-22 T024: US1의 `service.py`가 이미 버전 판정(다시 검색 없음)과 저장소 결과만 쓰는 구조여서 코드 변경 없이 T022·T023이 통과했다.
- 2026-10-22 T028: `retrieval/pack.py`를 contracts/retrieval.md 4절 알고리즘 전체(예산 검사 포함)로 한 번에 구현했다. US3 시험은 넉넉한 예산(8,000)으로 돌리고, 예산 동작은 US4 시험(T031·T032)이 확인한다. T033은 그 시험 통과 확인만 남는다.
