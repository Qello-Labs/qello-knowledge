# Contract: 자료원 설정·설정 항목·개인 정보 확인 기록

근거: [research.md](../research.md) R-12, R-13 | 값 형식: [data-model.md](../data-model.md) 1~3절

## `config/sources.toml` 비활성 등록(FR-024)

```toml
[[source]]
name = "confluence-scrum"
kind = "confluence_pages"
enabled = false
auth = "ATLASSIAN_API_TOKEN"
allowed_hosts = ["api.atlassian.com"]

[source.scope]
include = ["**"]
space_key = "SCRUM"
space_id = ""            # 켜기 전 사람이 채운다(실측 BLOCKED)
judge_mode = "site_users" # Free 사이트(2026-10-28 사용자 답)
doc_types = {}           # 첫 단계 콘텐츠 ID → 종류. 켜기 전 사람이 채운다
exclude_trees = []
```

## 검증(원본 호출 전, `qk-index sources check`·`run`)

비활성 자료원은 지금처럼 범위 값을 파싱하지 않고 확인 기록도 대조하지 않는다. 아래 표는 활성 자료원과, 측정 준비(`qk-dev source measure`)가 이름으로 고른 비활성 Confluence 자료원에 적용한다.

| 사례 | 결과 코드 |
| --- | --- |
| `space_key`가 `~`로 시작 | `INVALID`(`scope.space_key`) |
| 범위 값이 스페이스 둘 이상을 뜻함(목록 등) | `INVALID` |
| `include`가 `["**"]`가 아님, `exclude`가 있음 | `INVALID` |
| `judge_mode`가 두 값 밖, `team_group`인데 `team_group_id` 없음, `site_users`인데 있음 | `INVALID`·`MISSING` |
| `doc_types` 종류 값이 목록 밖, 키가 숫자 문자열이 아님 | `INVALID` |
| 활성인데 `space_id`가 비었음 | `MISSING` |
| 활성인데 `ATLASSIAN_*` 셋 중 하나 없음 | `AUTH_MISSING`(설정 값을 읽는 `run`·`qk-dev source measure`에서. `sources check`는 설정 값을 읽지 않는다) |
| 활성인데 확인 기록 없음·범위 불일치·`team_member_names` 없음·`site_users` 없음 | `REVIEW_MISSING`·`REVIEW_SCOPE_MISMATCH`·`REVIEW_INVALID` |
| 활성인데 Confluence 켜짐 인덱스 버전이 대응표에 없음 | `CONFLUENCE_INDEX_VERSION_UNREGISTERED` |

GitHub 자료원의 검증 규칙·결과 코드·메시지는 그대로다(SC-007). 결과 코드는 기존 이름을 따르고, 새로 만든 것은 `AUTH_MISSING`과 `CONFLUENCE_INDEX_VERSION_UNREGISTERED`다.

## 설정 항목(`config/registry.py`)

`ATLASSIAN_API_TOKEN`·`ATLASSIAN_EMAIL`·`ATLASSIAN_CLOUD_ID`·`ATLASSIAN_SITE_URL`(선택): INDEX 진입점, `secret=True`, `required=False`. 설정 예시 파일은 `uv run python -m qello_knowledge.config.example`로 다시 만든다.
비밀값 규칙의 `atlassian-token`(`ATATT` 접두어)은 그대로 두고, 범위 지정 토큰의 접두어는 발급자가 확인한다(ADR-026). 다르면 이 작업에서 규칙을 더한다.

## 한도

호출 한도는 QK-ING-001 기본값(분당 60, 실행당 2,000요청, 1,800초)이다. 이 값으로는 페이지 약 880개까지 한 실행에 끝난다(추론). 첫 측정 뒤 넘으면 `[source.limits]`로 올린다(코드 변경 없음).

## 확인 기록 예(`config/source_reviews/confluence-scrum.toml`, 사람이 쓴다)

```toml
source = "confluence-scrum"
reviewed_on = 2026-11-01
reviewer_role = "<역할>"
method = "<확인 방법>"
result = "팀원 이름 외 개인 정보 없음"
team_member_names = "허용"

[scope]
include = ["**"]
space_key = "SCRUM"
space_id = "<숫자>"
judge_mode = "site_users"
doc_types = { "<ID>" = "회의록" }
exclude_trees = []

[site_users]
reviewed_on = 2026-11-01
user_count = 0
```

이름·메일은 적지 않는다. `result = "개인 정보 트리 제외함"`이면 `moved_to_exclude = [{ id = "<ID>", reason = "<사유>" }]`가 필요하고 `id`는 `exclude_trees`에 있어야 한다.
에이전트는 이 파일을 대신 만들지 않는다(`config/source_reviews/README.md`).
