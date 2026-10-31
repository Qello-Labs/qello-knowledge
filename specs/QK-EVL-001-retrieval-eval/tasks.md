---
description: "QK-EVL-001 구현 작업 목록"
---

# Tasks: QK-EVL-001 골든셋 형식 검증, 검색 평가 실행기, 비교 리포트

**Input**: `specs/QK-EVL-001-retrieval-eval/`의 plan.md, spec.md, research.md(R-01~R-15), data-model.md, contracts/question-set.md, contracts/run-record.md, contracts/cli.md, quickstart.md

**Tests**: 포함한다. spec SC-001~SC-010과 C-12가 자동 시험을 요구한다. 시험을 먼저 쓰고 실패를 확인한 뒤 구현한다. 모든 자동 시험은 외부 호출 0건이다(가짜 임베딩 제공자
`embedding/fake.py`, 가짜 `EvalTarget`·`DayUsageReader`, `tests/unit/retrieval/fakes.py`의 `FakeRetrievalStore`, 로컬 DB). Workers AI·GitHub·운영 장부는 맨 끝 "사람 단계"다.

**Organization**: 사용자 스토리별 단계. US1 → US2(모두 P1, US2의 세트 파일은 별도 커밋) → US3(P1) → US4 → US5(P2). US5는 문서 작업이고 사람 단계 뒤에 한다.

**선행 조건**: spec.md·plan.md 사람 승인(2026-10-31), 이 목록의 사람 승인, `TASK.md` Scope를 아래 "TASK.md Scope 갱신안"대로 고치기(AGENTS.md 1절).

**공통 규칙**:
- 질문 문장, 핵심 사실, 라벨 근거 낱말, 검색어 낱말, 청크 본문, 비밀값, 접속 정보를 로그·예외 문구·`repr`·출력·실행 기록에 넣지 않는다(spec FR-006·FR-019, contracts/cli.md 머리말).
  예외는 `qk-dev eval identifiers`가 내는 식별자 하나와 문서 위치뿐이다(contracts/cli.md 4절). 시험은 이 규칙을 문자열 검사로 확인한다.
- 시험용 질문 세트는 `tests/fixtures/evaluation/question_sets/` 아래 합성 세트만 쓴다. 질문 문장은 문서 위치·자료원 이름·질문 ID와 겹치는 문자열을 담지 않게 만든다(SC-008).
  대상 저장소 원문을 시험에 복사하지 않는다(AGENTS.md 6절).
- 바꾸지 않는 것: `src/qello_knowledge/retrieval/`, `src/qello_knowledge/embedding/`, `adapters/postgres/migrations/`, `domain/retrieval.py`의 `RetrievalSettings` 기본값, `domain/keyword_rules.py`,
  기존 `adapters/postgres/*.py` 파일, QK-RET-001 문서(plan.md "구현 Scope 승인이 필요한 것"). 기존 시험 파일과 기대값은 고치지 않는다. 예외는 T002의 `tests/unit/test_boundaries.py`에 검사를 더하는 것뿐이다.
- 새 시험 파일 이름은 `tests/` 전체에서 겹치지 않게 한다(시험 디렉터리에 `__init__.py`가 없어 같은 이름이면 pytest 수집이 실패한다). 그래서 quickstart.md 1절의 로컬 DB 시험 이름을
  `test_eval_target.py`·`test_eval_run.py`·`test_day_usage_reader.py`로 고쳤다(`test_prechecks.py`가 단위 시험과 겹쳤다).
- `evaluation/`은 표준 라이브러리와 `qello_knowledge.domain`·`ports`·`embedding`·`retrieval`·`evaluation`만 가져온다(T002 경계 검사). `psycopg`·`adapters`·`devtools`·`security`·`indexer`는 가져오지 않는다.
  저장소 읽기는 `ports/evaluation.py`, 검색은 `retrieval.retrieve`, 임베딩은 `ports/embedder.py`의 `Embedder`만 거친다.
- 로컬 DB 시험은 `tests/localdb/` 아래에 둔다. 평가 대상 데이터베이스는 시험 함수마다 새로 만들고 끝나면 지운다(T001). 한 시험이 색인을 지우거나 활성 버전을 없애도 다른 시험에 남지 않게 하려는 것이다.
  시험이 만든 이름만 지운다. 사람 단계의 이름(`qk_eval_baseline_6aeccd039b82` 등)과 공유 `postgres` 데이터베이스는 건드리지 않는다.

**TDD 순서**: 각 단계에서 시험 작업을 먼저 쓰고 실패(아직 없는 모듈이면 수집 오류 포함)를 확인한 뒤 구현 작업을 한다. [P]는 같은 단계의 시험끼리, 구현끼리 병렬이라는 뜻이다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 다루고 미완료 작업에 기대지 않아 병렬로 할 수 있다
- **[Story]**: 해당 사용자 스토리(US1~US5)

---

## Phase 1: Setup

- [X] T001 자리 만들기: `src/qello_knowledge/evaluation/__init__.py`, `tests/unit/evaluation/`, `tests/localdb/evaluation/conftest.py`, `tests/fixtures/evaluation/question_sets/`. 시험 디렉터리에는 `__init__.py`를 만들지 않는다.
  conftest의 평가 대상은 손으로 행을 넣지 않고 실제 동기화 경로로 만든다. 기존 `tests/localdb/store/builders.py`는 인덱스 버전이 `v1`이라(18행) `index_rule_unknown`으로 거부되고,
  `PostgresStore.upsert_artifact`는 `qk.artifact.source_name`·`location`을 채우지 않으며(`adapters/postgres/store.py:214-232`), `record_run`은 `finished_at`을 넣지 않아서다.
  - `tests/localdb/devtools/test_eval_index.py`의 `origin` 픽스처와 `_prepare`·`_targets_factory`·`SHA`·`DOCS`를 가져와 쓴다. 그 파일은 고치지 않는다
  - 함수 범위 픽스처 `baseline_target`: `_prepare(origin, rule=INDEX_BASELINE)`로 `qk_eval_baseline_<SHA 12자>`를 만든다. 인덱스 버전 `iv-4c0bc4fcc642`, bge-m3·1024차원, `qk.sync_source`, `source_name`·`location`, 동기화 `finished_at`이 실제 경로로 채워진다
  - `idsplit_target`도 같은 방식으로 `INDEX_IDSPLIT`
  - 문서를 바꿔야 하는 시험은 `_prepare(…, targets_factory=_targets_factory(docs), allow_embed=True)`를 쓴다. 가짜 제공자라 외부 호출이 없다
  - 픽스처는 끝날 때 열었던 연결을 모두 닫는다. `origin` 픽스처가 시험 앞뒤로 시험 SHA가 붙은 `qk_eval_*`만 지운다
- [X] T002 [P] `tests/unit/test_boundaries.py`: 기존 검사는 그대로 두고 `EVALUATION_ALLOWED = (*ALLOWED_INTERNAL, "qello_knowledge.retrieval", "qello_knowledge.evaluation")`와 `evaluation_violations(root)`를 더한다(retrieval 검사와 같은 방식).
  위반 사례 시험: `evaluation/`이 `qello_knowledge.adapters`·`devtools`·`security`·`indexer`·`psycopg`를 가져오면 실패, `domain`·`ports`·`retrieval`이 `qello_knowledge.evaluation`을 가져오면 실패(research R-01, plan Constitution Check C-06)

---

## Phase 2: Foundational

**목적**: 모든 스토리가 쓰는 평가 대상 경계와 PostgreSQL 구현, 단위 시험용 가짜. 이 단계가 끝나야 스토리 시험을 쓸 수 있다.

- [X] T003 `src/qello_knowledge/ports/evaluation.py`: data-model 2절을 표준 라이브러리 불변 dataclass와 `Protocol`로 정의한다.
  `TargetDescription`(`database`, `index_version`, `embedding_model`, `dimension`, `index_rule`, `tokenizer`(읽지 못하면 `None`), `commits`(자료원 이름 → 원본 리비전), `synced_at`, `sources`),
  `TargetDocument`(`source`(`qk.artifact.source_name`), `location`(`qk.artifact.location`), `source_url`), `EvalTarget`(`describe() -> TargetDescription`, `documents() -> tuple[TargetDocument, ...]`, `store: RetrievalStore`),
  `DayUsageReader`(`today() -> AnswerUsageToday`, "읽기 전용, 쓰기 메서드 없음"). 활성 인덱스 버전이 없으면 `index_version`·`embedding_model`·`dimension`은 `None`이다. `AnswerUsageToday`는 `domain/generation.py`의 기존 타입을 쓴다.
  경계 예외 `TargetUnavailable`(대상 연결·읽기 실패)과 `LedgerUnavailable`(장부 읽기 실패)도 여기 둔다. `evaluation/`은 `adapters`의 `GenerationUsageUnavailable`·`StoreUnavailable`을 가져올 수 없어서다
- [X] T004 [P] `tests/unit/evaluation/fakes.py`(시험 도우미, 수집 대상 아님): `FakeEvalTarget(description, documents, store)`(`store`는 `tests.unit.retrieval.fakes.FakeRetrievalStore`), 읽은 횟수를 세는 `FakeDayUsageReader(usage | 예외)`,
  `question_set_file(tmp_path, set_id, version, text)` 도우미(contracts/question-set.md 1절 위치 규칙대로 `<set_id>/v<version>.toml`을 만든다)
