# Decision Record: ADR-019 첫 색인 자료원 — 백엔드 저장소 Markdown 문서

> Created at: `2026-10-20`
> Jira 이슈: `https://tkv123.atlassian.net/browse/SCRUM-100`
> 기능명세서 ID: `QK-ING-002`
> Status: Accepted

## Context

QK-ING-002(WBS 1.5)로 GitHub 저장소 파일 수집기를 만들었고, 첫 자료원 `dnd-backend-docs`를 `config/sources.toml`에 비활성으로 등록했다.
AGENTS.md 3.1은 새 자료원을 추가할 때 데이터 처리 정책(학습 사용 여부, 보존 기간)을 확인하고 결정 기록을 남기라고 한다.
`github_repo_files` 종류 등록(QK-ING-001)만으로는 이 의무가 없어지지 않으므로, 활성화 전에 이 기록이 필요하다(QK-ING-002 research R-16).

Phase 1 목표는 저장소 Markdown 문서만으로 Discord에서 출처가 붙은 답을 받는 것이다(로드맵 1절 원칙 1, 3절 Phase 1). 색인할 저장소 문서를 정해야 한다.

## Decision

`dnd-side-project/dnd-15th-2-backend`(공개 저장소)의 `main` 브랜치 Markdown 문서 중 인벤토리 1.2절 "포함" 범주를 첫 색인 자료원으로 추가하고,
개인 정보 확인 기록(`config/source_reviews/dnd-backend-docs.toml`)이 승인된 뒤에 활성화한다. 팀원 GitHub 계정 표기가 있는 `docs/harness/ARCHITECTURE.md`는 제외한다.

## Rationale

- 팀의 제품 저장소다. Qello 제품 저장소는 `Qello-Labs`가 아니라 DND 동아리 조직 `dnd-side-project`에 있다(인벤토리 1.1절).
- 공개 저장소라 0.5에서 발급한 읽기 전용 토큰(공개 저장소 읽기, 추가 권한 없음)으로 읽을 수 있고, QK-SEC-001 접근 규칙이 팀 공용으로 판정한다(FR-017, `visibility = public`).
- 팀 질문에 답할 설계 문서가 모여 있다. ADR, 제품 설계·데이터 모델, API 규약, 하네스, 계획·명세 문서가 "포함" 범주다(인벤토리 1.2절).
- 규모가 작다. "포함" 문서는 81개, 1,083 KB다(2026-10-06, `c070ae0` 기준). 전체 색인 1회 임베딩은 약 325 Neurons로 추정한다(ADR-002).
  수집 요청은 한 실행에 약 84회로 추정했고(QK-ING-002 research R-01, 추론), 2026-10-20 측정에서 83회, 73초, 80개 1,083,278바이트였다
  (`docs/sdd/research/github-source-measurement.md`).
- "결정 필요" 범주(테스트 계획·결과, 설계 보고서, 에이전트 설정)와 "제외" 범주(실험 기록)는 넣지 않는다(C-04). 넣으려면 개인 정보 확인 기록을 새로 쓴다.
- 2026-10-20 개인 정보 확인(대상 커밋 `6aeccd0`, 범위 안 81개)에서 `docs/harness/ARCHITECTURE.md` 흐름도에 팀원 GitHub 계정 표기가 나왔다. AGENTS.md 3.1은 계정 정보를
  색인하지 않으므로 그 파일을 제외 패턴으로 옮긴다(2026-10-20 사용자 결정, A안). 색인 범위는 80개다. 원본 문서에서 계정 표기를 역할 이름으로 바꾸면 제외를 풀 수 있다.

## Alternatives considered

