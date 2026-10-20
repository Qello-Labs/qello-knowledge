---
description: "QK-CHK-002 구현 작업 목록"
---

# Tasks: QK-CHK-002 Markdown 청커·검색 헤더

**Input**: `specs/QK-CHK-002-markdown-chunker/`의 plan.md, spec.md, research.md, data-model.md, contracts/chunker.md, contracts/cli.md, quickstart.md

**Tests**: 포함한다. 명세의 수용 시나리오와 C-12(수용 기준은 검증으로 닫는다)가 자동 시험을 요구한다. 시험을 먼저 쓰고 실패를 확인한 뒤 구현한다.
모든 시험은 외부 호출 0건이다. 실제 대상 문서 확인(SC-011 완료 판정, 관찰)은 맨 끝 "사람 단계"다.

**Organization**: 사용자 스토리별 단계로 나눈다. US1·US2·US3은 모두 P1이지만, 크기 판정이 검색 헤더를 포함하므로(spec FR-015) US1 → US3 → US2 → US4(P2) 순서로 한다.

**선행 조건**: spec.md·plan.md 사람 승인(2026-10-21), 이 목록의 사람 승인, `TASK.md` Scope를 구현 범위로 갱신(AGENTS.md 1절, 로드맵 1절 원칙 4).

**공통 규칙**: 본문·검색 헤더·임베딩 입력 텍스트를 로그·예외 문구·결과 요약에 넣지 않는다(spec FR-006). 시험용 합성 문서만 쓰고 대상 저장소 원문을 저장소에 복사하지 않는다(AGENTS.md 6절).
시험의 기대값 JSON은 사람이 정하는 정답이다. 구현 결과로 기대값을 덮어쓰지 않는다(AGENTS.md 9절). 이 픽스처는 청커의 결정적 수용 시험용 합성 자료이고,
검색 품질 평가 세트·정답 라벨(QK-EVL-001)이 아니며 이 작업에서 평가 세트를 바꾸지 않는다. 시험을 지우거나 `skip`·`xfail`로 체크포인트를 통과시키지 않는다.

**TDD 순서**: 각 단계에서 시험 작업을 먼저 쓰고 실패(아직 없는 모듈이면 수집 오류 포함)를 확인한 뒤 구현 작업을 한다. [P]는 같은 단계의 시험끼리, 구현끼리 병렬이라는 뜻이다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 다루고 미완료 작업에 기대지 않아 병렬로 할 수 있다
- **[Story]**: 해당 사용자 스토리(US1~US4)

---

## Phase 1: Setup

- [X] T001 `pyproject.toml`: `[project.optional-dependencies]`에 `index = ["markdown-it-py==4.2.0"]`, `[dependency-groups].dev`에 `"markdown-it-py==4.2.0"`을 더하고 `uv lock`으로 `uv.lock`을 갱신한다. 런타임 `dependencies = []`는 그대로 둔다(research R-01). `uv sync --locked` 뒤 `uv run python -c "import markdown_it; print(markdown_it.__version__)"`가 `4.2.0`인지 확인
- [X] T002 패키지 자리 만들기: `src/qello_knowledge/chunking/__init__.py`, `tests/unit/chunking/__init__.py`, `tests/fixtures/chunking/`
- [X] T003 [P] `tests/unit/test_boundaries.py`: 기존 `RESTRICTED`(`domain`·`ports`·`embedding`) 검사는 그대로 두고, `domain`·`ports`·`embedding`·`query` 아래 모듈이 `qello_knowledge.chunking`과 `markdown_it`를 가져오면 실패하는 검사를 더한다. `markdown_it`를 가져오는 `src/` 모듈은 `chunking/blocks.py` 하나뿐인지도 검사한다(research R-10). 위반 사례를 임시 디렉터리로 만든 시험도 추가

---

## Phase 2: Foundational

**목적**: 모든 스토리가 쓰는 타입·버전·블록 해석. 이 단계가 끝나야 스토리 시험을 쓸 수 있다.

- [X] T004 [P] `src/qello_knowledge/domain/chunking.py`: data-model.md 타입을 표준 라이브러리 불변 dataclass·`StrEnum`으로 정의한다.
  `ChunkingSettings(model_version="@cf/baai/bge-m3", target_tokens=512, limit_tokens=2800)` — `__post_init__`에서 검증한다. "`domain.embedding.MODELS`에 있어야 한다",
  "1 이상, `limit_tokens` 이하"(target), "`limit_tokens × bytes_per_token_estimate ÷ WORST_BYTES_PER_TOKEN ≤ max_input_tokens`"(limit), 어기면 생성 시 `ValueError`(그래서 `chunk_markdown`·`chunk_screened` 어느 쪽으로 들어와도 자료 처리 전에 막힌다).
  상수 `WORST_BYTES_PER_TOKEN = 1.2`. `ChunkOutcomeKind`(`CHUNKED`, `EMPTY`, `NOT_MARKDOWN`, `FAILED`), `ChunkFailureKind`(`LINE_TOO_LONG`, `HEADER_TOO_LONG`, `PROCESSING_ERROR`),
  `StructureWarningKind`(`TABLE_CELL_MISMATCH`, `UNCLOSED_FENCE`), `StructureWarning(kind, line)`, `ChunkDraft(chunk: ChunkInput, search_header, embedding_text, estimated_tokens)`(`chunk`·`search_header`·`embedding_text`는 `repr=False`. `ChunkInput`의 기본 `repr`에
  `body`·`search_text`가 들어가기 때문이다. 값은 그대로 둔다),
  `ChunkOutcome(outcome, document_title, drafts, warnings, failure, split_blocks, chunking_version)`, `ChunkedContent`(`screened`는 `repr=False`, 나머지는 `ChunkOutcome`과 같음),
  `ChunkingSummary`, `ChunkingResult(results, summary)`. `__post_init__` 불변식: "`FAILED`·`EMPTY`·`NOT_MARKDOWN`이면 `drafts == ()`", `failure`는 `FAILED`일 때만, `split_blocks`는 `CHUNKED`가 아니면 0.
  `ChunkingSummary.from_results(results)`: 결과별·실패별·경고별 수, `chunk_count`, `tokens_min`·`tokens_median`(`statistics.median_low`, 정수)·`tokens_max`(청크 없으면 `None`),
  `split_blocks`는 결과별 합. `ChunkDraft`에는 `estimated_tokens: int`(임베딩 입력 텍스트의 예상 토큰)를 두고, 요약은 이 값만 쓴다. 그래서 `domain/chunking.py`는
  `embedding`을 가져오지 않는다. 이 필드는 `chunking/service.py`가 `embedding.estimate.estimated_tokens`로 채운다(T016)
