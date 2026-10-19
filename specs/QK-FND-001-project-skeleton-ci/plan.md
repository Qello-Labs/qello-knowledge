# Implementation Plan: QK-FND-001 프로젝트 골격·설정 로딩·로컬 개발 환경·CI

**Branch**: `feat/SCRUM-97-gh-28-project-skeleton` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-FND-001-project-skeleton-ci/spec.md`

## Summary

Python 3.13 패키지 하나(`qello_knowledge`)에 질의응답·색인 두 진입점과 다섯 경계를 만든다. 설정은 레지스트리 한 곳에서 정의하고
진입점별로 필요한 항목만 점검하며 값은 출력하지 않는다. 로컬 개발 DB는 `supabase/postgres` 이미지를 `qk-dev db up` 한 명령으로 띄운다.
PR마다 테스트·린트·비밀값 검사를 GitHub Actions의 세 job으로 돌린다. 근거는 [research.md](research.md)에 있다.

## Technical Context

**Language/Version**: Python 3.13 (Cloudflare Python Workers 요구 버전, R-01)

**Primary Dependencies**: 런타임 의존성 없음(표준 라이브러리). 개발: pytest, ruff, psycopg[binary](로컬 DB 테스트), workers-py(배포 도구, 이 명세에서는 설치만)

**Storage**: 로컬 개발용 PostgreSQL 17(`supabase/postgres:17.11.0.004`, pgvector·PGroonga). 스키마는 없음(QK-STO-001)

**Testing**: pytest. 표시 `localdb`, `external`(R-07). 기본 실행에서 루프백 밖 연결 차단

**Target Platform**: 질의응답은 Cloudflare Workers(Python), 색인은 GitHub Actions `ubuntu-latest`와 개발자 PC(macOS·Linux)

**Project Type**: 단일 Python 패키지 + CLI 진입점 + Workers 진입점

**Performance Goals**: CI 세 검사 결과가 PR을 연 뒤 10분 안에 표시된다(SC-005). 새 팀원이 30분 안에 기본 테스트를 통과한다(SC-001)

**Constraints**: 기본 테스트의 외부 요청 0건(SC-002). CI Secret 없이 동작(FR-021). 비밀 값 출력 0건(SC-003). 런타임 의존성은 Workers에서 돌아야 한다

**Scale/Scope**: 골격 단계. 설정 항목 8개, 경계 5개, CI job 3개

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 아직 템플릿 상태라 원칙 초안 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다.

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01~C-03 답변 근거·현재 상태·자료 취급 | 답변 기능 없음 | 해당 없음 |
| C-04 작게 시작 | 기능 없이 자리와 규칙만 만든다. 런타임 의존성 0 | 통과 |
| C-05 비용 상한 | 유료 서비스 없음. CI는 GitHub Actions 기본 사용량 | 통과 |
| C-06 교체 가능한 경계 | `ports`에 다섯 경계, `domain`·`ports`의 외부 import를 테스트로 차단(R-04) | 통과 |
| C-07·C-08 재현·멱등 | `qk-dev db up` 재실행 안전, 색인 기능 없음 | 통과 |
| C-09 원본 읽기 전용·최소 권한 | 진입점별 필요한 토큰만 요구(FR-006). 원본 호출 없음 | 통과 |
| C-10 민감 정보 | `SecretValue` 마스킹, preflight를 CI에 연결, 응답 샘플도 검사 | 통과 |
| C-11 명세 먼저 | spec.md 승인(PR #27) 뒤 계획 | 통과 |
| C-12 검증으로 닫기 | 표시로 실제 API 테스트 분리, 응답 샘플 테스트 규칙 | 통과 |
| C-13 수치 조건 | SC-001·SC-005 실측 시 조건(러너, 캐시 여부)을 함께 기록 | 통과 |
| AGENTS.md 4절 공유 DB 초기화 금지 | `db reset`이 원격을 거부(R-06) | 통과 |
| AGENTS.md 4절 하네스 파일 변경 | AGENTS.md 7절 갱신(FR-015)은 승인 대기, 이 계획에서 고치지 않음(R-12) | 보류 — 사람 결정 |

Phase 1 설계 뒤 재점검: data-model과 contracts가 값 비출력(FR-008), 원격 재설정 거부(FR-013)를 계약으로 고정했다. 새 위반 없음.

## Project Structure

### Documentation (this feature)

```text
specs/QK-FND-001-project-skeleton-ci/
├── spec.md
├── plan.md              # 이 파일
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/cli.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks 산출물
```

### Source Code (repository root)

```text
pyproject.toml           # 패키지, 진입점 스크립트, pytest·ruff 설정
uv.lock
.python-version          # 3.13
.env.example             # 레지스트리에서 생성, 값 없음
compose.yaml             # 로컬 개발 DB 전용
src/qello_knowledge/
├── __init__.py
├── config/
│   ├── registry.py      # SettingSpec 목록과 형식 규칙
│   ├── loader.py        # 환경 변수 > .env > 기본값, SecretValue
│   ├── check.py         # CheckReport와 출력
│   └── example.py       # .env.example 생성
├── domain/              # 순수 도메인. 표준 라이브러리만
├── ports/               # 경계 Protocol: source, embedder, generator, store, chat
├── adapters/            # 외부 SDK는 여기서만 (지금은 비어 있음)
├── query/
│   ├── app.py           # handle(method, path)
│   ├── server.py        # qk-query (로컬 http.server)
│   └── worker.py        # Workers 겉껍질 (배포는 QK-BOT-001)
├── indexer/
│   └── cli.py           # qk-index
└── devtools/
    └── db.py            # qk-dev db up/down/reset
tests/
├── conftest.py          # 외부 연결 차단, localdb·external 처리
├── unit/
│   ├── config/
│   ├── query/
│   ├── indexer/
│   ├── devtools/
│   └── test_boundaries.py
├── localdb/
│   └── test_extensions.py   # 벡터·한국어 키워드 질의
├── fixtures/responses/README.md
├── test_jira_subtask.py     # 기존
└── fixtures/issue_opened.json  # 기존
scripts/
├── preflight.py         # 예외 목록 읽기 추가
└── preflight_allowlist.txt
.github/workflows/ci.yml
README.md                # 로컬 시작 절차 링크
```

**Structure Decision**: `src/` 레이아웃의 단일 패키지다. 질의응답과 색인이 설정·경계를 공유해야 하므로 패키지를 나누지 않는다.
색인 쪽 의존성이 질의응답 번들에 딸려 들어가지 않게, 무거운 의존성은 `adapters` 아래 선택 의존성 그룹(`[project.optional-dependencies]`)으로
후속 명세에서 추가한다. 기존 `tests/test_jira_subtask.py`는 그대로 두고 pytest가 함께 수집한다.

## Complexity Tracking

위반 없음.