| Alternative | Advantages | Disadvantages | Reason not selected |
| --- | --- | --- | --- |
| `Qello-Labs/qello-knowledge`(이 저장소) | 명세·설계 문서가 많다. `config/sources.toml` 주석 예시가 이 저장소다 | 비공개다. 토큰이 공개 저장소 읽기만 있고, QK-SEC-001이 비공개를 미확인으로 막는다(FR-017). 인벤토리가 "대상 아님(이 시스템 자체)"으로 정했다 | 읽을 수 없고 대상도 아니다 |
| `dnd-side-project/dnd-15th-2-android` | 같은 조직의 공개 제품 저장소다 | 설계 문서가 거의 없다(인벤토리 1.3절) | 문서로 답할 질문이 적다. 같은 종류로 나중에 추가할 수 있다 |
| 백엔드 저장소의 "결정 필요" 범주까지 포함 | 테스트 계획·보고서 질문에도 답할 수 있다 | 약 3.7 MB로 세 배 이상 커진다. 개인 정보 여부를 아직 보지 않았다 | 작게 시작하고 측정한 뒤 넓힌다(C-04) |
| ClickUp Docs를 첫 자료원으로 | 회의록·용어집이 있다 | Phase 2 범위다(QK-ING-003). 문서 분류 규칙이 먼저 필요하다 | 로드맵 순서 |

## Evidence

- `docs/sdd/research/inventory.md` 1.1~1.3절(조사 2026-10-06, 기준 커밋 `dnd-15th-2-backend@c070ae0`).
- `docs/sdd/research/tokens.md` 2절: 세분화 토큰, 공개 저장소 읽기만, 저장소 권한 추가 없음, 시간당 5,000회.
- `docs/sdd/research/spike-workers-ai.md` 7절 [C11]: Cloudflare는 Workers AI 입력·출력을 모델 학습에 쓰지 않는다고 밝힌다.
- Cloudflare Workers AI "Data usage": https://developers.cloudflare.com/workers-ai/platform/data-usage/ (조회 2026-10-20, 페이지 갱신일 2026-10-16). 학습 미사용, 일반 추론의 입력·출력 미보관과 예외.
- ADR-002(임베딩 모델 `@cf/baai/bge-m3`, 단가), ADR-008(실행 환경·저장 위치·비용 상한).
- QK-ING-002 `specs/QK-ING-002-github-repo-source/research.md` R-01, R-06, R-12, R-13, R-16.
- 첫 실제 수집 측정 `docs/sdd/research/github-source-measurement.md`(2026-10-20, 커밋 `6aeccd0`).

## Data and cost

- 외부로 전송되는 데이터와 제공자의 학습 사용·보존 정책:
  - 수집: GitHub REST API에 `GET` 요청만 보낸다(`api.github.com`). 보내는 것은 토큰과 요청 경로이고, 받는 것은 공개 저장소 내용이다.
  - 임베딩: QK-SEC-001을 통과한 문서의 청크 본문을 Cloudflare Workers AI로 보낸다(ADR-002, QK-EMB-001). Cloudflare는 Workers AI가 처리한 고객 콘텐츠를
    모델 학습에 쓰지 않는다고 밝힌다. 보존은 일반 추론이면 요청을 처리하고 응답을 돌려준 뒤 입력·출력을 보관하지 않는다고 밝히고, 정해진 보존 일수는 적지 않았다.
    AI Gateway 기록·캐시, 비동기·배치·파일 업로드 기능을 쓰면 그 기능에 필요한 동안 보관할 수 있다(Cloudflare "Data usage", 조회 2026-10-20).
    QK-EMB-001은 동기 REST 호출(`/ai/run`)을 쓰고 AI Gateway를 쓰지 않으므로(tasks T022) 일반 추론 규정에 해당한다고 판단한다(추론). 이 경로가 바뀌면 다시 확인한다.
  - 저장: 청크 본문과 메타데이터는 운영 PostgreSQL에 저장한다(ADR-008. Supabase Free, Oracle Cloud로 바꾸는 제안 있음).
    **ADR-008은 Supabase 데이터 처리 정책을 확인하지 않았다고 적었다.** 저장은 QK-SYN-001부터 일어나므로, QK-SYN-001이 첫 저장을 하기 전에 확인하고
    그 결과를 이 문서나 ADR-008에 적는다(2026-10-20 사용자 결정). 확인 전에는 이 자료원의 청크를 저장하지 않는다.
  - 이 결정으로 활성화되는 범위는 수집과 측정(QK-ING-002)까지다. 임베딩·저장은 QK-EMB-001·QK-SYN-001이 연결될 때 일어난다.