- [X] T005 [P] `tests/unit/chunking/test_domain.py`: 설정 기본값 통과, `target_tokens=0`·`target_tokens > limit_tokens`·`limit_tokens=2900`(2,900 × 3.5 ÷ 1.2 = 8,458 > 8,192)·없는 모델은 생성 시 `ValueError`,
  `repr(ChunkDraft)`·`repr(ChunkOutcome)`(실제 객체 그대로)에 본문·헤더·임베딩 입력 텍스트의 표지 문자열이 없다, `ChunkOutcome` 불변식 위반은 생성 실패, `from_results`가 직접 센 값과 같다(SC-010, 짝수 개 청크의 낮은 쪽 중앙값 포함)
- [X] T006 `src/qello_knowledge/chunking/version.py`(T008 뒤, `PARSER_VERSION`이 필요): `chunking_version(settings) -> str` = `"chk-md-" + sha256(json.dumps(재료, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()[:12]`.
  재료는 research R-07의 객체(`rules_revision`·`header_format`·`search_text_format`·`embedding_input_format` 판수 상수 1, `settings`(`limit_tokens`, `model_version`, `target_tokens`, `worst_bytes_per_token`),
  `parser`(`enable: ["table"]`, `name: "markdown-it-py"`, `preset: "commonmark"`, `version: markdown_it.__version__`)). 판수 상수는 이 파일 맨 위에 두고 "규칙 코드를 바꾸면 올린다" 주석을 단다.
  `markdown_it`는 이 파일에서 직접 가져오지 말고 `chunking/blocks.py`의 `PARSER_VERSION`을 쓴다(T003 검사)
- [X] T007 [P] `tests/unit/chunking/test_version.py`: 기본 설정 → `chk-md-20d966f730bb`(research R-07 고정값). 같은 설정 → 같은 값. `target_tokens`·`limit_tokens`·`model_version`·판수 4개·해석기 버전을 하나씩 바꾸면 값이 바뀐다(monkeypatch, SC-009). 경고 판정만 바꿨을 때 값이 같은지는 US4의 T029에서 본다
- [X] T008 `src/qello_knowledge/chunking/blocks.py`: research R-05·R-06. `PARSER_VERSION`, `parse_document(lines) -> ParsedDocument`(data-model.md 내부 중간값:
  `blocks`(최상위 블록 나무), `front_matter_title`, `fences`(`FenceInfo(start, end, content_newlines)`), `tables`(`TableInfo(start, end, container_depth)`)). T021은 `front_matter_title`을,
  T030은 `fences`·`tables`를 쓴다.
  (1) 앞머리 메타데이터: 1번 줄이 정확히 `---`이고 뒤에 `---`·`...`만 있는 줄이 있으면 그 범위를 `front_matter` 블록으로 하고, `title:`로 시작하는 줄의 값(앞뒤 따옴표 제거)을 `front_matter_title`로 둔다. 해석용 사본에서는 그 줄들을 빈 줄로 바꾼다.
  (2) 해석용 사본이 LF로 끝나지 않으면 LF 하나를 붙여 `MarkdownIt("commonmark").enable("table")`로 해석한다.
  (3) 여닫음 짝으로 블록 나무를 만든다: 최상위(`level == 0`) 블록, 목록 → `list_item`, 목록 항목·인용 → 바로 안쪽 블록. 각 `Block`은 data-model.md 내부 중간값 필드를 갖는다(`kind`, 0부터 `start`·끝 제외 `end`, 제목이면 `level`·`text`, 표면 머리글 두 줄, 펜스면 여는 줄, `children`).
  (4) 어느 최상위 블록에도 들지 않은 공백 아닌 줄은 `raw` 블록으로 메운다(링크 참조 정의 등).
  (5) 어느 수준이든 펜스 토큰마다 `FenceInfo(map[0], map[1], content.count("\n"))`, 표 토큰마다 감싼 인용·목록 항목 수를 센 `TableInfo`를 모은다.
  (6) 제목 글자: inline 자식의 `text`·`code_inline`·이미지 대체 글자를 잇고 `softbreak`·`hardbreak`는 공백 하나, 연속 공백을 줄이고 앞뒤 정리(research R-09).
  이 파일만 `markdown_it`를 가져온다
- [X] T009 [P] `tests/unit/chunking/test_blocks.py`: 링크 참조 정의 줄이 `raw` 블록이 된다, 앞머리 메타데이터 `---`가 구분선·밑줄형 제목으로 읽히지 않는다, 코드 펜스 안 `# 주석`·들여쓴 코드·인용·목록·HTML 블록 안의 제목 모양 줄은 최상위 제목이 아니다,
  중첩 목록의 나무가 상위 목록 항목 → (직접 자식) 하위 목록 → (그 자식) 하위 목록 항목(`level == 3`)이다, 여러 줄 밑줄형 제목 → `first second`, 제목 `## **중요** [링크](x) \`code\`` → `중요 링크 code`, 마지막 줄 바꿈 없는 입력의 줄 범위

