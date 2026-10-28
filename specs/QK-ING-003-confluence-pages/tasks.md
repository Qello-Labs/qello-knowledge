---
description: "QK-ING-003 구현 작업 목록"
---

# Tasks: QK-ING-003 Confluence 페이지 수집, 문서 분류, 회의록·용어집 처리

**Input**: `specs/QK-ING-003-confluence-pages/`의 plan.md, spec.md(FR-001~032, SC-001~014), research.md(R-01~R-19), data-model.md, contracts/(5개), quickstart.md

**Tests**: 포함한다. 수용 시나리오와 C-12(수용 기준은 검증으로 닫는다)가 자동 시험을 요구한다. 시험을 먼저 쓰고 실패를 확인한 뒤 구현한다.
모든 시험은 외부 호출 0건이다(재생 전송·가짜 제공자, 0 Neurons). 실제 Confluence 확인은 맨 끝 "사람 단계"다.

**Organization**: 사용자 스토리별 단계다. 순서는 P1(US1 → US2 → US3) 다음 P2(US4 → US5 → US6)다. 공통 형식·등록·버전 장치는 Phase 2에 모은다.

**선행 조건**:
- spec.md 승인(2026-10-28, R2 해석 포함), plan.md 승인(2026-10-28)과 plan 검토 반영(P3·P5 사용자 결정)
- 이 목록의 사람 승인, `TASK.md` Scope·Validation·완료 조건 갱신(AGENTS.md 1절)
- 단계 게이트 1.G 미완료 상태의 진행은 2026-10-27 사용자 결정(TASK.md)

**공통 규칙**:
- 비노출: 페이지 제목·제목 경로·본문·사람 이름·계정 ID·메일·Cloud ID·사이트 주소·토큰을 로그·예외 문구·요약·측정 출력에 넣지 않는다. 페이지는 ID로만 가리킨다(FR-011, FR-027, SC-004).
- 합성 자료만: 시험 응답은 시나리오 빌더(`tests/unit/adapters/confluence_scenarios.py`)가 만든다. 사이트 호스트는 `site.invalid`, 이름은 `팀원A` 같은 합성 값, 계정 ID는 `acct-000` 같은 합성 값이다.
  비밀값 모양 문자열은 `tests/unit/synthetic_secrets.py` 도우미로 실행 중에 만든다. 커밋 전에 `uv run python scripts/preflight.py`의 종료 코드를 확인한다.
- 기대값: ADF 변환 기대 Markdown·경고(`tests/fixtures/confluence/adf/`)는 사람이 정하는 정답이다. 구현 결과로 덮어쓰지 않는다(AGENTS.md 9절). 검색 평가 세트가 아니다(AGENTS.md 3.4).
- 통과 방식: 시험을 지우거나 `skip`·`xfail`로 통과시키지 않는다. 경고를 suppress하지 않는다. 새 `# noqa`가 필요하면 멈추고 사람에게 묻는다.
- 기존 시험: 기대값을 바꾸지 않는다. 사례를 **더하기만** 한다. 특히 다음은 그대로 통과해야 한다.
  - `tests/unit/sync/test_keys.py`(`iv-4c0bc4fcc642`, `chunk_input_hash` 기존 사례), `tests/unit/chunking/test_version.py`(`chk-md-20d966f730bb`), `tests/unit/chunking/test_keyword_rule_version.py`
  - `tests/unit/devtools/test_measure.py`(GitHub 측정 출력 고정값), `tests/unit/adapters/test_http_transport.py`(GitHub 헤더), `tests/unit/sources/test_scope_review.py`
  - `tests/contract/` 기존 계약 시험, `tests/unit/security/` 기존 시험(보안 규칙 버전 값 고정 시험은 없다, research R-19)
- 시험 파일 이름: 새 파일 이름에 `confluence`나 `atlassian`을 넣는다. `__init__.py`가 없는 폴더에서 pytest 수집 이름이 겹치지 않게 하려는 것이다(research R-18).
- 경계: `domain`·`ports`는 표준 라이브러리만(`tests/unit/test_boundaries.py`). `sources`는 `adapters`를 가져오지 않는다. 새 dataclass 필드는 끝에 기본값과 함께 둔다.
- 꺼짐 불변: Confluence 꺼짐 설정에서 인덱스·메타데이터·청킹 버전과 GitHub 문서의 `chunk_input_hash`·`locator`·검색 헤더·임베딩 입력·판정 기록(보안 규칙 버전 제외)이 지금과 같다(SC-014).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일이고 미완료 작업에 기대지 않아 병렬로 할 수 있다.
- **[Story]**: 사용자 스토리(US1~US6). Setup·Foundational·Polish에는 없다.

---

## Phase 1: Setup

- [X] T001 시험 자리 만들기: 폴더 `tests/unit/adapters/confluence/`, `tests/fixtures/confluence/adf/`를 만들고, 합성 응답 빌더 뼈대 `tests/unit/adapters/confluence_scenarios.py`를 둔다.
  `Scenario`는 스페이스(종류·상태·ID·키·`homepageId`), 페이지(ID·제목·`parentId`·`parentType`·버전·본문 ADF), 폴더, 보기 제한 상태, 응답 덮어쓰기(상태 코드·`Retry-After`)를 받아
  `ReplayTransport(exchanges)`(`src/qello_knowledge/adapters/replay.py`)를 돌려준다. 게이트웨이 기준 주소는 `https://api.atlassian.com/ex/confluence/cloud-test/wiki/api/v2`다.
