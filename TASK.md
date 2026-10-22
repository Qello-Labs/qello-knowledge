# Task Contract: QK-RET-001 하이브리드 검색·RRF·문맥 확장·토큰 예산·키워드 검색 텍스트 (WBS 1.9)

> Generated at: `2026-10-22`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-104` / https://tkv123.atlassian.net/browse/SCRUM-104 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: QK-RET-001 / `specs/QK-RET-001-hybrid-retrieval/spec.md`(2026-10-22 승인)
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#51`
- Branch: `feat/SCRUM-104-gh-51-hybrid-retrieval`
- Base branch: `main`. 2026-10-22 `origin/main` `e4fee77`(#49 병합)에서 분기했다

## Objective

- 완료: QK-RET-001 명세(`spec.md`)를 `/speckit-specify`로 작성하고, 별도 에이전트의 독립 검토 3회(변경 요청 2회, 승인 권고 1회)를 거쳐 사람 승인을 받았다(2026-10-22).
- 완료: `/speckit-plan` 설계 산출물(`plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`)을 만들고, 별도 에이전트 독립 검토 3회(변경 요청 2회, 승인 1회)를 거쳐 사람 승인을 받았다(2026-10-22).
- 완료: `/speckit-tasks` 작업 목록(`tasks.md`, 작업 56개 + 사람 단계 3개)을 만들고 사람 승인을 받았다(2026-10-22). 승인 뒤 독립 검토를 한다.
- 이번 단계: `tasks.md` T001~T056 구현. 독립 검토 지적을 반영한 뒤 시작한다. 사람 단계 H02·H03은 구현 뒤 사람 확인으로 한다.

## Scope

- `specs/QK-RET-001-hybrid-retrieval/spec.md`·`plan.md`·`research.md`·`data-model.md`·`quickstart.md`·`contracts/`(승인됨, 바꾸려면 다시 승인), `checklists/requirements.md`, `measurement/measure_context.py`
- 작업 목록 `tasks.md`(승인됨). 구현 중 체크 표시와 실행 기록은 고친다.
- 구현(plan.md Project Structure·"구현 Scope 승인이 필요한 것", 2026-10-22 tasks 승인과 함께 승인):
  - 새 파일: `src/qello_knowledge/domain/retrieval.py`, `domain/keyword_rules.py`, `ports/retrieval.py`, `retrieval/`(`__init__`, `keyword`, `fusion`, `pack`, `service`),
    `indexer/search_cli.py`, `devtools/eval_index.py`, `adapters/postgres/migrations/0005_retrieval.sql`(함수 2개 추가만)
  - 기존 파일 변경: `domain/chunking.py`·`chunking/header.py`·`chunking/service.py`·`chunking/version.py`(QK-CHK-002, 기준선 출력·해시 불변), `adapters/postgres/store.py`(메서드 추가만, QK-STO-001),
    `indexer/sync_cli.py`(조립 함수 인자, 기본 동작 그대로, QK-SYN-001), `indexer/cli.py`(`search` 등록), `devtools/db.py`·`devtools/bench.py`, `config/registry.py`와 설정 예시 재생성(QK-FND-001)
  - 시험: `tests/unit/retrieval/`, `tests/localdb/retrieval/`, `tests/localdb/devtools/`, `tests/unit/chunking/`·`tests/unit/indexer/`·`tests/unit/config/`의 새 파일, `tests/unit/test_boundaries.py`(검사 추가만),
    기대값 갱신 2건 `tests/localdb/sync/test_migration.py`·`tests/unit/devtools/test_measure.py`(2026-10-22 사용자 결정, 검사 내용 그대로)
- `TASK.md`(이 파일)

## Explicit exclusions

- Scope에 없는 코드 변경, 기존 SQL 함수·테이블·`PostgresStore` 기존 메서드 변경, 운영 색인 규칙·인덱스 버전 변경, 운영 저장소 대상 색인 실행.
- 실제 Workers AI 호출과 평가용 색인 준비(H02)·실제 검색 확인(H03)은 사람 확인 없이 하지 않는다.
- 질문 분류·필터 추론(QK-TRK-001), 질의 재작성(QK-BOT-002), 관계 기반 확장(QK-RET-002), 리랭커(QK-RET-003),
  검색 평가 실행기(QK-EVL-001), 인덱스 버전 활성화(QK-STO-002), 생성(QK-GEN-001).
- ADR-010 확정. 이 명세는 후보와 기준선을 정하고, 비교 평가와 확정은 QK-EVL-001 결과로 한다.
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, ADR, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 기본 검증 0건(가짜 제공자). H03에서만 질문 몇 개를 질의용 임베딩으로 보낸다(사람 확인 뒤)
- 예상 임베딩·생성 호출량과 무료 한도 대비: 명세 단계 0 Neurons. 구현 뒤 질의 임베딩은 질의응답 예비 예산(하루 3,000 Neurons)에서 차감한다
- 인덱스 버전 변경: 운영 색인은 없음(옵션 A, 기준선 유지). 평가용 색인(별도 로컬 DB)만 식별자 분해 후보의 새 인덱스 버전을 갖는다. 임베딩 캐시를 복사하므로 예상 0 Neurons이고,
  캐시로 처리되지 않는 임베딩이 있으면 미리 보기로 보고하고 사람 확인을 받는다

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-RET-001-hybrid-retrieval/`, `TASK.md` | tkv00 | 사람 리뷰 |
| `src/qello_knowledge/retrieval/`, `domain/retrieval.py`, `domain/keyword_rules.py`, `ports/retrieval.py` | tkv00 | 사람 리뷰 |
| `adapters/postgres/store.py`, `adapters/postgres/migrations/0005_retrieval.sql` | tkv00 | 사람 리뷰 |
| `domain/chunking.py`, `chunking/header.py`·`service.py`·`version.py` | tkv00 | 사람 리뷰(기준선 해시 불변 확인) |
| `indexer/search_cli.py`, `indexer/cli.py`, `indexer/sync_cli.py`, `devtools/eval_index.py`·`db.py`·`bench.py`, `config/registry.py`, `.env.example` | tkv00 | 사람 리뷰 |
| `tests/` 새 시험과 기대값 갱신 2건(`tests/localdb/sync/test_migration.py`, `tests/unit/devtools/test_measure.py`) | tkv00 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-22 `origin/main`(`e4fee77`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

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
uv run qk-dev store bench --retrieval   # SC-006, 결과는 tasks.md 실행 기록
```

## Completion criteria

- 벡터 쪽에만·키워드 쪽에만·양쪽에 걸린 청크가 RRF 순서대로 합쳐지고 두 번 실행이 같다 — 단위·로컬 DB 시험(SC-001)
- 접근 범위 미확인·제한, 비활성 인덱스 버전, 삭제·내림 청크가 결과와 Context에 0건이다 — 로컬 DB 시험(SC-002, 로드맵 1.G 조건)
- Context 예상 토큰 합이 예산 이하이고 잘림·중복 0건이다 — 단위 시험(SC-003)
- 기준선 `chk-md-20d966f730bb`·`iv-4c0bc4fcc642`가 그대로이고, 캐시를 복사한 평가용 DB 색인에서 임베딩 호출 0건이다 — 단위·로컬 DB 시험(SC-009, SC-010)
- 질의당 외부 호출 7회 이하, 단일 방식 실패가 다른 방식으로 바뀌지 않고, 요약·기록에 질문 원문 0건이다 — 단위 시험(SC-007, SC-008, SC-011)
- 로컬 1.1 MB에서 하이브리드 검색 + Context p95 1.5초 — `qk-dev store bench --retrieval` 측정(SC-006)

## Decisions

- 2026-10-22 사실: GitHub Issue #51을 작업 폼 형식으로 만들었고, `Jira subtask` 워크플로가 `SCRUM-42` 아래 `SCRUM-104`를 자동 생성했다.
  하위 작업의 Jira 스프린트는 상위 이슈를 따라 `Backend·Sprint 3`(10/12–10/18)이라 팀 스프린트 ID `QELLO-S2026-W43`과 어긋난다. 새 스프린트 생성은 사람이 한다.
- 2026-10-20 사용자 결정(이어받음): 단계 게이트 0.G는 미완료 상태로 Phase 1을 계속 진행한다.
- 2026-10-22 사용자 결정: 이 TASK.md를 승인했다("작업진행"). Jira 새 스프린트 생성도 요청했으나 Atlassian 연결이 인증되지 않아 하지 못했다(BLOCKED, 사람이 직접 만들거나 연결 인증 필요).
- 2026-10-22 사용자 결정(명세 확인 Q1): ADR-010 색인 쪽 후보(기준선, 식별자 분해)를 모두 구현하되 운영 기본값은 기준선으로 둔다. 질의 쪽 규칙은 바로 적용한다.
  운영 색인 규칙 변경은 QK-EVL-001 비교와 ADR-010 확정 뒤 별도 작업으로 한다.
- 2026-10-22 사실: 작성에 관여하지 않은 별도 에이전트가 명세를 독립 검토해 변경 요청을 냈다(높음 2, 중간 6, 낮음 8). 사용자는 별도 세션을 요청했으나 원격 제어 중이라
  세션을 만들 수 없어 서브에이전트로 했다.
- 2026-10-22 사용자 결정(검토 반영): H1 평가용 색인은 후보마다 별도 로컬 DB + 임베딩 캐시 복사(이 명세가 준비 절차, QK-EVL-001이 비교). H2 질의당 외부 호출 상한 6
  (사용량 기록 포함), 인덱스 버전 바뀜은 다시 검색하지 않음, 질의 임베딩 재시도 1회. M1 상위 절은 가장 가까운 절의 첫 청크만, 주변 청크 일괄 조회를 새로 둔다.
  M5 Context 토큰 예산 2,000(Context 몫), 생성 토크나이저 비율 측정을 계획 게이트로 둔다.
- 2026-10-22 사실: 같은 검토자의 재검토 판정은 변경 요청이다(높음 1: 재시도 경로 외부 호출 7, 중간 2: 다시 확인에서 빠진 중심 청크 처리, 평가 비교의 원본 시점). 질의용 임베딩이
  시도마다 사용량을 기록하는 것을 `embedding/service.py`에서 확인했다.
- 2026-10-22 사용자 결정(재검토 반영): 질의당 외부 호출 상한 7, 재시도 1회. 평가용 색인은 기준선 포함 모든 후보를 같은 원본 리비전으로 새 로컬 DB에 만든다.
- 2026-10-22 사실: 같은 검토자의 최종 확인 판정은 승인 권고다(명세 수준, N1~N9 해소, 새 모순 없음). 참고: FR-029의 커밋 고정이 자료원 설정으로 되는지는 계획 단계에서 확인한다.
  사람의 명세 승인은 아직 받지 않았다.
- 2026-10-22 사용자 결정: QK-RET-001 `spec.md`를 승인했다. 바꾸려면 다시 승인을 받는다.
- 2026-10-22 사실(plan): 로컬 컨테이너의 일회용 DB(`qk_scratch_ret001`, 측정 뒤 지움)에서 PGroonga 동작을 쟀다. `pgroonga_query_escape`는 `OR`를 이스케이프하지 않아
  새 키워드 SQL 없이 OR 검색이 된다(research R-03). 외부 API 0건, 0 Neurons.
- 2026-10-22 BLOCKED(plan 게이트 R-08): 생성 토크나이저 비율·예산 초과 청크 수 측정은 대상 저장소 복제와 Qwen3 토크나이저 내려받기 허락이 필요해 하지 않았다.
- 2026-10-22 사용자 결정: R-08 측정을 허용했다(Hugging Face 토크나이저 내려받기). 대상 저장소는 scratchpad에 읽기 전용으로 복제했다.
- 2026-10-22 사실(R-08 실측): 커밋 `6aeccd03`, 79개 문서·1,291개 청크, Qwen3 토크나이저 실제/예상 p95 1.286·최대 1.875, 예상 2,000 초과 청크 3개(0.23%). 판정 기준 안이라
  Context 예산 2,000을 유지한다. Workers AI 0건.
- 2026-10-22 사실: plan 독립 검토를 사용자가 별도 세션으로 요청했으나 원격 제어 중이라 세션을 만들 수 없어 별도 서브에이전트로 시작했다.
- 2026-10-22 사실: plan 독립 검토(별도 서브에이전트) 판정은 변경 요청이다(높음 3, 중간 4, 낮음 8). PGroonga 점수가 낱말 횟수인 것과 일치 확장(match escalation)을 일회용 DB에서 다시 재현했다.
- 2026-10-22 사용자 결정(plan 검토 반영): H1 새 키워드 함수 `qk.search_keyword_terms`(서로 다른 맞은 낱말 수 순). H2 그 함수에서 일치 확장을 끈다(기존 `qk.search_keyword`는 그대로).
  H3 평가용 색인 준비는 범위 검토 파일의 임시 사본에서만 `ref`를 바꾸고, `sync_cli` 조립 함수가 청커 설정을 인자로 받게 고쳐 라이브러리로 부른다.
- 2026-10-22 사실: 같은 검토자의 plan 재검토 판정은 변경 요청이다(중간 2: 낱말 "OR"이 점수 질의를 깨뜨림, spec에 없는 실패 종류 `vector_search_failed`. 낮음 7).
  N1은 대문자 `OR`를 소문자로 바꾸는 단계를 되살려 고쳤다. N2는 spec 재승인을 피해 벡터 전용의 벡터 검색 오류를 기존 종류 `store_unavailable`로 대응시켰다(작성 세션 판단, 사람 확인 대상).
- 2026-10-22 사실: 같은 검토자의 plan 최종 확인 판정은 승인이다. 남은 사소한 점 2건(`kw-query-raw`의 `OR`, R-10 옵션 줄)도 반영했다.
- 2026-10-22 사용자 결정: plan을 승인했다(독립 검토를 거친 뒤 진행하라는 지시, "3. 진행"). 다음 단계는 `/speckit-tasks`다.
- 2026-10-22 사용자 결정: `tasks.md`를 승인했다("승인 후 독립 검증 시행"). Scope를 구현 범위로 갱신했다. 독립 검토는 별도 서브에이전트로 한다(원격 제어 중이라 세션을 만들 수 없음).
- 2026-10-22 사실: tasks 독립 검토(별도 서브에이전트) 판정은 변경 요청이다(높음 2: Scope 밖 기존 시험 2개가 깨짐, 새 시험 파일 이름 충돌로 pytest 수집 실패. 중간 7, 낮음 8). 두 높음은 코드로 다시 확인했다.
- 2026-10-22 사용자 결정(tasks 검토 반영): (1) `tests/localdb/sync/test_migration.py`·`tests/unit/devtools/test_measure.py`의 기대값 갱신을 허용한다(검사 내용 그대로).
  (2) 설계 문서를 tasks에 맞춰 고치고 이 답을 재승인으로 본다: 키워드 결과 타입 `KeywordSearchResult`/`KeywordHit`(contracts), SC-006은 `qk-dev store bench --retrieval`(quickstart·plan), 시험 파일 이름.
  (3) Ownership은 tkv00. Validation·완료 조건을 구현 단계에 맞게 고쳤다.
- 2026-10-22 사실: 같은 검토자의 tasks 재검토는 경미한 변경 요청이다(중간 1: T043이 `build_runtime`의 종류 검사·실제 전송 때문에 가짜 자료원으로 실행되지 않음. 낮음 2). 검토자는 고치면 승인 권고, 재검토 불필요라고 했다.
  N1은 `targets_factory`·`provider_factory` 주입으로(종류 검사는 기본 대상 함수 안으로), N2는 T007 표기 통일로, N3은 `EmbedError` 경로의 호출 수를 최대치로 세고 표시 필드를 두지 않는 쪽으로 고쳤다
  (data-model 변경 없음, 작성 세션 판단).
- 2026-10-22 사실(구현): `tasks.md` T001~T056을 구현하고 스토리 단위로 커밋했다(e94b772~7172c93). 구현 중 발견 2건을 고쳤다. (1) `qk.search_keyword_terms`가 plpgsql 일반 계획으로 바뀐 뒤
  일치 확장이 켜진 것처럼 동작해 `plan_cache_mode = force_custom_plan`을 더했다. (2) 비슈퍼유저 역할의 새 연결에서 0005가 PGroonga 설정 이름을 인식하지 못해 실패해,
  마이그레이션 첫머리에서 PGroonga 함수를 불러 라이브러리를 로드하게 했다. 두 건 모두 회귀 시험이 있다. 0005는 병합 전이라 체크섬 문제는 없다.
- 2026-10-22 사실: preflight가 실패한 상태로 커밋 1건(e94b772, 시험 변수 이름 `SECRET` 오탐)이 들어갔다. 커밋 명령이 preflight 종료 코드를 `tail`로 가렸고 저장소에 커밋 훅이 없었다.
  다음 커밋(d00a678)에서 이름을 바꿔 고쳤고, 그 뒤 커밋은 preflight 종료 코드로 막았다. 값은 비밀값이 아니었다.
- 2026-10-22 검증: preflight, `git diff --check`, ruff check·format --check 통과, `qk-migrate` 두 번째 `applied=0 skipped=5`, `QK_REQUIRE_LOCALDB=1 uv run pytest` 1,506 passed,
  SC-006 bench p95 52.4 ms(목표 1,500 ms). 같은 세션의 자기 검증이라 독립 검증이 아니다. 실제 Workers AI 호출은 하지 않았다(H02·H03은 사람 단계).
- 2026-10-22 사실: 검증 명령의 `qk-migrate`로 로컬 개발 DB(`postgres`)에 0004·0005가 적용됐다. 0005 실패 시도 3건이 `qk.schema_migration`에 `failed`로 남아 있다.
