# H05 실측 질문 세트 `qk-bot-001-h05` v2

> 상태: 확정(2026-10-27 사람 확정). 코드와 다른 커밋으로 고정한다(AGENTS.md 3.4). 바꾸려면 버전을 올리고 별도 커밋에 사유를 남긴다. 기록은 이 문서의 번호만 쓴다.
> 대상 색인: 활성 인덱스 `iv-4c0bc4fcc642`, 자료원 `dnd-backend-docs`(`dnd-side-project/dnd-15th-2-backend` `main`의 문서).
> 정답 근거는 그 저장소의 문서 경로로 적는다. 질문에 개인 정보·비공개 원문은 없다.

## v1과 바뀐 점

- 바뀐 것: 있음 질문의 "근거 문서"를 문서 하나에서 같은 핵심 사실을 담은 문서 목록으로 넓혔다. 판정 기준의 출처 조건을 "출처 가운데 하나 이상이 근거 문서 목록에 있다"로 바꿨다.
- 그대로인 것: 질문 번호·유형·나만 보기·질문 문장·핵심 사실(정답 라벨), 없음 질문의 기대 응답, 내용 판정 기준, SC-005 합성 비밀값 질문([v1](h05-question-set.md)의 S01).
- 사유: #73 평가(예산 3,000)에서 Q02·Q04가 v1 근거 문서 대신 같은 내용을 담은 다른 팀 문서를 인용했다. 답 내용은 핵심 사실과 맞았지만 v1 기준을 글자 그대로 적용하면 실패라,
  글자 그대로 9/11과 사람 판정 11/11이 갈렸다(#76, [gh68 평가 보고서](gh68-budget-eval.md) 5·7절). 라벨이 근거 문서를 하나만 두는 한계를 고친다.
- 추가 근거 문서를 고른 방법: 백엔드 로컬 복제본(`6aeccd0`, 2026-10-16 `main`, 자료원 검토 기준 커밋과 같음)의 색인 범위 문서 80개에서 핵심어로 찾고, 해당 절을 읽어
  "그 문서만 보고도 핵심 사실에 틀림없이 답할 수 있는가"로 골랐다. 일부만 담아도 틀린 내용이 없으면 넣었다(내용 판정 기준과 같다).
- 넣지 않은 후보: Q05의 `docs/adr/README.md`(외부 큐 관련 문장은 ADR 작성 질문 예시이고 실제 결정과 다르다), Q06의 `docs/api-response.md`(예시 코드만 있고 형식 규칙은 `error-codes.md`에 맡긴다),
  Q07의 `infra/README.md`("Terraform 또는 AWS CDK"로 결정 전 문장), Q08의 `CLAUDE.md`(목록이 주석에 쓰지 말 값으로 한정된다).

## 비교 조건

- v1 결과와는 같은 질문, 같은 조건(인덱스 버전, 생성 모델, 프롬프트 버전, 검색 설정·문맥 예산)에서 나온 출력만 비교한다(AGENTS.md 3.3).
- v1과 v2는 질문과 핵심 사실이 같으므로 사람 판정은 그대로 비교할 수 있다. 글자 그대로 판정은 근거 문서 목록이 달라 v2가 같거나 더 많이 통과한다. 두 버전의 글자 그대로 수치를 품질 변화로 읽지 않는다.
- 같은 출력을 v1·v2 기준으로 함께 판정하면 라벨 변경만의 효과를 볼 수 있다.

## 판정 기준(SC-002)

- **있음**: 답변에 출처 목록이 붙고, 출처 가운데 하나 이상이 "근거 문서" 목록에 있으며, 각 링크가 원본 문서를 연다. 답변 내용이 "핵심 사실"과 어긋나지 않는다.
  핵심 사실이 일부만 들어가도 틀린 내용이 없으면 통과로 본다. 출처 확인 안 됨·출력 잘림 표시는 따로 적는다.
- **없음**: "제공된 자료만으로 확인할 수 없습니다."로 답한다. 자료에 없는 내용을 지어내면 실패다.
- 출처 조건(근거 문서 목록 포함 여부)은 출처 경로로 계산할 수 있다. 내용 판정은 사람이 원본 문서와 대조해 확정한다.

## 질문

| 번호 | 유형 | 나만 보기 | 질문 | 근거 문서(하나 이상) | 핵심 사실(정답 라벨) |
| --- | --- | --- | --- | --- | --- |
| Q01 | 있음 | 끔 | 백엔드에서 JPA와 JDBC는 각각 어떤 작업에 쓰기로 했어? | `docs/adr/0002-jpa-jdbc-boundary.md`, `docs/adr/README.md` | 일반 aggregate CRUD는 JPA, PostGIS 거리·방위 조회·행 잠금·조건부 갱신·bulk insert·Outbox claim 같은 DB 특화 연산은 JDBC |
| Q02 | 있음 | 끔 | API 성공 응답 형식은 어떻게 정했어? 204 No Content도 써? | `docs/adr/0005-api-success-response-contract.md`, `docs/api-response.md` | `ApiResponse`(status/data/timestamp)로 controller가 직접 감싼다. 204는 쓰지 않고 값이 없어도 200과 `data: null` |
| Q03 | 있음 | 끔 | 운영자와 앱 사용자는 인증 방식이 어떻게 달라? | `docs/adr/0006-split-operator-and-device-authentication.md`, `docs/product/AUTH_DESIGN.md` | 운영자는 `login_id`+bcrypt 비밀번호와 서버 세션·HttpOnly 쿠키·CSRF, 앱 사용자는 기기 자격증명(`device_secret`) 기반 단기 토큰 |
| Q04 | 있음 | 끔 | 앱 사용자 계정을 만들 때 국가는 어떤 값으로 받고 어떻게 검증해? | `docs/adr/0007-require-country-before-user-account-creation.md`, `docs/product/ONBOARDING_COUNTRY_DESIGN.md`, `docs/product/AUTH_DESIGN.md` | ISO 3166-1 alpha-2 `countryCode`, 공백 제거·대문자 변환 뒤 `region_code` 마스터의 COUNTRY와 대조, 계정 저장 전에 검증하고 실패하면 400 |
| Q05 | 있음 | 끔 | 푸시 발송에 SQS나 Kafka 같은 외부 큐를 쓰지 않은 이유가 뭐야? | `docs/adr/0008-adopt-fcm-push-delivery-pipeline.md` | 초기 규모에서는 별도 broker 근거가 부족해 기존 PostgreSQL delivery 원장을 queue로 쓰고, 짧은 claim transaction과 transaction 밖 FCM 호출, lease·fencing으로 분리 |
| Q06 | 있음 | 끔 | API 오류 응답의 `errorDetail.code`는 어떤 형식이야? | `docs/error-codes.md`, `docs/adr/0003-global-exception-handling.md` | `{BC}-{CATEGORY}-{SEQ}` 형식. 오류 본문의 `status`는 항상 `error` |
| Q07 | 있음 | 끔 | AWS 인프라는 어떤 도구로 관리하기로 했어? | `docs/adr/0004-adopt-terraform-for-aws-iac.md`, `AGENTS.md`, `CLAUDE.md`, `docs/adr/README.md` | Terraform 단독 채택(AWS CDK와 비교) |
| Q08 | 있음 | 켬 | 저장소에 절대 기록하면 안 되는 값에는 어떤 게 있어? | `docs/harness/SECRET_HANDLING.md`, `AGENTS.md` | `.env` 실제 값, API 토큰·세션·비밀번호·개인 키, AWS 접근 키·계정 ID, 서버 주소·내부 endpoint·DB 연결 주소 등 |
| Q09 | 없음 | 끔 | 앱 메인 화면의 대표 색상 코드는 뭐야? | — | 디자인(Figma)은 색인하지 않는다. "제공된 자료만으로 확인할 수 없습니다." |
| Q10 | 없음 | 끔 | 안드로이드 앱에서 Kotlin 코루틴을 도입하기로 한 이유가 뭐야? | — | 안드로이드 저장소는 색인하지 않는다. "제공된 자료만으로 확인할 수 없습니다." |
| Q11 | 없음 | 켬 | 다음 팀 회식은 언제 어디서 해? | — | 자료에 없다. "제공된 자료만으로 확인할 수 없습니다." |

표본: 있음 8(나만 보기 1), 없음 3(나만 보기 1), 합계 11. 모델 출력 편차를 보려고 질문마다 2회 이상 실행한다.

## 실행 전 확인

- 근거 문서 목록은 로컬 복제본(2026-10-16) 기준이다. 실행 전에 목록의 문서가 활성 색인에 있는지 확인하고, 없는 문서는 그 실행의 출처 판정에서 빼고 보고서에 적는다.
- 질문 문장은 v1과 같아 비밀값 규칙 검사 결과도 v1과 같다(질문 11개 모두 걸리지 않음).
