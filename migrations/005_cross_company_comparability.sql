-- migrations/005_cross_company_comparability.sql
-- Rule R7: Comparability & Non-Aligned Fiscal Calendars
-- Provides a deterministic function to evaluate whether financial quarters
-- across distinct companies align on calendar period-ends within a configurable threshold.

CREATE OR REPLACE FUNCTION cross_company_comparability(
    target_companies text[],
    fiscal_label text,
    threshold_days integer DEFAULT 15
)
RETURNS TABLE (
    company_a VARCHAR(16),
    fiscal_label_a TEXT,
    period_start_a DATE,
    period_end_a DATE,
    company_b VARCHAR(16),
    fiscal_label_b TEXT,
    period_start_b DATE,
    period_end_b DATE,
    days_apart INTEGER,
    aligned BOOLEAN
)
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    parsed_year integer;
    parsed_quarter integer;
BEGIN
    -- Parse fiscal label e.g. 'FY2024Q1', 'FY2024 Q1', '2024Q1'
    parsed_year := SUBSTRING(fiscal_label FROM '(\d{4})')::integer;
    parsed_quarter := SUBSTRING(fiscal_label FROM '[Qq](\d)')::integer;
    
    IF parsed_year IS NULL OR parsed_quarter IS NULL THEN
        RAISE EXCEPTION 'Invalid fiscal label format: %. Expected format like FY2024Q1 or FY2024 Q1.', fiscal_label;
    END IF;

    RETURN QUERY
    WITH company_periods AS (
        SELECT DISTINCT
            f.company_id,
            'FY' || f.fiscal_year || 'Q' || f.fiscal_quarter AS f_label,
            f.period_start,
            f.period_end
        FROM filings f
        WHERE f.company_id = ANY(target_companies)
          AND f.fiscal_year = parsed_year
          AND f.fiscal_quarter = parsed_quarter
    )
    SELECT 
        cp1.company_id AS company_a,
        cp1.f_label AS fiscal_label_a,
        cp1.period_start AS period_start_a,
        cp1.period_end AS period_end_a,
        cp2.company_id AS company_b,
        cp2.f_label AS fiscal_label_b,
        cp2.period_start AS period_start_b,
        cp2.period_end AS period_end_b,
        ABS(cp1.period_end - cp2.period_end)::INTEGER AS days_apart,
        (ABS(cp1.period_end - cp2.period_end) <= threshold_days) AS aligned
    FROM company_periods cp1
    JOIN company_periods cp2 ON cp1.company_id < cp2.company_id
    ORDER BY cp1.company_id, cp2.company_id;
END;
$$;

GRANT EXECUTE ON FUNCTION cross_company_comparability(text[], text, integer) TO app_ro, app_rw;
