-- QK-OBS-001: 색인과 독립된 질의 관측 저장소. 실행기가 이 파일 전체를 한 트랜잭션으로 적용한다.
CREATE TABLE qk.query_record (
    run_id text PRIMARY KEY CHECK (run_id ~ '^q-[0-9]{8}T[0-9]{6}-[0-9a-f]{8}$'),
    received_at timestamptz NOT NULL,
    questioner_id text CHECK (questioner_id ~ '^[0-9]{17,20}$'),
    private boolean NOT NULL,
    status text NOT NULL CHECK (status IN ('answered','cannot_confirm','retrieval_failed','generation_failed',
        'outgoing_blocked','timed_out','not_started','failed','undelivered','busy')),
    failure text,
    first_response_ms int NOT NULL CHECK (first_response_ms >= 0),
    total_ms int CHECK (total_ms >= 0),
    stage_ms jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(stage_ms) = 'object'
        AND NOT jsonb_path_exists(stage_ms, '$.* ? (@.type() != "number")')),
    calls jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(calls) = 'object'
        AND NOT jsonb_path_exists(calls, '$.* ? (@.type() != "number")')),
    retrieval jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(retrieval) = 'object'
        AND NOT jsonb_path_exists(retrieval, '$.* ? (@.type() != "number" && @.type() != "boolean")')),
    generation jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(generation) = 'object'
        AND NOT jsonb_path_exists(generation, '$.* ? (@.type() != "number" && @.type() != "boolean")')),
    input_tokens int CHECK (input_tokens >= 0), output_tokens int CHECK (output_tokens >= 0),
    context_chunk_ids bigint[] NOT NULL DEFAULT '{}', context_block_sizes int[] NOT NULL DEFAULT '{}',
    cited_blocks int[] NOT NULL DEFAULT '{}',
    index_version text, model_id text, prompt_version text,
    deliver_ms int CHECK (deliver_ms >= 0), deliver_calls int CHECK (deliver_calls >= 0),
    deliver_retries int CHECK (deliver_retries >= 0), deliver_failure text,
    consented boolean NOT NULL DEFAULT false, text_skipped boolean NOT NULL DEFAULT false
);
CREATE INDEX query_record_received ON qk.query_record(received_at);
CREATE TABLE qk.query_feedback (
    run_id text NOT NULL REFERENCES qk.query_record(run_id),
    rater_id text CHECK (rater_id ~ '^[0-9]{17,20}$'), value text NOT NULL CHECK (value IN ('up','down')),
    first_at timestamptz NOT NULL DEFAULT now(), last_at timestamptz NOT NULL DEFAULT now(),
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, UNIQUE (run_id, rater_id)
);
CREATE TABLE qk.query_text (
    run_id text PRIMARY KEY REFERENCES qk.query_record(run_id),
    question text NOT NULL CHECK (char_length(question) BETWEEN 1 AND 4000),
    consented_at timestamptz NOT NULL DEFAULT now(),
    consent_method text NOT NULL CHECK (consent_method = 'feedback_down')
);
CREATE TABLE qk.query_erasure_run (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, ran_at timestamptz NOT NULL DEFAULT now(),
    kind text NOT NULL CHECK (kind IN ('user','all_texts')),
    texts_deleted int NOT NULL, records_cleared int NOT NULL, feedback_cleared int NOT NULL
);
REVOKE ALL ON qk.query_record, qk.query_feedback, qk.query_text, qk.query_erasure_run FROM PUBLIC, qk_query;

CREATE FUNCTION qk.query_record_insert(p jsonb) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = qk, pg_temp AS $$
DECLARE
    clean jsonb := '{}'; nested jsonb; section text; k text; v jsonb; keys text[];
