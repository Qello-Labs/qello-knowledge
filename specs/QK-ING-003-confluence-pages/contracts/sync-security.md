# Contract: 보안 필터·동기화 확장

근거: [research.md](../research.md) R-04, R-05, R-07, R-09, R-10, R-13, R-15, R-19 | 요구: spec FR-011, FR-012, FR-019, FR-020a, FR-021a, FR-030~FR-032

모든 변경은 새 필드의 기본값(`None`·`False`·`()`)일 때 지금과 같은 결정·출력·해시를 만든다. GitHub 자료원의 시험 기대값은 바꾸지 않는다.

## 보안 필터(QK-SEC-001 코드)

| 위치 | 변경 |
| --- | --- |
| `security/kinds.py` | `KindSecurityPolicy`에 `opaque_item_fields=False`, `lookup_failure_threshold=None`. Confluence 등록과 판정 함수 `judge_confluence_access`(data-model 4절) |
| `security/screen.py` PATH 단계 | `item.exclusion`이 있으면 `PATH_EXCLUDED`, 규칙 `source-exclude:<값>`. 기존 제외 검사보다 먼저 본다 |
| `domain/redact.py` `OutputContext`, `security/policy.py` `output_context` | `opaque_item_fields` 전달 |
| `domain/security.py` `to_dict` | `opaque_item_fields`면 `title`·`location`·`url`을 `None` |
| `security/policy.py` `_version`, `load_policy` | 종류별 추가 재료(`judge_mode`, 확인 기록 sha256)를 받는 인자. 없으면 지금 재료 |

## 동기화(QK-SYN-001 코드)

| 위치 | 변경 |
| --- | --- |
| `sync/keys.py` `chunk_input_hash` | 선택 인자 `extra=None`. `None`이면 지금 바이트열, 아니면 끝에 `"\0" + extra` |
| `sync/keys.py` `scope_key` | `confluence_pages:<space_id>` |
| `sync/keys.py` `metadata_schema_version` | `(code, confluence)`. 둘 다 꺼짐 `meta-v1`, 코드만 `meta-v2`, Confluence 켜짐이면 뒤에 `+cf1` |
| `sync/plan.py` 변경 판정 | `chunk_input_hash(..., extra=content.fingerprint_extra)` |
| `sync/plan.py` 사라진 자료 | 어댑터가 `MissingItemChecker`면, 일반 내림 후보에서 이미 끝난 `SECURITY_ACCESS` 보안 내림을 빼고 `check_missing` 결과로 바꾼다(research R-04 표·실패 대응). 아니면 지금 그대로 |
| `sync/plan.py` 조회 실패 기준 | 종류의 `lookup_failure_threshold`가 있고 (`ACCESS_HELD` ∧ `access_raw` 빔) 수 > 목록 항목 수 × 기준이면: `COLLECTION_INCOMPLETE`를 더하고, 그 문서들의 보안 내림을 `delete_bodies=False`로, 비율 검사의 `purge`·`pending` 수에서 빼고, `--confirm-takedown`이어도 `PURGE`를 붙이지 않는다 |
| `domain/sync.py` `SourcePlan` | `incomplete_reason: str \| None = None`. 계획 단계에서 불완전이 되면 `listing_complete=False`와 사유(data-model 10절) |
| `sync/plan.py` 청킹 뒤 | 청크 `locator`에 `content.locator_extra`를 합친다(키 충돌이면 오류, `merge_locator`). 구현에서 `sync/execute.py` 대신 계획 단계로 옮겼다. `artifact_kind`는 `item.item_type` 그대로 |
| `sync/run.py` `current_spec`, `indexer/sync_cli.py` `current_index_version`·`run_command`, `config/check.py` `_code_checks` | "Confluence 켜짐" = 활성 `confluence_pages` 자료원이 있음 ∨ 저장소에 그 종류의 자료원 정체성이 등록됨. 명령별 계산 순서는 research R-10 표(`sources check`는 앞의 조건만, `run`은 저장소를 연 뒤 두 번째 검사, `index status/activate`는 저장소를 연 뒤 계산, `_code_checks`는 `meta-v2`·`meta-v2+cf1` 중 하나 등록이면 통과). 켜짐 인덱스 버전이 `INDEX_KEYWORD_RULES`에 없으면 원본 호출 전에 실패 |
| `sync/report.py`·요약 | data-model 10절 값. 페이지는 ID로만 |

## 불변식(시험으로 지킨다)

- Confluence 꺼짐 설정에서 `iv-4c0bc4fcc642`, `meta-v1`, `chk-md-20d966f730bb`, GitHub 문서의 `chunk_input_hash`·`locator`·검색 헤더·임베딩 입력이 지금과 같다(SC-014).
- 보안 숨김은 어떤 보류에서도 실행된다. 조회 실패 기준을 넘어도 숨김은 하고, 비밀값 차단 문서의 본문 삭제는 기존 비율 보류만 따른다(SC-002).
- `check_missing`이 없는 종류는 계획 단계의 원본 요청이 늘지 않는다. 볼 수 없게 되어 이미 보안 내림된 페이지는 다음 실행에서 다시 확인하지 않는다.
- 조회 실패 기준을 넘은 실행의 조회 실패 문서는 `--confirm-takedown`에서도 본문이 지워지지 않는다(FR-031).
- Confluence를 한 번 색인한 뒤 끄면 인덱스 버전이 그대로이고(`INDEX_MISMATCH`가 생기지 않는다), 끈 자료원의 페이지는 일반 내림(`SOURCE_DISABLED`)으로 내려간다.
  자료원 전체를 내리면 내림 비율(20%)을 넘어 보류되므로 실제 내림은 `--confirm-takedown` 실행에서 일어난다(`sync/plan.py:186-196`, plan 재검토 N2). 이 절차는 GitHub 자료원 끄기와 같다.
- `exclusion`이 있는 항목은 본문을 받지 않는다(PATH 단계에서 멈춤).
- 보안 규칙 버전 값은 Confluence 등록으로 바뀐다. 이 값은 문서 결정과 인덱스 버전에 쓰이지 않는다(research R-19).
