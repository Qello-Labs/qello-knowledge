-- QK-STO-002 인덱스 버전 교체(research R-01·R-07·R-18, data-model 1절). 행을 지우지 않는다.

-- 1. 버전별 출처 정보(R-01). 청크를 쓴 트랜잭션의 자료 행 값을 청크에 둔다. NULL이면 자료 행 값으로 돌아간다.
ALTER TABLE qk.chunk
    ADD COLUMN source_url text,
    ADD COLUMN source_modified_at timestamptz,
    ADD COLUMN collected_at timestamptz;

UPDATE qk.chunk c
SET source_url = a.source_url, source_modified_at = a.source_modified_at, collected_at = a.collected_at
FROM qk.artifact a
WHERE a.id = c.artifact_id;

CREATE OR REPLACE FUNCTION qk.hit_json(c qk.chunk, a qk.artifact, hit_rank bigint, hit_score double precision) RETURNS jsonb
LANGUAGE sql IMMUTABLE AS $$
    SELECT jsonb_build_object(
        'chunk_id', c.id,
        'rank', hit_rank,
        'score', hit_score,
        'body', c.body,
        'provenance', jsonb_build_object(
            'source_url', coalesce(c.source_url, a.source_url),
            'source_version', c.source_version,
            'locator', c.locator,
            'heading_path', to_jsonb(c.heading_path),
            -- 원본 수정 시각은 NULL일 수 있어, 청크 출처 열이 비어 있는 옛 행(source_url IS NULL)만 자료 행 값을 쓴다.
            'source_modified_at', CASE WHEN c.source_url IS NULL THEN a.source_modified_at ELSE c.source_modified_at END,
            'collected_at', coalesce(c.collected_at, a.collected_at)
        )
    )
$$;

-- 2. 정리 표시(data-model 1.2).
ALTER TABLE qk.index_version
    ADD COLUMN pruned_at timestamptz,
    ADD CONSTRAINT index_version_pruned_is_archived CHECK (pruned_at IS NULL OR status = 'archived');

-- 3. 재색인 실행 표시(R-02).
ALTER TABLE qk.sync_run
    ADD COLUMN kind text NOT NULL DEFAULT 'sync' CHECK (kind IN ('sync', 'reindex'));

-- 4. 새 설정에서만 대상 아님인 문서(R-03).
ALTER TABLE qk.artifact DROP CONSTRAINT artifact_processed_outcome_check;
ALTER TABLE qk.artifact
    ADD CONSTRAINT artifact_processed_outcome_check CHECK (processed_outcome IN ('chunked', 'empty', 'not_target'));

-- 5. 전환 기록(R-07, data-model 1.3). 사람 이름 열은 없다.
CREATE TABLE qk.index_transition (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('first_activation', 'activation', 'rollback', 'prune', 'reuse')),
    at timestamptz NOT NULL DEFAULT now(),
    version text NOT NULL REFERENCES qk.index_version (id),
    before_active text,
    after_active text,
    documents int NOT NULL CHECK (documents >= 0),
    chunks int NOT NULL CHECK (chunks >= 0),
    target text NOT NULL CHECK (target IN ('local', 'remote', 'unknown')),
    gate_record_id text,
    gate_record_sha256 text,
    reason text CHECK (reason IS NULL OR char_length(reason) BETWEEN 1 AND 200),
    provenance_mismatch int CHECK (provenance_mismatch IS NULL OR provenance_mismatch >= 0),
    deleted_chunks int CHECK (deleted_chunks IS NULL OR deleted_chunks >= 0),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT index_transition_gate_pair CHECK ((gate_record_id IS NULL) = (gate_record_sha256 IS NULL)),
    CONSTRAINT index_transition_activation_gate CHECK (kind <> 'activation' OR gate_record_id IS NOT NULL),
    CONSTRAINT index_transition_gate_only_activation CHECK (kind = 'activation' OR gate_record_id IS NULL),
    CONSTRAINT index_transition_rollback_reason CHECK (kind <> 'rollback' OR reason IS NOT NULL),
    CONSTRAINT index_transition_prune_count CHECK (kind <> 'prune' OR deleted_chunks IS NOT NULL)
);
CREATE INDEX index_transition_by_version ON qk.index_transition (version, at);

-- 지금 활성 버전의 첫 활성화 이력을 채운다. 실행 위치는 알 수 없다.
INSERT INTO qk.index_transition (kind, at, version, before_active, after_active, documents, chunks, target, details)
SELECT 'first_activation', coalesce(v.activated_at, v.created_at), v.id, NULL, v.id,
       (SELECT count(DISTINCT c.artifact_id) FROM qk.chunk c JOIN qk.artifact a ON a.id = c.artifact_id
        WHERE c.index_version = v.id AND a.status = 'active' AND a.access_scope = 'team'),
       (SELECT count(*) FROM qk.chunk c WHERE c.index_version = v.id),
       'unknown', '{"backfilled": true}'::jsonb
FROM qk.index_version v
WHERE v.status = 'active';
