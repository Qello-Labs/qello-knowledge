---
description: "QK-CHK-001 구현 작업 목록"
---

# Tasks: QK-CHK-001 코드 청커·코드 메타데이터

**Input**: `specs/QK-CHK-001-code-chunker/`의 plan.md, spec.md, research.md(R-01~R-15), data-model.md, contracts/chunker.md, quickstart.md

**Tests**: 포함한다. 명세의 수용 시나리오와 C-12(수용 기준은 검증으로 닫는다)가 자동 시험을 요구한다. 시험을 먼저 쓰고 실패를 확인한 뒤 구현한다.
모든 시험은 외부 호출 0건이다(가짜 제공자·가짜 저장소, 0 Neurons). 대상 저장소 실측과 성능 완료 판정은 맨 끝 "사람 단계"다.

**Organization**: 사용자 스토리별 단계로 나눈다. 순서는 P1(US1 → US2 → US3 → US6) 다음 P2(US4 → US5 → US7)다.
US6(켜기 설정)은 P1이지만 코드 청킹 규칙 버전의 재료가 US1~US3 규칙이라 그 뒤에 한다.

**선행 조건**:
- spec.md 재승인·plan.md 승인(2026-10-26, tree-sitter 의존성 채택 포함)
- 이 목록의 사람 승인, `TASK.md` Scope·완료 조건 갱신과 재승인(AGENTS.md 1절)
- 단계 게이트 1.G는 미완료다. 구현 시작 시점은 이 목록 승인 때 사람이 정한다(TASK.md)

**공통 규칙**:
- 비노출: 본문·시그니처·심볼 이름·표시 이름·검색 헤더·임베딩 입력 텍스트·`locator["code"]`를 로그·예외 문구·결과 요약에 넣지 않는다(spec FR-007).
- 합성 자료만: 시험용 합성 Java·Kotlin 파일만 쓴다. 대상 저장소 원문을 저장소에 복사하지 않는다(AGENTS.md 6절).
  비밀값 모양 문자열은 `tests/unit/synthetic_secrets.py` 도우미로 실행 중에 만든다. 저장소 파일에 리터럴로 쓰지 않는다. 커밋 전에 `python scripts/preflight.py`의 종료 코드를 확인한다(QK-GEN-001 0352f1b 교훈).
- 기대값 JSON:
  - 사람이 정하는 정답이다. 구현 결과로 덮어쓰지 않는다(AGENTS.md 9절).
  - 단계마다 키를 **더하기만** 한다. 그 단계가 만드는 값의 키만 넣고, 뒤 단계가 그 단계 키를 앞 단계 픽스처에도 더한다.
  - 단계 중 비교는 기대 JSON에 있는 키만 한다. 모든 필수 키 검사는 T047에서 한다(QK-CHK-002 tasks T011·T037과 같은 방식).
  - 이 픽스처는 청커의 결정적 수용 시험용 합성 자료다. 검색 품질 평가 세트·정답 라벨(QK-EVL-001)이 아니며, 이 작업에서 평가 세트를 바꾸지 않는다(AGENTS.md 3.4).
- 통과 방식: 시험을 지우거나 `skip`·`xfail`로 체크포인트를 통과시키지 않는다. 경고를 suppress하지 않는다. 새 `# noqa`가 필요하면 멈추고 사람에게 묻는다.
- 기존 시험: 기댓값을 바꾸지 않는다(plan "구현 Scope" 표). 다음 시험은 그대로 통과해야 한다.
  - `tests/unit/sync/test_keys.py`, `tests/unit/indexer/test_sync_cli_settings.py`
  - `tests/unit/chunking/test_keyword_rule_version.py`, `tests/unit/devtools/test_measure.py`
  - QK-CHK-002 Markdown 기대값 시험 전체
  - 기존 공용 시험 도우미(`tests/unit/sync/helpers.py`, `tests/localdb/*/conftest.py`)도 바꾸지 않는다. 코드 자료용 조립 함수는 새 시험 파일 안에 둔다.
- 시험 파일 이름: 새 파일은 `test_code_` 접두어를 쓴다. `__init__.py`가 없는 폴더(`tests/unit/config`·`indexer`·`sources`, `tests/localdb/*`)에서 pytest 수집 이름이 겹치지 않게 하려는 것이다.
- 경로 비교: 경계 시험의 경로 비교 문자열은 `as_posix()`나 `replace("\\", "/")`로 정규화한다. 이 PC(Windows)의 기존 기준선 실패 3건 말고 새 실패를 만들지 않는다.
- 지연 가져오기: `tree_sitter*`는 `src/qello_knowledge/chunking/code/parse.py`의 함수 안에서만 가져온다(research R-01·R-15).
- 텍스트 형식: 코드 청크 텍스트는 contracts/chunker.md 8절 형식을 따른다. 기존 `chunking/header.py`의 `search_text`·`embedding_text`를 그대로 다시 쓴다.
- **실행 전 사람 허용**이 필요한 작업:
  - T001: `uv lock`·`uv sync`가 PyPI에서 휠을 내려받는다.
  - T032: `.env.example` 재생성은 `.env.*` 쓰기다.

  실행 에이전트는 그 명령 직전에 멈추고 허용을 받는다.

**TDD 순서**: 각 단계에서 시험 작업을 먼저 쓰고 실패(아직 없는 모듈이면 수집 오류 포함)를 확인한 뒤 구현 작업을 한다. [P]는 같은 단계의 시험끼리, 구현끼리 병렬이라는 뜻이다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 다루고 미완료 작업에 기대지 않아 병렬로 할 수 있다
- **[Story]**: 해당 사용자 스토리(US1~US7)

---

## Phase 1: Setup

- [X] T001 `pyproject.toml`·`uv.lock`에 의존성을 더한다(research R-01, **실행 전 사람 허용**: `uv lock`·`uv sync`가 PyPI에서 휠을 내려받는다).
  - `[project.optional-dependencies] index`와 `[dependency-groups].dev`에 `"tree-sitter==0.26.0"`, `"tree-sitter-java==0.23.5"`, `"tree-sitter-kotlin==1.1.0"`을 더한다.
  - 기존 `markdown-it-py==4.2.0`과 런타임 `dependencies = []`는 그대로 둔다.
  - `uv lock`으로 잠금 파일을 갱신하고 `uv sync --locked`를 한다.
  - `uv run python -c "import importlib.metadata as m; print([m.version(p) for p in ('tree-sitter','tree-sitter-java','tree-sitter-kotlin')])"`가 `['0.26.0', '0.23.5', '1.1.0']`인지 확인한다.
  - `uv.lock`에 세 패키지의 `manylinux2014_x86_64`·`aarch64` 휠 항목이 있는지 실행 기록에 적는다.
- [X] T002 [P] `tests/unit/chunking/code/__init__.py`(빈 파일)와 `tests/unit/chunking/code/helpers.py`: 픽스처 읽기 도우미를 만든다.
  - 입력: `tests/fixtures/chunking/code/<이름>.java|.kt`와 `<이름>.expected.json` 쌍. 기대 JSON은 `input`(가짜 위치 `location`, 시험용 `code_settings` 덮어쓰기, `keyword_text_rule`)과 `expected`다.
  - `chunk_code(body, location=..., settings=ChunkingSettings(keyword_text_rule=...), code=CodeChunkingSettings(...))` 결과를 `expected`와 비교한다.
  - 비교 대상: 결과 종류, 실패 유형, `document_title`, 경고(종류·줄), 청크별 `ordinal`·`lines`·`heading_path`·`locator["code"]`·`search_header`·`search_text`·`embedding_text`.
  - 비교 규칙: `expected`에 있는 키만 비교한다. `locator["code"]`는 들어 있는 하위 키만 비교한다.
