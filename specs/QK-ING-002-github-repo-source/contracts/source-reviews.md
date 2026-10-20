# Contract: 개인 정보 확인 기록과 포함 패턴 확장자 검사

명세 FR-019, FR-020(2026-10-20 사용자 결정 안 A). 결정 근거는 [research.md](../research.md) R-11, R-12.

## 파일

`config/source_reviews/<자료원 이름>.toml`. 자료원 하나에 파일 하나. 사람이 확인한 뒤 쓰고 PR로 검토한다. 에이전트는 이 파일을 대신 만들지 않는다.

```toml
source = "dnd-backend-docs"
reviewed_on = 2026-10-21
reviewer_role = "백엔드 리뷰어"
method = "포함 패턴에 맞는 문서 81개 전체를 열어 이름·연락처·계정 정보가 있는지 확인"
result = "개인 정보 없음"            # 또는 "개인 정보 경로 제외함"

[scope]
repo = "dnd-side-project/dnd-15th-2-backend"
ref = "main"
include = ["README.md", "docs/adr/**/*.md"]
exclude = [".claude/**"]

# result가 "개인 정보 경로 제외함"이면 1개 이상
[[moved_to_exclude]]
pattern = "docs/team/members.md"
reason = "팀원 연락처 표"
```

- 예시의 값은 형식 설명용이다. 실제 기록의 날짜·방법·범위는 확인한 사람이 쓴다.
- 이름·연락처·계정은 어떤 항목에도 쓰지 않는다. 확인한 사람은 역할로 적는다.
- 모르는 키는 `REVIEW_INVALID`다.

## 검사 (`sources/scope_review.py`)

`check_scope(configs, reviews_dir) -> tuple[ConfigIssue, ...]`. 원본을 부르지 않고 설정 값과 기록 내용을 출력하지 않는다.

| 순서 | 대상 | 조건 | `ConfigIssue` |
| --- | --- | --- | --- |
| 1 | 모든 자료원(활성·비활성) | 포함 패턴 확장자가 `FILE_EXTENSIONS` 밖이거나 판정 불가 | `scope.include[<번호>]`, `UNKNOWN_EXTENSION` |
| 2 | 활성 자료원 | 기록 파일이 없음 | `review`, `REVIEW_MISSING` |
| 3 | 활성 자료원 | TOML 문법 오류, 필수 항목 누락, 모르는 키, 타입 오류, `source`와 파일 이름 다름, `result` 값 밖 | `review` 또는 `review.<항목>`, `REVIEW_INVALID` |
| 4 | 활성 자료원 | `scope`의 `repo`·`ref`·`include`·`exclude`가 설정과 다름(패턴 순서 포함), `moved_to_exclude.pattern`이 설정 `exclude`에 없음 | `review.scope` 또는 `review.moved_to_exclude[<번호>]`, `REVIEW_SCOPE_MISMATCH` |

- 1번은 ING-001 `load_sources`가 오류 없이 읽은 자료원에만 적용한다. 2~4번은 `scope.extra`에 `repo`·`ref`가 있는 종류(`github_repo_files`)와
  그 밖 종류 모두에 적용하되, 기록의 `scope`에는 그 종류의 범위 키만 쓴다(가짜 자료원은 `include`·`exclude`만).
- 확장자 판정: 포함 패턴의 마지막 `/` 뒤 조각에 `.`이 있으면 마지막 `.` 뒤를 확장자로 본다. 영숫자만이면 `FILE_EXTENSIONS`(소문자 비교)에 있어야 하고,
  글롭 문자(`*?[`)가 있으면 판정 불가다. 마지막 조각에 `.`이 없으면 검사하지 않는다.

## 쓰는 곳

| 명령 | 동작 |
| --- | --- |
| `qk-index sources check [--reviews 경로]` | `load_sources` 오류와 `check_scope` 오류를 합쳐 같은 보고 형식으로 보인다. 오류가 있으면 1 |
| `qk-index run [--reviews 경로]` | 같은 검사를 원본 호출 전에 한다. 오류가 있으면 보고하고 1 |
| `qk-dev source measure` | 같은 검사를 통과한 활성 자료원만 측정한다 |

기본 경로는 `config/source_reviews`다. 경로가 없으면 빈 디렉터리와 같다(활성 자료원이 있으면 `REVIEW_MISSING`).
