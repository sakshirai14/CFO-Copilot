-- migrations/004_kpi_engine.sql
-- Phase 2: KPI Engine Schema Expansion
-- Expands kpi_values to store full provenance, basis, status, reason, and policy version

-- 1. Alter kpi_values table
ALTER TABLE kpi_values RENAME COLUMN kpi_value TO value;
ALTER TABLE kpi_values ALTER COLUMN value DROP NOT NULL;

ALTER TABLE kpi_values 
    ADD COLUMN IF NOT EXISTS basis VARCHAR(32) NOT NULL DEFAULT 'as_restated' CHECK (basis IN ('as_restated', 'as_originally_reported')),
    ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'missing_input', 'conflict', 'unverified', 'not_meaningful', 'denominator_zero', 'non_aligned')),
    ADD COLUMN IF NOT EXISTS reason TEXT,
    ADD COLUMN IF NOT EXISTS input_line_item_ids INT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS restated BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS policy_version VARCHAR(16) NOT NULL DEFAULT 'v1.0.0',
    ADD COLUMN IF NOT EXISTS run_id VARCHAR(64);

-- 2. Drop old unique constraint and add new multi-basis versioned unique constraint
ALTER TABLE kpi_values DROP CONSTRAINT IF EXISTS uq_kpi_value;
ALTER TABLE kpi_values ADD CONSTRAINT uq_kpi_value UNIQUE (company_id, fiscal_year, fiscal_quarter, kpi_id, basis, policy_version);

-- 3. Indexes for fast lookup by company, period, kpi, and basis
CREATE INDEX IF NOT EXISTS idx_kpi_values_lookup 
ON kpi_values(company_id, fiscal_year, fiscal_quarter, kpi_id, basis);

CREATE INDEX IF NOT EXISTS idx_kpi_values_status 
ON kpi_values(status);

-- 4. Permissions
GRANT SELECT ON kpi_values TO app_ro;
GRANT SELECT, INSERT, UPDATE, DELETE ON kpi_values TO app_rw;
GRANT USAGE, SELECT ON SEQUENCE kpi_values_id_seq TO app_rw;