- [X] T003 [P] `tests/unit/test_boundaries.py`에 검사를 더한다(검사 추가만, research R-15).
  - `tree_sitter`·`tree_sitter_java`·`tree_sitter_kotlin` 가져오기는 `chunking/code/parse.py`에서만 허용한다.
  - `domain`·`ports`·`embedding`·`query`·`retrieval`·`generation`은 `qello_knowledge.chunking.code`를 가져오지 못한다.
  - 위반 검출 시험을 더한다(일부러 만든 위반 파일 3개). 비교 문자열은 `as_posix()`로 정규화해 Windows에서도 통과하게 한다.
  - 기존 검사 함수와 기대값은 바꾸지 않는다.

**Checkpoint**: 의존성 설치, 새 경계 시험 통과(Windows 기준선 3건은 그대로)

---

## Phase 2: Foundational (모든 스토리의 선행)

- [X] T004 [P] `tests/unit/chunking/code/test_code_domain.py`: data-model 규칙을 시험한다.
  - `CodeChunkingSettings`: 기본값은 `model_version="@cf/baai/bge-m3"`, `target_tokens=512`, `limit_tokens=1500`이다.
    다음 경우는 `ValueError`다: `model_version`이 `MODELS`에 없음, `1 ≤ target_tokens ≤ limit_tokens`가 아님, `limit × bytes_per_token_estimate ÷ WORST_BYTES_PER_TOKEN > max_input_tokens`.
  - `CodeChunkKind`: 값 11개(`FILE_HEAD`, `FILE_SUMMARY`, `TYPE_SUMMARY`, `TYPE_HEAD`, `METHOD`, `CONSTRUCTOR`, `TOP_FUNCTION`, `FIELDS`, `TOP_PROPERTIES`, `INITIALIZER`, `FALLBACK`)다.
  - `AndroidComponent`: 값 8개다.
  - `StructureWarningKind`: `PARSE_FALLBACK`·`CONTEXT_OMITTED`가 더해지고 기존 두 값은 그대로다.
  - `ChunkingSettings`: `asdict` 결과가 지금과 같은 4개 키다(plan 검토 H1).
  - `ChunkingSummary` 기본값: `code_chunking_version=None`, `by_code_kind` 빈 값, `code_test_chunks=0`, `code_components` 빈 값.
  - `from_results(results)`: 지금과 같다(결과 0개면 `chunking_version == ""`). `from_results(results, chunking_version=..., code_chunking_version=...)`는 넘긴 값을 쓴다(research R-10).
  - 코드 수치 셈(2026-10-26 사용자 결정): 합성 `ChunkedContent`로 확인한다.
    - `by_code_kind`: 코드 청크의 `locator["code"]["chunk_kind"]`별 수다.
    - `code_test_chunks`: `test_code`가 참인 청크 수다.
    - `code_components`: 형식 머리 청크의 첫 조각에서만 형식 컴포넌트를 세고, Composable은 메서드·최상위 함수 청크의 첫 조각에서만 센다. 멤버 청크·요약·뒤 조각은 세지 않는다.
- [X] T005 `src/qello_knowledge/domain/chunking.py`에 타입과 셈을 더한다(추가만, T004 통과).
  - 타입: `CodeChunkingSettings`(검증은 `__post_init__`), `CodeChunkKind`, `AndroidComponent`, 경고 두 값.
  - `ChunkingSummary`: 새 필드와 `from_results` 키워드 인자, 위 셈 규칙. "첫 조각"은 `locator["code"]`의 같은 심볼 경로 연속 조각 중 첫 청크다.
  - `ChunkingSettings`와 기존 필드·검증은 바꾸지 않는다. 표준 라이브러리만 쓴다.
- [X] T006 [P] `tests/unit/chunking/code/test_code_version.py`: 버전 함수를 시험한다(contracts 1~3절, research R-08·R-09).
  - `code_chunking_version(code, settings)`: `chk-code-` 뒤에 16진수 12자리가 붙고, 같은 설정이면 같은 값이다.
  - 재료 항목을 하나씩 바꾸면 값이 바뀐다. 재료는 research R-08 전체다.
    - 판수: 규칙·헤더 형식·키워드 텍스트 형식·임베딩 입력 형식 판수, 맥락 줄 생략·대체 청킹 전환·요약 생략 규칙 판수
    - 설정: 상한, 목표, 모델, `WORST_BYTES_PER_TOKEN`, 키워드 규칙
    - 해석기 버전 상수 셋, 사본 규칙 식별자
    - 목록: `ANDROID_BASES`, `COMPONENT_SUFFIXES`, `TEST_SOURCE_SETS`, `TEST_ANNOTATIONS`
  - 첫 값은 T038 뒤에 계산해 상수로 고정한다. 그 전에는 형식·결정성·재료 민감도만 단언한다.
  - `PARSER_VERSIONS` 상수가 `importlib.metadata.version()`과 같다.
  - 새 프로세스에서 `code_chunking_version`·`index_chunking_version`·`metadata_schema_version`을 계산한 뒤 `sys.modules`에 `tree_sitter`가 없다(plan 재검토 N1).
  - `index_chunking_version(ChunkingSettings())`: `chk-md-20d966f730bb`, 켜짐이면 `chk-md-20d966f730bb+chk-code-…`다. `metadata_schema_version(None)`은 `meta-v1`, 켜짐이면 `meta-v2`다.
  - 인덱스 버전(spec SC-010·SC-011): 꺼짐이면 `index_version_id("@cf/baai/bge-m3", 1024, index_chunking_version(ChunkingSettings()), metadata_schema_version(None))`가 `iv-4c0bc4fcc642`다.
    켜짐 값은 다르고, Markdown·코드 버전 중 하나만 바꿔도 바뀐다.
- [X] T007 `src/qello_knowledge/chunking/code/version.py`·`chunking/version.py`·`sync/keys.py`: 버전 함수와 규칙 상수를 만든다(T006 통과).
  - `src/qello_knowledge/chunking/code/__init__.py`
  - `src/qello_knowledge/chunking/code/version.py`: `code_chunking_version`, 판수 상수, `PARSER_VERSIONS`. 규칙 상수 `ANDROID_BASES`·`COMPONENT_SUFFIXES`·`TEST_SOURCE_SETS`·`TEST_ANNOTATIONS`, 사본 규칙 식별자 `suspend-lambda-v1`과 그 정규식도 여기 둔다. 값은 data-model 상수 표 그대로이고, 뒤 작업(T009·T035)이 여기서 가져다 쓴다.
  - `src/qello_knowledge/chunking/version.py`: `index_chunking_version`과 `version_for`를 더한다. 기존 `chunking_version`은 한 글자도 바꾸지 않는다.
    코드 청킹 대상 판정은 함수 `is_code_target(content, code)` 하나로 두고, `version_for`와 `chunk_screened`가 함께 쓴다.
  - `src/qello_knowledge/sync/keys.py`: `metadata_schema_version(code)`를 더한다. 기존 `index_version_id`·`METADATA_SCHEMA_VERSION`은 그대로다.
  - 가져오기 방향은 `chunking/version.py` → `chunking/code/version.py` → `domain`이다. `chunking/code/*`는 `qello_knowledge.chunking`(패키지 `__init__`)을 가져오지 않는다. 버전 계산은 `tree_sitter`를 가져오지 않는다.
