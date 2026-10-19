---
description: "QK-SEC-001 구현 작업 목록"
---

# Tasks: QK-SEC-001 색인 제외 경로·비밀값 차단·접근 범위 판정

**Input**: `specs/QK-SEC-001-security-filter/`의 plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (설계 승인 `7294c48`)

**Tests**: 포함한다. C-12(수용 기준은 검증으로 닫는다)와 quickstart.md가 성공 기준마다 자동 시험을 요구한다. 스토리마다 시험을 먼저 쓰고 실패를 확인한 뒤 구현한다.

**Organization**: 사용자 스토리별 단계로 나눈다. 우선순위는 US1(비밀값)·US2(접근 범위) P1 → US3(경로 제외)·US4(기록 검토) P2다. 판정 단계는 스토리마다 하나씩 `screen_items`에 끼워 넣는다.
US1 시험은 정책 주입(`SecurityPolicy.kinds`)으로 모든 자료를 팀 공용으로 판정하는 시험용 종류 정책을 써서 US2와 독립으로 돈다(research R-05).

**설계와 다르게 두는 두 곳** (경계·시험 수집 규칙 때문. 리뷰에서 확인):
- `FieldKind`, `AddressPolicy`, `OutputContext`, `safe_text()`를 plan.md 구조 표의 `security/redact.py`가 아니라 `src/qello_knowledge/domain/redact.py`에 둔다. data-model.md의
  `SecurityVerdict.to_dict(context)`는 `domain`에 있고, `domain`은 `qello_knowledge.security`를 가져올 수 없다(`tests/unit/test_boundaries.py`). 모두 표준 라이브러리(`re`, `ipaddress`)만 쓴다.
- plan.md의 `tests/unit/security/test_no_secret_leak.py`는 `tests/unit/config/test_no_secret_leak.py`와 이름이 겹친다. 시험 디렉터리에 `__init__.py`가 없어 같은 파일 이름을
  쓸 수 없으므로 `test_screen_no_secret_leak.py`로 쓴다.

**비밀값 시험 자료 규칙** (research R-12): 토큰 형식 값은 시험 코드에서 이어 붙여 만든다(예: `"gh" + "p_" + "A" * 36`). 응답 샘플 JSON에는 `{{SECRET:<종류>}}` 자리표시만 두고 시험 도우미가 실행 중에 바꾼다.
시험·샘플 파일을 커밋하기 전에 `python3 scripts/preflight.py --staged`가 통과해야 한다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 다루고 미완료 작업에 기대지 않아 병렬로 할 수 있다
- **[Story]**: 해당 사용자 스토리(US1~US4)

---

## Phase 1: Setup

**Purpose**: 새 패키지·디렉터리·설정 파일 자리. 의존성 추가 없음(plan.md Technical Context)

- [x] T001 `src/qello_knowledge/security/__init__.py`를 만들고 의존 규칙을 문서 문자열로 적는다: "`domain`·`ports`·`sources`(collect)만 가져오고 `adapters`를 가져오지 않는다. 판정 규칙·타입은 `domain`에 둔다"
- [x] T002 [P] 시험 디렉터리 만들기: `tests/unit/security/`, `tests/fixtures/security/`. 기존 `tests/unit/*`처럼 `__init__.py`를 두지 않는다. 새 시험 파일 이름이 `tests/` 전체에서 겹치지 않는지 `find tests -name "test_*.py" -exec basename {} \; | sort | uniq -d`로 확인한다
- [x] T003 [P] `config/security_exceptions.toml`: 예외 없이 형식 안내 주석만 둔다(contracts/security-exceptions.md의 예를 주석으로, "값은 적지 않는다", "변경은 PR 리뷰 대상"). 비밀값 없음

---

## Phase 2: Foundational

**Purpose**: 모든 스토리가 쓰는 판정 타입, 규칙 모듈과 커밋 검사 공유, 가림 함수, 정책 골격, 시험 도우미. 끝나야 스토리 작업을 시작한다

### Tests (Foundational)

