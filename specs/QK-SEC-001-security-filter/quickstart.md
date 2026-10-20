# Quickstart: QK-SEC-001 검증 절차

토큰과 실제 원본 없이 이 명세의 성공 기준을 확인하는 절차다. 모든 시험은 QK-ING-001 가짜 어댑터·재생 전송·가짜 시계로 돈다.
비밀값을 심은 시험 자료는 시험 코드가 실행 중에 만든다(research R-12). 저장소에 토큰 형식 값은 들어가지 않는다.

## 준비

QK-FND-001 [quickstart.md](../QK-FND-001-project-skeleton-ci/quickstart.md)대로 `uv sync`까지 마친다. 이 명세의 시험은 로컬 DB가 필요 없다.
PR #35(QK-ING-001)가 이 브랜치의 기반이다. #35가 바뀌면 rebase한 뒤 다시 확인한다.

## 성공 기준별 확인

시험 파일 이름은 tasks.md에서 확정한다. 아래는 확인할 내용이다.

| 성공 기준 | 명령 | 기대 결과 |
| --- | --- | --- |
| SC-001 반드시 잡을 종류 100% 차단, placeholder 0건 | `uv run pytest tests/unit/domain/test_secret_rules.py tests/unit/security -q -k "required or placeholder"` | `REQUIRED_KINDS` 종류마다 합성값이 `SECRET_BLOCKED`, `passed`에 없음. placeholder 샘플은 `PASSED` |
| SC-002 전송 직전 검사에서 보낸 요청 0건 | `uv run pytest tests/unit/security -q -k send_gate` | 비밀값 조각이 있으면 `allowed=False`. 가짜 전송자 호출 0회 |
| SC-003 기본 제외·사람 지정 제외 100%, 추가 본문 조회 0건 | `uv run pytest tests/unit/security -q -k exclusion` | 범주별 경로와 `scope.exclude` 경로가 `PATH_EXCLUDED`. `terraform.tfstate.example`도 제외. `list_all()` 반환 뒤 재생 전송 기록에 그 자료의 `items/<id>` 요청 0건 |
| SC-004 미확인·비공개·모순·미등록은 팀 공용 0건 | `uv run pytest tests/unit/security -q -k access` | 해당 사례 모두 `ACCESS_HELD`, 본문 요청 0건. 공개 사례는 `PASSED`·`TEAM` |
| SC-005 다섯 판정 경로 모두 기록 비밀값 0건 | `uv run pytest tests/unit/security -q -k no_secret_leak` | 판정 기록 JSON, 요약, `ScreenResult.fetch.to_dict()`, `caplog` 전체(ING-001 로그 포함)를 `find_secrets()`로 검사해 0건 |
| SC-006 두 번째 가짜 종류 규칙 추가 시 공통 코드 변경 0줄 | `uv run pytest tests/unit/security -q -k second_kind` | 통과 |
| | `git show --stat <두 번째 종류 규칙 커밋>` | 변경 파일이 `tests/` 아래뿐 |
| SC-007 판정 실패는 통과 0건, 나머지 100% 판정 | `uv run pytest tests/unit/security -q -k error` | 예외를 낸 자료는 `ERROR`, 나머지는 정상 판정 |
| SC-008 Phase 1 규모 1분 이내 | `uv run pytest tests/unit/security -q -k performance` | 합성 81개·1.1 MB 처리 시간 < 60초 |
| SC-009 예외가 번지지 않음 | `uv run pytest tests/unit/security -q -k exception_scope` | 같은 경로의 다른 자료원, 출처 없는 조각에 예외 적용 0건 |
| SC-010 공개 링크는 남고 내부 주소는 가림 | `uv run pytest tests/unit/security -q -k address` | `github.com` 링크 100% 남음. 등록된 내부 요청 주소·맨 호스트 이름·위치·권한 원값 안 주소, `source_id` 주소 사례의 ING-001 로그·요약 0건. 확장자와 겹치는 호스트(`<합성 이름>.md`)가 제목·권한 원값·디렉터리 부분·경로 아닌 `source_id`에 있으면 가리거나 막고, 경로 필드의 파일 이름일 때만 남는다 |
| (R-07) 같은 문자열이 필드 종류와 정책에 따라 달리 나옴 | `uv run pytest tests/unit/security/test_redact.py -q` | 같은 `<합성 이름>.md`를 `url`·`location`·`title`에 넣으면 `location`만 남음. 공개 호스트가 같고 `source_id_is_path`만 다른 두 정책에서 `source_id` 출력과 목록 단계 5번 판정이 서로 다름 |
| (FR-022) 정책 하나만 바꿔도 버전 변경 | `uv run pytest tests/unit/security -q -k version` | 비밀값 규칙·기본 제외·예외·`FILE_EXTENSIONS`·`source_id_is_path`·공개 링크 호스트 중 하나만 바꾼 정책마다 버전이 다름 |
| (FR-003·020) 판정 수 = 목록 수, 목록 불완전 보존 | `uv run pytest tests/unit/security/test_screen_source.py -q` | 조회 실패·건너뜀 자료가 `ERROR`(`fetch:…`). 페이지 실패 시 `fetch.listing_complete`가 거짓 |

## 커밋 검사와 규칙 공유 확인 (FR-009)

```bash
python3 -I scripts/preflight.py                                      # 통과. 패키지 없이 규칙 모듈을 경로로 불러온다
uv run pytest tests/unit/test_preflight_shared_rules.py -q           # 같은 규칙 목록, 3.12 문법, --staged는 index의 규칙 사용
```

## 명령줄 확인

```bash
uv run qk-index security check                                                          # 커밋된 설정: 예외 0건, 통과 0
uv run qk-index security check --exceptions tests/fixtures/security/invalid_exceptions.toml  # 종료 코드 1, 항목 번호·필드·코드만
uv run qk-index security check --json                                                   # JSON 한 줄
```

출력 형식은 [contracts/cli.md](contracts/cli.md)를 따른다.

## 전체 검증

AGENTS.md 7절 기본 검증을 그대로 실행한다. 이 PC에는 `python`이 없어 `python3`를 쓴다.

```bash
python3 scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
```

실제 외부 API 호출 시험(`-m external`)은 이 명세에 없다. 사용 Neurons는 0이다.
