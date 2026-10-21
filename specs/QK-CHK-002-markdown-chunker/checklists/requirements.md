# Specification Quality Checklist: QK-CHK-002 Markdown 청커·검색 헤더

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-21
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

- 1차 점검(2026-10-21): 확인 필요 표시 없이 썼다. 기본값을 고른 결정(검색 헤더를 본문에 넣지 않고 임베딩 입력·키워드 텍스트 앞에만 붙임,
  겹침 없음, 절 합치지 않음, 긴 줄은 실패 처리, 키워드 검색 텍스트 기본값 = 헤더 + 본문)은 Assumptions와 FR에 근거와 함께 적었고 사람 검토 대상이다.
- 1차 점검 수정: Edge Cases에 "문서 전체가 제목 줄뿐인 경우"를 더해 FR-009(원문 줄은 정확히 한 청크)와 맞췄다. 모든 항목 통과.
- 구현 세부: CommonMark·GitHub 표 확장은 Markdown 해석 기준을 가리키려고 남겼다(FR-021). bge-m3, 8,192토큰, 바이트당 토큰 추정은
  ADR-002·QK-EMB-001의 기존 결정을 가리킨다. 언어·라이브러리·저장 방식·자료 구조는 정하지 않았다.
- 상한의 안전 여유와 목표 크기 초기값은 측정이 필요해 `plan.md`로 넘겼다(FR-013, FR-014). 수치 없이도 수용 시험(SC-003)은 "설정한 상한" 기준으로 판정할 수 있다.
- 2차 점검(2026-10-21, Codex 1차 검토 "변경 요청" 11건 반영, 사용자가 권장안 승인):
  - 높음: US4 시나리오 4와 FR-023을 "언어 표시는 원문에 남기고 판정에 쓰지 않음"으로 좁힘(1). 크기 판정을 "헤더 + 반복 머리글 + 후보 본문" 기준으로 통일하고
    줄 길이 초과·헤더 길이 초과 실패 조건과 경계값 시나리오를 둠(FR-015, US2 시나리오 4·5, SC-003)(2). 청킹 결과가 검색 헤더·임베딩 입력 텍스트를 함께 넘기고
    저장 스키마에는 두지 않는다고 정함(FR-019, Key Entities)(3).
  - 중간: 본문 없는 절도 제목 줄 청크를 만들게 바꿈(FR-011, US3 시나리오 2, SC-006). 같은 제목 경로의 상위 절 조회 한계는 Edge Cases·Assumptions에 기록(4).
    국소성 보장을 "제목·절 경계가 그대로인 본문 수정"으로 한정하고 제목 수정 시나리오 추가(FR-011, US1 시나리오 6, SC-004)(5). 보장을 예상 토큰 기준으로 낮추고
    실제 토크나이저 대조·최대 줄 길이 측정을 plan 필수 항목으로 둠(US2, FR-013, Assumptions)(6). 제목·위치 선택 규칙을 QK-ING-001 data-model로 고정(FR-008, FR-017,
    US3 시나리오 4)(7). 구조 경고(표 셀 수 불일치, 닫히지 않은 코드 펜스) 추가(FR-004, FR-024, FR-027, SC-005)(8). 기대값 비교·대상 아님·저장 검증·버전·요약
    수용 기준 추가(SC-001·002·007·009·010), 버전 형식·첫 값을 plan 결정 항목으로 명시(FR-012)(9).
  - 낮음: STO-001 data-model 표현을 정합성 작업으로 고침(10). 성능 기준을 필터 통과 79개로 바꾸고 측정 조건을 plan으로 넘김(SC-011)(11).
  - FR-012를 "청크 결과에 영향을 주는 규칙"으로 좁혀 FR-024(경고 유형 추가는 버전 불변)와 맞췄다. 모든 항목 통과. Codex 재검토 대기.
- 3차 점검(2026-10-21, Codex 2차 검토 "변경 요청" 반영. 1차 지적 8건 해소·3건 일부, 새 지적 5건):
  - SC-004에 문서 제목·원본 위치·설정 불변 조건을 넣고, 제목 수정은 "문서 제목으로 쓰이지 않는 제목"으로 한정, 문서 제목 수정을 따로 판정(새 1, 1차 5).
  - FR-008~011을 청크 목록 결과에만 적용한다고 명시. SC-002·003을 성공 사례와 실패 경계값 사례로 나눔(새 2).
  - 목표 크기를 연성 목표로 정의(FR-014). 상한 이하 블록은 문단 포함 나누지 않음(FR-016). US2 시나리오 6·SC-003에 목표~상한 사이 문단 사례 추가(새 3).
  - SC-001 기대값에 순서 연속성, 키워드 검색용 텍스트, 임베딩 입력 텍스트(뒤 조각 머리글 포함)를 넣음. SC-009에 "경고 판정만 바꾸면 버전 유지" 추가(새 4, 1차 9).
  - TASK.md Scope·Data·완료 조건을 명세(FR-012 첫 버전은 plan, FR-013 예상 토큰 기준 상한)와 맞춤. Jira·GitHub Issue 본문 문구는 그대로다(새 5, 1차 6).
  - 모든 항목 통과.
- 4차 점검(2026-10-21, Codex 3차 검토 "승인" 권고, 남은 낮음 1건 반영): US1 시나리오 4와 US2 시나리오 1~3의 Given에 성공 결과·최소 조각이 상한에 드는 전제를 적었다. 모든 항목 통과.
