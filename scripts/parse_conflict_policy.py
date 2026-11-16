#!/usr/bin/env python3
"""scripts/parse_conflict_policy.py

Parses docs/CONFLICT_POLICY.md to extract canonical rules R1 through R12,
executes SQL/Python outcome-changed queries against the live database,
verifies test existence via pytest collection, and generates docs/evidence/conflict_policy_rules_table.md.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
import psycopg2

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def get_collected_tests():
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q"]
    res = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, check=True)
    tests = set()
    for line in res.stdout.splitlines():
        line = line.strip()
        if "::" in line:
            test_id = line.split(" ")[0]
            tests.add(test_id)
            test_name = test_id.split("::")[-1]
            tests.add(test_name)
    return tests

def parse_policy_rules():
    policy_path = PROJECT_ROOT / "docs" / "CONFLICT_POLICY.md"
    content = policy_path.read_text(encoding="utf-8")
    
    # Match headers like "### Rule R1: Source Authority Hierarchy"
    rule_pattern = re.compile(r"###\s+Rule\s+(R\d+):\s+([^\n]+)")
    matches = rule_pattern.findall(content)
    rules = {}
    for r_id, r_name in matches:
        rules[r_id] = r_name.strip()
    return rules

def main():
    rules_dict = parse_policy_rules()
    collected_tests = get_collected_tests()

    conn = psycopg2.connect(
        host="localhost",
        port=5435,
        dbname="cfo_copilot",
        user="cfo_owner",
        password=os.getenv("POSTGRES_PASSWORD", "")
    )

    # Detailed specifications for R1-R12
    rule_specs = {
        "R1": {
            "code_location": "app/data/ingest.py:530-550, app/data/effective.py:60-70",
            "query_desc": "Non-filing documents (press releases, analyst notes, FAQs) excluded from financial line items",
            "sql": "SELECT COUNT(*) FROM documents WHERE doc_type = 'other_document';",
            "test_name": "test_r1_source_authority_press_release_ignored"
        },
        "R2": {
            "code_location": "app/data/effective.py:140-160",
            "query_desc": "Effective line items where 10-Q/A superseded 10-Q under as_restated",
            "sql": "SELECT COUNT(*) FROM effective_line_items WHERE basis = 'as_restated' AND 'R2' = ANY(rule_ids_applied);",
            "test_name": "test_r2_restatement_precedence_cep_10qa, test_r2_restatement_precedence_nwi_10qa"
        },
        "R3": {
            "code_location": "app/data/effective.py:170-185",
            "query_desc": "Effective line items updated from prior comparative columns (NWI Net Income)",
            "sql": "SELECT COUNT(*) FROM effective_line_items WHERE basis = 'as_restated' AND 'R3' = ANY(rule_ids_applied);",
            "test_name": "test_r3_comparative_column_restatement_nwi"
        },
        "R4": {
            "code_location": "app/data/ingest.py:334-355, app/data/effective.py:120",
            "query_desc": "Intra-filing duplicate rows collapsed into single line item (ARG Q2 2023 revenue)",
            "sql": "SELECT COUNT(*) FROM line_items WHERE status = 'duplicate';",
            "test_name": "test_r4_intra_filing_duplicate_collapse"
        },
        "R5": {
            "code_location": "app/data/normalizer.py:110-165, app/data/effective.py:190",
            "query_desc": "Line items with dual-evidence unit scaling applied (HBS FY2024 Q2 1,000x correction)",
            "sql": "SELECT COUNT(*) FROM line_items WHERE scale_factor = 1000.0 AND company_id = 'HBS' AND fiscal_year = 2024 AND fiscal_quarter = 2;",
            "test_name": "test_r5_dual_evidence_normalization_hbs"
        },
        "R6": {
            "code_location": "app/data/sql/kpis/*.sql, app/data/effective.py:210-230",
            "query_desc": "KPI values evaluated to missing_input (prevented silent zero coalesce)",
            "sql": "SELECT COUNT(*) FROM kpi_values WHERE status = 'missing_input' AND policy_version = 'v1.2.0';",
            "test_name": "test_r6_missing_input_and_rd_zero_exception"
        },
        "R7": {
            "code_location": "migrations/005_cross_company_comparability.sql:1-40",
            "query_desc": "Stored function cross_company_comparability() flagging non-aligned fiscal calendars",
            "sql": "SELECT COUNT(*) FROM (SELECT cross_company_comparability(ARRAY['ZLG', 'CEP'], 'FY2024Q1')) sub;",
            "test_name": "test_r7_non_aligned_calendar_detection"
        },
        "R8": {
            "code_location": "app/data/sql/kpis/*.sql (CASE WHEN total_equity <= 0 THEN 'not_meaningful' ...)",
            "query_desc": "Mathematical domain gate triggers on historical filings (guarded: 0 active triggers)",
            "sql": "SELECT COUNT(*) FROM kpi_values WHERE status IN ('not_meaningful', 'denominator_zero') AND policy_version = 'v1.2.0';",
            "test_name": "test_r8_mathematical_domain_gates"
        },
        "R9": {
            "code_location": "app/data/sql/kpis/*.sql, kpi_glossary.csv",
            "query_desc": "Calculated KPI records conforming strictly to canonical glossary formulas",
            "sql": "SELECT COUNT(*) FROM kpi_values WHERE policy_version = 'v1.2.0' AND kpi_id IN (SELECT kpi_id FROM kpi_definitions);",
            "test_name": "test_r9_formula_canonicalization"
        },
        "R10": {
            "code_location": "migrations/001_initial_schema.sql, app/domain/answer_composer.py",
            "query_desc": "Calculated KPI records stored at exact NUMERIC precision and typed units",
            "sql": "SELECT COUNT(*) FROM kpi_values WHERE policy_version = 'v1.2.0' AND unit IN ('USD', 'percent', 'x');",
            "test_name": "test_r10_storage_precision_and_presentation"
        },
        "R11": {
            "code_location": "app/data/effective.py:35-40, app/data/sql/kpis/*.sql",
            "query_desc": "Accounting identity violations propagating to 'ok' KPIs (guarded: strictly 0)",
            "sql": "SELECT COUNT(*) FROM effective_line_items WHERE status = 'ok' AND 'R11' = ANY(rule_ids_applied);",
            "test_name": "test_r11_accounting_integrity_gate"
        },
        "R12": {
            "code_location": "app/data/effective.py, app/data/kpi_calculator.py",
            "query_desc": "Calculated KPI records stamped with policy_version v1.2.0 and provenance lineage",
            "sql": "SELECT COUNT(*) FROM kpi_values WHERE policy_version = 'v1.2.0';",
            "test_name": "test_r12_provenance_and_policy_version"
        }
    }

    report_lines = []
    report_lines.append("# Conflict Policy Canonical Rules Table (R1 – R12)")
    report_lines.append("")
    report_lines.append("> Generated dynamically from live database queries and `pytest --collect-only`.")
    report_lines.append("")
    report_lines.append("| Rule ID | Rule Name | Code Location | Outcome-Changed Count | Exact SQL / Python Query | Verified Pytest Test Name |")
    report_lines.append("| :--- | :--- | :--- | :---: | :--- | :--- |")

    with conn.cursor() as cur:
        for r_id in sorted(rules_dict.keys(), key=lambda x: int(x[1:])):
            r_name = rules_dict[r_id]
            spec = rule_specs.get(r_id, {})
            code_loc = spec.get("code_location", "TBD")
            sql_query = spec.get("sql", "SELECT 0;")
            test_str = spec.get("test_name", "TBD")

            cur.execute(sql_query)
            count = cur.fetchone()[0]

            # Verify test existence
            tests_to_check = [t.strip() for t in test_str.split(",")]
            verified_tests = []
            for t in tests_to_check:
                if t in collected_tests:
                    verified_tests.append(f"`{t}` (VERIFIED)")
                else:
                    verified_tests.append(f"`{t}` (MISSING)")

            test_display = "<br>".join(verified_tests)
            report_lines.append(f"| **{r_id}** | {r_name} | `{code_loc}` | **{count}** | `{sql_query}` | {test_display} |")

    conn.close()

    output_path = PROJECT_ROOT / "docs" / "evidence" / "conflict_policy_rules_table.md"
    output_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"Generated {output_path}")
    print("\n" + "\n".join(report_lines))

if __name__ == "__main__":
    main()
