-- migrations/003_effective_line_items.sql
-- Phase 2: Effective Line Items Resolution Schema
-- Enforces Conflict Policy Rules R1 through R5, R11, R12

CREATE TABLE IF NOT EXISTS effective_line_items (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(16) NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    fiscal_year INT NOT NULL,
    fiscal_quarter INT NOT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4),
    canonical_item VARCHAR(64) NOT NULL,
    effective_line_item_id INT REFERENCES line_items(id),
    basis VARCHAR(32) NOT NULL CHECK (basis IN ('as_restated', 'as_originally_reported')),
    rule_ids_applied TEXT[] NOT NULL DEFAULT '{}',
    status VARCHAR(32) NOT NULL CHECK (status IN ('ok', 'conflict', 'unverified', 'missing_input', 'not_meaningful', 'denominator_zero', 'non_aligned')),
    alternatives JSONB NOT NULL DEFAULT '[]'::jsonb,
    policy_version VARCHAR(16) NOT NULL DEFAULT 'v1.0.0',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_effective_line_item UNIQUE (company_id, fiscal_year, fiscal_quarter, canonical_item, basis, policy_version)
);

CREATE INDEX IF NOT EXISTS idx_effective_line_items_lookup 
ON effective_line_items(company_id, fiscal_year, fiscal_quarter, canonical_item, basis);

-- Grant privileges to application roles
GRANT SELECT ON effective_line_items TO app_ro;
GRANT SELECT, INSERT, UPDATE, DELETE ON effective_line_items TO app_rw;
GRANT USAGE, SELECT ON SEQUENCE effective_line_items_id_seq TO app_rw;
