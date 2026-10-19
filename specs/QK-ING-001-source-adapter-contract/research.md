# Research: QK-ING-001 자료원 어댑터 계약·자료원 설정·호출 한도·재시도

조회일은 모두 2026-10-19다. 기준 코드는 `main`의 `b7be62a`(QK-FND-001 병합)다. 계획(`plan.md`)의 기술 맥락에 남은 미정 항목을 여기서 닫는다.

## R-01 계약을 세 층으로 나눈다

- **Decision**: 수집을 세 층으로 나눈다.
  - **어댑터**(자료원마다 하나): 요청을 만들고 응답을 공통 자료 형식으로 해석한다. 응답 분류와 한도 정보 읽기도 어댑터가 한다.
  - **전송**(`SourceTransport`): 요청 하나를 보내고 응답 하나를 돌려준다. 리다이렉트를 따라가지 않는다.
  - **수집 세션**(`SourceSession`, 공통): 어댑터가 부르는 유일한 요청 창구다. 읽기 전용 강제, 호출 한도, 실행당 요청 상한,
    재시도, 리다이렉트 호스트 검사, 본문 크기 상한을 여기서 한 번만 구현한다.
- **Rationale**: 한도·재시도를 어댑터마다 구현하면 자료원이 늘 때마다 같은 코드가 갈라지고, 두 번째 어댑터 추가 시 계약 밖 코드 0줄(SC-001)을
  지키기 어렵다. 요청이 모두 세션의 `send()`를 지나므로 "요청 수"가 곧 `send()` 호출 수가 되어 한도 시험(SC-004)과 쓰기 요청 0건(SC-002)을
  한 지점에서 센다.
- **Alternatives considered**:
  - 어댑터가 HTTP·재시도를 직접 처리: 구현은 짧지만 자료원마다 중복되고, 계약 테스트가 요청을 관찰할 지점이 없다.
  - 어댑터 메서드(목록·본문)를 감싸는 재시도 데코레이터: 메서드 한 번이 요청 여러 번일 수 있어 요청 수를 정확히 셀 수 없고, 실패한 요청만
    다시 보내지 못한다.

## R-02 어댑터 메서드

- **Decision**: `ports/source.py`의 `SourceAdapter` Protocol은 다음을 가진다. 시그니처와 규칙은 [contracts/source-adapter.md](contracts/source-adapter.md)에 있다.
  - `kind`: 등록된 자료원 종류 이름
  - `list_page(session, config, cursor) -> ListPage`: 목록 한 페이지와 다음 커서
  - `fetch_content(session, config, item) -> SourceContent`: 자료 하나의 본문
  - `classify(response) -> ResponseClass`, `rate_limit_hint(response) -> RateLimitHint | None`: 응답 해석. 기본 구현은 `domain/source.py`의
    함수를 그대로 쓰고, 자료원 고유 규칙이 있을 때만 바꾼다(R-07).
- 페이지 순회, 중복 제거, 목록 완전성 표시, 자료별 결과 기록은 공통 수집 함수(`sources/collect.py`)가 한다. 어댑터는 한 페이지·한 자료만 다룬다.
- **Rationale**: 페이지를 넘기는 반복과 실패 격리(C-08)를 공통으로 두면 어댑터가 작아지고, 목록 불완전 표시(FR-005)를 모든 자료원이 같은 규칙으로 낸다.

## R-03 공통 자료 형식과 QK-STO-001 원본 자료 항목

- **Decision**: 공통 형식은 `domain/source.py`의 불변 dataclass(`SourceItem`, `SourceContent`)다. QK-STO-001 FR-001의 원본 자료 항목을 빠짐없이
  채울 수 있게 아래처럼 맞춘다. 대응표는 [data-model.md](data-model.md)에 있다.
  - **제목** 필드를 둔다. 이 명세 FR-002에는 없지만, FR-003이 "QK-STO-001 원본 자료 항목을 채울 수 있어야 한다"고 하고 그 항목에 제목이 있다.
    원본이 제목을 주지 않으면 `None`이고, 청커(QK-CHK-002)가 본문에서 채울 수 있다.
  - **내용 해시**(SHA-256)와 **수집 시각**(UTC)은 어댑터가 아니라 세션이 본문을 받은 순간에 채운다. 같은 본문이면 같은 해시가 나와야 하므로(C-07)
    계산 지점을 하나로 둔다.
  - **자료원 이름**(설정의 `name`)을 둔다. QK-STO-001은 "같은 자료원 안에서 원본 식별자가 중복되지 않는다"고 하므로, 같은 종류의 자료원을
    둘 이상 등록할 때 구분할 값이 필요하다.
