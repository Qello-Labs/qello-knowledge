# Decision Record: ADR-020 예약 색인 동기화를 OCI 인스턴스의 systemd 타이머로 실행

> Created at: `2026-10-23`
> Jira 이슈: `https://tkv123.atlassian.net/browse/SCRUM-103`
> 기능명세서 ID: `QK-SYN-001` (사람 단계 H07, 작업 T047)
> Status: Accepted
>
> 작성 방식: ASD-STE-100 원칙(짧은 문장, 한 문장에 한 내용, 능동형, 한 가지 뜻의 단어)을 한국어에 적용한다(2026-10-23 사용자 요청).

## Context

- QK-SYN-001 T047은 매일 색인 동기화를 GitHub Actions(`.github/workflows/index-sync.yml`)에서 실행한다.
- 운영 DB는 OCI 인스턴스 `Qello-Meeting-Bot-Server`에 있다(ADR-008).
  DB는 `127.0.0.1:5432`에서만 연결을 받는다. GitHub 호스티드 러너는 이 DB에 연결할 수 없다.
- 처음 계획은 같은 인스턴스에 셀프 호스티드 러너를 두는 것이었다. 러너는 `localhost`로 DB에 연결한다.
- 2026-10-23에 저장소 `Qello-Labs/qello-knowledge`가 공개(public) 저장소임을 확인했다.
  GitHub는 공개 저장소에 셀프 호스티드 러너를 거의 쓰지 말라고 권고한다.
- 이 인스턴스는 이 시스템 전용이 아니다. 회의 봇(`n8n`, `meeting-bot-recorder`)도 같은 인스턴스에서 실행한다.
  OCI 계정 소유자는 팀원이다.

## Decision

매일 색인 동기화는 OCI 인스턴스의 systemd 타이머로 실행하고 GitHub Actions를 쓰지 않으며, 저장소는 공개 상태를 유지한다.

## Rationale

- **CI 한도.** 저장소를 비공개로 바꾸면 GitHub 호스티드 러너의 CI 작업이 포함 시간을 소모한다.
  GitHub Free 조직은 비공개 저장소에 매월 2,000분을 받는다.
  공개 저장소는 표준 GitHub 호스티드 러너를 써도 이 시간을 소모하지 않는다.
- **외부 공개 용도.** 팀은 공개 저장소를 외부 공개 용도로 쓴다. 비공개로 바꾸면 이 용도가 없어진다.
- **보안.** 비공개 저장소는 셀프 호스티드 러너의 위험을 줄인다. 그러나 위의 두 문제가 생긴다.
  타이머는 러너 위험을 없애고 저장소를 공개 상태로 유지한다.
  - 공개 저장소는 누구나 포크하고 PR을 열 수 있다.
    PR은 러너 라벨을 쓰는 워크플로를 더할 수 있다. 그러면 신뢰할 수 없는 코드가 공유 인스턴스에서 실행된다.
  - 신뢰할 수 없는 코드는 작업이 끝난 뒤에도 인스턴스에 남을 수 있다.
    이 코드는 다음 예약 작업의 비밀값(DB 주소, GitHub 토큰, Cloudflare 토큰)을 읽을 수 있다.
  - 신뢰할 수 없는 코드는 같은 인스턴스의 다른 서비스에 연결할 수 있다. 예: `127.0.0.1:5678`의 `n8n`.
  - 타이머는 정해진 명령 하나만 실행한다. 외부 사람은 타이머에 작업을 보낼 수 없다.
  - 로그는 인스턴스에만 남는다. 로그는 공개 GitHub Actions 로그로 가지 않는다.
- **작은 작업량.** 동기화는 자원을 많이 쓰지 않는다. 별도 러너나 별도 기계가 필요 없다.
  - 2026-10-23 변경 없는 동기화는 1분 28초 걸렸고 0 Neurons를 썼다.
  - DB 컨테이너는 약 127 MiB를 썼다. 인스턴스의 가용 메모리는 4.5 GiB였다.

## Alternatives considered

| Alternative | Advantages | Disadvantages | Reason not selected |
| --- | --- | --- | --- |
| 셀프 호스티드 러너, 공개 저장소, 승인 규칙 강화 | T047과 맞는다. GitHub에서 실행 기록과 로그를 본다. 수동 실행 버튼이 있다. 예약 실행이 실패하면 메일이 온다. | 신뢰할 수 없는 PR 코드가 공유 인스턴스에서 실행될 수 있다. 사람이 나쁜 워크플로 변경을 찾아야 한다. 로그가 공개된다. | 공유 인스턴스와 팀원 서비스에 보안 위험이 있다. |
| 셀프 호스티드 러너, 비공개 저장소 | 위와 같은 장점이 있다. 팀원만 작업을 보낼 수 있다. 로그가 비공개다. | CI 작업이 포함 시간 2,000분을 소모한다. 외부 공개 용도가 없어진다. | CI 한도와 외부 공개 용도. |
| GitHub 호스티드 러너와 DB 터널(예: Tailscale, Cloudflare Tunnel, OCI Bastion 포트 포워딩) | 인스턴스에 상주 프로세스가 없다. T047과 맞는다. | 새 외부 서비스를 더하거나 OCI 자격 증명을 GitHub Secret에 둔다. 새 결정 기록이 필요하다(AGENTS.md 3.1). 실패할 수 있는 부분이 많다. | 작은 일일 작업에 비해 복잡하다. |
| 수동 동기화만 | 새 구성이 없다. | 주기 동기화가 없다. 로드맵 2.G의 "정해진 주기로 동기화" 증빙이 없다. | 동기화 목표를 만족하지 않는다. |

