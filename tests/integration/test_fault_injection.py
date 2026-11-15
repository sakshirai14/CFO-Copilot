"""tests/integration/test_fault_injection.py

Integration tests for Foundation Lock Fallback (Degraded Mode & Fault Injection).
Tests all 5 specified fault scenarios:
1. model_offline -> extractive fallback, degraded=true, reason
2. model_oom -> retry then extractive fallback, degraded=true
3. vector_fail -> FTS-only degraded mode with caveat
4. db_down -> 503 envelope with Retry-After (liveness stays up)
5. queue_saturated -> 429 envelope with Retry-After
"""

import pytest
import httpx
from app.api.main import app

AUTH_HEADER = {"X-API-Key": "cfo_key_acme_dev"}


@pytest.mark.anyio
async def test_fault_model_offline_serves_extractive_fallback():
    """Model server unreachable/offline -> serves extractive fallback with degraded=True."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/chat",
            json={"question": "What qualitative disclosures did Helix Biosystems provide regarding competition?"},
            headers={**AUTH_HEADER, "X-Fault-Inject": "model_offline", "X-Request-Id": "req_fault_offline_01"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["request_id"] == "req_fault_offline_01"
        assert data["llm_calls_made"] == 0
        assert any("degraded" in c.lower() or "fallback" in c.lower() for c in data["caveats"])
        assert "FAULT_MODEL_OFFLINE" in str(data["caveats"])
        assert len(data["answer"]) > 0


@pytest.mark.anyio
async def test_fault_model_oom_serves_extractive_fallback():
    """Model server OOM / context exceeded -> serves extractive fallback with degraded=True."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/chat",
            json={"question": "According to the filings, what drove the revenue change at Cobalt Energy Partners in fiscal 2023?"},
            headers={**AUTH_HEADER, "X-Fault-Inject": "model_oom", "X-Request-Id": "req_fault_oom_01"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["request_id"] == "req_fault_oom_01"
        assert any("degraded" in c.lower() or "fallback" in c.lower() for c in data["caveats"])
        assert "FAULT_MODEL_OOM" in str(data["caveats"])


@pytest.mark.anyio
async def test_fault_vector_fail_serves_fts_degraded():
    """Embedding/vector index failure -> falls back to FTS-only with degraded caveat."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/chat",
            json={"question": "According to the filings, what drove the revenue change at Cobalt Energy Partners in fiscal 2023?"},
            headers={**AUTH_HEADER, "X-Fault-Inject": "vector_fail", "X-Request-Id": "req_fault_vec_01"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert any("degraded" in c.lower() and "vector" in c.lower() for c in data["caveats"])


@pytest.mark.anyio
async def test_fault_db_down_returns_503_retry_after_while_liveness_stays_up():
    """Database down -> returns 503 with Retry-After header while /v1/health stays 200."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Verify liveness remains 200 OK
        health_resp = await client.get("/v1/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"

        # 2. Verify chat request with DB down fault returns 503 with Retry-After
        resp = await client.post(
            "/v1/chat",
            json={"question": "What was Helix Biosystems's revenue in fiscal 2024 quarter 2?"},
            headers={**AUTH_HEADER, "X-Fault-Inject": "db_down", "X-Request-Id": "req_fault_db_01"}
        )
        assert resp.status_code == 503
        assert resp.headers.get("Retry-After") == "5"
        err = resp.json()
        assert err["code"] == "DATABASE_UNAVAILABLE"
        assert err["retry_after"] == 5
        assert err["request_id"] == "req_fault_db_01"


@pytest.mark.anyio
async def test_fault_queue_saturated_returns_429_retry_after():
    """Queue saturated -> returns 429 with Retry-After header and ErrorEnvelope."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/chat",
            json={"question": "Analyze the customer concentration risks across suppliers."},
            headers={**AUTH_HEADER, "X-Fault-Inject": "queue_saturated", "X-Request-Id": "req_fault_queue_01"}
        )
        assert resp.status_code == 429
        assert resp.headers.get("Retry-After") == "5"
        err = resp.json()
        assert err["code"] == "QUEUE_SATURATED"
        assert err["retry_after"] == 5
        assert err["request_id"] == "req_fault_queue_01"
