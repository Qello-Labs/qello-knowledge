# Research: QK-EMB-001 임베딩 Provider·캐시·사용량 기록·일일 예산·실행 전 미리 보기

이 문서는 외부 호출 없이 저장소 코드, ADR-002·008, `docs/sdd/research/spike-workers-ai.md`, QK-STO-001 산출물을 읽고 정했다.
Workers AI를 새로 호출하지 않았다(0 Neurons). 확인하지 못한 사실은 "남는 위험"에 적고 구현 단계에서 공식 문서로 확인한다.

## R-01 경계를 두 층으로 나눈다

- **Decision**: `ports/embedder.py`에 두 Protocol을 둔다.
  - `Embedder`: 후속 명세(QK-SYN-001, QK-RET-001)가 부르는 경계. 캐시·예산·사용량 기록까지 끝난 결과를 돌려준다(FR-001).
  - `EmbeddingProvider`: 외부 제공자 한 번 호출. 텍스트 목록을 받아 벡터 목록과 제공자가 알려 준 사용량(없으면 `None`)을 돌려주거나
    도메인 실패 종류로 끝난다. Workers AI REST 어댑터와 가짜 제공자가 이것을 구현한다.
  - 규칙 덩어리(캐시 조회, 중복 제거, 묶음 나누기, 예산 판정, 사용량 기록)는 `embedding/service.py`의 `EmbeddingService(Embedder)` 하나에 둔다.
- **Rationale**: 제공자를 바꿔도 캐시·예산 규칙은 그대로다(C-06). 가짜 제공자로 규칙 전부를 외부 호출 없이 시험할 수 있다(FR-006).
  QK-ING-001이 수집기 계약(`ports/source.py`)과 공통 규칙(`sources/`)을 나눈 방식과 같다.
- **Alternatives considered**: 제공자 어댑터 안에 캐시·예산을 넣기(제공자마다 규칙을 다시 써야 한다), 데코레이터 체인(캐시 → 예산 → 기록 순서가
  호출 쪽 조립에 달려 실수 여지가 생긴다).

## R-02 도메인 타입

- **Decision**: `domain/embedding.py`에 표준 라이브러리 dataclass로 둔다. 경계 검사(`tests/unit/test_boundaries.py`)를 그대로 통과한다.
  - `EmbedPurpose`(`index`, `query`), `EmbedFailureKind`(spec FR-004의 7종: `empty_input`, `input_too_long`, `transient`, `provider_quota`,
    `index_budget`, `auth_config`, `bad_response`. 그 밖에 `secret_blocked`·`no_origin`(FR-005), `no_active_index`)
  - `EmbedInput(text, origin)`: `origin`은 (자료원 이름, 경로)이고 색인용은 반드시 있다. 질의용은 `None`이다. 전송 직전 검사(R-13)에 그대로 넘긴다.
  - `EmbedRequest(inputs, purpose, model_version, run_id, allow_partial)`, `EmbedItem`(벡터 또는 실패, `cached`), `EmbedResult`(항목 목록 + `RunSummary`)
  - `ModelSpec`, `BudgetSettings`, `UsageRecord`, `DailyUsage`, `EmbedPreview`
- **Rationale**: 실패를 예외가 아니라 항목별 값으로 돌려주면 한 텍스트의 실패가 묶음 전체를 막지 않는다(FR-003). 묶음 전체를 멈추는 실패
  (인증 오류, 활성 인덱스 없음)만 `EmbedError` 예외로 던진다.
- **Alternatives considered**: 항목마다 예외(묶음 처리 중 부분 결과를 잃는다).

## R-03 모델 설정은 코드 상수 + 선택 설정

- **Decision**: 모델별 고정값(차원 1,024, 입력 한도 8,192토큰, 요금표 단가 1M 토큰당 1,075 Neurons)은 `domain/embedding.py`의 `MODELS` 표에 둔다.
  어떤 모델을 쓸지는 인덱스 버전의 `embedding_model`이 정한다(QK-STO-001 data-model). 카탈로그 API 값은 읽지 않는다(스파이크 W-03).
- **Rationale**: 차원은 DB 칼럼 타입(`vector(1024)`)과 맞아야 하므로 환경 변수로 바꿀 수 있으면 오히려 위험하다. 모델을 바꾸는 일은
  인덱스 버전을 올리는 일이고(AGENTS.md 3.3), 그때 표에 행을 더한다.
