-- migrations/002_tenant_documents.sql
-- Hardening Foundation Lock 6: Multi-Tenant Document Store with Row-Level Security

CREATE TABLE IF NOT EXISTS tenant_documents (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    doc_text TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenant_documents_tenant ON tenant_documents(tenant_id);

ALTER TABLE tenant_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_documents FORCE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'tenant_documents' AND policyname = 'tenant_isolation_tenant_documents') THEN
        CREATE POLICY tenant_isolation_tenant_documents ON tenant_documents
            USING (tenant_id = current_setting('app.current_tenant', true))
            WITH CHECK (tenant_id = current_setting('app.current_tenant', true));
    END IF;
END $$;

-- Grant permissions to runtime roles
GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_documents TO app_rw;
GRANT SELECT ON tenant_documents TO app_ro;
GRANT USAGE, SELECT ON SEQUENCE tenant_documents_id_seq TO app_rw;

-- Seed initial canary documents for tenant isolation test verification
SET LOCAL app.current_tenant = 'acme';
INSERT INTO tenant_documents (tenant_id, title, doc_text, content_hash)
VALUES ('acme', 'Acme Board Minutes', 'CANARY_ACME_CONFIDENTIAL_DOCUMENT_PAYLOAD', 'hash_acme_doc_1')
ON CONFLICT DO NOTHING;

SET LOCAL app.current_tenant = 'borealis';
INSERT INTO tenant_documents (tenant_id, title, doc_text, content_hash)
VALUES ('borealis', 'Borealis Portfolio Strategy', 'CANARY_BOREALIS_CONFIDENTIAL_DOCUMENT_PAYLOAD', 'hash_borealis_doc_1')
ON CONFLICT DO NOTHING;

RESET app.current_tenant;