- **남는 위험**: QK-STO-001 `data-model.md`가 아직 없다(#33). 필드 이름이 달라도 대응표로 옮길 수 있게 쓰지만, 의미가 다른 필드(예: 원본 버전과
  변경 판별값의 관계)는 #33 담당과 확인해야 한다. TASK.md "확인 필요" 항목으로 남겼다.

## R-04 자료원 설정 파일

- **Decision**: 저장소 루트의 `config/sources.toml`에 `[[source]]` 표 배열로 선언하고, 표준 라이브러리 `tomllib`로 읽는다.
  `qk-index`는 `--sources <경로>`로 다른 파일을 받을 수 있다. 형식은 [contracts/sources-config.md](contracts/sources-config.md)에 있다.
  - 모르는 키는 오류다(오타로 제외 패턴이 무시되는 일을 막는다).
  - 인증은 `auth = "GITHUB_API_TOKEN"`처럼 QK-FND-001 설정 항목 이름으로만 쓴다. 그 이름이 레지스트리에 있고, 색인 진입점의 비밀 항목이어야 한다.
  - 설정 안의 모든 문자열 값을 토큰 형식 규칙(레지스트리의 비밀 항목 형식 규칙과 알려진 토큰 접두사)으로 검사해 걸리면 실패한다.
    오류에는 필드 경로만 나오고 값은 나오지 않는다(FR-009, AGENTS.md 6절).
  - 활성 자료원은 전부 엄격하게 검사한다. 비활성 자료원은 이름·종류·`enabled`만 검사하고 "비활성"으로 보고한다(FR-011, US2 시나리오 4).
- 커밋하는 `config/sources.toml`에는 자료원을 넣지 않고 형식 안내 주석만 둔다. 첫 실제 자료원(GitHub 저장소 파일)은 QK-ING-002가 추가한다.
  시험용 설정은 `tests/fixtures/sources/`에 둔다.
- **Rationale**: 런타임 의존성 없이(QK-FND-001 R-03) 읽을 수 있고, 주석을 달 수 있고, 중첩 표(`[source.scope]`, `[source.limits]`)로 자료원별
  항목을 나눌 수 있다. Python 3.13 표준 라이브러리에 있다.
- **Alternatives considered**: YAML(PyYAML 의존성 추가), JSON(주석 불가), 환경 변수(중첩 항목과 패턴 목록을 표현하기 어렵다).

## R-05 포함·제외 패턴

- **Decision**: `pathlib.PurePosixPath.full_match()`(Python 3.13 추가)로 경로 전체를 패턴과 맞춘다. 대소문자를 구분한다. 포함 패턴 중 하나에 맞고
  제외 패턴 어디에도 맞지 않을 때만 범위 안이다. 겹치면 제외가 이긴다(FR-012). 함수는 `domain/scope.py`에 둔다.
- 2026-10-19 `python3.13`(3.13.16)으로 확인한 동작:

| 경로 | 패턴 | 결과 |
| --- | --- | --- |
| `docs/a.md` | `**/*.md` | 맞음 |
| `a.md` | `**/*.md` | 맞음(`**`가 디렉터리 0개도 받는다) |
| `docs/x/y.md` | `docs/**` | 맞음 |
| `docs/x/y.md` | `docs/*` | 안 맞음(`*`는 `/`를 넘지 않는다) |
| `.github/a.md` | `**/*.md` | 맞음(숨김 경로도 맞으므로 제외는 QK-SEC-001 규칙이 맡는다) |
| `Docs/A.MD` | `**/*.md` | 안 맞음(대소문자 구분) |

- **Alternatives considered**: `fnmatch`(`*`가 `/`까지 맞아 `docs/*`가 하위 전체를 잡는다), gitignore 문법 라이브러리(의존성 추가).

## R-06 호출 한도

