# Quickstart: QK-FND-001 검증 절차

토큰과 `.env` 없이 저장소를 막 받은 상태에서 시작한다. 명령과 출력 형식은 [contracts/cli.md](contracts/cli.md)를 따른다.

## 준비물

- uv(Python 3.13은 uv가 받아 온다)
- Docker Desktop 또는 Docker Engine + Compose v2
- Node·wrangler·외부 계정은 필요 없다

## 1. 의존성 설치

```bash
uv sync
```

## 2. 로컬 DB 시작 (US1, FR-010~012)

```bash
uv run qk-dev db up
```

기대 결과: 확장 `vector`, `pgroonga`가 켜졌다는 출력과 종료 코드 0. 같은 명령을 한 번 더 실행해도 0이고 데이터가 남는다(SC-007).
포트 54322가 이미 쓰이면 `QK_LOCAL_DB_PORT=<다른 포트>`를 앞에 붙여 다시 실행한다.

## 3. 기본 테스트 (US1·US3, SC-001·SC-002)

```bash
QK_REQUIRE_LOCALDB=1 uv run pytest
```

기대 결과: 모두 통과. `external` 표시 테스트는 선택되지 않는다. 로컬 DB 테스트가 벡터 유사도 질의와 한국어 키워드 질의를 한 번씩 실행한다.
테스트 중 루프백 밖으로 연결을 시도하면 테스트가 실패하므로, 통과 자체가 외부 요청 0건의 증빙이다.

## 4. 린트·비밀값 검사 (US3, FR-019·FR-020)

```bash
uv run ruff check .
uv run ruff format --check .
python3 scripts/preflight.py
git diff --check origin/main...HEAD
```

## 5. 설정 점검 (US2)

`.env`가 없는 상태:

```bash
uv run qk-index check
```

기대 결과: 색인 진입점 항목이 모두 `MISSING`으로 나오고 종료 코드 1. Discord 항목은 나오지 않는다(FR-006).
값을 넣은 경우의 통과·형식 오류·우선순위 시나리오는 `tests/unit/config/`가 가짜 값으로 검증한다.

## 6. 진입점 실행 (US4)

```bash
uv run qk-query serve --port 8787
```

다른 터미널에서 `curl -i http://127.0.0.1:8787/healthz`를 보내면 설정이 없으므로 503과 항목별 상태 JSON이 온다.
설정이 갖춰진 경우의 200 응답은 `tests/unit/query/`가 검증한다.

## 7. 로컬 재설정 (FR-013)

```bash
uv run qk-dev db reset
```

기대 결과: 로컬 볼륨이 지워지고 다시 올라온다. `DATABASE_URL`이 로컬이 아닌 호스트를 가리키면 거부하고 1로 끝난다.

## 8. CI (US3, SC-004~006)

PR을 열면 `test`, `lint`, `secrets` 세 검사가 따로 표시된다. 같은 커밋에서 위 3~4단계의 로컬 결과와 비교한다.
SC-004의 실패 PR 세 개는 구현 PR 리뷰 때 임시 브랜치로 확인하고 결과 링크를 PR에 남긴다.
