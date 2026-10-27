# Task Contract: #58 마무리 — 운영 질의 릴리스 갱신, Discord 재확인, 문서 정리

> Generated at: `2026-10-28`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-115`(상위 `SCRUM-42`) / https://tkv123.atlassian.net/browse/SCRUM-115
- 기능명세서 ID / 링크: `QK-BOT-001` / `specs/QK-BOT-001-discord-ask/`
- 팀 스프린트 ID: `QELLO-S2026-W43`(Issue #58 기준)
- GitHub Issue: `#58`
- Branch: `docs/SCRUM-115-gh-58-query-release-recheck`
- Base branch: `main`. 2026-10-28 `origin/main` `ce6d1d8`(#84 병합)에서 분기했다

## Objective

- 운영 질의 릴리스를 `3a5a98e`(#65)에서 최신 `main`으로 갱신하는 절차를 운영 문서에 남기고, 그 절차로 운영을 갱신한다.
  질의 경로에 영향을 주는 병합: #71 비밀값 규칙 한글 경계, #73 문맥 예산 3,000(ADR-025), `query/app.py` import 이동.
- 갱신한 운영에서 Discord로 Q05(H05 SC-002 실패 문항)와 한글에 붙은 합성 토큰 차단(#71)을 다시 확인하고, 가능하면 SC-013(나만 보기)을 다른 계정 화면으로 대조한다.
- Issue #58 완료 조건의 증빙을 `tasks.md`에 정리하고, 사람 결정이 필요한 상태 변경(spec 승인, ADR-025 Accepted)을 사용자에게 묻는다.

## Scope

- `docs/ops/oci-production-store.md` 7절: 질의 릴리스 갱신 절차(새 릴리스 디렉터리 준비, `uv sync --locked --extra query --extra postgres`, `qk-query check`,
  서비스 전환, 루프백 `/healthz`, 옛 릴리스로 되돌리기). 실제 운영 구성(유닛의 `WorkingDirectory`·`ExecStart`, 릴리스 준비 방식)은 읽기 전용 확인으로 맞춘다
- `specs/QK-BOT-001-discord-ask/quickstart.md` 3절: 갱신 절차를 가리키는 한 줄(필요할 때만)
- `specs/QK-BOT-001-discord-ask/tasks.md`: T061 체크, H02 "남은 일" 갱신, 릴리스 갱신·Discord 재확인 기록(H05와 같은 꼴, 값·주소·식별자 없이)
- `specs/QK-BOT-001-discord-ask/spec.md` `Status`, `docs/sdd/decisions/ADR-025-context-budget-3000.md` `Status`: 사용자가 승인할 때만, 승인 날짜와 함께 바꾼다
- `TASK.md`
- 운영(Herdr 창 `wC:pF`의 Bastion 세션에서만, 명령 단계마다 사용자 승인):
  - 읽기 전용 확인: 지금 릴리스 커밋, `qk-query.service` 상태와 유닛 내용, `query.env` 소유자·모드·키 이름(값 출력 금지), 디스크 여유, 새 커밋에서 `qk-query check`
  - 승인받은 변경: 새 릴리스 준비, `qk-query.service` 전환·재시작. 옛 릴리스는 되돌리기용으로 남긴다
  - 질의 서비스 journal(원문 없는 JSON)로 상태·호출 수·Neurons 확인
- Discord 재확인(사람이 보낸다): Q05 1건, 한글에 붙은 합성 토큰 질문 1건, 가능하면 나만 보기 다른 계정 대조. v2 세트 전체 재실행 여부는 사용자가 정한다
- Issue #58 본문 체크박스와 "검증 결과·증빙" 갱신: 초안을 보여주고 승인받은 뒤에만 쓴다

## Explicit exclusions

- 코드·시험·평가 세트·정답 라벨 변경. 질문 세트 v1·v2 파일 변경
- `qk-sync`·`/opt/qello-knowledge` 체크아웃·`sync.env`, 회의 봇 등 팀원 서비스, `qk-cloudflared`·터널·Worker·VPC Service·Discord 수신 주소·명령 등록 변경
- 운영 DB 쓰기, 마이그레이션 적용, `qk_query` 역할 변경, `query.env` 값 변경(새 릴리스가 새 키를 요구하면 멈추고 사용자에게 알린다)
- Jira SCRUM-115 상태 변경(주간 리뷰에서 사람이 한다). 사람이 요청하지 않은 원본 자료원 쓰기
- `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env`·`query.env` 값, 비공개 원문, 실제 주소·OCID·도메인은 기록하지 않는다. 합성 토큰은 실행 때 만들고 어디에도 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: Discord 재확인 질문(Q05)과 그 Context 청크가 Workers AI로 간다(H05와 같은 경로). 합성 토큰 질문은 전송 전 검사에서 막혀 보내지 않는 것을 확인한다
- 예상 임베딩·생성 호출량과 무료 한도 대비: 릴리스 갱신 0 Neurons. Q05 1건 약 15~20 Neurons, 합성 토큰 질문 0 Neurons(예상).
  v2 세트 전체(11개)를 다시 돌리면 약 220 Neurons. 실행 전에 당일 사용량을 확인해 보고한다(무료 10,000, 질의 예비분 3,000)
- 인덱스 버전 변경: 없음(`iv-4c0bc4fcc642` 유지). 질의 쪽 문맥 예산 기본값만 2,000 → 3,000(ADR-025, 이미 `main`에 병합)

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `docs/ops/oci-production-store.md`, `specs/QK-BOT-001-discord-ask/{tasks,quickstart,spec}.md`, ADR-025, `TASK.md` | Byuntil | 사람 리뷰. PR 전 오케스트레이터 세션(구현 세션과 다른 세션)이 diff를 검토한다 |
| 운영 `qk-query` 질의 릴리스·서비스 | Byuntil(공유 인스턴스 관리자 동의 범위 안) | 명령 단계마다 사람 승인 |

## Existing user-owned changes

- 2026-10-28 `origin/main`(`ce6d1d8`)에서 브랜치를 만들 때 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
node --test workers/relay/relay.test.ts
```

운영: 새 릴리스에서 `qk-query check` 누락·형식 오류 0, 전환 뒤 `qk-query.service` active·재시작 0, 루프백 `/healthz` 200.

## Completion criteria

- 운영 질의 릴리스가 최신 `main` 커밋이고, `qk-query check`·서비스 상태·`/healthz`를 확인했으며, 되돌리기 경로(옛 릴리스)가 남아 있다 — 운영 확인 기록(`tasks.md`)
- 질의 릴리스 갱신 절차가 운영 문서에 있고 실제 운영 구성과 맞는다 — diff, 운영 읽기 전용 확인
- Discord에서 Q05 재확인 결과와 한글에 붙은 합성 토큰 차단 결과가 값 없이 `tasks.md`에 기록된다. SC-013 대조는 했으면 결과, 못 했으면 미확인과 사유 — 사람 화면 확인, 운영 로그
- `tasks.md` T061 체크. spec·ADR-025 상태와 Issue #58 본문은 사용자 결정대로 반영한다

## Decisions

- 2026-10-28 사실: ADR-022 Accepted, ADR-025 Proposed, `spec.md` `Status: Draft`. 운영 질의 릴리스 `3a5a98e`(tasks.md H02·H05)
- 2026-10-28 사실(코드 확인): `3a5a98e..ce6d1d8`의 질의 설정 변경은 `QK_RETRIEVAL_CONTEXT_BUDGET` 기본값 3,000과 색인 전용 `QK_CODE_CHUNKING`(질의 진입점 아님)뿐이다.
  `query.env`에 예산 키가 없으면 새 릴리스는 3,000을 쓴다. 키 이름만 읽기 전용으로 확인한다
- 2026-10-28 사용자 승인: TASK.md 초안 확정. 읽기 전용 확인, 단계 A(새 릴리스 준비, `--no-dev` 포함), 단계 B(전환)를 각각 승인했다
- 2026-10-28 사실(운영): 질의 릴리스를 `3a5a98e` → `ce6d1d8`로 갱신했다. 유닛은 링크 `/opt/qello-knowledge-query-current`를 가리키고 옛 릴리스·유닛 백업을 남겼다.
  `qk-query check` 통과, 전환 뒤 active·재시작 0·`/healthz` 200. 기록은 `tasks.md` "질의 릴리스 갱신과 H05 재확인"
- 2026-10-28 사용자 결정: Discord 재확인은 Q05 + 합성 토큰만 한다(v2 세트 전체 재실행 안 함). Q05는 나만 보기로 보내고 다른 계정으로 대조한다
- 2026-10-28 사람 판정: Q05 통과, SC-013(Q05·합성 토큰 안내 모두 다른 계정에 안 보임) 통과. 합성 토큰은 `outgoing_blocked`, 호출 0. 사용 22.11 Neurons(측정)
- 2026-10-28 사용자 결정: `spec.md` 승인(Status Approved), ADR-025 Accepted
