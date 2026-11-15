"""app/data/chunker.py

Phase 3 Deterministic Chunking Engine for CFO Copilot.
Implements:
- Section-boundary text chunking with structured context headers.
- Materialized financial table chunks from effective_line_items (R2 resolved values).
- Chunk-time prompt injection & adversarial payload detection.
- Tenant private document chunking under Row-Level Security.
- Idempotent database persistence (stamped with chunker_version).
"""

import hashlib
import json
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import psycopg2
from psycopg2.extras import execute_values

from app.core.config import get_settings
from app.data.normalizer import audit_document_security

CHUNKER_VERSION = "v1.0.0"

STATEMENT_NAMES = {
    "IS": "Income Statement",
    "BS": "Balance Sheet",
    "CF": "Cash Flow Statement",
}

COMPANY_FULL_NAMES = {
    "ARG": "Aurora Retail Group",
    "CEP": "Cobalt Energy Partners",
    "HBS": "Helix BioSystems",
    "MSI": "Meridian Software Inc.",
    "NWI": "Northwind Industrial Corp",
    "ZLG": "Zephyr Logistics Ltd.",
}

STATEMENT_KEYWORDS = {
    "IS": "revenue, gross margin, operating margin, net margin, ebitda, gross profit, operating income, net income, tax, interest, opex, rd intensity",
    "BS": "current ratio, debt to equity, return on equity roe, current assets, current liabilities, total debt, total equity, cash, working capital",
    "CF": "free cash flow, operating cash flow, capital expenditures capex",
}


@dataclass
class Chunk:
    chunk_id: str
    chunk_kind: str  # 'text' or 'table'
    company_id: Optional[str]
    doc_id: Optional[str]
    filing_id: Optional[str]
    doc_type: Optional[str]
    fiscal_year: Optional[int]
    fiscal_quarter: Optional[int]
    section: Optional[str]
    chunk_index: int
    authority_rank: int
    trust_level: str
    quarantined: bool
    risk_flags: List[str]
    content_hash: str
    text: str
    chunk_text: str
    chunker_version: str = CHUNKER_VERSION
    tenant_id: Optional[str] = None


def format_amount(val: Any) -> str:
    """Formats numeric values cleanly for markdown table display."""
    if val is None:
        return "N/A"
    try:
        d = Decimal(str(val))
        if d == d.to_integral():
            return f"{int(d):,}"
        return f"{d:,.2f}"
    except Exception:
        return str(val)


