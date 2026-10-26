# Implementation Plan: QK-BOT-001 Discord `/ask`·지연 응답·답변 표시·분할·접근 제어·오류 안내

**Branch**: `feat/SCRUM-115-gh-58-discord-ask` | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-BOT-001-discord-ask/spec.md`

## Summary

Discord `/ask`를 Cloudflare Worker(서명 검사·중계)와 OCI 공유 인스턴스의 질의 서비스(`qk-query`)로 연다(2026-10-25 사용자 결정, ADR-022 Proposed). Worker는 원본 요청을 Workers VPC 바인딩과
Cloudflare Tunnel로 질의 서비스에 넘기고, 질의 서비스가 정한 첫 응답(처리 중 또는 질문자만 보는 안내)을 Discord에 돌려준 뒤 시작 확인을 보낸다. 질의 서비스는 시작 확인을 받은 작업만 실행한다. 질의 서비스는 허용 범위·비밀값·중복을 검사한 뒤 기존 검색
(QK-RET-001)·생성(QK-GEN-001)을 `qk-index ask`와 같은 부품으로 실행하고, 결과를 본문 꼴 메시지로 나눠 상호작용 토큰으로 직접 갱신한다. 근거는 [research.md](research.md)에 있다.

## Technical Context

**Language/Version**: Python 3.13(기존). Worker는 Python Workers(`pywrangler`, QK-FND-001). CPU 한도를 넘으면 중계만 TypeScript로 옮긴다(R-13)

**Primary Dependencies**: 새 선택 의존성 묶음 `query = ["cryptography>=…"]`(질의 서비스의 Ed25519 재검사, R-04). 기존 `postgres` 묶음(`psycopg`). Worker는 패키지 의존성 없음(Web Crypto, VPC 바인딩)

**Storage**: 운영 PostgreSQL(OCI, `localhost`). 새 마이그레이션 `0007_query_role.sql`(역할 `qk_query`와 권한, data-model 4절). 표 추가 없음. 중복 판정 상태는 질의 서비스 메모리(R-10)

**Testing**: pytest. 가짜 서명 키(시험 안에서 만든 Ed25519 키 쌍), 가짜 Discord 수신부, 가짜 검색·생성 제공자(`ScriptedProvider` 등), 로컬 DB 시험(`QK_REQUIRE_LOCALDB=1`, 역할 권한).
실제 Discord·Workers AI는 사람 단계(M-01~M-04)

**Target Platform**: Worker는 Cloudflare Workers Free. 질의 서비스는 OCI A1 Ubuntu 22.04 aarch64(systemd), 회의 봇과 같은 인스턴스

**Project Type**: 기존 단일 패키지(`src/qello_knowledge`)에 Discord 도메인·어댑터와 질의 서비스 확장, Worker 겉껍질 교체

**Performance Goals**: 첫 응답 3초 안(Worker 중계 제한 2.5초), 답변·안내는 안내 전달 마감(60초) 안(SC-001)

**Constraints**: 질의 외부 호출 ≤ 20(FR-016), Worker는 질의 서비스 호출 최대 2회(중계, 시작 확인), 메시지 ≤ 4개·각 2,000자(FR-012), 원문·사용자 식별자 비기록(FR-021), 인스턴스 공인 포트 추가 없음(FR-018),
질의 서비스 DB 권한 최소(FR-019), 추가 고정비 월 0원(C-05)

**Scale/Scope**: 하루 질문 50건, 동시 처리 2. 새 모듈 약 9개, 마이그레이션 1개, CLI 하위 명령 1개, Worker 설정 1개, 운영 문서 1절, 결정 기록 1개

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 템플릿 상태라 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다. 설계 뒤 다시 점검한 결과도 같다.

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01 근거만 | 생성 결과(확인 불가 문장, 출처 목록)를 바꾸지 않고 보여 준다. 출처 확인 안 됨 경고 줄(FR-011) | 통과 |
| C-02 현재 상태는 원본 | 출처 항목에 수정일·수집 시각, 목록 머리 "자료 기준: 색인된 문서"(FR-013) | 통과 |
| C-03 자료는 데이터 | 자료 유래 글의 서식 글자 바꿈, 멘션 무력화(FR-014). 검색된 글을 명령으로 해석하지 않는다 | 통과 |
| C-04 작게 시작 | 명령 1개, 스레드·로그·피드백 없음, 사용자별 제한 없음(FR-005), 새 표 없음 | 통과 |
| C-05 비용 상한 | 추가 고정비 0(Workers Free, Workers VPC 베타 무료, Tunnel 요금은 구현 전 확인 — ADR-022), 질의당 약 38~51 Neurons, 실측 약 500~610 사람 확인 | 조건부 통과 — Tunnel 요금 확인 |
| 데이터 처리 정책(AGENTS.md 3.1) | Worker·Tunnel을 지나는 상호작용 본문의 보존·학습 사용은 미확인. 운영 구성 전 확인을 전제로 둔다(ADR-022 Data and cost, quickstart 3절) | 조건부 통과 — 정책 확인 |
| C-06 교체 가능한 경계 | `domain/discord.py`·`discord/`는 외부 SDK 없음. Discord HTTP는 `adapters/discord/`, 검색·생성은 기존 경계 그대로 | 통과 |
| C-07·C-08 색인 | 색인·동기화 변경 없음 | 해당 없음 |
| C-09 원본 읽기 전용, 쓰기는 답변 게시만 | Discord 쓰기는 상호작용 응답·갱신뿐. 봇 토큰을 서버에 두지 않는다(R-12) | 통과 |
| C-10 민감 정보 | 처리 중 응답 전 질문 비밀값 검사(FR-006), 운영 로그 허용 항목(FR-021), 서버 비밀값 파일 분리(R-08·R-14) | 통과 |
| C-11 명세 먼저 | 2026-10-25 실행 위치 결정을 spec에 먼저 반영했다(Clarifications, FR-008·015·016·018). plan·ADR-022 승인 전 구현하지 않는다 | 보류 — 사람 승인 |
| C-12 검증으로 닫기 | SC마다 자동 시험 또는 사람 단계(quickstart 1·4절). 중계·시작 확인 경합, 자리·마감, 검색 마감 주입, 역할 거부 목록의 실패 주입 시험(quickstart 1절) | 통과 |
| C-13 수치 조건 | 실측 기록 조건(FR-025) | 통과 |
| C-14 권한 확인 자료만 | Context는 QK-RET-001 노출 조건을 거친 것만. 출처는 생성 결과에서만 | 통과 |
| AGENTS.md 3.1 | 새 자료원·외부 모델 없음. 새 외부 경로(Workers VPC, Tunnel)는 ADR-022로 남김 | 통과 |
| AGENTS.md 3.2 | 답변 출처 표시. FR-015(출처 확인 안 됨) 예외는 QK-GEN-001에서 사람이 유지 | 예외 기록됨 |
| AGENTS.md 3.3·3.4 | 인덱스·평가 세트 변경 없음 | 해당 없음 |
| AGENTS.md 3.5 비용 | M-04 실행 전 예상량 보고·사람 확인 | 통과 |
| AGENTS.md 4절 변경 안전성 | 공유 인스턴스 변경은 팀원 동의 뒤, 명령마다 사람 승인. 되돌리기 절차(quickstart 3절) | 통과 |
| AGENTS.md 6절 민감정보 | 토큰·주소·채널 식별자를 저장소에 남기지 않는다. Worker 주소도 문서에 적지 않는다 | 통과 |

## Project Structure

### Documentation (this feature)

```text
specs/QK-BOT-001-discord-ask/
├── spec.md
├── plan.md              # 이 파일
├── research.md          # R-01~R-15
├── data-model.md        # 설정, 상호작용, 첫 응답, DB 역할, 작업·로그, 표시, 중복 판정
├── quickstart.md        # 자동 검증, 로컬 확인, 운영 구성, 실측
├── contracts/
│   ├── relay.md             # Discord → Worker → 질의 서비스
│   ├── discord-outbound.md  # 답변 갱신, 명령 등록
│   └── cli.md               # qk-query serve, register-commands
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks에서 만든다
docs/sdd/decisions/ADR-022-discord-query-path.md   # 새 결정 기록(Proposed)
```

### Source Code (repository root)

```text
src/qello_knowledge/
├── domain/discord.py            # Interaction, AccessDecision, FirstResponse, QueryJob 단계, RenderedReply, DedupEntry
├── discord/                     # 순수 로직(외부 호출 없음)
│   ├── __init__.py
│   ├── interactions.py          # 본문 해석, 첫 응답 결정
│   ├── access.py                # 허용 범위 판정
│   ├── notices.py               # 안내 문구 표(spec FR-011), 실패 종류 대응
│   ├── render.py                # 본문·출처 렌더링, 서식·멘션 무력화, 분할(FR-012~014)
│   └── signature.py             # Ed25519 검사(질의 서비스용, cryptography 지연 가져오기)
├── adapters/discord/
│   ├── __init__.py
│   └── webhook.py               # @original PATCH, 이어지는 메시지 POST, 다시 시도, 명령 등록 PUT(urllib)
├── query/
│   ├── app.py                   # POST /discord/interactions 경로 추가(기존 /healthz 유지)
│   ├── server.py                # 작업 실행기, register-commands 하위 명령
│   ├── jobs.py                  # 스레드 풀, 대기열 상한, 마감, 중복 판정 상태
│   ├── pipeline.py              # retrieve → generate(질의별 GenerationSettings) → render → deliver
│   └── worker.py                # 중계 Worker(서명 검사 + VPC fetch + 실패 안내)로 교체
├── config/registry.py           # Entrypoint.RELAY, 새 설정(data-model 1절), 진입점 조정
└── adapters/postgres/migrations/0007_query_role.sql

