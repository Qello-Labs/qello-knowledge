# Task Contract: QK-EVL-002 답변 평가·판정 모델·사람 표본 검토·생성 모델 비교 (WBS 2.5)

> Generated at: `2026-11-01`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.
>
## Work gate

- Jira 이슈: `SCRUM-126` / https://tkv123.atlassian.net/browse/SCRUM-126 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: `QK-EVL-002` / `specs/QK-EVL-002-answer-eval/spec.md`(Approved 2026-11-01)
- 팀 스프린트 ID: `QELLO-S2026-W44`
- GitHub Issue: `#93`
- Branch: `feat/SCRUM-126-gh-93-answer-eval`
- Base branch: `main`. 2026-11-01 `origin/main` `c4ca593`(#91 병합)에서 분기했다. `main`의 QK-EVL-001 계약은 git 이력에 남긴다. QK-EVL-001 측정 단계(#90)는 그 브랜치에서 계속한다.

## Objective

- 이번 단계: QK-EVL-002 `spec.md`를 쓰고 별도 에이전트 검토를 거쳐 사람 승인을 받는다. 외부 호출은 0건이다. plan·tasks·구현은 `1.G` 뒤에 시작한다.
- 목적: 2.G 완료 조건 가운데 "골든셋 답변 평가 리포트"와 "생성 모델 확정(ADR-009)"을 채울 평가 방법을 정한다. 파일럿(2.6)의 선행 작업이다.

## Scope

- `specs/QK-EVL-002-answer-eval/`: `spec.md`, `checklists/requirements.md`
- `TASK.md`(이 파일)
- spec이 정할 동작:
  - QK-EVL-001 질문 세트(`specs/QK-EVL-001-retrieval-eval/contracts/question-set.md`)의 `facts`를 기준으로 질문마다 검색과 생성을 돌려 답변 결과를 기록한다
  - 지표: 충실성, 인용 정확도, 답변 관련성, 확인 불가 응답 정확도, 출처 확인 안 됨 비율(QK-GEN-001 FR-015 재결정 근거)
  - 판정: 코드·판정 모델·사람 표본 검토의 역할, 루브릭, 사람 검토와의 일치율 기록(`templates/eval-report.md` 5절)
  - 생성 모델·프롬프트 비교: 후보 범위, 비교 조건, ADR-009를 확정하거나 다시 여는 판단 규칙. 프롬프트는 QK-GEN-001이 넘긴 `gen-p1`·`gen-base`를 포함한다
  - 질의 로그 내보내기를 골든셋 후보로 옮기는 절차와 개인 정보·비공개 문서 정리(QK-OBS-001 plan이 넘긴 일)
- 구현 범위는 tasks 승인 때 이 파일에 적는다.

## Explicit exclusions

- 구현, 측정, 외부 API 호출, 운영 DB 접근, 색인 실행
- 골든셋 질문 수집(WBS 0.7). 기존 질문 세트의 질문·핵심 사실·근거 문서 수정(AGENTS.md 3.4)
- QK-EVL-001 계약(`contracts/question-set.md`, `contracts/run-record.md`)과 검색 평가 변경
- 프롬프트, 생성 모델 기본값, `RetrievalSettings` 변경. ADR-009의 Status 변경(사람이 결정한다)
- 인덱스 버전 평가 게이트(QK-STO-002), 코드·Confluence 자료원 켜기
- 다른 명세 문서 수정. `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, 결정 기록, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정
- `.env`·`.env.*` 읽기. 설정은 항목 이름으로만 가리킨다
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문, 민감한 질의 원문, 사람 이름은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 없음
- 외부 API로 보내는 데이터: 명세 단계 0건
- 예상 임베딩·생성 호출량과 무료 한도 대비: 명세 단계 0 Neurons. 측정 단계 예상치는 plan에 적고 실행 전에 보고한다(AGENTS.md 3.5).
  참고로 H05 v2 측정(`specs/QK-BOT-001-discord-ask/measurement/h05-v2-eval.md`)에서 11문항 1회 생성이 약 220 Neurons(일일 무료 한도 10,000)였다. 후보·프롬프트·반복 횟수와 판정 호출만큼 늘어난다
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-EVL-002-answer-eval/`, `TASK.md` | 확인 필요(`#93` 담당자 미지정) | 독립 검토 에이전트, 사람 리뷰 |

## Existing user-owned changes

- 2026-11-01 `origin/main`(`c4ca593`)에서 브랜치 생성 시 `git status --short` 결과: `?? apps/`, `?? package-lock.json`. 이 작업과 무관한 추적되지 않은 파일이다. 건드리거나 커밋하지 않는다.

## Validation

명세 단계:

```bash
python scripts/preflight.py
git diff --check
```

구현 단계의 검증은 tasks 승인 때 AGENTS.md 7절 기본 검증과 평가 실행 결과로 고친다. `python`이 없는 환경에서는 `uv run python scripts/preflight.py`로 실행한다.

## Completion criteria

- `TASK.md`가 사람 승인을 받는다 — 이 파일의 Decisions
- `spec.md`가 별도 에이전트 검토를 반영한 뒤 사람 리뷰로 승인된다 — 검토 기록, 이 파일의 Decisions
- spec이 QK-EVL-001 질문 세트 형식을 바꾸지 않고 입력으로 쓰고, 판정 방식과 ADR-009 판단 규칙을 요구사항이나 사람 결정 항목으로 담는다 — spec 본문, 검토 기록

## Decisions

- 2026-11-01 사용자 결정: QK-EVL-002 이슈와 이 TASK.md 초안을 만든다("EVL-002 이슈랑 TASK.md 초안 만들어줘"). `#93`을 열었고 Jira 하위 작업 `SCRUM-126`이 자동으로 생겼다. TASK.md 승인은 아직 받지 않았다.
- 2026-11-01 사실(작성 세션 확인):
  - 선행 QK-GEN-001(`#53`)은 닫혔다. QK-EVL-001(`#90`)은 코드 단계가 병합됐고(`#91`) 측정 단계가 남아 열려 있다.
  - 골든 세트 v1(`eval/question_sets/qk-evl-001-golden/v1.toml`)은 11문항(`doc` 8, `no_answer` 3)이고 11문항 모두 `facts`가 있으며 `confirmed = false`다. 2.G가 요구하는 코드·회의·종합 유형이 없다.
  - 백로그의 FR-EVL-03과 `evaluation.md`는 저장소에 원문이 없다. 뜻을 추측해 대응시키지 않는다.
  - ADR-009는 Proposed이고 근거는 모델별 5문항 1회 측정이다. 재검토 조건에 이 평가가 들어 있다(ADR-009 Revisit conditions).
  - 코드·Confluence 자료원은 `enabled = false`라 지금 색인된 문서로는 코드·회의 유형을 평가할 수 없다.
- 2026-11-01 사용자 결정: 이 TASK.md 초안을 승인했다("승인"). `1.G` 전에는 명세 단계만 진행한다는 제안도 이 승인에 포함된 것으로 본다. 다음 단계는 `/speckit-specify`다.
- 아직 답을 받지 못한 항목: Owner, `#93`의 주간 계획 합의 체크.
- 2026-11-01 사실: `/speckit-specify`로 `specs/QK-EVL-002-answer-eval/spec.md`와 `checklists/requirements.md`를 썼다.
- 2026-11-01 사용자 결정(spec 질문 세 건): 내용 지표는 Workers AI 판정 모델과 사람 표본으로 판정한다. 비교 모델은 qwen3-30b-a3b와 granite-4.0-h-micro다(조합 3개). 첫 측정은 확정된 골든 세트 v1로 하고 WBS 0.7 뒤 다음 버전으로 다시 잰다.
- 2026-11-01 사실: spec 독립 검토(작성에 관여하지 않은 별도 서브에이전트, 읽기 전용) 판정은 변경 요청이다(높음 5, 중간 12, 낮음 6). 작성 세션이 주요 근거를 코드로 다시 확인했다.
  `gen-p1`과 `gen-base`는 시스템 프롬프트와 표시 규칙이 다르다(`generation/prompts.py`). `GenerationSettings`는 qwen3 계열이 아니면 거부한다(`domain/generation.py:75`). `model_unconfirmable_parts`의 상태는 확인 불가다(`generation/service.py:253`). 잔여량은 운영 장부만으로 계산한다(`evaluation/prechecks.py`). 질의 임베딩 실패는 하이브리드에서 생략이 된다(`retrieval/service.py:157`).
  지적을 spec 전체에 반영했고 FR을 FR-001~FR-036으로 다시 매겼다. 반영분은 다시 검토받지 않았다.
- 2026-11-01 사용자 결정(독립 검토의 사람 결정 네 건): 큰 세트는 날짜별로 이어 돌린다. 판정 대상 60건 이하는 사람이 전수로 읽는다. 표준 문구가 아닌 거절은 코드 지표에서 실패로 세고 판정 항목으로 따로 보인다. 파일럿 질문은 유형과 의도만 옮겨 사람이 새 문장으로 쓴다.
- 2026-11-01 사용자 결정: `spec.md`를 승인했다("승인"). 재검토 없이 승인했으므로 독립 검토 반영분은 다시 검토받지 않았다. 사람 확인 대상으로 남긴 초기값(핵심 사실을 하나도 담지 않은 답의 실패 처리, 표본 25%·20건, 주입 문항 I1 5회)도 이 승인에 포함된 것으로 본다.
- 측정 전 계약에서 사람이 정할 것: 지표별 목표값, 일치 기준, 항목별 보정 기준, 운영 몫 여유분, 동률 폭.
- 다음 단계: `1.G` 뒤 `/speckit-plan`. 이 명세 단계의 완료 조건은 커밋과 PR 리뷰로 닫는다.
