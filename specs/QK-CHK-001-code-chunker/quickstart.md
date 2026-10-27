# Quickstart: QK-CHK-001 검증 안내

구현이 명세를 만족하는지 확인하는 순서다. 1~3절은 외부 호출 0건이고, 4절은 사람이 실행하는 로컬 실측이다(대상 저장소 로컬 사본, 0 Neurons).
코드 자료원을 켜는 일, 첫 색인, 새 인덱스 버전 활성화는 이 작업에서 하지 않는다(spec FR-030·035·036).

## 0. 준비

```bash
uv sync --locked          # dev 그룹에 tree-sitter==0.26.0, tree-sitter-java==0.23.5, tree-sitter-kotlin==1.1.0 (research R-01)
```

## 1. 단위 시험 (외부 호출 0건)

```bash
uv run pytest tests/unit/chunking -q
uv run pytest tests/unit/sync tests/unit/indexer tests/unit/config tests/unit/sources -q
uv run pytest tests/unit/test_boundaries.py -q
```

| 시험 묶음 | 확인하는 것 | spec |
| --- | --- | --- |
| 기대값 시험(`tests/fixtures/chunking/code/*.java`·`*.kt` + 사람이 쓴 기대 JSON) | 결과 종류·실패 유형, 청크마다 순서·줄 범위·원문/요약 구분·심볼 경로·`locator["code"]`·키워드 검색 텍스트·임베딩 입력 텍스트(맥락 줄·반복 줄 포함) | SC-001, US1~5 |
| 반복·순서·정규화 | 두 번 청킹, 순서 섞기, CRLF·LF·BOM 차이 | SC-001, US1-8 |
| 원문 대조·줄 덮기 | 원문 청크 = 줄 범위 원문, 공백 아닌 줄 정확히 한 번, 요약 줄 ⊂ 범위 원문, 메서드 본문 줄 요약에 없음, `validate_chunks` 통과 | SC-002 |
| 국소성 | 본문 줄만 고친 판, 시그니처만 고친 판, 클래스 어노테이션만 고친 판, 멤버 문서 주석만 고친 판 | SC-003, FR-011 |
| 멤버 경계 | 문서 주석·어노테이션·시그니처·닫는 줄 같은 청크, 서로 다른 메서드 분리, 마지막 멤버에 형식 닫는 줄 | SC-004, US1-1 |
| 크기 | 작은 시험용 상한으로 3배 메서드·요약·열거형 머리·파일 머리, 한 줄 길이 초과, 헤더 길이 초과, 긴 클래스 어노테이션(맥락 줄 생략), 괄호 불일치(대체 청킹) | SC-005, US5 |
| 작은 청크 규칙 | 형식 머리 + 첫 필드 묶음 합치기(형식 머리만으로 목표 이상이면 합치지 않음), 본문 있는 멤버가 없는 DTO·레코드·인터페이스 요약 없음, 중첩 형식만 담은 컨테이너는 요약 있음, 최상위 프로퍼티만 있는 Kotlin 파일은 파일 요약 없음, 패키지가 경로 구성 요소 경계에 있을 때만 헤더에서 뺌(`a/b` 대 `x/a/bc/`) | US2-5·6, FR-010·013·014·021 |
| 메타데이터 | 선언·매개변수 어노테이션, 패키지까지 쓴 어노테이션, 제네릭, 확장 함수(수신 형식), `suspend`, 가변 인자, nullable, 함수 형식 매개변수(`() -> Unit`, `@Composable () -> Unit`), 백틱 이름, 연속 오버로드, 중첩 형식, 열거형, 레코드, `companion object`, 초기화 블록 | SC-006, US3 |
| Kotlin 해석용 사본 | `suspend { … }` 람다가 든 ViewModel 합성 파일이 대체 청킹되지 않고 심볼·컴포넌트가 나온다. 사본과 원문의 길이가 같다 | research R-01 |
| Android·테스트 | 직접 상속, 이름 규칙, `@Composable`, Android import 없는 Spring `*Service`, 다중 모듈 테스트 경로 4종, 테스트 어노테이션 유무, 테스트 경로 밖 `ABTest` | SC-007, US4 |
| Markdown 회귀 | QK-CHK-002 기대값 시험 묶음 전체가 그대로 통과, `chk-md-20d966f730bb` 불변, `.py`·`.kts` 같은 코드 자료 → `NOT_MARKDOWN` | SC-008 |
| 실패 격리·비노출 | 실패 주입 3종에서 실패 파일 청크 0·나머지 처리. 요약·경고·기록·`caplog`에 표지 문자열(본문·시그니처·심볼 이름) 없음. 외부 호출·원본 쓰기·저장 호출 0 | SC-009 |
| 비밀값 연결 | 비밀값을 심은 코드 파일은 보안 필터에서 빠져 청크 0. 빈 임베딩 캐시에서 요약 청크를 포함한 모든 `embedding_text`가 가짜 임베딩 제공자의 전송 직전 검사 호출에 나타난다(0 Neurons. 검사는 캐시에 없는 입력에만 한다, research R-12) | SC-009 |
| 버전 | `chk-code-` 첫 값 고정, 재료 항목별 변경 → 값 변경, 같은 설정 → 같은 값 | SC-010 |
| 요약 | 요약 수치(종류별 청크 수, 테스트 청크 수, 컴포넌트 수 포함) = 파일별 결과를 직접 센 값. `from_results`에 두 버전을 넘기면 첫 결과가 코드든 Markdown이든 같은 `chunking_version`이고, 결과 0개일 때 값도 확인 | SC-010, FR-029·031 |
| 켜기 설정 | 꺼짐: `iv-4c0bc4fcc642`, `meta-v1`, `.java` → `NOT_MARKDOWN`, `tree_sitter`를 가져오지 않음(`sys.modules`). 기존 고정값 시험 불변: `tests/unit/sync/test_keys.py`, `tests/unit/indexer/test_sync_cli_settings.py`, `tests/unit/chunking/test_keyword_rule_version.py`, `tests/unit/devtools/test_measure.py`(측정 출력 `settings`). 켜짐: 값이 다르고 두 버전 중 하나만 바꿔도 바뀜, `IndexSpec.metadata_schema_version`이 `meta-v2`. 켜짐에서 변경 없는 두 번째 동기화 계획의 다시 처리 0(가짜 저장소) | SC-011, US6 |
| 켜짐 방지 | 켜짐인데 인덱스 버전이 대응표에 없으면 `qk-index check`가 `CODE_INDEX_VERSION_UNREGISTERED`, `qk-index run`이 원본 호출 0건으로 멈춤. 시험용 대응표에 넣으면 통과 | SC-011, US6-5 |
| 설정 검사 | `QK_CODE_CHUNKING` 값 검사, 켜짐에서 코드 상한(바이트/토큰 환산) > Context 예산이면 `CODE_LIMIT_OVER_CONTEXT_BUDGET`, `index status`가 켜짐 설정의 현재 버전을 보고 | contracts/chunker.md 4절 |
| 코드 자료원 | 비활성 두 항목으로 `sources check` 오류 0, 같은 저장소 자료원 쌍의 포함 패턴 확장자 집합이 겹치지 않음(`dnd-backend-docs` `.md` 대 `dnd-backend-code` `.java`), `dnd-backend-docs` 범위·확인 기록 불변 | SC-013, US7 |
| 경계 | `domain`·`ports`·`embedding`·`query`·`retrieval`·`generation`이 `tree_sitter`·`chunking.code`를 가져오지 않는다. `tree_sitter`는 `chunking/code/parse.py` 함수 안에서만 가져온다 | research R-15 |

