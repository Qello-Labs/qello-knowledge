# Quickstart: QK-ING-002 검증 시나리오

성공 기준(SC)마다 무엇을 돌려 무엇을 보면 되는지 적는다. 기본 검증(1~3절)은 재생 응답만 쓰고 실제 원본을 부르지 않는다.
4절은 사람이 실제 원본으로 1회 실행한다. 형식과 동작은 [contracts/](contracts/)와 [data-model.md](data-model.md)를 따른다.

## 0. 준비

```bash
uv sync
uv run qk-dev db up                         # AGENTS.md 7절 기본 검증용. 이 기능 자체는 DB를 쓰지 않는다
```

## 1. 어댑터 (재생 응답, `tests/unit/adapters/github/`, `tests/contract/`)

| SC | 시나리오(재생 파일 `tests/fixtures/responses/github/`) | 볼 것 |
| --- | --- | --- |
| SC-001 | `basic`(일반 파일·하위 모듈·심볼릭 링크·디렉터리·제외 경로 섞임) | `list_all` 결과 경로 목록이 기대 목록과 같다. 하위 모듈·링크·디렉터리·제외 경로 0건 |
| SC-002 | `basic` 두 번, `moved_ref`(커밋 조회 뒤 브랜치가 움직인 상황) | 두 실행 결과가 같다. 모든 항목·본문의 `version`이 첫 커밋이고, 본문 요청 URL에 `ref`가 없다 |
| SC-003 | `truncated`, `ref_missing`(커밋 조회 422), `ref_missing_404`(커밋 조회 404), `repo_missing`(404), `empty_repo`(커밋 조회 409) | `Listing.complete`가 모두 거짓. `list_page`를 직접 부르면 `ref_missing`·`ref_missing_404`·`repo_missing`은 `NOT_FOUND`, `empty_repo`는 `INVALID_RESPONSE`이고 모두 재시도 0회 |
| SC-004 | `blob_mismatch`, 시험 안 전송 대역으로 만든 UTF-8 아닌 본문 | 해당 자료만 `PERMANENT_FAILED`·`INVALID_RESPONSE`, 나머지 100% 성공 |
| SC-005 | `visibility_public`·`_private`·`_internal`·`_missing` + SEC-001 `screen_source` | `public`만 `PASSED`, 나머지 `ACCESS_HELD`이고 본문 요청 0건 |
| SC-006 | `rate_limited_primary`(403, 남은 수 0), `rate_limited_secondary`(403, `retry-after`), `denied`(403, 헤더 없음) | 앞 둘은 `RATE_LIMITED` 일시적 실패(재시도 또는 `WAIT_TOO_LONG` 멈춤), 마지막은 재시도 0회 `ACCESS_DENIED` |
| SC-006 | `secondary_then_next`(첫 파일이 `retry-after: 60`·남은 수 100인 403을 재시도 상한까지 받고, 둘째 파일은 정상) | 둘째 파일 요청이 `retry-after` 시각 전에 나가지 않는다(가짜 시계의 대기 기록으로 확인, FR-013) |
| SC-007 | 공통 계약 시험 `tests/contract/test_github_adapter_contract.py` | 전부 통과. 모든 요청이 `GET`·`api.github.com` |

```bash
uv run pytest tests/unit/adapters tests/contract -q
```

## 2. 실제 전송 (`tests/unit/adapters/test_http.py`)

`urllib` 처리기 경계를 대역으로 바꿔 확인한다(research R-15). 볼 것: 3xx를 따라가지 않음, `max_bytes` 초과 시 `truncated`, 4xx·5xx를 응답으로 돌려줌,
시간 초과·연결 실패의 `TransportError` 종류, 인증 헤더가 `auth_hosts`에만 붙음, 예외 메시지·`repr`에 토큰이 없음(SC-010).

## 3. 설정 검사 (`tests/unit/sources/test_scope_review.py`, `tests/unit/indexer/test_cli.py`)

| SC | 사례 | 볼 것 |
| --- | --- | --- |
| SC-008 | 포함 패턴 `**/*.org`, `docs/*.m?` | `UNKNOWN_EXTENSION`, 종료 코드 1, 전송 대역 요청 0건 |
| — | 포함 패턴 `**/*.adoc`, `**/*.MD`, `docs/**` | 통과(`adoc`은 확장자 목록에 있다. 대소문자 무시. 확장자 없는 패턴은 검사하지 않는다) |
| SC-008 | 활성 자료원, 기록 없음 / 범위 다름 / 패턴 순서 다름 / `moved_to_exclude`가 제외에 없음 / 모르는 키 | `REVIEW_MISSING` / `REVIEW_SCOPE_MISMATCH` / 같음 / 같음 / `REVIEW_INVALID`, 종료 코드 1 |
| — | 비활성 자료원, 기록 없음 | 통과 |
| SC-010 | 위 모든 사례의 출력 | 기록 내용 값·설정 값이 출력에 없다 |

```bash
uv run pytest tests/unit/sources/test_scope_review.py tests/unit/indexer -q
uv run qk-index sources check                 # 저장소의 config/sources.toml: dnd-backend-docs 비활성이라 통과
```

## 3.5 측정 명령 (`tests/unit/devtools/test_measure.py`, 재생 응답)

정상, 본문 비밀값 차단(SEC-001 `SECRET_BLOCKED`), 범위 안 항목 0개 세 사례에서 측정 출력이 FR-022 항목을 모두 채우는지 본다.
본문 차단 사례도 `bodies_fetched`·`total_bytes`에 들어가고, 항목 0개 사례도 `commit`이 나온다. 실제 패턴 목록이 그대로 나오고, 출력에 본문·토큰이 없다.

## 4. 첫 실제 수집 측정 (사람, 외부 호출)

[research.md R-13](research.md#r-13-첫-자료원-등록-fr-018) 활성화 절차 1~5(결정 기록 승인 포함)를 마친 뒤 실행한다. GitHub 호출 약 84회, 0 Neurons.

```bash
uv run qk-index sources check                 # 확인 기록과 범위가 맞는지
uv run qk-dev source measure --name dnd-backend-docs
uv run pytest -m external tests/external/test_github_repo_source.py -q
```

- 볼 것(SC-009): 목록 완전, 요청 수 ≤ 실행당 한도, 판정 실패 0건, 막힌 자료마다 규칙 이름이 있다.
- 결과를 `docs/sdd/research/github-source-measurement.md`에 측정 조건과 함께 옮기고, 한도값 판단(FR-023)을 적는다.
- 측정 출력과 기록에 토큰·본문이 없는지 `python3 scripts/preflight.py`로 확인한다(SC-010).

## 5. 기본 검증 (AGENTS.md 7절)

```bash
python3 scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
QK_REQUIRE_LOCALDB=1 uv run pytest
```
