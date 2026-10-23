# Decision Record: ADR-008 실행 환경·비용 상한

> Created at: `2026-10-10`
> ClickUp 작업: 해당 없음: 초기 세팅 단계 예외(WBS 0.9)
> 기능명세서 ID: 해당 없음: Phase 0 준비 작업
> Status: Proposed

## Context

Phase 1 구현 전에 시스템이 돌아갈 환경과 비용 상한을 정해야 한다. constitution C-05가 추가 고정비 상한을
이 결정에 맡기고, QK-FND-001(골격·배포), QK-STO-001(저장), QK-SYN-001(스케줄러), QK-BOT-001(Discord 수신)이
모두 이 결정에 달려 있다.

지켜야 할 조건은 네 가지다. Discord `/ask`가 3초 안에 처리 중 응답을 보낸다(1.G). 하이브리드 검색이 벡터와
키워드를 한 DB에서 한다(QK-RET-001). 동기화가 정해진 주기로 돈다(2.G). 추가 고정비가 상한 안이다(C-05).

데이터 규모는 작다. Phase 1 대상 문서 원문이 1,083 KB이고 Phase 2 코드까지 합쳐 약 10 MB다.

## Decision

질의응답은 Cloudflare Workers에서 실행하고, 저장은 Oracle Cloud Infrastructure(OCI) Ampere A1 인스턴스(팀원 테넌시의 공유 인스턴스) 위의 자체 운영
PostgreSQL(pgvector·PGroonga)에 둔다(아래 2026-10-19 변경 제안을 채택. 처음 결정은 Supabase 무료 플랜이었다).
색인은 Workers 밖(GitHub Actions 또는 로컬 CLI)에서 실행한다. 추가 고정비 상한은 월 0원이고, 종량 호출은
Workers AI 무료 할당(하루 10,000 Neurons) 안에서 쓴다.

## Rationale

- Workers Free는 하루 100,000 요청을 처리한다. 하루 질문 50건 기준에 넉넉하다. Workers 안에서는 `env.AI`
  바인딩으로 Workers AI를 호출하므로 운영에서 Cloudflare REST 토큰을 들고 있지 않아도 된다.
- 색인을 Workers에 두지 않는 이유는 Workers Free의 **요청당 subrequest 50개**와 **CPU 10 ms** 한도다.
  파일 N개 읽기와 임베딩 N회를 한 호출에 담을 수 없고, Cron Trigger도 같은 CPU 한도를 받는다. 배치를 쪼개
  여러 번 깨우는 구조로도 가능하지만 QK-SYN-001에 재개 상태 설계가 추가된다. 색인을 밖으로 빼면 Phase 1
  범위를 넓히지 않고도 같은 결과를 얻는다.
- Supabase Free는 PGroonga를 확장 목록에 올려 둔다. PGroonga는 CJK를 기본 지원하므로 한국어 키워드 검색
  (RISK-05, ADR-010)의 선택지가 넓어진다. Neon 문서에서는 pgroonga·pg_bigm 지원 근거를 찾지 못했다.
- Supabase Free 저장 한도 500 MB는 위 데이터 규모 안이다.
- 추가 고정비가 0원이라 C-05를 지킨다. 유료 전환이 필요해지면 사람 승인을 받는다.

## Alternatives considered