- [x] T004 [P] `tests/unit/domain/test_security_types.py`: data-model.md 열거형 값 그대로(`AccessScope` = `TEAM`, `RESTRICTED`, `UNKNOWN` / `Verdict` = `PASSED`, `PATH_EXCLUDED`, `ACCESS_HELD`, `SECRET_BLOCKED`, `ERROR` / `Stage` = `PATH`, `ACCESS`, `ITEM_SECRET`, `FETCH`, `CONTENT_SECRET`, `PASSED` / `FieldKind` = `LINK`, `PATH`, `TEXT`). 상태 규칙: "`PASSED`면 `access_scope == TEAM`", "`ACCESS_HELD`면 `access_scope`는 `RESTRICTED` 또는 `UNKNOWN`", "`ERROR`면 `error_type`이 있다"를 어기면 생성 시 `ValueError`. 모든 타입 불변
- [x] T005 [P] `tests/unit/domain/test_secret_rules.py`(기존 규칙 부분): 지금 `scripts/preflight.py`의 규칙 12개 이름(`private-key`, `aws-access-key`, `github-token`, `slack-token`, `anthropic-key`, `openai-key`, `notion-token`, `figma-token`, `atlassian-token`, `db-url-with-password`, `assigned-secret`, `env-assigned-secret`)이 `RULES`에 모두 있고, 규칙마다 합성값 한 줄이 걸리며, `find_secrets()`는 `SecretHit(rule, line)`만 돌려주고 맞은 문자열을 담지 않는다. 모듈 소스가 `ast.parse(source, feature_version=(3, 12))`로 파싱된다
- [x] T006 [P] `tests/unit/test_preflight_shared_rules.py`: (a) `scripts/preflight.py`를 불러온 모듈의 `RULES`가 `domain/secret_rules.py`의 `RULES`와 이름·패턴이 같다, (b) `subprocess`로 `sys.executable -I scripts/preflight.py`가 저장소 루트에서 종료 코드 0, (c) `tmp_path`에 git 저장소를 만들고 규칙 파일의 index 버전과 작업 트리 버전을 다르게 둔 뒤 `--staged`가 index 규칙으로 검사한다(작업 트리에만 있는 규칙에 걸리는 staged 파일이 통과), (d) index에 규칙 파일이 없으면 `--staged`가 실패한다
- [x] T007 [P] `tests/unit/security/test_redact.py`(research R-07, quickstart.md 경로 그대로. 대상 모듈은 `domain/redact.py`): 필드 종류별 판정. 같은 합성 문자열 `<합성 이름>.md`를 `LINK`·`PATH`(파일 이름)·`TEXT`에 넣으면 `PATH` 파일 이름일 때만 남는다. `PATH`의 디렉터리 부분에 있으면 가린다. 숫자 버전 `1.2.3`은 `TEXT`에서도 남는다. `LINK`는 `public_link_hosts`의 `https` 주소만 남고 `http`, 다른 호스트, IP, `host:port`는 `[가림:address]`. 비밀값이 든 필드는 전체가 `[가림:<규칙 이름>]`. 확장자 비교는 대소문자 무시. 공개 호스트가 같고 `source_id_is_path`만 다른 두 `OutputContext`에서 `source_id` 출력이 다르다
- [x] T008 [P] `tests/unit/security/conftest.py`: 합성 비밀값 생성기 fixture(종류 이름 → 형식만 맞춘 값, 이어 붙여 만듦), 응답 샘플의 `{{SECRET:<종류>}}`를 바꿔 `ReplayTransport`를 만드는 도우미, 가짜 시계(`tests/unit/sources/conftest.py`의 `FakeClock`과 같은 동작을 이 파일에 둔다. conftest를 가져오지 않는다), 모든 자료를 `TEAM`으로 판정하는 시험용 종류 정책(`fake` 종류, `source_id_is_path=False`, `public_link_hosts=("fake.invalid",)`)

### Implementation (Foundational)

- [x] T009 `src/qello_knowledge/domain/security.py`: data-model.md의 `AccessScope`, `Verdict`, `Stage`, `FieldKind`, `SecurityVerdict`(필드 `source_name`, `source_id`, `location`, `url`, `title`, `verdict`, `stage`, `rule`, `lines`, `field`, `access_scope`, `access_raw`, `error_type`, `rules_version`), `ScreenedContent`, `FilterSummary`, `ScreenResult`. `SecurityVerdict.to_dict(context)`는 T012의 `safe_text`를 data-model.md `OutputContext`의 필드→`FieldKind` 대응("`url`→`LINK`, `location`→`PATH`, `source_id`→`source_id_is_path`면 `PATH` 아니면 `TEXT`, `title`·`access_raw` 키와 값·`error_type`→`TEXT`")대로 적용한다. 표준 라이브러리와 `qello_knowledge.domain`만. T004 통과
- [x] T010 `src/qello_knowledge/domain/secret_rules.py`: `scripts/preflight.py`의 `SECRET_NAME`, `PLACEHOLDER`, `RULES`를 동작 변경 없이 옮긴다. `SecretRule(name, pattern)`, `SecretHit(rule, line)`, `find_secrets(text) -> tuple[SecretHit, ...]`(줄마다 모든 규칙). 3.12 문법만, `re`만 가져온다. 이 단계에서는 규칙을 더하지 않는다(US1 T020). T005 통과
- [x] T011 `scripts/preflight.py`: 규칙 정의를 지우고 `_load_rules(staged)`로 `domain/secret_rules.py`를 불러온다. 일반 실행은 `importlib.util.spec_from_file_location`으로 작업 트리 파일을, `--staged`는 `git show :src/qello_knowledge/domain/secret_rules.py` 소스를 새 모듈 객체에 `exec`한다. index에 없으면 `rules-module-not-staged` 오류로 실패. 출력 형식·allowlist·`SKIP_PARTS`·`TEXT_SUFFIXES`는 바꾸지 않는다. 규칙 모듈 파일은 스스로를 검사하지 않도록 `candidate_paths()`의 자기 제외에 더한다. `python3 scripts/preflight.py`와 `python3 -I scripts/preflight.py` 통과, T006 통과
- [x] T012 `src/qello_knowledge/domain/redact.py`: `AddressPolicy(patterns, file_extensions, version)`, `ADDRESS_POLICY_VERSION`, `FILE_EXTENSIONS`(research R-07 목록, 소문자), `OutputContext(public_link_hosts, source_id_is_path, address_policy)`, `safe_text(value, field_kind, context) -> str`, `has_unsafe(value, field_kind, context) -> str | None`(가릴 것이 있으면 규칙 이름 또는 `address`). 순서: 비밀값이면 필드 전체 가림 → 주소 패턴(스킴 주소, IPv4·IPv6, `host:port`) → 점으로 이어진 이름을 필드 종류별로. 표준 라이브러리만. T007 통과
- [x] T013 `src/qello_knowledge/security/kinds.py`: `KindSecurityPolicy(kind, rule_name, judge, public_link_hosts, source_id_is_path)`와 모듈 등록부 `KINDS`(이 단계에서는 `github_repo_files`·`fake`의 `judge`가 모두 `UNKNOWN`을 돌려주는 자리만 둔다. 실제 규칙은 US2 T031). `public_link_hosts`·`source_id_is_path`는 data-model.md대로(`github_repo_files`=(`github.com`), 참 / `fake`=(`fake.invalid`), 거짓)
- [x] T014 `src/qello_knowledge/security/policy.py`: `SecurityPolicy(rules, exclusions, exceptions, kinds, address_policy)`와 `output_context(kind)`(등록되지 않은 종류면 공개 호스트 빈 튜플, `source_id_is_path=False`). `version`은 이 단계에서 임시 계산이어도 된다(US4 T045에서 research R-08대로 완성). `exclusions` 기본값은 빈 튜플(US3 T039에서 채움)

