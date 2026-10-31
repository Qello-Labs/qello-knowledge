# Contract: 명령

**Spec**: US1~US5, FR-006·FR-011~FR-013·FR-023 | **Research**: R-01, R-05, R-07, R-11~R-13

모든 명령은 `qk-dev` 아래에 있고 평가 대상은 로컬 컨테이너의 `qk_eval_*` 데이터베이스뿐이다. 대상 접속 정보는 `QK_LOCAL_DB_PORT`(기본 54322)와 데이터베이스 이름으로 만들고 `DATABASE_URL`을 읽지 않는다.
출력에 질문 문장, 핵심 사실, 라벨 근거 낱말, 검색어 낱말, 청크 본문, 접속 정보를 넣지 않는다. 예외는 4절 `eval identifiers` 하나다. 이 명령은 본문에서 뽑은 식별자(낱말 하나)를 내지만
본문 문장·줄은 내지 않고, 비밀값 규칙에 걸린 식별자는 빼고 그 수만 보인다. 공통 옵션은 `--json`(한 줄 JSON 출력)과 `--env-file`(기본 `.env`)이다.

## 1. `qk-dev eval check <세트 파일>`

질문 세트 형식 검증(US1). 외부 호출 없음.

| 옵션 | 뜻 |
| --- | --- |
| `--target DB` | 평가 대상 근거 미색인 경고를 더한다([question-set.md](question-set.md) 5절) |

출력: 통과면 세트 ID·버전·지문, 질문 수, 유형별·라벨 상태별 수, 미완료 수, 경고. 거부면 `(질문 ID, 필드, 규칙 이름)` 목록 전부.

| 종료 코드 | 뜻 |
| --- | --- |
| 0 | 통과(경고가 있어도 0) |
| 1 | 형식 오류로 거부 |
| 2 | 인자 오류, 파일 없음, 대상 연결 실패 |

## 2. `qk-dev eval run`

세트 하나를 대상 하나 이상에서 방식별로 검색해 실행 기록을 쓴다(US3·US4).

| 옵션 | 뜻 |
| --- | --- |
| `--set FILE` | 질문 세트(필수) |
| `--target DB` | 평가 대상(필수, 여러 번). 순서가 기록·표 순서 |
| `--mode {vector,keyword,hybrid}` | 여러 번. 기본 셋 다 |
| `--query-rule`, `--candidates`, `--rrf-k` | 요청 단위 검색 설정. 기본은 `RetrievalSettings()` |
| `--source-kind`, `--artifact-kind` | 검색 필터. 기본 없음 |
| `--usage-target DB` | 질의 임베딩 사용량을 기록할 대상. `--target` 가운데 하나. 기본 첫 대상 |
| `--ledger-url-env NAME` | 운영 사용 장부 접속 정보가 든 환경 변수 이름. 임베딩이 드는 방식이 있으면 필수. 로컬 컨테이너나 평가 대상을 가리키면 거부 |
| `--allow-remote-read` | 운영 장부 읽기를 허락 |
| `--allow-query-embedding` | 질의 임베딩 호출을 허락. `--max-neurons`와 함께만 쓴다 |
| `--max-neurons X` | 사람이 미리 보기에서 본 예상 Neurons 이상의 값. 실행 때 다시 계산한 예상치가 X를 넘으면 멈춘다 |
| `--out PATH` | 실행 기록 경로(필수, 이미 있으면 거부). 이미 있는 디렉터리면 그 안에 `<실행 ID>.json`으로 쓴다(research R-10). 파일 경로면 상위 디렉터리가 있어야 한다 |
| `--sources`, `--exceptions` | 전송 검사 정책을 만들 자료원 설정·보안 예외 파일. 기본 `config/sources.toml`, `config/security_exceptions.toml`(`qk-index search`와 같다) |

처리 순서: 세트 검증 → 대상 검사(research R-05) → (임베딩 방식이 있으면) 비용 미리 보기와 관문(research R-07) → 실행(research R-08) → 기록 쓰기 → 대상별·방식별 지표 요약 출력.
비용 미리 보기는 질문 수, 호출 상한, 예상 Neurons, 장부 날짜·`day_total`·잔여량·질의 예비분을 보인다. 임베딩이 드는 실행은 두 번 한다. 처음은 `--allow-query-embedding` 없이 미리 보기를 보고(종료 4),
사람이 그 값을 보고 `--allow-query-embedding --max-neurons X`로 다시 실행한다.