| Alternative | Advantages | Disadvantages | Reason not selected |
| --- | --- | --- | --- |
| 팀 dev 테스트 서버(EC2 `t3.small`)에 컨테이너 추가 | 추가 고정비 0원. `infra/environments/dev`의 Terraform을 재사용한다. 자동 정지 설정을 없애 상시 가동이 됐다(사용자 확인 2026-10-10) | 제품 테스트 서버와 CPU·메모리·장애를 공유한다. `t3.small`에 Postgres를 하나 더 올리는 부담이 있다 | 팀 공용 지식 시스템을 제품 테스트 서버에 얹지 않는다 |
| 전용 소형 VM 신설 | `docker compose` 전제를 그대로 쓴다. 상시 가동과 디스크를 직접 통제한다 | 고정비가 0~2만 원/월 생긴다. 백업·보안 패치를 직접 한다. 단일 장애점이다(RISK-08) | 추가 고정비 0원과 무료 플랜 운영 조건 |
| 색인까지 전부 Workers | 운영 지점이 한 곳이다. Cron Triggers로 주기를 관리한다 | subrequest 50개·CPU 10 ms 때문에 배치 재개 상태를 DB에 둬야 한다. Cron Trigger는 계정당 5개다 | QK-SYN-001 범위가 커진다. 필요가 확인되면 옮긴다 |
| Neon Free + Workers | 저장 1 GB로 더 크다. 100 CU-h/월 | pgroonga·pg_bigm 지원 근거를 못 찾았다. 5분 유휴 뒤 scale to zero를 Free에서 끌 수 없다 | 한국어 키워드 검색 선택지가 좁다 |
| 팀원 PC·홈서버 상시 가동 | 고정비 0원 | 토큰이 개인 기기에 남는다(C-09). 팀 공용 시스템의 가동이 개인에 묶인다 | 운영 연속성과 비밀값 보관 |

## Evidence

- Workers Free 한도(요청 100,000/일, CPU 10 ms/요청·Cron, subrequest 50, 동시 외부 연결 6, Cron Trigger 계정당 5,
  초과 시 오류 1027): https://developers.cloudflare.com/workers/platform/limits/ (조회 2026-10-10)
- Workflows Free 한도(스텝당 CPU 10 ms, 스텝 1,024개, 완료 상태 보관 3일):
  https://developers.cloudflare.com/workflows/reference/limits (조회 2026-10-10). 문서 개정 중이라 수치가 바뀔 수 있다
- Hyperdrive Free 한도(설정 10개, 원본 연결 약 20개, 쿼리 60초):
  https://developers.cloudflare.com/hyperdrive/platform/limits/ (조회 2026-10-10)
- Supabase 확장 목록에 PGroonga가 있다: https://supabase.com/docs/guides/database/extensions (조회 2026-10-10)
- Supabase Free 한도(프로젝트 2개, DB 500 MB, 송신 5 GB, 비활성 시 일시정지):
  https://supabase.com/docs/guides/platform/billing-on-supabase (조회 2026-10-10)
- Neon Free 한도와 pgvector: https://neon.com/docs/introduction/plans , https://neon.com/docs/extensions/pgvector
  (조회 2026-10-10)
- Workers AI 무료 할당과 초과 동작: `docs/sdd/research/spike-workers-ai.md` 6절
- 데이터 규모: `docs/sdd/research/inventory.md` 1.2·1.3절
- 팀 dev 서버 현황: 같은 문서 3.1절과 2026-10-10 사용자 확인(자동 정지 설정 제거)

## Data and cost

- 외부로 전송되는 데이터와 제공자의 학습 사용·보존 정책: 질의와 검색된 청크를 Cloudflare Workers AI로 보낸다
  (`spike-workers-ai.md` 7절). 청크 본문과 메타데이터는 Supabase 관리형 PostgreSQL에 저장된다.
  **Supabase의 데이터 처리 정책은 확인하지 않았다.** AGENTS.md 3.1에 따라 프로젝트를 만들기 전에 확인하고
  이 기록에 추가한다.
- 무료 한도와 예상 사용량: Workers 100,000 요청/일 대비 하루 50건. Workers AI 10,000 Neurons/일 대비 전체 색인
  1회 약 325 + 생성 50건 약 330. Supabase 500 MB 대비 원문 약 10 MB와 벡터·인덱스.
- 교체 시 영향: 실행 환경을 바꾸면 QK-FND-001 골격과 배포 절차를 고친다. 저장소를 바꾸면 원본에서 전체
  재색인으로 복구한다(RISK-08).

