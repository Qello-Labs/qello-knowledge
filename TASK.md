# Task Contract: QK-ING-001 자료원 어댑터 계약·자료원 설정·호출 한도·재시도 구현 (WBS 1.3)

> Generated at: `2026-10-19`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-98` / https://tkv123.atlassian.net/browse/SCRUM-98 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: QK-ING-001 / `specs/QK-ING-001-source-adapter-contract/spec.md`
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#34`
- Branch: `feat/SCRUM-98-gh-34-source-adapter-contract`
- Base branch: `main`

## Objective

- QK-ING-001 명세를 `/speckit-plan`·`/speckit-tasks`로 설계하고 구현해, 자료원 수집기(QK-ING-002 이후)와 그 결과를 쓰는 보안 필터·청커·동기화가
  공통으로 따를 어댑터 계약, 자료원 설정, 호출 한도·재시도 동작을 만든다.

## Scope

- `specs/QK-ING-001-source-adapter-contract/`의 `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`, `tasks.md`.
  `.specify/feature.json`(git 무시 파일, 로컬 전용)은 이 명세 디렉터리를 가리키게 한다.
- 어댑터 계약(FR-001~007): `src/qello_knowledge/ports/source.py`의 `SourceAdapter` Protocol을 채운다. 자료 목록 항목·자료 본문·수집 결과
  공통 타입은 `src/qello_knowledge/domain/`에 둔다. 공통 계약 테스트 세트와 저장된 응답으로 도는 가짜 자료원 어댑터를 만든다.
- 자료원 설정(FR-008~013): 저장소에 커밋하는 자료원 설정 파일, 등록된 자료원 종류 목록(GitHub 저장소 파일, 가짜 자료원), 설정 검증,
  검증만 하는 실행 방식. 인증은 `src/qello_knowledge/config/registry.py`의 설정 항목 이름으로만 가리킨다.
- 호출 한도(FR-014~016): 단위 시간당·실행 1회당 최대 요청 수, 원본이 알려 준 남은 호출 수와 다시 시도할 시각, 멈출 때의 보고.
- 재시도와 실패 분류(FR-017~022): 일시적·영구·인증 실패 구분, 지수 백오프와 무작위 지연, 등록되지 않은 호스트로의 리다이렉트 차단,
  결과·로그의 비밀값 비노출.
- 위 동작의 단위 테스트와 응답 샘플(`tests/fixtures/responses/`). 파일 위치와 실행 방식 이름은 `plan.md`에서 정한다.

## Explicit exclusions

- 실제 GitHub 수집기와 실제 원본 호출(QK-ING-002). `@pytest.mark.external` 테스트도 만들지 않는다.
- 색인 제외 경로, 비밀값 차단, 접근 범위 판정(QK-SEC-001). 원본 권한 정보는 그대로 넘기고 없으면 "미확인"으로 채우기까지만 한다.
- 수집 주기, 이어서 수집하기, 변경 비교, 삭제 반영(QK-SYN-001), 웹훅.
- 저장 스키마와 마이그레이션(QK-STO-001). 공통 자료 형식의 필드만 QK-STO-001 원본 자료 항목에 맞춘다.
- 런타임 의존성 추가(`pyproject.toml`의 `dependencies`). 필요하면 사람 승인을 받는다.
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, `.specify/memory/constitution.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다. 응답 샘플은 저장 전에 토큰·계정 식별자·내부 주소를 지운다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음. 자료원 종류를 정의만 하고 실제 호출은 QK-ING-002에서 한다
- 외부 API로 보내는 데이터: 해당 없음. 테스트의 실제 원본 호출은 0건이어야 한다(SC-002)
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-ING-001-source-adapter-contract/` 설계 산출물 | Byuntil | 사람 리뷰 |
| `src/qello_knowledge/ports/source.py`, `domain/`, `adapters/`의 자료원 관련 코드, 자료원 설정 파일 | Byuntil | 사람 리뷰 |
| `tests/` 계약 테스트·가짜 어댑터·응답 샘플 | Byuntil | 사람 리뷰 |
| `TASK.md` | Byuntil | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-19 `origin/main`(`b7be62a`, PR #29 병합 커밋)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
grep -rn "NEEDS CLARIFICATION" specs/QK-ING-001-source-adapter-contract/   # 결과가 없어야 한다
```

## Completion criteria

- 가짜 어댑터가 공통 계약 테스트를 모두 통과하고, 두 번째 가짜 어댑터를 추가할 때 계약 밖 코드 변경이 0줄이며 원본 쓰기 요청이 0건이다(SC-001, SC-002).
- 필수 항목 누락·미등록 종류·토큰 값 직접 기재 설정이 모두 실행 전에 실패하고, 원본 호출 0건, 출력·로그에 토큰 값이 없다(SC-003, SC-007).
- 한도·재시도 시험에서 한도를 넘은 요청이 0건이고, 재시도 상한 이내의 일시적 실패는 모두 성공, 영구 실패는 재시도 0회, 나머지 자료는 모두 처리된다(SC-004~006).

## Decisions

- 2026-10-19 사실: PR #29(QK-FND-001)가 `b7be62a`로 병합된 뒤 이 브랜치를 만들었다.
- 2026-10-19 사용자 결정: WBS 1.3은 SCRUM-42 아래 새 하위 작업 SCRUM-98로 추적하고 담당은 구성재(Byuntil)다. 자동 생성이 동작하지 않아 에이전트가 Atlassian 연결로 만들었다.
- 2026-10-19 기존 결정 따름: Phase 0 완료 리뷰(0.G) 전에 Phase 1을 시작한다(#28 TASK.md 기록).
- 2026-10-18 기존 결정 따름: 요구사항 FR-ING-01, 10, 11은 원문이 없어 명세의 백로그 제목 대응표로 다룸을 확인한다(SCRUM-92).
- 2026-10-19 사용자 결정: 설계 산출물(`specs/QK-ING-001-source-adapter-contract/`의 plan.md, research.md, data-model.md, contracts/, quickstart.md, tasks.md.
  커밋 `8097c71`, `e8a2c6f`, `152d80d`)을 사람 리뷰어 Byuntil이 승인했다. 설계를 쓴 세션은 승인하지 않았다(AGENTS.md 2절).
- 2026-10-19 사용자 결정: 이 브랜치에서 구현까지 진행한다. 구현은 Codex 세션이 맡는다.
- 2026-10-19 사용자 결정: Codex가 보고한 설계 빈틈(`Retry-After` 상대값을 절대 시각으로 바꿀 기준 시각 없음)은 B안으로 닫는다.
  `RateLimitHint`에 `retry_after_seconds`를 두고 세션이 주입한 시계로 변환한다. 어댑터 계약(`rate_limit_hint(response)`)은 바꾸지 않는다.
- 2026-10-19 사용자 결정: 검증 분담. Codex는 구현과 `uv run pytest`·`uv run ruff`만 실행한다. Codex 샌드박스가 `.env*` 읽기를 막아 preflight를
  실행할 수 없으므로, AGENTS.md 7절 전체 검증(preflight 포함)은 구현 검토 세션이 실행한다. 이 PC에는 `python`이 없어 `python3`로 실행한다.
- 확인 필요: 공통 자료 형식 필드를 QK-STO-001 담당과 언제 맞출지(#33의 `data-model.md` 작성 시점).