**Checkpoint**: 판정 타입, 공유 규칙, 가림 함수, 정책 골격 준비. `uv run pytest tests/unit/test_boundaries.py` 통과

---

## Phase 3: User Story 1 - 비밀값이 든 자료는 외부 API로 나가지 않는다 (P1) 🎯 MVP

**Goal**: Phase 1 토큰 형식까지 잡는 규칙, 자료원별 오탐 예외, 목록 단계 메타데이터·식별자 검사, 본문 단계 검사(문서 전체 차단), 조립 함수, 전송 직전 검사

**Independent Test**: 시험용 종류 정책(모두 `TEAM`)으로 합성 비밀값을 심은 가짜 자료원을 `screen_source()`에 흘려, `REQUIRED_KINDS`마다 `SECRET_BLOCKED`이고 `passed`에 없으며, placeholder 자료는 `PASSED`인지 본다

### Tests (US1)

- [x] T015 [P] [US1] `tests/unit/domain/test_secret_rules.py`(필수 종류 부분, SC-001): `REQUIRED_KINDS`의 종류마다 합성값이 걸린다(GitHub classic·세분화 `github_pat_`, Cloudflare `cfat_`, Discord 봇, ClickUp `pk_`, Anthropic, OpenAI, Atlassian, Figma, Notion, Slack, AWS, 개인 키 블록, 비밀번호 든 DB 주소). 이름 규칙은 접미사(`TOKEN`, `BOT_TOKEN`, `SECRET`, `PASSWORD`, `API_KEY`)마다 따옴표 할당(`NAME = "…"`, `name: '…'`)과 env 할당(`NAME=…`, `NAME="…"`) 모두 걸린다. 자리표시(`${GITHUB_TOKEN}`, `<github-token>`, `example`, `changeme`, `redacted`)는 걸리지 않는다. `REQUIRED_KINDS`마다 대응 규칙이 하나 이상 있다
- [x] T016 [P] [US1] `tests/unit/security/test_exceptions.py`: contracts/security-exceptions.md 오류 코드마다 한 사례(`INVALID_FILE`, `UNKNOWN_KEY`, `MISSING`, `INVALID`, `UNKNOWN_SOURCE`, `UNKNOWN_RULE`, `WILDCARD_PATH`, `INVALID_PATH`, `DUPLICATE`), 오류를 모두 모아 보고하고 값(`path`, `reason`)은 오류에 없음, 파일이 없으면 예외 0건, `path`는 정규화 비교·대소문자 구분, 비활성 자료원 이름 허용. 사례 파일은 `tests/fixtures/security/*.toml`
- [x] T017 [P] [US1] `tests/fixtures/responses/fake/security_secrets.json`: 자료 여러 개(`location`이 `docs/*.md`, `access` 공개, 버전 있음). 본문·제목·`location`·`source_id`에 `{{SECRET:<종류>}}` 자리표시를 둔 자료, placeholder만 든 자료, 정상 자료, 본문 조회가 404인 자료, 같은 경로를 두 자료원에서 쓰는 시나리오용 자료. `_meta`(`source_api`, `saved_at`, `redactions`) 포함. 저장된 파일에는 토큰 형식 값이 없다
- [x] T018 [P] [US1] `tests/unit/security/test_screen_source.py`(US1 부분): 본문에 비밀값 → `SECRET_BLOCKED`, `stage=CONTENT_SECRET`, `lines` 채움, `passed`에 없음(FR-011, US1-1). `source_id`·`location`·`title`·`url`에 비밀값 → `stage=ITEM_SECRET`이고 `list_all()` 반환 뒤 재생 전송에 그 자료의 `items/<id>` 요청 0건. 경로 아닌 `source_id`에 주소(맨 호스트 `<합성 이름>.md` 포함) → `rule=identifier-address`, 본문 요청 0건. 404 자료 → `ERROR`, `stage=FETCH`, `error_type=fetch:PERMANENT_FAILED:NOT_FOUND`. 목록에 나온 자료 수 = 판정 수. `ScreenResult.fetch.contents`는 빈 튜플. 페이지 조회 실패 시나리오에서 `fetch.listing_complete`가 거짓으로 남는다(R-11a)
- [x] T019 [P] [US1] `tests/unit/security/test_send_gate.py`(SC-002, SC-009): 비밀값 조각이 하나라도 있으면 `allowed=False`이고 가짜 전송자 호출 0회. `hits`에 조각 번호·규칙 이름·줄 번호만, 맞은 문자열 없음. 예외가 있는 `(자료원, 경로)` 조각은 그 규칙만 건너뜀. 같은 경로의 다른 자료원 조각, `origin=None` 조각(질의·프롬프트)에는 예외가 적용되지 않음. `test_screen_source.py`에도 같은 경로를 두 자료원에서 쓰고 한쪽에만 예외를 둔 사례를 더한다

### Implementation (US1)