- [X] T002 [P] 합성 확인 기록 픽스처 `tests/fixtures/source_reviews/confluence-ok.toml`, `confluence-no-names.toml`, `confluence-scope-mismatch.toml`, `confluence-site-expired.toml`(contracts/source-config.md 예 형식, 이름·메일 없음)

---

## Phase 2: Foundational (모든 스토리의 선행)

**시험 먼저**

- [X] T003 [P] 공통 형식 시험 `tests/unit/domain/test_confluence_source_fields.py`: `SourceItem.exclusion` 기본 `None`, `ListPage.incomplete_reason` 기본 `None`·`list_all`이 사유를 `Listing`에 옮김, `SourceContent.locator_extra`·`fingerprint_extra` 기본 `None`, `conversion_warnings` 기본 `()`, `ConversionWarning(kind, block)`의 `kind`가 `UNSUPPORTED_BLOCK`·`TABLE_FLATTENED`·`MEETING_METADATA_MISSING`·`NOT_GLOSSARY`만 받음, `MissingCheck` 네 값, 기존 위치 인자 생성이 그대로 동작
- [X] T004 [P] 키 시험 사례 추가 `tests/unit/sync/test_keys.py`: `chunk_input_hash(..., extra=None)`이 기존 고정값과 같음, `extra`가 있으면 달라짐, `scope_key("confluence_pages", …)`가 `confluence_pages:<space_id>`, `metadata_schema_version(code, confluence)`가 (꺼짐, 꺼짐) `meta-v1`, (켜짐, 꺼짐) `meta-v2`, (꺼짐, 켜짐) `meta-v1+cf1`, (켜짐, 켜짐) `meta-v2+cf1`. 기존 사례·고정값은 고치지 않는다
- [X] T005 [P] 보안 등록·출력 시험 `tests/unit/security/test_opaque_fields.py`: `KindSecurityPolicy` 새 필드 기본값(`opaque_item_fields=False`, `lookup_failure_threshold=None`), `opaque_item_fields`면 `to_dict`의 `title`·`location`·`url`이 `None`(모든 판정), GitHub `to_dict` 결과가 지금과 같음
- [X] T006 [P] PATH 표시 시험 `tests/unit/security/test_confluence_exclusion_stage.py`: `exclusion` 값마다 `PATH_EXCLUDED`·규칙 `source-exclude:<값>`, 본문 요청 0건, `exclusion=None`이면 기존 PATH 판정 그대로
- [X] T007 [P] 전송 주입 시험 사례 추가 `tests/unit/adapters/test_http_transport.py`: `authorization` 함수·`default_headers`를 주면 그 값이 붙고 GitHub 고정 헤더가 붙지 않음, 주지 않으면 기존 사례 그대로
- [X] T008 [P] 설정 검증기 시험 `tests/unit/sources/test_config_confluence.py`(형식만): `SourceKindSpec.scope_schema`로 GitHub 기존 결과(`repo` 정규식, 결과 코드·메시지) 그대로, `confluence_pages` 범위 값 규칙 —
  "`include`: 정확히 `[\"**\"]`", "`space_key`: 비지 않음, `~`로 시작하면 오류", "`space_id`: 활성이면 필수 숫자 문자열", "`judge_mode`: `team_group`·`site_users`",
  "`team_group_id`: `team_group`이면 필수, `site_users`면 없어야 함", "`doc_types`: 키는 숫자 문자열, 값은 `회의록`·`용어집`·`기능 명세`·`설계 문서`·`API 문서`·`디자인 문서`·`개발 규칙`·`색인 안 함`",
  "`exclude_trees`: 숫자 문자열 목록, 중복 없음", "`exclude`: 있으면 오류". 표·목록 값의 `extra` 정규화(키 정렬, `separators=(",", ":")`, `ensure_ascii=False`)

**구현**

- [X] T009 공통 형식 확장 `src/qello_knowledge/domain/source.py`(필드·`ConversionWarning`·`MissingCheck`·`ListPage.incomplete_reason`, `sources/collect.py`의 `Listing`으로 사유 전달)와 선택 Protocol `MissingItemChecker.check_missing(session, config, source_ids) -> Mapping[str, MissingCheck]` `src/qello_knowledge/ports/source.py` (T003 통과)
- [X] T010 키 확장 `src/qello_knowledge/sync/keys.py`: `chunk_input_hash` 선택 인자 `extra`, `scope_key` Confluence 분기, `metadata_schema_version(code=None, confluence=False)`(기존 호출 그대로 동작) (T004 통과)
- [X] T011 보안 등록 필드와 출력 `src/qello_knowledge/security/kinds.py`, `src/qello_knowledge/domain/redact.py`(`OutputContext.opaque_item_fields`), `src/qello_knowledge/security/policy.py`(`output_context` 전달), `src/qello_knowledge/domain/security.py`(`to_dict`) (T005 통과)
- [X] T012 PATH 단계 표시 처리 `src/qello_knowledge/security/screen.py`: `item.exclusion`을 기존 제외 검사보다 먼저 본다 (T006 통과)
- [X] T013 [P] 전송 인증 주입 `src/qello_knowledge/adapters/http.py`: 키워드 인자 `authorization: Callable[[], str] | None`, `default_headers`. 기본값이 지금 동작(`Bearer`, `x-github-api-version`)을 바이트 단위로 만든다 (T007 통과)
- [X] T014 종류 사양 확장 `src/qello_knowledge/sources/kinds.py`(`scope_schema`, `extra_auth`, `confluence_pages` 등록: 인증 필요, 기본 허용 호스트 `("api.atlassian.com",)`, 추가 인증 `ATLASSIAN_EMAIL`·`ATLASSIAN_CLOUD_ID`)와
  `src/qello_knowledge/sources/config.py`(종류 검증기 호출, GitHub `repo` 규칙을 GitHub 사양으로 옮김, 비활성 자료원은 지금처럼 범위 미파싱) (T008 통과)