**Checkpoint**: `uv run pytest tests/unit/chunking tests/unit/test_boundaries.py` 통과.

---

## Phase 3: User Story 1 - 청크마다 원본 위치로 되돌아가고, 다시 나눠도 같다 (P1) 🎯 MVP

**Goal**: 절마다 청크를 만들고, 본문 = 줄 범위 원문, 공백 아닌 줄 정확히 한 번, 결정적 결과. 크기 나누기는 US2, 헤더 규칙 세부는 US3에서 채운다.

**Independent Test**: 기대값 JSON을 적어 둔 합성 문서를 두 번(순서 섞어) 청킹해 줄 범위·제목 경로·본문 원문 대조·줄 덮기를 확인한다.

### Tests (US1)

- [X] T010 [P] [US1] `tests/fixtures/chunking/`에 합성 문서와 사람이 쓴 기대 JSON을 만든다(문서마다 `<이름>.md` + `<이름>.expected.json`): `sections_basic`(세 절), `head_section`(첫 제목 앞 문단), `heading_only`(`# A` 바로 다음 `## B`, 문서 끝 본문 없는 제목), `level_skip`, `duplicate_heading`, `refdef`(링크 참조 정의), `front_matter`.
  기대 JSON은 `input`(설정 덮어쓰기 `settings`, `location`, `source_title`, 없으면 기본값)과 `expected`(결과 종류, 실패 유형, `warnings`, 청크별 `ordinal`(0부터 연속)·`lines`·`heading_path`)를 나눠 담는다. US3·US2·US4 단계에서 `search_text`·`embedding_text` 기대값과 사례를 더한다. 대상 저장소 원문을 쓰지 않는다
- [X] T011 [P] [US1] `tests/unit/chunking/test_expected.py`: 픽스처 묶음을 `input`대로 `chunk_markdown`에 넣어 `expected`와 비교하는 시험(SC-001). 단계 중에는 `expected`에 있는 키만 비교한다. 최종 필수 키 검사는 T037
- [X] T012 [P] [US1] `tests/unit/chunking/test_invariants.py`: 모든 픽스처에서 (a) `"\n".join(원문줄[start-1:end]) == chunk.body`, (b) 공백 아닌 원문 줄이 정확히 한 청크 범위에 든다, (c) 청크 앞뒤 줄이 공백 아님, (d) 모든 절에 청크가 있다, (e) `validate_chunks(source_version, chunks)` 통과, (f) 모든 청크에 `chunking_version`, (g) `draft.estimated_tokens == estimated_tokens(draft.embedding_text, MODELS[model])` (SC-002, FR-008~011)
- [X] T013 [P] [US1] `tests/unit/chunking/test_determinism.py`: 같은 묶음 두 번, `chunk_screened`에 순서를 섞어 한 번 더 → 자료별 결과 동일(SC-001). CRLF·LF·CR만 다른 본문과 앞 BOM 유무 → 같은 결과, 탭·줄 끝 공백은 본문에 그대로(FR-007, US1 시나리오 7). 가운데 절 본문 한 줄만 고친 판 → 첫째·셋째 절 청크의 `body`·`heading_path`·`embedding_text` 동일(US1 시나리오 5, SC-004 첫 문장)
- [X] T014 [P] [US1] `tests/unit/chunking/test_screened.py`: 가짜 자료원(`adapters/fake.py`)으로 만든 `ScreenedContent` 묶음 — `content_format`이 `CODE`·`JSON`·`TEXT`인 자료는 `NOT_MARKDOWN`·청크 0개(SC-007), 빈 문서·공백만 → `EMPTY`, `chunk_markdown`이 예외를 던지도록 monkeypatch한 자료는 `FAILED`+`PROCESSING_ERROR`이고 나머지 자료는 처리된다(FR-005), 종류가 다른 두 가짜 자료원에 같은 본문·위치·제목 → 같은 결과(SC-008), 위치는 `content.location`을 쓴다(목록 항목 위치와 달라도)

### Implementation (US1)

- [X] T015 [US1] `src/qello_knowledge/chunking/sections.py`: `split_sections(blocks) -> tuple[Section, ...]` — 최상위 제목 블록마다 절, 첫 제목 앞 블록은 제목 경로가 빈 머리 절(공백 아닌 줄이 있을 때만). 제목 경로는 제목 수준 스택으로 만든다(실제 있는 제목만, spec FR-011·018)
- [X] T016 [US1] `src/qello_knowledge/chunking/service.py`: `chunk_markdown(body, *, location, source_title, settings) -> ChunkOutcome` — 줄 바꿈 LF 통일·BOM 제거(FR-007) → `parsed = parse_document(lines)` → `split_sections(parsed.blocks)` → 절마다 블록 범위로 청크(이 단계는 절 하나 = 청크 하나) → 앞뒤 공백 줄을 본문과 `locator`에서 함께 뺀다 → `ChunkInput(ordinal, locator={"path": location, "lines": [시작, 끝]}, body, search_text, chunking_version, heading_path)`.
  검색 헤더·`search_text`·`embedding_text`는 T023 전까지 `header.py`의 임시 구현(위치 + 문서 제목)을 쓴다. `ChunkDraft.estimated_tokens`는
  `embedding.estimate.estimated_tokens(embedding_text, MODELS[settings.model_version])`로 채운다. 공백만 있는 본문은 `EMPTY`. 예상하지 못한 예외는 잡아서 `FAILED`+`PROCESSING_ERROR`(예외 문구를 남기지 않는다).
  이후 제목(T021)·경고(T031) 처리도 같은 `parsed`를 쓴다.
  `chunk_screened(passed, settings) -> ChunkingResult` — 생성 시 검증된 설정을 그대로 쓰고, `content_format != MARKDOWN`이면 `NOT_MARKDOWN`, 아니면 `chunk_markdown(content.body, location=content.location, source_title=content.title or item.title, settings=settings)`, 입력 순서 유지, `ChunkingSummary.from_results`