## 2. 기본 검증 (AGENTS.md 7절)

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
```

로컬 DB 시험은 저장 스키마가 바뀌지 않았는지(마이그레이션 수 불변), 그리고 `locator["code"]`가 검색·문맥 확장·추적 결과의 `Provenance`로 그대로 돌아오는지 확인한다(spec SC-006).
켜짐 설정으로 로컬 DB에 시험 청크를 저장해 본다.

## 3. 성능 (spec SC-012)

```bash
uv run python specs/QK-CHK-001-code-chunker/measurement/measure_code.py \
    --repo ../qk-targets/backend --commit 6aeccd039b825dcd7a2b6c046a34ef72089a1f78 --time-chunking
uv run python specs/QK-CHK-001-code-chunker/measurement/measure_code.py \
    --repo ../qk-targets/android --commit 0314755ed916c021448c80394f05412d1d454ebb --time-chunking
```

조건은 research R-14를 따른다. 두 저장소 본문+테스트 1,361개 파일을 구현된 `chunk_code`로 3회 청킹한다. 저장소별 중앙값을 더해 적고, 기준은 60초 이하다.

## 4. 로컬 실측 (사람 실행, 0 Neurons)

research R-02 명령을 구현된 청커로 다시 돌려 청크 수·크기 분포·상한 초과 나누기 수·`PARSE_FALLBACK` 수·`CONTEXT_OMITTED` 수를 적는다.
값이 research R-02의 흉내 측정과 크게 다르면(청크 수 ±10% 초과) 원인을 기록한다. 결정 기록(ADR-023)의 비용 추정은 이 값으로 고친다. 출력의 `script_sha256_12`를 함께 적는다.