- [x] T020 [US1] `src/qello_knowledge/domain/secret_rules.py`: research R-03대로 규칙을 넓히고 더한다. `assigned-secret`의 `SECRET_NAME`에 일반 `token`·`secret`, `env-assigned-secret`에 일반 `TOKEN`·`SECRET` 접미사와 따옴표 값, 새 규칙 `github-fine-grained-token`, `cloudflare-account-token`, `discord-bot-token`, `clickup-token`. `REQUIRED_KINDS` 정의. 총 16개. T015 통과
- [x] T021 [US1] 넓힌 규칙으로 `python3 scripts/preflight.py`를 돌려 이 저장소 파일에 새로 걸리는 줄을 확인한다. 실제 비밀값이면 멈추고 보고한다. 오탐이면 `scripts/preflight_allowlist.txt`에 `경로:규칙 이름 # 사유` 형식으로 넣는다(값은 적지 않는다). 결과(파일·규칙·사유)를 PR 본문용으로 기록한다
- [x] T022 [US1] `src/qello_knowledge/security/exceptions.py`: `SecretException(source, path, rule, reason)`, `PolicyIssue(entry, field, code)`, `load_exceptions(path, configs, rules) -> tuple[frozenset[SecretException], tuple[PolicyIssue, ...]]`. contracts/security-exceptions.md 검증 표 그대로. 오류 문구에 값 없음. T016 통과
- [x] T023 [US1] `src/qello_knowledge/security/policy.py`: `load_policy(exceptions_path, configs) -> tuple[SecurityPolicy | None, tuple[PolicyIssue, ...]]`. 오류가 하나라도 있으면 `None`
- [x] T024 [US1] `src/qello_knowledge/security/screen.py`: `screen_items(items, config, policy)`. 이 단계에서는 contracts/security-filter.md 목록 단계 표의 4·5번만 구현한다: 메타데이터 비밀값(`source_id`, `location`, `title`, `url`, 예외 적용) → `SECRET_BLOCKED`, `stage=ITEM_SECRET`, `rule`=규칙 이름, `field` / 식별자 주소(`has_unsafe(source_id, PATH 또는 TEXT, policy.output_context(kind))`가 `address`) → `rule=identifier-address`, `field=source_id`. 자료마다 `try`로 감싸 예외면 `ERROR`, `error_type`=예외 클래스 이름(R-09). 1~3번 단계는 US2·US3에서 앞에 끼운다
- [x] T025 [US1] `src/qello_knowledge/security/screen.py`: `screen_contents(contents, items_by_id, config, policy)`. 본문·제목·위치를 `find_secrets()`로 검사하고 `(config.name, 정규화한 location, rule)` 예외를 건너뛴다. 하나라도 남으면 자료 전체 `SECRET_BLOCKED`, `stage=CONTENT_SECRET`, `field`, `lines`. 남지 않으면 `PASSED`, `access_scope=TEAM`, `ScreenedContent` 생성
- [x] T026 [US1] `src/qello_knowledge/security/screen.py`: `screen_source(adapter, config, session, policy) -> ScreenResult`. contracts/security-filter.md 조립 함수 1~6단계 그대로: `list_all` → `screen_items` → `fetch_contents(…, replace(listing, items=passed_items))` → `SUCCEEDED`가 아닌 `ItemOutcome`은 `ERROR`, `stage=FETCH`, `error_type=f"fetch:{status}:{failure or 'none'}"` → `screen_contents` → `ScreenResult(passed, verdicts, summary, fetch=replace(fetch_result, contents=()))`. 판정 순서는 목록 순서대로. T018 통과
- [x] T027 [US1] `src/qello_knowledge/security/send_gate.py`: `OutgoingPiece(text, origin)`(`text`는 repr 제외), `SendHit(piece_index, rule, line)`, `SendCheck(allowed, hits)`, `check_outgoing(pieces, policy)`. 예외는 `origin`이 있는 조각에만. 로그는 조각 번호·규칙 이름·줄 번호만. T019 통과

**Checkpoint**: 비밀값이 든 자료가 청킹·임베딩·저장 단계로 넘어가지 않는다(US1 독립 동작)

---

## Phase 4: User Story 2 - 팀 공용으로 확인한 자료만 검색 대상이 된다 (P1)

**Goal**: 자료원 종류별 접근 판정 규칙과 목록 단계의 접근 범위 판정

**Independent Test**: 원본 권한 공개·비공개·내부·정보 없음·모순·키 중복·미등록 종류 자료를 흘려 공개만 `PASSED`·`TEAM`이고 나머지는 `ACCESS_HELD`, 본문 요청 0건인지 본다

### Tests (US2)

- [x] T028 [P] [US2] `tests/unit/security/test_access.py`: research R-05 표 그대로. `github_repo_files`: `raw == (("visibility", "public"),)`만 `TEAM`, `private`·`internal`·빈 값·모르는 값·`visibility` 키 중복·다른 키 섞임·`AccessInfo(UNKNOWN)`은 `UNKNOWN`. `fake`: `public`→`TEAM`, `restricted`→`RESTRICTED`, 그 밖→`UNKNOWN`. 판정 함수는 `UNKNOWN` 입력이면 항상 `UNKNOWN`(FR-016). 판정 규칙 이름 `github-visibility-v1`, `fake-visibility-v1`
- [x] T029 [P] [US2] `tests/fixtures/responses/fake/security_access.json`: 권한 원값이 `public`, `restricted`, `private`, 없음, 모르는 값인 자료. 비밀값 없음
- [x] T030 [P] [US2] `tests/unit/security/test_screen_source.py`(US2 부분, SC-004): 기본 등록부 정책으로 `security_access.json`을 흘려 `public`만 `PASSED`·`TEAM`, 나머지는 `ACCESS_HELD`(`access_scope`는 `RESTRICTED` 또는 `UNKNOWN`), `rule`=접근 규칙 이름, `access_raw`=원값, `list_all()` 반환 뒤 그 자료들의 본문 요청 0건. 접근 판정 규칙이 등록되지 않은 종류(`kinds`에서 뺀 정책)면 모두 `ACCESS_HELD`·`UNKNOWN`(US2-4)