- [X] T005 [P] `tests/localdb/evaluation/test_eval_target.py`(research R-04·R-05): T001 `baseline_target`(시험마다 새로 만든다)에서
  - `describe()`가 활성 인덱스 버전·임베딩 모델·차원, `domain/keyword_rules.index_rule_for`의 값, `pg_class.reloptions`에서 읽은 `qk.chunk_search_text_pgroonga`의 `tokenizer=` 값(새 마이그레이션이면 `TokenBigramSplitSymbol`),
    `PostgresStore.source_revisions()`와 같은 고정 커밋, 그 동기화 실행의 `finished_at`, `qk.sync_source` 자료원 이름 목록을 돌려준다
  - 시험 안에서 색인을 지우면 `tokenizer`가 `None`, 활성 인덱스 버전이 없으면 `index_version`이 `None`
  - `documents()`가 활성 인덱스 버전에서 `qk.is_visible`을 통과한 청크가 하나 이상인 문서만 `(source_name, location, source_url)`로 돌려준다(숨김 문서·청크 없는 문서 제외)
  - 모든 읽기가 읽기 전용 트랜잭션이다(같은 연결로 쓰기를 시도하면 읽기 전용 오류). 실행 전후 `qk.embedding_usage`·`qk.chunk` 행 수가 같다
  - 이름이 `qk_eval_`로 시작하지 않으면 만들 때 거부하고, 환경에 `DATABASE_URL`이 다른 데이터베이스를 가리켜도 쓰지 않는다
- [X] T006 [P] `tests/localdb/evaluation/test_day_usage_reader.py`(research R-07, quickstart 1절 "장부 읽기 전용"): 시험용 데이터베이스에서 `PostgresDayUsageReader.today()`가 `qk.generation_usage_today(query_reserve)`를 한 번 불러
  `day_total`을 담은 `AnswerUsageToday`를 돌려주고, 그 연결로 쓰기를 시도하면 읽기 전용 오류, 실행 전후 장부 행 수가 같다. 연결 실패는 `LedgerUnavailable`(T003)로 알린다. 실행 명령의 관문은 로컬 장부를 거부하므로 이 시험은 구현만 직접 부른다
- [X] T007 `src/qello_knowledge/adapters/postgres/eval_target.py`(새 파일, 기존 어댑터 파일은 고치지 않음):
  - `eval_target_url(dbname, source_env)`: `database_url({k: v for k in ("QK_LOCAL_DB_PORT",)})`와 `with_database`로 로컬 컨테이너 주소만 만든다(`devtools/eval_index.py`의 `admin` 조립과 같은 방식). `DATABASE_URL`은 읽지 않는다. 이름이 `qk_eval_`로 시작하지 않으면 `ValueError`
  - `PostgresEvalTarget(dbname, source_env)`: `describe()`, `documents()`(T005 기준), `store`(같은 주소의 `PostgresStore`), `visible_chunk_texts()`(활성 인덱스 버전의 노출 청크를 `(source_name, location, body)`로 내는 반복자. `eval identifiers`만 쓰고 `EvalTarget` 경계에는 넣지 않는다), `close()`.
    연결 실패는 `TargetUnavailable`로 바꿔 올린다
  - `PostgresDayUsageReader(url, query_reserve)`: `connect(url, autocommit=False)`로 연 연결에 `read_only = True`를 걸고(autocommit 연결에서는 psycopg가 트랜잭션을 열지 않아 `read_only`가 걸리지 않는다, `connection.py:52`)
    `SELECT qk.generation_usage_today(%s)` 한 번을 부른 뒤 롤백한다. 결과는 기존 `adapters/postgres/generation_usage.answer_usage`로 읽는다. 쓰기 메서드를 두지 않고, 연결·읽기 실패는 `LedgerUnavailable`로 바꾼다
  - `describe()`·`documents()`도 같은 방식(`autocommit=False` + `read_only = True`)으로 읽는다

**Checkpoint**: T005·T006 통과, `tests/unit/test_boundaries.py` 통과

---

## Phase 3: User Story 1 - 평가 전에 질문 세트 파일을 검사한다 (P1) 🎯 MVP

**Goal**: 질문 세트 파일 형식과 검증 규칙(spec FR-001~FR-007, contracts/question-set.md, research R-02·R-03), `qk-dev eval check`(contracts/cli.md 1절).

**Independent Test**: 올바른 합성 세트는 통과하고, 규칙마다 그 규칙 하나만 어긴 세트는 그 규칙 이름으로 거부된다. 출력에 질문 문장·핵심 사실·라벨 근거 낱말이 없다. DB·외부 호출 없이 돈다(SC-001).

- [X] T008 [P] [US1] `tests/unit/evaluation/test_question_set.py`(SC-001):
  - contracts/question-set.md 4절 19개 규칙(`toml_invalid`, `unknown_field`, `required_missing`, `bad_format`, `set_path_mismatch`, `confirmed_date`, `source_duplicate`, `question_id_duplicate`, `bad_enum`, `text_empty`,
    `text_too_long`, `text_secret`, `evidence_unknown_source`, `evidence_bad_location`, `evidence_duplicate`, `evidence_required`, `evidence_forbidden`, `form_mixed`, `form_fields`)마다 그 규칙 하나만 어긴 파일이 1개 이상이고 그 규칙 이름으로만 거부된다.
    시험이 규칙 목록을 상수로 두고 사례가 빠진 규칙이 있으면 실패한다
  - 올바른 골든형 세트와 식별자형 세트가 통과하고 질문 수, 유형별, 라벨 상태별, 미완료 수가 맞다. 지문은 파일 바이트의 SHA-256(소문자 16진수 64자)이다
  - 한 파일의 여러 오류가 한 번에 모두 `(질문 ID, 필드, 규칙 이름)`으로 나온다(머리 정보 오류는 질문 ID `None`)
  - `confirmed = true`인데 `confirmed_on`이 없거나 `confirmed = false`인데 있으면 `confirmed_date`다(`required_missing`으로 세지 않는다)
  - 유형 `unknown` → `bad_enum`. `label = "pending"`인 질문은 통과하고 미완료 수에 들어간다. `text`는 앞뒤 공백을 뺀 길이 1~2,000자(`RetrievalSettings().question_max_chars`), 2,001자 → `text_too_long`
  - 식별자형: `query_form`이 `original`·`partial`이면 `identifier_form`과 `label_terms`(정확히 1개)가 있어야 하고, `sentence`면 `identifier_form`이 없고 `label_terms`가 1개 이상이어야 한다. 어기면 `form_fields`(research R-03, spec FR-002 정정)
  - `text_secret`은 `tests/unit/synthetic_secrets.py`의 합성 비밀값으로 만든다. 거부 출력과 `SetIssue`·`Question`·`QuestionSet`의 `repr`에 그 값, 질문 문장, `facts`, `label_terms` 문자열이 0번 나온다
- [X] T009 [P] [US1] `tests/unit/evaluation/test_set_warnings.py`(spec US1-7, FR-007, contracts/question-set.md 5절): `FakeEvalTarget.documents()`를 주면 근거 문서가 하나도 없는 질문은 `evidence_unindexed`,
  일부만 없는 질문은 `evidence_partly_unindexed`가 질문 ID와 빠진 근거 위치로 나오고 `ok`는 바뀌지 않는다. `no_answer` 질문은 경고하지 않는다
