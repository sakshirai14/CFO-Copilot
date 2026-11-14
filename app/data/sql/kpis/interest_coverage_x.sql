-- app/data/sql/kpis/interest_coverage_x.sql
-- KPI: Interest coverage
-- Formula: operating_income / interest_expense
-- Unit: x (Interest expense as a positive amount)

WITH periods AS (
    SELECT DISTINCT company_id, fiscal_year, fiscal_quarter, period_end
    FROM filings
),
oi AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'operating_income' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
),
ie AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'interest_expense' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
)
SELECT 
    p.company_id,
    p.fiscal_year,
    p.fiscal_quarter,
    p.period_end,
    'interest_coverage_x' AS kpi_id,
    CASE 
        WHEN oi.value_normalized IS NULL OR ie.value_normalized IS NULL THEN NULL
        WHEN ie.value_normalized = 0 THEN NULL
        WHEN 'R11' = ANY(oi.rule_ids_applied) OR oi.eli_status != 'ok' OR ie.eli_status != 'ok' THEN NULL
        ELSE ROUND(oi.value_normalized / ABS(ie.value_normalized), 6)
    END AS value,
    'x' AS unit,
    CASE 
        WHEN 'R11' = ANY(oi.rule_ids_applied) THEN 'unverified'
        WHEN oi.eli_status = 'conflict' OR ie.eli_status = 'conflict' THEN 'conflict'
        WHEN oi.eli_status = 'unverified' OR ie.eli_status = 'unverified' THEN 'unverified'
        WHEN oi.value_normalized IS NULL OR ie.value_normalized IS NULL THEN 'missing_input'
        WHEN ie.value_normalized = 0 THEN 'denominator_zero'
        ELSE 'ok'
    END AS status,
    CASE 
        WHEN 'R11' = ANY(oi.rule_ids_applied) THEN 'Operating income failed accounting integrity check (R11)'
        WHEN oi.eli_status = 'conflict' OR ie.eli_status = 'conflict' THEN 'Conflicting input values in filing'
        WHEN oi.eli_status = 'unverified' OR ie.eli_status = 'unverified' THEN 'Input failed accounting integrity check'
        WHEN oi.value_normalized IS NULL OR ie.value_normalized IS NULL THEN 'Missing required inputs: operating_income or interest_expense'
        WHEN ie.value_normalized = 0 THEN 'Interest expense denominator is zero'
        ELSE NULL
    END AS reason,
    ARRAY_REMOVE(ARRAY[oi.line_item_id, ie.line_item_id], NULL) AS input_line_item_ids,
    %(basis)s AS basis,
    COALESCE(('R2' = ANY(oi.rule_ids_applied) OR 'R2' = ANY(ie.rule_ids_applied)), FALSE) AS restated,
    %(policy_version)s AS policy_version
FROM periods p
LEFT JOIN oi ON p.company_id = oi.company_id AND p.fiscal_year = oi.fiscal_year AND p.fiscal_quarter = oi.fiscal_quarter
LEFT JOIN ie ON p.company_id = ie.company_id AND p.fiscal_year = ie.fiscal_year AND p.fiscal_quarter = ie.fiscal_quarter
ORDER BY p.company_id, p.fiscal_year, p.fiscal_quarter;