def build_text_chunks_from_documents(conn) -> List[Chunk]:
    """Chunks all documents in the documents table on section boundaries."""
    chunks = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT doc_id, company_id, doc_type, form_type, fiscal_year, fiscal_quarter,
                   authority_rank, trust_level, text
            FROM documents
            ORDER BY doc_id;
        """)
        docs = cur.fetchall()

    for doc_id, company_id, doc_type, form_type, fiscal_year, fiscal_quarter, authority_rank, doc_trust, full_text in docs:
        lines = full_text.split("\n")
        sections: List[Tuple[str, str]] = []
        current_section = "HEADER"
        current_lines: List[str] = []

        for line in lines:
            line_str = line.strip()
            if line_str.startswith("===") and line_str.endswith("==="):
                if current_lines:
                    sec_body = "\n".join(current_lines).strip()
                    if sec_body:
                        sections.append((current_section, sec_body))
                    current_lines = []
                current_section = line_str.strip("=").strip()
            else:
                current_lines.append(line)

        if current_lines:
            sec_body = "\n".join(current_lines).strip()
            if sec_body:
                sections.append((current_section, sec_body))

        # Build chunks for each section
        comp_name = COMPANY_FULL_NAMES.get(company_id, company_id or "")
        for idx, (section_name, section_body) in enumerate(sections, start=1):
            chunk_id = f"{doc_id}#c{idx}"
            period_part = f" | fiscal {fiscal_year} quarter {fiscal_quarter}" if fiscal_year and fiscal_quarter else ""
            header_prefix = f"[{comp_name} ({company_id}) {doc_id}{period_part} | {section_name}]:\n"
            chunk_text = header_prefix + section_body

            # Chunk-level injection detection
            chunk_trust, chunk_flags, _ = audit_document_security(chunk_text)
            is_quarantined = (chunk_trust == "quarantined")

            content_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
            filing_id = doc_id if doc_type == "filing" else None

            chunks.append(Chunk(
                chunk_id=chunk_id,
                chunk_kind="text",
                company_id=company_id,
                doc_id=doc_id,
                filing_id=filing_id,
                doc_type=doc_type,
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
                section=section_name,
                chunk_index=idx,
                authority_rank=authority_rank,
                trust_level=chunk_trust,
                quarantined=is_quarantined,
                risk_flags=chunk_flags,
                content_hash=content_hash,
                text=chunk_text,
                chunk_text=chunk_text,
                chunker_version=CHUNKER_VERSION,
                tenant_id=None,
            ))

    return chunks


def build_table_chunks_from_effective_line_items(conn, policy_version: str = "v1.1.0") -> List[Chunk]:
    """Builds structured markdown table chunks from effective_line_items (as_restated)."""
    chunks = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT e.company_id, e.fiscal_year, e.fiscal_quarter, l.statement,
                   e.canonical_item, l.value_normalized, l.original_unit,
                   e.rule_ids_applied, e.alternatives, l.filing_id
            FROM effective_line_items e
            JOIN line_items l ON e.effective_line_item_id = l.id
            WHERE e.basis = 'as_restated' AND e.policy_version = %s
            ORDER BY e.company_id, e.fiscal_year, e.fiscal_quarter, l.statement, e.canonical_item;
        """, (policy_version,))
        rows = cur.fetchall()

    # Group by (company_id, fiscal_year, fiscal_quarter, statement)
    groups: Dict[Tuple[str, int, int, str], List[Dict[str, Any]]] = {}
    for comp, fy, fq, stmt, canon, val_norm, orig_unit, rules, alts, fil_id in rows:
        key = (comp, fy, fq, stmt)
        if key not in groups:
            groups[key] = []
        groups[key].append({
            "canonical_item": canon,
            "value_normalized": val_norm,
            "original_unit": orig_unit,
            "rules": rules or [],
            "alternatives": alts or [],
            "filing_id": fil_id,
        })

    for (comp, fy, fq, stmt), items in groups.items():
        comp_name = COMPANY_FULL_NAMES.get(comp, comp)
        metric_keywords = STATEMENT_KEYWORDS.get(stmt, "")
        stmt_full = STATEMENT_NAMES.get(stmt, stmt)
        chunk_id = f"{comp}_{fy}Q{fq}_{stmt}#t1"
        primary_filing = items[0]["filing_id"] if items else f"{comp}-FY{fy}Q{fq}"

        # Build clean markdown table with distinctive statement and period identification
        md_lines = [
            f"[{comp} {primary_filing} | {stmt_full} Table (as_restated)]:",
            f"Company: {comp_name} ({comp}) | Period: fiscal {fy} quarter {fq} (FY{fy} Q{fq}) | Statement: {stmt_full} Table | Key Metrics: {metric_keywords} | Basis: as_restated",
            "",
            "| Canonical Item | Normalized Value (USD) | Units | Restatement Note |",
            "|:---|---:|:---|:---|",
        ]

        for item in items:
            c_name = item["canonical_item"]
            formatted_val = format_amount(item["value_normalized"])
            restatement_note = "-"
            if "R2" in item["rules"] and item["alternatives"]:
                orig_val = item["alternatives"][0].get("value")
                if orig_val is not None:
                    restatement_note = f"as restated, originally ${format_amount(orig_val)}"
                else:
                    restatement_note = "as restated"

            md_lines.append(f"| {c_name} | {formatted_val} | USD | {restatement_note} |")

        table_text = "\n".join(md_lines)
        content_hash = hashlib.sha256(table_text.encode("utf-8")).hexdigest()

        chunks.append(Chunk(
            chunk_id=chunk_id,
            chunk_kind="table",
            company_id=comp,
            doc_id=primary_filing,
            filing_id=primary_filing,
            doc_type="filing",
            fiscal_year=fy,
            fiscal_quarter=fq,
            section=stmt_full,
            chunk_index=1,
            authority_rank=1,
            trust_level="trusted",
            quarantined=False,
            risk_flags=[],
            content_hash=content_hash,
            text=table_text,
            chunk_text=table_text,
            chunker_version=CHUNKER_VERSION,
            tenant_id=None,
        ))

    return chunks


def build_tenant_chunks(conn) -> List[Chunk]:
    """Chunks tenant private documents under their respective tenant context."""
    chunks = []
    settings = get_settings()
    tenants = [t.strip() for t in settings.TENANTS.split(",") if t.strip()]

    with conn.cursor() as cur:
        for tenant in tenants:
            cur.execute("SET LOCAL app.current_tenant = %s;", (tenant,))
            cur.execute("""
                SELECT id, tenant_id, title, doc_text, content_hash
                FROM tenant_documents
                ORDER BY id;
            """)
            tenant_docs = cur.fetchall()

            for doc_pk, t_id, title, doc_text, _ in tenant_docs:
                chunk_id = f"tenant_{t_id}_{doc_pk}#c1"
                chunk_text = f"[{t_id.upper()} PRIVATE | {title}]:\n{doc_text}"
                content_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()

                chunk_trust, chunk_flags, _ = audit_document_security(chunk_text)
                is_quarantined = (chunk_trust == "quarantined")

                chunks.append(Chunk(
                    chunk_id=chunk_id,
                    chunk_kind="text",
                    company_id=None,
                    doc_id=f"tenant_doc_{doc_pk}",
                    filing_id=None,
                    doc_type="tenant_document",
                    fiscal_year=None,
                    fiscal_quarter=None,
                    section="PRIVATE_DOCUMENT",
                    chunk_index=1,
                    authority_rank=1,
                    trust_level=chunk_trust,
                    quarantined=is_quarantined,
                    risk_flags=chunk_flags,
                    content_hash=content_hash,
                    text=chunk_text,
                    chunk_text=chunk_text,
                    chunker_version=CHUNKER_VERSION,
                    tenant_id=t_id,
                ))

    return chunks


