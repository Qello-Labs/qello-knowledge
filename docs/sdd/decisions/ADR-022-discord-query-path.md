# Decision Record: ADR-022 Discord 질의 경로를 Worker 중계와 OCI 인스턴스 질의 서비스로 나눈다

> Created at: `2026-10-25`
> Jira 이슈: `https://tkv123.atlassian.net/browse/SCRUM-115`
> 기능명세서 ID: `QK-BOT-001` (research R-01·R-02·R-07·R-08·R-12·R-14)
> Status: Accepted
>
> ADR-008의 "질의응답은 Cloudflare Workers에서 실행한다"를 일부 고친다. ADR-008의 저장 위치(OCI 공유 인스턴스)와 추가 고정비 상한(월 0원)은 그대로다.

## Context

- ADR-008은 질의응답을 Cloudflare Workers에서 실행하고, Workers 질의 경로의 DB 연결 방식은 QK-BOT-001에서 정한다고 했다(ADR-008 확정 사항).
- 운영 DB는 OCI 공유 인스턴스의 `127.0.0.1:5432`에서만 받는다. 인스턴스는 22번 포트만 연다(ADR-008, ADR-020).
- 검색(QK-RET-001)과 생성(QK-GEN-001)은 동기 코드다. 저장소는 `psycopg`, Workers AI는 `urllib`로 부른다. 인스턴스에서는 이 조립이 `qk-index ask`로 이미 돈다.
- Python Workers에서는 이 코드가 그대로 돌지 않는다 `(추론)`. 동기 코드에서 비동기 `fetch`를 기다리는 방법(JSPI)이 Workers에서 되는지는 미확인이다.
- Workers의 응답 뒤 계속 처리는 30초까지다. 생성은 재시도까지 기본 45초가 걸릴 수 있다. Workers Free CPU는 요청당 10 ms이고, Python Worker 기동 CPU는 재지 않았다.
- Discord는 상호작용에 3초 안의 첫 응답을 요구하고, 상호작용 토큰은 15분 동안 메시지를 고치거나 더할 수 있게 한다.

## Decision

Cloudflare Worker는 Discord 상호작용의 서명 검사와 중계만 하고, 허용 범위·비밀값 검사와 검색·생성·답변 갱신은 OCI 공유 인스턴스의 질의 서비스가 하며, 둘은 Workers VPC Service 바인딩과
Cloudflare Tunnel로 공인 포트·공개 호스트명 없이 잇는다.

## Rationale

- **기존 코드 재사용.** 질의 서비스는 `qk-index ask`와 같은 부품으로 검색과 생성을 잇는다. 검색·생성 계약을 바꾸지 않는다.
- **실행 시간.** 질의 서비스는 실행 시간 제한이 없다. 생성 기본값(시간 제한 20초, 마감 45초)을 그대로 쓰고, 질의 마감 55초·안내 전달 마감 60초를 Discord 15분 안에 둔다.
- **CPU 위험 축소.** Worker는 서명 검사와 질의 서비스 호출 최대 2회(중계, 응답 뒤 시작 확인)만 한다. Free CPU 한도를 넘으면 중계만 TypeScript로 옮기면 된다.
- **DB 연결 단순화.** 질의 서비스는 같은 인스턴스의 DB에 `localhost`로 붙는다. PostgREST나 Hyperdrive 같은 HTTP·연결 중개 계층이 필요 없다.
- **노출 최소화.** 터널은 인스턴스에서 Cloudflare로 나가는 연결만 쓴다. 질의 서비스는 `127.0.0.1`에서만 받는다. 공개 주소는 Worker의 `workers.dev`뿐이라 도메인이 필요 없다.
- **장애 안내.** 질의 서비스에 닿지 않으면 Worker가 질문자만 보는 안내를 보낸다.

## Alternatives considered