- [X] T010 [US1] `src/qello_knowledge/evaluation/question_set.py`(data-model 1절, contracts/question-set.md 1~5절):
  - 열거값 `QuestionType`(`code`, `doc`, `meeting`, `synthesis`, `no_answer`), `LabelStatus`(`done`, `pending`), `QuestionOrigin`(`team`, `synthetic`), `IdentifierForm`(`camel`, `pascal`, `acronym`, `digit`, `snake`, `kebab`, `url_path`), `QueryForm`(`original`, `partial`, `sentence`)
  - 불변 dataclass `SourceLabel`(`name`, `label_commit`), `Evidence`(`source`, `location`), `Question`(`text`·`facts`·`label_terms`는 `field(repr=False)`), `QuestionSet`, `SetIssue`, `SetCheck`, `Question.is_metric_target`("`label == done` 이고 `type != no_answer`")
  - `check_question_set(path, documents=None) -> tuple[QuestionSet | None, SetCheck]`: `tomllib`로 읽고(같은 키 두 번은 `toml_invalid`), 모든 오류를 모은다. 형식은 contracts 2·3절 그대로다:
    세트 ID `^[a-z0-9]+(-[a-z0-9]+)*$`, 질문 ID `^[A-Za-z0-9_-]{1,40}$`, `label_commit` 40자 소문자 16진수, `version` 정수 ≥ 1, `created`·`confirmed_on`은 TOML 날짜, 파일 위치의 `<세트 ID>/v<버전>.toml`과 머리 정보 일치,
    `confirmed = true`일 때만 `confirmed_on`, 근거 위치는 비지 않고 `/`로 시작하지 않으며 `://`·`\`·`..` 경로 조각이 없음, 비밀값은 `domain/secret_rules.find_secrets(text)`로 질문 문장만 본다(예외 목록 적용 안 함)
  - 출력용 요약 함수는 `SetIssue`·수·경고만 담는다
- [X] T011 [P] [US1] `tests/unit/devtools/test_eval_cli.py`의 `check` 절(contracts/cli.md 1절): 통과 0(경고가 있어도 0), 형식 오류 1, 인자 오류·파일 없음 2, `--target` 이름이 `qk_eval_`로 시작하지 않으면 2,
  `--json`은 한 줄 JSON, 사람용·JSON 출력 모두 질문 문장·`facts`·`label_terms` 0번. 대상은 주입한 `target_factory`로 받아 DB에 연결하지 않는다
- [X] T012 [US1] `src/qello_knowledge/devtools/eval_cli.py`(새 파일)에 `run_check(args, *, target_factory=None, out)`과 `src/qello_knowledge/devtools/db.py`에 `eval` 묶음(`qk-dev eval check <파일> [--target DB] [--json] [--env-file]`)을 등록한다.
  `target_factory`가 `None`이면 함수 안에서 `adapters.postgres.eval_target`을 가져온다. `adapters/postgres/connection.py`가 `devtools.db`를 가져오므로(10행) `eval_cli.py`가 맨 위에서 `adapters`를 가져오면 순환 가져오기가 생긴다.
  `db.py`도 `eval_cli`를 `eval` 분기 안에서만 가져온다(`eval-index`의 기존 방식). 기존 `db`·`store`·`eval-index`·`source` 하위 명령과 인자는 그대로 둔다.
  `check`의 대상 이름 오류·연결 실패는 contracts/cli.md 1절대로 종료 2다(`run`의 1과 다른 것은 계약 그대로다)

**Checkpoint**: US1 시험 통과. 여기까지가 MVP(질문 세트 형식이 서면 QK-STO-002·QK-EVL-002가 형식을 쓸 수 있다)

---

## Phase 4: User Story 2 - 첫 질문 세트 두 개를 형식에 맞춰 만든다 (P1)

**Goal**: 식별자 세트 만들기 도우미(research R-13, contracts/cli.md 4절)와 골든 세트 v1·식별자 세트 v1 파일(spec FR-008~FR-010).

**Independent Test**: 골든 세트 v1이 H05 v2 표와 11문항 모두에서 같고(SC-002), 두 세트가 US1 검증을 통과한다. 도우미가 합성 문서에서 형태별 식별자와 문서 위치를 내고 본문 문장은 내지 않는다.

코드(T013~T016)는 시험 → 구현 순서. 세트 파일(T017·T018)은 평가 코드와 다른 커밋이다(spec US2-6, FR-010, AGENTS.md 3.4). T018은 사람 단계 H01 뒤에만 할 수 있다.

- [X] T013 [P] [US2] `tests/unit/evaluation/test_labeling.py`(research R-13):
  - 형태 판별: camelCase(`retryPayment`), PascalCase(`RetryPolicy`), 약어 경계(`HTTPClient`), 숫자 경계(`oauth2Token`), snake_case(`max_retries`), kebab-case(`kw-index-baseline-v1`), URL 경로(`/api/v1/users`, 호스트가 붙으면 후보 아님)
  - 일부 낱말 나누기(`retryPayment` → `retry`, `payment`), 형태별 후보 `(식별자, 문서 수, 문서 위치 목록)`
  - 근거 다시 계산: `original`·`partial`은 `label_terms[0]`의 대소문자 구별 부분 문자열이 노출 청크 본문에 있는 문서 전부, `sentence`는 모든 `label_terms`를 대소문자 무시로 포함하는 문서 전부(한 문서의 노출 청크를 합쳐 본다)
  - 비밀값 규칙(`find_secrets`)에 걸린 후보는 결과에서 빠지고 뺀 수만 남는다. 결과 객체의 `repr`에 본문 문장이 없다
- [X] T014 [US2] `src/qello_knowledge/evaluation/labeling.py`: `(source, location, body)` 반복자를 받는 순수 함수 `identifier_candidates(chunks, forms)`와 `recompute_evidence(question_set, chunks)`.
  형태 정규식은 한 곳에 상수로 둔다. 흔한 일부 낱말 제외(두 글자 이하, 문서 절반 이상에 나옴 등)는 코드가 아니라 `labeling.md`에 적고 사람이 적용한다(research R-13)
- [X] T015 [P] [US2] `tests/localdb/evaluation/test_identifiers_command.py`(contracts/cli.md 4절): T001 방식으로 형태별 식별자를 담은 합성 문서(`_targets_factory(docs)`, `allow_embed=True`)의 후보 A 대상을 만들고 `qk-dev eval identifiers --target`을 실행한다.
  출력에 대상 고정 커밋, 형태별 식별자·문서 수·문서 위치, 비밀값 규칙으로 뺀 수가 있고 본문 문장·줄은 없다. `--set`이 대상 고정 커밋과 다른 라벨 기준 커밋이면 1, 근거 문서가 다른 질문이 있으면 1과 그 질문 ID·(빠진 위치, 더 있는 위치),
  모두 같으면 0. 출력에 질문 문장과 `label_terms` 값이 없다. 인자 오류·대상 연결 실패 2
- [X] T016 [US2] `src/qello_knowledge/devtools/eval_cli.py`에 `run_identifiers`, `devtools/db.py`의 `eval` 묶음에 `identifiers`(`--target` 필수, `--set`, `--form` 여러 번)를 더한다. 본문은 `PostgresEvalTarget.visible_chunk_texts()`로 읽는다
- [ ] T017 [US2] 골든 세트(별도 커밋, research R-14 2번):
  - `eval/question_sets/qk-evl-001-golden/v1.toml`: spec FR-008 그대로. 세트 ID `qk-evl-001-golden`, `origin = { id = "qk-bot-001-h05", version = 2, document = "specs/QK-BOT-001-discord-ask/measurement/h05-question-set-v2.md" }`,
    자료원 `dnd-backend-docs`와 `label_commit = "6aeccd039b825dcd7a2b6c046a34ef72089a1f78"`, 질문 Q01~Q11(`id`와 `original_number`가 원본 번호), 질문 문장·근거 문서·핵심 사실 글자 그대로, "있음"은 `doc`, "없음"은 `no_answer`(근거 빈 배열),
    `label = "done"`, `origin = "synthetic"`, `confirmed = false`. "나만 보기"와 답변 판정 기준은 옮기지 않는다
  - `eval/question_sets/qk-evl-001-golden/labeling.md`: 라벨 기준(H05 v2 "v1과 바뀐 점"·판정 기준을 가리키고 옮기지 않은 항목과 이유), Recall@5 정의(spec Assumptions)
  - `tests/unit/evaluation/test_golden_v1.py`(SC-002): H05 v2 Markdown 표를 읽어 11문항의 번호·문장·근거(백틱 안 경로 목록, `—`은 빈 목록)·핵심 사실·유형이 세트 파일과 같고 `check_question_set`이 통과한다. 이 시험은 세트 파일을 읽으므로 세트와 같은 커밋에 둔다
  - 사람이 확인하면(사람 단계 H00) `confirmed = true`, `confirmed_on`을 넣는 확정 커밋을 따로 둔다
- [ ] T018 [US2] 식별자 세트 초안(사람 단계 H01 뒤, 별도 커밋, research R-14 3번):
  - `uv run qk-dev eval identifiers --target qk_eval_baseline_6aeccd039b82`로 후보를 받아 `eval/question_sets/qk-evl-001-identifiers/v1.toml`을 쓴다. spec US2-3·US2-4·FR-009 그대로:
    형태마다 식별자 5개 이상(모자라면 있는 만큼과 `shortfall`), 식별자마다 `original`·`partial` 질문, `sentence` 질문 10개 이상, `label_terms`(원형·일부는 식별자 원형 하나), 근거 문서는 도우미가 다시 계산한 목록, `confirmed = false`.
    문서 문장을 그대로 옮겨 질문으로 쓰지 않는다
  - `eval/question_sets/qk-evl-001-identifiers/labeling.md`: 형태 판별 규칙, 흔한 일부 낱말 제외 기준과 뺀 식별자 수, 근거 문서 규칙(US2-4), 청크 경계에 걸린 식별자 위험(research R-13)
  - 서버 주소·내부 도메인·호스트 이름이 섞인 식별자(kebab-case, URL 경로 등)는 쓰지 않는다. `find_secrets`는 이런 값을 거르지 못하므로(AGENTS.md 6절) 작성 세션이 하나씩 보고 H04에서 사람이 다시 본다
  - 확인: `uv run qk-dev eval check <파일> --target qk_eval_baseline_6aeccd039b82` 통과(경고 검토), `uv run qk-dev eval identifiers --target … --set <파일>` 종료 0. 사람 확정(H04) 뒤 `confirmed = true`, `confirmed_on`을 넣는 확정 커밋을 따로 둔다

**Checkpoint**: US2 코드 시험과 T017 시험 통과. T018은 측정 단계에서 닫는다

---

## Phase 5: User Story 3 - 평가 대상에서 세 검색 방식의 Recall@5·MRR을 잰다 (P1)

**Goal**: 질의 벡터 재사용(R-06), 실행 전 검사와 비용 관문(R-05·R-07), 실행 순서와 멈춤(R-08), 지표(R-09), 실행 기록(R-10), `qk-dev eval run`(contracts/cli.md 2절).

**Independent Test**: 손으로 정한 순위의 가짜 검색으로 지표 기대값을 확인하고, 로컬 시험 데이터베이스와 가짜 임베딩 제공자로 세 방식을 끝까지 돌린다(SC-003~SC-006, SC-008, SC-010).

- [X] T019 [P] [US3] `tests/unit/evaluation/test_reuse.py`(SC-006, research R-06):
  - 질문 N개 × 방식 셋(`vector`, `hybrid`, `keyword`) × 가짜 대상 셋을 `retrieve`로 돌리면 `CountingProvider` 시도 수가 N(일시 실패 없음)
  - 같은 문장의 두 번째 요청은 처음 받은 `EmbedResult`를 그대로 돌려준다. 항목 실패(`provider_quota` 포함)도, `EmbedError`도 같은 문장이면 다시 부르지 않고 같은 결과·같은 예외를 낸다
  - `outcome(text)`가 그 문장의 첫 결과 종류를 돌려준다: `None`(아직 부르지 않음), 벡터, 항목 실패(`EmbedFailureKind` 값), 묶음 전체 실패(`EmbedErrorKind` 값).
    실행기는 이 값으로만 멈춤을 가린다. `retrieve` 결과로는 가를 수 없다. `EmbedError`는 생략 사유 `query_embedding_failed`로 바뀌고(`retrieval/service.py:125-127`) `usage_unavailable`은 항목 실패와 묶음 실패 둘 다에 있다(`domain/embedding.py:56`, `:64`)
  - `forget(text)` 뒤에는 다시 부른다. 디스크·저장소에 벡터를 쓰지 않는다
  - `CountingProvider`는 성공·실패 시도를 모두 세고, Neurons는 성공한 묶음만 제공자 값(측정) 또는 `embedding/estimate.estimated_neurons`(추정)로 센다. 실패 시도는 0
  - 호출 상한이 주입한 `RetryPolicy(max_retries=1)`에서 N × 2로 계산되고, 같은 정책 객체를 `EmbeddingService`와 상한 계산이 함께 쓴다
- [X] T020 [P] [US3] `tests/unit/evaluation/test_prechecks.py`(SC-005, research R-05·R-07):
  - 실행 전 검사 실패마다 거부 사유, 가짜 제공자 호출 0, `FakeDayUsageReader` 읽기 0. 사유 이름은 이 작업에서 고정하고 contracts/cli.md 2절에 적었다: `set_invalid`, `target_not_eval`(이름이 `qk_eval_`로 시작하지 않음), `target_unreachable`(`TargetUnavailable`), `no_active_index`, `index_rule_unknown`, `tokenizer_unreadable`, `tokenizer_unknown`,
    `source_url_duplicate`, `source_missing`(세트 자료원이 대상에 없음), `commit_mismatch`(대상 고정 커밋 ≠ 라벨 기준 커밋), `model_mismatch`(대상 사이 임베딩 모델·차원 다름)
  - 후보 판별: (`kw-index-baseline-v1`, `TokenBigramSplitSymbol`) A, (`kw-index-idsplit-v1`, `TokenBigramSplitSymbol`) B, (`kw-index-baseline-v1`, `TokenBigramSplitSymbolAlpha`) C. 그 밖의 조합은 위 사유로 거부. 검색 요약의 `index_rule`은 쓰지 않는다
  - 검사 순서: 세트 → 대상별 → 모델·차원 → 자료원·고정 커밋 → 장부. 앞에서 멈추면 뒤를 부르지 않는다
  - 비용 관문(`CostPreview`, data-model 3절): 검색할 질문 수 N은 지표 대상 가운데 모든 대상에서 근거 미색인인 질문을 뺀 수, `max_calls = N × (max_retries + 1)`, `estimated_neurons`는 질문마다 `estimated_neurons([문장], MODELS["@cf/baai/bge-m3"]) × (max_retries + 1)`의 합.
    키워드 전용이면 장부를 읽지 않고 `ledger.target = none`. `blocked_reason`은 `approval_missing`, `ledger_not_production`, `remote_read_not_allowed`, `ledger_unreadable`, `over_remaining`, `over_max_neurons`, `None` 가운데 하나이고,
    `remaining = 일일 할당 − day_total`. 허락이 없으면 미리 보기 값이 모두 채워진 채 `approval_missing`이다. 장부 읽기의 `LedgerUnavailable`은 `ledger_unreadable`이다. 막히면 질의 임베딩 0
- [X] T021 [P] [US3] `tests/unit/evaluation/test_runner.py`(research R-08, spec US3-3~US3-9):
  - 반복 순서 질문 → 대상(요청 순서) → 방식(`vector`, `hybrid`, `keyword`). `retrieve`는 `RetrievalRequest(question, mode, filters, want_context=False)`와 요청 단위 `RetrievalSettings`로 부른다
  - 지표 대상이 아닌 질문(`no_answer`, 라벨 미완료)은 검색하지 않고 결과에 넣지 않는다. 어떤 대상에서 근거가 모두 미색인이면 그 대상의 방식마다 `status = skipped`, `skipped_reason = evidence_unindexed`. 모든 대상에서 미색인이면 질의 임베딩도 부르지 않는다
  - 근거 일부 미색인은 `unindexed_evidence` 수로 남긴다. 첫 근거 순위는 `FusedHit.provenance.source_url`로 문서 표에서 (자료원, 위치)를 찾아 근거 문서인 항목의 `rank` 최솟값이다(같은 문서 청크 여럿이면 처음 나온 순위)
  - 질문별 실패는 `RetrievalFailure` 값이 `status`이고 다른 방식으로 다시 묻지 않는다. 결과 0건은 `no_results`. 하이브리드 생략은 `omitted`(`search`, `reason`, `detail`은 실패 종류 값만), 키워드 낱말 수는 `keyword_terms`
  - 멈춤: 질문의 첫 임베딩 검색 뒤 `ReusingEmbedder.outcome(text)`가 항목 실패 `provider_quota`면 `provider_quota`, 묶음 전체 실패(`EmbedErrorKind`)면 `query_embedding_unavailable`.
    이때 그 질문의 결과는 버리고 앞 질문까지만 남긴다. 검색 상태 `store_unavailable` → `store_unavailable`, 검색 상태 `index_version_changed`·`no_active_index` 또는
    요약 인덱스 버전이 `None`이 아니면서 실행 전 값과 다름 → `index_version_changed`, `KeyboardInterrupt` → `interrupted`. 벡터 전용 임베딩 실패(요약 인덱스 버전 `None`)는 질문별 실패로 남고 멈추지 않는다.
    검색 결과의 `source_url`이 실행 전에 읽은 문서 표에 없으면 대상이 실행 중 바뀐 것으로 보고 `index_version_changed`로 멈춘다
  - 멈추면 남은 질문을 돌리지 않고 `complete = false`, `stop_reason`, 끝낸 질문의 결과만 담는다. 완료 기록의 결과 수 = 지표 대상 질문 수 × 대상 수 × 방식 수
  - `top5`는 상위 5건의 (순위, 자료원, 위치, 근거 여부), `result_digest`는 상위 20건의 `[순위, 자료원, 위치]` 배열을 `json.dumps(…, ensure_ascii=False, separators=(",", ":"))`로 직렬화한 UTF-8 바이트의 SHA-256(결과 0건·실패면 `None`)
- [X] T022 [P] [US3] `tests/unit/evaluation/test_metrics.py`(SC-003, research R-09): spec SC-003 사례 목록(근거 1위, 5위, 6위, 20위, 21위, 결과 없음, 검색 실패, 같은 문서 청크 여러 개, 근거 여럿 가운데 하나만 나옴, 상위 5건 가운데 근거 청크 0·3·5개)마다
  Recall@5·MRR·상위 20건 포함 비율·Precision@5의 분자·분모와 소수 넷째 자리 값이 손으로 정한 기대값과 같다. MRR은 20 초과·없음을 0, Precision@5는 결과가 5건보다 적어도 5로 나눈다.
  평균 결과 수·상한 도달 비율은 키워드 전용만(상한 도달은 결과 수 = 실행 조건 후보 수). 실패는 분모에 넣고 0, `skipped`·지표 대상 아님은 분모에서 빼고 사유별 수, 생략·낱말 0개 수, 유형·식별자 형태·질의 형태별 지표가 같은 함수로 나온다
- [X] T023 [P] [US3] `tests/unit/evaluation/test_record_schema.py`(SC-008, contracts/run-record.md): 최상위·`conditions`·`targets[]`·`questions[]`·`results[]`·`usage`와 중첩 객체
  (`conditions.question_set`·`ledger`·`filters`·`code_commit`, `questions[].evidence[]`, `results[].omitted[]`·`top5[]`)의 키가 계약 목록과 정확히 같다(목록 밖 키·빠진 키 모두 실패).
  `schema = "qk-evl-001-run/v1"`, `run_id`가 `^evl-\d{8}T\d{6}Z-[0-9a-f]{8}$`, 키 정렬·들여쓰기 2칸, 값이 없는 선택 필드는 `null`. 시험 세트의 질문 문장·`facts`·`label_terms` 문자열이 기록 파일에 0번.
  쓰기 규칙: 경로가 이미 있으면 거부, `<경로>.partial`에 쓴 뒤 이름 바꿈, 미완료도 같은 방식, 실행 전 검사·비용 관문에서 멈추면 파일 없음. 읽기 함수가 쓴 기록을 그대로 되살린다
- [X] T024 [US3] `src/qello_knowledge/evaluation/reuse.py`: `CountingProvider`(`EmbeddingProvider` 감싸기, 시도 수·측정 Neurons·추정 Neurons)와 `ReusingEmbedder`(`Embedder` 구현, 문장 → `EmbedResult` 또는 `EmbedError`를 메모리에만 담음, `outcome`, `forget`, `preview`는 그대로 넘김). research R-06
- [X] T025 [US3] `src/qello_knowledge/evaluation/prechecks.py`: `Candidate`(`A`, `B`, `C`), `candidate_for(index_rule, tokenizer)`, `precheck(question_set, targets) -> PrecheckResult`(T020 사유 이름), `cost_preview(questions, retry, ledger, *, ledger_is_production, allow_remote_read, allow_query_embedding, max_neurons, daily_allowance) -> CostPreview`.
  장부가 운영인지는 `evaluation/`이 판단하지 않고 조립하는 쪽(T031)이 `ledger_is_production`으로 넘긴다(접속 정보 해석이 `adapters`에 있어서다)
- [X] T026 [US3] `src/qello_knowledge/evaluation/records.py`: data-model 3절 `RunConditions`, `QuestionResult`(contracts/run-record.md 5절 이름 그대로), `TopHit`, `RunRecord`와 JSON 쓰기·읽기(contracts/run-record.md 1~7절), `new_run_id(clock, random)`
- [X] T027 [US3] `src/qello_knowledge/evaluation/metrics.py`: data-model 4절 `Ratio`(`fractions.Fraction`, 출력은 소수 넷째 자리), `MetricSet`, `Breakdown`. 입력은 `RunRecord` 하나뿐이다(`questions`·`results`와 상한 도달 판정에 쓰는 `conditions.candidates`, FR-020)
- [X] T028 [US3] `src/qello_knowledge/evaluation/runner.py`: `run(request, targets: Mapping[str, EvalTarget], descriptions, documents, embedder: ReusingEmbedder, counter: CountingProvider, *, clock, new_run_id, code_commit) -> RunRecord`.
  `RetrievalDeps(store=target.store, embedder=embedder, model_version=description.embedding_model)`는 runner가 대상마다 만들고, `embedder`는 모든 대상이 같은 객체 하나를 쓴다. 기록의 `usage`는 `counter` 값이다.
  T021 순서·멈춤·결과 규칙. 질문이 끝날 때마다 `ReusingEmbedder.forget`을 부른다
- [X] T029 [P] [US3] `tests/unit/devtools/test_eval_cli.py`의 `run` 절(contracts/cli.md 2절):
  - 종료 코드 0~5 각각: 세트 거부·대상 검사 실패 1, `--allow-query-embedding`에 `--max-neurons` 없음·기록 경로 있음·`--usage-target`이 `--target` 밖 2, 임베딩이 드는 방식인데 `--allow-remote-read` 없음 3,
    미리 보기 뒤 멈춤(허락 없음, `ledger_not_production`, 장부 읽기 실패, 잔여량·`--max-neurons` 초과) 4, 실행 미완료 5(기록은 `complete = false`로 씀)
  - 두 단계 허락: 처음 실행이 질문 수·호출 상한·예상 Neurons·장부 날짜·`day_total`·잔여량·질의 예비분을 보이고 4, 같은 인자에 `--allow-query-embedding --max-neurons X`를 더하면 실행
  - `ledger_not_production`: `--ledger-url-env`가 가리키는 접속 정보가 `adapters/postgres/connection.is_local`과 같은 규칙으로 로컬 컨테이너이거나 데이터베이스 이름이 `--target` 가운데 하나면 4. 키워드 전용이면 장부 옵션 없이 0
  - 환경의 `DATABASE_URL`은 쓰지 않는다. 출력·예외에 질문 문장과 접속 정보가 없다. `code_commit`은 주입한 `git` 조회로 `{sha, dirty}`를 채운다
  - 대상·장부·제공자·`git` 조회는 주입 인자(`target_factory`, `ledger_factory`, `provider_factory`, `git_state`)로 받아 DB·네트워크에 닿지 않는다
  - 설정 점검(`load(Entrypoint.INDEX)`·`build_report`) 실패, `budget_settings`가 `None`, `--sources`·`--exceptions`의 자료원 설정·예외 파일 오류는 2다
- [X] T030 [US3] `tests/localdb/evaluation/test_eval_run.py`(SC-004·SC-006·FR-022): T001의 `baseline_target`·`idsplit_target` 두 대상과 골든형 합성 세트로 `run_eval`을 두 번 돌린다.
  주입: `provider_factory`는 `FakeEmbeddingProvider`, `ledger_factory`는 `FakeDayUsageReader`(잔여량 충분), `--ledger-url-env`에는 로컬이 아닌 자리표시 접속 정보(예: `host=ledger.invalid dbname=qk`)를 담은 시험용 환경값을 주고
  `--allow-remote-read --allow-query-embedding --max-neurons`를 함께 준다. 접속 정보는 운영 판정에만 쓰이고 연결하지 않는다.
  키워드 전용 질문별 `result_digest`·첫 근거 순위가 두 실행에서 같고, 각 기록으로 다시 계산한 지표가 실행 출력과 같다. 제공자 시도 수가 검색한 질문 수와 같다.
  `qk.embedding_usage` 행이 `--usage-target` 대상에만 생기고 다른 대상은 0, `origin` 데이터베이스는 그대로다
- [X] T031 [US3] `src/qello_knowledge/devtools/eval_cli.py`에 `run_eval`, `devtools/db.py`의 `eval` 묶음에 `run`(contracts/cli.md 2절 옵션 전부)을 더한다. 조립:
  - 설정: `load(Entrypoint.INDEX, environ=source, env_file=None)`과 `build_report`(`eval-index`와 같은 방식), `budget_settings(settings)`(일일 할당 `daily_allowance`와 `query_reserve`의 출처)
  - 정책: `sources.config.load_sources(--sources)`와 `security.policy.load_policy(--exceptions, configs)`(`(policy, issues)`를 받는다, `indexer/search_cli.run_search`와 같은 방식)
  - 제공자 `indexer/sync_cli.workers_ai_provider`를 `CountingProvider`로 감싸고, `EmbeddingService(그 제공자, 사용량 대상의 PostgresStore, PostgresUsageLedger, budget, indexer/embedding.security_outgoing_check(policy), retry_policy=RetryPolicy(max_retries=1), retry_delay=query_retry_delay)`
    (`indexer/search_cli.postgres_search`와 같은 값)를 만든다. 사용량 대상은 `--usage-target`(기본 첫 `--target`)이다
  - `ReusingEmbedder` 하나를 만들어 모든 대상이 같이 쓰도록 T028 runner에 넘긴다
  - 장부: 환경 변수 이름으로 받은 접속 정보로 `PostgresDayUsageReader`를 열고, 운영 여부(`is_local`과 같은 규칙, 대상 이름과 같은지)를 판단해 T025에 넘긴다. 장부 읽기는 대상 검사가 모두 통과한 뒤에만 한다
  - `code_commit`은 `git rev-parse HEAD`와 `git status --porcelain`이 비었는지로 채운다
  - 끝나면 대상별·방식별 지표 요약(분자·분모)을 출력한다

**Checkpoint**: US3 시험 통과. 대상 하나로 세 방식 평가를 끝까지 돌릴 수 있다

---

## Phase 6: User Story 4 - ADR-010 후보 A·B·C를 같은 조건에서 비교한다 (P2)

**Goal**: 비교 조건 검사·공통 질문 집합·Markdown 표(R-11, `qk-dev eval tables`, contracts/cli.md 3절)와 후보 C 평가 대상 준비(R-12, contracts/cli.md 5절).

**Independent Test**: 조건이 같은 기록은 표가 나오고 조건 하나만 다른 기록은 그 항목 이름과 함께 거부된다(SC-007). 후보 C를 만든 뒤 A·B·원본 데이터베이스와 마이그레이션 목록이 그대로다(SC-009).

- [X] T032 [P] [US4] `tests/unit/evaluation/test_compare.py`(SC-007, spec US4-2~US4-6, FR-024·FR-025):
  - 세트 ID·버전·파일 지문, 자료원별 고정 커밋, 임베딩 모델, 질의 쪽 규칙, 후보 수, RRF 상수, 검색 필터 가운데 하나만 다른 기록 쌍마다 거부와 그 항목 이름·기록별 값. 미완료 기록은 거부
  - 같은 조건이면 후보별 표. 방식마다 공통 질문 집합은 모든 대상에서 지표 대상이고 실패가 아니며(`no_results`는 남김) 하이브리드 생략이 없는 질문이다. 한 후보에서만 실패·생략·`skipped`된 질문은 빠지고 질문 ID와 사유가 나온다
  - 벡터 전용 `result_digest`가 대상 사이에 다른 질문은 "벡터 순위 다름"으로 표시되고, 하이브리드 차이는 지문이 같은 질문에서만 키워드 규칙 효과로 읽는다는 고정 문장이 표 아래에 붙는다
  - 다른 실행의 기록이 섞이면 "질의 벡터 다름"이 붙는다. 대상이 하나면 비교표 없이 대상별 표만 나온다
  - US4-2 항목: 식별자 세트의 형태별·질의 형태별 키워드 전용 상위 20건 포함 비율과 Precision@5, 골든 세트의 키워드 전용·하이브리드 Recall@5·MRR, 키워드 전용 평균 결과 수·상한 도달 비율. 모든 칸에 분자·분모
  - 표 출력에 시험 세트의 질문 문장 문자열이 0번(SC-008)
- [X] T033 [US4] `src/qello_knowledge/evaluation/compare.py`: data-model 5절 `ConditionMismatch`, `CommonSet`, `ComparisonTable`과 Markdown 표 생성(대상별 표, 분류별 표, 비교표). 고정 문장은 상수로 둔다
- [X] T034 [P] [US4] `tests/unit/devtools/test_eval_cli.py`의 `tables` 절(contracts/cli.md 3절): 표 출력 0, 비교 조건 불일치·미완료 기록 1(다른 항목 이름과 기록별 값 출력), 인자 오류·기록 스키마 오류 2, `--target`·`--breakdown` 전달
- [X] T035 [US4] `src/qello_knowledge/devtools/eval_cli.py`에 `run_tables`, `devtools/db.py`의 `eval` 묶음에 `tables`(`--run` 여러 번, `--target`, `--breakdown {type,identifier_form,query_form}`)를 더한다. 저장소·외부 호출 없음
- [X] T036 [P] [US4] `tests/unit/devtools/test_eval_index_tokenizer_cli.py`(contracts/cli.md 5절, DB에 연결하지 않는 경로, `db.main([...])`로 부른다): `--keyword-tokenizer`가 `TokenBigramSplitSymbolAlpha` 밖이면 2, `--rule kw-index-idsplit-v1`과 함께 쓰면 2,
  `--source`·`--from-url-env`·`--allow-embed`·`--sources`·`--reviews`·`--exceptions` 가운데 하나라도 기본값과 다른 값을 주면 2, 커밋이 40자 SHA가 아니면 2, 최종 이름 `qk_eval_baseline_alpha_<sha12>`.
  설정이 없는 환경에서도 이 인자 오류가 2로 나온다(설정 점검보다 먼저 검사). 기존 `tests/unit/devtools/test_eval_index_cli.py`는 고치지 않고 그대로 통과한다
- [X] T037 [P] [US4] `tests/localdb/devtools/test_eval_index_tokenizer.py`(SC-009, research R-12): 기존 `tests/localdb/devtools/test_eval_index.py`의 `origin` 픽스처·`_prepare`·`SHA`를 가져와(그 파일은 고치지 않음) 후보 A를 만든 뒤 후보 C를 준비한다.
  - 종료 0, 출력 JSON에 `base_database`, `database`, `tokenizer`, `index_version`, `external_calls: 0`. 가짜 제공자 생성 0회
  - C의 `qk.chunk_search_text_pgroonga` 토크나이저가 `TokenBigramSplitSymbolAlpha`, 인덱스 버전·청크 ID·임베딩이 A와 같다
  - 같은 영문 일부 낱말(시험 문서 `retryPayment`의 `payment`)로 키워드 전용 검색을 하면 A는 0건, C는 그 문서를 찾는다
  - 후보 B(`_prepare(origin, rule=INDEX_IDSPLIT)`)도 미리 만들어 두고, A·B·원본 데이터베이스의 색인 정의(`pg_get_indexdef`)가 그대로, `load_migrations()` 파일 목록이 그대로
  - C가 이미 있으면 5, 같은 커밋의 A가 없으면 6, 이전 실패의 `__preparing`은 지우고 다시 만든다. 기준 데이터베이스에 다른 연결이 열려 있으면 1과 `stage = "clone"`
- [X] T038 [US4] `src/qello_knowledge/devtools/eval_index.py`에 `eval_tokenizer_db_name(commit)`(`qk_eval_baseline_alpha_<sha12>`)과 `prepare_tokenizer(*, commit, tokenizer, source_env, out)`을 더하고, `devtools/db.py`의 `eval-index`에 `--keyword-tokenizer {TokenBigramSplitSymbolAlpha}`를 더한다. research R-12 1~5단계:
  기준·최종 이름 확인(6·5) → `<최종>__preparing`만 지운 뒤 `CREATE DATABASE "<최종>__preparing" TEMPLATE "<기준>" STRATEGY = FILE_COPY`(`stage = "clone"`) → 한 트랜잭션에서 `DROP INDEX qk.chunk_search_text_pgroonga`와
  `CREATE INDEX chunk_search_text_pgroonga ON qk.chunk USING pgroonga (search_text) WITH (tokenizer = 'TokenBigramSplitSymbolAlpha')`(`stage = "reindex"`) → `pg_class.reloptions` 확인과 `SET enable_seqscan = off`에서 `&@~` 조건 `EXPLAIN`이 그 색인을 쓰는지 확인(`stage = "verify"`) →
  최종 이름으로 바꾸기(`stage = "rename"`). 옵션이 없으면 기존 `prepare`의 동작·출력·종료 코드·`eval_db_name`이 그대로다.
  `db.py`의 `eval-index` 분기는 `--keyword-tokenizer`가 있으면 옵션 조합을 먼저 검사하고(2), `load()`·`build_report()`를 부르지 않고 `prepare_tokenizer`로 간다. 이 경로는 설정·제공자·자료원이 필요 없다(`db.py:189-196`의 기존 순서는 옵션이 없을 때 그대로)

**Checkpoint**: US4 시험과 기존 `test_eval_index.py`·`test_eval_index_cli.py` 통과

---

## Phase 7: User Story 5 - 결과를 비교 리포트와 ADR-010 초안으로 남긴다 (P2)

**Goal**: 측정 전 계약 고정, 측정 뒤 리포트, ADR-010 Proposed(spec FR-026~FR-030, research R-14). 문서 작업이고 사람 단계와 번갈아 한다.

**Independent Test**: 리포트 4절의 수치가 커밋한 실행 기록에 `qk-dev eval tables`를 다시 돌린 출력과 같고, 1절이 측정 전 커밋과 같으며, 측정 결과·작성 세션 해석·사람 결정이 나뉘어 있다.

- [ ] T039 [US5] 측정 전 계약(H00·H04 뒤, 측정 전): 두 세트가 확정되어 표본 수가 정해진 뒤 `specs/QK-EVL-001-retrieval-eval/measurement/retrieval-eval-report.md`를 `templates/eval-report.md` 양식으로 만들고 1절(가설, 주 지표, 가드레일 지표, 성공 기준, 중단 기준)과
  ADR-010 판단 규칙만 채운다. 판단 규칙 초안은 research R-14 그대로(주 지표: 식별자 세트에서 camelCase·PascalCase·약어 경계·숫자 경계의 일부 질문에 대한 키워드 전용 상위 20건 포함 비율. 가드레일: 골든 세트 하이브리드 Recall@5·MRR(공통 질문 집합),
  식별자 세트 키워드 전용 Precision@5, 키워드 전용 상한 도달 비율, 대조군(snake·kebab·URL 경로) 포함 비율). "주 지표가 A보다 n문항 이상 오르고 가드레일이 각각 m문항 넘게 나빠지지 않으면 권고"의 n·m 자리는 비워 두고 표본 수를 함께 적는다.
  사람이 H05에서 n·m을 정하면 그 값을 넣어 "계약 고정" 커밋 하나로 남긴다. 이 커밋이 측정 전 기준이고, 그 뒤로 1절과 판단 규칙을 바꾸지 않는다
- [ ] T040 [US5] 측정 뒤 리포트 2~9절(사람 단계 H06·H07 뒤, 측정 커밋): `measurement/runs/<실행 ID>.json`을 커밋하고 `qk-dev eval tables` 출력을 4절에 붙인다. spec US5-2 그대로 채운다:
  생성 결과 절 "해당 없음(QK-EVL-002)", 검색 p50·p95 "해당 없음(로컬 평가용 데이터베이스, 운영 지연과 비교하지 않음)", 질문 유형 분포 칸에는 이 명세의 유형별 수와 양식 분류와 대응하지 않는다는 문장,
  Precision@5 행은 식별자 세트만 채우고 골든 세트는 "해당 없음(근거 문서 목록이 전부가 아님)". Recall@5 정의(하나라도 찾은 비율, Hit@5와 같음), 골든 세트 표본 한계(한 문항이 Recall@5를 12.5%p 바꿈, US5-6),
  비용 절에 실제 Neurons와 예상치, 평가 사용량이 평가 대상에만 기록되어 운영 장부에 보이지 않는다는 점(spec Assumptions). 측정 결과, 작성 세션 해석, 사람 결정을 나눈다(FR-027). 목표에 못 미쳐도 기록한다.
  Recall@5·MRR 목표 후보와 검색 설정 조정은 수치 근거와 함께 제안으로만 적는다(FR-028·FR-029). 질문 문장·핵심 사실·청크 본문은 넣지 않고 질문 ID와 문서 위치로 가리킨다. 확정 전 세트의 수치는 결론에 쓰지 않는다
- [ ] T041 [US5] `docs/sdd/decisions/ADR-010-keyword-search-text.md`(별도 커밋, `templates/decision-record.md` 양식): Status Proposed. 맥락, 후보 A·B·C, 비교 기준, T039에서 고정한 판단 규칙, 리포트의 측정 수치와 실행 조건(그대로 인용, SC-012), 리포트 링크, 작성 세션 권고.
  후보 C를 고를 때의 영향(토크나이저가 인덱스 버전 재료가 아니어서 운영에 반영하면 인덱스 버전이 그대로인 채 키워드 동작이 바뀜, QK-STO-002 평가 게이트와 `domain/keyword_rules.py` 대응표에 이를 가릴 식별자가 필요하고 방법은 사람 결정)을 적는다(FR-030). Status 결정과 운영 반영은 사람이 별도 작업으로 한다
- [ ] T042 [US5] 리포트 대조: 커밋한 실행 기록으로 `qk-dev eval tables`를 다시 돌려 리포트 4절과 글자 단위로 같은지, 1절과 판단 규칙이 "계약 고정" 커밋과 같은지(`git diff <계약 고정 커밋> -- …`에서 1절 범위 변경 0),
  ADR-010 수치가 리포트와 같은지, 실행 기록 `usage`의 실제 Neurons가 실행 전 미리 보기의 예상치 이하인지(SC-011) 확인하고 "실행 기록"에 적는다

**Checkpoint**: SC-011·SC-012 확인, ADR-010 Proposed

---

## Phase 8: Polish & Cross-Cutting

- [X] T043 경계·회귀 확인: `uv run pytest tests/unit/test_boundaries.py`, 기존 QK-RET-001·QK-EMB-001·QK-STO-001 시험 전부 통과.
  `git diff --stat origin/main --diff-filter=MD -- src/qello_knowledge/retrieval src/qello_knowledge/embedding src/qello_knowledge/adapters/postgres src/qello_knowledge/domain tests config docs/sdd specs/QK-RET-001-hybrid-retrieval specs/QK-BOT-001-discord-ask`의
  고친·지운 파일이 `tests/unit/test_boundaries.py` 하나뿐이다(새 파일 `adapters/postgres/eval_target.py`, ADR-010, 새 시험은 `--diff-filter=A`로 따로 본다)
- [X] T044 quickstart.md 1절 전체 실행(`python scripts/preflight.py`, `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run qk-dev db up`, `QK_REQUIRE_LOCALDB=1 uv run pytest`).
  결과를 "실행 기록"에 적고 이 목록 체크 표시를 갱신한다
- [ ] T045 `TASK.md` Decisions·검증 기록 갱신, `/pr-draft-summary`로 PR 초안(CLAUDE.md 의무 사용)

---

## 사람 단계

quickstart.md 2절과 같다. 각 단계는 실행 전에 사람이 허락한다. 비용 근거는 research R-15.

| 단계 | 내용 | 시점 | 비용·허락 |
| --- | --- | --- | --- |
| H00 | 골든 세트 v1 확인(SC-002 시험 결과와 H05 v2 대조) → T017 확정 커밋 | T017 뒤 | 없음 |
| H01 | `uv run qk-dev eval-index prepare --rule kw-index-baseline-v1 --commit 6aeccd039b825dcd7a2b6c046a34ef72089a1f78`. 실행 전에 캐시 원본이 로컬 개발 DB인지 사람이 확인한다: `--from-url-env`의 기본값은 `DATABASE_URL`이므로(`devtools/db.py:144`) 그 값이 비었거나 로컬 컨테이너가 아니면 로컬 개발 DB 접속 정보를 담은 환경 변수를 `--from-url-env`로 준다(2026-10-30 사용자 결정). QK-RET-001 H02로 같은 이름이 이미 있으면 종료 5이고 그 데이터베이스를 그대로 쓴다 | T038 뒤(코드 PR 병합 뒤 권장) | GitHub 읽기. 예상 0 Neurons, 종료 4면 사람이 다시 임베딩할지, 운영 DB를 읽기 전용으로 쓸지 정한다(후보당 약 900) |
| H02 | 같은 명령에 `--rule kw-index-idsplit-v1`. 캐시 원본으로 H01 데이터베이스를 `--from-url-env`로 줄 수 있다 | H01 뒤 | 위와 같음 |
| H03 | 같은 커밋에 `--rule kw-index-baseline-v1 --keyword-tokenizer TokenBigramSplitSymbolAlpha` | H01 뒤 | 외부 호출 0 |
| H04 | T018 식별자 세트 초안 확인 → 확정 커밋. 두 세트 `qk-dev eval check --target <H01 데이터베이스>` 경고 검토, 식별자에 서버 주소·내부 도메인·호스트 이름이 없는지 확인(AGENTS.md 6절) | T018 뒤 | 없음 |
| H05 | T039 리포트 계약 절과 ADR-010 판단 규칙 확인, n·m 결정 → 작성 세션이 그 값을 넣어 "계약 고정" 커밋 | T039 뒤, 측정 전 | 없음 |
| H06 | `qk-dev eval run`을 세트마다 대상 셋(H01·H02·H03)으로. 먼저 `--ledger-url-env`·`--allow-remote-read`만 주고 미리 보기(종료 4), 사람이 값을 보고 `--allow-query-embedding --max-neurons X`로 다시 실행 | H00·H04·H05 뒤 | 운영 장부 읽기 전용 조회(Bastion 터널), 질의 임베딩 두 세트 상한 약 8.3 Neurons |
| H07 | `qk-dev eval tables`로 대상별·비교 표 → T040 | H06 뒤 | 없음 |
| H08 | ADR-010 Proposed 검토, Status·운영 반영 결정(별도 작업) | T041 뒤 | 없음 |

정리: 평가용 데이터베이스(최종 이름)는 사람이 `DROP DATABASE`로 지운다. 명령은 `__preparing` 잔여물만 지운다.

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1 → US3. US2의 코드(T013~T016)는 Phase 2 뒤 US1과 병렬로 할 수 있다(T016은 T012 뒤, 같은 `eval_cli.py`·`db.py`). T017은 T010 뒤(검증기가 있어야 시험이 돈다). T018은 H01 뒤.
- US4의 비교(T032~T035)는 US3의 `records.py`·`metrics.py`(T026·T027) 뒤. 후보 C 준비(T036~T038)는 Phase 2와 무관해 언제든 할 수 있다.
- US5는 사람 단계와 번갈아 간다: H00·H04 → T039 → H05(n·m) → 계약 고정 커밋 → H06 → H07 → T040 → T041 → T042.
- 같은 파일을 고치는 작업은 순서대로 한다: `devtools/eval_cli.py`·`devtools/db.py`(T012 → T016 → T031 → T035, T038은 `db.py`의 `eval-index` 부분만), `tests/unit/devtools/test_eval_cli.py`(T011 → T029 → T034).
- 실행 경로 구현 순서: T024 → T025 → T026 → T027 → T028(runner가 앞의 넷을 쓴다) → T031. T030(로컬 DB 시험)은 T031보다 먼저 쓰고 실패를 확인한다.

## 커밋 단위 (research R-14, AGENTS.md 3.4)

1. 명세 문서: spec.md(FR-002·US2-4 정정 포함), plan 산출물, tasks.md, checklists, TASK.md
2. 평가 코드와 시험(스토리별로 나눠도 된다: US1, US2 도우미, US3, US4). 시험 세트는 `tests/fixtures/evaluation/` 합성 세트뿐이다
3. 골든 세트 v1과 `test_golden_v1.py`(T017) → 확정 표시(H00)
4. 식별자 세트 v1 초안(T018) → 확정 표시(H04)
5. 리포트 계약 절과 ADR-010 판단 규칙(T039, H05의 n·m을 넣은 "계약 고정" 커밋)
6. 측정: 실행 기록과 리포트 2~9절(T040)
7. ADR-010 Proposed(T041)

질문 세트(3·4)와 평가 코드(2)를 한 커밋에 넣지 않는다. 라벨을 고쳐야 하면 세트 버전을 올려 별도 커밋에 사유를 남긴다.

## Parallel Example

```text
Phase 2: T004, T005, T006 (시험·도우미) → T007 / T003은 먼저
US1:     T008, T009, T011 (시험) → T010 → T012
US2:     T013, T015 (시험) → T014 → T016 / T017은 T010 뒤
US3:     T019, T020, T021, T022, T023, T029, T030 (시험) → T024 → T025 → T026 → T027 → T028 → T031
US4:     T032, T034, T036, T037 (시험) → T033 → T035 / T038
```

## Implementation Strategy

1. MVP: Phase 1·2 + US1. 질문 세트 형식이 서면 골든 세트(T017)를 옮기고 QK-STO-002·QK-EVL-002가 형식을 쓸 수 있다.
2. US3으로 대상 하나에서 세 방식 평가를 끝까지 돌린다(1.G "벡터·키워드·하이브리드 비교"의 본체).
3. US4로 후보 C 준비와 후보 비교를 더한다. 여기까지가 코드 PR이다(측정 없음, 외부 호출 0).
4. 사람 단계 H00~H04로 평가 대상과 두 세트를 확정하고, T039 → H05 → 계약 고정 → H06 → T040 → T041로 측정과 ADR-010을 닫는다. 측정 PR은 코드 PR과 나눌지 사람이 정한다.
5. 스토리마다 시험 → 구현 → 체크포인트 → 커밋(`/harness-commit`).

## TASK.md Scope 갱신안 (이 목록 승인과 함께 반영)

`## Scope`의 "구현 범위(tasks 승인 때 확정, 지금은 쓰지 않음)" 문장을 다음 목록으로 바꾼다.

