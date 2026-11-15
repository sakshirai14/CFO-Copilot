"""app/domain/kpi_service.py

Domain service for deterministic financial data retrieval.
Encapsulates all database SQL operations for KPI values, line items, and cross-company comparability.
Keeps app/agents/ completely clean of SQL keywords and database driver imports.
"""

import os
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import psycopg2
from app.core.config import get_settings
from app.domain.agent_envelope import FactItem


class KpiService:
    """Provides pure SQL-based deterministic retrieval of financial facts and comparability."""

    def __init__(self, is_test: bool = False):
        self.settings = get_settings()
        self.is_test = is_test
        self.conn_params = self.settings.get_connection_params(role="ro", is_test=is_test)

    def _get_connection(self):
        return psycopg2.connect(**self.conn_params)

    def get_kpi_facts(
        self,
        company_id: str,
        fiscal_year: int,
        fiscal_quarter: int,
        kpi_id: str,
        basis: str = "as_restated",
        policy_version: str = "v1.2.0"
    ) -> List[FactItem]:
        """Retrieves verified KPI fact(s) and underlying filing metadata from PostgreSQL."""
        facts: List[FactItem] = []
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # 1. Try querying kpi_values directly
                cur.execute("""
                    SELECT kv.id, kv.company_id, kv.fiscal_year, kv.fiscal_quarter, kv.kpi_id,
                           kv.value, kv.unit, kv.status, kv.reason, kv.basis, kv.restated,
                           kv.input_line_item_ids
                    FROM kpi_values kv
                    WHERE kv.company_id = %s AND kv.fiscal_year = %s AND kv.fiscal_quarter = %s
                      AND kv.kpi_id = %s AND kv.basis = %s AND kv.policy_version = %s;
                """, (company_id, fiscal_year, fiscal_quarter, kpi_id, basis, policy_version))
                row = cur.fetchone()

                if row:
                    (kvid, cid, fy, fq, kid, val, unit, status, reason, b_mode, restated, input_ids) = row
                    val_float = float(val) if val is not None else None

                    # Build CFO-grade human-readable fact text
                    if status == "ok" and val_float is not None:
                        if unit == "USD":
                            val_str = f"${val_float:,.0f}"
                        elif unit == "percent":
                            val_str = f"{val_float:.2f}%"
                        elif unit == "x":
                            val_str = f"{val_float:.2f}x"
                        else:
                            val_str = f"{val_float}"
                        text = f"{cid} FY{fy} Q{fq} {kid} was {val_str} ({unit}) under basis '{b_mode}'."
                    else:
                        text = f"{cid} FY{fy} Q{fq} {kid} is {status}: {reason or 'Value not available'}."

                    facts.append(FactItem(
                        fact_id=f"fact_{cid}_{fy}Q{fq}_{kid}",
                        company_id=cid,
                        fiscal_year=fy,
                        fiscal_quarter=fq,
                        kpi_id=kid,
                        value=val_float,
                        unit=unit,
                        basis=b_mode,
                        restated=bool(restated),
                        status=status,
                        reason=reason,
                        text=text,
                        input_line_item_ids=input_ids or []
                    ))

                # 2. If not found in kpi_values, check effective_line_items (e.g. for revenue, net_income)
                if not facts:
                    cur.execute("""
                        SELECT eli.id, eli.company_id, eli.fiscal_year, eli.fiscal_quarter,
                               eli.canonical_item, li.value_normalized, li.original_unit,
                               eli.status, eli.basis, li.filing_id, eli.effective_line_item_id
                        FROM effective_line_items eli
                        JOIN line_items li ON eli.effective_line_item_id = li.id
                        WHERE eli.company_id = %s AND eli.fiscal_year = %s AND eli.fiscal_quarter = %s
                          AND eli.canonical_item = %s AND eli.basis = %s AND eli.policy_version = %s;
                    """, (company_id, fiscal_year, fiscal_quarter, kpi_id, basis, policy_version))
                    li_row = cur.fetchone()
                    if li_row:
                        (elid, cid, fy, fq, citem, val_norm, orig_unit, stat, b_mode, fid, lid) = li_row
                        val_float = float(val_norm) if val_norm is not None else None
                        val_str = f"${val_float:,.0f}" if val_float is not None else "None"
                        text = f"{cid} FY{fy} Q{fq} {citem} was {val_str} (USD) from filing {fid}."
                        facts.append(FactItem(
                            fact_id=f"fact_{cid}_{fy}Q{fq}_{citem}",
                            company_id=cid,
                            fiscal_year=fy,
                            fiscal_quarter=fq,
                            canonical_item=citem,
                            kpi_id=citem,
                            value=val_float,
                            unit="USD",
                            basis=b_mode,
                            restated=False,
                            status=stat,
                            text=text,
                            source_filing=fid,
                            input_line_item_ids=[lid] if lid else []
                        ))
        finally:
            conn.close()
        return facts

    def check_cross_company_alignment(
        self,
        company_ids: List[str],
        fiscal_year: int,
        fiscal_quarter: int
    ) -> Tuple[bool, Optional[str]]:
        """Invokes PostgreSQL cross_company_comparability helper to verify Rule R7."""
        if len(company_ids) < 2:
            return True, None

        label = f"FY{fiscal_year}Q{fiscal_quarter}"
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT days_apart, aligned
                    FROM cross_company_comparability(%s, %s);
                """, (company_ids, label))
                row = cur.fetchone()
                if row:
                    days_apart, aligned = row
                    if not aligned:
                        warning = (
                            f"Rule R7 Fiscal Calendar Warning: Companies {company_ids} have misaligned reporting periods "
                            f"({days_apart} days apart) for label {label}."
                        )
                        return False, warning
        except Exception:
            pass
        finally:
            conn.close()
        return True, None
