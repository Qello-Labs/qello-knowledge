# Research: QK-EVL-001 골든셋 형식 검증, 검색 평가 실행기, 비교 리포트

**Date**: 2026-10-31 | **Spec**: [spec.md](spec.md)(2026-10-31 승인)

코드 근거는 2026-10-31 브랜치 `feat/SCRUM-124-gh-90-retrieval-eval`(`origin/main` `00a98bb`)에서 읽었다. `NEEDS CLARIFICATION`은 없다.

## R-01 코드 위치와 경계

- **Decision**: 판단(형식 검증, 지표, 비교, 질의 벡터 재사용, 실행 순서)은 새 패키지 `src/qello_knowledge/evaluation/`에 둔다. 이 패키지는 표준 라이브러리와
  `domain`·`ports`·`embedding`·`retrieval`·`evaluation`만 가져온다. 평가 대상 읽기와 운영 사용 장부 읽기는 새 경계 `ports/evaluation.py`(`EvalTarget`, `DayUsageReader`)로 받고,
  PostgreSQL 구현은 새 파일 `adapters/postgres/eval_target.py`에 둔다. 명령 조립은 `devtools/eval_cli.py`가 하고 `qk-dev`(`devtools/db.py`)에 `eval` 묶음으로 등록한다.
  검색은 QK-RET-001 `retrieve`를 그대로 부른다(`want_context=False`). `retrieval/` 코드는 바꾸지 않는다(R-06).
- **Rationale**: 평가 대상은 로컬 컨테이너뿐이라 `qk-dev`(로컬 개발 도구)에 맞는다. QK-RET-001이 검색 흐름을 순수 함수로 두고 저장소 호출을 한 곳에 모은 구조(`retrieval/service.py`)를 따른다.
  지표·비교는 저장소 없이 시험해야 SC-003·SC-007을 빠르게 닫는다. `tests/unit/test_boundaries.py`에 `evaluation/` 규칙을 더한다(retrieval 규칙과 같은 방식).
- **Alternatives considered**: 새 실행 파일 `qk-eval`(`pyproject.toml` 스크립트 추가, 설정 진입점이 하나 더 생긴다), `indexer/`에 두기(`qk-index`는 운영 대상도 받는 명령이라 로컬 전용 규칙이 흐려진다).

## R-02 질문 세트 파일 형식: TOML

- **Decision**: 질문 세트 파일은 TOML 하나다. `[set]` 표에 머리 정보, `[[set.sources]]`에 자료원과 라벨 기준 커밋, `[[question]]` 배열에 질문 항목을 둔다. 필드는 [contracts/question-set.md](contracts/question-set.md).
  읽기는 표준 라이브러리 `tomllib`다. 파일 지문은 파일 바이트의 SHA-256이다. 위치는 `eval/question_sets/<세트 ID>/v<버전>.toml`, 라벨 기준 설명은 같은 디렉터리의 `labeling.md`다.
- **Rationale**: 사람이 리뷰하는 파일이라 주석과 여러 줄 문자열을 쓸 수 있는 형식이 낫다. 저장소 설정(`config/sources.toml`, `config/source_reviews/`)과 같은 형식이고 새 의존성이 없다.
  `tomllib`는 같은 키가 두 번 나오면 거부하므로 키 중복을 따로 검사하지 않아도 된다. 세트 ID 디렉터리에 버전 파일을 쌓으면 확정한 버전을 고치지 않고 새 버전을 더할 수 있다(FR-010).
- **Alternatives considered**: JSONL(첫 줄 머리 정보, 이어서 질문 한 줄씩. 주석이 없고 JSON은 같은 키를 조용히 덮어써 따로 막아야 한다), YAML(새 의존성), Markdown 표(H05 v1·v2 방식. 기계 검증이 어렵다).
  골든셋 v0(WBS 0.7) 내보내기는 아직 형식이 없으므로 이 형식으로 낸다.

## R-03 형식 검증 규칙과 출력

- **Decision**: 검증은 파일 하나를 읽어 규칙 이름이 붙은 오류를 모두 모은다. 규칙 목록은 [contracts/question-set.md](contracts/question-set.md) 4절이다. 비밀값은 `domain/secret_rules.find_secrets`로 질문 문장만 검사한다.
  질문 길이 상한은 `RetrievalSettings().question_max_chars`(2,000자)를 그대로 쓴다. 출력은 질문 ID·필드 이름·규칙 이름과 통과 시 수(질문, 유형별, 라벨 상태별, 미완료)다.
  평가 대상을 함께 주면 근거 문서 색인 여부를 경고로 더한다(FR-007, R-04).
