# Contract: 명령줄과 상태 확인

모든 명령은 저장소 루트에서 `uv run`으로 실행한다. 종료 코드 0은 성공, 1은 점검·검사 실패, 2는 사용법 오류다.

## `qk-index` (색인 진입점)

| 명령 | 동작 | 종료 코드 |
| --- | --- | --- |
| `qk-index check` | 색인 진입점 설정 점검. 외부 호출 없음 | 통과 0, 실패 1 |
| `qk-index run` | 설정 점검 후, 통과하면 "수집할 자료원 없음"을 출력하고 끝낸다. 실제 수집은 후속 명세가 채운다 | 통과 0, 실패 1 |

## `qk-query` (질의응답 진입점, 로컬)

| 명령 | 동작 | 종료 코드 |
| --- | --- | --- |
| `qk-query check` | 질의응답 진입점 설정 점검. 외부 호출 없음 | 통과 0, 실패 1 |
| `qk-query serve [--port 8787]` | 로컬 HTTP 서버. 루프백(127.0.0.1)에만 묶는다 | 종료 시 0 |

## 설정 점검 출력

사람용 표 형식이 기본이고, `--json`이면 아래 JSON 한 줄을 낸다. 어느 쪽도 값을 출력하지 않는다.

```text
설정 점검: index
  OK       CLOUDFLARE_ACCOUNT_ID
  MISSING  CLOUDFLARE_API_TOKEN
  INVALID  GITHUB_API_TOKEN
  OK       DATABASE_URL
결과: 실패 (누락 1, 형식 오류 1)
```

```json
{"entrypoint": "index", "ok": false, "items": [{"name": "CLOUDFLARE_ACCOUNT_ID", "status": "OK"}]}
```

## `GET /healthz`

- 200: 질의응답 설정 점검 통과. 본문은 위 JSON과 같은 형식이다.
- 503: 점검 실패. 본문 형식은 같다.
- 그 밖의 경로는 404, `GET` 외 메서드는 405다.

## `qk-dev db` (로컬 개발 DB)

| 명령 | 동작 | 종료 코드 |
| --- | --- | --- |
| `qk-dev db up` | `docker compose up -d --wait`, 확장 `vector`·`pgroonga` 켜기. 이미 떠 있으면 그대로 두고 데이터를 지우지 않는다 | 성공 0. 확장이 없으면 확장 이름을 출력하고 1. 포트 충돌이면 포트와 `QK_LOCAL_DB_PORT` 안내를 출력하고 1 |
| `qk-dev db down` | 컨테이너를 내린다. 볼륨은 남긴다 | 0 |
| `qk-dev db reset` | 로컬 판정(research R-06)을 통과하면 볼륨까지 지우고 다시 올린다. 원격이면 거부 | 성공 0, 거부 1 |

## 테스트·린트·비밀값 검사

| 검사 | 로컬 명령 | CI job |
| --- | --- | --- |
| 테스트 | `uv run pytest` (로컬 DB 필수 확인은 `QK_REQUIRE_LOCALDB=1`) | `test` |
| 실제 외부 API 테스트 | `uv run pytest -m external` | 실행하지 않음 |
| 린트 | `uv run ruff check .` 그리고 `uv run ruff format --check .` | `lint` |
| 비밀값 검사 | `python3 scripts/preflight.py` 그리고 `git diff --check origin/main...HEAD` | `secrets` |
