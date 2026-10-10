# Task Contract: WBS 0.9 열린 결정 확정

> Generated at: `2026-10-10`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- ClickUp 작업 ID / URL: 해당 없음: 초기 세팅 단계 예외. 진행 상태는 WBS 보드 0.9에서 관리
- 기능명세서 ID / 링크: 해당 없음: Phase 0 준비 작업(WBS 0.9)이라 명세 백로그 대상이 아님. 작업 정의는 `docs/sdd/roadmap.md` 3절
- 팀 스프린트 ID: `QELLO-S2026-W41`
- GitHub Issue: `#18`
- Branch: `docs/gh-18-adr-decisions`
- Base branch: `main`

## Objective

- `확인 필요` 상태인 ADR 네 건(ADR-002 임베딩 모델, ADR-008 실행 환경·비용 상한, ADR-009 생성 모델,
  ADR-016 질의 원문 저장)의 결정을 `templates/decision-record.md` 양식으로 남겨 0.G 완료 조건 첫 항목을 닫고,
  0.11 명세 3건이 확정된 전제 위에서 쓰이게 한다.

## Scope

- `docs/sdd/decisions/` 아래 결정 기록 4건을 만든다. 파일은 `ADR-002-embedding-model.md`,
  `ADR-008-runtime-and-cost-cap.md`, `ADR-009-generation-model.md`, `ADR-016-query-text-retention.md`다.
- ADR-002: 임베딩 모델을 `@cf/baai/bge-m3`로 정한다. 근거는 `spike-workers-ai.md` 3.2·5.1절이다.
- ADR-008: 실행 환경을 Cloudflare Workers와 Supabase Free(pgvector·PGroonga)로 정하고, 색인은 Workers 밖
  (GitHub Actions 또는 로컬 CLI)에서 실행한다. 추가 고정비 상한은 0원이다.
- ADR-009: 2026-10-09에 정한 `@cf/qwen/qwen3-30b-a3b-fp8`(`/no_think`)을 기록한다.
- ADR-016: 질의 메타데이터는 항상 저장하고, 질문·답변 원문은 저장 동의 질문에 동의한 건만 저장한다.
  Discord 사용자 식별자는 원본 ID를 쓰고 보존 기간은 무기한이다. 동의는 Discord 공지와 ClickUp 문서로 받는다.
- 각 기록의 Evidence에는 공식 문서 URL과 조회일, 또는 `spike-workers-ai.md`의 절 번호와 측정 조건을 적는다.
- 네 기록이 다른 문서에 남기는 후속 수정은 각 기록의 발견 사항으로만 적는다.

## Explicit exclusions

- ADR-007(저장 스키마)·ADR-010(키워드 검색 텍스트) 결정. Phase 1 스파이크 대상이다.
- 0.11 명세 작성, 구현, 수집·검색·봇 코드.
- Cloudflare Workers·Supabase 계정 설정, 배포, PGroonga 활성화 확인, 유료 플랜 전환.
- `inventory.md`, `tokens.md`, `roadmap.md`, `constitution.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정.
  고칠 점은 결정 기록의 발견 사항에 적는다.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 계정 ID, DB 연결 주소, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음.
- 외부 API로 보내는 데이터: 해당 없음. 외부 호출 없이 저장소 문서만 쓴다. 공식 문서 조회는 읽기뿐이다.
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons. 결정 내용은 추가 고정비 0원이고, 종량 호출은
  Workers AI 무료 할당(일 10,000 Neurons) 안이다.
- 인덱스 버전 변경: 없음. 임베딩 모델을 정했으므로 첫 인덱스 버전은 Phase 1(QK-EMB-001)에서 만든다.

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `docs/sdd/decisions/` | 확인 필요 | 사람 리뷰. 결정 승인은 사람이 한다(AGENTS.md 2절) |
| `TASK.md` | 확인 필요 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-10 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
grep -rnE 'github_pat_[A-Za-z0-9_]{20,}|cfat_[A-Za-z0-9_-]{20,}|pk_[0-9]{6,}|[0-9a-f]{32}' docs TASK.md   # 결과가 없어야 한다
grep -rnE 'postgres(ql)?://|\.supabase\.co|\.neon\.tech' docs TASK.md                                      # 결과가 없어야 한다. DB 연결 주소
```

## Completion criteria

- 결정 기록 4건에 Decision, Rationale, Alternatives considered, Evidence, Revisit conditions가 채워져 있다. 사람 리뷰로 확인한다.
- ADR-016 기록의 Negative / risks에 무기한 보존이 constitution C-10의 기간 요건과 어긋난다는 내용과 삭제 요청 처리 방법이 있다. 사람 리뷰로 확인한다.
- 결정 기록에 토큰, 계정 식별자, DB 연결 주소가 없다. 위 검증 명령과 리뷰로 확인한다.

## Decisions

- 2026-10-10 사용자 결정: 0.4·0.5와 같이 초기 세팅 단계 예외로 ClickUp 작업 없이 진행하고 GitHub Issue(#18)를 만든다.
- 2026-10-10 사용자 결정: 0.9와 0.11을 분리하고 0.9 Issue·브랜치만 먼저 만든다.
- 2026-10-10 사용자 결정(ADR-008): 실행 환경은 Cloudflare Workers와 관리형 Postgres 무료 티어다. Postgres는 최대한 무료 플랜으로 운영한다.
- 2026-10-10 사용자 결정(ADR-008): 색인은 Workers 밖(GitHub Actions 또는 로컬 CLI)에서 실행하고 Workers는 질의응답을 맡는다.
  Workers Free의 요청당 subrequest 50개와 CPU 10 ms 한도 때문이다.
- 2026-10-10 사용자 확인: 팀 dev 테스트 서버의 매일 03:00 자동 정지 설정을 없앴다. `inventory.md` 3.1절 서술이 더 이상 사실이 아니다.
- 2026-10-10 사용자 결정(ADR-002): 임베딩 모델은 `@cf/baai/bge-m3`다.
- 2026-10-10 사용자 결정(ADR-016): 메타데이터는 항상 저장하고 원문은 옵트인으로 받는다. 옵트인은 저장 동의 질문으로 받는다.
  저장 항목은 질문과 답변이고, Discord 사용자 식별은 원본 ID를 쓰며, 보존 기간은 무기한이다.
  동의는 Discord 공지와 ClickUp 문서로 받는다.
- 2026-10-10 에이전트 보고: 무기한 보존은 constitution C-10("동의한 범위와 기간에만 저장")의 기간 요건과 어긋난다고 알렸고,
  사용자가 무기한을 다시 선택했다. 결정대로 기록하고 충돌을 각 기록의 위험 항목에 남긴다.
