-- app/data/sql/kpis/opex_ratio_pct.sql
-- KPI: Operating expense ratio
-- Formula: (research_and_development + sales_and_marketing + general_and_administrative) / revenue * 100
-- Unit: percent (Excludes restructuring; R&D treated as 0 if company reports no R&D)

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
sm AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'sales_and_marketing' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
),
ga AS (
    SELECT eli.company_id, eli.fiscal_year, eli.fiscal_quarter, eli.status as eli_status,
           eli.rule_ids_applied, li.id as line_item_id, li.value_normalized
    FROM effective_line_items eli
    LEFT JOIN line_items li ON eli.effective_line_item_id = li.id
    WHERE eli.canonical_item = 'general_and_administrative' AND eli.basis = %(basis)s AND eli.policy_version = %(policy_version)s
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
    'opex_ratio_pct' AS kpi_id,
    CASE 
        WHEN rd.value_normalized IS NULL OR sm.value_normalized IS NULL OR ga.value_normalized IS NULL OR rev.value_normalized IS NULL THEN NULL
        WHEN rev.value_normalized = 0 THEN NULL
        WHEN rd.eli_status != 'ok' OR sm.eli_status != 'ok' OR ga.eli_status != 'ok' OR rev.eli_status != 'ok' THEN NULL
        WHEN 'R11' = ANY(rev.rule_ids_applied) THEN NULL
        ELSE ROUND(((rd.value_normalized + sm.value_normalized + ga.value_normalized) / rev.value_normalized) * 100, 6)
    END AS value,
    'percent' AS unit,
    CASE 
        WHEN 'R11' = ANY(rev.rule_ids_applied) THEN 'unverified'
        WHEN rd.eli_status = 'conflict' OR sm.eli_status = 'conflict' OR ga.eli_status = 'conflict' OR rev.eli_status = 'conflict' THEN 'conflict'
        WHEN rd.eli_status = 'unverified' OR sm.eli_status = 'unverified' OR ga.eli_status = 'unverified' OR rev.eli_status = 'unverified' THEN 'unverified'
        WHEN rd.value_normalized IS NULL OR sm.value_normalized IS NULL OR ga.value_normalized IS NULL OR rev.value_normalized IS NULL THEN 'missing_input'
        WHEN rev.value_normalized = 0 THEN 'denominator_zero'
        ELSE 'ok'
    END AS status,
    CASE 
        WHEN 'R11' = ANY(rev.rule_ids_applied) THEN 'Underlying filing failed accounting integrity check (R11)'
        WHEN rd.eli_status = 'conflict' OR sm.eli_status = 'conflict' OR ga.eli_status = 'conflict' OR rev.eli_status = 'conflict' THEN 'Conflicting input values in filing'
        WHEN rd.eli_status = 'unverified' OR sm.eli_status = 'unverified' OR ga.eli_status = 'unverified' OR rev.eli_status = 'unverified' THEN 'Input failed accounting integrity check'
        WHEN rd.value_normalized IS NULL OR sm.value_normalized IS NULL OR ga.value_normalized IS NULL OR rev.value_normalized IS NULL THEN 'Missing required inputs: research_and_development, sales_and_marketing, general_and_administrative, or revenue'
        WHEN rev.value_normalized = 0 THEN 'Revenue denominator is zero'
        ELSE NULL
    END AS reason,
    ARRAY_REMOVE(ARRAY[rd.line_item_id, sm.line_item_id, ga.line_item_id, rev.line_item_id], NULL) AS input_line_item_ids,
    %(basis)s AS basis,
    COALESCE(('R2' = ANY(rd.rule_ids_applied) OR 'R2' = ANY(sm.rule_ids_applied) OR 'R2' = ANY(ga.rule_ids_applied) OR 'R2' = ANY(rev.rule_ids_applied)), FALSE) AS restated,
    %(policy_version)s AS policy_version
FROM periods p
LEFT JOIN rd ON p.company_id = rd.company_id AND p.fiscal_year = rd.fiscal_year AND p.fiscal_quarter = rd.fiscal_quarter
LEFT JOIN sm ON p.company_id = sm.company_id AND p.fiscal_year = sm.fiscal_year AND p.fiscal_quarter = sm.fiscal_quarter
LEFT JOIN ga ON p.company_id = ga.company_id AND p.fiscal_year = ga.fiscal_year AND p.fiscal_quarter = ga.fiscal_quarter
LEFT JOIN rev ON p.company_id = rev.company_id AND p.fiscal_year = rev.fiscal_year AND p.fiscal_quarter = rev.fiscal_quarter
ORDER BY p.company_id, p.fiscal_year, p.fiscal_quarter;
