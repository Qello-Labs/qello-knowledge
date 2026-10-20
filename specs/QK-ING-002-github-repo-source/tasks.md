---
description: "QK-ING-002 구현 작업 목록"
---

# Tasks: QK-ING-002 GitHub 저장소 파일 수집(트리 비교, 포함·제외 패턴)

**Input**: `specs/QK-ING-002-github-repo-source/`의 plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
(명세 승인 `0ab2931`·예시 정정 재승인 `87f98a3`, 설계 승인 `361a9b1`)

**Tests**: 포함한다. C-12와 quickstart.md가 성공 기준마다 자동 시험을 요구한다. 스토리마다 시험을 먼저 쓰고 실패를 확인한 뒤 구현한다.

**Organization**: 사용자 스토리별 단계로 나눈다. US1(목록)·US2(본문·권한) P1 → US3(한도·권한 거부 분류)·US4(자료원 등록·확인 기록·측정) P2다.
ING-001 공통 형식 변경과 실제 전송은 모든 스토리가 기대므로 Foundational에 둔다.

**설계와 다르게 두는 세 곳** (리뷰에서 확인):
- research R-15의 재생 응답 JSON 파일(`tests/fixtures/responses/github/*.json`) 대신, 시나리오를 시험 도우미 `tests/unit/adapters/github_scenarios.py`가 코드로 만든다.
  blob SHA를 합성 본문에서 실행 중에 계산해야 SHA 검증(R-05)을 통과하는 응답을 손으로 틀리지 않게 만들 수 있다. `ReplayTransport(exchanges)` 생성자를 그대로 쓰므로
  ING-001 `ReplayTransport`는 바뀌지 않는다. 응답 샘플 README의 `_meta` 규칙은 파일에서 읽을 때만 적용된다.
- plan.md 시험 파일 이름 `test_listing.py`, `test_content.py`, `test_access.py`, `test_classify.py`, `test_http.py`는 `tests/` 전체에서 겹치거나(`tests/unit/security/test_access.py`)
  뜻이 흐려서 `test_github_listing.py`, `test_github_content.py`, `test_github_access.py`, `test_github_classify.py`, `test_http_transport.py`로 쓴다.
  시험 디렉터리에 `__init__.py`가 없어 같은 파일 이름을 쓸 수 없다(QK-SEC-001 tasks와 같은 규칙).
- 개인 정보 확인 기록 시험 자료는 `tests/fixtures/source_reviews/`에 두되, 시험이 `tmp_path`에 복사·수정해 쓴다.

**시험 자료 규칙**: 본문은 합성 Markdown이고 대상 저장소 내용을 옮기지 않는다. 토큰 형식 값은 시험 코드에서 이어 붙여 만든다(QK-SEC-001 R-12, 예: `"gh" + "p_" + "A" * 36`).
커밋 전에 `python3 scripts/preflight.py --staged`가 통과해야 한다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 다루고 미완료 작업에 기대지 않아 병렬로 할 수 있다
- **[Story]**: 해당 사용자 스토리(US1~US4)

---

## Phase 1: Setup

**Purpose**: 디렉터리와 시험 도우미 자리. 의존성 추가 없음(plan.md Technical Context)

- [ ] T001 시험 디렉터리 만들기: `tests/unit/adapters/`, `tests/unit/adapters/github/`, `tests/external/`, `tests/fixtures/source_reviews/`. 기존 `tests/unit/*`처럼 `__init__.py`를 두지 않는다.
  새 시험 파일 이름이 `tests/` 전체에서 겹치지 않는지 `find tests -name "test_*.py" -exec basename {} \; | sort | uniq -d`로 확인한다
- [ ] T002 [P] `tests/unit/adapters/github_scenarios.py`(시험 도우미, 시험 파일 아님): 합성 저장소를 받아 `ReplayTransport(exchanges)`용 교환 목록을 만드는 함수.
  입력은 `repo`(`소유자/이름`), `ref`, `visibility`(문자열 또는 `None`이면 키 생략), `archived`, `commit_sha`, `tree_sha`, 파일 목록(`path`, `mode`, `type`, 본문 바이트 또는 하위 모듈 SHA), `truncated`.
  저장소·커밋·트리·blob 네 종류 요청 URL은 contracts/github-adapter.md 그대로 만들고, blob SHA는 `sha1(b"blob " + 길이 + b"\0" + 바이트)`로 계산한다.
  응답 하나를 상태 코드·헤더로 바꿔 넣는 함수(`override(url, status, headers, body)`)와, 같은 URL에 응답을 여러 개 쌓는 함수를 둔다.
  `tests/unit/sources/conftest.py`의 `FakeClock`을 가져다 쓰는 `session(adapter, transport, config, clock, jitter)` 도우미를 둔다
- [ ] T003 `tests/unit/adapters/github/conftest.py`(T002 뒤): 기본 설정 fixture(`SourceConfig("docs", "github_repo_files", True, auth="GITHUB_API_TOKEN", scope=SourceScope(("docs/**/*.md", "README.md"), ("docs/private/**",), (("repo", "octo/docs"), ("ref", "main"))), allowed_hosts=("api.github.com",))`),
  `clock`·`jitter` fixture(값은 `tests/unit/sources/conftest.py`와 같게), `basic` 합성 저장소(일반 Markdown 5개, `100755` 파일 1개, 제외 경로 1개, 범위 밖 `.java` 1개, 하위 모듈 1개, 심볼릭 링크 1개, 디렉터리 항목 2개)