- **식별자 세트 필드**: 원형·일부 질문은 `identifier_form`이 있고, 문장형 질문은 없다(문장형은 식별자 형태로 나누지 않는다). `label_terms`(라벨 근거 낱말)는 문장형 질문에는 본문 낱말,
  원형·일부 질문에는 식별자 원형 하나를 담고 식별자 세트 질문 모두에 있어야 한다. 일부 질문은 질문 문장이 식별자를 이루는 낱말이라 원형을 따로 남기지 않으면 US2-4의 근거 문서를 다시 확인할 수 없다.
  이것은 spec FR-002 "라벨 근거 낱말(문장형 질문만)"을 식별자 세트 질문 전체로 넓힌 것이다. 2026-10-31 plan 승인에 포함되어 spec 문구를 고쳤다(plan "spec과 다른 점").
- **Rationale**: FR-001~FR-006, SC-001. 규칙 하나만 어긴 사례마다 시험을 둔다. 비밀값 규칙 예외(`config/security_exceptions.toml`)는 원본 자료용이라 질문 문장에는 적용하지 않는다.
- **Alternatives considered**: 처음 오류에서 멈추기(FR-006 위반), 일부 질문에 `pair` 같은 새 필드로 원형 질문을 가리키기(새 필드가 늘고 ID 규칙에 기대야 한다).

## R-04 근거 판정의 열쇠: 자료원 이름 + 자료원 안 위치

- **Decision**: 근거 문서는 (자료원 이름, 위치)다. 평가 대상에서 이 쌍을 `qk.artifact`의 `source_name`·`location` 열로 바로 찾는다(`0004_sync.sql:2-4`).
  GitHub 저장소 파일의 위치는 저장소 기준 경로다(`adapters/github.py` `SourceItem`의 `location`). 실행 전에 대상마다 노출 조건(`qk.is_visible`)을 통과한 청크가 하나 이상인 문서를
  (자료원 이름, 위치, `source_url`)로 한 번 읽어 둔다. 이 표에서 `source_url`이 겹치면 실행 전 검사에서 멈춘다(`source_url_duplicate`).
  검색 결과 항목은 `provenance.source_url`로 이 표에서 문서를 찾는다. 근거 문서 가운데 이 표에 없는 것은 "근거 미색인"이다.
- **Rationale**: 청크 ID는 데이터베이스마다 다르고 후보 B는 청킹 규칙 버전도 다르다(spec Assumptions). 문서 단위 열쇠는 후보 사이에 같다. 검색 결과(`FusedHit`)에는 문서 ID가 없고 `source_url`이 있으며,
  GitHub 문서의 URL은 커밋 SHA와 경로를 담아 문서마다 하나다(`adapters/github.py:132`). 노출 조건은 저장소 함수와 같은 `qk.is_visible`을 써 검색이 볼 수 없는 문서를 근거로 세지 않는다(C-14).
- **Alternatives considered**: `locator.path`로 맞추기(자료원 구분이 없다), 결과 청크 ID로 문서를 다시 조회(검색마다 저장소 호출이 하나 더 든다),
  `qk.sync_source`와 `source_kind`로 조인(그 열이 UNIQUE라서만 맞는 우회다, plan 독립 검토 L3).
- **남는 위험**: Confluence 등 다른 자료원의 위치 규칙은 그 자료원을 세트에 넣을 때 정한다. 지금 세트는 `dnd-backend-docs` 하나다.

## R-05 평가 대상 지정과 실행 전 검사

- **Decision**: 평가 대상은 데이터베이스 이름으로 받는다. 접속 정보는 `qk-dev eval-index prepare`와 같이 로컬 컨테이너 기본 주소(`QK_LOCAL_DB_PORT`, 기본 54322)에 이름만 바꿔 만든다.
  `DATABASE_URL`은 읽지 않는다. 이름은 `qk_eval_` 접두를 요구한다. 대상마다 다음을 읽는다(모두 읽기 전용 트랜잭션).
  - 활성 인덱스 버전과 그 행의 임베딩 모델·차원(`qk.index_version`), 색인 쪽 규칙(`domain/keyword_rules.index_rule_for`)
  - 키워드 색인 토크나이저: `pg_class.reloptions`에서 `qk.chunk_search_text_pgroonga`의 `tokenizer=` 값. 색인이 없거나 값이 없으면 "읽지 못함"
  - 고정 커밋: 자료원별 마지막 성공 동기화의 원본 리비전(`PostgresStore.source_revisions`와 같은 질의), 색인 시점: 그 동기화 실행의 `finished_at`
  - 자료원 이름 목록(`qk.sync_source`)과 R-04의 문서 표
