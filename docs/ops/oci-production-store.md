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
| 실패 알림 | `qk-sync.service`가 failed 상태가 되면 `OnFailure=`로 `qk-sync-notify@.service`가 팀 Discord 운영 알림 채널의 웹훅에 실패 요약 1건을 보낸다. 웹훅 URL은 `/etc/qello-knowledge/notify.env`(root:root, 0600)에 두고 `LoadCredential=`로 알림 유닛(전용 사용자 `qknotify`)에만 준다 | Bastion 세션 없이 실패를 같은 날 안다. `qksync`는 웹훅을, 알림 유닛은 동기화 토큰을 읽지 못한다(ADR-021) |
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
12. 실패 알림(ADR-021): 이 구성을 더한 PR의 리뷰 승인(인스턴스 관리자 동의) 뒤에 한다.
    - 웹훅(사람): 팀 Discord 운영 알림 채널의 설정 → 연동 → 웹후크에서 웹훅을 만든다(`MANAGE_WEBHOOKS` 권한).
      URL은 대화·문서·PR·Jira에 붙이지 않는다. 서버에서 숨김 입력으로 비밀값 파일을 만든다.

      ```bash
      sudo install -m 0600 -o root -g root /dev/null /etc/qello-knowledge/notify.env
      sudo bash -c 'read -rsp "webhook URL: " u; echo; printf "QK_NOTIFY_WEBHOOK_URL=%s\n" "$u" > /etc/qello-knowledge/notify.env'
      ```

    - 알림 스크립트 `/usr/local/libexec/qk-sync-notify`(root 소유, 0755). 유닛 결과와 `run_id`만 임베드 카드로 보내고 로그 원문은 보내지 않는다.
      첫 줄(휴대폰 알림에 보임)은 결과 한 문장이고, 카드에는 KST 시각과 걸린 시간, 실행 ID, 종료 코드별 다음 할 일을 담는다. `qk-sync.service`가 아닌 유닛이면 `[시험]`을 붙인다.

      ```python
      #!/usr/bin/python3 -I
      """실패한 유닛의 결과를 Discord 웹훅 임베드로 알린다(ADR-021). 로그 원문은 보내지 않는다."""

      import json
      import os
      import re
      import subprocess
      import sys
      import time
      import urllib.request
      from datetime import datetime, timedelta, timezone

      RED, ORANGE = 0xD83C3E, 0xF0A030
      KST = timezone(timedelta(hours=9))
      RUN_ID = re.compile(r"sync-\d{8}T\d{6}-[0-9a-f]{8}")
      # 종료 코드(contracts/cli.md 3절) → (제목, 설명, (다음 명령, 무엇을 보는지), 색)
      CODES = {
          "1": (
              "실행 전 점검 실패",
              "설정·정책 파일·비밀값·자료원 점검에서 멈췄습니다.",
              ("journalctl -u {unit}", "점검에 실패한 항목을 봅니다"),
              RED,
          ),
          "2": (
              "저장소 연결 실패",
              "운영 DB에 연결하지 못했습니다.",
              ("sudo docker ps", "qk-postgres 컨테이너가 떠 있는지 봅니다"),
              RED,
          ),
          "3": (
              "원격 쓰기 허용 없음",
              "--allow-remote 없이 운영 DB에 쓰려 했습니다.",
              ("cat /usr/local/libexec/qk-sync", "qk-index 인자를 봅니다"),
              RED,
          ),
          "4": (
              "일부 문서 실패",
              "일부 문서를 처리하지 못했습니다. 실패한 문서는 이전 버전을 유지합니다.",
              ("qk-index runs show {run_id} --failures", "실패한 문서와 단계를 봅니다"),
              RED,
          ),
          "5": (
              "멈춤 · 보류 있음",
              "예산 초과·인덱스 버전 불일치 등으로 일부 문서를 보류했습니다.",
              ("qk-index runs show {run_id}", "보류 사유를 봅니다"),
              ORANGE,
          ),
          "6": (
              "건너뜀 · 이전 실행이 도는 중",
              "다른 동기화가 잠금을 잡고 있어 이번 실행을 건너뛰었습니다.",
              ("systemctl status qk-sync.service", "이전 실행이 아직 도는지 봅니다"),
              ORANGE,
          ),
      }
      RESULTS = {
          "timeout": (
              "시간 초과",
              "제한 시간(30분) 안에 끝나지 않았습니다.",
              ("sudo docker stats --no-stream", "메모리 사용량과 회의 봇 영향을 봅니다"),
          ),
          "signal": (
              "신호로 종료",
              "실행 중 신호를 받고 끝났습니다(재부팅·중지 등).",
              ("journalctl -u {unit}", "종료 직전 기록을 봅니다"),
          ),
      }


      def prop(unit, name):
          out = subprocess.run(["systemctl", "show", unit, "-p", name, "--value"], capture_output=True, text=True)
          if out.returncode != 0:  # 원인이 로그에 남게 systemctl의 오류 한 줄을 적는다(비밀값은 들어가지 않는다)
              raise SystemExit(f"systemctl show {name} 실패: {out.stderr.strip()[:200]}")
          return out.stdout.strip()


      def parse_utc(value):
          try:  # 예: "Sun 2026-10-25 13:25:17 UTC"
              return datetime.strptime(value.split(" ", 1)[1], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
          except (IndexError, ValueError):
              return None


      def when(start, end):
          s, e = parse_utc(start), parse_utc(end)
          if not s:
              return "알 수 없음"
          text = s.astimezone(KST).strftime("%m/%d %H:%M")
          if not e:
              return f"{text} KST 시작"
          minutes, seconds = divmod(int((e - s).total_seconds()), 60)
          return f"{text}–{e.astimezone(KST).strftime('%H:%M')} KST ({minutes}분 {seconds}초)"


      def webhook_url():
          path = os.path.join(os.environ["CREDENTIALS_DIRECTORY"], "webhook")
          for line in open(path, encoding="utf-8"):
              if line.startswith("QK_NOTIFY_WEBHOOK_URL="):
                  return line.split("=", 1)[1].strip()
          raise SystemExit("QK_NOTIFY_WEBHOOK_URL 없음")


      def message(unit):
          result, status, invocation = prop(unit, "Result"), prop(unit, "ExecMainStatus"), prop(unit, "InvocationID")
          log = ""
          if invocation:
              log = subprocess.run(
                  ["journalctl", f"_SYSTEMD_INVOCATION_ID={invocation}", "-o", "cat", "--no-pager"],
                  capture_output=True,
                  text=True,
              ).stdout
          run_ids = RUN_ID.findall(log)
          run_id = run_ids[-1] if run_ids else "없음"
          if result == "exit-code" and status in CODES:
              title, detail, step, color = CODES[status]
          elif result in RESULTS:
              title, detail, step = RESULTS[result]
              color = RED
          else:
              title, detail, step, color = (
                  "알 수 없는 실패",
                  f"systemd 결과 {result}, 종료 코드 {status}",
                  ("journalctl -u {unit}", "실패 기록을 봅니다"),
                  RED,
              )
          prefix = "" if unit == "qk-sync.service" else "[시험] "
          headline = f"{prefix}색인 동기화 {title}"
          command = step[0].format(unit=unit, run_id=run_id if run_ids else "<실행 ID>")
          embed = {
              "title": headline,
              "description": detail,
              "color": color,
              "fields": [
                  {"name": "시각", "value": when(prop(unit, "ExecMainStartTimestamp"), prop(unit, "ExecMainExitTimestamp"))},
                  {"name": "실행 ID", "value": f"`{run_id}`"},
                  {"name": "다음 할 일", "value": f"`{command}`\n{step[1]}"},
              ],
              "footer": {"text": f"{unit} · Result={result} · 종료 코드 {status} · 명령은 Bastion 세션에서 실행합니다"},
          }
          return {"content": headline, "embeds": [embed], "allowed_mentions": {"parse": []}}


      def main():
          body = json.dumps(message(sys.argv[1])).encode()
          request = urllib.request.Request(
              webhook_url(),
              data=body,
              method="POST",
              headers={"Content-Type": "application/json", "User-Agent": "qk-sync-notify/1"},
          )
          for attempt in range(3):
              try:
                  with urllib.request.urlopen(request, timeout=10):
                      return
              except Exception as error:  # URL이 로그에 남지 않게 종류와 코드만 적는다
                  print(f"webhook 실패 {attempt + 1}/3: {type(error).__name__} {getattr(error, 'code', '')}", file=sys.stderr)
                  if attempt < 2:
                      time.sleep(5)
          raise SystemExit(1)


      main()
      ```

    - 알림 사용자: `sudo useradd --system --no-create-home --shell /usr/sbin/nologin qknotify`(sudo·docker 그룹 없음).
      `DynamicUser=yes`는 쓰지 않는다. 2026-10-25 이 인스턴스(systemd 249)에서 동적 사용자는 시스템 D-Bus에 붙지 못해
      `systemctl show`가 `Transport endpoint is not connected`로 실패했다. 일반 시스템 사용자는 성공했다.
    - 알림 유닛과 `qk-sync.service` drop-in:

      ```ini
      # /etc/systemd/system/qk-sync-notify@.service
      [Unit]
      Description=Notify Discord that %i failed (ADR-021)

      [Service]
      Type=oneshot
      User=qknotify
      Group=qknotify
      SupplementaryGroups=systemd-journal
      LoadCredential=webhook:/etc/qello-knowledge/notify.env
      ExecStart=/usr/local/libexec/qk-sync-notify %i
      TimeoutStartSec=2min
      NoNewPrivileges=yes
      PrivateTmp=yes
      ProtectSystem=strict
      ProtectHome=yes

      # /etc/systemd/system/qk-sync.service.d/notify.conf
      [Unit]
      OnFailure=qk-sync-notify@%n.service
      ```

      `sudo systemctl daemon-reload` 뒤 `systemd-analyze verify`로 두 유닛을 검사하고 `systemctl show qk-sync.service -p OnFailure`로 확인한다.
      되돌리기: `notify.conf`를 지우고 `daemon-reload`한다. 동기화는 알림 없이 이전처럼 돈다.