---

## Phase 2: Foundational

**Purpose**: ING-001 공통 형식 변경(R-03, R-09), 공통 계약 시험 기대값 주입(R-10), 실제 전송(R-08). 끝나야 스토리 작업을 시작한다.
이 단계의 ING-001 변경은 2026-10-20 사용자 결정으로 허용됐다(TASK.md). 기존 동작은 바뀌지 않아야 한다

### Tests (Foundational)

- [ ] T004 [P] `tests/unit/sources/test_list_all.py`에 사례 추가(R-03): 가짜 어댑터 대역이 첫 페이지에 `ListPage(items, next_cursor="2", complete=True)`, 둘째 페이지에 `ListPage(items, None, complete=False)`를 주면
  `Listing.complete`가 거짓이고 두 페이지 항목(범위 적용·중복 제거 뒤)이 모두 담기며 셋째 호출이 없다. `complete=False`인 첫 페이지에 `next_cursor`가 있어도 다음 페이지를 부르지 않는다. 기존 사례는 그대로 통과
- [ ] T005 [P] `tests/unit/domain/test_content_hash.py`(R-09): `content_hash("")`·`content_hash("# 제목\n")`이 `"sha256:" + sha256(UTF-8).hexdigest()`와 같다. `DefaultSourceSession.finalize_content`가 같은 값을 채운다
- [ ] T006 [P] `tests/unit/adapters/test_http_transport.py`(R-08, contracts/github-adapter.md `HttpsTransport` 표): `urllib` opener를 대역으로 바꿔 확인한다.
  (a) 200 응답의 상태·소문자 헤더·본문, (b) 302 응답을 따라가지 않고 상태 302와 `location` 헤더를 그대로 돌려줌, (c) 404·500도 예외 없이 응답으로 돌려줌,
  (d) 본문이 `max_bytes`보다 길면 `max_bytes`까지 자르고 `truncated=True`, 같거나 짧으면 `False`, (e) `TimeoutError`·`socket.timeout` → `TransportError("timeout")`,
  `URLError`·`ConnectionError`·`ssl.SSLError` → `TransportError("connection")`, (f) 요청 호스트가 `auth_hosts`에 있을 때만 `Authorization: Bearer <토큰>`이 붙고 다른 호스트에는 없다,
  (g) `User-Agent`·`X-GitHub-Api-Version: 2022-11-28`이 항상 붙고, 요청 헤더가 같은 이름을 주면 요청 쪽이 이기되 `Authorization`은 덮어쓸 수 없다,
  (h) 예외 메시지·`repr(transport)`·`str(transport)`에 토큰 문자열이 없다(SC-010), (i) 전송이 `logging`에 아무것도 남기지 않는다(`caplog` 비어 있음)

### Implementation (Foundational)

- [ ] T007 `src/qello_knowledge/domain/source.py`: `ListPage`에 `complete: bool = True` 필드를 더하고, `content_hash(body: str) -> str`를 둔다(`"sha256:" + sha256(body.encode("utf-8")).hexdigest()`). 표준 라이브러리만(C-06)
- [ ] T008 `src/qello_knowledge/sources/collect.py`: `list_all`이 페이지의 항목을 처리한 뒤 `page.complete`가 거짓이면 `Listing(items, duplicates, False, excluded)`로 끝낸다. T004 통과
- [ ] T009 [P] `src/qello_knowledge/sources/session.py`, `src/qello_knowledge/adapters/fake.py`: 해시 계산을 `content_hash()` 호출로 바꾼다. 결과 값은 같다. T005와 기존 `tests/unit/sources/`, `tests/contract/` 통과
- [ ] T010 `tests/contract/source_adapter_contract.py`(R-10, data-model.md 6절): 고정값을 `expected` fixture의 `ContractExpectations(item_count, content_version, access_raw, content_format, write_probe_url, scenarios, content_hash_requests)`로 바꾼다.
  시나리오 시험은 `request.getfixturevalue`나 하위 클래스가 넘긴 `scenarios[이름]`으로 전송을 만든다. 값이 `None`인 시나리오는 대신 기본 시나리오에서 같은 성질을 확인한다:
  `no_modified_at`이 `None`이면 "모든 항목 `change_key_kind == VERSION`이고 `change_key`가 비어 있지 않다", `page_overlap`이 `None`이면 "원본 식별자 중복 0건, `duplicates_dropped == 0`".
  `pytest.skip`·`xfail`을 쓰지 않는다(AGENTS.md 9절). 시험이 확인하는 성질은 줄이지 않는다
- [ ] T011 [P] `tests/contract/test_fake_adapter_contract.py`, `tests/contract/test_second_fake_contract.py`: 지금 값(항목 5개, `"v1"`, `(("visibility", "public"),)`, `MARKDOWN`, `https://fake.invalid/items`·`https://second.invalid/records`,
  시나리오 네 개 모두 재생 파일, 내용 해시 요청 12회)을 `expected`로 넘긴다. 두 클래스의 시험 수와 통과 결과가 변경 전과 같은지 `uv run pytest tests/contract -q`로 확인한다