wrangler.toml                    # Worker 이름, python_workers 플래그, VPC 바인딩(서비스 ID는 placeholder)
pyproject.toml                   # [project.optional-dependencies] query
tests/unit/discord/              # 해석, 허용 범위, 안내 대응, 렌더링·분할, 서명
tests/unit/query/                # 첫 응답, 작업·마감·중복, 파이프라인(가짜), 원문 비기록, 설정 교차 검사
tests/unit/adapters/test_discord_webhook.py   # 가짜 수신부, 다시 시도, 404
tests/localdb/query/test_query_role.py        # 역할 권한(SC-010 로컬)
docs/ops/oci-production-store.md # 질의 서비스·cloudflared·query.env·되돌리기 절
.env.example                     # 생성기로 다시 만듦(설정 추가)
```

**Structure Decision**: 기존 단일 패키지 구조를 따른다. Discord 규칙은 `discord/`(순수)와 `adapters/discord/`(HTTP)로 나눠 C-06 경계 시험(`tests/unit/test_boundaries.py`)에 더한다.
질의 서비스는 기존 `query/` 진입점을 넓힌다. `indexer/ask_cli.py`는 바꾸지 않고 같은 부품을 가져다 쓴다.

## Phase 0·1 산출물

| 산출물 | 내용 |
| --- | --- |
| [research.md](research.md) | R-01 실행 위치, R-02 연결, R-03 첫 응답, R-04 서명, R-05 실행 모델, R-06 마감, R-07 DB 역할, R-08 토큰, R-09 표시 꼴, R-10 중복, R-11 조립, R-12 봇 토큰, R-13 Worker 언어, R-14 운영, R-15 실측 |
| [data-model.md](data-model.md) | 설정 표와 교차 규칙, 도메인 타입, `qk_query` 권한 |
| [contracts/](contracts/) | 중계, Discord 송신·등록, CLI |
| [quickstart.md](quickstart.md) | 검증·운영·실측 절차 |
| ADR-022 | Worker 중계 + 인스턴스 질의 서비스 결정(ADR-008 일부 개정) |

## 구현 Scope 승인이 필요한 것

TASK.md는 지금 명세·결정 기록만 허용한다. 구현 전에 다음을 TASK.md Scope에 더하는 사람 승인이 필요하다.

| 항목 | 이유 |
| --- | --- |
| `src/`·`tests/` 위 구조 | 구현 |
| `pyproject.toml`·`uv.lock` | 선택 의존성 `query`(`cryptography`) |
| 마이그레이션 `0007_query_role.sql` | 역할·권한. 운영 적용은 코드 병합 전(운영 문서 규칙) |
| `wrangler.toml` | Worker 배포 설정. 비밀값·서비스 ID는 넣지 않는다 |
| `.env.example` | 설정 생성기로 다시 만든다(새 설정, 진입점 변경). 손으로 고치지 않는다 |
| `adapters/postgres/store.py`의 선택 인자 `deadline` | 검색 호출마다 남은 시간 확인과 마감 시각 연결 취소(research R-06). 저장소 질의 수·외부 호출 계수 불변. 인자가 없으면 지금 동작 그대로라 색인·CLI 영향 없음, 기존 시험 유지 |
| 마이그레이션 0007의 RLS(`qk.embedding_usage`) | 질의 역할이 `purpose = 'query'` 행만 넣게 한다(data-model 4절). 운영 적용 전 색인·마이그레이션 역할이 소유자·슈퍼유저인지 확인 |
| `tests/unit/test_boundaries.py` | `discord` 경계 검사 추가 |
| `docs/ops/oci-production-store.md` | 운영 절차 |
| `docs/sdd/decisions/ADR-022-*.md`, ADR-008 링크 한 줄 | 결정 기록 |
| 공유 인스턴스 변경(`qkquery`, `qk-query.service`, `cloudflared`, `query.env`, DB 역할 로그인) | 팀원 동의(PR 리뷰) 뒤, 명령마다 사람 승인 |
| Cloudflare 계정 변경(터널, VPC Service, Worker 배포), Discord 포털 변경(수신 주소, 명령 등록) | 사람이 인증하고 승인 |

## 사람 결정이 필요한 것 (plan 승인 전)

1. ADR-022 승인(ADR-008 일부 개정). 팀원(인스턴스 관리자)의 공유 인스턴스 구성 요소 추가 동의는 PR 리뷰로 받는다.
2. Cloudflare Tunnel 요금과 Worker·Tunnel 트래픽의 데이터 처리 정책 확인(무료가 아니거나 학습 사용·장기 보존이면 C-05 승인 또는 결정 재검토). 운영 구성 전에 닫는다.
3. 질의 서비스 전용 Workers AI 토큰 발급(R-08)과 DB 역할 신설(R-07) 동의.
4. 중복 판정 상태를 메모리에 두는 위험(R-10)을 받아들일지. spec FR-010·SC-011에 예외로 적어 두었다.
5. 인스턴스 바깥 방향 UDP 7844 사용(R-02 운영 전제). 열 수 없으면 ADR-022 Revisit.
6. 운영 색인·마이그레이션의 DB 역할이 표 소유자나 슈퍼유저인지 확인(data-model 4절 RLS 전제). 아니면 0007에 그 역할의 정책을 더한다.

## 다른 명세에 넘기는 것

| 대상 | 넘기는 내용 |
| --- | --- |
| QK-OBS-001 | 질의 로그(질문 원문 저장 옵션, 사용자 식별자, ADR-016), 피드백 버튼, `/sources`. 질의 서비스의 운영 로그 한 줄(`QueryRunLog`)과 `run_id`를 이어 쓸 수 있다 |
| QK-BOT-002 | 스레드 대화. 지금은 스레드를 허용 범위 밖으로 둔다(FR-004) |
| QK-SYN-002 | `/reindex`. 명령 등록 목록(통째 덮어쓰기)에 함께 넣어야 한다(R-12) |
| QK-OBS-002 | 질의 서비스·터널 상태 감시와 알림(ADR-021의 동기화 실패 알림과 같은 경로를 쓸 수 있다) |
| `docs/sdd/research/tokens.md` | 6절 운영 비밀값 위치(질의 서비스 전용 Workers AI 토큰, 봇 토큰은 로컬만), T-03 답 |
| `docs/sdd/roadmap.md` | 1.8~1.10 상태 열, 1.11 Issue 링크(#58). 로드맵 수정은 사람 승인 대상 |

## 독립 검토 이력

같은 세션이 계획을 쓰고 고쳤으므로, 검토는 오른쪽 Herdr 패널의 Codex(읽기 전용, 별도 지침)가 했다(AGENTS.md 2절).

| 차수 | 결과 | 지적 | 반영 |
| --- | --- | --- | --- |
| 1차(2026-10-25) | 변경 요청 | H4·M6·L2 | 중계 경합(두 단계 시작), 자리·마감, 검색 마감 주입, 최소 권한, 생성 설정 산식, QUIC 전제, 서명 실패 무기록, 재시작 예외, 데이터 정책 게이트, 수락 예외, Scope 누락 |
| 2차 | 변경 요청 | 기존 12건 중 해소 7·부분 5, 남은 H2·M3·L1 | RLS로 색인 예약 차단, `PostgresStore` 마감, 시작 대기 하한 4초, 404 재시도 통일, 감시·전달 분리, 두 단계 절차 반영 |
| 3차 | 변경 요청 | 해소 5·부분 1, 남은 H1·M2 | 수명 자리, 전달 시간 산식, `SET` 대신 연결 취소(호출 계수 불변) |
| 4차 | 승인(계획 범위) | 새 H·M 0, L1 | 대기 크기 설명, `cancel_safe`·`urllib` 제약을 research에 기록 |

승인은 계획 정합성 범위이고, plan·ADR-022의 사람 승인과 운영 게이트는 그대로다.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| ADR-008 "질의응답은 Workers"에서 벗어남 | 동기 검색·생성 코드와 Workers 30초·CPU 한도(R-01) | 전부 Workers는 비동기 재작성·미확인이 크고, 인스턴스 단독은 도메인·노출·장애 안내 문제(ADR-022) |
| 서명 검사를 두 번 | 네트워크 경로를 믿지 않는 이중 방어(R-04) | 한 번만 하면 Worker·터널 설정 실수 때 질의 서비스가 바로 노출된다 |
