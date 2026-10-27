# Decision Record: ADR-023 코드 자료원 — 백엔드 Java 코드와 Android Kotlin 코드

> Created at: `2026-10-27`
> Jira 이슈: `https://tkv123.atlassian.net/browse/SCRUM-118`
> 기능명세서 ID: `QK-CHK-001`
> Status: Accepted

## Context

Phase 2 목표는 팀 질문의 대부분을 차지하는 코드 질문("이 API는 어느 서비스 메서드가 처리해?", "이 화면의 ViewModel은?")에 출처가 붙은 답을 주는 것이다.
QK-CHK-001이 Java·Kotlin 코드 청커를 만들었고, 코드를 수집할 자료원 두 개(`dnd-backend-code`, `dnd-android-code`)를 `config/sources.toml`에 비활성으로 등록했다(spec FR-032).
AGENTS.md 3.1은 새 자료원을 더할 때 데이터 처리 정책을 확인하고 결정 기록을 남기라고 한다. 켜기 전에 이 기록과 사람의 개인 정보 확인 기록이 필요하다(spec FR-034·035).

번호는 처음에 ADR-022로 계획했다(research R-13). 구현 시점 `main`에는 ADR-021(동기화 실패 알림)과 ADR-022(Discord 질의 경로)가 이미 있어 다음 번호 023을 쓴다(tasks T041).

## Decision

공개 저장소 두 곳의 본문 코드를 각각 별도 자료원으로 등록하고, 아래 활성화 순서를 모두 마친 뒤 한 번에 하나씩 켠다. 첫 활성화는 본문 코드만 하고 테스트 소스 세트는 넣지 않는다.

| 이름 | 저장소 | 포함 | 제외 |
| --- | --- | --- | --- |
| `dnd-backend-code` | `dnd-side-project/dnd-15th-2-backend` | `src/main/java/**/*.java` | 기본 제외 규칙만 |
| `dnd-android-code` | `dnd-side-project/dnd-15th-2-android` | `app/src/main/**/*.kt`, `data/src/main/**/*.kt`, `domain/src/main/**/*.kt`, `presentation/src/main/**/*.kt` | 기본 제외 규칙만(`build-logic/`은 포함 패턴 밖) |

## Rationale

- 두 저장소 모두 팀 제품 저장소이고 공개다. 기존 읽기 전용 토큰으로 읽을 수 있고, QK-SEC-001이 팀 공용으로 판정한다(ADR-019와 같다).
- 백엔드 코드를 기존 `dnd-backend-docs`에 더하지 않고 따로 둔다. 기존 자료원의 확인 기록과 ADR-019를 건드리지 않고 따로 켜고 끌 수 있다(spec Assumptions).
  같은 저장소 두 자료원의 포함 패턴은 확장자로 갈려(`.md` 대 `.java`) 같은 파일을 함께 고르지 않는다. 고정 커밋 `6aeccd0` 트리에서 `dnd-backend-docs` 80개, `dnd-backend-code` 776개, 겹침 0개였다(research R-13).
- 본문만 첫 활성화하는 이유는 비용이다. 테스트까지 넣으면 첫 색인이 하루 색인 예산 5,000 Neurons를 넘는다(아래 Data and cost).
  구현된 청커 실측(2026-10-27)에서 본문 약 3,170, 테스트 포함 약 7,440이었다.
  테스트 코드 포함 여부는 첫 활성화 평가(QK-EVL-001) 뒤 별도로 정한다. 그때 백엔드 테스트 9개 파일의 비밀값 규칙(`assigned-secret`) 판정을 사람이 확인한다.

## Alternatives considered