## Consequences

### Positive

- 추가 고정비가 0원이다. 서버 가동·패치 관리가 없다.
- Workers 안에서 `env.AI` 바인딩을 쓰므로 운영 환경에 Cloudflare REST 토큰을 두지 않는다(`tokens.md` T-03 해소 경로).
- 색인과 질의가 분리돼, 색인 실패가 `/ask` 가용성에 영향을 주지 않는다.

### Negative / risks

- Workers Free의 CPU 10 ms와 subrequest 50개는 질의 경로에도 적용된다. 후보 확장이나 재순위를 Worker 안에서
  많이 호출하면 걸린다(QK-RET-001, 6.4 QK-RET-003 설계 제약).
- 색인 실행 주체가 저장소 밖에 생긴다. 2.G의 "정해진 주기로 동기화" 증빙을 GitHub Actions 실행 기록으로 남겨야 한다.
- Supabase Free는 비활성 기간 뒤 프로젝트를 일시정지한다. 정지까지의 정확한 기간을 확인하지 못했다.
- Supabase의 데이터 처리 정책을 확인하지 않았다(위 Data and cost).
- PGroonga가 Supabase 대시보드에서 실제로 켜지는지 확인하지 않았다. 공식 확장 목록에 있다는 것까지만 확인했다.
- Cron Trigger가 계정당 5개다. 자료원별로 주기를 나누면 Phase 3~4에서 모자랄 수 있다.
- Workers Free 일 100,000 요청을 넘으면 오류 1027로 막힌다. 하루 50건 기준에서는 멀지만 봇 재시도 폭주 시 위험이다.

## Revisit conditions

- 하루 질문이 50건을 크게 넘거나, 질의 경로가 Workers Free의 CPU·subrequest 한도에 걸릴 때.
- Supabase Free 저장 500 MB 또는 월 송신 5 GB의 80%를 넘을 때.
- PGroonga를 쓸 수 없는 것으로 확인될 때. Neon과 자체 호스팅을 다시 비교한다.
- Workers 밖 색인이 주기를 못 지킬 때. 전부 Workers(배치 재개) 구조로 옮긴다.
- 유료 전환이 필요해질 때. C-05에 따라 사람 승인을 받는다.

## Follow-ups

이 결정이 다른 문서에 남기는 수정이다. 이 작업(0.9)에서는 고치지 않는다.

- `docs/sdd/research/inventory.md` 3.1절의 "매일 새벽 3시 정지, 자동 시작 없음"과 104줄, 3.2절 F-7 판단을 갱신한다.
- `docs/sdd/research/tokens.md` 6절 보관 위치와 T-03을 Workers 기준으로 갱신한다.
- `docs/sdd/roadmap.md` QK-FND-001 산출물의 `docker compose`를 로컬 개발·테스트 범위로 좁힌다.
  로드맵 수정은 사람 승인을 받는다.
- Supabase 데이터 처리 정책 확인과 PGroonga 활성화 확인을 QK-STO-001 명세(0.11)의 작업으로 넣는다.
- `docs/sdd/constitution.md` 변경 이력이 "미합의 — Phase 0 리뷰에서 확정"으로 남아 있다. WBS 0.1은 끝났으므로
  (2026-10-10 사용자 확인, 0.4 작업 계약 기록) 합의 상태를 갱신한다. 원칙 문서 수정은 사람 승인을 받는다.

## 변경 제안 (2026-10-19): 운영 저장소를 Oracle Cloud Always Free 인스턴스로

