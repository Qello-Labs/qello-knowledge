-- 질의 역할은 로그인 없이 만든다. 운영 LOGIN·암호는 사람이 별도로 설정한다.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qk_query') THEN
        CREATE ROLE qk_query NOLOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA qk TO qk_query;
GRANT SELECT ON TABLE qk.index_version, qk.artifact, qk.chunk, qk.embedding,
    qk.embedding_usage, qk.embedding_usage_daily,
    qk.generation_usage, qk.generation_usage_daily TO qk_query;
GRANT INSERT ON TABLE qk.embedding_usage, qk.generation_usage TO qk_query;
GRANT USAGE ON SEQUENCE qk.embedding_usage_id_seq, qk.generation_usage_id_seq TO qk_query;

GRANT EXECUTE ON FUNCTION
    qk.active_index_version(), qk.visible_access_scope(),
    qk.is_visible(qk.chunk, qk.artifact, text),
    qk.kind_matches(qk.artifact, text[], text[]),
    qk.hit_json(qk.chunk, qk.artifact, bigint, double precision),
    qk.search_vector(vector, integer, text[], text[]),
    qk.search_keyword(text, integer, text[], text[]),
    qk.search_keyword_terms(text[], integer, text[], text[]),
    qk.chunk_neighbors(bigint, integer, integer),
    qk.context_item_json(qk.chunk, qk.artifact),
    qk.chunk_context(bigint[], integer, integer),
    qk.embedding_utc_day(), qk.embedding_amount(qk.embedding_usage),
    qk.embedding_used(date, text),
    qk.embedding_record(text, text, integer, integer, numeric, numeric, boolean, text, numeric),
    qk.embedding_usage_today(numeric, numeric, date),
    qk.generation_record(text, text, text, smallint, integer, integer, integer, numeric, boolean, text, boolean, integer),
    qk.generation_usage_today(integer, date)
TO qk_query;

-- SECURITY INVOKER 함수의 PUBLIC EXECUTE는 그대로 둔다.
-- SELECT+INSERT만 쓰는 embedding_reserve도 이 INSERT 정책으로 차단한다.
-- 소유자 색인 경로를 유지하기 위해 FORCE는 쓰지 않는다.
ALTER TABLE qk.embedding_usage ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policy
        WHERE polrelid = 'qk.embedding_usage'::regclass AND polname = 'query_usage_select'
    ) THEN
        CREATE POLICY query_usage_select ON qk.embedding_usage
            FOR SELECT TO qk_query USING (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policy
        WHERE polrelid = 'qk.embedding_usage'::regclass AND polname = 'query_usage_insert'
    ) THEN
        CREATE POLICY query_usage_insert ON qk.embedding_usage
            FOR INSERT TO qk_query WITH CHECK (purpose = 'query');
    END IF;
END
$$;