- [X] T017 [US1] `src/qello_knowledge/chunking/__init__.py`: `chunk_markdown`, `chunk_screened`, `chunking_version`을 공개한다(contracts/chunker.md)

**Checkpoint**: T011~T014 통과(US1 범위 키만). 외부 호출 0건.

---

## Phase 4: User Story 3 - 조각만 봐도 어느 문서의 어느 절인지 안다 (P1)

**Goal**: 문서 제목 규칙, 검색 헤더 두 줄, 키워드 검색용 텍스트, 임베딩 입력 텍스트를 research R-09대로 만든다.

**Independent Test**: 제목 우선순위·꾸밈 제거·중복 제거·제목 없는 문서 사례에서 헤더·`search_text`·`embedding_text`가 기대값과 같다.

### Tests (US3)

- [X] T018 [P] [US3] `tests/fixtures/chunking/`에 사례 추가(+ 기대 JSON에 `search_header`·`search_text`·`embedding_text`): `adr_like`(`# 결정 기록 A` > `## 결정` > `### 근거`, 문서 제목 = 첫 제목이라 한 번만), `no_title`(제목·원본 제목 없음 → 파일 이름), `decorated_heading`, `setext_multiline`, 앞머리 `title:`이 있는 문서. 기존 US1 픽스처 기대 JSON에도 세 값을 더한다
- [X] T019 [P] [US3] `tests/unit/chunking/test_header.py`: 문서 제목 순서(원본 제목 → 앞머리 `title` → 첫 수준-1 제목 → 파일 이름, spec FR-017), `chunk_screened`에서 `content.title`이 있으면 그것, 없으면 `item.title`(US3 시나리오 4), 같은 절에서 나온 청크의 제목 경로 동일(FR-018), 모든 `embedding_text`·`search_text`가 `search_header`로 시작(SC-006), 본문 없는 상위 제목마다 그 경로를 가진 청크가 있다(SC-006)
- [X] T020 [P] [US3] `tests/unit/chunking/test_locality_titles.py`: 문서 제목으로 쓰이지 않는 `## B` 제목 줄만 고친 판 → 바뀐 청크가 B를 경로에 가진 청크뿐, 문서 제목을 고친 판 → 모든 청크의 검색 헤더에 새 제목(SC-004 둘째·셋째 문장, US1 시나리오 6)

### Implementation (US3)

- [X] T021 [US3] `src/qello_knowledge/chunking/sections.py`: `document_title(source_title, front_matter_title, blocks, location) -> str`(spec FR-017 순서, 빈 문자열은 없는 것으로 본다)
- [X] T022 [US3] `src/qello_knowledge/chunking/header.py`: `search_header(location, title, heading_path)` = `location + "\n" + " > ".join([title, *경로])`, 경로 첫 항목이 문서 제목과 같으면 한 번만. `search_text(header, body) = header + "\n\n" + body`. `embedding_text(header, prefix, body) = header + "\n\n" + (prefix + "\n" if prefix else "") + body`(research R-09)
- [X] T023 [US3] `src/qello_knowledge/chunking/service.py`: T016의 임시 헤더를 T021·T022로 바꾸고 `ChunkOutcome.document_title`을 채운다.

**Checkpoint**: T011~T014, T018~T020 통과.

---

## Phase 5: User Story 2 - 청크는 추정 상한 안으로 나뉘고, 원문은 잘려 나가지 않는다 (P1)

**Goal**: 목표 512(연성)·상한 2,800 안의 탐욕 쌓기, 상한 초과 블록의 재귀 나누기와 반복 머리글, 줄·헤더 길이 초과 실패.

**Independent Test**: 시험용 작은 설정(예: `target_tokens=40`, `limit_tokens=80`)으로 큰 문서·큰 블록·경계값 사례를 청킹한다.

### Tests (US2)

- [X] T024 [P] [US2] `tests/fixtures/chunking/`에 사례 추가(시험용 설정은 기대 JSON의 `input.settings`에, 기대 결과는 `expected`에 `search_header`·`search_text`·`embedding_text`까지 적는다): `long_section`(블록 경계에서 나뉨), `big_table`(행 경계, 뒤 조각 `embedding_text`에 머리글 두 줄), `big_fence`(뒤 조각에 여는 펜스 줄), `big_list`(항목은 상한 이하 → 항목 경계), `big_list_item`(큰 항목 안의 작은 하위 항목·표·코드는 안 나뉨), `multi_paragraph_quote`(가운데 `>` 줄이 이웃 조각에 붙음), `paragraph_between`(목표~상한 사이 문단 하나 → 청크 하나, US2 시나리오 6), `three_times_limit`
- [X] T025 [P] [US2] `tests/unit/chunking/test_size.py`: 모든 청크에서 `estimated_tokens(draft.embedding_text, MODELS[model]) ≤ limit_tokens`이고 그 값이 `draft.estimated_tokens`와 같다, 잘린 원문 줄 0, 상한 이하 블록이 두 청크에 걸친 건수 0(어느 깊이든), `split_blocks`가 나뉜 최상위 블록 수와 같다(SC-003, FR-013~016). 경계값: 헤더를 붙여야 상한을 넘는 한 줄 → `FAILED`+`LINE_TOO_LONG`·청크 0, 반복 머리글이 없으면 통과하고 있으면 넘는 표·코드 줄 → `LINE_TOO_LONG`, 검색 헤더만으로 상한 이상 → `HEADER_TOO_LONG`(US2 시나리오 4·5). 실패한 자료와 같은 `chunk_screened` 묶음의 다른 자료는 정상(SC-007)