- [ ] T012 [P] `src/qello_knowledge/adapters/http.py`: `HttpsTransport(auth_hosts, token, *, user_agent="qello-knowledge-indexer", timeout_seconds=30, opener=None)`.
  기본 opener는 리다이렉트를 따르지 않는 처리기(`HTTPRedirectHandler`의 `redirect_request`가 `None`을 돌려줌)와 `ssl.create_default_context()`를 쓴다. `HTTPError`도 응답으로 바꾼다.
  `token`은 QK-FND-001 `SecretValue`이고 `send` 안에서만 `reveal()`한다. 로그를 남기지 않는다. `qello_knowledge.config.loader`의 `SecretValue`만 타입으로 쓰고 다른 설정 모듈을 가져오지 않는다. T006 통과

**Checkpoint**: ING-001 기존 시험 전체 통과, 공통 계약 시험이 기대값을 받는다, 실제 전송이 준비됐다

---

## Phase 3: User Story 1 — 대상 저장소의 문서 목록을 한 시점 기준으로 빠짐없이 받는다 (Priority: P1) 🎯 MVP

**Goal**: 한 커밋을 확정하고, 그 커밋의 일반 파일 목록을 blob SHA·크기와 함께 경로순으로 돌려준다. 잘리거나 실패하면 불완전으로 표시한다(FR-001~006, FR-014, FR-024)

**Independent Test**: `github_scenarios` 재생 응답으로 `list_all`을 돌려 기대 목록과 같은지, 두 번 같은지, 잘림·실패에서 불완전인지 본다(SC-001~003)

### Tests (US1)

- [ ] T013 [P] [US1] `tests/unit/adapters/github/test_github_listing.py`(SC-001): `basic`으로 `list_all`을 돌리면 경로 목록이 기대 목록(범위 안 Markdown 5개와 `100755` 파일 중 범위 안 것)과 정확히 같고,
  하위 모듈·심볼릭 링크·디렉터리·제외 경로·범위 밖 파일이 0건, 경로순 정렬, 요청은 저장소·커밋·트리 세 건(contracts/github-adapter.md 표 순서·URL·`Accept: application/vnd.github+json`)뿐이다
- [ ] T014 [US1] 같은 파일(SC-001, R-04 필드 표): 항목마다 `source_kind == "github_repo_files"`, `source_id == location == path`, `change_key == blob SHA`, `change_key_kind == VERSION`,
  `version == commit_sha`, `modified_at is None`, `item_type == "repo_file"`, `title is None`, `size_bytes ==` 트리 `size`, `url == "https://github.com/octo/docs/blob/<commit>/<경로>"`.
  공백·한글·`#`·`?`가 든 경로는 `url`에서 퍼센트 인코딩되고 `/`는 남으며 `source_id`는 원래 경로 그대로다. 대소문자만 다른 두 경로는 서로 다른 항목이다
- [ ] T015 [US1] 같은 파일(SC-002, FR-002·006): 같은 시나리오로 두 번 돌린 `Listing`이 항목·순서·값까지 같다. `ref`에 `/`가 든 경우(`release/1`) 커밋 요청 URL에서 `%2F`로 인코딩된다.
  모든 항목의 `version`이 커밋 응답의 `sha`다
- [ ] T016 [US1] 같은 파일(SC-003, FR-005·014, research R-07): (a) 트리 `truncated: true`이면 받은 항목을 담고 `Listing.complete`가 거짓, (b) 커밋 조회 422·404와 저장소 조회 404는
  `adapter.list_page`를 직접 부르면 `SourceFailure`의 `failure == NOT_FOUND`(원래 상태 코드 보존), `list_all`은 불완전·항목 0개, 재시도 0회, (c) 커밋 조회 409는 `INVALID_RESPONSE`이고 불완전,
  (d) 커밋이 있고 트리가 비거나 범위 안 파일이 0개면 `complete`가 참·항목 0개, (e) 응답 형식 오류(트리 항목 `sha` 누락, `truncated`가 불린 아님, `path`에 `..` 조각, 커밋 SHA가 40자 16진수 아님)는 `InvalidResponse`로 불완전
- [ ] T017 [US1] 같은 파일(research R-14 `last_snapshot`): 목록 조회 성공 뒤 `adapter.last_snapshot == ListSnapshot(commit_sha, visibility, truncated)`, 트리 조회 실패 시 `truncated is None`,
  저장소·커밋 조회 실패 시 `None`, 새 목록 조회를 시작하면 이전 값이 지워진다

### Implementation (US1)