- **후보 판별**: (색인 쪽 규칙, 토크나이저)로 정한다. (`kw-index-baseline-v1`, `TokenBigramSplitSymbol`) A, (`kw-index-idsplit-v1`, `TokenBigramSplitSymbol`) B,
  (`kw-index-baseline-v1`, `TokenBigramSplitSymbolAlpha`) C. 검색 요약의 `index_rule`은 쓰지 않는다(spec FR-012).
  색인 쪽 규칙이 `unknown`(`domain/keyword_rules.index_rule_for`가 대응표에 없는 버전에 돌려주는 값)이면 `index_rule_unknown`, 토크나이저를 읽었지만 위 두 값이 아니면 `tokenizer_unknown`으로
  실행 전에 멈춘다. 셋 가운데 어느 후보에도 맞지 않는 대상은 받지 않는다(spec FR-012·US3-9의 "알 수 없음"을 좁게 읽지 않는다).
- **검사 순서**: 질문 세트 검증 → 대상별 위 항목 읽기와 검사(FR-012) → 대상 사이 임베딩 모델·차원 일치 → 자료원·고정 커밋 일치 → (임베딩이 드는 방식이 있을 때만) R-07 장부 읽기.
  하나라도 어긋나면 외부 호출 없이 멈춘다(SC-005).
- **Rationale**: 운영 DB는 Bastion 터널로만 닿고(`docs/ops/oci-production-store.md`) 터널 주소도 루프백이라, 주소가 루프백인지로는 운영을 가를 수 없다. 대상 접속 정보를 로컬 컨테이너 주소로만 만들면
  운영 DB가 평가 대상이 될 길이 없다. 토크나이저는 인덱스 버전 재료가 아니므로(`sync/keys.py:22-30`) 데이터베이스에서 직접 읽어야 A와 C를 가를 수 있다.
- **Alternatives considered**: 접속 문자열을 받기(운영 주소를 넣을 수 있다), 이름 규칙 없이 받기(로컬 개발 DB `postgres`가 대상이 되면 운영과 같은 데이터로 사용량이 섞인다).

## R-06 질의 벡터 재사용과 호출 세기

- **Decision**: 실행 하나에서 `ReusingEmbedder`(`evaluation/reuse.py`, `Embedder` 구현)를 모든 대상의 `RetrievalDeps.embedder`로 넘긴다. 처음 받은 질문 문장은 실제 `EmbeddingService`에 넘기고,
  결과(`EmbedResult`)나 예외(`EmbedError`)를 메모리에만 담아 같은 문장의 다음 요청에 그대로 돌려준다. 실행이 끝나면 버린다. 디스크·저장소·실행 기록에 벡터를 남기지 않는다.
  제공자 호출은 `CountingProvider`(`EmbeddingProvider` 감싸기)가 시도마다 센다(성공·실패 모두). Neurons는 성공한 묶음만 세고, 제공자가 알려 준 값(측정), 없으면
  `embedding/estimate.estimated_neurons`(추정)로 센다. 실패한 시도는 0이다(서비스가 실패를 0으로 정산하는 것과 같다). 실행 기록의 호출 수·Neurons는 이 값이다.
  검색 요약의 `embedding`·`external_calls`는 쓰지 않는다(FR-014).
- **재시도 설정**: `EmbeddingService`는 `indexer/search_cli.py`와 같이 `RetryPolicy(max_retries=1)`과 `query_retry_delay`로 만든다. 기본값(`RetryPolicy.max_retries = 3`)을 쓰지 않는다.
  예상 호출 상한(R-07)은 주입한 정책의 `max_retries + 1`로 계산하고, 시험이 이 둘이 같은 값에서 나오는지 확인한다.
