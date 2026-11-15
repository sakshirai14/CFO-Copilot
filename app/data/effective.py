"""app/data/effective.py

Set-based resolution of effective line items across SEC filings.
Implements Rules R1 through R5, R6, R11, R12 of docs/CONFLICT_POLICY.md.
Resolves both 'as_restated' and 'as_originally_reported' bases into effective_line_items.
"""

import json
import logging
from typing import Optional, Dict, Any, List
import psycopg2
from psycopg2.extras import execute_batch

from app.core.config import get_settings

logger = logging.getLogger("cfo_copilot.effective")


def build_effective_line_items(conn, policy_version: str = "v1.1.0") -> int:
    """Computes and populates effective_line_items table deterministically.
    
    Returns the total number of effective line items upserted.
    """
    with conn.cursor() as cur:
        # 1. Fetch all distinct canonical items required across the company periods
        cur.execute("SELECT DISTINCT canonical_item FROM line_items ORDER BY 1;")
        canonical_items = [r[0] for r in cur.fetchall()]

        # 2. Fetch all company fiscal quarters (72 distinct periods)
        cur.execute("""
            SELECT DISTINCT company_id, fiscal_year, fiscal_quarter
            FROM filings
            ORDER BY company_id, fiscal_year, fiscal_quarter;
        """)
        company_periods = cur.fetchall()

        # 3. Fetch filings with known accounting identity failures (Rule R11)
        cur.execute("""
            SELECT DISTINCT filing_id, description
            FROM data_quality_issues
            WHERE severity = 'critical' AND issue_type LIKE '%identity%' AND filing_id IS NOT NULL;
        """)
        failing_filings = {r[0]: r[1] for r in cur.fetchall()}

        # 4. Fetch all non-duplicate candidate line items with filing metadata
        cur.execute("""
            SELECT 
                li.id as line_item_id,
                li.company_id,
                li.fiscal_year,
                li.fiscal_quarter,
                li.canonical_item,
                li.value_normalized,
                li.scale_factor,
                li.sign_multiplier,
                li.status as item_status,
                f.filing_id,
                f.form_type,
                f.filed_date,
                f.amends_filing_id,
                f.fiscal_year as filing_fy,
                f.fiscal_quarter as filing_fq
            FROM line_items li
            JOIN filings f ON li.filing_id = f.filing_id
            WHERE li.status != 'duplicate'
            ORDER BY li.company_id, li.fiscal_year, li.fiscal_quarter, li.canonical_item, f.filed_date ASC;
        """)
        all_candidates = cur.fetchall()

    # Index candidates by (company_id, fiscal_year, fiscal_quarter, canonical_item)
    candidates_map: Dict[tuple, List[Dict[str, Any]]] = {}
    for row in all_candidates:
        key = (row[1], row[2], row[3], row[4])
        cand = {
            "line_item_id": row[0],
            "company_id": row[1],
            "fiscal_year": row[2],
            "fiscal_quarter": row[3],
            "canonical_item": row[4],
            "value_normalized": row[5],
            "scale_factor": row[6],
            "sign_multiplier": row[7],
            "item_status": row[8],
            "filing_id": row[9],
            "form_type": row[10],
            "filed_date": row[11],
            "amends_filing_id": row[12],
            "filing_fy": row[13],
            "filing_fq": row[14],
        }
        candidates_map.setdefault(key, []).append(cand)

    records_to_insert = []

    for comp_id, fy, fq in company_periods:
        for item in canonical_items:
            key = (comp_id, fy, fq, item)
            cands = candidates_map.get(key, [])

            # --- A. Determine Original Line Item (as_originally_reported) ---
            # Original filing is where amends_filing_id IS NULL and period matches filing period
            orig_cands = [
                c for c in cands
                if c["amends_filing_id"] is None
                and c["filing_fy"] == fy
                and c["filing_fq"] == fq
            ]

            if not orig_cands and cands:
                # If no matching filing_period, pick earliest filed date candidate
                orig_cands = sorted(cands, key=lambda x: (x["filed_date"], x["line_item_id"]))

            if orig_cands:
                orig_item = orig_cands[0]
                rule_ids_orig = ["R1"]
                if orig_item["scale_factor"] != 1.0 or orig_item["sign_multiplier"] != 1:
                    rule_ids_orig.append("R5")

                status_orig = "ok"
                if orig_item["item_status"] == "flagged":
                    status_orig = "unverified"
                elif orig_item["item_status"] == "conflict":
                    status_orig = "conflict"

                records_to_insert.append((
                    comp_id, fy, fq, item, orig_item["line_item_id"],
                    "as_originally_reported",
                    rule_ids_orig,
                    status_orig,
                    json.dumps([]),
                    policy_version
                ))
            else:
                # Missing input
                records_to_insert.append((
                    comp_id, fy, fq, item, None,
                    "as_originally_reported",
                    ["R6"],
                    "missing_input",
                    json.dumps([]),
                    policy_version
                ))

            # --- B. Determine Restated Line Item (as_restated) ---
            if not cands:
                records_to_insert.append((
                    comp_id, fy, fq, item, None,
                    "as_restated",
                    ["R6"],
                    "missing_input",
                    json.dumps([]),
                    policy_version
                ))
                continue

            # Sort candidates by filed_date DESC, form_type (amendments first) DESC, id DESC
            restated_cands = sorted(
                cands,
                key=lambda x: (
                    x["filed_date"],
                    1 if x["form_type"] in ("10-Q/A", "10-K/A") else 0,
                    x["line_item_id"]
                ),
                reverse=True
            )
            winning = restated_cands[0]

            rule_ids_restated = ["R1"]
            alternatives = []
            is_restated = False

            # Check if winning candidate is from an amendment or comparative column
            orig_match = orig_cands[0] if orig_cands else None
            if orig_match and (winning["filing_id"] != orig_match["filing_id"] or winning["filed_date"] > orig_match["filed_date"]):
                if winning["form_type"] in ("10-Q/A", "10-K/A") or winning["amends_filing_id"]:
                    rule_ids_restated.append("R2")
                    is_restated = True
                elif winning["filing_fy"] != fy or winning["filing_fq"] != fq:
                    rule_ids_restated.extend(["R2", "R3"])
                    is_restated = True

                if winning["value_normalized"] != orig_match["value_normalized"]:
                    alternatives.append({
                        "filing_id": orig_match["filing_id"],
                        "form_type": orig_match["form_type"],
                        "filed_date": str(orig_match["filed_date"]),
                        "value": float(orig_match["value_normalized"]),
                        "reason": "as_originally_reported"
                    })

            # Check normalization rule R5
            if winning["scale_factor"] != 1.0 or winning["sign_multiplier"] != 1:
                rule_ids_restated.append("R5")

            # Check Rule R11 (Accounting integrity check on winning filing)
            if winning["filing_id"] in failing_filings:
                rule_ids_restated.append("R11")

            status_restated = "ok"
            if winning["item_status"] == "flagged":
                status_restated = "unverified"
            elif winning["item_status"] == "conflict":
                status_restated = "conflict"

            records_to_insert.append((
                comp_id, fy, fq, item, winning["line_item_id"],
                "as_restated",
                rule_ids_restated,
                status_restated,
                json.dumps(alternatives),
                policy_version
            ))

    # 5. Upsert into effective_line_items
    upsert_sql = """
        INSERT INTO effective_line_items (
            company_id, fiscal_year, fiscal_quarter, canonical_item, effective_line_item_id,
            basis, rule_ids_applied, status, alternatives, policy_version
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (company_id, fiscal_year, fiscal_quarter, canonical_item, basis, policy_version)
        DO UPDATE SET
            effective_line_item_id = EXCLUDED.effective_line_item_id,
            rule_ids_applied = EXCLUDED.rule_ids_applied,
            status = EXCLUDED.status,
            alternatives = EXCLUDED.alternatives,
            created_at = NOW();
    """

    with conn.cursor() as cur:
        execute_batch(cur, upsert_sql, records_to_insert, page_size=500)
    conn.commit()

    logger.info(f"Successfully populated {len(records_to_insert)} effective line items (policy_version={policy_version}).")
    return len(records_to_insert)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    conn_params = settings.get_connection_params(role="rw", is_test=False)
    conn = psycopg2.connect(**conn_params)
    try:
        count = build_effective_line_items(conn)
        print(f"Populated {count} effective line items in main DB.")
    finally:
        conn.close()
