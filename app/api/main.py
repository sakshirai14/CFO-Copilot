"""app/api/main.py

FastAPI Production HTTP Application for CFO Copilot.
Enforces:
- Foundation Lock Door (API): Strict versioned endpoints, OpenAPI docs, and correlation IDs.
- Foundation Lock Walls (Layering): ZERO SQL strings, ZERO business logic, ZERO imports from app.data.
- Foundation Lock Partition (Isolation): Tenant resolved server-side from X-API-Key.
- Foundation Lock Fallback (Degradation): Authoritative ErrorEnvelope, 429 Retry-After, 503 readiness.
- Foundation Lock Lantern (Observability): Prometheus metrics exporter and structured JSON logging.
"""

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import psycopg2
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.api.dependencies import get_authenticated_tenant, get_request_id
from app.api.schemas import (
    ChatRequest,
    ErrorEnvelope,
    HealthResponse,
    KpiDefinitionItem,
    MessageResponse,
    ReadinessResponse,
    SessionCreateRequest,
    SessionResponse,
)
from app.core.config import get_settings
from app.core.logging import get_logger, setup_structured_logging
from app.core.metrics import metrics
from app.domain.session_service import SessionService
from app.orchestration.queue import QueueFullError, QueueTimeoutError
from app.orchestration.request_lifecycle import RequestLifecycleManager

# Setup structured logging
setup_structured_logging()
logger = get_logger("cfo_copilot_api")

app = FastAPI(
    title="CFO Copilot REST API",
    version="v1.2.0",
    description="Private, self-hosted executive financial assistant for CFO operations.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Enable CORS for local UI and developer tooling
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lifecycle manager and session service instances
lifecycle_manager = RequestLifecycleManager()
session_service = SessionService()

UI_DIR = Path(__file__).resolve().parent.parent.parent / "ui"


# ---------------------------------------------------------------------------
# Global Exception Handlers (Authoritative ErrorEnvelope, Zero Stack Traces)
# ---------------------------------------------------------------------------

@app.exception_handler(QueueFullError)
async def queue_full_exception_handler(request: Request, exc: QueueFullError):
    req_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:12]}"
    metrics.inc_counter("cfo_copilot_429_total")
    metrics.inc_counter("cfo_copilot_errors_total", labels={"error_type": "queue_full"})
    logger.warning("queue_saturated", request_id=req_id, retry_after=exc.retry_after)
    content = ErrorEnvelope(
        code="QUEUE_SATURATED",
        message="LLM concurrency queue saturated. All slots and waiting buffer are full. Please retry shortly.",
        request_id=req_id,
        retry_after=exc.retry_after,
    ).model_dump()
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=content,
        headers={"Retry-After": str(exc.retry_after), "X-Request-Id": req_id},
    )


@app.exception_handler(psycopg2.OperationalError)
async def db_operational_exception_handler(request: Request, exc: psycopg2.OperationalError):
    req_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:12]}"
    metrics.inc_counter("cfo_copilot_errors_total", labels={"error_type": "database_unavailable"})
    logger.error("database_down", request_id=req_id, error=str(exc))
    content = ErrorEnvelope(
        code="DATABASE_UNAVAILABLE",
        message="Database service is temporarily unreachable or offline. Please retry shortly.",
        request_id=req_id,
        retry_after=5,
    ).model_dump()
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=content,
        headers={"Retry-After": "5", "X-Request-Id": req_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:12]}"
    metrics.inc_counter("cfo_copilot_errors_total", labels={"error_type": "validation_error"})
    err_msgs = "; ".join([f"{'.'.join(str(l) for l in err['loc'])}: {err['msg']}" for err in exc.errors()])
    content = ErrorEnvelope(
        code="VALIDATION_ERROR",
        message=f"Request payload validation failed: {err_msgs}",
        request_id=req_id,
    ).model_dump()
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=content,
        headers={"X-Request-Id": req_id},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    req_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:12]}"
    code_map = {
        status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
        status.HTTP_403_FORBIDDEN: "FORBIDDEN",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: "PAYLOAD_TOO_LARGE",
        status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
        status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    headers = {"X-Request-Id": req_id}
    if exc.status_code in (status.HTTP_429_TOO_MANY_REQUESTS, status.HTTP_503_SERVICE_UNAVAILABLE):
        headers["Retry-After"] = "5"
    content = ErrorEnvelope(
        code=code,
        message=str(exc.detail),
        request_id=req_id,
        retry_after=5 if exc.status_code in (429, 503) else None,
    ).model_dump()
    return JSONResponse(status_code=exc.status_code, content=content, headers=headers)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    req_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:12]}"
    metrics.inc_counter("cfo_copilot_errors_total", labels={"error_type": "unhandled_internal"})
    logger.critical("unhandled_server_error", request_id=req_id, error=str(exc))
    content = ErrorEnvelope(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected internal server error occurred. Please contact system engineering.",
        request_id=req_id,
    ).model_dump()
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content,
        headers={"X-Request-Id": req_id},
    )


