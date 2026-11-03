# Task Contract: QK-EVL-001 측정 단계와 골든 세트 v2 (WBS 1.12)

> Generated at: `2026-11-03`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-124` / https://tkv123.atlassian.net/browse/SCRUM-124 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: `QK-EVL-001` / `specs/QK-EVL-001-retrieval-eval/spec.md`(Approved 2026-10-31). 구현 순서는 같은 디렉터리의 `tasks.md`(승인 2026-10-31, 골든 세트 v2 작업 T046~T048·H09는 추가 승인 대상)
- 팀 스프린트 ID: `QELLO-S2026-W44`(Jira SCRUM-124 본문 값, 2026-11-03 확인)
- GitHub Issue: `#90`(열림)
- Branch: `docs/SCRUM-124-gh-90-retrieval-eval-measurement`
- Base branch: `main`. 2026-11-03 `origin/main` `69c04ea`(#95 병합)에서 분기했다. 코드 단계는 #91로 병합됐고, 그 브랜치의 QK-EVL-001 계약과 `main`의 QK-STO-002 계약은 git 이력에 남긴다.

## Objective

- 이번 단계: QK-EVL-001 `tasks.md`의 남은 측정 단계(T017 확정·T018·T039~T042·T045, 사람 단계 H00~H08)를 끝낸다. 코드는 고치지 않는다.
- 골든셋 v0(WBS 0.7) 최종본을 입력으로 골든 세트 v2를 만들어 측정에 넣는다. spec이 정한 대로다(spec 32행 "골든셋 v0가 나오면 다음 버전으로 더한다", 345행 "다음 버전에서 다시 잰다").
  최종본은 팀 질문 50문항이다(2026-11-03). v2 작업은 승인된 tasks.md에 없어서 T046~T048·H09로 더하고 승인을 받은 뒤 한다.
- 목적: 1.G 완료 조건 가운데 "첫 검색 평가 리포트(Recall@5, MRR, 벡터·키워드·하이브리드 비교)"와 "ADR-010 Proposed"를 채운다. ADR-010 Status 결정은 사람이 한다.

## Scope

- `TASK.md`(이 파일)
- `specs/QK-EVL-001-retrieval-eval/tasks.md`: 골든 세트 v2 작업(T046~T048, 사람 단계 H09) 추가, 체크 표시와 "실행 기록". 그 밖의 명세 문서(spec FR·SC, plan 산출물)는 바꾸지 않는다
- 골든 세트(`eval/question_sets/qk-evl-001-golden/`):
  - `v1.toml` 확정 표시(H00, `confirmed = true`, `confirmed_on`). 질문·근거는 바꾸지 않는다
  - `v2.toml`(T046): v1 11문항에 v0 문항 가운데 근거 문서가 `dnd-backend-docs`(라벨 기준 커밋 `6aeccd039b825dcd7a2b6c046a34ef72089a1f78`)에 있는 문항과 `no_answer` 문항을 더한다.
    수집 페이지 DB에 있는 24문항 기준 9문항이다(백엔드 근거 7: `qmv26kb2qzu4q`·`qmv26yx2nf6zx`·`qmv3nxemzw984`·`qmvap800bkpxt`·`qmvapdxvo621o`·`qmvb1yugb6wda`·`qmvcgtyx83h8s`, `no_answer` 2: `qmv272r8raqgk`·`qmvap6omullmy`). `cand-` 26문항도 같은 기준으로 고른다
  - `labeling.md` 갱신: v2 라벨 기준, v0에서 뺀 문항과 이유(Confluence 근거는 QK-ING-003 색인 뒤 다음 버전), 핵심 사실 출처
  - `tests/unit/evaluation/test_golden_v2.py`(T047): v2가 v1 11문항을 글자 그대로 담고 `check_question_set`을 통과하는지 본다. 세트를 읽는 시험이라 세트와 같은 커밋에 둔다(`test_golden_v1.py`와 같은 방식)
- 식별자 세트: `eval/question_sets/qk-evl-001-identifiers/`(`v1.toml`, `labeling.md`), T018·H04
- 측정: `specs/QK-EVL-001-retrieval-eval/measurement/`(`runs/<실행 ID>.json`, `retrieval-eval-report.md`), T039·T040·T042
- 결정 기록: `docs/sdd/decisions/ADR-010-keyword-search-text.md`(Status Proposed), T041

## Explicit exclusions

- `eval/golden/v0.jsonl` 등 WBS 0.7 산출물. QK-EVL-001 spec의 범위 밖이다(spec 348행 "골든셋 질문 수집(WBS 0.7)"). 별도 작업으로 한다
- 평가 코드(`src/`)와 기존 시험 기대값 변경. 측정 중 결함이 나오면 멈추고 별도 작업으로 나눈다
- 골든셋 v0 문장·유형 수정. 2026-11-03 최종본을 그대로 옮긴다. 확정한 세트 파일(v1, 확정 뒤 v2)도 고치지 않고, 바꿔야 하면 버전을 올려 평가 코드·결과와 다른 커밋에 사유를 남긴다(AGENTS.md 3.4)
- Confluence 근거 문항의 검색 측정(Confluence 색인은 QK-ING-003, Phase 2). 답변 정답 라벨(QK-EVL-002)
- 운영 키워드 규칙·운영 인덱스 버전 교체, `RetrievalSettings` 기본값 변경. 수치와 조정 제안까지만 리포트에 남긴다
- 운영 DB 쓰기와 운영 마이그레이션. 평가 대상은 로컬 평가용 DB(`qk_eval_*`)뿐이다
- 수집 페이지(Artifact) DB 쓰기. 읽기만 한다. 예외: 2026-11-03 사용자 결정으로 v0 최종본 50문항 반영(`cand-` 26문항 추가, 수정 22문항의 내보낼 문장·유형, 페이지 주인의 진행 개수)만 한다
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, ADR-010 밖의 결정 기록, 다른 명세 문서, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정
- `.env`·`.env.*` 읽기. 설정은 항목 이름으로만 가리킨다
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문, 민감한 질의 원문, 사람 이름은 기록하지 않는다. v0 질문에 사람을 가리키는 표현이 있으면 역할로 바꾸지 않고 멈춰 사람에게 묻는다

## Data and cost impact

- 새로 읽는 자료원: 없음. `dnd-backend-docs`를 고정 커밋 `6aeccd0`으로 다시 읽어 로컬 평가용 DB에 색인한다(GitHub 읽기 전용, H01·H02).
  골든셋 v0 원문은 수집 페이지 DB를 읽기 전용으로 읽는다
- 외부 API로 보내는 데이터: 평가 질문 문장만 Workers AI 임베딩으로 보낸다(H06). 생성 호출 0건
- 예상 임베딩·생성 호출량과 무료 한도 대비:
  - H01~H03 평가용 DB 준비: 캐시로 처리되면 0 Neurons. 모자라면 후보당 약 900 Neurons가 들 수 있어 준비 명령이 멈추고(종료 4) 사람이 정한다
  - H06 질의 임베딩: research R-15의 상한 약 8.3 Neurons(골든 8문항 + 식별자 80문항 가정)에서 골든 v2 문항만큼 늘어난다.
    골든 v2를 최대 45문항으로 잡으면 상한 약 13 Neurons이고, 일일 무료 할당 10,000 Neurons의 0.2% 아래다. 실행 명령의 미리 보기(종료 4)로 실제 값을 확인한 뒤 사람이 `--max-neurons`를 정한다
- 운영 DB 읽기: H06 실행 전 잔여량 확인을 위해 운영 사용 장부를 읽기 전용 트랜잭션으로 조회한다(Bastion 터널). 실행 때 사람이 허락한다
- 인덱스 버전 변경: 운영 없음. 로컬 평가용 DB에만 후보 A(`kw-index-baseline-v1`), B(`kw-index-idsplit-v1`), C(토크나이저 교체) 색인이 생긴다

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `TASK.md`, `specs/QK-EVL-001-retrieval-eval/tasks.md` | tkv00 | 사람 리뷰(T046~T048·H09 추가 승인) |
| `eval/question_sets/**`, `tests/unit/evaluation/test_golden_v2.py` | tkv00 | 사람 확정(H00·H04·H09), 평가 결과와 커밋 분리 확인 |
| `specs/QK-EVL-001-retrieval-eval/measurement/**` | tkv00 | 독립 검토 에이전트(리포트 대조 T042), 사람 리뷰 |
| `docs/sdd/decisions/ADR-010-keyword-search-text.md` | tkv00 | 사람 승인(H08) |

## Existing user-owned changes

- 2026-11-03 `origin/main`(`69c04ea`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음
- 저장소 밖: 골든셋 v0 수정 초안(`~/Downloads/golden-v0-revision-draft.md`, 사용자 작성). 저장소에 복사하지 않고 v2 작성의 입력으로만 쓴다

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
uv run qk-dev eval check eval/question_sets/qk-evl-001-golden/v2.toml --target <H01 데이터베이스>
uv run qk-dev eval check eval/question_sets/qk-evl-001-identifiers/v1.toml --target <H01 데이터베이스>
```

외부 호출 시험(`-m external`)은 넣지 않는다. 측정 단계의 실행 기록·리포트 대조는 tasks T042다.
`python`이 없는 환경에서는 `uv run python scripts/preflight.py`로 실행한다.

## Completion criteria

- 골든 세트 v1·v2와 식별자 세트 v1이 확정되고, v2와 식별자 세트가 `qk-dev eval check`를 평가 대상에 대해 통과한다 — 확정 커밋, 검사 출력
- 같은 질문 세트·고정 커밋·임베딩 모델로 세 검색 방식과 ADR-010 후보 A·B·C의 Recall@5·MRR이 표본 수와 함께 리포트에 남는다. 목표에 못 미쳐도 기록한다 — 리포트, 실행 기록(운영 DB 쓰기 0건)
- ADR-010이 Status Proposed로 리포트 수치를 그대로 인용한다. Status 결정은 사람이 한다

## Decisions

- 2026-10-30~31 QK-EVL-001 명세·plan·tasks 결정과 코드 단계 기록은 `feat/SCRUM-124-gh-90-retrieval-eval`의 `TASK.md`(#91 병합 커밋 `c4ca593`)와 `tasks.md` "실행 기록"에 있다.
- 2026-11-03 사용자 결정: 보내 준 골든셋 v0 수정 초안이 최종본이고 이를 반영한다. 초안의 "바로 정하지 못한 점" 5건도 적힌 대로 간다.
- 2026-11-03 사실(작성 세션 확인):
  - 수집 페이지 DB에는 팀 질문 24개가 있고 모두 채택(`accepted`)이다. 초안이 22개를 고쳤고 2개(`qmv26zrvzaicu`, `qmv270uanha2v`)는 그대로다.
  - 나머지 `cand-` 26문항의 문장·유형은 수집 페이지 DB, 페이지 본문, 저장소에서 찾지 못했다. v2는 이 원문을 받아야 끝난다(BLOCKED 항목).
  - DB에 있는 24문항의 백엔드 근거 문서 7개(FCM ADR 0008, README 테스트 서버 배포, 인증 분리 ADR 0006, 요청 로깅 설계, 방향 소통 ERD, `error-codes.md`, `AUTH_DESIGN.md`)는 라벨 기준 커밋 `6aeccd0`에 모두 있다(GitHub 읽기 전용 조회). 백엔드 저장소 `main`은 그 뒤로 움직였지만 라벨 기준 커밋은 그대로 둔다.
  - 질문 세트 형식의 `type`은 `code`·`doc`·`meeting`·`synthesis`·`no_answer`이고 `unknown`은 거부된다. 최종본은 `unknown`이 0개라 그대로 옮길 수 있다.
  - 머리 정보 `origin`은 원본 하나만 담고 저장소 경로를 요구한다. v2는 H05 v2와 v0 두 곳에서 오고 v0 원본은 저장소에 없어서 `origin`을 두지 않고 `labeling.md`에 두 출처를 적는다.
- 2026-11-03 사용자 결정: 첫 TASK.md 초안을 승인했다("승인"). 사람 확인 대상 4건(WBS 0.7 산출물 포함, v1 확정·v2 주 세트, 커밋 순서, 측정 PR 하나)과 스프린트 ID `QELLO-S2026-W45`도 포함했다. 그 판(`10e51ae`)이 git 이력에 있다.
- 2026-11-03 정정: 첫 판은 spec 범위 밖인 WBS 0.7 산출물(`eval/golden/v0.jsonl`)을 Scope에 넣었고, 승인된 tasks.md에 없는 v2 작업을 tasks 추가 없이 진행하려 했다. 작성 세션이 승인받을 때 이를 알리지 않았다.
  사용자 결정("명세 범위로 고치기"): v0.jsonl은 이 작업에서 빼서 별도로 한다. v2는 남기고 tasks.md에 T046~T048·H09를 더해 승인받은 뒤 진행한다. `test_golden_v2.py`는 v0.jsonl과 대조하지 않는다.
- 사람 확인 대상(작성 세션 제안, 위 정정 반영):
  - v1은 확정만 하고 그대로 둔다. 측정과 리포트의 주 세트는 v2이고, v1 수치는 v2의 부분 집합으로 함께 적는다.
  - 커밋 순서: 이 계약 정정과 tasks.md 추가 → v1 확정 → v2와 `test_golden_v2.py` → v2 확정 → 식별자 세트 초안 → 확정 → 리포트 계약 고정(T039·H05) → 실행 기록·리포트 → ADR-010. 평가 세트와 평가 결과는 다른 커밋이다.
  - 측정 PR은 하나로 낸다.
- 2026-11-03 사용자 결정: 정정한 TASK.md와 tasks.md Phase 9(T046~T048, H09)를 승인했다("승인하고 커밋"). 위 사람 확인 대상 3건도 포함한다. Phase 9 추가분은 별도 에이전트 검토를 받지 않았다.
- 2026-11-03 정정: 스프린트 ID `W45`는 작성 세션이 날짜로 추정한 값이었다. Jira SCRUM-124(읽기 전용 조회)의 `QELLO-S2026-W44`와 달라 사용자 결정("W44로 맞추기")으로 W44로 고쳤다.
  같은 조회에서 SCRUM-124 상태는 "해야 할 일"이었다. Jira 쓰기는 하지 않았다.
- 2026-11-03 사용자 결정("DB 반영 승인"): 골든셋 v0 최종본 50문항을 수집 페이지 DB에 반영한다. 최종 목록은 사용자가 준 50문항 표(질문·유형, 근거 없음)이고 수정 초안과 문장·유형 분포가 같다.
  `cand-` 26문항은 페이지 주인 문서에 채택 상태로 넣고, 수정 22문항은 원래 문장을 두고 검토 기록에 내보낼 문장·유형을 넣는다. 쓰기는 읽은 버전에 고정하고 다시 읽어 대조한다.
  `cand-` 문항의 근거 문서는 이 표에 없어 v2(T046) 전에 정한다.
