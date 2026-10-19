---
description: "QK-FND-001 구현 작업 목록"
---

# Tasks: QK-FND-001 프로젝트 골격·설정 로딩·로컬 개발 환경·CI

**Input**: `specs/QK-FND-001-project-skeleton-ci/`의 plan.md, spec.md, research.md, data-model.md, contracts/cli.md, quickstart.md

**Tests**: 포함한다. 명세의 수용 시나리오와 C-12(수용 기준은 검증으로 닫는다)가 자동 테스트를 요구한다.

**Organization**: 사용자 스토리별 단계로 나눈다. 우선순위는 US1·US2(P1) → US3(P2) → US4(P3)다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 다루고 미완료 작업에 기대지 않아 병렬로 할 수 있다
- **[Story]**: 해당 사용자 스토리(US1~US4)

---

## Phase 1: Setup

**Purpose**: 패키지와 도구 초기화

- [x] T001 `pyproject.toml` 작성: 이름 `qello-knowledge`, `requires-python = ">=3.13"`, 런타임 의존성 없음, `[dependency-groups] dev = [pytest, ruff, psycopg[binary], workers-py]`, `[project.scripts]` `qk-index = qello_knowledge.indexer.cli:main`, `qk-query = qello_knowledge.query.server:main`, `qk-dev = qello_knowledge.devtools.db:main`, `src/` 레이아웃 빌드 설정
- [x] T002 `.python-version`에 `3.13`을 쓰고 `uv lock`으로 `uv.lock`을 만든다
- [x] T003 [P] `pyproject.toml`에 ruff 설정(`target-version = "py313"`, `line-length = 120`, 규칙 `E,F,W,I,B,UP,S`, 테스트 경로의 `S101` 허용)을 추가한다
- [x] T004 [P] `pyproject.toml`에 pytest 설정 추가: `testpaths = ["tests"]`, `addopts = "-m 'not external' --strict-markers"`, markers `localdb`(로컬 DB 필요), `external`(실제 외부 API 호출)
- [x] T005 [P] 패키지 뼈대 만들기: `src/qello_knowledge/__init__.py`와 하위 패키지 `config/`, `domain/`, `ports/`, `adapters/`, `query/`, `indexer/`, `devtools/`의 `__init__.py`

---

## Phase 2: Foundational

**Purpose**: 모든 스토리가 쓰는 테스트 기반. 끝나야 스토리 작업을 시작한다

- [x] T006 `tests/conftest.py`: autouse fixture가 `socket.socket.connect`를 감싸 루프백(`127.0.0.1`, `::1`, `localhost`)과 유닉스 소켓 외 연결 시도를 `RuntimeError("외부 연결 차단: <host>")`로 막는다. `external` 표시 테스트에는 적용하지 않는다(research R-07)
- [x] T007 `tests/conftest.py`: `localdb` 표시 테스트는 로컬 DB 포트에 TCP 연결이 안 되면 건너뛰고, `QK_REQUIRE_LOCALDB=1`이면 `pytest.fail`로 바꾼다. `external` 표시 테스트용 fixture `require_env(name)`은 값이 없으면 `pytest.fail("토큰 없음: <이름>")`(값은 출력하지 않음)
- [x] T008 [P] `tests/unit/test_conftest_guards.py`: 외부 주소 연결이 차단되는지, 루프백은 허용되는지 확인
- [x] T009 `uv run pytest`로 기존 `tests/test_jira_subtask.py`가 pytest에서 그대로 통과하는지 확인한다

**Checkpoint**: 테스트 기반 완료

---

## Phase 3: User Story 2 - 실행 주체마다 필요한 설정만 검증한다 (P1)

US1의 DB 연결 판단(T021, T024)이 설정 로더를 쓰므로 US2를 먼저 한다.

**Goal**: 레지스트리 한 곳에서 설정을 정의하고, 진입점별로 필요한 항목만 점검하며 값을 출력하지 않는다

**Independent Test**: 가짜 값으로 누락·형식 오류·우선순위·통과 사례를 만들어 `check`를 실행하고, 이름과 상태만 출력되는지 본다

### Tests (US2)

