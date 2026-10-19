# Implementation Plan: QK-STO-001 저장 스키마·마이그레이션·검색 질의

**Branch**: `feat/SCRUM-90-gh-33-storage-schema` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-STO-001-storage-schema-search/spec.md`

## Summary

PostgreSQL `qk` 스키마에 원본 자료·청크·임베딩·인덱스 버전 테이블을 만들고, 출처 누락·차원 불일치·활성 버전 중복을 DB 제약으로 막는다.
벡터 검색(pgvector HNSW + iterative scan)과 한국어·식별자 키워드 검색(PGroonga)은 권한·상태·버전 조건을 안에 넣은 SQL 함수로 두고,
`Store` 경계 뒤의 psycopg 어댑터가 부른다. 문서 교체는 행 잠금을 건 트랜잭션 하나로 한다. 마이그레이션은 체크섬·원자 적용·파괴적 표시를
지키는 작은 실행기(`qk-migrate`)로 적용한다. ADR-007은 로컬 스파이크로 "자체 스키마"로 정했다. 근거는 [research.md](research.md)에 있다.

## Technical Context

**Language/Version**: Python 3.13 (QK-FND-001 R-01)

**Primary Dependencies**: psycopg[binary] 3.2+ (선택 의존성 `postgres`, 색인·테스트 쪽만). 그 밖은 표준 라이브러리

**Storage**: PostgreSQL 17 + pgvector 0.8.2 + PGroonga 3.2.5. 로컬은 `supabase/postgres:17.11.0.004`, 운영은 Oracle Cloud Always Free A1 인스턴스에 같은 이미지(ADR-008 변경 제안, 이 작업에서 적용 안 함)

**Testing**: pytest, `localdb` 표시. 세션 전용 데이터베이스 `qk_test_<무작위>`(R-10)

**Target Platform**: 색인 CLI(GitHub Actions `ubuntu-latest`, 개발자 PC). 질의 경로(Workers)는 같은 SQL 함수를 HTTP RPC로 부른다(R-06, 후속 명세)

**Project Type**: 단일 Python 패키지(QK-FND-001 구조) 안의 저장소 어댑터 + 마이그레이션 + CLI

**Performance Goals**: 원문 약 1.1 MB 규모에서 벡터·키워드 상위 20건 p95 1초 이하(SC-005)

**Constraints**: 질의 안 필터(C-14), 교체 원자성(C-08), 출처 필수(C-07), 외부 요청 0건, 운영 저장소 미적용, 런타임 의존성 추가 없음

**Scale/Scope**: 테이블 5개, SQL 함수 4개, 경계 연산 10개, 마이그레이션 1~2개, CLI 2개(`qk-migrate`, `qk-dev store bench`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 아직 템플릿 상태라 원칙 초안 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다.

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01 근거가 있는 것만 | 검색 결과마다 출처(링크·버전·위치·제목 경로)를 함께 돌려준다(FR-009) | 통과 |
| C-02 현재 상태는 원본에서 | 결과에 수집 시각을 싣는다 | 통과 |
| C-03 검색 자료는 데이터 | 본문을 해석·실행하지 않는다. 검색어는 이스케이프한다 | 통과 |
| C-04 작게 시작 | 테이블 5개·함수 4개. 리랭커·RRF 없음. 의존성 psycopg 하나 | 통과 |
| C-05 비용 상한 | 유료 서비스 없음, 0 Neurons | 통과 |
| C-06 교체 가능한 경계 | `Store` Protocol + `domain` dataclass, psycopg는 `adapters/postgres`에만(R-09) | 통과 |
| C-07 재현 | 청크마다 청킹 규칙·인덱스 버전, 임베딩마다 모델 버전. 차원은 칼럼 타입으로 고정 | 통과 |
| C-08 멱등·실패 격리 | 교체 한 트랜잭션 + 행 잠금 + 해시 비교(R-07), 마이그레이션 재적용 0건 | 통과 |
| C-09 원본 읽기 전용 | 원본 호출 없음 | 해당 없음 |
| C-10 민감 정보 | 테스트 데이터는 합성. 오류·출력에 접속 정보 없음 | 통과 |
| C-11 명세 먼저 | spec.md(PR #27 승인) 기준. 명세 밖 동작 없음 | 통과 |
| C-12 검증으로 닫기 | 수용 시나리오마다 `localdb` 테스트(quickstart 2절) | 통과 |
| C-13 수치 조건 | bench 출력과 기록 표에 이미지·CPU·규모·반복 횟수 | 통과 |
| C-14 권한 확인 자료만 | 노출 조건을 SQL 함수 `WHERE`에서만 판정, `access_scope` 기본 거부(R-05) | 통과 |
| AGENTS.md 3.1 새 외부 서비스 정책 | Oracle Cloud 정책을 ADR-008 변경 제안에 기록(학습 사용·보존 기간 일부 확인 못 함), 운영 PGroonga 확인은 인스턴스 생성 뒤(R-13) | 보류 — 사람 결정 |
| AGENTS.md 4절 공유 DB 보호 | 테스트·bench는 전용 데이터베이스, 파괴적 마이그레이션은 원격에서 플래그 필요 | 통과 |

Phase 1 설계 뒤 재점검: data-model이 FR-004·005를 DB 제약으로, contracts가 FR-008(질의 안 필터)과 FR-015(제품 타입 비노출)를 경계 규칙으로
고정했다. 새 위반 없음. 보류 항목은 R-13 하나다.

## Project Structure

### Documentation (this feature)

```text
specs/QK-STO-001-storage-schema-search/
├── spec.md
├── plan.md              # 이 파일
├── research.md          # ADR-007 스파이크 포함
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── store.md         # Store 경계와 SQL 함수
│   └── cli.md           # qk-migrate, qk-dev store bench
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks 산출물
docs/sdd/decisions/
├── ADR-007-storage-schema.md   # 새 결정 기록
└── ADR-008-runtime-and-cost-cap.md  # FR-022 확인 결과 추가
```

### Source Code (repository root)

```text
pyproject.toml                    # optional-dependencies.postgres, qk-migrate 스크립트
src/qello_knowledge/
├── domain/
│   └── store.py                  # ArtifactRecord, ChunkInput, SearchResult 등 dataclass, 오류 타입
├── ports/
│   └── store.py                  # Store Protocol (계약 채움)
├── adapters/
│   └── postgres/
│       ├── __init__.py
│       ├── connection.py         # DATABASE_URL 해석, 로컬 판단(devtools R-06 재사용), StoreUnavailable 변환
│       ├── store.py              # PostgresStore(Store)
│       ├── migrate.py            # 실행기 + qk-migrate main
│       └── migrations/
│           ├── 0001_initial_schema.sql   # qk 스키마, 테이블, 인덱스
│           └── 0002_search_functions.sql # 검색·주변 청크 SQL 함수
└── devtools/
    ├── db.py                     # 기존. is_local_target 재사용
    └── bench.py                  # qk-dev store bench
