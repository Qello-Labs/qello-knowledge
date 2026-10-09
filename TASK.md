# Task Contract: WBS 0.5 계정·토큰 발급

> Generated at: `2026-10-09`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- ClickUp 작업 ID / URL: 해당 없음: 초기 세팅 단계 예외. 진행 상태는 WBS 보드 0.5에서 관리
- 기능명세서 ID / 링크: 해당 없음: Phase 0 준비 작업(WBS 0.5)이라 명세 백로그 대상이 아님. 작업 정의는 `docs/sdd/roadmap.md` 3절
- 팀 스프린트 ID: `QELLO-S2026-W41`
- GitHub Issue: `#11`
- Branch: `docs/gh-11-token-scopes`
- Base branch: `main`

## Objective

- Qello Knowledge가 쓸 계정과 토큰의 권한 범위를 정해 `docs/sdd/research/tokens.md`에 남기고, Phase 1에 필요한 토큰(GitHub, Cloudflare, Discord)을 발급해 호출을 확인한다(FR-SEC-02).

## Scope

- 토큰마다 용도, 발급 계정, 권한 범위, 만료·교체, 보관 위치, 확인 방법을 공식 문서 근거와 함께 `tokens.md`에 쓴다.
- 대상: GitHub 세분화 토큰(읽기), Cloudflare 토큰(Workers AI 전용), Discord 애플리케이션·봇, ClickUp 수집 전용 계정, DB 읽기 전용 계정, Figma 토큰.
- Phase 1 3종(GitHub, Cloudflare, Discord)은 사람이 발급하고 확인 호출을 실행한다. 결과는 상태 코드와 확인한 권한만 `tokens.md`에 적는다.
- ClickUp 수집 계정, DB 계정, Figma 토큰은 권한 범위와 발급 시점(또는 발급하지 않는 사유)만 적는다.

## Explicit exclusions

- 토큰·키 값, 계정 비밀번호, 계정 식별자(Cloudflare account ID 등)를 문서·Issue·PR·커밋·대화에 기록. 값은 로컬 `.env`에만 둔다.
- 에이전트가 토큰 발급 화면을 조작하거나 토큰 값을 보는 일. 발급과 확인 명령 실행은 사람이 한다.
- ClickUp 수집 전용 계정 생성·초대, DB 계정 발급, Figma 토큰 발급.
- Discord 서버 초대, 슬래시 명령 등록, 채널 권한 변경.
- 수집·봇 코드 작성, Workers AI 추론 비교(0.6).
- `scripts/preflight.py` 규칙 추가. 빠진 토큰 패턴은 `tokens.md`에 후속 작업으로 적는다.
- `AGENTS.md`, `CLAUDE.md`, `.claude/**`, `docs/sdd/roadmap.md` 수정. 고칠 점은 `tokens.md`에 적는다.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음. 확인 호출은 토큰 자신의 상태와 공개 저장소 메타데이터만 읽는다.
- 외부 API로 보내는 데이터: GitHub·Cloudflare·Discord 확인 API에 토큰을 인증 헤더로 보낸다. 본문 데이터는 보내지 않는다.
- 예상 임베딩·생성 호출량과 무료 한도 대비: 해당 없음. Workers AI 추론 호출은 0.6에서 한다.
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `docs/sdd/research/tokens.md` | 확인 필요 | 사람 리뷰 |
| `TASK.md` | 확인 필요 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-09 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
grep -rnE 'github_pat_[A-Za-z0-9_]{20,}|pk_[0-9]+_[A-Za-z0-9]{20,}|[A-Za-z0-9_-]{23,}\.[A-Za-z0-9_-]{6,7}\.[A-Za-z0-9_-]{27,}' docs TASK.md   # 결과가 없어야 한다. preflight에 없는 GitHub 세분화·ClickUp·Discord 토큰 형식
```

## Completion criteria

- `tokens.md`에 토큰마다 용도, 발급 계정, 권한 범위, 만료, 보관 위치, 확인 방법이 있고 값이 없다. 리뷰와 위 검증 명령으로 확인한다.
- GitHub, Cloudflare, Discord 토큰이 발급되고 확인 호출이 성공했다. 사람이 실행한 확인 명령의 상태 코드를 `tokens.md`에 기록한다.
- 발급하지 않은 토큰(ClickUp 수집 계정, DB, Figma)의 사유와 발급 시점이 적혀 있다. 리뷰로 확인한다.

## Decisions

<!-- YYYY-MM-DD 사용자 결정: 내용 -->
- 2026-10-09 사용자 결정: 0.2·0.3·0.10처럼 초기 세팅 단계 예외로 ClickUp 작업 없이 진행한다. 진행 상태는 WBS 보드 0.5에서 관리한다.
- 2026-10-09 사용자 결정: 이번에 발급하는 것은 Phase 1 3종(GitHub, Cloudflare, Discord)이다. ClickUp 수집 계정은 Phase 2 전에 발급하고, DB 계정은 발급하지 않으며(인벤토리 3.2 제안), Figma는 보류한다(인벤토리 F-14). 나머지는 `tokens.md`에 권한 범위만 적는다.
- 2026-10-09 사용자 결정: 토큰 발급과 확인 호출은 사람이 직접 한다. 에이전트는 설정값과 확인 명령을 준비한다.
- 2026-10-09 사용자 결정: GitHub 토큰 만료를 무기한으로 발급했다(초안 권장 366일). 정기 점검 여부는 `tokens.md` T-06으로 남긴다. Cloudflare는 계정 소유 토큰으로 발급하고, Discord Public Bot은 끈다.
