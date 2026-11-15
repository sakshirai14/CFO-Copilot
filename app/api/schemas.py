"""app/api/schemas.py

Pydantic v2 Request & Response Schemas for the CFO Copilot REST API.
Enforces Foundation Lock Door (API) and Grounded-Answer contract.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ErrorEnvelope(BaseModel):
    """Authoritative API Error Envelope. No stack traces ever returned."""
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Executive-grade error description")
    request_id: str = Field(..., description="Unique correlation tracking ID")
    retry_after: Optional[int] = Field(None, description="Suggested retry backoff in seconds")


class ChatRequest(BaseModel):
    """Executive chat query payload."""
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language question regarding company financial KPIs or filings."
    )
    session_id: Optional[str] = Field(None, description="Optional chat session ID for multi-turn context.")
    stream: bool = Field(False, description="Whether to stream response via SSE.")


class SessionCreateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200, description="Optional title for the chat session.")


class SessionResponse(BaseModel):
    session_id: str
    tenant_id: str
    title: str
    created_at: str
    updated_at: Optional[str] = None


class MessageResponse(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    resolved_slots: Optional[Dict[str, Any]] = None
    created_at: str


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "v1.2.0"
    service: str = "cfo-copilot"


class ReadinessResponse(BaseModel):
    ready: bool
    components: Dict[str, bool]


class KpiDefinitionItem(BaseModel):
    kpi_id: str
    kpi_name: str
    formula: str
    unit: str
    notes: Optional[str] = None