- [X] T008 [P] `tests/unit/chunking/code/test_code_parse.py`: 해석 경계를 시험한다(research R-01).
  - 해석용 사본은 원문과 바이트 길이가 같다. `suspend {`, `suspend{`, 줄 바꿈 뒤 `{`는 바뀌고, `suspend fun`, `suspend () -> T`, `_suspend {`, `xsuspend {`는 바뀌지 않는다.
  - 문장 맨 앞 `suspend { … }` 람다가 든 합성 Kotlin ViewModel이 오류 없이 해석된다. 괄호 불일치 Java·Kotlin은 `has_error`로 판정된다.
  - `parse.py`를 가져오는 것만으로는 `tree_sitter`가 불러와지지 않고, 처음 해석할 때 불러와진다(새 프로세스).
  - 해석기 적재 실패를 흉내 내면(가져오기 함수 주입) 예외가 호출자에게 전달된다.
- [X] T009 `src/qello_knowledge/chunking/code/parse.py`: 언어별 해석기를 함수 안에서 지연 생성하고 한 번만 만든다(T008 통과).
  - `parse(source: bytes, language) -> tree`: Kotlin은 `chunking/code/version.py`의 사본 정규식을 쓴다.
  - `has_error`를 둔다. 노드 위치는 원문 바이트·줄에 그대로 쓴다.
- [X] T010 [P] `tests/unit/chunking/code/test_code_dispatch.py`: 나눠 주기를 시험한다(contracts 6절). `chunk_code`는 monkeypatch로 바꿔 호출 여부와 인자만 확인한다.
  - 꺼짐: `chunk_screened(passed, settings)`(위치 인자 그대로)는 `.java`·`.kt` 코드 자료를 `NOT_MARKDOWN`·청크 0개로 돌려준다. 새 프로세스에서 `tree_sitter`를 가져오지 않는다(spec US6-2).
  - 켜짐: `code=CodeChunkingSettings()`이면 `.java`·`.kt`만 `chunk_code`를 부른다. `.py`·`.kts`·`.gradle`·`JSON`·`TEXT`는 `NOT_MARKDOWN`이다.
  - `code.model_version != settings.model_version`이면 시작 전 `ValueError`다. `code`는 키워드 전용이다.
  - Markdown 자료의 결과는 꺼짐·켜짐에서 같다(spec FR-002).
  - 요약 `chunking_version`은 결과가 있으면 `index_chunking_version`이고, 결과 0개면 `""`다(plan 재검토 N8).
- [X] T011 `src/qello_knowledge/chunking/service.py`·`src/qello_knowledge/chunking/__init__.py`를 고친다(T010 통과).
  - `chunk_screened(..., *, code=None)`에 `is_code_target` 나눠 주기와 요약 인자를 넣는다.
  - `chunk_code`·`code_chunking_version`·`index_chunking_version`·`version_for`를 공개한다.
  - 이 단계의 `chunk_code`는 `chunking/code/service.py`의 빈 뼈대(`PROCESSING_ERROR`)다. Markdown 경로는 바꾸지 않는다.

**Checkpoint**: `uv run pytest tests/unit/chunking tests/unit/test_boundaries.py -q`에서 기존 Markdown 시험을 포함해 통과(Windows 기준선 3건 제외)

---

## Phase 3: User Story 1 - 메서드 하나를 물으면 그 메서드 청크가 출처로 나온다 (P1) 🎯 MVP

**Goal**: 형식 선언·멤버 경계의 원문 청크, 심볼 경로, 검색 헤더·맥락 줄, 재현성·국소성(spec FR-008~012, FR-020·021·022, US1)

**Independent Test**: 기대값 픽스처와 불변식 시험(원문 대조·줄 덮기·결정성·국소성)

- [X] T012 [P] [US1] `tests/fixtures/chunking/code/`에 합성 픽스처와 사람이 쓴 기대 JSON을 만든다.
  - 작성 규칙: 기대 JSON은 구현을 부르지 않고 원문, spec 규칙, contracts 8절 형식으로 직접 쓴다.
  - 이 단계 키: 결과 종류, `document_title`, `warnings`, 청크별 `ordinal`·`lines`·`heading_path`·`search_header`·`search_text`·`embedding_text`, `locator["code"]`의 `language`·`package`·`symbol`·`signature`·`chunk_kind`·`summary`.
  - 픽스처 목록:
    - `java_three_methods.java`: 문서 주석·어노테이션 붙은 메서드 3개, 클래스 닫는 줄은 마지막 메서드 청크
    - `java_controller.java`: 클래스 `@RequestMapping("/orders")`와 메서드
    - `java_nested.java`: 바깥·중첩 클래스와 메서드
    - `java_file_head.java`: 라이선스 주석, `package`, `import` 묶음
    - `java_comments.java`: 멤버에 붙은 주석과 떨어진 주석, 멤버 사이 빈 줄
    - `java_fields.java`: 연속 필드, 목표 크기를 넘는 필드 묶음, 형식 머리와 첫 필드 묶음 합치기, 형식 머리만으로 목표 이상이라 합치지 않는 사례
    - `java_multi_types.java`: 한 파일 최상위 형식 여럿
    - `kotlin_class.kt`: 주 생성자, 메서드, `companion object`
    - `kotlin_top_level.kt`: 최상위 함수·프로퍼티, 블록 본문
    - `java_package_boundary.java`: 위치 `x/a/bc/A.java`, 패키지 `a.b`. 경계가 맞지 않아 패키지가 헤더에 남는다
    - `java_package_in_path.java`: 위치 `src/main/java/a/b/A.java`, 패키지 `a.b`. 헤더에서 패키지가 빠진다(spec FR-021)
    - `java_idsplit.java`: `java_three_methods`와 같은 원문에 `keyword_text_rule = "kw-index-idsplit-v1"`. 분해 낱말 줄이 붙는다(spec FR-022)
- [X] T013 [P] [US1] `tests/unit/chunking/code/test_code_expected.py`: T012 픽스처를 T002 도우미로 비교한다(spec SC-001). `expected`에 있는 키만 비교하고, 필수 키 검사는 T047에서 한다.
- [X] T014 [P] [US1] `tests/unit/chunking/code/test_code_invariants.py`: 모든 코드 픽스처에서 불변식을 확인한다(spec SC-001·SC-002).
  - 원문 대조: 원문 청크(`locator["code"]["summary"] == False`) 본문이 `locator["lines"]` 범위의 원문과 같다.
  - 줄 덮기: 공백 아닌 원문 줄이 정확히 한 원문 청크에 든다.
  - 저장 검증: `ordinal`이 0부터 빈틈없고, QK-STO-001 `validate_chunks`를 통과한다.
  - 버전: `draft.chunk.chunking_version == code_chunking_version(code, settings)`다. `EMPTY`·`FAILED` 결과의 `chunking_version`도 같은 값이다.
  - 결정성: 같은 입력을 두 번, 순서를 섞어 한 번 더 돌려도 결과가 같다. CRLF·LF·BOM 차이에도 결과가 같다(US1-8).
  - 헤더: `embedding_text`와 `search_text`가 `search_header`로 시작한다.
- [X] T015 [P] [US1] `tests/unit/chunking/code/test_code_locality.py`: 국소성을 시험한다(spec SC-003, FR-011, US1-4·6). 요약 청크 관련 단언은 T021에서 한다.
  - 메서드 본문 줄(시그니처 줄이 아닌 줄)만 고친 판은 그 메서드 청크만 바뀐다.
  - 매개변수를 바꾼 판은 그 메서드 원문 청크만 바뀐다(원문 청크 기준).
  - 클래스 어노테이션을 고친 판은 그 클래스 모든 청크의 `embedding_text`가 바뀐다.
  - 멤버 문서 주석만 고친 판은 그 멤버 청크만 바뀐다.
  - 위치를 바꾼 판은 모든 청크의 검색 헤더가 바뀐다.