BEGIN
    -- 모르는 항목, 형식이 틀린 선택 항목은 버린다. 필수 항목 오류는 표 제약으로 거부한다.
    FOREACH k IN ARRAY ARRAY['run_id','received_at','questioner_id','status'] LOOP
        IF jsonb_typeof(p->k) = 'string' THEN clean := clean || jsonb_build_object(k,p->k); END IF;
    END LOOP;
    IF jsonb_typeof(p->'private') = 'boolean' THEN clean := clean || jsonb_build_object('private',p->'private'); END IF;
    FOREACH k IN ARRAY ARRAY['failure','index_version','model_id','prompt_version'] LOOP
        IF jsonb_typeof(p->k) = 'string' AND p->>k ~ '^[A-Za-z0-9@/._:+-]{1,64}$' THEN
            clean := clean || jsonb_build_object(k,p->k);
        END IF;
    END LOOP;
    FOREACH k IN ARRAY ARRAY['first_response_ms','input_tokens','output_tokens'] LOOP
        IF jsonb_typeof(p->k) = 'number' AND p->>k ~ '^[0-9]{1,9}$' THEN
            clean := clean || jsonb_build_object(k,p->k);
        END IF;
    END LOOP;
    FOREACH section IN ARRAY ARRAY['stage_ms','calls','retrieval','generation'] LOOP
        keys := CASE section WHEN 'stage_ms' THEN ARRAY['retrieve','generate']
            WHEN 'calls' THEN ARRAY['retrieve','generate']
            WHEN 'retrieval' THEN ARRAY['external_calls','neurons','estimated_neurons','measured']
            ELSE ARRAY['generation_calls','attempts','neurons','measured'] END;
        nested := '{}';
        FOREACH k IN ARRAY keys LOOP
            v := p->section->k;
            IF (k = 'measured' AND jsonb_typeof(v) = 'boolean') OR
               (k IN ('neurons','estimated_neurons') AND jsonb_typeof(v) = 'number' AND (v::text)::numeric >= 0) OR
               (k NOT IN ('measured','neurons','estimated_neurons') AND jsonb_typeof(v) = 'number'
                AND v::text ~ '^[0-9]{1,9}$') THEN
                nested := nested || jsonb_build_object(k,v);
            END IF;
        END LOOP;
        clean := clean || jsonb_build_object(section,nested);
    END LOOP;
    FOREACH k IN ARRAY ARRAY['context_chunk_ids','context_block_sizes','cited_blocks'] LOOP
        IF jsonb_typeof(p->k) = 'array' THEN
            SELECT coalesce(jsonb_agg(value ORDER BY ord), '[]') INTO v
            FROM jsonb_array_elements(p->k) WITH ORDINALITY x(value,ord)
            WHERE jsonb_typeof(value) = 'number' AND value::text ~ '^[0-9]{1,18}$'
              AND (k = 'context_chunk_ids' OR (value::text)::numeric <= 2147483647);
            clean := clean || jsonb_build_object(k,v);
        ELSE clean := clean || jsonb_build_object(k,'[]'::jsonb);
        END IF;
    END LOOP;
    INSERT INTO qk.query_record (
        run_id,received_at,questioner_id,private,status,failure,first_response_ms,stage_ms,calls,retrieval,generation,
        input_tokens,output_tokens,context_chunk_ids,context_block_sizes,cited_blocks,index_version,model_id,prompt_version
    ) SELECT r.run_id,r.received_at,r.questioner_id,r.private,r.status,r.failure,coalesce(r.first_response_ms,0),
        r.stage_ms,r.calls,r.retrieval,r.generation,r.input_tokens,r.output_tokens,r.context_chunk_ids,
        r.context_block_sizes,r.cited_blocks,r.index_version,r.model_id,r.prompt_version
      FROM jsonb_populate_record(NULL::qk.query_record,clean) r ON CONFLICT (run_id) DO NOTHING;
END $$;

CREATE FUNCTION qk.query_record_delivered(run text, p jsonb) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = qk, pg_temp AS $$
DECLARE clean jsonb := '{}'; k text;
BEGIN
    FOREACH k IN ARRAY ARRAY['total_ms','deliver_ms','deliver_calls','deliver_retries'] LOOP
        IF jsonb_typeof(p->k) = 'number' AND p->>k ~ '^[0-9]{1,9}$' THEN
            clean := clean || jsonb_build_object(k,p->k);
        END IF;
    END LOOP;
    UPDATE qk.query_record SET
        status = CASE WHEN p->>'final_status' = 'undelivered' THEN 'undelivered' ELSE status END,
        total_ms = (clean->>'total_ms')::int, deliver_ms = (clean->>'deliver_ms')::int,
        deliver_calls = (clean->>'deliver_calls')::int, deliver_retries = (clean->>'deliver_retries')::int,
        deliver_failure = CASE WHEN jsonb_typeof(p->'deliver_failure') = 'string'
            AND p->>'deliver_failure' ~ '^[A-Za-z0-9@/._:+-]{1,64}$' THEN p->>'deliver_failure' END
    WHERE run_id = run;
