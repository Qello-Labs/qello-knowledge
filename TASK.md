# Task Contract: 임베딩 Neurons 예상식 보정 (QK-EMB-001 SC-005 후속)

> Generated at: `2026-10-25`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-114` / https://tkv123.atlassian.net/browse/SCRUM-114 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: `QK-EMB-001` / `specs/QK-EMB-001-embedding-provider-budget/` (SC-005, FR-023, research R-04)
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: 해당 없음
- Branch: `fix/SCRUM-114-neuron-estimate-calibration`
- Base branch: `main`. 2026-10-25 `origin/main` `f11e146`(#56 병합)에서 분기했다

## Objective

- 미리 보기, 예산 예약, 제공자 값이 없을 때의 추정 기록이 쓰는 예상 Neurons가 실제에 가깝게 나오게 한다. 지금은 실제의 약 41%로 낮게 잡는다(첫 색인 예상 368.93, 실제 894.50).
- 청크 나누기와 묶음 나누기는 바꾸지 않는다. 청킹 판수와 인덱스 버전이 그대로다.

## Scope

- `TASK.md`
- `src/qello_knowledge/domain/embedding.py`: `ModelSpec`에 Neurons 예상 전용 바이트/토큰 계수를 더한다(bge-m3 값은 아래 분석으로 정한다. 기본안 1.4)
- `src/qello_knowledge/embedding/estimate.py`: `estimated_neurons`와 `estimate_basis`가 새 계수를 쓴다. `estimated_tokens`(청크 나누기·묶음 나누기·입력 한도 판정)는 지금 계수(3.5) 그대로
- `tests/unit/embedding/`: 새 계수 시험을 더하고, 3.5로 계산한 예상 Neurons 기댓값을 새 계수로 고친다. 청크 나누기 쪽 3.5 기댓값과 청킹 판수 시험(`chk-md-20d966f730bb`)은 그대로 둔다
- `specs/QK-EMB-001-embedding-provider-budget/`: `research.md` R-04에 보정 결정과 근거(표본·조건), `data-model.md` `ModelSpec`, `tasks.md`에 후속 기록
- `specs/QK-SYN-001-incremental-sync/tasks.md` H06 관찰에 이 작업 링크 한 줄
- 사용량 기록 읽기 전용 분석(로컬 DB. 필요하면 사람이 인증한 터널로 운영 DB 읽기 전용 조회)

## Explicit exclusions

- 청크 나누기 계수(3.5)·청킹 규칙·청킹 판수·인덱스 버전·재임베딩
- 묶음 나누기(`make_batches`)와 입력 한도 초과 판정(`over_limit`)의 토큰 추정. 실제 토큰이 예상보다 많다는 사실이 이 둘에도 영향을 줄 수 있으나 별도 이슈로 본다(아래 위험)
- 새 임베딩 실측(Neurons 소비), 새 자료원, 하루 예산 값(`QK_EMBED_*`) 변경
- `AGENTS.md`, `CLAUDE.md`, `.claude/**`, constitution, 로드맵 수정. 원본 자료원에 쓰기
- 공유 DB 쓰기·초기화, 인덱스 전체 삭제, 유료 과금 설정 변경
- 비밀값, 토큰, `.env` 값, 접속 주소, 비공개 원문은 기록하지 않는다

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 해당 없음(기존 사용량 기록만 읽는다)
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons
- 인덱스 버전 변경: 없음(`iv-4c0bc4fcc642`, `chk-md-20d966f730bb` 유지)
- 동작 영향: 예상 Neurons가 약 2.5배 커진다. 예산 사전 판정(`runnable`)이 더 보수적이 된다. 하루 색인 예산 5,000 기준 전체 색인 예상 약 920은 여전히 한도 안이다

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `src/qello_knowledge/domain/embedding.py`, `src/qello_knowledge/embedding/estimate.py`, `tests/unit/embedding/**` | Byuntil | 사람 리뷰 |
| `specs/QK-EMB-001-embedding-provider-budget/**`, QK-SYN-001 tasks 한 줄 | Byuntil | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-25 `origin/main`(`f11e146`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
```

보정 근거 분석(읽기 전용): 정산·실측된 색인 호출의 입력 바이트와 제공자 Neurons로 계수를 정하고, 같은 기록에서 일부 호출만 고른 작은 실행의 예상 오차 분포를 함께 적는다.

## Completion criteria

- 새 계수로 다시 계산한 첫 색인 예상이 실제 894.50의 ±20% 안이다(SC-005) — research R-04 보정 기록(표본 수, 기간, 모델, 인덱스 버전)
- 청킹 판수와 인덱스 버전이 바뀌지 않는다 — `chk-md-20d966f730bb` 시험, `index status`
- 미리 보기·예산 예약이 새 계수를 쓰고 기본 검증이 통과한다 — 단위 시험, pytest, PR CI

## Decisions

- 2026-10-25 사실: Jira `SCRUM-114`를 사용자 요청으로 만들었다(SCRUM-42 하위 작업, 레이블 `bug`·`team-backend`).
- 2026-10-25 사용자 결정: 청크 나누기 계수는 두고 Neurons 예상 전용 계수를 분리한다. 값은 기존 사용량 기록으로 정하고 새 실측은 하지 않는다.
- 2026-10-25 사실(읽기 전용, 로컬 DB `qk.embedding_usage`): 정산·실측 색인 호출 92건은 2026-10-21 로컬 첫 색인 `sync-20261021T091615-e8441b58` 한 실행이다.
  입력 1,291개·1,199,214바이트, 예상 368.93, 실제 894.50(운영 첫 색인도 청크 1,291개·894.50 Neurons로 같다. 운영 입력 바이트는 확인하지 않았다). 실제 환산 1.441바이트/토큰(1,075 Neurons/백만 토큰 기준).
  호출별 바이트/토큰은 최소 0.39·p10 1.12·중앙 1.80·p90 3.07·최대 4.58로 흩어진다. 호출당·입력당 고정 비용 항을 더해도 맞춤이 나아지지 않는다(계수 음수).
  같은 비율로 호출 30개를 무작위로 고른 작은 실행은 97%가 ±20% 안, 10개는 71%, 3개는 40%다. 표본은 실행 1개(자료원 `dnd-backend-docs`)뿐이다.
- 기본안: 계수 1.4(전체 색인 예상 약 921, +3%). 작은 실행의 오차가 크므로 SC-005 판정은 전체 색인 규모로 한다. 값과 판정 단위는 리뷰에서 확인한다.
- 2026-10-25 사용자 결정: 이 계약대로 진행한다. 계수 기본안 1.4와 SC-005를 전체 색인 규모로 판정하는 방식을 받아들였다.
