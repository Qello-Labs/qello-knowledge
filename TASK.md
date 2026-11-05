# Task Contract: QK-STO-002 인덱스 버전 생성·평가 게이트·활성화 구현 (WBS 2.1)

> Generated at: `2026-11-05`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-125` / https://tkv123.atlassian.net/browse/SCRUM-125 (상위 `SCRUM-42` 팀 RAG 구축). 2026-11-05 읽기 전용 조회 상태 "해야 할 일"
- 기능명세서 ID / 링크: `QK-STO-002` / `specs/QK-STO-002-index-version-gate/spec.md`(Approved 2026-11-02, PR #95). plan·tasks는 이 작업에서 만든다
- 팀 스프린트 ID: `QELLO-S2026-W44`(SCRUM-125 본문 값, 2026-11-05 확인)
- GitHub Issue: `#100`(구현용, 2026-11-05 생성). 명세 Issue `#92`는 PR #95로 닫혔다
- Branch: `feat/SCRUM-125-gh-100-index-version-gate-impl`
- Base branch: `main`. 2026-11-05 `origin/main` `6685b88`(#99 병합)에서 분기한다. 명세 단계 계약(QK-STO-002 명세)과 QK-EVL-001 측정 계약은 git 이력에 남긴다.

## Objective

- 승인된 명세의 US1~US5를 구현한다: 재색인(미리 보기·부분 실행·이어 하기), 게이트 판정과 게이트 기록, 활성화, 되돌리기, 상태 보기·정리, 전환 기록.
- 순서: `/speckit-plan` → `/speckit-tasks` → 별도 에이전트 검토 → 사람 승인 → `/speckit-implement`. 각 산출물은 작성에 관여하지 않은 에이전트가 검토하고 사람이 승인한다.
- 목적: 2.G 완료 조건 "새 인덱스 버전을 만들고 평가를 통과한 뒤 활성화하는 절차"를 운영에서 한 번 실행할 수 있게 한다. 그 실행(US6)은 이 브랜치 밖이다(Decisions).

## Scope

- `TASK.md`(이 파일)
- `specs/QK-STO-002-index-version-gate/`: `plan.md`, `research.md`, `data-model.md`, `contracts/**`, `quickstart.md`, `tasks.md`와 검토 기록(`checklists/`). `spec.md`는 바꾸지 않는다
- 코드(tasks.md "TASK.md Scope 갱신안" 반영, 2026-11-05):
  - 동기화·재색인: `src/qello_knowledge/sync/**`(QK-SYN-001의 `plan.py`·`decide.py`·`execute.py`·`preview.py`·`run.py` 수정 포함, 새 `versions.py`), `src/qello_knowledge/domain/sync.py`,
    `src/qello_knowledge/domain/store.py`(`SchemaOutdated`만), `src/qello_knowledge/ports/sync.py`, 새 `ports/index_versions.py`·`ports/history.py`
  - 저장: `src/qello_knowledge/adapters/postgres/**`(새 마이그레이션 `0009_index_versions.sql`, 새 `index_versions.py`, `sync_store.py`, QK-STO-001 `store.py`는 `_replace_chunk_rows`·`trace_chunk`만, `qk.hit_json` 교체).
    기존 마이그레이션 파일은 고치지 않는다
  - 게이트 판정: 새 패키지 `src/qello_knowledge/gate/**`, 새 `src/qello_knowledge/adapters/git_history.py`. QK-EVL-001 실행 기록을 입력으로만 읽는다
  - CLI: `src/qello_knowledge/indexer/**`(`cli.py`, `sync_cli.py`의 `index` 명령 이동과 `build_runtime` 실행 위치 전달, 새 `index_cli.py`), 새 `src/qello_knowledge/devtools/gate_cli.py`, `src/qello_knowledge/devtools/db.py`(`eval gate` 등록만)
- 시험: 새 시험 파일(`tests/unit/**`, `tests/localdb/**`, `tests/fixtures/**`), 기존 파일 가운데 `tests/unit/test_boundaries.py`(검사 추가만). 그 밖의 기존 시험 파일·도우미는 고치지 않는다
- 운영 절차 문서: `docs/ops/oci-production-store.md`(재색인 → 게이트 → 활성화·되돌리기·정리 절차)

## Explicit exclusions

- `spec.md` 수정. plan·구현 중 명세 결함이 나오면 멈추고 사람에게 묻는다
- QK-EVL-001 계약(`contracts/question-set.md`, `contracts/run-record.md`, `contracts/cli.md`)과 기존 시험 기대값 변경(FR-013, FR-036)
- US6 운영 실행: 운영 마이그레이션 적용, 운영 재색인, 운영 게이트 평가·활성화, 운영 DB 읽기·쓰기. ADR-010 Status 결정 뒤 별도 작업에서 승인받아 한다
- 운영에 쓸 첫 게이트 정책의 값(허용 하락·가드레일·최소 판정 질문 수). 사람이 정하고 측정 전에 별도 커밋·PR로 `main`에 병합한다(FR-012). 이 브랜치는 정책 형식과 시험용 예시만 둔다
- ADR-010 Status 결정, 운영 키워드 규칙·토크나이저 교체, D6 선택지 결정(FR-033: A·B면 토크나이저 고정 확인만 구현한다)
- 후보 A·B·C 밖의 평가 대상(코드 청킹·Confluence 켜짐·다른 임베딩 모델) 확장, 차원 변경, QK-SYN-003 물리 정리
- QK-ING-003(Confluence) 작업 파일. 다른 세션이 별도 워크트리에서 진행한다. 공통 파일(`sync/keys.py` 등)을 고쳐야 하면 먼저 알린다
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, 결정 기록, 다른 명세 문서, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정
- `.env`·`.env.*`·`secrets/` 읽기
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 없음
- 외부 API로 보내는 데이터: 없음. 시험은 로컬 DB, 가짜 임베딩 제공자, 손으로 만든 실행 기록·정책만 쓴다(FR-035)
- 예상 임베딩·생성 호출량과 무료 한도 대비: 이 브랜치 0 Neurons. 운영 재색인·평가 대상 준비·질의 임베딩의 예상 Neurons는 plan에서 추정만 하고, US6 실행 전에 다시 보고한다(FR-034)
- 인덱스 버전 변경: 없음. 저장 스키마는 새 마이그레이션을 더하고(전환 기록, 정리 여부 등. plan에서 정한다) 로컬 DB에만 적용한다

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `TASK.md`, `specs/QK-STO-002-index-version-gate/**` | tkv00 | 별도 에이전트 검토(plan·tasks), 사람 승인 |
| `src/qello_knowledge/**`, 새 마이그레이션 | tkv00 | 별도 에이전트 검토, 사람 PR 리뷰 |
| `tests/**` | tkv00 | 사람 PR 리뷰(기존 기대값 변경 0건 확인) |
| `docs/ops/oci-production-store.md` | tkv00 | 사람 PR 리뷰 |

## Existing user-owned changes

- 2026-11-05 앱 워크트리 브랜치 `claude/sto-002-index-gate-92d5fa`(`6685b88`)에서 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
```

외부 호출 시험(`-m external`)은 넣지 않는다. `python`이 없는 환경에서는 `uv run python scripts/preflight.py`로 실행한다.

## Completion criteria

- plan과 tasks가 작성에 관여하지 않은 에이전트의 검토를 반영한 뒤 사람 승인을 받는다 — 검토 기록, `TASK.md` Decisions
- 승인된 tasks.md의 구현 작업이 모두 체크되고, SC-001~SC-008이 시험으로 확인된다(SC-009는 US6이라 제외) — 시험 결과, tasks.md 실행 기록
- 위 검증이 모두 통과하고, 사용자 승인으로 PR이 열린다 — 검증 출력, PR 링크

## Decisions

- 2026-11-05 사용자 결정("구현까지 지금 진행"): 1.G(Phase 1 완료 리뷰) 전에 plan·tasks·구현까지 진행한다. 2026-10-31 결정(명세 391행 "plan·tasks·구현은 1.G 뒤")을 바꾼다. 운영 실행(US6)은 ADR-010 결정 뒤 별도로 한다.
- 2026-11-05 사용자 결정("새 Issue 생성"): 구현용 GitHub Issue를 새로 만든다. 본문의 "기존 Jira 이슈 키"에 `SCRUM-125`를 적어 Jira 하위 작업이 새로 생기지 않게 한다(`scripts/jira_subtask.py`).
- 2026-11-05 사실: ADR-010은 Status Proposed이고 후보 A 유지를 권고한다. FR-033에 따라 A·B로 정해지면 토크나이저는 지금 값으로 고정하고 FR-021 (8)은 그 값인지만 확인한다. C로 정해지면 D6 결정과 추가 구현이 필요하다.
- 2026-11-05 사용자 결정("승인"): 이 계약 초안과 Issue 본문을 승인했다. 아래 사람 확인 대상 3건(US6·첫 정책 값 제외, PR 하나, 스프린트 `W44`)도 포함한다. Issue `#100`을 만들었다.
- 사람 확인 대상(작성 세션 제안, 위 승인에 포함):
  - US6와 운영 첫 게이트 정책 값은 이 브랜치에서 뺀다(위 Explicit exclusions).
  - PR은 하나로 내고 커밋은 검토 목적(계약·plan·tasks, 마이그레이션, 도메인, CLI, 운영 문서)별로 나눈다. plan이 너무 크면 PR을 나누는 안을 plan 검토 때 다시 올린다.
  - 스프린트 ID는 SCRUM-125 본문 값 `W44`를 쓴다. 이번 주 값이 다르면 알려 주면 고친다.
- 2026-11-05 사용자 결정("승인"): QK-STO-002 plan 산출물(plan·research·data-model·contracts·quickstart)을 승인했다. 별도 서브에이전트 검토 2회를 반영한 판이다
  (1차 16건 해소 확인, 2차 7건은 반영 뒤 재검토 없음, `checklists/plan-review.md`). 함께 정한 것: PR 하나에 커밋을 단위별로 나눔, D7 출처 어긋남 = 되돌린 버전 청크가 문서의 마지막 처리 원본 버전보다 옛 문서 수,
  정책 `eval/gate_policies/<ID>/v<N>.toml`·게이트 기록 `eval/gate_records/<gate_id>.json`, 벡터 근사 색인 한계를 받아들이고 운영 문서에 적음, TASK.md Scope는 tasks 승인 때 plan "구현 Scope 승인이 필요한 것"대로 고침.
- 2026-11-05 사용자 결정("승인"): QK-STO-002 tasks.md(T001~T059)를 승인했다. 별도 서브에이전트 검토 2회를 반영한 판이다(1차 23건, 2차 8건은 문구 수준이라 반영 뒤 재검토 없음, `checklists/tasks-review.md`).
  같은 승인으로 위 Scope를 tasks.md "TASK.md Scope 갱신안"대로 고쳤다(`devtools/eval_index.py`는 Scope에서 뺐다).
