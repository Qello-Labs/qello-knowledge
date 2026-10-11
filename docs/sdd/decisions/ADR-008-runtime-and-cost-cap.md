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

질의응답은 Cloudflare Workers에서 실행하고, 저장은 Supabase 무료 플랜의 관리형 PostgreSQL(pgvector·PGroonga)에
둔다. 색인은 Workers 밖(GitHub Actions 또는 로컬 CLI)에서 실행한다. 추가 고정비 상한은 월 0원이고, 종량 호출은
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

## Approval

- Approvers: 확인 필요
- Approved at: 미승인. 사용자가 2026-10-10에 실행 환경과 색인 분리를 선택했고, 이 문서의 승인은 PR 리뷰에서 받는다.