13. 알림 시험(색인을 돌리지 않는다, 0 Neurons):
    - 시험 유닛 `/etc/systemd/system/qk-sync-failtest.service`(`[Unit] OnFailure=qk-sync-notify@%n.service`, `[Service] Type=oneshot`, `ExecStart=/bin/false`)를 만들고
      `daemon-reload` → `systemctl start qk-sync-failtest.service`. 채널에 알림 1건이 오는지, 메시지에 보내지 않기로 한 값이 없는지 사람이 본다.
      확인 뒤 시험 유닛을 지우고 `systemctl reset-failed qk-sync-failtest.service`, `daemon-reload`한다.
    - 다음 예약 실행(성공)에는 알림이 없어야 한다: `journalctl -u qk-sync.service -u 'qk-sync-notify@*' --since <실행 날짜>`.

## 3. 공유 인스턴스 운영 규칙

- 자원: DB 컨테이너는 메모리 상한 안에서만 쓴다. 색인 실행 중 회의 봇이 느려지면 상한이나 실행 시각을 다시 정한다.
- 경계: 회의 봇 컨테이너·설정·데이터를 읽거나 바꾸지 않는다. 이 서비스의 자원은 `qk-postgres`, `qk-pgdata`, `/root/qk`, `qksync`, `/opt/qello-knowledge`, `/etc/qello-knowledge`, `qk-sync.service`·`qk-sync.timer`, 실패 알림의 `qknotify`·`/usr/local/libexec/qk-sync-notify`·`qk-sync-notify@.service`·`qk-sync.service.d/notify.conf`, `qkbastion`뿐이다.
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
- 실패 알림: `qk-sync.service`가 실패하면 팀 Discord 운영 알림 채널에 요약 1건이 온다(2절 12번, ADR-021). 메시지의 `run_id`로 `qk-index runs show <run_id>`를 본다.
  실행이 아예 돌지 않으면 알림이 없다. 가끔 `systemctl list-timers qk-sync.timer`의 LAST를 본다. 알림 유닛 자체의 실패는 `journalctl -u 'qk-sync-notify@*'`에만 남는다.
- 사용량: `qk-index usage`(같은 DB를 보는 환경에서).
- 정리: 예약 실행이 `usage prune`과 `runs prune`을 함께 돈다(보관 90일).
- 마이그레이션 순서: 예약 실행은 매번 최신 `main`을 받아 실행하고 마이그레이션은 돌리지 않는다. 새 마이그레이션이 든 PR은 병합 전에 2절 4번으로 운영 DB에 적용한다.
  적용하지 않으면 새 코드가 없는 테이블·함수를 불러 실행이 실패한다(2026-10-23 `0006_generation_usage`: `usage prune`이 실패할 뻔했다).
- 자원: Bastion 세션으로 `free -h`, `df -h /`, `sudo docker stats --no-stream`.

## 7. Discord 질의 서비스 (ADR-022, 사람 단계 H00~H03)

아래는 적용 전 절차다. 이 문서 작성으로 운영 구성·배포를 실행하지 않았다. 주소·토큰·계정 및 서비스 식별자는 `<...>`로만 표현한다.
근거는 [ADR-022](../sdd/decisions/ADR-022-discord-query-path.md), [research R-02·R-14](../../specs/QK-BOT-001-discord-ask/research.md),
[quickstart 3절](../../specs/QK-BOT-001-discord-ask/quickstart.md)이다. 각 명령은 사람이 인증하고 개별 승인한 뒤 실행한다.

