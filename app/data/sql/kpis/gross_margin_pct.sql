-- app/data/sql/kpis/gross_margin_pct.sql
-- KPI: Gross margin (quarterly)
-- Formula: gross_profit / revenue * 100

WITH periods AS (
    SELECT DISTINCT company_id, fiscal_year, fiscal_quarter, period_end
    FROM filings
),
gp AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'gross_profit' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
),
rev AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'revenue' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
)
SELECT 
    p.company_id,
    p.fiscal_year,
    p.fiscal_quarter,
    p.period_end,
    'gross_margin_pct' AS kpi_id,
    CASE 
        WHEN gp.value_normalized IS NULL OR rev.value_normalized IS NULL THEN NULL
        WHEN rev.value_normalized = 0 THEN NULL
        WHEN gp.eli_status != 'ok' OR rev.eli_status != 'ok' THEN NULL
        ELSE ROUND((gp.value_normalized / rev.value_normalized) * 100, 6)
    END AS value,
    'percent' AS unit,
    CASE 
        WHEN gp.eli_status = 'conflict' OR rev.eli_status = 'conflict' THEN 'conflict'
        WHEN gp.eli_status = 'unverified' OR rev.eli_status = 'unverified' THEN 'unverified'
        WHEN gp.value_normalized IS NULL OR rev.value_normalized IS NULL THEN 'missing_input'
        WHEN rev.value_normalized = 0 THEN 'denominator_zero'
        ELSE 'ok'
    END AS status,
    CASE 
        WHEN gp.eli_status = 'conflict' OR rev.eli_status = 'conflict' THEN 'Conflicting input values in filing'
        WHEN gp.eli_status = 'unverified' OR rev.eli_status = 'unverified' THEN 'Input failed accounting integrity check'
        WHEN gp.value_normalized IS NULL OR rev.value_normalized IS NULL THEN 'Missing required inputs: gross_profit or revenue'
        WHEN rev.value_normalized = 0 THEN 'Revenue denominator is zero'
        ELSE NULL
    END AS reason,
    ARRAY_REMOVE(ARRAY[gp.line_item_id, rev.line_item_id], NULL) AS input_line_item_ids,
    %(basis)s AS basis,
    COALESCE(('R2' = ANY(gp.rule_ids_applied) OR 'R2' = ANY(rev.rule_ids_applied)), FALSE) AS restated,
    %(policy_version)s AS policy_version
FROM periods p
LEFT JOIN gp ON p.company_id = gp.company_id AND p.fiscal_year = gp.fiscal_year AND p.fiscal_quarter = gp.fiscal_quarter
LEFT JOIN rev ON p.company_id = rev.company_id AND p.fiscal_year = rev.fiscal_year AND p.fiscal_quarter = rev.fiscal_quarter
ORDER BY p.company_id, p.fiscal_year, p.fiscal_quarter;
