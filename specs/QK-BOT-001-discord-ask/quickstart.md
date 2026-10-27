# Quickstart: QK-BOT-001 Discord `/ask` 검증

명령 형식과 응답은 [contracts/](contracts/)를, 값의 뜻은 [data-model.md](data-model.md)를 본다. 비밀값과 주소는 placeholder로 쓴다.

## 1. 자동 검증 (외부 호출 0건)

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
```

기대 결과:

- 가짜 서명 키로 만든 요청, 가짜 Discord 수신부, 가짜 검색·생성 제공자로 SC-003~SC-009, SC-011, SC-013(가짜 시험 부분)이 통과한다.
- 로컬 DB 시험에서 `qk_query` 역할로 검색·사용량 기록·오늘 합계는 되고, data-model 4절의 거부 목록(쓰기·지우기, 기존 행 `UPDATE`, daily 쓰기, 예약·정산·정리 함수, `qk.sync_*`, 스키마 변경)은
  모두 권한 거부다(SC-010 로컬 부분).
- 설정 검사 시험에서 기본 설정은 통과하고, 출처 목록 산식·마감 교차 규칙을 어기는 설정은 거부된다.
- 실패 주입 시험(가짜 시계·가짜 수신부)으로 다음을 확인한다.
  - 중계·시작 확인: 시작 확인이 오면 실행, 안 오면 `NOT_STARTED` 안내로 첫 메시지 갱신·검색 0회, 서명 불일치·만료·중복 시작 확인은 `409`, 첫 `PATCH`가 `404`면 1초 뒤 1회만 다시 보냄.
  - 자리·마감: 실행 자리 2개가 늦게 끝나는 작업으로 차 있어도 동시 검색·생성이 2개를 넘지 않음, 대기 작업의 최소 시작 시간 미달은 시간 초과 안내, 결과와 시간 초과 안내 중 한 번만 전달.
  - 검색 마감 주입: 임베딩 시간 제한이 남은 시간 안, 남은 시간이 모자라면 재시도 대기 없이 시간 초과, 검색 호출 전 남은 시간 부족이면 저장소 질의 0회, 마감 동안 오래 걸리는 질의(로컬 DB
    `pg_sleep`)는 연결 취소로 시간 초과, 검색 요약의 외부 호출 수가 실제 저장소 질의 수와 같고 상한 7 이하, 남은 시간 7초 미만이면 생성 0회.
  - 늦게 끝난 생성의 사용량 기록이 남고 DB 연결이 닫힘.

## 2. 로컬 질의 서비스 확인 (외부 호출 0건)

`qk-query serve`는 실제 검색·생성·Discord 전송을 조립하고 가짜 제공자 선택이 없다. 시작 확인을 보내지 않아도 시작 대기 뒤 실제 Discord로 갱신을 보내므로, 로컬에서 `serve`를 띄워
확인하지 않는다(2026-10-26 사용자 결정). 실제 루프백 HTTP 경로는 `make_server`가 만든 서버에 가짜 검색·생성·Discord 전송을 주입한 시험이 확인한다.

```bash
.venv/bin/python -m pytest tests/unit/query/test_bot_http_integration.py tests/unit/query/test_bot_first_response.py tests/unit/query/test_bot_start_confirm.py
uv run qk-query register-commands --env-file <합성 애플리케이션·서버 ID만 둔 env> --dry-run
```

- 시험용 서명 키로 서명한 연결 확인 요청을 `POST /discord/interactions`로 보내면 `{"type": 1}`.
- 허용 채널의 `/ask` 요청이면 `{"type": 5}`와 응답 헤더 `X-QK-Run`이 바로 온다. 이어서 같은 서명 헤더로 `POST /discord/interactions/start`(`{"run_id": …}`)를 보내면 `204`가 오고, 가짜 Discord
  전송에 갱신 메시지가 도착한다. Neurons 0.
- 시작 확인을 보내지 않으면 시작 대기(기본 5초) 뒤 가짜 전송에 "요청을 처리하지 못했습니다…" 안내 하나만 오고 검색·생성 호출은 0회다(`NOT_STARTED`).
- `register-commands --dry-run`은 봇 토큰 없이 보낼 JSON만 출력하고 호출하지 않는다(contracts/discord-outbound.md 2절).
- `test_bot_http_integration.py`는 실제 `ThreadingHTTPServer`와 HTTP 요청으로 위 경로와 서명 오류 `401`을 확인한다. 나머지 두 시험은 단위 경계 확인이다. 이전의 `test_bot_server_runtime.py`는 서버를 모킹하므로 루프백 통합 증빙이 아니다.
- 루프백 시험은 Codex 샌드박스 안에서는 권한 오류로 실패한다. 샌드박스 밖에서 돌린다.

## 3. 운영 구성 (사람 단계, 명령마다 승인)

전제(모두 끝나야 1번을 시작한다):

- spec·plan·ADR-022 승인, 팀원(인스턴스 관리자) 동의(PR 리뷰).
- Cloudflare Tunnel 요금 확인과 Worker·Tunnel 트래픽의 데이터 처리 정책(보존, 학습 사용) 확인을 ADR-022 Data and cost에 URL과 함께 기록(C-05, AGENTS.md 3.1).
- 인스턴스에서 바깥 방향 UDP 7844(QUIC)를 쓸 수 있는지 읽기 전용으로 확인(OCI 보안 목록 egress, 호스트 방화벽). 막혀 있고 열 수 없으면 진행하지 않고 ADR-022 Revisit으로 돌아간다.

1. Cloudflare 대시보드에서 원격 관리 터널을 만들고, 인스턴스에 `cloudflared`(2025.7.0 이상)를 서비스로 설치한다. 터널 토큰은 서버에만 둔다.
2. 운영 DB에 마이그레이션 0007을 적용하고, `qk_query`에 `LOGIN`과 암호를 숨김 입력으로 정한다. 새 마이그레이션은 코드가 `main`에 들어가기 전에 적용한다(운영 문서 규칙).
3. 질의 서비스 전용 Workers AI 토큰을 발급하고 `/etc/qello-knowledge/query.env`(root:qkquery, 0640)를 숨김 입력으로 만든다.
4. 전용 사용자 `qkquery`와 `qk-query.service`를 설치하고 켠다. `systemd-analyze verify`, `systemctl status`, 루프백 `GET /healthz`.
5. Workers VPC Service(대상 `127.0.0.1:<포트>`, 터널 ID)를 만들고, Worker를 배포한다(`npx wrangler deploy`, TypeScript 중계 ADR-024). Worker 비밀값·변수는 `DISCORD_PUBLIC_KEY`, `QK_RELAY_TIMEOUT_SECONDS`.
6. Discord 개발자 포털에 Interactions Endpoint URL을 넣는다. 저장할 때 Discord의 서명 확인을 통과해야 한다(M-01).
7. 로컬에서 `qk-query register-commands --env-file .env`로 `/ask`를 서버에 등록한다(봇 토큰은 로컬 `.env`에만).
8. 인스턴스 공인 주소로 DB 포트와 질의 서비스 포트에 접속이 안 되는지 확인한다(SC-010).

되돌리기: Interactions Endpoint URL을 지우고, `qk-query.service`와 `cloudflared`를 끄고 지운다. `query.env`를 지운다. `qk_query`의 `LOGIN`을 뺀다. 색인 동기화(`qk-sync`)에는 영향이 없다.

## 4. 실측 (사람 단계)

| 단계 | 내용 | 비용 |
| --- | --- | --- |
| M-01~M-03 | research R-15. 연결 확인·허용 밖 채널 요청으로 Worker CPU·첫 응답 시간을 잰다 | 0 Neurons |
| M-04 | 질문 세트 10~12개(자료로 답할 수 있는 질문, 자료에 없는 질문, "나만 보기" 1개 이상)로 SC-001·SC-002·SC-012·SC-013을 기록한다. 합성 비밀값 질문으로 SC-005 화면 대조를 한다 | 약 500~610 Neurons. 실행 전 예상량 보고와 사람 확인 |

기록 위치: `specs/QK-BOT-001-discord-ask/tasks.md` "실행 기록". 화면 기록은 값을 가린다. 조건(날짜, 질문 세트, 모델, 프롬프트 버전, 인덱스 버전, 색인 시점, 실행 방식)을 붙인다(spec FR-025).
