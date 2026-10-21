# Task Contract: QK-CHK-002 Markdown 청커·검색 헤더 (WBS 1.6)

> Generated at: `2026-10-21`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-101` / https://tkv123.atlassian.net/browse/SCRUM-101 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: QK-CHK-002 / `specs/QK-CHK-002-markdown-chunker/spec.md`(2026-10-21 승인)
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#46`
- Branch: `feat/SCRUM-101-gh-46-markdown-chunker`
- Base branch: `main`. 2026-10-21 `origin/main` `53945e8`(#45 병합)에서 분기했다

## Objective

- 완료: QK-CHK-002 명세(`spec.md`)를 `/speckit-specify`로 작성하고 Codex 독립 검토 3회를 거쳐 사람 승인을 받았다(2026-10-21).
- 완료: `/speckit-plan` 설계 산출물을 만들고 Codex 독립 검토 4회를 거쳐 사람 승인을 받았다(2026-10-21).
- 완료: `/speckit-tasks` 작업 목록(`tasks.md`, 작업 38개 + 사람 단계 2개)을 Codex 독립 검토 2회를 거쳐 사람 승인을 받았다(2026-10-21).
- 이번 단계: `tasks.md` T001~T038 구현(우측 패널 Codex 세션, 2026-10-21 사용자 결정). 사람 단계 H01·H02는 구현 뒤 사람이 한다.
- 함께: 로드맵 진행 상태 열을 GitHub Issue 상태에 맞게 갱신한다(`scripts/roadmap_status.py --write`).

## Scope

- `specs/QK-CHK-002-markdown-chunker/spec.md`, `checklists/requirements.md`(승인됨, 바꾸려면 다시 승인)
- 설계 산출물: 같은 디렉터리의 `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`, `measurement/measure_inputs.py`(측정 재현용, 원문 출력 없음). 승인됨, 바꾸려면 다시 승인
- 작업 목록: 같은 디렉터리의 `tasks.md`(승인됨). 구현 중 체크 표시와 진행 기록은 고친다.
- 구현(tasks.md, plan.md Project Structure):
  - 새 파일: `src/qello_knowledge/domain/chunking.py`, `src/qello_knowledge/chunking/`(`__init__`, `blocks`, `sections`, `header`, `split`, `warnings`, `version`, `service`),
    `tests/unit/chunking/`, `tests/fixtures/chunking/`
  - 고치는 파일: `pyproject.toml`(선택 의존성 `index`와 `dev` 그룹에 `markdown-it-py==4.2.0`만), `uv.lock`, `tests/unit/test_boundaries.py`,
    `src/qello_knowledge/devtools/measure.py`·`db.py`(`--chunk`), `tests/unit/devtools/test_measure.py`,
    `specs/QK-CHK-002-markdown-chunker/measurement/measure_inputs.py`(T036, 계약과 다를 때만)
- `.specify/feature.json`(git 무시 파일, 로컬 전용)은 이 명세 디렉터리를 가리키게 한다.
- `docs/sdd/roadmap.md`의 `상태`·`진행` 열(스크립트 출력만, 손으로 고치지 않음)
- `TASK.md`
- 명세가 다룰 동작:
  - 입력: QK-SEC-001 필터를 통과한 Markdown 자료(저장소 문서. ClickUp 페이지도 같은 청커를 쓸 수 있게 자료원에 묶이지 않는 경계)
  - 출력: 저장 스키마의 청크 입력(`ChunkInput`: `ordinal`, `locator`, `body`, `search_text`, `heading_path`, `chunking_version`)
  - 제목 경로로 만든 검색 헤더. 원본이 제목을 주지 않으면 본문에서 채우는 규칙(QK-ING-001 research)
  - 재현성: 같은 원본·같은 설정이면 같은 청크 경계와 해시, 모든 청크에 경로·줄 범위(constitution C-07)
  - 청크 크기 상한: bge-m3 입력 한도 8,192토큰에서 안전 여유를 뺀 예상 토큰 상한(ADR-002, 스파이크 W-02, `embedding/estimate.py`와 같은 계산)
  - Markdown 구조 규칙: 코드 펜스 안의 `#`는 제목이 아님, 상한 이하인 표·코드 블록은 가르지 않음, 코드 블록 언어 표시를 판정 근거로 쓰지 않음
    (`clickup-migration-check.md` 2절·F-03·F-04, `clickup-writing-rules.md`)
  - `search_text` 기본값과 QK-RET-001(FR-CHK-07, ADR-010)의 경계, `chunking_version`이 바뀌는 조건(형식과 첫 값은 `plan.md`에서 정한다)

## Explicit exclusions

- 위 구현 목록 밖의 `src/`·`tests/` 변경. 런타임 `dependencies` 추가, `markdown-it-py` 밖의 새 의존성.
- `tests/fixtures/chunking/` 기대값 JSON을 구현 결과로 덮어쓰기, 시험 삭제·`skip`·`xfail`(AGENTS.md 9절).
- 코드 청킹(QK-CHK-001), 키워드 검색 텍스트 규칙(FR-CHK-07, ADR-010, QK-RET-001), ClickUp 수집(QK-ING-003),
  임베딩·저장·동기화 실행(QK-EMB-001, QK-SYN-001).
- QK-ING-001·QK-SEC-001·QK-STO-001 코드와 승인된 명세 변경. 저장 스키마 변경.
- 로드맵 `상태`·`진행` 열 외의 `docs/sdd/roadmap.md` 내용, `docs/sdd/constitution.md`, `.specify/memory/constitution.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정.
- 원본 자료원에 쓰기.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다. 명세 예시는 합성 문서로 쓴다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음. plan 측정(research R-02·R-03)은 이미 활성화된 `dnd-backend-docs`의 로컬 사본(커밋 `6aeccd0`)을 읽었다(GitHub API 0회)
- 외부 API로 보내는 데이터: 해당 없음(청커는 외부 호출이 없다). plan 측정용으로 Hugging Face에서 `BAAI/bge-m3` 토크나이저 파일을 내려받았다(GET만, 문서 데이터 전송 없음, 프로젝트 의존성 아님)
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons
- 인덱스 버전 변경: 없음. 첫 `chunking_version`은 `chk-md-20d966f730bb`(research R-07)이고 저장된 청크가 아직 없다. 이미 색인된 청크가 없어 재임베딩 대상이 없다(추론, QK-SYN-001 미구현)

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-CHK-002-markdown-chunker/` | Byuntil | 사람 리뷰(명세 승인) |
| `docs/sdd/roadmap.md` 상태 열 | Byuntil | 사람 리뷰 |
| `TASK.md` | Byuntil | 사람 리뷰 |
| `src/qello_knowledge/chunking/`, `domain/chunking.py`, `devtools/` 변경, `pyproject.toml`·`uv.lock` | Byuntil | 사람 리뷰 |
| `tests/unit/chunking/`, `tests/fixtures/chunking/`, `tests/unit/devtools/test_measure.py`, `tests/unit/test_boundaries.py` | Byuntil | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-21 `origin/main`(`53945e8`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
```

## Completion criteria

- `spec.md`가 사람 리뷰로 승인된다 — 리뷰 기록
- (구현 단계) 같은 입력을 두 번 청킹하면 경계와 해시가 같고, 모든 청크에 경로·줄 범위가 있다 — 단위 시험
- (구현 단계) 어떤 청크도 예상 토큰 기준 상한(임베딩 입력 한도 - 안전 여유)을 넘지 않고, 코드 펜스 안의 `#`은 제목으로 나뉘지 않는다 — 단위 시험.
  실제 한도 대비 안전 여유는 `plan.md`의 대상 문서 측정으로 정한다(명세 FR-013)

## Decisions

- 2026-10-21 사용자 결정: WBS 1.6 진행. 에이전트가 Jira `SCRUM-101`(SCRUM-42 하위 작업, 자동 생성 Secret이 없어 직접 생성)과 GitHub `#46`을 만들었다.
- 2026-10-21 사실: 요구사항 FR-CHK-01~05, 08은 저장소에 원문이 없다. QK-SEC-001처럼 백로그 제목·constitution·관련 조사에서 요구를 끌어내고 명세 Assumptions에 적는다.
- 2026-10-20 사용자 결정(이어받음): 단계 게이트 0.G 미완료 상태로 Phase 1을 계속 진행한다.
- 2026-10-21 사용자 결정: TASK.md 초안 승인, 명세 작성 시작.
- 2026-10-21 사실: `spec.md`·`checklists/requirements.md` 초안 작성(확인 필요 표시 0건, 기본값을 고른 결정은 Assumptions에 기록). 사람 검토 전이다.
- 2026-10-21 사실: `roadmap_status.py --write`로 상태 열 갱신(1.5 ✅, 1.6 🔄 #46, 1.7 ✅ #42, Phase 1 ✅ 6 · 🔄 1 / 13).
- 2026-10-21 사실: Codex 패널이 명세를 두 번 검토했다(1차 변경 요청 11건, 2차 1차 지적 8건 해소·3건 일부 + 새 지적 5건). 모두 반영했다.
- 2026-10-21 사용자 결정: 1차 검토 권장안 승인. 본문 없는 절도 제목 줄 청크를 만들고, 같은 제목 경로의 상위 절 조회 한계는 기록만 하고 QK-RET-001로 넘긴다.
- 2026-10-21 사실: 2차 검토 반영으로 완료 조건의 상한을 "예상 토큰 기준 상한"으로, 첫 `chunking_version` 결정 시점을 `plan.md`로 바꿨다(명세 FR-012·FR-013).
  Jira SCRUM-101·GitHub #46 본문의 같은 문장("임베딩 입력 한도를 넘지 않고")은 아직 그대로다.
- 2026-10-21 사용자 결정: QK-CHK-002 명세 승인(Codex 3차 검토 "승인" 권고 뒤). 저장소 관례대로 `spec.md`의 Status 표기는 바꾸지 않고 이 기록으로 승인을 남긴다.
- 2026-10-21 사실: Jira SCRUM-101·GitHub #46 본문을 명세에 맞춰 고쳤다(명세 링크 "승인", 상한 문장 2곳을 "예상 토큰 기준 상한"으로). 앞의 "아직 그대로다" 기록은 해소됐다.
- 2026-10-21 사용자 결정: Markdown 해석기는 `markdown-it-py==4.2.0`을 색인 전용 선택 의존성(`index`)과 `dev` 그룹으로 둔다(research R-01). 런타임 `dependencies`는 비워 둔다.
- 2026-10-21 사용자 결정: 상한 근거 측정은 로컬 bge-m3 토크나이저로 한다(research R-03). 결과: 표에서 실제 토큰이 예상의 최대 2.30배, 상한 예상 2,800·목표 512로 정했다.
- 2026-10-21 사실: plan 산출물(plan·research·data-model·contracts·quickstart) 작성. 사람 승인 전이다.
- 2026-10-21 사실: Codex 패널 plan 1차 검토 "변경 요청"(높음 2, 중간 7, 낮음 1). 해석기 동작 지적 5건을 직접 재실행해 확인하고 모두 반영했다. 첫 청킹 규칙 버전 `chk-md-20d966f730bb`.
- 2026-10-21 사실: Codex plan 2차 검토 "변경 요청"(1차 7건 해소·3건 일부, 새 지적 높음 2·중간 3) 반영. 블록을 나무 구조로 재귀 분할하고 자식 사이 줄 덮기 규칙을 두었다(R-05·R-08). 펜스 닫힘은 토큰 내용 줄 수로 판정한다(12사례 확인, R-11). SC-011 완료 판정 입력을 커밋 `6aeccd0` 79개로 고정했다(R-12).
- 2026-10-21 사실: Codex plan 3차 검토 "변경 요청"(높음 해소, 중간 3·낮음 2) 반영. 펜스 닫힘은 LF 개수 기준 + 해석 입력을 LF로 끝냄(16사례), 표 셀 수는 컨테이너 표지를 N번까지 제거(6사례), SC-011 통과 조건에 CHUNKED 79·청크 수 추가.
- 2026-10-21 사용자 결정: QK-CHK-002 plan 승인(Codex 4차 검토 "승인" 권고 뒤).
- 2026-10-21 사실: `tasks.md` 작성(작업 38개 + 사람 단계 2개). 작성 중 data-model `ChunkDraft`에 `estimated_tokens` 필드를 더했다(요약이 `domain` 밖 `embedding`을 가져오지 않게). 승인된 plan 산출물의 보완이라 tasks 승인 때 함께 확인받는다.
- 2026-10-21 사실: Codex tasks 1차 검토 "변경 요청"(높음 1, 중간 5, 낮음 2) 반영. T006→T008 의존성과 TDD 순서 명시, 경고 판정 버전 불변 시험을 US4로, `ParsedDocument` 계약(앞머리 제목·펜스·표 정보), 기대 JSON `input`/`expected` 분리와 최종 필수 키 검사(T037), 설정 생성 시 검증, `ChunkDraft` 민감 필드 `repr=False`, `estimated_tokens` 실제 텍스트 대조 불변식.
- 2026-10-21 사실: Codex tasks 2차 검토 "수정 후 승인"(낮음 3건: T016 `parse_document`·설정 검증 표기, T030 `content_newlines`) 반영.
- 2026-10-21 사용자 결정: `tasks.md`와 data-model 보완 승인. 구현은 우측 패널 Codex 세션이 한다. 이 Claude 세션은 Scope 갱신·커밋·검토 조율을 맡는다(구현을 같은 세션이 승인하지 않는다, AGENTS.md 2절).

## Execution handoff (2026-10-21)

- 실행 범위: QK-CHK-002 T001~T038 구현·시험 완료. 각 Phase의 RED/GREEN·판단 기록은 `specs/QK-CHK-002-markdown-chunker/tasks.md` 끝에 남겼다.
- 현재 상태: `PASS`(실행 에이전트 범위 T001~T038) — 사용자 결정으로 T033의 S311 한 줄 예외를 적용하고 필수 검증을 다시 실행해 통과했다. 이전 BLOCKED 사유는 해소됐다. 다른 suppress·린트 설정 변경 없음.
- 검증: 로컬 DB 포함 전체 1099 passed / 외부 2 deselected(9.05초). preflight(490파일)·diff 공백·ruff check·ruff format(325파일)·로컬 DB 준비·`uv lock --check` 모두 통과. 실제 `.env`를 읽지 않도록 DB 명령은 `--env-file /dev/null`, Docker는 `COMPOSE_DISABLE_ENV_FILE=1` 사용. 자세한 명령·환경 제약은 tasks 실행 기록 참조.
- H01·H02 및 독립 검증·승인은 별도 세션/사람에게 남긴다. 이 세션의 시험 실행은 독립 승인 증거로 쓰지 않는다. 외부 호출·스테이징·커밋·push·브랜치 변경 0건.
- 인덱스 생성·활성화 없음, embedding model `@cf/baai/bge-m3`(추정만), chunking version `chk-md-20d966f730bb`, 검색 품질 평가 세트 해당 없음. 합성 입력 79개·1,447,811바이트 성능 회귀 시험 약 0.41초, 0 Neurons.
- 2026-10-21 사용자 결정: `tests/unit/chunking/test_perf.py`의 시드 고정 합성 데이터 `random.Random(20261021)`에 저장소 관례(`tests/localdb/store/builders.py:56`, `devtools/bench.py:149`)와 같은 한 줄 예외 `# noqa: S311 - 재현 가능한 합성 데이터용이다`를 허용한다. 암호 용도가 아닌 오탐이고 규칙 전체를 끄지 않는다.
- 2026-10-21 사실: Claude 세션이 구현을 독립 리뷰했다(`/harness-review`, 권고 승인, 낮음 4건). 사용자 결정으로 Codex가 낮음 항목(설정 오류 메시지·주석 한국어화, import 위치)을 고쳤다. 재검증: ruff·format·preflight·diff 통과, `QK_REQUIRE_LOCALDB=1 uv run pytest` 1099 passed.
- 2026-10-21 사실: 사용자 요청으로 Claude 세션이 H01(SC-011 완료 판정)을 대신 실행했다. 79개 모두 `CHUNKED`, 청크 1,291개, 0.182초로 통과. 외부 호출 0건. H02(실제 `main` 관찰, GitHub 약 83회)는 미실행이다.