tests/
├── unit/
│   ├── store/test_domain.py      # 입력 검증(출처·차원), 상한
│   └── store/test_migrate_files.py  # 파일 이름·체크섬·파괴적 표시 파싱
└── localdb/
    └── store/
        ├── conftest.py           # qk_test_<무작위> DB 생성·마이그레이션·정리, 합성 데이터 빌더
        ├── test_provenance.py
        ├── test_search_filters.py
        ├── test_keyword.py
        ├── test_replace.py
        ├── test_embedding_reuse.py
        ├── test_migrate.py
        └── test_no_active_index.py
.github/workflows/ci.yml          # test job에 qk-migrate 두 번 실행 단계
```

**Structure Decision**: QK-FND-001의 단일 패키지 구조를 그대로 쓴다. 저장소 구현은 `adapters/postgres` 한 곳에 모으고, 마이그레이션 SQL은
패키지 데이터로 넣어 CLI가 설치 위치와 무관하게 찾게 한다. `qk-dev`에는 로컬 전용 도구(bench)만, 운영에도 쓰는 마이그레이션은 별도 진입점
`qk-migrate`로 둔다.

## Complexity Tracking

위반 없음. 자체 마이그레이션 실행기는 기존 도구 대비 단순한 쪽을 고른 결과다(R-08 Alternatives).
