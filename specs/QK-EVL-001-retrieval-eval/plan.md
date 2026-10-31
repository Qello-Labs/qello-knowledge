# Implementation Plan: QK-EVL-001 골든셋 형식 검증, 검색 평가 실행기, 비교 리포트

**Branch**: `feat/SCRUM-124-gh-90-retrieval-eval` | **Date**: 2026-10-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-EVL-001-retrieval-eval/spec.md`(2026-10-31 승인)

## Summary

질문 세트를 TOML 파일 하나로 정하고 형식 검증 규칙을 규칙 이름과 함께 고정한다. 평가 실행기는 로컬 컨테이너의 `qk_eval_*` 데이터베이스만 대상으로 받는다.
실행 전에 대상마다 활성 인덱스 버전, 색인 쪽 규칙, 키워드 색인 토크나이저(`pg_class.reloptions`), 고정 커밋을 읽어 후보 A·B·C를 가린다. 이어서 QK-RET-001 `retrieve`를
`want_context=False`로 방식·대상마다 부른다. 질의 벡터는 `Embedder`를 감싼 `ReusingEmbedder`가 질문당 한 번만 받아 모든 검색에 같이 쓰므로 검색 코드는 바꾸지 않는다.
비용 관문은 운영 사용 장부를 읽기 전용 연결로 한 번 읽어(`qk.generation_usage_today`의 `day_total`) 일일 할당 잔여량과 비교한다. 결과는 질문 문장 없는 JSON 실행 기록으로 남기고,
지표·비교표는 그 기록만으로 계산해 Markdown으로 낸다. 후보 C는 후보 A 데이터베이스를 템플릿으로 복제한 뒤 키워드 색인만 `TokenBigramSplitSymbolAlpha`로 다시 만든다.
외부 호출과 문서 임베딩이 없고, 벡터 결과가 A와 같아 대조군이 깨끗하다. 근거는 [research.md](research.md)에 있다.

## Technical Context

**Language/Version**: Python 3.13 (QK-FND-001 R-01)

**Primary Dependencies**: 새 의존성 없음. 질문 세트는 표준 라이브러리 `tomllib`, 지표는 `fractions`. 저장소 읽기는 기존 `psycopg`(adapters·devtools만)

**Storage**: 새 테이블·열·마이그레이션 없음. 평가 대상은 로컬 평가용 데이터베이스(읽기 + 질의 임베딩 사용량 기록 한 곳), 운영 사용 장부는 읽기 전용 연결.
후보 C만 그 평가용 데이터베이스 안에서 키워드 색인을 다시 만든다

**Testing**: pytest. 단위(가짜 `EvalTarget`·가짜 `RetrievalStore`·가짜 제공자·가짜 장부) + 로컬 DB(`QK_REQUIRE_LOCALDB=1`). 외부 호출 시험 없음

**Target Platform**: 작업자 PC의 CLI(`qk-dev`). 운영 장부는 Bastion 터널로만 닿는다(spec Assumptions)

**Project Type**: 단일 Python 패키지 안의 순수 평가 모듈 + 좁은 경계 + 개발 도구 명령

**Performance Goals**: 없음. 실행 시각과 걸린 시간은 기록에 남기기만 한다. 검색 지연은 리포트에서 "해당 없음"(spec US5-2)

**Constraints**: 대상은 `qk_eval_*` 로컬 데이터베이스뿐(FR-012), 질의 임베딩은 허락·잔여량 확인 뒤에만(FR-013), 질문 문장·검색어·본문·벡터 비기록(FR-019), 운영 DB 쓰기 0(FR-022),
`retrieval/`·마이그레이션·`RetrievalSettings` 기본값 불변(FR-029)

**Scale/Scope**: 질문 세트 두 개(골든 11문항, 식별자 약 80문항), 대상 셋, 방식 셋. 새 모듈 약 11개, 새 명령 넷과 옵션 하나

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 템플릿 상태라 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다.

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01 근거만 | 답변을 만들지 않는다. 리포트·ADR-010 수치는 실행 기록과 실행 조건을 인용한다 | 통과 |
| C-02 현재 상태는 원본 | 해당 없음(현재 상태 질문 없음). 고정 커밋은 대상 동기화 기록에서 읽는다 | 통과 |
| C-03 자료는 데이터 | 식별자 도우미가 청크 본문을 읽지만 해석·실행하지 않고 식별자와 위치만 낸다(R-13) | 통과 |
| C-04 작게 시작 | 새 의존성 0, 마이그레이션 0, `retrieval/` 변경 0. 리랭커·답변 평가 없음 | 통과 |
| C-05 비용 상한 | 측정 1회 상한 약 8.3 Neurons(R-15), 실행 전 장부 잔여량 관문(R-07), 기본 검증 0, 후보 C 준비 0 | 통과 |
| C-06 교체 가능한 경계 | `evaluation/`은 표준 라이브러리와 `domain`·`ports`·`embedding`·`retrieval`·`evaluation`만 가져오고(R-01), 저장소 읽기는 `ports/evaluation.py` 뒤에 둔다. 경계 시험 추가 | 통과 |
| C-07 재현 | 고정 커밋 검사, 세트 지문, 키워드 전용 결과 지문 비교(SC-004), 지표는 기록만으로 재계산 | 통과 |
| C-09 원본 읽기 전용 | 평가 실행은 원본 자료원을 부르지 않는다. 대상 준비만 GitHub를 읽는다(QK-RET-001 R-09) | 통과 |
| C-10 민감 정보 | 질문 문장 비밀값 검사(`find_secrets`), 질의 임베딩 전 `check_outgoing`(QK-EMB-001), 기록·출력에 문장·본문 없음, 접속 정보는 환경 변수 이름으로만 | 통과 |
| C-11 명세 먼저 | spec 승인 2026-10-31, plan 승인 2026-10-31(spec과 다른 점 세 건 포함). tasks 승인 전 구현하지 않는다 | 통과 |
| C-12 검증으로 닫기 | SC-001~SC-010마다 시험(quickstart 1절). SC-011·SC-012는 측정 단계 H01~H08 | 통과 |
| C-13 수치 조건 | 실행 조건 전체를 기록(contracts/run-record.md 2절), 표마다 분자·분모 | 통과 |
| C-14 권한 확인 자료만 | 근거 문서 표와 검색 모두 `qk.is_visible`을 거친 문서만 본다(R-04) | 통과 |
| AGENTS.md 3.1 | 새 자료원·외부 모델 없음 | 통과 |
| AGENTS.md 3.3 인덱스 버전 | 운영 버전 불변. 비교 조건 검사가 다른 조건의 수치를 한 표에 섞지 않는다(R-11) | 통과 |
| AGENTS.md 3.4 평가 | 세트·계약 절·측정을 평가 코드와 다른 커밋으로(R-14), 개인 정보 없는 합성 질문 | 통과 |
| AGENTS.md 3.5 비용 | 예상 사용량 R-15, 실행 전 보고와 허락(R-07) | 통과 |
| AGENTS.md 4절 | 최종 이름 데이터베이스를 덮어쓰거나 지우지 않는다. 지우는 것은 `__preparing` 잔여물뿐. 기록 파일도 덮어쓰지 않는다 | 통과 |

Phase 1 설계 뒤 재점검: data-model이 기록의 비노출 항목과 실행 상태 전이를, contracts가 검증 규칙 이름·종료 코드·외부 호출 0 조건을 고정했다. 새 위반 없음. C-11은 2026-10-31 plan 승인으로 통과했다.

## Project Structure

### Documentation (this feature)

```text
specs/QK-EVL-001-retrieval-eval/
├── spec.md
├── plan.md              # 이 파일
├── research.md          # R-01~R-15
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── question-set.md  # 질문 세트 파일 형식·검증 규칙
│   ├── run-record.md    # 실행 기록 qk-evl-001-run/v1
│   └── cli.md           # qk-dev eval check·run·tables·identifiers, eval-index --keyword-tokenizer
├── measurement/         # 측정 단계(사람 승인 뒤)
│   ├── runs/            # 실행 기록 JSON
│   └── retrieval-eval-report.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks 산출물
```

### Source Code (repository root)

```text
src/qello_knowledge/
├── evaluation/
│   ├── __init__.py
│   ├── question_set.py           # 읽기·검증·지문(R-02·R-03)
│   ├── labeling.py               # 식별자 형태 판별, 근거 다시 계산(R-13)
│   ├── reuse.py                  # ReusingEmbedder, CountingProvider(R-06)
│   ├── prechecks.py              # 대상 검사, 후보 판별, 비용 미리 보기(R-05·R-07)
│   ├── runner.py                 # 실행 순서, 멈춤, 결과 항목(R-08)
│   ├── metrics.py                # R-09
│   ├── records.py                # 기록 타입·JSON 쓰기/읽기(R-10)
│   └── compare.py                # 비교 조건, 공통 질문 집합, Markdown 표(R-11)
├── ports/evaluation.py           # EvalTarget, DayUsageReader, TargetDescription, TargetDocument(장부 값은 기존 AnswerUsageToday)
├── adapters/postgres/eval_target.py  # PostgresEvalTarget(읽기 전용 질의), PostgresDayUsageReader(read_only 연결 + 기존 answer_usage)
└── devtools/
    ├── db.py                     # eval 묶음 등록, eval-index --keyword-tokenizer 옵션
    ├── eval_cli.py               # check·run·tables·identifiers 조립(제공자·임베딩 서비스·대상 연결)
    └── eval_index.py             # prepare_tokenizer(후보 C, R-12) 추가. 기존 prepare 그대로
