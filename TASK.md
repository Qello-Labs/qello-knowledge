# Task Contract: QK-CHK-001 코드 청커(Java·Kotlin, Android 컴포넌트, 테스트)·코드 메타데이터 (WBS 2.2)

> Generated at: `2026-10-26`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-118` / https://tkv123.atlassian.net/browse/SCRUM-118 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: `QK-CHK-001` / `specs/QK-CHK-001-code-chunker/spec.md`(2026-10-26 승인, 같은 날 개정판 재승인)
- 팀 스프린트 ID: `QELLO-S2026-W44`
- GitHub Issue: `#63`
- Branch: `feat/SCRUM-118-gh-63-code-chunker`
- Base branch: `main`. 2026-10-26 `origin/main` `d7c9e3f`(#60 병합)에서 분기했고, 첫 커밋은 `1c9a9f6`(#62 병합) 위에 있다.
  같은 날 PR #65 충돌을 풀려고 `369b2ec`(#64 병합)를 병합했다. 충돌난 `TASK.md`는 이 계약을 남겼고, 이전 `main`의 계약(QK-BOT-001)은 git 이력에 남긴다

## Objective

- 완료: QK-CHK-001 `spec.md`를 쓰고 독립 검토 2회(변경 요청, 변경 요청)를 거쳐 사람 승인을 받았다(2026-10-26).
  plan 측정·검토 결과로 고친 판을 다시 승인받았다(2026-10-26). 바꾸려면 다시 승인을 받는다.
- 완료: `/speckit-plan` 설계 산출물(`plan.md`·`research.md` R-01~R-15·`data-model.md`·`contracts/chunker.md`·`quickstart.md`·`measurement/measure_code.py`)을 썼다.
  독립 검토 2회(변경 요청, 경미한 변경 요청)를 거쳐 사람 승인을 받았다(2026-10-26, tree-sitter 의존성 채택 포함). 바꾸려면 다시 승인을 받는다.
- 완료: `/speckit-tasks`로 작업 목록(`tasks.md`, 작업 48개 T001~T048 + 사람 단계 4개 H01~H04)을 쓰고 독립 검토 1회(변경 요청)를 반영해 사람 승인을 받았다(2026-10-26). 바꾸려면 다시 승인을 받는다.
- 다음 단계: 구현(T001~). 구현 시작 시점은 사람이 정한다(1.G 미완료). 시작 전 확인할 것: 실행 전 사람 허용(T001 PyPI 내려받기, T032 `.env.example` 재생성).
- tasks가 반드시 담을 것(plan이 넘긴 항목):
  - plan "구현 Scope 승인이 필요한 것" 표의 파일 범위
  - quickstart 1절 시험 묶음
  - 해석기 버전 상수와 `importlib.metadata` 비교 시험(research R-08)
  - 지연 가져오기·질의 경로 경계 시험(R-15)
  - 켜짐 방지 검사(R-09)
  - 비활성 자료원 두 개와 ADR-022(R-13)
  - `--time-chunking` 추가(R-14)
  - 사람 단계: 로컬 실측(quickstart 4절)과 ADR-022 승인

## Scope

- `specs/QK-CHK-001-code-chunker/`의 `spec.md`, `checklists/requirements.md`. spec 승인 뒤 같은 디렉터리의 `plan.md`·`research.md`·`data-model.md`·`quickstart.md`·`contracts/`·`tasks.md`
- plan 단계의 읽기 전용 측정(대상 저장소 로컬 사본의 파일 수·크기·구문 구조 집계, 원문 비출력). 측정 스크립트는 명세 디렉터리 `measurement/`에 둔다
- `TASK.md`(이 파일)
- 코드 자료원 결정 기록 새 파일 `docs/sdd/decisions/ADR-022-code-sources.md`(spec FR-034, plan research R-13)와 `config/sources.toml`의 비활성 코드 자료원 두 개 등록(spec FR-032·033).
  2026-10-26 사용자 결정으로 자료원 추가 규칙을 spec에 넣었다. 작성 시점은 plan·구현 단계다
- 구현 범위(tasks.md T001~T048, plan "구현 Scope 승인이 필요한 것" 표. 2026-10-26 tasks와 함께 승인):
  - 새 파일:
    - `src/qello_knowledge/chunking/code/`(`__init__`, `parse`, `units`, `symbols`, `header`, `split`, `version`, `service`)
    - `docs/sdd/decisions/ADR-022-code-sources.md`(Proposed)
    - `tests/fixtures/chunking/code/`(합성 Java·Kotlin + 사람이 쓴 기대 JSON)
    - `tests/unit/chunking/code/`(`__init__`, `helpers`, `test_code_*.py`)
    - `tests/unit/sync/test_code_*.py`, `tests/unit/indexer/test_code_sync_cli.py`, `tests/unit/config/test_code_check.py`, `tests/unit/sources/test_code_sources.py`
    - `tests/localdb/retrieval/test_code_provenance.py`(기존 conftest 사용, 새 conftest·`# noqa` 없음)
  - 기존 파일 변경:
    - `pyproject.toml`·`uv.lock`(tree-sitter 3종)
    - `config/sources.toml`(비활성 2항목 추가만)
    - `src/qello_knowledge/domain/chunking.py`(추가만, `ChunkingSettings` 불변)
    - `chunking/__init__.py`·`service.py`·`version.py`(Markdown 경로·`chunking_version` 불변)
    - `sync/keys.py`(함수 추가만), `sync/run.py`(`SyncDependencies.code_chunking`, `current_spec`), `sync/plan.py`(87·99·216행)
    - `indexer/sync_cli.py`, `config/registry.py`·`check.py`, `.env.example` 재생성
    - `specs/QK-CHK-001-code-chunker/measurement/measure_code.py`(`--time-chunking` 추가)
    - `tests/unit/test_boundaries.py`(검사 추가만)
  - 바꾸지 않음:
    - 마이그레이션·SQL, `adapters/`, `retrieval/`, `generation/`, `embedding/`, `security/`, `domain/keyword_rules.py`
    - `devtools/measure.py`·`devtools/eval_index.py`, `config/source_reviews/`
    - 기존 시험 기대값(0건 변경), 기존 시험 도우미(`tests/unit/sync/helpers.py`, `tests/localdb/*/conftest.py`)

## Explicit exclusions

- Scope 구현 범위 밖의 코드 변경, 마이그레이션 추가, 기존 시험 기대값 변경, 실제 색인 실행. 구현은 tasks 승인과 사람이 정한 시작 시점 전에는 하지 않는다.
- API·컨트롤러·네트워크 호출·테이블 교차 관계(QK-CHK-004), 인덱스 버전 생성·평가 게이트·활성화(QK-STO-002),
  OpenAPI·마이그레이션 수집(QK-ING-006·007), 검색 동작 변경(QK-RET-001), ADR-010 확정(QK-EVL-001 비교 리포트 뒤), 빌드 설정·리소스 파일 색인.
- 코드 자료원을 실제로 켜는 일(`enabled = true`), 개인 정보 확인 기록(`config/source_reviews/`) 작성, 첫 측정·첫 색인, 코드 청킹 켜기 설정을 켜는 일. 사람이 결정 기록 승인 뒤 별도로 한다.
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, 기존 ADR, `AGENTS.md`, `CLAUDE.md`, `.claude/**`, `.github/` 수정.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 이번 단계는 없다. 명세가 정할 후보는 백엔드 저장소 코드 경로(`dnd-side-project/dnd-15th-2-backend`, 기존 자료원 `dnd-backend-docs`와 같은 저장소)와
  Android 저장소(`dnd-side-project/dnd-15th-2-android`, 새 자료원). 둘 다 공개 저장소다. 새 자료원이면 `templates/decision-record.md`로 결정을 남긴다(AGENTS.md 3.1)
- 외부 API로 보내는 데이터: 이번 단계 0건. 운영에서는 코드 청크 본문이 Workers AI 임베딩(ADR-002)으로 간다
- 예상 임베딩·생성 호출량과 무료 한도 대비: 이번 단계 0 Neurons. plan 실측(research R-02)으로 운영 첫 색인은 보정 계수 기준 본문 코드 약 2,960 Neurons, 테스트 포함 약 7,000이다.
  토크나이저 기준 본문은 약 1,360이다. 하루 색인 예산 5,000이라 첫 활성화는 본문 코드만 권고한다(ADR-022)
- 내려받기: 구현 T001의 `uv lock`·`uv sync`가 PyPI에서 tree-sitter 휠 3종을 내려받는다(실행 전 사람 허용). 운영 인스턴스(OCI aarch64)도 다음 배포의
  `uv sync --locked --extra index`에서 같은 휠을 받는다. aarch64 휠은 PyPI에서 확인했다(research R-01)
- 인덱스 버전 변경: 이번 단계 없음. 구현은 코드 청킹 기본 꺼짐으로 배포해 인덱스 버전·`meta-v1`·저장 스키마가 그대로다(spec FR-030). 켜짐 계산 코드(`chk-md+chk-code`, `meta-v2`)는 미리 두지만,
  켜짐 인덱스 버전이 키워드 규칙 대응표에 없으면 `qk-index check`·`run`이 멈춘다. 켜는 변경(QK-STO-002 뒤)에서 대응표에 새 인덱스 버전을 더하고 활성화한다(AGENTS.md 3.3). 마이그레이션은 없다

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-CHK-001-code-chunker/`, `TASK.md` | tkv00 | 사람 리뷰 |
| 새 코드 자료원 결정 기록(`docs/sdd/decisions/`), `config/sources.toml`(비활성 코드 자료원 등록) | tkv00 | 사람 리뷰 |
| `src/qello_knowledge/chunking/code/`, `domain/chunking.py`, `chunking/`·`sync/`·`indexer/sync_cli.py`·`config/` 변경, `pyproject.toml`·`uv.lock` | tkv00 | 사람 리뷰 |
| `tests/`의 새 `test_code_*.py`·픽스처, `tests/unit/test_boundaries.py`(검사 추가만) | tkv00 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-26 `origin/main`(`d7c9e3f`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
uv run qk-migrate   # 두 번 실행, 두 번째는 applied=0(마이그레이션 수 불변)
uv run qk-migrate
QK_REQUIRE_LOCALDB=1 uv run pytest
```

문서 단계(spec·plan·tasks)는 앞 네 줄만 해당한다. 구현 단계는 전부 실행한다(tasks T048). 측정 스크립트는 ruff 검사 대상이다.

## Completion criteria

문서 단계(spec·plan·tasks 승인)는 끝났다. 아래는 구현 단계의 완료 조건이다(2026-10-26 tasks 검토 M7 반영, 같은 날 tasks와 함께 승인).

- 꺼짐 불변: 꺼짐 기본 설정에서 인덱스 버전 `iv-4c0bc4fcc642`·`meta-v1`·`chk-md-20d966f730bb`, Markdown 청킹 결과, 기존 고정값 시험이 그대로다 — 단위 시험(SC-008·SC-011, tasks T006·T010·T027)
- 청크 정확성: 합성 Java·Kotlin 픽스처의 결과가 사람이 쓴 기대값과 같다. 원문 청크가 모든 공백 아닌 줄을 한 번씩 덮고, 결정적이며 국소적이다 — 단위 시험(SC-001~004, T013~T015·T021·T047)
- 크기·실패: 상한·실패·대체 청킹·맥락 줄 생략이 기대대로 동작하고, 한 파일 실패가 다른 파일을 멈추지 않는다 — 단위 시험(SC-005·SC-009, T037·T042)
- 메타데이터·판정: `locator["code"]` 13개 키, Android·테스트 판정이 기대대로이고, 저장 후 출처 정보로 돌아온다 — 단위·로컬 DB 시험(SC-006·SC-007, T024·T025·T034)
- 켜짐 차단과 연결: 켜짐 인덱스 버전이 대응표에 없으면 `qk-index check`·`run`이 멈춘다. 켜짐 재계획의 다시 처리가 0이다 — 단위 시험(SC-011, T027~T029)
- 비노출과 전송 직전 검사: 기록·요약·로그에 원문이 0건이고, 요약 청크를 포함해 모든 임베딩 입력이 전송 직전 검사를 거친다 — 단위 시험(SC-009, T042·T043)
- 자료원·결정 기록: 비활성 자료원 두 개가 설정 검사를 통과하고, 범위가 겹치지 않으며, ADR-022(Proposed)가 FR-034 항목을 담는다 — 단위 시험·리뷰(SC-013, T039~T041)
- 기본 검증 통과(Windows 기준선 3건 별도) — T048
- 성능 완료 판정(SC-012), 로컬 실측, ADR-022 승인, 언어 팩 폴더 결정은 사람 단계 H01~H04에서 한다

## Decisions

- 2026-10-26 사실: QK-CHK-001과 겹치는 명세 디렉터리·GitHub Issue·PR·브랜치가 없음을 확인했다. Jira는 이 세션에서 조회하지 못했다(Atlassian MCP 미인증).
- 2026-10-26 사실: 기술 선행 QK-CHK-002(#46)는 완료다. 단계 게이트 1.G는 미완료다(1.11 QK-BOT-001 #58 진행 중, 1.12 QK-EVL-001 시작 전).
- 2026-10-26 사용자 결정: QK-BOT-001은 코드 청커와 무관하므로 1.G 미완료 상태로 QK-CHK-001을 진행한다. 작성 세션은 명세 작성부터 하고,
  QK-EVL-001에 걸린 ADR-010(식별자 분해 규칙)과 새 인덱스 버전 활성화(QK-STO-002)는 열린 항목으로 둔다(작성 세션 판단, 사람 확인 대상).
- 2026-10-26 사실: 사용자 요청으로 GitHub Issue #63을 작업 폼 형식으로 만들었고, `Jira subtask` 워크플로가 `SCRUM-42` 아래 `SCRUM-118`을 자동 생성했다.
  하위 작업의 Jira 스프린트는 상위 이슈를 따라 `Backend·Sprint 3`(10/12–10/18)이라 팀 스프린트 ID `QELLO-S2026-W44`와 어긋난다. 새 스프린트로 옮기는 일은 사람이 한다.
- 2026-10-26 사용자 결정: 이 TASK.md를 승인했다("TASK.md 승인"). `/speckit-specify`로 `spec.md` 초안을 쓴다.
- 2026-10-26 사실(specify): `specs/QK-CHK-001-code-chunker/spec.md`(US 5개, FR-001~029, SC-001~011)와 `checklists/requirements.md`를 썼다. [NEEDS CLARIFICATION]은 0개다.
  작성 세션 판단 6건(요약 청크 겹침 허용, 심볼 경로를 제목 경로 자리에 저장, 구문 해석 실패 시 대체 청킹, Android 컴포넌트 이름 규칙 판정, 인덱스 버전에 두 청킹 규칙 버전 반영,
  성능 기준 60초)은 사람 확인 대상이다. 외부 호출 0건, 0 Neurons. 다음은 별도 에이전트의 독립 검토다.
- 2026-10-26 사실: spec 독립 검토(작성에 관여하지 않은 별도 서브에이전트) 판정은 변경 요청이다(높음 2, 중간 12, 낮음 6).
  H1(검색 문맥 확장은 `section_first`만 써서 요약 청크가 상위로 붙지 않음, `retrieval/service.py:216`, `0005_retrieval.sql:96-104`, QK-RET-001 FR-014),
  H2(인덱스 버전이 바뀌면 동기화가 바뀐 문서 처리를 멈춤, QK-SYN-001 FR-020, `sync/run.py:43-45`), M6(문서별 비교가 청킹 버전 하나를 씀, `sync/plan.py:87`, `sync/decide.py:11`),
  M8(Context 예산 2,000 < 청크 상한 2,800, `domain/retrieval.py:86`, `retrieval/pack.py:63-64`)은 작성 세션이 코드로 다시 확인했다. 사람 결정 대기.
- 2026-10-26 사용자 결정(검토 반영): H1 청커에서 보완한다(요약 청크는 독립 검색 대상, 멤버 청크 임베딩 입력·키워드 텍스트에 형식 선언 맥락 줄을 붙임. QK-RET-001 불변).
  H2 코드 청킹 켜기 설정을 기본 꺼짐으로 두고 꺼져 있으면 인덱스 버전 재료가 지금과 같게 한다(켜는 일은 QK-STO-002 뒤). M12 작은 청크 규칙은 plan 측정 뒤 다시 정한다.
  M11 자료원 추가(비활성 코드 자료원 두 개 등록, 결정 기록)도 spec에 넣는다.
- 2026-10-26 사실: 위 결정과 나머지 지적(M1~M10, L1~L6)을 spec에 반영했다. US6(켜기 설정)·US7(코드 자료원), FR-029~035, SC-011·013을 더했다. M7은 심볼 이름에 매개변수 형식을 넣어 풀었다(작성 세션 판단).
  M1은 Android import가 있는 파일에서만, 상위 클래스만으로 판정하게 했고, L3은 테스트 판정에서 파일 이름 규칙을 뺐다(작성 세션 판단). 같은 검토자의 재검토를 받는다.
- 2026-10-26 사실: 같은 검토자의 재검토 판정은 변경 요청이다(이전 20건 중 해소 18·부분 해소 2·미해소 0, 새 지적 높음 1·중간 2·낮음 6). 검토자는 M1·M7·L3 처리를 타당하다고 했다.
  N1(같은 종류 자료원을 둘 이상 켜면 동기화가 `duplicate_source_kind`·`source_replacement`로 멈추고, 저장 문서를 자료원 종류로만 불러와 서로 내릴 수 있음,
  `sync/identity.py:17-25`, `adapters/postgres/sync_store.py:73-83`, `0004_sync.sql:19-20`, QK-SYN-001 spec 462-464행이 이 일을 "같은 종류 자료원을 더하는 명세"에 넘김)은
  작성 세션이 코드로 다시 확인했다. N1(맡을 명세)과 N3(코드 메타데이터 스키마 버전 해석, AGENTS.md 3.3)은 사람 결정 대기다.
- 2026-10-26 사용자 결정(재검토 반영): N1 자료원별 식별(저장 유일성·문서 불러오기·검사 풀기)은 별도 명세로 넘긴다. 이 명세는 비활성 등록만 하고 활성화 순서에 그 명세를 선행 조건으로 적는다.
  N3 메타데이터 스키마가 바뀌면 `meta-v1`을 올린다(AGENTS.md 3.3). 그래서 저장 스키마 마이그레이션과 새 메타데이터 스키마 버전은 기본 꺼짐 배포가 아니라 코드 청킹을 켜는 변경에 함께 넣는다.
  N2 맥락 줄이 상한을 넘으면 바깥 형식부터 덜어 내고 "맥락 줄 생략" 경고를 남긴다.
- 2026-10-26 사실: 위 결정과 N4~N9, L6 잔여를 spec·TASK.md·checklist에 반영했다(FR-036 추가, FR-018·020·021·026·030, US5-6, SC-005·009·011·013). 자료원별 식별 명세는 로드맵 백로그에 아직 없다.
  백로그 추가와 WBS 배치는 사람이 정한다(로드맵 수정은 이 작업의 제외 범위). 재검토는 다시 받지 않았다.
- 2026-10-26 사용자 결정: QK-CHK-001 `spec.md`를 승인했다("QK-CHK-001 spec.md 승인", 재검토 N1~N9 반영본). 바꾸려면 다시 승인을 받는다. 다음 단계는 `/speckit-plan`이다.
- 2026-10-26 사실(plan 준비): plan 측정 입력 상태를 확인했다. `BAAI/bge-m3` 토크나이저는 QK-CHK-002 R-03과 같은 리비전 `5617a9f…`가 로컬 캐시에 있다. 대상 저장소 두 곳
  (`dnd-side-project/dnd-15th-2-backend`, `dnd-side-project/dnd-15th-2-android`, 둘 다 공개, 기본 브랜치 `main`, GitHub 보고 크기 약 5.9 MB·2.5 MB)은 로컬 사본이 없다.
  구문 분석 라이브러리 후보는 설치돼 있지 않다. 사본 받기와 후보 라이브러리 임시 설치(`uv run --with`, 프로젝트 의존성 추가 아님)는 다운로드라 사람 확인 뒤 한다. 외부 호출 0 Neurons.
- 2026-10-26 사실: 자료원별 식별 명세의 백로그 추가 초안은 별도 세션(`자료원별 식별 명세 백로그 추가 초안`)에서 진행 중이다.
- 2026-10-26 사실(plan 측정): 사용자 허용으로 대상 저장소 두 곳을 `../qk-targets/`에 읽기 전용으로 클론했다(백엔드 `6aeccd0`, Android `0314755`).
  구문 분석 후보는 `uv run --with`로 임시 설치했다. 측정 스크립트는 `specs/QK-CHK-001-code-chunker/measurement/measure_code.py`이고 원문·경로·심볼을 출력하지 않는다. 외부 모델 호출 0건, 0 Neurons.
  후보 `tree-sitter-language-pack==1.22.1`은 실행 중에 네이티브 해석기 묶음을 외부에서 내려받았다(`%LOCALAPPDATA%/tree-sitter-language-pack/v1.22.1`, 약 28 MB). 허용할 때 예상하지 못한 내려받기라 사용자에게 알렸다.
  그 폴더는 지우지 않았다(`v1.21.0`은 이전부터 있던 것).
- 2026-10-26 사실(plan 측정 결과, research R-02): 백엔드 Java 21 1,128개 파일은 tree-sitter-java 0.23.5로 해석 오류 0이었다.
  Android Kotlin 233개 파일은 tree-sitter-kotlin 1.1.0으로 오류 11개였다(모두 ViewModel, 원인은 문장 맨 앞 `suspend { … }` 람다).
  본문 코드 첫 색인 보수 추정은 약 3,000 Neurons이고, 테스트를 포함하면 약 7,000이다. 비밀값 규칙에 걸린 파일은 백엔드 테스트 9개(`assigned-secret`)다.
- 2026-10-26 사용자 결정(plan): (1) Kotlin은 같은 길이 해석용 사본(`suspend {` → `run    {`)으로 해석한다. 오류 11→0, 새로 깨진 파일 0.
  (2) 작은 청크 규칙 세 가지를 spec에 반영한다. 패키지 중복 제거(FR-021), 형식 머리와 첫 필드 묶음 합치기(FR-010), 본문 있는 멤버가 없는 형식의 요약 생략(FR-013). 본문 코드 Neurons가 약 12% 준다.
  (3) 결정 기록에서 첫 활성화는 본문 코드만 권고한다.
- 2026-10-26 사실: (2)에 따라 승인된 spec의 FR-010·FR-013·FR-021, US2-5·6, Assumptions(작은 청크)를 고쳤다. spec 재승인 대상이다.
  `/speckit-plan`으로 `plan.md`, `research.md`(R-01~R-15), `data-model.md`, `contracts/chunker.md`, `quickstart.md`를 썼다. 주요 설계는 다음과 같다.
  - tree-sitter 3종 색인 전용 의존성
  - 코드 상한 1,500·목표 512
  - 메타데이터는 `locator["code"]`에 둔다(마이그레이션 없음)
  - 켜짐일 때 인덱스 버전 재료는 `chk-md+chk-code`와 `meta-v2`
  - 자료원 `dnd-backend-code`·`dnd-android-code`, ADR-021(이후 plan 검토 반영으로 ADR-022)
  사람의 spec 재승인과 plan 승인은 아직 받지 않았다. 독립 검토는 별도 서브에이전트로 한다.
- 2026-10-26 사실: plan 독립 검토(작성에 관여하지 않은 별도 서브에이전트) 판정은 변경 요청이다(높음 1, 중간 8, 낮음 13).
  다음 지적은 작성 세션이 코드로 다시 확인했다.
  - H1: `ChunkingSettings`에 필드를 더하면 `devtools/measure.py:134`의 `asdict(settings)` 출력이 바뀌어 `tests/unit/devtools/test_measure.py:252-257` 고정값 시험이 깨진다
  - M3: `IndexSpec.metadata_schema_version` 기본값 `meta-v1`(`ports/sync.py:27`)이 `qk.index_version`에 기록된다
  - M4: 실행 기록 요약을 `sync/plan.py:216`에서 다시 계산한다
  - M5: ADR-021 번호를 `origin/chore/SCRUM-108-sync-failure-alert`의 `ADR-021-sync-failure-alert.md`가 이미 쓴다
  - M6: 운영 색인이 Ubuntu 22.04 aarch64에서 `uv sync --locked --extra index`로 설치한다(`docs/ops/oci-production-store.md`)
  - L7: 이 파일의 경로 문자열에 제어 문자가 있었다. 고쳤다
  사람 결정 대기.
- 2026-10-26 사용자 결정(plan 검토 반영):
  - H1: 코드 청킹 설정은 `ChunkingSettings` 밖의 별도 타입으로 둔다(기존 측정 출력·고정값 시험 불변).
  - M2: 켜짐 경로 코드는 미리 두되, 켜짐 인덱스 버전이 `INDEX_KEYWORD_RULES`에 없으면 `qk-index check`·`run`이 멈추게 한다.
  - M1: 중첩 형식을 본문 있는 멤버로 세고, Kotlin 파일 요약에도 생략 규칙을 적용한다.
  - M5·M6: 결정 기록 번호는 ADR-022로 하고 휠을 확인한다.
- 2026-10-26 사실(plan 검토 반영):
  - 휠: PyPI JSON API 읽기 전용 조회로 세 패키지의 linux x86_64·aarch64·Windows 휠과 MIT 사용권을 확인했다(내려받기 없음).
  - 측정 스크립트: M7·L3을 고쳤다(해석용 사본 끄기 옵션, 합친 청크의 종류·맥락 줄, 경로 구성 요소 경계 비교, 스크립트 해시 출력).
    같은 스크립트(`185f73ceb4b6`)로 네 조건을 다시 쟀다. 승인판(사본 켬) 대비 본문 코드 Neurons는 3,427 → 2,957(13.7% 감소), 작은 청크는 31.2% 줄었다(재검토 N5·N6 반영 뒤 `1cc6ad12e564`로 다시 쟀다: 2,958, 31.1%).
  - 문서: spec(FR-013·014·020·021·026·030, US6-5, SC-011, Edge Cases·Assumptions), research·data-model·contracts·quickstart·plan에 반영했다.
    M3·M4·M8과 L1~L13은 작성 세션이 고쳤다. spec 재승인과 plan 승인은 아직 받지 않았다. 재검토는 받지 않았다.
- 2026-10-26 사실: 같은 검토자의 plan 재검토 판정은 경미한 변경 요청이다(이전 22건 해소 17·부분 해소 5, 새 지적 높음 0·중간 2·낮음 8).
  다음 지적은 작성 세션이 코드로 다시 확인했다.
  - N1: Markdown 해석기 버전은 모듈을 가져와 읽는다(`chunking/blocks.py:5-8`). 코드 쪽이 같은 방식이면 버전 계산이 네이티브를 불러온다.
  - N2: 질의 경로가 `config/check.py`를 가져온다(`query/worker.py:14`, `server.py:12`, `app.py:7`).
  - N3: 평가 색인 준비가 환경 설정을 그대로 넘긴다(`devtools/eval_index.py:163-175`).
  반영한 것은 다음과 같다. 사람 결정이 필요한 지적은 없었다. N4는 spec 재승인에 포함된다.
  - N1: 해석기 버전을 고정 상수로 두고 `importlib.metadata`와 비교한다.
  - N2: 교차 검사는 함수 안에서 지연 가져오기를 하고, INDEX 진입점이면서 켜짐일 때만 계산한다. `config.check`·`query.server`·`query.app`을 가져와도 `chunking`이 없음을 확인했다.
  - N3: `build_runtime`이 `code` 인자를 따로 받고, `chunking`을 명시하면 꺼짐이다.
  - N4: US2-4 Given, Edge Cases.
  - N5·N6: 측정 스크립트 합치기 크기 규칙, LF 정규화 해시. `1cc6ad12e564`로 네 조건을 다시 쟀고 수치 변화는 작다(본문 Neurons 2,958, 청크 11,821).
  - N7: `IndexSpec` 예시. N8: 결과가 있을 때만 버전을 넘긴다. N9: 키워드 전용 인자, 공개 방식. N10: 낡은 문구.
  남은 일은 언어 팩 내려받기 폴더(`%LOCALAPPDATA%/tree-sitter-language-pack/v1.22.1`) 처리, spec 재승인, plan 승인이다. 모두 사람 결정이다.
- 2026-10-26 사용자 결정: 개정한 QK-CHK-001 `spec.md`를 다시 승인하고, plan을 승인했다(tree-sitter 의존성 채택 포함).
  원문은 "QK-CHK-001 spec 재승인과 plan 승인(tree-sitter 의존성 채택 포함)"이다. 바꾸려면 다시 승인을 받는다. 다음 단계는 `/speckit-tasks`다.
  언어 팩 내려받기 폴더 처리는 아직 사람 결정 대기다.
- 2026-10-26 사실(tasks): `/speckit-tasks`로 `tasks.md`(작업 47개 T001~T047 + 사람 단계 3개 H01~H03)를 썼고, Scope에 구현 범위 초안을 더했다. 외부 호출 0건, 0 Neurons.
  단계 순서는 Setup → Foundational → US1 → US2 → US3 → US6 → US4 → US5 → US7 → Polish다. 새 시험 파일은 `test_code_` 접두어를 써서 수집 이름 충돌을 피한다.
  기존 시험 기대값 변경은 0건이다. 사람의 tasks 승인은 아직 받지 않았고, 구현 시작 시점(1.G 미완료)도 사람이 정한다. 독립 검토는 별도 서브에이전트로 한다.
- 2026-10-26 사실: tasks 독립 검토(작성에 관여하지 않은 별도 서브에이전트) 판정은 변경 요청이다(높음 2, 중간 9, 낮음 13). 다음 지적은 작성 세션이 코드로 다시 확인했다.
  - H1: 단계별 메타데이터 채우기와 전체 키 비교가 충돌한다.
  - H2: 비활성 자료원은 `load_sources`가 범위 없이 돌려준다(`sources/config.py:91-92`).
  - M1: 동기화 도우미가 Markdown을 고정한다(`tests/unit/sync/helpers.py`).
  - M2: localdb conftest 패턴에 `# noqa`가 있다.
- 2026-10-26 사용자 결정(tasks 검토 반영):
  - M3: 코드 청크 텍스트 형식은 기존 `search_text`·`embedding_text`를 다시 쓰는 contracts 8절 형식이다.
  - M1·M2: 조립 함수는 새 시험 파일 안에 두고, 로컬 DB 시험은 `tests/localdb/retrieval/`에 둔다(기존 파일 불변).
  - M4·M5: 코드 수치는 첫 조각에서만 세고, `COMPONENT_SUFFIXES`를 버전 재료에 넣는다.
  - M6·M7: `uv lock`·`uv sync`와 `.env.example` 재생성은 실행 전 사람 허용을 받고, 완료 조건을 구현용으로 바꾼다.
- 2026-10-26 사실: 위 결정과 나머지 지적을 반영해 `tasks.md`를 다시 썼다(작업 48개 T001~T048, 사람 단계 4개 H01~H04).
  - 고친 문서: contracts 8절, research R-07·R-08 보충, data-model 셈 규칙, plan 시험 경로, TASK.md Scope·Data and cost·Completion criteria.
  - 사람의 tasks 승인과 TASK.md 재승인은 아직 받지 않았다. 재검토는 받지 않았다.
- 2026-10-26 사용자 결정: QK-CHK-001 `tasks.md`와 TASK.md(Scope 구현 범위, 완료 조건)를 승인했다.
  원문은 "QK-CHK-001 tasks.md와 TASK.md(Scope·완료 조건) 승인"이다. 바꾸려면 다시 승인을 받는다.
  구현 시작 시점(1.G 미완료)과 언어 팩 내려받기 폴더 처리(H04)는 아직 사람 결정 대기다.
