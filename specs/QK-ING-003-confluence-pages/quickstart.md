# Quickstart: QK-ING-003 검증

근거: [plan.md](plan.md), [contracts/](contracts/) | 기본 검증은 재생 응답만 쓰고 실제 원본 호출·Workers AI 호출은 0건이다(SC-009).

## 1. 기본 검증(저장소 루트)

```bash
uv run python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
```

마이그레이션은 없으므로 `qk-migrate`는 지금 결과(`applied=0`)와 같아야 한다.

## 2. 성공 기준과 시험

| SC | 확인 | 시험(구현 단계 파일 이름, tasks에서 확정) |
| --- | --- | --- |
| SC-001 | 여러 쪽 목록이 기대 목록과 같고 중복·초안 0건, 두 번 같음 | `tests/unit/adapters/confluence/test_confluence_listing.py` |
| SC-002 | 판정 사례 100% 일치, 팀 공용 아닌 청크 0건, 사라진 페이지 보안 내림, 조회 실패 기준·목록 경합 | `tests/unit/adapters/confluence/test_confluence_access.py`, `tests/unit/security/test_confluence_judge.py`, `tests/unit/sync/test_plan_confluence.py` |
| SC-003 | ADF 사례가 기대 Markdown·경고와 같고 두 번 같음 | `tests/unit/adapters/test_atlassian_adf.py` + `tests/fixtures/confluence/adf/` |
| SC-004 | 계정 ID 0건, 판정 기록·측정 출력에 제목·경로·링크 0건, 이름 미허용 기록 실패, GitHub 판정 기록 그대로(규칙 버전 제외) | `tests/unit/security/test_opaque_fields.py`, `tests/unit/devtools/test_measure_confluence.py`, `tests/unit/sources/test_scope_review_confluence.py` |
| SC-005 | 회의 날짜·종류·명세 ID, 메타데이터 없음 경고 | `test_atlassian_adf.py` 회의록 사례 |
| SC-006 | 용어집 행 수 = 용어 청크 수 | `tests/unit/chunking/test_confluence_glossary_chunks.py` |
| SC-007 | 설정·기록 실패 사례의 원본 호출 0건, 개인 스페이스 종류는 페이지 호출 0건, GitHub 검증 그대로 | `tests/unit/sources/test_config_confluence.py`, `test_scope_review_confluence.py`, `test_confluence_listing.py` |
| SC-008 | 429 일시적, 401 정지, 페이지 403 그 페이지만 | `tests/unit/adapters/confluence/test_confluence_classify.py` |
| SC-009 | 공통 계약 시험 통과, 기본 검증의 실제 원본 호출·쓰기 0건 | `tests/contract/test_confluence_adapter_contract.py` |
| SC-010 | (사람 단계) 첫 실제 측정 기록 | 아래 4절 |
| SC-011 | 미분류·홈·홈 밖·색인 안 함·제외 트리 청크 0건, 보안 내림, 제목 바뀐 제외 트리 유지 | `test_confluence_listing.py`, `tests/localdb/sync/test_confluence_sync.py` |
| SC-012 | 링크 규칙 | `test_atlassian_adf.py` 링크 사례 |
| SC-013 | 변환 규칙 버전 바뀌면 Confluence만 다시 처리 | `tests/unit/sync/test_keys.py`(지문), `tests/localdb/sync/test_confluence_sync.py` |
| SC-014 | Confluence 꺼짐에서 인덱스·메타데이터·청킹 버전과 GitHub 기대값 그대로. 한 번 색인 뒤 끄면 버전 그대로이고 `--confirm-takedown` 실행에서 페이지가 내려감 | 기존 `tests/unit/sync/test_keys.py`·`tests/unit/chunking/test_version.py` 고정값, `tests/unit/config/test_confluence_check.py`, `tests/localdb/sync/test_confluence_sync.py` |
| (SC-002 보충) | 사라진 페이지 단건 확인 결과·실패 대응, 끝난 보안 내림 재확인 없음 | `tests/unit/adapters/confluence/test_confluence_missing.py`, `tests/unit/sync/test_plan_confluence.py` |

## 3. 꺼짐 배포 확인

```bash
uv run qk-index sources check
uv run qk-index index status
```

`confluence-scrum`이 비활성으로 보이고, 현재 인덱스 버전이 `iv-4c0bc4fcc642`로 그대로여야 한다.

## 4. 켜기 전 사람 단계(이 작업 범위 밖, 순서만)

1. Atlassian 토큰 범위와 접두어를 확인한다(ADR-026). 필요하면 plan 실측 스크립트를 돌린다(contracts/cli.md).
2. `space_id`, `doc_types`, `exclude_trees`를 채우고 개인 정보 확인 기록을 쓴다(contracts/source-config.md).
3. `qk-dev source measure --name confluence-scrum --chunk --json`으로 첫 측정을 하고 FR-027 항목을 기록한다(SC-010). 예상 Neurons가 하루 색인 예산을 넘으면 켜기 전에 보고한다.
4. 켜는 변경: `enabled = true`, `INDEX_KEYWORD_RULES`에 켜짐 인덱스 버전 추가, QK-STO-002 절차로 새 인덱스 버전 생성·평가·활성화(FR-032).
