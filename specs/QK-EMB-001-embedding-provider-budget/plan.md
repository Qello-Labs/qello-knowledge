# Implementation Plan: QK-EMB-001 임베딩 Provider·캐시·사용량 기록·일일 예산·실행 전 미리 보기

**Branch**: `docs/SCRUM-42-emb-001-spec` (명세 문서). 구현 브랜치는 명세 승인 뒤 따로 만든다 | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-EMB-001-embedding-provider-budget/spec.md`

## Summary

`Embedder` 경계 하나 뒤에 캐시 조회 → 중복 제거 → 미리 보기 → 묶음 나누기 → 예산 예약 → 제공자 호출 → 사용량 정산 → 벡터 저장 순서를 묶은
`EmbeddingService`를 둔다. 첫 제공자는 Workers AI REST의 `@cf/baai/bge-m3`이고 입력을 자르지 않는다. 예산 판정과 사용량 기록은 PostgreSQL 함수
(`qk.embedding_reserve`·`settle`·`record`·`usage_today`·`usage_prune`)에 두어, 동시 색인 실행과 Workers 질의 경로가 같은 하루 합계를 본다.
예상 Neurons는 UTF-8 바이트 ÷ 3.5를 토큰으로 보고 요금표 단가로 계산한다. 근거는 [research.md](research.md)에 있다.

## Technical Context

**Language/Version**: Python 3.13 (QK-FND-001 R-01)

**Primary Dependencies**: 표준 라이브러리(`urllib.request`, `hashlib`, `json`). 저장소 어댑터는 기존 선택 의존성 psycopg. 새 의존성 없음

**Storage**: PostgreSQL 17 + pgvector(QK-STO-001). 마이그레이션 `0003_embedding_usage.sql` 추가. 기존 `qk.embedding`을 캐시로 재사용

**Testing**: pytest. 단위·계약은 외부 호출 0건, `localdb`는 세션 전용 DB, 실측은 `external` 표시(기본 제외, 사람 승인 뒤)

**Target Platform**: 색인 CLI(GitHub Actions, 개발자 PC). Workers 질의 경로는 같은 경계·SQL 함수를 쓰되 바인딩 어댑터는 QK-RET-001(R-10)

**Project Type**: 단일 Python 패키지 안의 도메인 규칙 + 제공자 어댑터 + 저장소 함수 + CLI

**Performance Goals**: 캐시만으로 끝나는 재동기화에서 외부 호출 0건(SC-001). 미리 보기 예상과 실측 차이 ±20%(SC-005)

**Constraints**: 무료 할당 하루 10,000 Neurons, 색인 5,000·질의 예비분 3,000(사용자 결정). 입력 자르기 금지. 원문 미기록. 런타임 의존성 0

**Scale/Scope**: Protocol 3개, 서비스 1개, 제공자 2개(REST·가짜), 테이블 2개, SQL 함수 5개, 설정 3개, CLI 명령 2개

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 템플릿 상태라 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다.

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01 근거가 있는 것만 | 해당 없음(답변을 만들지 않는다) | 해당 없음 |
| C-02 현재 상태는 원본에서 | `qk-index usage`는 저장소 기록이며, 제공자 판정(3036)이 다르면 제공자를 따른다(FR-020) | 통과 |
| C-03 검색 자료는 데이터 | 텍스트를 해석하지 않고 바이트 그대로 보낸다 | 통과 |
| C-04 작게 시작 | 제공자 하나, 새 의존성 없음, Workers 바인딩은 첫 소비자에서 | 통과 |
| C-05 비용 상한 | 실행 전 미리 보기 + 요청마다 예약, 질의응답 우선(질의는 막지 않음). 유료 설정 없음 | 통과 |
| C-06 교체 가능한 경계 | `Embedder`·`EmbeddingProvider`·`UsageLedger` Protocol, 제공자 코드는 `adapters/workers_ai`에만 | 통과 |
| C-07 재현 | 해시 규칙 `emb-hash-v1`, 모델 버전은 인덱스 버전에서, 자르기 금지 | 통과 |
| C-08 멱등·실패 격리 | 캐시로 재실행 안전, 벡터 단위 저장, 정산·정리 재실행 안전, 항목별 실패 | 통과 |
| C-09 원본 읽기 전용 | 원본 호출 없음 | 해당 없음 |
| C-10 민감 정보 | `screened_by` 없는 색인 입력 거부, 기록에 원문 없음, 토큰은 어댑터 안에서만 | 통과(검사 자체는 QK-SEC-001) |
| C-11 명세 먼저 | spec.md 사람 승인 전에는 구현하지 않는다 | 보류 — 사람 승인 |
| C-12 검증으로 닫기 | 수용 시나리오마다 테스트(quickstart 1·2절) | 통과 |
| C-13 수치 조건 | 실측 시험 기록 항목 고정(quickstart 4절) | 통과 |
| C-14 권한 확인 자료만 | 해당 없음(검색 노출은 QK-STO-001 함수) | 해당 없음 |
| AGENTS.md 3.1 새 외부 서비스 | Workers AI는 ADR-002에서 정책 확인됨. 새 서비스 없음 | 통과 |
| AGENTS.md 3.5 비용 | 실측 시험 예상 약 6 Neurons를 quickstart에 적음. 기본 검증은 0 Neurons | 통과 |

Phase 1 설계 뒤 재점검: data-model이 FR-017(예산 합)·FR-021(동시 예약)을 DB 함수의 잠금과 체크로, contracts가 FR-001(제공자 타입 비노출)·FR-003(자르기 금지)을
경계 보장으로 고정했다. 새 위반 없음. 보류는 C-11(명세 승인) 하나다.

## Project Structure

### Documentation (this feature)

```text
specs/QK-EMB-001-embedding-provider-budget/
├── spec.md
├── plan.md              # 이 파일
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── embedder.md      # Embedder, EmbeddingProvider, UsageLedger
│   └── cli.md           # qk-index usage, usage prune, check 추가 검사
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks 산출물
```

### Source Code (repository root)

```text
src/qello_knowledge/
├── domain/
│   └── embedding.py              # MODELS, EmbedInput/Request/Item/Result, 실패 종류, BudgetSettings, EmbedPreview
├── ports/
│   ├── embedder.py               # Embedder, EmbeddingProvider, UsageLedger (계약 채움)
│   └── store.py                  # find_embeddings 추가
├── embedding/
│   ├── __init__.py
│   ├── hashing.py                # emb-hash-v1
│   ├── estimate.py               # 바이트 기반 예상 토큰·Neurons
│   ├── batching.py               # 묶음 나누기, 큰 텍스트 단독, 3030 쪼개기 순서
│   ├── service.py                # EmbeddingService(Embedder): embed, preview
│   └── fake.py                   # 결정적 가짜 제공자
├── adapters/
│   ├── workers_ai/
│   │   ├── __init__.py
│   │   └── rest.py               # WorkersAiRestProvider(EmbeddingProvider), 응답 분류
│   └── postgres/
│       ├── store.py              # find_embeddings 구현
│       ├── usage.py              # PostgresUsageLedger(UsageLedger)
│       └── migrations/0003_embedding_usage.sql
├── config/
│   ├── registry.py               # QK_EMBED_* 3항목
│   └── check.py                  # 예산 합 교차 검사
└── indexer/
    └── cli.py                    # usage, usage prune 하위 명령
