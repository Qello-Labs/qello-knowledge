# Task Contract: QK-SEC-001 색인 제외 경로·비밀값 차단·접근 범위 판정 (WBS 1.4)

> Generated at: `2026-10-19`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-99` / https://tkv123.atlassian.net/browse/SCRUM-99 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: QK-SEC-001 / `specs/QK-SEC-001-security-filter/spec.md`(작성 중)
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#37`
- Branch: `feat/SCRUM-99-gh-37-security-filter`
- Base branch: `feat/SCRUM-98-gh-34-source-adapter-contract`(PR #35). #35 병합 후 `main`으로 rebase한다. 아래 Decisions 참조

## Objective

- 완료: QK-SEC-001 명세(`spec.md`)를 작성하고 사람 승인을 받았다(2026-10-20).
- 완료: `/speckit-plan` 설계 산출물을 만들고 사람 승인을 받았다(2026-10-20, `7294c48`).
- 완료: `/speckit-tasks`로 작업 목록(57개)을 만들고 사람 승인을 받았다(2026-10-20, `ab3c90e`).
- 이번 단계: `tasks.md`대로 구현해, 첫 실제 색인 전에 색인 제외 경로·비밀값 차단·접근 범위 판정이
  모든 자료에 적용되게 한다(로드맵 2절, RISK-09).

## Scope

- `specs/QK-SEC-001-security-filter/spec.md`와 `checklists/requirements.md`(승인됨, 바꾸려면 다시 승인).
- 설계 산출물: 같은 디렉터리의 `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`(승인됨, 바꾸려면 다시 승인).
- 작업 목록: 같은 디렉터리의 `tasks.md`(승인됨). 구현 중 체크 표시와 진행 기록은 고친다.
- 구현(tasks.md, plan.md Project Structure):
  - 새 파일: `src/qello_knowledge/domain/{security,secret_rules,redact,exclusions}.py`, `src/qello_knowledge/security/`,
    `config/security_exceptions.toml`, `tests/unit/security/`, `tests/unit/domain/test_{security_types,secret_rules,exclusions}.py`,
    `tests/unit/test_preflight_shared_rules.py`, `tests/fixtures/security/`, `tests/fixtures/responses/fake/security_*.json`
  - 고치는 파일: `scripts/preflight.py`(규칙을 공유 모듈에서 불러옴, 2026-10-20 사용자 허용), `scripts/preflight_allowlist.txt`(넓힌 규칙의 오탐만, 사유 필수),
    `src/qello_knowledge/indexer/cli.py`(`security check`, `run` 검사), `tests/unit/indexer/test_cli.py`, `tests/unit/sources/test_config.py`(T037 사례 추가만)
- `.specify/feature.json`(git 무시 파일, 로컬 전용)은 이 명세 디렉터리를 가리키게 한다.
- 명세가 다룰 동작:
  - 색인 제외 경로: 자료원 설정의 포함·제외 패턴과 별개로 항상 적용하는 제외 규칙과 제외 사유 기록
  - 비밀값 차단: 임베딩·생성 API로 보내기 전 비밀값 패턴 검사, 걸린 자료는 임베딩·저장하지 않음(AGENTS.md 3.1)
  - 접근 범위(`access_scope`): 값 체계, QK-ING-001 `SourceItem.access`를 입력으로 한 판정, 확인할 수 없으면 "미확인"
- `TASK.md`

## Explicit exclusions

- 실제 GitHub 수집기와 실제 원본 호출(QK-ING-002), 청커(QK-CHK-002), 동기화·삭제 반영(QK-SYN-001), 저장 스키마와 마이그레이션(QK-STO-001).
- QK-ING-001 코드·명세 수정(`src/qello_knowledge/sources/`, `adapters/`, `domain/source*.py`, `domain/scope.py`). 필요한 변경은 PR #35 쪽에서 다룬다.
  ING-001 시험 파일에는 T037 사례 추가만 한다.
- 승인된 `spec.md`·설계 산출물의 내용 변경. FR-023 문구 보완은 PR에서 제안만 한다.
- 런타임 의존성 추가(`pyproject.toml`의 `dependencies`). 필요하면 사람 승인을 받는다.
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, `.specify/memory/constitution.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다. 명세의 비밀값 예시는 `<github-token>` 같은 placeholder로 쓴다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 해당 없음
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-SEC-001-security-filter/` | Byuntil | 사람 리뷰 |
| `TASK.md` | Byuntil | 사람 리뷰 |
| `src/qello_knowledge/domain/` 새 파일, `src/qello_knowledge/security/`, `src/qello_knowledge/indexer/cli.py`, `config/security_exceptions.toml` | Byuntil | 사람 리뷰 |
| `scripts/preflight.py`, `scripts/preflight_allowlist.txt` | Byuntil | 사람 리뷰(CI 검사 스크립트) |
| `tests/` 보안 필터 시험·픽스처 | Byuntil | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-19 `feat/SCRUM-98-gh-34-source-adapter-contract`(`baa59b8`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python3 scripts/preflight.py
python3 -I scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
grep -rn "NEEDS CLARIFICATION" specs/QK-SEC-001-security-filter/*.md specs/QK-SEC-001-security-filter/contracts/   # 결과가 없어야 한다
```

## Completion criteria

- `spec.md`가 사람 리뷰로 승인된다.
- 명세에 비밀값을 심은 샘플 자료가 임베딩·저장 단계로 넘어가지 않음을 확인할 측정 가능한 성공 기준이 있다.
- 명세에 접근 범위를 확인할 수 없는 자료가 "미확인"으로 판정되고 팀 공용으로 승격되지 않음을 확인할 측정 가능한 성공 기준이 있다.

## Decisions

- 2026-10-19 사실: PR #35(QK-ING-001)는 OPEN이고 팀원 리뷰 승인이 없다. `origin/main`은 `b7be62a`(#29)다.
- 2026-10-19 사용자 결정: PR #35가 승인·병합됐다고 가정하고 QK-SEC-001을 시작한다. AGENTS.md 1절 3항(최신 `origin/main`에서 분기)의 예외로,
  #35 브랜치 HEAD `baa59b8` 위에 이 브랜치를 쌓는다. PR을 열면 base를 #35 브랜치로 하고, #35가 병합되면 `main`으로 rebase한 뒤 base를 `main`으로 바꾼다.
  #35 리뷰에서 계약(`SourceItem.access` 등)이 바뀌면 이 명세도 다시 맞춘다.
- 2026-10-19 사용자 결정: 에이전트가 Jira 하위 작업 `SCRUM-99`(SCRUM-42 아래, 담당 구성재)와 GitHub Issue `#37`을 만든다. 저장소의 Jira 자동 생성은
  Secret이 없어 동작하지 않으므로 Jira를 먼저 만들고 Issue 폼의 "기존 Jira 이슈 키"에 넣었다.
- 2026-10-19 사용자 결정: 이번 세션은 명세(`spec.md`)까지만 작성한다. plan·tasks·구현은 명세 승인 뒤에 한다.
- 2026-10-19 사실: 백로그 행의 요구사항 FR-SEC-03, FR-SEC-06, sources.md 8절은 저장소에 원문이 없다. QK-ING-001과 같은 방식으로 명세 Assumptions에 기록한다.
- 2026-10-19 사용자 결정(명세 확인 필요 2건): 1) 접근 범위가 미확인·제한인 자료는 본문을 조회하지 않고 청킹·임베딩·저장하지 않는다(FR-018).
  2) 비밀값 규칙에 걸린 자료는 문서 전체를 청킹·임베딩·저장하지 않는다(FR-011).
- 2026-10-19 사실: `spec.md`와 `checklists/requirements.md` 초안을 이 세션이 썼다. 이 세션은 명세를 승인하지 않는다(AGENTS.md 2절). 사람 리뷰 대기.
- 2026-10-19 사실: 명세를 쓰지 않은 Codex 세션이 `$harness-review`로 `baa59b8..0465594`를 검토해 변경 요청(FAIL)을 냈다. P1 3건(Phase 1 토큰 탐지 누락,
  개인 정보 제외 책임 누락, 일찍 빠진 자료의 기록 유출 경로), P2 2건(본문 조회 0건과 QK-ING-001 계약 6항 충돌, 오탐 예외의 자료원 구분).
- 2026-10-19 사용자 결정(1차 검토 반영): 1) FR-009에 반드시 잡을 토큰 종류를 고정한다. 2) 개인 정보는 자동 탐지하지 않고, 자료원 범위를 정할 때
  사람이 확인하는 절차를 요구사항(FR-024)으로 두고 책임은 자료원 추가 명세에 넘긴다. 3) 모든 판정 경로에 기록 출력 규칙(FR-023)을 둔다.
  4) 본문 조회 보장을 "목록 반환 뒤 추가 본문 조회 0건"으로 좁히고 QK-ING-001 계약은 바꾸지 않는다. 5) 오탐 예외에 자료원을 넣고 출처 없는 조각에는 적용하지 않는다.
- 2026-10-20 사실: 같은 Codex 세션의 재검토에서 이전 5건 중 3건은 해소, 2건은 일부 해소로 판정하고 P2 2건(FR-023 주소 기록 기준이 `allowed_hosts`에 기댐,
  Assumptions의 예외 형식이 FR-012와 모순)을 냈다. 커밋 scope 지적은 철회했다.
- 2026-10-20 사용자 결정(재검토 반영): 기록 허용 주소는 자료원 종류별 공개 원본 링크 호스트로 따로 정하고 그 밖의 주소는 모든 출력 필드에서 가린다(SC-010).
  Assumptions의 예외 형식을 FR-012에 맞추고, 커밋 검사 예외 목록과 합칠지는 자료원 구분 유지를 조건으로 plan에서 정한다.
- 2026-10-20 사실: 같은 Codex 세션의 두 번째 재검토에서 남은 2건이 해소되고 명세 내용 승인 권고가 나왔다. 수정분은 `8d31c9d`, `c5f6260`으로 커밋했다.
- 2026-10-20 사용자 결정: 사람 리뷰어 Byuntil이 `spec.md`(`8d31c9d` 기준)를 승인했다. 명세를 쓴 세션은 승인하지 않았다(AGENTS.md 2절).
  `/speckit-plan`으로 설계를 진행한다.
- 2026-10-20 사실: 설계 산출물(`plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/` 3개)을 이 세션이 썼다. 설계 승인 대기.
  plan.md "사람 확인이 필요한 것"에 `scripts/preflight.py` 수정, 공수 S→M, ING-001 로그의 `source_id` 노출, ING-002 인계 항목을 남겼다.
- 2026-10-20 사실: 같은 Codex 세션이 설계를 검토해 변경 요청(FAIL)을 냈다. P1 4건(ING-001 로그·요약의 `source_id` 주소 노출, `Listing` 완료 표시 소실,
  맨 호스트 미가림, 따옴표 할당 `*_TOKEN`·`*_SECRET` 누락), P2 3건(`--staged`가 작업 트리 규칙 사용, 예시 예외가 tfstate까지 해제, 본문 조회 실패 자료의 판정 기록 없음).
- 2026-10-20 사용자 결정(설계 리뷰 반영): 1) #35는 고치지 않고, 비밀값이나 주소가 든 `source_id`는 본문 조회 전에 막는다. 2) 맨 호스트는 파일 확장자 목록 기준으로
  보수적으로 가린다. 3) 나머지(목록 상태 보존, `--staged` index 규칙, 이름 규칙 확장, 예시 예외 범위 축소, 조회 실패는 판정 실패로 기록)는 제안대로 고친다.
- 2026-10-20 사실: 같은 Codex 세션의 설계 재리뷰에서 이전 7건 중 5건 해소, 2건 일부 해소. P1 1건(확장자 예외가 확장자와 겹치는 호스트를 새게 함),
  P2 1건(주소 정책이 보안 규칙 버전 계산에 빠짐)을 냈다.
- 2026-10-20 사용자 결정(설계 재리뷰 반영, 방안 A): 맨 호스트는 필드 종류별로 판정하고, 확장자 예외는 경로 필드(`location`, 경로형 `source_id`)의 파일 이름
  부분에만 적용한다. FR-023 "주소"에서 경로 필드 파일 이름을 빼는 해석이므로 PR에서 명세 문구 보완을 제안한다. 주소 정책과 종류 정책을 규칙 버전 해시에 넣는다.
- 2026-10-20 사실: 같은 Codex 세션의 두 번째 설계 재리뷰에서 앞의 2건은 해소, 방안 A 해석은 사용자 결정을 근거로 재승인 없이 진행 가능으로 판정했다.
  새 P2 1건(출력 API에 필드 종류·정책 문맥이 없음)을 냈다. 방안 A의 일관성 수정이라 `OutputContext`와 `safe_text(value, field_kind, context)`로 바로 고쳤다.
- 2026-10-20 사실: 같은 Codex 세션의 세 번째 설계 재리뷰에서 남은 P2가 해소되고 설계 승인 권고(PASS)가 나왔다. 설계 산출물은 `7294c48`로 커밋했다.
- 2026-10-20 사용자 결정: 사람 리뷰어 Byuntil이 설계(`7294c48` 기준)를 승인했다. 설계를 쓴 세션은 승인하지 않았다(AGENTS.md 2절).
  `/speckit-tasks`로 작업 목록을 만든다. 구현과 `scripts/preflight.py` 수정은 tasks 승인 뒤에 범위를 넓힌다.
- 2026-10-20 사실: `tasks.md`(57개 작업)를 이 세션이 썼다. tasks 승인 대기. 설계와 다르게 둔 두 곳(`redact`를 `domain/redact.py`에 둠, 시험 파일
  `test_screen_no_secret_leak.py` 이름)을 tasks.md 머리에 적었다.
- 2026-10-20 사용자 결정: 사람 리뷰어 Byuntil이 `tasks.md`(설계 조정 두 곳 포함)를 승인했다. tasks를 쓴 세션은 승인하지 않았다(AGENTS.md 2절).
  `scripts/preflight.py` 수정(T011, T021)을 허용한다. 구현 범위를 Scope·Ownership에 넓혔다.
- 2026-10-20 사용자 결정: 구현은 이 Claude 세션이 맡고, 검증·코드 리뷰는 오른쪽 Codex 패널(명세·설계 리뷰를 맡은 세션)이 맡는다.
- 2026-10-20 사실: tasks.md T001~T050, T052~T056 구현 완료(T051 단독 커밋, T057 PR 본문 남음). AGENTS.md 7절 검증 전체 통과(pytest 459 passed, ruff, preflight 280개 파일,
  `-I` preflight, 로컬 DB). SC-008 측정: 합성 Markdown 81개, 1,088,640바이트, 0.086초(상한 60초).
- 2026-10-20 사실(T021): 넓힌 이름 규칙이 `src/qello_knowledge/domain/security.py`의 판정 이름 열거형(`SECRET_BLOCKED = "SECRET_BLOCKED"` 등)을 오탐으로 잡아
  `scripts/preflight_allowlist.txt`에 `assigned-secret`, `env-assigned-secret` 두 줄을 사유와 함께 넣었다. 실제 비밀값은 없었다.
- 2026-10-20 사실(구현 중 설계 조정, 리뷰에서 확인): 1) 누출 시험이 공개 호스트 링크의 경로에 든 내부 도메인을 찾아, 링크 필드는 공개 호스트라도 경로·쿼리에
  주소가 있으면 전체를 가리게 했다(R-07을 더 엄격하게 적용). 2) `scripts/preflight.py`에 다른 시험이 읽는 모듈 속성 `RULES`를 호환용으로 남겼다.
  3) `tests/unit/test_preflight_allowlist.py` 픽스처가 규칙 모듈도 복사하게 고쳤다. 4) 승인된 `contracts/security-filter.md` 코드 블록 한 곳을 `ruff format`이
  요구해 서식만 바꿨다(내용 변경 없음). 5) 요약·버전·오류 격리는 판정 단계 구현 때 함께 만들어 해당 시험이 처음부터 통과했다(시험 먼저 원칙의 예외).
- 2026-10-20 사실: 구현을 `a3196b1`(규칙 공유·preflight), `ddbb0d0`(보안 필터), `afb22bf`(security check 명령), `4e6297d`(SC-006 두 번째 종류,
  `git show --stat` 결과 `tests/unit/security/test_second_kind.py` 한 파일)로 커밋했다.
- 2026-10-20 사실: 같은 Codex 세션이 구현을 검토해 변경 요청(FAIL)을 냈다. P1 3건(오탐 예외가 `source_id` 사전 차단을 해제, 한 자리 포트 미탐지,
  퍼센트 인코딩 주소 미탐지), P2 4건(혼합 IPv6 일부만 가림, 접근 판정 뒤 권한 증빙 누락, `--staged`가 작업 트리 규칙 실행, 예상 밖 본문 식별자가 배치 중단).
  Codex 직접 실행: pytest 459 passed(로컬 DB 포함), ruff·format·diff 검사 통과. 전체 preflight는 샌드박스 제한으로 미실행.
- 2026-10-20 사실: 7건을 tasks.md Phase 9(T058~T064)로 고쳤다. 승인된 구현 범위 안의 버그 수정이라 바로 반영했다. AGENTS.md 7절 검증 재실행 통과
  (pytest 478 passed, preflight 283개 파일, `-I` preflight, ruff, 로컬 DB).
- 확인 필요: 요약·버전·오류 격리 시험이 구현 뒤에 쓰여 처음부터 통과한 "시험 먼저 원칙 예외"를 사람이 받아들일지(Codex 리뷰 required_human_decisions).
