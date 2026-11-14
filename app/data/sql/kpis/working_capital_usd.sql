-- app/data/sql/kpis/working_capital_usd.sql
-- KPI: Working capital
-- Formula: total_current_assets - total_current_liabilities
-- Unit: USD (At period end)

WITH periods AS (
    SELECT DISTINCT company_id, fiscal_year, fiscal_quarter, period_end
    FROM filings
),
ca AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'total_current_assets' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
),
cl AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'total_current_liabilities' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
)
SELECT 
    p.company_id,
    p.fiscal_year,
    p.fiscal_quarter,
    p.period_end,
    'working_capital_usd' AS kpi_id,
    CASE 
        WHEN ca.value_normalized IS NULL OR cl.value_normalized IS NULL THEN NULL
        WHEN ca.eli_status != 'ok' OR cl.eli_status != 'ok' THEN NULL
        ELSE ROUND(ca.value_normalized - cl.value_normalized, 4)
    END AS value,
    'USD' AS unit,
    CASE 
        WHEN ca.eli_status = 'conflict' OR cl.eli_status = 'conflict' THEN 'conflict'
        WHEN ca.eli_status = 'unverified' OR cl.eli_status = 'unverified' THEN 'unverified'
        WHEN ca.value_normalized IS NULL OR cl.value_normalized IS NULL THEN 'missing_input'
        ELSE 'ok'
    END AS status,
    CASE 
        WHEN ca.eli_status = 'conflict' OR cl.eli_status = 'conflict' THEN 'Conflicting input values in filing'
        WHEN ca.eli_status = 'unverified' OR cl.eli_status = 'unverified' THEN 'Input failed accounting integrity check'
        WHEN ca.value_normalized IS NULL OR cl.value_normalized IS NULL THEN 'Missing required inputs: total_current_assets or total_current_liabilities'
        ELSE NULL
    END AS reason,
    ARRAY_REMOVE(ARRAY[ca.line_item_id, cl.line_item_id], NULL) AS input_line_item_ids,
    %(basis)s AS basis,
    COALESCE(('R2' = ANY(ca.rule_ids_applied) OR 'R2' = ANY(cl.rule_ids_applied)), FALSE) AS restated,
    %(policy_version)s AS policy_version
FROM periods p
LEFT JOIN ca ON p.company_id = ca.company_id AND p.fiscal_year = ca.fiscal_year AND p.fiscal_quarter = ca.fiscal_quarter
LEFT JOIN cl ON p.company_id = cl.company_id AND p.fiscal_year = cl.fiscal_year AND p.fiscal_quarter = cl.fiscal_quarter
ORDER BY p.company_id, p.fiscal_year, p.fiscal_quarter;
