-- app/data/sql/kpis/revenue_yoy_growth_pct.sql
-- KPI: Revenue growth, year over year
-- Formula: (revenue / revenue same fiscal quarter prior fiscal year - 1) * 100
-- Unit: percent (Not defined for first four quarters in the data)

WITH periods AS (
    SELECT DISTINCT company_id, fiscal_year, fiscal_quarter, period_end
    FROM filings
),
rev_curr AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'revenue' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
),
rev_prior AS (
    SELECT eli.company_id, (eli.fiscal_year + 1) as target_fy, eli.fiscal_quarter, eli.status as eli_status,
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
    'revenue_yoy_growth_pct' AS kpi_id,
    CASE 
        WHEN p.fiscal_year <= 2022 THEN NULL
        WHEN curr.value_normalized IS NULL OR prior.value_normalized IS NULL THEN NULL
        WHEN prior.value_normalized = 0 THEN NULL
        WHEN curr.eli_status != 'ok' OR prior.eli_status != 'ok' THEN NULL
        ELSE ROUND(((curr.value_normalized / prior.value_normalized) - 1) * 100, 6)
    END AS value,
    'percent' AS unit,
    CASE 
        WHEN p.fiscal_year <= 2022 THEN 'missing_input'
        WHEN curr.eli_status = 'conflict' OR prior.eli_status = 'conflict' THEN 'conflict'
        WHEN curr.eli_status = 'unverified' OR prior.eli_status = 'unverified' THEN 'unverified'
        WHEN curr.value_normalized IS NULL OR prior.value_normalized IS NULL THEN 'missing_input'
        WHEN prior.value_normalized = 0 THEN 'denominator_zero'
        ELSE 'ok'
    END AS status,
    CASE 
        WHEN p.fiscal_year <= 2022 THEN 'Prior year fiscal quarter not available in dataset (first four quarters)'
        WHEN curr.eli_status = 'conflict' OR prior.eli_status = 'conflict' THEN 'Conflicting input values in filing'
        WHEN curr.eli_status = 'unverified' OR prior.eli_status = 'unverified' THEN 'Input failed accounting integrity check'
        WHEN curr.value_normalized IS NULL THEN 'Current quarter revenue is missing'
        WHEN prior.value_normalized IS NULL THEN 'Prior year quarter revenue is missing'
        WHEN prior.value_normalized = 0 THEN 'Prior year revenue is zero'
        ELSE NULL
    END AS reason,
    ARRAY_REMOVE(ARRAY[curr.line_item_id, prior.line_item_id], NULL) AS input_line_item_ids,
    %(basis)s AS basis,
    COALESCE(('R2' = ANY(curr.rule_ids_applied) OR 'R2' = ANY(prior.rule_ids_applied)), FALSE) AS restated,
    %(policy_version)s AS policy_version
FROM periods p
LEFT JOIN rev_curr curr ON p.company_id = curr.company_id AND p.fiscal_year = curr.fiscal_year AND p.fiscal_quarter = curr.fiscal_quarter
LEFT JOIN rev_prior prior ON p.company_id = prior.company_id AND p.fiscal_year = prior.target_fy AND p.fiscal_quarter = prior.fiscal_quarter
ORDER BY p.company_id, p.fiscal_year, p.fiscal_quarter;