- [X] T016 [US1] `src/qello_knowledge/chunking/code/units.py`: research R-05 노드 대응표대로 원문 청크 단위를 만든다.
  - 단위: 파일 머리, 형식 선언 머리, 메서드·생성자·초기화 블록·최상위 함수, 필드·프로퍼티 묶음. 중첩 형식은 재귀로 처리한다.
  - 주석: 멤버 앞에 이어 붙은 주석은 그 멤버 청크에 넣는다. 떨어진 주석과 형식 닫는 줄은 앞 청크에 붙인다.
  - 필드 묶음: 목표 크기까지 탐욕으로 쌓는다.
  - 형식 머리와 첫 필드 묶음 합치기: 머리 줄을 크기에 넣고, 머리만으로 목표 이상이면 합치지 않는다(spec FR-010).
  - 표에 없는 노드는 앞 청크에 붙인다.
- [X] T017 [US1] `src/qello_knowledge/chunking/code/symbols.py`: 이름·심볼 경로·시그니처를 만든다(research R-06).
  - 심볼 이름에 매개변수 형식 목록을 붙인다. 각 형식은 형식 노드 전체 원문에서 형식 어노테이션·수식어(`final`·`vararg`)·이름·기본값을 빼고 공백을 지운 값이다.
    가변 인자는 `형식...`으로 쓰고 nullable `?`는 남긴다.
  - Kotlin 확장 함수는 이름 앞에 수신 형식을 붙이고, 백틱 이름은 백틱을 뺀다.
  - 생성자 이름은 형식 이름이고, 초기화 블록은 `<init>`·`<clinit>`이다.
  - 심볼 경로는 spec FR-020 표를 따른다.
  - 시그니처는 선언 어노테이션과 본문을 뺀 원문을 공백 하나로 정리한 값이다. 시그니처 줄은 선언 시작부터 본문 여는 줄까지다(spec FR-013).
- [X] T018 [US1] `src/qello_knowledge/chunking/code/header.py`: contracts 8절 형식대로 검색 헤더, 맥락 줄, 반복 줄을 만든다.
  - 헤더 앞 줄: `<위치> <언어>[ <패키지>]`. 패키지는 `"/" + 패키지 경로 + "/"`가 `"/" + 위치`에 있으면 뺀다.
  - 헤더 둘째 줄: `<심볼 경로 " > ">` 뒤에 `[<CodeChunkKind 값>]`와 `[ <표시 이름>]`이 온다. 심볼 경로가 비면 `[<CodeChunkKind 값>]`만 쓴다. 끝 줄 바꿈은 없다.
  - 맥락 줄은 바깥 형식부터 선언 어노테이션과 선언 줄이다. 형식 머리·요약 청크에는 바깥 것만 붙인다.
  - 임베딩 입력은 기존 `chunking.header.embedding_text(header, prefix, body)`로 만든다. `prefix`는 맥락 줄·반복 줄을 `\n`으로 이은 값이고, 없으면 `""`다.
  - 키워드 텍스트는 기존 `chunking.header.search_text(header, context_and_body, rule)`로 만든다. `context_and_body`는 맥락 줄 + `\n` + 본문이고, 맥락 줄이 없으면 본문이다. 기존 함수는 바꾸지 않는다(spec FR-022).
- [X] T019 [US1] `src/qello_knowledge/chunking/code/service.py`: `chunk_code`를 구현한다(contracts 5절 1~3·5·6항, T013~T015 통과).
  - 전처리: 줄 바꿈을 LF로 바꾸고 앞 BOM을 뺀다. 공백만 있으면 `EMPTY`이고, `chunking_version`은 코드 버전이다(`sync/execute.py:159`가 이 값을 저장한다).
  - 순서: 해석 → 단위 → 심볼 → 헤더로 만들고 순서 번호를 매긴다(spec FR-012).
  - `locator`: `{"path", "lines", "code"}`. `code` 메타데이터는 이 단계에서 `language`·`package`·`symbol`·`signature`·`chunk_kind`·`summary`만 채우고, 나머지 키는 빈 값이다(뒤 단계에서 채운다).
  - `document_title`은 파일 이름이다.
  - 오류: 내부 예외와 해석기 적재 실패는 `FAILED`·`PROCESSING_ERROR`다.

**Checkpoint**: US1 픽스처·불변식·국소성 시험 통과, QK-CHK-002 시험 그대로 통과

---

## Phase 4: User Story 2 - 클래스 요약으로 "이 클래스에 뭐가 있어?"에 답한다 (P1)

**Goal**: 형식 요약·파일 요약과 생략 규칙(spec FR-012~015, US2)

**Independent Test**: 요약 픽스처 기대값 비교와 요약 줄 불변식

- [X] T020 [P] [US2] `tests/fixtures/chunking/code/`: 요약 픽스처와 기대 JSON을 만든다. T012 픽스처 가운데 요약이 생기는 것의 기대 JSON에도 요약 청크를 더한다(순서 번호도 함께 고친다).
  `java_summary_split`은 상한 초과 나누기(T038) 전에 쓰이므로 요약 말고 다른 원문 청크는 모두 상한 이하로 만든다.
  - `java_summary_basic.java`: 필드 2, 생성자 1, 메서드 3(US2-1·2)
  - `java_summary_split.java`: 시험용 작은 상한으로 요약이 나뉘고 뒤 조각에 선언 줄이 반복된다(US2-3)
  - `kotlin_slugs.kt`: 블록 본문 최상위 함수 2와 프로퍼티 1(US2-4)
  - `kotlin_constants.kt`: 최상위 프로퍼티·한 줄 함수만 있어 파일 요약이 없다(spec FR-014)
  - `java_nested_summary.java`: 메서드를 가진 중첩 클래스(US2-5)
  - `java_container.java`: 중첩 형식만 담은 컨테이너라 요약이 있다(spec FR-013)
  - `java_dto_record_interface.java`: DTO·레코드·추상 메서드 인터페이스라 요약이 없고, 형식 머리와 첫 필드 묶음이 합쳐진다(US2-6)
  - `java_one_line_body.java`: 한 줄 본문 선언(Edge Cases)
  - `java_multiline_field.java`: 여러 줄 필드 초기값. 요약에는 첫 줄만 들어간다(spec FR-013)
- [X] T021 [P] [US2] `tests/unit/chunking/code/test_code_summary.py`: T020 픽스처를 비교하고 요약 불변식을 확인한다(spec SC-002).
  - 요약 본문의 모든 줄이 형식 범위 안의 원문 줄이다. 시그니처 줄이 아닌 메서드 본문 줄이 없다.
  - 요약 `lines`는 형식 전체 범위다.
  - 순서(spec FR-012): 요약이 그 형식의 첫 원문 청크 바로 앞에 오고, 파일 요약은 파일 머리 다음에 온다.
  - 국소성(T015에서 옮김, spec SC-003·US1-5): 메서드 본문 줄만 고친 판은 요약이 그대로다. 매개변수를 바꾼 판은 요약이 바뀐다.
- [X] T022 [US2] `src/qello_knowledge/chunking/code/units.py`·`service.py`: 요약 청크를 만든다(spec FR-013~015, T020·T021 통과).
  - 조건: 본문 있는 멤버가 있을 때만 만든다. 본문 줄이 시그니처 밖에 있는 메서드·생성자·초기화 블록과 중첩 형식이 본문 있는 멤버다.
  - 내용: 형식의 문서 주석·어노테이션·선언 줄, 필드 선언 첫 줄, 멤버의 선언 어노테이션·시그니처 줄.
  - Kotlin 파일 요약: 블록 본문 최상위 함수가 있을 때만 만든다.
  - 나누기: 상한을 넘으면 멤버 경계에서 나누고, 뒤 조각의 임베딩 입력에 선언 줄을 반복한다.
  - `locator["code"]["summary"] = True`를 단다.

**Checkpoint**: US1·US2 시험 통과

---

## Phase 5: User Story 3 - 코드 메타데이터로 청크가 무엇인지 안다 (P1)

