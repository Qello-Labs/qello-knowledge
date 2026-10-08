# Task Contract: WBS 0.2 자료 인벤토리 작성

> Generated at: `2026-10-06`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- ClickUp 작업 ID / URL: 해당 없음: 초기 세팅 단계 예외. 진행 상태는 WBS 보드 0.2에서 관리
- 기능명세서 ID / 링크: 해당 없음: Phase 0 조사 작업(WBS 0.2)이라 명세 백로그 대상이 아님. 작업 정의는 `docs/sdd/roadmap.md` 3절
- 팀 스프린트 ID: `QELLO-S2026-W41`
- GitHub Issue: `#3`
- Branch: `docs/gh-3-source-inventory`
- Base branch: `main`

## Objective

- 색인할 자료원이 어디에 어떤 형태로 있는지 조사해 `docs/sdd/research/inventory.md`로 정리한다. 0.5 토큰 발급 범위와 0.9 열린 결정(ADR-008)의 입력으로 쓴다.

## Scope

- GitHub 저장소 목록(기본 브랜치·언어·크기)과 저장소별 자료 구성
- ClickUp Space·Folder 구조
- 회의록 위치·형식
- OpenAPI 노출 위치
- DB 접근 가능 여부
- Figma 파일 목록·소유자·좌석(보류: Decisions 참조)

## Explicit exclusions

- 토큰·계정 발급(WBS 0.5)
- 수집·색인 코드 작성
- 실제 DB 연결, AWS 리소스 조회·변경
- 원본 자료원(GitHub, ClickUp, Figma)에 쓰기
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: GitHub 공개 저장소 `dnd-side-project/dnd-15th-2-backend`, `dnd-side-project/dnd-15th-2-android`의 메타데이터와 파일 목록(읽기 전용, `gh` CLI). ClickUp `Qello` Space의 구조, Team Docs 문서 목록, 회의록 2건 본문(로그인된 웹 화면에서 조회, API·토큰 미사용, 2026-10-07). Figma는 조사하지 않는다(Decisions 참조)
- 외부 API로 보내는 데이터: 해당 없음
- 예상 임베딩·생성 호출량과 무료 한도 대비: 해당 없음
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `docs/sdd/research/inventory.md` | 확인 필요 | 사람 리뷰 |
| `TASK.md` | 확인 필요 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-06 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
```

## Completion criteria

- 로드맵 0.2의 조사 항목 6개가 모두 조사 결과 또는 "확인 불가와 사유"로 채워져 있다. 리뷰에서 항목별로 대조한다.
- 수치마다 조사일, 기준 커밋, 조사 방법이 적혀 있다.
- 비밀값, 서버 주소, DB 연결 정보가 없다. `python scripts/preflight.py`와 리뷰로 확인한다.

## Decisions

- 2026-10-06 사용자 결정: GitHub Issue는 ClickUp 작업 ID·URL을 '확인 필요'로 두고 먼저 만든다. 값이 정해지면 Issue #3과 이 파일을 함께 고친다.
- 2026-10-06 사용자 결정: PR #1·#2처럼 초기 세팅 단계 예외로 ClickUp 작업 없이 진행한다. 진행 상태는 WBS 보드 0.2에서 관리한다.
- 2026-10-07 사용자 결정: 팀 회의에서 MVP에서 Figma를 제외하기로 했으므로 Figma 조사는 보류한다. 인벤토리 6절은 보류와 사유로 채우고, Phase 4 명세 전에 다시 조사한다.
- 2026-10-09 사용자 요청: PR #6 병합 뒤 생긴 `TASK.md` 충돌을 이 브랜치의 0.2 계약으로 대체해 해결한다. 0.10 계약은 `main` 이력(`e1a62ab`)에 남는다.
