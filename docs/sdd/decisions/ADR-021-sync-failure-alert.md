# Decision Record: ADR-021 예약 동기화 실패를 Discord 채널 웹훅으로 알림

> Created at: `2026-10-25`
> Jira 이슈: `https://tkv123.atlassian.net/browse/SCRUM-108`
> 기능명세서 ID: 해당 없음(운영 구성 작업. ADR-020 Negative의 후속)
> Status: Proposed
>
> 작성 방식: ASD-STE-100 원칙(짧은 문장, 한 문장에 한 내용, 능동형, 한 가지 뜻의 단어)을 한국어에 적용한다(ADR-020과 같다).

## Context

- 매일 색인 동기화는 OCI 인스턴스의 systemd 타이머로 실행한다(ADR-020). 2026-10-24에 첫 예약 실행이 성공했다.
- 실행이 실패해도 알림이 없다. GitHub Actions를 쓰지 않으므로 GitHub는 메일을 보내지 않는다(ADR-020 Negative).
- 지금은 사람이 OCI Bastion 세션을 열고 `journalctl -u qk-sync.service`를 보아야 실패를 안다.
  세션은 사람이 인증해야 하고 최대 3시간 유지된다. 매일 확인하기 어렵다.
- `qk-index run`은 결과를 종료 코드로 알린다(`specs/QK-SYN-001-incremental-sync/contracts/cli.md` 3절).
  1은 실행 전 점검 실패, 2는 저장소 사용 불가, 3은 `--allow-remote` 없음, 4는 일부 실패, 5는 멈춤(예산 초과 등 보류), 6은 이미 실행 중이다.
  서버 스크립트 `/usr/local/libexec/qk-sync`는 이 코드를 그대로 돌려준다. 정리 단계가 실패하면 1을 돌려준다.
- 인스턴스는 팀원이 소유한다. 회의 봇도 같은 인스턴스에서 실행한다.
- 팀은 Discord를 쓴다. `Qello Knowledge` Discord 애플리케이션·봇은 발급만 했고 서버에 초대하지 않았다(`docs/sdd/research/tokens.md` 4절).
- 헌법 C-09는 "쓰기는 Discord에 답변·요약을 게시하는 경우로 한정한다"고 적는다(`docs/sdd/constitution.md` "보안" 절).
- 대시보드와 알림 전체는 로드맵 5.1 `QK-OBS-002`에서 한다. 그 전까지 실패를 알 최소 수단이 필요하다.

## Decision

`qk-sync.service`가 failed 상태가 되면 systemd `OnFailure=`로 알림 유닛을 실행하고, 알림 유닛이 팀 Discord 운영 알림 채널의 웹훅으로 실패 요약 1건을 보낸다.

## Rationale

- **권한이 좁다.** Discord 웹훅은 한 채널에 메시지를 쓰는 URL 하나다. 봇 사용자나 인증이 필요 없다.
  웹훅은 채널을 읽지 못한다. 봇 토큰은 서버 초대, `bot` 범위, Send Messages 권한이 필요하고 권한이 더 넓다.
- **되돌리기 쉽다.** 웹훅 URL이 새면 채널에서 그 웹훅을 지우고 새로 만든다. 다른 토큰은 바꾸지 않아도 된다.
- **실행 코드를 바꾸지 않는다.** `OnFailure=`는 유닛이 failed 상태가 되면 다른 유닛을 실행한다.
  `src/`, 서버 스크립트 `qk-sync`, 타이머는 그대로 둔다. `qk-sync.service`에는 drop-in 파일 하나만 더한다.
  drop-in을 지우면 알림이 없는 이전 상태로 돌아간다.
- **모든 실패를 잡는다.** 종료 코드 1~6, 시간 초과(`TimeoutStartSec=30min`), 신호 종료는 모두 유닛을 failed 상태로 만든다 `(추론: systemd 기본 동작, 시험으로 확인)`.
  5(멈춤)와 6(이미 실행 중)도 예약 실행에서는 사람이 보아야 한다. 그래서 종료 코드로 거르지 않는다.
- **비밀값을 나눈다.** 웹훅 URL은 `/etc/qello-knowledge/notify.env`(root:root, 0600)에 둔다. 동기화 비밀값 파일 `sync.env`와 나눈다.
  알림 유닛은 `LoadCredential=`로 이 파일을 받는다. systemd 관리자가 파일을 읽고 알림 유닛의 프로세스에만 보여 준다.
  동기화 사용자 `qksync`와 `qk-sync.service`는 웹훅 URL을 읽지 못한다. 알림 유닛은 동기화 토큰을 읽지 못한다.
  systemd 문서는 환경 변수가 비밀값 전달에 맞지 않는다고 적고 `LoadCredential=`을 권한다.