- [X] T015 [P] 설정 항목 `src/qello_knowledge/config/registry.py`: `ATLASSIAN_API_TOKEN`·`ATLASSIAN_EMAIL`·`ATLASSIAN_CLOUD_ID`·`ATLASSIAN_SITE_URL`(INDEX, `secret=True`, `required=False`).
  설정 예시 파일은 `uv run python -m qello_knowledge.config.example`로 다시 만들고 예시 동기화 시험을 통과시킨다(에이전트는 예시 파일을 직접 열지 않는다)
- [X] T016 계획 결과 필드 `src/qello_knowledge/domain/sync.py`: `SourcePlan.incomplete_reason: str | None = None`. 값은 `missing_check_present`·`missing_check_stopped`·`access_lookup_threshold` 중 하나
- [X] T017 종류별 대상 조립 `src/qello_knowledge/indexer/sync_cli.py`: `github_targets`를 종류 → (어댑터, 전송) 팩토리 표로 일반화. GitHub 조립 결과·오류(`unsupported_source_kind` 대신 등록 안 된 종류만 오류)는 그대로.
  기존 `tests/unit/indexer/` 시험이 그대로 통과한다

**Checkpoint**: Phase 2 뒤 `QK_REQUIRE_LOCALDB=1 uv run pytest`가 모두 통과하고 GitHub 관련 기대값 변경이 0건이다.

---

## Phase 3: User Story 1 - 팀 스페이스의 현재 페이지 목록을 빠짐없이 받는다 (P1) 🎯 MVP

**Goal**: 스페이스 하나의 현재 페이지 목록·원본 링크·위치·변경 판별값을 결정적으로 만든다(FR-001~005).

**Independent Test**: 재생 응답으로 목록을 두 번 받아 기대 목록과 같고 중복·초안이 0건이다(SC-001).

- [X] T018 [P] [US1] 목록 시험 `tests/unit/adapters/confluence/test_confluence_listing.py`: 여러 쪽(`_links.next` 경로를 게이트웨이 뒤에 잇기, 절대 주소면 호스트 버림), 쪽 경계 중복 제거, 한 쪽 영구 실패 → `complete=False`,
  `status=current` 파라미터, 같은 응답 두 번 → 같은 항목·순서(ID 오름차순)·판별값, 제목만 바뀜 → `change_key` 바뀜(`<version.number>:<sha256(title)[:12]>`), `location` 정규화(`/`→`／`, 빈 제목 `(제목 없음)`, `.`·`..`→`．`·`．．`),
  `url` = `_links.base` + `_links.webui`, `_links.base` 없음 → `ATLASSIAN_SITE_URL`, 둘 다 없음 → `complete=False`, 응답 스페이스 ID ≠ 설정 `space_id` → 그 뒤 요청 0건·`complete=False`·`origin`에 실제 값,
  `type=personal` → 페이지 요청 0건·`complete=False`, 첫 `ListPage.origin = SourceOrigin(space_id, space_key, None)`,
  불완전 사유 `space_not_found`·`space_id_mismatch`·`personal_space`·`site_base_missing`·`listing_failed`가 `ListPage.incomplete_reason`에 남음
- [X] T019 [US1] 어댑터 목록 `src/qello_knowledge/adapters/confluence.py`: `ConfluencePagesAdapter(kind="confluence_pages")`의 `list_page`(커서 무시, 한 번에 전체) 중 스페이스 조회·페이지 목록·항목 매핑(data-model 6절).
  생성 인자는 판정 방식, 팀 그룹 ID, 사이트 사용자 확인 기록 유효 여부, 사이트 기준 주소 대체값이다. 권한 원값은 US2 전까지 `AccessInfo(UNKNOWN)`로 둔다 (T018 통과)
- [X] T020 [US1] 대상 조립 연결 `src/qello_knowledge/indexer/sync_cli.py`: `confluence_pages` 팩토리(전송: `auth_hosts=("api.atlassian.com",)`, `Basic base64(email:token)` 생성 함수, `accept: application/json`, 게이트웨이 기준 주소에 Cloud ID).
  토큰·메일·Cloud ID는 `SecretValue.reveal()`로 꺼내 전송·어댑터 안에서만 쓴다

**Checkpoint**: US1 시험 통과. 권한이 아직 미확인이라 모든 페이지가 `ACCESS_HELD`로 색인되지 않는다(안전한 중간 상태).

---

## Phase 4: User Story 2 - 원본 권한을 접근 범위로 옮겨, 팀 공용 페이지만 색인된다 (P1)

**Goal**: 스페이스 종류·상태·팀 그룹 또는 사이트 사용자 확인·자신과 상위 보기 제한으로 판정하고, 사라진 페이지와 조회 실패를 안전하게 다룬다(FR-006~012, FR-030, FR-031).

**Independent Test**: 권한 사례 재생 응답으로 수집·보안 필터·계획을 돌려 판정이 표와 같고 팀 공용 아닌 청크가 0건이다(SC-002).