| Alternative | Advantages | Disadvantages | Reason not selected |
| --- | --- | --- | --- |
| 전부 Workers(ADR-008 원안) | 인스턴스에 상주 구성 요소가 늘지 않는다. Workers AI를 바인딩으로 불러 운영에 REST 토큰이 없다 | 비동기 어댑터와 DB 중개(Hyperdrive + `asyncpg` 또는 VPC → PostgREST)가 필요하다. 동기 서비스를 부르는 방법이 미확인이라 검색·생성 비동기화(계약 변경)가 생길 수 있다. 30초를 넘기려면 Queue 소비자가 필요하다. Python CPU 위험이 가장 크다 | 공수와 미확인이 가장 크다 |
| 인스턴스 단독(Tunnel 공개 호스트명으로 Discord 직접 수신) | 구성 요소가 가장 적다 | Cloudflare에 등록된 도메인이 필요하다(팀 보유 미확인). 공유 인스턴스가 공개 엔드포인트를 직접 받는다. 인스턴스 장애 때 Discord 기본 실패 표시만 보인다 | 도메인 미확인, 노출과 장애 안내 |
| Worker 중계 + Tunnel 공개 호스트명 + Access 서비스 토큰 | 정식 출시된 기능만 쓴다 | 도메인이 필요하다. 서비스 토큰이라는 비밀값이 Worker에 하나 더 생긴다 | Workers VPC가 도메인 없이 같은 일을 한다. 베타 조건이 바뀌면 이 안으로 옮긴다(Revisit) |

## Evidence

조회일은 모두 2026-10-25다.

- Workers Free 한도(CPU 10 ms, 외부 호출 50, `waitUntil` 응답 뒤 30초, Queue 소비자 15분): https://developers.cloudflare.com/workers/platform/limits/
- Workers VPC(Free·Paid 플랜, 베타 동안 무료, VPC Service HTTP·TCP): https://developers.cloudflare.com/workers-vpc/
- VPC Service 설정(`ipv4: 127.0.0.1`, `tunnel_id` 예시): https://developers.cloudflare.com/workers-vpc/configuration/vpc-services/
- Tunnel(나가는 연결만, 인바운드 규칙·공인 IP 불필요, Workers VPC에는 ingress 불필요, QUIC·UDP 7844 필요, `cloudflared` 2025.7.0 이상): https://developers.cloudflare.com/workers-vpc/configuration/tunnel/
- Workers VPC 요금(베타 동안 무료): https://developers.cloudflare.com/workers-vpc/platform/pricing/
- Workers Web Crypto Ed25519 `verify` 지원: https://developers.cloudflare.com/workers/runtime-apis/web-crypto/
- Discord 상호작용(3초, 15분, 지연 응답 플래그, 공개 범위 변경 불가, 웹후크 경로): https://docs.discord.com/developers/interactions/receiving-and-responding
- Python Workers 정식 출시(2026-09-21): https://blog.cloudflare.com/python-workers-ga/
- 기존 조립: `src/qello_knowledge/indexer/ask_cli.py`(`postgres_ask`)

## Data and cost

- 외부로 전송되는 데이터:
  - Discord → Worker → 질의 서비스: 상호작용 본문(질문 원문, 서버·채널·사용자 정보)이 Cloudflare 네트워크(Worker, 터널)를 지난다. Worker와 질의 서비스는 이 본문을 저장하지 않고,
    운영 로그에는 원문과 사용자 정보를 남기지 않는다(spec FR-021).
  - 질의 서비스 → Workers AI: 질문과 Context 청크 본문(ADR-009와 같다). 질의 서비스 → Discord: 답변 본문과 출처 링크.
- 데이터 처리 정책(학습 사용·보존), 확인한 것과 못 한 것을 나눈다.
  - 확인함: Workers AI 입력·출력은 학습에 쓰지 않는다고 Cloudflare가 밝힌다(ADR-009 Data and cost, 그 기록의 출처).
  - 미확인: Worker와 Tunnel을 지나는 상호작용 본문(질문 원문, 서버·채널·사용자 정보)에 대한 Cloudflare의 보존 기간과 학습 사용 여부. 같은 계정 약관을 따른다는 것은 추론이다.
  - 닫는 방법: 운영 구성 전에 Cloudflare의 데이터 처리 부속서(DPA)·개인정보 문서에서 Workers 요청 본문과 Tunnel 트래픽의 처리·보존·학습 사용 문장을 찾아 이 절에 URL과 함께 적는다. 이 확인은
    운영 구성의 전제다(QK-BOT-001 quickstart 3절). 학습 사용이나 장기 보존이 확인되면 이 결정을 다시 본다.
