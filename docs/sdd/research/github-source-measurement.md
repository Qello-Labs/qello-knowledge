# GitHub 자료원 첫 실제 수집 측정

QK-ING-002(WBS 1.5) FR-022·FR-023 산출물이다. 첫 자료원 `dnd-backend-docs`를 활성화한 뒤 실제 원본을 한 번 수집해 요청 수, 시간, 크기, 보안 필터 판정을 재고,
QK-ING-001 기본 한도값을 다시 본다. 토큰·`.env` 값과 문서 원문은 적지 않는다.

| 항목 | 내용 |
| --- | --- |
| 측정일 | 2026-10-20 (`measured_at` 2026-10-20T12:07:29Z) |
| 측정 방법 | `uv run qk-dev source measure --name dnd-backend-docs --json` 1회. 사용자가 `.env`를 채운 뒤 에이전트가 실행했다. 저장·임베딩은 하지 않는다(research R-14) |
| 실행 환경 | 로컬 개발 환경, macOS 26.6.2 arm64, Python 3.13.16 |
| 결과 | 종료 코드 0. 목록 완전, 판정 실패(`ERROR`) 0건, 중단 없음 |
| 사용량 | GitHub REST API `GET` 83회. 임베딩·생성 0 Neurons |

## 1. 측정 조건

| 조건 | 값 |
| --- | --- |
| 자료원 | `dnd-backend-docs` (`github_repo_files`) |
| 저장소 | `dnd-side-project/dnd-15th-2-backend`, `ref = main` |
| 확정 커밋 | `6aeccd039b825dcd7a2b6c046a34ef72089a1f78` |
| 공개 범위 원값 | `visibility = public` → 접근 범위 `TEAM`(규칙 `github-visibility-v1`) |
| 트리 잘림 | 없음 |
| 포함 패턴 | `config/sources.toml` 19개 그대로(`README.md`, `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `TASK.md`, `docs/adr/**/*.md`, `docs/product/**/*.md`, `docs/harness/**/*.md`, `docs/api-response.md`, `docs/error-codes.md`, `docs/filtering-production-gate.md`, `docs/push-production-setup.md`, `docs/api/OPENAPI_WRITING_GUIDE.md`, `docs/superpowers/plans/**/*.md`, `docs/superpowers/specs/**/*.md`, `infra/**/*.md`, `**/AGENTS.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `scripts/repo-map/README.md`) |
| 제외 패턴 | 7개(`.claude/**`, `.agents/**`, `.codex/**`, `agents/**`, `templates/**`, `docs/experiments/**`, `docs/harness/ARCHITECTURE.md`) |
| 확인 기록 | `config/source_reviews/dnd-backend-docs.toml`(결과 "개인 정보 경로 제외함") |
| 보안 규칙 버전 | `sec-7222e5dd1d6e` |
| 한도값 | 분당 60회, 초당 상한 없음, 실행당 2,000회, 최대 대기 300초, 최대 소요 1,800초, 본문 상한 1,000,000바이트(QK-ING-001 기본값) |

## 2. 측정값 (FR-022)

| 항목 | 값 | 한도 대비 |
| --- | --- | --- |
| 요청 수 | 83회 | 실행당 한도 2,000의 4.2% |
| 소요 시간 | 73.3초 | 최대 소요 1,800초의 4.1% |
| 범위 안 파일 | 80개 | — |
| 본문 받음 | 80건 | — |
| 총 바이트 | 1,083,278바이트 | — |
| 가장 큰 파일 | 65,365바이트 | 본문 상한 1,000,000의 6.5% |
| 판정 결과별 | `PASSED` 79, `SECRET_BLOCKED` 1 | — |
| 규칙별 | `github-visibility-v1` 79, `env-assigned-secret` 1 | — |

- 요청 수는 research R-01 구성과 맞는다. 목록 3회(저장소, 커밋, 재귀 트리)와 본문 80회다. 추정 84회는 범위 안 81개 기준이었고, A안으로 1개를 제외해 83회가 됐다.
- 소요 시간은 분당 상한 60회가 정한 것으로 보인다. 요청 83회가 60회를 넘어 한 번 기다린다 `(추론)`.
- 파일 수와 크기는 인벤토리 1.2절 "포함" 범주(81개, 1,083 KB, 2026-10-06 `c070ae0` 기준)와 거의 같다. 인벤토리 갱신은 필요 없다고 판단한다.