### 7.1 시작 전 확인

- PR 리뷰에서 ADR-022 Accepted와 인스턴스 관리자 동의를 받는다. 제안 상태로 운영을 바꾸지 않는다.
- H00에서 Tunnel 요금, Worker·Tunnel 트래픽의 보존·학습 사용 정책을 공식 문서 URL과 함께 ADR-022 Data and cost에 기록한다. 유료 설정이나 미합의 데이터 처리가 필요하면 멈춘다.
- 인스턴스 바깥 방향 UDP 7844(QUIC)를 OCI egress·호스트 방화벽에서 읽기 전용으로 확인한다. 열 수 없으면 ADR-022의 대안을 재검토한다. 들어오는 DB·질의 포트와 공개 호스트명은 만들지 않는다.
- 운영 색인과 마이그레이션 연결 역할이 `qk.embedding_usage` 소유자나 슈퍼유저인지 관리자가 확인한다. 아래 조회는 승인한 관리 연결 안에서만 실행하고 값은 기록하지 않는다.

  ```sql
  SELECT current_user, c.relowner::regrole AS table_owner, r.rolsuper
  FROM pg_class c JOIN pg_roles r ON r.rolname = current_user
  WHERE c.oid = 'qk.embedding_usage'::regclass;
  ```

  두 연결을 각각 확인한다. 단순히 소유자 역할의 멤버라는 사실로 RLS 우회를 가정하지 않는다. 소유자·슈퍼유저가 아니면 필요한 정책을 별도로 승인받기 전 0007을 적용하지 않는다.
- 질의 서비스 전용 Workers AI 토큰은 PR #62 계정 교체 결과에 맞춘다. 기존 색인 토큰을 재사용하지 않는다. 봇 토큰은 운영 담당자의 로컬 등록 환경에만 둔다.

### 7.2 역할·릴리스·비밀값 준비

1. 코드가 main에 병합되기 **전**, 2절의 승인된 관리 터널로 마이그레이션을 적용한다. 관리 자격 증명 파일은 질의용 파일과 분리한다.

   ```bash
   uv run qk-migrate --env-file <migration-config-file> --dry-run
   uv run qk-migrate --env-file <migration-config-file>
   uv run qk-migrate --env-file <migration-config-file>
   ```

   두 번째 적용은 `applied=0`인지 확인한다. 0001~0006은 수정하지 않는다. 0007은 `qk_query NOLOGIN`, 최소 권한, 사용량 RLS만 더하고 PUBLIC EXECUTE를 거두지 않는다.
   승인한 관리 연결에서 `ALTER ROLE qk_query LOGIN;` 뒤 psql의 `\password qk_query`로 암호를 숨김 입력한다. 암호 리터럴·접속 URL을 명령행이나 SQL 이력에 넣지 않는다.
2. 관리자가 `qkquery` 시스템 사용자(로그인 셸 없음, sudo·docker 그룹 없음)를 만들고 기존 서비스와 권한을 분리한다. 이미 있으면 소속 그룹과 셸부터 확인한다.
   승인된 커밋의 별도 질의 릴리스 `<query-release-directory>`를 준비해 그 안에서 `uv sync --locked --no-dev --extra query --extra postgres`를 실행한다.
   준비·전환 명령과 갱신 절차는 7.6을 따른다.
   릴리스는 관리자 소유, `qkquery`에는 코드·설정·가상환경 읽기와 실행만 준다. `qksync`가 매일 갱신하는 체크아웃·가상환경을 공유하지 않는다(동기화의 의존성 정리가 query 의존성을 제거할 수 있다).