### Implementation (US2)

- [x] T031 [US2] `src/qello_knowledge/security/kinds.py`: `judge_github_visibility`, `judge_fake_visibility`를 research R-05대로 구현하고 `KINDS` 등록부에 연결한다. T028 통과
- [x] T032 [US2] `src/qello_knowledge/security/screen.py`: `screen_items`의 메타데이터 검사 앞에 접근 판정(목록 단계 표 3번)을 끼운다. 등록되지 않은 종류는 `UNKNOWN`. `TEAM`이 아니면 `ACCESS_HELD`, `stage=ACCESS`, `access_scope`, `access_raw`, `rule`=접근 규칙 이름(미등록이면 `unregistered-kind`). `PASSED` 판정에도 `access_raw`와 접근 규칙 이름을 남긴다(FR-019). T030 통과
- [x] T033 [US2] US1 시험(`test_screen_source.py`, `test_send_gate.py`)이 시험용 종류 정책을 계속 쓰는지 확인하고, 기본 등록부로 돈 사례가 있으면 픽스처의 `access`를 공개로 맞춘다

**Checkpoint**: US1·US2가 함께 동작한다. 공개 자료만 본문까지 가고 비밀값 검사를 받는다

---

## Phase 5: User Story 3 - 색인하면 안 되는 경로는 자료원 설정과 상관없이 빠진다 (P2)

**Goal**: 기본 제외 규칙, 경로 정규화, 자료원 설정 제외의 재확인

**Independent Test**: 기본 제외 범주마다 경로 사례와 `scope.exclude` 사례를 포함 패턴 `**`로 흘려 모두 `PATH_EXCLUDED`이고 본문 요청 0건인지 본다

### Tests (US3)

- [x] T034 [P] [US3] `tests/unit/domain/test_exclusions.py`(research R-04): 범주마다 걸리는 경로(`.env`, `config/.env.production`, `deploy/id_rsa`, `certs/server.pem`, `secrets/db.txt`, `infra/terraform.tfstate`, `infra/terraform.tfstate.backup`, `infra/prod.tfvars`, `infra/.terraform/x`, `web/node_modules/a.md`, `app/build/x.md`, `.git/config`)와 걸리지 않는 경로(`.env.example`, `.env.sample`, `infra/prod.tfvars.example`, `docs/1.md`, `docs/building.md`). 예시 접미사여도 `terraform.tfstate.example`, `.terraform/config.sample`은 걸린다. 대소문자 무시(`.ENV`), 정규화(`./docs/../.ENV`), `..`로 시작하거나 절대 경로면 `path-invalid`. 범주 7개(`env-file`, `private-key-file`, `secret-dir`, `infra-state`, `build-output`, `vcs-internal`, `path-invalid`)
- [x] T035 [P] [US3] `tests/fixtures/responses/fake/security_paths.json`: T034의 걸리는 경로마다 자료 하나, 예시 파일 자료, 사람이 개인 정보 확인으로 `scope.exclude`에 넣을 경로의 자료(`docs/people/contacts.md`), 접근은 모두 공개
- [x] T036 [P] [US3] `tests/unit/security/test_screen_source.py`(US3 부분, SC-003): 포함 패턴 `**`, `scope.exclude = ["docs/people/**"]`인 설정으로 흘려 범주 경로와 사람 지정 경로가 `PATH_EXCLUDED`(`rule`=범주 이름 또는 `source-exclude`), `list_all()` 반환 뒤 본문 요청 0건, 예시 파일은 비밀값 검사로 넘어감. `scope.exclude`는 대소문자 무시로 재확인(`DOCS/People/x.md`)
- [x] T037 [P] [US3] `tests/unit/sources/test_config.py`에 사례 추가(FR-007): 기본 제외를 끄려는 키(`scope.disable_default_exclusions`, 최상위 `include_secrets`)가 있는 설정은 `UNKNOWN_KEY`로 실패한다. 이 시험은 ING-001 동작을 고정하는 것이고 ING-001 코드는 고치지 않는다

### Implementation (US3)

- [x] T038 [US3] `src/qello_knowledge/domain/exclusions.py`: `DefaultExclusion(category, pattern)`, 기본 목록(research R-04 표), `EXAMPLE_SUFFIXES`(`.example`, `.sample`, `.template`)를 "`env-file` 범주의 `.env` 패턴과 `infra-state` 범주의 `*.tfvars` 패턴에서만" 적용, `normalize_location(location)`, `excluded_by(location) -> str | None`. `PurePosixPath.full_match(pattern, case_sensitive=False)`. 표준 라이브러리만. T034 통과
- [x] T039 [US3] `src/qello_knowledge/security/policy.py`: `exclusions` 기본값을 T038 목록으로 채운다
- [x] T040 [US3] `src/qello_knowledge/security/screen.py`: `screen_items` 맨 앞에 기본 제외(표 1번)와 자료원 설정 제외 재확인(표 2번, 대소문자 무시)을 끼운다. 걸리면 `PATH_EXCLUDED`, `stage=PATH`. T036 통과

**Checkpoint**: 판정 단계 다섯 개(경로 → 접근 → 메타데이터 → 조회 → 본문)가 모두 동작한다

---

## Phase 6: User Story 4 - 운영 담당자가 막힌 자료와 이유를 검토한다 (P2)

**Goal**: 판정 기록 직렬화·로그·요약, 보안 규칙 버전, `qk-index security check`와 `run` 검사

**Independent Test**: US1~3 시험 자료를 한 번에 흘려 요약 건수가 판정과 맞고, 판정 기록·요약·`fetch.to_dict()`·로그 전체에 비밀값과 내부 주소가 없는지 본다

### Tests (US4)

