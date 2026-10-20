# Task Contract: QK-ING-002 첫 자료원 dnd-backend-docs 활성화 (WBS 1.5)

> Generated at: `2026-10-20`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-100` / https://tkv123.atlassian.net/browse/SCRUM-100 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: QK-ING-002 / `specs/QK-ING-002-github-repo-source/spec.md`(승인됨). 이 브랜치는 `tasks.md` "사람 단계"를 맡는다
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#41`
- Branch: `chore/SCRUM-100-gh-41-activate-backend-docs`
- Base branch: PR #43 브랜치 `feat/SCRUM-100-gh-41-github-repo-source`(`c761221`) 위에 쌓았다. 아래 Decisions 참조

## Objective

- 첫 자료원 `dnd-backend-docs`를 활성화하고 첫 실제 수집을 측정해, QK-ING-002의 마지막 요구(FR-022, FR-023, SC-009)를 채운다.
- 순서(`specs/QK-ING-002-github-repo-source/research.md` R-13): 1) 결정 기록 작성·승인 → 2) 개인 정보 확인 → 3) 확인 기록 작성 → 4) 활성화 → 5) `qk-index sources check` → 6) 측정·기록.

## Scope

- `docs/sdd/decisions/ADR-019-github-backend-docs-source.md`(결정 기록. 에이전트가 초안을 쓰고 사람이 사실 확인·승인)
- `config/source_reviews/dnd-backend-docs.toml`(개인 정보 확인 기록. **사람이 확인하고 쓴다.** 에이전트는 대신 쓰지 않는다)
- `config/sources.toml`의 `dnd-backend-docs` 항목: `enabled = true`, 확인 결과로 제외 패턴 추가, 측정 결과로 한도값 조정(FR-023)
- `docs/sdd/research/github-source-measurement.md`(측정 기록. 사람이 실행한 `qk-dev source measure` 결과와 측정 조건, 한도값 판단)
- `tests/unit/indexer/test_cli.py`의 `test_run_with_valid_settings_reports_and_exits_zero` 한 건(저장소 설정 대신 시험용 설정 파일을 쓰게 바꿈, 2026-10-20 사용자 허용)
- `TASK.md`

## Explicit exclusions

- 위 시험 한 건 밖의 코드·시험 변경(`src/`, `tests/`). 필요하면 PR #43 쪽에서 다룬다.
- 승인된 명세·설계·작업 목록 내용 변경, `docs/sdd/roadmap.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정.
- 포함 범위를 인벤토리 "결정 필요"·"제외" 범주로 넓히기. 넓히려면 확인 기록을 새로 쓰고 결정 기록을 고친다.
- 임베딩·저장·동기화 실행(QK-EMB-001, QK-SYN-001). 이 브랜치는 수집과 측정까지다.
- 원본 자료원(대상 저장소 포함)에 쓰기.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문, 사람 이름·연락처는 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: GitHub 공개 저장소 `dnd-side-project/dnd-15th-2-backend`의 `main`(읽기 전용 세분화 토큰, `tokens.md` 2절)
- 외부 API로 보내는 데이터: GitHub REST API `GET` 요청만(토큰, 요청 경로). 임베딩·생성 API 전송 없음
- 예상 호출량: 측정 1회에 GitHub 약 84회(추론, 토큰 한도 시간당 5,000회 안). 임베딩·생성 0 Neurons
- 인덱스 버전 변경: 없음
- 데이터 스키마: 마이그레이션 `0003_embedding_usage.sql` 추가. 로컬 DB에만 적용한다. 병합 뒤 체크섬이 바뀌지 않게 이 브랜치에서 파일을 확정한다

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `docs/sdd/decisions/ADR-019-github-backend-docs-source.md` | Byuntil | 사람 리뷰(결정 승인) |
| `config/source_reviews/dnd-backend-docs.toml` | Byuntil | 사람 리뷰(확인한 사람이 작성) |
| `config/sources.toml` | Byuntil | 사람 리뷰 |
| `docs/sdd/research/github-source-measurement.md` | Byuntil | 사람 리뷰 |
| `TASK.md` | Byuntil | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-20 `feat/SCRUM-100-gh-41-github-repo-source`(`c761221`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python3 scripts/preflight.py
git diff --check
uv run qk-index sources check                                   # 활성화 뒤 통과해야 한다
uv run qk-dev source measure --name dnd-backend-docs            # 사람 실행. 목록 완전, 판정 실패 0건
uv run pytest -m external tests/external/test_github_repo_source.py   # 사람 실행
QK_REQUIRE_LOCALDB=1 uv run pytest                              # 설정 변경 뒤 기본 시험이 깨지지 않는지
```

## Completion criteria

- 결정 기록 ADR-019가 사람 승인을 받는다.
- 확인 기록이 있고 `qk-index sources check`가 활성 `dnd-backend-docs`로 통과한다(FR-020).
- 첫 실제 수집 측정 기록이 FR-022 항목을 모두 갖고, 요청 수가 실행당 한도 이하이며, 막힌 자료마다 이유가 있다(SC-009). 한도값 판단이 기록된다(FR-023).

## Decisions