3. `/etc/qello-knowledge/query.env`는 root:qkquery, 0640이다. 값은 `getpass`로 터미널에서 숨겨 입력하고 원자적으로 교체한다. 아래 스크립트도 **사람이 서버에서만** 실행한다.

   ```bash
   sudo install -d -o root -g root -m 0755 /etc/qello-knowledge
   sudo python3 - <<'PY'
   import getpass
   import grp
   import os
   import tempfile

   names = ("DATABASE_URL", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID",
            "DISCORD_PUBLIC_KEY", "DISCORD_APPLICATION_ID", "QK_DISCORD_GUILD_ID",
            "QK_DISCORD_ALLOWED_CHANNELS", "QK_DISCORD_ALLOWED_ROLES")
   values = {name: getpass.getpass(name + ": ") for name in names}
   if any("\n" in value or "\r" in value for value in values.values()):
       raise SystemExit("여러 줄 값은 허용하지 않습니다")
   pending = None
   try:
       with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir="/etc/qello-knowledge", delete=False) as output:
           pending = output.name
           os.fchown(output.fileno(), 0, grp.getgrnam("qkquery").gr_gid)
           os.fchmod(output.fileno(), 0o640)
           for name, value in values.items():
               output.write(name + "=" + value + "\n")
       os.replace(pending, "/etc/qello-knowledge/query.env")
       pending = None
   finally:
       if pending is not None:
           os.unlink(pending)
   PY
   ```

   `DATABASE_URL`은 `qk_query`로 루프백 DB에 붙는다. 허용 채널은 빈 값이면 전부 거부하며 역할 목록은 비우면 역할 제한이 없다. `DISCORD_BOT_TOKEN`·터널 토큰은 이 파일에 넣지 않는다.
   파일 내용을 출력하지 않고 소유자·모드만 확인한다. 설정 검사는 릴리스의 `qk-query check --env-file /etc/qello-knowledge/query.env`로 값 없이 이름·상태만 확인한다.

### 7.3 qk-query.service

`<query-release-directory>`와 `<query-port>`를 승인한 릴리스 경로·비특권 포트로 바꾼다. 서버는 코드에서 루프백에만 바인딩한다.
기존 qk-sync.service의 격리 항목을 포함하고 다음을 둔다. R-14가 참조한 2절의 `qk-sync-notify@.service` 격리 항목(`NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`)을 모두 담고, 커널·제어 그룹 보호와 주소 체계·권한 제한, 메모리 상한을 더한다.

