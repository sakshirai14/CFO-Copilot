-- app/data/sql/kpis/debt_to_equity_x.sql
-- KPI: Debt to equity
-- Formula: total_debt / total_equity
-- Unit: x (At period end)

WITH periods AS (
    SELECT DISTINCT company_id, fiscal_year, fiscal_quarter, period_end
    FROM filings
),
debt AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'total_debt' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
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
    'debt_to_equity_x' AS kpi_id,
    CASE 
        WHEN debt.value_normalized IS NULL OR eq.value_normalized IS NULL THEN NULL
        WHEN eq.value_normalized <= 0 THEN NULL
        WHEN debt.eli_status != 'ok' OR eq.eli_status != 'ok' THEN NULL
        ELSE ROUND(debt.value_normalized / eq.value_normalized, 6)
    END AS value,
    'x' AS unit,
    CASE 
        WHEN debt.eli_status = 'conflict' OR eq.eli_status = 'conflict' THEN 'conflict'
        WHEN debt.eli_status = 'unverified' OR eq.eli_status = 'unverified' THEN 'unverified'
        WHEN debt.value_normalized IS NULL OR eq.value_normalized IS NULL THEN 'missing_input'
        WHEN eq.value_normalized <= 0 THEN 'not_meaningful'
        ELSE 'ok'
    END AS status,
    CASE 
        WHEN debt.eli_status = 'conflict' OR eq.eli_status = 'conflict' THEN 'Conflicting input values in filing'
        WHEN debt.eli_status = 'unverified' OR eq.eli_status = 'unverified' THEN 'Input failed accounting integrity check'
        WHEN debt.value_normalized IS NULL OR eq.value_normalized IS NULL THEN 'Missing required inputs: total_debt or total_equity'
        WHEN eq.value_normalized <= 0 THEN 'Stockholders equity is negative or zero; ratio is economically non-meaningful'
        ELSE NULL
    END AS reason,
    ARRAY_REMOVE(ARRAY[debt.line_item_id, eq.line_item_id], NULL) AS input_line_item_ids,
    %(basis)s AS basis,
    COALESCE(('R2' = ANY(debt.rule_ids_applied) OR 'R2' = ANY(eq.rule_ids_applied)), FALSE) AS restated,
    %(policy_version)s AS policy_version
FROM periods p
LEFT JOIN debt ON p.company_id = debt.company_id AND p.fiscal_year = debt.fiscal_year AND p.fiscal_quarter = debt.fiscal_quarter
LEFT JOIN eq ON p.company_id = eq.company_id AND p.fiscal_year = eq.fiscal_year AND p.fiscal_quarter = eq.fiscal_quarter
ORDER BY p.company_id, p.fiscal_year, p.fiscal_quarter;
