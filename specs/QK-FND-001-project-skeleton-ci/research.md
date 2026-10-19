# Research: QK-FND-001 프로젝트 골격·설정 로딩·로컬 개발 환경·CI

조회일은 모두 2026-10-19다. 계획(`plan.md`)의 기술 맥락에 남은 미정 항목을 여기서 닫는다.

## R-01 언어와 두 진입점

- **Decision**: 질의응답·색인 두 진입점 모두 Python 3.13으로 쓰고 패키지 하나(`qello_knowledge`)를 공유한다.
  질의응답은 Cloudflare Python Workers(`workers.WorkerEntrypoint`)로 배포하고, 색인은 같은 패키지의 CLI로 GitHub Actions나 로컬에서 돈다.
- **Rationale**: Cloudflare 문서가 Python Workers를 정식 언어로 안내하고(패키지, FFI, Workers AI 바인딩 포함), `pyproject.toml` 기반
  `pywrangler`로 배포한다. Python Workers가 `requires-python >=3.13`을 요구하므로 3.13으로 맞춘다. 한 언어면 설정 정의(FR-005)와
  경계(FR-002)를 한 번만 만들고, AGENTS.md 7절의 `pyproject.toml` 전제와도 맞는다.
- **Alternatives considered**:
  - 질의응답 TypeScript + 색인 Python: Workers 생태계는 가장 안정적이지만 설정 정의와 경계를 두 언어로 중복해야 하고 CI도 두 벌이 된다.
  - 전부 TypeScript: 색인 쪽 Markdown·Git 처리와 기존 Python 하네스 스크립트(`scripts/*.py`)를 다시 써야 한다.
- **남는 위험**: Workers Free의 요청당 CPU 10 ms(ADR-008)를 Python Worker 기동이 얼마나 쓰는지 확인하지 않았다. 배포는 이 명세 범위 밖이라
  QK-BOT-001에서 실제 배포로 측정하고, 넘으면 질의응답 진입점만 TypeScript로 옮긴다. 경계(R-04) 덕분에 도메인 코드는 옮기지 않는다.
- **Evidence**: https://developers.cloudflare.com/workers/languages/python/ ,
  https://developers.cloudflare.com/workers/languages/python/packages/

## R-02 패키지·실행 도구

- **Decision**: uv로 의존성과 가상환경을 관리한다(`pyproject.toml` + `uv.lock`). 모든 명령은 `uv run <명령>`으로 실행한다.
- **Rationale**: `pywrangler`가 uv를 전제로 한다. lock 파일로 로컬과 CI가 같은 버전을 쓴다(SC-006). uv가 Python 3.13을 직접 받아 오므로
  팀원 PC의 기본 Python 버전과 무관하다.
- **Alternatives considered**: `pip` + `venv`(lock 없음, 3.13 설치를 팀원이 따로 해야 함), Poetry(Workers 도구와 따로 논다).

## R-03 설정 로딩

- **Decision**: 외부 의존성 없이 표준 라이브러리로 구현한다. 설정 항목은 `config/registry.py`의 `SettingSpec` 목록 한 곳에서 정의하고,
  `.env` 읽기는 `KEY=VALUE` 줄만 받는 작은 파서로 한다. 실행 환경 변수가 `.env`보다 우선한다(FR-004).
  `.env.example`은 레지스트리에서 생성하고, 생성 결과와 저장된 파일이 다르면 테스트가 실패한다.
- **Rationale**: 같은 코드가 Workers(Pyodide)에서도 돌아야 하므로 의존성을 줄인다. Workers에서는 `.env`가 없고 바인딩 환경값을 같은
  로더에 넘긴다. 값은 `SecretValue`로 감싸 `repr`·`str`이 마스킹되게 해 로그·예외에 새지 않게 한다(FR-008).
- **Alternatives considered**: pydantic-settings(검증은 편하지만 Workers 번들 크기와 기동 시간이 늘고, 검증 오류 메시지에 입력값이 들어갈 수 있다),
  python-dotenv(파서 하나 때문에 의존성 추가).