- 무료 한도와 예상 사용량: GitHub 실행당 약 84회(토큰 한도 시간당 5,000회 안, 추론). 전체 색인 1회 약 325 Neurons(일일 무료 10,000의 3.3%, ADR-002 추정).
- 교체 시 영향(재임베딩, 인덱스 버전): 자료원을 추가하는 일은 인덱스 버전 변경이 아니다(AGENTS.md 3.3). 자료원을 끄거나 범위를 줄이면 해당 청크를 내리는 일은 QK-SYN-001이 한다.
  범위를 넓히면 개인 정보 확인 기록을 새로 쓰고, 수집 전 검사가 이를 강제한다(QK-ING-002 FR-020).

## Consequences

### Positive

- Phase 1 전 구간(수집 → 검색 → 답변 → Discord)을 실제 팀 문서로 이을 수 있다.
- 공개 저장소·읽기 전용 토큰이라 토큰이 새도 피해는 호출 한도 소모 정도다(`tokens.md` 2.1).
- 수집 범위와 개인 정보 확인 기록이 저장소에 남아 리뷰로 추적할 수 있다.

### Negative / risks

- 대상 저장소에 에이전트 지시 문서(`AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `TASK.md`)가 있다. 검색된 지시문은 실행하지 않고 데이터로만 다룬다(C-03, AGENTS.md 3.2).
  답변 품질에 영향을 주는지는 Phase 1 평가에서 본다.
- 토큰이 발급자 개인 계정에 묶여 있다. 발급자가 팀을 떠나면 수집이 멈춘다(`tokens.md` T-04).
- 하네스 구조 문서(`docs/harness/ARCHITECTURE.md`)가 검색에서 빠진다. 개인 정보 확인은 형식 있는 값(메일·전화번호·`@` 표기) 자동 검사와 사람의 열람에 기대므로,
  본문 속 사람 이름처럼 형식 없는 개인 정보를 놓칠 수 있다.
- 저장소가 비공개로 바뀌면 다음 실행부터 미확인으로 막히고, 이미 저장된 청크는 QK-SYN-001이 내려야 한다.
- 저장소 제공자의 데이터 처리 정책이 아직 확인되지 않았다(위 Data and cost). Workers AI 보존은 일반 추론 규정에 기대므로, AI Gateway나 배치 기능을 쓰게 되면 다시 확인해야 한다.

## Revisit conditions

- 대상 저장소의 공개 범위가 바뀌거나 저장소 이름·위치가 바뀔 때.
- 포함 범위를 "결정 필요" 범주로 넓히거나 다른 저장소를 더할 때.
- 한 실행의 요청 수가 1,000회(실행당 한도의 50%)를 넘거나, 막힌 자료가 범위의 10%를 넘을 때. 2026-10-20 측정은 각각 83회(4.2%), 1건(1.25%)이다
  (`docs/sdd/research/github-source-measurement.md`, 2026-10-20 사용자 결정). 분당 상한 60회에서는 약 1,800회에 실행 최대 시간(1,800초)이 먼저 걸리므로
  1,000회는 그 전에 다시 보는 지점이다(추론).
- 저장 위치(ADR-008)나 임베딩 공급자(ADR-002)가 바뀌거나, Workers AI 호출에 AI Gateway·배치·비동기 기능을 쓰게 될 때.
- 토큰 발급자가 바뀌거나 GitHub App으로 옮길 때(`tokens.md` T-04).

## Approval

- Approvers: 활성화 PR 리뷰어(기존 결정 기록과 같이 PR 리뷰로 승인한다)
- Approved at: 2026-10-20 사람 리뷰어 Byuntil이 결정 내용(ADR-019 번호, 첫 자료원 추가, 데이터 처리 정책, A안 제외)을 승인했다. 대화로 전달받은 결정이며, 활성화 PR 리뷰로 확정한다.
  이 문서 초안은 Claude 세션이 썼고 그 세션은 승인하지 않았다(AGENTS.md 2절).