- **Decision**:
  - 자료원마다 **미끄러지는 창**(sliding window) 기록으로 분당 요청 수를 센다. 최근 요청 시각을 보관하고, 새 요청이 창 안의 상한을 넘으면
    가장 오래된 요청이 창을 벗어날 때까지 기다린다. 선택 항목으로 초당 상한도 같은 방식으로 둔다.
  - 실행 1회당 요청 상한에 닿으면 멈춘다(`REQUEST_BUDGET`).
  - 원본이 알려 준 한도(`RateLimitHint`: 남은 호출 수, 다시 시도할 시각)가 있으면 남은 호출이 0일 때 그 시각까지 기다린다. 설정 한도와 원본 한도 중
    더 오래 기다리게 하는 쪽을 따른다(FR-015).
  - 기다릴 시간이 `max_wait_seconds`(기본 300초)를 넘으면 기다리지 않고 멈춘다(`WAIT_TOO_LONG`). 멈출 때 처리·남은 자료 수와 다시 시도할 수
    있는 시각을 결과에 담는다(FR-016).
  - 시각과 대기는 주입한 시계(`Clock`)로 한다. 시험은 가짜 시계로 실제로 기다리지 않는다.
- **Rationale**: 미끄러지는 창은 "어떤 1분 구간에도 60회를 넘지 않는다"(US3 시나리오 1)를 그대로 보장한다. 기본 응답 헤더 `Retry-After`(초 또는
  HTTP 날짜)는 `domain/source.py` 기본 함수가 읽고, GitHub의 `x-ratelimit-remaining`·`x-ratelimit-reset` 같은 자료원 고유 헤더는 해당 어댑터의
  `rate_limit_hint()`가 읽는다(QK-ING-002).
- **Alternatives considered**: 토큰 버킷(평균은 지키지만 창 경계에서 순간적으로 상한을 넘을 수 있어 SC-004 검증이 복잡하다).

## R-07 실패 분류와 재시도

- **Decision**: 기본 응답 분류(`domain/source.py`의 `default_classify`)는 아래와 같다. 어댑터는 `classify()`로 바꿀 수 있다.

| 응답·상황 | 분류 | 실패 유형 |
| --- | --- | --- |
| 2xx | 성공 | — |
| 429 | 일시적 | `RATE_LIMITED` |
| 500, 502, 503, 504 | 일시적 | `SERVER_ERROR` |
| 연결 시간 초과 | 일시적 | `TIMEOUT` |
| 연결 실패 | 일시적 | `CONNECTION` |
| 401 | 인증 실패 | `AUTH_FAILED` |
| 403 | 영구 | `ACCESS_DENIED` (GitHub는 한도 초과도 403이므로 QK-ING-002 어댑터가 일시적으로 다시 분류한다) |
| 404, 410 | 영구 | `NOT_FOUND` |
| 등록 밖 호스트로 리다이렉트 | 영구 | `REDIRECT_BLOCKED` |
| 해석 실패(필드 누락, 형식 변경, UTF-8 아님) | 영구 | `INVALID_RESPONSE` |
| 본문 크기 상한 초과 | 영구 | `SIZE_EXCEEDED` |
| 그 밖의 4xx | 영구 | `INVALID_RESPONSE` |

- 재시도: 상한 `max_retries`(기본 3)는 첫 시도를 뺀 **재시도 횟수**다. 간격은 지수 백오프에 전체 무작위 지연(full jitter)을 쓴다:
  `uniform(0, min(max_backoff, initial_backoff × 2^n))`(기본 1초, 60초). 원본이 다시 시도할 시각을 알려 주면 그 시각을 따른다(FR-018).
  무작위 값은 주입한 `random.Random`에서 꺼내 시험에서 고정한다.
- 대기를 더하면 실행 최대 소요 시간(`max_run_seconds`, 기본 1,800초)을 넘을 때는 남은 재시도를 하지 않고 멈춘다(`RUN_TIME`).
- 인증 실패는 재시도하지 않고 그 자료원 수집을 즉시 멈춘다(`AUTH_FAILED`). 남은 자료는 "건너뜀"으로 남긴다(FR-020).
- **Rationale**: 기본값과 백오프 공식은 명세 가정(재시도 3회, 1초, 60초, 5분, 30분)을 따른다. full jitter는 여러 실행이 같은 시각에 다시 몰리는 것을
  막는다(일반 설명).

