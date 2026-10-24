# OCI 운영 저장소 구성·운영 절차

운영 저장소를 팀원 테넌시의 OCI Ampere A1 인스턴스(회의 봇 서버와 공유) 위 자체 운영 PostgreSQL로 둔다(ADR-008, SCRUM-103·#50).
이 문서는 구성 설계, 기존 인스턴스에 얹는 순서, 운영·복구 절차다. 접속 주소, 비밀번호, 계정 식별자(OCID·테넌시·지문), 키 파일 내용은 적지 않는다. `<...>`는 placeholder다.

## 1. 구성 요약

| 항목 | 값 | 이유 |
| --- | --- | --- |
| 테넌시·계정 | 팀원 테넌시(유료 Pay As You Go 전환 계정). 계정 소유자는 팀원이고, 작업자는 컴파트먼트 `dnd_Qello`의 IAM 접근을 받았다 | 작업자 테넌시(도쿄)는 A1 용량 부족으로 인스턴스를 만들지 못했다(ADR-008) |
| 리전 | 홈 리전 `ap-osaka-1`(오사카) | 기존 인스턴스가 있는 곳 |
| 인스턴스 | 기존 `Qello-Meeting-Bot-Server`: `VM.Standard.A1.Flex` 1 OCPU·6 GB, Canonical Ubuntu 22.04(aarch64). 회의 봇 컨테이너(`meeting-bot-recorder`, `n8n`)와 같이 쓴다 | 2026-10-22 실측 가용 메모리 4.6 GiB, 디스크 여유 40 GB로 DB·러너·하루 1회 색인을 올릴 수 있다 `(추론)`. 새 인스턴스·크기 변경은 하지 않는다(PAYG라 무료 범위를 넘으면 과금, C-05) |
| 디스크 | 부트 볼륨(49 GB, 여유 40 GB), 추가 블록 볼륨 없음 | Phase 2 목표 규모(원문 약 10 MB, 벡터·색인 포함 수백 MB 이하, 추론)에 충분하다 |
| 들어오는 연결 | 보안 목록은 TCP 22(0.0.0.0/0)·ICMP, 호스트 iptables는 22만 받는다. DB 포트는 열지 않는다 | 22의 범위는 팀원 설정이다. 좁힐지는 팀원과 정한다(3절) |
| 작업자 접속 | OCI Bastion `qkbastion`(작업자 공인 IP `/32`만 허용, 세션 최대 3시간)의 관리형 SSH 세션, 사용자 `ubuntu`, 키 `~/.ssh/qello_oci` | 팀원 서버에 작업자 키를 영구히 두지 않는다. 세션마다 키가 임시로 들어간다 |
| DB | Docker의 `supabase/postgres:17.11.0.004`(로컬 개발 DB와 같은 이미지), 컨테이너 `qk-postgres`, `127.0.0.1:5432`에만 바인딩, 데이터는 명명 볼륨 `qk-pgdata` | pgvector·PGroonga가 들어 있다(ADR-007 스파이크) |
| DB 메모리 | 컨테이너 메모리 상한 1.5 GB(`--memory 1536m`), `shared_buffers` 256 MB `(추론)` | 같은 서버의 회의 봇을 보호한다. 상한 값은 팀원 동의를 받는다 |
| DB 자격 증명 | 인스턴스에서 무작위 비밀번호를 만들어 root만 읽는 파일(`/root/qk/postgres.env`)과 동기화 비밀값 파일에만 둔다 | 저장소·대화·로그에 남기지 않는다 |
| 예약 실행 | 인스턴스의 systemd 타이머 `qk-sync.timer`(매일 00:30 UTC = 09:30 KST)가 전용 사용자 `qksync`로 `qk-sync.service`를 실행한다 | DB에 `localhost`로 붙고 들어오는 포트가 필요 없다. 공개 저장소라 셀프 호스티드 러너를 쓰지 않는다(ADR-020) |
| 예약 실행 비밀값 | `/etc/qello-knowledge/sync.env`(root:qksync, 0640)에 `DATABASE_URL`(`127.0.0.1:5432`), `GITHUB_API_TOKEN`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | GitHub Secret을 쓰지 않는다. 값은 사람이 서버에서 직접 입력하고 저장소·대화·로그에 남기지 않는다 |
| 원격 판정 | 운영 DB 포트(5432)는 로컬 개발 포트(`QK_LOCAL_DB_PORT`, 기본 54322)와 다르게 둔다 | CLI가 운영 DB를 원격으로 판정해 `--allow-remote`와 `config/store_policy.toml` 검사가 그대로 걸린다 |

## 2. 기존 인스턴스에 얹는 순서

각 단계의 OCI 명령과 인스턴스 안 명령은 실행 전에 사람이 승인한다. 팀원 서비스(회의 봇)의 컨테이너·설정은 건드리지 않는다.

1. 접속 준비(2026-10-22 완료): 인스턴스 에이전트의 Bastion 플러그인을 켜고, `dnd_Qello`에 Bastion `qkbastion`을 만든다(무료).
2. 접속: `oci bastion session create-managed-ssh`로 세션(사용자 `ubuntu`, 공개 키 `~/.ssh/qello_oci.pub`)을 만들고 세션의 ProxyCommand로 접속한다.
   작업자 공인 IP가 바뀌면 Bastion의 허용 목록(`client-cidr-list`)을 새 `/32`로 갱신한다.
3. DB 컨테이너: 무작위 비밀번호를 만들어 root 전용 파일에 두고 다음과 같이 띄운다. 재부팅 때 자동 시작한다.

   ```bash
   sudo docker run -d --name qk-postgres --restart unless-stopped --memory 1536m \
     -p 127.0.0.1:5432:5432 -v qk-pgdata:/var/lib/postgresql/data \
     --env-file <root 전용 파일: POSTGRES_PASSWORD=...> \
     supabase/postgres:17.11.0.004 <이미지 기본 CMD> -c shared_buffers=256MB
   ```

   `<이미지 기본 CMD>`는 실행 전에 `sudo docker image inspect --format '{{json .Config.Cmd}}'`로 확인해 그대로 쓰고 `-c` 옵션만 덧붙인다(이미지 설정 파일 경로를 잃지 않게).
   확장 확인: `CREATE EXTENSION vector; CREATE EXTENSION pgroonga;` 결과를 ADR-008에 적는다(QK-STO-001 T031).
4. 마이그레이션: 작업자 PC에서 Bastion 세션을 거친 SSH 터널(`ssh -L 15432:127.0.0.1:5432 ...`)을 열고 `DATABASE_URL`을 터널 주소로 둔 채
   `uv run qk-migrate --dry-run` → `uv run qk-migrate` → 다시 실행해 `applied=0`.
   타이머를 켠 뒤에는 새 마이그레이션을 그 코드가 `main`에 병합되기 전에(늦어도 다음 00:30 UTC 실행 전에) 이 방법으로 적용한다(6절).
5. 첫 색인(H06, 2026-10-23 완료): 4번의 터널로 `qk-index run --preview --allow-remote --json` → 사용량 승인 → `qk-index run --allow-remote --json` 두 번(두 번째 임베딩 호출 0) → `qk-index index activate <버전> --allow-remote`.
6. 동기화 사용자와 코드: 시스템 사용자 `qksync`(홈 `/var/lib/qksync`, sudo·docker 그룹 없음)를 만든다. `qksync`로 `uv`(작업자 PC와 같은 판, 2026-10-23 기준 0.13.1)를 설치하고
   공개 저장소를 `/opt/qello-knowledge`에 받는다(인증 없음). 이 복제본은 동기화 전용이다. 사람이 고치지 않는다.
7. 비밀값 파일(사람): `/etc/qello-knowledge/sync.env`(root:qksync, 0640)를 만든다. DB 비밀번호는 `/root/qk/postgres.env`에서 옮기고, 토큰은 사람이 서버에서 숨김 입력(`read -s`)으로 넣는다.
   GitHub 토큰은 원본 저장소 내용 읽기만 되는 fine-grained 토큰을 쓴다.
8. 실행 스크립트 `/usr/local/libexec/qk-sync`(root 소유, 0755):

   ```bash
   #!/usr/bin/env bash
   set -uo pipefail
   cd /opt/qello-knowledge || exit 1
   git fetch --quiet origin main && git reset --quiet --hard origin/main || exit 1
   uv sync --locked --extra index --extra postgres || exit 1
   uv run qk-index run --allow-remote --trigger schedule --json; rc=$?
   # 색인이 실패하면 그 종료 코드를 남기고, 색인이 성공해도 정리가 하나라도 실패하면 1로 끝낸다.
   uv run qk-index usage prune --allow-remote || { [ "$rc" -eq 0 ] && rc=1; }
   uv run qk-index runs prune --allow-remote || { [ "$rc" -eq 0 ] && rc=1; }
   exit "$rc"
   ```

9. systemd 유닛:

   ```ini
   # /etc/systemd/system/qk-sync.service
   [Unit]
   Description=Qello Knowledge daily index sync (ADR-020)
   After=network-online.target docker.service
   Wants=network-online.target

   [Service]
   Type=oneshot
   User=qksync
   Group=qksync
   EnvironmentFile=/etc/qello-knowledge/sync.env
   ExecStart=/usr/local/libexec/qk-sync
   TimeoutStartSec=30min
   Nice=10
   MemoryMax=1G
   NoNewPrivileges=yes
   PrivateTmp=yes
   ProtectSystem=strict
   ProtectHome=yes
   ReadWritePaths=/opt/qello-knowledge /var/lib/qksync

   # /etc/systemd/system/qk-sync.timer
   [Unit]
   Description=Run qk-sync daily at 00:30 UTC

   [Timer]
   OnCalendar=*-*-* 00:30:00 UTC
   Persistent=true
   Unit=qk-sync.service

   [Install]
   WantedBy=timers.target
   ```

10. 켜기(H07): `config/store_policy.toml`이 `main`에 병합된 뒤에 한다(없으면 `store_policy_required`로 멈춘다). `systemctl start qk-sync.service`로 1회 실행해 성공을 확인하고
    `systemctl enable --now qk-sync.timer`로 예약을 켠다. `systemctl list-timers qk-sync.timer`로 다음 실행 시각을 확인한다.
    2026-10-23 #55 병합 뒤 0006 적용 → 수동 1회 실행 성공(0 Neurons) → 타이머 켜기를 마쳤다(`specs/QK-SYN-001-incremental-sync/tasks.md` H07).
11. GitHub 워크플로 `index-sync.yml`은 쓰지 않는다. 저장소 변수 `QK_SYNC_ENABLED`를 만들지 않는다(ADR-020).

## 3. 공유 인스턴스 운영 규칙

- 자원: DB 컨테이너는 메모리 상한 안에서만 쓴다. 색인 실행 중 회의 봇이 느려지면 상한이나 실행 시각을 다시 정한다.
- 경계: 회의 봇 컨테이너·설정·데이터를 읽거나 바꾸지 않는다. 이 서비스의 자원은 `qk-postgres`, `qk-pgdata`, `/root/qk`, `qksync`, `/opt/qello-knowledge`, `/etc/qello-knowledge`, `qk-sync.service`·`qk-sync.timer`, `qkbastion`뿐이다.
- 접근: 인스턴스 관리자(팀원)는 DB 내용을 볼 수 있다. 저장하는 것은 팀 공용 자료의 청크와 메타데이터뿐이다(AGENTS.md 3.1).
- 알림: 팀원이 재부팅·업데이트·인스턴스 재생성·종료를 계획하면 미리 알린다. DB를 잃으면 4절로 복구한다.
- SSH 범위: 보안 목록의 22(0.0.0.0/0)를 좁히거나 닫고 Bastion만 쓸지는 팀원이 정한다. 비밀번호 로그인은 꺼져 있다(2026-10-22 확인).

## 4. 유휴 회수와 과금

- 유휴 회수: Oracle의 Always Free 유휴 인스턴스 회수는 무료 계정을 대상으로 하는 것으로 보이며, 이 계정은 PAYG라 해당하지 않는다고 본다 `(추론, 공식 문서 확인 필요)`.
  사용률을 억지로 올리는 부하 작업은 두지 않는다.
- 과금: 테넌시 전체 A1 사용량이 무료 범위(월 1,500 OCPU 시간·9,000 GB 시간)를 넘으면 과금된다. 작업자는 다른 컴파트먼트를 볼 수 없으므로 크기 변경·새 유료 자원은 팀원 확인과 사람 승인(C-05) 뒤에만 한다.

## 5. 복구(재색인)

DB를 잃으면 2절 3~4번으로 다시 만들고 `qk-index run --allow-remote`로 처음부터 색인하고 첫 버전을 활성화한다. 원본이 진실이고 DB는 원본에서 다시 만들 수 있다(RISK-08).
첫 색인 비용은 약 900 Neurons(하루 무료 10,000 안)다. 실행 기록과 사용량 기록은 잃는다. 백업·복구 절차 전체는 QK-SYN-003에서 정한다.

## 6. 운영 확인

- 예약 실행 결과: Bastion 세션으로 `journalctl -u qk-sync.service`, `systemctl list-timers qk-sync.timer`, 그리고 `qk-index runs list`. GitHub Actions에는 기록이 없다(ADR-020).
- 수동 실행: Bastion 세션으로 `sudo systemctl start qk-sync.service`.
- 실패 알림: 아직 없다. 후속 작업으로 만든다(ADR-020 Negative).
- 사용량: `qk-index usage`(같은 DB를 보는 환경에서).
- 정리: 예약 실행이 `usage prune`과 `runs prune`을 함께 돈다(보관 90일).
- 마이그레이션 순서: 예약 실행은 매번 최신 `main`을 받아 실행하고 마이그레이션은 돌리지 않는다. 새 마이그레이션이 든 PR은 병합 전에 2절 4번으로 운영 DB에 적용한다.
  적용하지 않으면 새 코드가 없는 테이블·함수를 불러 실행이 실패한다(2026-10-23 `0006_generation_usage`: `usage prune`이 실패할 뻔했다).
- 자원: Bastion 세션으로 `free -h`, `df -h /`, `sudo docker stats --no-stream`.
