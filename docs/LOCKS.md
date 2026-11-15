# LOCKS.md: Canonical Foundation Locks Audit & Verification Status

> **Platform**: CFO Copilot on a Budget  
> **Phase**: Phase 6 Complete  
> **Date**: 2026-11-15  

This matrix tracks the architectural enforcement, implementation details, and empirical test proofs for the **11 Foundation Locks** defined in the project specification (`AGENT_BRIEF.md`).

---

## Foundation Locks Matrix

| Foundation Lock | Status | Implementation File & Function | Empirical Test Proof |
| :--- | :---: | :--- | :--- |
| **1. Door (API)** | **DONE** | `app/api/main.py`: FastAPI app with versioned routes (`/v1/chat`, `/v1/chat/stream`, `/v1/sessions`, `/v1/kpis`, `/v1/provenance/{id}`, `/v1/health`, `/v1/ready`, `/metrics`).<br>`app/api/schemas.py`: `ErrorEnvelope` (no stack traces). | `tests/integration/test_api_endpoints.py`: All 9 endpoint tests passing with authoritative error envelopes and `X-Request-Id` correlation. |
| **2. Walls (Layering)** | **DONE** | `app/agents/`: Layer contains ZERO SQL strings, ZERO database drivers, and ZERO tool authority.<br>`app/api/`: ZERO imports from `app.data`, ZERO SQL keywords.<br>`app/orchestration/`: ZERO SQL keywords. | `tests/unit/test_architecture.py`: 5 AST boundary tests asserting strict zero-SQL and forbidden import rules across agents, api, and orchestration. |
| **3. Crowd (Concurrency)** | **DONE** | `app/orchestration/queue.py`: `BoundedLlmQueue` with 16 in-flight slots and 16 waiting buffer.<br>`app/orchestration/request_lifecycle.py`: 100% queue bypass for structured queries; instant 429 shedding with `Retry-After: 5`. | `scripts/load_test.py`: 16 concurrent sessions, 3-minute load test, and 45-request burst saturation test (`benchmarks/results/load_test.json`). |
| **4. Echo (Idempotency)** | **DONE** | `app/data/ingest.py`: Deterministic SHA-256 row hashes; SQL `ON CONFLICT DO NOTHING / UPDATE`.<br>`app/data/kpi_calculator.py`: `compute_all_kpis()`. | `tests/integration/test_phase1_integration.py::TestIngestionIdempotency`: Re-running ingestion yields $\Delta = 0$ rows.<br>`scripts/compute_kpis.py`: 2,304 values with zero drift. |
| **5. Ledger (Data Integrity)** | **DONE** | `app/data/normalizer.py`: `normalize_line_item()` (unit scale factors, sign multipliers).<br>`app/data/effective.py`: Conflict policy rules R1-R12.<br>`app/data/provenance.py`: `get_kpi_provenance()`. | `tests/integration/test_conflict_policy.py::TestConflictPolicyRules`: Verifies rules R1-R12.<br>`docs/evidence/differential_test_results.txt`: 100.00% match against independent Pandas engine. |
| **6. Partition (Isolation)** | **DONE** | PostgreSQL Row-Level Security (`FORCE ROW LEVEL SECURITY`).<br>Three segregated DB roles: `cfo_owner`, `app_rw`, `app_ro`.<br>`app/api/dependencies.py`: Server-side API key to tenant mapping (`X-API-Key`). | `tests/integration/test_api_endpoints.py::test_tenant_isolation_sessions_and_messages`: Tenant Acme cannot view Tenant Borealis data.<br>`tests/integration/test_retrieval_integration.py`: 0 canary leakage. |
| **7. Fallback (Degraded Mode)** | **DONE** | `app/domain/answer_composer.py`: `compose_fallback_answer()` (extractive fallback quoting verbatim passages with citations).<br>`app/domain/retrieval_service.py`: FTS-only vector degradation.<br>`app/orchestration/request_lifecycle.py`: Fault injection handling. | `tests/integration/test_fault_injection.py`: All 5 fault scenarios passing (model offline, model OOM, vector fail, DB down 503, queue 429).<br>`scripts/fault_demo.sh`. |
| **8. Black Box (Reproducibility)** | **DONE** | `app/data/retrieval.py`: `save_retrieval_snapshot()`, `get_retrieval_snapshot()`.<br>`scripts/replay.py`: Request replay harness reloading facts, prompt hash, model hash, and diffing output. | `scripts/replay.py --batch 20`: Exact-match diff verification across logged requests in `answer_log`. Refuses execution on hash drift. |
| **9. Lantern (Observability)** | **DONE** | `app/core/logging.py`: Structlog JSON with `request_id`, `tenant`, `route`, `status`, `latency`.<br>`app/core/metrics.py`: Prometheus exporter exposing `/metrics` with standard histograms and counters. | `tests/integration/test_api_endpoints.py::test_prometheus_metrics_endpoint`: Exposes request counters, queue gauges, latency summaries. |
| **10. Proof (Testing)** | **DONE** | Automated pytest CI suite covering unit, domain, SQL conflict policy, RLS isolation, golden set evaluation, AST boundaries, fault injection, and API integration. | **122 automated tests passing** (`tests/unit/`, `tests/integration/`).<br>`make test`. |
| **11. Switch (Setup)** | **DONE** | `docker-compose.yml`: One-command containerized setup (PostgreSQL 16 + pgvector).<br>Zero repo secrets: `.env` mode 600 git-ignored, `.env.example` placeholders.<br>`Makefile`: `make up`, `make down`, `make run-api`, `make load-test`. | Verified offline execution with no external API calls. |
