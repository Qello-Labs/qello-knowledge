# Quickstart: QK-ING-001 검증 절차

토큰과 실제 원본 없이 이 명세의 성공 기준을 확인하는 절차다. 모든 시험은 저장된 응답(`tests/fixtures/responses/fake/`)과 가짜 시계로 돈다.

## 준비

QK-FND-001 [quickstart.md](../QK-FND-001-project-skeleton-ci/quickstart.md)대로 `uv sync`까지 마친다. 이 명세의 시험은 로컬 DB가 필요 없다.

## 성공 기준별 확인

| 성공 기준 | 명령 | 기대 결과 |
| --- | --- | --- |
| SC-001 계약 통과, 두 번째 어댑터 추가 시 계약 밖 변경 0줄 | `uv run pytest tests/contract -q` | 가짜 어댑터 두 개의 계약 시험이 모두 통과 |
| | `git show --stat <두 번째 가짜 어댑터 커밋>` | 변경 파일이 `tests/` 아래뿐 |
| SC-002 원본 쓰기 요청 0건 | `uv run pytest tests/contract -q -k write` | 기록된 요청 메서드가 모두 `GET`·`HEAD`. 다른 메서드는 `ReadOnlyViolation` |
| SC-003 잘못된 설정은 실행 전에 실패 | `uv run pytest tests/unit/sources/test_config.py -q` | 누락·미등록 종류·토큰 값 사례 모두 실패, 재생 전송에 기록된 요청 0건 |
| SC-004 한도 초과 요청 0건 | `uv run pytest tests/unit/sources/test_limits.py tests/unit/sources/test_session.py -q` | 자료 200개 수집에서 어떤 60초 창에도 요청이 60회 이하. 원본 힌트(남은 0)를 따르고, 대기 상한 초과면 멈춤 |
| SC-005 재시도 이내 일시적 실패 100% 성공, 영구 실패 재시도 0회 | `uv run pytest tests/unit/sources/test_collect.py -q -k retry` | 일시적 2회 뒤 성공 → `SUCCEEDED`, `retries=2`. 404 → `PERMANENT_FAILED`, `retries=0` |
| SC-006 실패 격리 | `uv run pytest tests/unit/sources/test_collect.py -q -k isolation` | 한 자료가 영구 실패해도 나머지 모두 `SUCCEEDED` |
| SC-007 결과·로그 비밀값 0건 | `uv run pytest tests/unit/sources/test_no_secret_leak.py -q` | 결과 JSON과 로그를 `scripts/preflight.py` 규칙으로 검사해 0건 |

## 명령줄 확인

```bash
uv run qk-index sources check --sources tests/fixtures/sources/valid.toml          # 종료 코드 0, 자료원별 OK와 범위 요약
uv run qk-index sources check --sources tests/fixtures/sources/invalid.toml        # 종료 코드 1, 필드 경로와 오류 코드만, 값 없음
uv run qk-index sources check --sources tests/fixtures/sources/valid.toml --json   # JSON 한 줄
uv run qk-index sources check                                                      # 커밋된 config/sources.toml: 자료원 없음, 0
```

출력 형식은 [contracts/cli.md](contracts/cli.md)를 따른다.

## 전체 검증

AGENTS.md 7절 기본 검증을 그대로 실행한다.

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
```

## 후속 명세가 이 계약을 쓰는 방법

- 새 어댑터의 계약 시험: `SourceAdapterContract`를 상속하고 fixture 세 개만 구현한다([contracts/source-adapter.md](contracts/source-adapter.md)).
- 실제 자료원 없이 수집 결과가 필요한 시험: `FakeSourceAdapter`와 `ReplayTransport`에 시나리오 파일을 넘긴다.
