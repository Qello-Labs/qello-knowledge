# Task Contract: QK-OBS-001 운영 반영 H01~H03 준비 문서 초안

> Generated at: `2026-11-04`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다. 2026-11-04 사람 승인(Decisions).

## Work gate

- Jira 이슈: `SCRUM-131` / https://tkv123.atlassian.net/browse/SCRUM-131 (상위 `SCRUM-42`, #96 자동 생성 댓글로 오케스트레이터 확인)
- 기능명세서 ID / 링크: `QK-OBS-001` / [spec.md](specs/QK-OBS-001-query-log-feedback/spec.md)
- 팀 스프린트 ID: `QELLO-S2026-W45` (GitHub Issue 본문)
- GitHub Issue: [#96](https://github.com/Qello-Labs/qello-knowledge/issues/96)
- Branch: `feat/SCRUM-131-gh-96-query-log-rollout`
- Base branch: `main` / 로컬 `origin/main`·HEAD `69c04ea7ac48072e5330114249165f38050d11e9` 일치 확인. 원격 최신성은 재확인하지 못했다.

## Objective

- #96의 운영 반영·확인 자체가 아니라, 사람이 H01~H03을 판단·실행할 준비 문서 네 개를 만들고 2026-11-04 사람 결정을 ADR-016에 기록한다.
- 공지·동의 문구를 ADR-016과 명세에 맞추고, 현재 질의 릴리스부터 배포 후보까지의 차이 및 예약 동기화 영향을 근거와 함께 정리한다.

## Scope

- `TASK.md`: 이 계약 초안으로 교체. 이전 QK-STO-002 내용은 git 이력에 남는다.
- `specs/QK-OBS-001-query-log-feedback/rollout/notice-draft.md`
- `specs/QK-OBS-001-query-log-feedback/rollout/consent-doc-draft.md`
- `specs/QK-OBS-001-query-log-feedback/rollout/rollout-preflight.md`
- `docs/sdd/decisions/ADR-016-query-text-retention.md`: 2026-11-04 사람 결정(상태, 승인, 보존 상한 날짜) 기록만

## Explicit exclusions

- 운영 명령 일체(OCI, SSH, 운영 DB 읽기·쓰기, Discord 등록, Worker 배포), Jira·Confluence·Discord·GitHub 쓰기.
- 커밋·push·PR 생성, src·tests 수정, 평가 실행, 비용 발생 외부 API 호출.
- 위 기록 외 ADR-016 변경, tasks.md·roadmap·AGENTS.md·CLAUDE.md·CODEX.md·.claude/**·.codex/**·.agents/** 수정.
- `.env`·`.env.*`·`secrets/` 읽기. 서버 주소, 내부 도메인, OCID, 역할 이름, 사용자 식별자, 실제 질의 원문을 기록하지 않는다.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: GitHub Issue #96(읽기 전용), 로컬 저장소 문서·코드·git 이력. 운영 자료원 접근 없음.
- 외부 API로 보내는 데이터: Issue 조회 식별 정보 외 로컬 자료·질의 원문 전송 없음.
- 예상 임베딩·생성 호출량과 무료 한도 대비: 준비 문서 작성 0회, 0 Neurons. H03의 재시도 없는 가정의 예상량 약 255 Neurons 사용은 후속 사람 승인 대상이다.
- 인덱스 버전 변경: 없음.

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| 위 Scope 다섯 파일 | Byuntil | 별도 검토자 검증, 사람 계약·운영 승인 |

## Existing user-owned changes

- 시작 시 `git status --short` 실행: 변경 행 없음. 다만 차단 경로에 대한 `Operation not permitted` 경고가 있어 완전한 무변경 확인으로 단정하지 않는다. 해당 경로를 읽거나 정리하지 않았다.
- 브랜치와 기준 커밋은 Work gate와 일치한다. 기존 파일은 이 요청에서 교체하도록 지정한 `TASK.md`만 수정한다.

## Validation

```bash
uv run python scripts/preflight.py
git diff --check
```

- 문서 초안 범위이며 DB·운영·평가 검증은 하지 않는다. 샌드박스 차단은 우회하지 않고 보고한다.
- 실행 에이전트의 자체 점검은 독립 검토나 승인이 아니다.
- 실행 결과(2026-11-04): `uv run python scripts/preflight.py`는 uv 캐시의 잠금용 임시 파일 생성 권한 오류로 종료 코드 2. 검사는 시작하지 못했으며 우회하지 않았다. `git diff --check`는 종료 코드 0이나 차단 경로 경고가 있었다. 네 문서의 공백·로컬 파일 링크 자체 점검은 통과했다. 필수 preflight가 남아 최종 상태는 BLOCKED다.
- 2026-11-04 오케스트레이터가 샌드박스 밖에서 다시 실행: `uv run python scripts/preflight.py` 통과(저장소 텍스트 파일 1005개, 미추적 새 문서 포함), `git diff --check` 종료 코드 0(새 문서 포함).

## Completion criteria

- Discord 공지·Confluence 동의 문서 초안에 저장 범위, 질의별 동의, 메모리 대기, 보존 상한, 삭제 경로가 있고 확정값은 반영하고 미확정값만 placeholder로 남긴다.
- 사전 점검에 `ce6d1d8..origin/main`의 질의 경로·설정·의존성·마이그레이션 변화와 `0008` 미적용 시 예약 동기화 영향이 파일:줄 근거로 정리된다.
- 사람 단계 순서표에 실행 주체·승인·예상 Neurons·되돌리기가 있고, 미확인·문서 차이와 필수 검증 결과가 구분된다. Issue #96의 운영 완료 조건은 이 문서 작성으로 충족되지 않는다.

## Decisions

- 2026-11-04 사용자 지시: 이 세션을 오케스트레이터로 두고 worktree의 Codex(gpt-6.1-sol, medium)로 진행한다. 범위를 네 준비 문서로 잡은 것은 오케스트레이터의 판단이다. 이 계약과 운영 반영의 사람 승인을 받았다고 해석하지 않는다.
- 2026-11-04 이슈 확인: `gh issue view 96`은 샌드박스 내·승격 재시도 모두 GitHub 연결 실패. 읽기 전용 GitHub 커넥터로 본문을 확인했다. 주간 계획 합의 체크박스는 미체크이므로 합의 완료로 추정하지 않는다.
- 2026-11-04 운영 배경은 사용자·오케스트레이터 및 #96의 읽기 전용 확인 기록을 인용한다. 실행 에이전트는 운영 상태를 직접 확인하지 않았다.
- 2026-11-04 사용자 결정: 이 계약을 승인했다("1: 승인"). 네 준비 문서 범위의 승인이고 운영 반영 승인이 아니다. 주간 계획 합의 여부는 이때 답을 받지 못했다(아래 2026-11-04 결정으로 확인).
- 2026-11-04 사용자 결정: 준비 문서 독립 검토를 새 Codex 패널(읽기 전용)에 맡긴다("2: 좋아").
- 2026-11-04 사실: 독립 검토(새 Codex 세션 `review96`, 작성 미관여, 읽기 전용) 1차 판정은 변경 요청이다(높음 2, 중간 4). 오케스트레이터가 근거를 코드·문서로 다시 확인했고 실행 에이전트가 반영했다. 2차에서 6건이 해소되고 낮음 1건(공지 게시 경계)이 나와 공지를 다시 썼다. 3차(공지만) 판정은 승인 권고이고 새 지적은 없다. 치환 전 공지 본문은 1,133자(UTF-16)다. 검토자는 전체 preflight를 실행하지 않았고(`.env.*` 읽기 가능성), 오케스트레이터가 `uv run python scripts/preflight.py`(1,005개 파일)와 `git diff --check`를 실행해 통과했다.
- 2026-11-04 사용자 결정(H01 값): 기록 기능은 운영 배포일부터 켠다. 보존 상한은 약 1개월이며 날짜는 배포일이 정해지면 계산한다. 원문 열람은 byuntil, tkv00이다. 삭제·문의는 운영 담당자 두 명에게 받는다. 담당자 실명과 Discord 식별자는 공개 저장소에 적지 않고 게시본에서만 치환한다(오케스트레이터 판단).
- 2026-11-04 사실(사용자 승인 뒤 오케스트레이터 읽기 전용 확인): Workers AI 공개 문서(2026-10-16 갱신)는 입력·출력을 학습에 쓰지 않고 일반 요청은 처리 뒤 보관하지 않는다고 밝힌다. 이 프로젝트는 AI Gateway·batch 없이 REST를 직접 호출한다. 확인한 도구·설정·경로에서 운영 DB 백업은 발견하지 못했다(다른 컴파트먼트의 수동 백업, 이름이 다른 스크립트, 서버 밖 복사는 미확인). 서버 관리 권한이 있으면 원문을 기술적으로 읽을 수 있고, 권한 보유자 명단은 미확인이다. 원본 수치 중 계정·키 수는 저장소에 적지 않는다. 검토자(`review96`)는 백업 문구 단정 표현 1건을 지적했고 반영했다. 이 마지막 문구 수정은 다시 검토받지 않았다.
- 2026-11-04 사용자 결정: 운영 담당자 두 명과 열람자 byuntil, tkv00은 같은 사람이다. 운영 서버 소유자는 tkv00이다. 기록 기능은 오늘(2026-11-04)부터 켜고 보존 상한은 2026-12-04(UTC)로 계산했다. ADR-016을 승인하고 메모리 대기 해석을 받아들였다. `0008` 지연 적용 순서를 받아들였다. 주간 계획에서 합의된 작업이다. 커밋과 PR을 요청했다. 이 결정들은 운영 명령 실행 승인이 아니며, H02 명령은 명령마다 승인받는다. 서버 관리 권한 전체 명단은 아직 미확인이다.
- H01 공지·동의 문서 게시와 링크 기록, H02·H03 운영 수행 및 결과 기록은 미완료다.
