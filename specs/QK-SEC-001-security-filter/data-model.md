# Data Model: QK-SEC-001 색인 제외 경로·비밀값 차단·접근 범위 판정

**Date**: 2026-10-20 | **Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

값 객체는 모두 불변(`frozen=True`)이다. `domain/` 아래 타입은 표준 라이브러리와 `qello_knowledge.domain`만 가져온다(C-06, 경계 시험).
입력 타입 `SourceItem`, `SourceContent`, `AccessInfo`, `FetchResult`, `SourceConfig`는 QK-ING-001 [data-model.md](../QK-ING-001-source-adapter-contract/data-model.md)를 따른다.

## 열거형 (`domain/security.py`)

### AccessScope (FR-014)

| 값 | 뜻 | 검색 대상 |
| --- | --- | --- |
| `TEAM` | 팀 공용으로 확인됨 | 예 |
| `RESTRICTED` | 원본이 일부만 볼 수 있다고 확정함 | 아니오 |
| `UNKNOWN` | 확인할 수 없음 | 아니오 |

QK-STO-001 원본 자료 항목의 "접근 범위" 값으로 쓴다. 값 이름은 #33 `data-model.md` 작성 때 맞춘다(TASK.md 확인 필요).

### Verdict (FR-003)

`PASSED`, `PATH_EXCLUDED`, `ACCESS_HELD`, `SECRET_BLOCKED`, `ERROR`.

### Stage

`PATH`, `ACCESS`, `ITEM_SECRET`(목록 항목의 식별자·위치·제목·링크 비밀값, 식별자 주소), `FETCH`(본문 조회 실패·미시도),
`CONTENT_SECRET`(본문·제목·위치), `PASSED`(모든 단계 통과).

### FieldKind (R-07)

`LINK`(공개 원본 링크 호스트의 `https` 주소만 남김), `PATH`(파일 이름 부분만 확장자 예외), `TEXT`(숫자 버전만 남김).

## 규칙 (`domain/secret_rules.py`, `domain/exclusions.py`)

### SecretRule (FR-009)

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `name` | str | 소문자·숫자·하이픈. 판정 기록과 예외 목록이 이 이름을 쓴다 |
| `pattern` | `re.Pattern` | 모듈을 불러올 때 한 번 컴파일 |

- `RULES: tuple[SecretRule, ...]`: 커밋 검사와 색인 필터가 함께 쓰는 유일한 목록(R-02, R-03).
- `REQUIRED_KINDS: tuple[str, ...]`: FR-009가 반드시 잡는다고 정한 종류 이름. SC-001 시험 샘플은 이 목록으로 만든다. 각 종류는 `RULES`의 규칙
  하나 이상에 대응해야 하고, 이를 시험으로 확인한다.
- `find_secrets(text) -> tuple[SecretHit, ...]`: 줄마다 모든 규칙을 맞춰 `SecretHit(rule, line)`을 돌려준다. 맞은 문자열은 돌려주지 않는다.

### DefaultExclusion (FR-006)

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `category` | str | `env-file`, `private-key-file`, `secret-dir`, `infra-state`, `build-output`, `vcs-internal`, `path-invalid` |
| `pattern` | str | `PurePosixPath.full_match` 패턴. 대소문자 무시 |

- `EXAMPLE_SUFFIXES`: `.example`, `.sample`, `.template`. 이 접미사로 끝나는 파일은 `env-file` 범주의 `.env` 패턴과 `infra-state` 범주의 `*.tfvars`
  패턴에서만 빠진다. `*.tfstate*`, `.terraform/**`와 다른 범주는 예시 이름이어도 뺀다(R-04).
- `excluded_by(location) -> str | None`: 정규화한 경로가 걸린 범주 이름을 돌려준다. `..`로 시작하거나 절대 경로면 `path-invalid`.

## 정책 (`security/`)

### SecretException (FR-012)

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `source` | str | 자료원 설정에 있는 이름 |
| `path` | str | 정규화한 저장소 안 경로. 와일드카드 금지 |
| `rule` | str | `RULES`에 있는 규칙 이름 |
| `reason` | str | 비어 있지 않음. 값은 적지 않는다 |

파일 형식과 검증은 [contracts/security-exceptions.md](contracts/security-exceptions.md).

### KindSecurityPolicy (FR-015~017, FR-023)

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `kind` | str | ING-001 자료원 종류 이름 |
| `rule_name` | str | 판정 기록에 남길 접근 규칙 이름(예: `github-visibility-v1`) |
| `judge` | `Callable[[AccessInfo], AccessScope]` | `UNKNOWN` 입력이면 항상 `UNKNOWN` |
| `public_link_hosts` | tuple[str, ...] | 기록에 남겨도 되는 원본 링크 호스트(소문자) |
| `source_id_is_path` | bool | `source_id`가 저장소 안 경로인지. 참이면 `source_id`를 경로 필드로, 거짓이면 글 필드로 판정한다(R-07). `github_repo_files`=참, `fake`=거짓 |

### AddressPolicy (R-07)

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `patterns` | tuple[`re.Pattern`, ...] | 스킴 주소, IPv4·IPv6, `host:port`, 점으로 이어진 이름 |
| `file_extensions` | frozenset[str] | `FILE_EXTENSIONS`(소문자) |
| `version` | str | `ADDRESS_POLICY_VERSION` |

### OutputContext (R-07)

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `public_link_hosts` | tuple[str, ...] | 자료원 종류 정책에서. 등록되지 않은 종류면 빈 튜플 |
| `source_id_is_path` | bool | 자료원 종류 정책에서. 등록되지 않은 종류면 거짓 |
| `address_policy` | `AddressPolicy` | `SecurityPolicy.address_policy` |

