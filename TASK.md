# Task Contract: QK-EMB-001 임베딩 Provider·캐시·사용량 기록·일일 예산·실행 전 미리 보기 구현 (WBS 1.7)

> Generated at: `2026-10-20`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-42` / https://tkv123.atlassian.net/browse/SCRUM-42 (팀 RAG 구축 상위 이슈. 하위 작업 없음)
- 기능명세서 ID / 링크: QK-EMB-001 / `specs/QK-EMB-001-embedding-provider-budget/spec.md`
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#42`
- Branch: `feat/SCRUM-42-gh-42-embedding-provider-budget`
- Base branch: `main`

## Objective

- 승인된 QK-EMB-001 명세의 `tasks.md`(T001~T048)를 구현해, 색인(QK-SYN-001)과 검색(QK-RET-001)이 쓸 임베딩 경계와
  캐시·사용량 기록·일일 예산·실행 전 미리 보기를 만든다.

## Scope

- 임베딩 경계(`src/qello_knowledge/ports/embedder.py`, `src/qello_knowledge/embedding/`)와 Workers AI 어댑터
  (`src/qello_knowledge/adapters/workers_ai/`, `@cf/baai/bge-m3`, 1,024차원)(US1, FR-001~006).
- 임베딩 캐시: 같은 텍스트·같은 모델이면 다시 부르지 않는다(US2).
- 사용량 기록·정산·90일 보관과 날짜 단위 집계, 마이그레이션 `0003_embedding_usage.sql`(US3, FR-025).
- 일일 예산(색인 5,000 / 질의응답 예비 3,000 / 여유 2,000 Neurons)과 예약 방식 예산 검사(US4).
- 실행 전 사용량 미리 보기, `qk-index usage`·`usage prune` 명령(US5).
- 제공자 호출 직전 QK-SEC-001 전송 검사(`check_outgoing`) 호출(FR-005).
- 위 동작의 단위·로컬 DB 시험, 가짜 제공자, 응답 샘플(`tests/fixtures/workers_ai/`), `external` 시험 파일(T045), 운영 안내(T047).
- `tasks.md` 체크 표시 갱신, `TASK.md`(이 파일).

## Explicit exclusions

