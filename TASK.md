# Task Contract: WBS 0.3 Notion→ClickUp 이전 품질 확인

> Generated at: `2026-10-08`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- ClickUp 작업 ID / URL: 해당 없음: 초기 세팅 단계 예외. 진행 상태는 WBS 보드 0.3에서 관리
- 기능명세서 ID / 링크: 해당 없음: Phase 0 준비 작업(WBS 0.3)이라 명세 백로그 대상이 아님. 작업 정의는 `docs/sdd/roadmap.md` 3절
- 팀 스프린트 ID: `QELLO-S2026-W41`
- GitHub Issue: `#8`
- Branch: `docs/gh-8-clickup-migration-check`
- Base branch: `main`

## Objective

- Notion에서 ClickUp으로 옮긴 문서를 ClickUp API Markdown으로 받아 표·토글·이미지·링크 등의 손실을 확인하고, ClickUp 문서의 `access_scope`를 API로 판별하는 방법을 조사한다(RISK-01).

## Scope

- Codex가 Computer Use로 ClickUp·Notion 화면을 보고 대상 문서(1차 D1~D5, 2차 D6~D7)와 권한 실험 케이스(A~F, A′)를 고른다.
- 대상 페이지를 `content_format=text/md`로 받아 Notion 원본·ClickUp 화면과 비교한다. 요소별 Markdown 표현과 손실 등급을 기록하고, 손실이 이전 단계(Notion→ClickUp)인지 변환 단계(ClickUp→Markdown)인지 구분한다.
- 케이스별 ClickUp 공유 패널 상태와 API가 주는 권한 관련 정보를 비교해 `access_scope` 판별 방식을 제안한다.
- 결과를 `docs/sdd/research/clickup-migration-check.md`에 쓴다.

## Explicit exclusions

- ClickUp, Notion, GitHub, Figma에 쓰기. 화면에서 본문 편집, 공유 설정 변경, 댓글, 이동·복제·삭제를 하지 않는다. ClickUp API는 GET만 호출한다.
- 테스트 문서 생성. Decisions에 허용과 조건이 적혀 있을 때만 그 조건대로 한다.
- ClickUp API 토큰 값의 출력·기록·커밋.
- 개인 페이지, 비공개 대화, 다른 사람의 Private 위치 열기.
- 수집·청킹 코드 작성, 조사용 스크립트 커밋. 조사용 스크립트와 받은 원문은 git 제외 작업 폴더에만 둔다.
- `access_scope` 값 체계 확정(QK-SEC-001 명세에서 정한다), ClickUp 작성 규칙 확정(0.4).
- `AGENTS.md`, `CLAUDE.md`, `.claude/**`, `docs/sdd/roadmap.md`, `scripts/preflight.py` 수정. 고칠 점은 보고서 5절에 적는다.
- 문서 제목, 원문 문장, 사람 이름, workspace·doc·page ID, 첨부 URL을 보고서에 기록하지 않는다.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: ClickUp Doc 페이지 7개(D1~D7)와 대응하는 Notion 원본 페이지, 권한 실험 케이스 문서의 메타데이터와 공유 패널, Space·Folder·List 메타데이터. 읽기만 한다.
- 외부 API로 보내는 데이터: ClickUp API에는 GET 요청만 보낸다. Computer Use 화면 캡처(Notion·ClickUp 화면)와 비밀값 패턴을 가린 대상 Markdown이 분석을 위해 Codex(OpenAI)로 전송된다. 실험 케이스 문서의 본문은 저장하지 않는다.
- 예상 임베딩·생성 호출량과 무료 한도 대비: 해당 없음(임베딩·생성 API 호출 없음). ClickUp API 호출은 1·2차 합계 50회 이하로 토큰당 분당 100회 한도 안.
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `docs/sdd/research/clickup-migration-check.md` | 확인 필요 | 사람 리뷰 |
| `TASK.md` | 확인 필요 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-09 브랜치 생성 시 `git status --short` 결과: 변경 없음
- 브랜치 생성 전 `main` 작업 트리에 있던 `.gitignore` 변경(`wbs-0.3-codex` 제외 줄)은 사용자 결정에 따라 `.git/info/exclude`로 옮기고 되돌렸다.

## Validation

```bash
python scripts/preflight.py
git diff --check
grep -rnE 'pk_[0-9]+_[A-Za-z0-9]{20,}' docs TASK.md   # 결과가 없어야 한다. preflight에 ClickUp 토큰 규칙이 없다
```

## Completion criteria

