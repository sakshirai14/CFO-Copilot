-- app/data/sql/kpis/asset_turnover_x.sql
-- KPI: Asset turnover (quarterly)
-- Formula: revenue / total_assets
-- Unit: x (Quarterly, not annualised)

WITH periods AS (
    SELECT DISTINCT company_id, fiscal_year, fiscal_quarter, period_end
    FROM filings
),
rev AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'revenue' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
),
ta AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'total_assets' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
)
SELECT 
    p.company_id,
    p.fiscal_year,
    p.fiscal_quarter,
    p.period_end,
    'asset_turnover_x' AS kpi_id,
    CASE 
        WHEN rev.value_normalized IS NULL OR ta.value_normalized IS NULL THEN NULL
        WHEN ta.value_normalized = 0 THEN NULL
        WHEN rev.eli_status != 'ok' OR ta.eli_status != 'ok' THEN NULL
        ELSE ROUND(rev.value_normalized / ta.value_normalized, 6)
    END AS value,
    'x' AS unit,
    CASE 
        WHEN rev.eli_status = 'conflict' OR ta.eli_status = 'conflict' THEN 'conflict'
        WHEN rev.eli_status = 'unverified' OR ta.eli_status = 'unverified' THEN 'unverified'
        WHEN rev.value_normalized IS NULL OR ta.value_normalized IS NULL THEN 'missing_input'
        WHEN ta.value_normalized = 0 THEN 'denominator_zero'
        ELSE 'ok'
    END AS status,
    CASE 
        WHEN rev.eli_status = 'conflict' OR ta.eli_status = 'conflict' THEN 'Conflicting input values in filing'
        WHEN rev.eli_status = 'unverified' OR ta.eli_status = 'unverified' THEN 'Input failed accounting integrity check'
        WHEN rev.value_normalized IS NULL OR ta.value_normalized IS NULL THEN 'Missing required inputs: revenue or total_assets'
        WHEN ta.value_normalized = 0 THEN 'Total assets denominator is zero'
        ELSE NULL
    END AS reason,
    ARRAY_REMOVE(ARRAY[rev.line_item_id, ta.line_item_id], NULL) AS input_line_item_ids,
    %(basis)s AS basis,
    COALESCE(('R2' = ANY(rev.rule_ids_applied) OR 'R2' = ANY(ta.rule_ids_applied)), FALSE) AS restated,
    %(policy_version)s AS policy_version
FROM periods p
LEFT JOIN rev ON p.company_id = rev.company_id AND p.fiscal_year = rev.fiscal_year AND p.fiscal_quarter = rev.fiscal_quarter
LEFT JOIN ta ON p.company_id = ta.company_id AND p.fiscal_year = ta.fiscal_year AND p.fiscal_quarter = ta.fiscal_quarter
ORDER BY p.company_id, p.fiscal_year, p.fiscal_quarter;
