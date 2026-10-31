# Task Contract: QK-EVL-001 골든셋 형식 검증·검색 평가 실행기·비교 리포트 (WBS 1.12)

> Generated at: `2026-10-30`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-124` / https://tkv123.atlassian.net/browse/SCRUM-124 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: `QK-EVL-001` / `specs/QK-EVL-001-retrieval-eval/spec.md`(Approved 2026-10-31)
- 팀 스프린트 ID: `QELLO-S2026-W44`
- GitHub Issue: `#90`
- Branch: `feat/SCRUM-124-gh-90-retrieval-eval`
- Base branch: `main`. 2026-10-30 `origin/main` `00a98bb`(#89 병합)에서 분기했다. 이전 `main`의 QK-OBS-001 계약은 git 이력에 남긴다.

## Objective

- 이번 단계: 승인된 `tasks.md`대로 구현한다(2026-10-31 spec·plan·tasks 승인). 코드 단계(T001~T038, T043~T045)는 외부 호출 0이다.
  측정 단계(H00~H08, T017 확정·T018·T039~T042)는 사람 단계마다 실행 전에 허락을 받는다.
- 목적: 1.G 완료 조건 가운데 "첫 검색 평가 리포트(Recall@5, MRR, 벡터·키워드·하이브리드 비교)"와 "ADR-010 확정"을 이 작업으로 채운다.

## Scope

- `specs/QK-EVL-001-retrieval-eval/`: `spec.md`, `checklists/requirements.md`. 승인 뒤 plan 산출물(`plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`)과 `tasks.md`
- `docs/sdd/decisions/ADR-010-keyword-search-text.md`: 비교 리포트가 나온 뒤 Proposed로 쓴다. 결정(Status)은 사람이 한다(QK-RET-001 FR-021)
- `TASK.md`(이 파일)
- 구현 범위(2026-10-31 tasks 승인으로 확정, `tasks.md` "TASK.md Scope 갱신안"):
  - 새 파일: `src/qello_knowledge/evaluation/`(`__init__.py`, `question_set.py`, `labeling.py`, `reuse.py`, `prechecks.py`, `runner.py`, `metrics.py`, `records.py`, `compare.py`), `src/qello_knowledge/ports/evaluation.py`,
    `src/qello_knowledge/adapters/postgres/eval_target.py`, `src/qello_knowledge/devtools/eval_cli.py`
  - 고치는 파일: `src/qello_knowledge/devtools/db.py`(`eval` 묶음, `eval-index --keyword-tokenizer`), `src/qello_knowledge/devtools/eval_index.py`(`prepare_tokenizer`, `eval_tokenizer_db_name` 추가, 기존 `prepare` 그대로),
    `tests/unit/test_boundaries.py`(`evaluation` 검사 추가)
  - 새 시험: `tests/unit/evaluation/`(fakes.py, test_question_set, test_set_warnings, test_labeling, test_golden_v1, test_reuse, test_prechecks, test_runner, test_metrics, test_record_schema, test_compare),
    `tests/unit/devtools/test_eval_cli.py`, `tests/unit/devtools/test_eval_index_tokenizer_cli.py`, `tests/localdb/evaluation/`(conftest, test_eval_target, test_day_usage_reader, test_identifiers_command, test_eval_run),
    `tests/localdb/devtools/test_eval_index_tokenizer.py`, `tests/fixtures/evaluation/question_sets/`
  - 질문 세트: `eval/question_sets/qk-evl-001-golden/`(v1.toml, labeling.md), `eval/question_sets/qk-evl-001-identifiers/`(v1.toml, labeling.md)
  - 측정: `specs/QK-EVL-001-retrieval-eval/measurement/`(runs/, retrieval-eval-report.md), `docs/sdd/decisions/ADR-010-keyword-search-text.md`
  - 후보 C 준비 명령의 계약은 QK-RET-001 `contracts/cli.md`(수정 제외)가 아니라 이 명세의 `contracts/cli.md` 5절에 둔다
  - 질의 벡터 재사용은 `Embedder` 감싸기로 하고 QK-RET-001 검색 경로 코드(`retrieval/`)는 바꾸지 않는다

## Explicit exclusions

- 운영 키워드 규칙·운영 인덱스 버전 교체(ADR-010 승인 뒤 별도 작업)
- 인덱스 버전 평가 게이트·활성화(QK-STO-002), 답변 평가(QK-EVL-002), 골든셋 질문 수집(WBS 0.7)
- `RetrievalSettings` 기본값 변경. 수치와 조정 제안까지만 리포트에 남긴다
- 다른 명세 문서(QK-RET-001·QK-BOT-001 등) 수정. 이 명세가 요구하는 코드 변경은 구현 범위에 넣되 기존 시험 기대값은 바꾸지 않는다
- H05 v2 질문 세트의 질문·핵심 사실·근거 문서 수정. 형식만 옮기고, 라벨을 바꿔야 하면 버전을 올려 평가 코드와 다른 커밋에 사유를 남긴다(AGENTS.md 3.4)
- 운영 DB 쓰기와 운영 마이그레이션 변경. 평가 색인과 후보 C의 토크나이저 교체는 로컬 평가용 DB에만 만든다
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, ADR-010 밖의 결정 기록, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정
- `.env`·`.env.*` 읽기. 설정은 항목 이름으로만 가리킨다
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문, 민감한 질의 원문, 사람 이름은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 없음. 구현·측정 단계에서 기존 `dnd-backend-docs`를 고정 커밋으로 다시 읽어 로컬 평가용 DB에 색인한다(GitHub 읽기 전용)
- 외부 API로 보내는 데이터: 명세 단계 0건. 측정 단계에서는 평가 질문 문장만 Workers AI 임베딩으로 보낸다. 생성 호출은 0건이다
- 예상 임베딩·생성 호출량과 무료 한도 대비: 명세 단계 0 Neurons. 측정 단계의 질의 임베딩은 질의 벡터를 다시 써서 검색할 질문 수(약 90건)만큼이다.
  평가용 DB 준비의 문서 임베딩은 캐시로 처리되면 0이고, 모자라면 후보당 약 900 Neurons가 들 수 있어 준비 명령이 멈춘 뒤 사람이 정한다.
  예상 Neurons는 plan에 적고, 실행 전에 보고한다(AGENTS.md 3.5)
- 운영 DB 읽기: 측정 단계에서 실행 전 잔여량 확인을 위해 운영 사용 장부(임베딩·생성)를 읽기 전용으로 조회한다. 실행 때 사람이 허락한다.
  평가용 DB 준비의 임베딩 캐시는 로컬 개발 DB에서 먼저 복사하고, 모자라면 다시 임베딩할지 운영 DB를 읽을지 그때 사람이 정한다
- 인덱스 버전 변경: 운영 없음. 로컬 평가용 DB에만 후보 B(`kw-index-idsplit-v1`) 인덱스 버전과 후보 C(토크나이저 교체) 색인이 생긴다

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-EVL-001-retrieval-eval/`, `TASK.md` | tkv00 | 독립 검토 에이전트, 사람 리뷰 |
| `docs/sdd/decisions/ADR-010-keyword-search-text.md` | tkv00 | 사람 승인 |
| 구현 코드·질문 세트·리포트(tasks 승인 뒤) | tkv00 | 사람 리뷰(평가 세트와 평가 코드의 커밋 분리 확인) |

## Existing user-owned changes

- 2026-10-30 `origin/main`(`00a98bb`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

명세 단계:

```bash
python scripts/preflight.py
git diff --check
```

구현 단계(2026-10-31 tasks 승인부터)는 AGENTS.md 7절 기본 검증 전체다.

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
```

외부 호출 시험(`-m external`)은 넣지 않는다. 측정 단계의 실행 기록·리포트 대조는 tasks T042다.

`python`이 없는 환경에서는 `uv run python scripts/preflight.py`로 실행한다.

## Completion criteria

- `spec.md`가 별도 에이전트 검토를 거쳐 사람 리뷰로 승인된다 — 리뷰 기록, 이 파일의 Decisions
- (구현 단계) 형식 검증기가 필수 필드 누락·질문 ID 중복·잘못된 유형을 거부하고 올바른 파일을 통과시킨다 — 단위 시험
- (구현 단계) 같은 질문 세트·고정 커밋·임베딩 모델로 세 검색 방식과 ADR-010 후보 A·B·C의 Recall@5·MRR이 표본 수와 함께 리포트에 남는다.
  목표에 못 미쳐도 기록한다 — 평가 리포트, 로컬 DB 시험(운영 DB 쓰기 0건)

## Decisions

- 2026-10-30 사용자 결정: QK-EVL-001을 시작한다("EVL-001 시작"). 산출물과 제외 범위는 Issue #90 본문을 따른다.
- 2026-10-30 사용자 결정(Issue #90 본문): 첫 질문 세트는 H05 v2(`specs/QK-BOT-001-discord-ask/measurement/h05-question-set-v2.md`)와 합성 식별자 질문(원형·일부·문장형)이다.
  골든셋 v0(WBS 0.7)는 나오면 다음 버전으로 더한다.
- 2026-10-30 사실(작성 세션 확인):
  - H05 v2는 11문항(있음 8, 없음 3)이다. Recall@5·MRR은 근거 문서가 있는 8문항에서만 계산되므로 표본이 작다. 리포트에 표본 수를 함께 적는다.
  - 로드맵이 골든셋 유형·형식의 근거로 가리키는 `evaluation.md`(1절)는 저장소에 없다. 골든셋 파일 형식은 이 명세에서 정한다.
  - 골든셋 v0 수집 페이지(WBS 0.7)는 저장소 스키마가 없어 임시 유형 값(`code`·`doc`·`meeting`·`synthesis`·`no_answer`·`unknown`)을 썼다. 형식을 정할 때 이 값과 맞출지는 사람이 정한다.
  - ADR-010 문서는 아직 없다(QK-RET-001 spec 363행). 후보와 비교 기준은 QK-RET-001 research R-11, 평가용 색인 준비는 `qk-dev eval-index prepare`(FR-029)에 있다.
  - Phase 1 게이트 `0.G`는 미완료지만 다른 Phase 1 명세와 같이 진행한다(작성 세션 해석, 사람 확인 대상).
- 2026-10-30 사용자 결정: 이 TASK.md 초안을 승인했다("승인"). 다음 단계는 `/speckit-specify`다.
- 2026-10-30 사실: `/speckit-specify`로 `specs/QK-EVL-001-retrieval-eval/spec.md`와 `checklists/requirements.md`를 썼다.
  spec 독립 검토(작성에 관여하지 않은 별도 서브에이전트, 읽기 전용) 판정은 변경 요청이다(높음 1, 중간 6, 낮음 5).
  다음 근거는 작성 세션이 코드로 다시 확인했다. 하이브리드는 질의 임베딩이 실패하면 키워드 결과만 낸다(`retrieval/service.py:157-161`). 질의 임베딩은 캐시를 쓰지 않는다(`embedding/service.py:156`).
  벡터 색인은 HNSW다(`migrations/0001_initial_schema.sql:48`). 질의 임베딩은 색인 예산과 관계없이 처리된다(QK-EMB-001 FR-019). Issue #90 "의존성·막힘"에 후보 C와 캐시 원본 DB가 미결정으로 있다.
  라벨 기준 커밋 전체 SHA는 QK-RET-001 research 123행에 있다.
- 2026-10-30 사용자 결정(spec 검토 반영): ADR-010 후보 C는 평가용 DB에서만 만들어 잰다. 임베딩 캐시는 로컬 개발 DB에서 먼저 복사한다. 실행 전 잔여량은 운영 사용 장부(임베딩·생성)를 읽기 전용으로 조회한다.
- 2026-10-30 사실: 나머지 지적은 작성 세션이 다음처럼 반영했다(사람 결정 필요 없음으로 판단, 사람 확인 대상).
  - 1: 한 실행 안에서 질의 벡터를 방식·대상 사이에 다시 쓰고(FR-014), 후보 비교는 공통 질문 집합으로 하며(FR-025), 생략 사유·낱말 수를 남긴다. 벡터 전용은 대조군이다.
  - 2: 예상 호출 수는 재시도 포함 상한, `provider_quota`는 실행 미완료(FR-013, FR-021). 4: 라벨 기준 커밋 40자 SHA와 실행 전 일치 검사(FR-008, FR-012).
  - 5: 평균 결과 수는 키워드 전용만, 상한 도달 비율과 식별자 세트 Precision@5 추가(FR-017). 6: 문장형 근거 문서 정의, PascalCase·약어·숫자 경계 추가, 확정 세트만 결론에 사용(US2).
  - 7: 리포트 계약 절과 ADR-010 판단 규칙을 측정 전에 별도 커밋으로 고정(FR-026). 8: 골든 세트 새 ID `qk-evl-001-golden`. 9: 세트에 자료원 목록.
  - 10~12: 비용 근거·출처 표기 정정, 외부 호출 정의, SC-008 구조 검사, 색인 시점·검색 필터·결정 기록 양식 추가.
- 2026-10-31 사실: 같은 검토자의 최종 확인 판정은 경미한 변경 요청이다(높음 0, 중간 2, 낮음 5). 지난 지적 1~12 가운데 10건 해소, 2·6 부분 해소.
  다음 근거는 작성 세션이 코드로 다시 확인했다. 인덱스 버전 재료에 토크나이저가 없다(`sync/keys.py:22-30`). 운영 DB는 Bastion 터널로만 닿는다(`docs/ops/oci-production-store.md` 42행).
  평가 대상은 로컬 컨테이너(기본 포트 54322, `devtools/db.py`)다. `no_results`는 실패가 아니다(`domain/retrieval.py:230-231`).
  작성 세션이 다음처럼 반영했다(사람 확인 대상).
  - N1: 후보는 인덱스 버전·색인 쪽 규칙·DB에서 읽은 토크나이저 셋으로 가리고 검색 요약의 규칙 표시는 쓰지 않는다(FR-012). C를 운영에 반영할 때 이를 가릴 식별자가 필요하다는 점을 ADR-010에 남기고 방법은 사람 결정으로 둔다(FR-030).
  - N2: 실행 위치는 작업자 PC, 평가 대상은 로컬 컨테이너 주소와 DB 이름(`DATABASE_URL` 안 씀), 장부는 별도 접속 정보와 읽기 전용 트랜잭션, 사용량은 지정한 평가 대상 하나에만 기록, 대상 검사를 장부 읽기보다 먼저(FR-012, FR-013, FR-022, Assumptions).
  - N3: 막는 기준은 일일 무료 한도 잔여량(임베딩+생성 차감), 예비분은 참고. 평가 사용량이 운영 장부에 안 보이는 점을 리포트 비용 절에 적는다. N4: 공통 질문 집합에 `no_results` 포함(FR-025).
  - N5: 선택 항목 "라벨 근거 낱말"(FR-002, US2-4). N6: 호출 수·Neurons는 실제 제공자 호출로 세고, 모든 대상의 임베딩 모델·차원 일치 검사(FR-012, FR-014). 11의 남은 점: 시험 세트 질문 문장을 문서 위치와 겹치지 않게(SC-008).
  - N7: 이 파일의 완료 조건을 A·B·C로, 캐시 비용 문장을 조건부로, 후보 C 계약 위치와 질의 벡터 재사용의 코드 변경 기록 방법을 Scope에 적었다.
  N1~N7 반영분은 다시 검토받지 않았다.
- 2026-10-31 사용자 결정: `spec.md`를 승인했다("승인"). 사람 확인 대상으로 남긴 기본값(유형 값 `unknown` 제외, Recall@5 정의, `0.G` 미완료 상태 진행)도 이 승인에 포함된 것으로 본다.
  다음 단계는 `/speckit-plan`이다.
- 2026-10-31 사실: `/speckit-plan`으로 `plan.md`, `research.md`(R-01~R-15), `data-model.md`, `contracts/`(question-set, run-record, cli), `quickstart.md`를 썼다.
  plan 독립 검토(작성에 관여하지 않은 별도 서브에이전트, 읽기 전용) 판정은 변경 요청이다(중간 4, 낮음 8). 작성 세션이 지적 근거를 코드로 다시 확인하고 반영했다(plan.md "Phase 0·1 산출물").
  L2 가운데 `CountingProvider` 제거는 받지 않았다. 호출이 나간 뒤 인증 오류가 나면 `RunSummary`가 사라진다(`embedding/service.py:276`, `:283`). 반영분은 다시 검토받지 않았다.
  - 질의 벡터 재사용은 `Embedder` 감싸기로 하고 QK-RET-001 검색 경로 코드(`retrieval/`)는 바꾸지 않는다(R-06). Scope 메모의 "검색 경로 코드 변경"은 해당 없다.
  - 예상 Neurons: 두 세트 한 번씩 상한 약 8.3, 후보 C 준비 0(R-15).
  - spec과 다른 점 세 건을 사람 확인 대상으로 남겼다(plan.md "spec과 다른 점"). FR-002 `label_terms` 확장(승인하면 spec 문구 정정), `EmbedError` 실행 멈춤, 알 수 없는 규칙·토크나이저 거부.
- 2026-10-31 사용자 결정: plan 산출물을 승인했다("승인"). spec과 다른 점 세 건도 이 승인에 포함된 것으로 본다.
  그에 따라 spec FR-002와 US2-4의 라벨 근거 낱말 문구를 식별자 세트 질문 전체로 고쳤다. 다음 단계는 `/speckit-tasks`다.
- 2026-10-31 사실: `/speckit-tasks`로 `tasks.md`(T001~T045, 사람 단계 H00~H08, Scope 갱신안)를 썼다. tasks 독립 검토(작성에 관여하지 않은 별도 서브에이전트, 읽기 전용) 판정은 변경 요청이다(높음 0, 중간 5, 낮음 9).
  빠진 FR·SC는 없다는 판정이다. 작성 세션이 지적 근거를 코드로 다시 확인하고 모두 반영했다. 반영분은 다시 검토받지 않았다.
  - 확인한 근거: `usage_unavailable`이 항목 실패와 묶음 실패 둘 다에 있다(`domain/embedding.py:56`, `:64`). 기존 시험 시드의 인덱스 버전은 `v1`이다(`tests/localdb/store/builders.py:18`).
    `upsert_artifact`는 `source_name`·`location`을 채우지 않는다(`adapters/postgres/store.py:214-232`). `connection.py`가 `devtools.db`를 가져온다(10행). `connect()`의 기본값은 autocommit이다(52행).
    `eval-index`는 인자를 보기 전에 설정 점검을 한다(`devtools/db.py:189-196`). `--from-url-env`의 기본값은 `DATABASE_URL`이다(144행).
  - 반영: 멈춤 판정은 `ReusingEmbedder.outcome`으로 한다. 로컬 DB 시험 대상은 실제 동기화 경로로 시험마다 만든다. 로컬 DB 실행 시험에는 가짜 장부와 운영 아닌 자리표시 접속 정보를 넣는다.
    순서는 H04 → T039 → H05(n·m) → 계약 고정 커밋이다. H01에서 캐시 원본이 로컬인지 확인한다. 장부 연결은 `autocommit=False`로 연다. 경계 예외 `TargetUnavailable`·`LedgerUnavailable`을 둔다.
    `target_not_eval` 사유를 더했다. 그 밖에 중첩 키 검사, 순환 가져오기 회피, 설정 점검 전 인자 검사, 회귀 diff 범위, SC-011 Neurons 확인을 넣었다.
  - 같이 고친 plan 산출물: contracts/cli.md 2절(실행 전 검사 사유 이름, `--sources`·`--exceptions`, 종료 2 사례), contracts/run-record.md 1절(`source_url`이 문서 표에 없으면 `index_version_changed`),
    quickstart.md·plan.md의 로컬 DB 시험 파일 이름(단위 시험 `test_prechecks.py`와 겹쳐 바꿨다)
- 2026-10-31 사용자 결정: `tasks.md`를 승인했다("승인"). Scope 갱신안도 이 승인에 포함된 것으로 보고 위 Scope·Validation·Objective를 고쳤다. 구현을 시작한다.
- 2026-10-31 사실: 코드 단계(T001~T016, T019~T038, T043, T044)를 구현했다. 외부 호출 0, 운영 DB 접근 0이다. 기록은 `tasks.md` "실행 기록"에 있다.
  - 골든 세트 v1(T017)은 파일과 대조 시험만 만들었고 `confirmed = false`다. 확정(H00), 식별자 세트(T018, H01 뒤), 리포트·ADR-010(T039~T042)은 사람 단계와 함께 남았다.
  - 구현 독립 검토(작성에 관여하지 않은 별도 서브에이전트, 읽기 전용, 시험 직접 실행) 판정은 경미한 변경 요청이다(높음 0, 중간 2, 낮음 7). 안전 항목(대상·장부·사용량·금지 경로·경계)은 문제가 없었다.
    작성 세션이 지적마다 시험을 먼저 쓰고 모두 반영했다(지적별 실패 확인은 하지 않음, `tasks.md` 실행 기록). 반영분은 다시 검토받지 않았다. 커밋하지 않았다.