- **알림 유닛은 권한이 작다.** 알림 유닛은 `DynamicUser=yes`로 실행한다. 실행할 때만 생기는 사용자이고 root가 아니다.
  실패한 실행의 `run_id`를 찾으려고 `systemd-journal` 그룹만 더한다.
- **보내는 내용이 적다.** 유닛 이름, systemd `Result`, 종료 코드와 그 뜻, 시작·끝 시각, `run_id`, 확인 방법 한 줄만 보낸다.
  `journalctl` 원문, 오류 메시지 원문, 문서 경로·내용, 접속 주소, 호스트 이름은 보내지 않는다. 오류 원문에 비밀값이나 주소가 섞일 수 있다.
  `run_id`는 정해진 형식(`sync-YYYYMMDDTHHMMSS-xxxxxxxx`)과 맞는 문자열만 로그에서 꺼낸다.
  메시지는 `allowed_mentions`를 비워서 아무도 멘션하지 않는다.
- **헌법 C-09의 범위 밖이다(해석).** C-09의 제목은 "원본은 읽기만 한다"이다. C-09는 수집기와 그 토큰이 원본 자료원에 쓰는 일을 막는다.
  쓰기 예외(Discord 답변·요약 게시)도 수집·질의 시스템의 쓰기를 다룬다.
  실패 알림은 수집기가 아니다. 알림은 원본 자료원에 쓰지 않는다. 알림은 수집기 토큰을 쓰지 않는다.
  그래서 이 결정은 C-09를 어기지 않는다 `(추론, 이 PR 리뷰에서 승인)`. 리뷰어가 동의하지 않으면 헌법 수정을 별도 작업으로 하고 이 결정을 보류한다.

## Alternatives considered

| Alternative | Advantages | Disadvantages | Reason not selected |
| --- | --- | --- | --- |
| `Qello Knowledge` 봇 토큰으로 채널에 게시 | 이미 발급한 애플리케이션을 쓴다. QK-BOT-001과 같은 경로다. | 봇을 서버에 초대하고 `bot` 범위와 Send Messages 권한을 주어야 한다. 권한이 넓은 봇 토큰을 팀원 서버에 둔다. 토큰이 새면 `/ask` 봇도 바꾸어야 한다. | 알림 한 건에 비해 권한과 영향 범위가 크다. |
| 메일 | 채널이 필요 없다. | 서버에 메일 발송 경로(SMTP 계정 또는 OCI Email Delivery)를 새로 구성해야 한다. 새 자격 증명이 서버에 생긴다. | 구성과 비밀값이 더 많다. |
| OCI Monitoring 알람과 OCI Notifications | OCI 안에서 끝난다. 인스턴스가 멈춘 경우도 잡을 수 있다. | 팀원 테넌시에 새 자원과 IAM 정책이 필요하다. 작업자 권한(`dnd_Qello`)으로 만들 수 있는지 확인하지 않았다. 서비스 결과를 지표로 내보내는 수단이 따로 필요하다. | 팀원 테넌시 변경이 크다. 확인할 것이 많다. |
| 외부 헬스체크 서비스(성공할 때 ping, 없으면 알림) | 실행이 아예 돌지 않는 경우(인스턴스 중지, 타이머 꺼짐)도 잡는다. | 새 외부 서비스와 계정이 필요하다. 그 서비스가 다시 알림 경로(메일, Discord)를 필요로 한다. | 이 작업의 범위를 넘는다. Revisit conditions에 둔다. |
| 알림 없음, 사람이 주기적으로 확인 | 구성이 없다. | 실패를 며칠 늦게 알 수 있다. Bastion 세션과 인증이 매번 필요하다. | ADR-020 Negative를 해결하지 못한다. |

## Evidence

- Discord Developer Docs, Webhook Resource(조회 2026-10-25): https://docs.discord.com/developers/resources/webhook
  문서는 웹훅이 "do not require a bot user or authentication to use"라고 적는다.
  Execute Webhook은 `POST /webhooks/{webhook.id}/{webhook.token}`이다. `content`는 2,000자까지다.
  문서는 예상하지 않은 멘션을 막으려고 `allowed_mentions`를 쓰라고 권한다. 웹훅을 만들려면 `MANAGE_WEBHOOKS` 권한이 필요하다.
