# Implementation Plan: QK-OBS-001 질의 로그, 👍/👎 피드백, `/sources`, 질의 원문 저장 옵션

**Branch**: `feat/SCRUM-120-gh-87-query-log-feedback` | **Date**: 2026-10-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-OBS-001-query-log-feedback/spec.md`(2026-10-29 사용자 승인)

## Summary

질의 서비스(`qk-query`, OCI 공유 인스턴스)에 기록기를 더해 `/ask`마다 원문 없는 질의 기록을 운영 저장소에 넣는다. 답변 마지막 메시지에 👍·👎 버튼을 달고, 버튼 상호작용을 같은 서명 검사·허용 범위를
거쳐 평가로 저장한다. 질문자가 자기 답변에 👎를 누르면 메모리의 원문 대기(1시간)에서 질문을 꺼내 동의를 묻고, 동의한 질문만 저장한다. `/sources`는 활성 인덱스의 보이는 문서를 자료원별로 묶어 보여 준다.
질의 역할은 표 권한 없이 `SECURITY DEFINER` 함수 여섯 개만 실행한다. 집계·내보내기·지우기는 `qk-index queries`(관리 연결)다. 기록 기능은 기본 꺼짐이다. 근거는 [research.md](research.md)에 있다.

## Technical Context

**Language/Version**: Python 3.13(기존), 중계 Worker TypeScript(기존, ADR-024)

**Primary Dependencies**: 새 의존성 없음. 기존 `psycopg`(postgres 묶음), `cryptography`(query 묶음)

**Storage**: 운영 PostgreSQL(OCI). 새 마이그레이션 `0008_query_log.sql`(표 4, 함수 7, 권한). 원문 대기는 질의 서비스 메모리(R-07)

**Testing**: pytest 단위(가짜 기록기·가짜 시계·시험 서명 키), 로컬 DB(`QK_REQUIRE_LOCALDB=1`, 역할 권한·함수·지우기·집계), `node --test`(중계). 실제 Discord는 사람 단계 M-01~M-03

**Target Platform**: 질의 서비스 OCI A1 Ubuntu(systemd `qk-query.service`), Worker Cloudflare Workers Free

**Project Type**: 기존 단일 패키지 확장

**Performance Goals**: 버튼·`/sources` 첫 응답 ≤ 1.5초(기록기 앞 길의 절대 마감, 중계 제한 2.5초 안), 질의 기록 넣기 대기 ≤ 1초(뒤 길, 답변 전달 전)

**Constraints**: 질의 역할 최소 권한(spec FR-005), 원문 대기 메모리만(FR-011), 답변 본문 비저장(FR-011, AGENTS.md 6절), 기록 기능 기본 꺼짐(FR-024), 인덱스 버전 불변(FR-020), 0 Neurons 추가

**Scale/Scope**: 하루 질의 50건 안팎, 원문 대기 ≤ 500건. 새 모듈 약 6개, 마이그레이션 1개, CLI 하위 명령 4개, Worker 2곳 수정

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 템플릿 상태라 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다. 설계 뒤 다시 점검한 결과도 같다.

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01 근거만 | 답변 생성·표시를 바꾸지 않는다. 버튼은 표시 뒤에 붙는다 | 해당 없음 |
| C-02 현재 상태는 원본 | `/sources`에 마지막 확인 시각(KST)과 활성 인덱스 버전·활성화 시각(R-11) | 통과 |
| C-03 자료는 데이터 | `/sources`의 자료원 이름은 `neutralize`를 거친다 | 통과 |
| C-04 작게 시작 | 기록 기능 기본 꺼짐, 대시보드 없음(QK-OBS-002), 명령 하나 추가 | 통과 |
| C-05 비용 | Workers AI 추가 호출 0, 저장량 작음(ADR-016), 새 유료 서비스 없음 | 통과 |
| C-06 경계 | 포트 `ports/query_log.py`, 어댑터 `adapters/postgres/query_log.py`. Discord 꼴은 `discord/` 순수 모듈 | 통과 |
| C-07·C-08 색인 | 색인 표·인덱스 버전 변경 없음(FR-020) | 해당 없음 |
| C-09 원본 읽기 전용 | Discord 쓰기는 상호작용 응답(콜백 4·7)뿐 | 통과 |
| C-10 민감 정보 | 원문은 동의한 질문만, 저장 직전 재검사, 대기는 메모리 1시간(사람 확인 대상 해석), 보존 상한 날짜, 지우기 경로 | 조건부 통과 — 대기 해석 사람 확인 |
| C-11 명세 먼저 | spec 승인 뒤 plan. 구현은 plan·tasks 승인과 TASK.md Scope 수정 뒤 | 보류 — 사람 승인 |
| C-12 검증으로 닫기 | SC마다 자동 시험 또는 사람 단계(quickstart 1·4절) | 통과 |
| C-13 수치 조건 | 집계 보고에 기간·표본 수·인덱스·모델·측정 경계(R-13) | 통과 |
| C-14 권한 확인 자료만 | `/sources`는 `qk.is_visible` 통과 문서만 센다. 기록에는 제목·경로 없음 | 통과 |
| AGENTS.md 3.1 | 새 자료원·외부 모델·외부 전송 없음 | 해당 없음 |
| AGENTS.md 3.3 | 색인과 분리된 표, 인덱스 버전 불변 | 통과 |
| AGENTS.md 3.4 | 내보내기에 식별자 없음, 평가 세트 이동 시 정리 안내(FR-019) | 통과 |
| AGENTS.md 4절 | 기존 마이그레이션·QK-BOT-001 시험 기대값 불변, 운영 반영은 사람 | 통과 |
| AGENTS.md 6절 | 답변 본문 비저장, 운영 로그 식별자 없음, 지우기 식별자는 표준 입력 | 통과 |

## Project Structure

### Documentation (this feature)

```text
specs/QK-OBS-001-query-log-feedback/
├── spec.md
├── plan.md              # 이 파일
├── research.md          # R-01~R-16
├── data-model.md        # 설정, 도메인 타입, 저장 구조·함수·권한, 메모리 상태
├── quickstart.md        # 자동 검증, 로컬 확인, 운영 반영, 운영 확인
├── contracts/
│   ├── discord-components.md   # 버튼, 동의, /sources, 중계 변경
│   └── cli.md                  # qk-index queries, register-commands
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks에서 만든다
```

### Source Code (repository root)

```text
src/qello_knowledge/
├── domain/discord.py            # InteractionKind.COMPONENT, Interaction.user_id·component_*, RenderedReply.components, QueryRunLog.record (추가만)
├── domain/query_log.py          # 새: QueryRecord, QueryDelivery, RecordStatus, FeedbackValue, ComponentAction, PendingQuestion, SourcesView
├── ports/query_log.py           # 새: QueryLog 포트
├── discord/interactions.py      # 종류 3·`sources` 해석, member.user.id (기존 /ask 해석 불변)
├── discord/components.py        # 새: custom_id 만들기·해석, 평가·동의 버튼 꼴, 동의 문구
├── discord/sources.py           # 새: /sources 렌더링
├── discord/notices.py           # 버튼·/sources 안내 문구 추가(기존 문구 불변)
├── adapters/discord/webhook.py  # 마지막 메시지에 components(없으면 지금과 같은 본문)
├── adapters/postgres/query_log.py               # 새: 함수 호출, statement_timeout
├── adapters/postgres/query_log_admin.py         # 새: 집계·내보내기·지우기(관리 연결)
├── adapters/postgres/migrations/0008_query_log.sql
├── query/recorder.py            # 새: 기록기(길마다 작업 스레드·연결 하나: 앞 길 버튼·/sources, 뒤 길 /ask 기록. 절대 마감)
├── query/pending.py             # 새: 원문 대기
├── query/app.py                 # 버튼·/sources 분기, 첫 응답 /ask 기록(기다리지 않음)
├── query/jobs.py                # _claim에서 버튼·대기, _send에서 기록 넣기(상한)·전달 결과
├── query/pipeline.py            # QueryReply에 청크·인용·인덱스·모델·토큰 항목 추가
├── query/server.py              # create_app 조립, register-commands에 /sources
├── indexer/cli.py, indexer/queries_cli.py       # 새 하위 명령 `queries`
└── config/registry.py, config/check.py          # 설정 7개(1개는 진입점 추가), 교차 검사