- **사용량 기록 대상**: `EmbeddingService`는 대상 하나의 `PostgresStore`·`PostgresUsageLedger`로 만든다. 기본은 첫 번째 대상이고 `--usage-target`으로 바꾼다. 실행 조건에 이 이름을 남긴다(FR-022).
- **Rationale**: `retrieve`는 질의 임베딩을 `deps.embedder.embed` 한 번으로 받는다(`retrieval/service.py:115-136`). 경계에서 감싸면 검색 코드를 바꾸지 않고 FR-014를 채운다.
  실패도 같이 재사용해야 한 질문의 임베딩 실패가 모든 대상·방식에 같게 나타나 공통 질문 집합(FR-025)이 흔들리지 않는다. 재사용한 결과의 요약에는 첫 호출의 제공자 호출 수가 그대로 있어,
  요약 값을 더하면 호출을 대상·방식 수만큼 겹쳐 센다. 그래서 감싼 제공자에서 직접 센다.
- **Alternatives considered**: `retrieve`에 미리 계산한 벡터를 넘기는 인자 추가(QK-RET-001 계약 변경), 질의 임베딩 캐시를 저장소에 두기(QK-EMB-001이 질의 캐시를 두지 않기로 했다, `embedding/service.py:156`),
  재사용 감싸기가 처음 받은 `RunSummary`만 더하기(plan 독립 검토 L2). 마지막 안은 제공자 호출이 나간 뒤 인증 오류가 나면 서비스가 `EmbedError`를 올려
  요약이 사라지므로(`embedding/service.py:276`, `:283`) 그 시도를 셀 수 없어 고르지 않았다.

## R-07 비용 관문: 장부 읽기와 허락 표시

- **Decision**: 임베딩이 드는 방식(`vector`·`hybrid`)이 있으면 실행 전에 다음을 보인다.
  - 예상 호출 상한: 검색할 질문 수 N × (`max_retries` + 1). 질의 경로 설정으로 N × 2다(R-06 재시도 설정)
  - 예상 Neurons: 질문마다 `estimated_neurons([문장], bge-m3)` × (`max_retries` + 1)의 합
  - 장부: `--ledger-url-env NAME`이 가리키는 환경 변수의 접속 정보로 새 연결을 열고 `read_only = True`로 `qk.generation_usage_today(query_reserve)` 한 번을 부른다.
    이 함수는 `STABLE`이고 `day_total`(생성 + 질의 임베딩 + 색인 임베딩)을 돌려준다(`0006_generation_usage.sql:37-58`). 결과는 기존 `adapters/postgres/generation_usage.answer_usage`로 읽어
    `AnswerUsageToday`(`domain/generation.py`)로 받는다. 새로 두는 것은 읽기 전용 연결뿐이다. 잔여량은 `QK_EMBED_DAILY_ALLOWANCE` − `day_total`, 참고로 질의 예비분 대비 값도 보인다.
  - 장부는 운영 장부여야 한다. 장부 접속 정보가 로컬 컨테이너(`connection.is_local`과 같은 규칙)를 가리키거나 평가 대상과 같은 데이터베이스면 `ledger_not_production`으로 멈춘다.
    로컬 장부로 관문을 통과하면 잔여량이 언제나 할당 전체로 나오기 때문이다. 시험은 가짜 `DayUsageReader`를 주입하고, 로컬 DB 시험은 읽기 전용 연결 자체만 확인한다(quickstart 1절).
  - 장부를 읽으려면 `--allow-remote-read`가 있어야 한다(원격 읽기 허락, spec FR-013).
  - 질의 임베딩은 두 단계로 허락한다. 처음에는 허락 없이 실행해 미리 보기만 보고 종료 4로 멈춘다. 사람이 그 값을 보고 `--allow-query-embedding --max-neurons X`로 다시 실행한다.
    실행 때 다시 계산한 예상 Neurons가 X를 넘으면 멈춘다. 그래서 허락은 사람이 본 예상치에 묶인다.
  - 허락 표시가 없거나, 장부를 읽지 못하거나, 예상 Neurons가 잔여량이나 `--max-neurons`를 넘으면 질의 임베딩 0건으로 멈춘다(FR-013, SC-005). 키워드 전용만이면 장부를 읽지 않는다.
- **Rationale**: 질의 임베딩은 색인 예산과 무관하게 처리되어(QK-EMB-001 FR-019) 이 확인이 유일한 관문이다. 임베딩 장부만 보면 생성 사용량이 빠져 잔여량을 크게 본다(H05 v2 평가 보고서 9절).
  `generation_usage_today`는 셋을 한 번에 더해 준다. 읽기 전용 연결이라 장부에 쓸 수 없다. 접속 정보는 환경 변수 이름으로만 받아 명령 줄·출력에 주소가 나오지 않는다(`eval-index prepare --from-url-env`와 같은 방식).