### 2.1 막힌 자료

| 경로 | 판정 | 단계 | 규칙 | 줄 | 이유 |
| --- | --- | --- | --- | --- | --- |
| `docs/superpowers/plans/2026-09-10-codex-agents-token-optimization.md` | `SECRET_BLOCKED` | `CONTENT_SECRET` | `env-assigned-secret` | 383 | 이름에 `TOKEN`이 든 변수 대입 줄이 비밀값 대입 형식에 걸렸다 |

- 값은 출력하지 않고 형태만 봤다. 변수 이름은 `TOKEN_TOOL_DIR`이고 값은 `$`로 시작하는 셸 변수 참조다. 비밀값이 아니라 오탐으로 보인다 `(추론)`.
  규칙은 `${`로 시작하는 값만 빼고 `$이름` 형태는 빼지 않는다(`src/qello_knowledge/domain/secret_rules.py`).
- 막는 쪽으로 틀린 것이므로 비밀값이 새지 않는다. 손실은 계획 문서 1개(범위의 1.25%)다.
- 식별자 주소 규칙으로 막힌 자료는 없다(SC-009).
- 2026-10-20 사용자 결정으로 그대로 둔다(4절 1번 (a)).

## 3. 한도값 판단 (FR-023)

| 항목 | 기본값 | 측정 | 판단 | 근거 |
| --- | --- | --- | --- | --- |
| `max_requests_per_minute` | 60 | 83회를 73초에 보냄 | 유지 | GitHub 토큰 시간당 5,000회의 72%다(`tokens.md` 2.1). 한 실행이 2분 안에 끝나므로 더 높일 이유가 없다 |
| `max_requests_per_run` | 2,000 | 83회 | 유지 | 범위를 "결정 필요" 범주의 테스트 계획·결과와 설계 보고서(150개, 인벤토리 1.2절)까지 넓혀도 약 233회다 `(추론)`. 다른 저장소를 더할 여유를 남긴다 |
| `max_content_bytes` | 1,000,000 | 최대 65,365바이트 | 유지 | 가장 큰 문서의 약 15배다. 줄여도 비용이 줄지 않고, 상한은 큰 바이너리를 막는 안전장치다 |
| `max_run_seconds` | 1,800 | 73.3초 | 유지 | 실행 시간의 약 25배 여유다. 한도 대기(최대 300초)를 몇 번 겪어도 넘지 않는다 |

- 네 값 모두 유지하고 `config/sources.toml`에 한도값을 따로 적지 않는다(기본값 적용).
- `max_wait_seconds`(300)와 재시도 값은 이번 측정에서 한도 대기가 일어났는지 출력하지 않아 판단하지 않았다. FR-023 대상도 아니다.
- 이 판단은 에이전트 제안이다. 활성화 PR 리뷰에서 확정한다.

## 4. 사람이 정할 것

1. 막힌 자료 처리(2.1절): (a) 그대로 둔다 — 문서 1개 손실, (b) `config/security_exceptions.toml`에 경로·규칙을 정확히 적은 예외를 더한다(QK-SEC-001 예외 절차),
   (c) `$이름` 형태를 빼도록 규칙을 고친다(QK-SEC-001 코드 변경, 별도 작업). 2026-10-20 사용자 결정으로 (a)를 골랐다. 그 문서는 색인되지 않는다.
2. 한도값 판단(3절) 확정.
3. ADR-019 "다시 볼 조건"의 기준값: 2026-10-20 사용자 결정으로 요청 수가 실행당 한도의 50%(1,000회)를 넘을 때, 막힌 자료가 범위의 10%를 넘을 때로 정했다.
   이번 측정은 각각 4.2%, 1.25%다.

## 5. 남은 확인

- 외부 호출 시험 `uv run pytest -m external tests/external/test_github_repo_source.py`는 토큰을 환경 변수에서만 읽는다. 에이전트 세션은 `.env`를 읽지 않아
  `토큰 없음: GITHUB_API_TOKEN`으로 실패했다(원본 호출 0건). 2026-10-20 사람이 `uv run --env-file .env pytest -m external tests/external/test_github_repo_source.py -q`로
  실행해 통과했다(요청 수 ≤ 실행당 한도, 목록 완전, 판정 실패 0건, 중단 없음). 이 실행도 GitHub를 약 83회 불렀다 `(추론)`.
