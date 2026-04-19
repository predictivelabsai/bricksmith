-- Bricksmith RAG schema. Idempotent. pgvector-backed retrieval over CRE
-- documents (leases, zoning memos, environmental Phase I, property condition,
-- title commitments, market reports).

CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS bricksmith_rag;

CREATE TABLE IF NOT EXISTS bricksmith_rag.documents (
    id           BIGSERIAL PRIMARY KEY,
    property_id  BIGINT,              -- soft reference to bricksmith.properties(id)
    doc_type     TEXT NOT NULL,       -- lease | zoning | environmental | pcr | title | market | misc
    title        TEXT NOT NULL,
    source_path  TEXT,
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS documents_property_idx ON bricksmith_rag.documents(property_id);
CREATE INDEX IF NOT EXISTS documents_type_idx     ON bricksmith_rag.documents(doc_type);

CREATE TABLE IF NOT EXISTS bricksmith_rag.chunks (
    id           BIGSERIAL PRIMARY KEY,
    document_id  BIGINT NOT NULL REFERENCES bricksmith_rag.documents(id) ON DELETE CASCADE,
    ord          INTEGER NOT NULL,
    text         TEXT NOT NULL,
    token_count  INTEGER,
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (document_id, ord)
);
CREATE INDEX IF NOT EXISTS chunks_document_idx ON bricksmith_rag.chunks(document_id);

-- Embedding dim parameterized at migration time via {{EMBEDDING_DIM}} —
-- db/migrate.py substitutes the value from EMBEDDING_DIM env var before
-- applying. If you change EMBEDDING_DIM, run `python -m db.migrate --drop`
-- (destroys RAG tables) and re-index.
CREATE TABLE IF NOT EXISTS bricksmith_rag.embeddings (
    chunk_id   BIGINT PRIMARY KEY REFERENCES bricksmith_rag.chunks(id) ON DELETE CASCADE,
    embedding  vector({{EMBEDDING_DIM}}) NOT NULL
);

-- ivfflat index is intentionally created AFTER bulk seeding (see
-- `rag.indexer.build_ann_index()`). ivfflat assigns rows to clusters when
-- it's built, so creating it before the table is populated gives empty or
-- near-empty cells and wrong results. For synthetic-scale (<10k chunks) a
-- sequential scan is fine; for larger corpora call build_ann_index() once
-- the table is loaded.

CREATE TABLE IF NOT EXISTS bricksmith_rag.rag_queries (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT,
    session_id  BIGINT,
    query       TEXT NOT NULL,
    top_k       INTEGER,
    filters     JSONB,
    latency_ms  INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
