-- QK-STO-001 검색 질의(FR-006~011, research R-03~R-06).
-- 노출 조건(활성 인덱스 버전, 활성 자료, 팀 공용 접근 범위)은 이 함수들 안에서만 판정한다(FR-008, C-14).
-- 반환 키는 contracts/store.md의 SearchHit·Provenance 필드 이름과 같다.

-- 검색에 노출할 접근 범위 값. 값 체계는 QK-SEC-001이 정한다. 그 밖의 값과 NULL(미확인)은 모두 뺀다(research R-05).
CREATE FUNCTION qk.visible_access_scope() RETURNS text
LANGUAGE sql IMMUTABLE AS $$ SELECT 'team'::text $$;

CREATE FUNCTION qk.active_index_version() RETURNS text
LANGUAGE sql STABLE AS $$ SELECT id FROM qk.index_version WHERE status = 'active' $$;

CREATE FUNCTION qk.hit_json(c qk.chunk, a qk.artifact, hit_rank bigint, hit_score double precision) RETURNS jsonb
LANGUAGE sql IMMUTABLE AS $$
    SELECT jsonb_build_object(
        'chunk_id', c.id,
        'rank', hit_rank,
        'score', hit_score,
        'body', c.body,
        'provenance', jsonb_build_object(
            'source_url', a.source_url,
            'source_version', c.source_version,
            'locator', c.locator,
            'heading_path', to_jsonb(c.heading_path),
            'source_modified_at', a.source_modified_at,
            'collected_at', a.collected_at
        )
    )
$$;

CREATE FUNCTION qk.is_visible(c qk.chunk, a qk.artifact, active text) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $$
    SELECT c.index_version = active AND a.status = 'active' AND a.access_scope = qk.visible_access_scope()
$$;

CREATE FUNCTION qk.kind_matches(a qk.artifact, source_kinds text[], artifact_kinds text[]) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $$
    SELECT (coalesce(cardinality(source_kinds), 0) = 0 OR a.source_kind = ANY (source_kinds))
       AND (coalesce(cardinality(artifact_kinds), 0) = 0 OR a.artifact_kind = ANY (artifact_kinds))
$$;