- **Alternatives considered**: `qk-index usage` 출력을 사람이 읽고 옮기기(생성 사용량이 없다), 설정 레지스트리에 새 환경값 추가(설정 예시 재생성이 필요하고 평가 때만 쓴다).
- **남는 위험**: 확인한 뒤 실행 중에 다른 작업이 사용량을 늘릴 수 있다. 실행 중 한도에 닿으면 `provider_quota`로 멈춘다(R-08).

## R-08 실행 순서, 멈춤, 실패 기록

- **Decision**: 바깥 반복은 질문, 안쪽은 대상, 그 안은 방식(`vector`, `hybrid`, `keyword` 순)이다. 지표 대상이 아닌 질문(`no_answer`, 라벨 미완료)은 검색하지 않는다.
  어떤 대상에서 근거 문서가 모두 미색인이면 그 대상에서는 검색하지 않고, 방식마다 `status = skipped`, `skipped_reason = evidence_unindexed` 결과를 남긴다.
  모든 대상에서 미색인이어도 같이 남겨 기록만으로 "근거 미색인" 수를 다시 센다(FR-018·FR-020, plan 독립 검토 M4). 모든 대상에서 미색인인 질문은 질의 임베딩도 부르지 않는다.
  - 질문별 실패: `retrieve`의 실패 상태(`outgoing_blocked`, `query_embedding_failed`, `keyword_search_failed`, `both_searches_failed`, `question_too_long` 등)를 그대로 적는다. 다른 방식으로 다시 묻지 않는다.
  - 실행 멈춤(미완료):
    - `provider_quota`: 재사용 감싸기가 본 항목 실패 종류(`EmbedFailureKind.PROVIDER_QUOTA`)
    - `query_embedding_unavailable`: 재사용 감싸기가 받은 `EmbedError`(인증·설정, 활성 인덱스 없음, 사용량 장부 쓰기 실패). 묶음 전체 실패라 다음 질문도 모두 같은 실패가 된다
    - `store_unavailable`: 검색 상태 `store_unavailable`
    - `index_version_changed`: 검색 상태 `index_version_changed`·`no_active_index`(실행 전에는 활성 인덱스가 있었다), 또는 요약의 인덱스 버전이 `None`이 아니면서 실행 전에 읽은 값과 다름.
      벡터 전용에서 임베딩이 실패하면 검색 전에 끝나 요약의 인덱스 버전이 `None`이므로(`retrieval/service.py:78-79`, `:157-160`) 이때는 비교하지 않고 질문별 실패로 둔다
    멈추면 남은 질문을 돌리지 않고 기록을 `complete=false`와 멈춘 사유로 쓴다(FR-021).
  - 하이브리드 생략은 요약의 `omitted`(검색 쪽, 사유)와 `keyword_terms`로 남긴다.
- **Rationale**: 질문을 바깥에 두면 질문 하나의 벡터를 그 질문의 모든 검색에 쓰고 바로 버릴 수 있다. 임베딩 실패가 모든 대상에 같은 상태로 남는다. 저장소 연결 실패는 QK-RET-001도 축소하지 않는 실패라(research R-14)
  질문별 실패가 아니라 실행 멈춤으로 본다(spec US3-8). `EmbedError`는 항목 실패가 아니라 서비스 전체 실패라(`domain/embedding.py` `EmbedErrorKind`) 질문별로 쌓으면 남은 질문이 모두 같은 실패로 채워진다.
  그래서 spec US3-3의 질문별 실패(전송 차단, 항목 단위 임베딩 실패)와 나눠 멈춤으로 둔다.
- **Alternatives considered**: 대상 바깥 반복(대상마다 질문 벡터를 다시 쓰려면 실행 내내 벡터를 쥐고 있어야 한다).

## R-09 지표 계산

- **Decision**: `evaluation/metrics.py`가 실행 기록 항목만 받아 계산한다. 비율은 `fractions.Fraction`으로 계산하고 출력 때 소수 넷째 자리로 반올림한다. 분자·분모를 함께 낸다.
  첫 근거 순위는 `FusedHit.rank`(1부터, `retrieval/fusion.py:39`) 가운데 근거 문서 항목의 최솟값이다. MRR은 20 초과·없음을 0으로 둔다. Precision@5는 상위 5건 가운데 근거 항목 수 ÷ 5(결과가 5건보다 적어도 5로 나눈다).
  키워드 전용의 결과 수는 `len(hits)`, 상한 도달은 결과 수가 실행 조건의 후보 수와 같은 질문이다. 분류(유형, 식별자 형태, 질의 형태)별 지표는 같은 함수를 부분 집합에 쓴다.