- systemd.unit(5)(조회 2026-10-25): https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html
  `OnFailure=`는 "units that are activated when this unit enters the "failed" state"다.
  `%i`는 인스턴스 유닛에서 `@`와 접미사 사이의 문자열이다. `%n`은 전체 유닛 이름이다.
  drop-in 디렉터리 `foo.service.d/`의 파일은 섹션 머리글을 가지고 설정을 더한다.
- systemd.exec(5)(조회 2026-10-25): https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html
  문서는 "environment variables are not suitable for passing secrets"라고 적고 `LoadCredential=`을 권한다.
  `LoadCredential=`(version 247)의 원본 파일은 서비스 관리자만 읽을 수 있으면 된다. 자격 증명은 그 유닛의 사용자와 root만 읽는다.
  `DynamicUser=`는 `NoNewPrivileges=`, `ProtectSystem=strict`, `ProtectHome=read-only`를 함께 켠다.
- 인스턴스: Ubuntu 22.04(`docs/ops/oci-production-store.md` 1절). Ubuntu 22.04의 systemd는 249다 `(추론, 구성할 때 systemctl --version으로 확인)`.
- 종료 코드: `specs/QK-SYN-001-incremental-sync/contracts/cli.md` 3절. 2026-10-23 잠금 시험의 6(`already_running`)은 `TASK.md`(SCRUM-103) 기록에 있다.

## Data and cost

- 외부로 전송되는 데이터와 제공자의 학습 사용·보존 정책: 실패할 때만 Discord에 운영 메타데이터를 보낸다.
  팀 자료의 원문·청크, 질의, 비밀값, 접속 주소는 보내지 않는다. 그래서 새 자료원이나 새 외부 모델의 데이터 처리 정책 확인 대상(AGENTS.md 3.1)이 아니다 `(추론)`.
  Discord는 메시지를 채널 기록으로 보관한다. 채널 관리자가 메시지를 지울 수 있다.
- 무료 한도와 예상 사용량: Discord 웹훅은 무료다. 실패한 날에만 요청 1건이다. Neurons는 쓰지 않는다.
- 교체 시 영향(재임베딩, 인덱스 버전): 없다. 인덱스 버전은 바뀌지 않는다.

## Consequences

### Positive

- 예약 실행이나 수동 실행이 실패하면 팀이 같은 날 안다.
- 알림 메시지의 `run_id`로 `qk-index runs show`와 `journalctl`을 바로 찾는다.
- 동기화 코드와 스크립트는 바뀌지 않는다. drop-in 파일을 지우면 이전 상태로 돌아간다.

### Negative / risks

- 실행이 아예 돌지 않으면 알림이 없다. 예: 인스턴스 중지, 타이머 꺼짐, systemd 고장. 사람은 여전히 가끔 `systemctl list-timers`를 보아야 한다.
- 알림 유닛이 실패하면(예: Discord 장애, 웹훅 삭제) 알림이 없다. 그 실패는 인스턴스의 `journalctl -u 'qk-sync-notify@*'`에만 남는다.
- 웹훅 URL이 새면 누구나 그 채널에 글을 쓸 수 있다. 채널에서 웹훅을 지우고 새로 만든다.
- 웹훅 URL은 팀원 인스턴스의 파일에 있다. 인스턴스 관리자(팀원)는 이 파일을 읽을 수 있다.
- 헌법 C-09 해석을 리뷰어가 받아들이지 않으면 이 결정은 보류된다.

## Revisit conditions

- `QK-OBS-002`(대시보드·알림)를 시작한다. 그 명세가 이 알림을 흡수하거나 대체한다.
- 실행이 돌지 않은 일을 늦게 알아서 문제가 된다. 그러면 외부 헬스체크 서비스나 OCI 알람을 다시 본다.
- `Qello Knowledge` 봇이 같은 서버에 설치되고 채널 게시 권한을 받는다(QK-BOT-001).
- 실패 알림이 너무 자주 와서 무시된다. 그러면 알릴 종료 코드를 다시 정한다.

## Approval

- Approvers:
- Approved at:
  이 기록은 Claude 세션이 썼다. 그 세션은 이 결정을 승인하지 않는다(AGENTS.md 2절).