def save_chunks_to_db(chunks: List[Chunk], conn) -> int:
    """Idempotently saves chunks into the chunks table in PostgreSQL."""
    insert_sql = """
        INSERT INTO chunks (
            chunk_id, chunk_kind, company_id, doc_id, filing_id, doc_type,
            fiscal_year, fiscal_quarter, section, chunk_index, authority_rank,
            trust_level, quarantined, risk_flags, content_hash, text, chunk_text,
            chunker_version, tenant_id
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (chunk_id) DO UPDATE SET
            chunk_kind = EXCLUDED.chunk_kind,
            company_id = EXCLUDED.company_id,
            doc_id = EXCLUDED.doc_id,
            filing_id = EXCLUDED.filing_id,
            doc_type = EXCLUDED.doc_type,
            fiscal_year = EXCLUDED.fiscal_year,
            fiscal_quarter = EXCLUDED.fiscal_quarter,
            section = EXCLUDED.section,
            chunk_index = EXCLUDED.chunk_index,
            authority_rank = EXCLUDED.authority_rank,
            trust_level = EXCLUDED.trust_level,
            quarantined = EXCLUDED.quarantined,
            risk_flags = EXCLUDED.risk_flags,
            content_hash = EXCLUDED.content_hash,
            text = EXCLUDED.text,
            chunk_text = EXCLUDED.chunk_text,
            chunker_version = EXCLUDED.chunker_version,
            tenant_id = EXCLUDED.tenant_id;
    """

    # Group chunks by tenant_id for RLS compliance
    public_chunks = [c for c in chunks if c.tenant_id is None]
    tenant_chunks_by_tenant: Dict[str, List[Chunk]] = {}
    for c in chunks:
        if c.tenant_id is not None:
            tenant_chunks_by_tenant.setdefault(c.tenant_id, []).append(c)

    saved_count = 0
    with conn.cursor() as cur:
        # 1. Insert public chunks
        for c in public_chunks:
            cur.execute(insert_sql, (
                c.chunk_id, c.chunk_kind, c.company_id, c.doc_id, c.filing_id, c.doc_type,
                c.fiscal_year, c.fiscal_quarter, c.section, c.chunk_index, c.authority_rank,
                c.trust_level, c.quarantined, c.risk_flags, c.content_hash, c.text, c.chunk_text,
                c.chunker_version, c.tenant_id
            ))
            saved_count += 1

        # 2. Insert tenant chunks with SET LOCAL app.current_tenant
        for tenant_id, t_chunks in tenant_chunks_by_tenant.items():
            cur.execute("SET LOCAL app.current_tenant = %s;", (tenant_id,))
            for c in t_chunks:
                cur.execute(insert_sql, (
                    c.chunk_id, c.chunk_kind, c.company_id, c.doc_id, c.filing_id, c.doc_type,
                    c.fiscal_year, c.fiscal_quarter, c.section, c.chunk_index, c.authority_rank,
                    c.trust_level, c.quarantined, c.risk_flags, c.content_hash, c.text, c.chunk_text,
                    c.chunker_version, c.tenant_id
                ))
                saved_count += 1

    conn.commit()
    return saved_count


def run_chunking_pipeline(is_test: bool = False) -> Dict[str, Any]:
    """Executes the full deterministic chunking pipeline."""
    settings = get_settings()
    db_name = settings.POSTGRES_TEST_DB if is_test else settings.POSTGRES_DB
    print(f"[chunker] Running chunking pipeline on database '{db_name}'...")

    conn = psycopg2.connect(**settings.get_connection_params(role="rw", is_test=is_test))
    try:
        text_chunks = build_text_chunks_from_documents(conn)
        table_chunks = build_table_chunks_from_effective_line_items(conn, policy_version="v1.1.0")
        tenant_chunks = build_tenant_chunks(conn)

        all_chunks = text_chunks + table_chunks + tenant_chunks
        saved = save_chunks_to_db(all_chunks, conn)

        quarantined = [c.chunk_id for c in all_chunks if c.quarantined]

        stats = {
            "total_chunks": len(all_chunks),
            "text_chunks": len(text_chunks),
            "table_chunks": len(table_chunks),
            "tenant_chunks": len(tenant_chunks),
            "quarantined_chunks_count": len(quarantined),
            "quarantined_chunk_ids": quarantined,
            "chunker_version": CHUNKER_VERSION,
        }

        print(f"[chunker] Successfully chunked and stored {saved} chunks:")
        print(f"  - Text chunks:   {len(text_chunks)}")
        print(f"  - Table chunks:  {len(table_chunks)}")
        print(f"  - Tenant chunks: {len(tenant_chunks)}")
        print(f"  - Quarantined:   {len(quarantined)} {quarantined}")
        return stats

    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run deterministic chunking pipeline")
    parser.add_argument("--test", action="store_true", help="Run against test database")
    args = parser.parse_args()
    run_chunking_pipeline(is_test=args.test)