- [x] T041 [P] [US4] `tests/unit/security/test_summary.py`(US4-1): 통과 5, 경로 제외 2, 비밀값 차단 1, 접근 미확인 1인 실행에서 `FilterSummary`의 결과별·규칙별·접근 범위별 건수가 그대로, 결과별 합 = 목록 자료 수
- [x] T042 [P] [US4] `tests/unit/security/test_policy_version.py`(FR-022, US4-2): 같은 정책이면 같은 버전(`sec-` + 12자리). 비밀값 규칙, 기본 제외, 예외 목록, `FILE_EXTENSIONS`, `ADDRESS_POLICY_VERSION`, 종류별 `rule_name`, `public_link_hosts`, `source_id_is_path` 중 하나만 바꾼 정책마다 버전이 다르다. 모든 판정 기록의 `rules_version`이 정책 버전과 같다
- [x] T043 [P] [US4] `tests/unit/security/test_screen_no_secret_leak.py`(SC-005, SC-010): 다섯 판정 결과(통과·경로 제외·접근 보류·비밀값 차단·판정 실패) 각각에 대해 `source_id`·`location`·`title`·원본 권한 원값에 합성 비밀값을 넣은 사례와, 내부 주소(스킴 주소, IP, `host:port`, `allowed_hosts`에 등록한 내부 호스트, 확장자와 겹치는 맨 호스트 `<합성 이름>.md`)를 링크·디렉터리 부분·제목·권한 원값·경로 아닌 `source_id`에 넣은 사례를 돌린다. 판정 기록 JSON, 요약, `ScreenResult.fetch.to_dict()`, `caplog` 전체(`qello_knowledge.security`와 ING-001 로그 포함)를 `find_secrets()`와 넣은 주소 문자열로 검사해 0건. `github.com` 공개 링크와 경로 필드의 파일 이름은 그대로 남는다
- [x] T044 [P] [US4] `tests/unit/indexer/test_cli.py`에 사례 추가(contracts/cli.md): `security check` 통과 시 종료 코드 0과 규칙 버전·규칙 수·범주 수·예외 수·접근 규칙 이름, 틀린 예외 파일이면 1이고 항목 번호·필드·코드만(`path`·`reason` 없음), `--json` 한 줄, 자료원 설정이 틀리면 `sources check`와 같은 보고로 1, `run`이 예외 파일 오류면 1이고 원본 호출 0건

### Implementation (US4)

- [x] T045 [US4] `src/qello_knowledge/security/policy.py`: research R-08대로 `version` 계산을 완성한다(비밀값 규칙 이름·패턴·플래그, 기본 제외 범주·패턴·예시 접미사, 정렬한 예외, 주소 정책 정규식 소스·정렬한 `FILE_EXTENSIONS`·`ADDRESS_POLICY_VERSION`, 종류별 `kind`·`rule_name`·`public_link_hosts`·`source_id_is_path`를 정해진 순서의 JSON → SHA-256 앞 12자리). T042 통과
- [x] T046 [US4] `src/qello_knowledge/domain/security.py`: `FilterSummary.from_verdicts(source_name, rules_version, verdicts)`와 `FilterSummary.to_dict()`. T041 통과
- [x] T047 [US4] `src/qello_knowledge/security/screen.py`: 로그 이름 `qello_knowledge.security`. 자료마다 `INFO` 한 줄(`verdict`, `stage`, `rule`, `SecurityVerdict.to_dict(policy.output_context(config.kind))`의 `source_id`)과 실행마다 요약 한 줄(`FilterSummary.to_dict()`). 로그에 원값을 직접 쓰지 않는다. T043 통과
- [x] T048 [US4] `src/qello_knowledge/security/report.py`: `security check` 표·JSON 출력(contracts/cli.md 형식). 예외 항목의 `path`·`reason`은 출력하지 않는다
- [x] T049 [US4] `src/qello_knowledge/indexer/cli.py`: `security check [--sources] [--exceptions] [--json]` 하위 명령을 더하고, `run`의 자료원 설정 검사 뒤에 예외 파일 검증을 넣는다. 원본 호출 없음. T044 통과

**Checkpoint**: 모든 스토리 완료

---

## Phase 7: SC-006 확인 — 두 번째 가짜 종류 규칙 (별도 커밋)

**Purpose**: 접근 판정 규칙을 더할 때 필터 공통 코드 변경이 0줄임을 보인다(FR-015, SC-006)

- [x] T050 [US2] `tests/unit/security/test_second_kind.py`: 시험 안에서 두 번째 가짜 종류(`fake2`, 원본 권한 키가 `sharing`이고 `team`이면 `TEAM`)의 `KindSecurityPolicy`를 만들어 `SecurityPolicy(kinds=…)`로 넘기고, `screen_items`가 그 규칙으로 판정하며 기록의 `rule`이 새 규칙 이름인지 본다
- [x] T051 [US2] T050만 한 커밋으로 만들고 `git show --stat HEAD`로 변경 파일이 `tests/` 아래뿐인지 확인해 PR 증빙으로 남긴다(SC-006)

---

## Phase 8: Polish & Cross-Cutting