- 표본 문서마다 표·토글·이미지·링크·헤딩·DB·하위 페이지·코드 손실 등급과 근거(원본 → 화면 → Markdown 요소 수, 손실 단계)가 보고서 3절에 있다. diff로 확인한다.
- `access_scope` 판별 방식 제안과 근거가 된 실험 결과가 보고서 4절에 있고, 확인하지 못한 케이스가 사유와 함께 남아 있다. diff로 확인한다.
- 보고서에 문서 원문·제목·ID·토큰·사람 이름이 없고, ClickUp·Notion의 기존 문서에 편집 기록이 생기지 않았다. 위 검증 명령, 활동 기록 확인, PR 리뷰로 확인한다.

## Decisions

<!-- YYYY-MM-DD 사용자 결정: 내용 -->
- 2026-10-08 사용자 결정: WBS 0.3 실행을 Codex 앱의 Computer Use로 맡긴다. Codex가 대상 문서 선정과 화면 비교까지 직접 한다.
- 2026-10-08 사용자 결정: 1차 조사 결과는 바로 정식 반영하지 않고, 빠진 항목(토글·이미지·회의록 표본, 권한 케이스 B~F)을 2차 조사로 채운 뒤 반영한다.
- 2026-10-08 사용자 결정: 권한 케이스 B~F를 위해 Codex가 ClickUp에 테스트 문서를 만들고 공유 설정을 바꿔 실험한 뒤 지운다. 조건은 이름 접두(`[QK-0.3 테스트·삭제 예정]`), 기존 대상 설정 변경 금지, Space 생성 금지, 정리 확인이다.
- 2026-10-09 사용자 결정: 0.2·0.10처럼 초기 세팅 단계 예외로 ClickUp 작업 없이 진행한다. 진행 상태는 WBS 보드 0.3에서 관리한다.
- 2026-10-09 사용자 확인: 2차에서 만든 테스트 Folder가 ClickUp에서 지워진 것을 화면으로 확인했다.
- 2026-10-09 사용자 결정: 2차 결과를 정식 반영한다. Issue #8과 이 브랜치를 만들고 보고서를 `docs/sdd/research/clickup-migration-check.md`로 옮긴다.
- 2026-10-09 사용자 결정: 로컬 작업 폴더 `wbs-0.3-codex/`는 git 추적에서 빠지기만 하면 된다. 제외 규칙은 커밋하지 않는 `.git/info/exclude`에 둔다.
- 2026-10-09 사용자 결정: PR #7 병합 뒤 생긴 `TASK.md` 충돌을 이 브랜치의 0.3 계약으로 대체해 해결한다. 0.2 계약은 `main` 이력(`d7ac303`)에 남는다.
- 2026-10-09 사용자 결정: 권한 케이스 B(비공개 Space)와 C(문서만 비공개)는 현재 Workspace에서 해당 없음으로 판정한다. 비공개 Space가 생기거나 요금제를 바꾸면 다시 확인한다.
- 2026-10-09 사용자 결정: 보고서 5절의 넘길 곳을 정한다. F-08·F-11(이미지)은 RAG 색인에 실제 이미지가 필요 없어 후속 작업 없이 닫는다. F-12는 일부 ClickUp 페이지를 정규화해야 한다고 보고 0.4로 넘긴다. F-15는 조사 방법의 한계 기록이라 닫는다(제안에 이견 없음).

## Execution record

작업 계약을 커밋하기 전에 조사를 실행했다. 계약과 다르게 진행된 부분을 남긴다.

- 1·2차 조사(2026-10-08)는 Issue·작업 브랜치·`TASK.md` 없이 `main` 작업 트리의 git 제외 폴더에서 진행했다. 저장소 추적 파일은 바꾸지 않았다(위 `.gitignore` 변경 제외).
- 초안은 ClickUp API 호출을 사람이 스크립트를 검토한 뒤 터미널에서 실행하도록 정했지만, 실제로는 Codex가 로컬 작업 폴더의 환경 파일에 있는 토큰으로 직접 GET을 호출했다. 기록 파일 기준 1차 10건, 2차 26건이며 모두 HTTP 200이다. 토큰 값은 출력·저장되지 않았다. 이 토큰은 쓰기 권한이 있으므로(RISK-02) 작업이 끝난 뒤 재발급을 권고한다.
- Codex 화면 캡처와 Markdown이 OpenAI로 전송되는 것에 대한 별도 동의 기록은 없다. Computer Use 실행은 사용자가 결정하고 직접 시작했다.
- 2차 테스트 항목은 Folder 2개, 자동 생성 List 2개, Doc 3개다. 모두 이름 접두를 지켰고 휴지통으로 옮겼다. Doc은 API에서 더 조회되지 않는다. Folder·List는 API가 계속 200을 돌려줘 사람이 화면에서 삭제를 확인했다.