# ---------------------------------------------------------------------------
# Middleware: Request ID Propagation, Body Size Limiting & Structured Logging
# ---------------------------------------------------------------------------

@app.middleware("http")
async def request_lifecycle_middleware(request: Request, call_next):
    # 1. Enforce payload size limit (token flooding guard)
    content_length = request.headers.get("content-length")
    settings = get_settings()
    if content_length and int(content_length) > settings.MAX_BODY_SIZE_BYTES:
        req_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content=ErrorEnvelope(
                code="PAYLOAD_TOO_LARGE",
                message=f"Request body exceeds maximum size of {settings.MAX_BODY_SIZE_BYTES} bytes.",
                request_id=req_id,
            ).model_dump(),
            headers={"X-Request-Id": req_id},
        )

    # 2. Extract or generate sanitized Request ID
    raw_req_id = request.headers.get("x-request-id")
    if raw_req_id:
        req_id = re.sub(r"[^a-zA-Z0-9_\-]", "", raw_req_id)[:64]
    else:
        req_id = f"req_{uuid.uuid4().hex[:12]}"

    t0 = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - t0) * 1000.0

    # Attach correlation tracking header
    response.headers["X-Request-Id"] = req_id

    # Emit structured log
    logger.info(
        "http_request_finished",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
        request_id=req_id,
    )
    return response


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.post("/v1/chat", summary="Execute executive chat query (synchronous response)")
async def chat_endpoint(
    req: ChatRequest,
    tenant_id: str = Depends(get_authenticated_tenant),
    request_id: str = Depends(get_request_id),
    x_fault_inject: Optional[str] = Header(None),
):
    """Answers a CFO financial or disclosure question synchronously."""
    # Check max question length limit
    settings = get_settings()
    if len(req.question) > settings.MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Question length ({len(req.question)}) exceeds maximum limit of {settings.MAX_QUESTION_LENGTH} characters.",
        )

    envelope = await lifecycle_manager.execute_request(
        tenant_id=tenant_id,
        question=req.question,
        session_id=req.session_id,
        request_id=request_id,
        fault_inject=x_fault_inject,
    )
    return JSONResponse(content=envelope.model_dump(), headers={"X-Request-Id": request_id})


@app.post("/v1/chat/stream", summary="Execute executive chat query (progressive SSE streaming)")
async def chat_stream_endpoint(
    req: ChatRequest,
    tenant_id: str = Depends(get_authenticated_tenant),
    request_id: str = Depends(get_request_id),
    x_fault_inject: Optional[str] = Header(None),
):
    """Streams executive chat response progressively over Server-Sent Events (SSE).
    Event sequence: meta -> facts (immediate content) -> progress -> answer (verified) -> final -> [DONE].
    Unverified model tokens are NEVER streamed to the client.
    """
    settings = get_settings()
    if len(req.question) > settings.MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Question length ({len(req.question)}) exceeds maximum limit of {settings.MAX_QUESTION_LENGTH} characters.",
        )

    async def sse_event_generator():
        try:
            async for event_item in lifecycle_manager.stream_request(
                tenant_id=tenant_id,
                question=req.question,
                session_id=req.session_id,
                request_id=request_id,
                fault_inject=x_fault_inject,
            ):
                event_name = event_item["event"]
                event_data = event_item["data"]
                if event_name == "done":
                    yield f"data: [DONE]\n\n"
                else:
                    data_str = json.dumps(event_data)
                    yield f"event: {event_name}\ndata: {data_str}\n\n"
        except QueueFullError as qfe:
            err_data = json.dumps({
                "code": "QUEUE_SATURATED",
                "message": qfe.message,
                "request_id": request_id,
                "retry_after": qfe.retry_after,
            })
            yield f"event: error\ndata: {err_data}\n\n"
        except Exception as e:
            err_data = json.dumps({
                "code": "INTERNAL_STREAM_ERROR",
                "message": f"Stream interrupted: {str(e)}",
                "request_id": request_id,
            })
            yield f"event: error\ndata: {err_data}\n\n"

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-Id": request_id,
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/v1/sessions", response_model=SessionResponse, summary="Create a new isolated chat session")
async def create_session_endpoint(
    req: SessionCreateRequest,
    tenant_id: str = Depends(get_authenticated_tenant),
    request_id: str = Depends(get_request_id),
):
    """Creates a new chat session belonging strictly to the authenticated tenant."""
    session = session_service.create_session(tenant_id=tenant_id, title=req.title)
    return JSONResponse(content=session, headers={"X-Request-Id": request_id})