- **Alternatives considered**: 전부 환경 변수(차원·한도를 실수로 바꿀 수 있다), 카탈로그 조회(bge-m3 한도가 60,000으로 틀리게 나온다).

## R-04 예상 Neurons는 UTF-8 바이트로 계산한다

- **Decision**: 예상 토큰 = `ceil(UTF-8 바이트 / 3.5)`, 예상 Neurons = 예상 토큰 × 단가 / 1,000,000. 미리 보기와 예산 예약, 헤더가 없을 때의
  추정 기록에 같은 함수를 쓴다(FR-014, FR-023).
- **Rationale**: 스파이크 3.1·3.2절 측정에서 bge-m3는 한국어 1.87자/토큰, 한국어 1자 평균 약 1.98바이트라 약 3.7바이트/토큰이다.
  1KB당 0.297 Neurons로 측정값(0.30)과 맞는다. 영어는 대략 4바이트/토큰이라 3.5를 쓰면 약 14% 크게 잡는다. 예산 판정에서는 크게 잡는 쪽이 안전하다.
  글자 수보다 바이트 수가 언어 사이 편차가 작다. 로컬 토크나이저를 두지 않아 런타임 의존성이 늘지 않는다(pyproject `dependencies = []`).
- **Alternatives considered**: 로컬 토크나이저(`tokenizers` 등, 의존성과 모델 파일 추가, Workers 번들에 못 싣는다), 글자 수 기준(한국어·영어 차이가 크다).
- **남는 위험**: 코드·영어가 많은 실제 문서에서 ±20%(SC-005)를 지키는지는 사람 승인 뒤 실측(`-m external`)으로 확인한다. 벗어나면 3.5를 고치고 근거를 이 절에 남긴다.

## R-05 입력 한도: 미리 걸러 단독 요청으로 보내고, 400(3030)이면 쪼갠다

- **Decision**:
  1. `truncate_inputs`를 보내지 않는다(FR-003).
  2. 예상 토큰이 한도의 75%(6,144)를 넘는 텍스트는 다른 텍스트와 묶지 않고 단독 요청으로 보낸다. 미리 보기는 예상 토큰이 한도를 넘는 텍스트를
     "입력 한도 초과 예상"으로 표시한다(US5 AS4).
  3. 여러 텍스트 요청이 400(코드 3030)으로 끝나면 반으로 나눠 다시 보내 원인 텍스트를 찾는다. 단독 요청의 3030은 `input_too_long`으로 끝낸다.
- **Rationale**: 제공자는 요청 하나에 텍스트 하나라도 한도를 넘으면 요청 전체를 400으로 거부한다(스파이크 3.1). 미리 걸러 두면 쪼개기는 드물다.
  400 응답에는 `cf-ai-neurons` 헤더가 없었다(스파이크 3.2). 사용량 0, `measured=false`로 기록한다.
- **Alternatives considered**: 모든 텍스트를 단독 요청(호출 수가 수십 배, 분당 3,000회 한도에 가까워진다), 실패한 묶음 전체를 실패 처리(FR-003 위반).
- **남는 위험**: 400 응답이 과금되지 않는다는 근거는 헤더가 없었다는 것뿐이다. 하루 합계가 제공자 대시보드와 어긋나면 이 가정을 다시 본다.

## R-06 묶음 크기

- **Decision**: 요청 하나에 텍스트 최대 32개, 예상 토큰 합 최대 32,768로 나눈다. 둘 다 `EmbeddingService` 생성 인자로 두고 기본값만 정한다.
- **Rationale**: 스파이크는 12개 묶음까지만 보냈다. 예산 예약 단위가 요청 하나이므로(R-08), 요청이 작을수록 예약과 실제의 차이(FR-021의 "묶음 하나의 예상량")가
  작아진다. 32,768토큰이면 예상 약 35 Neurons로 색인 예산 5,000의 1% 미만이다.
- **남는 위험**: bge-m3 입력 스키마의 배열 최대 길이를 공식 문서에서 확인하지 않았다. 구현 시 모델 문서의 입력 스키마를 확인하고 32보다 작으면 줄인다.

## R-07 캐시 키와 해시 규칙

- **Decision**: 입력 해시 = `"sha256:" + SHA-256(UTF-8 텍스트).hex()`. 텍스트는 외부로 보내는 문자열 그대로이고 정규화하지 않는다(FR-009).
  캐시 키는 QK-STO-001의 `(input_hash, model_version)`이고 `model_version`은 인덱스 버전의 `embedding_model` 값이다. 해시 규칙 이름 `emb-hash-v1`을
  상수로 두고, 바꾸면 인덱스 버전을 올린다(C-07).
