# Task Contract: QK-BOT-001 운영 게이트·실측 기록 (H00~)

> Generated at: `2026-10-26`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-115` / https://tkv123.atlassian.net/browse/SCRUM-115 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: `QK-BOT-001` / `specs/QK-BOT-001-discord-ask/`(구현은 PR #64로 병합)
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#58`
- Branch: `docs/SCRUM-115-gh-58-discord-ask-ops`
- Base branch: `main`. 2026-10-26 `origin/main` `3a5a98e`(#65 병합)에서 분기했다
- 이전 계약: `e07351f`의 `TASK.md`(QK-BOT-001 명세·구현). `main`의 직전 계약(QK-CHK-001, `3a5a98e`)은 git 이력에 남긴다

## Objective

- #58의 남은 완료 조건(허용 채널 `/ask` 실측)으로 가는 사람 단계 가운데 H00 운영 게이트를 닫고 근거를 기록한다(`specs/QK-BOT-001-discord-ask/tasks.md` 사람 단계).
- H01 이후(배포·구성·실측)는 H00 결과를 보고 사람이 이 계약에 더한다.

## Scope

- `TASK.md`
- `docs/sdd/decisions/ADR-022-discord-query-path.md`: Data and cost의 미확인 항목(Tunnel 요금, Worker·Tunnel 트래픽의 보존·학습 사용)과 UDP 7844 확인 결과
- `docs/sdd/research/tokens.md`: 질의 서비스 전용 토큰 `qk-workers-ai-query-prod` 행과 확인 결과(값·계정 ID 없음)
- `specs/QK-BOT-001-discord-ask/tasks.md`: 사람 단계 H00 상태와 실행 기록, T061 체크 정리
- `docs/ops/oci-production-store.md` 7절: H00 확인으로 절차 문장을 고쳐야 할 때만

## Explicit exclusions

- 공유 인스턴스 변경(`qkquery`, `qk-query.service`, `cloudflared`, `query.env`, `qk_query` 로그인·암호), OCI 보안 목록·호스트 방화벽 변경,
  Cloudflare 계정 변경(터널, VPC Service, Worker 배포), Discord 포털 변경. H00은 읽기 전용 확인만 한다.
- `src/`, `tests/`, 마이그레이션, `wrangler.toml` 변경. 필요해지면 따로 묻는다.
- `AGENTS.md`, `CLAUDE.md`, `.claude/**`, constitution, 로드맵 수정. 원본 자료원에 쓰기. Jira 상태 변경.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문, 계정·터널·서비스 ID, 접속 주소, 보안 목록 OCID는 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 해당 없음(공식 문서 조회, OCI 설정 읽기 전용 조회)
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons
- 인덱스 버전 변경: 없음(`iv-4c0bc4fcc642` 유지)

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `TASK.md`, `specs/QK-BOT-001-discord-ask/tasks.md`, `docs/sdd/research/tokens.md` | Byuntil | 사람 리뷰 |
| ADR-022 Data and cost 보강, 운영 문서 7절 | Byuntil | 사람 리뷰, 팀원(인스턴스 관리자) 확인 |

## Existing user-owned changes

- 2026-10-26 `origin/main`(`3a5a98e`)에서 브랜치를 만들 때 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
```

문서만 바꾸므로 위 두 줄이 해당한다.

## Completion criteria

- ADR-022 Data and cost에 Tunnel 요금, Worker·Tunnel 트래픽의 보존·학습 사용 정책이 공식 문서 URL·조회일과 함께 있고, 미확인으로 남는 것은 그렇다고 적혀 있다 — 리뷰
- 인스턴스 바깥 방향 UDP 7844 사용 가능 여부가 읽기 전용 확인 결과로 기록돼 있다 — 리뷰(값 가림)
- 질의 서비스 전용 토큰의 이름·권한 범위·만료·유효 확인이 값 없이 기록돼 있다 — 리뷰

## Decisions

- 2026-10-26 사실: PR #64가 병합됐다(`369b2ec`). #58은 열려 있고, 남은 완료 조건은 허용 채널 실측(H05)이다. 남은 사람 단계는 H00 일부(요금·데이터 처리 정책, UDP 7844, 전용 토큰)와 H01~H05다.
- 2026-10-26 사용자 결정: H00부터 시작한다. 사용자가 질의 서비스 전용 Workers AI 토큰을 이미 만들었다(값은 대화·저장소에 두지 않는다).
- 2026-10-26 사용자 결정: 이 계약 초안대로 진행한다(H00 읽기 전용 확인과 문서 기록만).
- 2026-10-26 사실: Tunnel 나가는 연결은 무료다. Worker·Tunnel 트래픽은 Self-Serve 약관·DPA의 목적 제한 조항만 있고 학습 금지 명시 문장은 없다. Workers Logs는 새 Worker에서 기본으로 켜지고 Free에서 3일 보존한다(ADR-022 Evidence).
- 2026-10-26 사용자 결정: 위 데이터 처리 수준을 받아들인다. Workers Logs는 H01~H05 동안 기본값으로 두고, H01에서 본문 미기록을 확인한 뒤 H05 뒤 `invocation_logs` 끄기를 다시 정한다.
  `wrangler.toml` 변경이 필요해지면 그때 범위에 더한다.
- 2026-10-26 사용자 결정: 전용 토큰은 `qk-workers-ai-query-prod`, Qello 전용 계정 소유, Workers AI만, TTL 365일이다. verify `active`는 사용자가 확인했다.
- 2026-10-26 사실(승인 뒤 실행, 읽기 전용): OCI 보안 목록 egress는 모든 프로토콜·`0.0.0.0/0` 허용이고 NSG는 없다. Bastion 세션(TTL 30분, 확인 뒤 삭제)으로 본 호스트 OUTPUT 정책은 ACCEPT이고,
  UDP·7844 차단 규칙이 없다(nftables accept, ufw 꺼짐). 아무 설정도 바꾸지 않았다.
- 2026-10-26 사실: `main`의 QK-CHK-001 계약이 `ADR-022-code-sources.md`를 만들 예정인데, ADR-022는 이미 `ADR-022-discord-query-path.md`가 쓰고 있다. 이 작업 범위 밖이라 그 작업 담당자에게 알린다.
