-- migrations/001_initial_schema.sql
-- Phase 1 Initial Schema for CFO Copilot on a Budget
-- Mirrors data_pack/CANDIDATE_PACK/data_dictionary.csv
-- Enforces Locks 5 (Data Integrity) and 6 (Isolation with RLS)

-- 1. Tenants Table
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed initial multi-tenant test accounts
INSERT INTO tenants (tenant_id, name)
VALUES 
    ('acme', 'Acme Holdings LLC'),
    ('borealis', 'Borealis Capital Management')
ON CONFLICT (tenant_id) DO NOTHING;

-- 2. Companies Table (Supports ZLG Sept 30 and HBS July 1 fiscal years)
CREATE TABLE IF NOT EXISTS companies (
    company_id VARCHAR(16) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    sector VARCHAR(128) NOT NULL,
    fiscal_year_end_month INT NOT NULL CHECK (fiscal_year_end_month BETWEEN 1 AND 12),
    reporting_currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    fiscal_year_note TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Filings Master Index
CREATE TABLE IF NOT EXISTS filings (
    filing_id VARCHAR(64) PRIMARY KEY,
    company_id VARCHAR(16) NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    form_type VARCHAR(16) NOT NULL CHECK (form_type IN ('10-K', '10-Q', '10-Q/A')),
    fiscal_year INT NOT NULL,
    fiscal_quarter INT NOT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4),
    period_start DATE,
    period_end DATE NOT NULL,
    filed_date DATE NOT NULL,
    reporting_unit VARCHAR(32) NOT NULL,
    amends_filing_id VARCHAR(64) REFERENCES filings(filing_id),
    doc_id VARCHAR(64),
    source_release VARCHAR(16) NOT NULL CHECK (source_release IN ('drop1', 'drop2')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_filings_company_fiscal ON filings(company_id, fiscal_year, fiscal_quarter);

-- 4. Raw Financial Rows (Immutable Auditing Layer - Full Provenance)
CREATE TABLE IF NOT EXISTS raw_financial_rows (
    row_id VARCHAR(32) PRIMARY KEY,
    source_release VARCHAR(16) NOT NULL CHECK (source_release IN ('drop1', 'drop2')),
    source_file VARCHAR(255) NOT NULL,
    source_row_number INT NOT NULL,
    row_hash VARCHAR(64) UNIQUE NOT NULL,
    company_id VARCHAR(16) NOT NULL REFERENCES companies(company_id),
    filing_id VARCHAR(64) NOT NULL REFERENCES filings(filing_id),
    statement VARCHAR(8) NOT NULL CHECK (statement IN ('IS', 'BS', 'CF')),
    line_item_raw TEXT NOT NULL,
    fiscal_year INT NOT NULL,
    fiscal_quarter INT NOT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4),
    period_start_raw VARCHAR(32),
    period_end_raw VARCHAR(32),
    value_raw VARCHAR(64),
    unit_raw VARCHAR(32),
    currency_raw VARCHAR(16),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_raw_rows_filing ON raw_financial_rows(filing_id);
CREATE INDEX IF NOT EXISTS idx_raw_rows_company_statement ON raw_financial_rows(company_id, statement);

-- 5. Line Item Taxonomy & Synonyms Mapping
CREATE TABLE IF NOT EXISTS line_item_map (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(16) REFERENCES companies(company_id),
    statement VARCHAR(8) NOT NULL CHECK (statement IN ('IS', 'BS', 'CF')),
    raw_name TEXT NOT NULL,
    canonical_name VARCHAR(64) NOT NULL,
    sign_multiplier INT NOT NULL DEFAULT 1 CHECK (sign_multiplier IN (1, -1)),
    notes TEXT,
    CONSTRAINT uq_line_item_map UNIQUE (company_id, statement, raw_name)
);

-- 6. Normalized Line Items (Calculations-Ready Table)
CREATE TABLE IF NOT EXISTS line_items (
    id SERIAL PRIMARY KEY,
    raw_row_id VARCHAR(32) NOT NULL REFERENCES raw_financial_rows(row_id),
    filing_id VARCHAR(64) NOT NULL REFERENCES filings(filing_id),
    company_id VARCHAR(16) NOT NULL REFERENCES companies(company_id),
    statement VARCHAR(8) NOT NULL CHECK (statement IN ('IS', 'BS', 'CF')),
    canonical_item VARCHAR(64) NOT NULL,
    period_start DATE,
    period_end DATE NOT NULL,
    duration_days INT NOT NULL,
    period_type VARCHAR(16) NOT NULL CHECK (period_type IN ('quarterly', 'half_year', 'nine_months', 'annual', 'point_in_time')),
    fiscal_year INT NOT NULL,
    fiscal_quarter INT NOT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4),
    value_normalized NUMERIC(20, 4) NOT NULL,
    original_value NUMERIC(20, 4) NOT NULL,
    original_unit VARCHAR(32) NOT NULL,
    scale_factor NUMERIC(16, 4) NOT NULL,
    sign_multiplier INT NOT NULL DEFAULT 1 CHECK (sign_multiplier IN (1, -1)),
    duplicate_of_id INT REFERENCES line_items(id),
    status VARCHAR(16) NOT NULL DEFAULT 'valid' CHECK (status IN ('valid', 'duplicate', 'restated', 'flagged')),
    normalization_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_line_items_query ON line_items(company_id, canonical_item, fiscal_year, fiscal_quarter);

-- 7. Data Quality Issues (Audit Log of Anomalies)
CREATE TABLE IF NOT EXISTS data_quality_issues (
    id SERIAL PRIMARY KEY,
    issue_type VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    company_id VARCHAR(16),
    filing_id VARCHAR(64),
    raw_row_id VARCHAR(32),
    doc_id VARCHAR(64),
    description TEXT NOT NULL,
    detected_by VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'detected' CHECK (status IN ('detected', 'resolved', 'ignored')),
    resolution_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dqi_severity ON data_quality_issues(severity);

-- 8. KPI Definitions (Staged for Phase 2)
CREATE TABLE IF NOT EXISTS kpi_definitions (
    kpi_id VARCHAR(64) PRIMARY KEY,
    kpi_name VARCHAR(128) NOT NULL,
    formula TEXT NOT NULL,
    unit VARCHAR(32) NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. KPI Values (Staged empty for Phase 2 computation)
CREATE TABLE IF NOT EXISTS kpi_values (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(16) NOT NULL REFERENCES companies(company_id),
    kpi_id VARCHAR(64) NOT NULL REFERENCES kpi_definitions(kpi_id),
    fiscal_year INT NOT NULL,
    fiscal_quarter INT NOT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4),
    period_end DATE NOT NULL,
    kpi_value NUMERIC(20, 6) NOT NULL,
    unit VARCHAR(32) NOT NULL,
    calculation_sql TEXT,
    source_filing_ids TEXT[],
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_kpi_value UNIQUE (company_id, kpi_id, fiscal_year, fiscal_quarter)
);

-- 10. Documents Corpus (Unstructured Filing Text & Exhibits)
CREATE TABLE IF NOT EXISTS documents (
    doc_id VARCHAR(64) PRIMARY KEY,
    company_id VARCHAR(16) NOT NULL REFERENCES companies(company_id),
    doc_type VARCHAR(32) NOT NULL CHECK (doc_type IN ('filing', 'other_document')),
    form_type VARCHAR(16),
    fiscal_year INT,
    fiscal_quarter INT,
    filed_date DATE,
    title TEXT NOT NULL,
    authority_rank INT NOT NULL CHECK (authority_rank BETWEEN 1 AND 4),
    text TEXT NOT NULL,
    source_release VARCHAR(16) NOT NULL CHECK (source_release IN ('drop1', 'drop2')),
    content_hash VARCHAR(64) NOT NULL,
    trust_level VARCHAR(16) NOT NULL DEFAULT 'trusted' CHECK (trust_level IN ('trusted', 'untrusted', 'quarantined')),
    risk_flags TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_docs_company ON documents(company_id);

-- 11. Document Chunks & Vector Store (Lock 5 & Lock 6)
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id VARCHAR(64) PRIMARY KEY,
    doc_id VARCHAR(64) NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    text TEXT NOT NULL,
    embedding vector(768),
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_chunk_doc_idx UNIQUE (doc_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON chunks USING GIN(tsv);

-- 12. Chat Sessions (Multi-Tenant with Row-Level Security)
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL,
    title TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_tenant ON chat_sessions(tenant_id);

-- 13. Chat Messages (Multi-Tenant with Row-Level Security)
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    role VARCHAR(16) NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_tenant ON chat_messages(tenant_id);

-- 14. Answer Log (Multi-Tenant with Row-Level Security - Provenance & Replay)
CREATE TABLE IF NOT EXISTS answer_log (
    log_id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    session_id VARCHAR(64) NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    request_id VARCHAR(64) NOT NULL,
    user_query TEXT NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    prompt_template_hash VARCHAR(64) NOT NULL,
    retrieval_snapshot JSONB,
    routed_to VARCHAR(16) NOT NULL,
    cached_tokens INT NOT NULL DEFAULT 0,
    prompt_tokens INT NOT NULL DEFAULT 0,
    completion_tokens INT NOT NULL DEFAULT 0,
    ttft_ms NUMERIC(10, 2),
    total_time_ms NUMERIC(10, 2),
    answer_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_answer_log_tenant ON answer_log(tenant_id);

-- 15. System Metrics
CREATE TABLE IF NOT EXISTS metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(64) NOT NULL,
    metric_value NUMERIC(14, 4) NOT NULL,
    dimensions JSONB,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 16. ENFORCE ROW-LEVEL SECURITY (Lock 6: Tenant Isolation)
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions FORCE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'chat_sessions' AND policyname = 'tenant_isolation_chat_sessions') THEN
        CREATE POLICY tenant_isolation_chat_sessions ON chat_sessions
            USING (tenant_id = current_setting('app.current_tenant', true))
            WITH CHECK (tenant_id = current_setting('app.current_tenant', true));
    END IF;
END $$;

ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages FORCE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'chat_messages' AND policyname = 'tenant_isolation_chat_messages') THEN
        CREATE POLICY tenant_isolation_chat_messages ON chat_messages
            USING (tenant_id = current_setting('app.current_tenant', true))
            WITH CHECK (tenant_id = current_setting('app.current_tenant', true));
    END IF;
END $$;

ALTER TABLE answer_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE answer_log FORCE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'answer_log' AND policyname = 'tenant_isolation_answer_log') THEN
        CREATE POLICY tenant_isolation_answer_log ON answer_log
            USING (tenant_id = current_setting('app.current_tenant', true))
            WITH CHECK (tenant_id = current_setting('app.current_tenant', true));
    END IF;
END $$;
