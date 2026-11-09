# Task Contract: QK-ING-003 Confluence 페이지 수집 마무리 (WBS 2.3)

> Generated at: `2026-11-05`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-119` / https://tkv123.atlassian.net/browse/SCRUM-119 (상위 `SCRUM-42` 팀 RAG 구축). 2026-11-05 읽기 전용 조회 상태 "해야 할 일"
- 기능명세서 ID / 링크: `QK-ING-003` / `specs/QK-ING-003-confluence-pages/spec.md`(2026-10-28 승인). 구현 순서는 같은 디렉터리의 `tasks.md`(2026-10-28 승인)
- 팀 스프린트 ID: `QELLO-S2026-W44`(Jira SCRUM-119 본문 값)
- GitHub Issue: `#72`(열림)
- Branch: `docs/SCRUM-119-gh-72-confluence-pages-closeout`
- Base branch: `main`. 2026-11-05 `origin/main` `6685b88`(#99 병합)에서 분기했다. 명세는 #77, 구현(T001~T057)은 #86으로 병합됐고 그 브랜치의 계약과 `main`의 QK-EVL-001 계약은 git 이력에 남긴다.

## Objective

- 이번 단계: QK-ING-003 `tasks.md`의 남은 4개(T058, 사람 단계 H01~H03)를 끝내거나, 사람이 미루기로 정한 이유를 기록한다. 수집·변환·판정 코드는 고치지 않는다.
- 목적: 구현 PR(#86)에서 열어 둔 사람 결정(ADR-026 승인, 토큰 범위·접두어 확인, 켜기 준비)을 닫아 Confluence 자료원을 켤 수 있는 상태인지 판단할 근거를 남긴다.
- 단계 게이트: 로드맵상 Phase 2는 1.G 뒤인데 1.G는 아직 끝나지 않았다. 이 작업은 2026-10-27 사용자 결정(1.G 전 예외 진행)을 이어 간다. 원본 호출이 생기는 단계(H02 실측 스크립트, H03 측정)는 실행 전에 따로 승인받는다.

## Scope

- `TASK.md`(이 파일)
- `specs/QK-ING-003-confluence-pages/tasks.md`: T058·H01~H03 체크 표시와 "마무리 기록"(결정, 미룬 이유, 측정 결과 요약). 다른 명세 문서(spec FR·SC, plan 산출물)는 바꾸지 않는다
- `docs/sdd/decisions/ADR-026-confluence-source.md`: H01 사람 결정에 따른 `Status`·`Approval` 기록과 H02·H03에서 확인한 사실 정정. 결정 내용(Decision) 자체를 바꿔야 하면 멈추고 다시 승인받는다
- H02 조건부: 토큰 접두어가 `ATATT`와 다르면 비밀값 규칙 추가(`src/qello_knowledge/domain/secret_rules.py`, `src/qello_knowledge/sources/config.py`와 사례 추가 시험). 이 작업에 넣을지 후속으로 미룰지는 확인 결과를 보고 사람이 정한다
- H03 조건부(사람이 이 작업에서 하기로 정할 때만):
  - `config/sources.toml`의 `confluence-scrum` `space_id`·`doc_types`·`exclude_trees` 채우기. `enabled = false`는 그대로 둔다
  - `config/source_reviews/confluence-scrum.toml`: 사람이 쓴다(에이전트는 대신 쓰지 않는다)
  - 첫 측정 기록: `specs/QK-ING-003-confluence-pages/measurement/first-measurement.md`(집계 값만, 페이지 ID 외 제목·경로·링크·본문·이름 없음)

## Explicit exclusions

- 자료원 켜기(`enabled = true`), `INDEX_KEYWORD_RULES` 등록, QK-STO-002 활성화 절차, 운영 서버 반영, 실제 색인과 임베딩
- QK-STO-002(인덱스 버전 게이트) 브랜치·파일. 다른 세션이 진행 중이다
- 골든셋 v0의 Confluence 근거 29문항을 다음 골든셋 버전에 넣는 일(QK-EVL-001 후속)
- Confluence·Jira·GitHub 원본 쓰기, Jira 이슈 상태 변경. 원본 호출은 승인 뒤 `GET`만 한다. 예외: 2026-11-05 사용자 요청으로 `SCRUM` 스페이스의 분류 페이지 11개를 `98435` 아래에서 홈(`98420`) 바로 아래로 옮기는 일만 Atlassian MCP로 한다(내용·제목·권한은 바꾸지 않는다)
- 수집기·변환기·판정 코드와 기존 시험 기대값 변경(H02 조건부 비밀값 규칙 추가는 예외로 사람이 정한다)
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, ADR-026 밖의 결정 기록, 다른 명세 문서, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정
- `.env`·`.env.*`·`secrets/` 읽기. 토큰 값은 묻거나 읽지 않고, 설정은 항목 이름으로만 가리킨다
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경, 운영 DB 쓰기
- 비밀값, 토큰, `.env` 값, 비공개 원문, 페이지 제목·본문, 사람 이름·메일·계정 ID 기록

## Data and cost impact

- 새로 읽는 자료원: 기본 0건. H03을 이 작업에서 하면 Confluence `SCRUM` 스페이스를 `qk-dev source measure`로 한 번 읽는다(`GET`만, 비활성 자료원, 저장·임베딩 없음)
- 외부 API로 보내는 데이터: 기본 0건. H03 측정은 Atlassian 게이트웨이에 요청 경로와 토큰만 보낸다. Workers AI 호출 0건
- 예상 호출량과 무료 한도 대비:
  - Workers AI: 0 Neurons. `--chunk`의 예상 Neurons는 계산값이고 호출하지 않는다
  - Atlassian 요청: 약 `2N + 2F + ⌈N/250⌉ + 1`(N 페이지, F 폴더, research R-02). 실행당 상한 2,000요청·분당 60·1,800초(약 880페이지)이고 넘으면 측정이 불완전으로 멈춘다. N은 측정 전 사람에게 확인한다
- 인덱스 버전 변경: 없음. 자료원이 꺼져 있어 `iv-4c0bc4fcc642`·`meta-v1`·`chk-md-20d966f730bb` 그대로다

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `TASK.md`, `specs/QK-ING-003-confluence-pages/tasks.md` | tkv00 | 사람 리뷰 |
| `docs/sdd/decisions/ADR-026-confluence-source.md` | tkv00 | 사람 승인(H01) |
| `config/sources.toml`, `config/source_reviews/confluence-scrum.toml`, 측정 기록(H03 조건부) | tkv00 | 사람 작성·확인 |
| 비밀값 규칙(H02 조건부) | tkv00 | 사람 리뷰, 독립 검토 에이전트 |

## Existing user-owned changes

- 2026-11-05 `origin/main`(`6685b88`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
uv run qk-index sources check
```

외부 호출 시험(`-m external`)은 넣지 않는다. H03 측정은 사람 승인 뒤 따로 실행하고 결과를 측정 기록에 남긴다.
`python`이 없는 환경에서는 `uv run python scripts/preflight.py`로 실행한다.

## Completion criteria

- `tasks.md`의 T058·H01·H02·H03이 체크되거나, 미루기로 한 항목은 사람 결정과 이유가 `tasks.md` 마무리 기록에 있다 — `tasks.md`
- ADR-026 `Status`가 사람 결정대로이고 승인했다면 승인자 역할·날짜가 있다 — ADR-026
- 기본 검증이 통과하고 `sources check`에서 `confluence-scrum`이 비활성이며 인덱스 버전이 그대로다 — 명령 출력
- 최종 보고에 AGENTS.md 8절 항목과 `index_version`·`embedding_model`·`chunking_version`·`eval_set_version`·`metrics_with_sample_size`·`estimated_or_used_neurons`가 있다

## Decisions

- 2026-10-27~28 QK-ING-003 명세·plan·tasks·구현 결정과 검증은 `feat/SCRUM-119-gh-72-confluence-pages`의 `TASK.md`(#86 병합 커밋 `81b974c`)와 `tasks.md` "구현 기록"에 있다.
- 2026-11-05 사실(작성 세션 확인): `tasks.md` 61개 가운데 57개 체크, 남은 것은 T058·H01·H02·H03이다. `tasks.md`는 H01~H03을 "사람 단계, 이 작업의 완료 조건 밖"으로, H03을 "별도 변경"으로 적었다.
  `config/sources.toml`의 `confluence-scrum`은 `enabled = false`, `space_id = ""`, `doc_types = {}`, `exclude_trees = []`이고 `config/source_reviews/confluence-scrum.toml`은 없다.
- 2026-11-05 사실: Jira SCRUM-119 본문은 결정 기록을 ADR-025로 적었지만 저장소의 기록은 ADR-026이다. Jira 본문을 고칠지는 사람이 정한다(Jira 쓰기는 하지 않았다).
- 2026-11-05 사용자 결정: 이 TASK.md 초안을 승인했다("TASK.md 승인"). 아래 H01~H03은 따로 정한다.
- 2026-11-05 사용자 결정(H01, "ADR-026 승인"): ADR-026을 승인했다. `Status: Accepted`와 Approval(승인자 GitHub `tkv00`, 날짜)만 바꿨고 Decision·Rationale은 그대로다.
- 2026-11-05 사용자 결정(H03, "지금 측정까지"): H03을 이 작업에서 측정까지 한다. 사용자가 확인 기록을 쓰고, 작성 세션은 설정을 채운 뒤 측정 실행 승인을 따로 받는다.
- 2026-11-05 사실(H03 준비, Atlassian MCP 읽기 전용 조회. 사용자 계정 권한이라 수집 계정과 보이는 범위가 다를 수 있다):
  - `SCRUM` 스페이스 ID `98307`, 종류 `global`, 상태 `current`, 홈 콘텐츠 ID `98420`. 팀 종류라 FR-002를 통과한다.
  - CQL로 센 현재 페이지 160개, 폴더 0개. 예상 Atlassian 요청은 약 `2×160 + 0 + 1 + 1 ≈ 322`건(research R-02)으로 실행당 상한 2,000건 안이다. Workers AI 0 Neurons.
  - 홈 바로 아래 첫 단계 콘텐츠는 페이지 3개(`98435`, `296811`, `294915`)다. 문서 분류 페이지 11개는 첫 단계가 아니라 `98435` 아래 두 번째 단계에 있다.
    수집기는 홈 바로 아래 콘텐츠만 대응표로 본다(`adapters/confluence.py:322`, FR-020). 그래서 지금 규칙으로는 `98435` 아래 모든 페이지가 같은 종류 하나가 된다.
  - 골든셋 v0 질문 목록 페이지(`3571713`)가 `98435` 아래에 있다. 색인되면 검색 평가가 오염되므로 `exclude_trees` 후보다(작성 세션 판단, 사람 확인 대상).
- 2026-11-05 사용자 결정("원본 구조 옮기기"): 사용자가 Confluence에서 `98435` 아래 분류 페이지를 홈 바로 아래로 직접 옮긴다. 작성 세션은 원본에 쓰지 않고, 옮긴 뒤 읽기 전용으로 구조를 다시 확인해 대응표를 채운다.
- 2026-11-05 사용자 요청("mcp 써서 너가 옮겨줘. 지금 안옮겨지는데"): 사용자가 화면에서 옮기지 못해 작성 세션이 Atlassian MCP `moveConfluenceContent`로 옮긴다. 옮긴 뒤 다시 읽어 부모를 대조한다.
- 2026-11-05 사실(원본 이동): `moveConfluenceContent`로 분류 페이지 10개(`98458`, `98650`, `66695`, `66183`, `66119`, `65957`, `65931`, `295131`, `131791`, `131387`)를 `98435` 아래에서 홈 `98420` 아래로 옮겼다.
  모든 응답의 `parentId`가 `98420`이었고 스페이스는 그대로다. 골든셋 질문 목록(`3571713`) 이동은 실행 환경의 권한 판정이 막아 `98435` 아래에 남았다. 다시 시도하지 않았다.
  CQL 검색 결과는 이동을 늦게 반영해서, 상위 조회(`getConfluenceContentAncestors`)로 `295131`의 상위가 홈인 것을 다시 확인했다. 내용·제목·권한은 바꾸지 않았다.
- 2026-11-05 작성 세션 제안(사람 확인 대상): `config/sources.toml` `confluence-scrum`에 `space_id = "98307"`, `exclude_trees = ["3571713"]`, 대응표 12개를 채웠다(`enabled = false` 그대로).
  대응표: 회의록 1, 용어집 1, 기능 명세 1, 설계 문서 2(설계 문서·ADR), API 문서 1, 디자인 문서 1, 개발 규칙 1, 색인 안 함 4(`131791`, `98435`, `296811`, `294915`). `131387`은 대응표에 넣지 않아 미분류다.
  `98435`는 "색인 안 함"이라 아래에 남은 `3571713`도 색인되지 않고, `exclude_trees`가 한 번 더 막는다. 범위 검증기(`sources/kinds.py` `_confluence_scope`)는 오류 0건이다.
- 2026-11-05 사용자 결정("이대로 확정"): 위 `space_id`·`exclude_trees`·대응표 12개를 확정했다. `131387`은 미분류로 둔다. 확인 기록은 이 값과 같게 사용자가 쓴다.
- 2026-11-05 사용자 요청("RAG 골든셋 v0 질문 목록도 가장 바깥으로 빼줘"): `3571713`도 `moveConfluenceContent`로 홈 `98420` 아래로 옮겼다(응답 `parentId` `98420`). 이제 첫 단계 콘텐츠이고 대응표에 없어 미분류이며, `exclude_trees`가 계속 막는다. 설정·대응표는 그대로다.
- 2026-11-05 사실(H02 접두어, 사용자 확인): 사용자가 로컬 `.env`에서 `grep -c '^ATLASSIAN_API_TOKEN=ATATT'`를 직접 실행해 `1`을 받았다. 접두어가 기존 비밀값 규칙과 같아 규칙 추가는 필요 없다. 작성 세션은 `.env`를 읽지 않았다.
  범위 세 개의 포함 여부는 화면에서 확인하지 못했고, H03 측정의 엔드포인트별 결과로 확인한다.
- 2026-11-05 사용자 결정("1. 승인"): 확인 기록 `config/source_reviews/confluence-scrum.toml`은 사용자가 준 값으로 작성 세션이 쓴다(`config/source_reviews/README.md`의 "에이전트는 대신 만들지 않는다" 규칙 예외). 개인 정보 패턴 훑어보기는 Atlassian MCP 읽기 전용으로 하고 페이지 ID만 보고한다. 판단은 사용자가 한다.
- 2026-11-05 사실(개인 정보 패턴 훑어보기, CQL 읽기 전용, 토큰 단위 검색이라 빠짐없는 검사는 아니다): 개인 메일 도메인(gmail·naver·kakao.com·daum.net·hanmail) 0건.
  연락처·전화번호·휴대폰·010·계좌·주민등록·생년월일·집 주소 11건, password·비밀번호·token·토큰·secret·@ 8건이 걸렸다. 발췌로 보면 하나(`294979`, 회의록 참석자 이름)를 빼면 모두 기능 명세·설계 문서의 제품 용어(휴대폰 회전, 푸시 토큰, 액세스 토큰 등)였다.
  참석자 이름은 `team_member_names = "허용"` 대상이다. 비밀값은 색인 때 QK-SEC-001 검사가 한 번 더 거른다. 판단은 사용자가 한다.
- 2026-11-05 사용자 답(확인 기록 값): 사이트 사용자 3명이고 모두 팀원이다. 결과는 "없음"(→ `팀원 이름 외 개인 정보 없음`). 사용자는 이름을 써도 된다고 했지만 `config/source_reviews/README.md`와 AGENTS.md 6절에 따라 역할(`팀원, SCRUM 스페이스 소유자`)로 적었다.
  역할은 MCP 조회에서 스페이스 소유자가 사용자 계정인 것으로 정했다(작성 세션 해석, 사람 확인 대상).
- 2026-11-05 사실: `config/source_reviews/confluence-scrum.toml`을 썼다. `enabled = true`로 바꾼 임시 설정 사본(작업 폴더 밖)으로 `check_scope`를 돌려 오류 0건, `confluence_review_context`의 사이트 사용자 확인 유효(`True`)를 확인했다. 저장소 설정은 `enabled = false` 그대로다.
- 2026-11-05 사실(H03 측정 1차, 사용자 승인 "측정 실행 승인"): `uv run qk-dev source measure --name confluence-scrum --chunk --json --env-file <원래 저장소 .env>`가 설정 점검에서 멈췄다(종료 1, Atlassian 요청 0건, 0 Neurons).
  점검 출력에서 `ATLASSIAN_API_TOKEN`·`ATLASSIAN_EMAIL`·`ATLASSIAN_CLOUD_ID`·`DATABASE_URL`이 `MISSING`이었다. 작성 세션은 `.env`를 읽지 않았고, 셸 환경 변수에도 같은 이름이 없다.
- 2026-11-05 검증 1차: preflight(1,015 파일)·`git diff --check`·ruff check·format --check(736 파일)·`qk-index sources check` 통과. `qk-dev db up`은 Docker 데몬이 꺼져 실패했고,
  그래서 `QK_REQUIRE_LOCALDB=1 uv run pytest`는 3,424 passed·3 deselected·353 errors(모두 로컬 DB 시험)다. Docker를 켠 뒤 다시 돌린다.
- 2026-11-05 검증 2차(사용자 요청 "너가 좀 해줘"로 작성 세션이 Docker Desktop을 켰다): `uv run qk-dev db up` 로컬 DB 준비 완료, `QK_REQUIRE_LOCALDB=1 uv run pytest` 3,777 passed·3 deselected(`external`). 같은 세션의 자기 검증이다.
- 2026-11-05 사실: `.env` 설정 이름을 점검하는 명령(`qk-index check --env-file`, 상태만 출력)은 실행 환경의 권한 판정이 막았다. 작성 세션은 `.env`를 읽지 않으므로 측정 1차의 `MISSING` 원인은 사람이 확인한다.
- 2026-11-05 사용자 결정(".env 고친 뒤 측정"): 사용자가 `.env`에 설정을 넣은 뒤 같은 조건(GET만, 약 322건, 0 Neurons)으로 측정을 다시 실행한다.
- 2026-11-09 사실(H03 측정 2차): 사용자가 `.env`를 고친 뒤 다시 돌렸다. 설정 점검에서 `DATABASE_URL`이 `INVALID`라 다시 멈췄다(Atlassian 요청 0건). 사용자가 형식을 고쳤다.
  `ATLASSIAN_SITE_URL`은 선택 항목이라 비어 있어도 된다.
- 2026-11-09 사실(H03 측정 3차, 같은 승인 조건): 정상 종료. 요청 308건(모두 `GET`·`200`), 306초, 목록 완전, 160페이지, 본문 146, 판정 `PASSED` 145·`PATH_EXCLUDED` 14·`SECRET_BLOCKED` 1(페이지 `98694`),
  미분류 1, 조회 실패 0, 청크 2,346, 예상 약 763 Neurons(하루 색인 예산 5,000 안), Workers AI 0건. 집계는 `specs/QK-ING-003-confluence-pages/measurement/first-measurement.md`에 페이지 ID만으로 남겼다.
  H02의 `read:space`·`read:page` 범위는 `200`으로 확인했고, `read:folder`는 폴더 0개라 확인하지 못했다.
- 2026-11-09 사실: `tasks.md` H01~H03을 체크하고 "마무리 기록"을 더했다. `SECRET_BLOCKED` 1건과 `UNSUPPORTED_BLOCK` 2,175건은 켜기 전에 사람이 본다(켜기는 이 작업 밖).
- 2026-11-09 검증 3차(측정 기록·`tasks.md` 반영 뒤): preflight(1,016 파일)·`git diff --check`·ruff check·format --check(737 파일)·`qk-index sources check`(활성 1, 비활성 3, 오류 0, `confluence-scrum` 비활성) 통과.
  Docker가 꺼져 있어 작성 세션이 다시 켠 뒤 `qk-dev db up` 준비 완료, `QK_REQUIRE_LOCALDB=1 uv run pytest` 3,777 passed·3 deselected(`external`). 같은 세션의 자기 검증이다.
- 사람 확인 대상(작성 세션 제안, 2026-11-09 기준 모두 위 기록대로 정했다):
  - H01: ADR-026 승인 여부
  - H02: Atlassian 화면에서 본 토큰 범위 세 개 포함 여부와 접두어가 `ATATT`인지(값은 묻지 않는다)
  - H03: 이 작업에서 측정까지 할지, 켜기 변경(QK-STO-002 절차와 함께)으로 미룰지
