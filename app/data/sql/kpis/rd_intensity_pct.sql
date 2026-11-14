-- app/data/sql/kpis/rd_intensity_pct.sql
-- KPI: R&D intensity
-- Formula: research_and_development / revenue * 100
-- Unit: percent (Zero where company reports no R&D)

WITH periods AS (
    SELECT DISTINCT company_id, fiscal_year, fiscal_quarter, period_end
    FROM filings
),
rd AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'research_and_development' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
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
    'rd_intensity_pct' AS kpi_id,
    CASE 
        WHEN rev.value_normalized IS NULL THEN NULL
        WHEN rev.value_normalized = 0 THEN NULL
        WHEN rev.eli_status != 'ok' THEN NULL
        WHEN rd.value_normalized IS NULL THEN 0.000000
        WHEN rd.eli_status != 'ok' THEN NULL
        ELSE ROUND((rd.value_normalized / rev.value_normalized) * 100, 6)
    END AS value,
    'percent' AS unit,
    CASE 
        WHEN rev.value_normalized IS NULL THEN 'missing_input'
        WHEN rev.value_normalized = 0 THEN 'denominator_zero'
        WHEN rev.eli_status = 'conflict' THEN 'conflict'
        WHEN rev.eli_status = 'unverified' THEN 'unverified'
        WHEN rd.eli_status = 'conflict' THEN 'conflict'
        WHEN rd.eli_status = 'unverified' THEN 'unverified'
        ELSE 'ok'
    END AS status,
    CASE 
        WHEN rev.value_normalized IS NULL THEN 'Missing required input: revenue'
        WHEN rev.value_normalized = 0 THEN 'Revenue denominator is zero'
        WHEN rev.eli_status = 'conflict' OR rd.eli_status = 'conflict' THEN 'Conflicting input values in filing'
        WHEN rev.eli_status = 'unverified' OR rd.eli_status = 'unverified' THEN 'Input failed accounting integrity check'
        WHEN rd.value_normalized IS NULL THEN 'Zero: company reports no R&D expense'
        ELSE NULL
    END AS reason,
    ARRAY_REMOVE(ARRAY[rd.line_item_id, rev.line_item_id], NULL) AS input_line_item_ids,
    %(basis)s AS basis,
    COALESCE(('R2' = ANY(rd.rule_ids_applied) OR 'R2' = ANY(rev.rule_ids_applied)), FALSE) AS restated,
    %(policy_version)s AS policy_version
FROM periods p
LEFT JOIN rd ON p.company_id = rd.company_id AND p.fiscal_year = rd.fiscal_year AND p.fiscal_quarter = rd.fiscal_quarter
LEFT JOIN rev ON p.company_id = rev.company_id AND p.fiscal_year = rev.fiscal_year AND p.fiscal_quarter = rev.fiscal_quarter
ORDER BY p.company_id, p.fiscal_year, p.fiscal_quarter;