- [x] T052 [P] `tests/unit/security/test_error_isolation.py`(SC-007, FR-004): 접근 판정이 예외를 내는 종류 정책과 `find_secrets`가 예외를 내는 상황(시험에서 바꿔 끼움)을 넣어, 예외 난 자료는 `ERROR`(`error_type`=예외 클래스 이름, 메시지 없음)이고 통과 0건, 나머지 자료는 100% 판정
- [x] T053 [P] `tests/unit/security/test_performance.py`(SC-008): 합성 Markdown 81개, 총 약 1.1 MB(비밀값 없음, 접근 공개)를 재생 전송으로 `screen_source()`에 흘려 처리 시간이 60초 미만. 측정값을 출력해 PR에 남긴다(C-13: 규모 조건 함께)
- [x] T054 [P] `uv run ruff format .`와 `uv run ruff check .`로 정리
- [x] T055 AGENTS.md 7절 기본 검증 전체 실행: `python3 scripts/preflight.py`, `python3 -I scripts/preflight.py`, `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run qk-dev db up`, `QK_REQUIRE_LOCALDB=1 uv run pytest`. 결과를 PR 본문용으로 기록
- [x] T056 quickstart.md의 성공 기준별 명령과 명령줄 확인을 차례로 실행하고 결과를 기록한다(SC-001~010)
- [ ] T057 PR 본문에 사람 확인 항목을 적는다(plan.md "사람 확인이 필요한 것"): `scripts/preflight.py` 수정과 T021 allowlist 추가, 공수 S→M, ING-001 로그의 `source_id`, QK-ING-002 인계(`visibility` 원값, GitHub `source_id`=저장소 안 경로, 포함 패턴 확장자와 `FILE_EXTENSIONS` 대조, 개인 정보 확인 절차), QK-STO-001 `AccessScope` 값 이름, FR-023 명세 문구 보완 제안, 이 tasks.md의 설계 조정 두 곳

---

## Phase 9: 구현 리뷰 반영 (2026-10-20 Codex 구현 리뷰 변경 요청 7건)

- [x] T058 [P] `tests/unit/security/test_screen_source.py`, `src/qello_knowledge/security/screen.py`: `source_id`에는 오탐 예외를 적용하지 않고 비밀값·주소가 있으면 본문 조회 전에 막는다(리뷰 1번, FR-020·023). 회귀 시험은 예외가 있어도 ING-001 로그·`fetch.to_dict()`에 토큰이 없는지 본다
- [x] T059 [P] `tests/unit/security/test_redact.py`, `src/qello_knowledge/domain/redact.py`: 포트 1~5자리(리뷰 2번), 퍼센트 인코딩을 최대 3번 풀어 다시 판정(리뷰 3번), IPv4를 붙인 IPv6 전체 가림(리뷰 4번)
- [x] T060 `src/qello_knowledge/security/screen.py`: 접근 판정 뒤의 모든 판정(`ITEM_SECRET`, `FETCH`, `CONTENT_SECRET`, 본문 단계 오류, `PASSED`)에 `access_scope=TEAM`과 `access_raw`를 남긴다(리뷰 5번, FR-019·021)
- [x] T061 `scripts/preflight.py`, `tests/unit/test_preflight_shared_rules.py`: 호환용 `RULES`를 모듈 `__getattr__`로 읽을 때만 불러와 `--staged`가 작업 트리 규칙을 실행하지 않게 한다. 작업 트리 규칙의 부작용·삭제·문법 오류 사례 시험(리뷰 6번, R-02)
- [x] T062 `src/qello_knowledge/security/screen.py`: 목록에 없는 식별자로 온 본문은 버리고, 본문을 받았다는데 판정이 없는 자료는 `ERROR`(`fetch:SUCCEEDED:content-mismatch`)로 남긴다(리뷰 7번, FR-004)
- [x] T063 [P] 시험 보완: 목록 멈춤 보존(`security_listing_stop.json`), 재시도 소진·인증 실패 건너뜀(`security_exhausted.json`, `security_auth_failed.json`). ING-001의 `exhausted.json`·`auth_failed.json`은 권한 정보가 없어 FR-016대로 모두 `ACCESS_HELD`가 되므로 권한 있는 시나리오를 따로 둔다
- [x] T064 AGENTS.md 7절 검증 전체 재실행

---

## Phase 10: 구현 재리뷰 반영 (2026-10-20 Codex 재리뷰 변경 요청 3건)

- [x] T065 [P] `src/qello_knowledge/domain/redact.py`: 순수 16진 IPv6 분기의 뒤 경계에서 마침표를 빼, `2001:db8::1.`·`docs/2001:db8::1.md`도 가린다(재리뷰 1번, T059 회귀). 가림 단위 시험과 누출 시험(식별자 사전 차단, ING-001 로그·요약)에 사례 추가
- [x] T066 `src/qello_knowledge/security/screen.py`: 성공한 요청 자료와 받은 본문을 순서대로 짝지어 식별자가 다르면 본문을 버리고 요청 자료를 `ERROR`(`fetch:SUCCEEDED:content-mismatch`)로 남긴다. 같은 식별자 본문이 두 번 오면 두 번째는 버린다(재리뷰 2번)
- [x] T067 `src/qello_knowledge/security/screen.py`: 목록 단계를 경로·접근·메타데이터 단계로 나눠 오류를 잡고, 접근 판정 뒤 단계의 오류에는 권한 증빙을 남긴다(재리뷰 3번, FR-019·021)
- [x] T068 AGENTS.md 7절 검증 전체 재실행

---

## Phase 11: 구현 재리뷰 2차 반영 (2026-10-20 Codex 재리뷰 변경 요청 1건)

- [x] T069 `src/qello_knowledge/domain/redact.py`: IP를 경계 정규식으로 찾지 않고, `[0-9A-Fa-f:.]` 구간 안의 후보를 `ipaddress`로 검증해 왼쪽부터 가장 긴 것을 가린다. 후보 앞뒤에 영숫자·`_`가 붙으면 주소로 보지 않는다(`std::map`). 점 앞뒤의 IPv6·IPv4(`file.2001:db8::1.md`, `file.10.0.0.5.md`, `file.::ffff:192.0.2.1.md`)를 모두 가린다. 주소 정책이 바뀌어 `ADDRESS_POLICY_VERSION`을 `address-v2`로 올렸다(규칙 버전도 바뀐다)
- [x] T070 [P] 시험: 점·확장자·괄호 옆 IP 사례, 코드·시각·버전 문자열 비가림 사례, 경로형 식별자 사전 차단과 기록 가림
- [x] T071 AGENTS.md 7절 검증 전체 재실행