- 새 파일: `src/qello_knowledge/evaluation/`(`__init__.py`, `question_set.py`, `labeling.py`, `reuse.py`, `prechecks.py`, `runner.py`, `metrics.py`, `records.py`, `compare.py`), `src/qello_knowledge/ports/evaluation.py`,
  `src/qello_knowledge/adapters/postgres/eval_target.py`, `src/qello_knowledge/devtools/eval_cli.py`
- 고치는 파일: `src/qello_knowledge/devtools/db.py`(`eval` 묶음, `eval-index --keyword-tokenizer`), `src/qello_knowledge/devtools/eval_index.py`(`prepare_tokenizer`, `eval_tokenizer_db_name` 추가, 기존 `prepare` 그대로),
  `tests/unit/test_boundaries.py`(`evaluation` 검사 추가)
- 새 시험: `tests/unit/evaluation/`(fakes.py, test_question_set, test_set_warnings, test_labeling, test_golden_v1, test_reuse, test_prechecks, test_runner, test_metrics, test_record_schema, test_compare),
  `tests/unit/devtools/test_eval_cli.py`, `tests/unit/devtools/test_eval_index_tokenizer_cli.py`, `tests/localdb/evaluation/`(conftest, test_eval_target, test_day_usage_reader, test_identifiers_command, test_eval_run),
  `tests/localdb/devtools/test_eval_index_tokenizer.py`, `tests/fixtures/evaluation/question_sets/`