- **Rationale**: 저장소가 이미 `Store.find_embedding`·`put_embedding`과 고유 제약을 제공한다(QK-STO-001 US5). 정규화(공백 정리 등)는 청커의 일이고,
  여기서 정규화하면 같은 해시에 다른 입력이 들어가는 사고가 생긴다.
- **결정 사항**: 캐시 조회는 묶음 단위 한 번이 좋지만 `Store`에는 단건 조회만 있다. 이번에 `Store.find_embeddings(refs) -> dict`를 추가한다
  (QK-STO-001 계약에 연산 하나 추가. 기존 연산은 바꾸지 않는다).
- **Alternatives considered**: 해시에 모델 버전을 섞기(저장소 키와 중복), 질의 벡터도 캐시(spec FR-012가 제외했다. 질의 해시만으로도 질의를 추측할 수 있어 ADR-016과 얽힌다).

## R-08 예산 판정과 사용량 기록은 DB 함수로, 예약 → 정산 2단계

- **Decision**: 마이그레이션 `0003_embedding_usage.sql`로 사용량 테이블과 SQL 함수를 만든다(data-model.md).
  - 색인용 요청 직전: `qk.embedding_reserve(run_id, model_version, estimated, index_budget)`가 그날(UTC)의 advisory lock을 잡고
    "정산된 색인 사용량 + 정산 전 예약의 예상량 + 이번 예상량 ≤ 색인 예산"이면 예약 행을 넣고 예약 id를 돌려준다. 넘으면 거부한다(FR-018).
  - 요청 직후: `qk.embedding_settle(reservation_id, neurons, measured, outcome, ...)`가 예약 행을 실제 값으로 바꾼다.
  - 질의용: 예약 없이 `qk.embedding_record(...)`로 한 번에 기록한다(FR-019). 예비분을 넘으면 결과에 경고를 싣는다.
  - 조회: `qk.embedding_usage_today(index_budget, query_reserve)`가 하루 합계·용도별 합계·남은 색인 예산을 `jsonb`로 돌려준다(FR-016).
- **Rationale**: 동시에 도는 색인 실행이 같은 합계를 보고 판정해야 한다(FR-021). 잠금과 합산을 함수 하나의 트랜잭션에 두면 경합이 없고, 넘을 수 있는
  양은 "예약 예상량과 실제의 차이"로 묶인다. 질의 경로(Workers)는 TCP 드라이버가 없어 QK-STO-001 R-06처럼 같은 함수를 HTTP RPC로 부른다.
  조건과 계산이 DB 한 곳에 있으면 두 경로가 같은 규칙을 쓴다(FR-007, FR-016).
- **정산되지 않은 예약**: 프로세스가 예약 뒤 죽으면 예약 행이 남는다. 실제로 호출이 나갔을 수 있으므로 예상량으로 계속 센다(보수적). 다음 날에는 영향이 없다.
- **사용량 기록 실패**: 예약·정산 함수 호출이 실패하면 색인 실행은 다음 외부 호출을 하지 않고 멈춘다(spec Edge Cases). 이미 받은 벡터는 저장하고 돌려준다.
- **Alternatives considered**: 애플리케이션에서 합계 조회 후 판정(동시 실행이 둘 다 통과한다), 행 잠금용 일별 카운터 테이블(예약 정산이 두 테이블에 걸쳐 복잡하다),
  프로세스 메모리 집계(실행 사이·질의 경로와 공유되지 않는다).

## R-09 제공자 응답 분류와 재시도

- **Decision**: Workers AI REST(`POST /client/v4/accounts/{account}/ai/run/@cf/baai/bge-m3`, 본문 `{"text": [...]}`)의 결과를 다음처럼 바꾼다.

| 제공자 응답 | 도메인 결과 | 재시도 |
| --- | --- | --- |
| 200, 벡터 개수·차원 일치 | 성공. `cf-ai-neurons` 헤더가 있으면 측정값, 없으면 추정값(R-04) | — |
| 200, 개수·차원 불일치 | `bad_response` | 안 함 |
| 400 + 코드 3030 | `input_too_long`(R-05로 쪼갠 뒤) | 안 함 |
| 429 + 코드 3036 | `provider_quota`. 그날 남은 색인을 멈춘다(FR-020) | 안 함 |
| 429(그 밖), 5xx, 연결 실패·시간 초과 | `transient` | `RetryPolicy`(최대 3회, 지수 대기, `Retry-After` 존중) |
| 401, 403 | `auth_config`(묶음 전체 `EmbedError`) | 안 함 |
| 그 밖의 4xx | `bad_response` | 안 함 |

