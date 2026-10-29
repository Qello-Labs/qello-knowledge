# Task Contract: QK-OBS-001 질의 로그·피드백·`/sources`·질의 원문 저장 명세 (WBS 2.4)

> Generated at: `2026-10-29`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-120` / https://tkv123.atlassian.net/browse/SCRUM-120 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: `QK-OBS-001` / `specs/QK-OBS-001-query-log-feedback/spec.md`(Draft)
- 팀 스프린트 ID: `QELLO-S2026-W44`
- GitHub Issue: `#87`
- Branch: `feat/SCRUM-120-gh-87-query-log-feedback`
- Base branch: `main`. 2026-10-29 `origin/main` `81b974c`(#86 병합)에서 분기했다. 이전 `main`의 QK-ING-003 계약은 git 이력에 남긴다.

## Objective

- 완료: `spec.md` 작성·독립 검토·사람 승인, ADR-016 정리(Proposed, 2026-10-29).
- 완료: plan 산출물 작성, Codex 독립 검토 4차, 사람 승인(2026-10-29).
- 완료: `tasks.md`(T001~T051, H01~H03) 작성과 사람 승인(2026-10-29).
- 이번 단계: `tasks.md` T001~T051 구현(오른쪽 Herdr 패널의 Codex가 실행, 2026-10-29 사용자 지시). 운영 반영·기록 기능 켜기·운영 확인(H01~H03)은 사람이 한다.

## Scope

- `specs/QK-OBS-001-query-log-feedback/`: `spec.md`, `checklists/requirements.md`, plan 산출물(`plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`), `tasks.md`
- `docs/sdd/decisions/ADR-016-query-text-retention.md`: 사실 정정(ClickUp → Confluence 동의 경로)과 사람 결정 반영만. 승인은 사람이 한다
- 구현(2026-10-29 tasks 승인, plan "Project Structure"):
  - 새 파일: `src/qello_knowledge/domain/query_log.py`, `ports/query_log.py`, `discord/components.py`, `discord/sources.py`, `adapters/postgres/query_log.py`, `adapters/postgres/query_log_admin.py`,
    `adapters/postgres/migrations/0008_query_log.sql`, `query/recorder.py`, `query/pending.py`, `indexer/queries_cli.py`
  - 기존 파일 변경(기록 기능 기본 꺼짐에서 지금 동작 그대로): `domain/discord.py`, `discord/interactions.py`·`notices.py`, `adapters/discord/webhook.py`, `query/app.py`·`jobs.py`·`pipeline.py`·`server.py`,
    `indexer/cli.py`, `config/registry.py`·`config/check.py`와 `.env.example` 재생성(생성기로만), `workers/relay/relay.ts`
  - 문서: `docs/ops/oci-production-store.md`(운영 절차, 주소·식별자·토큰 없음)
  - 시험: 새 파일(`test_obs_*.py`, `tests/unit/query/obs_builders.py`, `tests/localdb/query/obs_db.py`), 기존 시험은 사례 추가만(`workers/relay/relay.test.ts`, `tests/unit/test_boundaries.py`).
    기대값 변경 예외는 다음뿐이다(2026-10-29 사용자 허용): `tests/unit/query/test_bot_register_commands.py`의 `bot_expected_commands()`에 `/sources` 한 항목 추가(T024),
    `tests/unit/discord/test_bot_domain.py`의 `:22`(`InteractionKind`에 `COMPONENT`)·`:62`(`Interaction` 필드에 새 필드)·`:120`(`QueryRunLog` 필드·JSON 키에 `record`) 목록 추가,
    `tests/unit/discord/test_bot_interactions.py:86`의 `not hasattr(item, "user_id")`를 "사용자 이름은 저장하지 않고 `user_id`는 `repr`에 나오지 않는다"로 바꾸기(비노출 의도 유지)

## Explicit exclusions

- 위 Scope 밖의 코드·시험 변경. 기존 마이그레이션(0001~0007) 수정. 커밋·push·PR 생성(사람 승인 뒤 `/harness-commit`·`/harness-pr`)
- Grafana 대시보드·알림(QK-OBS-002), 스레드 대화(QK-BOT-002), 검색·생성 동작 변경, 골든셋·평가 실행기(QK-EVL-001)
- 운영 서버 반영, Discord 명령 등록 변경(사람 단계)
- 다른 명세 문서(QK-BOT-001·QK-GEN-001·QK-RET-001 등) 수정
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, ADR-016 밖의 결정 기록, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정
- `.env`·`.env.*` 읽기
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문, 실제 질의 원문, Discord 사용자 식별자는 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 없음
- 외부 API로 보내는 데이터: 0건. 기본 검증은 가짜 Discord 수신부·가짜 제공자만 쓴다
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons. 구현 뒤에도 질의 로그·피드백 자체는 Workers AI를 추가로 부르지 않는 것을 전제로 명세에서 확인한다
- 인덱스 버전 변경: 없음. 질의 로그·피드백 저장은 색인 스키마와 별개다(명세에서 확인)

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-OBS-001-query-log-feedback/`, `ADR-016`, `TASK.md` | Byuntil | 독립 검토 에이전트, 사람 리뷰 |
| 위 Scope의 구현 코드·마이그레이션·시험·운영 문서 | Byuntil(실행: Codex 패널) | 같은 구현 세션이 아닌 검토자, 사람 리뷰(QK-BOT-001 동작·기대값 불변 확인) |

## Existing user-owned changes

- 2026-10-29 `origin/main`(`81b974c`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
uv run qk-migrate   # 두 번 실행, 두 번째는 applied=0
uv run qk-migrate
QK_REQUIRE_LOCALDB=1 uv run pytest
node --test workers/relay/relay.test.ts
```

`python`이 없는 환경에서는 `uv run python scripts/preflight.py`로 실행한다.

## Completion criteria

- `spec.md`가 별도 에이전트 재검토를 거쳐 사람 리뷰로 승인된다 — 리뷰 기록(이 파일 Decisions)
- ADR-016의 동의 경로·보존 기간이 constitution C-10과 맞게 정리되고 사람이 상태를 정한다 — ADR 상태 줄
- 명세에 질의 로그 메타데이터, 👍/👎 연결, `/sources`, 원문 저장 동의, 비밀값 걸린 질문의 원문 비저장 규칙이 수용 기준으로 들어 있다 — `checklists/requirements.md`
- (구현) spec SC-001~SC-011 시험이 통과하고, 기본 검증의 외부 호출·Workers AI 호출이 0건이다 — `QK_REQUIRE_LOCALDB=1 uv run pytest`, `node --test workers/relay/relay.test.ts`
- (구현) 기록 기능 꺼짐(기본)에서 QK-BOT-001 시험 기대값이 T024 허용 한 곳 말고 바뀌지 않는다 — 기존 시험, `git diff`
- (구현) `qk_query`가 새 표 넷을 직접 읽거나 지울 수 없다 — 로컬 DB 시험(SC-007). SC-012는 사람 단계 H03이고 이 작업의 완료 조건이 아니다

## Decisions

- 2026-10-29 사용자 결정: Phase 2 다음 작업으로 WBS 2.4 QK-OBS-001을 진행한다. 단계 게이트 `1.G`는 미완료(1.12 QK-EVL-001 시작 전)지만 QK-CHK-001·QK-ING-003처럼 예외로 진행한다.
- 2026-10-29 사실: 사용자는 골든셋을 Phase 2까지 진행한 뒤 만들 계획이라고 했다. 로드맵상 2.1 QK-STO-002·2.5 QK-EVL-002의 선행이 QK-EVL-001이라 순서가 맞지 않는다. 이 브랜치에서는 로드맵을 고치지 않고 단계 리뷰나 별도 로드맵 갱신에서 정한다.
- 2026-10-29 사실: Jira 이슈 `SCRUM-120`은 사용자가 만들었다. GitHub Issue `#87`은 폼 형식 본문으로 만들었고 "기존 Jira 이슈 키"를 채워 하위 작업 자동 생성은 건너뛰었다(워크플로 성공).
- 2026-10-29 사실: ADR-016은 `Proposed`다. 팀 동의를 "Discord 공지와 ClickUp 문서"로 받는다고 적혀 있어 Confluence 이관과 맞지 않고, 보존 기간 "무기한"은 constitution C-10 "동의한 범위와 기간"과 함께 다시 볼 대상이다.
- 2026-10-29 사실: 로드맵 백로그의 요구사항 ID(FR-OBS-01, FR-BOT-04·05, FR-SEC-04)는 저장소에 원문이 없다. 명세 Assumptions에 기록한다.
- 2026-10-29 사용자 결정: 이 TASK.md 초안을 승인했다("TASK.md 승인합니다, 명세 작성 시작해줘"). Ownership `Byuntil`과 ADR-016 정리를 범위에 넣는 것을 포함한다.
- 2026-10-29 사실(spec): `/speckit-specify`로 `specs/QK-OBS-001-query-log-feedback/spec.md`(US1~US6, FR-001~022, SC-001~010)와 품질 체크리스트를 썼다. Status는 Draft다.
- 2026-10-29 사용자 결정(spec 질문 셋): 원문 저장 동의는 질문자가 자기 답변에 👎를 누를 때 묻는다. `/sources`는 검색할 수 있는 자료원 목록(이름·종류·마지막 수집 시각·문서 수)과 활성 인덱스 버전을 보여 준다.
  원문은 Phase 2 완료 리뷰(2.G)까지 보존하고 그때 사람이 연장·삭제를 정한다.
- 2026-10-29 사실: 👎 때 묻기를 위해 작성 세션이 "원문 대기"(동의 전 원문을 질의 서비스 메모리에만 최대 24시간·500건)를 더했고, 이를 C-10의 "저장"으로 보지 않는다고 해석했다.
  동의는 질문자 본인만 할 수 있게 했다. 둘 다 사람 확인 대상이다.
- 2026-10-29 사실(ADR-016, 사용자 요청): 동의 방식(👎 때 묻기), 보존 기간(2.G까지, "무기한" 대체로 C-10 충돌 해소), 원문 대기, 검토한 대안 셋을 반영했다.
  사실 정정은 ClickUp→Confluence 동의 문서, Supabase→OCI 운영 저장소(ADR-008 2026-10-19 변경·ADR-022)다. Status는 Proposed 그대로이고 승인은 사람이 한다.
- 2026-10-29 사실: spec·ADR-016 독립 검토를 작성에 관여하지 않은 별도 서브에이전트(읽기 전용)에 맡겼다(사용자 요청).
- 2026-10-29 사실: spec·ADR-016 독립 검토(별도 서브에이전트, 읽기 전용) 판정은 변경 요청이다(높음 2, 중간 7, 낮음 9). Discord 공식 문서는 조회하지 않았다고 보고했다.
  작성 세션이 코드로 다시 확인했다: `qk_query`는 사용량 표 INSERT만 있다(`0007_query_role.sql:11-15`), 실행 기록은 전달 뒤에 만든다(`jobs.py:295`),
  중계 Worker는 응답 종류 1·4·5만 넘기고 대체 문구가 "다시 질문해 주세요"다(`relay.ts:49,68`). ADR-016의 "팀 동의 → 팀 공지" 문구 약화(M4)는 작성 세션의 잘못이라 되돌렸다.
- 2026-10-29 사용자 결정(검토 반영): H2 원문 기록에는 질문만 저장하고 답변 본문은 저장하지 않는다(AGENTS.md 6절). M3 원문 대기는 1시간이다.
  M5 보존은 2.G까지, 늦어도 운영 설정의 보존 상한 날짜까지이고, 날짜가 지나면 동의를 묻지 않고 삭제를 알린다.
- 2026-10-29 사실: 나머지 지적은 작성 세션이 반영했다(사람 확인 대상). H1 질의 경로 권한을 넣기·정해진 항목 갱신·좁은 조회 함수로 한정(FR-005). M1 질의 기록을 전달 전에 넣고(상한 1초) 전달 결과는 뒤에 갱신(FR-004).
  M2 버튼·`/sources`의 첫 응답 저장소 호출은 BOT-001 FR-007 예외로 두고 상한 1.5초(FR-008), Worker 응답 종류 목록과 상호작용 종류별 대체·허용 범위 문구(FR-010), 두 번째 동의 선택 처리(FR-011).
  M4 기록 기능은 기본 꺼짐이고 공지·동의 문서가 ADR-016에 기록된 뒤 사람이 켠다(FR-024, SC-012). M6 내보내기 파일 폐기 안내(FR-019). M7 상태별 기록 여부 표와 측정 경계(FR-002, FR-018).
  L1~L9 SC 재정리(SC-001~012), 출력 가림 참조 삭제, 문구 참조 정정, 버튼 값 범위, 근거 청크 정의, 삭제 뒤 재평가, QK-GEN-001 하루 사용량 대응, TASK·ADR 문구, 시험 정의. 재검토는 받지 않았다.
- 2026-10-29 사용자 결정: 검토 반영본 `spec.md`를 승인했다("승인"). 재검토 없이 한 승인이다. 작성 세션 판단 항목(질의 경로 권한 범위, 전달 전 기록, 버튼·`/sources` 첫 응답 저장소 호출 예외,
  기록 기능 기본 꺼짐, 질문자 본인만 동의, 거부된 요청은 기록 없음, 원문 대기를 C-10의 "저장"으로 보지 않는 해석)도 이 승인에 들어간다(작성 세션 해석, 사람 확인 대상).
  저장소의 다른 승인된 명세처럼 `spec.md`의 `Status` 줄은 `Draft`로 두고 승인은 이 기록으로 남긴다. 다음 단계는 `/speckit-plan`이다. Scope·Objective를 plan 단계로 고쳤다.
- 2026-10-29 사실(plan): `/speckit-plan`으로 `plan.md`·`research.md`(R-01~R-16)·`data-model.md`·`contracts/`(2개)·`quickstart.md`를 썼다. Discord 공식 문서 두 쪽(상호작용 응답, 컴포넌트)을 조회했다.
  설계 요지: 질의 서비스 기록기(전달 전 넣기 1초 상한), 버튼 `qk1:<동작>:<run_id>`, 질의 역할은 `SECURITY DEFINER` 함수 다섯만 실행, 원문 대기 메모리 1시간, `/sources`는 `last_seen_at` 기준,
  운영 명령 `qk-index queries`(관리 연결), 중계 Worker 콜백 7·종류별 대체 문구, 기록 기능 기본 꺼짐. 외부 호출 0건, 0 Neurons.
- 2026-10-29 사용자 요청: plan 독립 검토를 오른쪽 Herdr 패널의 Codex(읽기 전용, 별도 지침)에 맡긴다.
- 2026-10-29 사실: plan 1차 검토(Codex, Herdr 오른쪽 패널, 읽기 전용) 판정은 변경 요청이다(높음 2, 중간 5, 낮음 2). PostgreSQL 공식 문서 두 쪽을 조회했다고 보고했다.
  작성 세션이 `relay.test.ts:61`·`:224-241`과 버튼 값 길이(35자, 검토자의 34자도 틀림)를 다시 확인했다. 콜백 7을 종류 3에만 허용하면 기존 중계 시험은 바꾸지 않아도 된다.
- 2026-10-29 사용자 결정(plan 검토 M1): spec FR-017을 "한도를 넘으면 줄 단위로 자르고 남은 자료원 수 표시, 설정 검사 경고"로 바꾼다. 승인된 spec의 변경이고 이 답을 승인으로 기록한다.
- 2026-10-29 사실: 나머지 지적(H1·H2·M2~M5·L1·L2)은 작성 세션이 반영했다(plan "독립 검토 이력", 사람 확인 대상). 같은 Codex 패널에 반영분 최종 확인을 맡긴다.
- 2026-10-29 사실: plan 2차 확인(같은 Codex 패널) 판정은 변경 요청이다. 1차 해소 8·부분 1(H1: SC-004 "상한 초과 시 저장 0건"을 커밋 직후 반환 지연에서 보장 못함), 새 지적 M6(동의 결과 불명 뒤 다시 누를 수 없음)·M7(여유 200 ms와 설정 하한 200 ms 충돌)·L3(단일 스레드 문구).
- 2026-10-29 사용자 결정(plan 검토 H1): spec SC-004·FR-008·US2-7을 "상한 초과·결과 불명이면 부분 저장 없이 '저장 여부를 확인하지 못했습니다. 다시 눌러 주세요.', 다시 눌러도 평가·원문은 하나"로 바꾼다. 승인된 spec의 변경이고 이 답을 승인으로 기록한다.
- 2026-10-29 사실: M6(동의 결과 불명 시 대기를 `waiting`으로 유지), M7(첫 응답 상한 하한 500 ms, 최소 실행 예산 100 ms), L3는 작성 세션이 반영했다(사람 확인 대상). 3차 확인은 받지 않았다.
- 2026-10-29 사실: plan 3차 확인(같은 Codex 패널, 사용자 요청) 판정은 변경 요청이다. 2차 해소 3·부분 1(M6), 새 지적 M8(결과 불명 규칙이 FR-011·US3에 없음)·M9(결과 불명 뒤 `skip`·만료 누름이 실제 저장과 다른 안내)·L4(R-04 옛 위험 문구).
  작성 세션이 반영했다(사람 확인 대상): 대기 상태 `uncertain`, 좁은 DEFINER 함수 `qk.query_text_status`(질문자 본인 질의의 원문 유무만), spec FR-005·FR-011·US3-8 문구 정정과 US3-10·11·SC-003 결과 불명 시험 추가,
  contracts 2절 6~13행 재작성. FR-011·US3·SC-003 변경은 2026-10-29 SC-004 변경 결정의 후속 정정이며 사람 확인 대상이다. 4차 확인은 받지 않았다.
- 2026-10-29 사실: plan 4차 확인(같은 Codex 패널, 사용자 요청) 판정은 변경 요청이다. 3차 해소 1·부분 3, 새 지적 M10(R-04가 `waiting` 복귀)·M11(6~13행 우선순위·선점 전후 상태 불명확)·L5(US3-4·7 전제, US3-8 조회 불명 예외).
  작성 세션이 반영했다(사람 확인 대상). 질문자가 아닌 사람이 대기 `chosen`·없음에서 누르면 13행 함수가 `not_questioner`를 돌려 "평가를 남기지 못했습니다."로 답하도록 정했다. 5차 확인은 받지 않았다.
- 2026-10-29 사용자 결정: plan을 승인했다("plan 승인할게"). 4차 확인 뒤 5차 확인 없이 한 승인이다. plan.md "사람 결정"(SECURITY DEFINER 방식, `/sources` 마지막 확인 시각, Context 묶음 순번 기록,
  삭제 식별자 표준 입력, 원문 대기 운영 조건)과 검토 반영으로 생긴 spec 후속 정정(FR-005·FR-011·US3·SC-003), 작성 세션 판단 항목도 이 승인에 들어간다(작성 세션 해석, 사람 확인 대상).
  다음 단계는 `/speckit-tasks`다.
- 2026-10-29 사실(tasks): `/speckit-tasks`로 `tasks.md`(작업 51개 T001~T051, 사람 단계 H01~H03)를 만들었다. 스토리 순서는 US1 → US2 → US3 → US4 → US5 → US6, MVP는 US1(기록 기능 켜면 `/ask`마다 원문 없는 기록).
  기존 시험 기대값 변경 예외 후보 하나: `tests/unit/query/test_bot_register_commands.py`의 `bot_expected_commands()`에 `/sources` 추가(T024, 사람 허용 필요). 사람 승인 뒤 Scope를 구현 파일 단위로 고친다.
- 2026-10-29 사용자 결정: `tasks.md`를 승인하고 T024(`test_bot_register_commands.py`의 `bot_expected_commands()`에 `/sources` 추가)를 허용했다("tasks.md 승인하고 T024 기대값 변경도 허용합니다").
  구현은 오른쪽 Herdr 패널의 Codex가 한다("구현은 우측 codex 패널에서 시작해줘"). Scope·Validation·완료 조건을 구현 단계로 고쳤다.
  Codex 패널은 plan 검토도 했으므로, 구현 검토는 다른 검토자(이 세션 또는 별도 에이전트)가 한다(AGENTS.md 2절).

- 2026-10-29 구현(실행 에이전트, **같은 세션의 자기 검증**, 독립 승인 아님): 사용자 지시로 T001~T050 순차 구현을 시작하고 T051은 이 기록 갱신만 수행한다. 기존 TASK.md·ADR-016·명세 변경을 보존했으며 커밋·push·PR 초안·운영 호출은 하지 않았다.
- 2026-10-29 상태 **BLOCKED**: Phase 1 T001·T002 완료, Phase 2 공통 타입·해석·설정·SQL·어댑터·기록기·중계 부분 구현. 기존 회귀 4개가 T012·T015 계약과 충돌하여 사용자 지시(허용한 T024 밖의 기존 시험 기대값 변경 금지)에 따라 중단했다. Phase 2 완료, T021~T050 완료를 주장하지 않는다. 기존 시험 네 사례를 고치거나 호환성 우회는 하지 않았다.
- 2026-10-29 차단 증거: `tests/unit/discord/test_bot_domain.py:22`는 InteractionKind 세 값만, `:62`는 Interaction의 기존 필드만, `:120`은 QueryRunLog 기존 필드·JSON 키만 요구한다. `tests/unit/discord/test_bot_interactions.py:86`은 user_id 속성 부재를 요구한다. 승인된 T012는 COMPONENT·user_id·component_action·component_run_id·record를 추가하고 T015는 질문자 식별자를 읽도록 하므로 기존 기대값 불변과 양립하지 않는다. 재개에는 이 네 사례의 계약 추가분 기대값 변경 허용 및 Scope 예외 갱신, 또는 사람의 spec·plan 계약 재결정이 필요하다.
- 2026-10-29 실행한 검증: (변경 전) `uv run pytest tests/unit/discord tests/unit/query tests/unit/config/test_bot_settings_registry.py tests/unit/test_boundaries.py -q` → 393 passed. Phase 1 도우미 smoke → exit 0. Phase 2 RED: 새 모듈 부재·설정/해석 미지원·0008 표 부재·중계 콜백 7 거부 확인. (변경 뒤) 새 도메인·버튼·해석·설정·기록기 단위 시험 → 29 passed, `QK_REQUIRE_LOCALDB=1 uv run pytest tests/localdb/query/test_obs_migration.py tests/localdb/query/test_obs_query_role.py tests/localdb/query/test_obs_adapter.py -q --tb=short` → 6 passed, `node --test workers/relay/relay.test.ts` → 15 passed. 기존 포함 단위 묶음 → 418 passed / 4 failed. 차단 재현 명령(`uv run pytest tests/unit/discord/test_bot_domain.py tests/unit/discord/test_bot_interactions.py tests/unit/test_boundaries.py -q --tb=short`) → 85 passed / 4 failed. `git diff --check` → exit 0.
- 2026-10-29 환경·미실행 검증: `uv run qk-dev db up --env-file /dev/null` 성공(로컬 컨테이너). `.env` 비읽기를 위해 env-file을 명시했다. `.env.example`은 `uv run python -m qello_knowledge.config.example`로만 재생성했다. qk-migrate CLI 두 번·preflight·ruff check·ruff format --check·전체 QK_REQUIRE_LOCALDB pytest는 T050 전에 차단되어 미실행이다(로컬 시험 fixture의 전체 마이그레이션 적용과 재적용 시험만 통과). 코드·시험은 부분 구현이며 미린트 상태, 권한·마감·비노출의 전체 수용 사례와 회귀 검증이 남았다. 사람 검토 전 병합·운영 사용 불가.
- 2026-10-29 계획 차이: components는 QueryReply 상속의 기존 위치 인자를 보존하는 키워드 전용 필드. SET ROLE 도우미는 로컬 비슈퍼유저를 위해 기존 시험과 같은 롤백 가능한 임시 멤버십 사용. 진행 ledger는 사용자 허용 범위인 tasks.md 구현 기록만 사용. PR 초안은 사용자 제외 지시를 따른다.
- 2026-10-29 데이터·비용: index_version 변경 없음, embedding_model 변경 없음, chunking_version 변경 없음, eval_set_version 해당 없음(검색·생성 동작 변경·평가 실행 없음), metrics_with_sample_size 해당 없음(수용 시험 결과만 위 기록), estimated_or_used_neurons=0. 실제 Discord·Workers AI·Atlassian·운영 DB 호출 0건.
- 2026-10-29 사실(구현 중): Codex가 Phase 2에서 BLOCKED로 멈췄다. 기존 시험 4개가 타입 모양을 고정해 승인된 T012·T015와 충돌한다(`test_bot_domain.py:22·62·120`, `test_bot_interactions.py:86`).
  작성 세션이 시험 내용을 다시 확인했다. tasks 작성 때 이 4곳을 예외로 잡지 않은 것은 작성 세션의 누락이다. Codex는 기존 기대값을 바꾸지 않았다.
- 2026-10-29 사용자 결정: 위 4곳의 기대값 갱신을 허용했다("4개 기대값 갱신 허용"). 새 멤버·필드를 목록에 더하고, `:86`은 비노출 의도(이름 비저장, `user_id`는 `repr`에 없음)를 유지한다. 다른 기대값은 그대로다.

- 2026-10-29 구현 재개·완료: 사용자 허용 네 기존 단언과 T024의 /sources 항목만 기대값을 갱신했다. T001~T050 구현·검증 및 T051의 TASK.md 기록 부분을 완료했다. PR 초안은 사용자 제외 지시대로 만들지 않았다. 이전 BLOCKED는 이 사용자 결정과 후속 검증으로 해소됐다. 기존 TASK.md·ADR-016·명세의 작성 변경은 보존했다.
- 2026-10-29 **같은 세션의 자기 검증 — status=PASS(구현 범위)**. 독립 검토나 사람 승인이 아니며 병합·운영 반영을 승인하지 않는다. `uv run python scripts/preflight.py` → 952개 파일 검사 통과, `git diff --check` → exit 0, `uv run ruff check .` → All checks passed, `uv run ruff format --check .` → 681 files already formatted.
- 2026-10-29 T050 로컬 저장소: `COMPOSE_DISABLE_ENV_FILE=1 DATABASE_URL= QK_LOCAL_DB_PORT=54322 uv run qk-dev db up --env-file /dev/null` 성공. 운영 연결과 .env 자동 로딩을 배제한 같은 로컬 고정 환경에서 `uv run qk-migrate --env-file /dev/null` 첫 실행은 `apply 0008 query_log ok; applied=1 skipped=7`, 두 번째는 `applied=0 skipped=8`이다. 공유 DB 초기화·인덱스 삭제 없음.
- 2026-10-29 T050 시험: `QK_REQUIRE_LOCALDB=1 uv run pytest` → **3523 passed, 3 deselected in 66.45s**. 제외 3개는 기존 external 표식이며 실제 외부 API 시험은 실행하지 않았다. `node --test workers/relay/relay.test.ts` → **15 passed, 0 failed, 0 skipped**. 최종 failed_checks=없음, blocked_checks=없음(구현 범위). RED 단계의 실패와 수정 내역은 tasks.md 구현 기록에 남겼다. 초기 localdb 두 모듈의 ACL/SET ROLE 시험 원인은 이미 수정됐으며 최종 회귀에서도 통과했다.
- 2026-10-29 changed_files: 이번 실행 전체 57개, 정확한 목록은 `specs/QK-OBS-001-query-log-feedback/tasks.md` 마지막 구현 기록에 있다. 코드·시험·운영 절차·설정 예시(생성기로만)·quickstart 시험 이름을 갱신했다. 0001~0007·보호 경로·다른 명세는 변경하지 않았다. 커밋·push·PR 생성·운영 배포·Discord 등록은 실행하지 않았다.
- 2026-10-29 계획과 다른 구현 세부: RenderedReply.components는 상속 위치 인자 보존을 위한 키워드 전용 기본 필드. 앞 길은 연결 뒤·완료 뒤 절대 마감을 다시 검사하며 내부 set_deadline으로 어댑터에도 전달한다. total_ms는 예약 시점과 구분해 요청 수신부터 잰다(검색·생성 마감 불변). 사용자 삭제는 동의 저장 경합을 막는 행 잠금을 먼저 건다. queries 인자·정리·표준 입력 실패는 원문을 버리는 전용 오류 경계를 사용한다. 버전 미기록 분포는 unknown으로 센다. 동작 계약의 변경은 없다.
- 2026-10-29 assumptions·risks·required_human_decisions: 기록 기능 기본 꺼짐을 유지한다. 실제 Discord의 비공개 동의 메시지 콜백 7, 운영 함수 소유자, 코어 덤프·스왑 조건은 로컬 시험으로 확인할 수 없다. 별도 독립 리뷰·사람 승인과 H01~H03(ADR 승인·공지·보존 날짜·운영 반영·비용 승인 후 운영 확인)이 남으며 이 구현 완료 범위 밖이다.
- 2026-10-29 색인·평가·비용: jira_issue=SCRUM-120, spec_id=QK-OBS-001, index_version=변경 없음, embedding_model=변경 없음, chunking_version=변경 없음, eval_set_version=해당 없음(평가 세트·실행기 변경 및 품질 평가 없음), metrics_with_sample_size=해당 없음(위 수치는 자동 수용 시험 건수), estimated_or_used_neurons=0. 실제 Discord·Workers AI·Atlassian·운영 DB 호출 0건.
- 2026-10-29 검증(구현 세션과 다른 이 세션이 다시 실행): preflight(952 파일)·`git diff --check`·ruff check·format --check 통과, `qk-migrate` 두 번 `applied=0 skipped=8`,
  `QK_REQUIRE_LOCALDB=1 uv run pytest` 3,523 passed·3 deselected, `node --test workers/relay/relay.test.ts` 15 passed. 기존 시험 변경은 허용된 다섯 곳(`test_bot_domain.py` 3곳,
  `test_bot_interactions.py:86`, `test_bot_register_commands.py`)과 사례 추가(`test_boundaries.py`, `relay.test.ts` 삭제 줄 0)뿐임을 `git diff`로 확인했다. 변경 파일은 TASK.md Scope 안이다. 코드 검토는 아직 하지 않았다.
- 2026-10-29 사실: 구현 독립 검토(오른쪽 위 Herdr 패널의 새 Codex 세션, 설계·구현 미관여, 읽기 전용) 판정은 변경 요청이다(높음 0, 중간 2). M1 `adapters/postgres/query_log.py:50-57` `set_config` 왕복 뒤 문장 제한을 줄이지 않아 R-04 마감 보장 위반,
  M2 `query/recorder.py:61-69` 시간 초과한 앞 길 작업이 질문 원문 인자를 대기열에 보유. 작성 세션이 두 곳을 코드로 다시 확인했다. 검토자는 전체 pytest·SC 단언 강도 전수 감사는 하지 않았다고 보고했다.
- 2026-10-29 사용자 지시: 수정은 오른쪽 아래 Herdr 패널의 새 Codex 세션이 한다. 재검토는 오른쪽 위 검토자 세션이 한다.

- 2026-10-29 **검토 M1·M2 수정, 같은 세션의 자기 검증 — status=BLOCKED(필수 검증 환경)**. 사용자 지시로 실행 에이전트가 지정한 7개 파일만 수정했다. 기존 변경·기존 시험 기대값 보존, git 상태 변경 명령·커밋·push·PR·외부 서비스 호출 없음.
- M1: 설정 왕복 뒤 남은 예산으로 statement_timeout을 다시 줄이고, 별도 Timer가 절대 마감 − 200ms에 해당 연결의 cancel_safe(timeout=0.2)를 요청한다. 설정 대기와 함수 실행을 함께 제한하며 취소 결과는 timeout이다. 취소 요청 완료를 join한 뒤 연결을 폐기하여 다음 작업을 잘못 취소하지 않는다. 연결 생성 뒤 최소 실행 예산 재검사는 유지한다. 네트워크 장애·취소 전달 실패 시점의 저장 여부는 기존 결과 불명 계약을 따른다.
- M2: 앞 길 작업 인자를 잠금 있는 상자로 전달한다. front 시간 초과 때 상자를 비우고 Future.cancel()하여 미시작 작업의 원문 참조를 제거한다. 실행할 때 인자를 꺼내 상자도 즉시 비운다. 이미 실행 중인 어댑터 작업은 M1의 취소 경로로 끝난다. 앞 길 대기열에 별도 개수 상한은 추가하지 않았다: 취소된 대기 작업은 빈 상자만 보유하며 기존 절대 마감 검사도 유지한다. 작업 스레드 자체가 멈추는 환경에서는 원문 없는 취소 작업 껍질이 일시 누적될 위험이 남는다.
- TDD: 수정 전 새 단위 시험 3개 실패(설정 대기 취소 부재, 함수 실행 취소 부재, 대기열 원문 weakref 생존)·기존 6개 통과 확인. 수정 뒤 9 passed(2.11s). 원문 대기 close 뒤, worker를 계속 막아 둔 상태에서도 weakref 소멸·Future 취소, worker 해제 뒤 저장 호출 0회를 확인했다. 로컬 DB에는 설정 pg_sleep 및 설정 왕복 600ms + 원문 INSERT AFTER trigger pg_sleep, 취소 뒤 원문 0건·consented=false 시험을 추가했지만 fixture 연결 차단으로 본문은 미실행이다.
- executed_checks / passed_checks: `uv run ruff check .` 통과, `uv run ruff format --check .` 682 files already formatted, `node --test workers/relay/relay.test.ts` 15 passed. `git diff --check` exit 0이나 `.env.example: Operation not permitted` 출력으로 전체 확인은 제한됨; 지정 변경 7파일의 diff check는 경고 없이 exit 0. uv 캐시는 쓰기 가능한 /private/tmp/qk-obs-uv-cache를 사용했다.
- blocked_checks: `uv run python scripts/preflight.py`는 정책상 차단된 설정 예시의 stat에서 PermissionError. `COMPOSE_DISABLE_ENV_FILE=1 DATABASE_URL= QK_LOCAL_DB_PORT=54322 uv run qk-dev db up --env-file /dev/null`은 Docker 소켓 접근 거부(권한 상승 재시도도 동일). 같은 로컬 고정 환경의 `uv run qk-migrate --env-file /dev/null` 두 번 모두 연결 불가(exit 4), 추가 권한 상승 재시도도 동일하여 applied=0을 확인하지 못했다. .env·.env.*·secrets 내용을 읽지 않았다.
- failed_checks / blocked_checks: `QK_REQUIRE_LOCALDB=1 uv run pytest`는 pytest가 루트 항목을 탐색하며 .env의 stat에서 수집 오류. 차단 경로를 탐색에서 제외한 `QK_REQUIRE_LOCALDB=1 uv run pytest --ignore=.env --ignore-glob='.env.*'`는 3196 passed, 3 deselected, 3 failed, 329 errors(11.19s). failed는 test_env_example_matches_registry(차단된 설정 예시 읽기), test_serve_answers_healthz_on_loopback 및 test_loopback_connection_is_allowed(소켓 권한); errors는 로컬 DB fixture 및 HTTP 통합 시험 소켓 권한이다. 시험 삭제·skip·suppress·새 noqa 없음. 관련 단위/query·discord 묶음도 429 passed, 동일 소켓 차단 1 failed·5 errors. 로컬 어댑터+수정 단위 묶음은 9 passed·DB fixture 4 errors. 코드 결함으로 확정된 최종 실패는 없지만 필수 검증 통과를 주장하지 않는다.
- assumptions / risks / required_human_decisions: 로컬 DB와 loopback·Docker 및 설정 예시 검사에 접근할 수 있는 검증 환경에서 필수 검증 전부를 재실행하고, 별도 검토자가 수정 diff와 취소·롤백 증거를 확인해야 한다. Timer 스케줄링·취소 전달은 OS/libpq/네트워크에 의존하며 실제 PostgreSQL 취소와 부분 저장 0건은 아직 확인하지 못했다. 독립 승인·운영 반영은 하지 않는다. jira_issue=SCRUM-120, spec_id=QK-OBS-001, 색인·임베딩·청킹·평가 세트 변경 없음, Neurons=0.

- 2026-10-29 추가 자기 검증: `uv run pytest --ignore=.env --ignore-glob='.env.*' tests/unit/query/test_obs_*.py -q --tb=short` → 86 passed(2.60s). 마지막 lint·format 재실행도 통과. 미추적 수정 파일은 `git diff --no-index --check /dev/null <파일>`로도 검사했으며 공백 오류 출력은 없었다(새 파일 차이로 exit 1). 최종 상태는 필수 환경 검증 차단에 따른 BLOCKED 그대로다.
- 2026-10-29 검증(검토 M1·M2 수정 뒤, 수정 세션과 다른 이 세션이 실행): 수정 세션은 Codex 샌드박스가 DB·소켓·설정 예시 접근을 막아 필수 검증을 끝내지 못하고 BLOCKED로 보고했다.
  이 세션이 다시 실행한 결과: preflight(953 파일)·`git diff --check`·ruff check·format --check 통과, `qk-migrate` 두 번 `applied=0 skipped=8`, `QK_REQUIRE_LOCALDB=1 uv run pytest` 3,528 passed·3 deselected,
  `node --test workers/relay/relay.test.ts` 15 passed. 기존 시험 변경 줄 수는 수정 전과 같다(허용 다섯 곳과 사례 추가). 재검토는 오른쪽 위 검토자 세션에 맡긴다.
- 2026-10-29 사실: 구현 재검토(오른쪽 위 검토자) 판정은 변경 요청이다(중간 1). M2 해소, M1 부분 해소: 클라이언트는 마감 − 여유에 취소를 요청만 할 수 있어 R-04의 "그 시각까지 취소 완료"를 입증할 수 없고,
  시험(`tests/localdb/query/test_obs_adapter.py:127`)은 950 ms 미만 완료만 본다. 검토자는 SC-002·003·004 시험 단언이 충분히 강하다고 확인했다.
- 2026-10-29 사용자 결정(구현 재검토 M1): plan 문구를 정정한다. research R-04·contracts 2절을 "마감 − 여유에 취소 요청, 호출자는 마감까지만 대기, 부분 저장 없음, 결과는 불명일 수 있음"으로 고쳤다(spec은 그대로).
  시험은 취소 요청 시각·롤백·다음 요청 성공을 검증하도록 수정 세션(오른쪽 아래)에 맡긴다.

- 2026-10-29 **재검토 M1 새 계약 시험 정정, 같은 세션의 자기 검증 — status=PASS(이번 시험 수정 범위)**. jira_issue=SCRUM-120, spec_id=QK-OBS-001. 변경 파일은 `tests/localdb/query/test_obs_adapter.py`, `specs/QK-OBS-001-query-log-feedback/tasks.md`, `TASK.md` 3개다. `query_log.py`·`recorder.py`는 새 계약과 맞아 수정하지 않았다. 설계 측 research·contracts·Decisions 변경과 나머지 미커밋 변경은 보존했다.
- 시험 정정: 기존 950ms 완료 단언을 제거하고 실제 `QueryRecorder.front` 호출로 검사한다. 연결 래퍼가 cancel_safe 진입의 monotonic 시각을 기록하여 `deadline − 200ms`부터 50ms 이내인지 확인한다. 50ms는 Timer/Future 뒤 Python 스레드 재개 시각의 측정 허용 오차이며 200ms 여유보다 작아서 마감에야 취소하는 구현은 실패한다. 호출자 반환도 `deadline`부터 50ms 이내인지 확인한다. 이는 서버 취소 완료 시각 보장이 아니다.
- 시험 주입: 설정 pg_sleep(2), 또는 설정 왕복 600ms + 원문 INSERT AFTER trigger pg_sleep(2)를 사용한다. 함수 지연 사례에서는 서버 statement_timeout을 시험 연결에서만 끄므로 서버 타이머가 클라이언트 취소 부재를 가리지 못한다(기존 서버 statement_timeout 시험은 유지). 실제 취소 전송 후 cancel_safe 반환을 Event로 막아 어댑터 정리가 늦어도 호출자는 마감에 timeout을 받음을 검증한다. 원문 0건·consented=false 확인 뒤 Event를 풀고 바로 다음 store_question이 stored인지, 첫 연결 폐기·새 backend PID·새 연결 객체·원문 1건·consented=true인지 확인한다. 두 번째 연결에는 지연을 주입하지 않는다.
- executed_checks / passed_checks: `UV_CACHE_DIR=/private/tmp/qk-obs-uv-cache QK_REQUIRE_LOCALDB=1 uv run pytest --ignore=.env --ignore-glob='.env.*' tests/localdb/query/test_obs_adapter.py tests/unit/query/test_obs_adapter_deadline.py tests/unit/query/test_obs_recorder.py -q --tb=short` → 13 passed(4.60s). 대상 시험 파일 ruff check·format --check 통과. 변경 문서 diff check와 미추적 시험 파일 no-index 공백 검사에서 오류 출력 없음(no-index exit 1은 새 파일 차이). 첫 시험 실행은 닫힌 연결에서 backend_pid를 읽는 시험 계측 오류로 2 failed·2 passed였고, PID를 연결 생성 때 캡처하도록 고친 뒤 위 최종 시험이 통과했다. 구현 결함으로 인한 RED라고 주장하지 않는다.
- failed_checks=없음(최종 실행), blocked_checks=없음(이번 범위). 전체 preflight·전체 pytest·마이그레이션·중계 등 기본 검증은 이번 사용자 지시대로 오케스트레이터가 재실행하며 이번 세션에서는 실행하지 않았다. pytest의 차단 경로 탐색은 ignore 옵션으로 제외했으며 .env·.env.*·secrets 내용 읽기, 시험 삭제·skip·noqa, git 상태 변경·커밋·외부 API 호출 없음. 이번 시험은 기존 로컬 DB의 세션 전용 시험 DB만 사용했다. Neurons=0.
- assumptions / risks / required_human_decisions: OS 부하가 측정 허용 오차 50ms를 넘으면 시험이 실패할 수 있다. 취소 요청은 서버 완료 시각을 보장하지 않고, 늦은 커밋은 기존 결과 불명·재시도 계약을 따른다. 독립 재검토와 오케스트레이터의 전체 검증이 남았다. 이번 자기 검증은 독립 승인·병합·운영 승인이 아니다.
- 2026-10-29 검증(M1 시험 정정 뒤, 이 세션이 다시 실행): preflight(953 파일)·`git diff --check`·ruff check·format --check 통과, `qk-migrate` `applied=0 skipped=8`, `QK_REQUIRE_LOCALDB=1 uv run pytest` 3,528 passed·3 deselected,
  `node --test` 15 passed. 기존 시험 변경 줄 수는 그대로다. 수정 세션은 구현을 바꾸지 않고 `tests/localdb/query/test_obs_adapter.py`만 새 계약 기준(취소 요청 시각 ±50 ms, 마감 안 timeout, 롤백, 새 연결 성공)으로 고쳤다.
- 2026-10-29 사실: M1 후속 재검토(오른쪽 위 검토자, 읽기 전용) 판정은 승인 권고다(새 지적 0). 새 계약이 spec FR-008·SC-004와 맞고, 구현이 계약을 지키며, 고친 시험이 네 조건(취소 요청 시각 0~+50 ms, 마감 안 timeout, 롤백, 새 연결 복구)을 검증한다고 확인했다.
  남은 위험은 네트워크 단절·취소 전달 실패·극심한 스케줄링 지연 미재현과, 서버 취소 완료 시각 비보장(계약에 명시)이다. 구현 검토는 M1·M2 범위에서 끝났다.
- 2026-10-29 사용자 결정: `/harness-commit` 분할 초안(11개)을 승인했다("응 그대로 커밋해줘"). `query/app.py`·`jobs.py`에 기록·평가·동의·`/sources`가 섞여 7번 커밋 하나로 묶고 본문에 목적을 나눠 적었다. push·PR은 하지 않았다.
