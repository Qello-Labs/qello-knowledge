# Contract: 명령줄

QK-FND-001 [contracts/cli.md](../../QK-FND-001-project-skeleton-ci/contracts/cli.md)의 `qk-index`에 하위 명령을 더하고 `run`의 동작을 넓힌다.
종료 코드 규칙(0 성공, 1 점검·검사 실패, 2 사용법 오류)은 같다. 모든 명령은 원본을 호출하지 않는다.

## `qk-index sources check [--sources 경로] [--json]`

자료원 설정만 검사한다(FR-013). 설정 항목 값(토큰)은 읽지 않는다. 통과 0, 실패 1, 파일 없음·TOML 문법 오류 1.

```text
자료원 설정 점검: config/sources.toml
  OK        qello-knowledge-docs  github_repo_files  repo=Qello-Labs/qello-knowledge ref=main include=1 exclude=1
  비활성     old-wiki              github_repo_files
  실패       broken                github_repo_files  MISSING scope.include, TOKEN_VALUE auth
결과: 실패 (활성 2, 비활성 1, 오류 2)
```

```json
{"file": "config/sources.toml", "ok": false, "sources": [
  {"name": "qello-knowledge-docs", "kind": "github_repo_files", "status": "OK",
   "scope": {"repo": "Qello-Labs/qello-knowledge", "ref": "main", "include": ["**/*.md"], "exclude": ["specs/**/checklists/**"]}},
  {"name": "old-wiki", "kind": "github_repo_files", "status": "DISABLED"},
  {"name": "broken", "kind": "github_repo_files", "status": "INVALID",
   "issues": [{"field": "scope.include", "code": "MISSING"}, {"field": "auth", "code": "TOKEN_VALUE"}]}]}
```

- `--json` 출력은 한 줄이다. 위 예는 읽기 쉽게 줄을 나눴다.
- 범위 요약에는 종류별 scope 키와 패턴을 그대로 보여 준다. `TOKEN_VALUE`가 난 필드는 값 대신 코드만 보인다.

## `qk-index run [--sources 경로] [--json]`

1. 색인 진입점 설정 점검(QK-FND-001). 실패하면 1.
2. 자료원 설정 검사. 실패하면 `sources check`와 같은 보고를 내고 1. 원본을 호출하지 않는다(FR-011, US2-1).
3. 통과하면 자료원별로 상태를 출력한다. 비활성은 `비활성`, 활성은 `수집 대기`다. 실제 수집 연결은 QK-SYN-001이 한다.
   활성 자료원이 없으면 `수집할 자료원 없음`을 출력한다(QK-FND-001과 같다). 0.

## `qk-index check`

바뀌지 않는다. 설정 항목만 점검한다.