- **Rationale**: FR-016·FR-017·FR-020, SC-003. 부동소수 누적 오차 없이 손으로 정한 기대값과 비교한다(QK-RET-001 R-02가 RRF에 `Fraction`을 쓴 것과 같다).

## R-10 실행 기록 형식과 비노출 항목

- **Decision**: 실행 기록은 JSON 파일 하나다(스키마 `qk-evl-001-run/v1`, [contracts/run-record.md](contracts/run-record.md)). 파일은 임시 이름으로 쓰고 끝에 이름을 바꾼다. 이미 있는 경로에는 쓰지 않는다.
  항목: 실행 조건(spec 용어 "실행 조건" 전부), 대상별 설명(R-05), 질문 목록(ID, 유형, 라벨 상태, 식별자·질의 형태, 근거 문서 위치), 질문 × 대상 × 방식 결과.
  결과에는 상태, 실패 종류나 생략 사유, 키워드 낱말 수, 첫 근거 순위, 결과 수, 상위 5건(문서 위치, 근거 여부), 미색인 근거 수, 결과 지문을 둔다.
  결과 지문은 상위 20건의 (순위, 자료원 이름, 위치) 열의 SHA-256이다.
- **비노출**: 질문 문장, 검색어 낱말, 청크 본문, 핵심 사실, `label_terms`, 질의 벡터, 청크 ID 필드가 없다(FR-019, SC-008). 스키마 시험이 허용 필드 목록 밖의 키를 거부한다.
- **Rationale**: 기록만으로 지표를 다시 계산하려면(FR-020) 첫 근거 순위·결과 수·상위 5건 근거 여부와 분류 값이 있어야 한다. 결과 지문은 후보 사이에 벡터 전용 순위가 같은지(FR-025)를 문서 단위로 가린다.
  청크 ID는 데이터베이스마다 달라 비교에 쓸 수 없고 남길 이유가 없다. `label_terms`는 식별자나 본문 낱말이라 질문 문장에 준해 뺀다.
- **위치**: 측정 기록은 `specs/QK-EVL-001-retrieval-eval/measurement/runs/<실행 ID>.json`에 커밋한다(리포트의 근거). 실행 ID는 `evl-<UTC 시각>-<무작위 8자리>`다.

## R-11 비교, 공통 질문 집합, 표

- **Decision**: `evaluation/compare.py`가 실행 기록 하나 이상을 받는다. 같은 실행 안의 대상끼리, 또는 다른 실행의 대상끼리 비교한다. 비교 조건(FR-024: 세트 ID·버전·파일 지문, 자료원별 고정 커밋, 임베딩 모델,
  질의 쪽 규칙, 후보 수, RRF 상수, 검색 필터)이 하나라도 다르면 다른 항목 이름을 모아 거부한다. 다른 실행이 섞이면 "질의 벡터 다름"을 표에 붙인다. 미완료 기록은 받지 않는다.
  방식마다 공통 질문 집합은 모든 대상에서 지표 대상이고, 실패가 아니며(`no_results`는 남김), 하이브리드 생략이 없는 질문이다. 뺀 질문 ID와 사유를 함께 낸다.
  벡터 전용 결과 지문이 대상 사이에 다른 질문은 "벡터 순위 다름"으로 표시하고, 하이브리드 차이 해석은 지문이 같은 질문으로 한정한다는 문구를 표 아래에 고정 문장으로 붙인다.
  표는 Markdown으로 낸다(`qk-dev eval tables`). 리포트 작성자는 이 출력을 리포트 4절에 붙인다.
- **Rationale**: FR-024·FR-025, US4-2~US4-6, SC-007. 표 생성을 코드로 고정해 리포트 수치가 실행 기록으로 다시 계산한 값과 같음을 시험한다(US5 독립 시험).

## R-12 후보 C 평가 대상: 후보 A 데이터베이스 복제 + 키워드 색인 재생성