| 종료 코드 | 뜻 | 외부 호출 |
| --- | --- | --- |
| 0 | 실행 완료, 기록 씀 | 질의 임베딩만 |
| 1 | 실행 전 검사 실패. 사유: `set_invalid`, `target_not_eval`, `target_unreachable`, `no_active_index`, `index_rule_unknown`, `tokenizer_unreadable`, `tokenizer_unknown`, `source_url_duplicate`, `document_location_missing`(노출 청크가 있는데 자료원 이름·위치가 빈 자료가 있음), `source_missing`, `commit_mismatch`, `model_mismatch` | 0 |
| 2 | 인자 오류(`--allow-query-embedding`에 `--max-neurons` 없음, `--usage-target`이 `--target` 밖 포함), 기록 경로가 이미 있음·상위 디렉터리 없음, 설정·자료원 설정·보안 예외 파일 오류 | 0 |
| 2 | 실행 뒤 기록 쓰기 실패(`record_write_failed`). 출력에 실행 ID와 실제 제공자 호출 수·Neurons를 남긴다 | 질의 임베딩만 |
| 3 | `--allow-remote-read` 없음(임베딩이 드는 방식이 있을 때) | 0 |
| 4 | 미리 보기 뒤 멈춤: `--allow-query-embedding` 없음, `ledger_not_production`, 장부 읽기 실패, 예상 Neurons가 잔여량이나 `--max-neurons` 초과 | 0(장부 읽기만) |
| 5 | 실행 미완료(기록은 `complete = false`로 씀, 멈춘 사유는 contracts/run-record.md 1절) | 멈추기 전까지 |

## 3. `qk-dev eval tables`

실행 기록에서 Markdown 표를 낸다(US3 지표, US4 비교). 저장소·외부 호출 없음.

| 옵션 | 뜻 |
| --- | --- |
| `--run FILE` | 실행 기록(필수, 여러 번) |
| `--target DB` | 표에 넣을 대상(여러 번). 기본 기록의 모든 대상 |
| `--breakdown {type,identifier_form,query_form}` | 분류별 표(여러 번) |

대상이 둘 이상이면 비교 조건을 검사하고(research R-11) 공통 질문 집합 비교표, 뺀 질문 ID와 사유, 벡터 순위 다름 표시를 더한다. 대상이 하나면 대상별 표만 낸다.
분류별 표는 대상이 둘 이상이면 공통 질문 집합으로, 하나면 그 대상의 지표 대상 전부로 계산하고 제목에 어느 쪽인지 적는다.

| 종료 코드 | 뜻 |
| --- | --- |
| 0 | 표 출력 |
| 1 | 비교 조건 불일치(다른 항목 이름과 기록별 값 출력), 미완료 기록 |
| 2 | 인자 오류(같은 실행 기록 두 번, 고른 대상이 하나도 없는 기록 포함), 기록 스키마·값 형식 오류 |

## 4. `qk-dev eval identifiers`

식별자 세트 만들기 도우미(research R-13). 평가 대상의 노출 청크 본문을 로컬에서 읽는다. 외부 호출 없음.

| 옵션 | 뜻 |
| --- | --- |
| `--target DB` | 후보 A 평가 대상(필수) |
| `--set FILE` | 주면 대상 고정 커밋과 세트 라벨 기준 커밋이 같은지 먼저 본 뒤, 식별자 세트 질문의 근거 문서를 다시 계산해 파일과 다른 질문 ID를 낸다 |
| `--form FORM` | 후보를 낼 식별자 형태(여러 번). 기본 일곱 형태 |

출력: 대상 고정 커밋. `--set`이 없으면 형태별 (식별자, 문서 수, 문서 위치)와 비밀값 규칙으로 뺀 후보 수. `--set`이 있으면 다른 질문 ID와 (빠진 위치, 더 있는 위치). 질문 문장과 `label_terms` 값은 내지 않는다.

| 종료 코드 | 뜻 |
| --- | --- |
| 0 | 후보 출력, 또는 `--set`의 근거 문서가 모두 같음 |
| 1 | `--set`의 근거 문서가 다른 질문이 있음, 또는 고정 커밋이 라벨 기준 커밋과 다름 |
| 2 | 인자 오류, 대상 연결 실패 |

## 5. `qk-dev eval-index prepare --keyword-tokenizer` (QK-RET-001 contracts/cli.md 2절에 더하는 것)

| 옵션 | 뜻 |
| --- | --- |
| `--keyword-tokenizer TokenBigramSplitSymbolAlpha` | 후보 C. `--rule kw-index-baseline-v1`과만 쓴다. 같은 커밋의 후보 A 데이터베이스를 복제해 키워드 색인 토크나이저만 바꾼다(research R-12) |

이 옵션을 주면 `--source`, `--from-url-env`, `--allow-embed`, `--sources`, `--reviews`, `--exceptions`는 쓰지 않는다(동기화하지 않는다).
최종 이름은 `qk_eval_baseline_alpha_<sha12>`, 준비용 이름은 그 뒤에 `__preparing`이다. 출력 JSON에 `base_database`, `database`, `tokenizer`, `index_version`, `external_calls: 0`을 둔다.

| 종료 코드 | 뜻 |
| --- | --- |
| 0 | 준비 완료 |
| 1 | 단계 실패(`stage`: `clone`(`STRATEGY = FILE_COPY` 복제, 기준 데이터베이스에 다른 연결이 있을 때 포함), `reindex`, `verify`(토크나이저 값·`EXPLAIN` 색인 사용), `rename`) |
| 2 | 인자 오류(`--rule kw-index-idsplit-v1`과 함께 씀 포함) |
| 5 | 최종 이름 데이터베이스가 이미 있음 |
| 6 | 같은 커밋의 후보 A 데이터베이스가 없음 |

옵션이 없으면 QK-RET-001 contracts/cli.md 2절의 동작·출력·종료 코드가 그대로다.
