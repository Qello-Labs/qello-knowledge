# Implementation Plan: QK-CHK-001 코드 청커·코드 메타데이터

**Branch**: `feat/SCRUM-118-gh-63-code-chunker` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-CHK-001-code-chunker/spec.md`

## Summary

보안 필터를 통과한 `.java`·`.kt` 파일을 tree-sitter로 해석해 청크로 나눈다. 단위는 형식 선언·멤버이고, 종류는 파일 머리, 형식 머리(+첫 필드 묶음), 메서드·생성자, 필드 묶음, 요약이다.
Kotlin은 `suspend { … }` 문법 결함을 피하려고 같은 길이 해석용 사본으로 해석한다. 청크 본문은 원문 줄 그대로다. 검색 헤더와 형식 선언 맥락 줄은 임베딩 입력과 키워드 텍스트에만 붙는다.
코드 메타데이터는 `locator["code"]`에, 심볼 경로는 `heading_path`에 담는다. 그래서 저장 스키마·SQL·검색·생성 코드를 바꾸지 않는다.

코드 청킹은 `QK_CODE_CHUNKING=off`가 기본이다. 꺼져 있으면 Markdown 청킹 규칙 버전, 메타데이터 스키마 버전(`meta-v1`), 인덱스 버전(`iv-4c0bc4fcc642`)이 지금과 같다.
코드 자료원 두 개(`dnd-backend-code`, `dnd-android-code`)는 비활성으로 등록하고 결정 기록 ADR-022을 쓴다.

대상 두 저장소 실측은 다음과 같다(research R-02). 청크 약 11,800개, 상한 1,500을 넘는 청크 22개, 해석 오류 0이다. 본문 코드 첫 색인은 보수 추정 약 3,000 Neurons다.
켜짐 계산 코드는 미리 넣되, 켜짐 인덱스 버전이 키워드 규칙 대응표에 없으면 `qk-index check`·`run`이 멈춘다. 그래서 환경값만으로는 켜지지 않는다(research R-09).

## Technical Context

**Language/Version**: Python 3.13 (QK-FND-001 R-01). 대상 코드는 Java 21(백엔드), Kotlin 2.3.21(Android)

**Primary Dependencies**: `tree-sitter==0.26.0`, `tree-sitter-java==0.23.5`, `tree-sitter-kotlin==1.1.0`(색인 전용 선택 의존성 `index`와 `dev` 그룹, research R-01). 그 밖에 표준 라이브러리와 기존 `markdown-it-py`

**Storage**: 스키마 변경 없음. 코드 메타데이터는 기존 `qk.chunk.locator`(jsonb)의 `code` 키, 심볼 경로는 `heading_path`(research R-11)

**Testing**: pytest. 단위 시험(외부 호출 0건)과 로컬 DB 시험(`QK_REQUIRE_LOCALDB=1`). 실측은 로컬 사본(사람 실행, 0 Neurons, quickstart 4절)

**Target Platform**: 색인 CLI(OCI 운영 인스턴스의 systemd 타이머, 개발자 PC). Workers 질의 번들에는 들어가지 않는다

**Project Type**: 단일 Python 패키지 안의 도메인 타입 + 청커 하위 패키지 + 동기화·설정 연결 + 자료원 설정·결정 기록

**Performance Goals**: 두 저장소 1,361개 파일 청킹 60초 이하(spec SC-012, research R-14)

**Constraints**: 다음을 지킨다.
- 원문 줄 보존과 원문 청크 겹침 없음(FR-009)
- 예상 토큰 상한 1,500 ≤ Context 예산 2,000(FR-016, research R-03)
- 결과·기록에 본문·시그니처·심볼 이름 없음(FR-007), 외부 호출 0(FR-004)
- 꺼짐이면 인덱스 버전 불변(FR-030), Markdown 결과 불변(FR-002)

**Scale/Scope**: 공개 함수 5개(`chunk_code`, `code_chunking_version`, `index_chunking_version`, `metadata_schema_version`, `version_for`), 새 도메인 타입 4개, 설정 1개, 자료원 2개, 의존성 3개

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 템플릿 상태라 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다.

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01·C-02 | 해당 없음(답변을 만들지 않는다) | 해당 없음 |
| C-03 검색 자료는 데이터 | 코드 주석·문자열 안의 지시를 해석하지 않고 원문 그대로 자른다. 해석용 사본은 해석에만 쓴다 | 통과 |
| C-04 작게 시작 | 기본 꺼짐, 비활성 자료원, 첫 활성화는 본문 코드만 권고(research R-13), 두 자료원은 하나씩 | 통과 |
| C-05 비용 상한 | 이 작업 0 Neurons. 첫 색인 보수 추정 약 3,000(하루 예산 5,000 안)을 ADR-022에 적는다 | 통과 |
| C-06 교체 가능한 경계 | 해석기는 `chunking/code/parse.py` 한 곳, 타입은 `domain/chunking.py`(표준 라이브러리만), 자료원 종류를 모르는 진입점 | 통과 |
| C-07 재현 | 원문 줄 그대로, 결정적 규칙, 해석기·사본 규칙 버전을 재료로 한 `chk-code-<해시>`, 켜짐일 때 인덱스 버전에 반영 | 통과 |
| C-08 멱등·실패 격리 | 순수 함수, 파일별 실패 값, 해석 실패는 대체 청킹, 문서별 버전 비교(research R-10) | 통과 |
| C-09 원본 읽기 전용 | 청커는 원본을 부르지 않는다. 실측 사본은 읽기 전용 클론 | 통과 |
| C-10 민감 정보 | 보안 필터 통과 자료만 받는다. 요약 청크도 전송 직전 검사(research R-12). 결과·기록에 본문·시그니처 없음 | 통과 |
| C-11 명세 먼저 | spec 2026-10-26 승인. 다만 plan 측정과 plan 검토 결과로 FR-010·013·014·020·021·026·030, US2·US6, SC-011을 고쳤다(사용자 결정). 재승인과 plan 승인 전에는 구현하지 않는다 | 보류 — spec 재승인·plan 승인 |
| C-12 검증으로 닫기 | SC마다 시험(quickstart 1절) | 통과 |
| C-13 수치 조건 | 커밋, 해석기·토크나이저 버전, 추정식, 표본을 research R-02에 고정 | 통과 |
| C-14 권한 확인 자료만 | 입력이 팀 공용 판정을 통과한 자료뿐. 두 저장소 모두 공개 | 통과 |
| AGENTS.md 3.1 새 자료원 | 비활성 등록 + ADR-022(데이터 처리 정책 포함). 켜기는 사람이 확인 기록과 함께 한다 | 통과 |
| AGENTS.md 3.3 인덱스 버전 | 켜짐에서만 `chk-code`·`meta-v2`가 인덱스 버전에 들어가고, 활성화는 QK-STO-002 | 통과 |
| AGENTS.md 3.5 비용 | 0 Neurons | 통과 |
| AGENTS.md 4절 | 다른 사람 파일 없음. 기존 시험 기대값 변경 없음(아래 Scope) | 통과 |

Phase 1 설계 뒤 다시 점검했다. 새 위반은 없다. 보류는 C-11 하나다(spec 재승인, plan 승인).
- data-model이 FR-005(실패 시 청크 0)·FR-009(원문 청크 덮기)·FR-030(꺼짐 불변)을 타입·함수 보장으로 고정했다.
- contracts가 FR-016~020·027~029를 진입점 보장으로 고정했다.

## Project Structure

### Documentation (this feature)

```text
specs/QK-CHK-001-code-chunker/
├── spec.md
├── plan.md              # 이 파일
├── research.md          # R-01~R-15
├── data-model.md
├── quickstart.md
├── contracts/
│   └── chunker.md       # chunk_code, 버전 함수, 설정 검사, chunk_screened 변경
├── measurement/
│   └── measure_code.py  # research R-02·R-04 재현(원문 출력 없음). 구현 단계에서 --time-chunking 추가
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks 산출물
```

### Source Code (repository root)

```text
pyproject.toml, uv.lock               # index 선택 의존성·dev 그룹에 tree-sitter 3종(R-01)
config/sources.toml                   # dnd-backend-code, dnd-android-code (enabled = false, R-13)
docs/sdd/decisions/ADR-022-code-sources.md   # 새 결정 기록(spec FR-034)
src/qello_knowledge/
├── domain/chunking.py                # CodeChunkingSettings(별도 타입, ChunkingSettings 불변), CodeChunkKind, AndroidComponent, 경고 2종, ChunkingSummary 추가 필드·from_results 키워드 인자
├── chunking/
│   ├── __init__.py                   # chunk_code, code_chunking_version, index_chunking_version, version_for 공개
│   ├── service.py                    # chunk_screened 나눠 주기, 요약
│   ├── version.py                    # index_chunking_version (Markdown chunking_version은 그대로)
│   └── code/
│       ├── __init__.py
│       ├── parse.py                  # tree-sitter 호출, Kotlin 해석용 사본(R-01)
│       ├── units.py                  # 노드 → 원문 청크 단위, 주석·닫는 줄 붙이기, 필드 묶음(R-05)
│       ├── symbols.py                # 심볼 이름, 매개변수 형식, 시그니처, 어노테이션, 컴포넌트, 테스트 판정(R-06)
│       ├── header.py                 # 검색 헤더, 맥락 줄, 임베딩 입력, 키워드 텍스트(R-07)
│       ├── split.py                  # 상한 초과 나누기, 반복 줄, 맥락 줄 생략, 실패 판정
│       ├── version.py                # chk-code-<해시>(R-08)
│       └── service.py                # chunk_code, 대체 청킹, 실패 격리
├── sync/keys.py                      # metadata_schema_version(code)
├── sync/run.py                       # current_spec가 index_chunking_version·metadata_schema_version 사용
├── sync/plan.py                      # change_reason에 version_for 값, 216행 요약에 두 버전(R-10)
├── indexer/sync_cli.py               # current_index_version, build_runtime에서 QK_CODE_CHUNKING 읽기
├── config/registry.py, config/check.py   # QK_CODE_CHUNKING, 교차 검사 CODE_LIMIT_OVER_CONTEXT_BUDGET·CODE_INDEX_VERSION_UNREGISTERED(함수 안 지연 가져오기)
└── (.env.example 재생성)
tests/
├── fixtures/chunking/code/           # 합성 Java·Kotlin + 사람이 쓴 기대 JSON
├── unit/chunking/code/               # quickstart 1절 표의 시험 묶음(새 파일 이름은 test_code_* 접두어)
├── unit/sync/test_code_*.py, unit/indexer/test_code_*.py, unit/config/test_code_*.py, unit/sources/test_code_*.py
├── localdb/retrieval/test_code_provenance.py   # 기존 conftest 사용(tasks T025)
└── unit/test_boundaries.py           # tree_sitter·chunking.code 금지 대상 추가(검사 추가만)
```

**Structure Decision**: QK-CHK-002의 `chunking/` + `domain/chunking.py` 나눔을 따르고, 코드 청커는 `chunking/code/` 하위 패키지로 둔다.
해석기 의존은 `chunking/code/parse.py`에만 둔다. 동기화는 `SyncDependencies.code_chunking`(기본 `None`) 추가와 네 곳(`current_spec`, `sync/plan.py`의 `change_reason` 호출·요약 계산, `current_index_version`)만 바꾼다.

## 구현 Scope 승인이 필요한 것

| 구분 | 내용 |
| --- | --- |
| 새 파일 | `chunking/code/*`, ADR-022, 시험·고정값, `measurement/measure_code.py`(이미 있음, `--time-chunking` 추가) |
| 기존 파일 변경 | `pyproject.toml`·`uv.lock`, `config/sources.toml`(비활성 2항목 추가만), `domain/chunking.py`(추가만, `ChunkingSettings` 불변), `chunking/__init__.py`·`service.py`·`version.py`(Markdown 경로 불변, 해석기 지연 가져오기), `sync/keys.py`·`run.py`(`SyncDependencies.code_chunking` 기본 `None`, `IndexSpec` 메타 버전)·`plan.py`(87·216행), `indexer/sync_cli.py`(`current_index_version`, `build_runtime`, 읽기 명령의 설정 읽기), `config/registry.py`·`check.py`(두 교차 검사), `.env.example` 재생성, `tests/unit/test_boundaries.py`(검사 추가만) |
| 바꾸지 않음 | 마이그레이션·SQL, `adapters/postgres/`, `retrieval/`, `generation/`, `embedding/`, `security/`, `domain/keyword_rules.py`(대응표 추가는 켜는 변경), `devtools/measure.py`·`devtools/eval_index.py`, `config/source_reviews/`, 기존 시험 기대값(측정 출력 고정값 포함) |
| 의존성 | tree-sitter 3종 추가(research R-01). linux x86_64·aarch64·Windows 휠과 MIT 사용권을 PyPI에서 확인했다. 사람 확인 대상 |

## Phase 0·1 산출물

- Phase 0: [research.md](research.md) R-01~R-15. `NEEDS CLARIFICATION` 없음. spec이 plan으로 넘긴 항목은 다음 위치에서 정했다.

  | spec이 넘긴 항목 | 결정 위치 |
  | --- | --- |
  | 해석 방법·의존성 | R-01 |
  | 코드 상한·목표·안전 여유(FR-016) | R-03 |
  | 작은 청크 규칙(Assumptions) | R-04 |
  | Android 기본 형식·테스트 목록(FR-024·025) | data-model |
  | 버전 형식(FR-027) | R-08 |
  | 인덱스 버전 합치기(FR-028) | R-09 |
  | 문서별 비교·실행 기록(FR-029) | R-10 |
  | 메타데이터 저장 방식·마이그레이션 순서(FR-026) | R-11. 마이그레이션 없음 |
  | 자료원 이름·패턴·겹침 확인·ADR 번호(FR-032~034) | R-13 |
  | 성능 조건(SC-012) | R-14 |

  남는 위험은 네 가지다.
  - 새 Kotlin 문법 결함(R-01)
  - `locator` 노출(R-11)
  - 보정 계수가 코드에 맞는지(R-02: 토크나이저 기준은 보수 추정의 약 절반)
  - ADR 번호: `ADR-022`는 진행 중인 SCRUM-108 브랜치의 `ADR-021` 다음 번호다. 병합 순서에 따라 다시 확인한다(R-13)
- Phase 1: [data-model.md](data-model.md), [contracts/chunker.md](contracts/chunker.md), [quickstart.md](quickstart.md).

## 다른 명세에 넘기는 것

| 대상 | 넘기는 내용 |
| --- | --- |
| 자료원별 식별 명세(별도 세션 초안 QK-SYN-005) | 같은 종류 자료원 여러 개. 코드 자료원 켜기의 선행 조건(spec FR-036). 로드맵 백로그 추가는 사람이 정한다 |
| QK-STO-002 | `QK_CODE_CHUNKING=on` 새 인덱스 버전의 생성·평가·활성화, `INDEX_KEYWORD_RULES`와 고정값 시험 갱신(contracts 7절) |
| QK-EVL-001 | 코드 질문 문항을 골든셋에 넣을 때 코드 청크 평가. ADR-010 비교에 코드 청크를 포함할지 |
| QK-TRK-001 | `locator["code"]`(테스트 여부, 컴포넌트, 청크 종류)로 필터 추론 |
| QK-CHK-004 | 어노테이션·시그니처 메타데이터로 컨트롤러 ↔ OpenAPI ↔ Ktor 호출 ↔ 테스트 연결 |

## Complexity Tracking

| 항목 | 이유 | 더 단순한 대안을 고르지 않은 이유 |
| --- | --- | --- |
| 새 의존성 tree-sitter 3종(선택) | Java 21·Kotlin 2.3 문법의 선언 경계를 직접 해석하면 크기가 크고 결함 위험이 크다(R-01) | 자체 스캐너 — 문자열 템플릿·원시 문자열·제네릭 처리 부담. 언어 팩 — 실행 중 네이티브 코드 내려받기 |
| Kotlin 해석용 같은 길이 사본 | 문법 결함 하나로 ViewModel 11개가 대체 청킹된다(R-01) | 대체 청킹 감수 — ViewModel 심볼·컴포넌트 손실(2026-10-26 사용자 결정으로 사본 채택) |