| Alternative | Advantages | Disadvantages | Reason not selected |
| --- | --- | --- | --- |
| 백엔드 코드 경로를 `dnd-backend-docs` 포함 패턴에 더하기 | 자료원 하나라 자료원별 식별 명세가 필요 없다 | 기존 확인 기록과 ADR-019 범위가 바뀌고, 문서와 코드를 따로 켜고 끌 수 없다 | 기존 자료원 범위를 바꾸지 않는다(spec FR-032) |
| 테스트 소스 세트까지 첫 활성화 | 테스트 질문에도 답할 수 있다 | 첫 색인 약 7,000 Neurons로 하루 색인 예산 5,000을 넘는다 | 작게 시작하고 평가한 뒤 넓힌다(C-04) |
| 두 자료원을 한 번에 켜기 | 준비가 한 번이다 | 문제가 생겼을 때 원인을 가르기 어렵다 | 한 번에 하나씩 켠다(spec FR-035) |

## Evidence

- QK-CHK-001 `specs/QK-CHK-001-code-chunker/research.md` R-02(측정 조건: 백엔드 `6aeccd0`, Android `0314755`, 스크립트 `1cc6ad12e564`), R-03, R-13.
- `docs/sdd/research/tokens.md` 2절: 세분화 토큰, 공개 저장소 읽기만, 저장소 권한 추가 없음, 시간당 5,000회.
- ADR-002(임베딩 공급자 Workers AI와 데이터 처리 정책), ADR-008(운영 저장소와 데이터 처리 정책), ADR-019(같은 저장소의 문서 자료원).
- Cloudflare Workers AI "Data usage": https://developers.cloudflare.com/workers-ai/platform/data-usage/ (ADR-019가 2026-10-20 조회). 이 기록에서는 다시 조회하지 않았다.
- 구현된 청커 실측(QK-CHK-001 사람 단계 H01·H02, 2026-10-27): `measurement/measure_code.py --compact-header --merge-small-heads --skip-trivial-summary --time-chunking`,
  스크립트 해시 `360e7f3810f9`, 같은 고정 커밋 두 곳, macOS arm64·Python 3.13, 코드 청킹 규칙 버전 `chk-code-4c1551b7519d`. 외부 모델 호출 0건.

## Data and cost

- 외부로 전송되는 데이터와 제공자의 학습 사용·보존 정책:
  - 수집: GitHub REST API에 `GET` 요청만 보낸다. 보내는 것은 토큰과 요청 경로, 받는 것은 공개 저장소 코드다.
  - 임베딩: QK-SEC-001을 통과한 파일의 코드 청크 본문과 임베딩 입력 텍스트(검색 헤더·형식 선언 맥락 줄·반복 줄 포함, 요약 청크 포함)를 Cloudflare Workers AI로 보낸다.
    모든 입력은 캐시에 없으면 전송 직전 비밀값 검사를 거친다(QK-SEC-001 FR-013, QK-CHK-001 SC-009). Cloudflare는 Workers AI 입력·출력을 모델 학습에 쓰지 않고,
    일반 추론의 입력·출력을 보관하지 않는다고 밝힌다(ADR-002, ADR-019). 동기 REST 호출이라 일반 추론 규정에 해당한다고 본다(추론, ADR-019와 같다).
  - 저장: 청크 본문과 코드 메타데이터(`locator["code"]`: 심볼·시그니처·어노테이션 이름 등)를 운영 PostgreSQL에 저장한다. 데이터 처리 정책은 ADR-008에 적었다.
- 보존과 삭제 반영: 원본에서 지워지거나 범위에서 빠진 파일의 청크는 QK-SYN-001 동기화가 내린다. 자료원을 끄면 그 자료원 문서는 "자료원 꺼짐"으로 내려간다.
- 무료 한도와 예상 사용량(구현된 청커 실측, 임베딩 입력 바이트 ÷ 1.4 × 1,075/백만, QK-EMB-001 보정 계수):
  - 첫 색인: 본문 코드 약 3,170 Neurons(백엔드 2,658 + Android 509), 테스트 포함 약 7,440(백엔드 테스트 4,271, Android 테스트 6). 하루 색인 예산은 5,000이다.
    Android 값에는 포함 패턴 밖인 `build-logic/` 11개 파일이 들어 있어 실제 자료원 범위는 조금 작다. plan 흉내 측정(research R-02)은 본문 약 2,960이었다.
  - 청크 수: 백엔드 10,866(흉내 측정 대비 +0.6%), Android 1,048(+2.6%). 구문 해석 실패 대체 청킹 0, 맥락 줄 생략 0, 상한 때문에 나뉜 원문 청크 15.
  - 첫 수집량: 백엔드 본문 776개 파일, 분당 60요청 기본값이면 약 13분으로 실행 상한 1,800초 안이다. Android 본문 216개 파일.