## Evidence

- 저장소 설정(2026-10-23 `gh`로 조회): 공개 범위 `PUBLIC`, 조직 플랜 `free`,
  포크 PR 승인 정책 `first_time_contributors`, `pull_request` 트리거가 있는 워크플로 `ci.yml`.
- GitHub, Secure use reference, "Hardening for self-hosted runners"(조회 2026-10-23):
  https://docs.github.com/en/actions/reference/security/secure-use
  문서는 "self-hosted runners should almost never be used for public repositories on GitHub"라고 적는다.
  문서는 저장소를 포크하고 PR을 여는 사람이 러너 환경을 침해할 수 있다고 적는다.
- GitHub, About billing for GitHub Actions(조회 2026-10-23):
  https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions
  문서는 "GitHub Actions usage is free for self-hosted runners and for public repositories that use standard GitHub-hosted runners"라고 적는다.
  문서는 GitHub Free 조직의 비공개 저장소에 매월 2,000분을 표시한다.
- 운영 인스턴스 측정(2026-10-23): `TASK.md` Decisions, `specs/QK-SYN-001-incremental-sync/tasks.md` H06.

## Data and cost

- 외부로 전송되는 데이터와 제공자의 학습 사용·보존 정책: 변경 없다. 동기화는 같은 청크를 Workers AI로 보내고(ADR-002) 같은 GitHub 원본을 읽는다(ADR-019).
  GitHub 토큰과 Cloudflare 토큰은 GitHub Secret 대신 인스턴스의 파일에 둔다. `root`와 동기화 사용자만 이 파일을 읽는다.
- 무료 한도와 예상 사용량: GitHub Actions 시간은 0이다. Neurons는 전과 같다(변경 없는 날 0, 전체 색인 약 900).
- 교체 시 영향(재임베딩, 인덱스 버전): 없다. 인덱스 버전은 바뀌지 않는다.

## Consequences

### Positive

- 외부 사람은 공유 인스턴스에서 작업을 시작할 수 없다.
- 동기화 로그는 인스턴스와 DB(`qk-index runs list`)에만 남는다.
- 타이머는 정해진 시각에 시작한다. `Persistent=true`는 재부팅으로 놓친 실행을 부팅 뒤에 시작한다.
- 실행과 실행 사이에 메모리에 남는 프로세스가 없다.

### Negative / risks

- GitHub는 실행 기록을 보여 주지 않는다. OCI Bastion 세션으로 `journalctl`과 `qk-index runs list`를 쓴다.
- 실행이 실패해도 GitHub는 메일을 보내지 않는다. 실패 알림은 후속 작업이다.
- 수동 실행에는 OCI Bastion 세션과 `systemctl start`가 필요하다.
- 토큰은 팀원이 소유한 인스턴스의 파일에 있다. 팀원은 이 파일을 읽을 수 있다.
- 매 실행은 최신 `main`을 받아 실행한다. `main`의 나쁜 변경은 인스턴스에서 실행된다. 이 위험은 러너와 같다.
- 이 결정은 QK-SYN-001의 T047과 H07을 바꾼다. `index-sync.yml`은 저장소에 남는다.
  저장소 변수 `QK_SYNC_ENABLED`가 없으므로 이 워크플로는 실행하지 않는다. 후속 작업에서 지우거나 고친다.
- `config/store_policy.toml`이 `main`에 들어가기 전에는 타이머를 켤 수 없다.
  이 파일이 없으면 `qk-index run --allow-remote`는 `store_policy_required`로 멈춘다.

## Revisit conditions

- 저장소를 비공개로 바꾼다.
- 팀에 GitHub 실행 기록, 수동 실행 버튼, 실패 메일이 필요하다.
- 운영 DB가 다른 인스턴스나 제공자로 옮긴다.
- 동기화가 10분보다 오래 걸리거나 회의 봇을 느리게 한다.
- 질의 경로(QK-BOT-001)가 DB에 다른 연결 방식을 요구한다.

## Approval

- Approvers: PR #55 리뷰어 tkv00(팀원, OCI 계정 소유자)
- Approved at: 2026-10-23 PR #55 리뷰 승인(APPROVED)과 병합(`59132b2`). 사용자가 2026-10-23에 systemd 타이머를 선택했다.
  이 기록은 Claude 세션이 썼고 그 세션은 승인하지 않았다(AGENTS.md 2절).
