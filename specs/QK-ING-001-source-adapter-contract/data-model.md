# Data Model: QK-ING-001

이 명세는 DB 스키마를 만들지 않는다(QK-STO-001 범위). 아래는 코드 안의 값 객체다. 공통 자료 형식과 요청·응답·결과 타입은
`domain/source.py`에 두고 표준 라이브러리만 쓴다(C-06, `tests/unit/test_boundaries.py`). 모두 불변(`frozen=True`)이다.

## 공통 자료 형식

### SourceItem (자료 목록 항목, FR-002)

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `source_name` | str | 자료원 설정의 `name`. 세션이 채운다 |
| `source_kind` | str | 등록된 자료원 종류 이름 |
| `source_id` | str | 원본 식별자. 자료원 안에서 유일하다. 비어 있으면 안 된다 |
| `url` | str | 사람이 여는 원본 링크. `https` |
| `change_key` | str | 변경 판별값. 비어 있으면 안 된다 |
| `change_key_kind` | `ChangeKeyKind` | `VERSION`, `MODIFIED_AT`, `CONTENT_HASH` 중 무엇으로 채웠는지 |
| `version` | str \| None | 원본 버전(커밋 SHA, 리비전 등) |
| `modified_at` | datetime \| None | 원본 수정 시각(UTC, 시간대 있음) |
| `item_type` | str | 자료 종류(예: `markdown_file`). 자료원 종류마다 정한 값 |
| `title` | str \| None | 원본이 준 제목. 없으면 `None` (research R-03) |
| `location` | str | 원본 안 위치(경로 등). 포함·제외 패턴을 이 값에 맞춘다 |
| `size_bytes` | int \| None | 원본이 알려 준 크기. 알면 크기 상한을 요청 전에 검사한다 |
| `access` | `AccessInfo` | 원본 권한 정보 |
| `origin_state` | `OriginState` \| None | 원본이 알려 준 상태. 모르면 `None` |

- `change_key` 우선순위: 원본 버전 → 수정 시각(ISO 8601 UTC 문자열) → 내용 해시. 원본이 앞의 두 값을 주지 않으면 어댑터가 본문을 받아
  해시로 채운다(US1 시나리오 3). 그 요청도 한도에 들어간다.

### AccessInfo (원본 권한 정보)

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `status` | `AccessStatus` | `PROVIDED`(원본이 줬다), `UNKNOWN`("미확인") |
| `raw` | tuple[tuple[str, str], ...] | 원본이 준 값 그대로(예: `("visibility", "public")`). `UNKNOWN`이면 빈 튜플 |

- 이 명세는 판정하지 않는다. 팀 공용인지 판정은 QK-SEC-001이 `raw`를 읽어 한다. `UNKNOWN` 자료는 검색에 노출되지 않는다(QK-STO-001 FR-008).

### OriginState

`ACTIVE`, `ARCHIVED`, `DELETED`. 원본이 알려 주는 경우에만 쓴다.

### SourceContent (자료 본문, FR-003)

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `source_id` | str | 목록 항목과 같은 값 |
| `body` | str | UTF-8로 해석한 본문. 해석 실패는 `INVALID_RESPONSE` |
| `content_format` | `ContentFormat` | `MARKDOWN`, `CODE`, `JSON`, `TEXT` |
| `version` | str \| None | 본문을 받은 시점의 원본 버전 |
| `location` | str | 원본 안 위치 |
| `title` | str \| None | 본문 조회에서 얻은 제목 |
| `content_hash` | str | `sha256:` + 본문 UTF-8 바이트의 16진 해시. 세션이 채운다 |
| `fetched_at` | datetime | 본문을 받은 시각(UTC). 세션이 채운다 |

### QK-STO-001 원본 자료 항목(FR-001)과의 대응

| QK-STO-001 FR-001 | 이 명세 |
| --- | --- |
| 자료원 종류 | `SourceItem.source_kind` (자료원 구분은 `source_name`) |
| 원본 식별자 | `SourceItem.source_id` |
| 원본 링크 | `SourceItem.url` |
| 원본 버전 | `SourceContent.version`, 없으면 `SourceItem.version` |
| 원본 수정 시각 | `SourceItem.modified_at` |
| 수집 시각 | `SourceContent.fetched_at` |
| 내용 해시 | `SourceContent.content_hash` |
| 자료 종류 | `SourceItem.item_type` |
| 제목 | `SourceContent.title`, 없으면 `SourceItem.title` |
| 접근 범위 | `SourceItem.access`를 QK-SEC-001이 판정한 값 |
| 자료 상태 | `SourceItem.origin_state`. 원본에서 사라진 것의 판단은 QK-SYN-001 |