```ini
# /etc/systemd/system/qk-query.service
[Unit]
Description=Qello Knowledge Discord query service
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=qkquery
Group=qkquery
WorkingDirectory=<query-release-directory>
EnvironmentFile=/etc/qello-knowledge/query.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=<query-release-directory>/.venv/bin/qk-query serve --port <query-port> --env-file /etc/qello-knowledge/query.env
Restart=on-failure
RestartSec=5
TimeoutStopSec=65
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
CapabilityBoundingSet=
UMask=0077
Nice=10
MemoryMax=512M
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

쓰기 경로는 필요 없다. 메모리 상한은 공유 인스턴스 관리자와 확인할 초기값이며 실측값이 아니다.
`systemd-analyze verify /etc/systemd/system/qk-query.service` → `systemctl daemon-reload` → `systemctl enable --now qk-query.service` 순으로 실행한다.
`systemctl status qk-query.service`와 루프백의 `GET /healthz` 성공을 확인한다. journal의 일반 질의 로그는 원문 없는 JSON 한 줄이다.
2026-10-28(#58)부터 운영 유닛의 `<query-release-directory>`는 링크 `/opt/qello-knowledge-query-current`다(7.6).

### 7.4 Tunnel·Worker·Discord와 외부 접속 차단 확인

1. H00 뒤 원격 관리 터널 `<tunnel-id>`와 `cloudflared` 서비스를 준비한다. `cloudflared --version`으로 2025.7.0 이상인지 확인한다.
   터널 토큰은 서버의 전용 root 읽기 파일에 숨김 입력하고, 설치한 CLI의 도움말에서 지원하는 token-file 방식을 확인해 서비스에서 참조한다.
   토큰을 인자·이력·journal에 전달하는 방식은 쓰지 않는다. 공개 호스트명이나 호스트 ingress 규칙을 더하지 않는다. 서비스 상태와 터널 연결을 확인한다.
   H01(2026-10-26) 구성: 서비스 `qk-cloudflared.service`(`DynamicUser=yes`, `LoadCredential=tunnel-token:/etc/qello-knowledge/cloudflared-token`,
   `cloudflared --no-autoupdate tunnel --protocol quic run --token-file ${CREDENTIALS_DIRECTORY}/tunnel-token`, `MemoryMax=256M`). 토큰 파일(root:root 0600)은
   `sudo /usr/local/sbin/qk-tunnel-token-setup`으로 숨김 입력한다. 로그의 `Registered tunnel connection ... protocol=quic`과 Cloudflare 쪽 `healthy`로 확인한다.
2. Workers VPC Service `<vpc-service-id>`를 터널 `<tunnel-id>`와 대상 `<loopback-address>:<query-port>`에 연결하고, `wrangler.toml`의 `QUERY_SERVICE` 바인딩 placeholder를 사람이 바꾼다.
   Worker 설정은 `DISCORD_PUBLIC_KEY=<discord-public-key>`와 `QK_RELAY_TIMEOUT_SECONDS=<relay-timeout>`뿐이다. DB URL·Workers AI 토큰·봇 토큰은 두지 않는다.
   배포는 사람이 인증하고 `npx wrangler deploy -c <사본>`으로 한다. Worker는 TypeScript(`workers/relay/`, ADR-024)이고 VPC `fetch` 경로는 H01에서 확인했다(tasks.md "H01 배포 확인").
   실제 VPC Service ID는 저장소 밖 `wrangler.toml` 사본에 넣고 `-c`로 배포한다. 계정에 workers.dev 서브도메인이 없으면 비대화형 배포가 임의 이름으로 등록하므로, 배포 전에 대시보드에서 확인한다.
3. Discord 개발자 포털에 `<worker-interactions-url>`을 등록하고 서명 확인을 통과한다. 허용 밖 채널에서는 비공개 안내만 오는지 확인한다.
4. 운영 담당자의 로컬에서 `qk-query register-commands --env-file <local-register-config> --dry-run`으로 JSON을 확인한 뒤 같은 명령에서 `--dry-run`을 빼고 등록한다.
   봇 토큰은 로컬에서 숨김 입력한다. 서버 안의 기존 명령 목록을 통째로 바꾸므로 대상 `<application-id>`·`<guild-id>`를 사람이 확인한다.
5. SC-010은 인스턴스 밖 승인된 위치에서 `<instance-public-address>:<db-port>`와 `<instance-public-address>:<query-port>`로 접속이 실패하는지 확인한다.
   밖에서는 실패하고 안쪽 healthz·터널 경유는 성공하는 결과를 모두 기록한다(주소·ID 가림). 이 절차 작성 시점에는 모두 미실행이다.

### 7.5 되돌리기

관리자가 Discord 수신 주소를 해제해 새 요청을 멈추고, 진행 중 요청을 정리한 뒤 qk-query.service와 이번 질의 전용 cloudflared 서비스를 중지·비활성화한다.
다른 서비스가 공유하는 터널은 중지하지 않는다. Worker·VPC Service·터널 연결과 전용 토큰은 사람 승인 뒤 해제하고, query.env를 제거한다.
관리 연결에서 `ALTER ROLE qk_query NOLOGIN;`으로 새 DB 로그인을 막는다(이미 열린 연결을 끊는 명령은 아니므로 질의 서비스를 먼저 중지한다).
0007·사용량 기록·RLS는 유지하고 데이터 삭제나 기존 마이그레이션 변경으로 되돌리지 않는다. qk-sync의 코드·설정·역할을 건드리지 않으며 기존 색인 성공을 별도로 확인한다.
질의 릴리스 폴더(7.6의 `releases/`와 첫 릴리스), 링크 `/opt/qello-knowledge-query-current`, 유닛 백업도 지운다.
새 릴리스 하나만 옛 릴리스로 되돌릴 때는 이 절이 아니라 7.6 6번을 따른다.

### 7.6 질의 릴리스 갱신

질의 서비스는 `qk-sync`처럼 스스로 갱신하지 않는다. 질의 경로(`query/`, `discord/`, 질의가 가져오는 `domain/` 규칙, 질의 설정 기본값, 의존성)에 영향을 주는
병합 뒤에 사람이 승인해 갱신한다. 각 명령은 사람이 개별 승인하며 갱신 자체는 0 Neurons다.

구성(2026-10-28 #58부터):

- 릴리스: `/opt/qello-knowledge-query-releases/<commit>`(root:qkquery 0750). 공개 저장소 git 클론이고 `.venv`와 uv 관리 Python(`.python/`)을 릴리스 안에 둔다.
  가상환경의 실행 파일과 `pyvenv.cfg`가 절대 경로를 담으므로 릴리스 폴더를 옮기거나 이름을 바꾸지 않는다.
- 유닛 `qk-query.service`의 `WorkingDirectory`·`ExecStart`는 링크 `/opt/qello-knowledge-query-current`를 가리킨다. 갱신은 링크만 바꾸고 유닛은 고치지 않는다.
- 첫 릴리스 `/opt/qello-knowledge-query`(`3a5a98e`, H02)는 되돌리기용으로 남겼다. 이 구성으로 바꾸기 전 유닛은 `/root/qk-query.service.before-gh58`에 있다.

1. 대상 확인(로컬): `git diff <current-commit> <new-commit> -- src pyproject.toml uv.lock`로 질의 경로 변경, 새 설정 키, 의존성 변화를 본다.
   새 필수 키가 있으면 전환 전에 7.2 3번 방식으로 `query.env`를 바꾼다. 키 이름은 `sudo cut -d= -f1 /etc/qello-knowledge/query.env`로만 보고 값은 출력하지 않는다.
2. 새 릴리스 준비(서비스 영향 없음). 작업 사용자는 0750 폴더에 들어갈 수 없으므로 `cd` 대신 `uv --directory`를 쓴다. 실패하면 `"$NEW"`를 지우고 다시 한다.

   ```bash
   SHA=<new-commit>
   NEW=/opt/qello-knowledge-query-releases/$SHA
   sudo install -d -o root -g qkquery -m 0750 /opt/qello-knowledge-query-releases
   sudo git clone -q "$(sudo git -C /opt/qello-knowledge-query remote get-url origin)" "$NEW"
   sudo git -C "$NEW" checkout -q --detach "$SHA"
   sudo env UV_PYTHON_INSTALL_DIR="$NEW/.python" UV_PYTHON_PREFERENCE=only-managed \
     /usr/local/bin/uv --directory "$NEW" sync --locked --no-dev --extra query --extra postgres
   sudo chown -R root:qkquery "$NEW" && sudo chmod -R g+rX,g-w,o-rwx "$NEW"
   ```

3. 전환 전 확인: `sudo -u qkquery "$NEW/.venv/bin/qk-query" check --env-file /etc/qello-knowledge/query.env`가 누락·형식 오류 0이다(이름·상태만 출력한다).
   `sudo head -1 "$NEW/.venv/bin/qk-query"`가 `$NEW` 경로를 가리킨다.
4. 전환: 진행 중 질의가 끊길 수 있으므로 `journalctl -u qk-query.service --since -10min`에 최근 실행이 없는지 먼저 본다. 링크를 원자적으로 바꾸고 재시작한다.

   ```bash
   sudo ln -sfn "$NEW" /opt/qello-knowledge-query-current.tmp
   sudo mv -T /opt/qello-knowledge-query-current.tmp /opt/qello-knowledge-query-current
   sudo systemctl restart qk-query.service
   ```

5. 확인: `systemctl show qk-query.service -p ActiveState -p NRestarts`가 active, `sudo readlink /proc/<main-pid>/cwd`가 `$NEW`, 루프백 `GET /healthz`가 200,
   `qk-cloudflared.service`·`qk-sync.timer`가 active다. 필요하면 허용 밖 채널 `/ask` 1회(0 Neurons)로 Worker 경로를 확인한다.
6. 되돌리기: 4번과 같은 방식으로 링크를 직전 릴리스(처음에는 `/opt/qello-knowledge-query`)로 돌리고 재시작한 뒤 5번을 다시 확인한다.
   이 구성 이전으로 완전히 되돌리려면 유닛 백업을 `/etc/systemd/system/qk-query.service`로 복원하고 `systemctl daemon-reload`·재시작한 뒤 링크를 지운다.
7. 정리: 지금 릴리스와 직전 릴리스 하나를 남기고, 그보다 오래된 릴리스는 사람 승인 뒤 지운다. 릴리스 하나는 약 140~170 MB다.
