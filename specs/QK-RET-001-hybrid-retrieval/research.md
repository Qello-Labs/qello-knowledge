# Research: QK-RET-001 하이브리드 검색·RRF·문맥 확장·토큰 예산·키워드 검색 텍스트

이 문서는 저장소 코드, QK-STO-001·QK-EMB-001·QK-CHK-002·QK-SYN-001 산출물, ADR-007·008·009, 아래 R-03의 로컬 실측으로 정했다.
실측은 로컬 PostgreSQL 컨테이너 안의 일회용 데이터베이스(`qk_scratch_ret001`, 측정 뒤 지움)에서 합성 문장 8개로 했다. 외부 API 호출 0건, 0 Neurons다.
R-08은 대상 저장소 사본(GitHub 읽기)과 Hugging Face 토크나이저 파일 하나(GET만, 문서 데이터 전송 없음, 2026-10-22 사용자 허용)로 쟀다. Workers AI 호출 0건이다.

## R-01 코드 위치: 순수 `retrieval/` 패키지 + 저장소 경계 확장

- **Decision**: 검색 흐름은 새 패키지 `src/qello_knowledge/retrieval/`에 둔다. 이 패키지는 `domain`·`ports`·`embedding`(예상 토큰 계산)만 가져온다.
  경계 시험(`tests/unit/test_boundaries.py`)의 제한 목록에 `retrieval`을 더한다. 저장소 쪽은 새 Protocol `RetrievalStore`(`ports/retrieval.py`)로 받고,
  `PostgresStore`가 기존 `search_vector`와 새 `search_keyword_terms`·`chunk_context`로 이를 만족한다. 임베딩은 QK-EMB-001 `Embedder`로 받는다.
- **Rationale**: 같은 검색 함수를 로컬 서버·확인 명령·평가·Workers가 부른다(spec FR-027). Workers(Pyodide)에는 `psycopg`와 `markdown-it-py`가 없다
  (QK-FND-001 R-03, QK-CHK-002 R-01). 그래서 검색 흐름은 표준 라이브러리와 경계 타입만 써야 한다. QK-STO-001 `Store` Protocol에 메서드를 더하면 동기화와
  가짜 저장소 전부가 넓어지므로, 검색이 쓰는 세 연산만 가진 좁은 Protocol을 따로 둔다(QK-SYN-001 R-01 `SyncStore`와 같은 방식).
- **Alternatives considered**: `query/` 안에 두기(HTTP 처리와 검색 규칙이 섞인다), `Store`에 `chunk_context` 추가(시험 가짜 구현 전부가 바뀐다).

## R-02 RRF와 동점 처리

- **Decision**: `fusion.fuse(vector_hits, keyword_hits, k)`는 청크 식별자별로 `Σ 1/(k + rank)`를 더한다. 순위는 각 검색이 돌려준 1부터 시작하는 순위
  (`SearchHit.rank`)다. 비교는 `fractions.Fraction`으로 정확하게 하고, 결과에는 `float`으로 싣는다. 정렬 키는 `(-score, vector_rank or ∞, keyword_rank or ∞, chunk_id)`다.
  수학적으로 같은 합은 언제나 동점이 되어 동점 규칙이 적용된다(독립 검토 L3). 한 검색 결과에 같은 청크가 두 번 나오면 그 검색의 `StoreError`로 본다(R-14).
- **Rationale**: spec FR-003·FR-004. 순위만 쓰므로 거리와 키워드 점수의 척도를 맞추지 않는다. `k=60`은 Cormack 외(2009)의 값이다.
- **Alternatives considered**: 점수 정규화 후 가중합(척도가 질의마다 달라 평가 없이는 가중치를 정할 수 없다), 가중 RRF(가중치 근거가 없다. QK-EVL-001 뒤 다시 본다),
  `float` 비교(같은 합이 미세하게 달라 동점 규칙을 건너뛸 수 있다).


## R-03 질의 쪽 키워드 규칙과 새 키워드 함수 (실측)

- **실측 1**(2026-10-22, 일회용 DB, PGroonga 3.2.5, 실제 색인 설정 `TokenBigramSplitSymbol`, `enable_seqscan = off`, 합성 문장):