**Goal**: `locator["code"]` 전체와 저장 후 출처 정보(spec FR-020·023·026, US3)

**Independent Test**: 메타데이터 픽스처 비교와 로컬 DB 왕복

- [X] T023 [P] [US3] `tests/fixtures/chunking/code/`: 메타데이터 픽스처와 기대 JSON을 만든다(spec SC-006). 앞 단계 픽스처의 기대 JSON에 `type_kind`·`type_modifiers`·`annotations` 키를 더한다.
  - `java_metadata.java`: 다음을 담는다.
    - 선언·매개변수 어노테이션, 패키지까지 쓴 어노테이션
    - 제네릭, 연속 오버로드 `find(Long)`·`find(String)`, 가변 인자
    - 열거형, 레코드, 초기화 블록(`static`·인스턴스)
  - `kotlin_metadata.kt`: 다음을 담는다.
    - 확장 함수 `String.toSlug()`, `suspend`, nullable
    - 함수 형식 매개변수 `() -> Unit`·`@Composable () -> Unit`, 백틱 이름
    - `data`·`sealed` 수식어, `companion object`
- [X] T024 [P] [US3] `tests/unit/chunking/code/test_code_metadata.py`: T023을 비교하고 `locator["code"]`의 키 13개가 모두 있는지 확인한다(data-model 표). 연속 오버로드의 심볼 경로가 서로 다르고, `locator`가 `json.dumps`로 그대로 직렬화되는 평범한 dict인지도 본다.
- [X] T025 [P] [US3] `tests/localdb/retrieval/test_code_provenance.py`: 로컬 DB 왕복을 시험한다(spec SC-006, US3-5).
  - 준비: 기존 `tests/localdb/retrieval/conftest.py`의 `store`·`db_url` 픽스처를 쓴다. 새 conftest와 새 `# noqa`는 만들지 않는다. 모듈에 `pytestmark = pytest.mark.localdb`를 단다.
  - 켜짐 설정의 코드 청크와 Markdown 청크를 저장한다(가짜 임베딩).
  - 검색(벡터·키워드), 문맥 확장(`chunk_context`), 청크 추적 결과의 `Provenance.locator["code"]`와 `heading_path`가 저장 전 값과 같다.
  - Markdown 청크의 `locator`·출처 정보는 바뀌지 않는다.
  - 마이그레이션: 이 변경이 `adapters/postgres/migrations/`에 새 파일을 더하지 않는다. 디렉터리 목록을 `git ls-files`의 기준 커밋 목록과 비교하며, 개수를 숫자로 고정하지 않는다.
- [X] T026 [US3] `src/qello_knowledge/chunking/code/symbols.py`·`service.py`: 메타데이터를 채운다(T023~T025 통과).
  - `type_kind`·`type_modifiers`를 채운다.
  - `annotations`는 선언에 직접 붙은 어노테이션의 단순 이름이다. 매개변수 어노테이션은 넣지 않는다.
  - `test_code`·`test_method`·`display_name`·`component`는 US4에서 채운다.

**Checkpoint**: US1~US3 시험과 로컬 DB 왕복 통과

---

## Phase 6: User Story 6 - 코드 청킹은 켜기 전까지 운영 색인을 바꾸지 않는다 (P1)

**Goal**: 켜기 설정, 동기화 연결, 인덱스 버전, 켜짐 방지(spec FR-028~030, US6, SC-011)

**Independent Test**: 꺼짐 불변(고정값 시험 그대로), 켜짐 계산·계획, 대응표 없는 켜짐 차단

- [X] T027 [P] [US6] `tests/unit/sync/test_code_sync_versions.py`: 동기화 연결을 시험한다(research R-09·R-10).
  - 조립 함수: 이 파일 안에 둔다. `helpers.py`는 바꾸지 않는다. 도우미의 가짜 저장소(`tests/unit/sync/fake_store.py`)를 쓰고, 다음을 직접 조립한다.
    - CODE 형식 자료와 `**/*.java` 범위
    - 호출을 기록하는 outgoing check
    - `SyncDependencies(..., code_chunking=...)`
  - `version_for`: 코드 대상이면 코드 버전, 아니면 Markdown 버전이다.
  - `SyncDependencies`를 기존 위치 인자로 만들면 `code_chunking is None`이다.
  - `current_spec` 꺼짐: `IndexSpec("iv-4c0bc4fcc642", "@cf/baai/bge-m3", 1024, "chk-md-20d966f730bb", "meta-v1")`이다.
  - `current_spec` 켜짐: id가 다르고, `metadata_schema_version == "meta-v2"`이며, `chunking_version`에 `+chk-code-`가 들어 있다.
  - 재계획(spec US6-4): 켜짐에서 코드·Markdown·빈 `.java` 문서가 섞인 자료원을 `run_sync`로 한 번 실행한다. 같은 저장소로 `plan_source`를 다시 계획하면 다시 처리로 판정된 문서가 0이다.
  - 요약: 실행 요약의 `chunking_version`은 첫 문서가 코드든 Markdown이든 같고, 결과 없는 계획은 `""`다.
- [X] T028 [P] [US6] `tests/unit/indexer/test_code_sync_cli.py`: CLI 연결을 시험한다(contracts 4절, plan 재검토 N3).
  - `current_index_version()`은 지금 값이고, `current_index_version(code=CodeChunkingSettings())`는 다르다.
  - `build_runtime`:
    - `chunking`을 명시하면(평가 준비) `QK_CODE_CHUNKING=on`이어도 `code_chunking is None`이다.
    - `code`를 명시하면 그 값이다.
    - 둘 다 없으면 설정에서 읽는다.
  - 읽기 명령: `index status`가 켜짐 설정의 현재 버전을 보고한다(가짜 저장소). `QK_CODE_CHUNKING`이 형식 오류면 설정 오류로 종료 코드 1이다.
- [X] T029 [P] [US6] `tests/unit/config/test_code_check.py`: 설정 검사를 시험한다(contracts 4절).
  - 값: `QK_CODE_CHUNKING`은 `off`·`on`만 받고, 다른 값은 설정 오류다. 기본은 `off`다.
  - 켜짐이고 `limit_tokens × MODELS[model].bytes_per_token_estimate ÷ RetrievalSettings.bytes_per_token > QK_RETRIEVAL_CONTEXT_BUDGET`이면 `CODE_LIMIT_OVER_CONTEXT_BUDGET`이다.
  - 켜짐 인덱스 버전이 `INDEX_KEYWORD_RULES`에 없으면 `CODE_INDEX_VERSION_UNREGISTERED`다. 시험용으로 대응표를 monkeypatch하면 통과한다.
  - 꺼짐이거나 문제가 없으면 검사 항목이 없다(기존 보고 꼴 유지).
  - `qk-index run`은 켜짐·미등록이면 원본 호출 0건으로 멈춘다(spec US6-5).
  - 질의 경로(plan 재검토 N2): 새 프로세스에서 `qello_knowledge.config.check`·`query.server`·`query.app`을 가져온 뒤, `sys.modules`에 `qello_knowledge.chunking`·`markdown_it`·`tree_sitter`가 없다. `query.worker`는 Workers 전용 `js`를 가져오므로 대상이 아니다.
- [X] T030 [US6] `src/qello_knowledge/sync/run.py`·`src/qello_knowledge/sync/plan.py`: 동기화를 연결한다(T027 통과).
  - `SyncDependencies`의 마지막 필드 `preflight` 뒤에 `code_chunking: object = None`을 더한다.
  - `current_spec`이 `index_chunking_version`·`metadata_schema_version`으로 `IndexSpec` 다섯 필드를 채운다(contracts 2절).
  - `plan.py:87`의 `change_reason` 버전을 `version_for(content, deps.chunking_settings, deps.code_chunking)`로 바꾼다.
  - `plan.py:99`는 `chunk_screened`에 `code=deps.code_chunking`을 넘긴다.
  - `plan.py:216`은 결과가 있을 때만 두 버전을 `from_results`에 넘긴다.