eval/question_sets/
├── qk-evl-001-golden/            # v1.toml, labeling.md(H05 v2 옮김, 별도 커밋)
└── qk-evl-001-identifiers/       # v1.toml, labeling.md(별도 커밋, 사람 확정)
tests/
├── unit/evaluation/              # question_set, golden_v1(세트 커밋), metrics, reuse, prechecks, runner, compare, record_schema, labeling
├── fixtures/evaluation/          # 시험용 합성 질문 세트(문장이 문서 위치와 겹치지 않게, SC-008)
├── localdb/evaluation/           # eval_run(SC-004·SC-006), eval_target, day_usage_reader, identifiers_command
├── localdb/devtools/test_eval_index_tokenizer.py  # SC-009
└── unit/test_boundaries.py       # evaluation 경계 추가
```

**Structure Decision**: 판단은 저장소 없이 시험되는 `evaluation/`에 두고, 저장소 읽기는 `ports/evaluation.py` 경계와 `adapters/postgres/eval_target.py` 한 곳에서만 한다.
검색은 `retrieve`를 그대로 부르고 질의 벡터 재사용은 `Embedder` 경계에서 감싼다. 명령 조립(Workers AI 제공자, 비밀값 정책, 대상 연결)은 `devtools/eval_cli.py`가 맡는다.

## Phase 0·1 산출물

- Phase 0: [research.md](research.md) R-01~R-15. `NEEDS CLARIFICATION` 없음. TASK.md가 plan으로 넘긴 항목의 결정 위치:
  예상 Neurons → R-15(측정 1회 상한 약 8.3, 후보 C 준비 0), 후보 C 준비 명령의 계약 → [contracts/cli.md](contracts/cli.md) 5절과 R-12(후보 A 복제 + 색인 재생성),
  질의 벡터 재사용 방법 → R-06(`Embedder` 감싸기. QK-RET-001 검색 경로 코드 변경 없음).
- Phase 1: [data-model.md](data-model.md), [contracts/question-set.md](contracts/question-set.md), [contracts/run-record.md](contracts/run-record.md), [contracts/cli.md](contracts/cli.md), [quickstart.md](quickstart.md).
- 남는 위험: R-04 다른 자료원의 위치 규칙(지금은 GitHub 하나), R-07 확인 뒤 실행 중 사용량 증가, R-12 템플릿 복제 중 기준 데이터베이스 연결, R-13 청크 경계에 걸린 식별자.
- 독립 검토(작성에 관여하지 않은 별도 서브에이전트, 읽기 전용, 판정 변경 요청: 중간 4, 낮음 8) 반영. 지적 근거는 작성 세션이 코드로 다시 확인했다.
  - M1: 장부가 로컬 컨테이너나 평가 대상을 가리키면 `ledger_not_production`으로 멈춘다(R-07).
  - M2: `index_rule_unknown`·`tokenizer_unknown`이면 실행 전에 멈추고 `other` 후보를 없앴다(R-05).
  - M3: 요약 인덱스 버전은 `None`이 아닐 때만 비교하고, `no_active_index`도 멈춤에 넣었다(R-08).
  - M4: 근거 미색인을 대상·방식마다 `skipped` 결과로 남긴다(R-08, contracts/run-record.md 5절).
  - L1: 재시도 정책을 고정했다(R-06). L3: `qk.artifact.source_name`·`location`을 바로 쓴다(R-04).
  - L4: `STRATEGY = FILE_COPY`로 복제하고, `EXPLAIN`으로 확인하며, 토크나이저에 따른 결과 차이를 시험으로 확인한다(R-12).
  - L5: 문서 사이의 이름과 키를 맞췄다. L6: `eval identifiers` 출력 예외, 비밀값 검사, 커밋 검사를 넣었다(R-13). L7: `--max-neurons`와 두 단계 허락(R-07). L8: 골든 세트 대조 시험을 세트 커밋에 둔다(R-14).
  - L2 가운데 `DayUsage`는 기존 `AnswerUsageToday`로 바꿨다. `CountingProvider`는 남겼다. 호출이 나간 뒤 `EmbedError`가 나면 `RunSummary`가 사라지기 때문이다(R-06 Alternatives).
  - 반영분은 다시 검토받지 않았다. FR-027·FR-028(리포트 채우기 규칙, 목표값 제안)은 tasks에서 리포트 작업이 직접 인용한다.

## spec과 다른 점 (2026-10-31 plan 승인에 포함)

| spec | plan | 이유 |
| --- | --- | --- |
| FR-002 "라벨 근거 낱말(문장형 질문만)" | 식별자 세트의 원형·일부 질문에도 `label_terms`(식별자 원형 하나)를 둔다 | 일부 질문은 문장이 식별자의 한 낱말이라 원형이 파일에 없으면 US2-4 근거 문서("그 식별자 원형이 들어 있는 문서 전부")를 다시 확인할 수 없다(R-03) |
| US3-3 "검색이 실패한다(전송 차단, 질의 임베딩 실패 등) → 그 질문의 실패로 기록" | 항목 단위 임베딩 실패는 질문별 실패로 두되, 서비스 전체 실패인 `EmbedError`(인증·설정, 활성 인덱스 없음, 사용량 장부 쓰기 실패)는 실행을 `query_embedding_unavailable`로 멈춘다 | 다음 질문도 모두 같은 실패가 되어 질문별로 쌓으면 미완료와 구별되지 않는다(R-08) |
| FR-012 "색인 쪽 규칙과 토크나이저를 대상에서 읽을 수 있음" | 읽혀도 후보 A·B·C의 값이 아니면(`index_rule_unknown`, `tokenizer_unknown`) 멈춘다 | 비교표가 후보 이름으로 나뉘는데 알 수 없는 조합을 섞으면 해석할 수 없다(R-05) |

승인에 따라 spec FR-002·US2-4 문구를 첫 행대로 고쳤고, 이 정정은 plan 커밋과 함께 둔다. 둘째·셋째 행은 spec보다 좁게 읽은 것이라 spec 문구는 그대로 둔다.

## 구현 Scope 승인이 필요한 것

TASK.md Scope는 지금 plan 단계다. tasks 승인 때 Scope를 고쳐 함께 승인받는다.

| 변경 | 걸리는 범위 | 이유 |
| --- | --- | --- |
| `devtools/eval_index.py`·`devtools/db.py`에 `--keyword-tokenizer`와 `prepare_tokenizer` | QK-RET-001 코드 | 후보 C 준비(R-12). 옵션이 없으면 기존 동작·시험 기대값 그대로 |
| `devtools/db.py`에 `eval` 묶음, 새 `devtools/eval_cli.py` | 개발 도구 | 명령 조립(contracts/cli.md) |
| 새 `evaluation/`, `ports/evaluation.py` | 새 패키지·경계 | R-01 |
| 새 `adapters/postgres/eval_target.py` | QK-STO-001 어댑터 영역(새 파일) | 대상 설명·문서 표·장부 읽기(R-04·R-05·R-07). 기존 파일·함수 변경 없음 |
| `tests/unit/test_boundaries.py` | 기존 시험 | `evaluation/` 경계 규칙 추가. 기존 규칙 그대로 |
| 새 `eval/question_sets/` | 저장소 최상위 새 디렉터리 | 다른 명세(QK-STO-002, QK-EVL-002)와 같이 쓰는 질문 세트(R-02) |

바꾸지 않는 것: `retrieval/`, `embedding/`, `adapters/postgres/migrations/`, `domain/retrieval.py`의 `RetrievalSettings` 기본값, `domain/keyword_rules.py`, QK-RET-001 문서.

## 다른 명세에 넘기는 것

| 대상 | 넘기는 내용 |
| --- | --- |
| QK-STO-002 | 질문 세트 형식(contracts/question-set.md)과 실행 기록 스키마(contracts/run-record.md)를 평가 게이트 입력으로 쓴다. 후보 C를 고르면 토크나이저를 버전 재료나 규칙 식별자에 넣는 방법(spec FR-030) |
| QK-EVL-002 | 골든 세트의 `facts`(핵심 사실)와 같은 형식으로 답변 평가 |
| WBS 0.7 골든셋 v0 | 수집 페이지 내보내기를 이 형식으로, `unknown` 유형은 사람이 정한 뒤 넣는다. 골든 세트 v2로 더한다 |
| ADR-010 결정 뒤 작업 | 운영 키워드 규칙·토크나이저 교체, 운영 인덱스 버전 절차 |

## Complexity Tracking

| 항목 | 이유 | 더 단순한 대안을 고르지 않은 이유 |
| --- | --- | --- |
| 새 경계 `ports/evaluation.py`와 어댑터 | 대상 검사·근거 판정·비용 관문을 저장소 없이 시험해야 SC-003·SC-005·SC-007을 단위 시험으로 닫는다 | `evaluation/`이 `psycopg`를 직접 쓰기 — 경계 규칙(C-06)과 단위 시험이 깨진다 |
| `ReusingEmbedder`·`CountingProvider` | 질의 벡터 재사용(FR-014)과 실제 호출 세기를 검색 코드 변경 없이 채운다 | `retrieve`에 벡터 인자 추가 — QK-RET-001 계약과 Workers 경로가 바뀐다 |
| 후보 C 템플릿 복제 | 외부 호출 0, 벡터 결과가 A와 같아 대조군이 깨끗하다 | 처음부터 동기화 — GitHub 읽기가 한 번 더 들고 HNSW 색인이 따로 만들어져 벡터 순위가 흔들린다 |