| 검색어 | 결과 |
| --- | --- |
| `pgroonga_query_escape('결제 취소 API 경로가 뭐야?')` 그대로 | 0건. 낱말 전부가 맞아야 한다(AND) |
| `결제 OR 취소 OR API OR 경로가 OR 뭐야?` | "결제 취소 API 경로는…" 청크를 찾음 |
| `pgroonga_query_escape('a OR b')` | `a OR b` 그대로. **`OR`는 이스케이프되지 않는다** |
| `pgroonga_query_escape('"x" (y) -z')` | `\"x\" \(y\) \-z`. 따옴표·괄호·`-` 등은 이스케이프된다 |
| 소문자 `or` 한 낱말 | 글자 `OR`와 `or`가 든 청크를 찾는다. 연산자가 아니다 |
| `경로가` / `경로` (본문은 "경로는") | 0건 / 찾음. 조사가 붙은 낱말은 맞지 않는다 |

- **실측 2**(독립 검토 H1·H2 재현, 같은 조건):
  - `pgroonga_score`는 **맞은 낱말 가짓수가 아니라 나온 횟수**다. `결제 OR 취소 OR API OR 경로`에서 "결제"만 6번 나온 청크가 6점, 네 낱말이 다 맞은 청크가 4점이었다.
  - **일치 확장**(`pgroonga.match_escalation_threshold` 기본 0): 정확히 맞는 결과가 0건일 때만 부분 일치로 넓힌다. 다른 청크에 `retry`가 없으면 `retry`가
    `retryPayment`를 찾고, `retry`가 든 청크가 있거나 `결제 OR retry`처럼 다른 낱말이 맞으면 찾지 못했다. 독립 검토는 지운 행이 VACUUM 전이면 결과가 달라지는 것도 관찰했다.
    값을 `-1`로 두면 확장이 꺼져 `retry`는 `retryPayment`를 찾지 않고, 원형 `retryPayment`와 한국어 낱말은 그대로 찾았다.
  - 낱말 배열을 `unnest`해 낱말마다 `search_text &@~ pgroonga_query_escape(낱말)`로 색인 조회하고 청크별로 서로 다른 낱말 수를 세면, 같은 입력에서 두 번 모두 같은 순서였다.
    이 결합 안의 `pgroonga_score`는 0이 나오는 행이 있어 점수로 쓰지 않는다.
