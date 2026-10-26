# Decision Record: ADR-024 Discord 중계 Worker를 TypeScript로 옮긴다

> Created at: `2026-10-27`
> Jira 이슈: `https://tkv123.atlassian.net/browse/SCRUM-115`
> 기능명세서 ID: `QK-BOT-001` (research R-13 대안, tasks.md "H04 일부 측정")
> Status: Proposed
>
> ADR-022의 구조(Worker는 서명 검사·중계만, 검색·생성은 OCI 질의 서비스, Workers VPC + Tunnel)는 그대로다. 바뀌는 것은 Worker 구현 언어뿐이다.

## Context

- ADR-022와 research R-13은 Worker를 Python Workers(`pywrangler`)로 두고, M-02에서 Worker CPU가 Free 한도(요청당 10 ms)를 자주 넘으면 중계만 TypeScript로 옮긴다고 정했다.
- H01(2026-10-26)과 H04 일부(2026-10-27)에서 Python Worker의 `/ask` 중계 요청 23건이 모두 10 ms를 넘었다(p50 31 ms, p95 167 ms, 최대 250 ms). 서명 검사만 하는 PING도 8 ms였다.
- Cloudflare 문서상 가끔 넘는 것은 허용하지만 꾸준히 넘으면 Error 1102(`exceededCpu`)로 끊는다. 끊기면 Worker의 대체 안내도 나가지 않고 Discord에 "응답하지 않음"이 뜬다.
- Worker가 하는 일은 서명 검사, 본문 그대로 중계, 시작 확인 보내기뿐이다. 도메인 코드는 질의 서비스(Python)에 있다.

## Decision

Discord 중계 Worker를 npm 의존성 없는 TypeScript(`workers/relay/`)로 다시 쓰고, Python Worker 겉껍질(`query/worker.py`)과 Worker 전용 판단(`discord/relay.py`)을 지운다.

## Rationale

- **CPU 한도.** JS Worker는 Pyodide 기동과 Python↔JS 변환이 없어 요청당 CPU가 크게 줄 것으로 본다 `(추론)`. 운영 CPU는 재배포 뒤 H04로 다시 잰다.
- **작은 이전 범위.** 옮길 것은 이전 `discord/relay.py`(약 90줄)와 `query/worker.py`(약 140줄)의 계약뿐이다. 질의 서비스와 검색·생성 계약은 바뀌지 않는다.
- **의존성 없음.** 런타임 표준 API(Web Crypto Ed25519, `fetch`, `AbortSignal.timeout`)만 쓴다. 시험은 Node 내장 `node --test`와 타입 제거 실행으로 돌려 `package.json`·잠금 파일이 없다.
- **같은 계약.** 이전 Python 계약 시험의 기대값을 TS 시험으로 옮기고, Worker 진입점을 실제 Ed25519 서명과 가짜 VPC 바인딩·`waitUntil`로 끝까지 돌린다.

## Alternatives considered

| Alternative | Advantages | Disadvantages | Reason not selected |
| --- | --- | --- | --- |
| Python Worker 안에서 줄이기 | 언어가 하나로 남는다 | 서명 검사만 해도 8 ms라 10 ms 안을 보장하기 어렵다 `(추론)`. 새 isolate 기동 비용(108~250 ms)은 코드로 줄이기 어렵다 | 한도 안을 보장하지 못한다 |
| Workers Paid | 코드 변경 없음. CPU 한도 30초 | 월 고정비. ADR-008 "추가 고정비 월 0원"을 고쳐야 하고 사람 승인(C-05)이 필요하다 | 비용 원칙과 충돌 |
| TS + vitest·Workers 풀 | workerd에서 시험한다 | npm 의존성·잠금 파일이 생긴다 | 계약이 작아 Node 내장 시험으로 충분하다. 실제 런타임은 `wrangler dev`와 배포로 확인한다 |
| Python Worker 유지 + TS 병행 | 되돌리기 쉽다 | 같은 계약의 구현이 둘이라 어긋날 수 있다 | 사용자 결정(2026-10-27)으로 하나만 둔다 |

## Evidence

- Workers 한도(CPU는 실행 시간만 셈, 네트워크 대기 제외, 꾸준히 넘으면 1102·`exceededCpu`, isolate별 약간의 여유): https://developers.cloudflare.com/workers/platform/limits/ (조회 2026-10-27)
- H01·H04 일부 측정 조건과 수치: `specs/QK-BOT-001-discord-ask/tasks.md` "H01 배포 확인", "H04 일부 측정"
- 로컬 확인(2026-10-27, wrangler 4.149.0, 로컬 workerd 호환 날짜 2026-10-13, 합성 Ed25519 키, 외부 호출 0): `/healthz` 200, 서명 없음·잘못된 서명 401, 서명된 PING `{"type":1}`,
  바인딩 없는 `/ask` → 대체 안내와 `{"kind":"relay_failed","error":"TypeError"}`

## Data and cost

- 외부로 전송되는 데이터: ADR-022와 같다. 언어만 바뀌고 Worker가 보는 데이터와 기록 항목(결과 종류·경과 시간·예외 이름)은 같다.
- 무료 한도와 예상 사용량: Workers Free 안. 재배포 뒤 요청별 CPU가 10 ms 안인지 다시 잰다. Neurons 영향 없음.
- 교체 시 영향: 인덱스 버전·임베딩 변경 없음. 개발 의존성 `workers-py`와 그 의존성 제거(`uv.lock` 패키지 항목 24개 → 16개).

## Consequences

### Positive

- Worker CPU 한도 초과로 Discord가 "응답하지 않음"을 띄울 위험이 줄어든다(재측정으로 확인).
- Worker 기동이 빨라진다(Python 기동 681 ms가 없어진다).

### Negative / risks

- 저장소에 언어가 하나 늘었다. CI에 Node 시험 단계가 더해졌다.
- 타입 검사(`tsc`)를 하지 않는다. 형식 오류는 시험과 `wrangler` 번들, 배포 확인으로 잡는다.
- Python 설정 레지스트리의 `relay` 진입점 규칙(공개 키 형식, 제한 시간 0.5~2.8초)을 TS가 따로 구현한다. 규칙을 바꿀 때 두 곳을 함께 고친다.

## Revisit conditions

- 재배포 뒤에도 Worker CPU가 10 ms를 자주 넘을 때: Workers Paid나 다른 진입점을 다시 본다.
- 중계 로직이 커져 타입 검사가 필요해질 때: `tsc`와 Workers 타입을 더한다.

## Approval

- Approvers:
- Approved at:
