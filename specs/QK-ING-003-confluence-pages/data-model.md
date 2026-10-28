# Data Model: QK-ING-003 Confluence 페이지 수집

**Date**: 2026-10-28 | 근거: [research.md](research.md) | 요구: [spec.md](spec.md)

새 저장 테이블·열·마이그레이션은 없다. 아래는 코드 안의 값 객체와 설정·기록 파일의 형식이다. 새 dataclass 필드는 모두 끝에 기본값과 함께 둔다(GitHub 어댑터가 위치 인자로 만든다).

## 1. 자료원 설정 범위 값(Confluence)

`config/sources.toml`의 `[source.scope]`. 검증은 종류 사양의 `scope_schema`가 한다(research R-12). `SourceScope.extra`에는 정규화한 문자열로 담는다.

| 키 | 형식 | 규칙 | 요구 |
| --- | --- | --- | --- |
| `include` | 문자열 목록 | 정확히 `["**"]` | FR-021a |
| `space_key` | 문자열 | 비지 않음, `~`로 시작하면 오류 | FR-002 |
| `space_id` | 숫자 문자열 | 활성이면 필수, 비활성이면 빈 값 허용 | FR-002a |
| `judge_mode` | `team_group` · `site_users` | 필수 | FR-007, FR-012 |
| `team_group_id` | 문자열 | `team_group`이면 필수, `site_users`면 없어야 함 | FR-007 |
| `doc_types` | 표 `{ "<ID>" = "<종류>" }` | 종류는 아래 표의 값. 키는 숫자 문자열 | FR-020 |
| `exclude_trees` | 문자열 목록 | 숫자 문자열, 중복 없음 | FR-021a |
| `exclude` | — | 쓰지 않는다(있으면 오류) | FR-021a |

문서 종류 값: `회의록`, `용어집`, `기능 명세`, `설계 문서`, `API 문서`, `디자인 문서`, `개발 규칙`, `색인 안 함`.

`extra` 정규화: 문자열은 그대로, 표·목록은 키 정렬·공백 없는 JSON(`separators=(",", ":")`, `ensure_ascii=False`). 범위 키 `scope_key = "confluence_pages:" + space_id`.

## 2. 설정 항목

| 이름 | 진입점 | 비밀 | 필수 | 쓰임 |
| --- | --- | --- | --- | --- |
| `ATLASSIAN_API_TOKEN` | INDEX | 예 | 켜진 Confluence 자료원이 있을 때 | `auth` |
| `ATLASSIAN_EMAIL` | INDEX | 예(계정 정보라 값 비노출) | 같음 | Basic 인증 |
| `ATLASSIAN_CLOUD_ID` | INDEX | 예(내부 식별값) | 같음 | 게이트웨이 경로 |
| `ATLASSIAN_SITE_URL` | INDEX | 예(사이트 주소) | 아니오 | 응답에 `_links.base`가 없을 때만 원본 링크 기준 주소 |

## 3. 개인 정보 확인 기록(Confluence)

`config/source_reviews/<자료원 이름>.toml`. 사람이 쓴다. 형식 예는 [contracts/source-config.md](contracts/source-config.md).

| 키 | 형식 | 규칙 |
| --- | --- | --- |
| `source`, `reviewed_on`, `reviewer_role`, `method` | 기존과 같음 | 기존과 같음 |
| `result` | `팀원 이름 외 개인 정보 없음` · `개인 정보 트리 제외함` | 뒤의 값이면 `moved_to_exclude` 필수 |
| `moved_to_exclude` | `[{ id, reason }]` | 각 `id`가 설정 `exclude_trees`에 있어야 함 |
| `team_member_names` | `허용` | 켜진 Confluence 자료원은 필수(FR-021) |
| `scope` | 설정 범위 값과 같은 키·값 | 순서 포함 일치(`doc_types`는 키 정렬 비교) |
| `site_users` | `{ reviewed_on, user_count }` | `judge_mode = "site_users"`면 필수. 이름·메일 없음 |

파생 값 `site_review_valid = site_users.reviewed_on + 90일 ≥ 오늘(UTC 날짜)`. 기록 파일 sha256과 `judge_mode`는 보안 규칙 버전 재료다(FR-012).

