-- app/data/sql/kpis/roe_quarterly_pct.sql
-- KPI: Return on equity (quarterly)
-- Formula: net_income / total_equity * 100
-- Unit: percent (Quarterly, not annualised)

WITH periods AS (
    SELECT DISTINCT company_id, fiscal_year, fiscal_quarter, period_end
    FROM filings
),
ni AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'net_income' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
),
eq AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'total_equity' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
)
SELECT 
    p.company_id,
    p.fiscal_year,
    p.fiscal_quarter,
    p.period_end,
    'roe_quarterly_pct' AS kpi_id,
    CASE 
        WHEN ni.value_normalized IS NULL OR eq.value_normalized IS NULL THEN NULL
        WHEN eq.value_normalized <= 0 THEN NULL
        WHEN ni.eli_status != 'ok' OR eq.eli_status != 'ok' THEN NULL
        ELSE ROUND((ni.value_normalized / eq.value_normalized) * 100, 6)
    END AS value,
    'percent' AS unit,
    CASE 
        WHEN ni.eli_status = 'conflict' OR eq.eli_status = 'conflict' THEN 'conflict'
        WHEN ni.eli_status = 'unverified' OR eq.eli_status = 'unverified' THEN 'unverified'
        WHEN ni.value_normalized IS NULL OR eq.value_normalized IS NULL THEN 'missing_input'
        WHEN eq.value_normalized <= 0 THEN 'not_meaningful'
        ELSE 'ok'
    END AS status,
    CASE 
        WHEN ni.eli_status = 'conflict' OR eq.eli_status = 'conflict' THEN 'Conflicting input values in filing'
        WHEN ni.eli_status = 'unverified' OR eq.eli_status = 'unverified' THEN 'Input failed accounting integrity check'
        WHEN ni.value_normalized IS NULL OR eq.value_normalized IS NULL THEN 'Missing required inputs: net_income or total_equity'
        WHEN eq.value_normalized <= 0 THEN 'Stockholders equity is negative or zero; ratio is economically non-meaningful'
        ELSE NULL
    END AS reason,
    ARRAY_REMOVE(ARRAY[ni.line_item_id, eq.line_item_id], NULL) AS input_line_item_ids,
    %(basis)s AS basis,
    COALESCE(('R2' = ANY(ni.rule_ids_applied) OR 'R2' = ANY(eq.rule_ids_applied)), FALSE) AS restated,
    %(policy_version)s AS policy_version
FROM periods p
LEFT JOIN ni ON p.company_id = ni.company_id AND p.fiscal_year = ni.fiscal_year AND p.fiscal_quarter = ni.fiscal_quarter
LEFT JOIN eq ON p.company_id = eq.company_id AND p.fiscal_year = eq.fiscal_year AND p.fiscal_quarter = eq.fiscal_quarter
ORDER BY p.company_id, p.fiscal_year, p.fiscal_quarter;
