# Task Contract: QK-STO-002 인덱스 버전 생성·평가 게이트·활성화 (WBS 2.1)

> Generated at: `2026-10-31`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-125` / https://tkv123.atlassian.net/browse/SCRUM-125 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: `QK-STO-002` / `specs/QK-STO-002-index-version-gate/spec.md`(작성 예정)
- 팀 스프린트 ID: `QELLO-S2026-W44`
- GitHub Issue: `#92`
- Branch: `feat/SCRUM-125-gh-92-index-version-gate`
- Base branch: `main`. 2026-10-31 `origin/main` `c4ca593`(#91 병합)에서 분기했다. 이전 `main`의 QK-EVL-001 계약은 git 이력에 남긴다.

## Objective

- 이번 단계: 명세 단계다. 이 계약이 승인되면 `/speckit-specify`로 `spec.md`를 쓰고, 작성에 관여하지 않은 별도 에이전트의 읽기 전용 검토를 반영한 뒤 사람 승인을 받는다.
  plan·tasks·구현은 1.G 뒤에 시작한다.
- 목적: C-07과 AGENTS.md 3.3의 "평가를 통과한 버전만 활성화"를 실행할 수 있는 절차로 정한다. 2.G 완료 조건 "청킹·검색 설정을 바꿔 새 인덱스 버전을 만들고, 평가를 통과한 뒤 활성화하는 절차를 한 번 실행했다"와
  QK-CHK-001·QK-ING-003의 켜는 변경, ADR-010 운영 반영이 이 절차를 선행으로 둔다.

## Scope

- `specs/QK-STO-002-index-version-gate/`: `spec.md`, `checklists/requirements.md`
- `TASK.md`(이 파일)
- 명세 단계라 코드·시험·마이그레이션·설정 파일은 바꾸지 않는다.

## Explicit exclusions

- plan·tasks·구현(1.G 뒤), 색인·평가 실행, 외부 API 호출, 운영 DB 접근(읽기 포함)
- QK-EVL-001 계약 문서(`contracts/question-set.md`, `contracts/run-record.md`, `contracts/cli.md`)와 평가 코드 수정. 게이트는 이 계약을 입력으로만 쓰고, 바꿔야 할 점이 나오면 spec에 넘김 항목으로 남긴다
- 다른 명세 문서(QK-STO-001, QK-SYN-001, QK-EMB-001, QK-EVL-001, QK-CHK-001, QK-ING-003 등) 수정
- 운영 키워드 규칙·토크나이저 교체와 ADR-010 결정, 코드 청킹·Confluence 자료원 켜기
- 답변 평가(QK-EVL-002), 쓰지 않는 벡터·내린 문서의 물리 정리(QK-SYN-003)
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, 결정 기록(ADR), `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정
- `.env`·`.env.*` 읽기. 설정은 항목 이름으로만 가리킨다
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문, DB 연결 주소·서버 주소는 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 없음
- 외부 API로 보내는 데이터: 없음
- 예상 임베딩·생성 호출량과 무료 한도 대비: 명세 단계 0 Neurons. 새 인덱스 버전 전체 재색인과 게이트 평가의 예상 Neurons는 plan에서 추정한다
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-STO-002-index-version-gate/`, `TASK.md` | tkv00 | 독립 검토 에이전트, 사람 리뷰 |

## Existing user-owned changes

- 2026-10-31 `origin/main`(`c4ca593`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
```

`python`이 없는 환경에서는 `uv run python scripts/preflight.py`로 실행한다.

## Completion criteria

- `TASK.md`가 사람 승인을 받는다 — 이 파일의 Decisions
- `spec.md`가 별도 에이전트 검토를 반영한 뒤 사람 리뷰로 승인된다 — 검토 기록, 이 파일의 Decisions
- spec의 평가 게이트가 QK-EVL-001 계약(질문 세트 형식, 실행 기록 `qk-evl-001-run/v1`, `qk-dev eval run`·`tables`)을 바꾸지 않고 입력으로 쓰고,
  QK-EVL-001 FR-030(토크나이저를 가릴 식별자)을 요구사항이나 사람 결정 항목으로 담는다 — spec 본문, 검토 기록

## Decisions

- 2026-10-31 사용자 결정: QK-STO-002 이슈를 `/harness-issue`로 만든다. GitHub Issue #92를 저장소 작업 폼 형식으로 열었고, Jira 하위 작업 `SCRUM-125`는 `jira-subtask` 워크플로가 만들었다. 팀 스프린트 ID는 `QELLO-S2026-W44`다.
  사용자 스킬의 type 라벨·Project 필드 단계는 이 저장소가 쓰지 않아(#90도 라벨·Project 없음) 건너뛰었다.
- 2026-10-31 사용자 결정: 1.G(Phase 1 완료 리뷰)가 끝나지 않은 상태에서 명세 단계만 진행한다. plan·tasks·구현은 1.G 뒤에 한다(로드맵 1절 5번).
- 2026-10-31 사실(작성 세션 확인):
  - Jira 하위 작업의 스프린트가 상위 이슈를 따라 `Backend·Sprint 3 (12/10–18/10)`으로 잡혔다(#90의 `SCRUM-124`와 같다). 스프린트 이동은 사람이 Jira에서 한다.
  - 백로그 요구사항 열의 FR-STO-04, FR-EMB-05, ADR-018은 저장소와 git 이력에 원문이 없다. `git log --all -S`로 찾으면 로드맵을 처음 더한 커밋(`2aa2f8e`)에만 나오고 `docs/sdd/decisions/`에 ADR-018이 없다.
    QK-STO-001·QK-EMB-001과 같은 상황이라 뜻을 추측해 대응시키지 않는다.
  - 검색 함수는 활성 인덱스 버전만 대상으로 한다(`migrations/0002_search_functions.sql:9-10`의 `qk.active_index_version()`). 준비 상태 버전의 청크는 검색되지 않는다(QK-STO-001 FR-008).
  - QK-EVL-001 실행기의 평가 대상은 로컬 컨테이너의 `qk_eval_*` DB뿐이다(`contracts/cli.md` 머리말). 그래서 운영 DB의 준비 버전을 어디서 어떻게 평가할지가 spec의 핵심 결정이다.
  - 동기화는 활성 버전이 있고 현재 설정의 버전과 다르면 바뀐 문서 처리를 멈춘다(QK-SYN-001 FR-020, `sync/run.py:93-94`). 문서별 처리 상태는 버전 하나만 기록한다(`artifact.processed_index_version`, `migrations/0004_sync.sql:7`).
  - 첫 버전 활성화 명령은 활성 버전이 없을 때만 동작한다(`adapters/postgres/sync_store.py`의 `_activation_check`, 조건 `active_exists`).
  - 인덱스 버전 재료는 임베딩 모델, 차원, 청킹 규칙 버전, 메타데이터 스키마 버전 넷이다(`sync/keys.py`의 `index_version_id`). 키워드 색인 토크나이저는 재료가 아니다(QK-EVL-001 FR-030).
    벡터 차원은 스키마가 1024로 고정한다(`migrations/0001_initial_schema.sql:12`, `:44`).
  - 코드 청킹·Confluence가 켜진 인덱스 버전은 키워드 규칙 대응표(`domain/keyword_rules.py`의 `INDEX_KEYWORD_RULES`)에 없으면 설정 점검이 막는다(`config/check.py:150`, `indexer/sync_cli.py:135-138`).
  - 다른 명세가 이 명세에 넘긴 일: QK-SYN-001 plan(쓰지 않게 된 준비 버전 정리, 평가 게이트를 거친 버전 교체, 버전 불일치 해소), QK-EVL-001 plan(질문 세트·실행 기록을 게이트 입력으로 사용, FR-030 식별자),
    QK-CHK-001 `contracts/chunker.md` 7절(켜짐 인덱스 버전을 대응표에 더하고 생성·평가·활성화), QK-ING-003 plan(`+cf1` 제거는 새 인덱스 버전 절차).
- 2026-11-02 사용자 결정: 이 초안의 승인 질문을 닫고 "작업 계속진행"이라고 지시했다. 이 계약을 승인한 것으로 보고 `/speckit-specify`로 넘어간다(작성 세션 해석, 사람 확인 대상).
- 2026-11-02 사실: `/speckit-specify`로 `specs/QK-STO-002-index-version-gate/spec.md`와 `checklists/requirements.md`를 썼다.
  spec 독립 검토(작성에 관여하지 않은 별도 서브에이전트, 읽기 전용) 판정은 변경 요청이다(높음 3, 중간 11, 낮음 5). 작성 세션이 지적 근거를 코드로 다시 확인하고 모두 반영했다. 반영분은 다시 검토받지 않았다.
  - 확인한 근거: 불일치 보류는 처리·원본 사라짐·일반 내림을 막는다(`domain/sync.py:88`). 다시 처리한 문서는 그 버전만 본문 삭제 대기에서 빠진다(`adapters/postgres/sync_store.py:189-194`).
    문서 행 갱신이 원본 링크·제목·원본 수정 시각·수집 시각을 덮어쓴다(`sync_store.py:151-162`). 검색 결과의 원본 링크는 문서 행, 원본 버전은 청크에서 온다(`migrations/0002_search_functions.sql:20-21`).
    QK-EVL-001 공통 질문 집합은 근거 미색인·실패·하이브리드 생략을 비교에서 뺀다(`evaluation/compare.py:96-102`, `:137-149`). 보류된 실행은 현재 설정 버전을 적고 "멈춤"으로 끝난다(`sync/run.py:74-85`, `sync/report.py:65`).
    예산 초과의 기본 동작은 실행하지 않음이다(QK-EMB-001 FR-024). 버전 재등록은 `ON CONFLICT DO NOTHING`이다(`sync_store.py:63-70`). 실행기는 후보 A·B·C 조합만 받는다(`evaluation/prechecks.py:67-76`).
    전환 순간 검색은 `index_version_changed`로 실패하고 다시 시도하지 않는다(`retrieval/service.py:204-205`, `:219-220`).
  - 반영(높음): 활성화·되돌리기에 본문 삭제 대기 0 조건(FR-021 (10), FR-024), 정리 때 대기 목록 갱신(FR-027). 불일치 중 일반 내림 보류를 Edge Cases에 바로 적고, 재색인 실행이 설정과 무관한 일반 내림을 하게 함(FR-010, D2).
    판정 질문 집합을 기준 대상으로 정하고 후보에서만 생긴 실패를 놓침으로 셈(FR-016), 가드레일 G1.
  - 반영(중간·낮음): 재색인 실행만 보는 활성화 조건(FR-021 (2)), 예산 초과 기본 실행 안 함과 미리 보기 제한 문구(FR-006, US1-1·US1-3), 출처 정보 항목에 수집 시각·원본 링크·원본 수정 시각(FR-005, SC-001),
    되돌리기의 출처 어긋남 확인(FR-024, D7), 토크나이저 선택지 셋과 FR-021 (8) 문구(FR-033, D6), 정책 지문·`main` 병합 고정·코드 커밋 검사(FR-012, FR-015 (8), D4), 가드레일 목록(FR-017),
    "대상 아님"을 덮음에 셈과 영구 실패 처리(FR-010, FR-011), 재사용 전환(FR-001, US1-8), 평가 대상 준비 한계와 넘김(FR-013, Assumptions), 평가 사용량 합산 보고(FR-034), `+cf1`을 범위 밖과 넘김으로,
    재처리 범위 문구(FR-025), 되돌리기 대상 문구 통일(US4, D5), 전환 순간 실패 허용(SC-004), 활성화의 `RetrievalSettings` 검사(FR-021 (9)), 기록의 임베딩 모델(FR-018, FR-032), 모델 교체 시나리오(US1-9), SC-001 시험 데이터 조건.
- 2026-11-02 사용자 결정: `spec.md`를 승인했다("spec 승인"). 사람 확인 대상으로 남긴 기본값 D1~D7과, "작업 계속진행"을 이 계약의 승인으로 본 해석도 이 승인에 포함된 것으로 본다.
  plan·tasks·구현은 1.G 뒤에 `/speckit-plan`부터 한다(2026-10-31 사용자 결정).
