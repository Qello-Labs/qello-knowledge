# Implementation Plan: QK-RET-001 하이브리드 검색·RRF·문맥 확장·토큰 예산·키워드 검색 텍스트

**Branch**: `feat/SCRUM-104-gh-51-hybrid-retrieval` | **Date**: 2026-10-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-RET-001-hybrid-retrieval/spec.md`(2026-10-22 승인)

## Summary

질문을 질의용으로 임베딩(QK-EMB-001, 재시도 1회)해 벡터 검색을 하고, 같은 질문을 `kw-query-v1` 규칙(낱말 정리·조사 제거)으로 낱말 배열로 바꿔 새 키워드 함수(서로 다른 맞은 낱말 수 순, 일치 확장 끔)로 검색한 뒤
RRF(k=60)로 합친다. 통합 상위 8개의 주변 청크를 새 저장소 함수 `qk.chunk_context` 한 번으로 다시 확인해 가져오고, Context 예산(예상 2,000토큰) 안에 결정적 알고리즘으로
담아 문서별 묶음과 Source ID를 만든다. 흐름은 표준 라이브러리와 경계 타입만 쓰는 새 패키지 `retrieval/`에 두어 로컬·확인 명령·평가·Workers가 같은 함수를 부른다.
색인 쪽 규칙은 청커 설정으로 고르되 기준선은 해시 재료에 넣지 않아 운영 인덱스 버전을 그대로 둔다. 식별자 분해 후보는 같은 커밋·복사한 임베딩 캐시로 만든 별도 로컬 DB에서만 쓴다.
PGroonga 점수가 낱말 횟수이고 일치 확장이 결과를 데이터에 따라 바꾸는 것을 실측해(독립 검토 H1·H2), 키워드 검색은 새 함수 `qk.search_keyword_terms`로 한다. 근거는 [research.md](research.md)에 있다.

## Technical Context

**Language/Version**: Python 3.13 (QK-FND-001 R-01)

**Primary Dependencies**: 새 런타임 의존성 없음. `retrieval/`은 표준 라이브러리만. 측정 스크립트만 `uv run --with tokenizers==0.23.3`(프로젝트 의존성 아님, R-08)

**Storage**: PostgreSQL. 마이그레이션 `0005_retrieval.sql`(함수 `qk.search_keyword_terms`·`qk.chunk_context` 추가만, R-03·R-06). 테이블·열·기존 함수 변경 없음

**Testing**: pytest. 단위(가짜 `RetrievalStore`·가짜 임베딩) + 로컬 DB(`QK_REQUIRE_LOCALDB=1`). 외부 호출 시험 없음

**Target Platform**: 검색 흐름은 로컬 서버·CLI·Workers(Pyodide) 공용. Workers 배포·저장소 연결은 QK-BOT-001과 ADR-008 변경 제안 몫

**Project Type**: 단일 Python 패키지 안의 순수 흐름 모듈 + 저장소 함수 + CLI·개발 도구

**Performance Goals**: 로컬 1.1 MB에서 하이브리드 검색 + Context p95 1.5초(SC-006), 순수 처리 p95 5 ms 이하 보고(R-13)

**Constraints**: 질의당 외부 호출 ≤ 7(FR-026), 노출 조건 우회 없음(FR-007), 질문 원문 비저장(FR-008), 기준선 해시 불변(SC-010), 원본 쓰기 없음(C-09)

**Scale/Scope**: Phase 1 문서 79개·청크 수백 개, 하루 질문 50건. 새 모듈 약 7개, 마이그레이션 1개, CLI 하위 명령 2개

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 템플릿 상태라 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다.

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01 근거만 | Context 묶음마다 Source ID와 문서 단위 출처(contracts/retrieval.md 4절). 답변 생성은 QK-GEN-001 | 통과 |
| C-02 현재 상태는 원본 | 출처에 수집 시각·원본 수정 시각을 싣는다 | 통과 |
| C-03 자료는 데이터 | 청크 본문을 해석하지 않는다 | 통과 |
| C-04 작게 시작 | 새 의존성 0, 새 SQL 함수 2개(추가만), 설정 환경값 1개, 리랭커·다양성 제한 없음 | 통과 |
| C-05 비용 상한 | R-08 측정 반영 질의당 약 53 Neurons(생성 포함, 하루 50건 약 2,660 < 예비분 3,000), 기본 검증 0, 평가용 색인 0(캐시 복사, 0이 아니면 멈춤) | 통과 |
| C-06 교체 가능한 경계 | `RetrievalStore`·`Embedder`만 사용, `retrieval/` 경계 시험 | 통과 |
| C-07 재현 | 동점 규칙·Source ID 결정적, 규칙 대응표 시험, 평가는 고정 커밋 | 통과 |
| C-09 원본 읽기 전용 | 검색·평가 준비 모두 원본에 쓰지 않음. 평가 준비는 GitHub 읽기만 | 통과 |
| C-10 민감 정보 | 질의용 임베딩 전 `check_outgoing`(QK-EMB-001), 요약·출력에 질문·검색어·본문 없음 | 통과 |
| C-11 명세 먼저 | spec 승인 2026-10-22. plan 승인 전 구현하지 않는다 | 보류 — plan 사람 승인 |
| C-12 검증으로 닫기 | SC마다 시험(quickstart 1절), 측정은 사람 단계 H01 | 통과 |
| C-13 수치 조건 | 성능·평가 수치에 데이터 규모·반복·커밋·규칙 기록(R-11·R-13) | 통과 |
| C-14 권한 확인 자료만 | 모든 청크가 저장소 노출 조건을 거침. 결과 뒤 내림도 주변 조회가 다시 거름 | 통과 |
| AGENTS.md 3.1 | 새 자료원·외부 모델 없음. Qwen3 토크나이저는 측정용 파일(데이터 전송 없음, 허락 필요) | 통과 |
| AGENTS.md 3.3 인덱스 버전 | 운영 버전 불변. 식별자 분해는 평가용 DB의 다른 버전 | 통과 |
| AGENTS.md 3.4 평가 | 이 명세는 평가 수치를 만들지 않는다(QK-EVL-001). 시험 질문은 합성 | 통과 |
| AGENTS.md 4절 | 평가 DB는 최종 이름을 덮어쓰지 않고 지우지 않음. 지우는 것은 로컬 컨테이너의 `qk_eval_*__preparing` 잔여물뿐(재실행 안전). 마이그레이션은 추가만 | 통과 |

Phase 1 설계 뒤 재점검: data-model이 Context 불변식(청크 한 번, 같은 자료·버전)과 요약의 비노출 항목을, contracts가 처리 순서(버전 비교 → 다시 확인 → 담기)와
외부 호출 계산을 고정했다. 새 위반 없음. 보류는 C-11(plan 승인)이다. C-05의 R-08 측정은 2026-10-22에 끝났다(예산 유지).

## Project Structure

### Documentation (this feature)

```text
specs/QK-RET-001-hybrid-retrieval/
├── spec.md
├── plan.md              # 이 파일
├── research.md          # R-01~R-14
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── retrieval.md     # retrieve·fuse·pack, RetrievalStore, 다른 경계에 더하는 것
│   └── cli.md           # qk-index search, qk-dev eval-index prepare
├── measurement/
│   └── measure_context.py   # R-08 측정(원문 출력 없음)
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks 산출물
```

### Source Code (repository root)

```text
src/qello_knowledge/
├── domain/
│   ├── retrieval.py              # RetrievalSettings, RetrievalRequest, FusedHit, ContextChunk, ContextBlock, Skipped, RetrievalSummary, RetrievalResult, RetrievalFailure
│   ├── keyword_rules.py          # 규칙 식별자, INDEX_KEYWORD_RULES 대응표(R-05)
│   └── chunking.py               # ChunkingSettings.keyword_text_rule 추가(R-04)
├── ports/
│   └── retrieval.py              # RetrievalStore, ContextResult, ContextItem
├── retrieval/
│   ├── __init__.py               # retrieve, keyword_query, fuse, pack 공개
│   ├── keyword.py                # kw-query-v1·kw-query-raw(R-03)
│   ├── fusion.py                 # RRF·동점(R-02)
│   ├── pack.py                   # 담기·묶음·Source ID(spec FR-013·016)
│   └── service.py                # retrieve 처리 순서, 실패 매핑(R-14), 외부 호출 계산
├── chunking/
│   ├── header.py                 # search_text(header, body, rule), 식별자 분해(R-04)
│   └── version.py                # 기준선이 아닐 때만 재료 추가(R-04)
├── adapters/postgres/
│   ├── store.py                  # PostgresStore.chunk_context 추가
│   └── migrations/0005_retrieval.sql
├── config/registry.py            # QK_RETRIEVAL_CONTEXT_BUDGET
├── indexer/
│   ├── cli.py                    # search 하위 명령 등록
│   └── search_cli.py             # 조립(R-07 재시도·대기), 표준 입력, 출력, 종료 코드
└── devtools/
    ├── db.py                     # eval-index 하위 명령 등록
    └── eval_index.py             # R-09 준비 절차
