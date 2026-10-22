-- QK-RET-001 검색 질의(research R-03 결정 2, R-06, data-model 4절). 함수만 더한다. 기존 함수·테이블은 바꾸지 않는다.
-- 노출 조건은 0002의 qk.is_visible·qk.kind_matches를 그대로 쓴다(spec FR-007, C-14).

-- 낱말 배열 키워드 검색. 서로 다른 맞은 낱말 수 → 낱말을 OR로 이은 질의 한 번의 점수 → 청크 식별자 순.
-- pgroonga_score는 낱말이 나온 횟수라 1차 정렬 키로 쓰지 않는다. 일치 확장은 끈다(결과가 다른 청크·VACUUM 상태와 무관하다).
CREATE FUNCTION qk.search_keyword_terms(
    terms text[], top_n int, source_kinds text[] DEFAULT NULL, artifact_kinds text[] DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql STABLE
SET search_path = qk, public, extensions
SET enable_seqscan = off
SET pgroonga.match_escalation_threshold = -1
SET plan_cache_mode = force_custom_plan
AS $$
DECLARE
    active text := qk.active_index_version();
    used text[] := ARRAY(
        SELECT u.term FROM unnest(coalesce(terms, '{}'::text[])) WITH ORDINALITY u(term, ord)
        WHERE u.ord <= 16 AND btrim(u.term) <> '' ORDER BY u.ord
    );
    or_query text := array_to_string(ARRAY(SELECT pgroonga_query_escape(t) FROM unnest(used) t), ' OR ');
    hits jsonb;
BEGIN
    IF active IS NULL THEN
        RETURN jsonb_build_object('active_index_version', NULL, 'hits', '[]'::jsonb);
    END IF;
    IF cardinality(used) = 0 THEN
        RETURN jsonb_build_object('active_index_version', active, 'hits', '[]'::jsonb);
    END IF;
    WITH matched AS (
        SELECT c.id, count(DISTINCT q.ord) AS n
        FROM unnest(used) WITH ORDINALITY q(term, ord)
        JOIN qk.chunk c ON c.search_text &@~ pgroonga_query_escape(q.term)
        JOIN qk.artifact a ON a.id = c.artifact_id
        WHERE qk.is_visible(c, a, active) AND qk.kind_matches(a, source_kinds, artifact_kinds)
        GROUP BY c.id
    ), scored AS (
        SELECT c.id, pgroonga_score(c.tableoid, c.ctid) AS score
        FROM qk.chunk c
        WHERE c.search_text &@~ or_query
    )
    SELECT coalesce(
        jsonb_agg(qk.hit_json(t.c, t.a, t.hit_rank, t.score) || jsonb_build_object('matched_terms', t.n) ORDER BY t.hit_rank),
        '[]'::jsonb
    )
    INTO hits
    FROM (
        SELECT r.c, r.a, r.n, r.score, r.hit_rank
        FROM (
            SELECT c, a, m.n, coalesce(s.score, 0) AS score,
                   row_number() OVER (ORDER BY m.n DESC, coalesce(s.score, 0) DESC, c.id) AS hit_rank
            FROM matched m
            JOIN qk.chunk c ON c.id = m.id
            JOIN qk.artifact a ON a.id = c.artifact_id
            LEFT JOIN scored s ON s.id = m.id
        ) r
        ORDER BY r.hit_rank
        LIMIT least(greatest(top_n, 1), 50)
    ) t;
    RETURN jsonb_build_object('active_index_version', active, 'hits', hits);
END
$$;

CREATE FUNCTION qk.context_item_json(c qk.chunk, a qk.artifact) RETURNS jsonb
LANGUAGE sql IMMUTABLE AS $$
    SELECT qk.hit_json(c, a, 0, 0) || jsonb_build_object('ordinal', c.ordinal, 'artifact_id', c.artifact_id)
$$;

-- 중심 청크(앞 20개)를 다시 확인하고 같은 자료·같은 인덱스 버전의 앞뒤 청크(각 0~3)와 절 첫 청크를 한 번에 돌려준다.
-- 절 첫 청크: 중심보다 앞서고 제목 경로가 다른 마지막 청크 바로 다음 청크(없으면 자료의 첫 청크). 그것이 중심이면 null.
CREATE FUNCTION qk.chunk_context(center_ids bigint[], before int, after int) RETURNS jsonb
LANGUAGE plpgsql STABLE
SET search_path = qk, public, extensions
AS $$
DECLARE
    active text := qk.active_index_version();
    n_before int := least(greatest(coalesce(before, 0), 0), 3);
    n_after int := least(greatest(coalesce(after, 0), 0), 3);
    ids bigint[] := ARRAY(
        SELECT u.id FROM unnest(coalesce(center_ids, '{}'::bigint[])) WITH ORDINALITY u(id, ord)
        WHERE u.ord <= 20 ORDER BY u.ord
    );
    items jsonb;
BEGIN
    IF active IS NULL THEN
        RETURN jsonb_build_object('active_index_version', NULL, 'items', '[]'::jsonb);
    END IF;
    SELECT coalesce(jsonb_agg(jsonb_build_object(
        'center', qk.context_item_json(c, a),
        'section_first', (
            SELECT qk.context_item_json(s, a)
            FROM qk.chunk s
            WHERE s.artifact_id = c.artifact_id AND s.index_version = c.index_version AND s.ordinal < c.ordinal
              AND s.ordinal = coalesce(
                  (SELECT max(p.ordinal) + 1 FROM qk.chunk p
                   WHERE p.artifact_id = c.artifact_id AND p.index_version = c.index_version
                     AND p.ordinal < c.ordinal AND p.heading_path <> c.heading_path),
                  (SELECT min(p.ordinal) FROM qk.chunk p
                   WHERE p.artifact_id = c.artifact_id AND p.index_version = c.index_version)
              )
        ),
        'before', (
            SELECT coalesce(jsonb_agg(qk.context_item_json(n, a) ORDER BY n.ordinal), '[]'::jsonb)
            FROM qk.chunk n
            WHERE n.artifact_id = c.artifact_id AND n.index_version = c.index_version
              AND n.ordinal >= c.ordinal - n_before AND n.ordinal < c.ordinal
        ),
        'after', (
            SELECT coalesce(jsonb_agg(qk.context_item_json(n, a) ORDER BY n.ordinal), '[]'::jsonb)
            FROM qk.chunk n
            WHERE n.artifact_id = c.artifact_id AND n.index_version = c.index_version
              AND n.ordinal > c.ordinal AND n.ordinal <= c.ordinal + n_after
        )
    ) ORDER BY u.ord), '[]'::jsonb)
    INTO items
    FROM unnest(ids) WITH ORDINALITY u(id, ord)
    JOIN qk.chunk c ON c.id = u.id
    JOIN qk.artifact a ON a.id = c.artifact_id
    WHERE qk.is_visible(c, a, active);
    RETURN jsonb_build_object('active_index_version', active, 'items', items);
END
$$;