- [X] T031 [US6] `src/qello_knowledge/indexer/sync_cli.py`: CLI를 연결한다(T028 통과).
  - `current_index_version(chunking=None, code=None)`로 바꾼다.
  - `build_runtime(..., chunking=None, code=_UNSET)`: `chunking`을 명시하면 꺼짐이다.
  - `index status`·`index` 읽기 명령은 `writes`가 아니어도 `load(Entrypoint.INDEX, ...)`로 설정을 읽는다. 그리고 `config.check.code_chunking_from(settings)` 값을 쓴다. 형식 오류면 설정 보고를 출력하고 1로 끝난다.
- [X] T032 [US6] `src/qello_knowledge/config/registry.py`·`src/qello_knowledge/config/check.py`: 설정과 교차 검사를 더한다(T029 통과).
  - registry: `QK_CODE_CHUNKING`을 더한다(진입점 INDEX, 기본 `off`, 값 `off`·`on`).
  - check: `code_chunking_from(settings) -> CodeChunkingSettings | None`을 `generation_settings` 옆에 둔다.
  - 교차 검사 둘: `_generation_check`처럼 문제가 있을 때만 항목을 만든다. 함수 안에서 `chunking.version`·`chunking.code.version`·`sync.keys`·`domain.keyword_rules`를 가져오고, INDEX 진입점에서 켜짐일 때만 계산한다.
  - 그 뒤 `uv run python -m qello_knowledge.config.example`로 `.env.example`을 다시 만든다(**실행 전 사람 허용**). `tests/unit/config/test_example_file.py`가 통과하는지 확인한다.

**Checkpoint**: 기존 고정값 시험(`test_keys.py`, `test_sync_cli_settings.py`, `test_keyword_rule_version.py`, `test_measure.py`)과 US6 시험 통과

---

## Phase 7: User Story 4 - Android 컴포넌트와 테스트를 구분한다 (P2)

**Goal**: 컴포넌트·테스트 판정과 표시 이름(spec FR-021·024·025, US4)

**Independent Test**: Android·테스트 픽스처 비교

- [X] T033 [P] [US4] `tests/fixtures/chunking/code/`: Android·테스트 픽스처와 기대 JSON을 만든다(spec SC-007). 앞 단계 픽스처의 기대 JSON에도 `test_code`·`test_method`·`display_name`·`component` 키를 더한다.
  - Android: 다음 픽스처를 만든다.
    - `android_viewmodel.kt`: `androidx.lifecycle.ViewModel` 직접 상속과 `suspend { … }` 람다
    - `android_base_fragment.kt`: `androidx` import와 `BaseFragment` 상속
    - `android_composable.kt`: `@Composable` 최상위 함수
  - Android import가 없는 파일(컴포넌트 아님): 다음 픽스처를 만든다.
    - `spring_service_impl.java`: `extends BaseService implements OrderService`
    - `spring_activity_named.java`: `*Activity` 이름 상위 클래스
  - 테스트 경로 판정: 다음 픽스처를 만든다.
    - 위치가 `order/src/test/java/…`인 `test_display_name.java`: `@Test @DisplayName("…")`, `@ParameterizedTest`, `@Nested` 클래스 안의 `@Test`
    - 위치가 `src/integrationTest/…`·`src/androidTest/…`·`src/testFixtures/…`인 픽스처 각 1개
    - `test_helper_no_annotation.java`: 테스트 경로의 도우미 클래스
    - 위치가 `src/main/…`인 `abtest_main.java`: `class ABTest`
    - `kotlin_test_backtick.kt`: 백틱 이름 테스트 함수
- [X] T034 [P] [US4] `tests/unit/chunking/code/test_code_android_tests.py`: T033을 비교한다. 다음을 확인한다.
  - 컴포넌트 종류, `test_code`·`test_method`·`display_name`
  - 검색 헤더의 표시 이름
  - 형식의 컴포넌트가 멤버 청크에도 붙는지
- [X] T035 [US4] `src/qello_knowledge/chunking/code/symbols.py`·`header.py`·`service.py`: 판정을 구현한다(T033·T034 통과).
  - 컴포넌트: Android import가 있는 파일에서만 판정한다. 상위 클래스만 본다(Java `extends`, Kotlin `constructor_invocation`). `chunking/code/version.py`의 `ANDROID_BASES`·`COMPONENT_SUFFIXES` 이름 규칙과 `@Composable`을 쓴다.
  - 테스트 코드: 경로 구성 요소에 `TEST_SOURCE_SETS`가 있으면 테스트 코드다. 파일 이름으로는 판정하지 않는다.
  - 테스트 메서드: `TEST_ANNOTATIONS`가 붙은 메서드다(`@Nested` 클래스 안 포함).
  - 표시 이름: `@DisplayName` 값, 없으면 백틱 이름이다. 검색 헤더에 붙인다.
  - 요약 수치 셈은 T005에 이미 있다.

**Checkpoint**: US1~US4·US6 시험 통과

---

## Phase 8: User Story 5 - 코드 청크도 상한 안으로 나뉘고, 한 파일의 실패가 동기화를 멈추지 않는다 (P2)

**Goal**: 상한 초과 나누기, 맥락 줄 생략, 대체 청킹, 실패 격리(spec FR-016~019, US5)

**Independent Test**: 작은 시험용 상한의 크기·실패 픽스처

- [X] T036 [P] [US5] `tests/fixtures/chunking/code/`: 크기·실패 픽스처와 기대 JSON을 만든다. 기대 JSON에 시험용 상한·목표를 적는다(spec SC-005).
  - 상한 초과 나누기: 다음 픽스처를 만든다.
    - `size_big_method.java`: 상한 3배 메서드. 최상위 문장 경계에서 나뉘고, 뒤 조각에 시그니처가 반복되며, 닫는 줄은 마지막 조각에 있다
    - `size_big_enum.java`: 상수 줄만으로 상한을 넘는 열거형 머리
    - `size_big_imports.java`: `import`가 많은 파일 머리
  - 실패: 다음 픽스처를 만든다.
    - `size_line_too_long.java`: `LINE_TOO_LONG`
    - `size_header_too_long.java`: 아주 긴 위치나 심볼 경로로 `HEADER_TOO_LONG`
  - 경고: 다음 픽스처를 만든다.
    - `size_long_class_annotation.java`: 바깥 클래스의 긴 어노테이션 묶음 때문에 맥락 줄이 생략되고 `CONTEXT_OMITTED`가 붙는다(US5-6)
    - `fallback_unbalanced.java`·`fallback_unbalanced.kt`: 파일 전체 대체 청킹과 `PARSE_FALLBACK`
- [X] T037 [P] [US5] `tests/unit/chunking/code/test_code_size.py`: T036을 비교하고 다음을 확인한다.
  - 상한: 모든 청크의 `estimated_tokens(embedding_text) ≤ limit_tokens`이고, 잘린 원문 줄이 0이다.
  - 상한 이하 메서드는 나뉘지 않는다(SC-004).
  - `split_blocks`가 나뉜 원문 청크 수와 같다.
  - 대체 청크는 심볼 경로가 비고, 종류가 `FALLBACK`이며, 요약이 없다.
