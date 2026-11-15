"""app/data/retrieval.py

Database Access Layer for Hybrid Retrieval (Foundation Locks 6, 7 & 8).
All SQL queries for vector search, full-text search (FTS), and snapshot persistence
live exclusively in this module.
"""

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import psycopg2


def build_filter_clause(
    company_id: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    fiscal_quarter: Optional[int] = None,
    doc_type: Optional[str] = None,
    chunk_kind: Optional[str] = None,
    include_quarantined: bool = False,
) -> Tuple[str, List[Any]]:
    """Builds parameterized WHERE clauses for chunk filtering."""
    clauses = []
    params = []

    if not include_quarantined:
        clauses.append("quarantined = FALSE")

    if company_id:
        clauses.append("company_id = %s")
        params.append(company_id)

    if fiscal_year:
        clauses.append("fiscal_year = %s")
        params.append(int(fiscal_year))

    if fiscal_quarter:
        clauses.append("fiscal_quarter = %s")
        params.append(int(fiscal_quarter))

    if doc_type:
        clauses.append("doc_type = %s")
        params.append(doc_type)

    if chunk_kind:
        clauses.append("chunk_kind = %s")
        params.append(chunk_kind)

    where_str = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where_str, params


def execute_vector_search(
    conn,
    query_embedding: List[float],
    company_id: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    fiscal_quarter: Optional[int] = None,
    doc_type: Optional[str] = None,
    chunk_kind: Optional[str] = None,
    include_quarantined: bool = False,
    top_k: int = 20,
    tenant_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Executes pgvector cosine similarity search."""
    where_clause, params = build_filter_clause(
        company_id=company_id,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        doc_type=doc_type,
        chunk_kind=chunk_kind,
        include_quarantined=include_quarantined,
    )

    vec_str = "[" + ",".join(f"{x:.6f}" for x in query_embedding) + "]"
    
    # Cosine distance ordering
    sql = f"""
        SELECT chunk_id, chunk_kind, company_id, doc_id, filing_id, doc_type,
               fiscal_year, fiscal_quarter, section, authority_rank,
               trust_level, quarantined, risk_flags, text, tenant_id,
               (1 - (embedding <=> %s::vector)) AS score
        FROM chunks
        {where_clause}
        ORDER BY embedding <=> %s::vector ASC
        LIMIT %s;
    """

    full_params = [vec_str] + params + [vec_str, top_k]

    with conn.cursor() as cur:
        if tenant_id:
            cur.execute("SET LOCAL app.current_tenant = %s;", (tenant_id,))
        cur.execute(sql, full_params)
        cols = [desc[0] for desc in cur.description]
        results = [dict(zip(cols, row)) for row in cur.fetchall()]

    return results


def execute_fts_search(
    conn,
    query_text: str,
    company_id: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    fiscal_quarter: Optional[int] = None,
    doc_type: Optional[str] = None,
    chunk_kind: Optional[str] = None,
    include_quarantined: bool = False,
    top_k: int = 20,
    tenant_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Executes PostgreSQL Full-Text Search using websearch_to_tsquery and ts_rank_cd."""
    where_clause, params = build_filter_clause(
        company_id=company_id,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        doc_type=doc_type,
        chunk_kind=chunk_kind,
        include_quarantined=include_quarantined,
    )

    # First attempt: websearch_to_tsquery (strict phrasing/boolean)
    sql_websearch = f"""
        SELECT chunk_id, chunk_kind, company_id, doc_id, filing_id, doc_type,
               fiscal_year, fiscal_quarter, section, authority_rank,
               trust_level, quarantined, risk_flags, text, tenant_id,
               ts_rank_cd(tsv, websearch_to_tsquery('english', %s)) AS score
        FROM chunks
        {where_clause} {'AND' if where_clause else 'WHERE'} tsv @@ websearch_to_tsquery('english', %s)
        ORDER BY score DESC
        LIMIT %s;
    """

    with conn.cursor() as cur:
        if tenant_id:
            cur.execute("SET LOCAL app.current_tenant = %s;", (tenant_id,))

        cur.execute(sql_websearch, [query_text] + params + [query_text, top_k])
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

        if rows:
            return [dict(zip(cols, row)) for row in rows]

        # Fallback: keyword-based OR query if websearch produced zero matches
        words = [w.strip() for w in query_text.replace("'", " ").replace('"', " ").split() if len(w.strip()) > 2]
        stopwords = {"what", "was", "the", "for", "and", "with", "from", "according", "filings", "filing", "that", "did", "does"}
        keywords = [w for w in words if w.lower() not in stopwords]
        if not keywords:
            keywords = words

        if not keywords:
            return []

        or_query = " | ".join(keywords)
        sql_fallback = f"""
            SELECT chunk_id, chunk_kind, company_id, doc_id, filing_id, doc_type,
                   fiscal_year, fiscal_quarter, section, authority_rank,
                   trust_level, quarantined, risk_flags, text, tenant_id,
                   ts_rank_cd(tsv, to_tsquery('english', %s)) AS score
            FROM chunks
            {where_clause} {'AND' if where_clause else 'WHERE'} tsv @@ to_tsquery('english', %s)
            ORDER BY score DESC
            LIMIT %s;
        """
        cur.execute(sql_fallback, [or_query] + params + [or_query, top_k])
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def save_retrieval_snapshot(
    conn,
    snapshot_id: str,
    query_text: str,
    filters: Dict[str, Any],
    tenant_id: Optional[str],
    embedding_model: str,
    chunker_version: str,
    retrieved_chunks: List[Dict[str, Any]],
) -> None:
    """Implements Foundation Lock 8: Immutable audit snapshot for query replay."""
    sql = """
        INSERT INTO retrieval_snapshots (
            snapshot_id, query_text, filters, tenant_id, embedding_model,
            chunker_version, retrieved_chunks
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (snapshot_id) DO NOTHING;
    """
    with conn.cursor() as cur:
        if tenant_id:
            cur.execute("SET LOCAL app.current_tenant = %s;", (tenant_id,))
        cur.execute(sql, (
            snapshot_id,
            query_text,
            json.dumps(filters),
            tenant_id,
            embedding_model,
            chunker_version,
            json.dumps(retrieved_chunks),
        ))
    conn.commit()


def get_retrieval_snapshot(conn, snapshot_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Loads a persisted snapshot for exact query replay."""
    sql = """
        SELECT snapshot_id, query_text, filters, tenant_id, embedding_model,
               chunker_version, retrieved_chunks, created_at
        FROM retrieval_snapshots
        WHERE snapshot_id = %s;
    """
    with conn.cursor() as cur:
        if tenant_id:
            cur.execute("SET LOCAL app.current_tenant = %s;", (tenant_id,))
        cur.execute(sql, (snapshot_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))