## 목록·요청·응답

### ListPage

`items: tuple[SourceItem, ...]`, `next_cursor: str | None`. `None`이면 마지막 페이지다.

### Listing (목록 전체 결과, FR-005)

| 필드 | 규칙 |
| --- | --- |
| `items` | `source_id` 기준 중복 제거. 처음 나온 항목을 남긴다 |
| `duplicates_dropped` | 버린 중복 수 |
| `complete` | 마지막 페이지까지 받았으면 참. 페이지 실패·실행 중단이면 거짓. 거짓이면 이 목록으로 "원본에서 삭제됨"을 판단하지 않는다 |
| `excluded` | 포함·제외 패턴으로 뺀 항목 수 |
| `stop` | `StopInfo` \| None |

### SourceRequest, SourceResponse

| 타입 | 필드 |
| --- | --- |
| `SourceRequest` | `method`(`GET`·`HEAD`만), `url`, `headers`(토큰 제외, 전송이 인증 헤더를 붙인다), `max_bytes` |
| `SourceResponse` | `status`, `headers`(소문자 키), `body`(bytes), `truncated`(크기 상한에 닿아 끊었는지) |

전송 오류(시간 초과, 연결 실패)는 응답 대신 `TransportError(kind)`로 낸다.

### ResponseClass, RateLimitHint

- `ResponseClass`: `outcome`(`OK`, `TRANSIENT`, `PERMANENT`, `AUTH`)과 `failure`(`FailureType` \| None)
- `RateLimitHint`: `remaining`(int \| None), `retry_at`(datetime \| None)

## 자료원 설정

값 객체(`SourceConfig`, `SourceScope`, `RateLimits`, `RetryPolicy`)는 `domain/source_config.py`에 둔다. `ports/source.py`가 이 타입을 쓰므로
경계 규칙(표준 라이브러리와 `domain`·`ports`만)을 지키려는 배치다. 파일 읽기와 검증(`ConfigIssue`)은 `sources/config.py`가 한다.

### SourceConfig (FR-008)

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `name` | str | 소문자·숫자·`-`, 1~64자. 파일 안에서 유일 |
| `kind` | str | 등록된 종류(`SourceKindSpec`)만. Notion은 없다 |
| `enabled` | bool | 필수 |
| `auth` | str \| None | QK-FND-001 설정 항목 이름. 종류가 인증을 요구하면 필수. 레지스트리의 색인 진입점 비밀 항목이어야 한다 |
| `scope` | `SourceScope` | 종류별 키 + `include`·`exclude` |
| `limits` | `RateLimits` | 아래 |
| `retry` | `RetryPolicy` | 아래 |
| `max_content_bytes` | int | 1 이상. 기본 1,000,000 |
| `allowed_hosts` | tuple[str, ...] | 리다이렉트를 따라갈 호스트. 기본값은 종류가 정한다 |

### SourceScope

| 필드 | 규칙 |
| --- | --- |
| `include` | 비어 있지 않은 패턴 목록 |
| `exclude` | 패턴 목록. 겹치면 제외가 이긴다(FR-012) |
| 종류별 키 | `SourceKindSpec.scope_keys`가 정한다. 예: GitHub 저장소 파일은 `repo`(`owner/name`), `ref` |

### RateLimits (FR-014~016)

| 필드 | 기본값 | 규칙 |
| --- | --- | --- |
| `max_requests_per_minute` | 60 | 1 이상 |
| `max_requests_per_second` | 없음 | 선택. 1 이상 |
| `max_requests_per_run` | 2000 | 1 이상 |
| `max_wait_seconds` | 300 | 0 이상 |
| `max_run_seconds` | 1800 | 1 이상 |

### RetryPolicy (FR-018)