- 무료 한도와 예상 사용량: Workers Free 하루 100,000 요청 안(하루 질문 50건 × 요청 1~2개). Workers VPC는 베타 동안 무료. Cloudflare Tunnel은 "모든 플랜에서 사용 가능"하다고 적혀 있으나
  요금 문장은 찾지 못했다(https://developers.cloudflare.com/tunnel/) `(미확인, 구현 전 확인. 유료면 C-05에 따라 사람 승인)`. Workers AI 사용량은 질의당 약 38~51 Neurons로 바뀌지 않는다(QK-GEN-001).
- 비밀값: 질의 서비스 전용 Workers AI 토큰과 DB 역할 `qk_query` 암호, 터널 토큰을 인스턴스에만 둔다. 봇 토큰은 서버에 두지 않는다(명령 등록은 로컬에서 사람이 한다).
- 교체 시 영향: 인덱스 버전·임베딩 변경 없음.

## Consequences

### Positive

- 검색·생성 계약을 바꾸지 않고 Discord 창구를 연다.
- 생성 시간과 Workers CPU 한도의 충돌이 사라진다.
- 인스턴스에 공인 포트를 새로 열지 않는다.

### Negative / risks

- ADR-008의 "운영에서 Cloudflare REST 토큰을 들고 있지 않는다"는 장점이 사라진다. 질의 서비스 전용 토큰으로 범위를 줄인다.
- 공유 인스턴스(회의 봇과 같이 씀)에 상주 구성 요소(질의 서비스, `cloudflared`)가 늘어난다. 팀원(인스턴스 관리자) 동의가 필요하다. 인스턴스는 이미 DB의 단일 장애점이다.
- Workers VPC는 베타다. API나 가격이 바뀔 수 있다.
- 질의 서비스 메모리 안의 중복 판정 상태는 다시 시작하면 사라진다(QK-BOT-001 research R-10).
- Workers VPC 터널은 QUIC와 바깥 방향 UDP 7844를 요구한다. `http2`로 바꾸는 대안은 없다. 인스턴스에서 열 수 없으면 이 결정을 다시 본다(Revisit).
- VPC 바인딩은 지정한 대상으로만 보내지만, 다른 Worker에 같은 VPC Service를 바인딩할 수 있는 계정 권한까지 막지는 않는다. 그래서 질의 서비스가 Discord 서명을 다시 검사한다(QK-BOT-001
  research R-04). VPC Service 생성·바인딩 권한(Connectivity Directory Admin·Bind)은 운영 담당자에게만 둔다.

## Revisit conditions

- Workers VPC 정식 출시 뒤 Free 플랜에서 유료가 되거나 조건이 바뀔 때, 또는 인스턴스에서 바깥 방향 UDP 7844를 열 수 없을 때: Tunnel 공개 호스트명 + Access 서비스 토큰 안으로 옮긴다
  (도메인 확보 필요).
- Worker·Tunnel 트래픽의 데이터 처리 정책 확인(Data and cost)에서 학습 사용이나 장기 보존이 드러날 때.
- 인스턴스를 옮기거나 회의 봇과 분리할 때.
- 하루 질문이 크게 늘어 질의 서비스 동시 처리(작업자 2)가 부족할 때.
- Python Workers에서 동기 코드를 그대로 쓸 수 있게 되거나, 검색·생성을 Workers로 옮길 이유(인스턴스 부하, 가용성)가 생길 때.

## Approval

- Approvers: PR #64 리뷰어 tkv00(팀원, OCI 계정 소유자·인스턴스 관리자. ADR-008·ADR-020 Approval의 역할 기록)
- Approved at: 2026-10-26 PR #64 리뷰 승인(APPROVED, [마지막 승인 기록](https://github.com/Qello-Labs/qello-knowledge/pull/64#pullrequestreview-5649650760)).
  PR 본문에서 요청한 ADR-008 일부 개정과 공유 인스턴스 구성 요소(`qk-query.service`, `cloudflared`, 전용 사용자 `qkquery`, DB 역할 `qk_query`) 추가 동의를 이 승인으로 기록한다.
  운영 구성 전 Data and cost의 미확인 항목을 닫는 조건은 유지한다. 이 세션은 사람의 리뷰를 기록하며 결정을 스스로 승인하지 않는다.
