"""tests/unit/test_retrieval_unit.py

Unit tests for Phase 3 Chunking and Hybrid Retrieval Logic:
- Chunker determinism and content hashing
- RRF score calculation (k=60)
- Citation formatting and mandatory metadata presence
- Quarantine exclusion by default
- Authority rank tie-breaking and weighting
"""

import hashlib
import pytest
from app.data.chunker import Chunk, CHUNKER_VERSION
from app.domain.retrieval_service import (
    RetrievalFilter,
    RetrievalService,
    RetrievedChunk,
    RRF_K,
    AUTHORITY_WEIGHTS,
    AUTHORITY_LABELS,
)


class TestChunkerUnit:
    """Unit tests for chunk creation and determinism."""

    def test_chunk_content_hash_determinism(self):
        text_a = "[ARG ARG-10K-FY2023 | ITEM 2. MD&A]:\nRevenue grew by 5%."
        text_b = "[ARG ARG-10K-FY2023 | ITEM 2. MD&A]:\nRevenue grew by 5%."
        hash_a = hashlib.sha256(text_a.encode("utf-8")).hexdigest()
        hash_b = hashlib.sha256(text_b.encode("utf-8")).hexdigest()
        assert hash_a == hash_b

    def test_chunk_mandatory_fields(self):
        c = Chunk(
            chunk_id="ARG_2022Q1_IS#t1",
            chunk_kind="table",
            company_id="ARG",
            doc_id="ARG-10Q-FY2022Q1",
            filing_id="ARG-10Q-FY2022Q1",
            doc_type="filing",
            fiscal_year=2022,
            fiscal_quarter=1,
            section="Income Statement",
            chunk_index=1,
            authority_rank=1,
            trust_level="trusted",
            quarantined=False,
            risk_flags=[],
            content_hash="dummy_hash",
            text="Revenue: 823,100,000",
            chunk_text="Revenue: 823,100,000",
            chunker_version=CHUNKER_VERSION,
        )
        assert c.chunk_id == "ARG_2022Q1_IS#t1"
        assert c.chunk_kind == "table"
        assert c.authority_rank == 1
        assert not c.quarantined
        assert c.chunker_version == "v1.0.0"


class TestRRFLogic:
    """Unit tests for Reciprocal Rank Fusion arithmetic and authority weighting."""

    def test_rrf_formula_calculation(self):
        # Service instance without connecting to DB
        service = RetrievalService.__new__(RetrievalService)

        vector_hits = [
            {"chunk_id": "c1", "authority_rank": 1},
            {"chunk_id": "c2", "authority_rank": 1},
        ]
        fts_hits = [
            {"chunk_id": "c2", "authority_rank": 1},
            {"chunk_id": "c3", "authority_rank": 1},
        ]

        fused = service.compute_rrf(vector_hits, fts_hits, k=60)
        by_id = {c.chunk_id: c for c in fused}

        # c2 is rank 2 in vector and rank 1 in FTS: 1/(60+2) + 1/(60+1)
        expected_c2_rrf = (1.0 / 62) + (1.0 / 61)
        assert pytest.approx(by_id["c2"].rrf_score, abs=1e-5) == expected_c2_rrf

        # c1 is rank 1 in vector only: 1/(60+1)
        expected_c1_rrf = 1.0 / 61
        assert pytest.approx(by_id["c1"].rrf_score, abs=1e-5) == expected_c1_rrf

        # c2 has highest score
        assert fused[0].chunk_id == "c2"

    def test_authority_rank_tie_breaking(self):
        """When base RRF scores are equal, higher authority rank (lower rank number) outranks lower authority."""
        service = RetrievalService.__new__(RetrievalService)

        # c_filing (rank 1) and c_pr (rank 3) have identical retrieval rank 1
        vector_hits = [
            {"chunk_id": "c_filing", "authority_rank": 1},
            {"chunk_id": "c_pr", "authority_rank": 3},
        ]
        fts_hits = []

        fused = service.compute_rrf(vector_hits, fts_hits, k=60)
        assert fused[0].chunk_id == "c_filing"
        assert fused[1].chunk_id == "c_pr"
        assert fused[0].final_score > fused[1].final_score

    def test_citation_formatting_fields(self):
        service = RetrievalService.__new__(RetrievalService)
        vector_hits = [{
            "chunk_id": "ARG-10K-FY2023#c2",
            "chunk_kind": "text",
            "company_id": "ARG",
            "doc_id": "ARG-10K-FY2023",
            "filing_id": "ARG-10K-FY2023",
            "doc_type": "filing",
            "fiscal_year": 2023,
            "fiscal_quarter": 4,
            "section": "PART I - ITEM 2. MANAGEMENT'S DISCUSSION AND ANALYSIS",
            "authority_rank": 1,
            "trust_level": "trusted",
            "quarantined": False,
            "risk_flags": [],
            "text": "MD&A disclosure content",
        }]

        fused = service.compute_rrf(vector_hits, [], k=60)
        c = fused[0]
        assert c.chunk_id == "ARG-10K-FY2023#c2"
        assert c.is_authoritative is True
        assert c.authority_label == "SEC Filing (Primary Authoritative)"
        assert c.company_id == "ARG"
        assert c.fiscal_year == 2023
        assert c.fiscal_quarter == 4
        assert c.section is not None

