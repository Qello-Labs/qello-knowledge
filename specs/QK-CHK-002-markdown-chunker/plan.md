# Implementation Plan: QK-CHK-002 Markdown 청커·검색 헤더

**Branch**: `feat/SCRUM-101-gh-46-markdown-chunker` | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-CHK-002-markdown-chunker/spec.md`

## Summary

보안 필터를 통과한 Markdown 자료를 `markdown-it-py`로 최상위 블록 줄 범위까지만 해석하고, 절(최상위 제목) 단위로 블록을 탐욕적으로 쌓아
목표 512·상한 2,800(예상 토큰) 안의 청크로 나눈다. 청크 본문은 줄 범위 원문 그대로이고, 검색 헤더(위치 + 문서 제목 > 제목 경로)는 키워드 검색용
텍스트와 임베딩 입력 텍스트 앞에만 붙는다. 결과는 QK-STO-001 `ChunkInput`을 감싼 `ChunkDraft`로 넘기며 저장 스키마는 바꾸지 않는다.
상한은 대상 문서 79개를 bge-m3 토크나이저로 잰 결과(표에서 실제가 예상의 최대 2.3배)로 정했다. 근거는 [research.md](research.md)에 있다.

## Technical Context

**Language/Version**: Python 3.13 (QK-FND-001 R-01)

**Primary Dependencies**: `markdown-it-py==4.2.0`(색인 전용 선택 의존성 `index`와 `dev` 그룹, research R-01, 2026-10-21 사용자 결정). 그 밖에 표준 라이브러리.
런타임 `dependencies`는 비워 둔다

**Storage**: 없음. 청커는 저장하지 않는다. 결과 타입은 QK-STO-001 `ChunkInput` 그대로

**Testing**: pytest. 단위 시험만(외부 호출 0건). 실제 대상 확인은 `qk-dev source measure --chunk`(사람 실행, GitHub 약 83회, 0 Neurons)

**Target Platform**: 색인 CLI(GitHub Actions, 개발자 PC). Workers 질의 번들에는 들어가지 않는다

**Project Type**: 단일 Python 패키지 안의 도메인 타입 + 규칙 모듈 + 측정 도구 확장

**Performance Goals**: 필터 통과 79개(약 1.0 MB) 청킹 10초 이하(SC-011)

**Constraints**: 원문 줄 보존(FR-008), 겹침 없음(FR-009), 예상 토큰 상한 2,800(FR-013, research R-03), 결과·기록에 본문 없음(FR-006), 외부 호출 0(FR-003)

**Scale/Scope**: 공개 함수 3개(`chunk_markdown`, `chunk_screened`, `chunking_version`), 도메인 타입 약 9개, 측정 CLI 선택 인자 1개, 의존성 1개

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 템플릿 상태라 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다.

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01 근거가 있는 것만 | 해당 없음(답변을 만들지 않는다) | 해당 없음 |
| C-02 현재 상태는 원본에서 | 해당 없음 | 해당 없음 |
| C-03 검색 자료는 데이터 | 본문 안의 지시를 해석·실행하지 않고 줄 범위로 자르기만 한다 | 통과 |
| C-04 작게 시작 | Markdown만, 의존성 하나, 저장·CLI 추가 없이 측정 인자 하나 | 통과 |
| C-05 비용 상한 | 외부 호출 없음. 실측은 기존 수집 측정과 같은 GitHub 호출 수 | 통과 |
| C-06 교체 가능한 경계 | 해석기는 `chunking/blocks.py` 한 곳, 규칙 타입은 `domain/chunking.py`(표준 라이브러리만). 자료원 종류를 모르는 진입점 | 통과 |
| C-07 재현 | 원문 줄 그대로, 결정적 탐욕 쌓기, 해석기 버전 고정, 청킹 규칙 버전 `chk-md-<해시>` | 통과 |
| C-08 멱등·실패 격리 | 순수 함수, 자료별 실패 값, 부분 청크 없음 | 통과 |
| C-09 원본 읽기 전용 | 원본 호출 없음(측정 인자는 기존 읽기 경로 재사용) | 통과 |
| C-10 민감 정보 | 보안 필터 통과 자료만 받는다. 결과·요약·측정 출력에 본문 없음, 위치는 `safe_text` | 통과 |
| C-11 명세 먼저 | spec.md 2026-10-21 승인. plan 승인 전에는 구현하지 않는다 | 보류 — plan 사람 승인 |
| C-12 검증으로 닫기 | SC마다 시험(quickstart 1절) | 통과 |
| C-13 수치 조건 | 측정 조건(커밋, 토크나이저 버전, 표본, 추정식)을 research R-02·R-03에 고정 | 통과 |
| C-14 권한 확인 자료만 | 입력이 팀 공용 판정을 통과한 자료뿐 | 통과 |
| AGENTS.md 3.1 새 외부 서비스·모델 | 없음. 측정용 토크나이저 내려받기는 GET만, 데이터 전송 없음, 사용자 허용 | 통과 |
| AGENTS.md 3.3 인덱스 버전 | 첫 청킹 규칙 버전이라 바꿀 이전 버전 없음. 이후 변경은 버전 값으로 드러난다 | 통과 |
| AGENTS.md 3.5 비용 | 0 Neurons | 통과 |

Phase 1 설계 뒤 재점검: data-model이 FR-004(실패 시 청크 0)·FR-019(임베딩 입력 텍스트 비저장)를 타입 불변식으로, contracts가 FR-008~013을 진입점
보장으로 고정했다. 경계 검사에 `chunking`·`markdown_it` 금지 대상을 더한다(research R-10). 새 위반 없음. 보류는 C-11(plan 승인) 하나다.

## Project Structure

### Documentation (this feature)

```text
specs/QK-CHK-002-markdown-chunker/
├── spec.md
├── plan.md              # 이 파일
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── chunker.md       # chunk_markdown, chunk_screened, chunking_version
│   └── cli.md           # qk-dev source measure --chunk
├── measurement/
│   └── measure_inputs.py  # research R-02·R-03 재현용 집계 스크립트(원문 출력 없음)
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks 산출물
```

### Source Code (repository root)

```text
pyproject.toml                    # optional-dependencies.index, dev 그룹에 markdown-it-py==4.2.0
uv.lock
src/qello_knowledge/
├── domain/
│   └── chunking.py               # ChunkingSettings, 상태 값, StructureWarning, ChunkDraft, ChunkedContent, ChunkingSummary, ChunkingResult
├── chunking/
│   ├── __init__.py               # chunk_markdown, chunk_screened, chunking_version 공개
│   ├── blocks.py                 # markdown-it-py 호출, 최상위 블록, 원문 블록 메우기, 앞머리 메타데이터(R-05·R-06)
│   ├── sections.py               # 절 나누기, 제목 글자, 문서 제목(FR-011·017·018)
│   ├── header.py                 # 검색 헤더, 키워드 검색용 텍스트, 임베딩 입력 텍스트(R-09)
│   ├── split.py                  # 탐욕 쌓기, 상한 초과 블록 줄 나누기, 반복 머리글, 실패 판정(R-08)
│   ├── warnings.py               # 표 셀 수, 닫히지 않은 펜스(R-11)
│   ├── version.py                # chk-md-<해시>(R-07)
│   └── service.py                # chunk_markdown, chunk_screened, 실패 격리
└── devtools/
    ├── measure.py                # --chunk 결과 항목
    └── db.py                     # source measure --chunk 인자
