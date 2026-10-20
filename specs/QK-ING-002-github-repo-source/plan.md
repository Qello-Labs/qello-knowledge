# Implementation Plan: QK-ING-002 GitHub 저장소 파일 수집(트리 비교, 포함·제외 패턴)

**Branch**: `feat/SCRUM-100-gh-41-github-repo-source` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-ING-002-github-repo-source/spec.md` (2026-10-20 사람 승인, `0ab2931` 기준)

## Summary

QK-ING-001 어댑터 계약을 구현하는 첫 실제 수집기 `GitHubRepoFilesAdapter`와 표준 라이브러리 기반 실제 전송 `HttpsTransport`를 만든다.
목록 조회는 저장소 정보 → 커밋 확정 → 재귀 트리 세 요청으로 한 커밋 기준의 일반 파일 목록과 blob SHA를 만들고, 트리가 잘리면 ING-001 `ListPage`에
새로 더하는 `complete` 표시로 불완전을 알린다. 본문은 blob을 원문 형식으로 받아 git blob SHA를 검증한다. 공개 범위는 `visibility` 원값으로 넘겨
SEC-001이 판정한다. GitHub 한도 응답(403·429)은 일시적 실패로 다시 분류한다. 포함 패턴 확장자 검사와 자료원별 개인 정보 확인 기록 검사를
`qk-index sources check`·`run`에 더하고, 첫 자료원 `dnd-backend-docs`를 비활성으로 등록한다. 사람이 확인 기록을 쓰고 활성화한 뒤 `qk-dev source measure`로
첫 실제 수집을 잰다. 근거는 [research.md](research.md)에 있다.

## Technical Context

**Language/Version**: Python 3.13 (QK-FND-001 R-01)

**Primary Dependencies**: 런타임·개발 의존성 추가 없음(`urllib.request`, `ssl`, `hashlib`, `json`, `tomllib`, `datetime`, `platform`)

**Storage**: 해당 없음. 수집 결과 저장은 QK-SYN-001·QK-STO-001. 확인 기록은 저장소 파일 `config/source_reviews/<자료원>.toml`

**Testing**: pytest 단위 시험과 공통 계약 시험. ING-001 재생 전송(`tests/fixtures/responses/github/`)과 시험 안 전송 대역으로 외부 요청 0건.
실제 원본 시험은 `tests/external/`에 `@pytest.mark.external`로만 둔다(기본 실행에서 빠짐, `pyproject.toml` `addopts`)

**Target Platform**: 색인 진입점(`qk-index`)과 개발 도구(`qk-dev`). GitHub Actions `ubuntu-latest`와 개발자 PC. 질의응답 진입점(Workers)은 쓰지 않는다(ADR-008)

**Project Type**: 단일 Python 패키지. `adapters`에 두 모듈, `sources`·`devtools`에 각각 한 모듈을 더한다

**Performance Goals**: 별도 목표 없음. Phase 1 대상 한 실행 요청 약 84회, 기본 분당 60회 한도로 약 1분 반 `(추론)`. 실제 값은 측정(FR-022)

**Constraints**: 원본 쓰기 0건, `api.github.com`만(C-09, FR-015). 기본 검증의 실제 원본 호출 0건(FR-016). 토큰·헤더·본문 기록 0건(FR-015, SC-010).
`domain`·`ports`는 표준 라이브러리만(C-06, `tests/unit/test_boundaries.py`). 런타임 의존성 추가 없음(TASK 제외 범위)

**Scale/Scope**: 첫 자료원 1개(포함 문서 81개 추정, 인벤토리 `c070ae0` 기준). 요구사항 FR-001~024, 성공 기준 SC-001~010.
QK-ING-001 코드·시험 변경 네 곳(R-03, R-09, R-10, 사람 승인 필요)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 템플릿 상태라 원칙 초안 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다(QK-ING-001·QK-SEC-001과 같다).

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01~C-03 답변 근거·현재 상태·자료 취급 | 답변 기능 없음. 본문은 검증·전달만 하고 해석하지 않는다. 대상 저장소의 `AGENTS.md` 같은 지시 문서도 데이터로만 다룬다 | 해당 없음 |
| C-04 작게 시작 | 첫 자료원은 "포함" 범주 Markdown만(R-13). 잘린 트리 나눠 받기, 2차 한도 본문 판별, 웹훅 없음 | 통과 |
| C-05 비용 상한 | GitHub 약 84회/실행, 0 Neurons. 임베딩 없음 | 통과 |
| C-06 교체 가능한 경계 | 어댑터·전송은 ING-001 Protocol만 구현. GitHub 응답 형식은 어댑터 밖으로 나가지 않는다. `domain` 변경은 표준 라이브러리만(R-03, R-09) | 통과 |
| C-07 재현 | 한 커밋 확정, 항목 경로순 정렬, `version`=커밋, `change_key`=blob SHA, 본문 SHA 검증(R-02, R-04, R-05) | 통과 |
| C-08 멱등·실패 격리 | 본문 실패는 자료별 영구 실패. 목록 실패·잘림은 불완전 표시로 삭제 판단을 막는다(R-03) | 통과 |
| C-09 원본 읽기 전용 | `GET`만, 세션이 강제. 토큰은 공개 저장소 읽기 권한(`tokens.md` 2절) | 통과 |
| C-10 민감 정보 | 필터는 SEC-001 그대로. 개인 정보는 확인 기록으로 수집 전에 강제(R-12). 확장자 검사로 식별자 오인 차단을 줄임(R-11) | 통과 |
| C-14 권한 확인 | `visibility` 원값 그대로 전달, 판정은 SEC-001(R-06) | 통과 |
| C-11 명세 먼저 | 승인된 spec.md 뒤 계획. 빈 저장소(커밋 없음)를 불완전으로 보는 해석이 하나 있다(R-07). PR에서 명세 Edge Cases 문구 보완을 제안한다 | 통과 — 사람 확인 |
| C-12 검증으로 닫기 | SC마다 시험([quickstart.md](quickstart.md)). 실제 원본 확인은 사람 실행 측정 1회(SC-009) | 통과 |
| C-13 수치 조건 | 측정 기록에 커밋·범위·환경·날짜를 붙인다(R-14). 계획의 요청 수·크기는 `(추론)` 표시 | 통과 |
| AGENTS.md 3.1 자료원 추가 | 첫 자료원 활성화 전 결정 기록 필요 여부를 사람이 정한다(R-16) | 사람 확인 |
| AGENTS.md 4절 범위·하네스 파일 | `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정 없음. QK-ING-001 코드·시험 변경은 현재 TASK 제외 범위라 승인 후 범위를 넓힌다 | 사람 확인 |
| AGENTS.md 6절 민감정보 | 시험 자료는 합성 내용, 토큰 형식 값 없음(R-15). 전송 예외·로그에 주소·헤더 없음(R-08) | 통과 |
| AGENTS.md 9절 금지 | 계약 시험에 `skip`을 쓰지 않는다(R-10). 확인 기록은 사람이 쓴다(R-12) | 통과 |