## 4. 원본 권한 원값

`AccessInfo(status=PROVIDED, raw=…)`. 키 순서는 아래 순서로 고정한다. 사용자·그룹 ID와 이름은 담지 않는다(FR-006).

| 키 | 값 |
| --- | --- |
| `judge_mode` | `team_group` · `site_users` |
| `space_type` | 원본 문자열 |
| `space_status` | 원본 문자열 |
| `team_group_read` | `true` · `false` (`team_group`일 때만) |
| `site_review_valid` | `true` · `false` (`site_users`일 때만) |
| `read_restricted` | `none` · `self` · `ancestor` · `unknown` |
| `ancestor_count` | 0 이상 정수 문자열 |

권한 요청(스페이스 권한·보기 제한·폴더)이 실패한 페이지는 `AccessInfo(status=UNKNOWN)`(원값 없음)이다. 판정 기록에서 `access_raw`가 비어 있는 미확인이 FR-031의 "조회 실패"다.
응답은 왔지만 값을 모르거나 상위 사슬이 구조적으로 끊긴 페이지는 `read_restricted=unknown`(규칙상 미확인, 실패로 세지 않음)이다(research R-03, R-05).

판정 규칙 `confluence-access-v1`:

| 조건 | 결과 |
| --- | --- |
| `read_restricted ∈ {self, ancestor}` | RESTRICTED (`unknown`은 아래 "그 밖"으로 UNKNOWN) |
| `space_type ∈ {global, collaboration, knowledge_base}` ∧ `space_status = current` ∧ (`team_group_read = true` ∨ `site_review_valid = true`) ∧ `read_restricted = none` | TEAM |
| 그 밖(모르는 값, 누락, `judge_mode`와 맞지 않는 키) | UNKNOWN |

## 5. 공통 형식 확장(QK-ING-001)

| 대상 | 새 필드 | 기본값 | 쓰임 |
| --- | --- | --- | --- |
| `SourceItem` | `exclusion: str \| None` | `None` | research R-07의 값. 있으면 보안 필터 PATH 단계에서 `PATH_EXCLUDED`(`source-exclude:<값>`) |
| `SourceContent` | `locator_extra: Mapping[str, object] \| None` | `None` | 청크 `locator`에 더할 키(예: `{"confluence": …}`) |
| `SourceContent` | `fingerprint_extra: str \| None` | `None` | `chunk_input_hash`의 `extra` 재료(research R-09) |
| `SourceContent` | `conversion_warnings: tuple[ConversionWarning, ...]` | `()` | 수집 요약의 변환 경고 수 |
| `ListPage` | `incomplete_reason: str \| None` | `None` | 어댑터가 목록을 불완전으로 돌려준 사유(`space_not_found`·`space_id_mismatch`·`personal_space`·`site_base_missing`·`listing_failed`) |

`ConversionWarning(kind, block)`: `kind`는 `UNSUPPORTED_BLOCK`·`TABLE_FLATTENED`·`MEETING_METADATA_MISSING`·`NOT_GLOSSARY`, `block`은 0부터 센 최상위 블록 순번이다. 원문은 담지 않는다.

선택 Protocol `MissingItemChecker`(`ports/source.py`):

```text
check_missing(session, config, source_ids: Sequence[str]) -> Mapping[str, MissingCheck]
MissingCheck = GONE | ARCHIVED | PRESENT | UNCERTAIN
```

## 6. 목록 항목 매핑(Confluence 페이지 → `SourceItem`)

| 필드 | 값 |
| --- | --- |
| `source_kind` / `item_type` | `confluence_pages` / `confluence_page` |
| `source_id` | 페이지 ID |
| `url` | `_links.base` + `_links.webui` |
| `change_key` / `change_key_kind` | `<version.number>:<sha256(title)[:12]>` / `VERSION` |
| `version` | `version.number` 문자열 |
| `modified_at` | `version.createdAt`(시간대 포함) |
| `title` | 페이지 제목 |
| `location` | `<space_key>/<제목 조각>/…`(research R-06 정규화) |
| `size_bytes` | `None`(목록에 본문이 없다). 크기 상한은 본문 요청에서 세션이 건다 |
| `access` | 4절 |
| `exclusion` | 5절 |
| `origin` | 첫 `ListPage`에 `SourceOrigin(space_id, space_key, None)` |

