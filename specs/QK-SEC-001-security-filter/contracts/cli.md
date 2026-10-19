# Contract: 명령줄

QK-ING-001 [contracts/cli.md](../../QK-ING-001-source-adapter-contract/contracts/cli.md)의 `qk-index`에 하위 명령 하나를 더하고 `run`의 검사를 넓힌다.
종료 코드 규칙(0 성공, 1 검사 실패, 2 사용법 오류)은 같다. 모든 명령은 원본과 외부 API를 호출하지 않는다.

## `qk-index security check [--sources 경로] [--exceptions 경로] [--json]`

자료원 설정을 읽은 뒤 예외 파일을 검증하고 보안 규칙 버전을 보여 준다. 기본 경로는 `config/sources.toml`, `config/security_exceptions.toml`이다.
자료원 설정이 틀리면 `sources check`와 같은 보고를 내고 1이다(예외의 `source` 검사에 자료원 이름이 필요하다).

```text
보안 규칙 점검: config/security_exceptions.toml
  규칙 버전   sec-3f9a1c0b7d2e
  비밀값 규칙 16개, 기본 제외 범주 7개, 예외 1건
  접근 규칙   github_repo_files=github-visibility-v1, fake=fake-visibility-v1
결과: 통과
```

```text
보안 규칙 점검: config/security_exceptions.toml
  실패  exception[2].rule  UNKNOWN_RULE
  실패  exception[3].path  WILDCARD_PATH
결과: 실패 (오류 2)
```

```json
{"file": "config/security_exceptions.toml", "ok": true, "rules_version": "sec-3f9a1c0b7d2e",
 "secret_rules": 16, "exclusion_categories": 7, "exceptions": 1,
 "access_rules": {"github_repo_files": "github-visibility-v1", "fake": "fake-visibility-v1"}, "issues": []}
```

- `--json` 출력은 한 줄이다. 위 예는 읽기 쉽게 줄을 나눴다.
- 예외 항목의 `path`와 `reason`은 출력하지 않는다. 오류에는 항목 번호, 필드, 코드만 나온다.
- 규칙 수와 버전 문자열은 예시다.

## `qk-index run`

QK-ING-001의 2단계(자료원 설정 검사) 뒤에 예외 파일 검증을 더한다. 실패하면 `security check`와 같은 보고를 내고 1이다. 원본을 호출하지 않는다.
실제 수집과 필터 실행 연결은 QK-SYN-001이 한다.
