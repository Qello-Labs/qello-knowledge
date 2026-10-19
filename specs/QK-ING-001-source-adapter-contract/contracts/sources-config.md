# Contract: 자료원 설정 파일

위치는 저장소 루트의 `config/sources.toml`이다. `qk-index sources check`와 `qk-index run`의 `--sources <경로>`로 다른 파일을 쓸 수 있다. 비밀값이 아니므로 커밋하고,
비밀값 검사(`scripts/preflight.py`) 대상이다. 필드 정의는 [data-model.md](../data-model.md)의 SourceConfig를 따른다.

## 예

```toml
[[source]]
name = "qello-knowledge-docs"
kind = "github_repo_files"
enabled = true
auth = "GITHUB_API_TOKEN"          # QK-FND-001 설정 항목 이름. 값을 쓰지 않는다
max_content_bytes = 1_000_000
# allowed_hosts = ["api.github.com"]  # 생략하면 종류의 기본값

[source.scope]
repo = "Qello-Labs/qello-knowledge"
ref = "main"
include = ["**/*.md"]
exclude = ["specs/**/checklists/**"]

[source.limits]
max_requests_per_minute = 60
max_requests_per_run = 2000
max_wait_seconds = 300
max_run_seconds = 1800

[source.retry]
max_retries = 3
initial_backoff_seconds = 1
max_backoff_seconds = 60
```

`[source.limits]`, `[source.retry]`, `max_content_bytes`, `allowed_hosts`는 생략하면 기본값([research.md](../research.md) R-16)을 쓴다.
위 GitHub 항목은 형식 예시이고, 실제 대상과 패턴은 QK-ING-002가 정한다.

## 검증 규칙

| 규칙 | 오류 코드 | 근거 |
| --- | --- | --- |
| 필수 키(`name`, `kind`, `enabled`, 종류가 요구하는 `auth`, `scope.include`, 종류별 scope 키)가 있다 | `MISSING` | FR-008, US2-1 |
| 모르는 키가 없다 | `UNKNOWN_KEY` | research R-04 |
| 형식(이름 규칙, 양의 정수, 패턴 목록, `owner/name`)이 맞다 | `INVALID` | FR-008 |
| `name`이 파일 안에서 유일하다 | `DUPLICATE_NAME` | FR-008 |
| `kind`가 등록된 종류다. 아니면 결정 기록이 필요하다고 안내한다 | `UNKNOWN_KIND` | FR-010, US2-2 |
| `auth`가 설정 레지스트리에 있는 색인 진입점 비밀 항목 이름이다 | `UNKNOWN_AUTH_SETTING` | FR-009 |
| 어떤 문자열 값도 토큰 형식이 아니다 | `TOKEN_VALUE` | FR-009, US2-3 |

- 활성 자료원은 모든 규칙을 검사한다. 비활성 자료원은 `name`, `kind`, `enabled`와 토큰 형식(`TOKEN_VALUE`)만 검사한다.
  토큰 값 금지(FR-009)는 활성 여부와 관계없다(2026-10-19 독립 검토 반영, 사용자 결정).
- 오류는 한 번에 모두 모아 보고한다. 오류 메시지에 값을 넣지 않는다(필드 경로와 코드만).
- `UNKNOWN_KIND` 안내 문구: `등록되지 않은 자료원 종류다. 종류를 추가하려면 결정 기록이 필요하다(AGENTS.md 3.1)`.
- 토큰 형식 판단: 알려진 토큰 접두사(`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`, `cfat_`, `xox`, `sk-`, `ATATT`, `figd_`)로
  시작하는 값, 또는 `postgres`·`postgresql` 스킴 URL. 길이만 보는 규칙(예: 설정 레지스트리 `CLOUDFLARE_API_TOKEN`의 "공백 없는 40자 이상")은
  쓰지 않는다. 레지스트리 형식 규칙은 토큰이 들어갈 자리의 값을 너그럽게 확인하려고 만든 것이라, 임의 문자열 판정에 쓰면 긴 경로 패턴 같은
  정상 값을 오판한다(2026-10-19 독립 검토 반영, 사용자 결정). 토큰으로 판정된 필드는 `TOKEN_VALUE` 하나만 보고하고 같은 필드의 형식 오류를
  겹쳐 보고하지 않는다.
