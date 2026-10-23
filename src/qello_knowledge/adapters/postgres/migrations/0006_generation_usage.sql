-- QK-GEN-001 생성 사용량(data-model 6절, research R-06). 테이블·함수를 더하기만 한다. 0001~0005의 객체는 바꾸지 않는다.
-- 질문·답변·프롬프트 원문 열은 없다(spec FR-012). 하루 경계는 UTC다(QK-EMB-001과 같음).

CREATE TABLE qk.generation_usage (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    purpose text NOT NULL DEFAULT 'generate' CHECK (purpose = 'generate'),
    occurred_at timestamptz NOT NULL DEFAULT now(),
    usage_day date GENERATED ALWAYS AS ((occurred_at AT TIME ZONE 'UTC')::date) STORED,
    run_id text NOT NULL,
    model_id text NOT NULL,
    prompt_version text NOT NULL,
    attempt smallint NOT NULL CHECK (attempt IN (1, 2)),
    input_tokens int CHECK (input_tokens >= 0),
    output_tokens int CHECK (output_tokens >= 0),
    estimated_input_tokens int NOT NULL CHECK (estimated_input_tokens >= 0),
    neurons numeric(14, 6) NOT NULL CHECK (neurons >= 0),
    measured boolean NOT NULL,
    truncated boolean NOT NULL DEFAULT false,
    outcome text NOT NULL CHECK (
        outcome IN ('ok', 'transient', 'timeout', 'provider_quota', 'auth_config', 'bad_response', 'input_too_long')
    )
);
CREATE INDEX generation_usage_day ON qk.generation_usage (usage_day);

-- 90일 지난 날의 합계(spec FR-020, QK-EMB-001 FR-025와 같은 보관 규칙).
CREATE TABLE qk.generation_usage_daily (
    usage_day date NOT NULL,
    model_id text NOT NULL,
    neurons numeric(16, 6) NOT NULL CHECK (neurons >= 0),
    calls int NOT NULL CHECK (calls >= 0),
    estimated_calls int NOT NULL CHECK (estimated_calls >= 0),
    PRIMARY KEY (usage_day, model_id)
);

-- 오늘(UTC) 질의응답 사용량. 질의 임베딩·색인 사용량은 0003의 qk.embedding_used를 읽기만 한다.
-- `qk-index usage`의 query_used(질의 임베딩만)와 answer_total은 다를 수 있다(research R-06 남는 차이).
CREATE FUNCTION qk.generation_usage_today(p_query_reserve int, p_day date DEFAULT NULL) RETURNS jsonb
LANGUAGE sql STABLE AS $$
    WITH d AS (SELECT coalesce(p_day, qk.embedding_utc_day()) AS day),
    s AS (
        SELECT
            (SELECT coalesce(sum(g.neurons), 0) FROM qk.generation_usage g WHERE g.usage_day = d.day) AS generation_used,
            qk.embedding_used(d.day, 'query') AS query_embedding_used,
            qk.embedding_used(d.day, 'index') AS index_used
        FROM d
    )
    SELECT jsonb_build_object(
        'usage_day', d.day,
        'generation_used', s.generation_used,
        'query_embedding_used', s.query_embedding_used,
        'answer_total', s.generation_used + s.query_embedding_used,
        'index_used', s.index_used,
        'day_total', s.generation_used + s.query_embedding_used + s.index_used,
        'query_reserve', p_query_reserve,
        'query_reserve_exceeded', s.generation_used + s.query_embedding_used > p_query_reserve
    )
    FROM d, s
$$;

-- 생성 시도 하나를 기록하고 오늘 질의응답 사용량을 돌려준다. 예비분을 넘어도 막지 않는다(spec FR-021).
CREATE FUNCTION qk.generation_record(
    p_run_id text,
    p_model_id text,
    p_prompt_version text,
    p_attempt smallint,
    p_input_tokens int,
    p_output_tokens int,
    p_estimated_input_tokens int,
    p_neurons numeric,
    p_measured boolean,
    p_outcome text,
    p_truncated boolean,
    p_query_reserve int
) RETURNS jsonb
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO qk.generation_usage (
        run_id, model_id, prompt_version, attempt, input_tokens, output_tokens, estimated_input_tokens,
        neurons, measured, truncated, outcome
    ) VALUES (
        p_run_id, p_model_id, p_prompt_version, p_attempt, p_input_tokens, p_output_tokens, p_estimated_input_tokens,
        p_neurons, p_measured, p_truncated, p_outcome
    );
    RETURN qk.generation_usage_today(p_query_reserve);
END
$$;

-- 보관 기간이 지난 날을 날짜·모델 단위 합계로 옮기고 시도별 행을 지운다. 두 번째 실행은 0건이다.
CREATE FUNCTION qk.generation_usage_prune(retention_days int DEFAULT 90) RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    cutoff date;
    days int;
    deleted int;
BEGIN
    IF retention_days IS NULL OR retention_days < 1 THEN
        RAISE EXCEPTION 'retention_days must be >= 1' USING ERRCODE = '22023';
    END IF;
    cutoff := qk.embedding_utc_day() - retention_days;
    INSERT INTO qk.generation_usage_daily (usage_day, model_id, neurons, calls, estimated_calls)
    SELECT g.usage_day, g.model_id, sum(g.neurons), count(*), count(*) FILTER (WHERE NOT g.measured)
    FROM qk.generation_usage g
    WHERE g.usage_day < cutoff
    GROUP BY g.usage_day, g.model_id
    ON CONFLICT (usage_day, model_id) DO UPDATE
    SET neurons = EXCLUDED.neurons, calls = EXCLUDED.calls, estimated_calls = EXCLUDED.estimated_calls;

    SELECT count(DISTINCT usage_day) INTO days FROM qk.generation_usage WHERE usage_day < cutoff;
    DELETE FROM qk.generation_usage WHERE usage_day < cutoff;
    GET DIAGNOSTICS deleted = ROW_COUNT;
    RETURN jsonb_build_object('days_rolled_up', days, 'rows_deleted', deleted);
END
$$;
