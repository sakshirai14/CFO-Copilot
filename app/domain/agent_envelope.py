"""app/domain/agent_envelope.py

Typed data models for the CFO Copilot Agent Architecture.
Defines the authoritative AnswerEnvelope ("Show Your Work" contract).
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RouteType(str, Enum):
    STRUCTURED = "STRUCTURED"
    UNSTRUCTURED = "UNSTRUCTURED"
    MIXED = "MIXED"
    REFUSAL = "REFUSAL"
    CHITCHAT = "CHITCHAT"


class AnswerStatus(str, Enum):
    OK = "ok"
    MISSING_DATA = "missing_data"
    REFUSED = "refused"
    UNVERIFIED = "unverified"
    ERROR = "error"


class FactItem(BaseModel):
    fact_id: str
    company_id: Optional[str] = None
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    kpi_id: Optional[str] = None
    canonical_item: Optional[str] = None
    statement: Optional[str] = None
    value: Optional[float] = None
    unit: str = "USD"
    basis: str = "as_restated"
    restated: bool = False
    status: str = "ok"
    reason: Optional[str] = None
    text: str
    source_filing: Optional[str] = None
    input_line_item_ids: List[int] = Field(default_factory=list)


class VerificationResult(BaseModel):
    is_valid: bool
    reasons: List[str] = Field(default_factory=list)
    ungrounded_numbers: List[str] = Field(default_factory=list)
    cited_fact_ids: List[str] = Field(default_factory=list)


class ResolvedQuery(BaseModel):
    question: str
    route: RouteType
    company_ids: List[str] = Field(default_factory=list)
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    prior_year: Optional[int] = None
    prior_quarter: Optional[int] = None
    kpi_id: Optional[str] = None
    basis: str = "as_restated"
    is_comparative: bool = False
    refusal_reason: Optional[str] = None
    text_search_query: Optional[str] = None


class AnswerEnvelope(BaseModel):
    request_id: str
    question: str
    route: RouteType
    status: AnswerStatus
    answer: str
    llm_calls_made: int = 0
    latency_ms: float = 0.0
    facts_used: List[FactItem] = Field(default_factory=list)
    caveats: List[str] = Field(default_factory=list)
    provenance_traces: List[Dict[str, Any]] = Field(default_factory=list)
    verification: VerificationResult
