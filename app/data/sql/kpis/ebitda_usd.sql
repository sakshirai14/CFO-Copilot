-- app/data/sql/kpis/ebitda_usd.sql
-- KPI: EBITDA
-- Formula: operating_income + depreciation_and_amortization
-- Unit: USD (In whole US dollars. No other add-backs)

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
da AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'depreciation_and_amortization' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
)
SELECT 
    p.company_id,
    p.fiscal_year,
    p.fiscal_quarter,
    p.period_end,
    'ebitda_usd' AS kpi_id,
    CASE 
        WHEN oi.value_normalized IS NULL OR da.value_normalized IS NULL THEN NULL
        WHEN 'R11' = ANY(oi.rule_ids_applied) OR oi.eli_status != 'ok' OR da.eli_status != 'ok' THEN NULL
        ELSE ROUND(oi.value_normalized + da.value_normalized, 4)
    END AS value,
    'USD' AS unit,
    CASE 
        WHEN 'R11' = ANY(oi.rule_ids_applied) THEN 'unverified'
        WHEN oi.eli_status = 'conflict' OR da.eli_status = 'conflict' THEN 'conflict'
        WHEN oi.eli_status = 'unverified' OR da.eli_status = 'unverified' THEN 'unverified'
        WHEN oi.value_normalized IS NULL OR da.value_normalized IS NULL THEN 'missing_input'
        ELSE 'ok'
    END AS status,
    CASE 
        WHEN 'R11' = ANY(oi.rule_ids_applied) THEN 'Operating income failed accounting integrity check (R11)'
        WHEN oi.eli_status = 'conflict' OR da.eli_status = 'conflict' THEN 'Conflicting input values in filing'
        WHEN oi.eli_status = 'unverified' OR da.eli_status = 'unverified' THEN 'Input failed accounting integrity check'
        WHEN oi.value_normalized IS NULL OR da.value_normalized IS NULL THEN 'Missing required inputs: operating_income or depreciation_and_amortization'
        ELSE NULL
    END AS reason,
    ARRAY_REMOVE(ARRAY[oi.line_item_id, da.line_item_id], NULL) AS input_line_item_ids,
    %(basis)s AS basis,
    COALESCE(('R2' = ANY(oi.rule_ids_applied) OR 'R2' = ANY(da.rule_ids_applied)), FALSE) AS restated,
    %(policy_version)s AS policy_version
FROM periods p
LEFT JOIN oi ON p.company_id = oi.company_id AND p.fiscal_year = oi.fiscal_year AND p.fiscal_quarter = oi.fiscal_quarter
LEFT JOIN da ON p.company_id = da.company_id AND p.fiscal_year = da.fiscal_year AND p.fiscal_quarter = da.fiscal_quarter
ORDER BY p.company_id, p.fiscal_year, p.fiscal_quarter;