- [X] T038 [US5] `src/qello_knowledge/chunking/code/split.py`·`service.py`: 나누기·생략·대체·실패를 구현한다(research R-05·R-07, T036·T037 통과).
  - 상한 초과 나누기: 멤버는 본문 노드 바로 아래 문장이 끝나는 줄을 후보로 삼아 목표 근처의 마지막 후보에서 나누고, 후보가 없으면 줄 경계에서 나눈다. 반복 줄은 멤버면 시그니처 줄, 형식 머리·필드 묶음이면 선언 줄이다.
  - 맥락 줄 생략: 바깥 형식부터 생략하고 경고를 붙인다.
  - 실패: `HEADER_TOO_LONG`·`LINE_TOO_LONG`이면 파일 전체가 실패다.
  - 대체 청킹: `has_error`면 빈 줄 블록을 탐욕으로 쌓는다(spec FR-019).
  - 격리: `chunk_screened`에서 한 파일의 실패가 다른 파일을 멈추지 않는다.
  - 이 작업 뒤 T006의 `chk-code-` 첫 값을 계산해 상수로 고정한다.

**Checkpoint**: US1~US6 시험 통과, T006 첫 값 고정

---

## Phase 9: User Story 7 - 코드 자료원을 등록하고, 결정 기록과 사람 확인을 거쳐 켠다 (P2)

**Goal**: 비활성 코드 자료원 두 개와 결정 기록(spec FR-032~036, US7, SC-013)

**Independent Test**: 설정 검사와 범위 시험, 결정 기록 리뷰

- [X] T039 [P] [US7] `tests/unit/sources/test_code_sources.py`: 저장소의 실제 `config/sources.toml`로 다음을 확인한다(spec SC-013, plan 재검토 H2).
  - 원문 확인: `tomllib`로 원문을 읽어 `dnd-backend-code`·`dnd-android-code`가 `enabled = false`인지, `scope.repo`·`ref`·`include`가 research R-13 표와 같은지 확인한다.
  - 확장자 검사: `load_checked_sources(Path("config/sources.toml"), Path("config/source_reviews"))`로 하고, 오류가 0이어야 한다. 비활성 항목의 include가 실제로 되살아나 검사되는지(빈 include가 아닌지)도 단언한다.
  - 임시 복사본: 두 항목만 `enabled = true`로 바꾼 TOML을 `tmp_path`에 쓴다. `load_sources`로 읽었을 때 설정 오류(`auth`·`repo`·`ref`·`include` 형식)가 0이어야 한다. 확인 기록이 없다는 오류만 나는 것은 정상이다.
  - 범위 겹침: 원문에서 같은 `scope.repo`를 가진 자료원 쌍을 찾는다. `dnd-backend-docs`·`dnd-backend-code` 쌍이 정확히 1개 있는지 먼저 단언한 뒤, 두 포함 패턴의 확장자 집합이 겹치지 않는지 본다(research R-13).
  - 범위 불변: `dnd-backend-docs`의 원문 `scope`가 `config/source_reviews/dnd-backend-docs.toml`의 `[scope]`와 같다.
  - 대상 선택: `sync/identity.py:select_targets`가 비활성 두 자료원을 대상에 넣지 않는다(spec FR-036).
- [X] T040 [US7] `config/sources.toml`에 항목 두 개를 더한다(항목 추가만, T039 통과).
  - research R-13 표대로 `dnd-backend-code`와 `dnd-android-code`를 더한다.
  - 각 항목: `kind = "github_repo_files"`, `enabled = false`, `auth = "GITHUB_API_TOKEN"`. `[source.scope]`에는 `repo`·`ref = "main"`·`include`를 적는다.
  - 각 항목 바로 위에 활성화 선행 조건 주석 한 줄을 단다(spec FR-036, ADR-022).
  - 기존 줄과 `dnd-backend-docs` 항목은 한 글자도 바꾸지 않는다.
- [X] T041 [US7] `docs/sdd/decisions/ADR-022-code-sources.md`: `templates/decision-record.md` 형식으로 쓰고, Status는 `Proposed`다. 담을 것은 다음과 같다(spec FR-034·036, research R-02·R-13).
  - 자료원과 범위. 첫 활성화는 본문 코드만 권고하고, 테스트 소스 세트는 평가 뒤 별도로 결정한다.
  - 읽기 전용 토큰 권한(`docs/sdd/research/tokens.md`).
  - 외부로 나가는 데이터: 코드 청크 본문과 임베딩 입력 텍스트. ADR-002 공급자의 데이터 처리 정책을 함께 적는다.
  - 보존과 삭제 반영.
  - 비용: 보수 추정 약 3,000 Neurons, 테스트 포함 약 7,000, 하루 색인 예산 5,000.
  - 첫 수집량: 백엔드 776개 파일 약 13분, Android 216개 파일.
  - 활성화 순서: 자료원별 식별 명세(초안 QK-SYN-005) 완료 → QK-STO-002로 새 인덱스 버전 생성·평가·활성화와 대응표 추가 → 사람의 개인 정보 확인 기록 → `enabled = true` → `sources check` → 측정. 두 자료원은 한 번에 하나씩 켠다.
  - 번호: 진행 중인 SCRUM-108 브랜치의 ADR-021과 병합 순서에 따라 번호를 다시 확인한다.
  - 사람이 승인하기 전까지 Status는 Proposed다.

**Checkpoint**: 설정 검사·범위 시험 통과, ADR-022는 사람 리뷰 대기

---

## Phase 10: Polish & Cross-Cutting

- [X] T042 [P] `tests/unit/chunking/code/test_code_no_leak.py`: 비노출과 실패 격리를 확인한다(spec SC-009, FR-007, research R-01).
  - 입력: 본문·시그니처·심볼 이름·표시 이름에 표지 문자열(`QK-CHK-001-LEAK-MARKER`)을 넣은 합성 파일. 성공, `EMPTY`, `FAILED`(세 유형), 두 경고 사례를 돌린다.
  - 표지가 없어야 하는 곳: `ChunkOutcome`·`ChunkingSummary`·`StructureWarning`의 `repr`, 실행 기록 JSON(`sync/report.py:summary_values`), `caplog` 전체.
  - 묶음 격리: 실패를 주입한 파일과 해석기 적재 실패(가져오기 함수 주입)를 섞은 묶음을 `chunk_screened`로 돌린다. 주입한 파일만 `FAILED`·`PROCESSING_ERROR`이고, 나머지 코드·Markdown 자료는 100% 처리된다.
  - 호출 수: 외부 호출·원본 쓰기·저장 호출이 0이다(가짜 객체 호출 수).
- [X] T043 [P] `tests/unit/sync/test_code_send_gate.py`: 전송 직전 검사를 확인한다(spec SC-009, research R-12, 0 Neurons).
  - 준비: T027과 같은 방식으로 이 파일 안에서 조립한다(빈 임베딩 캐시, 가짜 제공자, 호출을 기록하는 outgoing check).
  - 켜짐 동기화 계획·실행을 한 번 돈다. 요약 청크를 포함한 모든 코드 청크의 `embedding_text`가 전송 직전 검사 호출에 나타나야 한다.
  - 비밀값 파일: `tests/unit/synthetic_secrets.py`로 실행 중에 비밀값을 넣은 코드 파일을 만든다. 보안 필터에서 빠져 청크가 0이어야 한다.
- [X] T044 [P] `tests/unit/chunking/code/test_code_summary_counts.py`: 섞인 결과에서 요약 수치가 파일별 결과를 직접 센 값과 같은지 확인한다(spec SC-010, FR-031).
  - 대상: 결과별 수, 종류별 청크 수, 실패·경고 유형별 수, 토큰 분포, `split_blocks`, 테스트 청크 수, 컴포넌트 수
  - 컴포넌트 수는 T005 셈 규칙으로, 나뉜 형식 머리와 멤버 청크를 두 번 세지 않는다.
