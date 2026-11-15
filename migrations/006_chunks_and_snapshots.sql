-- migrations/006_chunks_and_snapshots.sql
-- Foundation Locks 5, 6, 7 & 8: Schema extensions for deterministic text/table chunks,
-- multi-tenant Row-Level Security, and immutable retrieval snapshots.

-- 1. Evolve chunks table from initial skeleton
ALTER TABLE chunks DROP CONSTRAINT IF EXISTS chunks_doc_id_fkey;
ALTER TABLE chunks DROP CONSTRAINT IF EXISTS uq_chunk_doc_idx;
ALTER TABLE chunks ALTER COLUMN doc_id DROP NOT NULL;

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS chunk_kind VARCHAR(16) NOT NULL DEFAULT 'text' CHECK (chunk_kind IN ('text', 'table'));
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS company_id VARCHAR(16);
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS filing_id VARCHAR(64);
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS doc_type VARCHAR(32);
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS fiscal_year INT;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS fiscal_quarter INT;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS section VARCHAR(128);
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS authority_rank INT NOT NULL DEFAULT 1 CHECK (authority_rank BETWEEN 1 AND 4);
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS trust_level VARCHAR(16) NOT NULL DEFAULT 'trusted' CHECK (trust_level IN ('trusted', 'untrusted', 'quarantined'));
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS quarantined BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS risk_flags TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS chunk_text TEXT;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS chunker_version VARCHAR(32) NOT NULL DEFAULT 'v1.0.0';
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(64) REFERENCES tenants(tenant_id) ON DELETE CASCADE;

-- 2. Indexes for retrieval performance and filtering
CREATE INDEX IF NOT EXISTS idx_chunks_company ON chunks(company_id);
CREATE INDEX IF NOT EXISTS idx_chunks_kind ON chunks(chunk_kind);
CREATE INDEX IF NOT EXISTS idx_chunks_tenant ON chunks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_chunks_quarantined ON chunks(quarantined);
CREATE INDEX IF NOT EXISTS idx_chunks_authority ON chunks(authority_rank);
CREATE INDEX IF NOT EXISTS idx_chunks_lookup ON chunks(company_id, fiscal_year, fiscal_quarter);
CREATE UNIQUE INDEX IF NOT EXISTS uq_chunks_id_version ON chunks(chunk_id, chunker_version);

-- 3. Row-Level Security on chunks (Foundation Lock 6)
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS chunks_tenant_isolation ON chunks;
CREATE POLICY chunks_tenant_isolation ON chunks FOR ALL
    USING (tenant_id IS NULL OR tenant_id = current_setting('app.current_tenant', true))
    WITH CHECK (tenant_id IS NULL OR tenant_id = current_setting('app.current_tenant', true));

-- 4. Immutable Retrieval Snapshots (Foundation Lock 8)
CREATE TABLE IF NOT EXISTS retrieval_snapshots (
    snapshot_id VARCHAR(64) PRIMARY KEY,
    query_text TEXT NOT NULL,
    filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    tenant_id VARCHAR(64) REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    embedding_model VARCHAR(64) NOT NULL,
    chunker_version VARCHAR(32) NOT NULL,
    retrieved_chunks JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_retrieval_snapshots_tenant ON retrieval_snapshots(tenant_id);

ALTER TABLE retrieval_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE retrieval_snapshots FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS retrieval_snapshots_tenant_isolation ON retrieval_snapshots;
CREATE POLICY retrieval_snapshots_tenant_isolation ON retrieval_snapshots FOR ALL 
    USING (tenant_id IS NULL OR tenant_id = current_setting('app.current_tenant', true))
    WITH CHECK (tenant_id IS NULL OR tenant_id = current_setting('app.current_tenant', true));

-- 5. Privileges for app_rw and app_ro roles
GRANT SELECT, INSERT, UPDATE, DELETE ON chunks TO app_rw;
GRANT SELECT ON chunks TO app_ro;
GRANT SELECT, INSERT, UPDATE, DELETE ON retrieval_snapshots TO app_rw;
GRANT SELECT ON retrieval_snapshots TO app_ro;