Phase 1 설계 뒤 재점검: [contracts/github-adapter.md](contracts/github-adapter.md)가 요청 순서·허용 호스트·분류를, [contracts/source-reviews.md](contracts/source-reviews.md)가
수집 전 검사를, [contracts/cli.md](contracts/cli.md)가 측정 명령의 사람 전용 실행을 고정했다. 새 위반 없음.

## Project Structure

### Documentation (this feature)

```text
specs/QK-ING-002-github-repo-source/
├── spec.md
├── plan.md                 # 이 파일
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── github-adapter.md   # 어댑터 요청·매핑·분류, HttpsTransport
│   ├── source-reviews.md   # 확인 기록 형식, 확장자·기록 검사
│   └── cli.md              # sources check·run 확장, qk-dev source measure
├── checklists/requirements.md
└── tasks.md                # /speckit-tasks 산출물
```

### Source Code (repository root)

```text
config/
├── sources.toml                       # 고침. dnd-backend-docs 비활성 등록 (R-13)
└── source_reviews/
    └── README.md                      # 새 파일. 기록 형식 안내(contracts/source-reviews.md 요약). 기록 파일은 사람이 쓴다
src/qello_knowledge/
├── domain/
│   └── source.py                      # 고침(ING-001). ListPage.complete, content_hash() (R-03, R-09)
├── sources/
│   ├── collect.py                     # 고침(ING-001). list_all이 page.complete를 따른다 (R-03)
│   ├── session.py                     # 고침(ING-001). finalize_content가 content_hash() 사용 (R-09)
│   └── scope_review.py                # 새 파일. 확장자 검사, ScopeReview 읽기·대조, check_scope (R-11, R-12)
├── adapters/
│   ├── fake.py                        # 고침(ING-001). content_hash() 사용 (R-09)
│   ├── github.py                      # 새 파일. GitHubRepoFilesAdapter (R-01~R-07)
│   └── http.py                        # 새 파일. HttpsTransport (R-08)
├── indexer/
│   └── cli.py                         # 고침. sources check·run에 --reviews와 check_scope 연결
└── devtools/
    ├── db.py                          # 고침. qk-dev에 source measure 하위 명령 연결
    └── measure.py                     # 새 파일. SourceMeasurement, measure_source (R-14)
tests/
├── contract/
│   ├── source_adapter_contract.py     # 고침(ING-001). ContractExpectations 주입 (R-10)
│   ├── test_fake_adapter_contract.py  # 고침(ING-001). 가짜 어댑터 기대값
│   ├── test_second_fake_contract.py   # 고침(ING-001). 두 번째 가짜 어댑터 기대값
│   └── test_github_adapter_contract.py  # 새 파일
├── unit/
│   ├── adapters/
│   │   ├── github/
│   │   │   ├── conftest.py            # 재생 시나리오 조립, 시험 안 전송 대역
│   │   │   ├── test_listing.py        # SC-001~003
│   │   │   ├── test_content.py        # SC-004
│   │   │   ├── test_access.py         # SC-005 (SEC-001 screen_source와 함께)
│   │   │   └── test_classify.py       # SC-006
│   │   └── test_http.py               # 실제 전송, SC-010 일부
│   ├── sources/
│   │   ├── test_list_all.py           # 고침(ING-001). page.complete 사례 추가
│   │   └── test_scope_review.py       # SC-008
│   ├── indexer/test_cli.py            # 고침. --reviews 사례
│   └── devtools/test_measure.py       # 재생 전송으로 측정 출력 형식·가림 확인
├── external/
│   └── test_github_repo_source.py     # 새 파일. @pytest.mark.external, 사람 실행 (SC-009)
└── fixtures/
    ├── responses/github/*.json        # 합성 재생 응답 (R-15)
    └── source_reviews/*.toml          # 올바른·틀린 확인 기록
docs/sdd/research/
└── github-source-measurement.md       # 사람 실행 측정 결과(구현 뒤, FR-022·023)
```