## R-04 경계 규칙 검사

- **Decision**: `qello_knowledge.domain`과 `qello_knowledge.ports`는 표준 라이브러리와 두 패키지끼리만 가져올 수 있다.
  `tests/unit/test_boundaries.py`가 AST로 import를 읽어 위반하면 실패한다. 외부 SDK는 `qello_knowledge.adapters` 아래에서만 쓴다.
- **Rationale**: FR-002가 자동 검사를 요구한다. 의존성 없는 테스트로 충분하고 위반 위치(파일·줄·모듈)를 바로 보여 준다.
- **Alternatives considered**: import-linter(설정 파일이 하나 더 생기고 규칙이 두 개뿐인 지금은 과하다). 규칙이 늘면 옮긴다.

## R-05 로컬 데이터베이스

- **Decision**: `supabase/postgres:17.11.0.004` 이미지를 `compose.yaml`로 띄운다. 호스트 포트는 `QK_LOCAL_DB_PORT`(기본 54322)로 바꿀 수 있다.
  시작은 `uv run qk-dev db up` 한 명령이다. 이 명령은 `docker compose up -d --wait`로 컨테이너를 띄우고(이미 떠 있으면 그대로 둔다),
  `vector`·`pgroonga` 확장을 `CREATE EXTENSION IF NOT EXISTS`로 켠 뒤, 켜지지 않은 확장 이름을 보고하고 실패한다(FR-011).
- **Rationale**: 운영 저장소가 Supabase(ADR-008)라 같은 배포판 이미지를 쓰면 확장 버전 차이를 줄인다. Docker Hub에 2026-10-17 갱신된
  amd64·arm64 태그가 있다. 데이터는 이름 붙은 볼륨에 둬서 재시작해도 남는다(FR-012).
- **Alternatives considered**: `groonga/pgroonga:4.1.0-alpine-17`(PGroonga는 있지만 pgvector를 따로 빌드해야 한다), `pgvector/pgvector`(PGroonga 없음).
- **남는 위험**: 이미지가 약 360 MB라 첫 시작이 느리다(SC-001 30분 안에는 든다고 본다. 실측은 SC-001 기록에서 한다).
- **Evidence**: https://hub.docker.com/r/supabase/postgres/tags

## R-06 로컬 재설정 보호

- **Decision**: `uv run qk-dev db reset`은 `DATABASE_URL`(없으면 compose 기본값)의 호스트가 `localhost`, `127.0.0.1`, `::1` 중 하나이고
  포트가 `QK_LOCAL_DB_PORT`와 같을 때만 `docker compose down -v` 후 `up`을 실행한다. 그 밖이면 원격으로 판단해 거부하고 0이 아닌 코드로 끝난다(FR-013).
  외부로 나가는 연결은 열지 않는다.
- **Rationale**: AGENTS.md 4절 공유 DB 초기화 금지. 판단은 문자열 검사만으로 하고 DB에 접속하지 않는다.

## R-07 테스트 구성

- **Decision**: pytest를 쓴다. 표시(marker)는 두 가지다.
  - `localdb`: 로컬 DB가 필요한 테스트. DB가 없으면 건너뛰되, `QK_REQUIRE_LOCALDB=1`이면 실패로 바꾼다. CI는 이 값을 켠다.
  - `external`: 실제 외부 API 테스트. 기본 실행(`addopts = -m "not external"`)에서 빠진다. `uv run pytest -m external`로 켜고,
    필요한 토큰이 없으면 `pytest.fail`로 실패한다(FR-016).
- 기본 실행에서 외부 연결은 autouse fixture가 `socket.connect`를 감싸 루프백·유닉스 소켓 외에는 예외를 내게 한다. SC-002(외부 요청 0건)를 테스트가 직접 지킨다.
- 응답 샘플은 `tests/fixtures/responses/<api>/<이름>.json`에 두고 `_meta`에 출처 API와 저장 일자를 적는다. 샘플도 비밀값 검사 대상이다(FR-017).
- **Alternatives considered**: pytest-socket(같은 일을 하지만 의존성 추가), DB 테스트를 기본 실행에서 아예 빼기(US1이 로컬 DB 검색 기능 확인을 요구한다).