CREATE FUNCTION qk.search_vector(
    query vector(1024), top_n int, source_kinds text[] DEFAULT NULL, artifact_kinds text[] DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql STABLE
SET search_path = qk, public, extensions
SET hnsw.iterative_scan = relaxed_order
AS $$
DECLARE
    active text := qk.active_index_version();
    hits jsonb;
BEGIN
    IF active IS NULL THEN
        RETURN jsonb_build_object('active_index_version', NULL, 'hits', '[]'::jsonb);
    END IF;
    SELECT coalesce(jsonb_agg(qk.hit_json(t.c, t.a, t.hit_rank, 1 - t.distance) ORDER BY t.hit_rank), '[]'::jsonb)
    INTO hits
    FROM (
        SELECT r.c, r.a, r.distance, row_number() OVER (ORDER BY r.distance, (r.c).id) AS hit_rank
        FROM (
            SELECT c, a, e.vector <=> query AS distance
            FROM qk.chunk c
            JOIN qk.artifact a ON a.id = c.artifact_id
            JOIN qk.embedding e ON e.id = c.embedding_id
            WHERE qk.is_visible(c, a, active) AND qk.kind_matches(a, source_kinds, artifact_kinds)
            ORDER BY e.vector <=> query
            LIMIT least(greatest(top_n, 1), 50)
        ) r
    ) t;
    RETURN jsonb_build_object('active_index_version', active, 'hits', hits);
END
$$;

-- pgroonga_score는 PGroonga 인덱스를 쓸 때만 점수를 계산하므로 순차 스캔을 끈다.
CREATE FUNCTION qk.search_keyword(
    query text, top_n int, source_kinds text[] DEFAULT NULL, artifact_kinds text[] DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql STABLE
SET search_path = qk, public, extensions
SET enable_seqscan = off
AS $$
DECLARE
    active text := qk.active_index_version();
    hits jsonb;
BEGIN
    IF active IS NULL THEN
        RETURN jsonb_build_object('active_index_version', NULL, 'hits', '[]'::jsonb);
    END IF;
    IF query IS NULL OR btrim(query) = '' THEN
        RETURN jsonb_build_object('active_index_version', active, 'hits', '[]'::jsonb);
    END IF;
    SELECT coalesce(jsonb_agg(qk.hit_json(t.c, t.a, t.hit_rank, t.score) ORDER BY t.hit_rank), '[]'::jsonb)
    INTO hits
    FROM (
        SELECT r.c, r.a, r.score, row_number() OVER (ORDER BY r.score DESC, (r.c).id) AS hit_rank
        FROM (
            SELECT c, a, pgroonga_score(c.tableoid, c.ctid) AS score
            FROM qk.chunk c
            JOIN qk.artifact a ON a.id = c.artifact_id
            WHERE c.search_text &@~ pgroonga_query_escape(query)
              AND qk.is_visible(c, a, active) AND qk.kind_matches(a, source_kinds, artifact_kinds)
            ORDER BY score DESC, c.id
            LIMIT least(greatest(top_n, 1), 50)
        ) r
    ) t;
    RETURN jsonb_build_object('active_index_version', active, 'hits', hits);
END
$$;

-- 같은 자료·같은 인덱스 버전 안의 앞뒤 청크와 상위 절. 상위 절은 중심 청크의 제목 경로 접두(자기 절 포함)마다
-- 중심보다 앞선 첫 청크다. 중심 청크가 노출되지 않으면 NULL.
CREATE FUNCTION qk.chunk_neighbors(center_id bigint, before int, after int) RETURNS jsonb
LANGUAGE plpgsql STABLE
SET search_path = qk, public, extensions
AS $$
DECLARE
    active text := qk.active_index_version();
    center qk.chunk;
    owner qk.artifact;
BEGIN
    SELECT * INTO center FROM qk.chunk WHERE id = center_id;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;
    SELECT * INTO owner FROM qk.artifact WHERE id = center.artifact_id;
    IF active IS NULL OR NOT qk.is_visible(center, owner, active) THEN
        RETURN NULL;
    END IF;
    RETURN jsonb_build_object(
        'center', qk.hit_json(center, owner, 0, 0),
        'before', (
            SELECT coalesce(jsonb_agg(qk.hit_json(c, owner, 0, 0) ORDER BY c.ordinal), '[]'::jsonb)
            FROM qk.chunk c
            WHERE c.artifact_id = center.artifact_id AND c.index_version = center.index_version
              AND c.ordinal >= center.ordinal - greatest(before, 0) AND c.ordinal < center.ordinal
        ),
        'after', (
            SELECT coalesce(jsonb_agg(qk.hit_json(c, owner, 0, 0) ORDER BY c.ordinal), '[]'::jsonb)
            FROM qk.chunk c
            WHERE c.artifact_id = center.artifact_id AND c.index_version = center.index_version
              AND c.ordinal > center.ordinal AND c.ordinal <= center.ordinal + greatest(after, 0)
        ),
        'parents', (
            SELECT coalesce(jsonb_agg(qk.hit_json(p, owner, 0, 0) ORDER BY cardinality(p.heading_path)), '[]'::jsonb)
            FROM (
                SELECT DISTINCT ON (c.heading_path) c.*
                FROM qk.chunk c
                WHERE c.artifact_id = center.artifact_id AND c.index_version = center.index_version
                  AND c.ordinal < center.ordinal
                  AND cardinality(c.heading_path) BETWEEN 1 AND cardinality(center.heading_path)
                  AND c.heading_path = center.heading_path[1:cardinality(c.heading_path)]
                ORDER BY c.heading_path, c.ordinal
            ) p
        )
    );
END
$$;
