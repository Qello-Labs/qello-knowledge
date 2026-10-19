# Contract: 저장소 경계 (`ports/store.py`)

후속 명세(QK-EMB-001, QK-SYN-001, QK-RET-001, QK-STO-002)가 이 경계만 보고 저장소를 쓴다. 입력과 출력은 `domain/store.py`의
표준 라이브러리 dataclass이고 psycopg·pgvector 타입이 나오지 않는다(FR-015, C-06). 필드 의미와 DB 제약은 [data-model.md](../data-model.md)를 따른다.

## 타입

```text
ArtifactRecord   source_kind, source_id, source_url, source_version, source_modified_at?, collected_at,
                 content_hash, artifact_kind, title?, access_scope?
ChunkInput       ordinal, locator: Mapping, heading_path: tuple[str, ...], body, search_text,
                 chunking_version, embedding: EmbeddingRef?
EmbeddingRef     input_hash, model_version
SearchFilter     source_kinds: tuple[str, ...] = (), artifact_kinds: tuple[str, ...] = ()
Provenance       source_url, source_version, locator, heading_path, source_modified_at?, collected_at
SearchHit        chunk_id, rank, score, body, provenance: Provenance
SearchResult     status: "ok" | "no_active_index", index_version?, hits: tuple[SearchHit, ...]
NeighborResult   center: SearchHit, before: tuple[SearchHit, ...], after: tuple[SearchHit, ...], parents: tuple[SearchHit, ...]
ChunkTrace       chunk_id, provenance: Provenance, chunking_version, index_version, embedding_model?
ReplaceOutcome   "replaced" | "unchanged"
StoreUsage       total_bytes, chunk_count, embedding_count
```

## 연산

| 연산 | 입력 | 출력 | 규칙 |
| --- | --- | --- | --- |
| `upsert_artifact` | `ArtifactRecord` | artifact id | `(source_kind, source_id)`로 갱신. 출처 필드가 비면 `InvalidRecord` |
| `replace_chunks` | artifact id, index version, `source_version`, `Sequence[ChunkInput]` | `ReplaceOutcome` | 한 트랜잭션. 같은 버전·같은 묶음이면 `unchanged`. 실패하면 이전 묶음 유지(FR-012·013) |
| `mark_deleted` | `(source_kind, source_id)` | 없음 | 상태를 `deleted`로. 이미 삭제면 그대로(FR-014) |
| `put_embedding` | `EmbeddingRef`, `Sequence[float]` | 없음 | 길이 1,024가 아니면 `InvalidRecord`. 이미 있으면 그대로(FR-003·004) |
| `find_embedding` | `EmbeddingRef` | `tuple[float, ...] \| None` | 모델 버전이 다르면 `None`(US5) |
| `search_vector` | 질의 벡터, `top_n`, `SearchFilter` | `SearchResult` | 거리 순. `top_n`은 1~50으로 자른다(FR-006·008·010) |
| `search_keyword` | 검색어, `top_n`, `SearchFilter` | `SearchResult` | 관련도 순. 빈 검색어는 질의 없이 `hits=()`. 특수 문자는 글자 그대로(FR-007·010) |
| `chunk_neighbors` | chunk id, `before`, `after` | `NeighborResult \| None` | 같은 자료·같은 인덱스 버전 안. 노출 조건을 똑같이 건다(FR-011) |
| `trace_chunk` | chunk id | `ChunkTrace \| None` | 출처·청킹 규칙 버전·인덱스 버전·임베딩 모델 버전. 운영 확인용이라 노출 조건을 걸지 않는다(US1, SC-001) |
| `usage` | 없음 | `StoreUsage` | FR-023 |

- 검색 결과의 `rank`는 1부터 시작하고, `score`는 클수록 가깝다(벡터: `1 - 코사인 거리`, 키워드: PGroonga 점수).
- 활성 인덱스 버전이 없으면 `SearchResult(status="no_active_index", hits=())`다. 오류를 던지지 않는다.
- 노출 조건(활성 인덱스 버전 · `artifact.status = active` · `access_scope = team`)은 검색 함수 안에서만 판정한다. 경계 구현이 결과를 다시 거르지 않는다.

## 오류

| 오류 | 언제 | 호출자 처리 |
| --- | --- | --- |
| `InvalidRecord` | 출처 누락, 차원 불일치, 빈 위치 정보 | 해당 문서만 실패 처리(C-08) |
| `StoreUnavailable` | 연결 실패, 운영 인스턴스 중지·회수 | 사용자 안내는 호출자(QK-BOT-001)가 정한다 |
| `StoreError` | 그 밖의 DB 오류 | 메시지에 접속 정보·비밀 값을 넣지 않는다 |

## SQL 함수 (Workers 경로와 공유, research R-06)

| 함수 | 반환 |
| --- | --- |
| `qk.search_vector(query vector(1024), top_n int, source_kinds text[], artifact_kinds text[])` | `jsonb` `{active_index_version, hits[]}` |
| `qk.search_keyword(query text, top_n int, source_kinds text[], artifact_kinds text[])` | 같은 형식 |
| `qk.chunk_neighbors(chunk_id bigint, before int, after int)` | `jsonb` |
| `qk.visible_access_scope()` | `text` (`'team'`) |

`hits[]` 원소의 키는 `SearchHit`·`Provenance` 필드 이름과 같다.
