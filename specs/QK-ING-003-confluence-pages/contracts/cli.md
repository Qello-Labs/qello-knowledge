# Contract: 명령

근거: [research.md](../research.md) R-10, R-12, R-17

## `qk-index sources check`

Confluence 자료원의 범위 값·설정 항목·확인 기록·켜짐 인덱스 버전 검사(contracts/source-config.md)를 더한다. 원본과 저장소를 부르지 않는다.
비활성 자료원은 지금처럼 범위 값을 파싱하지 않는다(GitHub 동작 그대로).

## `qk-index run [--preview] [--source <이름>]`

- 원본 호출 전 검사에 Confluence 켜짐 인덱스 버전 대응표 검사를 더한다(실패하면 원본 요청 0건, 저장소 쓰기 0건).
- 활성 Confluence 자료원은 종류별 팩토리로 조립한다. 같은 종류 둘 이상은 지금처럼 `duplicate_source_kind`로 멈춘다.
- `--preview`도 사라진 페이지 단건 확인(`GET`)을 보낸다. 미리 보기는 저장소에 쓰지 않는다.
- 요약에 data-model 10절 값을 더한다.

## `qk-dev source measure --name <이름> [--chunk] [--json]`

- 종류 제한을 없애고 종류별 어댑터·전송을 쓴다. Confluence는 비활성 자료원도 잴 수 있다(확인 기록 필수, 저장·임베딩 없음). 측정 준비가 그 자료원 하나만 활성처럼 범위를 파싱하고
  확인 기록을 대조한다(research R-17). GitHub는 지금처럼 활성 자료원만 잰다.
- Confluence 출력: 요청 수(엔드포인트 종류별), 소요 시간, 목록 완전성, 페이지 수, 본문 총·최대 바이트, 판정별 수, 규칙별 수, 미분류 수, 변환 경고 종류별 수, 조회 실패 수,
  `--chunk`이면 청킹 요약과 예상 Neurons(캐시 전 상한). 페이지는 ID로만 가리키고 제목·제목 경로·링크·본문·이름은 내지 않는다(FR-027, SC-004).
- 실제 원본을 부르는 사람 전용 명령이다. 기본 검증에서는 재생 전송으로만 시험한다.

## plan 실측 스크립트(선택, 사람 실행)

`uv run python specs/QK-ING-003-confluence-pages/measurement/measure_confluence.py --space-key SCRUM`. 스페이스 종류, 엔드포인트별 상태 코드(토큰 범위),
트리 구조, 매크로·노드 분포를 켜기 전에 알고 싶을 때만 쓴다. 2026-10-28에는 보류했다.
