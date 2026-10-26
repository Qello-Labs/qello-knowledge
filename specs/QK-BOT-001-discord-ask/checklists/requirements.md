# Specification Quality Checklist: QK-BOT-001 Discord `/ask`·지연 응답·답변 표시·분할·접근 제어·오류 안내

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-25
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- 1차 검토(2026-10-25, 작성 세션): 남은 항목은 [NEEDS CLARIFICATION] 2개다. FR-005(사용자별 호출 제한), FR-007(답변 공개 범위). 사람 답을 받은 뒤 반영하고 다시 확인한다.
- 2차 검토(2026-10-25, 작성 세션): 사용자 답(Q1: C 기본 공개 + "나만 보기" 선택 인자, Q2: A Phase 1 제한 없음)을 Clarifications, FR-003·FR-005·FR-007·FR-022, US1-5·6,
  Edge Cases, Key Entities, SC-013에 반영했다. 남은 표시 0개, 모든 항목 통과.
- 독립 검토 1차(2026-10-25, 오른쪽 Herdr 패널의 Codex, 읽기 전용): 변경 요청(높음 2, 중간 7, 낮음 2). 2차 검토의 "모든 항목 통과"가 H1·H2·M2 때문에 맞지 않다고 지적했다(L2).
  작성 세션이 코드로 근거를 확인했고(`RetrievalFailure` 9종, `GenerationResult`에 실행 식별자 없음, `GenerationRequest.run_id`) 11건을 모두 반영했다.
  - H1(30초 `waitUntil`과 45초 생성): 사용자 결정으로 명세는 질의 마감 조건만 정하고 실행 방식은 계획 단계 실측 뒤 사람 승인 필수 결정으로 뒀다(Clarifications, FR-008, Assumptions).
  - H2(출처 목록 분할 모순): 출처 목록이 먼저 자리를 받고 여러 메시지에 걸칠 수 있게, 항목 길이 규칙과 설정 검사를 더했다(FR-012·FR-013, SC-007). 메시지 수 상한 초기값 3 → 4.
  - M1 FR-011 검색 실패 9종 대응, M2 SC-013 범위와 공개 뒤 전송 차단(Edge Cases), M3 비공개 가정 미확인 유지와 사람 단계 확인(SC-005, Assumptions),
    M4 질의 실행 식별자를 진입점이 만들어 `run_id`로 넘김(FR-011), M5 운영 로그 허용 항목 통일(FR-021), M6 US1-4 전제 분리, M7 실측 조건(FR-025, SC-012),
    L1 원본 버전 표시와 링크 없는 항목(FR-013, Edge Cases).
  - 플랫폼 사실 확인 결과와 출처 URL을 Assumptions에 옮겼다.
- 3차 검토(2026-10-25, 작성 세션): 남은 표시 0개. 반영본은 아직 독립 재검토를 받지 않았다. 재검토는 같은 검토자에게 맡긴다.
- 독립 재검토(2026-10-25, 같은 검토자): 변경 요청. 기존 11건 중 해소 7·부분 해소 4(H1·H2·M2·L2), 새 지적 5건(중간 4, 낮음 1). 모두 반영했다.
  - N1 남은 시간 7초 미만이면 생성을 시작하지 않음(FR-008, Edge Cases). N2 출처 분할 검사를 항목 단위 산식으로 바꾸고 기본 상한을 제목 80자·링크 300자로 낮춤(FR-012·FR-013).
  - N3 질의 마감과 안내 전달 마감 구분, SC-001·FR-009가 안내 전달 마감을 씀(FR-008). N4 중복 판정 상태를 15분 보존(FR-010, Key Entities, SC-011, Edge Cases).
  - N5 US1-2·US1-5를 새 FR에 맞추고 이 Notes의 플랫폼 확인·사람 단계 범위를 고침.
  - 검토자 확인: 질의별 생성 설정 전달은 기존 함수 인자로 가능하고 생성 결과 계약 변경은 필요 없다(Assumptions "실행 환경 한도").
- 4차 검토(2026-10-25, 작성 세션): 남은 표시 0개. 반영본의 독립 재검토 여부는 아래에 적는다.
- 독립 2차 재검토(2026-10-25, 같은 검토자): 승인(명세 검토 범위). 대상 9건(N1~N5, H1·H2·M2·L2) 모두 해소, 새 지적 0건. N2 기본 설정을 계산으로 확인했다
  (항목 최대 551자, 메시지당 3항목, 출처 8개 → 3개 메시지 + 본문 1개 = 상한 4). 이 값을 FR-012 추론 표시에 옮겼다. 실제 렌더러 검증과 실행 방식 승인은 계획 단계 몫이다.
  검토자는 읽기 전용 문서·코드 대조와 계산만 했고 실측은 하지 않았다. 명세 승인은 사람 리뷰로 받는다.
- 구현 세부 항목은 저장소 관례(QK-RET-001·QK-GEN-001 명세)에 맞춰 판정했다. Discord·Workers·ADR-008 이름은 이미 결정된 실행 환경과 창구라 명세에 둔다. 연결 방식(HTTP 계층·터널),
  메시지 꼴(본문·임베드), 응답 뒤 처리 방식, 중복 판정 상태 보존 위치, 생성 포트 어댑터, 봇 토큰 필요 여부, 모듈 구성은 계획 단계로 넘겼다(Assumptions).
- 플랫폼 동작: 3초, 15분, 2,000자, 응답 공개 범위 변경 불가, Ed25519 서명, Workers `waitUntil` 30초, CPU·외부 호출 한도는 독립 검토가 공식 문서로 확인했다(Assumptions의 URL).
  질문자만 보는 첫 응답이면 명령 실행 사실과 인자까지 숨겨지는지는 미확인이고 SC-005 사람 단계로 확인한다.
- 사람 단계: SC-001, SC-002, SC-005의 화면 대조, SC-010의 운영 포트 확인, SC-012, SC-013의 화면 확인. 나머지(SC-003~009, SC-011, SC-013 가짜 시험)는 가짜 수신부·제공자 시험이다.
- 같은 세션이 쓰고 검토했으므로 이 체크리스트는 독립 검토가 아니다(AGENTS.md 2절). 독립 검토는 별도 에이전트로 한다.