## R-08 크기 초과의 기록 방식 (명세 문구 해석)

- **Decision**: 크기 초과는 상태 "영구 실패", 실패 유형 `SIZE_EXCEEDED`로 기록한다. 상태 "건너뜀"은 시도하지 않은 자료(실행이 멈춰 남은 자료)에만 쓴다.
  - 목록이 크기를 알려 주면 본문 요청을 보내지 않는다.
  - 크기를 모르면 전송이 상한+1바이트까지만 읽고 끊는다. 본문은 결과에 남기지 않는다.
- **Rationale**: 명세 Edge Cases는 "크기 초과로 건너뜀"이라고 쓰고 FR-017은 크기 초과를 영구 실패로 분류한다. 요구사항(FR-017)을 따르고,
  동기화(QK-SYN-001)가 "건너뜀 = 다음 실행에서 다시 시도"로 읽을 수 있게 두 상태를 나눈다.
- **사람 확인**: 명세 Edge Cases 문구를 "크기 초과(영구 실패)"로 맞추는 수정을 PR에서 제안한다(C-11). 이 계획은 명세를 고치지 않는다.

## R-09 리다이렉트

- **Decision**: 전송은 리다이렉트를 따라가지 않고 3xx 응답을 그대로 돌려준다. 세션이 `Location`의 호스트가 자료원 설정 `allowed_hosts`에 있으면
  최대 3번까지 따라가고(한 번이 요청 1회로 세어진다), 없으면 따라가지 않고 `REDIRECT_BLOCKED`로 기록한다(FR-022).
- `allowed_hosts`의 기본값은 자료원 종류가 정한다. GitHub 저장소 파일은 `api.github.com`이다.

## R-10 읽기 전용 강제

- **Decision**: 세션은 `GET`과 `HEAD`만 보낸다. 다른 메서드는 보내기 전에 `ReadOnlyViolation`을 낸다. 이는 원본 실패가 아니라 어댑터 결함이므로
  자료별 결과로 삼키지 않고 실행을 멈춘다. 계약 테스트는 재생 전송이 기록한 요청의 메서드가 모두 `GET`·`HEAD`인지 본다(SC-002, C-09).
- **남는 위험**: GitHub GraphQL처럼 조회도 `POST`로 하는 API는 지금 규칙으로 막힌다. 필요해지면(QK-ING-005 후보) 자료원 종류별로 읽기 전용 `POST`
  엔드포인트를 명시하는 명세 변경을 한다.

## R-11 가짜 자료원과 재생 전송

- **Decision**:
  - `adapters/fake.py`의 `FakeSourceAdapter`: `https://fake.invalid`(RFC 2606 예약 도메인)의 가상 API를 읽는다. 목록은 커서로 페이지를 나누고,
    본문은 자료마다 한 요청이다. 수정 시각을 주지 않는 모드(내용 해시 대체, US1 시나리오 3)와 권한 정보를 주지 않는 모드를 고를 수 있다.
  - `adapters/replay.py`의 `ReplayTransport`: `tests/fixtures/responses/fake/<시나리오>.json`에 저장한 응답을 요청 키(메서드, URL)별로 순서대로
    돌려주고, 받은 요청을 모두 기록한다. 준비되지 않은 요청이 오면 시험을 실패시킨다.
  - 응답 샘플은 QK-FND-001 형식(`_meta` + `body`)을 따른다.
- **Rationale**: 후속 명세(QK-SEC-001, QK-CHK-002, QK-SYN-001)가 실제 자료원 없이 이 어댑터로 시험해야 하므로(FR-007) 테스트 디렉터리가 아니라
  패키지 안(`adapters/`)에 둔다. `fake.invalid`는 실제로 해석되지 않고, 기본 테스트의 외부 연결 차단(QK-FND-001 R-07)과도 충돌하지 않는다.
- **Alternatives considered**: 가짜 어댑터가 메모리 목록을 직접 돌려주기(세션·전송을 거치지 않아 한도·재시도·쓰기 0건을 계약대로 시험할 수 없다).