END $$;

CREATE FUNCTION qk.query_feedback_set(run text, rater text, rating text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = qk, pg_temp AS $$
BEGIN
    PERFORM 1 FROM qk.query_record WHERE run_id = run FOR KEY SHARE;
    IF NOT FOUND THEN RETURN 'missing'; END IF;
    IF rater IS NULL THEN RAISE EXCEPTION 'invalid_rater' USING ERRCODE = '23514'; END IF;
    INSERT INTO qk.query_feedback(run_id,rater_id,value) VALUES(run,rater,rating)
    ON CONFLICT(run_id,rater_id) DO UPDATE SET value = excluded.value, last_at = now();
    RETURN 'stored';
END $$;

CREATE FUNCTION qk.query_text_store(run text, questioner text, body text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = qk, pg_temp AS $$
DECLARE owner_id text;
BEGIN
    SELECT questioner_id INTO owner_id FROM qk.query_record WHERE run_id = run FOR UPDATE;
    IF NOT FOUND THEN RETURN 'missing'; END IF;
    IF owner_id IS NULL OR questioner IS NULL OR owner_id <> questioner THEN RETURN 'not_questioner'; END IF;
    IF EXISTS(SELECT 1 FROM qk.query_text WHERE run_id = run) THEN RETURN 'exists'; END IF;
    INSERT INTO qk.query_text(run_id,question,consent_method) VALUES(run,body,'feedback_down');
    UPDATE qk.query_record SET consented = true WHERE run_id = run;
    RETURN 'stored';
END $$;

CREATE FUNCTION qk.query_text_skip(run text) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = qk, pg_temp AS $$
    UPDATE qk.query_record SET text_skipped = true WHERE run_id = run
$$;

CREATE FUNCTION qk.query_text_status(run text, questioner text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = qk, pg_temp AS $$
DECLARE owner_id text;
BEGIN
    SELECT questioner_id INTO owner_id FROM qk.query_record WHERE run_id = run;
    IF NOT FOUND THEN RETURN 'missing'; END IF;
    IF owner_id IS NULL OR questioner IS NULL OR owner_id <> questioner THEN RETURN 'not_questioner'; END IF;
    IF EXISTS(SELECT 1 FROM qk.query_text WHERE run_id = run) THEN RETURN 'stored'; END IF;
    RETURN 'none';
END $$;

CREATE FUNCTION qk.sources_summary() RETURNS jsonb
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = qk, pg_temp AS $$
    SELECT jsonb_build_object('index_version',i.id,'activated_at',i.activated_at,'sources',coalesce((
        SELECT jsonb_agg(jsonb_build_object('name',s.name,'kind',s.kind,'documents',s.documents,
            'last_seen_at',s.last_seen_at) ORDER BY s.name,s.kind) FROM (
            SELECT coalesce(a.source_name,a.source_kind) AS name, a.source_kind AS kind,
                count(*) AS documents, max(coalesce(a.last_seen_at,a.collected_at)) AS last_seen_at
            FROM qk.artifact a WHERE EXISTS(
                SELECT 1 FROM qk.chunk c WHERE c.artifact_id=a.id AND qk.is_visible(c,a,i.id))
            GROUP BY coalesce(a.source_name,a.source_kind), a.source_kind
        ) s), '[]'::jsonb)) FROM (SELECT (SELECT id FROM qk.index_version WHERE status='active') AS id,
            (SELECT activated_at FROM qk.index_version WHERE status='active') AS activated_at) i
$$;

REVOKE ALL ON FUNCTION qk.query_record_insert(jsonb),qk.query_record_delivered(text,jsonb),
    qk.query_feedback_set(text,text,text),qk.query_text_store(text,text,text),qk.query_text_skip(text),
    qk.query_text_status(text,text),qk.sources_summary() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION qk.query_record_insert(jsonb),qk.query_record_delivered(text,jsonb),
    qk.query_feedback_set(text,text,text),qk.query_text_store(text,text,text),qk.query_text_skip(text),
    qk.query_text_status(text,text),qk.sources_summary() TO qk_query;