- **Rationale**: 재시도 대기 계산은 QK-ING-001의 `sources/retry.py` `next_delay`와 `domain/source_config.RetryPolicy`를 재사용한다. HTTP는 표준 라이브러리
  `urllib.request`로 보낸다(런타임 의존성 0 유지). 토큰은 `SecretValue.reveal()`로 어댑터 안에서만 꺼낸다(QK-FND-001).
- **남는 위험**: 3036 이외의 429(분당 호출 한도)와 3036을 응답 본문 `errors[].code`로 구분한다는 것은 스파이크가 인용한 문서 근거([C1][C2])이고 재현하지 않았다.
  계약 테스트는 저장된 응답 사례로 한다.

## R-10 Workers 질의 경로는 경계와 SQL 함수까지만 이번에 만든다

- **Decision**: 이번 작업은 (1) `Embedder`·`EmbeddingProvider` 계약, (2) REST 제공자(색인 경로), (3) 가짜 제공자, (4) 예산·기록 SQL 함수,
  (5) 어떤 제공자에도 돌릴 수 있는 제공자 계약 테스트 묶음을 만든다. Workers `env.AI` 바인딩 제공자와 HTTP RPC 사용량 기록 어댑터는 Workers 질의 경로를
  처음 만드는 QK-RET-001에서 이 계약 테스트를 통과시키는 조건으로 만든다.
- **Rationale**: Workers 런타임의 실제 실행 검증은 QK-BOT-001이 맡기로 돼 있고(`query/worker.py` 주석), HTTP RPC 계층도 아직 정하지 않았다(QK-STO-001 R-06 남는 위험).
  지금 바인딩 어댑터를 쓰면 검증할 수 없는 코드가 생긴다. 규칙을 SQL 함수와 `EmbeddingService`에 두었으므로 나중에 붙이는 어댑터는 호출만 한다.
- **남는 위험**: `env.AI.run`이 사용량(Neurons)을 돌려주는지 확인하지 않았다. 돌려주지 않으면 질의 사용량은 추정값(`measured=false`)으로 기록된다.
  질의 임베딩은 하루 1 Neurons 미만이라(ADR-002) 예산 판정에 주는 영향은 작다. QK-RET-001 명세에 이 확인을 넘긴다.
- **Alternatives considered**: Workers에서도 REST 호출(운영 Workers에 Cloudflare REST 토큰을 두게 된다. ADR-008이 피한 구조).

## R-11 설정 항목

- **Decision**: `config/registry.py`에 세 항목을 더한다. 모두 비밀 아님, 기본값 있음, 진입점은 색인·질의 둘 다.
  - `QK_EMBED_DAILY_ALLOWANCE`(기본 10000), `QK_EMBED_INDEX_BUDGET`(기본 5000), `QK_EMBED_QUERY_RESERVE`(기본 3000). 양의 정수.
  - 설정 검사(`qk-index check`)는 색인 예산 + 질의응답 예비분 ≤ 하루 무료 할당이 아니면 실패한다(FR-017, US4 AS6). 이 교차 검사는 `config/check.py`의 보고에 넣는다.
- **Rationale**: QK-FND-001 설정 로딩·검사 규칙을 그대로 쓴다. Workers에서는 바인딩 환경값으로 같은 이름을 받는다.

## R-12 미리 보기와 CLI

- **Decision**: 미리 보기는 `EmbeddingService.preview(request) -> EmbedPreview` 함수로 둔다. 외부 호출은 0건이고 캐시 조회(`find_embeddings`)와
  하루 사용량 조회(`qk.embedding_usage_today`)만 한다(FR-022). 색인 실행(`embed`)은 첫 외부 호출 전에 같은 미리 보기를 계산하고, `over_budget`이면
  `allow_partial=False`(기본)일 때 외부 호출 없이 전 항목을 `index_budget`으로 돌려준다(FR-024).
  CLI는 `qk-index usage`(오늘 사용량·남은 예산 출력, `--json`)와 `qk-index usage prune`(90일 정리) 두 명령만 이번에 더한다.
  어떤 텍스트를 미리 볼지 정하는 `qk-index run --preview`는 청크를 만드는 QK-SYN-001이 이 함수를 불러 만든다.