- [x] T010 [P] [US2] `tests/unit/config/test_registry.py`: 이름 유일, 설명 비어 있지 않음, "비밀 항목이면 `default`는 `None`이어야 한다", 각 항목이 진입점 하나 이상을 가짐
- [x] T011 [P] [US2] `tests/unit/config/test_loader.py`: 실행 환경 변수가 `.env`보다 우선(AS4), 빈 문자열·공백은 `MISSING`, `.env`가 없어도 예외 없음, `SecretValue`의 `str`·`repr`이 `***`
- [x] T012 [P] [US2] `tests/unit/config/test_check.py`: 색인 필수 두 개 누락 시 두 이름을 한 번에 보고하고 `ok=False`(AS1), 형식 오류는 이름과 `INVALID`만(AS2), 질의응답 점검은 `GITHUB_API_TOKEN`이 없어도 통과(AS3), 전부 올바르면 `ok=True`(AS5). 가짜 토큰은 테스트 안에서 문자열을 이어 붙여 만든다(파일에 토큰 형식 문자열을 그대로 두지 않는다)
- [x] T013 [P] [US2] `tests/unit/config/test_no_secret_leak.py`: 비밀 항목에 표식 문자열을 넣고 표 출력, `--json` 출력, 예외 메시지, 로그 어디에도 표식이 일부라도 나오지 않는지(SC-003)
- [x] T014 [P] [US2] `tests/unit/config/test_example_file.py`: `config.example.render()` 결과와 저장소의 `.env.example`이 같다

### Implementation (US2)

- [x] T015 [US2] `src/qello_knowledge/config/registry.py`: `Entrypoint`(`QUERY`, `INDEX`), `SettingSpec`, 형식 규칙과 data-model.md의 초기 항목 8개. 형식 규칙: `DATABASE_URL` "`postgres` 또는 `postgresql` 스킴의 URL", `GITHUB_API_TOKEN` "`ghp_` 또는 `github_pat_`로 시작", `CLOUDFLARE_API_TOKEN` "공백 없는 40자 이상", `CLOUDFLARE_ACCOUNT_ID` "32자리 16진수", `DISCORD_APPLICATION_ID` "숫자 17~20자리", `DISCORD_PUBLIC_KEY` "64자리 16진수", `DISCORD_BOT_TOKEN` "공백 없는 50자 이상", `QK_LOG_LEVEL` "`DEBUG`, `INFO`, `WARNING`, `ERROR` 중 하나. 기본 `INFO`"
- [x] T016 [US2] `src/qello_knowledge/config/loader.py`: `.env` 파서(`KEY=VALUE`, 주석·빈 줄 무시, 따옴표 제거), 원천 우선순위 "실행 환경 변수 > `.env` > `default`", `SecretValue`(`reveal()`로만 값 접근), 진입점별 `Settings`
- [x] T017 [US2] `src/qello_knowledge/config/check.py`: `SettingStatus`, `CheckReport`, 표 출력과 `--json` 출력(contracts/cli.md 형식). 값은 담지 않는다
- [x] T018 [US2] `src/qello_knowledge/config/example.py`와 `.env.example`: 레지스트리에서 이름·설명·placeholder(`<이름-소문자>`)만 생성. 실제 값 없음
- [x] T019 [US2] `qk-index check`·`qk-query check` 명령의 공통 부분을 `src/qello_knowledge/config/cli.py`에 두고 종료 코드(통과 0, 실패 1, 사용법 2)를 맞춘다

**Checkpoint**: 설정 점검이 단독으로 동작한다

---

## Phase 4: User Story 1 - 외부 계정 없이 로컬에서 개발·테스트를 시작한다 (P1) 🎯 MVP

**Goal**: 토큰 없이 한 명령으로 로컬 DB를 띄우고 기본 테스트를 통과한다

**Independent Test**: 깨끗한 클론에서 quickstart 1~3단계를 따라 한다. 테스트 통과와 외부 요청 0건이면 통과다

### Tests (US1)

- [x] T020 [P] [US1] `tests/localdb/test_extensions.py` (`localdb` 표시): `vector`·`pgroonga` 확장이 켜져 있고, 임시 테이블에서 벡터 유사도 질의(`<->` 정렬)와 한국어 키워드 질의(`&@~`) 한 번씩 성공(AS3). 테이블은 테스트 끝에 지운다
- [x] T021 [P] [US1] `tests/unit/devtools/test_db_guard.py`: 로컬 판정이 `localhost`·`127.0.0.1`·`::1`이고 포트가 `QK_LOCAL_DB_PORT`와 같을 때만 참, 그 밖의 호스트는 거부(AS4, FR-013). DB 접속 없이 문자열만 판단
- [x] T022 [P] [US1] `tests/unit/devtools/test_db_commands.py`: `subprocess.run`을 가짜로 바꿔 `db up`이 `docker compose up -d --wait`를 부르고 볼륨 삭제 옵션을 쓰지 않는지, 확장이 없을 때 확장 이름을 출력하고 1로 끝나는지, 포트 충돌 출력이 `QK_LOCAL_DB_PORT`를 안내하는지