**Structure Decision**: GitHub 응답 해석과 실제 전송은 `adapters`(외부 시스템 경계)에 둔다. 확인 기록 검사는 자료원 설정 검사와 같은 층인 `sources`에 새 모듈로 두고,
ING-001 `sources/config.py`와 SEC-001 `security/`는 고치지 않는다. 측정 명령은 실제 원본을 부르는 사람 전용 도구라 `devtools`에 둔다.
종류 이름과 어댑터를 잇는 일반 등록부는 QK-SYN-001이 만든다.

## Complexity Tracking

위반 없음. QK-ING-001 코드 변경 네 곳은 원칙 위반이 아니라 TASK 제외 범위 조정 대상이라 아래 "사람 확인"에 둔다.

## 사람 확인이 필요한 것

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| QK-ING-001 코드·시험 변경 | `ListPage.complete`·`list_all`(R-03), `content_hash()`와 두 호출처(R-09), 공통 계약 시험 기대값 주입(R-10). 현재 TASK 제외 범위("QK-ING-001 코드 수정")를 넓혀야 한다. 기존 동작은 바뀌지 않는다 | R-03, R-09, R-10 |
| 첫 자료원 활성화 | 구현은 비활성 등록까지다. 개인 정보 확인, 확인 기록 작성, 활성화, 측정은 사람이 한 PR에서 한다. 에이전트는 확인 기록을 대신 쓰지 않는다 | R-12, R-13 |
| 결정 기록 | 첫 자료원 활성화 전에 AGENTS.md 3.1 결정 기록이 필요한지, 필요하면 ID를 정한다 | R-16 |
| 포함 패턴 초안 | 인벤토리 "포함" 범주를 옮긴 초안이다. `**/AGENTS.md`와 에이전트 설정 디렉터리 제외의 조합을 확인해 달라 | R-13 |
| 명세 문구 보완 제안 | Edge Cases "파일이 하나도 없으면 완전"을 "커밋이 있고 트리가 비면 완전, 커밋이 없는 저장소는 불완전"으로 보완하는 수정을 PR에서 제안한다. 명세 수정은 재승인 대상이다 | R-07 |
| 2차 한도 한계 | 헤더 없이 본문으로만 오는 GitHub 2차 한도 응답은 영구 실패로 남는다. 받아들일지 | R-07 |
| 로드맵 1.7 표시 | `roadmap_status.py`가 다른 작업의 Issue #42로 1.7을 최신이 아니라고 한다. 이 작업 범위 밖이라 반영하지 않는다 | TASK.md |