- [X] T021 [P] [US2] 판정 함수 시험 `tests/unit/security/test_confluence_judge.py`: data-model 4절 표 전 사례 — 팀 종류 셋(`global`·`collaboration`·`knowledge_base`)·`system`·모르는 값, `space_status` `current`·`archived`,
  `team_group_read`·`site_review_valid` 참·거짓·누락·`judge_mode`와 안 맞는 키, `read_restricted` `none`·`self`·`ancestor`·`unknown`, 원값 키 순서 고정
- [X] T022 [P] [US2] 권한 원값 시험 `tests/unit/adapters/confluence/test_confluence_access.py`: `team_group` 모드의 권한 할당 매칭(`principal.type=group`, 설정 그룹 ID, `operation.key=read`, `targetType=space`, 다른 할당 무시),
  `site_users` 모드는 권한 요청 0건, 자신·상위 페이지·상위 폴더 `VIEW_RESTRICTED`, `EDIT_RESTRICTED`는 제한 없음, 모르는 상태 값 → `unknown`, 사슬이 목록 밖 페이지·페이지와 폴더가 아닌 상위에서 끊김 → `unknown`,
  보기 제한·폴더 요청 403·404·429 소진 → `AccessInfo(UNKNOWN)`, 콘텐츠마다 보기 제한 요청 1회(하위가 다시 씀), 폴더 사슬 `GET /folders/{id}` 1회씩
- [X] T023 [P] [US2] 단건 확인 시험 `tests/unit/adapters/confluence/test_confluence_missing.py`: 403·404 → `GONE`, 다른 스페이스 → `GONE`, `archived`·`trashed`·`deleted` → `ARCHIVED`, `current`·같은 스페이스 → `PRESENT`,
  그 밖의 상태·크기 초과·잘못된 응답·429·5xx → `UNCERTAIN`, 요청에 상태 `current`·`archived`·`trashed`·`deleted` 명시
- [X] T024 [P] [US2] 계획 시험 `tests/unit/sync/test_plan_confluence.py`: (1) 사라진 페이지 결과별 결정(`GONE` → `SECURITY_ACCESS` 보안 내림·일반 내림 수 제외, `ARCHIVED` → `SOURCE_MISSING`, `PRESENT` → 내림 0·`COLLECTION_INCOMPLETE`·`incomplete_reason=missing_check_present`,
  `UNCERTAIN` → 그대로), 확인 중 `RunStopped` → 남은 후보 그대로·`missing_check_stopped`, 이미 끝난 `SECURITY_ACCESS` 내림은 단건 요청 0건. (2) 조회 실패 기준: 10% 이하 → 기존대로 본문 삭제,
  초과 → 해당 문서 `delete_bodies=False`·`purge`·`pending` 수 제외·`--confirm-takedown`에서도 `PURGE` 없음·`access_lookup_threshold`, 비밀값 차단 문서는 그대로 숨김(본문 삭제는 비율 보류를 따름),
  규칙상 미확인(`read_restricted=unknown`, 기록 만료)은 실패로 세지 않음. (3) `MissingItemChecker`가 아닌 어댑터(GitHub·가짜)는 결정·요청 수가 지금과 같음
- [X] T025 [P] [US2] 보안 규칙 버전 재료 시험 `tests/unit/security/test_confluence_policy_version.py`: `judge_mode`나 확인 기록 sha256이 바뀌면 버전이 바뀌고, 종류별 재료가 없으면 지금 재료와 같다
- [X] T026 [US2] 판정 함수와 등록 `src/qello_knowledge/security/kinds.py`: `judge_confluence_access`, `KindSecurityPolicy("confluence_pages", "confluence-access-v1", …, public_link_hosts=(), source_id_is_path=False, opaque_item_fields=True, lookup_failure_threshold=0.10)` (T021 통과)
- [X] T027 [US2] 어댑터 권한 단계 `src/qello_knowledge/adapters/confluence.py`: 스페이스 권한(`team_group`), 폴더 사슬, 보기 제한 상태, 원값 계산, 조회 실패 표시, `check_missing` (T022·T023 통과)
- [X] T028 [US2] 계획 확장 `src/qello_knowledge/sync/plan.py`: 사라진 자료 단건 확인(끝난 `SECURITY_ACCESS` 제외, `RunStopped` 처리), 조회 실패 기준(종류의 `lookup_failure_threshold`), `incomplete_reason`·`listing_complete` (T024 통과)
- [X] T029 [US2] 종류별 보안 버전 재료 `src/qello_knowledge/security/policy.py`(`load_policy`에 종류별 재료 인자)와 `src/qello_knowledge/indexer/sync_cli.py`(`run_command`가 확인 기록을 읽은 뒤 `judge_mode`·기록 sha256 전달),
  사이트 사용자 확인 유효 여부(`site_users.reviewed_on + 90일 ≥ 오늘(UTC 날짜)`) 계산 후 어댑터 생성 인자로 전달 (T025 통과)

**Checkpoint**: 권한·사라진 페이지·조회 실패 사례가 통과하고, 팀 공용이 아닌 페이지의 본문 요청이 0건이다.

---

## Phase 5: User Story 3 - 본문을 Markdown으로 바꿔 청커에 넘기고, 잃는 내용은 경고로 남긴다 (P1)

**Goal**: ADF를 결정적으로 Markdown으로 바꾸고 변환 경고·링크·멘션 규칙을 지키며, 변환 규칙 버전이 Confluence 문서의 변경 판정에만 들어간다(FR-013~019, FR-019a).

