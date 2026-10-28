# Implementation Plan: QK-ING-003 Confluence 페이지 수집, 문서 분류, 회의록·용어집 처리

**Branch**: `feat/SCRUM-119-gh-72-confluence-pages` | **Date**: 2026-10-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-ING-003-confluence-pages/spec.md` (2026-10-28 사람 승인, R2 해석 포함)

## Summary

QK-ING-001 어댑터 계약을 구현하는 두 번째 실제 수집기 `ConfluencePagesAdapter`와 ADF → Markdown 변환기를 만든다. 한 실행은 스페이스 조회 → (팀 그룹 방식이면) 스페이스 권한 →
본문 없는 페이지 목록 → 폴더 사슬 → 콘텐츠별 보기 제한 상태 순서로 목록과 원본 권한 원값을 만들고, 팀 공용 판정을 통과한 페이지만 본문을 받는다.
문서 종류·미분류·제외 트리는 첫 단계 콘텐츠 ID로 어댑터가 정해 보안 필터 PATH 단계로 넘긴다. 사라진 페이지는 선택 Protocol로 단건 확인하고, 권한 조회 실패가 10%를 넘으면
문서 단위로 숨김만 한다. 변환 규칙 버전은 Confluence 문서의 변경 판정 재료(`chunk_input_hash`의 `extra`)에 넣고, 문서 종류·회의록 메타데이터는 청크 `locator["confluence"]`에 둔다.
새 메타데이터 스키마 버전은 Confluence가 켜졌을 때(활성이거나 한 번이라도 색인한 이력이 있을 때)만 인덱스 버전 재료가 되며, 대응표가 없으면 켜도 실행되지 않는다.
본문 링크 주소는 사이트(사람·개인 스페이스 경로 제외)와 등록된 공개 링크 호스트만 남긴다. 자료원은 비활성으로 등록한다.
plan 실측은 2026-10-28 사용자 결정으로 보류했고, 실측이 필요한 값은 설정·기본값에만 들어가게 설계했다. 근거는 [research.md](research.md)에 있다.

## Technical Context

**Language/Version**: Python 3.13 (QK-FND-001 R-01)

**Primary Dependencies**: 런타임·개발 의존성 추가 없음(`urllib`, `json`, `hashlib`, `base64`, `datetime`, `tomllib`). Markdown 청커는 기존 `markdown-it-py` 경로 그대로

**Storage**: 새 테이블·열·마이그레이션 없음. 메타데이터는 청크 `locator` JSON(research R-10). 확인 기록은 저장소 파일 `config/source_reviews/<자료원>.toml`

**Testing**: pytest 단위·공통 계약·로컬 DB 시험. 재생 전송(`adapters/replay.py`)과 시나리오 빌더로 외부 요청 0건. 실제 원본 시험은 `tests/external/`에 `@pytest.mark.external`로만 둔다

**Target Platform**: 색인 진입점(`qk-index`)과 개발 도구(`qk-dev`). 질의 진입점은 바꾸지 않는다

**Project Type**: 단일 Python 패키지. `adapters`에 두 모듈을 더하고 `domain`·`ports`·`sources`·`security`·`sync`·`indexer`·`config`·`devtools`를 고친다

**Performance Goals**: 별도 목표 없음. `Free` 사이트 정상 실행 약 `2N + 2F + ⌈N/250⌉ + 1`요청(N 페이지, F 폴더, 추론). 실제 값은 첫 측정(FR-027)

**Constraints**: 원본 쓰기 0건, `GET`만, 허용 호스트 `api.atlassian.com`. 기본 검증의 실제 원본 호출 0건(SC-009). 토큰·메일·Cloud ID·제목·본문·이름 기록 0건.
`domain`·`ports`는 표준 라이브러리만(`tests/unit/test_boundaries.py`). Confluence 꺼짐 배포에서 인덱스·메타데이터·청킹 버전과 GitHub 처리 결과 불변(SC-014)

**Scale/Scope**: 첫 자료원 1개(`SCRUM`, 페이지 수 BLOCKED). 요구사항 FR-001~032, 성공 기준 SC-001~014. QK-ING-001·QK-SEC-001·QK-SYN-001·QK-ING-002 코드 확장(spec Assumptions 범위)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 템플릿 상태라 원칙 초안 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다(QK-ING-002와 같다).

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01~C-03 답변 근거·현재 상태·자료 취급 | 답변 기능 없음. 본문의 지시문은 데이터로만 변환한다(spec Edge Cases) | 해당 없음 |
| C-04 작게 시작 | 스페이스 하나, 페이지 본문만. 첨부·댓글·블로그·화이트보드 없음. 스페이스 여러 개는 자료원별 식별 명세 뒤 | 통과 |
| C-05 비용 상한 | 0 Neurons(이 작업). 첫 색인 Neurons는 켜기 전 측정과 예산 대비 보고(SC-010) | 통과 — 측정 BLOCKED |
| C-06 교체 가능한 경계 | 어댑터·전송은 Protocol 구현, ADF 형식은 `adapters` 밖으로 나가지 않는다. 판정은 원값만 읽는다 | 통과 |
| C-07 재현 | 항목 ID순 정렬, 변환 바이트 결정성, 변환 규칙 버전, 변경 판별값에 제목 해시(R-08, R-09) | 통과 |
| C-08 멱등·실패 격리 | 목록 실패·잘림은 불완전, 페이지 실패는 그 페이지만, 조회 실패 대량이면 숨김만(R-05) | 통과 |
| C-09 원본 읽기 전용 | `GET`만, 세션이 강제. 범위 지정 토큰의 읽기 범위 | 통과 |
| C-10 민감 정보 | 계정 ID 버림, 메일 자리 표시, 이름은 확인 기록의 허용으로만(FR-021). 판정 기록·측정 출력은 ID만(R-15) | 통과 |
| C-11 명세 먼저 | 승인된 spec.md 뒤 계획. 요구사항 문구는 바꾸지 않았다 | 통과 |
| C-12 검증으로 닫기 | SC마다 시험([quickstart.md](quickstart.md)). 실제 원본 확인은 사람 측정 1회(SC-010) | 통과 |
| C-13 수치 조건 | 요청 수는 `(추론)`, 실측 값은 BLOCKED로 표시 | 통과 |
| C-14 권한 확인 | 스페이스 종류·상태·팀 그룹 또는 사이트 사용자 확인·자신과 상위 보기 제한을 모두 확인한 페이지만 팀 공용(R-03) | 통과 |
| AGENTS.md 3.1 자료원 추가 | ADR-026(Proposed)이 근거. 비활성 등록까지만 하고 켜기는 사람 단계 | 통과 — 켜기 때 ADR 승인 |
| AGENTS.md 3.3 인덱스 버전 | 꺼짐에서 버전 불변. 켜짐 버전은 대응표·QK-STO-002 없이는 실행되지 않음(R-10) | 통과 |
| AGENTS.md 4절 범위 | `AGENTS.md`·`CLAUDE.md`·`.claude/**` 수정 없음. 다른 명세 문서 수정 없음, 코드 확장은 spec Assumptions 범위 | 통과 |
| AGENTS.md 6절 민감정보 | 합성 시험 자료, 사이트 호스트 `site.invalid`. 실제 사이트 주소·Cloud ID는 저장소에 적지 않는다 | 통과 |
| AGENTS.md 9절 금지 | 계약 시험 `skip` 없음. 확인 기록은 사람이 쓴다 | 통과 |

Phase 1 설계 뒤 재점검: [contracts/confluence-adapter.md](contracts/confluence-adapter.md)가 요청 순서·허용 호스트·분류를, [contracts/adf-markdown.md](contracts/adf-markdown.md)가
변환 규칙을, [contracts/source-config.md](contracts/source-config.md)가 원본 호출 전 검사를, [contracts/sync-security.md](contracts/sync-security.md)가 GitHub 불변식을,
[contracts/cli.md](contracts/cli.md)가 사람 전용 측정을 고정했다. 새 위반 없음.

## Project Structure

### Documentation (this feature)

```text
specs/QK-ING-003-confluence-pages/
├── spec.md
├── plan.md                    # 이 파일
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── confluence-adapter.md  # 요청·매핑·권한 원값·단건 확인·분류
│   ├── adf-markdown.md        # 변환 규칙·경고·회의록·용어집
│   ├── source-config.md       # 설정·설정 항목·확인 기록·검증
│   ├── sync-security.md       # 보안 필터·동기화 확장과 불변식
│   └── cli.md                 # sources check·run·measure
├── measurement/
│   └── measure_confluence.py  # plan 실측(보류, 사람이 선택 실행)
├── checklists/requirements.md
└── tasks.md                   # /speckit-tasks 산출물
```

### Source Code (repository root)

```text
config/
├── sources.toml                         # 고침. confluence-scrum 비활성 등록
└── source_reviews/README.md             # 고침. Confluence 기록 형식 안내
src/qello_knowledge/
├── domain/
│   ├── source.py                        # 고침(ING-001). SourceItem.exclusion, SourceContent 새 필드 셋, ConversionWarning, MissingCheck
│   ├── sync.py                          # 고침(SYN-001). SourcePlan.incomplete_reason
│   ├── redact.py                        # 고침(SEC-001). OutputContext.opaque_item_fields
│   └── security.py                      # 고침(SEC-001). to_dict 비우기
├── ports/source.py                      # 고침(ING-001). MissingItemChecker
├── sources/
│   ├── kinds.py                         # 고침. scope_schema·extra_auth, confluence_pages
│   ├── config.py                        # 고침. 종류별 범위 값 검증과 정규화(GitHub 규칙 이전), 비활성 자료원 하나를 측정용으로 파싱
│   └── scope_review.py                  # 고침(ING-002). 종류별 범위 키, Confluence 기록 필드, 측정용 단일 대조
├── security/
│   ├── kinds.py                         # 고침. 새 필드 둘, Confluence 판정
│   ├── screen.py                        # 고침. exclusion → PATH_EXCLUDED
│   └── policy.py                        # 고침. output_context 전달, 종류별 버전 재료
├── adapters/
│   ├── http.py                          # 고침. authorization·default_headers 주입(기본값 = 지금 동작)
│   ├── confluence.py                    # 새 파일. ConfluencePagesAdapter
│   └── atlassian_adf.py                 # 새 파일. convert_adf
├── sync/
│   ├── keys.py                          # 고침(SYN-001). chunk_input_hash extra, scope_key, metadata_schema_version
│   ├── plan.py                          # 고침(SYN-001). 지문 extra, 사라진 자료 확인, 조회 실패 기준, incomplete_reason
│   ├── execute.py                       # 변경 없음(구현에서 locator_extra 합치기를 plan.py로 옮김)
│   ├── run.py                           # 고침(SYN-001). Confluence 켜짐(활성 ∨ 등록 이력) 반영
│   └── report.py                        # 고침. 요약 값
├── indexer/
│   ├── sync_cli.py                      # 고침. 종류별 팩토리, current_index_version, 켜짐 대응표 검사
│   └── cli.py                           # 고침. sources check 연결
├── config/
│   ├── registry.py                      # 고침. ATLASSIAN_* 설정 항목 넷(설정 예시 재생성)
│   └── check.py                         # 고침. _code_checks가 Confluence 켜짐도 반영
└── devtools/
    ├── measure.py                       # 고침. 종류별 측정, Confluence 출력
    └── db.py                            # 고침. measure 연결
tests/
├── contract/test_confluence_adapter_contract.py   # 새 파일
├── unit/
│   ├── adapters/confluence_scenarios.py           # 새 파일. 합성 응답 빌더
│   ├── adapters/confluence/test_confluence_{listing,access,content,classify,missing}.py   # 새 파일 다섯(이름 겹침 없음)
│   ├── adapters/test_atlassian_adf.py             # 새 파일
│   ├── adapters/test_http_transport.py            # 고침. 주입 사례(기존 사례 그대로)
│   ├── security/test_confluence_judge.py, test_opaque_fields.py   # 새 파일
│   ├── sources/test_config_confluence.py, test_scope_review_confluence.py   # 새 파일
│   ├── sync/test_plan_confluence.py               # 새 파일. 사라진 자료·조회 실패·exclusion
│   ├── sync/test_keys.py                          # 고침. extra·scope_key·스키마 버전 사례 추가(기존 고정값 그대로)
│   ├── config/test_confluence_check.py            # 새 파일
│   ├── chunking/test_confluence_glossary_chunks.py   # 새 파일
│   └── devtools/test_measure_confluence.py        # 새 파일
├── localdb/sync/test_confluence_sync.py           # 새 파일. 동기화 왕복·보안 내림·재처리
├── external/test_confluence_source.py             # 새 파일. @pytest.mark.external, 사람 실행
└── fixtures/
    ├── confluence/adf/*.json, *.md, *.warnings.json   # 합성 변환 사례
    └── source_reviews/confluence-*.toml               # 올바른·틀린 확인 기록
```

**Structure Decision**: Confluence 응답 해석·ADF 변환·실제 전송 설정은 `adapters`(외부 경계)에 둔다. 판정 규칙은 원값만 읽어 `security`에, 문서 단위 동기화 규칙은 `sync`에 일반 장치
(선택 Protocol, 새 필드의 기본값)로 넣고 Confluence 이름을 쓰지 않는다. 종류와 어댑터를 잇는 표는 `indexer`에 둔다(`sources`는 `adapters`를 가져올 수 없다).

## Complexity Tracking

위반 없음. 다른 명세 영역의 코드 변경은 spec Assumptions가 이 명세 구현 범위로 넣은 것이라 아래 "사람 확인"에 목록으로 둔다.

## 사람 확인이 필요한 것

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| 실측 보류의 영향 | 스페이스 종류·ID, 페이지 수·크기, 토큰 범위, `restriction-state` 상속 반영, `_links.base`, 대응표 ID, 첫 색인 Neurons가 BLOCKED다. 모두 설정·기본값·켜기 전 측정으로 채운다 | R-01 |
| 다른 영역 코드 확장 | ING-001(새 필드·선택 Protocol), ING-002(확인 기록 종류별화), SEC-001(PATH 표시·출력 비우기·버전 재료·조회 실패 기준 필드), SYN-001(지문 `extra`·사라진 자료 확인·조회 실패 기준·메타데이터 스키마 버전), 설정(범위 값 검증기·설정 항목 셋), 전송(인증 주입). 기본값에서 지금 동작 그대로 | R-04, R-05, R-07, R-09, R-10, R-12~R-15 |
| 본문을 따로 받기 | 목록에 본문을 넣지 않고 판정을 통과한 페이지만 받는다. ADR-026의 "목록에 본문을 함께 받아 단건 호출이 필요 없다"를 정정한다 | R-02 |
| 기본 제외를 제목 경로에 적용 | 파일 경로용 기본 제외가 `build`·`secrets` 같은 제목 페이지를 뺄 수 있다(덜 수집). 측정의 `PATH_EXCLUDED` 수로 본다 | R-06 |
| 판정 기록 전부 비우기 | Confluence 판정 기록은 팀 공용 판정도 제목·위치·링크를 비운다(spec보다 엄격) | R-15 |
| 보안 규칙 버전 변화 | Confluence 종류 등록만으로 꺼짐 배포의 보안 규칙 버전 값이 바뀐다. 문서 결정·인덱스 버전에는 영향 없음 | R-19 |
| 날짜 기준 | 사이트 사용자 확인 90일은 UTC 날짜로 센다 | R-13 |
| 미리 보기 요청 | `--preview`도 사라진 페이지 단건 확인 `GET`을 보낸다 | R-04 |
| 메일·Cloud ID 비밀 표시 | 비밀값은 아니지만 설정 보고에 값이 나오지 않게 비밀 항목으로 둔다 | R-12 |
| 켜짐 신호(결정됨) | 2026-10-28 사용자 결정: 활성 ∨ 저장소 등록 이력. 한 번 색인하면 끈 뒤에도 `+cf1`을 유지하고, 끈 자료원 페이지는 `--confirm-takedown` 동기화에서 내려간다(전체 내림은 비율 보류에 걸린다). `+cf1` 제거는 QK-STO-002 | R-10, plan 검토 P3 |
| 링크 주소 범위(결정됨) | 2026-10-28 사용자 결정: 사이트(사람·개인 스페이스 경로 제외)와 등록 공개 링크 호스트만, 쿼리·조각 버림. spec "공개 웹 주소"를 등록 목록으로 해석 | R-06, plan 검토 P4·P5 |
| 사이트 주소 설정 | 응답에 `_links.base`가 없을 때만 쓰는 선택 설정 `ATLASSIAN_SITE_URL`을 더한다 | R-01, R-12, plan 검토 P9 |
| 켜기와 ADR | 이 작업은 비활성 등록까지다. ADR-026 승인, 확인 기록, 대응표·`space_id`, 측정, 인덱스 대응표·QK-STO-002는 켜는 변경에서 사람이 한다 | R-10, R-17 |