- **Decision**: `qk-dev eval-index prepare`에 `--keyword-tokenizer TokenBigramSplitSymbolAlpha`를 더한다. `--rule kw-index-baseline-v1`과만 함께 쓴다. 순서:
  1. 기준 이름 `qk_eval_baseline_<sha12>`가 있는지, 최종 이름 `qk_eval_baseline_alpha_<sha12>`가 없는지 확인한다(없으면 6, 있으면 5).
  2. 이전 실패의 `<최종 이름>__preparing`만 지우고, `CREATE DATABASE "<최종>__preparing" TEMPLATE "<기준>" STRATEGY = FILE_COPY`로 복제한다.
     PostgreSQL 15부터 기본인 `WAL_LOG`는 관계 파일만 옮기는데 PGroonga는 데이터베이스 디렉터리에 자기 파일을 따로 두므로, 디렉터리를 통째로 옮기는 `FILE_COPY`로 고정한다
     (로컬 이미지 `supabase/postgres:17`, plan 독립 검토 L4).
  3. 준비용 데이터베이스에서 한 트랜잭션으로 `DROP INDEX qk.chunk_search_text_pgroonga`와 같은 이름·같은 열·`tokenizer = 'TokenBigramSplitSymbolAlpha'`의 `CREATE INDEX`를 한다.
  4. `pg_class.reloptions`로 토크나이저를 확인하고, `qk.search_keyword_terms`와 같은 설정(`enable_seqscan = off`)에서 `&@~` 조건의 `EXPLAIN`이
     `chunk_search_text_pgroonga`를 쓰는지 본다. 결과 건수로는 색인 사용을 알 수 없어 쓰지 않는다. 토크나이저에 따라 결과가 달라지는지는 시험이 본다(SC-009, quickstart 1절).
  5. 최종 이름으로 바꾼다. 출력에 기준 이름, 최종 이름, 토크나이저, 인덱스 버전, 외부 호출 0을 남긴다.
  옵션이 없으면 지금 동작과 출력, 이름 규칙(`eval_db_name(rule, commit)`)이 그대로다.
- **Rationale**: 복제는 청크 ID·임베딩·HNSW 색인·동기화 기록을 그대로 옮긴다. 그래서 A와 C는 키워드 색인 토크나이저만 다르고, 벡터 전용 결과가 같아 대조군이 깨끗하다.
  GitHub·Workers AI 호출이 없고 문서 임베딩도 0이다(FR-023의 "캐시로 처리"보다 강하다). `qk.search_keyword_terms`는 `enable_seqscan = off`라(`0005_retrieval.sql`) 키워드 검색이 이 색인의 토크나이저를 쓴다.
  마이그레이션 파일은 더하지 않아 운영 마이그레이션 목록이 바뀌지 않는다(SC-009).
- **Alternatives considered**: 후보 A처럼 처음부터 동기화한 뒤 색인만 바꾸기(GitHub 읽기가 한 번 더 들고 HNSW 색인이 따로 만들어져 벡터 결과가 달라질 수 있다), 같은 데이터베이스에 색인 두 개(함수가 어느 색인을 쓸지 정할 수 없다).
- **남는 위험**: 템플릿 복제는 기준 데이터베이스에 다른 연결이 있으면 실패한다. 그때는 단계 실패(1, `stage=clone`)로 멈추고 사람이 연결을 닫고 다시 실행한다.

## R-13 식별자 세트 만들기 도우미

- **Decision**: `qk-dev eval identifiers --target <후보 A 데이터베이스>`는 활성 인덱스 버전의 노출 청크 본문을 로컬에서 읽어 식별자 형태별 후보(식별자, 그 식별자를 담은 문서 수와 위치)를 낸다.
  출력에 대상의 고정 커밋을 함께 보인다. 후보 식별자마다 `find_secrets`를 돌려 걸린 것은 내지 않고 그 수만 보인다.
  이 명령은 본문에서 뽑은 식별자를 내는 유일한 명령이라 contracts/cli.md에 출력 예외로 적는다. 본문 문장이나 줄은 내지 않는다.
  `--set <파일>`을 주면 먼저 대상의 고정 커밋이 세트의 라벨 기준 커밋과 같은지 확인한다(다르면 종료 1). 그다음 식별자 세트 질문마다 `label_terms`로 근거 문서를 다시 계산해
  파일의 목록과 다른 질문 ID를 낸다(원형·일부는 대소문자 구별 부분 문자열, 문장형은 모든 낱말을 대소문자 무시로 포함).
  형태 판별은 `evaluation/labeling.py`의 정규식이다(camelCase, PascalCase, 약어 경계, 숫자 경계, snake_case, kebab-case, URL 경로).
  흔한 일부 낱말 제외 기준(예: 두 글자 이하, 문서 절반 이상에 나옴)은 `labeling.md`에 적는다.