tests/
├── fixtures/chunking/            # 합성 Markdown + 사람이 쓴 기대 JSON
├── unit/chunking/                # quickstart 1절 표의 시험 묶음
├── unit/devtools/test_measure.py # --chunk 출력(재생 전송)
└── unit/test_boundaries.py       # chunking·markdown_it 금지 대상 추가
```

**Structure Decision**: QK-EMB-001의 `embedding/` + `domain/embedding.py` 나눔을 따른다. 해석기 의존은 `chunking/blocks.py`에만 둬서 해석기를 바꿀 때
고칠 곳을 하나로 한다. 측정은 새 명령 대신 기존 `qk-dev source measure`에 선택 인자를 더해 수집·필터 경로를 재사용한다(research R-12).

## Phase 0·1 산출물

- Phase 0: [research.md](research.md) R-01~R-12. `NEEDS CLARIFICATION` 없음. spec이 plan으로 넘긴 항목의 결정 위치:
  안전 여유와 그 측정(FR-013) → R-03, 목표 크기 초기값(FR-014) → R-04, 청킹 규칙 버전 형식과 첫 값 `chk-md-20d966f730bb`(FR-012) → R-07,
  헤더·반복 머리글을 붙인 최대 줄 길이와 줄 길이 초과 비율(0%) → R-02, 성능 측정 조건(SC-011) → R-12. 측정은 `measurement/measure_inputs.py`로 재현한다.
  남는 위험은 R-03(1.2바이트/토큰보다 촘촘한 텍스트)과 R-11(셀 안 줄바꿈 뒤 줄이 문단으로 읽혀 표가 끝나는 경우는 경고 대상 아님)이다.
- Phase 1: [data-model.md](data-model.md), [contracts/chunker.md](contracts/chunker.md), [contracts/cli.md](contracts/cli.md), [quickstart.md](quickstart.md).

## 다른 명세에 넘기는 것

| 대상 | 넘기는 내용 |
| --- | --- |
| QK-SYN-001 | `chunk_screened` 결과로 저장·임베딩을 잇는다(contracts/chunker.md 마지막 표). `EMPTY`·`FAILED` 자료의 이전 청크 처리, 실행 기록에 `ChunkingSummary`, 첫 색인의 "입력 한도 초과" 건수 확인(research R-03 남는 위험) |
| QK-EMB-001 | 바꿀 것 없음. 상한을 정할 때 `estimate.estimated_tokens`를 같이 쓴다 |
| QK-RET-001 | `search_text` 기본값(헤더 + 본문)을 ADR-010 비교의 기준선으로 쓴다. 같은 제목 경로 중복의 상위 절 조회 한계. STO-001 data-model `search_text` 설명 정합성 |
| QK-EVL-001 | 목표 크기 512의 검색 평가와 조정(research R-04) |
| QK-ING-003 | ClickUp 페이지 위치 정보(블록 ID)를 위치 값에 더하는 방식, 다이어그램 블록 처리 |

## Complexity Tracking

| 항목 | 이유 | 더 단순한 대안을 고르지 않은 이유 |
| --- | --- | --- |
| 새 의존성 `markdown-it-py`(선택) | CommonMark 블록 경계를 직접 구현하면 크기 S를 넘고 경계 사례 결함 위험이 크다(R-01) | 표준 라이브러리 직접 구현 — 사용자 결정으로 의존성 채택 |
