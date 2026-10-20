-- QK-EMB-001 임베딩 사용량 기록·일일 예산(data-model.md 2·3절, research R-08, R-13).
-- 외부 호출 한 번 = 행 하나. 텍스트 원문은 저장하지 않는다(FR-013). 하루 경계는 00:00 UTC다.
-- 예산 판정과 합산은 이 함수들 안에서만 한다. 색인 CLI와 Workers 질의 경로가 같은 규칙을 쓴다(FR-007, FR-016).

CREATE TABLE qk.embedding_usage (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    usage_day date GENERATED ALWAYS AS ((occurred_at AT TIME ZONE 'UTC')::date) STORED,
    purpose text NOT NULL CHECK (purpose IN ('index', 'query')),
    run_id text NOT NULL,
    model_version text NOT NULL,
    input_count int NOT NULL CHECK (input_count >= 0),
    input_bytes int NOT NULL CHECK (input_bytes >= 0),
    -- 작은 호출(0.01 Neurons 미만)도 합계에 남도록 소수 여섯째 자리까지 둔다(2026-10-20 사용자 결정).
    estimated_neurons numeric(14, 6) NOT NULL CHECK (estimated_neurons >= 0),
    neurons numeric(14, 6) CHECK (neurons >= 0),  -- 정산 전 NULL
    measured boolean,  -- 정산 전 NULL. 제공자 값이면 true, 추정이면 false(FR-014)
    state text NOT NULL CHECK (state IN ('reserved', 'settled')),
    outcome text CHECK (
        outcome IN ('ok', 'input_too_long', 'transient', 'provider_quota', 'bad_response', 'auth_config')
    ),
    CONSTRAINT embedding_usage_settled_complete
        CHECK (state <> 'settled' OR (neurons IS NOT NULL AND measured IS NOT NULL AND outcome IS NOT NULL)),
    -- 질의는 예약하지 않는다(FR-019).
    CONSTRAINT embedding_usage_query_settled CHECK (purpose <> 'query' OR state = 'settled')
);
CREATE INDEX embedding_usage_day_purpose ON qk.embedding_usage (usage_day, purpose);

-- 90일 지난 날의 합계(FR-025).
CREATE TABLE qk.embedding_usage_daily (
    usage_day date NOT NULL,
    purpose text NOT NULL CHECK (purpose IN ('index', 'query')),
    model_version text NOT NULL,
    neurons numeric(16, 6) NOT NULL CHECK (neurons >= 0),
    calls int NOT NULL CHECK (calls >= 0),
    estimated_calls int NOT NULL CHECK (estimated_calls >= 0),
    PRIMARY KEY (usage_day, purpose, model_version)
);

CREATE FUNCTION qk.embedding_utc_day() RETURNS date
LANGUAGE sql STABLE AS $$ SELECT (now() AT TIME ZONE 'UTC')::date $$;

-- 정산된 행은 실제 사용량, 예약만 된 행은 예상량으로 센다(research R-08 보수적 집계).
CREATE FUNCTION qk.embedding_amount(u qk.embedding_usage) RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN u.state = 'settled' THEN u.neurons ELSE u.estimated_neurons END
$$;

CREATE FUNCTION qk.embedding_used(day date, use_purpose text) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT coalesce(sum(qk.embedding_amount(u)), 0)
    FROM qk.embedding_usage u
    WHERE u.usage_day = day AND u.purpose = use_purpose
$$;

-- 색인용 요청 직전 예약(FR-018, FR-021). 그날 키의 잠금 안에서 합산·판정·삽입한다.
CREATE FUNCTION qk.embedding_reserve(
    p_run_id text,
    p_model_version text,
    p_input_count int,
    p_input_bytes int,
    p_estimated numeric,
    p_index_budget numeric
) RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    day date := qk.embedding_utc_day();
    used numeric;
    reservation bigint;
BEGIN
    PERFORM pg_advisory_xact_lock(7340003, day - date '2000-01-01');
    used := qk.embedding_used(day, 'index');
    IF used + p_estimated > p_index_budget THEN
        RETURN jsonb_build_object(
            'granted', false, 'reservation_id', NULL,
            'index_used', used, 'index_remaining', greatest(p_index_budget - used, 0)
        );
    END IF;
    INSERT INTO qk.embedding_usage (
        purpose, run_id, model_version, input_count, input_bytes, estimated_neurons, state
    ) VALUES ('index', p_run_id, p_model_version, p_input_count, p_input_bytes, p_estimated, 'reserved')
    RETURNING id INTO reservation;
    used := qk.embedding_used(day, 'index');
    RETURN jsonb_build_object(
        'granted', true, 'reservation_id', reservation,
        'index_used', used, 'index_remaining', greatest(p_index_budget - used, 0)
    );
END
$$;