## R-08 린트

- **Decision**: ruff로 코드 규칙(`ruff check`)과 형식(`ruff format --check`)을 검사한다. 버전은 `uv.lock`으로 고정해 로컬과 CI가 같다(FR-019).
- **Alternatives considered**: flake8 + black(도구 두 개, 설정 두 벌).
- **범위**: 기존 하네스 파일(`.claude/`, `.agents/`, `.codex/`, `.specify/`, `scripts/`, `tests/test_jira_subtask.py`)은 린트 대상에서 뺀다.
  이 파일들에 규칙 위반이 18건 있지만 이 작업 범위 밖이고, 하네스 파일은 사람 승인 없이 고치지 않는다(AGENTS.md 4절).
  정리는 별도 작업으로 한다.

## R-09 CI

- **Decision**: `.github/workflows/ci.yml` 한 파일에 `test`, `lint`, `secrets` 세 job을 둔다. `pull_request`와 `main` push에서 돈다.
  `permissions: contents: read`이고 Secret을 쓰지 않는다(FR-021). `test`는 `uv run qk-dev db up` 후 `QK_REQUIRE_LOCALDB=1 uv run pytest`를 돌린다.
  `secrets`는 `python scripts/preflight.py`와 `git diff --check <base>...HEAD`를 돌린다(FR-020).
- **Rationale**: job이 셋이라 PR 화면에 결과가 따로 보인다(FR-018). 기존 `jira-subtask.yml`과 섞지 않는다.
- **남는 위험**: `supabase/postgres` 내려받기 시간이 SC-005(10분)를 압박할 수 있다. 첫 실행 시간을 PR 증빙으로 남긴다.

## R-10 비밀값 오탐 예외

- **Decision**: `scripts/preflight_allowlist.txt`에 `경로:규칙 이름 # 사유` 형식으로 예외를 둔다. 사유가 없는 줄은 preflight가 오류로 처리한다.
  규칙을 끄는 옵션은 두지 않는다(FR-022). 값은 기록하지 않는다.
- **Rationale**: 예외 추가가 PR diff에 드러난다. 지금 preflight에는 예외 장치가 없다.
- **범위 밖**: `tokens.md` T-01의 누락 규칙(`github_pat_`, `cfat_`, Discord 봇 토큰) 추가는 이 명세에 넣지 않는다.

## R-11 질의응답 진입점의 로컬 실행

- **Decision**: 요청 처리 로직은 순수 함수(`query/app.py`의 `handle(method, path) -> (status, body)`)로 두고 두 겉껍질이 이를 부른다.
  로컬은 표준 라이브러리 `http.server` 기반 `uv run qk-query serve`, 배포는 `query/worker.py`의 `WorkerEntrypoint`.
  `GET /healthz`는 설정 점검 결과 요약(항목 이름과 상태)을 JSON으로 돌려준다.
- **Rationale**: FR-003의 로컬 실행에 Node·wrangler를 요구하지 않는다(SC-001). Workers 겉껍질은 배포 명세(QK-BOT-001)에서 `pywrangler dev`로 검증한다.
- **Alternatives considered**: `pywrangler dev`를 로컬 기본 실행으로 쓰기(Node 설치가 필요하고 첫 기동이 느리다).

## R-12 AGENTS.md 7절 갱신

- FR-015에 따라 AGENTS.md 7절 기본 검증에 린트(`uv run ruff check .`, `uv run ruff format --check .`), 로컬 DB 시작(`uv run qk-dev db up`),
  테스트(`QK_REQUIRE_LOCALDB=1 uv run pytest`)를 추가했다. AGENTS.md는 사람 승인 대상이라 2026-10-19 사용자 승인을 받고 고쳤다.
