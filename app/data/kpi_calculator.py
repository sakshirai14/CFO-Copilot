"""app/data/kpi_calculator.py

Executes pure SQL KPI definitions, computes 16 standard KPIs across all companies/periods,
populates kpi_values table, and asserts provenance integrity.
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, List
import psycopg2
from psycopg2.extras import execute_batch

from app.core.config import get_settings
from app.data.effective import build_effective_line_items

logger = logging.getLogger("cfo_copilot.kpis")

KPI_SQL_DIR = Path(__file__).parent / "sql" / "kpis"

KPI_NAMES = [
    "gross_margin_pct",
    "operating_margin_pct",
    "net_margin_pct",
    "ebitda_usd",
    "ebitda_margin_pct",
    "current_ratio_x",
    "debt_to_equity_x",
    "roe_quarterly_pct",
    "free_cash_flow_usd",
    "fcf_margin_pct",
    "revenue_yoy_growth_pct",
    "opex_ratio_pct",
    "interest_coverage_x",
    "asset_turnover_x",
    "rd_intensity_pct",
    "working_capital_usd",
]


def verify_provenance_integrity(conn, policy_version: str = "v1.1.0") -> int:
    """SQL Assertion: Asserts zero status='ok' KPI values depend on non-effective inputs."""
    assertion_sql = """
        SELECT COUNT(*)
        FROM kpi_values kv
        CROSS JOIN LATERAL UNNEST(kv.input_line_item_ids) AS input_id
        LEFT JOIN effective_line_items eli 
          ON eli.company_id = kv.company_id 
         AND (
              (eli.fiscal_year = kv.fiscal_year AND eli.fiscal_quarter = kv.fiscal_quarter)
              OR (kv.kpi_id = 'revenue_yoy_growth_pct' AND eli.fiscal_year = kv.fiscal_year - 1 AND eli.fiscal_quarter = kv.fiscal_quarter)
             )
         AND eli.basis = kv.basis 
         AND eli.policy_version = kv.policy_version 
         AND eli.effective_line_item_id = input_id
        WHERE kv.status = 'ok'
          AND kv.policy_version = %s
          AND eli.id IS NULL;
    """
    with conn.cursor() as cur:
        cur.execute(assertion_sql, (policy_version,))
        violation_count = cur.fetchone()[0]

    if violation_count > 0:
        raise ValueError(
            f"CRITICAL INTEGRITY VIOLATION: {violation_count} status='ok' KPI values depend on non-effective line items!"
        )
    return violation_count


def compute_all_kpis(conn, policy_version: str = "v1.1.0", run_id: str = None) -> Dict[str, Any]:
    """Runs all 16 KPI SQL definitions for both bases and persists to kpi_values."""
    if run_id is None:
        run_id = f"run_{uuid.uuid4().hex[:12]}"

    # Step 1: Ensure effective line items are updated
    build_effective_line_items(conn, policy_version=policy_version)

    upsert_sql = """
        INSERT INTO kpi_values (
            company_id, fiscal_year, fiscal_quarter, period_end, kpi_id,
            value, unit, status, reason, input_line_item_ids, basis, restated, policy_version, run_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (company_id, fiscal_year, fiscal_quarter, kpi_id, basis, policy_version)
        DO UPDATE SET
            value = EXCLUDED.value,
            unit = EXCLUDED.unit,
            status = EXCLUDED.status,
            reason = EXCLUDED.reason,
            input_line_item_ids = EXCLUDED.input_line_item_ids,
            restated = EXCLUDED.restated,
            run_id = EXCLUDED.run_id,
            computed_at = NOW();
    """

    total_inserted = 0
    kpi_records_batch = []

    for kpi_id in KPI_NAMES:
        sql_file = KPI_SQL_DIR / f"{kpi_id}.sql"
        if not sql_file.exists():
            raise FileNotFoundError(f"Missing SQL definition for KPI: {sql_file}")

        with open(sql_file, "r") as f:
            query = f.read()

        for basis in ["as_restated", "as_originally_reported"]:
            with conn.cursor() as cur:
                cur.execute(query, {"basis": basis, "policy_version": policy_version})
                rows = cur.fetchall()

            for r in rows:
                kpi_records_batch.append((
                    r[0],   # company_id
                    r[1],   # fiscal_year
                    r[2],   # fiscal_quarter
                    r[3],   # period_end
                    r[4],   # kpi_id
                    r[5],   # value
                    r[6],   # unit
                    r[7],   # status
                    r[8],   # reason
                    r[9],   # input_line_item_ids
                    r[10],  # basis
                    r[11],  # restated
                    r[12],  # policy_version
                    run_id  # run_id
                ))

    with conn.cursor() as cur:
        execute_batch(cur, upsert_sql, kpi_records_batch, page_size=1000)
    conn.commit()

    total_inserted = len(kpi_records_batch)

    # Step 3: Assert provenance integrity
    verify_provenance_integrity(conn, policy_version=policy_version)

    logger.info(f"Successfully computed and stored {total_inserted} KPI values (run_id={run_id}).")
    return {
        "run_id": run_id,
        "policy_version": policy_version,
        "total_computed": total_inserted,
        "provenance_violations": 0
    }