**Independent Test**: 합성 ADF 사례가 사람이 쓴 기대 Markdown·경고와 바이트 단위로 같다(SC-003, SC-012).

- [X] T030 [P] [US3] 기대값 픽스처(사람이 정함) `tests/fixtures/confluence/adf/`: contracts/adf-markdown.md "시험" 사례마다 `<사례>.json`, `<사례>.md`, `<사례>.warnings.json`. 링크 사례는 사이트 일반 경로, `/wiki/people/…`,
  `/wiki/display/~…`, `~`로 시작하는 경로 조각, 등록 호스트(`github.com`), 그 밖의 공개 주소, 쿼리·조각, `mailto:`, 텍스트가 버린 주소와 같은 자동 링크(→ `[링크]`)를 모두 넣는다
- [X] T031 [P] [US3] 변환 시험 `tests/unit/adapters/test_atlassian_adf.py`: 픽스처 전체 일치, 두 번 변환 바이트 같음, 계정 ID(`attrs.id`)·메일 주소가 결과에 0건, 이미지·첨부만 있는 페이지 → 빈 본문, 경고에 원문 없음
- [X] T032 [P] [US3] 본문 시험 `tests/unit/adapters/confluence/test_confluence_content.py`: `GET /pages/{id}?body-format=atlas_doc_format`, `value` JSON 문자열 재파싱, 크기 초과 → 그 페이지만 영구 실패, ADF 최상위가 `doc`가 아님 → `InvalidResponse`,
  `SourceContent` 필드(data-model 6절: `content_format=MARKDOWN`, 첫 줄 `# <제목>`, `locator_extra`, `fingerprint_extra`), 판정을 통과하지 못한 페이지의 본문 요청 0건
- [X] T033 [US3] 변환기 `src/qello_knowledge/adapters/atlassian_adf.py`: `convert_adf(doc, *, title, site_host, public_link_hosts, doc_type) -> ConvertResult`, 규칙 버전 `adf-md-v1`, 블록·인라인·링크·본문 없음 규칙(contracts/adf-markdown.md) (T031 통과)
- [X] T034 [US3] 어댑터 본문 `src/qello_knowledge/adapters/confluence.py`의 `fetch_content`. `public_link_hosts`는 보안 종류 표의 합집합을 대상 조립에서 넘긴다 (T032 통과)
- [X] T035 [P] [US3] 동기화 연결 시험 사례 추가 `tests/unit/sync/test_plan_confluence.py`: 변경 판정이 `chunk_input_hash(..., extra=content.fingerprint_extra)`를 쓴다, 청크 `locator`에 `confluence` 키가 합쳐지고 `path`·`lines`가 그대로, 키 충돌이면 오류
- [X] T036 [US3] `src/qello_knowledge/sync/plan.py`(지문 `extra`)와 `src/qello_knowledge/sync/execute.py`(`locator_extra` 합치기) (T035 통과)

**Checkpoint**: P1 완료. 재생 응답으로 목록 → 판정 → 본문 → 변환 → 청킹이 이어지고 기본 검증이 통과한다.

---

## Phase 6: User Story 4 - 문서 종류를 정하고 회의록에서 날짜·결정·액션 아이템을 찾게 한다 (P2)

**Goal**: 첫 단계 콘텐츠 ID 대응표로 문서 종류를 정하고, 미분류·홈·제외 트리를 색인하지 않으며, 회의록 메타데이터를 남긴다(FR-020~022).

**Independent Test**: 대응표·제외 트리 사례에서 `exclusion`과 문서 종류가 기대값과 같고, 회의록 메타데이터가 정확하다(SC-005, SC-011).

- [X] T037 [P] [US4] 분류 시험 사례 추가 `tests/unit/adapters/confluence/test_confluence_listing.py`: `space-home`, `outside-home`, `unclassified`, `not-indexed-type`, `excluded-tree`(트리 맨 위와 하위, 폴더 포함), 첫 단계 페이지 자신의 종류,
  첫 단계 제목만 바뀐 경우 종류 그대로, 제외 트리 맨 위 제목이 바뀌어도 제외 유지, 표시된 페이지의 본문 요청 0건
- [X] T038 [P] [US4] 회의록 사례(T030 픽스처에 더함)와 시험 `tests/unit/adapters/test_atlassian_adf.py`: `일시` `2026-10-14` → `meeting.date`, `회의 종류`, `관련 명세 ID` 쉼표 분리·`없음` 제외, `일시` 없음·형식 틀림 → `meeting=None`과 `MEETING_METADATA_MISSING`, 제목의 날짜는 쓰지 않음
- [X] T039 [US4] 어댑터 분류 `src/qello_knowledge/adapters/confluence.py`: 첫 단계 콘텐츠 찾기, `doc_types`·`exclude_trees`로 `exclusion`·문서 종류 결정, `locator_extra`·`fingerprint_extra`에 문서 종류 반영 (T037 통과)
- [X] T040 [US4] 변환기 회의록 처리 `src/qello_knowledge/adapters/atlassian_adf.py` (T038 통과)

**Checkpoint**: 미분류·제외 페이지는 보안 내림으로만 가고, 회의록 메타데이터가 `locator["confluence"]`로 나온다.

---

## Phase 7: User Story 5 - 용어집 한 줄이 한 검색 단위가 된다 (P2)

**Goal**: 용어집 표를 행마다 절로 바꿔 행 하나가 청크 하나가 되게 한다(FR-023).