### Implementation (US1)

- [x] T023 [US1] `compose.yaml`: 서비스 `db`, 이미지 `supabase/postgres:17.11.0.004`, 포트 `${QK_LOCAL_DB_PORT:-54322}:5432`, 이름 붙은 볼륨, `pg_isready` healthcheck. 로컬 개발·테스트 전용이라는 주석. 비밀번호는 로컬 기본값만 쓴다
- [x] T024 [US1] `src/qello_knowledge/devtools/db.py`: `qk-dev db up|down|reset`(contracts/cli.md). `up`은 compose를 띄운 뒤 `docker compose exec db psql`로 `CREATE EXTENSION IF NOT EXISTS vector`, `pgroonga`를 실행하고 켜지지 않은 확장 이름을 보고한다. `reset`은 T021 판정을 통과할 때만 `down -v` 후 `up`
- [x] T025 [US1] `README.md`에 "로컬 시작" 절을 추가해 quickstart.md 1~3단계와 포트 변경 방법을 링크한다(FR-014)
- [x] T026 [US1] `tests/fixtures/responses/README.md`: 응답 샘플 형식(`_meta.source_api`, `_meta.saved_at`, `_meta.redactions`, `body`)과 "토큰·계정 식별자는 저장 전에 지운다" 규칙(FR-017)
- [x] T027 [US1] 로컬에서 `uv run qk-dev db up`을 두 번 연속 실행하고 데이터가 남는지 확인한다(SC-007). 결과를 PR 증빙으로 남긴다

**Checkpoint**: 로컬 시작과 기본 테스트 통과(MVP)

---

## Phase 5: User Story 3 - PR마다 테스트·린트·비밀값 검사가 자동으로 돈다 (P2)

**Goal**: 세 검사를 CI job 셋으로 돌리고, 오탐은 사유 있는 예외 목록으로만 처리한다

**Independent Test**: 실패 테스트·린트 위반·비밀값 샘플을 각각 넣은 임시 PR에서 해당 job만 실패하는지 본다

### Tests (US3)

- [x] T028 [P] [US3] `tests/unit/test_preflight_allowlist.py`: 예외 목록의 `경로:규칙 이름 # 사유` 줄은 해당 발견을 제외하고, 사유 없는 줄은 오류로 처리하며, 출력에 값이 나오지 않는다. 비밀값 형식 문자열은 테스트 안에서 이어 붙여 만든다

### Implementation (US3)

- [x] T029 [US3] `scripts/preflight.py`: `scripts/preflight_allowlist.txt`를 읽어 예외를 적용한다. 사유 없는 줄은 실패, 규칙을 끄는 옵션은 두지 않는다(FR-022). 빈 `scripts/preflight_allowlist.txt`에 형식 설명 주석을 둔다
- [x] T030 [US3] `.github/workflows/ci.yml`: `pull_request`와 `main` push, `permissions: contents: read`, Secret 사용 없음. job `test`(setup-uv → `uv sync` → `uv run qk-dev db up` → `QK_REQUIRE_LOCALDB=1 uv run pytest`), job `lint`(`uv run ruff check .`, `uv run ruff format --check .`), job `secrets`(`python3 scripts/preflight.py`, `fetch-depth: 0`로 받아 PR이면 `git diff --check origin/<base>...HEAD`, push면 `git diff --check HEAD^ HEAD`). job마다 `timeout-minutes: 10`
- [ ] T031 [US3] 이 브랜치 PR에서 세 job이 따로 표시되고 통과하는지, 로컬 결과와 같은지 확인하고 실행 기록 링크를 남긴다(SC-005, SC-006)
- [ ] T032 [US3] SC-004 확인: 임시 브랜치 세 개(실패 테스트, 린트 위반, 비밀값 샘플)를 Draft PR로 열어 해당 job만 실패하는지 보고 링크를 남긴 뒤 닫고 브랜치를 지운다. 비밀값 샘플은 실제 값이 아닌 형식만 맞춘 가짜 문자열을 쓴다

**Checkpoint**: CI 동작

---

## Phase 6: User Story 4 - 교체 경계와 두 실행 진입점 (P3)

**Goal**: 두 진입점이 따로 실행되고, 도메인 코드의 외부 SDK 의존을 자동으로 막는다

**Independent Test**: 두 진입점을 실행하고, 경계를 어기는 import를 넣으면 테스트가 실패하는지 본다

### Tests (US4)

