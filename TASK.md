# Task Contract: QK-ING-003 Confluence 페이지 수집 설계·구현 (WBS 2.3)

> Generated at: `2026-10-27`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-119` / https://tkv123.atlassian.net/browse/SCRUM-119 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: `QK-ING-003` / `specs/QK-ING-003-confluence-pages/spec.md`(2026-10-28 승인)
- 팀 스프린트 ID: `QELLO-S2026-W44`
- GitHub Issue: `#72`
- Branch: `feat/SCRUM-119-gh-72-confluence-pages`
- Base branch: `main`. 2026-10-27 `origin/main` `256de6f`(#78 병합)에서 분기했다. 명세 단계는 `feat/SCRUM-119-gh-72-confluence-source`(#77 병합)에서 했고,
  그 계약과 이전 `main`의 #70 계약은 git 이력에 남긴다.
  push 전에 `origin/main` `d0542bb`(#85 병합) 위로 커밋 16개를 다시 쌓았다(2026-10-28 사용자 지시). 충돌난 `TASK.md`는 이 계약을 남겼고, `main`의 #58 마무리 계약은 git 이력에 남긴다.

## Objective

- 완료: `spec.md` 재검토·승인, plan 산출물 작성·독립 검토·승인, `tasks.md`(T001~T058, H01~H03) 승인(모두 2026-10-28). plan 실측은 사용자 결정으로 보류했다.
- 이번 단계: `tasks.md` T001~T058 구현. 자료원은 비활성으로 등록하고, 켜기와 첫 실제 수집 측정(FR-027)·H01~H03은 사람이 한다.

## Scope

- `specs/QK-ING-003-confluence-pages/`: `spec.md`·`checklists/requirements.md`(재검토 반영), plan 산출물(`plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`, `measurement/`), `tasks.md`
- `docs/sdd/decisions/ADR-026-confluence-source.md`(Proposed. spec·plan 검토에서 나온 사실 정정만. 승인은 사람이 한다)
- 구현(2026-10-28 tasks 승인, plan "Project Structure"):
  - 새 파일: `src/qello_knowledge/adapters/confluence.py`, `adapters/atlassian_adf.py`
  - 기존 파일 변경(기본값에서 지금 동작 그대로): `domain/source.py`·`ports/source.py`·`sources/collect.py`(QK-ING-001), `sources/kinds.py`·`sources/config.py`·`sources/scope_review.py`(QK-ING-001·002),
    `security/kinds.py`·`security/screen.py`·`security/policy.py`·`domain/redact.py`·`domain/security.py`(QK-SEC-001), `sync/keys.py`·`sync/plan.py`·`sync/execute.py`·`sync/run.py`·`sync/report.py`·`domain/sync.py`(QK-SYN-001),
    `adapters/http.py`, `indexer/sync_cli.py`·`indexer/cli.py`, `config/registry.py`·`config/check.py`와 설정 예시 재생성, `devtools/measure.py`·`devtools/db.py`
  - 설정: `config/sources.toml`(`confluence-scrum` 비활성 등록), `config/source_reviews/README.md`(기록 형식 안내. 기록 파일은 사람이 쓴다)
  - 시험: 새 파일(이름에 `confluence`·`atlassian`), `tests/fixtures/confluence/`, `tests/fixtures/source_reviews/confluence-*.toml`. 기존 시험은 사례 추가만(`tests/unit/sync/test_keys.py`,
    `tests/unit/adapters/test_http_transport.py`, `tests/unit/adapters/confluence/test_confluence_listing.py` 등), 기대값 변경 0건
- `TASK.md`(이 파일)

## Explicit exclusions

- 자료원 켜기(`enabled = true`), 개인 정보 확인 기록 승인, 운영 서버 반영과 실제 색인, 첫 실제 수집 측정(FR-027, 사람 단계)
- Confluence·Jira 원본 쓰기. 실측은 사람 승인 뒤 `GET` 요청만 한다
- Jira 이슈 수집(QK-ING-004), Atlassian 토큰·서비스 계정 발급(사람)
- 다른 명세 문서(QK-ING-001·QK-ING-002·QK-SEC-001·QK-SYN-001·QK-CHK-002) 수정. 이 명세가 요구하는 코드 변경은 구현 범위에 넣되 기존 자료원 동작·시험 기대값은 바꾸지 않는다
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, ADR-026 밖의 결정 기록, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정
- `.env`·`.env.*` 읽기. 토큰은 설정 항목 이름으로만 가리킨다
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문, 페이지 제목·본문, 사람 이름·메일은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 구현 단계 0건. Confluence `SCRUM` 스페이스(비공개 팀 자료, ADR-026)는 켜기 전 사람 측정(H03)에서만 읽는다
- 외부 API로 보내는 데이터: 0건. 기본 검증은 재생 전송·가짜 제공자만 쓴다
- 예상 임베딩·생성 호출량과 무료 한도 대비: 이 브랜치 0 Neurons. 첫 색인 예상 Neurons는 켜기 전 측정(FR-027)으로 잰다
- 인덱스 버전 변경: 운영 인덱스 없음(Confluence 자료원은 비활성 등록). 메타데이터 스키마·청킹 규칙 버전 영향은 plan에서 정하고, 바뀌면 AGENTS.md 3.3을 따른다

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-ING-003-confluence-pages/`, `ADR-026`, `TASK.md` | tkv00 | 독립 검토 에이전트, 사람 리뷰 |
| 위 Scope의 구현 코드·설정·시험 | tkv00 | 사람 리뷰(기존 GitHub 자료원 동작·기대값 불변 확인) |

## Existing user-owned changes

- 2026-10-27 `origin/main`(`256de6f`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
uv run qk-migrate   # 두 번 실행, 두 번째는 applied=0(새 마이그레이션 없음)
uv run qk-migrate
QK_REQUIRE_LOCALDB=1 uv run pytest
```

`python`이 없는 환경에서는 `uv run python scripts/preflight.py`로 실행한다.

## Completion criteria

- 목록·권한·변환·분류·용어집·등록 시험이 SC-001~SC-009, SC-011~SC-013 사례에서 통과하고, 기본 검증의 실제 원본 호출·쓰기와 Workers AI 호출이 0건이다 — `QK_REQUIRE_LOCALDB=1 uv run pytest`
- Confluence 꺼짐 설정에서 `iv-4c0bc4fcc642`·`meta-v1`·`chk-md-20d966f730bb`와 GitHub 자료원 시험 기대값이 그대로이고, 한 번 색인 뒤 꺼도 `INDEX_MISMATCH`가 없다(SC-014) — 기존 고정값 시험, 로컬 DB 시험
- `confluence-scrum`이 비활성으로 등록되고, 확인 기록·대응표 없이는 켜도 원본 호출 전에 막힌다 — `qk-index sources check`, 단위 시험
- 실측(SC-010)은 사람 단계 H03이고 이 작업의 완료 조건이 아니다

## Decisions

- 2026-10-27 사용자 결정: QK-ING-003을 구현까지 진행한다. 단계 게이트 1.G는 미완료(QK-EVL-001 시작 전)이지만 0.G·QK-CHK-001 선례처럼 예외로 진행한다.
- 2026-10-27 사용자 결정: Draft인 `spec.md`는 별도 에이전트의 재검토를 거친 뒤 사람이 승인한다. 승인 전에는 plan을 시작하지 않는다.
- 2026-10-27 사실: 사용자는 Atlassian 읽기 전용 토큰이 로컬 `.env`에 준비돼 있다고 답했다. 값과 변수 이름은 읽지 않았다. 실측 전에 설정 항목 이름을 사람에게 확인한다.
- 2026-10-27 사실: Issue #72 본문의 제외 범위에 "수집기 구현"이 있다(명세 단계 기준). #77 본문은 설계·작업 목록·구현을 다음 PR에서 한다고 적었다. Issue 본문을 고칠지는 사람이 정한다.
- 2026-10-27 사용자 결정: 이 TASK.md 초안을 승인했다("TASK.md 초안 승인합니다").
- 2026-10-27 사실: spec 재검토(작성에 관여하지 않은 별도 서브에이전트, 읽기 전용) 판정은 변경 요청이다(높음 2, 중간 8, 낮음 4).
  다음 근거는 작성 세션이 코드로 다시 확인했다. 수집 불완전 보류에서도 보안 숨김은 허용된다(`domain/sync.py:94`, `sync/decide.py:25`).
  원본 이름만 바뀌어도 `MISMATCH`다(`sync/identity.py:52`). 판정 기록에 제목·위치가 남는다(`domain/security.py:75-77`).
  메타데이터 스키마 버전은 인덱스 버전 재료다(`sync/keys.py:19-27`). 확인 기록 `result`는 두 값만 받는다(`sources/scope_review.py:64`). 어댑터 포트에 단건 조회가 없다(`ports/source.py:25-31`).
  검토자의 L6("AGENTS.md 3.1에 Confluence 없음")은 틀렸다(`AGENTS.md:43`). 검토자는 허용 호스트 밖의 Atlassian 공식 OpenAPI 파일(`dac-static.atlassian.com`)을 한 번 읽었다고 보고했다.
- 2026-10-27 사용자 결정(재검토 반영): N1 권한 조회 실패가 기준을 넘는 실행에서도 미확인 페이지는 검색에서 숨기고, 본문 삭제와 일반 내림만 보류한다.
  규칙상 미확인(Free 확인 기록 만료 등)은 실패로 세지 않는다. N9 문서 종류·회의록 메타데이터는 QK-CHK-001 방식으로 한다.
  새 메타데이터 스키마 버전은 Confluence 자료원이 켜졌을 때만 인덱스 버전 재료가 되고, 켜기는 QK-STO-002 절차와 사람 승인 뒤 별도 변경으로 한다.
- 2026-10-28 사용자 결정(재검토 반영): N2 개인 스페이스(`personal`)만 거부하고 `global`·`collaboration`·`knowledge_base`는 팀 스페이스 종류로 허용한다. 모르는 종류는 미확인이다.
  N8 팀 그룹은 자료원 설정에 그룹 ID로 적는다. 이름→ID 조회와 그 토큰 범위는 쓰지 않는다.
- 2026-10-28 사실: 나머지 지적은 작성 세션이 다음처럼 반영했다(사람 결정 필요 없음으로 판단, 사람 확인 대상).
  - N3: 설정에 스페이스 ID·키를 함께 두고 범위 키는 ID로 계산한다. 키만 바뀌어도 QK-SYN-001 FR-002대로 멈춘다(FR-002a). N4: Confluence 제한·미확인 판정 기록과 측정 출력에서 제목·제목 경로·링크를 비우는
    종류별 출력 규칙을 구현 범위에 넣었다(FR-011, FR-027, SC-004). N5: 트리 제외를 ID로 한다. 필수 포함 패턴은 모든 위치 하나로 고정한다(FR-021a).
  - N6: 첫 단계는 홈 바로 아래 페이지·폴더이고 자신도 포함한다. 홈 밖 최상위 페이지는 미분류다(FR-020, FR-020a). N7: 단건 확인이 현재·같은 스페이스면 내리지 않고 목록을 불완전으로 둔다.
    어댑터 계약에 단건 확인을 더한다(FR-030). 미분류 페이지는 목록에 남아 사라진 자료 확인 대상이 아니다.
  - N10: SC-002를 FR-031에 맞췄다. N11: 이름 색인 허용은 자료원 전체에 걸리고 확인 결과 값을 새로 둔다(FR-021, FR-025a). N12: US4 번호. N13: SC-011~014 추가, SC-010 사람 단계 표시. N14: 블록 단위 위치 없음(FR-019a).
  - ADR-026: 스페이스 종류 표, 팀 그룹 ID, 폴더 제한 범위 행(재검토자 보고, 작성 세션 미확인), 10% 기준 설명, 근거 [A9]를 고쳤다. 상태는 Proposed 그대로다.
- 2026-10-28 사실: 같은 검토자의 최종 확인 판정은 승인 권고다(높음 0, 중간 3, 낮음 3). N1~N14는 N1·N4 부분 해소, 나머지 해소. 검토자는 1차의 L6 판정이 예전 사본을 본 오류였다고 정정했다.
  작성 세션이 다음처럼 반영했다. R1: FR-031에 "조회 실패로 생긴 미확인" 구분과 문서 단위 보류를 적고, SC-002의 비밀값 문서는 숨김(본문 삭제는 비율 보류를 따름)으로 고쳤다.
  R2: 변환 규칙 버전은 변경 키에 넣고, 이 변환을 AGENTS.md 3.3의 "청킹 규칙"으로 보지 않는다(FR-019, 사람 확인 대상). R3: Confluence 측정 출력은 판정과 무관하게 제목·경로·링크를 비운다(FR-011, SC-004).
  R4: 163행 Edge 문구를 FR-031에 맞췄다. R5: 자료원 설정 형식 확장을 구현 범위에 적었다. R6: SC-004의 보안 규칙 버전 예외와 ADR [A9]의 추론 표시를 더했다. 재검토는 받지 않았다.
- 2026-10-28 사용자 결정: R2 해석(변환 규칙 버전은 변경 키에 넣고 AGENTS.md 3.3의 청킹 규칙으로 보지 않음)을 포함해 QK-ING-003 `spec.md`를 승인했다. 바꾸려면 다시 승인을 받는다.
  저장소의 다른 승인된 명세처럼 `spec.md`의 `Status` 줄은 `Draft`로 두고 승인은 이 기록으로 남긴다. 다음 단계는 `/speckit-plan`이다.
- 2026-10-28 사실(사용자 답, plan 실측 준비): `.env`의 Atlassian 설정 이름은 ADR-026 초안 그대로 `ATLASSIAN_API_TOKEN`·`ATLASSIAN_EMAIL`·`ATLASSIAN_CLOUD_ID`다.
  토큰은 범위 지정 토큰이라 `api.atlassian.com` 게이트웨이로 부른다. 고른 범위는 기억나지 않아 실측에서 엔드포인트별 허용 여부로 확인한다. 사이트 요금제는 Free라 판정 방식은 "사이트 사용자 확인"(FR-012)이다.
- 2026-10-28 사용자 결정: plan 실측(`measurement/measure_confluence.py`, `GET`만, 최대 1,500요청, 집계만 출력)은 보류한다. 스크립트는 `--dry-run`만 돌렸고 원본 호출은 0건이다.
  plan은 공식 문서와 코드로 쓰고, 실측이 필요한 항목(스페이스 종류, 페이지 수·크기, 폴더·보기 제한 실태, 토큰 범위, 첫 단계 대응표, 첫 색인 예상 Neurons)은 research에 BLOCKED로 남긴다.
- 2026-10-28 사실(plan): `plan.md`·`research.md`(R-01~R-19)·`data-model.md`·`contracts/`(5개)·`quickstart.md`를 썼다. 코드 조사는 읽기 전용 탐색 에이전트 셋에 나눠 맡겼다.
  설계 요지: 본문 없는 목록 + 콘텐츠별 보기 제한 + 통과 페이지만 본문, 미분류·제외 트리는 어댑터가 `exclusion` 표시, 사라진 페이지는 선택 Protocol 단건 확인,
  조회 실패 기준은 문서 단위 숨김, 변환 규칙 버전은 `chunk_input_hash`의 `extra`, 메타데이터는 `locator["confluence"]`, 켜짐에서만 `+cf1` 스키마 버전. 외부 호출 0건, 0 Neurons.
  plan 독립 검토는 별도 서브에이전트로 시작했다.
- 2026-10-28 사용자 결정: plan을 승인했다("승인"). 독립 검토 결과가 나오기 전의 승인이다. 검토 지적은 반영하고, 설계를 바꾸는 지적이면 다시 승인을 받는다.
  plan "사람 확인" 표의 항목(다른 영역 코드 확장, 본문 따로 받기와 ADR-026 정정, 기본 제외의 제목 경로 적용, 판정 기록 전부 비우기, 보안 규칙 버전 변화, UTC 날짜, 미리 보기 요청,
  메일·Cloud ID 비밀 표시, 켜기는 사람 단계)도 이 승인에 들어간다(작성 세션 해석, 사람 확인 대상).
- 2026-10-28 사실: plan 독립 검토(별도 서브에이전트, 읽기 전용) 판정은 변경 요청이다(높음 4, 중간 7, 낮음 4). P1(끝난 보안 내림이 매 실행 다시 확인·내림됨)과
  P2(삭제 대기 문서가 다음 실행 `pending`·확인 실행 `PURGE`로 돌아옴)는 작성 세션이 `sync/plan.py:129,185-204`에서 다시 확인했다. 기본 호출 한도(분당 60, 실행당 2,000, 1,800초)도 확인했다.
- 2026-10-28 사용자 결정(plan 검토 반영): P3 "Confluence 켜짐"은 활성 자료원이 있거나 저장소에 그 종류의 자료원 정체성이 등록된 것이다(한 번 색인하면 끈 뒤에도 `+cf1` 유지,
  끈 자료원 페이지는 다음 동기화에서 내려감). P5 본문 링크 주소는 사이트(사람·개인 스페이스 경로 제외)와 등록된 공개 링크 호스트만 남기고, spec의 "공개 웹 주소"를 등록 목록으로 해석한다.
- 2026-10-28 사실: 나머지 지적은 작성 세션이 반영했다(사람 결정 필요 없음으로 판단, 사람 확인 대상). P1 끝난 `SECURITY_ACCESS` 내림은 단건 확인 후보에서 뺀다. P2 조회 실패 문서는 `pending`·`PURGE`에서도 뺀다.
  P4 사람·개인 스페이스 링크와 쿼리·조각을 버린다. P6 모르는 상태 값·구조적 사슬 끊김은 원값 `read_restricted=unknown`(실패로 세지 않음). P7 단건 확인의 상태 명시와 실패 대응표, 확인 중 멈춤 처리.
  P8 응답 스페이스 ID가 설정과 다르면 어댑터가 멈춘다. P9 한도 범위(약 880페이지)와 설정 조정, `_links.next` 잇기, `_links.base` 없을 때 선택 설정 `ATLASSIAN_SITE_URL`.
  P10 비활성 Confluence 측정은 그 자료원 하나만 파싱·대조. P11 시험 파일 이름을 겹치지 않게. P12 `config/check.py`·`current_index_version` 변경 목록 추가. P13 `incomplete_reason`.
  P14 홈 ID 출처, 사용자 정보 매크로는 일반 매크로 자리 표시, 미디어 `alt`, 빈 본문 규칙. P15 줄 번호. FR-032 "본문 없음"은 빈 본문 → 청킹 `EMPTY`로 센다.
  같은 검토자에게 반영분 최종 확인을 맡겼다.
- 2026-10-28 사실(tasks): `/speckit-tasks`로 `tasks.md`(작업 58개 T001~T058, 사람 단계 H01~H03)를 만들었다. 스토리 순서는 US1 → US2 → US3 → US4 → US5 → US6, MVP는 US1(목록만, 권한 미확인이라 색인 0건).
  사람 승인 뒤 Scope를 구현 파일 단위로 고친다.
- 2026-10-28 사실: 같은 검토자의 plan 최종 확인 판정은 경미한 변경 요청이다(높음 0, 중간 1, 낮음 3). P1~P15·FR-032는 해소(P12는 N1로 이어짐). 검토자는 N1만 고치면 승인 권고, 재검토 불필요라고 했다.
  작성 세션이 반영했다(사람 확인 대상). N1 명령별 켜짐 계산 순서(`sources check` 활성만, `run`은 저장소를 연 뒤 두 번째 검사, `index status/activate`는 저장소 뒤),
  `_code_checks`는 `meta-v2`·`meta-v2+cf1` 중 하나 등록이면 통과(QK-CHK-001 시험 그대로). N2 끈 자료원 전체 내림은 비율 보류라 `--confirm-takedown`에서 일어난다(GitHub와 같음).
  N3 자동 링크 텍스트도 `[링크]`. N4 단건 확인 상태에 `deleted` 추가, 목록 불완전 사유 `ListPage.incomplete_reason`. tasks(T003·T009·T018·T023·T030·T044·T048·T053)에도 반영했다.
- 2026-10-28 사용자 결정: `tasks.md`를 승인했다("tasks.md를 승인합니다. TASK.md Scope를 구현 범위로 고치고 구현을 시작하세요"). Scope·데이터 영향·Validation·완료 조건을 구현 단계로 고쳤다.
- 2026-10-28 사용자 결정(구현 중): Confluence 판정 규칙 등록(FR-008)으로 `tests/unit/indexer/test_cli.py::test_security_check_json_is_one_line`의 `access_rules` 기대값에
  `confluence_pages: confluence-access-v1` 한 줄을 더하는 것을 허용했다(기존 두 항목은 그대로). Scope의 "기대값 변경 0건"의 예외다.
- 2026-10-28 사실(구현 중): 설정 항목 넷을 등록하면서 공용 시험 도우미 `tests/unit/fakes.py`의 `valid_environ()`에 합성 값 넷을 더했다(QK-BOT-001 #58 선례와 같은 추가). 기존 기대값은 그대로다.
- 2026-10-28 사실(구현): `tasks.md` T001~T057을 구현·검증했다. 새 파일은 `adapters/confluence.py`·`adapters/atlassian_adf.py`와 시험이고, 기존 코드는 새 필드의 기본값에서 지금 동작 그대로다.
  계획과 달라진 점 넷(locator 합치기를 `sync/plan.py`에서, `AUTH_MISSING`은 `run`·측정에서만, GitHub `repo` 규칙 제자리, 확인 기록 픽스처는 임시 폴더)은 `tasks.md` 구현 기록에 있다(사람 확인 대상).
  `.env.example`은 `uv run python -m qello_knowledge.config.example`로 다시 만들었고 내용은 열지 않았다.
- 2026-10-28 검증(같은 세션의 자기 검증이라 독립 검증이 아니다): preflight, `git diff --check`, ruff check·format --check 통과, `qk-migrate` 두 번째 `applied=0 skipped=7`,
  `QK_REQUIRE_LOCALDB=1 uv run pytest` 3,261 passed·3 deselected, `qk-index sources check` 통과. 외부 호출 0건, 0 Neurons. 실제 Confluence 측정(H03)과 ADR-026 승인(H01)·토큰 범위 확인(H02)은 사람 단계다.
- 2026-10-28 사실: 구현 독립 검토(별도 서브에이전트, 사용자 요청) 판정은 변경 요청이다(높음 2: 끊긴 상위 사슬을 `outside-home`으로 내려 조회 실패·불완전 목록에서 본문까지 지움, 레이아웃·결정 목록 내용 유실.
  중간 2: 사이트 링크의 계정 ID, 실행 요약 값 누락. 낮음 6). C1은 작성 세션이 코드로 다시 확인했다. C1~C10을 반영했다(내용은 `tasks.md` 구현 기록). 재검토는 받지 않았다.
  검토자는 이 작업 폴더가 `origin/main`보다 20커밋 뒤라고 지적했다(겹치는 파일은 `domain/redact.py` 하나). 다시 쌓기는 사람 승인 뒤에 한다.
- 2026-10-28 검증(검토 반영 뒤, 같은 세션의 자기 검증): preflight(906 파일)·`git diff --check`·ruff check·format --check 통과, `qk-migrate` `applied=0 skipped=7`,
  `QK_REQUIRE_LOCALDB=1 uv run pytest` 3,287 passed·3 deselected. 외부 호출 0건, 0 Neurons. 커밋·다시 쌓기 전이다.
- 2026-10-28 사실(다시 쌓기, 사용자 지시): `origin/main` `d0542bb` 위로 커밋 16개를 다시 쌓았다. 15개는 충돌 없이 올라갔고, 양쪽이 고친 `domain/redact.py`는 자동 병합됐다
  (이 브랜치 몫은 `OutputContext.opaque_item_fields` 한 줄 그대로). `TASK.md` 충돌은 이 계약을 남겨 풀었다. push는 하지 않았다.
- 2026-10-28 검증(다시 쌓은 뒤, 같은 세션의 자기 검증): preflight(908 파일)·`git diff --check`·ruff check·format --check 통과, `qk-migrate` 두 번 모두 `applied=0 skipped=7`,
  `QK_REQUIRE_LOCALDB=1 uv run pytest` 3,347 passed·3 deselected(`main`에서 들어온 시험 포함), `qk-index sources check` 통과(활성 1, 비활성 3, 오류 0). 외부 호출 0건, 0 Neurons.