**Independent Test**: 5행 합성 용어집이 청크 5개가 되고 각 청크에 용어·정의·동의어·식별자가 있다(SC-006).

- [X] T041 [P] [US5] 용어집 사례(T030 픽스처에 더함: 정상 5행, 머리글 다름 → `NOT_GLOSSARY`)와 청크 시험 `tests/unit/chunking/test_confluence_glossary_chunks.py`: 변환 결과를 `chunk_markdown`에 넣어 행 수 = 용어 청크 수, 각 청크에 네 값
- [X] T042 [US5] 변환기 용어집 처리 `src/qello_knowledge/adapters/atlassian_adf.py`: 머리글이 정확히 `용어 | 정의 | 동의어·약어·영문 | 코드 식별자·API 경로 | 관련 문서`인 표를 `## <용어>`와 `- <머리글>: <값>`(빈 값 생략)으로 (T041 통과)

---

## Phase 8: User Story 6 - 자료원을 비활성으로 등록하고, 사람 확인과 실측 뒤에 켠다 (P2)

**Goal**: 비활성 등록, 확인 기록 강제, 켜짐 인덱스 버전 막기, 응답 분류, 측정 도구를 갖춘다(FR-024~029, FR-032).

**Independent Test**: 확인 기록·설정 실패 사례가 원본 호출 0건으로 실패하고, 꺼짐 설정의 버전 값이 그대로다(SC-007, SC-008, SC-014).

- [X] T043 [P] [US6] 확인 기록 시험 `tests/unit/sources/test_scope_review_confluence.py`: data-model 3절 규칙 — `result`는 `팀원 이름 외 개인 정보 없음`·`개인 정보 트리 제외함`, 뒤의 값이면 `moved_to_exclude`의 `id`가 `exclude_trees`에 있음,
  `team_member_names = "허용"` 없음 → 실패, `site_users` 모드에 `site_users` 없음 → 실패, 범위 불일치 → `REVIEW_SCOPE_MISMATCH`, GitHub 기록 형식·결과 코드 그대로, 이름·메일 키 없음
- [X] T044 [P] [US6] 켜짐 검사 시험 `tests/unit/config/test_confluence_check.py`: "Confluence 켜짐" = 활성 `confluence_pages` 자료원 ∨ 저장된 자료원 정체성 등록, 명령별 계산 순서(research R-10 표: `sources check`는 활성만, `run`은 저장소를 연 뒤 두 번째 검사, `index status/activate`는 저장소를 연 뒤 계산),
  `_code_checks`는 `meta-v2`·`meta-v2+cf1` 중 하나가 대응표에 있으면 통과(둘 다 없으면 기존 `CODE_INDEX_VERSION_UNREGISTERED`, `tests/unit/config/test_code_check.py` 그대로), 켜짐 인덱스 버전이 `INDEX_KEYWORD_RULES`에 없으면
  `CONFLUENCE_INDEX_VERSION_UNREGISTERED`로 원본 호출 0건·저장소 쓰기 0건, 코드 청킹과 함께 켜지면 `meta-v2+cf1`로 검사, 꺼짐이면 `iv-4c0bc4fcc642` 그대로, 활성인데 `ATLASSIAN_*` 셋 중 하나 없으면 `AUTH_MISSING`
- [X] T045 [P] [US6] 응답 분류 시험 `tests/unit/adapters/confluence/test_confluence_classify.py`: 429와 `Retry-After` → 일시적 실패와 그 시간 뒤 재시도, 401 → 실행 정지(남은 요청 0건), 페이지 하나 403 → 그 페이지만 영구 실패, 목록·스페이스 403 → 목록 불완전
- [X] T046 [P] [US6] 측정 시험 `tests/unit/devtools/test_measure_confluence.py`: 비활성 Confluence 자료원 측정(확인 기록 필수, 저장·임베딩 0건), 출력 키(엔드포인트별 요청 수, 소요 시간, 목록 완전성, 페이지 수, 본문 총·최대 바이트, 판정·규칙별 수,
  미분류 수, 변환 경고 종류별 수, 조회 실패 수, `--chunk` 예상 Neurons), 출력에 제목·제목 경로·링크·이름 0건, GitHub 측정 출력은 `tests/unit/devtools/test_measure.py` 그대로
- [X] T047 [US6] 확인 기록 확장 `src/qello_knowledge/sources/scope_review.py`: 종류 사양 기반 범위 키·`extra` 복원, Confluence 필드, 측정용 단일 자료원 대조 함수 (T043 통과)
- [X] T048 [US6] 켜짐 신호와 대응표 검사(research R-10 명령별 순서) `src/qello_knowledge/sync/run.py`(`current_spec`), `src/qello_knowledge/indexer/sync_cli.py`(`current_index_version`, `run_command`의 저장소 연 뒤 두 번째 검사·`--preview`·`index status/activate`), `src/qello_knowledge/config/check.py`(`_code_checks` 두 버전 중 하나 허용),
  `src/qello_knowledge/indexer/cli.py`(`sources check`) (T044 통과)
