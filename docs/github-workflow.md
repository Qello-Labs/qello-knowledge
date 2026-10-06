# ClickUp과 GitHub 작업 연결

기능명세서는 요구 동작을, ClickUp 스프린트 작업은 이번 주에 검증할 산출물을 관리한다. GitHub Issue·PR은 구현 범위와 코드·검증 증거를 연결한다.

## 계획과 Issue

- 주간 계획에서 합의한 작업만 해당 Sprint 목록에 넣는다. 담당자·기한·우선순위·상태는 ClickUp 기본 필드로 관리한다.
- 제목은 `[기능명세서 ID] 이번 주에 끝낼 산출물`로 쓴다. 예: `[QK-ING-002] GitHub 저장소 파일 수집기`. 명세가 없는 도구·기술부채 작업은 명세 입력에 해당 없음과 사유를 남긴다.
- GitHub Issue가 필요하면 Qello Knowledge 작업 폼을 사용한다. 기능명세서 드롭다운에서 명세를 고르고 ClickUp 작업 URL과 팀 주기 `QELLO-SYYYY-Www`를 입력한다.
- 드롭다운 목록은 `docs/sdd/roadmap.md` 4절 명세 백로그에서 만든다. 백로그를 바꾸면 같은 PR에서 `python scripts/sync_issue_form.py`를 실행해 폼을 갱신한다. CI가 폼과 백로그가 같은지 검사한다.
- 팀 주기 ID는 사람이 읽는 표기다. ClickUp 작업 ID와 목록 ID를 대신하지 않는다.
- `feature`, `bug`, `tech-debt`, `research`는 작업 종류다. 파트·상태·우선순위 태그를 만들지 않는다. 이 폼은 GitHub 라벨을 자동 생성하거나 동기화하지 않는다.
- Android·Backend는 별도 작업으로 만들고 같은 명세 ID를 연결한다. 팀 보드에는 별도 복제하지 않고 목록 필터로 조회한다.
- 서브태스크는 담당자 또는 완료 조건이 다른 독립 산출물에만 만든다. 구현·리뷰·테스트 순서는 체크리스트로 관리한다.

## PR과 검증

1. 저장소의 커밋 규칙을 따른다. 초기 커밋은 Conventional Commits 형태를 사용하며, GitHub Issue가 있으면 번호를 연결한다. ClickUp ID나 스프린트 ID를 커밋의 필수 접두사로 추가하지 않는다.
2. PR에 ClickUp 작업 ID(`CU-<task-id>`)와 URL, 명세 ID·링크를 입력한다. GitHub Issue가 있으면 `Closes #번호`로 연결하고 없으면 해당 행을 제거한다.
3. 관찰할 완료 조건 1~3개에 검증 방법·실제 결과·증빙 링크를 적는다. 테스트나 측정을 하지 않았다면 미실행과 이유를 적는다.
4. 품질·시간·비용 수치를 적을 때 데이터·모델·질문 세트·표본 수 등 조건을 함께 남긴다. 후보 생성·측정 결과·사람의 검토·실제 반영을 구분한다.
5. ClickUp GitHub 연동이 켜져 있으면 PR 본문의 `CU-<task-id>`로 작업과 PR이 연결된다. 연동을 쓰지 않으면 ClickUp 작업 설명에 PR URL을 다시 붙인다. 리뷰어가 양쪽 링크를 확인한다.
6. 데일리에는 상태·막힘을 갱신한다. 주간 리뷰에서 완료 조건과 증빙을 확인한 뒤 ClickUp 작업을 완료로 변경한다. PR 병합 자체는 완료 판정이 아니다.

## ClickUp 작업 ID와 명세 ID

명세 ID(`QK-ING-002`)는 기능 단위이고 ClickUp 작업은 주간 산출물 단위라서 명세 하나에 작업이 여러 개 생긴다. 두 ID를 같게 만들지 않고 다음 위치에서 함께 적어 연결한다.

| 위치 | 명세 ID | ClickUp 작업 ID |
| --- | --- | --- |
| ClickUp 작업 제목 | `[QK-ING-002] …` | — |
| GitHub Issue | 기능명세서 드롭다운 | 작업 URL |
| PR 본문 | 기능명세서 ID / 링크 | `CU-<task-id>`와 URL |

- ClickUp 작업 ID는 기본 ID를 그대로 쓴다. 사용자 지정 Task ID는 Space마다 `접두사-자동번호` 형식만 만들 수 있어 명세 ID와 같게 만들 수 없고, 무료 요금제에서는 사용이 제한되는 기능이라 쓰지 않는다.
- PR에는 `#<task-id>` 대신 `CU-<task-id>`를 쓴다. `#` 뒤에 숫자만 오면 GitHub Issue 참조로 링크된다.
- ClickUp GitHub 연동의 상태 자동 변경(`#<task-id>[상태]`)과 "PR 병합 시 완료" 자동화는 쓰지 않는다. 완료는 주간 리뷰에서 판정한다.

새 팀 주기를 만들면 팀 보드의 Location/List 필터를 해당 Sprint 목록으로 바꾼다. RAG 전용 Sprint 목록은 실제 팀 합의에 따라 연결하며 이 템플릿이 임의로 생성하거나 선택하지 않는다.

## 템플릿 적용

템플릿은 기본 브랜치에 반영된 뒤 신규 Issue·PR 작성에 사용된다. 기존 본문은 자동으로 변경되지 않는다. Issue Form의 드롭다운은 명세 ID 오타를 막지만, ClickUp URL 형식·작업 일치·증빙의 정확성은 강제하지 않으므로 리뷰에서 확인한다. `/harness-pr`은 PR을 만들기 전에 명세 ID가 로드맵 백로그에 있는지 `python scripts/roadmap.py <명세 ID>`로 확인한다.
