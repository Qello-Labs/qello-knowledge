# Specification Quality Checklist: QK-OBS-001 질의 로그, 👍/👎 피드백, `/sources`, 질의 원문 저장 옵션

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-29
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

- 1차 검증(2026-10-29): [NEEDS CLARIFICATION] 3개가 남았다. US3-5(저장 동의 방식), US5(`/sources` 내용), FR-012(원문 보존 기간). 사람 답을 받아 반영한다.
- 2차 검증(2026-10-29): 사용자 답(동의는 👎 때 묻기, `/sources`는 자료원 목록, 보존은 2.G까지)을 Clarifications, US3·US5, FR-010·FR-012·FR-015, Edge Cases, Key Entities,
  SC-003·SC-010, Assumptions에 반영했다. 남은 표시는 0개다.
  👎 때 묻기는 동의 시점에 원문이 있어야 하므로 "원문 대기"(메모리에만, 처음 24시간·500건, 3차에서 질문만·1시간)를 더했고, 동의는 질문자 본인만 하게 했다. 둘 다 작성 세션 판단이다(사람 확인 대상).
- 3차 검증(2026-10-29, 독립 검토 반영 뒤): 독립 검토(변경 요청, 높음 2·중간 7·낮음 9)와 사용자 결정 셋(질문만 저장, 대기 1시간, 날짜 상한)을 반영해 spec을 다시 썼다.
  FR은 FR-001~024, SC는 SC-001~012로 번호가 바뀌었다. 남은 표시는 0개다. 재검토는 받지 않았다.
- 구현 세부: 이 저장소의 다른 명세(QK-BOT-001)처럼 Discord 상호작용, 서명 검사, 중계 Worker, 마이그레이션 같은 계약 수준의 말은 남겼다. 저장 구조·버튼 값 형식·명령 이름은 plan에 둔다.
- US1-5·FR-003(허용 범위 밖 요청은 질의 기록 없음), FR-001(질문자 식별자는 동의와 관계없이 저장, ADR-016)은 작성 세션 판단이다(사람 확인 대상).