- [X] T049 [US6] 측정 일반화 `src/qello_knowledge/devtools/measure.py`, `src/qello_knowledge/devtools/db.py`, 비활성 자료원 하나 파싱 `src/qello_knowledge/sources/config.py` (T046 통과)
- [X] T050 [US6] 비활성 등록 `config/sources.toml`(contracts/source-config.md 예 그대로: `space_id=""`, `judge_mode="site_users"`, `doc_types={}`, `exclude_trees=[]`)과 기록 안내 `config/source_reviews/README.md`(Confluence 기록 형식, 에이전트가 대신 쓰지 않음)
- [X] T051 [P] [US6] 외부 시험 `tests/external/test_confluence_source.py`(`@pytest.mark.external`, 사람 실행): 측정 함수를 실제 전송으로 부르고 FR-027 항목이 모두 있는지 본다. 기본 실행에서 빠지는지 확인한다

**Checkpoint**: P2 완료. `uv run qk-index sources check`가 `confluence-scrum`을 비활성으로 보이고 인덱스 버전이 그대로다.

---

## Phase 9: Polish & Cross-Cutting

- [X] T052 [P] 공통 계약 시험 `tests/contract/test_confluence_adapter_contract.py`: `ContractExpectations`(항목 3건 이상, `no_modified_at`·`no_access`·`page_overlap`·`invalid_shape` 시나리오), 쓰기 요청 0건 (SC-009)
- [X] T053 [P] 로컬 DB 동기화 시험 `tests/localdb/sync/test_confluence_sync.py`: 재생 응답 + 가짜 임베딩 제공자로 첫 색인 → 변경 없는 재동기화 임베딩 0건 → 페이지 수정·제목 변경 → 보기 제한·미분류·제외 트리 보안 내림 →
  변환 규칙 버전 변경 시 Confluence 문서만 재처리(SC-013) → 한 번 색인 뒤 끄면 인덱스 버전 그대로(`INDEX_MISMATCH` 없음)이고 `--confirm-takedown` 실행에서 `SOURCE_DISABLED` 내림이 일어남(SC-014). 켜짐 인덱스 버전은 시험 안에서 대응표 대역으로 등록한다
- [X] T054 [P] 비노출 점검 시험 `tests/unit/adapters/confluence/test_confluence_logging.py`: 실패·예외·로그·요약 문자열에 제목·이름·계정 ID·메일·Cloud ID·사이트 주소·토큰이 0건(caplog와 예외 메시지 검사)
- [X] T055 GitHub 불변 회귀: 기존 시험 전체를 돌려 기대값 변경 0건을 확인하고, `git diff`에서 기존 시험 파일은 사례 추가만 있는지 본다
- [X] T056 [P] 문서 갱신: ADR-026에 구현 결과의 사실 정정(있으면), `specs/QK-ING-003-confluence-pages/quickstart.md`의 시험 파일 이름을 실제와 맞춘다
- [X] T057 기본 검증(quickstart 1절): `uv run python scripts/preflight.py`, `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run qk-dev db up`, `uv run qk-migrate`(두 번, 두 번째 `applied=0`),
  `QK_REQUIRE_LOCALDB=1 uv run pytest`. 결과를 TASK.md에 기록한다
- [ ] T058 `TASK.md` Decisions·검증 기록 갱신, `/pr-draft-summary`로 PR 초안(CLAUDE.md 의무 사용). 최종 보고에 `index_version`(꺼짐 `iv-4c0bc4fcc642`), `embedding_model`, `chunking_version`,
  `eval_set_version`(해당 없음, 사유), `metrics_with_sample_size`(해당 없음), `estimated_or_used_neurons`(0)를 넣는다

---

## 사람 단계 (구현 뒤, 이 작업의 완료 조건 밖)

- [ ] H01 ADR-026 리뷰·승인(사람). 승인 전에는 Proposed로 둔다.
- [ ] H02 Atlassian 토큰 범위·접두어 확인(사람): 범위 `read:space:confluence`·`read:page:confluence`·`read:folder:confluence` 포함 여부, 접두어가 `ATATT`와 다르면 비밀값 규칙 추가를 이 작업이나 후속에 넣는다.
  필요하면 plan 실측 스크립트를 돌린다(contracts/cli.md).
- [ ] H03 켜기 준비(사람, 별도 변경): `space_id`·`doc_types`·`exclude_trees`를 채우고 확인 기록을 쓴 뒤 `qk-dev source measure --name confluence-scrum --chunk --json`으로 첫 측정(FR-027, SC-010).
  예상 Neurons가 하루 색인 예산을 넘으면 켜기 전에 보고한다. 켜는 변경에서 `INDEX_KEYWORD_RULES` 항목과 QK-STO-002 절차를 함께 한다.

---

## Dependencies & Execution Order

- **단계 순서**: Phase 1 → Phase 2 → US1(Phase 3) → US2(Phase 4) → US3(Phase 5) → US4(Phase 6) → US5(Phase 7) → US6(Phase 8) → Polish(Phase 9) → 사람 단계.
- **스토리 사이 의존**:
  - US2는 US1의 목록·항목에, US3은 US2의 판정(통과 페이지만 본문)에 기댄다.
  - US4는 US1의 상위 사슬과 US3의 변환기에, US5는 US3의 변환기에 기댄다.
  - US6의 확인 기록·켜짐 검사(T043·T044·T047·T048)는 Phase 2 뒤 언제든 할 수 있다. 측정(T046·T049)은 US1~US3 뒤다.