- **Rationale**: US2-3·US2-4의 "그 식별자 원형이 들어 있는 문서 전부"를 손으로 세면 빠뜨리기 쉽다. 같은 고정 커밋의 평가 대상을 읽으므로 외부 호출이 없다. 출력은 식별자와 문서 위치뿐이고 본문 문장을 내지 않는다.
- **Alternatives considered**: 원본 저장소를 그 커밋으로 받아 검색(GitHub 호출, 색인 제외 문서까지 세어 검색할 수 없는 문서가 근거가 된다).
- **남는 위험**: 청크 경계에 걸린 식별자는 놓칠 수 있다. Markdown 청커는 블록 경계로 나눠 한 줄 안의 식별자는 나뉘지 않는다. 사람 확인(US2-5)에서 다시 본다.

## R-14 리포트·ADR-010 순서와 커밋 분리

- **Decision**: 측정 전후를 다음 커밋으로 나눈다(AGENTS.md 3.4, spec FR-010·FR-026).
  1. 평가 코드와 시험(시험용 질문 세트는 `tests/fixtures/evaluation/` 아래 합성 세트만 쓴다)
  2. 골든 세트 v1(H05 v2 옮김)과 그 대조 시험 `tests/unit/evaluation/test_golden_v1.py`. 이 시험은 세트 파일을 읽으므로 1번이 아니라 세트와 같은 커밋에 둔다(plan 독립 검토 L8)
  3. 식별자 세트 v1 초안 → 사람 확인 → 확정 표시 커밋
  4. 리포트 계약 절(1절)과 ADR-010 판단 규칙(측정 전 고정) → 사람 확인
  5. 측정: 실행 기록과 리포트 2~9절
  6. ADR-010 Proposed
  리포트는 `specs/QK-EVL-001-retrieval-eval/measurement/retrieval-eval-report.md`다.
- **판단 규칙 초안**(4번 커밋에서 사람이 정한다):
  - 주 지표: 식별자 세트에서 후보 B가 겨냥하는 형태(camelCase·PascalCase·약어 경계·숫자 경계, spec 용어 절)의 일부 질문에 대한 키워드 전용 상위 20건 포함 비율
  - 가드레일: 골든 세트 하이브리드 Recall@5·MRR(공통 질문 집합), 식별자 세트 키워드 전용 Precision@5, 키워드 전용 상한 도달 비율, 대조군(snake·kebab·URL 경로) 포함 비율
  - 형식: "주 지표가 A보다 n문항 이상 오르고 가드레일이 각각 m문항(또는 정한 폭) 넘게 나빠지지 않으면 권고" 꼴. n·m은 사람이 표본 수를 보고 정한다
- **Rationale**: 수치를 본 뒤 기준을 고르는 편향을 막는다(`templates/eval-report.md` 1절). 골든 세트는 8문항이라 한 문항 차이가 12.5%p다(US5-6). 그래서 비율이 아니라 문항 수로 기준을 쓰는 편이 읽기 쉽다.

## R-15 예상 사용량 (AGENTS.md 3.5)

| 단계 | 외부 호출 | 예상 Neurons | 근거 |
| --- | --- | --- | --- |
| 기본 검증(시험) | 0 | 0 | 가짜 제공자·로컬 DB(FR-031) |
| 후보 A·B 평가 대상 준비 | GitHub 읽기(고정 커밋), 임베딩은 캐시로 0 | 0, 캐시로 처리되지 않으면 후보당 약 900 | QK-RET-001 R-09. 0이 아니면 준비 명령이 멈춘다(종료 4) |
| 후보 C 준비 | 0 | 0 | R-12 복제 |
| 골든 세트 실행 1회 | 질의 임베딩만 | 상한 약 0.9 | 지표 대상 8문항의 질문 문장 570바이트 → 0.44 Neurons(1회 시도), 재시도 상한 ×2 |
| 식별자 세트 실행 1회 | 질의 임베딩만 | 상한 약 7.4 | 80문항(원형·일부 70문항 각 40바이트 이하, 문장형 10문항 각 200바이트 이하로 가정) → 3.72, 재시도 상한 ×2 |

두 세트를 한 번씩 돌리면 상한 약 8.3 Neurons로, 일일 무료 할당 10,000 Neurons(`BudgetSettings.daily_allowance`)의 0.1% 아래다. 실제 질문 문장이 정해지면 실행 명령이 다시 계산해 보인다(FR-013).
