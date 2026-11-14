-- scripts/provenance.sql
-- Phase 2: Full provenance trace function and view
-- Maps any kpi_values row back through effective_line_items, line_items, filings, and raw_financial_rows

CREATE OR REPLACE VIEW v_kpi_provenance AS
SELECT 
    kv.id AS kpi_value_id,
    kv.company_id,
    c.name AS company_name,
    c.sector,
    kv.fiscal_year,
    kv.fiscal_quarter,
    kv.period_end,
    kv.kpi_id,
    kd.kpi_name,
    kd.formula,
    kv.value,
    kv.unit,
    kv.status AS kpi_status,
    kv.reason AS kpi_reason,
    kv.basis,
    kv.restated,
    kv.policy_version,
    kv.computed_at,
    eli.canonical_item,
    eli.status AS effective_status,
    eli.rule_ids_applied,
    eli.alternatives,
    li.id AS line_item_id,
    li.statement,
    li.value_normalized,
    li.scale_factor,
    li.sign_multiplier,
    li.original_value,
    li.original_unit,
    f.filing_id,
    f.form_type,
    f.filed_date,
    f.amends_filing_id,
    r.row_id,
    r.source_file,
    r.source_row_number,
    r.line_item_raw,
    r.value_raw,
    r.unit_raw,
    r.row_hash
FROM kpi_values kv
JOIN companies c ON kv.company_id = c.company_id
JOIN kpi_definitions kd ON kv.kpi_id = kd.kpi_id
CROSS JOIN LATERAL UNNEST(kv.input_line_item_ids) AS input_li_id
JOIN line_items li ON li.id = input_li_id
JOIN filings f ON li.filing_id = f.filing_id
JOIN raw_financial_rows r ON li.raw_row_id = r.row_id
JOIN effective_line_items eli 
  ON eli.company_id = kv.company_id 
 AND eli.canonical_item = li.canonical_item
 AND eli.basis = kv.basis 
 AND eli.policy_version = kv.policy_version
 AND (
      (eli.fiscal_year = kv.fiscal_year AND eli.fiscal_quarter = kv.fiscal_quarter)
      OR (kv.kpi_id = 'revenue_yoy_growth_pct' AND eli.fiscal_year = kv.fiscal_year - 1 AND eli.fiscal_quarter = kv.fiscal_quarter)
     );

-- Function to query provenance for a specific KPI ID
CREATE OR REPLACE FUNCTION get_kpi_provenance(target_kpi_value_id INT)
RETURNS SETOF v_kpi_provenance AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM v_kpi_provenance WHERE kpi_value_id = target_kpi_value_id;
END;
$$ LANGUAGE plpgsql STABLE;