- [X] T045 [P] `tests/unit/chunking/code/test_code_perf.py`: 회귀 감시다(완료 판정 아님, 주석에 적는다, spec SC-012).
  - 입력: `random` 없이 결정적으로 만든 합성 Java·Kotlin 파일 1,361개. 파일마다 클래스 1, 필드 3, 메서드 6, 메서드마다 문장 8개다.
  - 입력 SHA-256과 총 바이트는 처음 실행에서 계산해 상수로 고정한다.
  - `chunk_screened` 1회가 60초 이하여야 한다.
- [X] T046 [P] `specs/QK-CHK-001-code-chunker/measurement/measure_code.py`: `--time-chunking`을 더한다(research R-14).
  - 동작: 구현된 `chunk_code`로 대상 파일을 3회 청킹한다.
  - 출력: 중앙값 `elapsed_seconds`, 실제 청킹 결과의 청크 수·종류별 수·`PARSE_FALLBACK`·`CONTEXT_OMITTED` 수·`split_blocks`, 장비 정보, `script_sha256_12`
  - 흉내 측정 부분은 그대로 둔다. 원문·경로·심볼을 출력하지 않는다.
  - 이 변경으로 스크립트 해시가 research R-02의 `1cc6ad12e564`와 달라진다. 옛 수치는 그 커밋의 스크립트로 재현한다고 머리말에 적는다. 실행은 사람 단계다.
- [X] T047 [P] `tests/unit/chunking/code/test_code_expected.py`: 최종 필수 키 검사를 더한다(spec SC-001, QK-CHK-002 T037과 같은 방식).
  - 모든 코드 픽스처의 `expected`에 결과 종류, `document_title`, `warnings`가 있어야 한다.
  - `CHUNKED`면 청크마다 다음이 있어야 한다: `ordinal`, `lines`, `heading_path`, `search_header`, `search_text`, `embedding_text`, data-model의 `locator["code"]` 키 13개 전부.
  - `FAILED`면 `failure`가 있어야 한다.
  - 빠지면 시험이 실패한다.
- [X] T048 기본 검증(AGENTS.md 7절, `TASK.md` Validation)을 돌리고 보고한다.
  - 명령:
    - `python scripts/preflight.py`, `git diff --check`
    - `uv run ruff check .`, `uv run ruff format --check .`
    - `uv run qk-dev db up`, `uv run qk-migrate` 두 번(두 번째는 `applied=0`)
    - `QK_REQUIRE_LOCALDB=1 uv run pytest`
  - 실패는 원인을 고친다. 시험을 지우거나 건너뛰지 않는다. 이 PC(Windows)의 `test_boundaries.py` 기준선 실패 3건(`test_violation_is_detected`, `test_chunking_violations_are_detected`, `test_domain_must_not_import_retrieval`)은 따로 적는다.
  - 최종 보고에는 AGENTS.md 8절 항목을 넣는다.
    - `index_version`: 꺼짐 `iv-4c0bc4fcc642` 불변
    - `chunking_version`: `chk-md` 불변, `chk-code` 첫 값
    - `embedding_model`
    - `eval_set_version`: 해당 없음(검색 평가는 QK-STO-002·QK-EVL-001), 미실행 사유와 함께
    - `estimated_or_used_neurons`: 0

---

## 사람 단계 (구현 뒤)

- [X] H01 spec SC-012 완료 판정(quickstart 3절): 대상 저장소 로컬 사본 두 곳으로 `measure_code.py --time-chunking`을 실행한다(`../qk-targets/backend` `6aeccd0`, `../qk-targets/android` `0314755`).
  - 기준: 저장소별 중앙값 합이 60초 이하다.
  - 증빙: 출력(장비, 새 `script_sha256_12` 포함)을 PR에 붙인다. 외부 호출은 0건이다.
- [X] H02 로컬 실측(quickstart 4절): 구현된 청커로 research R-02 항목을 다시 잰다.
  - 항목: 청크 수, 종류별 수, 크기 분포, 상한 초과 나누기 수, `PARSE_FALLBACK`, `CONTEXT_OMITTED`
  - 흉내 측정과 청크 수가 ±10%를 넘게 다르면 원인을 적는다. ADR-022 비용 추정을 그 값으로 고치고, 새 스크립트 해시를 적는다.
- [X] H03 ADR-022 리뷰·승인(사람). 승인 전에는 Proposed로 둔다. 코드 자료원 켜기와 개인 정보 확인 기록 작성은 이 작업 밖이다(spec FR-035·036).
- [X] H04 언어 팩 내려받기 폴더 처리 결정(사람): plan 측정 중 `tree-sitter-language-pack`이 내려받은 `%LOCALAPPDATA%/tree-sitter-language-pack/v1.22.1`(약 28 MB)을 지울지 사유와 함께 남길지 정한다. TASK.md에 기록한다.

---

## Dependencies & Execution Order

- **단계 순서**: Phase 1 → Phase 2 → US1(Phase 3) → US2(Phase 4) → US3(Phase 5) → US6(Phase 6) → US4(Phase 7) → US5(Phase 8) → US7(Phase 9) → Polish(Phase 10) → 사람 단계.
- **스토리 사이 의존**:
  - US2·US3은 US1의 `units.py`·`symbols.py`·`service.py`에 기댄다.
  - US6은 Phase 2의 버전 함수만 필요하다. 코드 청킹 규칙 버전 첫 값은 T038 뒤에 고정한다.
  - US4는 US3의 메타데이터 자리에, US5는 US1의 단위·헤더에 기댄다.
  - US7은 코드와 독립이라 Phase 2 뒤 언제든 할 수 있다.
- **같은 파일 작업 순서**:
  - `units.py`: T016 → T022
  - `symbols.py`: T017 → T026 → T035
  - `chunking/code/service.py`: T019 → T022 → T026 → T035 → T038
  - `chunking/code/header.py`: T018 → T035
  - `domain/chunking.py`: T005 하나
  - `test_code_expected.py`: T013 → T047
- **기대 JSON**: 픽스처는 T012 → T020 → T023 → T033 → T036 순서로 키를 더하기만 한다.
- **TDD**: 각 단계의 시험 작업([P])을 먼저 쓰고 실패를 확인한 뒤 구현 작업을 한다.

## Parallel Opportunities

- **Phase 1**: T002·T003은 T001과 병렬이다.
- **Phase 2**: 시험 T004·T006·T008·T010을 먼저 병렬로 쓴다. 구현은 T005 → T007 → T009 → T011 순서다. T007은 타입이, T009는 규칙 상수가, T011은 버전·해석 경계가 필요하다.
- **스토리 안**: 픽스처·시험 작업은 서로 병렬이다. 단, 같은 픽스처의 기대 JSON을 고치는 작업(T020·T023·T033)은 앞 단계 시험이 통과한 뒤에 한다.
  - US1: T012~T015
  - US2: T020~T021
  - US3: T023~T025
  - US6: T027~T029
  - US4: T033~T034
  - US5: T036~T037
  - US7: T039
- **US7**: T039~T041은 US1~US6 구현과 병렬로 할 수 있다(다른 파일).
- **Polish**: T042~T047은 병렬이고, T048은 맨 마지막이다.

## Implementation Strategy

1. **MVP = Phase 1~3(US1)**: 원문 청크·심볼 경로·헤더·재현성이다. 켜기 설정이 꺼짐이라 운영에 영향이 없다.
2. **P1 마무리**: US2·US3으로 요약과 메타데이터를 더하고, US6으로 켜짐 경로와 차단을 연결한다.
3. **P2**: US4·US5로 판정·크기·실패 처리를 채우고, US7로 비활성 자료원과 ADR-022를 더한다.
4. **마무리**: Polish(비노출·격리, 전송 직전 검사, 요약 수치, 성능 회귀, 측정 옵션, 필수 키)와 기본 검증을 한다. 사람 단계 H01~H04는 구현 뒤 사람이 한다.