- **Decision 1 (질의 쪽 규칙 `kw-query-v1`)**: 질문을 공백으로 나눈 낱말마다 (1) 앞뒤의 문장 부호·따옴표·괄호·백틱(`` ? ! . , ; : ' " ` ( ) [ ] < > `` 와 한글 따옴표)를
  떼고(독립 검토 M4), (2) 한글로 끝나는 낱말이면 끝의 조사를 긴 것부터 하나만 떼되 남는 부분이 2글자 이상일 때만 뗀다
  (목록: `에서 으로 에게 까지 부터 처럼 보다 하고 이랑 은 는 이 가 을 를 의 에 로 와 과 도 만`. 예: "경로가" → "경로", "집에서"는 남는 부분이 1글자라 그대로),
  (3) 대문자 `OR`는 소문자 `or`로 바꾸고(정규화로 같은 글자를 찾는다, 실측 1), (4) 1글자 한글 낱말과 질문 어미 목록(`뭐야 뭔가요 무엇 어디 어떻게 알려줘 있나요`)과 빈 낱말을 빼고,
  (5) 대소문자를 무시한 중복을 없애고 64자 넘는 낱말을 뺀 뒤 앞에서부터 최대 16개를 낱말 배열로 만든다. 결정 2 (b)의 점수 질의가 낱말을 ` OR `로 잇기 때문에 (3)이 필요하다.
  재검토 실측: `커피 OR OR OR 결제`는 "결제" 청크만 돌려줘 "커피"·"OR" 청크가 점수를 받지 못했다(독립 재검토 N1).
  비교용 규칙 `kw-query-raw`는 질문 전체를 낱말 하나로 두고(AND 검색) 대문자 `OR`만 소문자로 바꾼다. 새 함수로 부르므로 일치 확장이 꺼진 조건이다. SC-005의 "적용 전 비율"은 이 조건의 값으로 기록한다.
- **Decision 2 (새 함수 `qk.search_keyword_terms`, 0005, 사람 결정 2026-10-22)**: 입력은 낱말 배열, 상위 N, 필터다. 함수에 `SET pgroonga.match_escalation_threshold = -1`,
  `SET enable_seqscan = off`를 건다. (a) 낱말마다 색인 조회해 청크별 서로 다른 맞은 낱말 수 `matched`를 세고, (b) 같은 낱말들을 ` OR `로 이은 질의 한 번으로 `pgroonga_score`를 구해
  `score`로 쓰며((a)에서 찾았지만 (b)에 없는 행의 `score`는 0), (c) `matched DESC, score DESC, chunk_id` 순으로 상위 N을 돌려준다. 노출 조건은 `qk.is_visible`·`qk.kind_matches` 그대로다. 반환 형식은 `qk.search_keyword`와 같고
  항목에 `matched_terms`가 더해진다. 낱말 배열이 비면 `active_index_version`과 빈 결과를 돌려준다(키워드 전용에서도 활성 인덱스 없음을 알 수 있게, 독립 검토 M3).
  기존 `qk.search_keyword`는 바꾸지 않는다(QK-STO-001 계약 유지). 검색은 새 함수만 쓴다.
- **Rationale**: spec FR-017의 "낱말이 많이 맞을수록 순위가 높다"를 점수 해석 없이 정렬 키로 보장한다. 일치 확장을 끄면 결과가 다른 청크·VACUUM 상태와 무관해져
  SC-004·SC-005와 ADR-010 비교가 규칙 차이만 잰다. 낱말 배열을 함수 안에서 낱말마다 이스케이프하므로 연산자 주입이 없다.
- **Alternatives considered**: `pgroonga_score` 횟수 점수를 받아들이고 spec 재승인(한 낱말이 많이 나오는 청크가 위로 온다, 사람 결정으로 제외), 확장을 허용하고 조건만 기록
  (결과가 색인 내용에 따라 흔들린다, 사람 결정으로 제외), 기존 함수에 설정 추가(QK-STO-001 계약이 바뀐다), 형태소 분석기(새 의존성, Workers에 못 넣는다).
- **남는 위험**: 조사 목록은 휴리스틱이다. 명사 자체가 조사 글자로 끝나는 3글자 이상 낱말("전문가" → "전문")을 잘못 뗄 수 있다. bigram이라 남은 부분도 대부분 맞는다.
  낱말 16개면 색인 조회가 16번이라 SC-006에서 시간을 확인한다.


## R-04 색인 쪽 규칙과 청킹 규칙 버전: 기준선 해시를 바꾸지 않는다

- **실측**(R-03과 같은 조건, 일치 확장을 끈 새 함수 기준): `retry`는 `retryPayment`를 찾지 못한다. 본문에 `retry payment`를 덧붙인 청크는 찾았다.
  일치 확장이 켜진 기존 함수에서는 다른 청크에 `retry`가 없을 때만 찾는다(R-03 실측 2). ADR-007의 "찾지 못했다"도 이 조건에 따른 관찰이다.
  `payment`·`status`는 `payment_status`를 찾았다. `TokenBigramSplitSymbol`이 `_`·`-`·`/`를 기호로 쪼개기 때문이다.
- **Decision**: 색인 쪽 규칙은 청커 설정 `ChunkingSettings.keyword_text_rule`(기본 `kw-index-baseline-v1`)로 고른다. 후보 `kw-index-idsplit-v1`은
  `search_text` 끝에 빈 줄과, 본문·검색 헤더의 camelCase·PascalCase·약어 경계(`HTTPClient` → `http client`)와 숫자 경계로 나눈 소문자 낱말 목록(중복 없이 원문 순서)을 덧붙인다.
  snake_case·kebab-case·경로는 토크나이저가 이미 나누므로 따로 덧붙이지 않는다. 원형은 그대로 둔다. `embedding_text`는 바꾸지 않는다(spec FR-019).
  `chunking/version.py`는 규칙이 기준선이 아닐 때만 해시 재료에 `"keyword_text_rule": <규칙>`을 넣는다. 기준선 재료는 지금과 글자 하나 다르지 않다.
  그래서 기준선 `chk-md-20d966f730bb`과 운영 인덱스 버전 `iv-4c0bc4fcc642`가 그대로다(spec SC-010). 메타데이터 스키마 버전 `meta-v1`도 그대로다.
- **Rationale**: spec FR-018~020. 재료 키를 조건부로 넣는 것이 기존 값을 지키는 가장 작은 방법이다. 시험은 `chunking_version(ChunkingSettings())`이
  상수와 같은지 본다.
- **Alternatives considered**: `SEARCH_TEXT_FORMAT`을 2로 올리기(기준선 해시가 바뀐다), 토크나이저를 `TokenBigramSplitSymbolAlpha`로 바꾸기(인덱스 재생성 마이그레이션이 운영에 닿고,
  QK-STO-001 R-03이 정밀도 문제로 미뤘다. ADR-010 세 번째 후보로 R-11에 남긴다).

## R-05 규칙 식별자 기록: 코드의 대응표

- **Decision**: 새 열이나 마이그레이션 없이 `domain/keyword_rules.py`에 대응표 `INDEX_KEYWORD_RULES: {인덱스 버전 식별자: 규칙 식별자}`를 둔다. 값은 현재 기본 청커 설정과
  bge-m3로 계산한 두 항목(기준선 `iv-4c0bc4fcc642`, 식별자 분해는 구현 때 계산)이다. 단위 시험이 `index_version_id(…, chunking_version(ChunkingSettings(keyword_text_rule=r)))`로
  표가 맞는지 확인한다. 표에 없는 버전은 `unknown`으로 보인다. 검색 요약(spec FR-024)은 인덱스 버전과 이 표로 푼 규칙을 함께 담는다.
- **Rationale**: spec FR-020. 청킹 규칙 버전은 해시라 거꾸로 풀 수 없다. 해시 계산(`chunking/version.py`)은 `markdown-it-py` 버전을 가져와 Workers 번들에 못 넣으므로
  계산 결과를 상수로 둔다. 열을 더하면 동기화가 버전 행을 만들 때 규칙을 넘겨야 하고 QK-SYN-001 코드가 넓어진다.
- **Alternatives considered**: `qk.index_version`에 열 추가(마이그레이션, 동기화 변경, 기존 행 채우기), 검색 때마다 해시 계산(Workers에서 못 한다).
- **남는 위험**: 청커 설정(목표·상한)을 바꾸면 표가 낡는다. 그때는 시험이 실패하므로 같은 변경에서 표를 고친다.

## R-06 주변 청크 일괄 조회: 새 함수 `qk.chunk_context`

- **Decision**: 마이그레이션 `0005_retrieval.sql`에 `qk.chunk_context(center_ids bigint[], before int, after int) RETURNS jsonb`를 더한다(R-03의 `qk.search_keyword_terms`와 같은 파일).
  중심 청크 식별자 배열(최대 20개, 넘으면 앞 20개)과 앞뒤 개수(각 0~3)를 받아, 활성 인덱스 버전과 노출 조건(`qk.is_visible`)을 통과한 중심 청크마다
  `{center, section_first, before[], after[]}`를 돌려준다. 항목마다 청크 식별자, 순서 번호(`ordinal`), 제목 경로, 본문, 출처 정보(`qk.hit_json`과 같은 키)가 있다.
  `section_first`는 같은 자료·같은 인덱스 버전에서 순서 번호가 중심보다 작고 제목 경로가 다른 마지막 청크 바로 다음 청크다. 그것이 중심 자신이면 `null`이다
  (spec FR-014 정의). 순서 번호는 청커가 0부터 빈틈없이 매긴다(`len(drafts)`). 반환 최상위에는 `active_index_version`이 있다. 노출 조건을 통과하지 못한 중심 청크는
  결과에 없다(spec FR-012 다시 확인). 기존 `qk.chunk_neighbors`·`qk.hit_json`은 바꾸지 않는다.
- **Rationale**: spec FR-012·FR-014·FR-026. 질의 하나에서 주변 조회를 한 번으로 끝낸다. 지금 함수는 중심 하나씩이고 순서 번호가 없으며 상위 절을 접두마다 목록으로 준다
  (spec 독립 검토 M1). 노출 조건은 기존 함수와 같은 `qk.is_visible`을 쓴다(spec FR-007).
- **Alternatives considered**: 기존 함수를 고치기(QK-STO-001 계약 변경), 파이썬에서 중심마다 부르기(외부 호출 상한을 넘는다).


## R-07 질의용 임베딩과 재시도

- **Decision**: 질의 경로는 QK-EMB-001 `EmbeddingService`를 `RetryPolicy(max_retries=1)`과 짧은 대기(`min(Retry-After 또는 0.5초, 2초)`)로 조립한다.
  요청은 `EmbedPurpose.QUERY`, 입력 1개, `run_id`는 질의마다 새 UUID다. 전송 직전 검사는 출처 없이 부른다(QK-EMB-001 Clarifications).
  결과 항목이 `secret_blocked`면 "외부 전송 차단", `transient`·`provider_quota`·`input_too_long`·`bad_response`면 "질의 임베딩 실패"로 본다.
  사용량 기록은 시도마다 한 번 쓰인다(`embedding/service.py` `_account`, 독립 검토 N1). 그래서 최대 외부 호출은 임베딩 2 + 기록 2 + 저장소 3 = 7이다(spec FR-026).
- **Rationale**: QK-EMB-001 동작은 바꾸지 않는다(TASK.md 제외 범위). 대기 상한 2초는 Discord 지연 응답(QK-BOT-001) 안에서 검색 전체가 끝나게 하려는 초기값이다.
- **Alternatives considered**: 재시도 0회(사람 결정으로 1회), 질의 경로 전용 제공자 호출(사용량 기록 규칙이 갈린다).

## R-08 토큰 예산 측정: 예산 2,000 유지

- **무엇을 재나**: (1) Phase 1 대상 문서를 기준선 청커로 나눈 청크의 예상 토큰 분포와 예상 2,000 초과 청크 수(spec N4), (2) 생성 모델 토크나이저 기준
  "실제 ÷ 예상" 비율(청크 단위 중앙값·p95·최대, spec M5).
- **방법**: `specs/QK-RET-001-hybrid-retrieval/measurement/measure_context.py`(원문을 출력하지 않는 집계 스크립트, QK-CHK-002 measure_inputs.py와 같은 방식).
  입력은 대상 저장소 로컬 사본의 고정 커밋(QK-CHK-002 R-02와 같은 `6aeccd03…` 또는 그 뒤 커밋)과 `Qwen/Qwen3-30B-A3B` 토크나이저 파일 하나(`tokenizer.json`,
  리비전과 SHA-256을 기록). `uv run --with tokenizers==0.23.3`으로 돌리고 프로젝트 의존성에는 넣지 않는다. Workers AI 호출 0건이다.
- **판정 기준**(측정 전에 정함): 비율 p95가 1.5를 넘으면 예산 초기값을 `floor(3,000 × 2/3 ÷ p95)`로 낮추는 안을 사람에게 올린다. 예상 2,000 초과 청크가
  전체의 2%를 넘으면 예산 또는 청크 목표 크기를 다시 정하는 안을 올린다.
- **측정 조건**(2026-10-22): 대상 저장소 `dnd-side-project/dnd-15th-2-backend` 커밋 `6aeccd039b825dcd7a2b6c046a34ef72089a1f78`(그날 `main` 머리, QK-CHK-002 R-02와 같은 커밋),
  `config/sources.toml`의 `dnd-backend-docs` 포함·제외 패턴, 보안 필터에 막힌 계획 문서 1개 제외. 기준선 청커(`chk-md-20d966f730bb`)로 나눈 청크 본문(검색 헤더 제외,
  Context에 들어가는 텍스트). 토크나이저는 `tokenizers` 0.23.3 + `Qwen/Qwen3-30B-A3B` `tokenizer.json`(리비전 `ad44e777bcd18fa416d9da3bd8f70d33ebb85d39`,
  SHA-256 `aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4`, 특수 토큰 제외 `encode().ids` 길이). ADR-009 생성 모델 `qwen3-30b-a3b-fp8`의 원 모델 토크나이저다.
- **결과**:

| 항목 | 값 |
| --- | --- |
| 문서, 청크 | 79개(모두 청킹 성공), 1,291개 |
| 청크 예상 토큰 | 중앙값 182, p95 464, 최대 2,744. 예상 2,000 초과 3개(0.23%) |
| 청크 실제 토큰 | 중앙값 180, p95 471, 최대 2,814. 실제 2,000 초과 3개 |
| 실제 ÷ 예상 | 청크별 중앙값 0.976, p95 1.286, 최대 1.875. 전체 합 비율 0.968 |

- **Decision**: 판정 기준을 넘지 않아 예산 초기값 2,000과 바이트당 토큰 3.5를 유지한다. 예산 2,000을 예상 기준으로 꽉 채운 Context는 p95 비율에서 실제 약 2,572토큰이다.
  프롬프트 몫 1,000을 더한 입력 약 3,572 × 4,625/1M ≈ 16.5, 출력 1,200 ≈ 36.6으로 질의당 약 53 Neurons, 하루 50건 약 2,660으로 질의응답 예비분 3,000 안이다.
  Context에 들어갈 수 없는 청크(예상 2,000 초과)는 3개다.
- **재현**: `specs/QK-RET-001-hybrid-retrieval/measurement/measure_context.py`. 실행 명령은 그 파일 머리말에 있다. 원문·경로는 출력하지 않는다.
- **남는 위험**: 전체 합 비율은 1보다 작지만 청크별 최대 1.875다. 표·코드가 몰린 질문에서는 실제 입력이 예산보다 커질 수 있다. QK-GEN-001이 실제 사용 토큰을 기록하면 다시 본다.

## R-09 평가용 색인 준비: `qk-dev eval-index prepare`

- **확인한 제약**(독립 검토 H3, 코드 확인): (1) `sources/scope_review.py check_scope`는 범위 검토 파일의 범위(`ref` 포함)가 자료원 설정과 같아야 통과하고, 동기화 명령은
  `load_checked_sources`로 이를 검사한다. (2) `indexer/sync_cli.py`는 `ChunkingSettings()`를 고정해 쓰고, 활성화 명령도 기준선 설정으로 현재 버전을 계산한다.
  `PostgresSyncStore.activate`는 대상 버전이 현재 설정 버전과 다르면 거부한다. (3) `devtools/db.py is_local_target`은 `DATABASE_URL`을 본다.
- **Decision**(사람 결정 2026-10-22): 개발 도구 `qk-dev eval-index prepare --rule <규칙> --commit <40자 SHA> [--source NAME] [--from-url-env VAR] [--allow-embed]`.
  CLI를 다시 부르지 않고 라이브러리 함수로 잇는다. 순서는 다음과 같다.
  1. 최종 이름 `qk_eval_<baseline|idsplit>_<SHA 앞 12자>`가 로컬 컨테이너에 이미 있으면 멈춘다(종료 코드 5, 덮어쓰지 않음).
  2. 준비용 이름 `<최종 이름>__preparing`을 쓴다. 이 이름의 데이터베이스가 있으면 이전 실패의 잔여물이므로 지우고 다시 만든다. 지우는 대상은 로컬 컨테이너의 `qk_eval_*__preparing`
     이름뿐이다(독립 검토 M1, 재실행 안전).
  3. 대상 접속 정보는 `DATABASE_URL`이 아니라 로컬 컨테이너 주소(`devtools/db.py local_port`)와 준비용 이름으로 만든다. 원본 접속 정보는 `--from-url-env`(기본 `DATABASE_URL`)에서
     읽고 읽기 전용 트랜잭션으로만 쓴다.
  4. `qk-migrate` 함수로 마이그레이션을 적용하고, 원본 `qk.embedding`의 bge-m3 행 `(input_hash, model_version, vector)`을 대상에 복사한다.
  5. 임시 디렉터리에 `config/sources.toml`과 범위 검토 디렉터리를 복사하고, 대상 자료원의 설정과 검토 파일 두 곳의 `ref`만 커밋 SHA로 바꾼다. 저장소 안의 파일은 바꾸지 않는다.
     검사는 평소대로 `load_checked_sources`로 한다. 끝나면 임시 디렉터리를 지운다.
  6. `indexer/sync_cli.py`의 조립 함수가 `ChunkingSettings`를 인자로 받게 고치고(기본값은 지금과 같음), `ChunkingSettings(keyword_text_rule=<규칙>)`으로 동기화 미리 보기를 돈다.
     예상 Neurons가 0이 아니면 숫자를 보이고 `--allow-embed` 없이 멈춘다(종료 코드 4, AGENTS.md 3.5). 준비용 데이터베이스는 남고 다음 실행이 2단계에서 다시 만든다.
  7. 동기화를 실행하고, 같은 설정에서 계산한 현재 버전으로 첫 인덱스 버전 활성화를 부른다.
  8. 성공하면 저장소·장부·동기화 연결을 모두 닫은 뒤 준비용 이름을 최종 이름으로 바꾼다(`ALTER DATABASE … RENAME`은 연결이 남으면 실패한다). 결과로 이름, 규칙, 커밋, 인덱스 버전, 복사한 벡터 수, 임베딩 호출 수·Neurons를 출력한다.
  기준선도 같은 명령(`--rule kw-index-baseline-v1`)으로 만든다(spec FR-029, spec 독립 검토 N3).
- **원본 리비전 기록**(독립 검토 M2): 평가용 데이터베이스의 리비전은 동기화 실행 기록 `qk.sync_run_source.origin_version`(QK-SYN-001)에 남는다. `qk-index search`와 평가는
  `retrieve()` 밖에서 자료원별 가장 최근 `succeeded` 실행의 값을 읽어 `RetrievalSummary.source_revisions`에 채운다. `retrieve()` 자체(Workers 경로)는 채우지 않아 외부 호출 수가 늘지 않는다.
- **Rationale**: GitHub 어댑터는 `ref`로 `/commits/{ref}`를 조회하므로 커밋 SHA를 그대로 받는다(`adapters/github.py`). 임베딩 입력의 원본 위치는 경로라
  (`chunking/header.py`, `SourceContent.location`) 커밋이 바뀌어도 내용이 같으면 캐시가 맞는다. 검토 파일은 임시 사본만 바꾸므로 사람이 승인한 기록은 그대로다.
- **Alternatives considered**: 운영 데이터베이스에 준비 버전을 만들고 지정 검색(C-14 경로가 운영 코드에 생긴다, 제외), 캐시 없이 다시 임베딩(후보당 약 900 Neurons),
  평가 준비를 QK-EVL-001로 넘김(spec 재승인 필요, 사람 결정으로 제외), 검토 파일에 커밋 고정 예외 규칙 추가(QK-ING-002 검사 동작이 바뀐다).
- **남는 위험**: 고정 커밋이 원본 데이터베이스를 색인한 커밋과 다르면 바뀐 문서만큼 임베딩이 필요하다. 6단계의 게이트가 사람 확인으로 넘긴다.


## R-10 확인 명령: `qk-index search`

- **Decision**: `qk-index search [--mode hybrid|vector|keyword] [--query-rule kw-query-v1|kw-query-raw] [--ranks-only] [--sources …] [--exceptions …] [--json] [--allow-remote]`.
  질문은 표준 입력에서 한 번 읽는다(spec FR-025). 명령행 인자로 받지 않는다. 로컬이 아닌 저장소는 `--allow-remote` 없이 거부한다(사용량 기록이 원격에 쓰이기 때문이다).
  출력에 대상(`target=local|remote`), 통합 순위, 검색별 순위, 출처 링크, 요약을 보인다. 청크 본문과 질문은 출력하지 않는다(`--json`도 같다).
- **Rationale**: 셸 기록·CI 로그에 질문이 남지 않게 한다(독립 검토 L4). 원격 대상 규칙은 QK-EMB-001 `usage prune`, QK-SYN-001 `run`과 같다.

## R-11 ADR-010 후보와 비교 기준 (spec FR-021)

| 후보 | 색인 쪽 | 질의 쪽 | 운영 변경 |
| --- | --- | --- | --- |
| A 기준선 | `kw-index-baseline-v1`(헤더 + 본문) | `kw-query-v1` | 없음(이 명세의 운영 기본값) |
| B 식별자 분해 | `kw-index-idsplit-v1` | `kw-query-v1` | 새 인덱스 버전 |
| C 토크나이저 교체 | 기준선 + `TokenBigramSplitSymbolAlpha` | `kw-query-v1` | 인덱스 재생성 마이그레이션. 이 명세에서 구현하지 않는다. 비교가 필요하면 QK-EVL-001이 평가용 DB에서만 바꿔 잰다 |

- **비교 기준**: 키워드 전용 상위 20건 포함 비율(식별자 원형·일부·문장형, spec SC-004·SC-005), 골든셋의 키워드 전용·하이브리드 Recall@5·MRR, 평균 결과 수(정밀도 대용).
  같은 고정 커밋, 같은 질문 세트 버전, 같은 임베딩 모델, 인덱스 버전, 표본 수를 함께 기록한다(AGENTS.md 3.4).
- **결정 절차**: QK-EVL-001이 리포트를 내면 사람이 ADR-010 문서를 승인하고 운영 규칙 변경을 별도 작업으로 정한다.

## R-12 설정

- **Decision**: `domain/retrieval.py`의 `RetrievalSettings`(후보 수 20, RRF 60, 확장 상위 8, 앞뒤 각 1, Context 예산 2,000, 질문 상한 2,000자, 질의 규칙 `kw-query-v1`)가
  기본값과 범위 검사를 갖는다. 범위: 후보 1~50, RRF 1~1,000, 확장 상위 1~20, 앞뒤 0~3, 예산 1~8,000, 질문 상한 1~8,000자. 환경값으로 바꿀 수 있는 것은
  `QK_RETRIEVAL_CONTEXT_BUDGET` 하나다(QK-FND-001 설정 등록부에 추가). 나머지는 요청 인자(평가·확인 명령)로만 바꾼다.
- **Rationale**: spec FR-028. 운영에서 조정할 가능성이 큰 것은 예산이다(R-08). 다른 값은 평가가 요청마다 바꾼다(spec US6). 설정 항목을 늘리면 Workers 바인딩과
  예시 파일이 함께 늘어난다(C-04).

## R-13 성능과 Workers CPU

- **Decision**: SC-006은 로컬 DB에 합성 1.1 MB(QK-STO-001 `devtools/bench.py`와 같은 생성기)를 넣고 질문 50개 × 5회로 하이브리드 검색 + Context 만들기를 재
  p50·p95를 기록한다. 질의용 임베딩은 가짜 제공자(시간 0)로 뺀다. Workers CPU는 배포가 없어 직접 잴 수 없다(QK-BOT-001 몫). 대신 저장소 호출을 뺀 순수 처리
  (규칙·RRF·담기) 시간을 같은 질문으로 재 질의당 p95를 기록하고, 5 ms를 넘으면 ADR-008 Revisit 조건 검토 대상으로 보고한다.
- **Rationale**: spec Assumptions(Workers 한도는 SC가 직접 재지 않는다). 순수 처리 시간은 Workers CPU 10 ms 중 검색 몫의 하한 근거가 된다 `(추론)`.

## R-14 실패 매핑

예외는 하위 클래스부터 잡는다: `StoreUnavailable` → 그 밖의 `StoreError` → `EmbedError`. `StoreUnavailable`은 어느 단계에서 나든 축소하지 않고 실패다(독립 검토 M3).

| 원인 | 하이브리드 | 단일 방식 |
| --- | --- | --- |
| 어느 저장소 호출이든 `StoreUnavailable` | 실패 `store_unavailable` | 같음 |
| 검색 결과 `no_active_index` | 실패 `no_active_index` | 같음(키워드 전용은 낱말 0개여도 새 함수가 알려 준다) |
| 두 결과·주변 조회의 `active_index_version` 불일치 | 실패 `index_version_changed`(다시 검색하지 않음) | 주변 조회와의 불일치만 같음 |
| 임베딩 `secret_blocked` | 키워드만, 생략 사유 "외부 전송 차단" | 벡터 전용: 실패 `outgoing_blocked` |
| 임베딩 그 밖의 항목 실패·`EmbedError` | 키워드만, 생략 사유 "질의 임베딩 실패(종류)" | 벡터 전용: 실패 `query_embedding_failed` |
| 벡터 검색 `StoreError`(연결 실패 아님, 결과 중복 포함) | 키워드만, 생략 사유 "벡터 검색 실패" | 벡터 전용: 실패 `store_unavailable`(spec FR-011의 종류 안에서 대응, 독립 재검토 N2) |
| 키워드 검색 `StoreError`(연결 실패 아님, 결과 중복 포함) | 벡터만, 생략 사유 "키워드 검색 실패" | 키워드 전용: 실패 `keyword_search_failed` |
| 벡터 쪽이 생략됐고(사유 무관) 키워드 낱말이 0개 | 벡터 쪽 사유에 따라 `query_embedding_failed` / `outgoing_blocked` / `store_unavailable` | 해당 없음 |
| 벡터 쪽과 키워드 쪽이 모두 생략(사유 무관) | 실패 `both_searches_failed` | 해당 없음 |
| 주변 조회 `StoreError` | 실패 `store_unavailable`(순위만 요청이면 부르지 않음) | 같음 |
