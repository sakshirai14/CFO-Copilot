"""app/data/provenance.py

Provenance inspection CLI for CFO Copilot.
Traces any KPI value back through effective line items, filing metadata,
and raw financial CSV rows with full cryptographic row-hash audit trail.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
import psycopg2

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings


def parse_period(period_str: str) -> tuple[int, int]:
    """Parses period strings like 'FY2024Q3', '2024Q3', 'FY2024-Q3', '2024-3'."""
    clean = period_str.upper().replace("FY", "").replace("-", "").replace(" ", "")
    if "Q" in clean:
        parts = clean.split("Q")
        return int(parts[0]), int(parts[1])
    raise ValueError(f"Unrecognized fiscal period format '{period_str}'. Expected e.g. 'FY2024Q3'.")


def format_currency_or_number(val: Optional[float], unit: str) -> str:
    if val is None:
        return "N/A"
    if unit == "USD":
        return f"${val:,.2f}"
    elif unit == "percent":
        return f"{val:.2f}%"
    elif unit == "x":
        return f"{val:.2f}x"
    return f"{val}"


def get_provenance_trace(
    conn,
    company_id: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    fiscal_quarter: Optional[int] = None,
    kpi_id: Optional[str] = None,
    basis: str = "as_restated",
    kpi_value_id: Optional[int] = None,
    policy_version: str = "v1.0.0"
) -> Dict[str, Any]:
    """Retrieves full provenance trace from database."""
    with conn.cursor() as cur:
        if kpi_value_id is not None:
            cur.execute("""
                SELECT 
                    kv.id, kv.company_id, c.name, c.sector, kv.fiscal_year, kv.fiscal_quarter,
                    kv.period_end, kv.kpi_id, kd.kpi_name, kd.formula, kv.value, kv.unit,
                    kv.status, kv.reason, kv.basis, kv.restated, kv.policy_version, kv.computed_at,
                    kv.input_line_item_ids
                FROM kpi_values kv
                JOIN companies c ON kv.company_id = c.company_id
                JOIN kpi_definitions kd ON kv.kpi_id = kd.kpi_id
                WHERE kv.id = %s;
            """, (kpi_value_id,))
        else:
            cur.execute("""
                SELECT 
                    kv.id, kv.company_id, c.name, c.sector, kv.fiscal_year, kv.fiscal_quarter,
                    kv.period_end, kv.kpi_id, kd.kpi_name, kd.formula, kv.value, kv.unit,
                    kv.status, kv.reason, kv.basis, kv.restated, kv.policy_version, kv.computed_at,
                    kv.input_line_item_ids
                FROM kpi_values kv
                JOIN companies c ON kv.company_id = c.company_id
                JOIN kpi_definitions kd ON kv.kpi_id = kd.kpi_id
                WHERE kv.company_id = %s AND kv.fiscal_year = %s AND kv.fiscal_quarter = %s
                  AND kv.kpi_id = %s AND kv.basis = %s AND kv.policy_version = %s;
            """, (company_id, fiscal_year, fiscal_quarter, kpi_id, basis, policy_version))

        kpi_row = cur.fetchone()
        if not kpi_row:
            return {"error": "KPI record not found"}

        kpi_info = {
            "kpi_value_id": kpi_row[0],
            "company_id": kpi_row[1],
            "company_name": kpi_row[2],
            "sector": kpi_row[3],
            "fiscal_year": kpi_row[4],
            "fiscal_quarter": kpi_row[5],
            "period_end": str(kpi_row[6]),
            "kpi_id": kpi_row[7],
            "kpi_name": kpi_row[8],
            "formula": kpi_row[9],
            "value": float(kpi_row[10]) if kpi_row[10] is not None else None,
            "unit": kpi_row[11],
            "status": kpi_row[12],
            "reason": kpi_row[13],
            "basis": kpi_row[14],
            "restated": kpi_row[15],
            "policy_version": kpi_row[16],
            "computed_at": str(kpi_row[17]),
            "input_line_item_ids": kpi_row[18]
        }

        # Query input line items provenance
        inputs_provenance = []
        if kpi_info["input_line_item_ids"]:
            cur.execute("""
                SELECT 
                    li.id, li.canonical_item, li.statement, li.value_normalized,
                    li.scale_factor, li.sign_multiplier, li.original_value, li.original_unit,
                    f.filing_id, f.form_type, f.filed_date, f.amends_filing_id,
                    r.row_id, r.source_file, r.source_row_number, r.line_item_raw, r.value_raw, r.unit_raw, r.row_hash,
                    eli.rule_ids_applied, eli.alternatives
                FROM line_items li
                JOIN filings f ON li.filing_id = f.filing_id
                JOIN raw_financial_rows r ON li.raw_row_id = r.row_id
                LEFT JOIN effective_line_items eli 
                  ON eli.effective_line_item_id = li.id 
                 AND eli.basis = %s 
                 AND eli.policy_version = %s
                WHERE li.id = ANY(%s)
                ORDER BY li.statement, li.canonical_item;
            """, (kpi_info["basis"], kpi_info["policy_version"], kpi_info["input_line_item_ids"]))

            for r in cur.fetchall():
                inputs_provenance.append({
                    "line_item_id": r[0],
                    "canonical_item": r[1],
                    "statement": r[2],
                    "value_normalized": float(r[3]),
                    "scale_factor": float(r[4]),
                    "sign_multiplier": r[5],
                    "original_value": float(r[6]),
                    "original_unit": r[7],
                    "filing_id": r[8],
                    "form_type": r[9],
                    "filed_date": str(r[10]),
                    "amends_filing_id": r[11],
                    "raw_row_id": r[12],
                    "source_file": r[13],
                    "source_row_number": r[14],
                    "line_item_raw": r[15],
                    "value_raw": r[16],
                    "unit_raw": r[17],
                    "row_hash": r[18],
                    "rule_ids_applied": r[19] or [],
                    "alternatives": r[20] or []
                })

        # Query any data quality issues touching these raw rows or filings
        issues = []
        raw_row_ids = [inp["raw_row_id"] for inp in inputs_provenance]
        filing_ids = list(set([inp["filing_id"] for inp in inputs_provenance]))
        if raw_row_ids or filing_ids:
            cur.execute("""
                SELECT issue_type, severity, filing_id, raw_row_id, description
                FROM data_quality_issues
                WHERE raw_row_id = ANY(%s) OR filing_id = ANY(%s)
                ORDER BY severity DESC;
            """, (raw_row_ids, filing_ids))
            for issue_row in cur.fetchall():
                issues.append({
                    "issue_type": issue_row[0],
                    "severity": issue_row[1],
                    "filing_id": issue_row[2],
                    "raw_row_id": issue_row[3],
                    "description": issue_row[4]
                })

        return {
            "kpi": kpi_info,
            "inputs": inputs_provenance,
            "data_quality_issues": issues
        }


def render_provenance_report(trace: Dict[str, Any]) -> str:
    """Formats provenance trace into structured CFO-ready report."""
    if "error" in trace:
        return f"[ERROR] {trace['error']}"

    kpi = trace["kpi"]
    inputs = trace["inputs"]
    issues = trace["data_quality_issues"]

    val_str = format_currency_or_number(kpi["value"], kpi["unit"])

    lines = []
    lines.append("=" * 80)
    lines.append(f"CFO COPILOT - FINANCIAL KPI PROVENANCE TRACE")
    lines.append("=" * 80)
    lines.append(f"Company:         {kpi['company_name']} ({kpi['company_id']}) - Sector: {kpi['sector']}")
    lines.append(f"Fiscal Period:   FY{kpi['fiscal_year']} Q{kpi['fiscal_quarter']} (Period End: {kpi['period_end']})")
    lines.append(f"KPI Identifier:  {kpi['kpi_id']} ({kpi['kpi_name']})")
    lines.append(f"Formula:         {kpi['formula']}")
    lines.append(f"Calculated Val:  {val_str} ({kpi['unit']})")
    lines.append(f"Status:          {kpi['status'].upper()} (Basis: {kpi['basis']}, Restated: {kpi['restated']})")
    if kpi["reason"]:
        lines.append(f"Status Reason:   {kpi['reason']}")
    lines.append(f"Policy Version:  {kpi['policy_version']} | Computed At: {kpi['computed_at']}")
    lines.append("-" * 80)

    if not inputs:
        lines.append("[No underlying input line items resolved for this KPI calculation]")
    else:
        lines.append(f"INPUT LINE ITEMS RESOLVED ({len(inputs)} inputs):")
        for idx, inp in enumerate(inputs, 1):
            lines.append(f"\n  [{idx}] Canonical Item: {inp['canonical_item']} (Statement: {inp['statement']})")
            lines.append(f"      Normalized Value:  ${inp['value_normalized']:,.2f}")
            lines.append(f"      Effective Rules:   {', '.join(inp['rule_ids_applied'])}")
            lines.append(f"      Source Filing:     {inp['filing_id']} ({inp['form_type']}, filed {inp['filed_date']})")
            if inp["amends_filing_id"]:
                lines.append(f"      Amends Filing:     {inp['amends_filing_id']}")
            lines.append(f"      Normalization:     Scale {inp['scale_factor']}x, Sign Multiplier {inp['sign_multiplier']}, Raw: {inp['value_raw']} {inp['unit_raw']}")
            lines.append(f"      Raw Source Row:    {inp['raw_row_id']} in '{inp['source_file']}' (line {inp['source_row_number']})")
            lines.append(f"      Raw Line Item:     \"{inp['line_item_raw']}\"")
            lines.append(f"      Row Hash (SHA256): {inp['row_hash']}")

            if inp["alternatives"]:
                lines.append(f"      Historical Values:")
                for alt in inp["alternatives"]:
                    lines.append(f"        - ${alt['value']:,.2f} originally reported in {alt['filing_id']} ({alt['form_type']} filed {alt['filed_date']})")

    if issues:
        lines.append("\n" + "-" * 80)
        lines.append(f"DATA QUALITY ISSUES AUDIT ({len(issues)} issues detected on underlying inputs/filings):")
        for iss in issues:
            lines.append(f"  * [{iss['severity'].upper()}] {iss['issue_type']} (Filing: {iss['filing_id']}): {iss['description']}")
    else:
        lines.append("\n" + "-" * 80)
        lines.append("DATA QUALITY ISSUES AUDIT: 0 integrity issues detected on inputs.")

    lines.append("=" * 80)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Query KPI provenance trace")
    parser.add_argument("--company", help="Company ID (e.g. ARG, CEP, NWI)")
    parser.add_argument("--period", help="Fiscal period (e.g. FY2024Q3, 2024Q3)")
    parser.add_argument("--kpi", help="KPI identifier (e.g. gross_margin_pct)")
    parser.add_argument("--basis", choices=["as_restated", "as_originally_reported"], default="as_restated", help="Reporting basis")
    parser.add_argument("--kpi-id", type=int, help="Direct lookup by kpi_values primary key")
    parser.add_argument("--json", action="store_true", help="Output raw JSON trace")
    parser.add_argument("--test", action="store_true", help="Query test database")

    args = parser.parse_args()

    if not args.kpi_id and not (args.company and args.period and args.kpi):
        parser.error("Either --kpi-id OR (--company, --period, and --kpi) must be provided.")

    fy, fq = (None, None)
    if args.period:
        fy, fq = parse_period(args.period)

    settings = get_settings()
    conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=args.test))

    try:
        trace = get_provenance_trace(
            conn=conn,
            company_id=args.company,
            fiscal_year=fy,
            fiscal_quarter=fq,
            kpi_id=args.kpi,
            basis=args.basis,
            kpi_value_id=args.kpi_id
        )
        if args.json:
            print(json.dumps(trace, indent=2))
        else:
            print(render_provenance_report(trace))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
