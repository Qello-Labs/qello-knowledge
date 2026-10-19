# Task Contract: QK-STO-001 저장 스키마·마이그레이션·검색 질의 구현 (WBS 1.2)

> Generated at: `2026-10-19`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-90` / https://tkv123.atlassian.net/browse/SCRUM-90 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: QK-STO-001 / `specs/QK-STO-001-storage-schema-search/spec.md`
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#33`
- Branch: `feat/SCRUM-90-gh-33-storage-schema`
- Base branch: `main`

## Objective

- QK-STO-001 명세를 `/speckit-plan`·`/speckit-tasks`로 설계하고 구현해, 임베딩(1.7)과 하이브리드 검색(1.9)이
  올라설 저장 스키마·마이그레이션·검색 질의를 만든다.

## Scope

- `specs/QK-STO-001-storage-schema-search/`의 `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`, `tasks.md`.
  `.specify/feature.json`은 이 명세 디렉터리를 가리키게 한다.
- 스키마: 원본 자료, 청크, 임베딩, 인덱스 버전(FR-001~005). 출처 정보가 빠진 청크와 차원이 1,024가 아닌 벡터는 저장을 거부한다.
- 검색 질의: 벡터 검색, 키워드 검색(PGroonga), 주변 청크 조회. 활성 인덱스 버전·팀 공용 접근 범위·활성 자료 조건을 질의 안에서 적용한다(FR-006~011).
- 쓰기 연산: 문서 단위 청크 교체(원자적, 동시 실행 안전), 삭제 상태 전환, 임베딩 재사용 조회, 사용량 조회(FR-012~015, FR-023).
- 마이그레이션: 버전·체크섬·적용 기록, 재적용 안전, 하나씩 원자적 적용, 파괴적 변경 표시, CI에서 빈 로컬 DB 전체 적용(FR-016~020).
- `ports/store.py` 저장소 경계 계약과 로컬 DB(pgvector·PGroonga) 대상 구현, 로컬 DB 테스트.
- ADR-007(자체 스키마 vs PGVectorStore) 스파이크와 결정 기록(FR-021). plan 확정 전에 끝낸다.
- 운영 저장소를 Oracle Cloud Always Free 인스턴스로 바꾸는 ADR-008 변경 제안과 그 데이터 처리 정책 확인 결과를 결정 기록에 남긴다(FR-022).
  운영 PGroonga 확인은 인스턴스가 생긴 뒤 한다.

## Explicit exclusions