- [ ] T018 [US1] `src/qello_knowledge/adapters/github.py`: `GitHubRepoFilesAdapter.kind = "github_repo_files"`, `scope.extra`에서 `repo`·`ref` 읽기, `list_page`의 세 요청과 data-model.md 2절 응답 검증
  (`RepoInfo`: "`visibility`가 문자열이 아니면 `None`(미확인). `archived`가 불린이 아니면 오류" / `CommitRef`: "둘 다 40자 소문자 16진수" / `TreeEntry`: "`path`는 빈 문자열·앞 `/`·`..` 조각 금지. `blob`이면 `sha`는 40자 16진수, `size`는 0 이상 정수" / `TreeListing`: "`truncated`가 불린이 아니면 오류"),
  일반 파일 선별(`type == "blob"`이고 `mode`가 `100644` 또는 `100755`), R-04 필드 매핑, 경로순 정렬, `ListPage(items, None, complete=not truncated)`.
  ING-001 세션은 정상 응답에서도 `classify`·`rate_limit_hint`를 부르므로(`sources/session.py`) 이 단계에서 `classify`는 `default_classify`, `rate_limit_hint`는 `default_rate_limit_hint`에 위임한다.
  GitHub 규칙은 US3 T028에서 이 두 메서드를 넓힌다. T013~T015 통과
- [ ] T019 [US1] `src/qello_knowledge/adapters/github.py`: 커밋 확정 요청의 `SourceFailure`(HTTP 404·422)를 `SourceFailure(NOT_FOUND, 원래 상태 코드)`로 바꿔 올리고, 그 밖 실패는 그대로 올린다.
  `ListSnapshot`과 `last_snapshot`(목록 조회 시작 때 `None`, 커밋 확정 뒤 갱신). T016·T017 통과

**Checkpoint**: US1만으로 한 커밋 기준의 완전·불완전 목록이 나온다

---

## Phase 4: User Story 2 — 본문은 목록과 같은 내용이고, 공개 범위 정보와 함께 보안 필터로 간다 (Priority: P1)

**Goal**: blob 원문을 받아 SHA·UTF-8을 검증하고, `visibility` 원값을 권한 정보로 담아 SEC-001이 공개 저장소만 통과시키게 한다(FR-007~011, FR-017)

**Independent Test**: 네 가지 공개 범위와 본문 불일치·비 UTF-8 사례를 SEC-001 `screen_source`와 함께 돌린다(SC-004, SC-005, SC-007)

### Tests (US2)

- [ ] T020 [P] [US2] `tests/unit/adapters/github/test_github_content.py`(SC-004, FR-007·008): 본문 요청 URL이 `/git/blobs/<change_key>`이고 `Accept: application/vnd.github.raw+json`이며 `ref`를 쓰지 않는다.
  `SourceContent`의 `body`·`version == item.version`·`location == path`·`title is None`, 내용 형식(`md`·`mdx`·`markdown` → `MARKDOWN`, `json` → `JSON`, `py`·`java`·`kt` → `CODE`, `txt` → `TEXT`).
  본문 바이트의 blob SHA가 `change_key`와 다르면 그 자료만 `PERMANENT_FAILED`·`INVALID_RESPONSE`이고 나머지는 100% 성공한다. UTF-8이 아닌 바이트(재생 JSON으로 만들 수 없으므로 시험 안 전송 대역)도 같다.
  목록 크기가 `max_content_bytes`를 넘는 자료는 본문 요청 없이 `PERMANENT_FAILED`·`SIZE_EXCEEDED`(ING-001 R-08)
- [ ] T021 [P] [US2] `tests/unit/adapters/github/test_github_access.py`(SC-005, FR-010·011): `visibility`가 `public`·`private`·`internal`이면 항목 `access == AccessInfo(PROVIDED, (("visibility", 값),))`,
  키가 없거나 문자열이 아니면 `AccessInfo(UNKNOWN)`. 네 사례를 SEC-001 `screen_source`(`SecurityPolicy()` 기본값)로 돌리면 `public`만 `PASSED`, 나머지는 `ACCESS_HELD`이고 blob 요청 0건.
  `archived: true`면 `origin_state == ARCHIVED`, 아니면 `ACTIVE`. `public` 사례의 판정 기록 `to_dict(context)`에서 `url`·`source_id`가 가려지지 않는다(공개 원본 링크 호스트 `github.com`, 경로형 식별자)
- [ ] T022 [P] [US2] `tests/contract/test_github_adapter_contract.py`(SC-007, FR-017): `SourceAdapterContract`를 상속하고 `expected`에 `item_count`(기본 시나리오 범위 안 파일 수), `content_version`(커밋 SHA),
  `access_raw=(("visibility", "public"),)`, `content_format=MARKDOWN`, `write_probe_url="https://api.github.com/repos/octo/docs"`, `scenarios`(`no_modified_at`·`page_overlap`은 `None`,
  `no_access`는 `visibility` 없는 저장소, `invalid_shape`는 둘째 blob 응답이 SHA 불일치인 저장소), `content_hash_requests=None`을 넘긴다. 모든 요청이 `GET`·`api.github.com`

### Implementation (US2)

- [ ] T023 [US2] `src/qello_knowledge/adapters/github.py`: `fetch_content` — blob 원문 요청, git blob SHA 검증, UTF-8 엄격 디코드(`errors="strict"`), 확장자별 내용 형식, `SourceContent(item.source_id, body, 형식, item.version, item.location, None)`. T020 통과
- [ ] T024 [US2] `src/qello_knowledge/adapters/github.py`: 저장소 응답의 `visibility` 원값으로 `AccessInfo`를 만들고(값을 바꾸거나 `private`에서 추론하지 않는다), `archived`로 `origin_state`를 채운다. T021·T022 통과

