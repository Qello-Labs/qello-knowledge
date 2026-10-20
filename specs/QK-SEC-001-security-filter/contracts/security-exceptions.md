# Contract: 오탐 예외 파일 `config/security_exceptions.toml`

색인 필터의 비밀값 오탐 예외다(FR-012). 커밋 검사 예외(`scripts/preflight_allowlist.txt`)와 별개 파일이다(research R-06).
이 파일은 저장소에 커밋하고, 바꿀 때는 PR에서 사람이 검토한다. 값(비밀값처럼 보이는 문자열)은 적지 않는다.

## 형식

```toml
# 예외가 없으면 표 없이 이 주석만 둔다.
[[exception]]
source = "qello-knowledge-docs"     # config/sources.toml의 자료원 이름
path = "docs/guide/setup.md"        # 저장소 안 경로. 와일드카드 금지
rule = "assigned-secret"            # domain/secret_rules.py의 규칙 이름
reason = "설정 예시의 자리표시 값이 12자를 넘어 규칙에 걸린다"
```

## 검증

모든 오류를 모아 보고하고, 하나라도 있으면 수집 전에 멈춘다. 오류에는 필드 경로와 코드만 넣고 값은 넣지 않는다.

| 코드 | 조건 |
| --- | --- |
| `INVALID_FILE` | TOML 문법 오류, UTF-8 아님 |
| `UNKNOWN_KEY` | 최상위 `exception` 밖의 키, 항목 안 네 필드 밖의 키 |
| `MISSING` | 네 필드 중 하나가 없음 |
| `INVALID` | 빈 문자열이나 문자열 아님 |
| `UNKNOWN_SOURCE` | `source`가 자료원 설정에 없음 |
| `UNKNOWN_RULE` | `rule`이 등록된 비밀값 규칙이 아님 |
| `WILDCARD_PATH` | `path`에 `*`, `?`, `[`가 있음 |
| `INVALID_PATH` | 정규화 뒤 `..`로 시작하거나 절대 경로 |
| `DUPLICATE` | 같은 (source, path, rule)이 두 번 |

- 파일이 없으면 예외 0건으로 본다.
- `path`는 정규화(`posixpath.normpath`)한 값으로 비교한다. 대소문자는 구분한다(예외는 좁게 적용한다).
- 비활성 자료원 이름도 `source`로 쓸 수 있다.
- 예외 목록 내용은 보안 규칙 버전에 들어간다(R-08). 예외를 바꾸면 버전이 바뀐다.