| 필드 | 기본값 | 규칙 |
| --- | --- | --- |
| `max_retries` | 3 | 0 이상. 첫 시도를 뺀 횟수 |
| `initial_backoff_seconds` | 1 | 0보다 크다 |
| `max_backoff_seconds` | 60 | `initial_backoff_seconds` 이상 |

### SourceKindSpec (등록된 자료원 종류, FR-010)

| 필드 | 규칙 |
| --- | --- |
| `name` | 예: `github_repo_files`, `fake` |
| `requires_auth` | bool |
| `scope_keys` | 필수·선택 키와 형식 규칙 |
| `default_allowed_hosts` | tuple[str, ...] |

Phase 1 등록 종류는 `github_repo_files`와 `fake` 둘이다. 종류를 더하려면 결정 기록이 필요하다(AGENTS.md 3.1).

### ConfigIssue (검증 오류)

| 필드 | 규칙 |
| --- | --- |
| `source` | 자료원 이름. 이름을 읽지 못했으면 `[[source]]` 순번 |
| `field` | 필드 경로(예: `scope.include`, `auth`) |
| `code` | `MISSING`, `UNKNOWN_KEY`, `INVALID`, `UNKNOWN_KIND`, `DUPLICATE_NAME`, `UNKNOWN_AUTH_SETTING`, `TOKEN_VALUE` |

값은 담지 않는다. 출력 형식은 [contracts/sources-config.md](contracts/sources-config.md)를 따른다.

## 수집 결과 (FR-016, FR-021)

### ItemOutcome

| 필드 | 규칙 |
| --- | --- |
| `source_id` | |
| `status` | `ItemStatus`: `SUCCEEDED`, `TRANSIENT_EXHAUSTED`(일시적 실패, 재시도 소진), `PERMANENT_FAILED`, `SKIPPED`(실행이 멈춰 시도하지 않음) |
| `retries` | 재시도 횟수 |
| `failure` | `FailureType` \| None |
| `http_status` | int \| None |

### FailureType

일시적: `RATE_LIMITED`, `SERVER_ERROR`, `TIMEOUT`, `CONNECTION`. 영구: `NOT_FOUND`, `ACCESS_DENIED`, `INVALID_RESPONSE`, `SIZE_EXCEEDED`,
`REDIRECT_BLOCKED`. 인증: `AUTH_FAILED`. 분류 기본값은 [research.md](research.md) R-07이다.

### StopInfo

| 필드 | 규칙 |
| --- | --- |
| `reason` | `AUTH_FAILED`, `WAIT_TOO_LONG`, `REQUEST_BUDGET`, `RUN_TIME` |
| `retry_at` | datetime \| None. 다시 시도할 수 있는 시각을 알면 채운다 |

### FetchResult

| 필드 | 규칙 |
| --- | --- |
| `source_name` | |
| `started_at`, `finished_at` | UTC |
| `requests_made` | 세션이 보낸 요청 수(리다이렉트·재시도 포함) |
| `listing_complete` | `Listing.complete` |
| `processed`, `failed`, `remaining` | 성공 수, 실패 수(일시적 소진 + 영구), 시도하지 않은 수 |
| `stop` | `StopInfo` \| None |
| `items` | `ItemOutcome` 목록 |
| `contents` | 성공한 `SourceContent` 목록. `to_dict()`에는 넣지 않는다 |

`to_dict()`는 JSON으로 바꿀 수 있는 사전을 돌려준다. 본문·헤더·URL 질의 문자열·토큰을 담지 않는다(SC-007).

## 상태 전이

자료 하나의 결과는 한 번만 정해진다.

```text
대기 ──시도──▶ 성공(SUCCEEDED)
  │            ├─일시적 실패─▶ 재시도 대기 ──(재시도 ≤ max_retries)──▶ 시도
  │            │                         └─(재시도 소진)──▶ TRANSIENT_EXHAUSTED
  │            ├─영구 실패──▶ PERMANENT_FAILED
  │            └─인증 실패──▶ SKIPPED(failure=AUTH_FAILED), 실행 중단
  └─실행 중단(인증·대기 초과·요청 상한·시간 초과)──▶ SKIPPED
```

인증 실패는 자료 탓이 아니므로 그 자료도 `SKIPPED`로 두어 다음 실행에서 다시 시도하게 한다.
