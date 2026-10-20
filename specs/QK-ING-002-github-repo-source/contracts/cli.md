# Contract: 명령줄

QK-ING-001 [contracts/cli.md](../../QK-ING-001-source-adapter-contract/contracts/cli.md)와 QK-SEC-001 [contracts/cli.md](../../QK-SEC-001-security-filter/contracts/cli.md)의
`qk-index`를 넓히고 `qk-dev`에 측정 명령을 더한다. 종료 코드 규칙(0 성공, 1 점검·검사 실패, 2 사용법 오류)은 같다.

## `qk-index sources check [--sources 경로] [--reviews 경로] [--json]`

ING-001 동작에 [source-reviews.md](source-reviews.md) 검사를 더한다. 원본을 부르지 않는다.

```text
자료원 설정 점검: config/sources.toml
  실패       dnd-backend-docs  github_repo_files  REVIEW_SCOPE_MISMATCH review.scope
결과: 실패 (활성 1, 비활성 0, 오류 1)
```

JSON 형식은 ING-001과 같다. 새 오류는 `issues`의 `{"field", "code"}`로 나온다.

## `qk-index run [--sources 경로] [--reviews 경로] [--exceptions 경로] [--json]`

ING-001·SEC-001 순서에서 자료원 설정 검사 단계에 확인 기록·확장자 검사가 들어간다. 그 밖은 바뀌지 않는다. 실제 수집 연결은 QK-SYN-001이 한다.

## `qk-dev source measure --name 자료원 [--sources 경로] [--reviews 경로] [--exceptions 경로] [--env-file 경로] [--json]`

실제 원본을 부르는 사람 전용 측정 명령이다(research R-14). CI와 기본 검증에서 부르지 않는다.

1. `qk-index run`과 같은 설정 점검(색인 진입점 설정, 자료원 설정, 확인 기록·확장자, 보안 예외 파일). 하나라도 실패하면 원본 호출 없이 1.
2. `--name` 자료원이 없거나 비활성이면 1.
3. 그 자료원 종류의 어댑터를 고른다. 지금은 `github_repo_files`만 지원하고, 그 밖 종류는 1.
4. `CountingTransport(HttpsTransport)`(토큰은 자료원 `auth` 설정 항목) → ING-001 세션 → SEC-001 `screen_source`. 저장·임베딩은 하지 않는다.
5. [data-model.md 9절](../data-model.md#9-수집-측정-기록-sourcemeasurement-devtoolsmeasurepy) 항목을 출력한다. 커밋·공개 범위는 어댑터 `last_snapshot`, 본문 크기는
   `CountingTransport`에서 온다. 목록이 불완전하거나 판정 실패가 있으면 출력하고 1, 아니면 0.

```text
수집 측정: dnd-backend-docs (dnd-side-project/dnd-15th-2-backend@main, 커밋 <40자>, visibility=public, 트리 잘림 없음)
  범위      include=["README.md", "docs/adr/**/*.md", ...] exclude=[".claude/**", ...]
  환경      macOS-15 / Python 3.13.x, 2026-10-21T01:23:45Z
  요청      84회 (실행당 한도 2000), 소요 92.4초, 목록 완전
  파일      범위 안 81개, 본문 받음 80건, 1,083,512바이트, 최대 61,204바이트 (본문 상한 1,000,000)
  판정      PASSED 79, SECRET_BLOCKED 1, PATH_EXCLUDED 1
  막힌 자료  docs/x/y.md  SECRET_BLOCKED  github-token
```

- 위 수치는 형식 예시이고 측정값이 아니다.
- 막힌 자료 줄의 값은 SEC-001 `SecurityVerdict.to_dict(context)`를 거친 값이다. 본문·토큰·요청 헤더는 출력하지 않는다.
- `--json`은 한 줄 JSON이다.
