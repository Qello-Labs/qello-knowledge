# Implementation Plan: QK-SEC-001 색인 제외 경로·비밀값 차단·접근 범위 판정

**Branch**: `feat/SCRUM-99-gh-37-security-filter` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-SEC-001-security-filter/spec.md` (2026-10-20 사람 승인, `8d31c9d` 기준)

## Summary

QK-ING-001의 `list_all()`과 `fetch_contents()` 사이에 보안 필터를 끼운다. 목록 단계에서 경로 제외 → 접근 범위 → 메타데이터 비밀값·식별자 주소를 판정해
빠진 자료는 본문을 추가로 조회하지 않고(원래 목록의 완료 상태는 보존한다), 본문 단계에서 본문·제목·위치의 비밀값을 판정한다. 본문을 받지 못한 자료도 판정 실패로 기록한다. 두 단계를 잇는 `screen_source()`를 QK-SYN-001이 부른다.
비밀값 규칙은 `domain/secret_rules.py` 한 곳에 두고 `scripts/preflight.py`가 같은 파일을 경로로(`--staged`면 index에서) 불러 커밋 검사와 한 벌로 쓴다. Phase 1에서 쓰는
토큰 형식(GitHub 세분화, Cloudflare `cfat_`, Discord 봇, ClickUp `pk_`)을 더하고, 이름 규칙에 일반 `TOKEN`·`SECRET`과 따옴표 값을 더한다. 접근 판정 규칙과 공개 원본 링크 호스트는 자료원 종류별 정책으로
등록하고, 판정 기록·요약·로그는 모든 판정 경로에서 같은 가림 함수를 거친다. 근거는 [research.md](research.md)에 있다.

## Technical Context

**Language/Version**: Python 3.13 (QK-FND-001 R-01). 단, `domain/secret_rules.py`는 CI의 시스템 `python3`(3.12)에서 `preflight.py`가 불러오므로
3.12 문법·표준 라이브러리만 쓴다(R-02). 경로 맞춤은 3.13 `PurePosixPath.full_match(case_sensitive=False)`(R-04)

**Primary Dependencies**: 런타임·개발 의존성 추가 없음(`re`, `posixpath`, `pathlib`, `hashlib`, `json`, `tomllib`, `importlib`, `logging`)

**Storage**: 해당 없음. 판정 기록의 영구 저장은 QK-SYN-001·QK-STO-001. 예외 목록은 저장소 파일 `config/security_exceptions.toml`

**Testing**: pytest 단위 시험(`tests/unit/security/`, `tests/unit/domain/`). QK-ING-001 가짜 어댑터·재생 전송·가짜 시계로 외부 요청 0건.
비밀값 시험 자료는 실행 중에 만든다(R-12). `external` 시험 없음

**Target Platform**: 색인 진입점(`qk-index`)만. 전송 직전 검사는 QK-EMB-001·GEN-001이 쓸 함수로만 제공한다. GitHub Actions `ubuntu-latest`와 개발자 PC

**Project Type**: 단일 Python 패키지에 하위 패키지 하나(`security`)를 더한다

**Performance Goals**: Phase 1 규모(81개, 1.1 MB) 필터 처리 1분 이내(SC-008). 예상 1초 안팎 `(추론)`

**Constraints**: 필터를 끄는 설정 없음(FR-001). 추가 본문 조회 0건(FR-002). 판정 실패는 통과 0건(FR-004). 판정 기록·로그 비밀값·내부 주소 0건(FR-023).
`domain`·`ports`는 표준 라이브러리만(C-06). QK-ING-001 코드는 고치지 않는다(TASK.md 제외 범위)

**Scale/Scope**: 비밀값 규칙 16개(기존 12 중 2개 확장 + 신규 4, R-03), 기본 제외 범주 7개(R-04), 접근 규칙 2개(`github_repo_files`, `fake`).
요구사항 FR-001~024, 성공 기준 SC-001~010

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 아직 템플릿 상태라 원칙 초안 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다(QK-ING-001과 같다).

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01~C-03 답변 근거·현재 상태·자료 취급 | 답변 기능 없음. 본문은 패턴 검사만 하고 해석·실행하지 않는다 | 해당 없음 |
| C-04 작게 시작 | Phase 1 종류 두 개만 규칙 등록. 개인 정보 자동 탐지·엔트로피 탐지 없음(R-03, R-13) | 통과 |
| C-05 비용 상한 | 외부 호출 0, 0 Neurons | 통과 |
| C-06 교체 가능한 경계 | 규칙·제외·판정 타입은 `domain`(표준 라이브러리만). 필터는 ING-001 공통 형식만 입력으로 받음 | 통과 |
| C-07 재현 | 보안 규칙 버전을 판정을 바꾸는 모든 입력(규칙·제외·예외·주소 정책·종류 정책)의 해시로 계산(R-08). 경로 필드의 파일 이름은 가리지 않아 원본 위치로 되돌아갈 수 있다 | 통과 |
| C-08 멱등·실패 격리 | 자료별 판정, 예외는 `ERROR`로 막고 다음 자료 처리(R-09). 목록 불완전 표시 보존(R-11a), 본문 조회 실패도 판정 기록(R-11b) | 통과 |
| C-09 원본 읽기 전용 | 필터는 요청을 보내지 않는다. 본문 조회는 ING-001 세션이 `GET`만 보냄 | 통과 |
| C-10 민감 정보 | 경로 제외, 비밀값 차단(문서 전체), 전송 직전 검사, 기록 가림. 개인 정보는 사람 확인 절차(FR-024, QK-ING-002) | 통과 |
| C-14 권한 확인 | 팀 공용만 통과, 원본 권한 원값을 판정 기록에 보존(가림 우선) | 통과 |
| C-11 명세 먼저 | 승인된 spec.md 뒤 계획. FR-023 "주소"에서 경로 필드의 파일 이름 부분을 뺀 해석이 하나 있다(R-07, 2026-10-20 사용자 결정). PR에서 명세 문구 보완을 제안한다 | 통과 — 사람 확인 |
| C-12 검증으로 닫기 | SC마다 시험([quickstart.md](quickstart.md)). 응답 샘플·합성 자료로만 시험 | 통과 |
| C-13 수치 조건 | SC-008은 규모 조건(81개, 1.1 MB)과 함께 기록 | 통과 |
| AGENTS.md 3.1 비밀값 검사·권한 보존 | 임베딩·생성 전 검사(FR-013), 권한 원값 보존(FR-019) | 통과 |
| AGENTS.md 4절 하네스 파일 | `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정 없음. `scripts/preflight.py`는 보호 목록 밖이지만 CI 검사 스크립트라 사람 확인 항목으로 둠 | 통과 — 사람 확인 |
| AGENTS.md 6절 민감정보 | 시험 자료에 토큰 형식 값을 커밋하지 않음(R-12). 기록에 내부 주소 없음(맨 호스트 포함, R-07). ING-001 로그로 새는 `source_id`는 본문 조회 전에 막음(R-01) | 통과 |