tests/
├── unit/embedding/               # service·cache·budget·preview·estimate·settings
├── unit/fakes.py                 # 메모리 Store·UsageLedger 추가
├── contract/
│   ├── embedding_provider_contract.py
│   └── test_embedding_providers.py
├── fixtures/workers_ai/          # 합성 응답 사례(200, 400-3030, 429-3036, 429, 500, 401)
├── localdb/embedding/            # 예약·동시성·하루 경계·정리·find_embeddings
└── external/test_workers_ai_embedding.py  # -m external
```

**Structure Decision**: 규칙은 `embedding/`(도메인 서비스), 외부 제공자는 `adapters/workers_ai/`, 저장은 `adapters/postgres/`로 나눈다. QK-ING-001의
`sources/`(공통 규칙)·`adapters/`(구현) 구분과 같다. `embedding/`은 `domain`·`ports`만 가져와 제공자 모듈을 모른다(SC-007). 이를 검사하도록
`tests/unit/test_boundaries.py`의 제한 대상에 `embedding`을 더한다.

## Phase 0·1 산출물

- Phase 0: [research.md](research.md) R-01~R-14. `NEEDS CLARIFICATION` 없음. 남는 위험은 R-04(예상 오차), R-05(400 과금 여부), R-06(배열 최대 길이),
  R-09(429 코드 구분 근거), R-10(`env.AI` 사용량 반환)이다.
- Phase 1: [data-model.md](data-model.md), [contracts/embedder.md](contracts/embedder.md), [contracts/cli.md](contracts/cli.md), [quickstart.md](quickstart.md).

## 다른 명세에 넘기는 것

| 대상 | 넘기는 내용 |
| --- | --- |
| QK-SEC-001 | 비밀값 검사를 통과한 텍스트에 검사 규칙 버전(`screened_by`)을 붙여 넘긴다 |
| QK-CHK-002 | 청크 상한을 bge-m3 8,192토큰 안으로 지킨다. 예상 토큰 계산(`embedding/estimate.py`)을 같이 쓸 수 있다 |
| QK-SYN-001 | `RunSummary`를 실행 기록에 넣고, `qk-index run --preview`와 `usage prune` 주기 실행을 붙인다 |
| QK-RET-001 | Workers `env.AI` 바인딩 제공자와 HTTP RPC 사용량 장부를 계약 테스트로 만든다. `env.AI`가 사용량을 돌려주는지 확인한다 |
| QK-GEN-001 | 생성 호출 사용량도 같은 `qk.embedding_usage` 구조를 쓸지(이름 일반화 포함) 정한다 |

## Complexity Tracking

위반 없음. 예약·정산 2단계는 동시 실행 초과(FR-021)를 막는 가장 작은 방법으로 골랐다(R-08 Alternatives).