**Checkpoint**: US1+US2로 공개 저장소 문서가 SEC-001을 지나 본문까지 나온다

---

## Phase 5: User Story 3 — GitHub의 한도 응답과 권한 거부를 구분한다 (Priority: P2)

**Goal**: 403·429 한도 응답은 일시적 실패로, 나머지 403은 영구 실패로 분류하고, 한도 힌트를 ING-001 관문 규칙에 맞게 넘긴다(FR-012, FR-013)

**Independent Test**: 1차·2차 한도, 헤더 없는 거부, 2차 한도 뒤 다음 파일 사례를 가짜 시계로 돌린다(SC-006)

### Tests (US3)

- [ ] T025 [P] [US3] `tests/unit/adapters/github/test_github_classify.py`(SC-006, contracts/github-adapter.md `classify` 표): 403·429에 `x-ratelimit-remaining: 0` → `TRANSIENT/RATE_LIMITED`,
  403·429에 `retry-after` → `TRANSIENT/RATE_LIMITED`, 그 밖 403 → `PERMANENT/ACCESS_DENIED`, 401 → 인증 실패, 200·404·500은 `default_classify`와 같다
- [ ] T026 [US3] 같은 파일(`rate_limit_hint` 표): `retry-after: 60`과 `x-ratelimit-remaining: 100` → `remaining=0`, `retry_after_seconds=60`; `retry-after`와 `x-ratelimit-remaining: 0`·`x-ratelimit-reset` →
  `remaining=0`, 늦은 쪽 시각; `retry-after` 없이 남은 수 0과 `reset` → `retry_at`이 그 유닉스 초(UTC); 남은 수 양수만 → `remaining`만, `retry_at is None`; 헤더 없음 → `None`;
  숫자가 아닌 헤더 값은 없는 것으로 본다
- [ ] T027 [P] [US3] `tests/unit/adapters/github/test_github_rate_limit.py`(SC-006, FR-013): 세션으로 끝까지 돌린다. (a) 1차 한도(403, 남은 수 0, `reset`이 지금+30초) 뒤 성공 → 그 자료 성공, 가짜 시계 대기 ≥ 30초,
  (b) `reset`이 최대 대기 시간보다 멀면 `StopReason.WAIT_TOO_LONG`으로 멈추고 남은 자료는 `SKIPPED`, (c) 헤더 없는 403 → 그 자료만 `PERMANENT_FAILED`·`ACCESS_DENIED`, 재시도 0회,
  (d) `secondary_then_next`: 첫 파일이 `retry-after: 60`·남은 수 100인 403을 재시도 상한까지 받아 `TRANSIENT_EXHAUSTED`가 된 뒤, 둘째 파일 요청은 마지막 `retry-after` 시각 전에 나가지 않는다(가짜 시계 기록),
  (e) 401 → `AUTH_FAILED`로 멈추고 남은 요청 0건

### Implementation (US3)

- [ ] T028 [US3] `src/qello_knowledge/adapters/github.py`: US1의 위임 구현을 넓혀 `classify`, `rate_limit_hint`를 contracts/github-adapter.md 표대로 만든다( `retry-after` 읽기는 `default_rate_limit_hint`를 쓴다). T025~T027 통과

**Checkpoint**: 모든 어댑터 동작 완료. US1~US3 시험과 공통 계약 시험 통과

---

## Phase 6: User Story 4 — 첫 자료원을 등록하고, 범위는 사람이 확인한 기록과 함께 넓힌다 (Priority: P2)

**Goal**: 포함 패턴 확장자·개인 정보 확인 기록 검사를 수집 전에 강제하고, 첫 자료원을 비활성으로 등록하고, 사람이 쓸 측정 명령을 만든다(FR-018~023)

**Independent Test**: 확장자·기록 오류 사례가 원본 호출 0건으로 실패하는지, 측정 명령이 재생 응답으로 FR-022 항목을 모두 채우는지 본다(SC-008, SC-009의 자동 부분, SC-010)

### Tests (US4)

- [ ] T029 [P] [US4] `tests/fixtures/source_reviews/`: 올바른 기록 `valid.toml`(contracts/source-reviews.md 형식, `result = "개인 정보 없음"`), `excluded.toml`(`result = "개인 정보 경로 제외함"`과 `moved_to_exclude` 1개).
  값은 합성(`source = "docs"`, `reviewer_role = "시험용 역할"`). 이름·연락처 없음
- [ ] T030 [P] [US4] `tests/unit/sources/test_scope_review.py`(SC-008, R-11, T029 뒤): 확장자 검사 — `**/*.org`, `docs/*.m?`, `docs/*.[mM]d` → `UNKNOWN_EXTENSION scope.include[<번호>]`;
  `**/*.adoc`, `**/*.MD`, `docs/**`, `README*`, `README.md` → 통과. 비활성 자료원에도 적용된다