### Implementation (US2)

- [X] T026 [US2] `src/qello_knowledge/chunking/split.py`: research R-08. 크기는 항상 `estimated_tokens(검색 헤더 + 빈 줄 + (반복 머리글) + 후보 본문)`.
  (1) 헤더만으로 `≥ limit_tokens` → `HEADER_TOO_LONG`. (2) 절의 블록을 순서대로 쌓아, 다음 블록을 더하면 목표를 넘고 쌓인 것이 있으면 끊는다. 목표를 넘어도 상한 이하인 블록은 혼자 청크.
  (3) 상한을 넘는 블록은 `split(블록)`: 자식이 있으면 자식 단위(자식 밖 줄은 다음 자식에, 꼬리는 마지막 자식에 붙여 부모 범위를 빈틈없이 덮는다, research R-05 5번)를 (2) 규칙으로 쌓고, 상한 초과 자식 단위는 재귀. 자식 없는 블록만 줄을 쌓아 상한 안에서 끊는다.
  반복 머리글은 표 머리글 두 줄·여는 펜스 줄(원문 그대로). (4) 줄 하나 + 헤더 + 필요한 반복 머리글 > 상한 → `LINE_TOO_LONG`(자료 전체 실패, 부분 청크 없음). (5) `split`이 일어난 최상위 블록마다 `split_blocks` 1
- [X] T027 [US2] `src/qello_knowledge/chunking/service.py`: 절마다 `split.py`를 써서 청크 범위와 반복 머리글을 받고 `ChunkDraft`를 만든다. 실패 유형이 나오면 `FAILED`로 돌려준다(청크 0, `split_blocks` 0)

**Checkpoint**: Phase 3~5 시험 전부 통과.

---

## Phase 6: User Story 4 - Markdown 구조를 깨지 않고 나눈다 (P2)

**Goal**: 구조 경고 두 가지와 언어 표시 무관성.

**Independent Test**: 구조 사례 픽스처에서 경고·실패·경계가 기대값과 같다.

### Tests (US4)