- 질문 세트: `eval/question_sets/qk-evl-001-golden/`(v1.toml, labeling.md), `eval/question_sets/qk-evl-001-identifiers/`(v1.toml, labeling.md)
- 측정: `specs/QK-EVL-001-retrieval-eval/measurement/`(runs/, retrieval-eval-report.md), `docs/sdd/decisions/ADR-010-keyword-search-text.md`
- 질의 벡터 재사용은 `Embedder` 감싸기로 하고 QK-RET-001 검색 경로 코드(`retrieval/`)는 바꾸지 않는다

`## Validation`의 구현 단계 문장("tasks 승인 때 이 절을 고친다")은 AGENTS.md 7절 기본 검증 전체로 바꾼다.

## 실행 기록

- 2026-10-31 T005~T007: 어댑터와 로컬 DB 시험을 같은 단계에서 쓰고 함께 돌렸다(시험 먼저 실패 확인을 하지 않았다). US1부터는 시험을 먼저 쓰고 수집 오류로 실패를 확인한 뒤 구현했다.
- 2026-10-31 T001·T015 구현 중 발견: 가짜 자료원은 원본 리비전을 `v1`로 남겨 40자 SHA인 라벨 기준 커밋과 맞출 수 없었다. `tests/localdb/evaluation/conftest.py`의 `prepare_target`이
  평가 대상의 `qk.sync_run_source.origin_version`을 시험 SHA로 바꿔 둔다(시험 데이터베이스만, 실제 GitHub 자료원은 커밋 SHA를 남긴다).