본문(`SourceContent`): `content_format=MARKDOWN`, `body`=변환 결과(첫 줄 `# <제목>`. 제목 줄과 자리 표시 말고 텍스트가 없으면 빈 문자열 → 청킹 `EMPTY`, "본문 없음"),
`version`=`version.number`, `title`=페이지 제목, `location`=항목과 같음,
`locator_extra={"confluence": {"page_id", "doc_type", "meeting"}}`, `fingerprint_extra`=`{"rules":"adf-md-v1","doc_type":…,"meeting":…}`의 정렬 JSON.

## 7. 청크 `locator["confluence"]`

```json
{"page_id": "<ID>", "doc_type": "회의록", "meeting": {"date": "2026-10-14", "kind": "정기 회의", "spec_ids": ["QK-RET-001"]}}
```

`meeting`은 회의록이 아니거나 `일시`가 없으면 `null`이다. Markdown 청커의 기존 키 `path`·`lines`는 그대로다.

## 8. 버전 값

"Confluence 켜짐" = 활성 `confluence_pages` 자료원이 설정에 있거나, 저장소에 그 종류의 자료원 정체성이 등록돼 있음(한 번 색인하면 끈 뒤에도 켜짐, research R-10). 아래 표의 켜짐 열은 이 뜻이다.

| 값 | 지금 | Confluence 꺼짐 | Confluence 켜짐 |
| --- | --- | --- | --- |
| 청킹 규칙 버전 | `chk-md-20d966f730bb` | 같음 | 같음(같은 Markdown 청커) |
| 메타데이터 스키마 버전 | `meta-v1`(코드 꺼짐) / `meta-v2`(코드 켜짐) | 같음 | 뒤에 `+cf1` |
| 인덱스 버전 | `iv-4c0bc4fcc642` | 같음 | 새 값. `INDEX_KEYWORD_RULES`에 없으면 검사 실패 |
| 변환 규칙 버전 | — | `adf-md-v1`(Confluence 문서 지문에만) | 같음 |
| 보안 규칙 버전 | `sec-…` | 바뀐다(종류 등록, research R-19) | 판정 방식·기록 해시도 재료 |

## 9. 보안 종류 등록(`KindSecurityPolicy`)

| 필드 | GitHub | Confluence |
| --- | --- | --- |
| `rule_name` | `github-visibility-v1` | `confluence-access-v1` |
| `public_link_hosts` | `("github.com",)` | `()` (원본 링크는 출력에서 비운다) |
| `source_id_is_path` | `True` | `False` |
| `opaque_item_fields`(새, 기본 `False`) | `False` | `True` |
| `lookup_failure_threshold`(새, 기본 `None`) | `None` | `0.10` |

## 10. 수집·동기화 요약에 더하는 값

모두 Confluence에서만 채우고 다른 종류는 0 또는 비운다: `unclassified`(미분류 페이지 수), `conversion_warnings`(종류별 수), `access_lookup_failed`(조회 실패 수),
`missing_checks`(결과별 수, 실행이 멈춰 묻지 못한 ID는 `NOT_CHECKED`), `empty_bodies`(청킹 `EMPTY` 수). 계획의 `kind_summary`에 담고, 실행·미리 보기 요약에는
값이 있을 때만 `kind_summary`·`incomplete_reason` 키를 더한다(GitHub 요약 키는 그대로). 페이지는 ID로만 가리킨다.

`SourcePlan.listing_complete`는 목록이 완전해도 계획 단계에서 불완전이 되면 거짓이고, 새 필드 `incomplete_reason`(기본 `None`)에
`missing_check_present`·`missing_check_stopped`·`access_lookup_threshold` 중 하나를 남긴다(research R-04, R-05). 목록 자체가 불완전하면 `ListPage.incomplete_reason`을 옮긴다.
GitHub 계획은 지금처럼 목록 완전성만 따르고 사유는 비어 있다.