- [ ] T031 [US4] 같은 파일(SC-008, R-12, contracts/source-reviews.md 검사 표): 활성 자료원에 대해 기록 없음 → `REVIEW_MISSING review`; TOML 문법 오류, 필수 항목 누락(항목마다), 모르는 키,
  `source`와 파일 이름 다름, `result`가 두 값 밖, `result = "개인 정보 경로 제외함"`인데 `moved_to_exclude` 없음 → `REVIEW_INVALID`; `repo`·`ref`·`include`·`exclude` 하나라도 다름,
  패턴 순서만 다름, `moved_to_exclude.pattern`이 설정 `exclude`에 없음 → `REVIEW_SCOPE_MISMATCH`; 비활성 자료원은 기록이 없어도 통과; 가짜 종류 자료원의 기록 `scope`에 `repo`·`ref`가 없어도 통과.
  모든 오류 문자열에 기록 내용 값·설정 값이 없다(SC-010)
- [ ] T032 [P] [US4] `tests/unit/indexer/test_cli.py`에 사례 추가(contracts/cli.md): `sources check --reviews <dir>`가 확장자·기록 오류를 ING-001 보고 형식(표·`--json`)으로 보이고 종료 코드 1,
  `run --reviews <dir>`도 같은 오류에서 1이고 원본 호출이 없다(전송이 만들어지지 않는다), 저장소의 `config/sources.toml`과 기본 `--reviews`로 `sources check`와 `run`이 통과한다(첫 자료원 비활성).
  `security check`는 확인 기록을 검사하지 않는다(contracts/cli.md)
- [ ] T033 [US4] `tests/unit/indexer/test_cli.py` 기존 성공 사례 전환(T032와 같은 파일, T032 뒤): `tests/fixtures/sources/valid.toml`의 활성 자료원 `docs`(가짜 종류)로 `sources check`·`run`이 0을 기대하던 사례는
  새 계약에서 `REVIEW_MISSING`이 되므로, 시험 도우미 `tests/unit/review_records.py`(시험 파일 아님)가 `SourceConfig`와 같은 범위의 확인 기록을 `tmp_path`에 써서 `--reviews`로 넘긴다.
  같은 호출을 기록 없이 부르는 사례는 실패(1, `REVIEW_MISSING`) 사례로 따로 남긴다. 저장소의 `config/source_reviews/`에는 기록 파일을 만들지 않는다
- [ ] T034 [P] [US4] `tests/unit/devtools/test_measure.py`(SC-009 자동 부분, research R-14, data-model.md 9절): 사전 검증 `prepare_source`가 확인 기록 없음·범위 불일치·확장자 오류·보안 예외 파일 오류·자료원 설정 오류에서
  `PreparedSource`가 아닌 오류 목록을 돌려주고, 이때 전송 생성 함수(대역)가 한 번도 불리지 않으며 요청이 0건이다(FR-020, 호출 전 검사). `measure_source`는 `PreparedSource`만 받는다.
  이어서 통과한 `PreparedSource`와 재생 전송으로 `measure_source`를 세 사례에서 돌린다 — 정상, 본문 비밀값 차단(합성 토큰을 본문에 심음),
  범위 안 항목 0개. 세 사례 모두 FR-022 항목(`commit`, `visibility`, `tree_truncated`, `include`·`exclude` 실제 목록, `measured_at`, `environment`, `requests`, `elapsed_seconds`, `listing_complete`, `stop`,
  `files`, `bodies_fetched`, `total_bytes`, `max_file_bytes`, `by_verdict`, `by_rule`, `blocked`, `limits`)이 있다. `files`는 범위 안 고유 목록 항목 수와 같다(통과 자료를 두 번 세지 않는다).
  본문 차단 사례도 `bodies_fetched`·`total_bytes`에 들어간다. 항목 0개 사례도 `commit`이 나온다. 출력(표·JSON)에 본문·토큰 문자열이 없다. `CountingTransport`는 blob 2xx 응답 길이만 세고 응답을 바꾸지 않는다
- [ ] T035 [US4] `tests/unit/devtools/test_measure.py`에 명령 사례 추가(contracts/cli.md `qk-dev source measure`): 설정 점검 실패·확인 기록 오류·없는 이름·비활성 자료원·지원하지 않는 종류면 전송을 만들지 않고 1.
  목록 불완전이나 판정 실패가 있으면 출력하고 1. 실제 전송 생성 함수를 대역으로 바꿔 재생 전송으로 정상 사례 0
- [ ] T036 [P] [US4] `tests/external/test_github_repo_source.py`(SC-009, `@pytest.mark.external`): `require_env("GITHUB_API_TOKEN")`로 토큰을 받고, `config/sources.toml`의 첫 활성 `github_repo_files` 자료원을
  CLI와 같은 사전 검증 `prepare_source`(기본 `config/source_reviews`, `config/security_exceptions.toml`)로 통과시킨 뒤에만 실제 전송을 만든다. 오류가 있으면 전송을 만들지 않고 오류 코드로 실패한다.
  통과하면 `measure_source`를 실제 전송으로 돌려 요청 수 ≤ 실행당 한도, 목록 완전, `ERROR` 판정 0건을 확인한다. 활성 자료원이 없으면 "활성화 절차(research R-13) 뒤 실행" 메시지로 실패한다(건너뛰지 않는다).
  기본 실행(`-m 'not external'`)에서 빠지는지 `uv run pytest --collect-only -q tests/external`로 확인한다