> 상태: 채택(2026-10-21 사용자 결정, SCRUM-103·#50). 2026-10-19 사용자가 QK-STO-001 작업 중 "운영 저장소는 아마 Oracle Cloud 프리티어급 인스턴스로 바꾼다"고 정했고,
> 2026-10-21 대안(Supabase·Neon·Aiven·Koyeb·Xata·무료 VPS) 비교 뒤 OCI로 확정했다. 위 Decision의 저장 부분을 이 절로 바꿨다. 이 기록의 승인은 PR 리뷰로 받는다.
> 경과: 2026-10-21 작업자 테넌시(도쿄)에서 A1 인스턴스 생성이 "Out of host capacity"로 실패해 같은 날 Supabase Free로 잠시 돌렸다가,
> 2026-10-22 팀원 테넌시의 기존 A1 인스턴스를 같이 쓰기로 하고 OCI로 되돌렸다(사용자 결정).

### 확정 사항 (2026-10-22 갱신)

- 계정: 팀원 테넌시(유료 Pay As You Go 전환 계정)다. 계정 소유자는 팀원이고, 작업자는 컴파트먼트 `dnd_Qello`의 IAM 접근을 받았다(루트 컴파트먼트는 못 본다). 홈 리전은 오사카(`ap-osaka-1`)다.
- 인스턴스: 새로 만들지 않고 기존 `Qello-Meeting-Bot-Server`(A1 Flex 1 OCPU·6 GB, Ubuntu 22.04 aarch64)를 회의 봇과 같이 쓴다.
  2026-10-22 실측 가용 메모리 4.6 GiB·디스크 여유 40 GB로 크기 변경 없이 올린다 `(추론)`. DB 컨테이너에 메모리 상한을 둔다.
  PAYG라 테넌시 전체 A1 사용량이 무료 범위를 넘으면 과금되고, 작업자는 다른 컴파트먼트를 볼 수 없으므로 크기 변경·새 유료 자원은 팀원 확인과 C-05 승인 뒤에만 한다.
- 작업자 접속: OCI Bastion `qkbastion`(무료, 작업자 공인 IP /32만 허용)의 관리형 SSH 세션으로 한다. 이를 위해 인스턴스의 Bastion 플러그인을 켰다(2026-10-22, 팀원 승인).
- 색인 연결: 예약 실행은 인스턴스의 systemd 타이머로 돌고 DB에는 `localhost`로 붙는다(ADR-020. 저장소가 공개라 셀프 호스티드 러너는 쓰지 않는다).
  DB 포트는 인터넷에 열지 않는다(보안 목록·호스트 iptables 모두 22만 받음). 작업자의 수동 실행은 Bastion 세션의 SSH 터널로 한다. Workers 질의 경로의 연결은 그대로 QK-BOT-001에서 정한다.
- 작업자 테넌시(도쿄)에 만든 무료 네트워크 자원(컴파트먼트·VCN·서브넷·게이트웨이·경로 표·보안 목록)은 남겨 둔다(2026-10-22 사용자 결정).
- 구성과 절차는 `docs/ops/oci-production-store.md`에 둔다.

### 제안 내용

운영 저장소를 Supabase Free 관리형 PostgreSQL에서 Oracle Cloud Infrastructure(OCI) Always Free Ampere A1 인스턴스 위의
자체 운영 PostgreSQL로 바꾼다. 이미지는 로컬 개발 DB와 같은 `supabase/postgres:17.11.0.004`(arm64 태그 있음, pgvector·PGroonga 포함)를 쓴다.
질의응답(Cloudflare Workers), 색인 분리, 고정비 상한 월 0원은 그대로다.

### 근거

- PGroonga를 우리가 직접 켠다. 로컬 개발 DB(aarch64)와 같은 이미지라 Supabase 대시보드 활성화 여부(위 Negative / risks)에 기대지 않는다.
  QK-STO-001 ADR-007 스파이크에서 같은 이미지의 pgvector 0.8.2·PGroonga 3.2.5로 한국어·식별자 검색을 확인했다.
- 저장 한도: Always Free 블록 볼륨이 부트 볼륨 포함 200 GB다. Supabase Free 500 MB보다 크다.
- Supabase Free의 비활성 일시정지가 없다. 대신 아래 유휴 회수 위험이 있다.

### 대가와 위험

- **유휴 인스턴스 회수**: 7일 동안 CPU 95번째 백분위 20% 미만, 네트워크 20% 미만, 메모리 20% 미만(A1만)이면 Oracle이 회수할 수 있다.
  2026-10-22: 쓰는 계정이 PAYG라 이 회수는 해당하지 않는다고 본다 `(추론, 공식 문서 확인 필요)`.
  하루 질문 50건 규모의 DB는 이 조건에 걸릴 가능성이 높다. 대응(유료 계정 전환 시 Always Free 무과금 유지 여부, 메모리 사용률 유지 등)을 정하기 전에는
  실제 팀 자료의 유일한 사본을 두지 않는다. 원본에서 전체 재색인으로 복구할 수 있어야 한다(RISK-08).
- **운영 부담**: 백업, 보안 패치, 디스크 관리, 단일 장애점을 팀이 맡는다. 이 기록의 Alternatives에서 "전용 소형 VM 신설"을 뺀 이유 중 고정비는 사라지지만
  운영 부담은 그대로 남는다.
- **용량 확보**: 홈 리전에서만 만들 수 있고, "out of host capacity"로 일시적으로 못 만들 수 있다. 2026-10-21 도쿄에서 실제로 실패했다.
- **공유 인스턴스**: 회의 봇과 CPU·메모리·디스크를 나눠 쓰고, 단일 장애점도 공유한다. 팀원(인스턴스 관리자)은 DB 내용을 볼 수 있다(저장하는 것은 팀 공용 자료 청크뿐).
  팀원이 인스턴스를 재생성·종료하면 DB를 잃으므로 미리 알리기로 하고, 잃으면 재색인으로 복구한다(RISK-08).
- **Workers 연결**: Supabase Data API가 없어진다. Python Workers에서 TCP 드라이버를 쓸 수 없으므로 인스턴스에 HTTP RPC 계층(예: PostgREST)을 두고
  공인 포트를 열지 않는 경로(예: Cloudflare Tunnel)로 연결하는 방안을 QK-BOT-001에서 정한다. QK-STO-001은 검색을 SQL 함수로 두어 어느 쪽이든 쓸 수 있다.
- **계정**: 팀원 계정은 이미 PAYG다. 무료 범위를 넘는 자원은 바로 과금되므로 C-05에 따라 사람 승인을 받는다.

### 데이터 처리 정책 (QK-STO-001 FR-022, QK-SYN-001 H04 확인 결과)

- 저장 위치: 팀원 테넌시의 VM 부트 볼륨이다. 관리형 DB 서비스가 아니므로 DB 내용을 제공자 서비스가 처리하지 않는다. 콘텐츠는 서비스의 데이터 센터 리전(오사카, APAC)에 저장되고,
  Oracle은 중복을 위해 같은 리전 안에만 복제할 수 있다(Hosting and Delivery Policies 3.13, Overview).
- Oracle의 접근: Oracle 관리 구성 요소에서 고객 콘텐츠 접근은 권한 있는 인원으로 제한되고 need to know·최소 권한 원칙을 따른다(같은 문서 1.4).
  테넌시 안에서는 계정 소유자인 팀원과 인스턴스 관리자가 DB 내용을 볼 수 있다.
- 학습 사용: Cloud Services Agreement는 고객이 Oracle에 콘텐츠를 "서비스 제공을 위해" 호스팅·사용·처리할 권리를 준다고 적는다(3.3절, 확인한 판은 2016~2018년판).
  모델 학습에 쓸 권리를 주는 조항은 찾지 못했다. AI Terms(2026-09-16)는 AI 기능에 쓰는 콘텐츠에만 적용되고, 이 시스템은 OCI AI 기능을 쓰지 않는다.
  그래서 컴퓨트·블록 볼륨 내용은 학습에 쓰이지 않는다고 판단한다 `(추론)`. 학습 금지를 명시한 문장은 찾지 못했다.
- 보존 기간: 유료 서비스는 서비스 기간이 끝난 뒤 60일 동안 회수할 수 있게 두고, 무료 체험·시범은 끝난 뒤 30일이다. 회수 기간이 지나면 Oracle은 콘텐츠를 지운다(같은 문서 6.1).
  팀원 계정은 PAYG라 유료 서비스 쪽(60일)에 해당한다고 본다 `(추론)`. 인스턴스나 DB를 잃으면 원본에서 재색인으로 복구한다(RISK-08).
- 2026-10-23 사람 판단: 팀원 계정이 가입 때 동의한 Cloud Services Agreement의 판(버전)은 확인하지 않았다. 위 학습 사용 추론을 사용자가 받아들였다.
  판 미확인과 추론이라는 한계는 남는다. 공개 검색으로는 2018년판보다 새 판을 찾지 못했다.

### 근거 (조회 2026-10-19)

- Always Free 자원(A1 월 1,500 OCPU 시간·9,000 GB 시간 = 2 OCPU·12 GB, 블록 볼륨 200 GB·백업 5개, 송신 10 TB/월, 유휴 회수 조건, 홈 리전 제한, out of host capacity):
  https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- OCI Generative AI 데이터 처리: https://docs.oracle.com/en-us/iaas/Content/generative-ai/data-handling.htm
- Oracle AI Terms: https://www.oracle.com/contracts/docs/oracle-ai-terms.pdf
- Oracle Cloud Hosting and Delivery Policies(종료·정지 정책 6절): https://www.oracle.com/contracts/docs/ocloud-hosting-delivery-policies-soc.pdf
- (조회 2026-10-21) Oracle Cloud Hosting and Delivery Policies 3.13(2026-09, Overview·1.4·6.1): https://www.oracle.com/contracts/docs/ocloud_hosting_delivery_policies_3089853.pdf
- (조회 2026-10-21) Oracle AI Terms(2026-09-16): https://www.oracle.com/contracts/docs/oracle-ai-terms.pdf
- (조회 2026-10-21) Oracle Cloud Services Agreement(3.3 콘텐츠 사용 권한, 2016~2018년판): https://www.oracle.com/contracts/docs/oracle_cloud_services_agreement___oracle_systems_limited___v031916.pdf ,
  https://www.oracle.com/us/corporate/contracts/cloud-csa-v012418-jp-eng-4420526.pdf
- 이미지 arm64 태그: https://hub.docker.com/r/supabase/postgres/tags , 로컬 실측은 `docs/sdd/decisions/ADR-007-storage-schema.md` Evidence

### 이 제안이 남기는 수정

- `compose.yaml` 주석은 2026-10-21 SCRUM-103 작업에서 고쳤다. `docs/sdd/roadmap.md`에는 Supabase 표기가 없다(2026-10-21 확인).
- PGroonga 운영 확인은 DB 컨테이너를 띄운 뒤 같은 이미지로 `CREATE EXTENSION` 결과를 이 절에 적는다(QK-STO-001 T031, SCRUM-103).
  2026-10-23 결과: 운영 컨테이너 `qk-postgres`(`supabase/postgres:17.11.0.004`, PostgreSQL 17.11, arm64)에서 `postgres` 사용자(superuser 아님)로
  `CREATE EXTENSION vector`·`CREATE EXTENSION pgroonga`가 성공했고 설치 버전은 pgvector 0.8.2·PGroonga 3.2.5다(로컬 스파이크와 같다).

## Approval

- Approvers: 확인 필요
- Approved at: 미승인. 사용자가 2026-10-10에 실행 환경과 색인 분리를 선택했고, 이 문서의 승인은 PR 리뷰에서 받는다.