- [X] T028 [P] [US4] `tests/fixtures/chunking/`에 사례 추가(`expected`에 `warnings`와 청크별 `search_header`·`search_text`·`embedding_text`까지): `fence_heading`(펜스 안 `# 주석`), `unclosed_fence`, `lang_mermaid`·`lang_css`(내용 같고 언어 표시만 다름, 크기 경계에서 먼 입력), `broken_table`(셀 수 다른 행과 파이프 없는 행), `nested_tables`(인용 안 바깥 파이프 섞인 표, 목록 첫 줄에서 시작하는 표, 순서 목록, 목록 안 인용 → 경고 없음), `html_block`
- [X] T029 [P] [US4] `tests/unit/chunking/test_warnings.py`: research R-11 표 셀 수 6사례(경고 있음/없음)와 펜스 닫힘 16사례(닫힘: 일반, 빈 내용, 빈 줄 내용, 인용 안, 목록 안, 마지막 줄 바꿈 없음, 내용에 U+2028, 내용에 수직 탭 / 열림: 여는 줄만, 내용만, 내용만이고 줄 바꿈 없음, 뒤 빈 줄, 네 칸 들여쓴 닫는 펜스 모양, 코드 안 `> ```` 줄, 인용이 끝나 펜스가 끝난 경우)를 매개변수 시험으로. 경고가 있어도 결과는 `CHUNKED`(SC-005). 경고 판정 함수를 monkeypatch로 바꿔도 `chunking_version`과 청크 결과가 같다(SC-009, FR-024). `lang_mermaid`·`lang_css`의 줄 범위·제목 경로가 같고 본문은 각자 원문(US4 시나리오 4)

### Implementation (US4)

- [X] T030 [US4] `src/qello_knowledge/chunking/warnings.py`: research R-11. 표(어느 수준이든): 감싼 컨테이너 수 N만큼 `^[ \t]*(?:>[ \t]?|(?:[-+*]|\d{1,9}[.)])[ \t]+)` 표지를 최대 N번 지우고 앞뒤 공백 제거, 이스케이프되지 않은 `|`로 나눠(앞뒤 `|` 제외) 셀 수가 머리글 행과 다르면 `TABLE_CELL_MISMATCH`(원문 줄 번호, 1부터). 펜스(어느 수준이든): `fence.content_newlines != fence.end - fence.start - 2`이면 `UNCLOSED_FENCE`(여는 줄 번호 `fence.start + 1`). 입력은 `ParsedDocument.fences`·`tables`와 원문 줄이다(이 파일은 `markdown_it`를 가져오지 않는다)
- [X] T031 [US4] `src/qello_knowledge/chunking/service.py`: `CHUNKED` 결과에 경고를 줄 번호 순으로 붙인다. 경고는 청크 결과와 `chunking_version`에 영향을 주지 않는다(FR-024)

**Checkpoint**: 모든 스토리 시험 통과.

---

## Phase 7: Polish & Cross-Cutting

- [X] T032 [P] `tests/unit/chunking/test_no_leak.py`: 표지 문자열(예: `QK-CHK-002-LEAK-MARKER`)을 본문에 넣은 자료로 성공·`EMPTY`·`FAILED`(세 실패 유형)·경고 사례를 돌려, `ChunkingSummary`·`StructureWarning`·`ChunkOutcome`의 `repr`(본문 필드 제외)·`caplog` 전체와 측정 출력(T035)에 표지가 없음을 확인(SC-007, FR-006)
- [X] T033 [P] `tests/unit/chunking/test_perf.py`: 시드 `20261021`의 `random.Random`으로 합성 문서 79개 생성(research R-12: 문서마다 절 13개, 절마다 한국어·영문 섞인 문단 2~4개, 표 1개(4열 × 6~12행), 코드 펜스 1개(10~40줄), 목록 1개(3~8항목)). 입력 전체 SHA-256과 총 바이트를 처음 실행에서 계산해 시험에 상수로 고정하고, `chunk_screened` 1회 소요 ≤ 10초. 완료 판정이 아니라 회귀 감시라고 주석으로 적는다
- [X] T034 `src/qello_knowledge/devtools/measure.py`·`src/qello_knowledge/devtools/db.py`: `qk-dev source measure`에 `--chunk`를 더한다(contracts/cli.md). 없으면 출력·동작이 지금과 같다. 있으면 `ScreenResult.passed`를 기본 `ChunkingSettings`로 `chunk_screened`에 넘기고 그 구간만 `time.perf_counter`로 재서 `chunking` 항목(버전, 설정, `elapsed_seconds`, 요약, 실패·경고 목록)을 더한다. 경로는 `safe_text(..., FieldKind.PATH, context)`. 종료 코드 규칙은 그대로
- [X] T035 [P] `tests/unit/devtools/test_measure.py`: 재생 전송으로 `--chunk` 없음 → 기존 출력 그대로, 있음 → 사람용 줄·JSON `chunking` 항목, 본문·헤더·임베딩 입력 텍스트 없음, 원본 요청 수가 `--chunk` 없을 때와 같다
- [X] T036 [P] `specs/QK-CHK-002-markdown-chunker/measurement/measure_inputs.py`: `--time-chunking`이 구현된 `chunk_markdown`·`ChunkOutcome`과 맞는지 확인만 한다(코드가 계약과 다르면 이 파일을 고친다). 실행은 사람 단계
- [X] T037 [P] `tests/unit/chunking/test_expected.py`: 최종 필수 키 검사를 더한다. 모든 픽스처의 `expected`에 결과 종류가 있고, `CHUNKED`면 청크마다 `ordinal`·`lines`·`heading_path`·`search_header`·`search_text`·`embedding_text`가,
  `FAILED`면 `failure`가, 모든 결과에 `warnings`(빈 목록 포함)가 있어야 한다. 빠지면 시험 실패(SC-001)
- [X] T038 기본 검증(AGENTS.md 7절): `python scripts/preflight.py`, `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run qk-dev db up`, `QK_REQUIRE_LOCALDB=1 uv run pytest`. 실패는 원인을 고치고, 시험을 지우거나 건너뛰지 않는다

---

## 사람 단계 (구현 뒤)

- [X] H01 SC-011 완료 판정(quickstart 3절): 대상 저장소 로컬 사본으로 `measure_inputs.py --time-chunking` 1회. `files == 79`, `total_bytes == 1017913`, `by_outcome == {"CHUNKED": 79}`, `chunk_count > 0`, 반올림하지 않은 `elapsed_seconds ≤ 10`. 출력(장비 포함)을 PR 증빙에 붙인다. 외부 호출 0건
- [ ] H02 관찰(quickstart 4절): `uv run qk-dev source measure --name dnd-backend-docs --chunk --json` 1회(GitHub 약 83회, 0 Neurons). 결과를 `docs/sdd/research/github-source-measurement.md`에 측정 조건과 함께 덧붙일지는 사람이 정한다

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1(Phase 3) → US3(Phase 4) → US2(Phase 5) → US4(Phase 6) → Polish(Phase 7) → 사람 단계.
- US3은 US1의 `service.py` 뼈대에, US2는 US3의 헤더(크기 판정에 필요)에 기댄다. US4의 경고는 US1 뒤라면 US2·US3과 독립이지만 같은 `service.py`를 고치므로 US2 뒤에 한다.
- 같은 파일을 고치는 작업(T016·T023·T027·T031은 `service.py`, T015·T021은 `sections.py`)은 순서대로 한다.
- 각 단계의 시험 작업([P])을 먼저 쓰고 실패를 확인한 뒤 구현 작업을 한다.

## Parallel Opportunities

- Phase 1: T003은 T001·T002와 병렬.
- Phase 2: 시험 T005·T007·T009를 먼저 병렬로 쓴다. 구현은 T004 → T008 → T006 순서다(T008은 타입, T006은 `PARSER_VERSION`이 필요).
- 각 스토리의 픽스처·시험 작업(T010~T014, T018~T020, T024~T025, T028~T029)은 서로 병렬.
- Polish: T032·T033·T035·T036·T037은 병렬, T034는 T035와 짝. T038은 맨 마지막.

## Implementation Strategy

1. **MVP = Phase 1~3(US1)**: 절 단위 청크와 위치·재현성. 이것만으로 QK-SYN-001이 계약을 맞춰 볼 수 있다(크기 상한은 아직 없음).
2. US3 → US2로 헤더와 크기 상한을 더하면 Phase 1 색인에 쓸 수 있다(1.8의 남은 선행 해소).
3. US4 경고와 Polish(측정 CLI, 비노출, 성능 회귀)로 마무리하고, 사람 단계 H01로 SC-011을 닫는다.

## 실행 기록 (2026-10-21, 실행 에이전트)

- 시작: `feat/SCRUM-101-gh-46-markdown-chunker`, HEAD `575fdca`, 작업 트리 깨끗함. 승인된 Scope와 연결 확인. 외부 호출·스테이징·커밋 없음.
- 인터페이스 점검: 타입 → 블록 파서 → 버전 → 서비스 → 헤더 → 분할 → 경고 → 측정 CLI 순서. T006은 T008 뒤 실행(목록의 의존 규칙). 공개 계약과 소비자 서명 일치.
- Phase 1 RED: 경계 검사 2건 NameError → GREEN 4 passed. `uv lock`, `uv sync --locked`, 버전 출력 `4.2.0` 성공.
- 환경 판단: 기본 uv 캐시는 쓰기 불가, 읽을 수 있는 캐시를 `/private/tmp/qk-chk-uv-cache`에 복사. 오프라인 메타데이터가 없어 기존 lock의 동일 패키지 연결을 먼저 추가한 뒤 `uv lock` 재검증 성공(21 packages). 패키지 버전·해시 변경 없음. 이후 모든 uv 명령은 `UV_CACHE_DIR=/private/tmp/qk-chk-uv-cache UV_OFFLINE=1` 사용. 빌드 도구 버전 경고는 그대로 보고하며 suppress하지 않음.
- Phase 2 RED: 아직 없는 3개 모듈의 수집 오류 → GREEN `uv run pytest tests/unit/chunking tests/unit/test_boundaries.py -q`: 38 passed.

- Phase 3 RED: 공개 진입점·sections 미구현 수집 오류 → GREEN `uv run pytest tests/unit/chunking tests/unit/test_boundaries.py -q`: 62 passed. 기대 JSON은 구현을 호출하지 않고 합성 원문과 명시한 범위로 작성.

- Phase 4 RED: 제목·헤더 기대 시험 16 failed → GREEN `uv run pytest tests/unit/chunking tests/unit/test_boundaries.py -q`: 82 passed. 제목 우선순위·경로 국소성 확인.

- Phase 5 RED: 크기·경계 기대 시험 23 failed → GREEN `uv run pytest tests/unit/chunking tests/unit/test_boundaries.py -q`: 129 passed. 기대값 변경 없음, 모든 깊이의 상한 이하 블록 보존과 split_blocks 대조 포함.

- Phase 6 판단: `a | b / - | - / onecell` 합성 단위 시험은 구분 행이 목록으로 해석되어 표가 아니었음(해석기 토큰으로 확인). research R-11은 **표 토큰 범위만** 경고한다고 정하므로 원래 입력은 경고 없음 사례로 보존하고, 경고 사례 구분 행을 `--- | ---`로 명확히 함. 기대 JSON 변경 없음. 긍정 표 시험에는 실제 table 토큰 존재 검사 추가.

- Phase 6 RED: 경고 시험 11 failed(추가 원인 점검 포함) → GREEN `uv run pytest tests/unit/chunking tests/unit/test_boundaries.py -q`: 176 passed. 경고 규칙 변경 시 청크·버전 불변, 언어 표시 독립 확인.

- Phase 7 판단: 기존 PATH 출력 정책은 `.md` 파일 이름의 점 이름을 보존하므로 email 모양 파일명도 그대로일 수 있음. 이 범위에서 정책을 바꾸지 않고 측정의 safe_text 호출(종류 PATH·context 전달·반환값 사용)을 주입 시험으로 검증. 기존 보안 정책 코드 변경 없음.

- Phase 7 RED: `--chunk` 인자·측정 옵션 미구현 4 failed → GREEN 217 passed(청커·측정 CLI·경계). 추가 합성 표·비노출 사례 검증 중.
- T036: 측정 스크립트 `time_chunking`의 호출 서명·`outcome`·`drafts`·`chunking_version` 사용이 공개 계약과 일치함을 읽어서 확인. 수정·실행 없음(H01은 사람 단계).
- T033 입력 고정: seed `20261021`, 79개, 1,447,811바이트, SHA-256 `4bebfaa6fdc9a802f3b572c2103ffd61caae30a9fedee2ba75870feef9ee2751`. 회귀 시험 약 0.4초(완료 판정 아님). Ruff S311이 `random.Random` 생성자를 금지하므로 T033 명시 요구와 경고 suppress 금지의 충돌을 사용자에게 질의함. 예외·설정 변경 없이 대기.
- 추가 판단: `- a | b`·`1. a | b`로 시작하는 표는 해석기 우선순위상 최상위 표가 될 수 있음(독립 토큰 확인). 컨테이너 깊이는 모양이 아니라 실제 list_item·blockquote 토큰 수(R-11)를 따름. JSON 기대 경계·텍스트 변경 없음. 명확한 표 문법의 합성 픽스처를 추가해 깊이 1·0·0·2 검증.

- Phase 7 체크포인트: `uv run pytest tests/unit/chunking tests/unit/devtools/test_measure.py tests/unit/test_boundaries.py -q --tb=short --durations=3`: 224 passed, 합성 성능 시험 약 0.41초. 기대 JSON 최종 필수 키 검사와 키 누락 시 실패하는 검사 포함.
- T038 환경: `qk-dev db up`은 실제 `.env`를 읽지 않도록 `--env-file /dev/null`, Docker에는 `COMPOSE_DISABLE_ENV_FILE=1`을 사용. 로컬 이미지 존재를 먼저 확인(다운로드 없음). 샌드박스의 Docker socket 접근 제한은 자동 승인된 로컬 실행으로 해소. DB 준비·vector·pgroonga 확인 성공.
- T038 첫 전체 시험: `QK_REQUIRE_LOCALDB=1 uv run pytest`는 샌드박스 루프백 bind/connect 제한으로 2 failed, 1011 passed, 86 errors, 2 deselected. 코드·시험 수정 없이 로컬 소켓 접근을 허용받아 같은 명령 재실행 → **1099 passed, 2 deselected, 9.06초**. skip·xfail·경고 suppress 추가 없음. 제외 2개는 원래 기본 설정의 external 시험.
- T038 `python scripts/preflight.py`: 통과(초기 488 files, 최종 다시 확인). `git diff --check`: 통과. `uv run ruff format --check .`: 통과. `uv run ruff check .`: **S311 1건 실패**, `tests/unit/chunking/test_perf.py`의 T033 필수 `random.Random(20261021)` 때문. 입력 생성·성능 시험은 구현·통과했으나 T038은 미완료. 명시적인 경고 suppress 금지에 따라 noqa·ignore·정적 분석 우회 없음. 사람 결정 필요.
- H01·H02 미실행. 실제 SC-011 완료 판정·독립 리뷰는 이 실행 세션에서 승인하지 않음. 원본 호출 0, 임베딩·생성 호출 0, 0 Neurons. 실제 `.env`·`secrets/` 읽기 없음(기존 설정 시험은 임시 합성 파일만 사용). 원본 대상 문서 복사 없음.
- 로드맵 상태 갱신은 현재 요청의 외부 호출 0건 제약 때문에 실행하지 않음(작업 T001~T038 밖). 승인된 명세·설계·측정 스크립트 변경 없음.

- 최종 정적 검사: preflight **490 files 통과**, diff 공백 통과, ruff format **325 files 통과**, ruff check **S311 한 건 실패**. 변경 92파일(추적 8·신규 84), staged 0, 브랜치·HEAD 그대로. T038과 사람 단계 H01·H02는 미체크 유지.

### 변경 파일 목록

- 기존: `TASK.md`, 이 `tasks.md`, `pyproject.toml`, `uv.lock`, `src/qello_knowledge/devtools/db.py`, `src/qello_knowledge/devtools/measure.py`, `tests/unit/test_boundaries.py`, `tests/unit/devtools/test_measure.py`.
- 신규 도메인: `src/qello_knowledge/domain/chunking.py`.
- 신규 `src/qello_knowledge/chunking/` 8개: `__init__.py`, `blocks.py`, `sections.py`, `header.py`, `split.py`, `warnings.py`, `version.py`, `service.py`.
- 신규 `tests/unit/chunking/` 15개: `__init__.py`, `helpers.py`, `test_blocks.py`, `test_determinism.py`, `test_domain.py`, `test_expected.py`, `test_header.py`, `test_invariants.py`, `test_locality_titles.py`, `test_no_leak.py`, `test_perf.py`, `test_screened.py`, `test_size.py`, `test_version.py`, `test_warnings.py`.
- 신규 `tests/fixtures/chunking/` 60개: 아래 30개 이름마다 `.md`와 `.expected.json` 한 쌍.
  `adr_like`, `big_fence`, `big_list`, `big_list_item`, `big_table`, `broken_table`, `decorated_heading`, `duplicate_heading`, `fence_heading`, `front_matter`, `front_matter_title`, `head_section`, `header_too_long`, `heading_only`, `html_block`, `lang_css`, `lang_mermaid`, `level_skip`, `line_too_long`, `long_section`, `multi_paragraph_quote`, `nested_tables`, `nested_tables_valid`, `no_title`, `paragraph_between`, `refdef`, `sections_basic`, `setext_multiline`, `three_times_limit`, `unclosed_fence`.

### T038 재검증 — S311 사용자 결정 반영 (2026-10-21)

- `TASK.md`에 기록된 사용자 결정에 따라 `test_perf.py`의 `random.Random(20261021)` 한 줄에만 `# noqa: S311 - 재현 가능한 합성 데이터용이다`를 적용했다. 다른 suppress·설정 변경 없음. `pyproject.toml`은 index 전용 주석만 추가했고 의존성 값은 그대로다.
- `uv lock --check`: PASS, 21 packages. `python scripts/preflight.py`: PASS, 490 files. `git diff --check`: PASS. `uv run ruff check .`: PASS. `uv run ruff format --check .`: PASS, 325 files.
- `uv run qk-dev db up --env-file /dev/null`: PASS, vector·pgroonga 확인. `QK_REQUIRE_LOCALDB=1 uv run pytest`: PASS, 1099 passed / 2 deselected, 9.05초. 제외 2개는 기존 기본 설정의 external 시험이며 skip·xfail 추가 없음.
- uv 명령은 기존처럼 `UV_CACHE_DIR=/private/tmp/qk-chk-uv-cache UV_OFFLINE=1`, DB·전체 시험은 `COMPOSE_DISABLE_ENV_FILE=1` 사용. 로컬 Docker·소켓 접근 권한으로 실행했으며 실제 `.env` 읽기·외부 호출 없음. uv 빌드 도구 버전 경고는 숨기지 않았고 명령은 성공했다.
- 이전 S311 BLOCKED 사유 해소. T001~T038 완료(`PASS`, 실행 에이전트 범위). H01·H02와 독립 검증·승인은 여전히 사람/별도 세션 단계. git add·commit·push 없음.

### H01 결과 (2026-10-21, Claude 세션이 사용자 요청으로 대신 실행)

- 명령: quickstart 3절(`measure_inputs.py --time-chunking`, 커밋 `6aeccd0`, 막힌 문서 1개 제외). 외부 호출 0건, 0 Neurons.
- 결과: `files=79`, `total_bytes=1017913`, `by_outcome={"CHUNKED": 79}`, `chunk_count=1291`, `elapsed_seconds=0.18208541604690254`, `chunking_version=chk-md-20d966f730bb`, 환경 `macOS-26.6.2-arm64-arm-64bit-Mach-O / Python 3.13.16`. 통과(≤ 10초).
- 낮음 리뷰 항목 수정 뒤 최종 코드로 다시 실행한 값이다(수정 전 실행도 같은 결과, 0.178초).
