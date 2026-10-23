# Specification Quality Checklist: QK-GEN-001 답변 생성 프롬프트·출처 표시·확인 불가·충돌 처리·생성 Provider

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-23
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

- 1차 검토(2026-10-23, 작성 세션): 남은 항목은 [NEEDS CLARIFICATION] 2개다. FR-015(유효 인용이 하나도 없는 답변 처리), FR-017(팀 자료와 무관한 질문 처리).
  사람 답을 받은 뒤 반영하고 다시 확인한다.
- 2차 검토(2026-10-23, 작성 세션): 사용자 답(Q1: B 출처 확인 안 됨 표시, Q2: A 같은 경로로 처리)을 FR-015·FR-017, US2-5, US3-4·5, FR-026, SC-001, SC-008, Clarifications에
  반영했다. 남은 표시 0개, 모든 항목 통과.
- 독립 검토 1차(2026-10-23, 별도 서브에이전트): 변경 요청(높음 3, 중간 11, 낮음 10). "Requirements are testable and unambiguous" 통과 표시가 M3·M9·M10·H3 때문에
  맞지 않다고 지적했다. H2·H3(일부)·M1~M5·M7~M11·L1~L10을 반영했다. H3 지적 중 "템플릿 원문이 없다"는 사실과 달라(TASK.md "승인된 입력"에 있음) 표기 차이만 FR-003에 적었다.
  H1(묶음 출처)은 FR-010에 [NEEDS CLARIFICATION]으로 두고 사람 결정을 기다린다. M6(FR-015 결정과 AGENTS.md 3.2의 충돌)은 사람 확인 대상이다.
- 사용자 답(2026-10-23): H1 A(출처 없이 검사), M6 유지. FR-010·FR-015, Clarifications, Assumptions에 반영했다. 남은 표시 0개. 재검토는 같은 검토자에게 맡긴다.
- 독립 재검토(2026-10-23, 같은 검토자): 경미한 변경 요청(높음 0, 중간 3, 낮음 6). 고치면 승인 권고이고 다시 검토할 필요 없다고 했다. H3 지적은 검토자가 철회했다.
  N1~N9를 반영했다. N3(FR-009 (나)일 때 인용·출처 목록)은 인용을 지우고 출처 목록을 비우는 쪽으로 작성 세션이 정했다(US2-1과 맞춤, 사람 확인 대상).
- 구현 세부 항목은 저장소 관례(QK-RET-001·QK-EMB-001 명세)에 맞춰 판정했다. 생성 모델 식별자, 추론 끔 표기, Source ID 표기, Context 머리줄 형식은 ADR-009와 승인된
  프롬프트 후보 1이 정한 계약이라 명세에 둔다. 저장 구조, 호출 방식(바인딩·HTTP), 모듈 구성은 계획 단계로 넘겼다(Assumptions).
- SC-008은 실제 생성 모델 호출이 필요한 사람 단계다. 가짜 제공자 시험(SC-001~007, 009, 010)과 구분한다.
- 같은 세션이 쓰고 검토했으므로 이 체크리스트는 독립 검토가 아니다(AGENTS.md 2절). 독립 검토는 별도 에이전트로 한다.
