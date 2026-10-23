# Task Contract: 운영 저장소 OCI 구성·데이터 처리 정책 확인·운영 첫 색인과 예약 실행 (QK-SYN-001 사람 단계 H04~H07)

> Generated at: `2026-10-21`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-103` / https://tkv123.atlassian.net/browse/SCRUM-103 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: 해당 없음: 운영 구성 작업이다. ADR-008 변경 제안(2026-10-19) 확정과 QK-SYN-001 사람 단계 H04~H07(`specs/QK-SYN-001-incremental-sync/quickstart.md` 3절) 실행
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#50`
- Branch: `chore/SCRUM-103-gh-50-oci-production-store`
- Base branch: `main`. 2026-10-21 `origin/main` `e4fee77`(#49 병합)에서 분기했다. 2026-10-23 `origin/main` `4c66ff6`(#52 병합) 위로 rebase했다

## Objective

- 운영 저장소를 OCI Ampere A1 인스턴스(팀원 테넌시의 공유 인스턴스 `Qello-Meeting-Bot-Server`) 위 자체 운영 PostgreSQL로 확정한다(ADR-008 변경 제안 승인, 2026-10-21·2026-10-22 사용자 결정).
- H04: OCI 데이터 처리 정책(컴퓨트·블록 볼륨 내용의 학습 사용 여부, 보존 기간)을 확인해 결정 기록에 남기고 `config/store_policy.toml`을 더한다.
- 기존 인스턴스에 DB 컨테이너를 얹고 pgvector·PGroonga와 마이그레이션 0001~0004를 적용한다(QK-STO-001 T031 포함). 새 인스턴스·크기 변경은 하지 않는다.
- H05: 색인 CLI(로컬·GitHub Actions)의 연결 경로를 정하고 세션 advisory lock이 유지되는지 확인한다.
- H06·H07: 운영 첫 색인과 첫 인덱스 버전 활성화, 예약 실행을 OCI 인스턴스의 systemd 타이머로 구성하고 첫 실행 확인(ADR-020. 공개 저장소라 GitHub Actions 셀프 호스티드 러너를 쓰지 않는다).
- 함께: 로드맵 진행 상태 열을 GitHub Issue 상태에 맞게 갱신한다(`scripts/roadmap_status.py --write`).

## Scope

- `docs/sdd/decisions/ADR-008-runtime-and-cost-cap.md`: 변경 제안 확정, Decision의 저장 부분, 데이터 처리 정책 확인 결과, Approval
- `docs/sdd/decisions/ADR-019-github-backend-docs-source.md`: Data and cost의 저장소 정책 확인 문장을 OCI 결과로 갱신
- `compose.yaml`: 운영 저장소 표기 주석만
- `config/store_policy.toml`(새 파일): 제공자, 확인 날짜, 결정 기록 경로(QK-SYN-001 research R-13). 비밀값·접속 주소 없음
- `docs/ops/oci-production-store.md`(새 파일): 인스턴스 구성·연결·유휴 회수 대응·복구(재색인) 절차. 접속 주소·OCID·키는 placeholder로만 쓴다
- `specs/QK-SYN-001-incremental-sync/tasks.md`: 사람 단계 H04~H07 체크와 결과 기록
- `docs/sdd/roadmap.md`의 `상태`·`진행` 열(스크립트 출력만)
- `TASK.md`
- `docs/sdd/decisions/ADR-020-scheduled-sync-systemd-timer.md`(새 파일): 예약 실행을 systemd 타이머로 하는 결정(2026-10-23 사용자 결정)
- `tests/unit/indexer/test_run_cli.py`의 `test_remote_gates_before_runtime`: 정책 파일 경로를 없는 파일로 주입하는 것만(2026-10-23 사용자 결정. `config/store_policy.toml` 추가로 시험이 저장소 상태에 기대던 것이 드러났다)
- OCI 콘솔·인스턴스 작업(계정 소유자가 하거나 승인한 명령만): DB 컨테이너, 동기화 사용자 `qksync`, 코드 복제본, systemd 유닛·타이머, 비밀값 파일(값 입력은 사람)

## Explicit exclusions

- `src/`·`tests/`(위 시험 하나 제외)·`pyproject.toml`·`uv.lock`·마이그레이션·`.github/workflows/` 변경. `index-sync.yml`의 삭제·수정은 후속 작업이다(ADR-020). 코드 변경이 필요해지면 멈추고 별도 작업으로 한다.
- GitHub Actions 셀프 호스티드 러너 설치, 저장소 변수 `QK_SYNC_ENABLED` 생성, 저장소 공개 범위 변경.
- Workers 질의 경로의 DB 연결(QK-BOT-001), 백업·복구 절차 전체(QK-SYN-003), 미리 보기 예상식 보정(QK-EMB-001 후속).
- DB 포트를 공인 인터넷에 여는 설정. 유료 계정 전환·유료 자원 생성(별도 사람 승인).
- `AGENTS.md`, `CLAUDE.md`, `.claude/**`, constitution 수정. 로드맵 상태 열 외의 로드맵 내용.
- 원본 자료원에 쓰기.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 접속 주소, OCI 계정 식별자(OCID·테넌시·지문), 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음(기존 `dnd-backend-docs`)
- 외부 API로 보내는 데이터: 운영 첫 색인과 예약 실행에서 필터를 통과한 청크를 Workers AI bge-m3로 보낸다(기존 경로). 청크 본문·메타데이터를 OCI 인스턴스에 저장한다(새 저장 위치)
- 예상 임베딩·생성 호출량과 무료 한도 대비: 운영 첫 색인 약 900 Neurons(로컬 실측 894.50 기준, 하루 무료 10,000의 약 9%). 이후 변경 없는 날은 0. 실행 전 미리 보기로 다시 보고하고 승인받는다
- 인덱스 버전 변경: 없음. 운영 저장소에 `iv-4c0bc4fcc642`를 새로 만들고 활성화한다(같은 설정)
- 운영비: 팀원 PAYG 계정의 기존 인스턴스(추가 고정비 0원 목표, 크기 변경·새 유료 자원 없음. Bastion은 무료), GitHub Actions 실행 시간 0(예약 실행은 서버 타이머, ADR-020. 저장소는 공개라 기존 CI도 할당을 쓰지 않는다)

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `docs/sdd/decisions/ADR-008-*.md`, `ADR-019-*.md` | Byuntil | 사람 리뷰(결정 승인) |
| `config/store_policy.toml`, `compose.yaml` 주석 | Byuntil | 사람 리뷰 |
| `docs/ops/oci-production-store.md` | Byuntil | 사람 리뷰 |
| `specs/QK-SYN-001-incremental-sync/tasks.md` 사람 단계 기록, `docs/sdd/roadmap.md` 상태 열, `TASK.md` | Byuntil | 사람 리뷰 |
| OCI 계정·인스턴스, GitHub Secret·변수 | Byuntil | 계정 소유자 |

## Existing user-owned changes

- 2026-10-21 `origin/main`(`e4fee77`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
```

운영 확인(사람 승인 뒤): `qk-migrate --dry-run`·`qk-migrate`(운영 대상), `qk-index run --preview --allow-remote --json`, `qk-index run --allow-remote --json` 두 번, `qk-index index activate`, GitHub Actions 예약 실행 1회.

## Completion criteria

- 운영 저장소 결정(ADR-008)과 데이터 처리 정책 확인 결과가 기록되고 사람이 승인한다 — 결정 기록·PR 리뷰
- OCI 인스턴스의 PostgreSQL에서 pgvector·PGroonga 확장과 마이그레이션 0001~0004가 적용된다 — `qk-migrate` 결과, 확장 확인 기록
- 운영 저장소 첫 색인과 활성화 뒤 변경 없는 재동기화의 임베딩 호출이 0건이고, 예약 실행 1회가 성공한다 — `qk-index` 실행 기록, GitHub Actions 실행 기록

## Decisions

- 2026-10-21 사용자 결정: 운영 저장소를 OCI로 간다(ADR-008 변경 제안 채택 방향). OCI 계정은 사용자가 만들어 두었다.
- 2026-10-21 사실: 대안 조사(Supabase·Neon·Aiven·Koyeb·Xata·무료 VPS)에서 PGroonga까지 0원에 맞추는 곳은 Supabase Free뿐이었다. 사용자는 OCI를 골랐다.
- 2026-10-21 사실: OCI Always Free 현재 조건(공식 문서): A1 2 OCPU·12 GB(월 1,500 OCPU 시간·9,000 GB 시간), 블록 200 GB·백업 5개, 홈 리전 한정, A1은 South Korea North(춘천) 불가, 7일 유휴 회수.
  2026-06 A1 무료 범위가 4/24에서 2/12로 줄었다는 제3자 보도가 있다.
- 2026-10-21 사실: 에이전트가 사용자 요청으로 Jira `SCRUM-103`(SCRUM-42 하위 작업)과 GitHub `#50`을 만들었다.
- 2026-10-21 사실: 이 PC에는 OCI CLI와 `~/.oci` 설정이 없다. OCI 작업은 콘솔에서 사용자가 하거나, CLI를 설치·인증한 뒤 승인한 명령만 실행한다.
- 2026-10-21 사용자 결정: TASK.md 초안 승인. OCI 계정은 방금 등록한 Free Tier 계정이다. 이 PC에 OCI CLI를 설치·인증하고, 에이전트는 사용자가 승인한 OCI 명령만 실행한다(인증은 사용자가 직접). `~/.oci`의 키·토큰 파일은 에이전트가 읽거나 기록하지 않는다.
- 2026-10-21 사실: OCI CLI 3.95.1을 Homebrew로 설치했다. 사용자가 `oci session authenticate`(프로필 `qello`, 세션 토큰)로 직접 인증했다. API 개인 키는 만들지 않았다.
- 2026-10-21 사실(승인한 읽기 전용 명령): 홈 리전은 `ap-tokyo-1`(도쿄, READY)이다. 서울·춘천 등은 구독하지 않았다. 도쿄 가용 도메인은 1개다.
  compute 서비스 한도는 A1 리전 16 OCPU·96 GB(가용 도메인 41 OCPU·277 GB)로 나온다. 이 값은 무료 체험 기간의 서비스 한도로 보이며 Always Free 무료 사용량(월 1,500 OCPU 시간·9,000 GB 시간 = 2 OCPU·12 GB)과 다르다 `(추론)`.
  체험이 끝나면 무료 범위를 넘는 자원이 멈출 수 있으므로 인스턴스는 2 OCPU·12 GB 이하로 만든다. 계정 식별자는 출력·기록하지 않았다.
- 2026-10-21 사용자 결정: 예약 실행의 DB 연결은 OCI 인스턴스의 GitHub Actions 셀프 호스티드 러너로 한다(DB는 localhost, 들어오는 포트 없음). Scope에 워크플로 `runs-on`과 그 시험 기대값을 더했다.
- 2026-10-21 사실(H04 조사): Oracle Cloud Hosting and Delivery Policies 3.13(2026-09)에서 콘텐츠는 데이터 센터 리전 안에 저장·복제(Overview), Oracle 접근은 권한자로 제한(1.4),
  종료 뒤 회수 기간 유료 60일·무료 체험 30일 뒤 삭제(6.1)를 확인했다. Cloud Services Agreement(2016~2018년판 3.3)는 콘텐츠 사용 권한을 서비스 제공 목적으로 한정한다.
  학습 사용 금지를 명시한 문장은 찾지 못했고, AI Terms(2026-09-16)는 AI 기능에만 적용된다. 컴퓨트·블록 볼륨 내용은 학습에 쓰이지 않는다고 판단했다 `(추론)`.
  남은 사람 확인: 가입 때 동의한 Cloud Services Agreement 판.
- 2026-10-21 사실: ADR-008 확정 초안(Decision 저장 부분 OCI로, 변경 제안 "채택", 확정 사항, 데이터 처리 정책 갱신), ADR-019 추가 문장, `compose.yaml` 주석, `config/store_policy.toml`을 작성했다. 사람 승인 전이다.
- 2026-10-21 사용자 결정: ADR-008·ADR-019 확정 초안, `compose.yaml` 주석, `config/store_policy.toml`, H04 판단(학습 사용 없음은 추론)을 승인했다. 가입 때 동의한 Cloud Services Agreement 판 확인은 남아 있다.
- 2026-10-21 사실: 인스턴스 설계안 `docs/ops/oci-production-store.md` 작성(도쿄 AD-1, 컴파트먼트 `qello-knowledge`, A1 2 OCPU·12 GB Ubuntu 24.04, SSH만 작업자 IP /32, DB는 `127.0.0.1:5432` Docker,
  셀프 호스티드 러너 `qello-oci`, 유휴 회수는 재색인 복구로 받아들임). 운영 DB 포트 5432는 로컬 개발 포트와 달라 CLI가 원격으로 판정해 `--allow-remote`·정책 파일 검사가 유지된다. 사람 승인 전이다.
- 2026-10-21 사용자 결정: 인스턴스 설계안 `docs/ops/oci-production-store.md` 승인. 1단계(SSH 키)·1-1단계(공인 IP 확인)부터 실행한다.
- 2026-10-21 사실(사용자 승인 명령): OCI 도쿄에 컴파트먼트 `qello-knowledge`, VCN `qk-vcn`(10.20.0.0/16), 인터넷 게이트웨이 `qk-igw`, 경로 표 `qk-rt`(0.0.0.0/0 → IGW),
  보안 목록 `qk-sl`(들어오는 연결 TCP 22를 작업자 IP /32에서만, 나가는 연결 전체), 공개 서브넷 `qk-subnet-public`(10.20.1.0/24)을 만들었다. 모두 무료 자원. 식별자는 세션 임시 폴더에만 두고 기록하지 않았다.
  SSH 키 `~/.ssh/qello_oci`(ED25519, 암호 없음, 개인 키는 작업자 PC에만)를 만들었다. 4단계 이미지 후보: `Canonical-Ubuntu-24.04-aarch64-2026.09.18-0`.
- 2026-10-21 사실: 4단계 인스턴스 생성 시도 결과 — A1 2 OCPU·12 GB "Out of host capacity"(500), 1 OCPU·6 GB 첫 시도 TooManyRequests(429), 2분 뒤 재시도 "Out of host capacity"(500). 인스턴스는 만들어지지 않았다.
- 2026-10-21 사용자 결정: OCI는 도쿄 A1 용량 부족으로 보류하고 운영 저장소는 Supabase Free로 간다. 팀 공유 문서("운영 저장소 결정 경과 공유", Claude Docs)를 작성했다.
  후속: ADR-008을 Supabase 기준으로 되돌리고 OCI 변경 제안은 "채택하지 않음(용량 부족)"으로 정리, ADR-019·`compose.yaml`·`config/store_policy.toml`·`docs/ops/oci-production-store.md` 정리,
  Supabase 데이터 처리 정책 확인(H04), OCI에 만든 무료 네트워크 자원 정리 여부 결정. 이 TASK.md의 목표·범위도 Supabase 기준으로 고쳐 다시 승인받는다.
- 2026-10-22 사용자 결정: Supabase 전환을 거두고 운영 저장소를 다시 OCI로 간다. 팀원이 미리 만들어 둔 OCI 자원이 있고, 사용자는 그 테넌시의 IAM 접근을 받았다. 사용자 테넌시(도쿄)에 만든 무료 네트워크 자원은 남겨 둔다. 브랜치 이름과 `docs/ops/oci-production-store.md`는 OCI 기준으로 유지한다. 팀원 OCI 자원의 구성(리전·인스턴스·DB 유무·Always Free 여부)은 확인 전이다.
- 2026-10-22 사용자 답변: 팀원 테넌시는 유료(PAYG) 전환 계정이다. 팀원이 다른 서비스를 돌리는 인스턴스를 같이 쓰기로 했고, 그 안에 이 서비스용 구성이 이미 있을 수 있다(확인 전).
  이 PC에서는 팀원 테넌시용 새 OCI CLI 프로필을 사용자가 직접 인증하고, 에이전트는 승인한 명령만 실행한다.
  영향(추론): PAYG라 유휴 회수 위험은 줄지만 무료 범위를 넘으면 과금되므로 유료 자원 생성·크기 변경은 C-05 승인 대상이다. 계정 소유자가 팀원이므로 ADR-008 확정 사항의 계정·소유자, 인스턴스 공유 경계를 다시 쓴다.
- 2026-10-22 사실(사용자 승인 읽기 전용 명령, 프로필 `qello-team`): 팀원 테넌시 홈 리전은 `ap-osaka-1`(오사카)이다. 사용자 IAM은 루트 컴파트먼트 조회 권한이 없고(`NotAuthorizedOrNotFound`), 접근할 수 있는 컴파트먼트는 `dnd_Qello` 하나다.
  그 안의 인스턴스는 `Qello-Meeting-Bot-Server` 하나(`VM.Standard.A1.Flex` 1 OCPU·6 GB, RUNNING, 2026-10-13 생성)다. 다른 컴파트먼트의 A1 사용량은 보이지 않아 테넌시 전체가 무료 범위 안인지는 확인하지 못했다. 식별자는 세션 임시 폴더에만 두었다.
- 2026-10-22 사실(사용자 승인 읽기 전용 명령): `Qello-Meeting-Bot-Server`는 공인 IP가 있고 NSG는 없다. 서브넷 보안 목록의 들어오는 규칙은 TCP 22(0.0.0.0/0), ICMP(0.0.0.0/0), ICMP(VCN 범위 /16)뿐이다. DB 포트는 열려 있지 않다.
  SSH가 인터넷 전체에 열려 있어 설계안(작업자 IP /32만)과 다르다. 팀원 자원이므로 바꾸지 않고 팀원과 정할 항목으로 남긴다.
- 2026-10-22 사실: 사용자는 `Qello-Meeting-Bot-Server`에 SSH로 접속할 키가 없다. 3단계(인스턴스 안 확인)는 팀원에게 묻는 질문 목록으로 대신하고, 답을 받을 때까지 인스턴스 작업과 H05~H07은 멈춘다.
- 2026-10-22 사실(사용자 요청 읽기 전용 확인): 인스턴스 OS는 Canonical Ubuntu 22.04(aarch64). 에이전트 플러그인은 Run Command RUNNING, Bastion 비활성(STOPPED), 컴파트먼트에 Bastion 자원 없음.
  `dnd_Qello`에 붙은 IAM 정책은 보이지 않는다(정책이 루트에 있거나 조회 권한 없음). 작업자 PC에는 기존 키 `~/.ssh/qello_oci`(ED25519)가 있다.
  키를 만드는 것은 가능하지만 기존 인스턴스에 넣으려면 팀원이 `authorized_keys`에 공개 키를 더하거나, Bastion 플러그인 켜기·Bastion 생성, Run Command 권한 같은 팀원 자원 변경이 필요하다 `(추론)`.
- 2026-10-22 사용자 결정: 팀원(계정 소유자) 승인을 받아 Bastion 경로로 SSH 접속을 시도한다.
- 2026-10-22 사실(승인한 쓰기): `Qello-Meeting-Bot-Server` 에이전트 설정에서 Bastion 플러그인만 DISABLED→ENABLED로 바꿨다(나머지 플러그인·상위 플래그는 변경 전과 같음을 비교로 확인).
  `dnd_Qello`에 Bastion `qkbastion`(STANDARD, 대상 서브넷은 인스턴스 서브넷, 접속 허용은 작업자 공인 IP /32, 세션 최대 3시간)을 만들었다(무료). 보안 목록은 바꾸지 않았다.
  사용자 IAM이 인스턴스 갱신과 Bastion 생성을 허용함을 이로써 확인했다. 변경 전 에이전트 설정은 세션 임시 폴더에 두었다.
- 2026-10-22 사실: Bastion 플러그인은 켠 뒤 약 8분 만에 RUNNING이 됐다. 관리형 SSH 세션 `qk-check`(1시간, 사용자 `ubuntu`, 공개 키 `qello_oci.pub`)를 만들어 `whoami`·`uname -m`만 실행해 접속을 확인했다(`ubuntu aarch64`).
  호스트 키는 세션 임시 폴더의 known_hosts에만 두었다. 세션은 TTL이 지나면 끝나고, 다시 접속할 때마다 새 세션을 만든다.
- 2026-10-22 사실(사용자 승인 읽기 전용 확인, Bastion 세션): `Qello-Meeting-Bot-Server`는 1 OCPU, 메모리 5.8 GiB 중 사용 1.0 GiB·가용 4.6 GiB, 스왑 없음, 부하 0.00, 디스크 49 GB 중 40 GB 여유.
  컨테이너는 `meeting-bot-recorder`(약 66 MiB)와 `n8n`(약 429 MiB, `127.0.0.1:5678`)뿐이고 PostgreSQL은 호스트·컨테이너 모두 없다. 이 서비스용으로 미리 만든 것은 없다.
  듣는 포트는 22(sshd), 111(rpcbind), 127.0.0.1:5678, 로컬 DNS. 호스트 iptables는 22·ICMP·lo·기존 연결만 받고 나머지는 거부한다(ufw 비활성). SSH는 비밀번호·키보드 대화형 로그인 꺼짐, root는 키만(`without-password`).
  `ubuntu`는 비밀번호 없이 sudo를 쓸 수 있다. 판단 `(추론)`: 가용 4.6 GiB면 PostgreSQL(공유 버퍼를 작게)·러너·하루 1회 색인을 크기 변경 없이 올릴 수 있다. 크기 변경(과금 가능)은 지금 필요 없다.
- 2026-10-22 사실: 이 환경 기준으로 `docs/ops/oci-production-store.md`(오사카·팀원 PAYG 계정·공유 인스턴스·Bastion 접속·DB 메모리 상한·얹는 순서), ADR-008 확정 사항·대가와 위험·데이터 처리 정책, ADR-019 문장,
  `config/store_policy.toml`(provider·checked_at·decision_record 앵커), TASK.md Objective·운영비 문구를 고친 초안을 작성했다. 사람 승인 전이다.
- 2026-10-23 사용자 결정: 2026-10-22 초안(`docs/ops/oci-production-store.md`, ADR-008·ADR-019, `config/store_policy.toml`, TASK.md 문구)을 승인했다. 추론 항목(PAYG 유휴 회수 미해당, 보존 60일, 메모리 상한 값)은 표시한 채 둔다.
- 2026-10-23 사실(사용자 승인 명령, Herdr 오른쪽 패널에서 실행): Bastion 세션 `qk-db-setup`(3시간)을 만들고 `Qello-Meeting-Bot-Server`에 DB 컨테이너를 구성했다.
  `supabase/postgres:17.11.0.004`(arm64, 기본 CMD `postgres -D /etc/postgresql`, 약 1.7 GB)를 받고, `/root/qk/postgres.env`(디렉터리 700·파일 600, root)에 무작위 비밀번호를 두었다(출력·기록 안 함).
  `qk-postgres`는 `127.0.0.1:5432`에만 듣고, 재시작 정책 `unless-stopped`, 메모리 상한 1.5 GiB, `shared_buffers` 256MB, 볼륨 `qk-pgdata`다. 띄운 직후 사용 메모리는 약 127 MiB, 호스트 가용 4.5 GiB다. 회의 봇 컨테이너는 건드리지 않았다.
  확장 확인(T031) 첫 실행은 `docker exec`에 `-i`가 빠져 SQL이 전달되지 않았고(출력 없음), 고쳐 다시 실행해 `postgres`(superuser 아님)로 `CREATE EXTENSION vector`·`pgroonga` 성공, pgvector 0.8.2·PGroonga 3.2.5를 확인했다. 결과를 ADR-008에 적었다.
- 2026-10-23 사실(사용자 승인 명령, Herdr 오른쪽 패널): Bastion 세션 경유 SSH 터널(작업자 `127.0.0.1:15432` → 서버 `127.0.0.1:5432`)로 운영 DB에 마이그레이션을 적용했다. 비밀번호는 셸 변수로만 받았다.
  `qk-migrate --dry-run`: `target=remote`, pending 0001~0004. `qk-migrate`: `applied=4 skipped=0`. 재실행: `applied=0 skipped=4`. 첫 시도는 SSH 제어 소켓 경로가 너무 길어 터널을 열기 전에 실패했다(적용 없음). 스크립트의 종료 trap이 파이프 안 서브셸에서 돌지 않아 터널이 남았고, 그 ssh 프로세스를 직접 종료해 닫았다.
- 2026-10-23 사실(사용자 승인 명령, Herdr 오른쪽 패널, 터널 경유): 운영 DB 대상 `qk-index run --preview --allow-remote --json` 성공(`target=remote`, 정책 파일 검사 통과, 터널 정상 종료).
  `dnd-backend-docs` FULL, GitHub 요청 83회, 문서 80건 중 PASSED 79·SECRET_BLOCKED 1(`env-assigned-secret`), 청크 1,291개(토큰 중앙값 224, 최대 2,776), 보류·내림 없음.
  인덱스 `iv-4c0bc4fcc642`, 규칙 `sec-7222e5dd1d6e`, 청킹 `chk-md-20d966f730bb`, 활성 버전 없음. 예상 Neurons 368.93(색인 일일 예산 5,000 중 사용 0). 미리 보기의 임베딩 호출 0.
  로컬 실측(894.50)보다 낮은 것은 알려진 예상식 과소 추정(QK-EMB-001 후속)이며 실제 소비는 약 900으로 본다 `(추론)`.
- 2026-10-23 사실(사용자 승인 명령, Herdr 오른쪽 패널, 터널 경유): 운영 첫 색인 `qk-index run --allow-remote --json` 1회차 `sync-20261023T075442-2f24051c` succeeded(`target=remote`, `iv-4c0bc4fcc642`):
  PROCESS 79·SKIP 1, 청크 1,291, 임베딩 요청 1,291·제공자 호출 94·**사용 Neurons 894.50**(같은 실행의 예상 398.87). 보류·내림·실패 없음.
  2회차 `sync-20261023T080122-16d16ba5` succeeded: UNCHANGED 79·SKIP 1, 임베딩 요청 0·제공자 호출 0·Neurons 0. 두 실행 모두 종료 코드 0, 터널 정상 종료. 인덱스는 아직 활성화하지 않았다(`index_active=false`).
- 2026-10-23 사실(사용자 승인 명령, Herdr 오른쪽 패널, 터널 경유): `qk-index index activate iv-4c0bc4fcc642 --allow-remote --json` 성공(문서 79, 청크 1,291, 벡터 없는 청크 0, 마지막 실행 succeeded, 실패 조건 없음).
  `qk-index index status --json`: `active=current=iv-4c0bc4fcc642`, `matches=true`. `runs list`에 두 실행이 succeeded로 남아 있다. H06 완료.
  (상태 확인 첫 시도는 읽기 전용 `status`에 `--allow-remote`를 붙여 인자 오류로 실행되지 않았고, 옵션을 빼고 다시 실행했다.)
- 2026-10-23 사실(사용자 요청): 워크플로 `runs-on`을 `[self-hosted, linux, ARM64, qello-oci]`로 바꾸고 시험 기대값에 그 줄을 더했다. `specs/QK-SYN-001-incremental-sync/tasks.md`에 H04(진행 기록, 미완)·H05·H06(완료)·H07(진행 기록) 결과를 적었다.
- 2026-10-23 사실(읽기 전용 확인): 이 저장소 `Qello-Labs/qello-knowledge`는 **공개(PUBLIC)** 저장소다. 앞서 TASK.md·대화에서 "비공개 저장소"라고 적은 것은 틀렸다. 조직 플랜 free, Actions 허용 `all`, 포크 PR 워크플로 승인 정책 `first_time_contributors`, `pull_request` 트리거 워크플로는 `ci.yml`.
  공개 저장소의 셀프 호스티드 러너는 포크 PR이 러너(팀원 공유 서버, 같은 서버의 n8n `127.0.0.1:5678` 포함)에서 코드를 실행할 위험이 있고 Actions 로그가 공개된다 `(추론)`. 러너 설치는 진행 방식을 사람이 정할 때까지 멈춘다. 러너 최신 릴리스는 v2.338.1(2026-10-22 공개).
- 2026-10-23 사용자 결정: 예약 실행은 OCI 인스턴스의 systemd 타이머로 한다. 저장소는 공개로 둔다. 이유: 비공개 전환 시 CI 한도 소모, 외부 공개 용도, 공개 저장소 셀프 호스티드 러너의 보안 문제, 작업량이 작아 별도 실행 환경이 필요 없음.
  결정은 ADR-020(한국어, ASD-STE-100 원칙)으로 남긴다. Scope·제외 범위·운영비를 이에 맞게 고쳤다.
- 2026-10-23 사실: 워크플로 `runs-on`과 시험 기대값 변경을 되돌렸다(`main`과 같음). ADR-020 작성, ADR-008 색인 연결 문장, `docs/ops/oci-production-store.md`(타이머 설계·순서·운영 확인), tasks.md H05·H07 기록을 고쳤다. 사람 승인 전이다.
- 2026-10-23 사용자 결정: ADR-020 초안과 타이머 방식으로 고친 문서(ADR-008 색인 연결, 운영 문서, tasks.md, TASK.md Scope·제외 범위·운영비)를 승인했다.
- 2026-10-23 사실(사용자 승인 명령, Herdr 오른쪽 패널): Bastion 세션 `qk-timer-setup`으로 ADR-020 타이머를 설치했다(타이머는 켜지 않음, `disabled/inactive`).
  `qksync`(uid 996, 추가 그룹 없음), `uv` 0.13.1(SHA-256 확인, `/usr/local/bin`), `/opt/qello-knowledge`(`main` `4c66ff6`, 11 MB), 의존성·Python(`/var/lib/qksync` 148 MB), `qk-index` 실행 확인,
  `/etc/qello-knowledge/sync.env`(750/640 root:qksync, `DATABASE_URL`만), `/usr/local/libexec/qk-sync`, `qk-sync.service`·`qk-sync.timer`(`systemd-analyze verify` 통과, 다음 예정 2026-10-24 00:30 UTC).
  verify 경고는 기존 시스템 유닛(OCI 에이전트·snapd)의 것이며 우리 유닛과 무관하다.
- 2026-10-23 사실(읽기 전용): `origin/main`이 이 브랜치 기준 `e4fee77`보다 10커밋 앞서 있다(#51·#52, QK-RET-001). 새 마이그레이션 `0005_retrieval.sql`은 검색 함수만 더한다.
  기준 키워드 규칙에서는 청킹 버전이 바뀌지 않는다(`chunking/version.py`). 운영 DB에는 0005가 아직 없다. PR 전에 이 브랜치를 `origin/main` 위로 옮겨야 한다.
- 2026-10-23 사실: 사용자가 오른쪽 패널에서 숨김 입력으로 `GITHUB_API_TOKEN`·`CLOUDFLARE_API_TOKEN`·`CLOUDFLARE_ACCOUNT_ID`를 `sync.env`에 넣었다. 에이전트는 `키=<설정됨>` 네 줄과 완료 표시만 확인했고 값은 보지 않았다.
- 2026-10-23 사실(사용자 승인): 변경을 6개 커밋으로 나누고 `origin/main` `4c66ff6` 위로 rebase했다. 충돌은 TASK.md 하나였고 이 브랜치의 계약을 그대로 두었다.
- 2026-10-23 사실(사용자 승인 명령, Herdr 오른쪽 패널, 터널 경유): 운영 DB에 `0005_retrieval` 적용. dry-run `pending 0005 retrieval`만 → `applied=1 skipped=4` → 재실행 `applied=0 skipped=5`.
  `postgres`(superuser 아님)로 0005의 PGroonga 설정(`SET pgroonga.match_escalation_threshold`)이 권한 오류 없이 만들어졌다.
- 2026-10-23 사실: PR 전 전체 검증에서 `test_remote_gates_before_runtime`이 실패했다(1 failed, 1505 passed). 시험이 기본 경로 `config/store_policy.toml`이 없다는 저장소 상태에 기대고 있었다.
  사용자 결정으로 이 PR에서 시험에 없는 정책 파일 경로를 주입했다(검사 강도 그대로, 삭제·skip 없음). PR은 Draft, 리뷰어 없음으로 정했다.