Phase 1 설계 뒤 재점검: [contracts/security-filter.md](contracts/security-filter.md)가 단계 순서·추가 본문 조회 범위·막힌 본문 비우기를 고정했고,
[data-model.md](data-model.md)의 `SecurityVerdict.to_dict(context)`가 필드 종류별 가림 함수를 거친 값만 담고, 판정과 기록이 같은 `OutputContext`를 쓴다. 새 위반 없음.

## Project Structure

### Documentation (this feature)

```text
specs/QK-SEC-001-security-filter/
├── spec.md
├── plan.md                    # 이 파일
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── security-filter.md     # screen_source·단계 함수·전송 직전 검사·출력
│   ├── security-exceptions.md # config/security_exceptions.toml 형식과 검증
│   └── cli.md                 # qk-index security check, run 검사 추가
├── checklists/requirements.md
└── tasks.md                   # /speckit-tasks 산출물
```

### Source Code (repository root)

```text
config/
└── security_exceptions.toml          # 새 파일. 예외 없음 + 형식 안내 주석
scripts/
└── preflight.py                      # 고침. RULES·SECRET_NAME·PLACEHOLDER를 domain/secret_rules.py에서 경로로 불러온다 (R-02)
src/qello_knowledge/
├── domain/
│   ├── secret_rules.py               # 새 파일. SecretRule, RULES, REQUIRED_KINDS, find_secrets (3.12 호환)
│   ├── exclusions.py                 # 새 파일. 기본 제외 범주·패턴, 경로 정규화, excluded_by
│   └── security.py                   # 새 파일. AccessScope, Verdict, Stage, SecurityVerdict, FilterSummary, ScreenedContent
├── security/                         # 새 하위 패키지
│   ├── __init__.py
│   ├── kinds.py                      # KindSecurityPolicy 등록부(github_repo_files, fake). ING-001 sources/kinds.py는 고치지 않음
│   ├── policy.py                     # SecurityPolicy, 규칙 버전 계산, load_policy
│   ├── exceptions.py                 # 예외 파일 읽기·검증, PolicyIssue
│   ├── redact.py                     # FieldKind, AddressPolicy, OutputContext, safe_text(value, field_kind, context) (R-07)
│   ├── screen.py                     # screen_items, screen_contents, screen_source
│   ├── send_gate.py                  # OutgoingPiece, SendCheck, check_outgoing
│   └── report.py                     # security check 출력(표·JSON)
└── indexer/
    └── cli.py                        # 고침. security check 추가, run에 예외 파일 검증
tests/
├── unit/
│   ├── domain/
│   │   ├── test_secret_rules.py      # 필수 종류 합성값, placeholder, 3.12 호환(문법 검사)
│   │   └── test_exclusions.py
│   ├── security/
│   │   ├── conftest.py               # 합성 비밀값 생성기, 가짜 자료원 시나리오 조립
│   │   ├── test_access.py
│   │   ├── test_exceptions.py
│   │   ├── test_redact.py
│   │   ├── test_screen_items.py
│   │   ├── test_screen_contents.py
│   │   ├── test_screen_source.py     # 추가 본문 조회 0건, 목록 불완전 보존, 판정 수 = 목록 수
│   │   ├── test_send_gate.py
│   │   ├── test_no_secret_leak.py    # SC-005, SC-010
│   │   ├── test_error_isolation.py   # SC-007
│   │   ├── test_performance.py       # SC-008
│   │   └── test_second_kind.py       # SC-006 (별도 커밋)
│   ├── indexer/test_cli.py           # 고침. security check 사례
│   └── test_preflight_shared_rules.py  # 같은 규칙, 3.12 문법, -I 실행, --staged는 index 규칙
└── fixtures/
    ├── responses/fake/security_*.json  # 경로·접근 시나리오. 비밀값 자리는 {{SECRET:<종류>}} 자리표시
    └── security/*.toml                 # 올바른·틀린 예외 파일
```