- **Rationale**: 텍스트 묶음은 청커 다음 단계에서만 생긴다. 이번에 입력 파일 형식을 따로 만들면 QK-SYN-001과 겹친다.

## R-13 사용량 기록 보관 90일

- **Decision**: `qk.embedding_usage_prune(retention_days int DEFAULT 90)`가 기준일보다 오래된 날짜를 날짜 단위로 통째로 골라, 그 날의 합계를
  `qk.embedding_usage_daily`에 넣고(같은 키면 덮어씀) 호출별 행을 지운다. 한 트랜잭션이다(FR-025).
- **Rationale**: 날짜 단위로 처리하면 덮어쓰기가 멱등이다. 일부만 지운 날이 생기지 않는다. 일 합계 행은 하루·용도·모델당 하나라 작다.
- **실행 주체**: 정리는 `qk-index usage prune`으로 하고, 주기 실행은 QK-SYN-001 스케줄러에 붙인다. 이 작업은 명령과 함수만 만든다.

## R-14 시험 방법

- **Decision**:
  - 단위(`tests/unit/embedding/`): 가짜 제공자 + 메모리 저장소·메모리 사용량 장부로 US1~5 규칙 전부. 시각은 주입한다(하루 경계 시험).
  - 계약(`tests/contract/embedding_provider_contract.py`): 제공자 계약 묶음. 가짜 제공자와 "저장된 응답을 돌려주는 REST 제공자"(QK-ING-001 `adapters/replay.py` 방식)에 돌린다.
    응답 사례는 합성 값으로 만든다. 실제 응답을 저장하지 않는다(토큰·계정 ID가 섞일 수 있다).
  - 로컬 DB(`tests/localdb/embedding/`): 예약·정산·동시 예약(스레드 2개)·질의 기록·하루 경계·정리 멱등.
  - 외부(`-m external`, 기본 제외): 실제 bge-m3로 텍스트 몇 개를 임베딩해 측정값과 예상값 차이를 기록(SC-005). 실행 전 예상 사용량(수 Neurons 이하)을 적고 사람 승인 뒤 돌린다.
- **Rationale**: AGENTS.md 7절(외부 API 테스트는 기본 검증 밖), 3.5절(실행 전 사용량 적기).

## R-13 비밀값 전송 직전 검사 연결

- **Decision**: `EmbeddingService`는 생성할 때 QK-SEC-001의 `SecurityPolicy`(`security.policy.load_policy`로 읽은 예외 목록)를 받는다.
  캐시 조회와 중복 제거 뒤, 묶음을 나누기 전에 보낼 텍스트마다 `security.send_gate.check_outgoing([OutgoingPiece(text, origin)], policy)`를 부른다.
  걸린 항목은 `secret_blocked`로 끝내고 묶음에 넣지 않는다. 그래서 제공자로 가는 요청에는 검사를 통과한 텍스트만 담긴다.
  색인용인데 `origin`이 없으면 검사 전에 `no_origin`으로 끝낸다.
- **Rationale**: QK-SEC-001이 `screened_by` 같은 통과 표시를 만들지 않고, 대신 보내기 직전 검사 함수를 두고 "실제 호출에 잇는 일은 QK-EMB-001이 한다"고 정했다
  (`send_gate.py`, QK-SEC-001 FR-013). 표시를 믿는 방식보다 보내기 직전에 같은 규칙으로 다시 보는 쪽이 AGENTS.md 3.1을 직접 지킨다.
  항목 단위로 검사하면 한 텍스트가 걸려도 같은 묶음의 다른 텍스트는 보낼 수 있고, 걸린 텍스트가 든 요청은 만들어지지 않는다.
- **Alternatives considered**: 묶음 단위로 한 번 검사하고 걸리면 묶음 전체를 막기(무관한 텍스트까지 실패한다), 통과 표시(`screened_by`)를 새로 만들어
  QK-SEC-001에 요구하기(이미 병합된 구현과 계약을 바꿔야 하고, 표시가 붙은 뒤 텍스트가 바뀌면 지키지 못한다).
- 로그·`RunSummary`에는 항목 번호·규칙 이름·줄 번호와 `secret_blocked` 건수만 남긴다. 텍스트와 맞은 문자열은 남기지 않는다(QK-SEC-001 계약).
