# Task Contract: QK-FND-001 프로젝트 골격·설정 로딩·로컬 compose·CI 구현 (WBS 1.1)

> Generated at: `2026-10-19`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-97` / https://tkv123.atlassian.net/browse/SCRUM-97 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: QK-FND-001 / `specs/QK-FND-001-project-skeleton-ci/spec.md`
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#28`
- Branch: `feat/SCRUM-97-gh-28-project-skeleton`
- Base branch: `main`

## Objective

- QK-FND-001 명세를 `/speckit-plan`·`/speckit-tasks`로 설계하고 구현해, 이후 Phase 1 명세가 올라설 골격·설정·로컬 개발 환경·CI를 만든다.

## Scope

- `specs/QK-FND-001-project-skeleton-ci/`의 `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`, `tasks.md`
  (Spec Kit이 만드는 설계 산출물). `.specify/feature.json`은 이 명세 디렉터리를 가리키게 한다.
- 질의응답 진입점과 색인 진입점, 자료원·임베딩·생성·저장소·채팅 창구 경계(인터페이스) 골격(FR-001~003).
- 설정 항목 정의, 설정 로딩, 진입점별 필수 검사, 외부 호출 없는 점검 모드, 비밀값 비노출(FR-004~009).
- 로컬 개발·테스트 전용 `docker compose`(pgvector·PGroonga를 켤 수 있는 빈 DB), 재실행 안전한 시작 절차, 로컬 한정 재설정(FR-010~014).
- 프로젝트 정의 파일(`pyproject.toml` 등)과 기본 테스트·린트 명령, 외부 API 테스트 분리, 응답 샘플 테스트(FR-015~017).
- PR CI 워크플로(테스트·린트·비밀값 검사, CI Secret 불필요)(FR-018~022).
- 로컬 시작부터 기본 테스트 통과까지의 절차 문서(README 또는 `quickstart.md`).

## Explicit exclusions

- 운영 배포, Cloudflare Workers·Supabase 계정과 프로젝트 설정, 운영 비밀값 등록.
- 저장 스키마·마이그레이션(QK-STO-001), 자료원 어댑터 계약 내용(QK-ING-001), 색인 스케줄(QK-SYN-001).
- 실제 자료원·임베딩·생성 API 호출.
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, `.specify/memory/constitution.md`, `CLAUDE.md`, `.claude/**` 수정.
- `AGENTS.md` 7절 기본 검증 명령 추가(FR-015)는 사람 승인 뒤에만 한다. 승인 전에는 PR 본문에 필요 사항으로 적는다.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 해당 없음. 기본 테스트는 외부 요청 0건이어야 한다(SC-002)
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons
- 인덱스 버전 변경: 없음
- GitHub Actions 실행 시간: PR마다 검사 한 번(목표 10분 이내, SC-005)

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-FND-001-project-skeleton-ci/` 설계 산출물 | 확인 필요 | 사람 리뷰 |
| 골격 코드, 설정, `pyproject.toml`, compose 파일, 테스트 | 확인 필요 | 사람 리뷰 |
| `.github/workflows/` 새 CI 워크플로 | 확인 필요 | 사람 리뷰 |
| `.specify/feature.json`, `TASK.md`, `README.md` | 확인 필요 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-19 `origin/main`(`82efdd6`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
# 아래는 구현 후 pyproject.toml에 등록한 명령으로 바꾼다
# 기본 테스트(외부 API 테스트 제외), 린트, 설정 점검 모드, compose 시작 두 번 연속 실행
```

## Completion criteria

- 토큰 없이 문서 절차만으로 로컬 시작과 기본 테스트 통과까지 끝나고, 기본 테스트의 외부 요청이 0건이다(SC-001, SC-002).
- 필수 설정 누락·오류가 항목 이름으로 한 번에 보고되고 비밀 값은 출력에 나오지 않는다(SC-003).
- PR에서 테스트·린트·비밀값 검사가 각각 표시되고, 같은 커밋의 로컬 결과와 같다(SC-004, SC-006).

## Decisions

- 2026-10-19 사용자 결정: Phase 0 완료 리뷰(0.G)를 마치기 전에 Phase 1을 시작한다. 0.7·0.8(골든셋·기준선)은 봇(WBS 1.11) 전까지 끝낸다.
- 2026-10-19 사용자 결정: WBS 1.1은 기존 SCRUM-89 대신 SCRUM-42 아래 새 하위 작업 SCRUM-97로 추적한다. SCRUM-89 정리는 Jira에서 사람이 한다.
- 2026-10-19 사용자 결정: 한 브랜치에서 plan·tasks·구현까지 진행한다.
- 2026-10-19 사실: 저장소에 Jira Secret이 없어 #28의 하위 작업 자동 생성이 실패했고, SCRUM-97은 사람이 Jira에서 직접 만들었다.
