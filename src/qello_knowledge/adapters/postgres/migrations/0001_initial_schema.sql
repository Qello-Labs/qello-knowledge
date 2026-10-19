-- QK-STO-001 초기 스키마(data-model.md). 요구사항은 가능한 한 DB 제약으로 강제한다(research R-02).
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgroonga;

CREATE SCHEMA IF NOT EXISTS qk;

-- 적용 기록 테이블(qk.schema_migration)은 실행기가 먼저 만든다(migrate.py BOOTSTRAP).

CREATE TABLE qk.index_version (
    id text PRIMARY KEY,
    embedding_model text NOT NULL,
    dimension int NOT NULL CHECK (dimension = 1024),
    chunking_version text NOT NULL,
    metadata_schema_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('ready', 'active', 'archived')),
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz
);
-- 활성 인덱스 버전은 하나 이하다(FR-005, C-07).
CREATE UNIQUE INDEX index_version_one_active ON qk.index_version ((true)) WHERE status = 'active';

CREATE TABLE qk.artifact (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_kind text NOT NULL,
    source_id text NOT NULL,
    source_url text NOT NULL CHECK (btrim(source_url) <> ''),
    source_version text NOT NULL CHECK (btrim(source_version) <> ''),
    source_modified_at timestamptz,
    collected_at timestamptz NOT NULL,
    content_hash text NOT NULL,
    chunk_set_hash text,
    artifact_kind text NOT NULL,
    title text,
    access_scope text,  -- NULL은 미확인. 검색에서 뺀다(research R-05)
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_kind, source_id)
);

CREATE TABLE qk.embedding (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    input_hash text NOT NULL,
    model_version text NOT NULL,
    vector vector(1024) NOT NULL,  -- 다른 차원은 DB가 거부한다(FR-004, ADR-002)
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (input_hash, model_version)
);
CREATE INDEX embedding_vector_hnsw ON qk.embedding USING hnsw (vector vector_cosine_ops);

CREATE TABLE qk.chunk (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    artifact_id bigint NOT NULL REFERENCES qk.artifact (id),
    index_version text NOT NULL REFERENCES qk.index_version (id),
    source_version text NOT NULL CHECK (btrim(source_version) <> ''),
    locator jsonb NOT NULL CHECK (jsonb_typeof(locator) = 'object' AND locator <> '{}'::jsonb),
    heading_path text[] NOT NULL DEFAULT '{}',
    ordinal int NOT NULL CHECK (ordinal >= 0),
    body text NOT NULL,
    search_text text NOT NULL,
    chunking_version text NOT NULL CHECK (btrim(chunking_version) <> ''),
    embedding_id bigint REFERENCES qk.embedding (id),
    UNIQUE (artifact_id, index_version, ordinal)
);
-- TokenBigramSplitSymbol: 백틱 등 기호에 붙은 식별자(`/health`)도 찾는다. 영문 부분 일치는 ADR-010에서 정한다(research R-03).
CREATE INDEX chunk_search_text_pgroonga ON qk.chunk USING pgroonga (search_text)
    WITH (tokenizer = 'TokenBigramSplitSymbol');
CREATE INDEX chunk_embedding ON qk.chunk (embedding_id);
