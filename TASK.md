# Task Contract: QK-BOT-001 운영 게이트·실측 기록 (H00~)

> Generated at: `2026-10-26`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-115` / https://tkv123.atlassian.net/browse/SCRUM-115 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: `QK-BOT-001` / `specs/QK-BOT-001-discord-ask/`(구현은 PR #64로 병합)
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#58`
- Branch: `docs/SCRUM-115-gh-58-discord-ask-ops`
- Base branch: `main`. 2026-10-26 `origin/main` `3a5a98e`(#65 병합)에서 분기했다
- 이전 계약: `e07351f`의 `TASK.md`(QK-BOT-001 명세·구현). `main`의 직전 계약(QK-CHK-001, `3a5a98e`)은 git 이력에 남긴다

## Objective

- #58의 남은 완료 조건(허용 채널 `/ask` 실측)으로 가는 사람 단계 가운데 H00 운영 게이트를 닫고 근거를 기록한다(`specs/QK-BOT-001-discord-ask/tasks.md` 사람 단계).
- H01(M-01): 시험 질의 서비스(연결 확인만 응답)로 Tunnel·Workers VPC Service·Worker 배포와 Discord 수신 주소 등록을 해 Python Worker의 미확인 런타임 API를 확인한다
  (요청 본문·Web Crypto 서명 검사·VPC 바인딩 `fetch`·`waitUntil`·`[[vpc_services]]` 설정·`pywrangler` 번들). 2026-10-26 사용자 요청으로 범위에 더했다.
- H02 이후(실제 질의 서비스 구성·실측)는 H01 결과를 보고 사람이 이 계약에 더한다.

## Scope

- `TASK.md`
- `docs/sdd/decisions/ADR-022-discord-query-path.md`: Data and cost의 미확인 항목(Tunnel 요금, Worker·Tunnel 트래픽의 보존·학습 사용)과 UDP 7844 확인 결과
- `docs/sdd/research/tokens.md`: 질의 서비스 전용 토큰 `qk-workers-ai-query-prod` 행과 확인 결과(값·계정 ID 없음)
- `specs/QK-BOT-001-discord-ask/tasks.md`: 사람 단계 H00 상태와 실행 기록, T061 체크 정리
- `docs/ops/oci-production-store.md` 7절: H00·H01 확인으로 절차 문장을 고쳐야 할 때만
- H01 시험 질의 서비스 `specs/QK-BOT-001-discord-ask/measurement/h01_probe.py`(새 파일, 표준 라이브러리와 서명 재검사용 시스템 `python3-cryptography`): `127.0.0.1:8787`에서 Worker 중계 요청에 연결 확인 응답만 한다.
  검색·생성·DB·Workers AI를 부르지 않고, 본문·토큰을 기록하지 않는다. 시작 확인 뒤 Discord에 원 메시지 갱신 1회만 보낸다
- H01 운영 변경(사람이 인증하고 명령마다 승인. 2026-10-26 사용자 요청으로 더함):
  - 로컬: `pywrangler dev`로 Worker 기동·`/healthz`·서명 오류 401 확인(외부 호출 없음)
  - Cloudflare(Qello 전용 계정): 원격 관리 터널 1개, Workers VPC Service 1개, Worker `qello-knowledge-relay` 배포와 비밀값 `DISCORD_PUBLIC_KEY`. Workers Logs는 기본값 유지(H00 결정)
  - 공유 인스턴스: `cloudflared` 설치와 서비스(터널 토큰은 root 전용 파일에 숨김 입력), 시험 질의 서비스의 임시 실행(`systemd-run`, 비특권 사용자, H01 끝나면 중지)
  - Discord(`Qello Knowledge` 애플리케이션): Interactions Endpoint URL 등록, 서버 한정 `/ask` 명령 등록(`register-commands`, 먼저 `--dry-run`. 봇 토큰은 사용자 로컬 `.env`)
  - 시험 채널에서 `/ask` 소수 호출로 중계·시작 확인 경로 확인, Workers Logs에 요청 본문이 없는지 확인
- H01 로컬 확인으로 찾은 Worker 수정(2026-10-26 사용자 승인으로 더함):
  - `src/qello_knowledge/query/worker.py`: Python Workers SDK의 요청·응답 본문(`bytes()`), VPC 바인딩 `fetch(url, **kwargs)`, `headers.get`, `waitUntil` 프록시. 실패 로그에 예외 클래스 이름만 더함
  - `wrangler.toml`: `base_dir = "src"`

## Explicit exclusions

- 실제 질의 서비스 구성(`qkquery`, `qk-query.service`, 질의 릴리스, `query.env`, `qk_query` 로그인·암호, 전용 토큰 서버 배치)과 SC-010 외부 접속 확인은 H02·H03이다.
  OCI 보안 목록·호스트 방화벽 변경, 공개 호스트명·ingress 규칙 추가, Cloudflare 유료 기능(Argo 등) 켜기는 하지 않는다.
- `src/`(아래 Worker 수정 제외), `tests/`, 마이그레이션 변경. H01에서 더 수정이 필요해지면 멈추고 따로 묻는다.
- `wrangler.toml`의 실제 VPC Service ID는 저장소에 커밋하지 않는다(추적하지 않는 로컬 사본으로 배포).
- `AGENTS.md`, `CLAUDE.md`, `.claude/**`, constitution, 로드맵 수정. 원본 자료원에 쓰기. Jira 상태 변경.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문, 계정·터널·서비스 ID, 접속 주소, 보안 목록 OCID는 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: H00은 해당 없음(공식 문서 조회, OCI 설정 읽기 전용 조회). H01은 시험 `/ask` 상호작용 본문(시험 질문, 서버·채널·사용자 정보)이 Discord → Worker → Tunnel → 시험 서비스로 가고,
  시험 서비스가 Discord에 연결 확인 문구로 원 메시지를 갱신한다. 시험 질문에는 실제 업무 내용을 넣지 않는다
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons(Workers AI 호출 없음). Workers 요청 수십 건(Free 하루 100,000 안), Workers VPC 베타 무료, Tunnel 무료
- 인덱스 버전 변경: 없음(`iv-4c0bc4fcc642` 유지)

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `TASK.md`, `specs/QK-BOT-001-discord-ask/tasks.md`, `docs/sdd/research/tokens.md` | Byuntil | 사람 리뷰 |
| ADR-022 Data and cost 보강, 운영 문서 7절 | Byuntil | 사람 리뷰, 팀원(인스턴스 관리자) 확인 |
| H01 시험 질의 서비스, 공유 인스턴스의 `cloudflared`·임시 실행 | Byuntil | 사람 리뷰, 팀원(인스턴스 관리자) 확인(PR #64 동의 범위의 `cloudflared` + 임시 시험 서비스) |

## Existing user-owned changes

- 2026-10-26 `origin/main`(`3a5a98e`)에서 브랜치를 만들 때 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
```

H00 문서는 위 두 줄이 해당한다. H01 시험 서비스를 더하면 `uv run ruff check .`와 `uv run ruff format --check .`도 실행한다.

## Completion criteria

- ADR-022 Data and cost에 Tunnel 요금, Worker·Tunnel 트래픽의 보존·학습 사용 정책이 공식 문서 URL·조회일과 함께 있고, 미확인으로 남는 것은 그렇다고 적혀 있다 — 리뷰
- 인스턴스 바깥 방향 UDP 7844 사용 가능 여부가 읽기 전용 확인 결과로 기록돼 있다 — 리뷰(값 가림)
- 질의 서비스 전용 토큰의 이름·권한 범위·만료·유효 확인이 값 없이 기록돼 있다 — 리뷰
- (H01) Discord 수신 주소 등록이 서명 확인을 통과하고, 시험 채널 `/ask`가 Worker → VPC → 시험 서비스로 중계돼 연결 확인 응답과 시작 확인(204)까지 가며, 터널이 QUIC으로 붙는다.
  Workers Logs에 요청 본문이 없다 — `tasks.md` 실행 기록(값 가림)

## Decisions

- 2026-10-26 사실: PR #64가 병합됐다(`369b2ec`). #58은 열려 있고, 남은 완료 조건은 허용 채널 실측(H05)이다. 남은 사람 단계는 H00 일부(요금·데이터 처리 정책, UDP 7844, 전용 토큰)와 H01~H05다.
- 2026-10-26 사용자 결정: H00부터 시작한다. 사용자가 질의 서비스 전용 Workers AI 토큰을 이미 만들었다(값은 대화·저장소에 두지 않는다).
- 2026-10-26 사용자 결정: 이 계약 초안대로 진행한다(H00 읽기 전용 확인과 문서 기록만).
- 2026-10-26 사실: Tunnel 나가는 연결은 무료다. Worker·Tunnel 트래픽은 Self-Serve 약관·DPA의 목적 제한 조항만 있고 학습 금지 명시 문장은 없다. Workers Logs는 새 Worker에서 기본으로 켜지고 Free에서 3일 보존한다(ADR-022 Evidence).
- 2026-10-26 사용자 결정: 위 데이터 처리 수준을 받아들인다. Workers Logs는 H01~H05 동안 기본값으로 두고, H01에서 본문 미기록을 확인한 뒤 H05 뒤 `invocation_logs` 끄기를 다시 정한다.
  `wrangler.toml` 변경이 필요해지면 그때 범위에 더한다.
- 2026-10-26 사용자 결정: 전용 토큰은 `qk-workers-ai-query-prod`, Qello 전용 계정 소유, Workers AI만, TTL 365일이다. verify `active`는 사용자가 확인했다.
- 2026-10-26 사실(승인 뒤 실행, 읽기 전용): OCI 보안 목록 egress는 모든 프로토콜·`0.0.0.0/0` 허용이고 NSG는 없다. Bastion 세션(TTL 30분, 확인 뒤 삭제)으로 본 호스트 OUTPUT 정책은 ACCEPT이고,
  UDP·7844 차단 규칙이 없다(nftables accept, ufw 꺼짐). 아무 설정도 바꾸지 않았다.
- 2026-10-26 사용자 결정: H01을 진행하고 이 계약의 범위를 넓힌다(Scope "H01 운영 변경").
- 2026-10-26 사실: Worker는 Discord PING에 직접 응답하고 질의 서비스로 보내지 않는다(`discord/relay.py` `relay_plan`). VPC `fetch`와 `waitUntil`은 등록된 명령 요청이 와야 실행되므로
  H01에 `/ask` 명령 등록(quickstart 3절 7번)을 앞당겨 넣었다. 저장소에 "연결 확인만" 하는 질의 서비스 모드가 없어 시험 서비스를 따로 둔다.
- 2026-10-26 사실(H01 로컬, 외부 호출 0): 저장소 밖 사본에서 `pywrangler dev`(wrangler 4.149.0 고정, 로컬 workerd가 호환 날짜 2026-10-13까지라 로컬만 낮춤, 합성 Ed25519 키)로 Worker를 띄웠다.
  원래 코드는 번들에 `query/` 폴더만 들어가고(`base_dir` 없음), 모든 요청이 `Request.arrayBuffer` 없음으로 500이었다. VPC 바인딩은 SDK가 감싼 Fetcher라 `fetch(url, **kwargs)`만 받고,
  응답에 `arrayBuffer`·`headers.has`가 없다(SDK 소스 확인). `waitUntil`에 코루틴을 그대로 넘기던 것은 SDK ASGI 구현 꼴(프록시)로 바꿨다.
- 2026-10-26 사용자 결정: 위 수정을 위해 `worker.py`·`wrangler.toml`을 범위에 더한다. 수정 뒤 로컬 재시험: `/healthz` 200, 서명 없음·잘못된 서명 401, 서명된 PING `{"type":1}`,
  바인딩 없는 `/ask`는 대체 안내(type 4, 나만 보기)와 `relay_failed`·`error=AttributeError` 로그. VPC `fetch`와 `waitUntil`은 원격 바인딩이 있어야 해서 배포에서 확인한다.
  전체 검증(preflight·diff·ruff·`QK_REQUIRE_LOCALDB=1 pytest` 2,313 passed, 외부 2 제외) 통과. `worker.py`는 단위 시험이 가져오지 않는다.
- 2026-10-26 사실: `main`의 QK-CHK-001 계약이 `ADR-022-code-sources.md`를 만들 예정인데, ADR-022는 이미 `ADR-022-discord-query-path.md`가 쓰고 있다. 이 작업 범위 밖이라 그 작업 담당자에게 알린다.
