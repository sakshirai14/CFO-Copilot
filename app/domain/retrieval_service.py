"""app/domain/retrieval_service.py

Domain Service for Hybrid Retrieval with Strict Provenance & Citations.
Implements:
- Vector search (BAAI/bge-small-en-v1.5, HNSW cosine similarity)
- Full-Text Search (PostgreSQL websearch_to_tsquery, ts_rank_cd)
- Reciprocal Rank Fusion (RRF, k=60)
- Authority weighting (Filings outrank press releases and analyst notes)
- Multi-tenant isolation (Foundation Lock 6)
- Degraded mode fallback (Foundation Lock 7)
- Immutable retrieval snapshotting (Foundation Lock 8)

Pure domain service: All database access queries are delegated to app/data/retrieval.py.
"""

import datetime
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import psycopg2

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.data.chunker import CHUNKER_VERSION
from app.data.retrieval import (
    execute_fts_search,
    execute_vector_search,
    get_retrieval_snapshot,
    save_retrieval_snapshot,
)
from fastembed import TextEmbedding

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
RRF_K = 60

AUTHORITY_WEIGHTS = {
    1: 1.00,  # 10-K, 10-Q (Authoritative SEC filing)
    2: 0.90,  # 10-Q/A (SEC Amendment)
    3: 0.60,  # Press Release (Unaudited preliminary)
    4: 0.40,  # Analyst Note / Third Party
}

AUTHORITY_LABELS = {
    1: "SEC Filing (Primary Authoritative)",
    2: "SEC Filing Amendment (Primary Authoritative)",
    3: "Press Release (Unaudited / Low Authority)",
    4: "Analyst Note / Third Party (Unverified)",
}


@dataclass
class RetrievalFilter:
    company_id: Optional[str] = None
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    doc_type: Optional[str] = None
    chunk_kind: Optional[str] = None  # 'text' or 'table'
    include_quarantined: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class RetrievedChunk:
    chunk_id: str
    chunk_kind: str
    company_id: Optional[str]
    doc_id: Optional[str]
    filing_id: Optional[str]
    doc_type: Optional[str]
    fiscal_year: Optional[int]
    fiscal_quarter: Optional[int]
    section: Optional[str]
    authority_rank: int
    authority_label: str
    is_authoritative: bool
    trust_level: str
    quarantined: bool
    risk_flags: List[str]
    text: str
    tenant_id: Optional[str] = None
    vector_rank: Optional[int] = None
    fts_rank: Optional[int] = None
    rrf_score: float = 0.0
    final_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RetrievalResult:
    snapshot_id: str
    query: str
    tenant_id: Optional[str]
    filters: Dict[str, Any]
    chunks: List[RetrievedChunk]
    degraded: bool
    degraded_reason: Optional[str]
    latency_ms: float
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["chunks"] = [c.to_dict() for c in self.chunks]
        return d