### Implementation (US4)

- [ ] T037 [US4] `src/qello_knowledge/sources/scope_review.py`: `extension_issues(config) -> tuple[ConfigIssue, ...]`(research R-11 규칙, `qello_knowledge.domain.redact.FILE_EXTENSIONS` 사용),
  `ScopeReview` 값 객체(data-model.md 8절: "`source`는 파일 이름(확장자 제외)과 같다", "`reviewed_on`은 TOML 날짜", "`reviewer_role`·`method`는 비어 있지 않다",
  "`result`는 `개인 정보 없음` 또는 `개인 정보 경로 제외함`", "`scope`는 현재 자료원 설정과 같다(패턴 순서 포함)", "`moved_to_exclude`는 `result`가 `개인 정보 경로 제외함`이면 1개 이상, `pattern`은 현재 `exclude`에 있다"),
  `load_review(path)`, `check_scope(configs, reviews_dir)`(contracts/source-reviews.md 검사 표 순서, 경로가 없으면 빈 디렉터리와 같음). ING-001 `sources/config.py`·SEC-001 `security/`는 고치지 않는다. T030·T031 통과
- [ ] T038 [US4] `src/qello_knowledge/indexer/cli.py`: `sources check`와 `run`에 `--reviews`(기본 `config/source_reviews`)를 더하고, `load_sources` 오류에 `check_scope` 오류를 합쳐 기존 보고 함수로 보인다.
  오류가 있으면 원본 호출 없이 1. 그 밖 동작은 바꾸지 않는다. T032·T033 통과
- [ ] T039 [P] [US4] `config/sources.toml`: research R-13의 `dnd-backend-docs` 항목을 `enabled = false`로 더한다. 기존 형식 안내 주석은 남기고 첫 줄 주석("첫 실제 자료원은 QK-ING-002가 추가한다")을
  "활성화는 결정 기록·개인 정보 확인 기록과 함께 사람이 한다(QK-ING-002 research R-13)"로 바꾼다. `uv run qk-index sources check`가 통과한다
- [ ] T040 [P] [US4] `config/source_reviews/README.md`: contracts/source-reviews.md의 파일 형식·검사·"에이전트는 이 파일을 대신 만들지 않는다"·이름과 연락처 금지를 요약하고, 활성화 절차(research R-13 1~6단계)를 적는다.
  `.toml` 기록 파일은 만들지 않는다
- [ ] T041 [US4] `src/qello_knowledge/devtools/measure.py`: `prepare_source(name, sources_path, reviews_dir, exceptions_path) -> PreparedSource | tuple[이슈, ...]`(색인 진입점 설정 점검을 뺀
  `qk-index run`의 설정 검사 순서: `load_sources` → `check_scope` → `load_policy` → 이름·활성·종류 확인. 원본 호출 없음. `PreparedSource(config, policy)`는 이 함수로만 만든다),
  `CountingTransport(inner)`(URL 경로에 `/git/blobs/`가 있는 2xx 응답의 본문 길이만 셈), `SourceMeasurement`(data-model.md 9절 필드),
  `measure_source(prepared: PreparedSource, transport, clock) -> SourceMeasurement`(GitHub 어댑터·ING-001 세션·SEC-001 `screen_source`, `files = len(ScreenResult.verdicts)`, `blocked`는 `SECRET_BLOCKED`·`ERROR`·`identifier-address` 판정의 `to_dict(context)`),
  표·한 줄 JSON 출력 함수(contracts/cli.md 형식). 저장·임베딩 없음. T034 통과
- [ ] T042 [US4] `src/qello_knowledge/devtools/db.py`: `qk-dev source measure --name [--sources] [--reviews] [--exceptions] [--env-file] [--json]` 하위 명령을 연결한다.
  순서는 contracts/cli.md 1~5. 색인 진입점 설정 점검 뒤 `prepare_source`를 부르고, 통과했을 때만 `CountingTransport(HttpsTransport(allowed_hosts, GITHUB_API_TOKEN))`을 만든다 → 출력·종료 코드. 토큰은 QK-FND-001 설정 로딩으로 읽는다. T035 통과
- [ ] T043 [US4] T036 외부 호출 시험 파일을 완성하고, 기본 실행에서 수집되지만 실행되지 않는지(`deselected`) 확인한다. 이 작업에서는 외부 호출 시험을 실행하지 않는다(첫 자료원이 비활성)

**Checkpoint**: 모든 스토리 완료. 첫 자료원은 비활성이고, 활성화·측정은 사람 단계로 남는다

---

## Phase 7: Polish & Cross-Cutting

- [ ] T044 [P] `tests/unit/adapters/github/test_github_no_secret_leak.py`(SC-010): 합성 토큰으로 만든 `HttpsTransport`와 GitHub 어댑터로 재생 시나리오(정상·실패·한도)를 돌린 뒤
  `FetchResult.to_dict()`, `caplog` 전체, 예외 문자열, `last_snapshot` `repr`에 토큰·`Authorization` 문자열이 없다