**Structure Decision**: QK-ING-001의 `sources` 하위 패키지와 같은 층에 `security`를 둔다. `security`는 `domain`·`ports`·`sources`(collect)를 가져오고
`adapters`를 가져오지 않는다. 규칙·제외·판정 타입처럼 순수한 것은 `domain`에 두어 경계 시험을 받는다. ING-001 코드(`sources/`, `adapters/`, `domain/source*.py`)는
고치지 않는다. `indexer/cli.py`는 하위 명령만 더한다.

## Complexity Tracking

위반 없음.

## 사람 확인이 필요한 것

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| `scripts/preflight.py` 수정 | 규칙을 `domain/secret_rules.py`에서 불러오고 새 규칙 4개를 더한다. 새 규칙이 기존 저장소 파일에 걸리면 같은 PR에서 예외 목록에 넣고 사유를 적는다 | R-02, R-03 |
| 공수 | 로드맵 크기 S(약 1인일)를 M(약 2~3인일)으로 보는 게 맞다. 로드맵 4절 수정은 사람 승인 대상이다 | R-15 |
| QK-ING-001 로그 | `collect.py` 로그와 `FetchResult.to_dict()`가 `source_id`를 그대로 남긴다. #35는 고치지 않고, 비밀값이나 주소가 든 `source_id`는 본문 조회 전에 막는다(2026-10-20 사용자 결정) | R-01 |
| QK-ING-002 인계 | GitHub 저장소 공개 범위를 `AccessInfo.raw`의 `("visibility", "public")`로 담고, 개인 정보 확인 기록 절차를 정한다 | R-05, R-13 |
| QK-STO-001 값 이름 | `AccessScope`(`TEAM`·`RESTRICTED`·`UNKNOWN`)를 #33 `data-model.md`와 맞춘다 | data-model.md |
| 맨 호스트 이름 | 필드 종류별로 판정한다(방안 A, 2026-10-20 사용자 결정). 확장자 예외는 경로 필드의 파일 이름에만 적용한다. QK-ING-002는 포함 패턴의 확장자를 목록과 대조하고 GitHub `source_id`를 저장소 안 경로로 정한다 | R-07 |
| 명세 문구 보완 제안 | FR-023에 "경로 필드의 파일 이름 부분은 주소로 보지 않는다(C-07)"를 더하는 수정을 PR에서 제안한다. 명세 수정은 재승인 대상이다 | R-07 |
| `--staged` 규칙 | `--staged`는 index의 규칙 파일로 검사한다. 규칙 파일이 index에 없으면 실패한다 | R-02 |