- 2026-10-20 사용자 결정: 활성화 작업을 PR #43 브랜치 위에 쌓는 브랜치로 시작한다. AGENTS.md 1절 3항(최신 `origin/main`에서 분기)의 예외다.
  PR을 열면 base를 #43 브랜치로 하고, #43이 병합되면 `main`으로 rebase한 뒤 base를 `main`으로 바꾼다(QK-SEC-001 때와 같은 절차).
- 2026-10-20 사실: 결정 기록 초안을 이 Claude 세션이 썼다. ID는 저장소에 원문이 없는 번호(001, 004, 005, 011, 013, 014)와 겹치지 않게 ADR-019로 두었다. 사람 확인 필요.
  초안의 확인 필요 항목: Workers AI 입력 보존 기간, 저장소 제공자(Supabase) 데이터 처리 정책(ADR-008 미확인 항목), 다시 볼 기준값(제안 값), 승인자.
- 2026-10-20 사실: 범위 안 파일은 대상 커밋 `6aeccd0`에서 81개, 1,087,120바이트다(트리 잘림 없음). 에이전트가 메일·전화번호·`@` 표기 후보를 자동 검사해(값은 출력하지 않음)
  `docs/harness/ARCHITECTURE.md` 흐름도의 `@` 표기 1건을 사람 확인 대상으로 올렸다. 나머지 후보는 코드·버전 표기·표 머리였다.
- 2026-10-20 사용자 결정: 그 표기는 팀원 GitHub 핸들이다. AGENTS.md 3.1(계정 정보 색인 금지)에 따라 A안으로 그 파일을 제외 패턴에 넣는다. 색인 범위는 80개가 된다.
- 2026-10-20 사실: 사람이 확인 기록 초안(에이전트가 형식만 만들고 날짜를 비워 둔 것)을 고쳐 저장했고, 에이전트가 `config/source_reviews/dnd-backend-docs.toml`로 옮겼다.
  옮길 때 `reviewed_on`의 따옴표만 빼 TOML 날짜로 바꿨다(값은 그대로). 형식 검사 통과. 자료원은 아직 비활성이다(4단계 전).
- 2026-10-20 사용자 결정: ADR-019 — 번호 019 확정, 다시 볼 기준값은 측정 뒤 정함, 승인은 기존처럼 PR 리뷰로 받음, Supabase 데이터 처리 정책은 QK-SYN-001 첫 저장 전에 확인,
  결정 내용 승인(Status Accepted, 대화로 전달받은 승인을 PR 리뷰로 확정).
- 2026-10-20 사실: 4단계 활성화(`enabled = true`, 제외 패턴에 `docs/harness/ARCHITECTURE.md` 추가), 5단계 `qk-index sources check` 통과(활성 1, 포함 19, 제외 7).
- 2026-10-20 사실: 활성화 뒤 `test_run_with_valid_settings_reports_and_exits_zero`가 실패했다. 저장소 `config/sources.toml`에 활성 자료원이 없다고 가정한 시험이다.
  사용자 결정으로 이 브랜치에서 고쳤다. 시험이 활성 자료원 없는 시험용 설정을 `--sources`로 넘긴다(검증 내용은 같음). `QK_REQUIRE_LOCALDB=1 uv run pytest` 792 passed.
- 2026-10-20 사실: 6단계 측정 명령이 색인 진입점 설정 점검에서 멈췄다(작업 폴더에 `.env` 없음, 필수 항목 4개 누락). 원본 호출 0건.
  사용자 결정으로 Codex 패널이 `.env.example`을 바탕으로 `.env`를 만들고 사용자가 값을 직접 채우도록 안내한다. `.env`는 커밋하지 않는다. 이 Claude 세션은 `.env`에 접근하지 않는다.
- 2026-10-20 사실: 사용자가 `.env`를 채운 뒤 `qk-index check` 통과(누락·형식 오류 0). 에이전트가 6단계 측정을 1회 실행했다. 종료 코드 0, 요청 83회, 73.3초, 목록 완전,
  파일 80개 1,083,278바이트, `PASSED` 79·`SECRET_BLOCKED` 1(계획 문서 1개, `env-assigned-secret`, 셸 변수 참조 오탐으로 추정). 0 Neurons.
  기록은 `docs/sdd/research/github-source-measurement.md`. 한도값은 네 개 모두 유지를 제안했다(PR 리뷰에서 확정).
- 2026-10-20 사실: 외부 호출 시험은 토큰을 환경 변수에서만 읽어 이 세션에서 `토큰 없음`으로 실패했다(원본 호출 0건).
  사람이 `uv run --env-file .env pytest -m external tests/external/test_github_repo_source.py -q`로 실행해 통과했다.
- 2026-10-20 사용자 결정: ADR-019 다시 볼 기준값은 권장안 A — 요청 1,000회(실행당 한도의 50%) 초과, 막힌 자료 범위의 10% 초과.
- 2026-10-20 사용자 결정: 측정에서 막힌 계획 문서 1개(`env-assigned-secret` 오탐 추정)는 그대로 둔다(예외·규칙 수정 없음). 한도값 유지 제안은 PR 리뷰에서 확정한다.