## R-12 공통 계약 테스트의 재사용

- **Decision**: `tests/contract/source_adapter_contract.py`에 `SourceAdapterContract` 기반 클래스를 둔다. 어댑터마다 `Test<이름>Contract` 하위 클래스를
  만들고 어댑터·전송·설정을 만드는 fixture만 구현한다. 검사 항목은 US1 시나리오 1~5와 FR-002~006이다.
- SC-001 확인: 두 번째 가짜 어댑터(`tests/contract/second_fake.py`)를 별도 커밋으로 추가하고, 그 커밋의 변경 파일이 `tests/` 아래뿐인지
  `git show --stat`으로 PR에 남긴다.
- **Rationale**: 실제 어댑터(QK-ING-002)가 같은 검사를 한 줄 상속으로 받는다. pytest는 `Test`로 시작하지 않는 기반 클래스를 수집하지 않는다(일반 설명).

## R-13 결과·로그의 비밀값

- **Decision**: 자료별 결과와 로그에는 자료원 이름, 원본 식별자, 상태, 재시도 횟수, 실패 유형, HTTP 상태 코드만 담는다. 요청 헤더, 응답 본문,
  URL 질의 문자열은 담지 않는다. 토큰은 QK-FND-001 `SecretValue`로 받아 전송 안에서만 `reveal()`한다.
- SC-007 시험은 수집 결과 JSON과 캡처한 로그를 `scripts/preflight.py`의 `RULES`로 검사한다. preflight는 고치지 않고 `importlib`로 읽는다.

## R-14 명령줄

- **Decision**:
  - `qk-index sources check [--sources 경로] [--json]`: 자료원 설정만 검사한다. 원본 호출 없음. 자료원별 통과 여부와 적용될 수집 범위 요약을 낸다(FR-013).
  - `qk-index run`: 설정 점검(QK-FND-001) 뒤 자료원 설정을 검사하고, 틀리면 원본 호출 없이 종료 코드 1로 멈춘다(FR-011). 통과하면 자료원별로
    "비활성" 또는 "수집 대기"를 보고한다. 실제 수집 연결은 QK-SYN-001이 한다. 활성 자료원이 없으면 지금처럼 "수집할 자료원 없음"을 출력한다.
- 형식은 [contracts/cli.md](contracts/cli.md)에 있다.

## R-15 실행 방식

- **Decision**: 자료원 하나 안의 요청은 순서대로(동시성 없이) 보낸다. 자료원끼리도 순서대로 처리한다.
- **Rationale**: Phase 1 대상은 저장소 하나의 Markdown 문서(수백 개 이하)이고 분당 상한(기본 60회)이 처리 속도를 정한다. 동시성은 한도 계산과
  실패 격리를 복잡하게 만든다. 측정 결과 느리면 QK-ING-002 이후에 다시 본다(C-04).

## R-16 기본값

| 항목 | 기본값 | 근거 |
| --- | --- | --- |
| `max_retries` | 3 | 명세 가정 |
| `initial_backoff_seconds` | 1 | 명세 가정 |
| `max_backoff_seconds` | 60 | 명세 가정 |
| `max_wait_seconds` | 300 | 명세 가정(최대 대기 5분) |
| `max_run_seconds` | 1800 | 명세 가정(실행 1회 30분) |
| `max_requests_per_minute` | 60 | US3 시나리오 예시. GitHub 토큰 시간당 5,000회(`tokens.md` 2절)의 약 72% |
| `max_requests_per_run` | 2000 | (추론) Phase 1 저장소 문서 수백 개 × 목록·본문 요청. GitHub 시간당 한도 안에 다른 작업 몫을 남긴다 |
| `max_content_bytes` | 1,000,000 | (추론) Markdown 문서 기준 넉넉한 값. QK-ING-002 측정으로 조정 |

모두 초기값이며 QK-ING-002 측정 결과로 조정한다.

## 이 계획에서 하지 않는 것

- 실제 HTTP 전송(`urllib` 기반)과 GitHub 어댑터는 QK-ING-002가 만든다. 이 명세는 전송 Protocol과 재생 전송까지다.
- 수집 결과를 저장하거나 이전 버전과 비교하는 일은 QK-SYN-001이다.