- [ ] T045 [P] `tests/unit/test_boundaries.py`가 통과하는지 확인한다(`domain` 변경이 표준 라이브러리만 쓰는지). 새 모듈 `adapters/github.py`·`adapters/http.py`가 `qello_knowledge.security`를 가져오지 않는다
- [ ] T046 다른 파일 수정이 모두 끝난 뒤 `uv run ruff format .`와 `uv run ruff check .`로 정리
- [ ] T047 AGENTS.md 7절 기본 검증 전체 실행: `python3 scripts/preflight.py`, `python3 -I scripts/preflight.py`, `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run qk-dev db up`, `QK_REQUIRE_LOCALDB=1 uv run pytest`. 결과를 PR 본문용으로 기록
- [ ] T048 quickstart.md 1~3.5절 명령을 차례로 실행하고 SC별 결과를 기록한다(SC-001~008, SC-010, SC-009 자동 부분). 4절(실제 측정)은 사람 단계로 남긴다
- [ ] T049 PR 본문에 사람 확인 항목을 적는다(plan.md "사람 확인이 필요한 것"): QK-ING-001 변경 네 곳과 기존 동작 유지 증빙, 첫 자료원 비활성 등록과 활성화 절차(결정 기록 필수),
  포함 패턴 초안, 명세 예시 정정 재승인(`87f98a3`), 2차 한도 한계, 이 tasks.md의 설계 조정 세 곳

---

## 사람 단계 (구현 범위 밖, 활성화 PR)

research R-13 활성화 절차. 이 작업 목록의 완료 조건이 아니며, 에이전트가 대신하지 않는다.

1. 결정 기록(AGENTS.md 3.1, research R-16)을 쓰고 승인받는다.
2. 포함 패턴 범위 안 파일을 살펴 개인 정보를 확인한다.
3. `config/source_reviews/dnd-backend-docs.toml`을 쓴다.
4. `config/sources.toml`의 `dnd-backend-docs`를 `enabled = true`로 바꾼다.
5. `uv run qk-index sources check`가 통과하는지 본다.
6. `uv run qk-dev source measure --name dnd-backend-docs`와 `uv run pytest -m external tests/external/test_github_repo_source.py`를 실행하고,
   결과와 한도값 판단(FR-023)을 `docs/sdd/research/github-source-measurement.md`에 측정 조건과 함께 적는다.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 바로 시작. T003은 T002 뒤
- **Foundational (Phase 2)**: Setup 뒤. 모든 스토리를 막는다. T007 → T008·T009, T010 → T011. T006·T012(실제 전송)는 나머지와 병렬
- **US1 (Phase 3)**: Foundational 뒤. 어댑터 목록 조회
- **US2 (Phase 4)**: US1 뒤(같은 파일 `adapters/github.py`, 계약 시험이 목록·본문을 함께 씀)
- **US3 (Phase 5)**: US1 뒤. US2와는 시험 파일이 달라 시험 작성은 병렬로 할 수 있지만, 구현 T028은 같은 파일이라 T024 뒤에 한다
- **US4 (Phase 6)**: Foundational 뒤 시작할 수 있다(T029~T033, T037~T040은 어댑터와 무관). 측정 T034~T036·T041~T043은 US1~US3 뒤
- **Polish (Phase 7)**: 모든 스토리 뒤

### Within Each User Story

- 시험을 먼저 쓰고 실패를 확인한 뒤 구현한다
- `adapters/github.py`를 고치는 작업(T018, T019, T023, T024, T028)은 순서대로 한다
- 같은 시험 파일을 쓰는 작업(T013~T017, T025·T026, T030·T031, T032·T033, T034·T035)은 [P] 없이 차례로 쓴다
- 시험 자료 T029는 T030~T033보다 먼저, 시험 도우미 T002는 T003보다 먼저다

### Parallel Opportunities

- Phase 1: T001 뒤 T002(T003은 T002 뒤)
- Phase 2: T004, T005, T006 시험 / T009, T011, T012 구현
- US1 시험 T013(같은 파일의 T014~T017은 이어서)
- US2 시험 T020, T021, T022(파일이 서로 다름), US3 시험 T025(T026은 이어서)와 T027
- US4: T030, T032, T034, T036 시험(파일이 서로 다름, T029 뒤), T039·T040 설정 문서

---

## Parallel Example: User Story 4

```text
Task: "T030 [US4] tests/unit/sources/test_scope_review.py 확장자 검사"
Task: "T032 [US4] tests/unit/indexer/test_cli.py --reviews 사례"
Task: "T039 [US4] config/sources.toml 첫 자료원 비활성 등록"
Task: "T040 [US4] config/source_reviews/README.md"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1~2(ING-001 변경, 계약 시험 기대값, 실제 전송)
2. Phase 3 US1: 한 커밋 기준 목록
3. 멈추고 확인: 재생 응답으로 목록이 기대와 같고, 잘림·실패가 불완전인지

### Incremental Delivery

1. US1 → 목록
2. US2 → 본문·권한(SEC-001과 연결된 전 구간)
3. US3 → 한도·거부 분류
4. US4 → 수집 전 검사, 비활성 등록, 측정 명령
5. 사람 단계 → 활성화 PR에서 실제 측정
