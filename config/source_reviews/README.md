# 자료원 범위 확인 기록

`<자료원 이름>.toml` 한 파일을 사람이 확인한 뒤 쓰고 PR로 검토한다. 에이전트는 이 파일을 대신 만들지 않는다.
이름·연락처·계정 정보는 어떤 항목에도 쓰지 않는다. 확인한 사람은 역할로 적는다.

필수 항목은 `source`, TOML 날짜 `reviewed_on`, 비어 있지 않은 `reviewer_role`·`method`, `result`, `[scope]`다.
`source`는 파일 이름(확장자 제외)과 같아야 한다. `result`는 `개인 정보 없음` 또는 `개인 정보 경로 제외함`이다.
`scope.include`·`scope.exclude`는 현재 설정과 순서까지 같아야 하고, GitHub 종류는 `scope.repo`·`scope.ref`도 같아야 한다.
`개인 정보 경로 제외함`이면 `[[moved_to_exclude]]`에 `pattern`·`reason`을 한 건 이상 적는다.
모든 `pattern`은 현재 `exclude`에 있어야 한다. 모르는 키와 타입 오류는 허용하지 않는다.

`sources check`·`run`·`source measure`는 원본 호출 전에 확인 기록을 검사한다.
기록 없음은 `REVIEW_MISSING`, 형식 오류는 `REVIEW_INVALID`, 범위 차이는 `REVIEW_SCOPE_MISMATCH`다.
포함 패턴 확장자가 보안 정책의 목록 밖이거나 판정 불가하면 비활성 자료원도 `UNKNOWN_EXTENSION`이다.
오류에는 기록 내용 값을 출력하지 않는다. 비활성 자료원은 확인 기록이 없어도 된다.

활성화는 다음 여섯 단계를 사람이 한 PR에서 검토한다([research R-13](../../specs/QK-ING-002-github-repo-source/research.md#r-13-첫-자료원-등록-fr-018)).

1. 데이터 처리 정책을 포함한 결정 기록을 쓰고 승인받는다(R-16).
2. 포함 범위의 파일을 열어 개인 정보를 확인한다.
3. `config/source_reviews/<자료원 이름>.toml`을 쓴다.
4. `config/sources.toml`의 해당 자료원을 `enabled = true`로 바꾼다.
5. `qk-index sources check` 통과를 확인한다.
6. `qk-dev source measure --name <자료원 이름>`과 해당 외부 시험을 실행하고, 측정 조건·결과·한도값 판단을 기록한다.

정확한 형식은 [확인 기록 계약](../../specs/QK-ING-002-github-repo-source/contracts/source-reviews.md)을 따른다.