-- 예약을 실제 값으로 바꾼다. 이미 정산된 행이면 아무것도 하지 않는다(재실행 안전).
CREATE FUNCTION qk.embedding_settle(
    p_reservation_id bigint, p_neurons numeric, p_measured boolean, p_outcome text
) RETURNS void
LANGUAGE sql AS $$
    UPDATE qk.embedding_usage
    SET neurons = p_neurons, measured = p_measured, outcome = p_outcome, state = 'settled'
    WHERE id = p_reservation_id AND state = 'reserved'
$$;

-- 질의용 호출 기록(FR-019). 예비분을 넘어도 막지 않고 결과로 알린다.
CREATE FUNCTION qk.embedding_record(
    p_run_id text,
    p_model_version text,
    p_input_count int,
    p_input_bytes int,
    p_estimated numeric,
    p_neurons numeric,
    p_measured boolean,
    p_outcome text,
    p_query_reserve numeric
) RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    used numeric;
BEGIN
    INSERT INTO qk.embedding_usage (
        purpose, run_id, model_version, input_count, input_bytes, estimated_neurons,
        neurons, measured, state, outcome
    ) VALUES (
        'query', p_run_id, p_model_version, p_input_count, p_input_bytes, p_estimated,
        p_neurons, p_measured, 'settled', p_outcome
    );
    used := qk.embedding_used(qk.embedding_utc_day(), 'query');
    RETURN jsonb_build_object('query_used', used, 'query_reserve_exceeded', used > p_query_reserve);
END
$$;

-- 하루 사용량 조회(FR-016). `p_day`를 비우면 오늘(UTC)이다.
CREATE FUNCTION qk.embedding_usage_today(
    p_index_budget numeric, p_query_reserve numeric, p_day date DEFAULT NULL
) RETURNS jsonb
LANGUAGE sql STABLE AS $$
    WITH d AS (SELECT coalesce(p_day, qk.embedding_utc_day()) AS day),
    s AS (
        SELECT
            coalesce(sum(qk.embedding_amount(u)), 0) AS total,
            coalesce(sum(qk.embedding_amount(u)) FILTER (WHERE u.purpose = 'index'), 0) AS index_used,
            coalesce(sum(qk.embedding_amount(u)) FILTER (WHERE u.purpose = 'query'), 0) AS query_used,
            coalesce(sum(qk.embedding_amount(u)) FILTER (WHERE u.state = 'reserved' OR NOT u.measured), 0) AS estimated
        FROM qk.embedding_usage u, d
        WHERE u.usage_day = d.day
    )
    SELECT jsonb_build_object(
        'usage_day', d.day,
        'total', s.total,
        'index_used', s.index_used,
        'query_used', s.query_used,
        'index_budget', p_index_budget,
        'query_reserve', p_query_reserve,
        'index_remaining', greatest(p_index_budget - s.index_used, 0),
        'estimated_share', CASE WHEN s.total > 0 THEN round(s.estimated / s.total, 4) ELSE 0 END
    )
    FROM d, s
$$;

-- 보관 기간이 지난 날을 날짜 단위로 일 합계에 옮기고 호출별 행을 지운다(FR-025, research R-13).
-- 함수 호출 하나가 트랜잭션 하나다. 두 번째 실행은 0건이다.
CREATE FUNCTION qk.embedding_usage_prune(retention_days int DEFAULT 90) RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    cutoff date;
    days int;
    deleted int;
BEGIN
    -- 오늘 기록을 지우면 그날 예산이 초기화된다. 1일 미만은 거부한다(FR-018, 리뷰 반영).
    IF retention_days IS NULL OR retention_days < 1 THEN
        RAISE EXCEPTION 'retention_days must be >= 1' USING ERRCODE = '22023';
    END IF;
    cutoff := qk.embedding_utc_day() - retention_days;
    INSERT INTO qk.embedding_usage_daily (usage_day, purpose, model_version, neurons, calls, estimated_calls)
    SELECT
        u.usage_day, u.purpose, u.model_version,
        sum(qk.embedding_amount(u)),
        count(*),
        count(*) FILTER (WHERE u.state = 'reserved' OR NOT u.measured)
    FROM qk.embedding_usage u
    WHERE u.usage_day < cutoff
    GROUP BY u.usage_day, u.purpose, u.model_version
    ON CONFLICT (usage_day, purpose, model_version) DO UPDATE
    SET neurons = EXCLUDED.neurons, calls = EXCLUDED.calls, estimated_calls = EXCLUDED.estimated_calls;

    SELECT count(DISTINCT usage_day) INTO days FROM qk.embedding_usage WHERE usage_day < cutoff;
    DELETE FROM qk.embedding_usage WHERE usage_day < cutoff;
    GET DIAGNOSTICS deleted = ROW_COUNT;
    RETURN jsonb_build_object('days_rolled_up', days, 'rows_deleted', deleted);
END
$$;
