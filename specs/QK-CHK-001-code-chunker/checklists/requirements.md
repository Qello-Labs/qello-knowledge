# Specification Quality Checklist: QK-CHK-001 코드 청커(Java·Kotlin, Android 컴포넌트, 테스트)·코드 메타데이터

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-26
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

- 1차 점검(2026-10-26): 확인 필요 표시 없이 썼다. 자료원 활성화(Android 저장소, 테스트 코드 포함)는 청커 명세가 아니라 자료원을 켜는 별도 결정이라
  표시를 두지 않고 Assumptions "범위"에 넘겼다.
- 작성 세션 판단(사람 검토 대상): 요약 청크를 원문 줄 셈에서 빼고 겹침을 허용(FR-009·FR-013), 심볼 경로를 제목 경로 자리에 저장(FR-020),
  구문 해석 실패 시 실패 대신 줄 단위 대체 청킹(FR-019), Android 컴포넌트를 직접 상위 형식 이름과 이름 규칙으로만 판정(FR-024),
  인덱스 버전에 두 청킹 규칙 버전을 모두 반영(FR-028), 성능 기준 60초(지금 SC-012).
- 1차 점검 수정: US2 시나리오 3과 US5 시나리오 1의 Given에 "한 줄은 헤더·반복 줄과 합쳐 상한 이하" 전제를 넣었다. FR-010 (3)에 상한 초과 시 FR-017로 나눈다는
  단서를, FR-013에 여러 줄 시그니처의 정의를 넣었다. 모든 항목 통과.
- 구현 세부: 언어 이름(Java·Kotlin), 어노테이션 이름, Android 기본 형식 이름, 테스트 경로는 판정 대상을 가리키려고 남겼다. bge-m3·예상 토큰·`meta-v1`·`sync/keys.py`는
  기존 결정과 현재 계약을 가리킨다. 구문 분석 방법, 라이브러리, 저장 방식, 버전 형식은 정하지 않고 `plan.md`로 넘겼다(FR-016·FR-026~028, Assumptions).
- 다음 단계: 작성에 관여하지 않은 별도 에이전트의 독립 검토, 그 뒤 사람 승인. 같은 세션의 자기 점검이라 독립 검증이 아니다.
- 2차 점검(2026-10-26, 독립 검토 "변경 요청" 반영. 높음 2, 중간 12, 낮음 6):
  - 사람 결정 반영: H1 형식 선언 맥락 줄을 임베딩 입력·키워드 텍스트에 붙이고 요약 청크는 독립 검색 대상으로 고침(US1·US2, FR-021, Assumptions).
    H2 코드 청킹 켜기 설정 기본 꺼짐(US6, FR-030, SC-011). M12 작은 청크 규칙은 plan 측정 뒤 결정(Assumptions). M11 코드 자료원 등록·결정 기록(US7, FR-032~035, SC-013), 비밀값 SC(SC-009).
  - 작성 세션 수정: M1 Android 판정을 Android import가 있는 파일·상위 클래스로 한정(FR-024, US4, SC-007). M2 멤버 문서 주석은 요약을 바꾸지 않음(FR-011, Edge Cases).
    M3 본문 수정 시나리오에 "시그니처 줄이 아닌 줄" 전제, 한 줄 본문 선언은 Edge Cases. M4 청크 종류 목록 하나와 심볼 경로 표(FR-020, FR-023). M5 구문 해석 실패 판정·해석기 버전을 버전 재료로(FR-019, FR-027, SC-010).
    M6 문서별 버전 비교와 실행 기록(FR-029). M7 심볼 이름에 매개변수 형식(FR-020, SC-006). M8 코드 상한 ≤ Context 예산(FR-016). M9 모든 원문 청크의 상한 초과 나누기 규칙(FR-017, US5).
    M10 키워드 규칙은 그대로, 입력과 대응표 갱신 명시(FR-022). L1 닫는 줄 위치(US1-1, SC-004). L2 파일 요약 심볼·순서·범위(FR-012, FR-014). L3 테스트 판정 경로만, Kotest 제외(FR-025).
    L4 어노테이션·시그니처의 매개변수 어노테이션 처리(FR-023, US3-1). L5 문서 제목(FR-008). L6 BOM·외부 호출 0 SC(SC-001, SC-009).
  - 모든 항목 통과. 같은 검토자의 재검토 대기.
- 3차 점검(2026-10-26, 같은 검토자 재검토 "변경 요청" 반영. 이전 20건 해소 18·부분 해소 2, 새 지적 높음 1·중간 2·낮음 6):
  - 사람 결정 반영: N1 자료원별 식별은 별도 명세로 넘기고 활성화 선행 조건으로 적음(FR-036, FR-035, US7-4, SC-013, Assumptions). N3 스키마가 바뀌면 `meta-v1` 올림,
    마이그레이션·새 버전은 켜는 변경에 함께(FR-026·028·030, US6-1, SC-011). N2 맥락 줄 바깥부터 덜어 내고 경고(FR-018, FR-021, FR-027, US5-6, SC-005, Key Entities).
  - 작성 세션 수정: N4 확장 함수 수신 형식과 매개변수 정규화(FR-020, US3-2). N6 상한을 예산보다 여유 있게(FR-016). N7 US5-1 문구. N8 해석기 지원·Android import 없는 후보 측정(Assumptions).
    N9 TASK.md 낡은 문구와 이 파일의 SC 번호. L6 원본 쓰기·저장 호출 0(SC-009). US7-2 범위 겹침 확인 방법은 plan으로.
  - 모든 항목 통과. 재검토는 다시 받지 않았다.
- 4차 점검(2026-10-26, plan 측정 뒤 사용자 결정으로 FR-010·013·021 개정): 형식 머리와 첫 필드 묶음 합치기, 본문 있는 멤버가 없는 형식의 요약 생략, 패키지 중복 제거.
  US2-5를 고치고 US2-6을 더했으며 Assumptions(작은 청크)를 측정 결과로 바꿨다. 국소성(SC-003)과 원문 줄 덮기(SC-002)는 그대로다. 모든 항목 통과. spec 재승인 대상이다.
- 5차 점검(2026-10-26, plan 독립 검토 반영):
  - 바꾼 것: M1 요약 생략 규칙에 중첩 형식을 넣고 파일 요약에도 적용(FR-013·014, 도입부·US2·Edge Cases 문장 조건부). M2 켜짐 방지(FR-026·030, US6-5, SC-011).
    M8 함수 형식 매개변수(FR-020). L2 형식 머리와 요약 중복 수용(Assumptions). L3 경로 구성 요소 경계(FR-021). L4 비율 분모(Assumptions). 비용 추정을 측정값으로 고침.
  - 모든 항목 통과. spec 재승인 대상이다.
- 6차 점검(2026-10-26, plan 재검토 N4 반영): US2-4 Given에 블록 본문 함수, Edge Cases 형식 문서 주석 사례를 요약이 있을 때로 한정. 모든 항목 통과. spec 재승인 대상이다.
