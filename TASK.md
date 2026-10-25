# Task Contract: 운영 예약 동기화 실패 알림

> Generated at: `2026-10-25`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-108` / https://tkv123.atlassian.net/browse/SCRUM-108 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: 해당 없음: 운영 구성 작업이다. ADR-020 Negative("실패 알림은 후속 작업")의 후속이다.
  로드맵 5.1 `QK-OBS-002`(Grafana 대시보드·알림)가 생기기 전까지 쓰는 최소 알림이며, 그 명세가 이 알림을 흡수하거나 대체한다
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: 해당 없음
- Branch: `chore/SCRUM-108-sync-failure-alert`
- Base branch: `main`. 2026-10-25 `origin/main` `f11e146`(#56 병합)에서 분기했다

## Objective

- 서버 systemd 예약 동기화(`qk-sync.service`)가 0이 아닌 종료 코드로 끝나면 팀이 알림을 받게 한다. 지금은 Bastion 세션으로 `journalctl`을 열어야만 실패를 안다.
- 알림 경로, 보내는 내용, 비밀값 위치를 결정 기록으로 남기고 운영 문서에 구성 절차를 적는다.
- 실패를 흉내 낸 시험으로 알림이 실제로 오는지, 성공 실행에는 알림이 없는지 확인한다.

## Scope

- `TASK.md`
- `docs/sdd/decisions/ADR-0xx-sync-failure-alert.md`(새 결정 기록, 번호는 작성 때 확인): Discord 채널 웹훅 선택과 대안(`Qello Knowledge` 봇, 메일, OCI Notifications, 헬스체크 서비스),
  보내는 필드, 비밀값 위치, 헌법 "보안" 절(`docs/sdd/constitution.md:40`) 해석
- `docs/sdd/decisions/ADR-020-scheduled-sync-systemd-timer.md`: Negative의 실패 알림 줄에 새 결정 링크만 더한다
- `docs/ops/oci-production-store.md`: 2절에 알림 스크립트·유닛·비밀값 파일 단계, 3절 자원 목록, 6절 운영 확인
- OCI 인스턴스 변경(사람이 인증하고 명령마다 승인한 것만):
  - 알림 스크립트 `/usr/local/libexec/qk-sync-notify`(root 소유, 0755)
  - 템플릿 유닛 `qk-sync-notify@.service`(oneshot, 인자로 실패한 유닛 이름을 받음)와 `qk-sync.service`의 `OnFailure=qk-sync-notify@%n.service` 한 줄
  - 알림 비밀값 파일 `/etc/qello-knowledge/notify.env`(root:root, 0600, Discord 웹훅 URL). 값은 사람이 서버에서 숨김 입력으로 넣는다

## Explicit exclusions

- `src/`·`tests/`·`pyproject.toml`·`uv.lock`·마이그레이션·`.github/workflows/` 변경. `index-sync.yml` 정리는 별도 작업이다.
- 실행이 아예 돌지 않는 경우(인스턴스 중지, 타이머 꺼짐)를 잡는 외부 감시(dead man's switch). 필요하면 결정 기록에 대안으로만 적고 별도 작업으로 한다.
- 대시보드, 지표 수집, 성공 알림·일일 요약. `QK-OBS-002` 범위다.
- `qk-sync` 실행 스크립트의 색인·정리 단계, 타이머 시각, 자원 상한 변경.
- 회의 봇 컨테이너·설정·데이터와 팀원 서비스의 알림 경로.
- `AGENTS.md`, `CLAUDE.md`, `.claude/**`, constitution, 로드맵 수정. 원본 자료원에 쓰기.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, 웹훅 URL, `.env` 값, 접속 주소, OCI 계정 식별자(OCID·테넌시·지문), 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 실패할 때만 팀 Discord 채널 웹훅으로 운영 메타데이터를 보낸다. 유닛 이름, 결과(`Result`), 종료 코드와 그 뜻(`contracts/cli.md` 3절), 시작·끝 시각, `run_id`.
  `journalctl` 원문, 문서 경로·내용, 오류 메시지 원문, 접속 주소는 보내지 않는다. 오류 원문에 비밀값이나 주소가 섞일 수 있어서다
- 예상 임베딩·생성 호출량과 무료 한도 대비: 해당 없음(Neurons 0). 시험은 색인을 돌리지 않고 알림 유닛만 실행한다
- 인덱스 버전 변경: 없음(`iv-4c0bc4fcc642` 유지)

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `TASK.md`, `docs/ops/oci-production-store.md` | Byuntil | 사람 리뷰 |
| 새 ADR, ADR-020 링크 줄 | Byuntil | 사람 리뷰(헌법 해석 승인 포함), Discord 채널 관리자 확인 |
| 서버 알림 스크립트·유닛·비밀값 파일 | Byuntil | 인스턴스 관리자(팀원) 확인 |

## Existing user-owned changes

- 2026-10-25 `origin/main`(`f11e146`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
```

운영 확인(사람 인증 뒤, 명령마다 승인):

- `systemd-analyze verify`로 바뀐 유닛 검사, `systemctl show qk-sync.service -p OnFailure`
- 알림 유닛 단독 실행(`systemctl start qk-sync-notify@qk-sync.service.service`)으로 시험 알림 1건 수신. 메시지에 보내지 않기로 한 필드가 없는지 사람이 확인
- 실패 흉내: 색인을 돌리지 않는 시험 유닛 `qk-sync-failtest.service`(`ExecStart=/bin/false`, `OnFailure=qk-sync-notify@%n.service`)를 잠깐 두고 실행해 실패 → 알림 1건, 확인 뒤 시험 유닛을 지운다
- 다음 예약 실행(성공)에 알림이 오지 않음: `journalctl -u qk-sync.service -u 'qk-sync-notify@*'`

## Completion criteria

- `qk-sync.service`가 실패하면 알림 채널에 알림이 1건 온다 — 실패 흉내 시험의 수신 화면(값 가림)과 `journalctl -u 'qk-sync-notify@*'`
- 성공한 예약 실행에는 알림이 오지 않고, 다음 예약 실행이 계속 성공한다 — `qk-index runs list`, `journalctl`
- 알림 경로·보내는 필드·비밀값 위치의 결정과 구성 절차가 결정 기록과 운영 문서에 남는다 — 이 PR 리뷰

## Decisions

- 2026-10-25 사실: Jira `SCRUM-108`을 사용자 요청으로 만들었다(SCRUM-42 하위 작업, 레이블 `feature`·`team-backend`, 상위 스프린트를 따름).
- 2026-10-25 사용자 결정: 알림은 팀 Discord 채널의 웹훅으로 보낸다. 봇을 새로 만들지 않고, 발급만 해 둔 `Qello Knowledge` 봇(서버 미초대, `docs/sdd/research/tokens.md` 4절)과 팀원의 회의 봇도 쓰지 않는다.
  근거: 웹훅은 한 채널에 쓰기만 하는 URL이라 봇 토큰(서버 초대, `bot` 범위, Send Messages 권한)보다 권한이 좁고, 유출되면 채널에서 지우고 새로 만들면 된다.
- 2026-10-25 사용자 결정(해석 A): 헌법 "보안" 절의 "쓰기는 Discord에 답변·요약을 게시하는 경우로 한정한다"(`docs/sdd/constitution.md:40`)는 수집기와 그 토큰의 권한 규칙으로 읽는다.
  운영 실패 알림은 수집기가 아니고 원본 자료원에 쓰지 않으므로 이 규칙의 범위 밖이다 `(추론)`. 새 ADR에 이 해석과 근거를 적고 PR 리뷰에서 승인을 받는다. 헌법은 고치지 않는다.
  리뷰어가 해석에 동의하지 않으면 헌법 수정을 별도 작업으로 하고, 이 작업은 `BLOCKED`로 둔다.
- 2026-10-25 사용자 결정: 웹훅 URL은 `/etc/qello-knowledge/notify.env`(root:root, 0600)에 두고 `sync.env`와 나눈다. 알림 유닛만 root로 이 파일을 읽고,
  동기화 사용자 `qksync`와 `qk-sync.service`는 읽지 못한다. 동기화 쪽 토큰과 알림 웹훅이 서로의 유출 범위에 들지 않게 하려는 것이다
- 2026-10-25 사용자 결정: 0이 아닌 모든 종료 코드(1~6, `contracts/cli.md` 3절)와 시간 초과·신호 종료처럼 `Result`가 `success`가 아닌 경우에 알린다.
  예약 실행에서 5(멈춤: 예산 초과 등)와 6(이미 실행 중)도 사람이 봐야 하는 상황으로 본다. `OnFailure=`가 이 경우들에 모두 걸린다
- 2026-10-25 사용자 결정: 웹훅을 받을 채널을 정하고 웹훅을 만드는 사람은 Byuntil이다. 웹훅 URL은 Byuntil이 서버 비밀값 파일에 직접(숨김 입력) 넣고, 대화·문서·PR·Jira에 붙이지 않는다
- 2026-10-25 사용자 결정: 팀원(인스턴스 관리자)의 동의는 이 작업의 PR 리뷰로 받는다. 서버에 유닛과 비밀값 파일을 만드는 단계는 그 동의(PR 승인) 뒤에 한다.
  그래서 PR은 문서·결정 기록을 먼저 올린다. 리뷰 승인 뒤 서버를 구성하고 시험한 결과를 같은 PR에 커밋으로 더하고, 그 커밋까지 확인을 받은 뒤 병합한다.
- 2026-10-25 사용자 결정: 위 순서(승인 → 서버 구성·시험 → 같은 PR에 결과 커밋 → 병합)로 진행한다
- 2026-10-25 사실: PR #57을 올렸다(리뷰어 tkv00). CI `lint`·`test`·`secrets` 통과. 리뷰는 아직 없다.
- 2026-10-25 사용자 결정: PR 승인을 받은 것으로 가정하고 서버 구성·시험을 먼저 진행한다. 팀원(인스턴스 관리자)의 실제 동의는 아직 없으며 PR 리뷰로 받는다.
  동의를 받지 못하면 운영 문서 2절 12번의 되돌리기(drop-in 삭제)와 알림 스크립트·유닛·`notify.env` 삭제로 서버를 이전 상태로 돌린다.
- 2026-10-25 사실(사용자 재인증 뒤 승인 명령, Herdr 새 패널): Bastion 세션 `qk-notify`(1시간)를 만들었다. SSH가 Bastion에서 끊겼다(rc=255).
  확인 결과 작업자 공인 IP가 허용 목록에 없었다. 사용자 승인으로 `qkbastion` 허용 목록을 지금 공인 IP `/32` 하나로 바꿨다(운영 문서 2절 2번, 작업 상태 SUCCEEDED, 비용 없음).
- 2026-10-25 사실(읽기 전용 사전 확인): systemd 249(`LoadCredential=`는 247부터), Python 3.10.12, `systemd-journal` 그룹 있음, 알림 파일 5개 모두 없음,
  `/etc/qello-knowledge` 750 root:qksync, `qk-sync.service` inactive·Result=success·OnFailure 없음, 타이머 LAST 2026-10-25 00:30:09 UTC·NEXT 2026-10-26 00:30 UTC,
  서버 스크립트의 정리 단계 줄은 운영 문서 2절 8번과 같다.
- 2026-10-25 사실(사용자 승인 명령, Bastion 세션 `qk-notify`): 사용자가 Discord 운영 알림 채널에 웹훅을 만들고 서버에서 숨김 입력으로 `notify.env`를 만들었다(600 root:root, 값 출력 없음).
  알림 스크립트·`qk-sync-notify@.service`(`DynamicUser=yes`)·drop-in `notify.conf`를 설치했다. `systemd-analyze verify` 통과, `qk-sync.service`의 `OnFailure=qk-sync-notify@qk-sync.service.service`.
  `verify` 출력의 경고 5줄은 OCI 모니터링 에이전트·snapd의 기존 유닛 것이라 건드리지 않았다.
- 2026-10-25 사실(첫 실패 흉내 시험, 13:21 UTC): 알림 유닛이 `systemctl show`에서 실패해 메시지를 보내지 않았다. 읽기 전용 진단(일회성 `systemd-run`)에서
  `DynamicUser`는 `Transport endpoint is not connected`로 실패하고 `User=nobody`는 성공했다. `DynamicUser`로 `journalctl`은 읽을 수 있었다.
- 2026-10-25 사용자 결정: 알림 유닛을 전용 시스템 사용자 `qknotify`(로그인 없음, sudo·docker 그룹 없음, `systemd-journal` 그룹만 추가)로 실행한다. 격리 설정은 유닛에 직접 적는다.
  알림 스크립트는 `systemctl`이 실패하면 오류 한 줄을 남기고 끝낸다. 서버에 적용했다(`qknotify` uid 995, 스크립트 sha256 `62c83af1bdda`).
- 2026-10-25 사실(두 번째 실패 흉내 시험, 13:25 UTC): 알림 유닛 `Result=success`, 사용자가 Discord에서 알림 1건을 받았고 보내지 않기로 한 값이 없음을 확인했다.
- 2026-10-25 사용자 결정: 첫 수신 메시지가 읽기 어려워 Discord 임베드 카드로 바꾼다. 첫 줄은 결과 한 문장, 카드에 KST 시각·걸린 시간·실행 ID·종료 코드별 다음 명령, systemd 값은 바닥글,
  멈춤(5·6) 주황·그 밖 빨강, 시험 유닛이면 `[시험]`. 보내는 정보의 범위는 바꾸지 않는다. 로컬에서 종료 코드 1·4·5·6, 시간 초과, 알 수 없는 결과, 끝 시각 없음을 가짜 `systemctl`과 로컬 서버로 시험했다.
- 2026-10-25 사실(사용자 승인 명령): 서버 스크립트를 카드판으로 바꿨다(sha256 `62c83af1bdda` → `c11f07537079`, 문서 판과 같음).
  세 번째 실패 흉내 시험(13:32 UTC) 알림 유닛 `Result=success`, 사용자가 `[시험] 색인 동기화 실행 전 점검 실패` 카드를 받아 형식을 승인했다.
- 2026-10-25 사실(사용자 요청, 성공 시험 13:33 UTC): `/bin/true` 시험 유닛은 성공했고 알림 유닛은 실행되지 않았다(실행 ID 없음, 시험 뒤 알림 유닛 로그 0줄). 시험 유닛은 지웠다.
  성공 알림·일일 요약은 이 작업 범위 밖이다(`QK-OBS-002` 또는 별도 이슈). 완료 조건 둘째의 예약 실행 확인은 2026-10-26 00:30 UTC 실행 뒤에 한다.
