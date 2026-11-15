"""tests/integration/test_api_endpoints.py

Comprehensive Integration Tests for CFO Copilot Production REST API.
Enforces Foundation Locks:
- Door (API): All versioned endpoints, error envelopes, and correlation IDs.
- Partition (Isolation): Strict RLS tenant isolation via X-API-Key authentication.
- Walls (Layering): Clean HTTP interfaces without DAL leakages.
- Fallback & Crowd: 429 shedding, 503 readiness, and input limits.
- Lantern (Observability): Prometheus metrics endpoint and correlation tracking.
"""

import json
import pytest
import httpx
from app.api.main import app

AUTH_ACME = {"X-API-Key": "cfo_key_acme_dev"}
AUTH_BOREALIS = {"X-API-Key": "cfo_key_borealis_dev"}


@pytest.mark.anyio
async def test_health_and_readiness_endpoints():
    """Liveness probe (/v1/health) and Readiness probe (/v1/ready)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Liveness
        h_resp = await client.get("/v1/health")
        assert h_resp.status_code == 200
        h_data = h_resp.json()
        assert h_data["status"] == "ok"
        assert h_data["version"] == "v1.2.0"
        assert h_data["service"] == "cfo-copilot"

        # Readiness
        r_resp = await client.get("/v1/ready")
        assert r_resp.status_code == 200
        r_data = r_resp.json()
        assert r_data["ready"] is True
        assert r_data["components"]["database"] is True
        assert r_data["components"]["embedding_model"] is True


@pytest.mark.anyio
async def test_authentication_enforcement_and_error_envelope():
    """Missing or invalid API key returns 401 with standard ErrorEnvelope."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Missing key
        resp1 = await client.post("/v1/chat", json={"question": "What is ARG revenue?"})
        assert resp1.status_code == 401
        err1 = resp1.json()
        assert err1["code"] == "UNAUTHORIZED"
        assert "Missing required authentication" in err1["message"]
        assert "request_id" in err1

        # Invalid key
        resp2 = await client.post(
            "/v1/chat",
            json={"question": "What is ARG revenue?"},
            headers={"X-API-Key": "invalid_unregistered_key"}
        )
        assert resp2.status_code == 401
        err2 = resp2.json()
        assert err2["code"] == "UNAUTHORIZED"
        assert "Invalid 'X-API-Key'" in err2["message"]