---

## Phase 12: 구현 재리뷰 3차 반영 (2026-10-20 Codex 재리뷰 변경 요청 2건)

- [x] T072 `src/qello_knowledge/domain/redact.py`: 코드로 보고 주소에서 빼는 후보를 "숫자가 하나도 없고 영문자에 붙은 후보"(`std::map`, `Foo::bar()`)로 좁힌다. 숫자가 든 후보는 앞뒤에 무엇이 붙든 가린다(`10.0.0.5_backup`, `backup_2001:db8::1`, `a2001:db8::1`, 재리뷰 1번). `IP_RUN` 최소 길이를 2로 낮춰 `::`, `[::]:9`도 가린다(재리뷰 2번). `ADDRESS_POLICY_VERSION`을 `address-v3`로 올렸다
- [x] T073 [P] 시험: 영문자·`_`에 붙은 IP, 두 글자 IPv6 가림 단위 시험. 누출 시험에 `10.0.0.9_backup`, `::` 식별자 자료를 넣어 사전 차단과 ING-001 로그·요약 비노출 확인
- [x] T074 AGENTS.md 7절 검증 전체 재실행

---

## Phase 13: 구현 재리뷰 4차 반영 (2026-10-20 Codex 넓은 조합 재리뷰 변경 요청 2건)

- [x] T075 `src/qello_knowledge/domain/redact.py`: T072의 코드 예외(숫자 없고 영문자에 붙은 후보)를 없앤다. `face::beef`, `backupbeef::cafe` 같은 숫자 없는 IPv6도 실제 주소라 구분할 수 없으므로 유효한 IPv6 후보는 모두 가린다(재리뷰 1번, FR-023 완화 없음). 대가: 글 필드의 `std::map`도 가려지고, 경로에 `::`가 든 자료는 식별자 주소로 막힌다
- [x] T076 `src/qello_knowledge/domain/redact.py`: IPv6는 콜론이 두 개 이상인 16진 구간에서만 찾고, IPv4는 숫자·점 덩어리 전체(앞뒤 점 제외)가 유효할 때만 가린다. `1.2.3.456`, `2026.10.20.1`, `docs/2026.10.20.1.md`는 남는다(재리뷰 2번). 16진 문자열 10만 자 4.98초→0.02초. `ADDRESS_POLICY_VERSION`=`address-v4`
- [x] T077 [P] 시험: 숫자 없는 IPv6(글·경로·링크), 숫자 버전 파일 이름 비차단, 긴 비주소 문자열 처리 시간
- [x] T078 AGENTS.md 7절 검증 전체 재실행. 넓힌 `env-assigned-secret` 규칙이 새 상수 `IPV4_TOKEN = re.compile(...)`을 오탐으로 잡아 이름을 `IPV4_DIGITS`로 바꿨다(PR 사람 확인 항목: Python 상수 `*_TOKEN = 호출` 계열 오탐)

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** → 스토리 단계.
- **US1 (Phase 3)**: Foundational 뒤. 시험용 종류 정책으로 US2와 독립. `screen.py`를 처음 만든다.
- **US2 (Phase 4)**: Foundational 뒤 시험은 병렬로 쓸 수 있다. 구현 T032는 US1의 `screen.py`(T024~T026)에 단계를 끼우므로 US1 구현 뒤.
- **US3 (Phase 5)**: T034·T038은 독립. T040은 US1·US2의 `screen_items` 뒤.
- **US4 (Phase 6)**: T041·T042·T044는 Foundational 뒤 쓸 수 있다. T043·T047은 판정 단계 다섯 개가 다 있어야 의미가 있어 US3 뒤.
- **Phase 7**: US2 뒤. 반드시 다른 변경과 섞지 않은 단독 커밋.
- **Polish**: 모든 스토리 뒤.
- 같은 파일(`screen.py`, `policy.py`, `secret_rules.py`, `test_screen_source.py`)을 다루는 작업은 순서대로 한다.

## Parallel Examples

```text
Foundational 시험:   T004, T005, T006, T007, T008 동시에
US1 시험:           T015, T016, T017, T019 동시에 (T018은 T017 픽스처 뒤)
US2·US3 시험:       T028, T029, T034, T035, T037 동시에 (Foundational 뒤)
US4 시험:           T041, T042, T044 동시에
Polish:             T052, T053, T054 동시에
```

## Implementation Strategy

1. **MVP**: Setup → Foundational → US1. 비밀값이 든 자료가 다음 단계로 가지 않고, 커밋 검사와 색인 필터가 같은 규칙을 쓴다. 로드맵 1.G "비밀값을 심은 샘플 파일이 색인되지 않는다"의 판정 쪽이 여기서 닫힌다.
2. US2를 더해 팀 공용만 통과하게 한다(1.G "접근 범위를 확인할 수 없는 샘플 문서가 검색되지 않는다"의 판정 쪽).
3. US3으로 경로 제외를 더한다. Phase 1 포함 패턴(`**/*.md`)에서는 실제로 걸리는 일이 적지만 Phase 2 코드 수집 전에 있어야 한다.
4. US4로 기록·버전·명령줄을 마무리하고, Phase 7 단독 커밋으로 SC-006을 증빙한다.
5. 커밋은 `/harness-commit`으로 검토 목적별로 나눈다. `scripts/preflight.py` 수정(T011, T021)은 다른 변경과 섞지 않는다.