workers/relay/relay.ts, relay.test.ts            # 콜백 7, 종류별 대체 문구
tests/unit/discord/test_obs_*.py, tests/unit/query/test_obs_*.py, tests/unit/config/test_obs_*.py, tests/unit/indexer/test_obs_*.py
tests/localdb/query/test_obs_*.py
docs/ops/oci-production-store.md                 # 0008 적용, LimitCORE, 켜기·되돌리기 절
.env.example                                     # 생성기로 다시 만듦
```

**Structure Decision**: 기존 질의 서비스 구조를 넓힌다. Discord 꼴(버튼 값·문구·렌더링)은 `discord/` 순수 모듈, 저장소는 포트·어댑터로 나눠 C-06 경계 시험(`tests/unit/test_boundaries.py`)에 더한다.
운영 명령은 관리 연결을 가진 `qk-index` 아래에 둔다(R-12).

## Phase 0·1 산출물

| 산출물 | 내용 |
| --- | --- |
| [research.md](research.md) | R-01 버튼 꼴, R-02 버튼 값, R-03 버튼 달기, R-04 기록 시점, R-05 저장·권한, R-06 근거 청크, R-07 원문 대기, R-08 첫 응답 상한, R-09 중계, R-10 설정, R-11 `/sources`, R-12 운영 명령, R-13 측정 경계, R-14 운영 로그, R-15 꺼짐 불변, R-16 시험 |
| [data-model.md](data-model.md) | 설정 표·교차 규칙, 도메인 타입, `0008` 표·함수·권한, 메모리 상태 |
| [contracts/](contracts/) | Discord 버튼·`/sources`·중계, 운영 명령 |
| [quickstart.md](quickstart.md) | 검증·운영 반영·운영 확인 |

## 구현 Scope 승인이 필요한 것

TASK.md는 지금 명세·plan 산출물과 ADR-016만 허용한다. 구현 전에 다음을 TASK.md Scope에 더하는 사람 승인이 필요하다.

| 항목 | 이유 |
| --- | --- |
| 위 `src/`·`tests/` 구조 | 구현 |
| 기존 파일 변경: `domain/discord.py`, `discord/interactions.py`·`notices.py`, `adapters/discord/webhook.py`, `query/app.py`·`jobs.py`·`pipeline.py`·`server.py`, `indexer/cli.py`, `config/registry.py`·`check.py` | QK-BOT-001 영역. 기본값(기록 기능 꺼짐)에서 지금 동작 그대로, 기존 시험 기대값 변경 0건을 목표로 한다 |
| `workers/relay/relay.ts`·`relay.test.ts` | 콜백 7(종류 3만), 종류별 대체 문구(R-09). 기존 시험(`:61`, `:224-241`) 기대값 그대로, 사례 추가만 |
| 마이그레이션 `0008_query_log.sql` | 저장소 처음의 `SECURITY DEFINER` 함수(R-05) |
| `tests/unit/test_boundaries.py` | 새 모듈 경계 검사 추가 |
| `docs/ops/oci-production-store.md` | 운영 절차(quickstart 3절) |
| `.env.example` | 생성기로 다시 만든다 |
| 운영 반영(마이그레이션 적용, 배포, 명령 등록, Worker 재배포, 기록 기능 켜기) | 사람 단계, 명령마다 승인 |

## 사람 결정이 필요한 것 (plan 승인 전)

1. `SECURITY DEFINER` 함수로 질의 역할 권한을 좁히는 방식(R-05). 저장소 처음 쓰는 방식이고, 운영 적용 때 함수 소유자를 확인해야 한다.
2. ~~`/sources`가 2,000자를 넘으면 자르기(R-11)~~ 2026-10-29 사용자 결정으로 spec FR-017을 자르기로 바꿨다(plan 검토 M1).
3. `/sources`의 "마지막 수집 시각"을 문서의 마지막 확인 시각(`last_seen_at`)으로 하는 것(R-11). 화면 문구는 "마지막 확인"이다.
4. 근거 기록을 출처 경로 대신 Context 묶음 순번으로 남기는 것(R-06).
5. 지우기 명령이 사용자 식별자를 표준 입력으로만 받는 것(R-12).
6. 원문 대기를 C-10의 "저장"으로 보지 않는 해석(spec Assumptions, spec 승인에 포함됨)과 그 운영 조건(`LimitCORE=0`, 스왑 확인, R-07).

## 다른 명세에 넘기는 것

| 대상 | 넘기는 내용 |
| --- | --- |
| QK-OBS-002 | 집계 보고 항목의 대시보드 표시, 질의응답 하루 사용량 운영 화면, 기록 실패·보존 상한 경과 알림 |
| QK-EVL-002·QK-EVL-001 | 내보내기(JSON Lines)를 골든셋 후보로 옮기는 절차와 개인 정보·비공개 문서 정리 |
| QK-BOT-002 | 스레드 대화에서 버튼·기록 연결(지금은 스레드가 허용 범위 밖) |
| QK-SYN-002 | `/reindex` 등록 시 명령 목록(통째 덮어쓰기)에 `/sources`를 함께 둔다 |
| `docs/sdd/roadmap.md` | 2.G 완료 조건에 원문 보존 결정, 상태 열 갱신. 사람 승인 대상 |

## 독립 검토 이력

같은 세션이 계획을 쓰고 고쳤으므로, 검토는 오른쪽 Herdr 패널의 Codex(읽기 전용, 별도 지침)가 했다(AGENTS.md 2절, 2026-10-29 사용자 요청).

| 차수 | 결과 | 지적 | 반영 |
| --- | --- | --- | --- |
| 1차(2026-10-29) | 변경 요청 | H2·M5·L2 | 기록기 두 길·절대 마감·늦은 작업 폐기(H1), 원문 대기 주기 정리(H2), `/sources` spec 자르기로 변경(M1, 사용자 결정), 꺼짐에서도 앞 길(M2), 대기 선점 상태·날짜 재검사(M3), 콜백 7은 종류 3만·기존 중계 시험 불변(M4), 전달 실패 상태(M5), 중첩 jsonb 허용 키·오류 문구(L1), 길이 35자·줄 번호(L2) |
| 2차(2026-10-29) | 변경 요청 | 1차 해소 8·부분 1(H1), 새 M2·L1 | SC-004를 "결과 불명 안내, 다시 눌러도 하나"로 바꿈(사용자 결정, H1), 동의 결과 불명 시 대기 유지(M6), 첫 응답 상한 하한 500 ms·최소 실행 예산(M7), 기록기 두 길 문구 통일(L3) |
| 3차(2026-10-29) | 변경 요청 | 2차 해소 3·부분 1(M6), 새 M2·L1 | 대기 상태 `uncertain` 추가, 결과 불명 뒤 `skip`·만료·재시작 누름은 좁은 함수 `qk.query_text_status`로 원문 유무 확인(M8·M9), US3-8 확정 선택 한정·US3-10·11 추가, SC-003 결과 불명 시험, R-04 남는 위험 문구 갱신(L4) |
| 4차(2026-10-29) | 변경 요청 | 3차 해소 1·부분 3, 새 M2·L1 | R-04 `uncertain` 통일(M10), contracts 6~13행 평가 순서·선점 전 상태·조회 불명 시 `uncertain` 복원·조합 표(M11), US3-4·7 "저장 시도 없이" 전제와 US3-8 조회 불명 예외(L5) |
| 구현 재검토(2026-10-29) | 변경 요청 | 구현 M1 부분 해소 | R-04·contracts 2절의 "마감 − 여유까지 커밋 또는 취소 완료"를 "마감 − 여유에 취소 요청, 부분 저장 없음, 마감까지 결과 없으면 불명"으로 정정(사용자 결정) |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| `SECURITY DEFINER` 함수 | 평가 바꾸기(`ON CONFLICT DO UPDATE`)·질문자 확인에 필요한 읽기를 질의 역할에 표 권한으로 주면 질문자 식별자 전체를 읽게 된다(R-05) | 표 권한 + RLS는 질의 역할의 "자기 행" 기준이 없다 |
| 질의 서비스 메모리의 원문 대기 | 👎 때 동의를 묻는 사용자 결정에 동의 시점의 질문이 필요하다(R-07) | 저장소에 두면 동의 없는 저장, 버튼 메시지에서 다시 얻을 수 없다 |
