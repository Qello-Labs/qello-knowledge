-- QK-SYN-001: 더하기만 하는 동기화 상태와 실행 기록. 청크 스키마는 바꾸지 않는다.
ALTER TABLE qk.artifact
    ADD COLUMN source_name text,
    ADD COLUMN location text,
    ADD COLUMN chunk_input_hash text,
    ADD COLUMN processed_chunking_version text,
    ADD COLUMN processed_index_version text REFERENCES qk.index_version(id),
    ADD COLUMN processed_outcome text CHECK (processed_outcome IN ('chunked', 'empty')),
    ADD COLUMN last_seen_version text,
    ADD COLUMN last_seen_at timestamptz,
    ADD COLUMN takedown_reason text CHECK (takedown_reason IN
        ('security_path', 'security_secret', 'security_access', 'config_excluded', 'source_missing', 'not_target', 'source_disabled')),
    ADD COLUMN takedown_at timestamptz,
    ADD COLUMN purge_pending text[] NOT NULL DEFAULT '{}',
    ADD COLUMN purge_reason text CHECK (purge_reason IN ('security_path', 'security_secret', 'security_access', 'config_excluded')),
    ADD CONSTRAINT artifact_purge_reason_matches_pending CHECK ((purge_pending <> '{}') = (purge_reason IS NOT NULL));

CREATE TABLE qk.sync_source (
    source_name text PRIMARY KEY,
    source_kind text NOT NULL UNIQUE,
    scope_key text NOT NULL,
    origin_id text,
    origin_name text,
    registered_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE qk.sync_run (
    run_id text PRIMARY KEY,
    trigger text NOT NULL CHECK (trigger IN ('manual', 'schedule')),
    target text NOT NULL CHECK (target IN ('local', 'remote')),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    rules_version text NOT NULL,
    chunking_version text NOT NULL,
    index_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('running', 'succeeded', 'partial', 'stopped', 'unfinished')),
    summary jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE qk.sync_run_source (
    run_id text NOT NULL REFERENCES qk.sync_run(run_id) ON DELETE CASCADE,
    source_name text NOT NULL,
    status text NOT NULL CHECK (status IN ('running', 'succeeded', 'partial', 'stopped', 'unfinished')),
    origin_version text,
    listing_complete boolean,
    stop_reason text,
    holds text[] NOT NULL DEFAULT '{}',
    retry_at timestamptz,
    summary jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (run_id, source_name)
);
CREATE TABLE qk.sync_document_result (
    run_id text NOT NULL REFERENCES qk.sync_run(run_id) ON DELETE CASCADE,
    doc_key text NOT NULL,
    action text NOT NULL CHECK (action IN ('PROCESS','UNCHANGED','TAKE_DOWN','PURGE','FAIL','HOLD','SKIP')),
    source_name text NOT NULL,
    doc_display text NOT NULL,
    artifact_id bigint,
    outcome text NOT NULL CHECK (outcome IN ('PROCESSED','PROCESSED_EMPTY','UNCHANGED','TAKEN_DOWN','PURGED','FAILED','HELD','SKIPPED')),
    change_reason text,
    stage text CHECK (stage IN ('fetch','screen','chunk','embed','store')),
    failure text,
    takedown_reason text,
    rule text,
    lines int[],
    PRIMARY KEY (run_id, doc_key, action)
);
CREATE INDEX sync_document_result_by_source ON qk.sync_document_result(source_name, doc_key, outcome);
