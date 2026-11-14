-- app/data/sql/kpis/free_cash_flow_usd.sql
-- KPI: Free cash flow
-- Formula: cash_from_operations - capital_expenditures
-- Unit: USD (Capex taken as a positive outflow amount)

WITH periods AS (
    SELECT DISTINCT company_id, fiscal_year, fiscal_quarter, period_end
    FROM filings
),
cfo AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'cash_from_operations' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
),
capex AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'capital_expenditures' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
)
SELECT 
    p.company_id,
    p.fiscal_year,
    p.fiscal_quarter,
    p.period_end,
    'free_cash_flow_usd' AS kpi_id,
    CASE 
        WHEN cfo.value_normalized IS NULL OR capex.value_normalized IS NULL THEN NULL
        WHEN cfo.eli_status != 'ok' OR capex.eli_status != 'ok' THEN NULL
        ELSE ROUND(cfo.value_normalized - capex.value_normalized, 4)
    END AS value,
    'USD' AS unit,
    CASE 
        WHEN cfo.eli_status = 'conflict' OR capex.eli_status = 'conflict' THEN 'conflict'
        WHEN cfo.eli_status = 'unverified' OR capex.eli_status = 'unverified' THEN 'unverified'
        WHEN cfo.value_normalized IS NULL OR capex.value_normalized IS NULL THEN 'missing_input'
        ELSE 'ok'
    END AS status,
    CASE 
        WHEN cfo.eli_status = 'conflict' OR capex.eli_status = 'conflict' THEN 'Conflicting input values in filing'
        WHEN cfo.eli_status = 'unverified' OR capex.eli_status = 'unverified' THEN 'Input failed accounting integrity check'
        WHEN cfo.value_normalized IS NULL OR capex.value_normalized IS NULL THEN 'Missing required inputs: cash_from_operations or capital_expenditures'
        ELSE NULL
    END AS reason,
    ARRAY_REMOVE(ARRAY[cfo.line_item_id, capex.line_item_id], NULL) AS input_line_item_ids,
    %(basis)s AS basis,
    COALESCE(('R2' = ANY(cfo.rule_ids_applied) OR 'R2' = ANY(capex.rule_ids_applied)), FALSE) AS restated,
    %(policy_version)s AS policy_version
FROM periods p
LEFT JOIN cfo ON p.company_id = cfo.company_id AND p.fiscal_year = cfo.fiscal_year AND p.fiscal_quarter = cfo.fiscal_quarter
LEFT JOIN capex ON p.company_id = capex.company_id AND p.fiscal_year = capex.fiscal_year AND p.fiscal_quarter = capex.fiscal_quarter
ORDER BY p.company_id, p.fiscal_year, p.fiscal_quarter;