- **같은 파일 작업 순서**:
  - `adapters/confluence.py`: T019 → T027 → T034 → T039
  - `adapters/atlassian_adf.py`: T033 → T040 → T042
  - `sync/plan.py`: T028 → T036
  - `indexer/sync_cli.py`: T017 → T020 → T029 → T048
  - `security/kinds.py`: T011 → T026, `security/policy.py`: T011 → T029
  - `sources/config.py`: T014 → T049
  - `tests/unit/adapters/confluence/test_confluence_listing.py`: T018 → T037
  - `tests/unit/adapters/test_atlassian_adf.py`·픽스처: T030·T031 → T038 → T041
  - `tests/unit/sync/test_plan_confluence.py`: T024 → T035
- **TDD**: 각 단계의 시험 작업을 먼저 쓰고 실패를 확인한 뒤 구현한다.

## Parallel Opportunities

- **Phase 2**: 시험 T003~T008을 병렬로 쓴다. 구현 T013·T015는 다른 작업과 병렬이고, T009 → T010 → T011 → T012, T014, T016, T017 순서다.
- **스토리 안**: 시험·픽스처 작업([P])은 서로 병렬이다. US2는 T021~T025, US3은 T030~T032·T035, US6은 T043~T046·T051.
- **US6 일부**: T043·T044·T047·T048은 US1~US5와 병렬로 할 수 있다(다른 파일).
- **Polish**: T052~T054·T056은 병렬이고 T055 → T057 → T058이 마지막이다.

## Implementation Strategy

1. **MVP = Phase 1~3(US1)**: 목록·위치·변경 판별값·정체성. 권한이 미확인이라 아무것도 색인되지 않는 안전한 중간 상태다.
2. **P1 마무리**: US2로 판정·사라진 페이지·조회 실패를, US3으로 본문 변환과 동기화 연결을 더한다.
3. **P2**: US4·US5로 분류·회의록·용어집을, US6으로 비활성 등록·확인 기록·켜짐 막기·측정을 갖춘다.
4. **마무리**: Polish(계약 시험, 로컬 DB 왕복, 비노출, GitHub 불변 회귀, 문서, 기본 검증, PR 초안). 사람 단계 H01~H03은 구현 뒤 사람이 한다.

---

## 구현 기록(2026-10-28)

- T001~T056을 구현했다. 계획과 달라진 점(사람 확인 대상):
  - T002: 확인 기록 픽스처는 파일 이름이 자료원 이름과 같아야 해서 저장소 픽스처 대신 각 시험의 임시 폴더에 만든다.
  - T014: GitHub `repo` 형식 규칙은 옮기지 않고 기존 공통 경로(`_common_scope`)에 그대로 두었다. 결과·결과 코드는 같다. Confluence만 종류 검증기를 쓴다.
  - T036: 청크 `locator` 합치기는 `sync/execute.py`가 아니라 계획 단계(`sync/plan.py` `merge_locator`)에서 한다. 실행 코드는 바뀌지 않았다.
  - T048: `AUTH_MISSING`은 설정 값을 읽는 `run`·`qk-dev source measure`에서 본다. `sources check`는 설정 값을 읽지 않아 대응표 검사만 한다.
  - 보안 출력: Confluence 판정 기록은 판정과 무관하게 제목·위치·링크를 비운다(research R-15).
- 기존 시험 변경: `tests/unit/indexer/test_cli.py` `access_rules` 기대값에 한 줄 추가(2026-10-28 사용자 허용), `tests/unit/fakes.py` `valid_environ()`에 합성 설정 값 넷 추가. 나머지는 사례 추가만이다.
- 외부 호출 0건, 0 Neurons. 실제 Confluence 측정은 사람 단계 H03이다.
- T057 기본 검증(2026-10-28, 같은 세션의 자기 검증): `uv run python scripts/preflight.py` 통과(891 파일), `git diff --check` 통과, ruff check·format --check 통과,
  `qk-dev db up` 뒤 `qk-migrate` 두 번 `applied=0 skipped=7`, `QK_REQUIRE_LOCALDB=1 uv run pytest` 3,261 passed·3 deselected(외부 시험). `qk-index sources check` 통과(`confluence-scrum` 비활성).
- 구현 독립 검토(2026-10-28, 작성에 관여하지 않은 별도 서브에이전트, 읽기 전용): 변경 요청(높음 2, 중간 2, 낮음 6). GitHub 불변은 검토자도 코드로 확인했다.
  작성 세션이 C1을 코드로 다시 확인하고 다음처럼 고쳤다. C1 끊긴 사슬을 `outside-home`으로 내리지 않고 권한 판정에 맡기며, 불완전한 목록·읽지 못한 폴더에서 끊긴 사슬은 조회 실패로 세고
  불완전한 목록에서는 본문을 남긴다. C2 레이아웃·결정 목록 변환. C3 인코딩을 푼 경로의 `people`·`~` 조각과 스킴 없는 자동 링크 차단. C4 실행·미리 보기 요약의 `kind_summary`·`incomplete_reason`.
  C5 단건 확인을 한 건씩 해 멈춰도 앞 결과 유지. C6 변환 예외를 그 페이지의 잘못된 응답으로. C7 코드 울타리·줄 머리 기호 이스케이프. C8 미리 읽기 중복 경고 제거, 회의 종류 자리 표시 제거,
  날짜 유효성, 하위 목록으로 시작하는 항목. C9 보기 제한 응답을 공식 모양으로, 시험 보강(끊긴 사슬, 새 변환 사례 5개, 제외 트리·사라진 페이지 로컬 DB 왕복). C10 사이트 주소 `/wiki` 정규화, 미래 확인일 거부.
  C10의 `origin/main` 위로 다시 쌓기는 git 작업이라 사람 승인 뒤에 한다.