- RRF·문맥 확장 범위·토큰 예산·키워드 검색 텍스트 생성 방식(QK-RET-001, ADR-010).
- 접근 범위 값 체계와 판정(QK-SEC-001). 이 작업은 값을 저장하고 "팀 공용 확인됨"만 검색 대상으로 삼는다.
- 인덱스 버전 활성화 절차와 평가 게이트(QK-STO-002), 임베딩 캐시 정책(QK-EMB-001), 교체 시점 판단(QK-SYN-001), 물리 삭제(QK-SYN-003).
- Oracle Cloud 계정·인스턴스 생성과 운영 DB 구축, 운영 저장소에 마이그레이션 적용, 운영 저장소에 실제 팀 자료 저장.
- `docs/sdd/roadmap.md`, `compose.yaml`의 Supabase 표기 수정(ADR-008 변경 확정 뒤 별도 승인).
- 실제 자료원·임베딩·생성 API 호출.
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, `.specify/memory/constitution.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문, DB 연결 주소는 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 해당 없음. 테스트 벡터는 고정 값이나 난수로 만든다
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons
- 인덱스 버전 변경: 없음(스키마에 인덱스 버전 테이블만 만든다. 활성화는 QK-STO-002)
- 데이터 스키마: 새 스키마와 마이그레이션 추가. 로컬 DB에만 적용한다

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-STO-001-storage-schema-search/` 설계 산출물 | 확인 필요 | 사람 리뷰 |
| 저장소 계약·구현 코드, 마이그레이션 파일, 테스트 | 확인 필요 | 사람 리뷰 |
| ADR-007 결정 기록, ADR-008 확인 결과 | 확인 필요 | 사람 리뷰 |
| `.github/workflows/` 마이그레이션 적용 검사 추가 | 확인 필요 | 사람 리뷰 |
| `.specify/feature.json`, `TASK.md` | 확인 필요 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-19 `origin/main`(`b7be62a`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
uv run qk-migrate   # 두 번 실행, 두 번째는 applied=0
uv run qk-migrate
uv run qk-dev store bench   # SC-005·SC-006 측정(기본 검증 아님)
```

## Completion criteria

- 접근 범위 미확인·삭제·비활성 인덱스 청크가 섞인 검증 세트에서 검색 결과에 그런 청크가 0건이다 — 로컬 DB 테스트(SC-002)
- 교체 도중 실패를 넣은 시험에서 검색 결과가 교체 전과 같고, 마이그레이션 두 번째 적용의 변경이 0건이다 — 로컬 DB 테스트(SC-003, SC-004)
- ADR-007 결정과 운영 저장소(Oracle Cloud) 데이터 처리 정책·PGroonga 확인 결과가 결정 기록에 있다 — 결정 기록 리뷰(SC-008)

## Decisions

- 2026-10-19 사실: 선행 PR #29(QK-FND-001)가 `main`에 병합돼 `origin/main`에서 브랜치를 만들었다.
- 2026-10-19 사실: Jira는 기존 이슈 SCRUM-90을 쓴다(#33 본문). 하위 작업 자동 생성은 쓰지 않는다.
- 2026-10-19 사용자 결정: 이 TASK.md 초안을 승인했다. `/speckit-plan`을 시작하고 ADR-007 스파이크는 `research.md`에 포함한다.
- 2026-10-19 사실: ADR-007 스파이크를 로컬 DB 전용 데이터베이스 `qk_spike`에서 실행하고 지웠다. 결과는 자체 스키마 채택(`docs/sdd/decisions/ADR-007-storage-schema.md`, 승인 대기).
- 2026-10-19 사용자 결정(잠정): 운영 저장소를 Supabase 대신 Oracle Cloud 프리티어급 인스턴스로 바꾼다("아마"). ADR-008에 변경 제안으로 기록했다.
- 2026-10-19 미결: 운영 PGroonga 확인(T031)은 Oracle Cloud 인스턴스가 필요해 사람 확인 대기다. 유휴 인스턴스 회수 대응도 정해야 한다(ADR-008 변경 제안).
- 2026-10-19 사용자 결정: plan 설계를 승인했다. `/speckit-tasks`로 `tasks.md`(T001~T036)를 만들었다.
- 2026-10-19 검증: preflight·`git diff --check`·ruff check·ruff format --check 통과, `qk-migrate` 두 번째 `applied=0`, `QK_REQUIRE_LOCALDB=1 uv run pytest` 183 passed.
  bench(로컬 arm64, 합성 1.1 MB): 벡터 p95 5.4 ms, 키워드 p95 6.2 ms, 10 MB 추정 137 MB(예산의 27.4%). 같은 세션의 자기 검증이라 독립 검증이 아니다.
- 2026-10-19 사실: 키워드 토크나이저를 `TokenBigramSplitSymbol`로 정했다. 기본값은 백틱 감싼 경로를 못 찾았다(research R-03). 영문 부분 일치는 ADR-010에서 정한다.
- 2026-10-19 사용자 결정: ADR-007(자체 스키마)을 승인했다. Status를 Accepted로 바꿨다.
- 2026-10-19 사용자 결정: ADR-008 운영 저장소 변경(Oracle Cloud)은 제안으로 유지한다. 유휴 회수 대응과 Workers 연결 방식이 정해진 뒤 확정한다.
- 2026-10-19 사용자 결정: T031은 `BLOCKED`로 두고 운영 인스턴스를 만드는 후속 작업에서 확인한다. 이 PR에서 완료 조건 3은 ADR-007·정책 확인까지만 충족한다.
- 2026-10-19 사용자 결정: `adapters/postgres/connection.py`의 로컬 기본 비밀번호 린트 억제(`noqa: S105`)는 사유를 달아 유지하고 PR 본문에 명시한다.
