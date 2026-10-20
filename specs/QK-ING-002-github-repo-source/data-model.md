# Data Model: QK-ING-002 GitHub 저장소 파일 수집

새 영구 저장 데이터는 없다. 수집 결과는 QK-ING-001 공통 형식(`SourceItem`, `SourceContent`, `Listing`, `FetchResult`)으로 나가고,
저장은 QK-SYN-001·QK-STO-001이 한다. 아래는 새로 생기거나 바뀌는 값 객체와 파일 형식이다. 근거는 [research.md](research.md).

## 1. QK-ING-001 공통 형식의 변경

| 대상 | 변경 | 근거 |
| --- | --- | --- |
| `domain/source.py` `ListPage` | `complete: bool = True` 추가. 거짓이면 그 페이지가 원본 목록의 일부만 담았다는 뜻이다 | R-03 |
| `domain/source.py` | `content_hash(body: str) -> str` 추가. `"sha256:" + sha256(body UTF-8).hexdigest()` | R-09 |
| `sources/collect.py` `list_all` | `page.complete`가 거짓이면 그 페이지 항목을 담고 `Listing.complete=False`로 끝낸다. 중복 제거·범위 적용은 같다 | R-03 |
| `sources/session.py` `finalize_content`, `adapters/fake.py` | `content_hash()`를 부른다. 결과 값은 지금과 같다 | R-09 |

기본값과 결과 값이 지금과 같아 기존 어댑터·시험의 동작은 바뀌지 않는다.

## 2. GitHub 응답에서 읽는 값 (어댑터 내부)

어댑터 밖으로 나가지 않는다. 필드가 없거나 타입이 다르면 `InvalidResponse`다(ING-001 FR-017 응답 형식 오류).

| 이름 | 출처 | 필드 | 검증 |
| --- | --- | --- | --- |
| `RepoInfo` | 저장소 조회 | `visibility: str \| None`, `archived: bool` | `visibility`가 문자열이 아니면 `None`(미확인). `archived`가 불린이 아니면 오류 |
| `CommitRef` | 커밋 조회 | `commit_sha: str`, `tree_sha: str` | 둘 다 40자 소문자 16진수 |
| `TreeEntry` | 트리 조회 | `path: str`, `mode: str`, `type: str`, `sha: str`, `size: int \| None` | `path`는 빈 문자열·앞 `/`·`..` 조각 금지. `blob`이면 `sha`는 40자 16진수, `size`는 0 이상 정수 |
| `TreeListing` | 트리 조회 | `entries: tuple[TreeEntry, ...]`, `truncated: bool` | `truncated`가 불린이 아니면 오류 |

목록에 쓰는 항목: `type == "blob"`이고 `mode`가 `100644` 또는 `100755`(R-04).

## 3. 목록 항목과 본문 (QK-ING-001 형식 채우기)