- 교체 시 영향(재임베딩, 인덱스 버전): 자료원 추가 자체는 인덱스 버전 변경이 아니다. 다만 코드 청크를 만들려면 코드 청킹을 켜야 하고(`QK_CODE_CHUNKING=on`),
  그러면 인덱스 버전이 바뀐다(QK-CHK-001 FR-028·030). 새 인덱스 버전은 QK-STO-002 절차로 만들고 평가한 뒤 활성화한다(AGENTS.md 3.3).

## 활성화 순서

1. 자료원별 식별 명세(초안 QK-SYN-005) 완료. 지금 동기화는 같은 종류(`github_repo_files`) 자료원을 하나만 받는다(`sync/identity.py`, spec FR-036).
2. QK-STO-002로 `QK_CODE_CHUNKING=on`의 새 인덱스 버전을 만들고, 키워드 규칙 대응표(`INDEX_KEYWORD_RULES`)에 더하고, 평가한 뒤 활성화한다.
   대응표에 없으면 `qk-index check`·`run`이 `CODE_INDEX_VERSION_UNREGISTERED`로 멈춘다.
3. 사람이 포함 범위 파일을 확인하고 개인 정보 확인 기록(`config/source_reviews/<자료원 이름>.toml`)을 쓴다. 에이전트는 대신 쓰지 않는다.
4. 그 자료원 하나만 `enabled = true`로 바꾼다.
5. `qk-index sources check`로 설정과 확인 기록을 검사한다.
6. 미리 보기로 예상 Neurons를 확인하고 측정한다. 하루 색인 예산을 넘으면 실행하지 않는다(AGENTS.md 3.5).

두 번째 자료원은 첫 자료원의 측정과 평가를 본 뒤 같은 순서로 켠다.

## Consequences

### Positive

- 코드 질문에 메서드·클래스 단위 출처를 줄 수 있다. 메타데이터는 QK-CHK-004(API·코드 교차 관계)와 QK-TRK-001(필터)이 쓴다.
- 비활성으로 등록만 해도 운영 동기화 대상 선택에서 빠져 지금 동작에 영향이 없다(`sync/identity.py`).

### Negative / risks

- 코드 주석·문자열에 지시문이 있을 수 있다. 검색된 지시문은 데이터로만 다룬다(C-03, AGENTS.md 3.2).
- 코드에는 형식 없는 개인 정보(주석 속 사람 이름 등)가 있을 수 있다. 사람의 개인 정보 확인이 그 판단을 한다.
- 토큰이 발급자 개인 계정에 묶여 있다(`tokens.md` T-04).
- 비용 추정은 흉내 측정이고 보정 계수가 코드에 맞는지 확인되지 않았다(research R-02, 토크나이저 기준은 보수 추정의 약 절반).

## Revisit conditions

- 첫 활성화 측정의 청크 수나 예상 Neurons가 위 실측과 ±10% 넘게 다를 때.
- 테스트 소스 세트를 포함하거나 다른 저장소를 더할 때.
- 저장소 공개 범위가 바뀌거나, 임베딩 공급자(ADR-002)나 저장 위치(ADR-008)가 바뀔 때.

## Approval

- Approvers: tkv00(작업 담당자)
- Approved at: 2026-10-27. 대화로 받은 승인이다(원문 "6.승인"). 작성 세션은 이를 ADR-023 승인으로 해석했고, 위 실측 수치는 승인 뒤 반영했다. PR 리뷰로 확정한다.

이 문서 초안은 Claude 세션이 썼고 그 세션은 승인하지 않았다(AGENTS.md 2절). 승인은 코드 자료원을 켜는 것이 아니다. 켜는 일은 위 활성화 순서를 따른다.