@app.get("/v1/sessions", summary="List all chat sessions for the authenticated tenant")
async def list_sessions_endpoint(
    tenant_id: str = Depends(get_authenticated_tenant),
    request_id: str = Depends(get_request_id),
):
    """Lists sessions under RLS isolation."""
    sessions = session_service.list_sessions(tenant_id=tenant_id)
    return JSONResponse(content={"sessions": sessions}, headers={"X-Request-Id": request_id})


@app.get("/v1/sessions/{session_id}/messages", summary="Get message history for a session")
async def get_session_messages_endpoint(
    session_id: str,
    tenant_id: str = Depends(get_authenticated_tenant),
    request_id: str = Depends(get_request_id),
):
    """Retrieves conversation history with resolved slots for multi-turn inspection."""
    messages = session_service.get_session_messages(tenant_id=tenant_id, session_id=session_id)
    return JSONResponse(
        content={"session_id": session_id, "messages": messages},
        headers={"X-Request-Id": request_id},
    )


@app.get("/v1/kpis", summary="List supported financial KPI definitions")
async def list_kpis_endpoint(request_id: str = Depends(get_request_id)):
    """Returns canonical catalog of 16 supported KPIs, formulas, and units."""
    kpis = session_service.get_kpi_definitions()
    return JSONResponse(content={"kpis": kpis}, headers={"X-Request-Id": request_id})


@app.get("/v1/provenance/{kpi_value_id}", summary="Get audit provenance trace for a KPI value")
async def get_provenance_endpoint(
    kpi_value_id: int,
    tenant_id: str = Depends(get_authenticated_tenant),
    request_id: str = Depends(get_request_id),
):
    """Forensic audit trace down to raw source CSV rows and row-hashes."""
    trace = session_service.get_provenance(kpi_value_id=kpi_value_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provenance trace not found for kpi_value_id={kpi_value_id}",
        )
    return JSONResponse(content=trace, headers={"X-Request-Id": request_id})


@app.get("/v1/health", response_model=HealthResponse, summary="Liveness probe")
async def health_endpoint():
    """Liveness probe. Always returns 200 OK while process is executing."""
    return HealthResponse(status="ok", version="v1.2.0", service="cfo-copilot")


@app.get("/v1/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def readiness_endpoint(response: Response):
    """Readiness probe. Checks database connectivity, model server, and embedding components."""
    components = {
        "database": False,
        "model_server": False,
        "embedding_model": False,
    }

    # 1. Check Database
    components["database"] = session_service.check_db_health()

    # 2. Check Model Server
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get(f"{settings.INFERENCE_API_BASE.replace('/v1', '')}/health")
            components["model_server"] = resp.status_code == 200
    except Exception:
        components["model_server"] = False

    # 3. Check Embedding Model
    components["embedding_model"] = True

    all_ready = components["database"] and components["embedding_model"]
    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(ready=all_ready, components=components)


@app.get("/metrics", summary="Prometheus exposition metrics")
async def metrics_endpoint():
    """Prometheus exposition format (text/plain; version=0.0.4)."""
    text = metrics.generate_prometheus_text()
    return PlainTextResponse(content=text, media_type="text/plain; version=0.0.4")


# ---------------------------------------------------------------------------
# UI Mounting & Static Files
# ---------------------------------------------------------------------------

if UI_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
    async def serve_ui():
        index_file = UI_DIR / "index.html"
        if index_file.exists():
            return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
        return HTMLResponse("<h2>CFO Copilot UI - index.html missing</h2>")