- 만드는 곳은 하나다: `SecurityPolicy.output_context(kind)`. 판정(목록 단계 5번)과 기록 출력이 같은 함수로 같은 값을 얻는다.
- 필드와 `FieldKind` 대응(고정): `url`→`LINK`, `location`→`PATH`, `source_id`→`source_id_is_path`면 `PATH` 아니면 `TEXT`,
  `title`·`access_raw` 키와 값·`error_type`→`TEXT`. `verdict`·`stage`·`rule`·`rules_version`은 정해진 값이라 거르지 않는다.

### SecurityPolicy

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `rules` | tuple[SecretRule, ...] | 기본값 `RULES` |
| `exclusions` | tuple[DefaultExclusion, ...] | 기본값 모듈 목록 |
| `exceptions` | frozenset[SecretException] | 예외 파일에서 읽음 |
| `kinds` | Mapping[str, KindSecurityPolicy] | 기본값 모듈 등록부. 시험은 다른 등록부를 넘긴다(SC-006) |
| `address_policy` | `AddressPolicy` | 주소 탐지 정규식, `FILE_EXTENSIONS`, `ADDRESS_POLICY_VERSION`(R-07) |
| `version` | str | `sec-` + 12자리 해시(R-08). 위 모든 필드에서 계산 |

## 판정 결과

### SecurityVerdict (FR-019, FR-020, FR-023)

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `source_name` | str | |
| `source_id` | str | 출력 때 가림 대상 |
| `location` | str | 출력 때 가림 대상 |
| `url` | str | 출력 때 공개 원본 링크 호스트만 남김 |
| `title` | str \| None | 출력 때 가림 대상 |
| `verdict` | `Verdict` | |
| `stage` | `Stage` | 판정이 끝난 단계 |
| `rule` | str \| None | 걸린 규칙 이름(제외 범주, 비밀값 규칙, 접근 규칙 이름) |
| `lines` | tuple[int, ...] | 비밀값이 걸린 줄 번호. 본문 단계만 |
| `field` | str \| None | 비밀값이나 식별자 주소가 걸린 필드(`source_id`, `location`, `title`, `url`, `body`) |
| `access_scope` | `AccessScope` \| None | 접근 단계까지 갔으면 채움 |
| `access_raw` | tuple[tuple[str, str], ...] | 원본 권한 원값. 출력 때 키·값 각각 가림 대상 |
| `error_type` | str \| None | `ERROR`일 때. 판정 중 예외면 예외 클래스 이름만, 본문 조회 실패·미시도면 `fetch:<ItemStatus>:<FailureType 또는 none>`(R-11b) |
| `rules_version` | str | `SecurityPolicy.version` |

- 상태 규칙: `PASSED`면 `access_scope == TEAM`이고 `rule`은 접근 규칙 이름이다. `ACCESS_HELD`면 `access_scope`는 `RESTRICTED` 또는 `UNKNOWN`이다.
  `ERROR`면 `error_type`이 있다. 목록에 나온 자료마다 판정 기록이 정확히 하나다(R-11b).
- `to_dict(context: OutputContext)`: 위 대응대로 문자열 필드마다 `safe_text(value, field_kind, context)`를 거친 사전만 돌려준다(R-07). 비밀값 원문, 앞뒤 문맥, 일부를 가린 값을 담지 않는다.

### ScreenedContent

통과한 자료 하나. `item: SourceItem`, `content: SourceContent`, `access_scope: AccessScope`(항상 `TEAM`), `rules_version: str`.

### FilterSummary (FR-021)

| 필드 | 형식 |
| --- | --- |
| `source_name` | str |
| `rules_version` | str |
| `by_verdict` | Mapping[Verdict, int] |
| `by_rule` | Mapping[str, int] |
| `by_access_scope` | Mapping[AccessScope, int] |

### ScreenResult

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `passed` | tuple[ScreenedContent, ...] | 다음 단계(QK-CHK-002)로 넘길 자료만 |
| `verdicts` | tuple[SecurityVerdict, ...] | 목록에 나온 모든 자료의 판정 |
| `summary` | `FilterSummary` | |
| `fetch` | `FetchResult` | ING-001 결과에서 `contents`를 비운 사본(R-11). `listing_complete`·`stop`은 원래 목록 상태 그대로(R-11a) |

## 전송 직전 검사 (`security/send_gate.py`, FR-013)

### OutgoingPiece

`text: str`(repr 제외), `origin: tuple[str, str] | None` — `(source_name, path)` 또는 출처 없음.

### SendCheck

`allowed: bool`, `hits: tuple[SendHit, ...]`. `SendHit(piece_index, rule, line)`. 맞은 문자열은 담지 않는다.

## 상태 흐름 (자료 하나)

```text
SourceItem ─▶ PATH ──걸림──▶ PATH_EXCLUDED
                │
                ▼
             ACCESS ──TEAM 아님──▶ ACCESS_HELD
                │
                ▼
           ITEM_SECRET ──걸림──▶ SECRET_BLOCKED (식별자 주소는 rule=identifier-address)
                │
                ▼  (여기서만 fetch_contents로 넘어간다)
              FETCH ──실패·건너뜀──▶ ERROR (error_type=fetch:…)
                │
                ▼
         CONTENT_SECRET ──걸림──▶ SECRET_BLOCKED
                │
                ▼
              PASSED

어느 단계든 예외 ─▶ ERROR (통과 아님)
```
