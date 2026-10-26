# Task Contract: Workers AI 토큰을 Qello 전용 Cloudflare 계정으로 교체

> Generated at: `2026-10-26`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-117` / https://tkv123.atlassian.net/browse/SCRUM-117 (상위 `SCRUM-42` 팀 RAG 구축, GitHub Issue 폼으로 자동 생성)
- 기능명세서 ID / 링크: 해당 없음: 운영 자격 증명 교체 작업이다
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#61`
- Branch: `chore/SCRUM-117-gh-61-cloudflare-token-rotation`
- Base branch: `main`. 2026-10-26 `origin/main` `d7c9e3f`(#60 병합)에서 별도 worktree로 분기했다
- 이전 계약: `d7c9e3f`의 `TASK.md`(SCRUM-114). 그 Decisions 기록은 git 이력에 남긴다

## Objective

- Workers AI 토큰을 Qello 전용 Cloudflare 계정의 계정 소유 토큰으로 옮긴 사실과 확인 결과를 기록한다.
- 서버 교체가 별도 이슈 없이 이뤄진 것을 이 이슈로 바로잡는다.

## Scope

- `TASK.md`
- `docs/sdd/research/tokens.md`: 6절 보관 위치·이름, 7절 확인 결과(값·계정 식별자 없음)
- 이미 끝난 운영 변경(사람이 값 입력, 기록만 한다): 서버 `/etc/qello-knowledge/sync.env`의 `CLOUDFLARE_API_TOKEN`·`CLOUDFLARE_ACCOUNT_ID`, 로컬 `.env`의 같은 두 값

## Explicit exclusions

- `src/`·`tests/`·`pyproject.toml`·`uv.lock`·마이그레이션·`.github/workflows/` 변경.
- 질의 서비스용 `qk-workers-ai-query-prod`, Worker·Tunnel·Workers VPC 생성(QK-BOT-001, ADR-022).
- 임베딩 모델·인덱스 변경, 재색인.
- `AGENTS.md`, `CLAUDE.md`, `.claude/**`, constitution, 로드맵 수정. 원본 자료원에 쓰기.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 계정 ID, 접속 주소, OCI 계정 식별자는 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 바뀌지 않는다(같은 Workers AI 모델, 계정만 바뀜)
- 예상 임베딩·생성 호출량과 무료 한도 대비: 확인에 0.01 Neurons를 썼다. 무료 할당은 새 계정 기준(하루 10,000 Neurons)
- 인덱스 버전 변경: 없음(`iv-4c0bc4fcc642` 유지)

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `TASK.md`, `docs/sdd/research/tokens.md` | Byuntil | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-26 `origin/main`(`d7c9e3f`)에서 별도 worktree(`../qello-knowledge-cf-rotation`)로 브랜치를 만들 때 `git status --short` 결과: 변경 없음.
  기본 체크아웃은 다른 작업(`fix/SCRUM-114-neuron-estimate-calibration`)이 쓰고 있어 건드리지 않았다.

## Validation

```bash
python scripts/preflight.py
git diff --check
```

## Completion criteria

- 서버·로컬 새 토큰이 동작한다 — 서버: 예약 실행 성공, 벡터 검색 1회 임베딩 성공(측정 0.01 Neurons). 로컬: 계정 소유 토큰 확인 `active`
- 기존 계정 토큰이 지워졌다 — 사용자가 기존 계정 대시보드에서 확인
- 교체 기록이 tokens.md에 남는다(값 없음) — 이 PR 리뷰

## Decisions

- 2026-10-26 사용자 결정: Qello 전용 Cloudflare 계정을 새로 만들고, Workers AI 토큰을 쓰는 곳마다 나눈다. 이번에는 `qk-workers-ai-index-prod`(서버)와 `qk-workers-ai-dev`(로컬) 두 개.
- 2026-10-26 사용자 결정: 예약 실행(00:30 UTC) 전에 교체한다.
- 2026-10-26 사실: 오른쪽 Herdr 패널의 Codex가 사용자와 함께 서버 `sync.env` 두 값을 숨김 입력으로 교체했다(파일 시각 10-25 17:02 UTC, root:qksync 0640 유지). 모델 조회 HTTP 200.
  이때 별도 Jira 이슈 없이 SCRUM-114 계약 아래에서 진행됐다. 이 이슈(SCRUM-117, #61)로 기록을 옮긴다.
- 2026-10-26 사실: 예약 실행 `sync-20261026T003032-b9cadf41` succeeded(UNCHANGED 79·SKIP 1, 임베딩 호출 0). 같은 실행 뒤 `qk-sync-notify@*` 로그 0줄(SCRUM-108 완료 조건 증빙과 겹침).
- 2026-10-26 사실(사용자 재인증 뒤 Bastion 세션, 읽기 전용 + 임베딩 1회): `qksync` 환경 벡터 검색 1회 종료 코드 0, 임베딩 호출 1, `qk-index usage` 질의 0.01 Neurons(측정값).
  서버 비밀값 파일 가운데 토큰 이름·`cfat_` 형식이 든 파일은 `sync.env` 하나. 교체 중 임시 파일 없음. 로컬 임시 스크립트(비밀값 없음)는 지웠다.
- 2026-10-26 사실: 사용자가 로컬 `.env`를 교체하고 계정 소유 토큰 확인으로 `active`를 확인했다.
