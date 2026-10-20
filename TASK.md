# Task Contract: QK-ING-002 GitHub 저장소 파일 수집 (WBS 1.5)

> Generated at: `2026-10-20`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-100` / https://tkv123.atlassian.net/browse/SCRUM-100 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: QK-ING-002 / `specs/QK-ING-002-github-repo-source/spec.md`(2026-10-20 승인)
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#41`
- Branch: `feat/SCRUM-100-gh-41-github-repo-source`
- Base branch: `main`. `40fe214`에서 분기했고 2026-10-20 `origin/main` `0b8d5d5`(#40 병합) 위로 rebase했다

## Objective

- 완료: QK-ING-002 명세(`spec.md`)를 작성하고 사람 승인을 받았다(2026-10-20, `0ab2931` 기준).
- 완료: `/speckit-plan` 설계 산출물을 만들고 사람 승인을 받았다(2026-10-20, `361a9b1` 기준).
- 완료: `/speckit-tasks` 작업 목록(49개)을 만들고 사람 승인을 받았다(2026-10-20, `89ce3e1` 기준).
- 완료: `tasks.md` T001~T048과 리뷰 반영 Phase 8(T050~T055)을 구현했다(Codex 세션, 2026-10-20). T049(PR 본문)는 이 세션이 한다.
- 남은 것: 사람 단계(결정 기록, 개인 정보 확인, 확인 기록, 활성화, 실제 측정. tasks.md "사람 단계").
- 함께: 로드맵 진행 상태 열을 GitHub Issue 상태에 맞게 갱신한다(`scripts/roadmap_status.py --write`).

## Scope

- `specs/QK-ING-002-github-repo-source/spec.md`, `checklists/requirements.md`(승인됨, 바꾸려면 다시 승인)
- 설계 산출물: 같은 디렉터리의 `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`(승인됨, 바꾸려면 다시 승인)
- 작업 목록: 같은 디렉터리의 `tasks.md`(승인됨). 구현 중 체크 표시와 진행 기록은 고친다.
- 구현(tasks.md, plan.md Project Structure):
  - 새 파일: `src/qello_knowledge/adapters/{github,http}.py`, `src/qello_knowledge/sources/scope_review.py`, `src/qello_knowledge/devtools/measure.py`,
    `config/source_reviews/README.md`, `tests/unit/adapters/`, `tests/unit/review_records.py`, `tests/unit/domain/test_content_hash.py`, `tests/unit/sources/test_scope_review.py`,
    `tests/unit/devtools/test_measure.py`, `tests/contract/test_github_adapter_contract.py`, `tests/external/`, `tests/fixtures/source_reviews/`
  - 고치는 파일(QK-ING-001, 2026-10-20 사용자 허용): `src/qello_knowledge/domain/source.py`(`ListPage.complete`, `content_hash()`), `src/qello_knowledge/sources/collect.py`,
    `src/qello_knowledge/sources/session.py`, `src/qello_knowledge/adapters/fake.py`, `tests/contract/source_adapter_contract.py`, `tests/contract/test_fake_adapter_contract.py`,
    `tests/contract/test_second_fake_contract.py`, `tests/unit/sources/test_list_all.py`
  - 고치는 파일(그 밖): `src/qello_knowledge/indexer/cli.py`, `src/qello_knowledge/devtools/db.py`, `tests/unit/indexer/test_cli.py`, `config/sources.toml`(첫 자료원 비활성 등록)
- `docs/sdd/roadmap.md`의 `상태`·`진행` 열(스크립트 출력만, 손으로 고치지 않음)
- `.specify/feature.json`(git 무시 파일, 로컬 전용)은 이 명세 디렉터리를 가리키게 한다.
- `TASK.md`
- 명세가 다룰 동작:
  - 첫 대상 저장소 `dnd-side-project/dnd-15th-2-backend`(공개, 기본 브랜치 `main`)의 Markdown 문서 수집
  - QK-ING-001 계약(`github_repo_files` 종류, 필수 설정 `repo`·`ref`, 허용 호스트 `api.github.com`)에 맞춘 어댑터와 실제 HTTP 전송
  - 기본 브랜치 트리 조회, 포함·제외 패턴 적용, 파일별 blob SHA 제공. 변경 비교 판정과 삭제 반영은 QK-SYN-001과 경계를 나눈다
  - QK-SEC-001 인계: 공개 범위를 `AccessInfo.raw`의 `("visibility", "public")`로 전달, `source_id`는 저장소 안 경로,
    포함 패턴 확장자와 `FILE_EXTENSIONS` 대조, 자료원 범위를 넓힐 때의 개인 정보 확인 기록 형식과 위치(FR-024)
  - QK-ING-001 인계: GitHub 403 한도 초과의 일시적 재분류, 기본 한도값 측정·조정, T053 후속 메모 두 건

## Explicit exclusions

- 첫 자료원 활성화(`enabled = true`), 개인 정보 확인 기록(`config/source_reviews/*.toml`) 작성, 결정 기록 작성, 실제 원본 호출·외부 호출 시험 실행. 사람 단계다(tasks.md).
- 청킹(QK-CHK-002), 임베딩(QK-EMB-001), 동기화·변경 판정·삭제 반영(QK-SYN-001).
- 위 구현 목록 밖의 QK-ING-001 코드, QK-SEC-001 코드(`src/qello_knowledge/security/`, `domain/{security,secret_rules,redact,exclusions}.py`), 승인된 명세·설계 산출물 내용 변경.
- 런타임 의존성 추가(`pyproject.toml`의 `dependencies`).
- 로드맵 `상태`·`진행` 열 외의 `docs/sdd/roadmap.md` 내용, `docs/sdd/constitution.md`, `.specify/memory/constitution.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정.
- 원본 자료원(GitHub 대상 저장소 포함)에 쓰기.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다. 명세의 토큰 예시는 `<github-token>` 같은 placeholder로 쓴다.

## Data and cost impact

- 새로 읽는 자료원: 이번 단계는 해당 없음. 구현 단계에서 GitHub 공개 저장소 `dnd-side-project/dnd-15th-2-backend`를 읽는다(읽기 전용 토큰)
- 외부 API로 보내는 데이터: 해당 없음
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-ING-002-github-repo-source/` | Byuntil | 사람 리뷰 |
| `docs/sdd/roadmap.md` 상태 열 | Byuntil | 사람 리뷰 |
| `TASK.md` | Byuntil | 사람 리뷰 |
| `src/qello_knowledge/adapters/`, `sources/`, `domain/source.py`, `indexer/cli.py`, `devtools/` 변경, `config/sources.toml`, `config/source_reviews/README.md` | Byuntil | 사람 리뷰 |
| `tests/` GitHub 수집기·계약·CLI 시험 | Byuntil | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-20 `main`(`40fe214`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python3 scripts/preflight.py
git diff --check
python3 -I scripts/preflight.py
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
grep -rn "NEEDS CLARIFICATION" specs/QK-ING-002-github-repo-source/*.md   # 결과가 없어야 한다
```

## Completion criteria

- `spec.md`가 사람 리뷰로 승인된다(SCRUM-100 완료 조건 1).
- 구현 단계 조건(SCRUM-100): 대상 저장소의 포함 패턴에 맞는 파일 목록과 본문을 공개 범위 정보와 함께 읽는다(재생 전송 단위 시험, 실제 호출은 external 시험).
  공개 범위를 확인할 수 없는 저장소의 자료는 미확인으로 판정된다(단위 시험).

## Decisions

- 2026-10-20 사용자 결정: 에이전트가 Jira 하위 작업 `SCRUM-100`(SCRUM-42 아래, 담당 구성재)을 만든다.
- 2026-10-20 사용자 결정: 첫 대상 저장소는 `dnd-side-project/dnd-15th-2-backend`다. `config/sources.toml` 예시의 `Qello-Labs/qello-knowledge`는
  비공개이고 인벤토리상 색인 대상이 아니며(`docs/sdd/research/inventory.md:22`), 토큰도 공개 저장소 읽기만 있다(`docs/sdd/research/tokens.md:16`).
- 2026-10-20 사용자 결정: 에이전트가 GitHub Issue `#41`을 만든다(기존 Jira 키 SCRUM-100 입력). 브랜치를 `feat/SCRUM-100-gh-41-github-repo-source`로 바꿨다(push 전).
- 2026-10-20 사용자 결정: 로드맵 상태를 최신화한다. `roadmap_status.py --write`로 0.9·0.11·1.1~1.4 8건과 1.5(🔄 #41)를 반영했다.
- 2026-10-20 사실: 단계 게이트 `0.G`는 ⬜다. 0.1(SDD 리뷰), 0.7(골든셋 v0, `eval/` 없음), 0.8(생산성 기준선)이 끝나지 않아 완료 조건을 채우지 못한다.
  1.1~1.4가 이미 이 상태에서 진행됐고, 사용자 결정으로 Phase 1을 계속 진행한다. 0.8 기준선은 봇 사용 시작(1.11) 전에 끝내야 한다(로드맵 0.8).
- 2026-10-20 사실: FR-ING-02, FR-SYN-02(파일)는 저장소에 원문이 없다. 명세 Assumptions에 기록한다.
- 2026-10-20 사실: "트리 비교" 경계를 명세 FR-024로 제안했다. 수집기는 한 커밋 기준의 완전한 목록과 파일별 blob SHA까지, 이전 실행과의 비교·삭제 판정은 QK-SYN-001이다.
  명세 승인 때 함께 확인한다.
- 2026-10-20 사용자 결정(명세 확인 필요 1건, FR-020): 개인 정보 확인 기록은 자료원마다 한 파일로 `config/` 아래에 두고, 수집 전 검증이 기록된 범위와
  현재 자료원 설정을 대조해 없거나 다르면 원본 호출 없이 실패한다(안 A).
- 2026-10-20 사실: `spec.md`와 `checklists/requirements.md` 초안을 이 세션이 썼다. 이 세션은 명세를 승인하지 않는다(AGENTS.md 2절). 독립 검토와 사람 리뷰 대기.
  FR-009·FR-017은 QK-ING-001 코드·시험 수정이 필요해 plan에서 제외 범위 조정 승인을 받는다.
- 2026-10-20 사실: 명세를 쓰지 않은 Codex 세션이 `$harness-review`로 `40fe214..1208461`을 검토해 변경 요청(FAIL)을 냈다. P1 0건, P2 1건
  (Edge Cases의 크기 초과를 "건너뜀"으로 써 QK-ING-001 R-08·`collect.py`의 "영구 실패, `SIZE_EXCEEDED`"와 다름). 나머지 인계 항목, FR-024 경계,
  FR-020 안 A는 일치로 판정했다. Codex 실행: preflight 318개 파일, `git diff --check`, 확인 필요 표시 검사 통과.
- 2026-10-20 사실: P2를 명세 Edge Cases에서 고쳤다. 검토 중 `roadmap_status.py`가 다른 작업의 Issue #42(1.7 QK-EMB-001)로 1.7 상태가 최신이 아니라고 했다.
  이 작업의 범위가 아니어서 반영하지 않았다.
- 2026-10-20 사실: 같은 Codex 세션이 P2 반영분(`3bf585b`, `0ab2931`)을 재검토해 PASS를 냈다. 남은 P1·P2 없음. PR #43(리뷰어 tkv00)을 열었고 CI가 통과했다.
- 2026-10-20 사용자 결정: 사람 리뷰어 Byuntil이 `spec.md`(`0ab2931` 기준)를 승인했다. PR #43에는 아직 GitHub 리뷰 기록이 없어 대화로 전달받은 결정을 적는다.
  명세를 쓴 세션은 승인하지 않았다(AGENTS.md 2절). `/speckit-plan`으로 설계를 진행한다.
- 2026-10-20 사실: 설계 산출물(`plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/` 3개)을 이 세션이 썼다. 설계 승인 대기.
  plan.md "사람 확인이 필요한 것"에 QK-ING-001 코드·시험 변경 네 곳(TASK 제외 범위 조정), 첫 자료원 활성화는 사람이 한다는 점, 결정 기록 필요 여부,
  포함 패턴 초안, 빈 저장소 해석의 명세 문구 보완 제안, 2차 한도 한계를 남겼다.
- 2026-10-20 사실: 같은 Codex 세션이 `$harness-review`로 설계(`0ab2931..2529102`)를 검토해 변경 요청(FAIL)을 냈다. P1 1건(데이터 처리 결정 기록을 선택 사항으로 둠),
  P2 4건(2차 한도 `retry-after`가 다음 파일 요청에서 무시됨, 측정이 `screen_source` 반환값으로 본문 크기·커밋·실제 패턴을 얻을 수 없음, SC-008 `.adoc` 예시가
  실제 확장자 목록과 반대, 없는 `ref`의 분류가 FR-014와 다르고 409·422 뜻을 단정함). Codex 실행: preflight 334개 파일, ruff, 기존 계약·목록 시험 15 passed.
- 2026-10-20 사실: 5건을 설계에서 고쳤다. 1) 결정 기록을 활성화의 필수 선행 조건으로(R-16). 2) `retry-after`가 있으면 `remaining=0`으로 정규화해 ING-001 관문을
  고치지 않고 다음 요청도 기다리게 함(R-07). 3) 측정은 `CountingTransport`(blob 응답 바이트), 어댑터 `last_snapshot`(커밋·공개 범위·잘림), 실제 패턴 목록으로 모음(R-14).
  4) 확장자 실패 예시를 `**/*.org`로, `adoc`은 통과 사례로. 5) 커밋 확정 요청의 404·422만 `NOT_FOUND`로 바꾸고 상태 코드 뜻은 일반화하지 않음(R-07).
- 2026-10-20 사실(사람 재승인 대상): 위 4)·커밋 없는 저장소 해석 때문에 승인된 `spec.md` 예시 두 곳(US4 시나리오 1, Edge Cases 빈 저장소)을 고쳤다. FR·SC 문구는 그대로다.
- 2026-10-20 사실: 같은 Codex 세션의 설계 재검토에서 이전 5건은 해소, 새 P2 1건(측정 `files`를 "판정 수 + 통과 수"로 정의해 통과 자료를 두 번 셈)을 냈다.
  SEC-001은 통과 자료에도 `PASSED` 판정을 남기므로 `files = len(verdicts)`로 고치고, 세 측정 사례에서 고유 항목 수와 같은지 보는 시험을 quickstart에 더했다.
- 2026-10-20 사실: 같은 Codex 세션의 두 번째 설계 재검토에서 남은 P2가 해소되고 PASS가 나왔다(남은 P1·P2 없음).
- 2026-10-20 사용자 결정: 사람 리뷰어 Byuntil이 다음을 모두 승인했다. 1) `spec.md` 예시 두 곳 정정(`87f98a3`) 재승인. 2) 설계(`361a9b1` 기준) 승인.
  3) QK-ING-001 코드·시험 변경 네 곳(`ListPage.complete`·`list_all`, `content_hash()`와 호출처, 공통 계약 시험 기대값 주입) 허용. 구현 범위(Scope·Ownership·제외 범위 조정)는
  SEC-001 때처럼 tasks 승인 뒤에 반영한다. 4) 헤더 없이 본문으로만 오는 GitHub 2차 한도 응답을 영구 실패로 남기는 한계를 받아들인다.
  5) 활성화 단계(결정 기록, 포함 패턴 확정, 확인 기록, 활성화, 측정)는 사람이 한다는 절차를 확인했다. 설계를 쓴 세션은 승인하지 않았다(AGENTS.md 2절).
  `/speckit-tasks`로 작업 목록을 만든다.
- 2026-10-20 사실: `tasks.md`(48개 작업, Phase 1~7과 사람 단계 6개)를 이 세션이 썼다. tasks 승인 대기. 설계와 다르게 둔 세 곳(재생 응답을 JSON 파일 대신 시험 도우미가 코드로 만듦,
  겹치는 시험 파일 이름 변경, 확인 기록 시험 자료를 `tmp_path`에 복사해 씀)을 tasks.md 머리에 적었다. 승인되면 구현 범위를 Scope·Ownership·제외 범위에 반영한다.
- 2026-10-20 사실: 같은 Codex 세션이 `tasks.md`(`c492b8d..dc45f9f`)를 검토해 변경 요청(FAIL)을 냈다. P1 1건(외부 호출 시험이 `measure_source`를 직접 불러 확인 기록 검사를 우회할 수 있음),
  P2 3건(세션이 정상 응답에도 부르는 `classify`·`rate_limit_hint` 구현이 US3에 있어 US1을 끝낼 수 없음, 같은 파일·선행 의존 작업에 `[P]` 표시, 기존 CLI 성공 시험이 새 확인 기록 검사로
  실패하게 되는데 전환 작업이 없음). 설계와 다르게 둔 세 곳은 타당하다고 판정했다. Codex 실행: preflight 335개 파일, ruff, 기존 계약·경계·CLI·개발 도구 시험 48 passed.
- 2026-10-20 사실: 4건을 `tasks.md`에서 고쳤다. 1) CLI와 외부 호출 시험이 함께 쓰는 사전 검증 `prepare_source`를 두고 `measure_source`는 그 결과(`PreparedSource`)만 받게 했다.
  검사 실패 시 전송 생성·요청 0건 시험을 더했다. 2) US1(T018)에서 두 메서드를 ING-001 기본 함수에 위임하고 US3(T028)에서 넓힌다. 3) 같은 파일·선행 의존 작업의 `[P]`를 지우고 의존 순서를 적었다.
  4) 기존 CLI 성공 사례를 `tmp_path` 확인 기록과 `--reviews`로 바꾸는 작업(T033)을 더했다(저장소 `config/source_reviews/`에는 기록을 만들지 않음). 작업 수는 49개다.
- 2026-10-20 사실: 같은 Codex 세션의 `tasks.md` 재검토에서 이전 4건 중 3건 해소, 1건 일부 해소(기존 CLI 시험 전환 대상에서 `tests/fixtures/security/sources.toml`로 `run`을 부르는
  보안 예외 시험이 빠짐). 재번호의 교차 참조 오류는 없었다. T033에 그 시험의 두 호출과 전환 누락 확인 방법을 더했다.
- 2026-10-20 사실: 같은 Codex 세션의 `tasks.md` 세 번째 검토에서 남은 P2가 해소되고 PASS가 나왔다(남은 P1·P2 없음).
- 2026-10-20 사용자 결정: 사람 리뷰어 Byuntil이 `tasks.md`(`89ce3e1` 기준)와 설계 조정 세 곳을 승인했다. 작업 목록을 쓴 세션은 승인하지 않았다(AGENTS.md 2절).
  이미 허용한 구현 범위(QK-ING-001 네 곳 포함)를 Scope·Ownership·제외 범위에 반영했다. push와 PR 본문 갱신도 승인했다.
- 2026-10-20 사용자 결정: 구현은 오른쪽 Codex 패널 세션(명세·설계·작업 목록 검토를 맡은 세션)이 맡고, 검증·코드 리뷰는 명세·설계·작업 목록을 쓴 이 Claude 세션이 맡는다.
  Claude 세션은 구현을 쓰지 않았으므로 구현 리뷰는 독립이다. 다만 설계를 쓴 세션이 그 설계의 구현을 검토한다는 한계가 있다.
- 2026-10-20 사실: Codex 세션이 T001~T048을 구현했다(커밋·push 없음). 보고: AGENTS.md 7절 검증 통과, pytest 782 passed·1 deselected(외부 호출 시험), quickstart 1~3.5절 통과.
  `uv run` 캐시 권한 문제로 `.venv/bin`으로 실행했다. 설계와 다르게 둔 곳 하나를 더했다(비활성 자료원의 포함 패턴을 원본 TOML에서 다시 읽는 `load_checked_sources`, tasks.md 머리).
- 2026-10-20 사실: 이 Claude 세션이 구현 diff를 리뷰해 변경 요청을 냈다. P2 1건(`http.client.HTTPException`이 `TransportError`로 바뀌지 않아 응답이 끊기면 실행 전체가 멈춤, 직접 재현),
  P3 4건(연결 단계 시간 초과가 `connection`으로 분류, 측정 명령의 토큰 누락 출력이 `--json`을 무시, 타입 표기 누락, 저장소 이름 URL 인코딩). 범위·안전 경계(확인 기록 미작성, 비활성 유지,
  외부 호출 미실행, SEC-001·명세·하네스 파일 무변경)는 지켜졌다. 이 세션은 명세·설계를 쓴 세션이라 구현 리뷰에 그 한계가 있다.
- 2026-10-20 사용자 결정: P3까지 모두 고친다. Codex 세션이 tasks.md Phase 8(T050~T055)로 고쳤다.
- 2026-10-20 사실: 이 세션이 재검증했다. 재현 사례 네 개가 계약대로 분류되고, preflight(일반·`-I`, 357개 파일), `git diff --check`, ruff 검사·서식, 로컬 DB,
  `QK_REQUIRE_LOCALDB=1 uv run pytest`(792 passed, 1 deselected), `qk-index sources check` 통과. 실제 GitHub 호출과 외부 호출 시험은 실행하지 않았다(사람 단계).