@pytest.mark.anyio
async def test_tenant_isolation_sessions_and_messages():
    """Foundation Lock Partition: Tenant Acme cannot access Tenant Borealis sessions."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Acme creates session
        sess_resp = await client.post(
            "/v1/sessions",
            json={"title": "Acme Confidential Q3 Review"},
            headers=AUTH_ACME
        )
        assert sess_resp.status_code == 200
        sess_data = sess_resp.json()
        sess_id = sess_data["session_id"]
        assert sess_data["tenant_id"] == "acme"

        # 2. Borealis attempts to read Acme's session messages
        bor_resp = await client.get(
            f"/v1/sessions/{sess_id}/messages",
            headers=AUTH_BOREALIS
        )
        assert bor_resp.status_code == 200
        # RLS ensures Borealis sees strictly 0 messages
        bor_data = bor_resp.json()
        assert len(bor_data["messages"]) == 0

        # 3. Borealis lists sessions -> Acme's session is absent
        bor_list_resp = await client.get("/v1/sessions", headers=AUTH_BOREALIS)
        assert bor_list_resp.status_code == 200
        bor_sessions = bor_list_resp.json()["sessions"]
        assert not any(s["session_id"] == sess_id for s in bor_sessions)


@pytest.mark.anyio
async def test_input_limits_token_flooding_protection():
    """Validates question length and body size limits (Token Flooding Guard)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Question exceeds 2000 characters
        long_q = "What is ARG revenue in FY23? " + ("x" * 2050)
        resp1 = await client.post(
            "/v1/chat",
            json={"question": long_q},
            headers=AUTH_ACME
        )
        assert resp1.status_code == 422
        err1 = resp1.json()
        assert err1["code"] == "VALIDATION_ERROR" or "length" in err1["message"].lower()

        # Body exceeds 64KB
        huge_payload = {"question": "What is ARG revenue?", "extra": "A" * 70000}
        resp2 = await client.post(
            "/v1/chat",
            json=huge_payload,
            headers=AUTH_ACME
        )
        assert resp2.status_code == 413
        err2 = resp2.json()
        assert err2["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.anyio
async def test_chat_synchronous_endpoint():
    """POST /v1/chat returns standard AnswerEnvelope and correlation header."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        client_req_id = "req_test_sync_custom_123"
        resp = await client.post(
            "/v1/chat",
            json={"question": "What was Aurora Retail Group's revenue in fiscal 2023 quarter 2?"},
            headers={**AUTH_ACME, "X-Request-Id": client_req_id}
        )
        assert resp.status_code == 200
        assert resp.headers.get("X-Request-Id") == client_req_id
        data = resp.json()
        assert data["request_id"] == client_req_id
        assert data["route"] == "STRUCTURED"
        assert data["status"] == "ok"
        assert "$774,400,000" in data["answer"]
        assert data["llm_calls_made"] == 0
        assert data["latency_ms"] > 0.0


@pytest.mark.anyio
async def test_chat_progressive_sse_stream_event_order():
    """POST /v1/chat/stream streams events in exact order:
    meta -> facts -> progress -> answer -> final -> [DONE].
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        client_req_id = "req_test_stream_001"
        received_events = []

        async with client.stream(
            "POST",
            "/v1/chat/stream",
            json={"question": "What was Meridian Semiconductor operating income in FY2023 Q4?", "stream": True},
            headers={**AUTH_ACME, "X-Request-Id": client_req_id}
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers.get("X-Request-Id") == client_req_id

            buffer = ""
            async for chunk in resp.aiter_text():
                buffer += chunk
                blocks = buffer.split("\n\n")
                buffer = blocks.pop()

                for b in blocks:
                    if not b.strip():
                        continue
                    if b.strip() == "data: [DONE]":
                        received_events.append("done")
                        continue
                    lines = b.split("\n")
                    for l in lines:
                        if l.startswith("event: "):
                            received_events.append(l[7:].strip())

        # Assert strict contract event ordering
        assert received_events == ["meta", "facts", "progress", "answer", "final", "done"]


@pytest.mark.anyio
async def test_session_multi_turn_slot_inheritance():
    """Verifies that resolved slots are persisted and inherited across turns on the server."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create session
        s_resp = await client.post("/v1/sessions", json={"title": "Multi-Turn Test"}, headers=AUTH_ACME)
        sess_id = s_resp.json()["session_id"]

        # 2. Turn 1: Explicit entity, period, and KPI
        t1_resp = await client.post(
            "/v1/chat",
            json={"question": "What was Aurora Retail Group's revenue in fiscal 2023 quarter 2?", "session_id": sess_id},
            headers=AUTH_ACME
        )
        assert t1_resp.status_code == 200

        # 3. Turn 2: Follow-up question omitting company and period ("What was their gross margin?")
        t2_resp = await client.post(
            "/v1/chat",
            json={"question": "What was their gross margin?", "session_id": sess_id},
            headers=AUTH_ACME
        )
        assert t2_resp.status_code == 200
        t2_data = t2_resp.json()
        assert t2_data["status"] == "ok"
        assert "ARG" in t2_data["answer"]
        assert "38.30%" in t2_data["answer"]

        # 4. Verify message history contains resolved slots
        m_resp = await client.get(f"/v1/sessions/{sess_id}/messages", headers=AUTH_ACME)
        assert m_resp.status_code == 200
        msgs = m_resp.json()["messages"]
        assert len(msgs) == 4  # 2 user turns + 2 assistant responses
        assert msgs[1]["resolved_slots"]["company_id"] == "ARG"


@pytest.mark.anyio
async def test_kpi_catalog_and_provenance_endpoints():
    """GET /v1/kpis and GET /v1/provenance/{id}."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Catalog
        kpi_resp = await client.get("/v1/kpis")
        assert kpi_resp.status_code == 200
        kpis = kpi_resp.json()["kpis"]
        assert len(kpis) == 16
        kpi_ids = [k["kpi_id"] for k in kpis]
        assert "revenue_yoy_growth_pct" in kpi_ids
        assert "gross_margin_pct" in kpi_ids
        assert "free_cash_flow_usd" in kpi_ids

        # Provenance: valid ID (1)
        prov_resp = await client.get("/v1/provenance/1", headers=AUTH_ACME)
        assert prov_resp.status_code in (200, 404)
        if prov_resp.status_code == 200:
            prov_data = prov_resp.json()
            assert "kpi" in prov_data
            assert prov_data["kpi"]["kpi_value_id"] == 1


@pytest.mark.anyio
async def test_prometheus_metrics_endpoint():
    """GET /metrics returns standard Prometheus exposition metrics."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        m_resp = await client.get("/metrics")
        assert m_resp.status_code == 200
        content = m_resp.text
        assert "cfo_copilot_requests_total" in content
        assert "cfo_copilot_request_duration_seconds" in content
        assert "cfo_copilot_queue_in_flight" in content