- 청킹(QK-CHK-002), 동기화·교체 시점(QK-SYN-001), 검색·RRF(QK-RET-001), 인덱스 버전 활성화(QK-STO-002), 실제 자료 색인.
- `spec.md`의 요구사항·수용 기준 변경. 설계 빈틈이 나오면 구현을 멈추고 사람 결정을 받는다.
- `src/qello_knowledge/security/`(QK-SEC-001) 동작 변경.
- 실제 Workers AI 호출(T045·T046 실측)은 사람 승인 없이 하지 않는다.
- 런타임 의존성 추가(`pyproject.toml`의 `dependencies`)는 사람 승인을 받는다.
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, ADR, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문, Cloudflare 계정 식별자는 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 기본 검증은 0건(가짜 제공자). 실측 시험(T046)은 사람 승인 뒤 합성 텍스트 20개만 보낸다
- 예상 임베딩·생성 호출량과 무료 한도 대비: 기본 검증 0 Neurons. 실측 1회 약 6 Neurons(하루 무료 10,000 대비 0.06%)
- 인덱스 버전 변경: 없음
- 데이터 스키마: 마이그레이션 `0003_embedding_usage.sql` 추가. 로컬 DB에만 적용한다. 병합 뒤 체크섬이 바뀌지 않게 이 브랜치에서 파일을 확정한다

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `src/qello_knowledge/embedding/`, `adapters/workers_ai/`, `ports/embedder.py` | 확인 필요 | 사람 리뷰 |
| `adapters/postgres/migrations/0003_embedding_usage.sql`, `adapters/postgres/usage.py`, `indexer/cli.py` | 확인 필요 | 사람 리뷰 |
| `tests/` 임베딩 시험·응답 샘플 | 확인 필요 | 사람 리뷰 |
| `specs/QK-EMB-001-embedding-provider-budget/tasks.md` 체크 표시, `TASK.md` | 확인 필요 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-20 `origin/main`(`0b8d5d5`, PR #40 병합 커밋)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
uv run qk-migrate   # 두 번 실행, 두 번째는 applied=0
uv run qk-migrate
QK_REQUIRE_LOCALDB=1 uv run pytest
```

## Completion criteria

- 같은 텍스트 묶음을 두 번 임베딩하면 두 번째 외부 호출이 0건이고 벡터가 같다 — 단위 시험(SC-001)
- 색인 예산을 작게 둔 시험에서 예산 초과 0건, 같은 날 질의 거부 0건 — 로컬 DB 시험(SC-002)
- 비밀값 규칙에 걸리는 텍스트와 출처 없는 색인 입력이 제공자로 나간 사례 0건, 사용량 기록에 원문 0건 — 단위 시험(SC-003, SC-006)
- 미리 보기 예상 Neurons와 실측 차이 ±20% 안 — 사람 승인 뒤 `external` 시험 1회(SC-005). 승인 전에는 `BLOCKED`

## Decisions

- 2026-10-20 사실: 명세 PR #40이 사람 리뷰어 Byuntil의 승인(APPROVED)을 받고 `main`에 병합됐다.
- 2026-10-20 사용자 결정: GitHub Issue #42를 만들고, Jira는 하위 작업 없이 상위 이슈 `SCRUM-42`로 추적한다. 자동 생성은 Jira Secret이 없어 동작하지 않는다.
- 2026-10-20 사용자 결정: 이 TASK.md를 승인했다. `/speckit-implement`로 `tasks.md` 순서대로 구현하고 스토리 단위로 커밋한다.
- 2026-10-20 사용자 결정(설계 빈틈): T002(`embedding/`은 표준 라이브러리·`domain`·`ports`·자기 자신만 가져온다)와 T020(서비스가 `security.send_gate`·
  `sources/retry.py`를 직접 쓴다)이 충돌한다. 생성자 주입으로 닫는다. `embedding/`은 `domain`·`ports`만 가져오고, 전송 직전 검사와 재시도 대기 계산은
  `EmbeddingService` 생성 인자(callable)로 받는다. QK-SEC-001·QK-ING-001 함수를 잇는 조립 코드는 `embedding/` 밖에 둔다. T002 경계 시험은 글자 그대로 지킨다.
- 2026-10-20 사실(구현): T001의 시험 디렉터리 `__init__.py`(`tests/unit/embedding`, `tests/localdb/embedding`, `tests/external`)는 만들지 않았다.
  저장소 시험 디렉터리는 `tests/contract` 말고는 `__init__.py`가 없고, 두 `embedding` 디렉터리에 만들면 같은 최상위 패키지 이름이 겹친다.
- 2026-10-20 사실(구현): 기존 `tests/localdb/store/test_migrate.py`가 마이그레이션 개수 2를 고정해 `0003` 추가로 실패했다. 파일 개수에서 세도록 고쳤다(검사 내용은 같다).
  `scripts/preflight_allowlist.txt`에 `domain/embedding.py`의 `SECRET_BLOCKED` 오탐 한 줄을 QK-SEC-001과 같은 사유로 더했다.
- 2026-10-20 검증: preflight, `git diff --check`, ruff check·format --check 통과, `qk-migrate` 두 번째 `applied=0 skipped=3`,
  `QK_REQUIRE_LOCALDB=1 uv run pytest` 706 passed, quickstart 3절 CLI 종료 코드 계약대로(0, 0, 0, 1). 같은 세션의 자기 검증이라 독립 검증이 아니다.
- 2026-10-20 BLOCKED: T046(실제 Workers AI 실측, 예상 6.65 Neurons)은 사람 승인 전이라 실행하지 않았다. 완료 조건 4(SC-005)는 미충족이다.
- 2026-10-20 사실: 구현에 관여하지 않은 별도 에이전트가 `/harness-review` 절차로 검토해 변경 요청을 냈다. 직접 재현 3건(prune 음수 보관 일수로 예산 초기화,
  기록 실패 시 비용을 낸 결과 폐기, `numeric(12,2)` 반올림), 추정 2건(제공자 원시 예외 시 예약 미정산, 재시도 대기 기본값 no-op).
- 2026-10-20 사용자 결정(리뷰 반영): 1) 기록 실패는 spec Edge Cases를 따른다. 결과를 먼저 저장하고 돌려주며, 색인용이면 이후 호출을 멈춘다.
  `contracts/embedder.md` 7단계와 `data-model.md`를 같이 고치고 항목 실패 종류 `usage_unavailable`을 더한다. 2) Neurons 칼럼을 `numeric(14,6)`
  (일 합계 `numeric(16,6)`)으로 넓힌다. `data-model.md`도 고친다. 3) prune은 보관 일수 1 이상을 CLI·SQL 양쪽에서 강제하고, `target=local|remote`를
  출력하며, 원격 DB는 `--allow-remote`가 있을 때만 지운다(종료 코드 3). `contracts/cli.md`도 고친다.
- 2026-10-20 사실: 4) 전송 계층의 읽기 오류를 `NetworkError`로 감싸고, 서비스는 예상 밖 제공자 예외에도 예약을 정산한 뒤 올린다. 5) 재시도 대기 기본값을
  `time.sleep`과 1·2·4초…(최대 60초)로 바꿨다. 반영 뒤 `QK_REQUIRE_LOCALDB=1 uv run pytest` 718 passed.
- 2026-10-20 사실: 0003 파일이 바뀌어, 이 세션 앞부분에서 0003을 적용한 로컬 개발 DB(`postgres`)는 `qk-migrate`가 체크섬 불일치(종료 코드 2)로 멈춘다.
  시험은 세션 전용 임시 DB를 써서 영향이 없다. 로컬 개발 DB 정리는 사람이 정한다.
- 2026-10-20 사실: 같은 검토자의 재검토 판정은 승인이다. 남은 낮은 문제 3건(저장 실패 시 예약 미정산, Retry-After 상한 없음, CLI 종료 코드 2 중복)도 반영했다.
  정산은 `finally`로 보장하고, 대기 상한은 60초, 종료 코드 2의 중복은 `contracts/cli.md`에 적었다. 반영 뒤 pytest 719 passed.
- 2026-10-20 사용자 실행(T046 승인·실행): `uv run pytest -m external tests/external/test_workers_ai_embedding.py -s` 1 passed.
  합성 텍스트 20개(한국어 10, 영어·코드 10), UTF-8 21,620바이트, 예상 6.65 Neurons, 측정 6.49 Neurons(`cf-ai-neurons` 합), 차이 +2.5%,
  모델 `@cf/baai/bge-m3`, 실행일 2026-10-20, 차원 1,024·순서 확인. SC-005(±20%) 충족, `bytes_per_token_estimate` 3.5 유지. 완료 조건 4 충족.
