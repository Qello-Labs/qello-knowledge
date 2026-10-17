# Task Contract: <TASK-TITLE>

> Generated at: `<CREATED-AT>`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-<번호>` / <!-- 이슈 URL -->
- 기능명세서 ID / 링크: <!-- 명세가 없으면 '해당 없음: 사유' -->
- 팀 스프린트 ID: `QELLO-SYYYY-Www`
- GitHub Issue: 해당 없음 또는 `#<번호>`
- Branch: <!-- <type>/SCRUM-<번호>-gh-<번호>-<short-slug> -->
- Base branch: `main`

## Objective

- TODO

## Scope

- TODO

## Explicit exclusions

- TODO
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음 또는 설명
- 외부 API로 보내는 데이터: 해당 없음 또는 설명
- 예상 임베딩·생성 호출량과 무료 한도 대비: 해당 없음 또는 설명
- 인덱스 버전 변경: 없음 또는 `<이전>` → `<새 버전>`

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| TODO | TODO | TODO |

## Existing user-owned changes

- 작업 시작 시 `git status --short` 결과를 확인하고 여기에 기록한다.

## Validation

```bash
python scripts/preflight.py
git diff --check
```

## Completion criteria

<!-- Jira 이슈의 관찰 가능한 완료 조건 1~3개를 옮긴다. -->
- TODO

## Decisions

<!-- YYYY-MM-DD 사용자 결정: 내용 -->
