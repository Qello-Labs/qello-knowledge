# Task Contract: Discord `/ask` 질의응답 창구 (QK-BOT-001)

> Generated at: `2026-10-25`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-115` / https://tkv123.atlassian.net/browse/SCRUM-115 (상위 `SCRUM-42` 팀 RAG 구축, GitHub Issue 폼으로 자동 생성)
- 기능명세서 ID / 링크: `QK-BOT-001` / `specs/QK-BOT-001-discord-ask/`. 로드맵 WBS 1.11, 요구사항 FR-BOT-01, 02, 06, 07(저장소에 원문 없음)
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#58`
- Branch: `feat/SCRUM-115-gh-58-discord-ask`
- Base branch: `main`. 2026-10-25 `origin/main` `f11e146`(#56 병합)에서 분기했고, 2026-10-26 `d7c9e3f`(#60 병합)로 rebase했다
- 이전 계약: `f11e146`의 `TASK.md`(SCRUM-103 H07 기록). 그 Decisions 기록은 git 이력에 남긴다

## Objective

- 팀원이 허용된 Discord 채널에서 `/ask`로 질문하면 3초 안에 처리 중 응답을 받고, QK-RET-001 검색과 QK-GEN-001 생성을 거친 출처 링크가 붙은 답변으로 갱신되게 한다(로드맵 1.G).
- ADR-008이 넘긴 Workers 질의 경로 ↔ 운영 DB 연결 방식을 결정 기록으로 정한다.
- 명세를 먼저 쓰고 사람 승인을 받은 뒤 같은 브랜치에서 계획·작업 목록·구현으로 넘어간다(로드맵 1절 원칙 4).

## Scope

명세·계획 단계에서 정한 범위와, 2026-10-26 plan 승인으로 더한 구현 범위다.

- `TASK.md`
- `specs/QK-BOT-001-<짧은 이름>/`: `spec.md`(이번 주), 승인 뒤 `plan.md`·`research.md`·`tasks.md` 등 Spec Kit 산출물
- `docs/sdd/decisions/ADR-0xx-<짧은 이름>.md`(새 결정 기록, 번호는 작성 때 확인. ADR-021은 PR #57이 쓰고 있다): Workers ↔ 운영 DB 연결(HTTP RPC 계층, 공인 포트를 열지 않는 경로)의 선택과 대안, 비용·데이터 처리 정책, 공유 인스턴스 영향
- 명세에서 다룰 결정:
  - HTTP 상호작용 수신, 요청 서명 검사, 지연 응답과 답변 갱신 방식
  - Workers AI 바인딩 생성 제공자(QK-GEN-001 `GenerationProvider`), 바인딩 응답의 Neurons·종료 사유
  - 답변 표시: 출처 링크 꼴, 답변 분할, "출처 확인 안 됨"·"출력 잘림" 표시
  - 접근 제어: 허용 채널·역할과 허용 밖 요청 처리
  - 상태별 오류 안내 문구(검색 실패, 전송 차단, 생성 실패, 시간 초과, 예산 초과)
  - 질의 전체 시간과 Workers 한도(요청당 CPU, subrequest, 응답 뒤 처리 시간) 측정 방법, 넘을 때의 대안(QK-FND-001 research의 TypeScript 진입점)
  - `wrangler.toml`과 `DISCORD_BOT_TOKEN` 필요 여부

구현 범위(2026-10-26 plan·ADR-022 사람 승인, plan "구현 Scope 승인이 필요한 것"):

- `src/qello_knowledge/`: `domain/discord.py`, `discord/`, `adapters/discord/`, `query/`(`app.py`·`server.py`·`jobs.py`·`pipeline.py`·`worker.py`), `config/registry.py`
- `src/qello_knowledge/adapters/postgres/store.py`: 선택 인자 `deadline`만 더한다(research R-06). 인자가 없으면 지금 동작 그대로
- `src/qello_knowledge/adapters/postgres/migrations/0007_query_role.sql`: 역할 `qk_query`, 권한, `qk.embedding_usage` RLS(data-model 4절)
- `tests/unit/discord/`, `tests/unit/query/`, `tests/unit/adapters/test_discord_webhook.py`, `tests/localdb/query/`, `tests/unit/test_boundaries.py`(`discord` 경계 추가)
- `pyproject.toml`·`uv.lock`: 선택 의존성 묶음 `query`(`cryptography`)
- `wrangler.toml`: 비밀값·서비스 ID는 placeholder
- `.env.example`: 설정 생성기로 다시 만든다(손으로 고치지 않는다)
- `docs/ops/oci-production-store.md`: 질의 서비스·`cloudflared`·`query.env`·되돌리기 절
- `docs/sdd/decisions/ADR-022-discord-query-path.md`, ADR-008 링크 한 줄
- `specs/QK-BOT-001-discord-ask/tasks.md`

## Explicit exclusions

- 공유 인스턴스 변경(`qkquery` 계정, `qk-query.service`, `cloudflared`, `query.env`, DB 역할 로그인·마이그레이션 운영 적용), Cloudflare 계정 변경(터널, VPC Service, Worker 배포),
  Discord 포털 변경(수신 주소, 명령 등록). 팀원(인스턴스 관리자) 동의(PR 리뷰) 뒤, 사람이 인증하고 명령마다 승인한 것만 한다.
- 질의 로그·피드백 버튼·`/sources`·질의 원문 저장 옵션(QK-OBS-001), 스레드 대화·질의 재작성(QK-BOT-002), `/reindex`(QK-SYN-002), 질문 분류(QK-TRK-001), 요약 게시.
- 검색·생성 동작 변경(QK-RET-001·QK-GEN-001 범위). 넘겨받은 결정 밖의 변경이 필요하면 따로 묻는다.
- `AGENTS.md`, `CLAUDE.md`, `.claude/**`, constitution, 로드맵 수정. 원본 자료원에 쓰기.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, Discord Public Key·Application ID, `.env` 값, 접속 주소, 내부 도메인, OCI 계정 식별자, 비공개 원문, 질문·답변 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음. QK-RET-001이 접근 범위를 거른 Context만 쓴다
- 외부 API로 보내는 데이터: 질문과 Context 청크 본문이 Workers AI(질의 임베딩 embeddinggemma, 생성 qwen3-30b-a3b-fp8)로 간다(기존 결정 ADR-002·ADR-009). 답변 본문과 출처 링크가 Discord로 간다(constitution C-09 범위). 전송 직전 검사는 QK-SEC-001 `check_outgoing`(QK-GEN-001이 연결)
- 예상 임베딩·생성 호출량과 무료 한도 대비: 이번 주(명세·결정 기록)는 0 Neurons. 구현 단계 기본 검증은 가짜 제공자로 0 Neurons. 운영은 질의당 약 51 Neurons, 하루 50건 약 2,550으로 질의응답 예비분(3,000) 안(QK-RET-001 spec 추정, 실측 전). 실측은 사람 확인 뒤 소수 질문으로 하고 실행 전에 예상량을 적는다
- 새 외부 경로(Cloudflare Tunnel 등)의 요금·데이터 처리 정책은 결정 기록에서 확인한다. 유료 설정이 필요하면 사람 승인(C-05)
- 인덱스 버전 변경: 없음(`iv-4c0bc4fcc642` 유지)

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `TASK.md`, `specs/QK-BOT-001-*/` | Byuntil | 사람 리뷰(명세 승인) |
| 새 ADR(Workers ↔ DB 연결) | Byuntil | 사람 리뷰, 공유 인스턴스 구성 요소를 더하면 팀원(인스턴스 관리자) 확인 |
| 구현(`src/`, `tests/`, `pyproject.toml`, `uv.lock`, 마이그레이션, `wrangler.toml`, `.env.example`, 운영 문서) | Byuntil | 사람 리뷰, 0007 운영 적용 전 팀원(인스턴스 관리자) 확인 |

## Existing user-owned changes

- 2026-10-25 `origin/main`(`f11e146`)에서 별도 worktree(`../qello-knowledge-bot-001`)로 브랜치를 만들 때 `git status --short` 결과: 변경 없음.
  기본 체크아웃은 다른 작업(`chore/SCRUM-113-remove-index-sync-workflow`)이 쓰고 있어 건드리지 않았다.

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
```

사람 단계(quickstart 2~4절): Workers 로컬 실행(`pywrangler dev`) 확인, 운영 구성 뒤 Discord 실측. 실측 전에 예상 Neurons를 적는다.

## Completion criteria

- `spec.md`가 사람 리뷰로 승인되고, Workers ↔ DB 연결 결정 기록이 승인된다 — 리뷰 기록
- (구현 단계) 서명 검사·지연 응답·답변 분할·허용 밖 채널 거부·상태별 오류 문구가 동작한다 — 단위 시험(가짜 검색·생성 제공자, 0 Neurons)
- (구현 단계) 허용된 Discord 채널에서 `/ask`가 3초 안에 처리 중 응답을 보내고 출처 링크가 붙은 답변으로 갱신되며, 자료에 없는 질문에 "확인할 수 없습니다"로 답한다 — 사람 확인 뒤 소수 질문 실측, 화면 기록(값 가림)

## Decisions

- 2026-10-25 사실: 사용자 요청으로 GitHub Issue #58을 작업 폼 형식으로 열었고, `Jira subtask` 워크플로가 SCRUM-115를 SCRUM-42 아래에 만들었다(스프린트는 상위 이슈를 따름).
- 2026-10-25 사실: 선행 WBS 1.10 QK-GEN-001(#53, PR #54 병합)과 1.9 QK-RET-001(#51, PR #52 병합)이 끝났다. 로드맵 상태 열은 1.8~1.10이 갱신되지 않은 상태다(로드맵 수정은 이 작업 범위 밖).
- 2026-10-25 사실: 단계 게이트 0.G는 미완료 상태로 Phase 1을 계속 진행한다(2026-10-20 사용자 결정, Issue #53 기록).
- 2026-10-25 사실: 기본 체크아웃이 다른 작업 브랜치로 바뀌어 있어, 이 작업은 별도 worktree에서 한다. 브랜치 이름 type은 이전 질의 트랙(#52, #54)처럼 명세와 구현을 한 브랜치에서 하는 `feat`로 했다.
- 2026-10-25 사용자 결정(명세): 답변은 기본 공개 + "나만 보기" 선택 인자(Q1 C), Phase 1 사용자별 호출 제한 없음(Q2 A).
- 2026-10-25 사실: 명세 독립 검토를 오른쪽 Herdr 패널의 Codex(읽기 전용)로 했다. 1차 변경 요청 11건 → 재검토 변경 요청 5건 → 2차 재검토 승인(명세 검토 범위). 명세 커밋 `ee4e724`.
- 2026-10-25 사용자 결정(H1): Workers `waitUntil` 30초와 생성 45초 충돌은 명세에 마감 조건만 두고 실행 방식은 계획 단계에서 정한다.
- 2026-10-25 사용자 결정(계획): Cloudflare Worker는 서명 검사·중계만 하고, 검색·생성은 OCI 공유 인스턴스의 질의 서비스가 기존 코드로 실행한다. 연결은 Workers VPC + Cloudflare Tunnel
  (공인 포트·공개 호스트명 없음). ADR-008 일부 개정이라 ADR-022(Proposed)를 쓰고, 승인과 팀원(인스턴스 관리자) 동의를 PR 리뷰로 받는다. 이 결정을 spec에 먼저 반영했다(C-11).
- 2026-10-26 사실: 계획 독립 검토를 오른쪽 Herdr 패널의 Codex(읽기 전용)로 네 차례 했다. 변경 요청 12건 → 6건 → 3건 → 승인(계획 범위, 비차단 L1 반영). 이력은 plan "독립 검토 이력".
  반영하면서 spec의 FR-007·FR-008·FR-009·FR-010·FR-016, US1-1·US1-5, SC-011·SC-013, Edge Cases, Assumptions를 고쳤다(C-11).
- 2026-10-25 사실: plan·research·data-model·contracts·quickstart와 ADR-022 초안을 썼다. 구현 Scope 추가(src·tests·pyproject·마이그레이션·wrangler·운영 문서)는 plan 승인 뒤 사람 승인으로
  이 계약에 더한다(plan "구현 Scope 승인이 필요한 것").
- 2026-10-26 사용자 결정: plan과 ADR-022 초안을 승인하고, plan "구현 Scope 승인이 필요한 것" 표의 저장소 항목 전부를 Scope에 더했다. 공유 인스턴스·Cloudflare·Discord 변경은 제외로 남긴다.
  ADR-022 상태(Accepted)와 팀원(인스턴스 관리자) 동의는 PR 리뷰로 받는다. 운영 게이트(Tunnel 요금·데이터 처리 정책, UDP 7844, 전용 Workers AI 토큰, 색인 역할 소유권 확인)는 운영 구성 전에 닫는다.
- 2026-10-26 사용자 결정: 중복 판정 상태를 질의 서비스 메모리에 두는 위험(research R-10, spec FR-010·SC-011 예외)을 받아들인다.
- 2026-10-26 사실: 그사이 `origin/main`에 #59(예약 동기화 워크플로 삭제)와 #60(임베딩 Neurons 예상 보정)이 병합됐다. 계획 산출물을 커밋한 뒤 rebase로 반영한다.
  열린 PR #62(Workers AI 토큰 Qello 전용 계정 교체)는 R-08 전용 토큰 발급과 겹칠 수 있어 운영 구성 때 다시 본다.