- 2026-10-31 T017: 골든 세트 v1은 H05 v2 표를 일회용 스크립트(저장소 밖 작업 공간)로 글자 그대로 옮겼고 `test_golden_v1.py`가 11문항 대조를 통과했다. `confirmed = false`이며 확정은 사람 단계 H00이다.
- 2026-10-31 T029·T031: 설정 점검(`load(Entrypoint.INDEX)`·`build_report`)이 `DATABASE_URL` 형식을 검사한다. 실행은 그 값을 쓰지 않지만 형식이 틀리면 종료 2(`config_invalid`)다. `eval-index prepare`와 같은 동작이다.
- 2026-10-31 T037: 후보 C 준비 뒤 같은 영문 일부 낱말(`retryPayment`의 `payment`)로 키워드 전용 검색을 하면 후보 A 0건, 후보 C는 그 문서를 찾았다. 기준 데이터베이스에 연결이 열려 있으면 `stage = "clone"` 종료 1이다.
- 2026-10-31 T043: `git diff --stat --diff-filter=MD HEAD`로 `retrieval/`·`embedding/`·`adapters/postgres/`·`domain/`·`tests/`·`config/`·`docs/sdd/`·QK-RET-001·QK-BOT-001 문서·`AGENTS.md`·`CLAUDE.md`·`.claude/`를 보면
  고친 파일은 `tests/unit/test_boundaries.py`(추가 79줄)뿐이다. `devtools/db.py`·`devtools/eval_index.py`도 추가만 있고 지운 줄이 없다(기존 `prepare` 동작 그대로).
