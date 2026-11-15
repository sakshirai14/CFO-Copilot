# LOCKS.md: Canonical Foundation Locks Audit & Verification Status

> **Platform**: CFO Copilot on a Budget  
> **Phase**: Phase 5b Corrections & Phase 6 Target  
> **Date**: 2026-11-15  

This matrix tracks the architectural enforcement, implementation details, and empirical test proofs for the **11 Foundation Locks** defined in the project specification (`AGENT_BRIEF.md`).

---

## Foundation Locks Matrix

| Foundation Lock | Status | Implementation File & Function | Empirical Test Proof |
| :--- | :---: | :--- | :--- |
| **1. Door (API)** | **PARTIAL** (Complete in Phase 6) | `app/api/main.py`: `create_app()`<br>`app/domain/agent_envelope.py`: `AnswerEnvelope` schema | `tests/unit/test_agents.py`<br>`tests/integration/test_offline_survivability.py` (Full FastAPI integration in Phase 6 Step 1) |
| **2. Walls (Layering)** | **DONE** | `app/agents/`: Layer contains ZERO SQL strings, ZERO database drivers, and ZERO tool authority.<br>`app/data/sql/kpis/`: Pure SQL KPI calculations. | `tests/unit/test_architecture.py`: AST architectural boundary test asserts zero SQL keywords in `app/agents` and zero tools on `AnswerWriterAgent`. |
| **3. Crowd (Concurrency)** | **PARTIAL** (Queue in Phase 6) | `scripts/benchmark_serving_rigorous.py`: 16 concurrent slots (`-np 16 -c 65536`).<br>`app/orchestration/queue.py`: Bounded concurrency queue (Phase 6 Step 2). | `scripts/benchmark_prefix_50tails.py`: Measured streaming TTFT across 50 distinct tails (p50: 99.72 ms).<br>`docs/evidence/serving_benchmark_rigorous.md`. |
| **4. Echo (Idempotency)** | **DONE** | `app/data/ingest.py`: Deterministic SHA-256 row hashes; SQL `ON CONFLICT DO NOTHING / UPDATE`.<br>`app/data/kpi_calculator.py`: `compute_all_kpis()`. | `tests/integration/test_phase1_integration.py::TestIngestionIdempotency`: Re-running ingestion yields $\Delta = 0$ rows.<br>`scripts/compute_kpis.py`: 2,304 values with zero drift. |
| **5. Ledger (Data Integrity)** | **DONE** | `app/data/normalizer.py`: `normalize_line_item()` (unit scale factors, sign multipliers).<br>`app/data/effective.py`: Conflict policy rules R1-R12.<br>`app/data/provenance.py`: `get_kpi_provenance()`. | `tests/integration/test_conflict_policy.py::TestConflictPolicyRules`: Verifies rules R1-R12.<br>`docs/evidence/differential_test_results.txt`: 100.00% match against independent Pandas engine. |
| **6. Partition (Isolation)** | **DONE** | PostgreSQL Row-Level Security (`FORCE ROW LEVEL SECURITY`).<br>Three segregated DB roles: `cfo_owner`, `app_rw`, `app_ro`.<br>`tests/conftest.py`: Localhost network guard. | `tests/integration/test_phase1_integration.py::TestTenantIsolationRLS`<br>`tests/integration/test_retrieval_integration.py::test_tenant_canary_isolation`: 0 leaked canary records across tenants. |
| **7. Fallback (Degraded Mode)** | **DONE** | `app/domain/answer_composer.py`: `compose_fallback_answer()` (extractive fallback quoting verbatim passages with citations).<br>`app/domain/retrieval_service.py`: FTS-only vector degradation. | `tests/integration/test_offline_survivability.py`: 100% structured survival with model offline.<br>`tests/unit/test_agents.py::test_extractive_fallback_quoted_passages`. |
| **8. Black Box (Reproducibility)** | **PARTIAL** (Full replay in Phase 6) | `app/data/retrieval.py`: `save_retrieval_snapshot()`, `get_retrieval_snapshot()`.<br>`scripts/replay.py`: Request replay harness (Phase 6 Step 5). | `tests/integration/test_retrieval_integration.py::test_snapshot_replay`: Exact chunk replay from immutable database snapshot ID. |
| **9. Lantern (Observability)** | **PENDING** (Phase 6 Step 6) | `app/core/logging.py`: Structlog JSON with `request_id`, `tenant`, `latency`.<br>`app/core/metrics.py`: Prometheus metrics exporter. | Scheduled for implementation in Phase 6 Step 6 (`GET /metrics`). |
| **10. Proof (Testing)** | **DONE** | Automated pytest CI suite covering unit, domain, SQL conflict policy, RLS isolation, golden set evaluation, AST boundaries, and ADK offline evals. | **104 automated tests passing** (`tests/unit/`, `tests/integration/`).<br>`make test`, `make adk-eval`. |
| **11. Switch (Setup)** | **DONE** | `docker-compose.yml`: One-command containerized setup (PostgreSQL 16 + pgvector).<br>Zero repo secrets: `.env` mode 600 git-ignored, `.env.example` placeholders.<br>`scripts/download_models.sh`: Local open-weight models. | `make up`, `make down`, `make test`. Verified offline execution with no external API calls. |
