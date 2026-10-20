# Specification Quality Checklist: QK-ING-002 GitHub 저장소 파일 수집(트리 비교, 포함·제외 패턴)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-20
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

- 1차 점검(2026-10-20): FR-020(개인 정보 확인 기록의 위치와 검증 방식)에 확인 필요 표시 1건이 남았다.
- 2차 점검(2026-10-20): 사용자 결정(안 A)으로 닫았다. 자료원별 확인 기록 파일을 `config/` 아래에 두고, 수집 전 검증이 기록 범위와 현재 설정을 대조한다.
  FR-020과 Key Entities를 고쳤고, 이 안을 전제로 쓴 US4 시나리오 2와 SC-008을 대조했다. 모든 항목 통과.
- 구현 세부: blob SHA, UTF-8, HTTPS, `GITHUB_API_TOKEN`, `github_repo_files`, `scripts/preflight.py`는 기존 계약(QK-ING-001·QK-SEC-001)과
  정책 근거를 가리키려고 남겼다. GitHub API 엔드포인트, 언어·라이브러리, 저장 방식은 정하지 않았다.
- 대상 규모(81개, 약 1,083 KB)는 인벤토리 기준일과 커밋을 붙여 적었다(C-13). 실제 값은 FR-022 측정으로 확인한다.
- FR-009·FR-017은 QK-ING-001 코드를 고치는 요구라 plan에서 범위와 사람 승인을 받는다(Assumptions "설계 단계로 넘기는 것").