class RetrievalService:
    """Domain service orchestrating hybrid vector + FTS retrieval, RRF, and snapshots."""

    def __init__(
        self,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
        is_test: bool = False,
    ):
        self.embedding_model_name = embedding_model_name
        self.is_test = is_test
        self.settings = get_settings()
        self._model = TextEmbedding(model_name=embedding_model_name)

    def _get_connection(self, role: str = "ro"):
        params = self.settings.get_connection_params(role=role, is_test=self.is_test)
        return psycopg2.connect(**params)

    def embed_query(self, query: str) -> List[float]:
        """Generates query embedding with model-specific search prefix."""
        prefix = BGE_QUERY_PREFIX if "bge" in self.embedding_model_name.lower() else ""
        formatted_query = prefix + query
        embeddings = list(self._model.embed([formatted_query]))
        return [float(x) for x in embeddings[0]]

    def compute_rrf(
        self,
        vector_hits: List[Dict[str, Any]],
        fts_hits: List[Dict[str, Any]],
        k: int = RRF_K,
    ) -> List[RetrievedChunk]:
        """Combines vector and FTS ranked lists using Reciprocal Rank Fusion with authority weighting."""
        chunk_map: Dict[str, Dict[str, Any]] = {}
        rrf_scores: Dict[str, float] = {}
        vector_ranks: Dict[str, int] = {}
        fts_ranks: Dict[str, int] = {}

        # 1. Process Vector Hits
        for rank, hit in enumerate(vector_hits, start=1):
            cid = hit["chunk_id"]
            vector_ranks[cid] = rank
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (k + rank))
            if cid not in chunk_map:
                chunk_map[cid] = hit

        # 2. Process FTS Hits
        for rank, hit in enumerate(fts_hits, start=1):
            cid = hit["chunk_id"]
            fts_ranks[cid] = rank
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (k + rank))
            if cid not in chunk_map:
                chunk_map[cid] = hit

        # 3. Apply Authority Weighting
        retrieved = []
        for cid, data in chunk_map.items():
            base_rrf = rrf_scores[cid]
            auth_rank = data.get("authority_rank", 1)
            weight = AUTHORITY_WEIGHTS.get(auth_rank, 0.50)
            final_score = base_rrf * weight

            label = AUTHORITY_LABELS.get(auth_rank, "Other")
            is_authoritative = (auth_rank <= 2)

            retrieved.append(RetrievedChunk(
                chunk_id=cid,
                chunk_kind=data.get("chunk_kind", "text"),
                company_id=data.get("company_id"),
                doc_id=data.get("doc_id"),
                filing_id=data.get("filing_id"),
                doc_type=data.get("doc_type"),
                fiscal_year=data.get("fiscal_year"),
                fiscal_quarter=data.get("fiscal_quarter"),
                section=data.get("section"),
                authority_rank=auth_rank,
                authority_label=label,
                is_authoritative=is_authoritative,
                trust_level=data.get("trust_level", "trusted"),
                quarantined=bool(data.get("quarantined", False)),
                risk_flags=data.get("risk_flags") or [],
                text=data.get("text", ""),
                tenant_id=data.get("tenant_id"),
                vector_rank=vector_ranks.get(cid),
                fts_rank=fts_ranks.get(cid),
                rrf_score=round(base_rrf, 6),
                final_score=round(final_score, 6),
            ))

        # Sort descending by final score
        retrieved.sort(key=lambda x: x.final_score, reverse=True)
        return retrieved

    def retrieve(
        self,
        query: str,
        filters: Optional[RetrievalFilter] = None,
        top_k: int = 5,
        tenant_id: Optional[str] = None,
        include_quarantined: bool = False,
        force_vector_failure: bool = False,
        mode: str = "hybrid",  # 'hybrid', 'vector_only', 'fts_only'
    ) -> RetrievalResult:
        """Executes full hybrid retrieval with RRF, snapshots, and graceful degradation."""
        t_start = time.perf_counter()
        filters = filters or RetrievalFilter()
        inc_quarantine = include_quarantined or filters.include_quarantined

        vector_hits: List[Dict[str, Any]] = []
        fts_hits: List[Dict[str, Any]] = []
        degraded = False
        degraded_reason = None

        # 1. Vector Search
        if mode == "fts_only" or force_vector_failure:
            degraded = True
            degraded_reason = "FTS-only mode requested" if mode == "fts_only" else "Vector search simulated failure (Foundation Lock 7 test)"
        else:
            try:
                q_emb = self.embed_query(query)
                conn_ro = self._get_connection(role="ro")
                try:
                    vector_hits = execute_vector_search(
                        conn=conn_ro,
                        query_embedding=q_emb,
                        company_id=filters.company_id,
                        fiscal_year=filters.fiscal_year,
                        fiscal_quarter=filters.fiscal_quarter,
                        doc_type=filters.doc_type,
                        chunk_kind=filters.chunk_kind,
                        include_quarantined=inc_quarantine,
                        top_k=max(20, top_k * 2),
                        tenant_id=tenant_id,
                    )
                finally:
                    conn_ro.close()
            except Exception as e:
                degraded = True
                degraded_reason = f"Vector search unavailable: {str(e)}"

        # 2. Full-Text Search
        if mode != "vector_only":
            conn_ro = self._get_connection(role="ro")
            try:
                fts_hits = execute_fts_search(
                    conn=conn_ro,
                    query_text=query,
                    company_id=filters.company_id,
                    fiscal_year=filters.fiscal_year,
                    fiscal_quarter=filters.fiscal_quarter,
                    doc_type=filters.doc_type,
                    chunk_kind=filters.chunk_kind,
                    include_quarantined=inc_quarantine,
                    top_k=max(20, top_k * 2),
                    tenant_id=tenant_id,
                )
            finally:
                conn_ro.close()

        # 3. Reciprocal Rank Fusion & Ranking
        fused_chunks = self.compute_rrf(vector_hits, fts_hits, k=RRF_K)
        final_chunks = fused_chunks[:top_k]

        latency_ms = (time.perf_counter() - t_start) * 1000.0
        snapshot_id = f"snap_{uuid.uuid4().hex[:16]}"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # 4. Immutable Retrieval Snapshotting (Foundation Lock 8)
        conn_rw = self._get_connection(role="rw")
        try:
            save_retrieval_snapshot(
                conn=conn_rw,
                snapshot_id=snapshot_id,
                query_text=query,
                filters=filters.to_dict(),
                tenant_id=tenant_id,
                embedding_model=self.embedding_model_name,
                chunker_version=CHUNKER_VERSION,
                retrieved_chunks=[c.to_dict() for c in final_chunks],
            )
        finally:
            conn_rw.close()

        return RetrievalResult(
            snapshot_id=snapshot_id,
            query=query,
            tenant_id=tenant_id,
            filters=filters.to_dict(),
            chunks=final_chunks,
            degraded=degraded,
            degraded_reason=degraded_reason,
            latency_ms=round(latency_ms, 2),
            created_at=now_iso,
        )

    def replay_snapshot(self, snapshot_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Replays an exact immutable snapshot for deterministic audit verification."""
        conn_ro = self._get_connection(role="ro")
        try:
            return get_retrieval_snapshot(conn_ro, snapshot_id, tenant_id=tenant_id)
        finally:
            conn_ro.close()