- [x] T033 [P] [US4] `tests/unit/test_boundaries.py`: `src/qello_knowledge/domain`·`ports` 아래 모든 파일의 import를 AST로 읽어 표준 라이브러리와 `qello_knowledge.domain`·`qello_knowledge.ports` 외에는 실패. 실패 메시지에 파일·줄·모듈 이름. 위반 예시를 임시 파일로 만들어 검사가 실제로 잡는지도 확인(AS3)
- [x] T034 [P] [US4] `tests/unit/query/test_app.py`: `GET /healthz`가 설정 통과 시 200, 실패 시 503과 contracts 형식 본문, 다른 경로 404, 다른 메서드 405
- [x] T035 [P] [US4] `tests/unit/query/test_server.py`: `qk-query serve`를 루프백 임의 포트로 띄워 `/healthz`에 요청해 응답을 받는다(AS1)
- [x] T036 [P] [US4] `tests/unit/indexer/test_cli.py`: `qk-index run`이 설정 통과 시 점검 결과와 "수집할 자료원 없음"을 출력하고 0, 실패 시 1, `check`는 외부 호출 없이 끝난다(AS2)

### Implementation (US4)

- [x] T037 [P] [US4] `src/qello_knowledge/ports/`: `source.py`, `embedder.py`, `generator.py`, `store.py`, `chat.py`에 `typing.Protocol` 경계만 정의한다. 메서드 시그니처는 후속 명세(QK-ING-001 등)가 채우므로 지금은 이름과 문서 문자열만 둔다
- [x] T038 [P] [US4] `src/qello_knowledge/domain/__init__.py`와 `src/qello_knowledge/adapters/__init__.py`에 의존 규칙을 문서 문자열로 적는다
- [x] T039 [US4] `src/qello_knowledge/query/app.py`: `handle(method, path) -> (status, body)`. 설정 점검 결과 요약만 돌려준다
- [x] T040 [US4] `src/qello_knowledge/query/server.py`: `qk-query check|serve [--port 8787]`, `127.0.0.1`에만 묶는 `http.server`
- [x] T041 [US4] `src/qello_knowledge/query/worker.py`: `workers.WorkerEntrypoint`의 `fetch`가 `handle`을 부르는 얇은 겉껍질. `workers` 모듈은 Workers 런타임에만 있으므로 테스트에서 가져오지 않는다. 배포 설정(`wrangler.toml`)은 QK-BOT-001에서 추가한다고 문서 문자열에 적는다
- [x] T042 [US4] `src/qello_knowledge/indexer/cli.py`: `qk-index check|run`

**Checkpoint**: 모든 스토리 완료

---

## Phase 7: Polish & Cross-Cutting

- [x] T043 [P] `uv run ruff format .`와 `uv run ruff check .`로 전체 정리
- [ ] T044 quickstart.md 1~7단계를 처음부터 다시 따라 하고 걸린 시간과 결과를 기록한다(SC-001 일부. 팀원 실측은 리뷰 때 받는다)
- [x] T045 `python3 scripts/preflight.py`, `git diff --check origin/main...HEAD`, TASK.md의 grep 검증을 실행한다
- [ ] T046 PR 본문에 AGENTS.md 7절에 추가할 기본 검증 명령 제안을 적는다(FR-015, research R-12). AGENTS.md는 승인 전에는 고치지 않는다

---

## Dependencies & Execution Order

- Setup(T001~T005) → Foundational(T006~T009) → US2 → US1 → US3 → US4 → Polish
- US1의 `db reset` 판정(T021, T024)이 US2의 설정 로더(T016)를 쓴다
- US3의 CI `test` job(T030)은 US1의 `qk-dev db up`(T024)을 부른다
- US4는 US2의 점검 결과(T017)를 쓴다. US1·US3와는 독립이다
- 같은 스토리 안에서는 테스트를 먼저 쓰고 실패를 확인한 뒤 구현한다

## Parallel Examples

- US2: T010~T014는 서로 다른 테스트 파일이라 함께 쓸 수 있다
- US1: T020~T022를 함께 쓴 뒤 T023·T024를 진행한다
- US4: T033~T036, T037·T038을 함께 진행한다

## Implementation Strategy

1. MVP: Setup → Foundational → US2 → US1. 여기서 로컬 시작과 기본 테스트가 된다
2. US3로 CI를 붙여 이후 커밋부터 자동 검증을 받는다
3. US4로 진입점과 경계를 마무리한다
4. 커밋은 단계별로 나눈다(`/harness-commit`): 도구 설정, 설정 로딩, 로컬 DB, CI, 진입점·경계
