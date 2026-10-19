# Data Model: QK-STO-001 저장 스키마·마이그레이션·검색 질의

모든 객체는 PostgreSQL `qk` 스키마에 둔다(research R-02). 이름은 구현에서 바뀔 수 있지만 제약과 관계는 이 문서를 따른다.
코드 쪽 타입은 [contracts/store.md](contracts/store.md)에 있다.

## 관계

```text
index_version 1 ──< chunk >── 1 artifact
                      │
                      └── 0..1 embedding   (같은 embedding을 여러 chunk가 공유)
schema_migration       (독립)
```

## index_version (FR-005)

| 필드 | 타입 | 제약 |
| --- | --- | --- |
| `id` | text | PK. 예: `v1` |
| `embedding_model` | text | NOT NULL. 예: `@cf/baai/bge-m3` |
| `dimension` | int | NOT NULL, `= 1024` (ADR-002) |
| `chunking_version` | text | NOT NULL |
| `metadata_schema_version` | text | NOT NULL |
| `status` | text | `ready`·`active`·`archived` 중 하나 |
| `created_at`, `activated_at` | timestamptz | `created_at` 기본 `now()` |

- 활성은 하나 이하: 부분 고유 인덱스 `ON ((true)) WHERE status = 'active'`.
- 상태 전환(`ready → active → archived`)과 평가 게이트는 QK-STO-002가 만든다. 이 작업은 테스트 데이터로만 행을 넣는다.

## artifact (FR-001, FR-014)

| 필드 | 타입 | 제약 |
| --- | --- | --- |
| `id` | bigint identity | PK |
| `source_kind` | text | NOT NULL. 예: `github` |
| `source_id` | text | NOT NULL. `(source_kind, source_id)` 고유 |
| `source_url` | text | NOT NULL, 빈 문자열 금지 |
| `source_version` | text | NOT NULL, 빈 문자열 금지 |
| `source_modified_at` | timestamptz | NULL 허용(원본이 주지 않을 때) |
| `collected_at` | timestamptz | NOT NULL |
| `content_hash` | text | NOT NULL. 원본 내용 해시 |
| `chunk_set_hash` | text | NULL 허용. 마지막으로 반영한 청크 묶음 해시(R-07 멱등 판정) |
| `artifact_kind` | text | NOT NULL. 예: `markdown` |
| `title` | text | NULL 허용 |
| `access_scope` | text | NULL 허용. NULL은 "미확인" |
| `status` | text | `active`·`archived`·`deleted`, 기본 `active` |
| `updated_at` | timestamptz | 기본 `now()` |

- 상태 전환: `active ↔ archived`, `active|archived → deleted`. 삭제 전환은 즉시 모든 검색에서 빠진다. 물리 삭제는 QK-SYN-003.
- 검색 노출 조건: `status = 'active' AND access_scope = qk.visible_access_scope()`(현재 `'team'`, R-05).

## embedding (FR-003)

| 필드 | 타입 | 제약 |
| --- | --- | --- |
| `id` | bigint identity | PK |
| `input_hash` | text | NOT NULL |
| `model_version` | text | NOT NULL. `(input_hash, model_version)` 고유 |
| `vector` | vector(1024) | NOT NULL. 다른 차원은 DB가 거부 |
| `created_at` | timestamptz | 기본 `now()` |

- 인덱스: HNSW `vector_cosine_ops`.
- 같은 (입력 해시, 모델 버전)은 `INSERT ... ON CONFLICT DO NOTHING` 후 조회로 재사용한다. 지우는 정책은 QK-EMB-001.

## chunk (FR-002, FR-004)

| 필드 | 타입 | 제약 |
| --- | --- | --- |
| `id` | bigint identity | PK |
| `artifact_id` | bigint | FK → artifact, NOT NULL |
| `index_version` | text | FK → index_version, NOT NULL |
| `source_version` | text | NOT NULL, 빈 문자열 금지 |
| `locator` | jsonb | NOT NULL, `{}` 금지. 예: `{"path": "docs/a.md", "lines": [10, 42]}` |
| `heading_path` | text[] | NOT NULL, 기본 빈 배열 |
| `ordinal` | int | NOT NULL, `>= 0`. `(artifact_id, index_version, ordinal)` 고유 |
| `body` | text | NOT NULL |
| `search_text` | text | NOT NULL. 이번 작업에서는 `body`와 같다(R-03) |
| `chunking_version` | text | NOT NULL |
| `embedding_id` | bigint | FK → embedding, NULL 허용(임베딩 전 청크) |

- 인덱스: PGroonga(`search_text`), btree(`artifact_id, index_version, ordinal`).
- 원본 링크는 `artifact.source_url`, 모델 버전은 `embedding.model_version`·`index_version.embedding_model`로 되짚는다(SC-001).
- 벡터 검색은 `embedding_id`가 있는 청크만, 키워드 검색은 모든 청크를 대상으로 한다. 둘 다 노출 조건(위)과 활성 인덱스 버전을 건다.

## schema_migration (FR-016~018)

| 필드 | 타입 | 제약 |
| --- | --- | --- |
| `id` | bigint identity | PK |
| `version` | int | NOT NULL. 파일 이름 앞 번호 |
| `description` | text | NOT NULL |
| `checksum` | text | NOT NULL. 파일 SHA-256 |
| `destructive` | boolean | NOT NULL |
| `applied_at` | timestamptz | 기본 `now()` |
| `result` | text | `success`·`failed` |
| `error` | text | NULL 허용. 실패 시 오류 분류와 메시지(접속 정보 제외) |

- `version`별 `success` 행은 하나 이하(부분 고유 인덱스). 실패 행은 여러 개일 수 있다.
- 이 테이블과 `qk` 스키마는 실행기가 마이그레이션 적용 전에 `IF NOT EXISTS`로 만든다. 첫 마이그레이션이 실패해도 실패 기록을 남기기 위해서다.

## 검증 규칙 요약

| 규칙 | 강제 위치 | 요구사항 |
| --- | --- | --- |
| 출처(링크·버전·위치) 누락 거부 | DB 제약 + 경계 입력 검증 | FR-004 |
| 1,024차원 외 벡터 거부 | `vector(1024)` 칼럼 | FR-004 |
| 활성 인덱스 하나 이하 | 부분 고유 인덱스 | FR-005 |
| 권한·상태·버전 조건 | 검색 함수 `WHERE` | FR-008, C-14 |
| 상위 N 상한 50 | 검색 함수(`least(n, 50)`)와 경계 | FR-010 |
| 교체 원자성·직렬화 | 트랜잭션 + `FOR UPDATE` | FR-012, FR-013 |