- 2026-10-31 ruff E501은 한글을 두 칸으로 센다. 긴 문서 문자열과 시험 문자열을 줄 나눔으로 고쳤다.
- 2026-10-31 T044 구현 중 발견: preflight의 `env-assigned-secret` 규칙이 `prechecks.py`의 토크나이저 이름 상수(`…_TOKENIZER = "TokenBigram…"`)에 걸렸다(이름에 `TOKEN`, 값 12자 이상).
  허용 목록을 늘리지 않고 상수 이름을 `KEYWORD_BASELINE`·`KEYWORD_ALPHA`로 바꿨다.
- 2026-10-31 T044: quickstart 1절 실행. `uv run python scripts/preflight.py`(998개 통과), `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run qk-dev db up`, `QK_REQUIRE_LOCALDB=1 uv run pytest` 3,755 passed(3 deselected는 `external`). 이 가운데 QK-EVL-001 새 시험 파일은 단위 188개(`tests/unit/evaluation/`, `test_eval_cli.py`, `test_eval_index_tokenizer_cli.py`)·로컬 DB 28개이고, `test_boundaries.py`에 경계 검사가 더해졌다.
- 2026-10-31 구현 검토(작성에 관여하지 않은 별도 서브에이전트, 읽기 전용, 시험 직접 실행): 경미한 변경 요청(높음 0, 중간 2, 낮음 7). 작성 세션이 지적마다 시험을 먼저 썼다. 실패 확인은 새 필드 때문에 수집 단계에서 실패한 것까지만 했고 지적별로 따로 보지 않았다.
  - 중간 1: `--out`의 상위 디렉터리가 없으면 검색을 끝낸 뒤 기록을 못 쓰고 traceback으로 끝났다. 인자 단계에서 종료 2(`out_dir_missing`), 쓰기 실패는 종료 2(`record_write_failed`)와 실행 ID·호출 수 출력.
    `--out`이 디렉터리면 `<실행 ID>.json`으로 쓴다(research R-10 파일 이름 규칙). contracts/cli.md 2절과 quickstart H06에 적었다.
  - 중간 2: SC-008 기록 문장 검사가 손으로 만든 기록만 봤다. `test_eval_cli.py`와 `tests/localdb/evaluation/test_eval_run.py`가 실제로 쓴 기록 파일을 검사한다.
  - 낮음 3: `tables`에 같은 기록 두 번(`duplicate_run`), 고른 대상이 없는 기록(`target_not_in_record`)을 종료 2로 거부한다.
  - 낮음 4: 자료원 머리 정보가 불량이면 근거 문서의 자료원 대조를 건너뛰고, `label_terms` 형식 오류면 `form_fields`를 붙이지 않는다(오류 하나에 규칙 하나).
  - 낮음 5: 기록 읽기가 값 형식도 검사한다(종료 2 `record_invalid`). 낮음 6: 위치 없는 노출 자료는 실행 전 `document_location_missing`으로 거부한다(`TargetDescription.unlocated_documents`, data-model 2절).
  - 낮음 7: 분류별 표 제목에 "(공통 질문 집합)"·"(대상별)"을 적는다. 낮음 8: 키워드 전용 기록의 `usage_target`은 `null`(contracts/run-record.md 2절).
  - 낮음 9: T029의 설정·정책 오류 종료 2와 T020의 "실행 전 검사 실패에서 장부 읽기 0"을 CLI 시험으로 더했다(`test_config_and_policy_errors_exit_2`, `test_precheck_failures_read_no_ledger_and_call_no_provider`).
  반영분은 다시 검토받지 않았다.
- 2026-10-31 검토 반영 뒤 기본 검증 전체 다시 실행: preflight 998개 통과, `git diff --check`, ruff check·format --check 통과, `QK_REQUIRE_LOCALDB=1 uv run pytest` 3,776 passed(3 deselected는 `external`).