tests/
├── unit/retrieval/               # keyword, fuse, pack, degrade, calls(가짜 저장소·임베딩)
├── unit/chunking/test_keyword_rule_version.py # 기준선 해시·대응표(SC-010)
├── unit/indexer/test_search_cli.py
├── localdb/retrieval/            # hybrid, visibility, chunk_context, context, keyword_terms, keyword_rules, search_command (SC-006은 qk-dev store bench --retrieval)
├── localdb/devtools/test_eval_index.py
└── unit/test_boundaries.py       # retrieval 경계
```

**Structure Decision**: 판단(규칙·RRF·담기)은 저장소 없이 시험되는 순수 함수로, 저장소 호출은 `service.py` 한 곳에서만 한다. 노출 조건은 저장소 함수만 판정하고
흐름은 결과만 다룬다(FR-007). Workers 진입점 연결은 하지 않는다. `query/app.py`는 바꾸지 않고 QK-BOT-001이 `retrieve`를 부른다.

## Phase 0·1 산출물

- Phase 0: [research.md](research.md) R-01~R-14. `NEEDS CLARIFICATION` 없음. 사용자가 넘긴 확인 항목의 결정 위치:
  평가용 색인 커밋 고정 → R-09(`ref`에 커밋 SHA, `/commits/{ref}`), 키워드 검색어 `OR` 처리 → R-03(실측: `OR` 미이스케이프·점수는 낱말 횟수·일치 확장. 새 함수 `qk.search_keyword_terms`, 낱말 `OR`는 소문자로),
  Workers CPU → R-13(순수 처리 시간 대용 측정, 실제는 QK-BOT-001), 생성 토크나이저 비율·예산 초과 청크 수 → R-08(실측: 비율 p95 1.286, 예산 초과 청크 3/1,291, 예산 2,000 유지),
  규칙 식별자 기록 → R-05(코드 대응표, 마이그레이션 없음), 주변 청크 일괄 조회 → R-06(`qk.chunk_context`).
- Phase 1: [data-model.md](data-model.md), [contracts/retrieval.md](contracts/retrieval.md), [contracts/cli.md](contracts/cli.md), [quickstart.md](quickstart.md).
- 남는 위험: R-03 조사 목록 휴리스틱과 낱말 16개 색인 조회 시간, R-05 청커 설정 변경 시 대응표 갱신, R-09 고정 커밋과 원본 색인 커밋 차이.
- 독립 검토(작성에 관여하지 않은 별도 에이전트, 판정 변경 요청: 높음 3, 중간 4, 낮음 8) 반영. 사람 결정 3건: 새 키워드 함수(서로 다른 맞은 낱말 수), 그 함수에서 일치 확장 끔,
  평가 준비는 임시 검토 사본 + 라이브러리 호출. 나머지: 준비용 이름과 재실행(R-09), 리비전 기록(R-09), 실패 매핑 보강(R-14), 백틱(R-03), 조사 규칙 확정, `expand_top` 1~20,
  건너뛴 청크 중복 제거, `Fraction` 비교(R-02), 경계 시험 허용 목록, Scope 표 보강, quickstart FR-009·FR-028 행.

## 구현 Scope 승인이 필요한 것

TASK.md Scope는 지금 명세 작성 단계다. tasks 승인 때 Scope를 고쳐 함께 승인받는다.

| 변경 | 걸리는 범위 | 이유 |
| --- | --- | --- |
| `domain/chunking.py`, `chunking/header.py`, `chunking/version.py` | QK-CHK-002 코드 | 색인 쪽 규칙 선택(R-04). 기준선 출력·해시 불변 |
| `adapters/postgres/store.py`에 `search_keyword_terms`·`chunk_context`·`source_revisions`, `0005_retrieval.sql` | QK-STO-001 코드·스키마 | 키워드 정렬·일치 확장(R-03), 주변 청크 일괄 조회(R-06). 기존 함수·메서드 변경 없음 |
| `indexer/sync_cli.py` 조립 함수에 `ChunkingSettings` 인자 | QK-SYN-001 코드 | 평가용 색인의 규칙별 동기화·활성화(R-09). 기본 동작 그대로 |
| `indexer/cli.py`에 `search` 등록 | QK-EMB-001·QK-SYN-001이 쓰는 CLI 파일 | 확인 명령(R-10) |
| 설정 예시 파일 재생성 | QK-FND-001 생성물 | `QK_RETRIEVAL_CONTEXT_BUDGET`(R-12) |
| `config/registry.py` | QK-FND-001 설정 | `QK_RETRIEVAL_CONTEXT_BUDGET`(R-12) |
| `devtools/db.py`·`devtools/eval_index.py` | 개발 도구 | 평가용 색인 준비(R-09). 범위 검토 파일은 임시 사본만 바꾼다 |
| `tests/unit/test_boundaries.py`, `tests/localdb/store/test_migrate.py`(개수 확인이 파일 수 기반인지 확인) | 기존 시험 | 경계 목록, 마이그레이션 추가 |

## 다른 명세에 넘기는 것

| 대상 | 넘기는 내용 |
| --- | --- |
| QK-GEN-001 | Context 묶음의 생략 표시·제목 경로 표시 형식, 프롬프트 몫(예산 상한 8,000 재검토), "확인할 수 없습니다" 판단에 쓸 검색별 원래 점수, 질문이 전송 차단됐을 때 처리 |
| QK-BOT-001 | Workers 진입점에서 `retrieve` 호출, 실제 Workers CPU·subrequest 측정, 저장소 연결(ADR-008 변경 제안), 재시도 대기 2초와 Discord 지연 응답 |
| QK-EVL-001 | `qk-dev eval-index prepare`로 만든 DB에서 방식·규칙별 Recall@5·MRR, ADR-010 비교(R-11), 초기값 조정 |
| QK-CHK-001 | 코드 청크의 키워드 검색 텍스트에 ADR-010 확정 규칙 재사용 |
| ADR-010 확정 뒤 작업 | 운영 색인 규칙 변경, 인덱스 버전 교체 방식(QK-STO-002) |

## Complexity Tracking

| 항목 | 이유 | 더 단순한 대안을 고르지 않은 이유 |
| --- | --- | --- |
| 새 저장소 함수 `qk.chunk_context` | 외부 호출 상한과 순서 번호·절 경계가 필요하다(FR-012·014·026) | 기존 함수 중심별 호출 — 확장 8개면 호출 8회, 순서 번호 없음 |
| 평가용 색인 준비 도구 | 활성 버전이 DB당 하나라 후보를 같은 DB에 둘 수 없다(독립 검토 H1) | 운영 DB의 준비 버전 검색 — 노출 조건 우회 경로가 운영 코드에 생긴다(사람 결정으로 제외) |
| 조건부 해시 재료 | 기준선 해시를 지켜야 운영 동기화가 멈추지 않는다(SC-010) | 형식 번호 올리기 — 운영 인덱스 버전이 바뀐다 |
