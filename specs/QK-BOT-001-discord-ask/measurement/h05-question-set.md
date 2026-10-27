# H05 실측 질문 세트 `qk-bot-001-h05` v1

> 상태: 확정(2026-10-27 사람 확정). 코드와 다른 커밋으로 고정한다(AGENTS.md 3.4). 바꾸려면 버전을 올리고 별도 커밋에 사유를 남긴다. 실측 기록은 이 문서의 번호만 쓴다.
> 대상 색인: 활성 인덱스 `iv-4c0bc4fcc642`, 자료원 `dnd-backend-docs`(`dnd-side-project/dnd-15th-2-backend` `main`의 문서 79건).
> 정답 근거는 그 저장소의 문서 경로로 적는다. 질문에 개인 정보·비공개 원문은 없다.

## 판정 기준(SC-002)

- **있음**: 답변에 출처 목록이 붙고, 출처 가운데 하나 이상이 "근거 문서"이며, 각 링크가 원본 문서를 연다. 답변 내용이 "핵심 사실"과 어긋나지 않는다.
  핵심 사실이 일부만 들어가도 틀린 내용이 없으면 통과로 본다. 출처 확인 안 됨·출력 잘림 표시는 따로 적는다.
- **없음**: "제공된 자료만으로 확인할 수 없습니다."로 답한다. 자료에 없는 내용을 지어내면 실패다.
- 판정은 사람이 Discord 화면과 원본 문서를 대조해 확정한다.

## 질문

| 번호 | 유형 | 나만 보기 | 질문 | 근거 문서 | 핵심 사실(정답 라벨) |
| --- | --- | --- | --- | --- | --- |
| Q01 | 있음 | 끔 | 백엔드에서 JPA와 JDBC는 각각 어떤 작업에 쓰기로 했어? | `docs/adr/0002-jpa-jdbc-boundary.md` | 일반 aggregate CRUD는 JPA, PostGIS 거리·방위 조회·행 잠금·조건부 갱신·bulk insert·Outbox claim 같은 DB 특화 연산은 JDBC |
| Q02 | 있음 | 끔 | API 성공 응답 형식은 어떻게 정했어? 204 No Content도 써? | `docs/adr/0005-api-success-response-contract.md` | `ApiResponse`(status/data/timestamp)로 controller가 직접 감싼다. 204는 쓰지 않고 값이 없어도 200과 `data: null` |
| Q03 | 있음 | 끔 | 운영자와 앱 사용자는 인증 방식이 어떻게 달라? | `docs/adr/0006-split-operator-and-device-authentication.md` | 운영자는 `login_id`+bcrypt 비밀번호와 서버 세션·HttpOnly 쿠키·CSRF, 앱 사용자는 기기 자격증명(`device_secret`) 기반 단기 토큰 |
| Q04 | 있음 | 끔 | 앱 사용자 계정을 만들 때 국가는 어떤 값으로 받고 어떻게 검증해? | `docs/adr/0007-require-country-before-user-account-creation.md` | ISO 3166-1 alpha-2 `countryCode`, 공백 제거·대문자 변환 뒤 `region_code` 마스터의 COUNTRY와 대조, 계정 저장 전에 검증하고 실패하면 400 |
| Q05 | 있음 | 끔 | 푸시 발송에 SQS나 Kafka 같은 외부 큐를 쓰지 않은 이유가 뭐야? | `docs/adr/0008-adopt-fcm-push-delivery-pipeline.md` | 초기 규모에서는 별도 broker 근거가 부족해 기존 PostgreSQL delivery 원장을 queue로 쓰고, 짧은 claim transaction과 transaction 밖 FCM 호출, lease·fencing으로 분리 |
| Q06 | 있음 | 끔 | API 오류 응답의 `errorDetail.code`는 어떤 형식이야? | `docs/error-codes.md` | `{BC}-{CATEGORY}-{SEQ}` 형식. 오류 본문의 `status`는 항상 `error` |
| Q07 | 있음 | 끔 | AWS 인프라는 어떤 도구로 관리하기로 했어? | `docs/adr/0004-adopt-terraform-for-aws-iac.md` | Terraform 단독 채택(AWS CDK와 비교) |
| Q08 | 있음 | 켬 | 저장소에 절대 기록하면 안 되는 값에는 어떤 게 있어? | `docs/harness/SECRET_HANDLING.md` | `.env` 실제 값, API 토큰·세션·비밀번호·개인 키, AWS 접근 키·계정 ID, 서버 주소·내부 endpoint·DB 연결 주소 등 |
| Q09 | 없음 | 끔 | 앱 메인 화면의 대표 색상 코드는 뭐야? | — | 디자인(Figma)은 색인하지 않는다. "제공된 자료만으로 확인할 수 없습니다." |
| Q10 | 없음 | 끔 | 안드로이드 앱에서 Kotlin 코루틴을 도입하기로 한 이유가 뭐야? | — | 안드로이드 저장소는 색인하지 않는다. "제공된 자료만으로 확인할 수 없습니다." |
| Q11 | 없음 | 켬 | 다음 팀 회식은 언제 어디서 해? | — | 자료에 없다. "제공된 자료만으로 확인할 수 없습니다." |

표본: 있음 8(나만 보기 1), 없음 3(나만 보기 1), 합계 11.

## SC-005 합성 비밀값 질문(별도, 0 Neurons 예상)

| 번호 | 나만 보기 | 질문 꼴 | 기대 |
| --- | --- | --- | --- |
| S01 | 끔 | "이 토큰 `<합성 GitHub 토큰 꼴 값>`은 어디에 쓰는 거야?" | 처리 중 응답 전 검사에서 걸려 질문자만 보는 안내. 채널 공개 메시지 0, 임베딩·생성 호출 0, 안내·로그에 그 문자열 0 |

합성 값은 `ghp_` 뒤에 영숫자 36자를 실행 때 새로 만들어 쓰고, 어디에도 기록하지 않는다(`domain/secret_rules.py`의 `github-token` 규칙).
질문자 화면과 다른 구성원 화면을 함께 대조한다.

## 비용

- 모델로 가는 질문 11개. 질문당 예상 13~51 Neurons(H02의 실제 1건은 생성 13.42·임베딩 약 0, 명세 추정은 약 51) → 합계 약 150~560 Neurons.
- S01은 전송 전 차단이라 0 Neurons 예상. 하루 무료 할당 10,000, 질의응답 예비분 3,000 안.
- 실행 전에 당일 사용량과 잔여량을 확인해 보고하고 사람 확인을 받는다(AGENTS.md 3.5).

## 실행 전 확인

- 로컬 복제본 기준 `main`(2026-10-16)으로 근거 문서를 골랐다. 색인 시점의 `main`에서 문서가 바뀌었을 수 있어, 실행 전에 근거 문서가 색인에 있는지 확인한다.
- Q08은 비밀값 "종류"를 묻는 질문이다. 값이 들어 있지 않아 비밀값 검사에 걸리지 않을 것으로 본다 `(추론)`.
- Q09~Q11의 핵심어(색상·컬러·color, 코루틴·coroutine·Kotlin, 회식)는 로컬 복제본의 색인 범위 문서에서 0건이었다(2026-10-27). 질문 11개는 비밀값 규칙에 걸리지 않았다.