필드 대응은 [research.md R-04](research.md#r-04-목록-항목-필드)다. 요약:

- `SourceItem`: `source_id = location = path`, `change_key = blob SHA`(`VERSION`), `version = commit_sha`, `url = https://github.com/{repo}/blob/{commit_sha}/{path}`,
  `item_type = "repo_file"`, `title = None`, `size_bytes = size`, `access = visibility 원값 또는 미확인`, `origin_state = ARCHIVED | ACTIVE`.
- `SourceContent`: `source_id = path`, `body = UTF-8 본문`, `content_format = 확장자별`, `version = commit_sha`(항목의 `version`), `location = path`, `title = None`.
  `content_hash`·`fetched_at`은 세션이 채운다.

검증 규칙:

- 본문 바이트의 git blob SHA가 항목의 `change_key`와 같아야 한다. 다르면 `InvalidResponse`(FR-007).
- 본문은 UTF-8 엄격 디코드. 실패하면 `InvalidResponse`(FR-008).

## 4. 응답 분류와 한도 정보

| 함수 | 입력 | 출력 |
| --- | --- | --- |
| `classify(response)` | `SourceResponse` | `ResponseClass`. 403·429 한도 응답은 `TRANSIENT/RATE_LIMITED`, 그 밖 403은 `PERMANENT/ACCESS_DENIED`, 나머지는 `default_classify` |
| `rate_limit_hint(response)` | `SourceResponse` | `RateLimitHint(remaining, retry_after_seconds, retry_at)` 또는 `None`. `x-ratelimit-reset`은 남은 수가 0일 때만 `retry_at`으로 쓴다 |

## 5. 실제 전송 `HttpsTransport` (`adapters/http.py`)

| 생성 인자 | 뜻 |
| --- | --- |
| `auth_hosts: tuple[str, ...]` | 인증 헤더를 붙일 호스트(자료원 `allowed_hosts`) |
| `token: SecretValue \| None` | QK-FND-001 설정 값. `send` 안에서만 `reveal()` |
| `user_agent: str` | 기본 `qello-knowledge-indexer` |
| `timeout_seconds: float` | 기본 30 |
| `opener` | 시험용 주입점. 기본은 리다이렉트를 따르지 않는 `urllib` opener |

`send(request) -> SourceResponse`: 상태 코드, 소문자 헤더, 본문(최대 `max_bytes`), `truncated`. 예외는 `TransportError("timeout" | "connection")`뿐이다.

## 6. 공통 계약 시험 기대값 `ContractExpectations` (`tests/contract/`)

| 필드 | 가짜 어댑터 값 | GitHub 어댑터 값 |
| --- | --- | --- |
| `item_count` | 5 | 기본 시나리오 파일 수 |
| `content_version` | `"v1"` | 확정 커밋 SHA |
| `access_raw` | `(("visibility", "public"),)` | 같음 |
| `content_format` | `MARKDOWN` | 같음 |
| `write_probe_url` | `https://fake.invalid/items` | `https://api.github.com/repos/...` |
| `scenarios` | 이름 → 재생 파일. `no_modified_at`, `no_access`, `page_overlap`, `invalid_shape` | `no_modified_at`·`page_overlap`은 `None`, 나머지는 GitHub 재생 파일 |
| `content_hash_requests` | 12 | 해당 없음(`None`) |

`None` 시나리오는 대신 기본 시나리오에서 같은 성질(모든 항목 `VERSION`, 중복 0건)을 확인한다(R-10).

## 7. 포함 패턴 확장자 오류

`ConfigIssue(source=<자료원 이름>, field="scope.include[<번호>]", code="UNKNOWN_EXTENSION")`. 판정 규칙은 [research.md R-11](research.md#r-11-포함-패턴-확장자-검증-fr-019).

## 8. 개인 정보 확인 기록 `ScopeReview` (`config/source_reviews/<자료원 이름>.toml`)

형식과 검사는 [contracts/source-reviews.md](contracts/source-reviews.md). 값 객체:

| 필드 | 타입 | 규칙 |
| --- | --- | --- |
| `source` | `str` | 파일 이름(확장자 제외)과 같다 |
| `reviewed_on` | `date` | TOML 날짜 |
| `reviewer_role` | `str` | 비어 있지 않다. 이름·연락처를 쓰지 않는다(리뷰로 확인) |
| `method` | `str` | 비어 있지 않다. 살펴본 경로·표본 수 |
| `result` | `str` | `개인 정보 없음` 또는 `개인 정보 경로 제외함` |
| `scope` | `repo`, `ref`, `include`, `exclude` | 현재 자료원 설정과 같다(패턴 순서 포함) |
| `moved_to_exclude` | `[{pattern, reason}]` | 선택. `result`가 `개인 정보 경로 제외함`이면 1개 이상. `pattern`은 현재 `exclude`에 있다 |

오류 코드(`ConfigIssue.code`, 필드는 `review` 또는 `review.<항목>`): `REVIEW_MISSING`, `REVIEW_INVALID`, `REVIEW_SCOPE_MISMATCH`.
오류에 기록 내용 값은 넣지 않는다(ING-001 R-13과 같다).

## 9. 수집 측정 기록 `SourceMeasurement` (`devtools/measure.py`)

| 필드 | 출처 |
| --- | --- |
| `source_name`, `repo`, `ref`, `commit` | 설정, 항목의 `version` |
| `include_count`, `exclude_count` | 설정 |
| `measured_at`, `environment` | 실행 시각(UTC), `platform.platform()`과 Python 버전 |
| `requests`, `elapsed_seconds` | `FetchResult.requests_made`, `finished_at - started_at` |
| `listing_complete`, `stop` | `FetchResult` |
| `files`, `total_bytes`, `max_file_bytes` | 목록 항목 수, 받은 본문 UTF-8 바이트 합·최댓값 |
| `by_verdict`, `by_rule` | SEC-001 `FilterSummary` |
| `blocked` | `SECRET_BLOCKED`·`ERROR` 판정과 `identifier-address` 규칙 판정의 `SecurityVerdict.to_dict(context)` 목록(가림 거친 값) |
| `limits` | 적용한 `RateLimits`, `max_content_bytes` |

본문, 토큰, 요청 헤더는 담지 않는다.
