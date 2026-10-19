# Implementation Plan: QK-ING-001 자료원 어댑터 계약·자료원 설정·호출 한도·재시도

**Branch**: `feat/SCRUM-98-gh-34-source-adapter-contract` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-ING-001-source-adapter-contract/spec.md`

## Summary

QK-FND-001이 비워 둔 자료원 경계(`SourceAdapter`)를 채운다. 수집을 어댑터(요청 만들기·응답 해석), 전송(요청 하나), 수집 세션(읽기 전용 강제·
호출 한도·재시도·리다이렉트·크기 상한) 세 층으로 나눠, 한도와 재시도는 세션에서 한 번만 구현한다. 공통 자료 형식은 QK-STO-001 원본 자료 항목을
채울 수 있게 맞춘다. 자료원 설정은 `config/sources.toml`(TOML, 표준 라이브러리)로 선언하고 수집 전에 검증한다. 시험은 저장된 응답을 돌려주는
재생 전송과 가짜 시계로 하고, 모든 어댑터가 상속할 공통 계약 테스트를 둔다. 근거는 [research.md](research.md)에 있다.

## Technical Context

**Language/Version**: Python 3.13 (QK-FND-001 R-01). 포함·제외 패턴에 3.13의 `PurePath.full_match()`를 쓴다(R-05)

**Primary Dependencies**: 런타임 의존성 추가 없음(`tomllib`, `pathlib`, `hashlib`, `random`, `logging`). 개발 의존성도 추가 없음

**Storage**: 해당 없음. 저장은 QK-STO-001·QK-SYN-001

**Testing**: pytest. 계약 시험(`tests/contract/`)과 단위 시험(`tests/unit/sources/`). 재생 전송·가짜 시계로 외부 요청 0건, 실제 대기 0초.
`external` 시험 없음

**Target Platform**: 색인 진입점(`qk-index`)만. GitHub Actions `ubuntu-latest`와 개발자 PC. Workers(질의응답)에서는 쓰지 않는다(ADR-008)

**Project Type**: 단일 Python 패키지(QK-FND-001 구조)에 하위 패키지 하나(`sources`)를 더한다

**Performance Goals**: 처리 속도 목표 없음. 분당 요청 상한(기본 60회)이 속도를 정한다(R-15). 단위·계약 시험 전체가 수 초 안에 끝난다(가짜 시계)

**Constraints**: 원본 쓰기 요청 0건(SC-002). 결과·로그 비밀값 0건(SC-007). 잘못된 설정이면 원본 호출 0건(SC-003). `domain`·`ports`는 표준
라이브러리만(C-06). 런타임 의존성 0 유지

**Scale/Scope**: 등록 종류 2개(`github_repo_files`, `fake`). 실제 어댑터 0개(GitHub 어댑터는 QK-ING-002). 요구사항 FR-001~022, 성공 기준 SC-001~007

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 아직 템플릿 상태라 원칙 초안 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다(QK-FND-001과 같다).

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01~C-03 답변 근거·현재 상태·자료 취급 | 답변 기능 없음. 본문은 데이터로만 다루고 해석하지 않는다 | 해당 없음 |
| C-04 작게 시작 | 실제 어댑터 없이 계약·가짜 어댑터까지. 동시성 없음(R-15) | 통과 |
| C-05 비용 상한 | 외부 호출 0, 0 Neurons | 통과 |
| C-06 교체 가능한 경계 | 공통 형식·요청·응답이 `domain`, Protocol이 `ports`. 경계 시험이 그대로 검사 | 통과 |
| C-07 재현 | 내용 해시를 세션 한 곳에서 같은 규칙(SHA-256, UTF-8)으로 계산. 모든 항목에 원본 위치·버전 | 통과 |
| C-08 멱등·실패 격리 | 자료별 실패를 결과에 기록하고 다음 자료 처리. 목록 불완전 표시로 잘못된 삭제 판단 방지 | 통과 |
| C-09 원본 읽기 전용 | 세션이 `GET`·`HEAD` 밖을 막고 계약 시험이 요청을 기록해 확인(R-10) | 통과 |
| C-10 민감 정보 | 결과·로그에 헤더·본문·질의 문자열 없음, preflight 규칙으로 시험(R-13). 설정의 토큰 값 차단 | 통과 |
| C-14 권한 확인 | 원본 권한을 그대로 보존, 없으면 `UNKNOWN`. 판정은 QK-SEC-001 | 통과 |
| C-11 명세 먼저 | spec.md 승인(PR #27) 뒤 계획. 명세 문구와 다르게 해석한 두 곳(제목 필드 R-03, 크기 초과 상태 R-08)은 PR에서 명세 수정 제안 | 통과 — 사람 확인 |
| C-12 검증으로 닫기 | 성공 기준마다 시험([quickstart.md](quickstart.md)). 응답 샘플로만 시험 | 통과 |
| C-13 수치 조건 | 기본값(R-16)은 초기값으로 표시. 측정은 QK-ING-002 | 통과 |
| AGENTS.md 3.1 자료원 추가 | 종류 목록에 Notion 없음. 종류 추가는 결정 기록 필요를 오류 문구로 안내 | 통과 |
| AGENTS.md 4절 하네스 파일 | `AGENTS.md`, `CLAUDE.md`, `.claude/**`, `scripts/preflight.py` 수정 없음(preflight는 읽기만) | 통과 |

Phase 1 설계 뒤 재점검: [contracts/source-adapter.md](contracts/source-adapter.md)가 어댑터의 직접 I/O 금지·읽기 전용·SDK 타입 금지를 규칙으로 고정했고,
[data-model.md](data-model.md)의 `FetchResult.to_dict()`가 본문·헤더·토큰을 담지 않는다. 새 위반 없음.

## Project Structure

### Documentation (this feature)

```text
specs/QK-ING-001-source-adapter-contract/
├── spec.md
├── plan.md                  # 이 파일
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── source-adapter.md    # Protocol, 세션, 공통 수집 함수, 계약 시험
│   ├── sources-config.md    # config/sources.toml 형식과 검증
│   └── cli.md               # qk-index sources check, run
├── checklists/requirements.md
└── tasks.md                 # /speckit-tasks 산출물
```

### Source Code (repository root)

```text
config/
└── sources.toml                     # 새 파일. 자료원 없음 + 형식 안내 주석 (R-04)
src/qello_knowledge/
├── domain/
│   ├── source.py                    # 새 파일. 공통 자료 형식, 요청·응답, 분류·힌트 기본 함수, 결과, 오류
│   ├── source_config.py             # 새 파일. 자료원 설정 값 객체(SourceConfig 등). 읽기·검증은 sources/config.py
│   └── scope.py                     # 새 파일. 포함·제외 패턴(full_match, 제외 우선)
├── ports/
│   └── source.py                    # 채움. SourceAdapter, SourceTransport, SourceSession Protocol
├── sources/                         # 새 하위 패키지. 수집 공통 동작
│   ├── __init__.py
│   ├── kinds.py                     # 등록 종류(github_repo_files, fake)와 scope 키 규칙
│   ├── config.py                    # TOML 읽기, 검증, ConfigIssue. 결과는 domain/source_config.py 값 객체
│   ├── clock.py                     # Clock Protocol과 시스템 시계
│   ├── limits.py                    # 미끄러지는 창 한도, 실행당 상한, 원본 힌트 합치기
│   ├── retry.py                     # RetryPolicy, full jitter 백오프
│   ├── session.py                   # 수집 세션: 읽기 전용, 한도, 재시도, 리다이렉트, 크기, 해시·시각
│   ├── collect.py                   # list_all, fetch_contents
│   └── report.py                    # 설정 점검·수집 결과 출력(표·JSON), 값 비노출
├── adapters/
│   ├── fake.py                      # 새 파일. FakeSourceAdapter (fake.invalid 가상 API)
│   └── replay.py                    # 새 파일. ReplayTransport (응답 샘플 재생, 요청 기록)
└── indexer/
    └── cli.py                       # 고침. sources check 추가, run에 자료원 검사
tests/
├── contract/
│   ├── __init__.py
│   ├── source_adapter_contract.py   # 공통 계약 시험 기반 클래스
│   ├── test_fake_adapter_contract.py
│   ├── second_fake.py               # SC-001용 두 번째 가짜 어댑터 (별도 커밋)
│   └── test_second_fake_contract.py
├── unit/
│   ├── domain/test_scope.py
│   ├── sources/
│   │   ├── conftest.py              # 가짜 시계, 고정 난수
│   │   ├── test_config.py
│   │   ├── test_limits.py
│   │   ├── test_retry.py
│   │   ├── test_session.py
│   │   ├── test_collect.py
│   │   └── test_no_secret_leak.py
│   └── indexer/test_cli.py          # 고침. sources check, run 사례 추가
└── fixtures/
    ├── responses/fake/*.json        # 시나리오별 저장 응답
    └── sources/*.toml               # 올바른·틀린 설정 예
```

**Structure Decision**: QK-FND-001의 단일 패키지 구조를 그대로 쓴다. 공통 자료 형식은 경계 규칙을 받는 `domain`에, 수집 공통 동작은 새 하위 패키지
`sources`에 둔다. `sources`는 `domain`·`ports`·`config`만 가져오고 `adapters`를 가져오지 않는다. 종류 이름과 어댑터 구현을 잇는 일은 수집을 실제로
실행하는 QK-SYN-001이 진입점에서 한다. 가짜 어댑터와 재생 전송은 후속 명세의 시험에서 가져다 쓰므로 `tests/`가 아니라 `adapters/`에 둔다(R-11).

## Complexity Tracking

위반 없음.

## 사람 확인이 필요한 것

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| 명세 문구 정리 | Edge Cases "크기 초과로 건너뜀"을 FR-017(영구 실패)에 맞추고, FR-002 목록에 제목을 더하는 수정을 PR에서 제안한다 | R-03, R-08 |
| QK-STO-001 필드 맞춤 | [data-model.md](data-model.md) 대응표를 #33 담당과 확인한다 | R-03, TASK.md |
| 기본값 | 분당 60회, 실행당 2,000회, 본문 1 MB는 추론값이다. QK-ING-002 측정으로 조정한다 | R-16 |
