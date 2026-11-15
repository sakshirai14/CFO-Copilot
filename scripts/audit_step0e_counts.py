#!/usr/bin/env python3
"""scripts/audit_step0e_counts.py
Examine rule table counts, R1 column existence, R4 duplicates, R11 issues, and search ARG filing text.
"""

import psycopg2
import re
from pathlib import Path
from app.core.config import get_settings

def run_queries():
    settings = get_settings()
    params = settings.get_connection_params(role="owner")
    conn = psycopg2.connect(**params)
    cur = conn.cursor()

    print("=== 1. STATUS COUNTS ===")
    cur.execute("""
        SELECT status, count(*) 
        FROM kpi_values 
        WHERE policy_version = 'v1.2.0' 
        GROUP BY status;
    """)
    for row in cur.fetchall():
        print(f"Status: {row[0]} | Count: {row[1]}")

    print("\n=== 2. MISSING INPUT BREAKDOWN ===")
    cur.execute("""
        SELECT kpi_id, basis, count(*) 
        FROM kpi_values 
        WHERE policy_version = 'v1.2.0' AND status = 'missing_input' 
        GROUP BY kpi_id, basis 
        ORDER BY kpi_id, basis;
    """)
    for row in cur.fetchall():
        print(f"KPI: {row[0]} | Basis: {row[1]} | Count: {row[2]}")

    print("\n=== 3. R4 DUPLICATES IN LINE_ITEMS ===")
    cur.execute("""
        SELECT column_name FROM information_schema.columns WHERE table_name = 'line_items';
    """)
    cols = [r[0] for r in cur.fetchall()]
    print("line_items columns:", cols)

    cur.execute("""
        SELECT count(*) FROM line_items WHERE status = 'duplicate';
    """)
    print("line_items duplicates count:", cur.fetchone()[0])

    cur.execute("""
        SELECT * FROM line_items WHERE status = 'duplicate';
    """)
    for row in cur.fetchall():
        print("  Duplicate row:", row)

    print("\n=== 4. R11 ACCOUNTING IDENTITY FAILURES ===")
    cur.execute("""
        SELECT filing_id, issue_type, description, severity 
        FROM data_quality_issues 
        WHERE issue_type = 'accounting_identity_failure';
    """)
    r11_rows = cur.fetchall()
    print("R11 issue count:", len(r11_rows))
    for row in r11_rows:
        print(f"  Filing: {row[0]} | Severity: {row[3]} | Desc: {row[2]}")

    print("\n=== 5. R1 TABLE SCHEMA CHECK ===")
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'raw_financial_rows';
    """)
    raw_cols = [r[0] for r in cur.fetchall()]
    print("Columns in raw_financial_rows:", raw_cols)

    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'filings';
    """)
    filing_cols = [r[0] for r in cur.fetchall()]
    print("Columns in filings:", filing_cols)

    cur.execute("""
        SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
    """)
    print("\nTables in public schema:", [r[0] for r in cur.fetchall()])

    cur.execute("""
        SELECT count(*) FROM filings WHERE form_type NOT IN ('10-K', '10-Q', '10-Q/A');
    """)
    print("Non-filing count in filings:", cur.fetchone()[0])

    cur.execute("""
        SELECT filing_id, form_type, reporting_unit 
        FROM filings;
    """)
    for row in cur.fetchall():
        if row[1] not in ('10-K', '10-Q', '10-Q/A'):
            print(f"  Non-filing Doc: {row[0]} | Type: {row[1]} | Unit: {row[2]}")

    conn.close()

if __name__ == "__main__":
    run_queries()
